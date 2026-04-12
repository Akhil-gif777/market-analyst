"""
Price action strategies for backtesting.

Each strategy takes the same inputs (price data, indicators, structure)
and returns a signal: "buy", "sell", or None (no signal / skip).

None means "this strategy has no opinion today" — different from neutral.
We only measure forward returns when a strategy fires a signal.
"""

from __future__ import annotations

from typing import List, Dict, Any, Optional


# ── Strategy 0: Current Confluence Score (Baseline) ──────────────────────────

def strategy_confluence_score(
    daily_structure: Dict[str, Any],
    weekly_structure: Dict[str, Any],
    levels: List[Dict[str, Any]],
    patterns: List[Dict[str, Any]],
    volume: Dict[str, Any],
    current_price: float,
    rsi: List[Dict[str, Any]],
    macd: List[Dict[str, Any]],
    score_result: Dict[str, Any],
    **kwargs,
) -> Optional[str]:
    """
    Baseline: the existing confluence scoring engine.
    Maps score to buy/sell. Neutral = no signal.
    """
    signal = score_result.get("signal", "neutral")
    if signal in ("buy", "strong_buy"):
        return "buy"
    elif signal in ("sell", "strong_sell"):
        return "sell"
    return None


# ── Strategy 1: Mean Reversion at Support ────────────────────────────────────

def strategy_mean_reversion(
    daily_prices: List[Dict[str, Any]],
    weekly_structure: Dict[str, Any],
    levels: List[Dict[str, Any]],
    current_price: float,
    **kwargs,
) -> Optional[str]:
    """
    Buy weakness in an uptrend at support.

    Rules:
      - Weekly trend is uptrend (any strength)
      - 3+ consecutive red candles (close < open) in the last 5 bars
      - Price is within 2% of a support level
      - Entry trigger: current candle is bullish (close > open) — the reversal

    Research basis: mean-reversion on daily equities has 80% win rate
    for 3-lower-lows, profit factor 2.7 for buying bearish engulfing.
    """
    w_trend = weekly_structure.get("trend", "")
    if w_trend != "uptrend":
        return None

    if len(daily_prices) < 5:
        return None

    # Check for 3+ consecutive red candles in the last 5 bars (excluding current)
    recent = daily_prices[-5:-1]  # bars before the current one
    consecutive_red = 0
    for bar in reversed(recent):
        if bar["close"] < bar["open"]:
            consecutive_red += 1
        else:
            break

    if consecutive_red < 3:
        return None

    # Price must be near support
    supports = [l for l in levels if l["type"] == "support"]
    near_support = any(
        abs(current_price - s["price"]) / current_price < 0.02
        for s in supports
    )
    if not near_support:
        return None

    # Current candle must be bullish (the reversal candle)
    curr = daily_prices[-1]
    if curr["close"] <= curr["open"]:
        return None

    return "buy"


# ── Strategy 2: Liquidity Sweep Reversal ─────────────────────────────────────

def strategy_liquidity_sweep(
    daily_prices: List[Dict[str, Any]],
    daily_swings: List[Dict[str, Any]],
    weekly_structure: Dict[str, Any],
    volume: Dict[str, Any],
    **kwargs,
) -> Optional[str]:
    """
    Buy when price sweeps below a swing low then closes back above.

    Rules:
      - Weekly trend is uptrend or ranging (not downtrend)
      - Current bar's low is below a recent swing low (sweep)
      - Current bar's close is ABOVE that swing low (closes back inside)
      - Volume is above average (confirms stops were hit)

    Research basis: Osler (2000, 2003) Fed research on stop clusters;
    ICT liquidity sweep methodology.
    """
    w_trend = weekly_structure.get("trend", "")
    if w_trend == "downtrend":
        return None

    if len(daily_prices) < 10:
        return None

    # Find recent swing lows (from the last 30 bars, excluding last 3 due to lookback)
    recent_swing_lows = [
        s for s in daily_swings
        if s["type"] == "swing_low"
    ]

    if not recent_swing_lows:
        return None

    curr = daily_prices[-1]
    curr_low = curr["low"]
    curr_close = curr["close"]

    # Check if current bar swept below any recent swing low then closed above
    for swing in recent_swing_lows[-5:]:  # check last 5 swing lows
        swing_price = swing["price"]
        if curr_low < swing_price and curr_close > swing_price:
            # Sweep detected — check volume
            vol_ratio = volume.get("current_ratio", 0)
            if vol_ratio > 1.0:
                return "buy"

    # Mirror for bearish: sweep above swing high then close below
    w_trend = weekly_structure.get("trend", "")
    if w_trend == "uptrend":
        return None  # only take bearish sweeps in downtrend/ranging

    recent_swing_highs = [
        s for s in daily_swings
        if s["type"] == "swing_high"
    ]

    curr_high = curr["high"]
    for swing in recent_swing_highs[-5:]:
        swing_price = swing["price"]
        if curr_high > swing_price and curr_close < swing_price:
            vol_ratio = volume.get("current_ratio", 0)
            if vol_ratio > 1.0:
                return "sell"

    return None


