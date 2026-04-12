"""
Main analysis pipeline — data-driven market analysis.

Alpha Vantage provides the WHAT (tickers, sentiment, sector movement).
The LLM provides the WHY (causal chains, reasoning, evaluation).

Full analysis phases:
  1. Fetch news + aggregate ticker data from articles
  2. LLM groups articles into events
  3. Market snapshot (sectors, movers, indicators, commodities)
  4. Rank events by severity + market confidence, pick top N
  5. LLM causal analysis per event (chains + sectors)
  6. Profile candidate tickers (deduped) + per-event LLM stock evaluation
  7. Synthesis — merge all per-event evaluations into one report
"""

from __future__ import annotations

import json
import logging
from typing import Dict, Any, List, Tuple

from app.clients import alpha_vantage
from app.clients import ollama
from app.db import database as db

logger = logging.getLogger(__name__)


def _compute_trade_setup(score: Dict, current_price: float, atr: float, levels: list) -> Optional[Dict]:
    """Compute actionable trade parameters — entry, stop, target — for the UI."""
    signal = score.get("signal", "neutral")
    if signal not in ("buy", "strong_buy", "sell", "strong_sell"):
        return None

    SLIPPAGE = 0.001

    is_short = signal in ("sell", "strong_sell")
    direction = "short" if is_short else "long"

    if is_short:
        entry = round(current_price * (1 - SLIPPAGE), 2)
    else:
        entry = round(current_price * (1 + SLIPPAGE), 2)

    # Structural stop: nearest support (long) or resistance (short)
    stop = None
    stop_type = "atr"
    buffer = min(atr * 0.5, entry * 0.005) if atr > 0 else entry * 0.005

    if not is_short:
        supports = sorted(
            [l for l in levels if l.get("type") == "support" and l["price"] < entry],
            key=lambda l: -l["price"],
        )
        if supports:
            stop = round(supports[0]["price"] - buffer, 2)
            stop_type = "support"
    else:
        resistances = sorted(
            [l for l in levels if l.get("type") == "resistance" and l["price"] > entry],
            key=lambda l: l["price"],
        )
        if resistances:
            stop = round(resistances[0]["price"] + buffer, 2)
            stop_type = "resistance"

    # Fallback: ATR-based
    if stop is None:
        if atr > 0:
            stop = round(entry - 2.5 * atr, 2) if not is_short else round(entry + 2.5 * atr, 2)
        else:
            stop = round(entry * (1 - 0.07), 2) if not is_short else round(entry * (1 + 0.07), 2)

    stop_distance = abs(entry - stop)
    risk_per_share = round(stop_distance, 2)

    return {
        "direction": direction,
        "viable": True,
        "entry": entry,
        "stop": stop,
        "stop_type": stop_type,
        "target": None,
        "target_type": "trailing",
        "risk_per_share": risk_per_share,
        "atr": round(atr, 2) if atr else None,
    }


# ── Public API ───────────────────────────────────────────────────────────────

def analyze_stock_fundamentals(ticker: str) -> Dict[str, Any]:
    """
    Standalone fundamental analysis — NOT connected to the scoring/signaling system.

    Fetches company overview, financial statements, earnings, and ownership data
    (7 AV calls), runs the programmatic fundamentals engine across 7 silos,
    then calls LLM for a narrative.

    Returns: company info, 7 silo analyses, LLM narrative, duration.
    """
    import time as _time
    from app.analysis import fundamentals as fa

    start = _time.time()
    ticker = ticker.upper().strip()

    # ── Fetch data (7 AV calls) ──────────────────────────────────────────────
    logger.info("[%s] Fundamentals: fetching overview", ticker)
    overview = alpha_vantage.get_company_overview(ticker)
    if not overview or not overview.get("name"):
        return {"error": f"Could not fetch company data for {ticker}"}

    quote = alpha_vantage.get_stock_quote(ticker)
    current_price = float(quote["price"]) if quote and quote.get("price") else 0

    logger.info("[%s] Fundamentals: fetching financial statements", ticker)
    income = alpha_vantage.get_income_statement(ticker)
    balance_sheet = alpha_vantage.get_balance_sheet(ticker)
    cash_flow = alpha_vantage.get_cash_flow(ticker)
    earnings = alpha_vantage.get_earnings(ticker)

    logger.info("[%s] Fundamentals: fetching ownership data", ticker)
    insider_txns = alpha_vantage.get_insider_transactions(ticker)
    institutional = alpha_vantage.get_institutional_holdings(ticker)

    # ── Run fundamentals engine (all programmatic) ───────────────────────────
    logger.info("[%s] Fundamentals: running analysis engine", ticker)
    analysis = fa.run_fundamental_analysis(
        overview=overview,
        income=income,
        balance_sheet=balance_sheet,
        cash_flow=cash_flow,
        earnings=earnings,
        insider_txns=insider_txns,
        institutional=institutional,
        current_price=current_price,
    )

    # ── LLM narrative ────────────────────────────────────────────────────────
    logger.info("[%s] Fundamentals: generating LLM narrative", ticker)
    fundamental_text = fa.format_fundamentals_for_llm(analysis)
    llm_result = ollama.narrate_fundamentals(fundamental_text)
    narrative = llm_result.get("data")
    if not narrative:
        logger.warning("[%s] Fundamentals LLM narrative failed: %s", ticker, llm_result.get("error"))

    return {
        "ticker": ticker,
        "name": overview.get("name", ""),
        "sector": overview.get("sector", ""),
        "industry": overview.get("industry", ""),
        "current_price": current_price,
        "quote": quote,
        **analysis,
        "narrative": narrative,
        "duration_seconds": round(_time.time() - start, 1),
        "error": llm_result.get("error") if not narrative else None,
    }


