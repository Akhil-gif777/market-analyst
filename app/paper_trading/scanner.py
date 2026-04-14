"""
Paper trading scanner -- scans the watchlist for trade opportunities.

The confluence scoring engine IS the strategy. It scores 13 layers
(trend, structure, levels, patterns, volume, indicators, MAs, momentum,
insider, institutional, earnings, revenue, relative strength) and produces
a buy/sell signal with dynamic thresholds (volume gate + regime gate).

Pattern strategies (mean reversion, liquidity sweep, wyckoff) run
alongside for labeling -- they tell you WHAT KIND of setup triggered,
but they don't gate the trade. The confluence signal is sufficient.

Flow per ticker:
  1. Fetch daily, weekly, RSI, MACD, earnings, insider, institutional, income, sector ETF, VIX (~10 AV calls)
  2. Compute ATR, momentum, MAs, gaps, market regime locally
  3. Run 13-layer confluence scoring (identical inputs to Stock Analysis tab)
  4. If signal is buy/strong_buy -> open long trade (after news check)
  5. If signal is sell/strong_sell -> open short trade (after news check)
  6. Run pattern strategies for informational labeling
"""
from __future__ import annotations
import logging
import time
from typing import Dict, Any, List

from app.clients import alpha_vantage as av
from app.analysis import price_action as pa
from app.paper_trading.watchlist import get_dynamic_watchlist
from app.paper_trading.pre_trade import analyze_pre_trade
from app.paper_trading import executor
from app.db import database as db
from validation.strategies import (
    strategy_mean_reversion, strategy_liquidity_sweep,
    strategy_wyckoff_buy_only,
)

logger = logging.getLogger(__name__)

PATTERN_STRATEGIES = {
    "mean_reversion": strategy_mean_reversion,
    "liquidity_sweep": strategy_liquidity_sweep,
    "wyckoff_buy_only": strategy_wyckoff_buy_only,
}

SCAN_DELAY = 0.5  # seconds between tickers