# ── Strategy 3: Fresh Demand Zone Bounce ─────────────────────────────────────

def strategy_demand_zone(
    daily_prices: List[Dict[str, Any]],
    weekly_structure: Dict[str, Any],
    current_price: float,
    atr: float,
    **kwargs,
) -> Optional[str]:
    """
    Buy at a fresh demand zone (Sam Seiden methodology).

    Rules:
      - Weekly trend is uptrend or ranging
      - Detect demand zones: 1-3 bar consolidation followed by explosive
        move up (departure body > 1.5x ATR)
      - Zone is fresh (price hasn't returned to it since formation)
      - Price enters the zone for the first time
      - Entry: current bar touches the zone

    Research basis: Sam Seiden supply/demand; fresh zones outperform
    tested zones because unfilled institutional orders remain.
    """
    w_trend = weekly_structure.get("trend", "")
    if w_trend == "downtrend":
        return None

    if len(daily_prices) < 30 or atr <= 0:
        return None

    # Scan for demand zones in the price history (skip last 5 bars for freshness check)
    zones = _detect_demand_zones(daily_prices[:-5], atr)

    if not zones:
        return None

    # Check if current price enters a fresh zone
    for zone in zones:
        zone_high = zone["high"]
        zone_low = zone["low"]

        # Is zone still fresh? (price hasn't returned to it since formation)
        formation_idx = zone["formation_idx"]
        was_revisited = False
        for bar in daily_prices[formation_idx + zone["departure_bars"]: -1]:
            if bar["low"] <= zone_high:
                was_revisited = True
                break

        if was_revisited:
            continue

        # Does current price enter the zone?
        if daily_prices[-1]["low"] <= zone_high and current_price >= zone_low:
            return "buy"

    # Mirror: supply zones for sells
    if w_trend == "uptrend":
        return None

    supply_zones = _detect_supply_zones(daily_prices[:-5], atr)
    for zone in supply_zones:
        zone_high = zone["high"]
        zone_low = zone["low"]

        formation_idx = zone["formation_idx"]
        was_revisited = False
        for bar in daily_prices[formation_idx + zone["departure_bars"]: -1]:
            if bar["high"] >= zone_low:
                was_revisited = True
                break

        if was_revisited:
            continue

        if daily_prices[-1]["high"] >= zone_low and current_price <= zone_high:
            return "sell"

    return None


def _detect_demand_zones(
    prices: List[Dict[str, Any]], atr: float
) -> List[Dict[str, Any]]:
    """Find demand zones: tight consolidation followed by explosive up move."""
    zones = []
    i = 3
    while i < len(prices) - 3:
        # Look for 1-3 bars of tight consolidation (range < 0.7 * ATR)
        consolidation_bars = 0
        for j in range(i, min(i + 3, len(prices) - 1)):
            bar_range = prices[j]["high"] - prices[j]["low"]
            if bar_range < 0.7 * atr:
                consolidation_bars += 1
            else:
                break

        if consolidation_bars < 1:
            i += 1
            continue

        # Check for explosive departure upward after consolidation
        dep_idx = i + consolidation_bars
        if dep_idx >= len(prices):
            i += 1
            continue

        dep_bar = prices[dep_idx]
        dep_body = abs(dep_bar["close"] - dep_bar["open"])

        if dep_body > 1.5 * atr and dep_bar["close"] > dep_bar["open"]:
            # Demand zone found
            zone_low = min(p["low"] for p in prices[i:i + consolidation_bars])
            zone_high = max(p["high"] for p in prices[i:i + consolidation_bars])
            zones.append({
                "low": zone_low,
                "high": zone_high,
                "formation_idx": i,
                "departure_bars": consolidation_bars + 1,
            })
            i = dep_idx + 1
        else:
            i += 1

    return zones[-5:]  # keep most recent 5 zones


def _detect_supply_zones(
    prices: List[Dict[str, Any]], atr: float
) -> List[Dict[str, Any]]:
    """Find supply zones: tight consolidation followed by explosive down move."""
    zones = []
    i = 3
    while i < len(prices) - 3:
        consolidation_bars = 0
        for j in range(i, min(i + 3, len(prices) - 1)):
            bar_range = prices[j]["high"] - prices[j]["low"]
            if bar_range < 0.7 * atr:
                consolidation_bars += 1
            else:
                break

        if consolidation_bars < 1:
            i += 1
            continue

        dep_idx = i + consolidation_bars
        if dep_idx >= len(prices):
            i += 1
            continue

        dep_bar = prices[dep_idx]
        dep_body = abs(dep_bar["close"] - dep_bar["open"])

        if dep_body > 1.5 * atr and dep_bar["close"] < dep_bar["open"]:
            zone_low = min(p["low"] for p in prices[i:i + consolidation_bars])
            zone_high = max(p["high"] for p in prices[i:i + consolidation_bars])
            zones.append({
                "low": zone_low,
                "high": zone_high,
                "formation_idx": i,
                "departure_bars": consolidation_bars + 1,
            })
            i = dep_idx + 1
        else:
            i += 1

    return zones[-5:]