def analyze_stock_price_action(ticker: str) -> Dict[str, Any]:
    """
    Per-ticker price action analysis with multi-timeframe confluence scoring.

    Fetches price data + indicators from AV (9 calls), runs the programmatic
    price action engine (swing detection, structure, S/R, patterns, volume,
    scoring), then calls LLM to narrate the score.

    Returns everything the frontend needs: chart data, score, narrative.
    """
    import time as _time
    from app.analysis import price_action as pa

    start = _time.time()
    ticker = ticker.upper().strip()

    # ── Phase 1: Fetch data from Alpha Vantage (9 calls) ──
    logger.info("[%s] Fetching quote and overview", ticker)
    quote = alpha_vantage.get_stock_quote(ticker)
    if not quote or not quote.get("price"):
        return {"error": f"Could not fetch quote for {ticker}"}

    overview = alpha_vantage.get_company_overview(ticker)
    current_price = float(quote["price"])

    # Extended hours price (pre-market / after-hours)
    logger.info("[%s] Fetching extended hours price", ticker)
    extended = alpha_vantage.get_extended_hours_price(ticker)

    logger.info("[%s] Fetching institutional holdings and insider transactions", ticker)
    institutional = alpha_vantage.get_institutional_holdings(ticker)
    insider_txns = alpha_vantage.get_insider_transactions(ticker)

    logger.info("[%s] Fetching daily and weekly prices", ticker)
    daily_prices_desc = alpha_vantage.get_daily_prices(ticker, compact=False)
    weekly_prices_desc = alpha_vantage.get_weekly_prices(ticker)

    if not daily_prices_desc:
        return {"error": f"No daily price data for {ticker}"}

    # Ascending order for the engine (oldest first)
    # 452 bars = 252 display bars + 200 warmup for MA200 to cover the full chart
    daily_asc = list(reversed(daily_prices_desc))[-452:]
    weekly_asc = list(reversed(weekly_prices_desc[:200]))  # Last ~4 years of weekly data

    logger.info("[%s] Fetching RSI and MACD", ticker)
    rsi_raw = alpha_vantage.get_rsi(ticker)
    macd_raw = alpha_vantage.get_macd(ticker)

    # ── Phase 2: Run price action engine (all programmatic) ──
    logger.info("[%s] Running price action engine", ticker)

    # Display window = last 252 bars (swings, structure, patterns use this)
    # Full 452 bars used only for MA warmup
    daily_display = daily_asc[-252:]

    # Swing points — detect on display window so all markers are visible
    daily_swings = pa.detect_swing_points(daily_display, lookback=3)
    weekly_swings = pa.detect_swing_points(weekly_asc, lookback=3)

    # Market structure
    daily_structure = pa.classify_market_structure(daily_swings)
    weekly_structure = pa.classify_market_structure(weekly_swings)

    # Moving averages — use full 452 bars for warmup so MA200 covers the display window
    ma_50_series = pa.compute_sma(daily_asc, 50)
    ma_200_series = pa.compute_sma(daily_asc, 200)
    ma_50_value = ma_50_series[-1]["value"] if ma_50_series else None
    ma_200_value = ma_200_series[-1]["value"] if ma_200_series else None

    # MA-based signals (position, alignment, crossovers)
    ma_signals = pa.compute_ma_signals(ma_50_series, ma_200_series, current_price)

    # Support & Resistance
    levels = pa.find_support_resistance(
        daily_swings, weekly_swings, current_price,
        ma_50=ma_50_value, ma_200=ma_200_value,
    )

    # Candlestick patterns — use display window
    patterns = pa.detect_candlestick_patterns(daily_display, levels)

    # Volume analysis — use display window
    volume = pa.analyze_volume(daily_display)

    # ATR (14) — used for proximity thresholds, gap detection, strategies
    atr_value = pa.compute_atr(daily_display, period=14)

    # Gap detection
    gaps = pa.detect_gaps(daily_display, levels, atr=atr_value)

    # ── Phase 2.5: Fetch fundamental & smart money data ──
    logger.info("[%s] Fetching earnings and income data", ticker)
    earnings_raw = alpha_vantage.get_earnings(ticker)
    income_raw = alpha_vantage.get_income_statement(ticker)

    # Sector relative strength: stock vs sector ETF over last 5 days
    sector_change_pct = None
    sector = overview.get("sector", "")
    _sector_etf_map = {
        "Technology": "XLK", "Healthcare": "XLV", "Financials": "XLF",
        "Energy": "XLE", "Consumer Discretionary": "XLY", "Consumer Staples": "XLP",
        "Industrials": "XLI", "Materials": "XLB", "Utilities": "XLU",
        "Real Estate": "XLRE", "Communication Services": "XLC",
    }
    # AV returns sectors in ALL CAPS — normalize to title case for lookup
    etf_ticker = _sector_etf_map.get(sector) or _sector_etf_map.get(sector.title())
    if etf_ticker:
        etf_quote = alpha_vantage.get_stock_quote(etf_ticker)
        if etf_quote and etf_quote.get("change_percent"):
            try:
                sector_change_pct = float(str(etf_quote["change_percent"]).replace("%", ""))
            except (ValueError, TypeError):
                pass

    # ── Phase 2.6: Lightweight market regime check ──
    logger.info("[%s] Checking market regime (VIX + sector rotation)", ticker)
    vix_quote = alpha_vantage.get_stock_quote("VIXY")
    _mini_snapshot = {
        "vix": vix_quote if vix_quote else {},
        "sectors": {"realtime": {}},
    }
    # Reuse the sector ETF quote we already fetched for relative strength
    if etf_ticker and sector_change_pct is not None:
        _mini_snapshot["sectors"]["realtime"][sector] = f"{sector_change_pct}%"
    # Fetch a couple more sector ETFs for rotation detection
    for _s_name, _s_etf in [("Technology", "XLK"), ("Utilities", "XLU"), ("Consumer Staples", "XLP")]:
        if _s_etf != etf_ticker:
            _sq = alpha_vantage.get_stock_quote(_s_etf)
            if _sq and _sq.get("change_percent"):
                _mini_snapshot["sectors"]["realtime"][_s_name] = _sq["change_percent"]

    market_regime = pa.classify_market_regime(_mini_snapshot)
    logger.info("[%s] Market regime: %s (score %d)", ticker, market_regime["label"], market_regime["score"])

    # ── Phase 3: Confluence scoring ──
    rsi_data = rsi_raw.get("data", [])
    macd_data = macd_raw.get("data", [])

    # RSI divergence — compares price swing direction vs RSI swing direction
    rsi_divergence = pa.detect_rsi_divergence(daily_swings, rsi_data)
    if rsi_divergence.get("bullish") or rsi_divergence.get("bearish"):
        logger.info("[%s] RSI divergence: %s (%s)", ticker, "bullish" if rsi_divergence["bullish"] else "bearish", rsi_divergence.get("strength"))

    score = pa.compute_confluence_score(
        weekly_structure=weekly_structure,
        daily_structure=daily_structure,
        levels=levels,
        patterns=patterns,
        volume=volume,
        current_price=current_price,
        rsi_data=rsi_data,
        macd_data=macd_data,
        ma_signals=ma_signals,
        rsi_divergence=rsi_divergence,
        atr=atr_value,
        gaps=gaps,
        insider_txns=insider_txns,
        institutional=institutional,
        earnings=earnings_raw,
        income=income_raw,
        daily_prices=daily_display,
        sector_change_pct=sector_change_pct,
        market_regime=market_regime,
    )

    logger.info("[%s] Confluence score: %d (%s)", ticker, score["total_score"], score["signal"])

    # ── Phase 3.5: Run validated buy strategies ──
    from validation.strategies import (  # noqa: PLC0415
        strategy_mean_reversion, strategy_liquidity_sweep, strategy_wyckoff_buy_only,
        ALL_STRATEGIES as _ALL_STRATS,
    )

    _LIVE_STRATEGIES = {
        "mean_reversion": strategy_mean_reversion,
        "liquidity_sweep": strategy_liquidity_sweep,
        "wyckoff_buy_only": strategy_wyckoff_buy_only,
    }
    _strat_kwargs = dict(
        daily_prices=daily_display,
        weekly_prices=weekly_asc,
        daily_swings=daily_swings,
        weekly_swings=weekly_swings,
        daily_structure=daily_structure,
        weekly_structure=weekly_structure,
        levels=levels,
        patterns=patterns,
        volume=volume,
        current_price=current_price,
        score_result=score,
        rsi=rsi_data,
        macd=macd_data,
        atr=atr_value,
    )
    strategy_signals = {}
    for _key, _fn in _LIVE_STRATEGIES.items():
        try:
            _sig = _fn(**_strat_kwargs)
            strategy_signals[_key] = {
                "name": _ALL_STRATS[_key]["name"],
                "signal": _sig,
                "fired": _sig is not None,
            }
        except Exception as _e:
            logger.warning("[%s] Strategy %s failed: %s", ticker, _key, _e)
            strategy_signals[_key] = {
                "name": _ALL_STRATS[_key]["name"],
                "signal": None,
                "fired": False,
            }

    logger.info(
        "[%s] Strategy signals: %s",
        ticker,
        {k: v["signal"] for k, v in strategy_signals.items()},
    )

    # ── Phase 4: LLM narrative ──
    technical_text = _format_price_action_for_llm(
        ticker, overview, quote, daily_structure, weekly_structure,
        levels, patterns, volume, rsi_data, macd_data, current_price,
        ma_50_value, ma_200_value,
    )
    score_text = _format_score_for_llm(score)

    logger.info("[%s] Generating LLM narrative", ticker)
    llm_result = ollama.narrate_price_action(technical_text, score_text)
    narrative = llm_result.get("data")
    if not narrative:
        logger.warning("[%s] LLM narrative failed: %s", ticker, llm_result.get("error"))

    # ── Phase 5: Build chart data for frontend ──
    chart_data = _build_chart_data(
        daily_display, weekly_asc, daily_swings, weekly_swings,
        daily_structure, weekly_structure, levels, patterns,
        ma_50_series, ma_200_series, rsi_data, macd_data, current_price,
    )

    return {
        "ticker": ticker,
        "name": overview.get("name", ""),
        "sector": overview.get("sector", ""),
        "quote": quote,
        "score": score,
        "weekly_structure": {
            "trend": weekly_structure["trend"],
            "strength": weekly_structure["strength"],
            "bos": weekly_structure.get("bos"),
            "choch": weekly_structure.get("choch"),
        },
        "daily_structure": {
            "trend": daily_structure["trend"],
            "strength": daily_structure["strength"],
            "bos": daily_structure.get("bos"),
            "choch": daily_structure.get("choch"),
        },
        "levels": levels,
        "patterns": [
            {k: v for k, v in p.items() if k != "at_level"}
            for p in patterns
        ],
        "volume": volume,
        "atr": atr_value,
        "gaps": gaps,
        "market_regime": market_regime,
        "strategy_signals": strategy_signals,
        "narrative": narrative,
        "extended_hours": extended if extended else None,
        "institutional": institutional,
        "insider_transactions": insider_txns[:20],
        "earnings": earnings_raw,
        "sector_relative": {
            "sector": sector,
            "etf": etf_ticker,
            "sector_change_pct": sector_change_pct,
        } if sector_change_pct is not None else None,
        "chart_data": chart_data,
        "trade_setup": _compute_trade_setup(score, current_price, atr_value, levels),
        "duration_seconds": round(_time.time() - start, 1),
        "error": llm_result.get("error") if not narrative else None,
    }