def _analyze(ticker: str, sector: str = "Unknown") -> Dict[str, Any]:
    """
    Full price action analysis without LLM.
    Uses the same data as the Stock Analysis tab to ensure identical scores.
    ~10 AV calls per ticker: daily, weekly, RSI, MACD, earnings, insider, institutional, income, sector ETF, VIX.
    """
    # ── Phase 1: Fetch all data ──
    daily_desc = av.get_daily_prices(ticker, compact=False)
    time.sleep(SCAN_DELAY)
    weekly_desc = av.get_weekly_prices(ticker)
    time.sleep(SCAN_DELAY)
    rsi_raw = av.get_rsi(ticker)
    time.sleep(SCAN_DELAY)

    if not daily_desc:
        return {"error": f"No data for {ticker}"}

    # MACD — same as Stock Analysis tab
    macd_raw = av.get_macd(ticker)
    time.sleep(SCAN_DELAY)
    macd_data = macd_raw.get("data", []) if macd_raw else []

    # Earnings — feeds earnings momentum layer (±3)
    earnings_raw = None
    try:
        earnings_raw = av.get_earnings(ticker)
        time.sleep(SCAN_DELAY)
    except Exception:
        pass

    # Insider transactions — feeds insider activity layer (±2)
    insider_txns = None
    try:
        insider_txns = av.get_insider_transactions(ticker)
        time.sleep(SCAN_DELAY)
    except Exception:
        pass

    # Institutional holdings — feeds institutional layer (±1)
    institutional = None
    try:
        institutional = av.get_institutional_holdings(ticker)
        time.sleep(SCAN_DELAY)
    except Exception:
        pass

    # Income statement — feeds revenue acceleration layer (±1)
    income_raw = None
    try:
        income_raw = av.get_income_statement(ticker)
        time.sleep(SCAN_DELAY)
    except Exception:
        pass

    daily_asc = list(reversed(daily_desc))
    weekly_asc = list(reversed(weekly_desc[:104]))  # 2 years weekly
    rsi_data = rsi_raw.get("data", [])

    current_price = daily_asc[-1]["close"]

    # ── Phase 2: Compute indicators locally ──
    atr_value = pa.compute_atr(daily_asc, period=14)

    daily_swings = pa.detect_swing_points(daily_asc, lookback=3)
    weekly_swings = pa.detect_swing_points(weekly_asc, lookback=3)
    daily_structure = pa.classify_market_structure(daily_swings)
    weekly_structure = pa.classify_market_structure(weekly_swings)

    ema_21_series = pa.compute_ema(daily_asc, 21)
    ma_50_series = pa.compute_sma(daily_asc, 50)
    ma_200_series = pa.compute_sma(daily_asc, 200)
    ema_21_value = ema_21_series[-1]["value"] if ema_21_series else None
    ma_50_value = ma_50_series[-1]["value"] if ma_50_series else None
    ma_200_value = ma_200_series[-1]["value"] if ma_200_series else None

    levels = pa.find_support_resistance(
        daily_swings, weekly_swings, current_price,
        ma_50=ma_50_value, ma_200=ma_200_value, ema_21=ema_21_value,
    )
    patterns = pa.detect_candlestick_patterns(daily_asc, levels)
    volume = pa.analyze_volume(daily_asc)
    rsi_divergence = pa.detect_rsi_divergence(daily_swings, rsi_data)
    ma_signals = pa.compute_ma_signals(ma_50_series, ma_200_series, current_price, ema_21_series=ema_21_series)
    gaps = pa.detect_gaps(daily_asc, levels, atr_value) if atr_value > 0 else []

    # ── Phase 2.5: Sector relative strength + market regime ──
    sector_change_pct = None
    _sector_etf_map = {
        "Technology": "XLK", "Healthcare": "XLV", "Financials": "XLF",
        "Energy": "XLE", "Consumer Discretionary": "XLY", "Consumer Staples": "XLP",
        "Industrials": "XLI", "Materials": "XLB", "Utilities": "XLU",
        "Real Estate": "XLRE", "Communication Services": "XLC",
    }
    etf_ticker = _sector_etf_map.get(sector)
    if etf_ticker:
        try:
            etf_quote = av.get_stock_quote(etf_ticker)
            time.sleep(SCAN_DELAY)
            if etf_quote and etf_quote.get("change_percent"):
                sector_change_pct = float(str(etf_quote["change_percent"]).replace("%", ""))
        except Exception:
            pass

    # Lightweight market regime from available data
    market_regime = None
    try:
        _mini_snapshot = {
            "vix": av.get_stock_quote("VIXY") or {},
            "sectors": {"realtime": {}},
        }
        time.sleep(SCAN_DELAY)
        if etf_ticker and sector_change_pct is not None:
            _mini_snapshot["sectors"]["realtime"][sector] = f"{sector_change_pct}%"
        market_regime = pa.classify_market_regime(_mini_snapshot)
    except Exception:
        pass

    # ── Phase 3: Full 13-layer confluence score — identical inputs to Stock Analysis tab ──
    score = pa.compute_confluence_score(
        weekly_structure=weekly_structure,
        daily_structure=daily_structure,
        levels=levels,
        patterns=patterns,
        volume=volume,
        current_price=current_price,
        rsi_data=rsi_data,
        macd_data=macd_data,
        rsi_divergence=rsi_divergence,
        ma_signals=ma_signals,
        atr=atr_value,
        gaps=gaps,
        daily_prices=daily_asc,
        insider_txns=insider_txns,
        institutional=institutional,
        earnings=earnings_raw,
        income=income_raw,
        sector_change_pct=sector_change_pct,
        market_regime=market_regime,
    )

    # Pattern strategies -- informational labels only, not gates
    matched_patterns = []
    strat_kwargs = dict(
        daily_prices=daily_asc, weekly_prices=weekly_asc,
        daily_swings=daily_swings, weekly_swings=weekly_swings,
        daily_structure=daily_structure, weekly_structure=weekly_structure,
        levels=levels, patterns=patterns, volume=volume,
        current_price=current_price, score_result=score,
        rsi=rsi_data, macd=[], atr=atr_value,
        ma_50=ma_50_value, ma_200=ma_200_value,
    )
    for name, fn in PATTERN_STRATEGIES.items():
        try:
            sig = fn(**strat_kwargs)
            if sig in ("buy", "strong_buy"):
                matched_patterns.append(name)
        except Exception:
            pass

    # Build analysis snapshot — complete paper trail for post-trade review
    snapshot = {
        "score": score,  # total_score, signal, layers[], alignment, risk_reward
        "weekly_structure": {
            "trend": weekly_structure.get("trend"),
            "strength": weekly_structure.get("strength"),
            "bos": weekly_structure.get("bos"),
            "choch": weekly_structure.get("choch"),
        },
        "daily_structure": {
            "trend": daily_structure.get("trend"),
            "strength": daily_structure.get("strength"),
            "bos": daily_structure.get("bos"),
            "choch": daily_structure.get("choch"),
        },
        "patterns_detected": [
            {"name": p.get("name"), "direction": p.get("direction"), "strength": p.get("strength")}
            for p in patterns[:5]
        ],
        "volume": {
            "ratio": volume.get("current_ratio"),
            "trend": volume.get("trend"),
            "confirming": volume.get("confirming"),
        },
        "key_levels": [
            {"type": lv.get("type"), "price": lv.get("price"), "strength": lv.get("strength")}
            for lv in levels[:10]
        ],
        "momentum": {
            "atr": atr_value,
            "ma_50": ma_50_value,
            "ma_200": ma_200_value,
        },
        "matched_patterns": matched_patterns,
        "gaps": [
            {"direction": g.get("direction"), "pct": g.get("gap_pct"), "through_level": bool(g.get("through_level"))}
            for g in gaps[:3]
        ],
        "market_regime": {
            "label": market_regime.get("label") if market_regime else None,
            "score": market_regime.get("score") if market_regime else None,
            "signals": market_regime.get("signals", []) if market_regime else [],
        },
        "sector_relative": {
            "sector": sector,
            "etf": etf_ticker,
            "sector_change_pct": sector_change_pct,
        },
        "earnings": {
            "quarterly": (earnings_raw or {}).get("quarterly", [])[:4],
        },
    }

    return {
        "ticker": ticker,
        "current_price": current_price,
        "score": score,
        "levels": levels,
        "matched_patterns": matched_patterns,
        "daily_structure": daily_structure,
        "weekly_structure": weekly_structure,
        "atr": atr_value,
        "snapshot": snapshot,
    }