# ── Strategy 4: Wyckoff Spring ───────────────────────────────────────────────

def strategy_wyckoff_spring(
    daily_prices: List[Dict[str, Any]],
    volume: Dict[str, Any],
    **kwargs,
) -> Optional[str]:
    """
    Buy the spring — a false breakdown below range support on low volume.

    Rules:
      - Detect a range: last 30 bars have a defined support/resistance
        (high-low range < 15% of price, at least 20 bars in range)
      - Current bar breaks below range support (low < support)
      - Volume on breakdown is below average (supply exhausted)
      - Current bar closes back above support (the spring)

    Research basis: Wyckoff accumulation Phase C; the spring is the
    final shakeout before markup begins.
    """
    if len(daily_prices) < 30:
        return None

    # Define the range from last 30 bars (excluding current)
    range_bars = daily_prices[-31:-1]
    range_high = max(b["high"] for b in range_bars)
    range_low = min(b["low"] for b in range_bars)
    range_size = range_high - range_low
    avg_price = (range_high + range_low) / 2

    # Must be a defined range (not trending): range < 15% of price
    if range_size / avg_price > 0.15:
        return None

    # Check that price has been oscillating in range (at least 60% of bars
    # have closes within the range boundaries)
    bars_in_range = sum(
        1 for b in range_bars
        if range_low <= b["close"] <= range_high
    )
    if bars_in_range / len(range_bars) < 0.6:
        return None

    curr = daily_prices[-1]

    # Spring: current bar breaks below range low, closes back above
    if curr["low"] < range_low and curr["close"] > range_low:
        vol_ratio = volume.get("current_ratio", 0)
        # Low volume on spring = supply exhausted = bullish
        if vol_ratio < 1.2:
            return "buy"

    # Upthrust (mirror): breaks above range high, closes back below
    if curr["high"] > range_high and curr["close"] < range_high:
        vol_ratio = volume.get("current_ratio", 0)
        if vol_ratio < 1.2:
            return "sell"

    return None


# ── Strategy 5: Failed Breakout ──────────────────────────────────────────────

def strategy_failed_breakout(
    daily_prices: List[Dict[str, Any]],
    daily_swings: List[Dict[str, Any]],
    volume: Dict[str, Any],
    **kwargs,
) -> Optional[str]:
    """
    Trade the failure of a breakout — fade the false move.

    Rules:
      - A recent swing high/low was broken (1-3 bars ago)
      - The breakout failed: price has closed back inside
      - Volume on the breakout was below average (weak conviction)
      - Entry: in the opposite direction of the failed breakout

    Research basis: Al Brooks — failed breakouts lead to sharp reversals;
    chart pattern failure rates have surged to ~50%.
    """
    if len(daily_prices) < 10:
        return None

    recent_highs = [s for s in daily_swings if s["type"] == "swing_high"]
    recent_lows = [s for s in daily_swings if s["type"] == "swing_low"]

    curr = daily_prices[-1]

    # Check for failed breakout above a swing high (bearish)
    for swing in recent_highs[-3:]:
        swing_price = swing["price"]
        # Was there a breakout above this level in the last 3 bars?
        breakout_bar = None
        for lookback in range(2, min(5, len(daily_prices))):
            bar = daily_prices[-lookback]
            if bar["close"] > swing_price:
                breakout_bar = bar
                break

        if breakout_bar and curr["close"] < swing_price:
            # Failed breakout above — now price is back below
            return "sell"

    # Check for failed breakdown below a swing low (bullish)
    for swing in recent_lows[-3:]:
        swing_price = swing["price"]
        breakout_bar = None
        for lookback in range(2, min(5, len(daily_prices))):
            bar = daily_prices[-lookback]
            if bar["close"] < swing_price:
                breakout_bar = bar
                break

        if breakout_bar and curr["close"] > swing_price:
            return "buy"

    return None


# ── Strategy 6: Wyckoff Spring (Buy Only) ────────────────────────────────────

def strategy_wyckoff_buy_only(
    daily_prices: List[Dict[str, Any]],
    volume: Dict[str, Any],
    **kwargs,
) -> Optional[str]:
    """Wyckoff Spring buy side only — strip the broken sell (upthrust) logic."""
    result = strategy_wyckoff_spring(daily_prices=daily_prices, volume=volume, **kwargs)
    if result == "buy":
        return "buy"
    return None