def _format_price_action_for_llm(
    ticker, overview, quote, daily_structure, weekly_structure,
    levels, patterns, volume, rsi_data, macd_data, current_price,
    ma_50, ma_200,
) -> str:
    """Format all price action data as text for LLM consumption."""
    lines = [
        f"{'='*60}",
        f"{ticker} — {overview.get('name', 'Unknown')}",
        f"Sector: {overview.get('sector', 'N/A')}",
        f"{'='*60}",
        "",
        "CURRENT PRICE:",
        f"  Price: ${quote.get('price', 'N/A')} | Change: {quote.get('change_percent', 'N/A')}",
        f"  Volume: {quote.get('volume', 'N/A')}",
        "",
        "PRICE LEVELS:",
        f"  52-Week High: {overview.get('52_week_high', 'N/A')} | Low: {overview.get('52_week_low', 'N/A')}",
    ]

    if ma_50:
        pos = "ABOVE" if current_price > ma_50 else "BELOW"
        lines.append(f"  50-Day MA: ${ma_50} (price {pos})")
    if ma_200:
        pos = "ABOVE" if current_price > ma_200 else "BELOW"
        lines.append(f"  200-Day MA: ${ma_200} (price {pos})")

    lines.extend([
        "",
        "WEEKLY MARKET STRUCTURE:",
        f"  Trend: {weekly_structure['trend'].upper()} ({weekly_structure['strength']})",
    ])
    w_swings = weekly_structure.get("labeled_swings", [])[-4:]
    if w_swings:
        labels = " → ".join(f"{s['label']}({s['price']:.2f})" for s in w_swings)
        lines.append(f"  Recent swings: {labels}")
    if weekly_structure.get("bos"):
        lines.append(f"  BOS: {weekly_structure['bos']['type']}")
    if weekly_structure.get("choch"):
        lines.append(f"  CHoCH: {weekly_structure['choch']['type']}")

    lines.extend([
        "",
        "DAILY MARKET STRUCTURE:",
        f"  Trend: {daily_structure['trend'].upper()} ({daily_structure['strength']})",
    ])
    d_swings = daily_structure.get("labeled_swings", [])[-6:]
    if d_swings:
        labels = " → ".join(f"{s['label']}({s['price']:.2f})" for s in d_swings)
        lines.append(f"  Recent swings: {labels}")
    if daily_structure.get("bos"):
        lines.append(f"  BOS: {daily_structure['bos']['type']}")
    if daily_structure.get("choch"):
        lines.append(f"  CHoCH: {daily_structure['choch']['type']}")

    # S/R levels
    supports = [l for l in levels if l["type"] == "support"]
    resistances = [l for l in levels if l["type"] == "resistance"]
    lines.append("")
    lines.append("SUPPORT LEVELS:")
    for s in supports[:3]:
        src = s.get("source", "swing")
        tfs = "+".join(s.get("timeframes", []))
        lines.append(f"  ${s['price']} (strength {s['strength']}, source: {src}, TFs: {tfs})")
    lines.append("RESISTANCE LEVELS:")
    for r in resistances[:3]:
        src = r.get("source", "swing")
        tfs = "+".join(r.get("timeframes", []))
        lines.append(f"  ${r['price']} (strength {r['strength']}, source: {src}, TFs: {tfs})")

    # Candlestick patterns
    if patterns:
        lines.extend(["", "CANDLESTICK PATTERNS DETECTED:"])
        for p in patterns[-5:]:
            at = f" at {p['at_level']['type']} ${p['at_level']['price']}" if p.get("at_level") else ""
            lines.append(f"  {p['name'].replace('_', ' ').title()} ({p['direction']}, strength {p['strength']}){at} on {p['date']}")

    # Volume
    lines.extend([
        "",
        "VOLUME ANALYSIS:",
        f"  Current vs 20-day avg: {volume.get('current_ratio', 0)}x",
        f"  Trend: {volume.get('trend', 'N/A')}",
        f"  Confirming: {volume.get('confirmation_type', 'none')}",
    ])

    # Indicators (confirmation)
    if rsi_data:
        lines.extend(["", "INDICATORS (confirmation only):"])
        lines.append(f"  RSI(14): {rsi_data[0].get('value', 'N/A')}")
    if macd_data:
        m = macd_data[0]
        lines.append(f"  MACD: {m.get('macd', 0):.3f} | Signal: {m.get('signal', 0):.3f} | Hist: {m.get('histogram', 0):.3f}")

    return "\n".join(lines)


def _format_score_for_llm(score: Dict[str, Any]) -> str:
    """Format the confluence score breakdown for LLM."""
    lines = [
        f"CONFLUENCE SCORE: {score['total_score']} / {score['max_score']}",
        f"SIGNAL: {score['signal'].upper()}",
        "",
        "LAYER BREAKDOWN:",
    ]
    for layer in score["layers"]:
        lines.append(f"  {layer['name']}: {layer['score']:+d} (max ±{layer['max']}) — {layer['reasoning']}")
    align = score.get("alignment", {})
    if align:
        lines.append(f"  Alignment: {align.get('score', 0):+d} — {align.get('reasoning', '')}")
    return "\n".join(lines)