def run_scan() -> Dict[str, Any]:
    """
    Scan the full watchlist for signals and open trades automatically.
    Supports both long (buy/strong_buy) and short (sell/strong_sell) signals.
    """
    portfolio = db.get_paper_portfolio()
    if not portfolio:
        db.init_paper_portfolio()

    open_trades = db.get_paper_trades(status="open")
    open_tickers = {t["ticker"] for t in open_trades}

    watchlist = get_dynamic_watchlist()
    results = {"scanned": 0, "signals": 0, "opened": 0, "skipped": 0, "watchlist_size": len(watchlist), "details": []}

    for ticker, sector in watchlist.items():
        if ticker in open_tickers:
            results["skipped"] += 1
            results["details"].append({
                "ticker": ticker, "sector": sector,
                "action": "SKIPPED — already have open position",
                "score": None, "signal": "held",
            })
            continue

        logger.info("[SCAN] Analyzing %s (%s)", ticker, sector)
        results["scanned"] += 1

        try:
            analysis = _analyze(ticker, sector=sector)
            if analysis.get("error"):
                results["details"].append({
                    "ticker": ticker, "sector": sector,
                    "action": f"ERROR — {analysis['error']}",
                    "score": 0, "signal": "error",
                })
                continue

            signal = analysis["score"].get("signal", "neutral")
            score_val = analysis["score"].get("total_score", 0)
            buy_threshold = analysis["score"].get("buy_threshold", 4)
            layers = analysis["score"].get("layers", [])

            # Build layer summary for the detail
            top_layers = sorted(layers, key=lambda l: abs(l.get("score", 0)), reverse=True)[:5]
            layer_summary = [{"name": l["name"], "score": l["score"], "max": l["max"]} for l in top_layers]

            # Determine trade direction from confluence signal
            if signal in ("buy", "strong_buy"):
                direction = "long"
            elif signal in ("sell", "strong_sell"):
                direction = "short"
            else:
                # No signal — record WHY (score vs threshold)
                results["details"].append({
                    "ticker": ticker, "sector": sector,
                    "score": score_val, "signal": signal,
                    "threshold": buy_threshold,
                    "price": analysis.get("current_price"),
                    "layers": layer_summary,
                    "action": f"NO SIGNAL — score {score_val} (need {buy_threshold} for buy, -{buy_threshold} for sell)",
                })
                continue

            results["signals"] += 1

            patterns = analysis.get("matched_patterns", [])
            strategy_label = patterns[0] if patterns else "confluence"

            # Pre-trade: news gate + earnings check (direction-aware)
            pre_trade = analyze_pre_trade(
                ticker=ticker,
                sector=sector,
                confluence_score=analysis["score"],
                levels=analysis["levels"],
                direction=direction,
            )

            # Volatility label based on ATR as % of price
            _atr = analysis.get("atr", 0)
            _price = analysis.get("current_price", 1)
            _atr_pct = (_atr / _price * 100) if _price > 0 and _atr > 0 else 0
            volatility = "high" if _atr_pct > 2.5 else "medium" if _atr_pct > 1.5 else "low"

            detail = {
                "ticker": ticker,
                "sector": sector,
                "strategy": strategy_label,
                "patterns": patterns,
                "score": score_val,
                "signal": signal,
                "direction": direction,
                "threshold": buy_threshold,
                "price": analysis.get("current_price"),
                "atr": _atr,
                "atr_pct": round(_atr_pct, 1),
                "volatility": volatility,
                "layers": layer_summary,
            }

            # Enrich snapshot with pre-trade results
            snap = analysis.get("snapshot") or {}
            snap["news_sentiment"] = {
                "score": pre_trade.get("sentiment_score"),
                "blocked": not pre_trade.get("go"),
                "reason": pre_trade.get("reason"),
            }
            snap["direction"] = direction

            if not pre_trade.get("go"):
                detail["action"] = f"BLOCKED — {pre_trade.get('reason', 'pre-trade check failed')}"
                if pre_trade.get("earnings_warning"):
                    detail["earnings_warning"] = pre_trade["earnings_warning"]
                results["skipped"] += 1
            else:
                try:
                    trade = executor.open_trade(
                        ticker=ticker,
                        sector=sector,
                        strategy=strategy_label,
                        signal_price=analysis["current_price"],
                        conviction_score=pre_trade["conviction_score"],
                        max_score=analysis["score"].get("max_score", 27),
                        levels=analysis["levels"],
                        sentiment_score=pre_trade.get("sentiment_score"),
                        atr=analysis.get("atr", 0),
                        analysis_snapshot=snap,
                        direction=direction,
                    )
                except Exception as ex:
                    logger.error("[SCAN] executor.open_trade failed for %s: %s", ticker, ex)
                    trade = None

                if trade:
                    pct = trade["position_value"] / 100000 * 100
                    dir_label = "SHORT" if direction == "short" else "LONG"
                    detail["action"] = f"OPENED {dir_label} — score {score_val}, size ${trade['position_value']:.0f} ({pct:.1f}%), entry ${trade['entry_price']:.2f}"
                    detail["trade_id"] = trade.get("id")
                    results["opened"] += 1
                    open_tickers.add(ticker)
                else:
                    detail["action"] = "REJECTED — risk budget full or portfolio limit"
                    results["skipped"] += 1

            results["details"].append(detail)
            time.sleep(SCAN_DELAY)

        except Exception as e:
            logger.error("[SCAN] Error analyzing %s: %s", ticker, e, exc_info=True)
            results["details"].append({
                "ticker": ticker, "sector": sector,
                "action": f"ERROR — {str(e)[:100]}",
                "score": 0, "signal": "error",
            })

    logger.info("[SCAN] Complete: %d scanned, %d signals, %d opened, %d skipped",
                results["scanned"], results["signals"], results["opened"], results["skipped"])

    # Persist scan results
    try:
        scan_id = db.save_scan(results, results["details"])
        results["scan_id"] = scan_id
        logger.info("[SCAN] Saved as scan #%d", scan_id)
    except Exception as e:
        logger.error("[SCAN] Failed to save scan history: %s", e)

    return results