# ── Strategy 7: Ensemble (3 Buy Strategies) ──────────────────────────────────

def strategy_ensemble_buy(
    daily_prices: List[Dict[str, Any]],
    daily_swings: List[Dict[str, Any]],
    weekly_structure: Dict[str, Any],
    levels: List[Dict[str, Any]],
    volume: Dict[str, Any],
    current_price: float,
    atr: float,
    **kwargs,
) -> Optional[str]:
    """
    Ensemble of the 3 working buy strategies.

    Calls Mean Reversion, Liquidity Sweep (buy only), and Wyckoff Spring (buy only).
    Returns tiered signal based on agreement:
      - 1 strategy fires → "buy"
      - 2+ strategies fire → "strong_buy"
      - 0 → None

    Hypothesis: days where multiple independent strategies agree
    should produce better forward returns than single-strategy days.
    """
    votes = 0

    if strategy_mean_reversion(
        daily_prices=daily_prices, weekly_structure=weekly_structure,
        levels=levels, current_price=current_price, **kwargs,
    ) == "buy":
        votes += 1

    # Liquidity sweep — buy side only
    sweep_result = strategy_liquidity_sweep(
        daily_prices=daily_prices, daily_swings=daily_swings,
        weekly_structure=weekly_structure, volume=volume, **kwargs,
    )
    if sweep_result == "buy":
        votes += 1

    if strategy_wyckoff_spring(
        daily_prices=daily_prices, volume=volume, **kwargs,
    ) == "buy":
        votes += 1

    if votes >= 2:
        return "strong_buy"
    elif votes == 1:
        return "buy"
    return None


# ── Strategy 8: Ensemble (2+ Agreement Only) ─────────────────────────────────

def strategy_ensemble_strict(
    daily_prices: List[Dict[str, Any]],
    daily_swings: List[Dict[str, Any]],
    weekly_structure: Dict[str, Any],
    levels: List[Dict[str, Any]],
    volume: Dict[str, Any],
    current_price: float,
    atr: float,
    **kwargs,
) -> Optional[str]:
    """
    Only fires when 2+ buy strategies agree. Tests whether
    agreement adds conviction over any single strategy.
    """
    votes = 0

    if strategy_mean_reversion(
        daily_prices=daily_prices, weekly_structure=weekly_structure,
        levels=levels, current_price=current_price, **kwargs,
    ) == "buy":
        votes += 1

    sweep_result = strategy_liquidity_sweep(
        daily_prices=daily_prices, daily_swings=daily_swings,
        weekly_structure=weekly_structure, volume=volume, **kwargs,
    )
    if sweep_result == "buy":
        votes += 1

    if strategy_wyckoff_spring(
        daily_prices=daily_prices, volume=volume, **kwargs,
    ) == "buy":
        votes += 1

    if votes >= 2:
        return "buy"
    return None


# ── Strategy Registry ────────────────────────────────────────────────────────

ALL_STRATEGIES = {
    "confluence_score": {
        "fn": strategy_confluence_score,
        "name": "Confluence Score (Baseline)",
        "description": "Current engine: sum 6 layers + alignment → score → signal",
    },
    "mean_reversion": {
        "fn": strategy_mean_reversion,
        "name": "Mean Reversion at Support",
        "description": "Buy 3+ red candles at support in weekly uptrend, on reversal candle",
    },
    "liquidity_sweep": {
        "fn": strategy_liquidity_sweep,
        "name": "Liquidity Sweep Reversal",
        "description": "Buy when price sweeps below swing low then closes back above",
    },
    "demand_zone": {
        "fn": strategy_demand_zone,
        "name": "Fresh Demand Zone Bounce",
        "description": "Buy at untested demand zone (consolidation→explosion origin)",
    },
    "wyckoff_spring": {
        "fn": strategy_wyckoff_spring,
        "name": "Wyckoff Spring",
        "description": "Buy false breakdown below range support on low volume",
    },
    "failed_breakout": {
        "fn": strategy_failed_breakout,
        "name": "Failed Breakout",
        "description": "Fade a breakout that closes back inside the range",
    },
    "wyckoff_buy_only": {
        "fn": strategy_wyckoff_buy_only,
        "name": "Wyckoff Spring (Buy Only)",
        "description": "Buy false breakdown below range support, no sell signals",
    },
    "ensemble_buy": {
        "fn": strategy_ensemble_buy,
        "name": "Ensemble (3 Buy Strategies)",
        "description": "Mean Reversion + Liquidity Sweep + Wyckoff buy: 1=buy, 2+=strong_buy",
    },
    "ensemble_strict": {
        "fn": strategy_ensemble_strict,
        "name": "Ensemble Strict (2+ Agree)",
        "description": "Only fires when 2+ of the 3 buy strategies agree",
    },
}