def _build_chart_data(
    daily_asc, weekly_asc, daily_swings, weekly_swings,
    daily_structure, weekly_structure, levels, patterns,
    ma_50_series, ma_200_series, rsi_data, macd_data, current_price,
) -> Dict[str, Any]:
    """Build all data needed for Lightweight Charts rendering."""
    # Candle data format: {time: "YYYY-MM-DD", open, high, low, close}
    daily_candles = [
        {"time": p["date"], "open": p["open"], "high": p["high"], "low": p["low"], "close": p["close"]}
        for p in daily_asc
    ]
    weekly_candles = [
        {"time": p["date"], "open": p["open"], "high": p["high"], "low": p["low"], "close": p["close"]}
        for p in weekly_asc
    ]

    # Swing point markers
    def _swing_markers(swings, structure):
        markers = []
        labeled = {(s["date"], s["type"]): s.get("label", "") for s in structure.get("labeled_swings", [])}
        for s in swings:
            label = labeled.get((s["date"], s["type"]), "")
            is_high = s["type"] == "swing_high"
            markers.append({
                "time": s["date"],
                "position": "aboveBar" if is_high else "belowBar",
                "shape": "arrowDown" if is_high else "arrowUp",
                "color": "#f85149" if "L" in label else "#3fb950",
                "text": label,
            })
        return markers

    daily_markers = _swing_markers(daily_swings, daily_structure)
    weekly_markers = _swing_markers(weekly_swings, weekly_structure)

    # Pattern markers on daily chart
    pattern_markers = []
    for p in patterns:
        shape_map = {
            "hammer": "arrowUp", "bullish_engulfing": "arrowUp",
            "shooting_star": "arrowDown", "bearish_engulfing": "arrowDown",
            "inside_bar": "circle", "doji": "circle",
            "three_white_soldiers": "arrowUp", "morning_star": "arrowUp",
            "three_black_crows": "arrowDown", "evening_star": "arrowDown",
        }
        color_map = {"bullish": "#3fb950", "bearish": "#f85149", "neutral": "#d29922"}
        pattern_markers.append({
            "time": p["date"],
            "position": "belowBar" if p["direction"] == "bullish" else "aboveBar",
            "shape": shape_map.get(p["name"], "circle"),
            "color": color_map.get(p["direction"], "#d29922"),
            "text": p["name"].replace("_", " ").title(),
        })

    # S/R lines — only levels within 20% of current price to avoid y-axis clutter
    _price_filter = 0.20
    support_lines = [
        {"price": l["price"], "strength": l["strength"]}
        for l in levels
        if l["type"] == "support" and abs(l["price"] - current_price) / current_price <= _price_filter
        and not l.get("source", "").startswith("fib_")
    ]
    resistance_lines = [
        {"price": l["price"], "strength": l["strength"]}
        for l in levels
        if l["type"] == "resistance" and abs(l["price"] - current_price) / current_price <= _price_filter
        and not l.get("source", "").startswith("fib_")
    ]

    # Fibonacci levels — rendered distinctly on the chart (gold color)
    fib_lines = [
        {"price": l["price"], "type": l["type"], "ratio": l.get("fib_ratio", 0), "source": l["source"]}
        for l in levels
        if "fib" in l.get("source", "") and abs(l["price"] - current_price) / current_price <= _price_filter
    ]

    # MA series — trim to display window
    display_start = daily_asc[0]["date"] if daily_asc else ""
    ma_50_chart = [{"time": m["date"], "value": m["value"]} for m in ma_50_series if m["date"] >= display_start]
    ma_200_chart = [{"time": m["date"], "value": m["value"]} for m in (ma_200_series or []) if m["date"] >= display_start]

    # RSI series — AV returns newest-first; Lightweight Charts needs oldest-first
    rsi_series = [{"time": r["date"], "value": r["value"]} for r in reversed(rsi_data or [])]

    # MACD series — same ordering fix
    macd_series = []
    macd_signal_series = []
    macd_hist_series = []
    for m in reversed(macd_data or []):
        macd_series.append({"time": m["date"], "value": m["macd"]})
        macd_signal_series.append({"time": m["date"], "value": m["signal"]})
        color = "#3fb950" if m["histogram"] >= 0 else "#f85149"
        macd_hist_series.append({"time": m["date"], "value": m["histogram"], "color": color})

    return {
        "daily_candles": daily_candles,
        "weekly_candles": weekly_candles,
        "daily_markers": daily_markers,
        "weekly_markers": weekly_markers,
        "pattern_markers": pattern_markers,
        "support_lines": support_lines,
        "resistance_lines": resistance_lines,
        "fib_lines": fib_lines,
        "ma_50": ma_50_chart,
        "ma_200": ma_200_chart,
        "rsi": rsi_series,
        "macd": macd_series,
        "macd_signal": macd_signal_series,
        "macd_histogram": macd_hist_series,
    }


def generate_market_overview() -> Dict[str, Any]:
    """
    Build a comprehensive market snapshot and generate an LLM-powered narrative overview.

    Returns both raw data and LLM analysis.
    """
    logger.info("Building market snapshot for overview")
    snapshot = _build_market_snapshot()

    snapshot_text = _format_snapshot_for_llm(snapshot)
    logger.info("Generating LLM market overview (%d chars of data)", len(snapshot_text))

    llm_result = ollama.generate_market_overview(snapshot_text)
    overview = llm_result.get("data")
    if not overview:
        logger.warning("LLM overview failed: %s", llm_result.get("error"))
        return {
            "snapshot": snapshot,
            "overview": None,
            "error": llm_result.get("error", "Failed to generate overview"),
            "duration_seconds": llm_result.get("duration_seconds", 0),
        }

    return {
        "snapshot": snapshot,
        "overview": overview,
        "duration_seconds": llm_result.get("duration_seconds", 0),
    }


def scan_news() -> Dict[str, Any]:
    """
    Scan news and extract market-moving events (lightweight).

    Fetches news, LLM groups into events, saves to DB.
    User picks which events to deep-analyze.
    """
    logger.info("Scanning news for market-moving events")

    articles = _fetch_all_news()
    if not articles:
        return {"error": "No news articles fetched — check API keys", "events": []}

    new_count = db.save_articles(articles)
    logger.info("Fetched %d articles (%d new)", len(articles), new_count)

    # LLM groups articles into events (batched divide & conquer)
    raw_events, duration = _extract_events_batched(articles)
    if not raw_events:
        return {"error": "No market-moving events detected", "events": []}

    saved_events = []
    for event in raw_events:
        event_id = db.save_event(event)
        saved_events.append({
            "event_id": event_id,
            "title": event.get("title", ""),
            "summary": event.get("summary", ""),
            "category": event.get("category", ""),
            "severity": event.get("severity", ""),
            "regions": event.get("regions", []),
            "related_tickers": event.get("related_tickers", []),
        })

    return {
        "events": saved_events,
        "count": len(saved_events),
        "articles_fetched": len(articles),
        "duration_seconds": duration,
    }


def analyze_event_by_id(event_id: int) -> Dict[str, Any]:
    """
    Deep-analyze a previously scanned event.

    Uses the event's related_tickers to scope ticker data (consistent with full analysis).
    Updates the existing event instead of creating a duplicate.
    """
    stored = db.get_event(event_id)
    if not stored:
        return {"error": f"Event {event_id} not found"}

    # Aggregate ticker data from stored articles
    recent_articles = db.get_recent_articles(limit=200)
    all_ticker_data = _aggregate_ticker_data(recent_articles)

    # Filter to event-specific tickers (same as full analysis)
    event_tickers = stored.get("related_tickers", [])
    event_ticker_data = {t: all_ticker_data[t] for t in event_tickers if t in all_ticker_data}

    return _run_analysis(
        event_id=event_id,
        event_title=stored["title"],
        event_summary=stored.get("summary", ""),
        category=stored.get("category", ""),
        severity=stored.get("severity", ""),
        ticker_data=event_ticker_data,
    )



def _run_analysis(
    event_title: str,
    event_summary: str,
    ticker_data: Dict[str, Dict[str, Any]],
    event_id: int = None,
    category: str = "",
    severity: str = "",
) -> Dict[str, Any]:
    """
    Core analysis logic for deep analysis.

    Phase 1: Build market snapshot (sectors, movers, indicators)
    Phase 2: LLM causal analysis (explains WHY, doesn't guess tickers)
    Phase 3: Full profiles for AV-identified candidate tickers
    Phase 4: LLM evaluates candidates with fundamentals

    If event_id is provided, updates the existing event. Otherwise creates a new one.
    """
    import time
    start = time.time()

    event = {
        "title": event_title,
        "summary": event_summary,
        "category": category or "manual",
        "severity": severity or "high",
    }

    # Phase 1: Market snapshot from AV
    logger.info("Phase 1: Building market snapshot")
    snapshot = _build_market_snapshot()
    snapshot_text = _format_snapshot_for_llm(snapshot)

    movers = snapshot.get("movers", {})
    ticker_data_text = _format_ticker_data_for_llm(ticker_data, movers)

    # Phase 2: LLM causal analysis (no ticker guessing)
    logger.info("Phase 2: LLM causal analysis")
    analysis = ollama.analyze_event(event, snapshot_text, ticker_data_text)

    if analysis.get("error"):
        return {"error": f"LLM analysis failed: {analysis['error']}"}

    data = analysis["data"]
    if not data:
        return {"error": "Failed to parse LLM response"}

    # Save causal analysis — update existing or create new
    if event_id:
        db.update_event_analysis(
            event_id,
            signal_type=data.get("signal_type", ""),
            signal_reasoning=data.get("signal_reasoning", ""),
        )
    else:
        event_id = db.save_event(
            event,
            signal_type=data.get("signal_type", ""),
            signal_reasoning=data.get("signal_reasoning", ""),
        )
    db.save_causal_chains(event_id, data.get("causal_chains", []))
    db.save_sector_impacts(event_id, data.get("sectors", []))

    # Phase 3: Select candidate tickers from AV data and build full profiles
    candidates = _select_candidate_tickers(ticker_data, movers)

    if candidates:
        logger.info("Phase 3: Full profiles for %d candidates: %s", len(candidates), candidates)
        profiles = {}
        for ticker in candidates:
            profile = alpha_vantage.get_full_stock_profile(ticker)
            if profile.get("overview"):
                profiles[ticker] = profile
                logger.info("  Profiled %s (%s)", ticker, profile["overview"].get("name", ""))

        # Phase 4: LLM evaluates candidates with fundamentals
        if profiles:
            logger.info("Phase 4: LLM stock evaluation")
            macro_text = f"Event: {event_title}\n{event_summary}\n"
            macro_text += f"Signal: {data.get('signal_type', 'UNKNOWN')} — {data.get('signal_reasoning', '')}\n\n"
            macro_text += "Causal Analysis:\n"
            for chain in data.get("causal_chains", []):
                macro_text += f"  - {chain.get('chain', '')}\n"
            macro_text += "\nSector Impacts:\n"
            for sector in data.get("sectors", []):
                macro_text += f"  - {sector.get('name', '')} → {sector.get('direction', '')}: {sector.get('reason', '')}\n"

            fund_text = ""
            for ticker, profile in profiles.items():
                fund_text += alpha_vantage.format_stock_profile_for_llm(profile)

            sector_text = _format_sector_perf(snapshot.get("sectors", {}))

            refined = ollama.select_stocks(macro_text, fund_text, sector_text or "Not available")
            if refined.get("data"):
                refined_data = refined["data"]
                data["top_picks"] = refined_data.get("top_picks", [])
                data["avoid"] = refined_data.get("avoid", [])

                all_picks = refined_data.get("top_picks", []) + [
                    {"ticker": a["ticker"], "direction": "bearish", "action": "avoid", "reason": a["reason"]}
                    for a in refined_data.get("avoid", [])
                ]
                db.save_stock_picks(all_picks, event_id=event_id)
    else:
        logger.info("No candidate tickers found from AV data — skipping Phases 3 & 4")

    return {
        "event_id": event_id,
        "event": event,
        "analysis": data,
        "ticker_data": ticker_data,
        "duration_seconds": round(time.time() - start, 1),
    }


SEVERITY_WEIGHT = {"high": 6, "medium": 3, "low": 1}


def _score_event_confidence(
    event: Dict[str, Any],
    all_ticker_data: Dict[str, Dict[str, Any]],
    movers: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Score an event's confidence based on market evidence.

    Returns dict with: confidence (high/medium/low), score (float),
    evidence (list of reasons), priority_score (combined severity + confidence).
    """
    event_tickers = event.get("related_tickers", [])
    evidence = []
    confidence_score = 0.0

    # Build set of top movers for quick lookup
    mover_tickers = {}
    for category in ["top_gainers", "top_losers", "most_active"]:
        for m in movers.get(category, []):
            ticker = m.get("ticker", "")
            try:
                pct = float(str(m.get("change_pct", "0")).replace("%", ""))
            except (ValueError, TypeError):
                pct = 0.0
            if ticker:
                mover_tickers[ticker] = {"change_pct": pct, "category": category}

    # Check how many of the event's tickers are actually moving
    moving_tickers = []
    for t in event_tickers:
        if t in mover_tickers:
            moving_tickers.append((t, mover_tickers[t]))

    if moving_tickers:
        confidence_score += min(len(moving_tickers) * 2, 6)
        names = [f"{t}({m['change_pct']:+.1f}%)" for t, m in moving_tickers]
        evidence.append(f"Tickers in top movers: {', '.join(names)}")

    # Check sentiment alignment: are tickers moving in the direction articles suggest?
    aligned = 0
    for t in event_tickers:
        td = all_ticker_data.get(t)
        mv = mover_tickers.get(t)
        if td and mv:
            sentiment_dir = 1 if td["avg_sentiment"] > 0 else -1 if td["avg_sentiment"] < 0 else 0
            move_dir = 1 if mv["change_pct"] > 0 else -1 if mv["change_pct"] < 0 else 0
            if sentiment_dir != 0 and sentiment_dir == move_dir:
                aligned += 1

    if aligned > 0:
        confidence_score += aligned * 1.5
        evidence.append(f"{aligned} ticker(s) moving in direction sentiment suggests")

    # Ticker mention volume from articles
    total_mentions = sum(
        all_ticker_data[t]["mentions"] for t in event_tickers if t in all_ticker_data
    )
    if total_mentions >= 5:
        confidence_score += 2
        evidence.append(f"High news coverage ({total_mentions} ticker mentions)")
    elif total_mentions >= 2:
        confidence_score += 1
        evidence.append(f"Moderate news coverage ({total_mentions} ticker mentions)")

    # Sentiment intensity across event tickers
    sentiment_scores = [
        abs(all_ticker_data[t]["avg_sentiment"])
        for t in event_tickers if t in all_ticker_data
    ]
    if sentiment_scores:
        avg_intensity = sum(sentiment_scores) / len(sentiment_scores)
        if avg_intensity > 0.25:
            confidence_score += 2
            evidence.append(f"Strong sentiment intensity ({avg_intensity:.2f})")
        elif avg_intensity > 0.1:
            confidence_score += 1
            evidence.append(f"Moderate sentiment intensity ({avg_intensity:.2f})")

    # Classify confidence level
    if confidence_score >= 6:
        confidence = "high"
    elif confidence_score >= 3:
        confidence = "medium"
    else:
        confidence = "low"

    # Combined priority: severity weight + confidence score
    severity = event.get("severity", "low")
    severity_w = SEVERITY_WEIGHT.get(severity, 1)
    priority_score = severity_w + confidence_score

    if not evidence:
        evidence.append("No market movement evidence found for related tickers")

    return {
        "confidence": confidence,
        "confidence_score": round(confidence_score, 1),
        "evidence": evidence,
        "priority_score": round(priority_score, 1),
    }


def run_full_analysis(max_events: int = 5) -> Dict[str, Any]:
    """
    Run the complete pipeline: fetch → extract → snapshot → rank → analyze → profile → synthesize.

    Events are ranked by severity + market confidence (actual ticker movement).
    Only the top max_events are deeply analyzed.
    """
    logger.info("Starting full analysis pipeline (max_events=%d)", max_events)

    # Phase 1: Fetch news
    logger.info("Phase 1: Fetching news from Alpha Vantage")
    articles = _fetch_all_news()
    if not articles:
        return {"error": "No news articles fetched — check API keys"}

    new_count = db.save_articles(articles)
    logger.info("Fetched %d articles (%d new)", len(articles), new_count)

    # Aggregate all ticker data from articles
    all_ticker_data = _aggregate_ticker_data(articles)

    # Phase 2: Extract events (batched divide & conquer)
    logger.info("Phase 2: Extracting events")
    raw_events, _ = _extract_events_batched(articles)
    if not raw_events:
        return {"error": "No market-moving events detected"}

    # Phase 3: Market snapshot (moved before ranking so we can score confidence)
    logger.info("Phase 3: Market snapshot")
    snapshot = _build_market_snapshot()
    snapshot_text = _format_snapshot_for_llm(snapshot)
    movers = snapshot.get("movers", {})

    # Score and rank events by severity + market confidence
    for event in raw_events:
        scoring = _score_event_confidence(event, all_ticker_data, movers)
        event["_confidence"] = scoring["confidence"]
        event["_confidence_score"] = scoring["confidence_score"]
        event["_evidence"] = scoring["evidence"]
        event["_priority_score"] = scoring["priority_score"]

    raw_events.sort(key=lambda e: -e.get("_priority_score", 0))

    # Save all events to DB, track IDs
    for event in raw_events:
        event["_db_id"] = db.save_event(event)

    events_to_analyze = raw_events[:max_events]

    logger.info("Detected %d events, analyzing top %d:", len(raw_events), len(events_to_analyze))
    for e in events_to_analyze:
        logger.info(
            "  [%s sev, %s conf (%.1f)] %s — %s",
            e.get("severity", "?"), e.get("_confidence", "?"),
            e.get("_priority_score", 0), e.get("title", "?"),
            "; ".join(e.get("_evidence", [])),
        )

    # Phase 4: Causal analysis per event
    logger.info("Phase 4: Causal analysis")

    analyzed_events = []
    for event in events_to_analyze:
        logger.info("Analyzing: %s", event.get("title", "unknown"))
        event_id = event["_db_id"]

        # Get ticker data for this event from articles
        event_tickers = event.get("related_tickers", [])
        event_ticker_data = {t: all_ticker_data[t] for t in event_tickers if t in all_ticker_data}
        ticker_data_text = _format_ticker_data_for_llm(event_ticker_data, movers)

        analysis = ollama.analyze_event(event, snapshot_text, ticker_data_text)
        if analysis.get("error"):
            logger.error("Analysis failed for '%s': %s", event.get("title"), analysis["error"])
            continue

        data = analysis.get("data", {})
        if not data:
            continue

        # Update the existing event with analysis results
        db.update_event_analysis(
            event_id,
            signal_type=data.get("signal_type", ""),
            signal_reasoning=data.get("signal_reasoning", ""),
        )
        db.save_causal_chains(event_id, data.get("causal_chains", []))
        db.save_sector_impacts(event_id, data.get("sectors", []))

        analyzed_events.append({
            "event_id": event_id,
            "event": event,
            "analysis": data,
            "ticker_data": event_ticker_data,
        })

    if not analyzed_events:
        return {"error": "No events could be analyzed"}

    # Phase 5: Profile candidate tickers (deduped across all events)
    logger.info("Phase 5: Profiling candidate tickers")
    profiles = {}
    for e in analyzed_events:
        event_candidates = _select_candidate_tickers(e["ticker_data"], movers)
        e["candidates"] = event_candidates
        for ticker in event_candidates:
            if ticker not in profiles:
                profile = alpha_vantage.get_full_stock_profile(ticker)
                if profile.get("overview"):
                    profiles[ticker] = profile
                    logger.info("  Profiled %s (%s)", ticker, profile["overview"].get("name", ""))

    logger.info("Profiled %d unique tickers across %d events", len(profiles), len(analyzed_events))

    # Phase 6: Per-event stock evaluation
    logger.info("Phase 6: Per-event stock evaluation")
    sector_text = _format_sector_perf(snapshot.get("sectors", {}))
    all_eval_texts = []

    for e in analyzed_events:
        event_profiles = {t: profiles[t] for t in e.get("candidates", []) if t in profiles}
        if not event_profiles:
            logger.info("  No profiled candidates for '%s' — skipping evaluation", e["event"].get("title"))
            continue

        # Build macro context from THIS event only
        macro_text = f"Event: {e['event'].get('title', '')}\n{e['event'].get('summary', '')}\n"
        analysis = e["analysis"]
        macro_text += f"Signal: {analysis.get('signal_type', 'N/A')} — {analysis.get('signal_reasoning', '')}\n\n"
        macro_text += "Causal Analysis:\n"
        for chain in analysis.get("causal_chains", []):
            macro_text += f"  - {chain.get('chain', '')}\n"
        macro_text += "\nSector Impacts:\n"
        for sector in analysis.get("sectors", []):
            macro_text += f"  - {sector.get('name', '')} → {sector.get('direction', '')}: {sector.get('reason', '')}\n"

        fund_text = ""
        for ticker, profile in event_profiles.items():
            fund_text += alpha_vantage.format_stock_profile_for_llm(profile)

        logger.info("  Evaluating %d candidates for '%s'", len(event_profiles), e["event"].get("title"))
        refined = ollama.select_stocks(macro_text, fund_text, sector_text or "Not available")
        if refined.get("data"):
            refined_data = refined["data"]
            e["stock_eval"] = refined_data

            # Save picks linked to this event
            all_picks = refined_data.get("top_picks", []) + [
                {"ticker": a["ticker"], "direction": "bearish", "action": "avoid", "reason": a["reason"]}
                for a in refined_data.get("avoid", [])
            ]
            db.save_stock_picks(all_picks, event_id=e["event_id"])

            # Collect for synthesis with event context
            eval_text = f"[Event: {e['event'].get('title', '')}]\n"
            eval_text += _format_stock_eval_for_synthesis(refined_data)
            all_eval_texts.append(eval_text)

    stock_eval_text = "\n\n".join(all_eval_texts)

    # Phase 7: Synthesize all event analyses + per-event stock evaluations
    logger.info("Phase 7: Synthesis")
    report = _synthesize_report(analyzed_events, snapshot, stock_eval_text)

    logger.info("Analysis complete — sentiment: %s", report.get("overall_sentiment", "unknown"))
    return report


# ── News Fetching ────────────────────────────────────────────────────────────

NEWS_TOPIC_GROUPS = [
    "economy_macro,economy_fiscal,economy_monetary",
    "energy_transportation,manufacturing",
    "financial_markets,technology",
]


def _fetch_all_news() -> List[Dict[str, Any]]:
    """Fetch news from Alpha Vantage across multiple topic categories (last 24h)."""
    from datetime import datetime, timedelta

    # Only fetch articles from the last 24 hours
    time_from = (datetime.utcnow() - timedelta(hours=24)).strftime("%Y%m%dT%H%M")

    articles = []
    seen_urls = set()

    for topic_group in NEWS_TOPIC_GROUPS:
        batch = alpha_vantage.fetch_market_news(
            topics=topic_group,
            sort="LATEST",
            limit=15,
            time_from=time_from,
        )
        for article in batch:
            url = article.get("url", "")
            if url not in seen_urls:
                seen_urls.add(url)
                articles.append(article)
        logger.info("Alpha Vantage [%s]: %d articles", topic_group, len(batch))

    logger.info("Total unique articles: %d", len(articles))
    return articles[:75]


# ── Event Extraction (Divide & Conquer) ─────────────────────────────────────

BATCH_SIZE = 10


def _extract_events_batched(articles: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], float]:
    """
    Extract events using divide-and-conquer: split articles into small batches,
    LLM extracts events per batch, then merge duplicates across batches.

    Returns (events, total_duration_seconds).
    """
    import time
    start = time.time()

    if not articles:
        return [], 0.0

    # Split into batches
    batches = [articles[i:i + BATCH_SIZE] for i in range(0, len(articles), BATCH_SIZE)]
    logger.info("Extracting events in %d batches of ~%d articles", len(batches), BATCH_SIZE)

    # Extract events per batch
    all_raw_events = []
    for i, batch in enumerate(batches):
        logger.info("  Batch %d/%d (%d articles)", i + 1, len(batches), len(batch))
        extraction = ollama.extract_events(batch)
        if extraction.get("error"):
            logger.error("  Batch %d failed: %s", i + 1, extraction["error"])
            continue
        batch_events = extraction.get("data", {}).get("events", [])
        all_raw_events.extend(batch_events)
        logger.info("  Batch %d: %d events", i + 1, len(batch_events))

    if not all_raw_events:
        return [], time.time() - start

    # Merge duplicate events across batches
    merged = _merge_events(all_raw_events)
    duration = round(time.time() - start, 1)
    logger.info("Extracted %d events total, merged to %d (%.1fs)", len(all_raw_events), len(merged), duration)
    return merged, duration


def _merge_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Merge events from different batches that are about the same thing.

    Two events are merged if they share 2+ tickers or have very similar titles.
    """
    if not events:
        return []

    merged = []
    used = [False] * len(events)

    for i, event_a in enumerate(events):
        if used[i]:
            continue
        used[i] = True

        group = [event_a]
        tickers_a = set(event_a.get("related_tickers", []))
        title_a = event_a.get("title", "").lower()
        # Title words for fuzzy matching (skip short common words)
        words_a = {w for w in title_a.split() if len(w) > 3}

        for j in range(i + 1, len(events)):
            if used[j]:
                continue

            event_b = events[j]
            tickers_b = set(event_b.get("related_tickers", []))
            title_b = event_b.get("title", "").lower()
            words_b = {w for w in title_b.split() if len(w) > 3}

            # Check ticker overlap
            shared_tickers = tickers_a & tickers_b
            ticker_overlap = len(shared_tickers)

            # Check title similarity (50%+ word overlap)
            word_overlap = len(words_a & words_b) / max(len(words_a | words_b), 1)

            # Merge if: 2+ shared tickers, OR both have <=2 tickers and share 1
            # (single-stock events about the same company), OR titles are very similar
            small_and_same = (
                ticker_overlap >= 1
                and len(tickers_a) <= 2
                and len(tickers_b) <= 2
            )

            if ticker_overlap >= 2 or small_and_same or word_overlap >= 0.5:
                used[j] = True
                group.append(event_b)
                tickers_a |= tickers_b
                words_a |= words_b

        # Combine group into one event
        merged.append(_combine_event_group(group))

    return merged


def _combine_event_group(group: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Combine a group of duplicate events into one."""
    if len(group) == 1:
        return group[0]

    # Pick the event with the highest severity as the base
    severity_rank = {"high": 0, "medium": 1, "low": 2}
    group.sort(key=lambda e: severity_rank.get(e.get("severity", "low"), 2))
    base = group[0]

    # Merge fields from all events in the group
    all_tickers = []
    all_headlines = []
    all_regions = []
    seen_tickers = set()
    seen_headlines = set()

    for event in group:
        for t in event.get("related_tickers", []):
            if t not in seen_tickers:
                seen_tickers.add(t)
                all_tickers.append(t)
        for h in event.get("source_headlines", []):
            if h not in seen_headlines:
                seen_headlines.add(h)
                all_headlines.append(h)
        for r in event.get("regions", []):
            if r not in all_regions:
                all_regions.append(r)

    # Use the longest summary
    best_summary = max((e.get("summary", "") for e in group), key=len)

    return {
        "title": base.get("title", ""),
        "summary": best_summary,
        "category": base.get("category", ""),
        "severity": base.get("severity", ""),
        "regions": all_regions,
        "related_tickers": all_tickers,
        "source_headlines": all_headlines,
    }


# ── Ticker Data Aggregation ──────────────────────────────────────────────────

def _aggregate_ticker_data(articles: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Extract and aggregate ticker mentions + sentiment from AV article data.

    Returns dict keyed by ticker with mention counts, avg sentiment, and source articles.
    """
    tickers = {}
    for article in articles:
        for ticker, ts in article.get("ticker_sentiments", {}).items():
            if ts.get("relevance_score", 0) < 0.3:
                continue
            if ticker not in tickers:
                tickers[ticker] = {"mentions": 0, "scores": [], "articles": []}
            tickers[ticker]["mentions"] += 1
            tickers[ticker]["scores"].append(ts.get("sentiment_score", 0))
            tickers[ticker]["articles"].append(article.get("title", "")[:80])

    result = {}
    for ticker, data in tickers.items():
        avg = sum(data["scores"]) / len(data["scores"])
        if avg > 0.1:
            label = "bullish"
        elif avg < -0.1:
            label = "bearish"
        else:
            label = "neutral"
        result[ticker] = {
            "mentions": data["mentions"],
            "avg_sentiment": round(avg, 3),
            "sentiment_label": label,
            "articles": data["articles"][:5],
        }

    return dict(sorted(result.items(), key=lambda x: -x[1]["mentions"]))



def _select_candidate_tickers(
    ticker_data: Dict[str, Dict[str, Any]],
    movers: Dict[str, Any],
    max_candidates: int = 6,
) -> List[str]:
    """
    Select candidate tickers for deep profiling — purely from AV data.

    Priority:
    1. Tickers from news with multiple mentions or strong sentiment
    2. Top market movers (gainers + losers)
    """
    candidates = {}

    # From news sentiment data
    for ticker, data in ticker_data.items():
        score = data["mentions"] * 2 + abs(data["avg_sentiment"]) * 10
        if data["mentions"] >= 2 or abs(data["avg_sentiment"]) > 0.15:
            candidates[ticker] = score

    # From market movers
    for category in ["top_gainers", "top_losers"]:
        for mover in movers.get(category, [])[:3]:
            ticker = mover.get("ticker", "")
            if ticker and ticker not in candidates:
                candidates[ticker] = 1

    # Sort by score, take top N
    sorted_tickers = sorted(candidates.keys(), key=lambda t: -candidates[t])
    return sorted_tickers[:max_candidates]


# ── Market Snapshot ──────────────────────────────────────────────────────────

def _build_market_snapshot() -> Dict[str, Any]:
    """Build complete market snapshot from Alpha Vantage."""
    snapshot = {}

    # Sector performance via ETF proxies (11 calls)
    snapshot["sectors"] = alpha_vantage.get_sector_performance()

    # Market movers (1 call)
    snapshot["movers"] = alpha_vantage.get_market_movers()

    # Major indices (4 calls)
    indices = {}
    for name, ticker in [("S&P 500", "SPY"), ("Nasdaq 100", "QQQ"), ("Dow Jones", "DIA"), ("Russell 2000", "IWM")]:
        quote = alpha_vantage.get_stock_quote(ticker)
        if quote:
            indices[name] = quote
    snapshot["indices"] = indices

    # VIX proxy (1 call)
    vix_quote = alpha_vantage.get_stock_quote("VIXY")
    if vix_quote:
        snapshot["vix"] = vix_quote

    # Treasury yields (3 calls)
    yields = {}
    for maturity in ["2year", "10year", "30year"]:
        data = alpha_vantage.get_treasury_yield(maturity)
        if data.get("recent"):
            yields[maturity] = data["recent"][0]
    snapshot["treasury_yields"] = yields

    # Economic indicators (5 calls — dropped INFLATION, it's annual-only and redundant with CPI)
    indicators = {}
    econ_indicators = [
        ("CPI", None),
        ("FEDERAL_FUNDS_RATE", None),
        ("UNEMPLOYMENT", None),
        ("REAL_GDP", "quarterly"),
        ("NONFARM_PAYROLL", None),
    ]
    for name, interval in econ_indicators:
        data = alpha_vantage.get_economic_indicator(name, interval=interval)
        if data.get("recent"):
            indicators[name] = data["recent"][0]
    snapshot["indicators"] = indicators

    # Commodities + Gold (4 calls)
    commodities = {}
    for name in ["WTI", "NATURAL_GAS", "COPPER"]:
        data = alpha_vantage.get_commodity_price(name)
        if data.get("recent_prices"):
            commodities[name] = data["recent_prices"][0]
    gold = alpha_vantage.get_stock_quote("GLD")
    if gold and gold.get("price"):
        commodities["GOLD"] = {"date": "", "value": gold["price"], "change_pct": gold.get("change_percent", "")}
    snapshot["commodities"] = commodities

    # Forex (3 calls)
    forex = {}
    for from_c, to_c in [("EUR", "USD"), ("USD", "JPY"), ("GBP", "USD")]:
        data = alpha_vantage.get_currency_exchange_rate(from_c, to_c)
        if data:
            forex[f"{from_c}/{to_c}"] = data
    snapshot["forex"] = forex

    # Crypto (2 calls)
    crypto = {}
    for symbol in ["BTC", "ETH"]:
        data = alpha_vantage.get_currency_exchange_rate(symbol, "USD")
        if data:
            crypto[symbol] = data
    snapshot["crypto"] = crypto

    # Recent news headlines + sentiment (1 call)
    from datetime import datetime, timedelta
    time_from = (datetime.utcnow() - timedelta(hours=24)).strftime("%Y%m%dT%H%M")
    news = alpha_vantage.fetch_market_news(
        topics="economy_macro,economy_fiscal,economy_monetary,financial_markets,energy_transportation",
        sort="RELEVANCE",
        limit=20,
        time_from=time_from,
    )
    snapshot["news"] = news

    # Market regime classification (programmatic, no LLM)
    from app.analysis import price_action as _pa
    snapshot["regime"] = _pa.classify_market_regime(snapshot)

    return snapshot


def _format_snapshot_for_llm(snapshot: Dict[str, Any]) -> str:
    """Format market snapshot as text for LLM consumption."""
    parts = []

    # Market regime (programmatic classification — tell LLM what we already know)
    regime = snapshot.get("regime", {})
    if regime:
        parts.append(f"MARKET REGIME: {regime.get('label', 'Unknown')} (score {regime.get('score', 0)}/{regime.get('max_score', 10)})")
        for sig in regime.get("signals", []):
            parts.append(f"  - {sig}")
        parts.append("")

    # Major indices
    indices = snapshot.get("indices", {})
    if indices:
        parts.append("MAJOR INDICES:")
        for name, q in indices.items():
            parts.append(f"  {name} ({q.get('ticker', '')}): ${q.get('price', 'N/A')} | {q.get('change_percent', 'N/A')}")

    # VIX — VIXY is an ETF proxy, only the % change matters (NOT the dollar price)
    vix = snapshot.get("vix")
    if vix:
        parts.append(f"\nVOLATILITY (VIXY ETF proxy — direction only, dollar price is NOT the VIX index): today's change {vix.get('change_percent', 'N/A')}")

    # Sectors
    sectors = snapshot.get("sectors", {}).get("realtime", {})
    if sectors:
        parts.append("\nSECTOR PERFORMANCE (ETF proxies):")
        for sector, perf in sectors.items():
            parts.append(f"  {sector}: {perf}")

    # Movers
    movers = snapshot.get("movers", {})
    if movers.get("top_gainers"):
        parts.append("\nTOP GAINERS TODAY:")
        for m in movers["top_gainers"][:5]:
            parts.append(f"  {m['ticker']}: {m['change_pct']} (${m['price']})")
    if movers.get("top_losers"):
        parts.append("\nTOP LOSERS TODAY:")
        for m in movers["top_losers"][:5]:
            parts.append(f"  {m['ticker']}: {m['change_pct']} (${m['price']})")

    # Treasury yields
    yields = snapshot.get("treasury_yields", {})
    if yields:
        parts.append("\nTREASURY YIELDS:")
        labels = {"2year": "2-Year", "10year": "10-Year", "30year": "30-Year"}
        for mat, data in yields.items():
            parts.append(f"  {labels.get(mat, mat)}: {data['value']}% (as of {data['date']})")
        # Yield curve spread
        if "2year" in yields and "10year" in yields:
            try:
                spread = float(yields["10year"]["value"]) - float(yields["2year"]["value"])
                status = "NORMAL" if spread > 0 else "INVERTED"
                parts.append(f"  10Y-2Y Spread: {spread:+.2f}% ({status})")
            except (ValueError, TypeError):
                pass

    # Economic indicators
    indicators = snapshot.get("indicators", {})
    if indicators:
        parts.append("\nECONOMIC INDICATORS:")
        for name, data in indicators.items():
            parts.append(f"  {name}: {data['value']} (as of {data['date']})")

    # Commodities
    commodities = snapshot.get("commodities", {})
    if commodities:
        parts.append("\nCOMMODITIES:")
        for name, data in commodities.items():
            extra = f" | {data['change_pct']}" if data.get("change_pct") else ""
            parts.append(f"  {name}: ${data['value']}{extra} (as of {data.get('date', 'today')})")

    # Forex
    forex = snapshot.get("forex", {})
    if forex:
        parts.append("\nFOREX:")
        for pair, data in forex.items():
            parts.append(f"  {pair}: {data.get('rate', 'N/A')} (as of {data.get('last_refreshed', 'N/A')})")

    # Crypto
    crypto = snapshot.get("crypto", {})
    if crypto:
        parts.append("\nCRYPTO:")
        for symbol, data in crypto.items():
            parts.append(f"  {symbol}/USD: ${data.get('rate', 'N/A')} (as of {data.get('last_refreshed', 'N/A')})")

    # News headlines + sentiment
    news = snapshot.get("news", [])
    if news:
        parts.append("\nRECENT NEWS & SENTIMENT (last 24h):")
        for article in news[:15]:
            sentiment = article.get("overall_sentiment_label", "N/A")
            score = article.get("overall_sentiment_score", 0)
            title = article.get("title", "")
            source = article.get("source", "")
            topics = ", ".join(article.get("topics", [])[:3])
            parts.append(f"  [{sentiment} ({score:+.2f})] {title} — {source}")
            if topics:
                parts.append(f"    Topics: {topics}")

    return "\n".join(parts) if parts else "No market data available."


def _format_ticker_data_for_llm(
    ticker_data: Dict[str, Dict[str, Any]],
    movers: Dict[str, Any],
) -> str:
    """Format aggregated ticker data + market movers for LLM."""
    parts = []

    if ticker_data:
        parts.append("TICKERS FROM RELATED NEWS (Alpha Vantage sentiment):")
        for ticker, data in list(ticker_data.items())[:20]:
            parts.append(
                f"  {ticker}: {data['sentiment_label'].upper()} "
                f"(score: {data['avg_sentiment']}, {data['mentions']} mention(s))"
            )

    if movers.get("top_gainers"):
        parts.append("\nMARKET MOVERS — TOP GAINERS:")
        for m in movers["top_gainers"][:5]:
            parts.append(f"  {m['ticker']}: {m['change_pct']} (${m['price']}, vol: {m.get('volume', 'N/A')})")

    if movers.get("top_losers"):
        parts.append("\nMARKET MOVERS — TOP LOSERS:")
        for m in movers["top_losers"][:5]:
            parts.append(f"  {m['ticker']}: {m['change_pct']} (${m['price']}, vol: {m.get('volume', 'N/A')})")

    if movers.get("most_active"):
        parts.append("\nMOST ACTIVELY TRADED:")
        for m in movers["most_active"][:5]:
            parts.append(f"  {m['ticker']}: {m['change_pct']} (${m['price']}, vol: {m.get('volume', 'N/A')})")

    return "\n".join(parts) if parts else "No ticker data available."


def _format_sector_perf(sectors: Dict[str, Any]) -> str:
    """Format sector performance as text."""
    realtime = sectors.get("realtime", {})
    if not realtime:
        return ""
    return "\n".join(f"{sector}: {perf}" for sector, perf in realtime.items())


def _format_stock_eval_for_synthesis(eval_data: Dict[str, Any]) -> str:
    """Format stock evaluation results for the synthesis prompt."""
    parts = []
    for pick in eval_data.get("top_picks", []):
        parts.append(
            f"{pick.get('ticker', '?')} — {pick.get('action', '?').upper()}: "
            f"{pick.get('reason', '')} (Risk: {pick.get('risk', 'N/A')})"
        )
    for avoid in eval_data.get("avoid", []):
        parts.append(f"{avoid.get('ticker', '?')} — AVOID: {avoid.get('reason', '')}")
    return "\n".join(parts)


# ── Synthesis ────────────────────────────────────────────────────────────────

def _synthesize_report(
    events: List[Dict[str, Any]],
    snapshot: Dict[str, Any],
    stock_eval_text: str,
) -> Dict[str, Any]:
    """Synthesize all event analyses into a holistic report."""
    # Format event analyses
    event_text = ""
    for e in events:
        analysis = e.get("analysis", {})
        event_text += f"\n### {e['event'].get('title', 'Unknown Event')}\n"
        event_text += f"Signal: {analysis.get('signal_type', 'N/A')} — {analysis.get('signal_reasoning', '')}\n"
        event_text += f"Severity: {e['event'].get('severity', 'unknown')}\n"

        for chain in analysis.get("causal_chains", []):
            event_text += f"  Chain: {chain.get('chain', '')}\n"
        for sector in analysis.get("sectors", []):
            event_text += f"  Sector: {sector.get('name', '')} → {sector.get('direction', '')} ({sector.get('reason', '')})\n"

    # Format indicators
    econ_text = ""
    for name, data in snapshot.get("indicators", {}).items():
        econ_text += f"{name}: {data['value']} (as of {data['date']})\n"
    for name, data in snapshot.get("commodities", {}).items():
        econ_text += f"{name}: ${data['value']} (as of {data['date']})\n"

    sector_text = _format_sector_perf(snapshot.get("sectors", {}))

    synthesis = ollama.synthesize(
        event_analyses=event_text or "No events analyzed",
        stock_evaluations=stock_eval_text,
        economic_indicators=econ_text or "No economic data available",
        sector_performance=sector_text or "No sector data available",
    )

    if synthesis.get("error"):
        logger.error("Synthesis failed: %s", synthesis["error"])
        return {"error": f"Synthesis failed: {synthesis['error']}"}

    report = synthesis.get("data", {})
    if not report:
        return {"error": "Failed to parse synthesis response"}

    report_id = db.save_report(report)
    report["report_id"] = report_id
    report["events_analyzed"] = len(events)
    report["duration_seconds"] = synthesis["duration_seconds"]

    return report
