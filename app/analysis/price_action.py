"""
Price action analysis engine — programmatic, rule-based.

Reads raw OHLCV data and produces:
  - Swing points (highs/lows)
  - Market structure (HH/HL/LH/LL, trend, BOS/CHoCH)
  - Support & resistance levels (from swing clusters + MAs)
  - Candlestick patterns (engulfing, pin bar, inside bar, doji)
  - Volume analysis
  - Confluence score (multi-layer, multi-timeframe)

No LLM calls — everything here is deterministic.
"""

from __future__ import annotations

import logging
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


# ── Swing Point Detection ────────────────────────────────────────────────────

def detect_swing_points(
    prices: List[Dict[str, Any]],
    lookback: int = 3,
) -> List[Dict[str, Any]]:
    """
    Detect swing highs and swing lows from OHLCV data.

    A swing high is a bar whose high is greater than the highs of `lookback`
    bars on both sides. Swing lows are the inverse.

    Args:
        prices: OHLCV list sorted by date ASCENDING (oldest first).
        lookback: Number of bars on each side to compare.

    Returns:
        List of swing points: {date, price, type, index}
    """
    swings = []
    n = len(prices)

    for i in range(lookback, n - lookback):
        high = prices[i]["high"]
        low = prices[i]["low"]

        # Check swing high
        is_swing_high = all(
            high > prices[i - j]["high"] and high > prices[i + j]["high"]
            for j in range(1, lookback + 1)
        )
        if is_swing_high:
            swings.append({
                "date": prices[i]["date"],
                "price": high,
                "type": "swing_high",
                "index": i,
            })

        # Check swing low
        is_swing_low = all(
            low < prices[i - j]["low"] and low < prices[i + j]["low"]
            for j in range(1, lookback + 1)
        )
        if is_swing_low:
            swings.append({
                "date": prices[i]["date"],
                "price": low,
                "type": "swing_low",
                "index": i,
            })

    return swings


# ── Market Structure Classification ──────────────────────────────────────────

def classify_market_structure(
    swing_points: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Classify market structure from swing points.

    Labels each swing as HH/LH (highs) or HL/LL (lows), determines
    trend direction, and detects Break of Structure (BOS) and
    Change of Character (CHoCH).

    Returns:
        {
            trend: "uptrend"|"downtrend"|"ranging",
            strength: "strong"|"moderate"|"weak",
            labeled_swings: [{...swing, label: "HH"|"HL"|"LH"|"LL"}],
            bos: None | {type: "bullish"|"bearish", at: swing_point},
            choch: None | {type: "bullish"|"bearish", at: swing_point},
        }
    """
    if len(swing_points) < 4:
        return {
            "trend": "insufficient_data",
            "strength": "weak",
            "labeled_swings": [],
            "bos": None,
            "choch": None,
        }

    # Separate and label swing highs and lows
    highs = [s for s in swing_points if s["type"] == "swing_high"]
    lows = [s for s in swing_points if s["type"] == "swing_low"]

    labeled = []

    # Label highs: HH or LH
    for i, h in enumerate(highs):
        if i == 0:
            label = "HH"  # First high has no reference
        else:
            label = "HH" if h["price"] > highs[i - 1]["price"] else "LH"
        labeled.append({**h, "label": label})

    # Label lows: HL or LL
    for i, l in enumerate(lows):
        if i == 0:
            label = "HL"
        else:
            label = "HL" if l["price"] > lows[i - 1]["price"] else "LL"
        labeled.append({**l, "label": label})

    # Sort by index for chronological order
    labeled.sort(key=lambda x: x["index"])

    # Determine trend from the last 3 swing highs and last 3 swing lows.
    # Using only recent swings keeps the classification responsive — a 4-year
    # uptrend won't mask a current breakdown (Dow Theory: 3 of each is the
    # standard for trend confirmation without excess lag).
    recent_highs = [s for s in labeled if s["type"] == "swing_high"][-3:]
    recent_lows  = [s for s in labeled if s["type"] == "swing_low"][-3:]

    hh_count = sum(1 for s in recent_highs if s["label"] == "HH")
    lh_count = sum(1 for s in recent_highs if s["label"] == "LH")
    hl_count = sum(1 for s in recent_lows  if s["label"] == "HL")
    ll_count = sum(1 for s in recent_lows  if s["label"] == "LL")

    bullish_score = hh_count + hl_count  # max 6
    bearish_score = lh_count + ll_count  # max 6

    if bullish_score >= 5:
        trend = "uptrend"
        strength = "strong"
    elif bullish_score >= 4:
        trend = "uptrend"
        strength = "moderate"
    elif bullish_score == 3 and bearish_score < 3:
        trend = "uptrend"
        strength = "weak"
    elif bearish_score >= 5:
        trend = "downtrend"
        strength = "strong"
    elif bearish_score >= 4:
        trend = "downtrend"
        strength = "moderate"
    elif bearish_score == 3 and bullish_score < 3:
        trend = "downtrend"
        strength = "weak"
    elif bullish_score > bearish_score:
        trend = "uptrend"
        strength = "weak"
    elif bearish_score > bullish_score:
        trend = "downtrend"
        strength = "weak"
    else:
        trend = "ranging"
        strength = "weak"

    # Detect BOS and CHoCH from most recent swings
    bos = None
    choch = None

    if len(labeled) >= 3:
        last = labeled[-1]
        second_last_same_type = None
        for s in reversed(labeled[:-1]):
            if s["type"] == last["type"]:
                second_last_same_type = s
                break

        if second_last_same_type:
            # BOS: trend violation
            if trend == "uptrend" and last["label"] == "LL":
                bos = {"type": "bearish", "at": last}
            elif trend == "uptrend" and last["label"] == "LH":
                bos = {"type": "bearish", "at": last}
            elif trend == "downtrend" and last["label"] == "HH":
                bos = {"type": "bullish", "at": last}
            elif trend == "downtrend" and last["label"] == "HL":
                bos = {"type": "bullish", "at": last}

    # CHoCH: character changed — structure broke AFTER the last trend-confirming swing.
    #
    # Bearish CHoCH: there was a HH somewhere, and AFTER it both LH and LL appeared.
    #   The HH was the peak of the uptrend; the LH+LL after it = trend broke.
    #   If a new HH appeared after the LH+LL, it invalidated the CHoCH.
    #
    # Bullish CHoCH: there was a LL somewhere, and AFTER it both HH and HL appeared.
    #   Same logic inverted.
    #
    # This is independent of the trend label — the trend might already show "ranging"
    # because the breakdown pulled the score down. CHoCH detects the transition.
    all_highs = [s for s in labeled if s["type"] == "swing_high"]
    all_lows = [s for s in labeled if s["type"] == "swing_low"]

    if len(all_highs) >= 2 and len(all_lows) >= 2:
        # Find the last HH and last LL
        last_hh_idx = None
        for s in reversed(all_highs):
            if s["label"] == "HH":
                last_hh_idx = s["index"]
                break

        last_ll_idx = None
        for s in reversed(all_lows):
            if s["label"] == "LL":
                last_ll_idx = s["index"]
                break

        bearish_choch = False
        bullish_choch = False

        # ── Bearish CHoCH: after the last HH, both LH and LL appeared ──
        # No newer HH invalidated it. Most recent low confirms (is LL).
        if last_hh_idx is not None:
            lh_after = any(s["label"] == "LH" and s["index"] > last_hh_idx for s in all_highs)
            ll_after = any(s["label"] == "LL" and s["index"] > last_hh_idx for s in all_lows)
            newer_hh = any(s["label"] == "HH" and s["index"] > last_hh_idx for s in all_highs)
            last_low_is_ll = all_lows[-1]["label"] == "LL"
            if lh_after and ll_after and not newer_hh and last_low_is_ll:
                bearish_choch = True

        # ── Bullish CHoCH: after the last LL, both HH and HL appeared ──
        # No newer LL invalidated it. Most recent high confirms (is HH).
        if last_ll_idx is not None:
            hh_after = any(s["label"] == "HH" and s["index"] > last_ll_idx for s in all_highs)
            hl_after = any(s["label"] == "HL" and s["index"] > last_ll_idx for s in all_lows)
            newer_ll = any(s["label"] == "LL" and s["index"] > last_ll_idx for s in all_lows)
            last_high_is_hh = all_highs[-1]["label"] == "HH"
            if hh_after and hl_after and not newer_ll and last_high_is_hh:
                bullish_choch = True

        # If both fire (transitional), use the more recent pivot
        if bearish_choch and bullish_choch:
            hh_i = last_hh_idx or -1
            ll_i = last_ll_idx or -1
            if ll_i > hh_i:
                choch = {"type": "bullish", "at": labeled[-1]}
            else:
                choch = {"type": "bearish", "at": labeled[-1]}
        elif bearish_choch:
            choch = {"type": "bearish", "at": labeled[-1]}
        elif bullish_choch:
            choch = {"type": "bullish", "at": labeled[-1]}

    return {
        "trend": trend,
        "strength": strength,
        "labeled_swings": labeled,
        "bos": bos,
        "choch": choch,
    }


# ── RSI Divergence Detection ─────────────────────────────────────────────────

def detect_rsi_divergence(
    swing_points: List[Dict[str, Any]],
    rsi_data: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Detect RSI divergence against price swing points.

    Bullish divergence: price makes lower low, RSI makes higher low
      → selling pressure is exhausting, reversal likely
    Bearish divergence: price makes higher high, RSI makes lower high
      → momentum is failing at new highs, reversal likely

    Args:
        swing_points: From detect_swing_points() sorted ascending.
        rsi_data: RSI series newest-first from get_rsi().

    Returns:
        {bullish, bearish, strength: "strong"|"moderate"|None, description}
    """
    result: Dict[str, Any] = {"bullish": False, "bearish": False, "strength": None, "description": ""}

    if not swing_points or not rsi_data:
        return result

    rsi_by_date = {r["date"]: r["value"] for r in rsi_data}

    highs = [s for s in swing_points if s["type"] == "swing_high"]
    lows  = [s for s in swing_points if s["type"] == "swing_low"]

    # Bearish: price HH but RSI LH — momentum failing at new highs
    if len(highs) >= 2:
        h1, h2 = highs[-2], highs[-1]
        rsi_h1 = rsi_by_date.get(h1["date"])
        rsi_h2 = rsi_by_date.get(h2["date"])
        if rsi_h1 is not None and rsi_h2 is not None:
            if h2["price"] > h1["price"] and rsi_h2 < rsi_h1:
                diff = rsi_h1 - rsi_h2
                result["bearish"] = True
                result["strength"] = "strong" if diff > 8 else "moderate"
                result["description"] = (
                    f"Bearish divergence: price HH (${h2['price']:.2f}) but RSI falling "
                    f"({rsi_h2:.1f} vs {rsi_h1:.1f})"
                )

    # Bullish: price LL but RSI HL — selling exhaustion
    if len(lows) >= 2 and not result["bearish"]:
        l1, l2 = lows[-2], lows[-1]
        rsi_l1 = rsi_by_date.get(l1["date"])
        rsi_l2 = rsi_by_date.get(l2["date"])
        if rsi_l1 is not None and rsi_l2 is not None:
            if l2["price"] < l1["price"] and rsi_l2 > rsi_l1:
                diff = rsi_l2 - rsi_l1
                result["bullish"] = True
                result["strength"] = "strong" if diff > 8 else "moderate"
                result["description"] = (
                    f"Bullish divergence: price LL (${l2['price']:.2f}) but RSI rising "
                    f"({rsi_l2:.1f} vs {rsi_l1:.1f})"
                )

    return result


# ── Fibonacci Retracement Levels ──────────────────────────────────────────────

def compute_fibonacci_levels(
    swing_points: List[Dict[str, Any]],
    current_price: float,
) -> List[Dict[str, Any]]:
    """
    Compute Fibonacci retracement levels (38.2%, 50%, 61.8%) from the most
    recent major swing range.

    Uses the highest of the last 3 swing highs and lowest of the last 3 swing
    lows as the range boundaries. The 61.8% level gets strength 2 — it is the
    most-watched level by institutional participants.

    Returns levels with source="fib_382|fib_500|fib_618".
    """
    highs = [s for s in swing_points if s["type"] == "swing_high"]
    lows  = [s for s in swing_points if s["type"] == "swing_low"]

    if not highs or not lows:
        return []

    swing_high = max(h["price"] for h in highs[-3:])
    swing_low  = min(l["price"] for l in lows[-3:])

    if swing_high <= swing_low:
        return []

    rng = swing_high - swing_low
    levels = []

    for ratio, strength in [(0.382, 1), (0.500, 1), (0.618, 2)]:
        price = round(swing_high - ratio * rng, 2)
        level_type = "support" if price < current_price else "resistance"
        levels.append({
            "price": price,
            "type": level_type,
            "strength": strength,
            "source": f"fib_{int(ratio * 1000)}",
            "touches": 0,
            "timeframes": ["daily"],
            "fib_ratio": ratio,
        })

    return levels


# ── Support & Resistance Detection ───────────────────────────────────────────

def find_support_resistance(
    daily_swings: List[Dict[str, Any]],
    weekly_swings: List[Dict[str, Any]],
    current_price: float,
    ma_50: Optional[float] = None,
    ma_200: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    Find support and resistance levels from swing points and moving averages.

    Clusters nearby swing points into zones, scores by touches and recency,
    and merges weekly + daily levels (levels on both TFs get strength bonus).

    Returns list of levels sorted by distance from current price.
    """
    levels = []

    # Collect all swing prices with their timeframe
    all_points = []
    for s in daily_swings:
        all_points.append({"price": s["price"], "tf": "daily", "type": s["type"], "date": s["date"]})
    for s in weekly_swings:
        all_points.append({"price": s["price"], "tf": "weekly", "type": s["type"], "date": s["date"]})

    if not all_points:
        # Still add MA levels if available
        if ma_50 is not None:
            level_type = "support" if current_price > ma_50 else "resistance"
            levels.append({"price": round(ma_50, 2), "type": level_type, "strength": 2, "source": "ma_50", "timeframes": ["daily"]})
        if ma_200 is not None:
            level_type = "support" if current_price > ma_200 else "resistance"
            levels.append({"price": round(ma_200, 2), "type": level_type, "strength": 2, "source": "ma_200", "timeframes": ["daily"]})
        return levels

    # Cluster nearby swing points (within 1.5% of each other)
    all_points.sort(key=lambda x: x["price"])
    clusters = []
    current_cluster = [all_points[0]]

    for p in all_points[1:]:
        if current_cluster and abs(p["price"] - current_cluster[-1]["price"]) / current_cluster[-1]["price"] < 0.015:
            current_cluster.append(p)
        else:
            clusters.append(current_cluster)
            current_cluster = [p]
    clusters.append(current_cluster)

    # Score each cluster
    for cluster in clusters:
        if not cluster:
            continue

        avg_price = sum(p["price"] for p in cluster) / len(cluster)
        touches = len(cluster)
        timeframes = list(set(p["tf"] for p in cluster))

        # Strength: 1 = weak (1-2 touches), 2 = moderate (3-4), 3 = strong (5+)
        strength = min(3, max(1, (touches + 1) // 2))

        # Bonus for multi-timeframe visibility
        if len(timeframes) > 1:
            strength = min(3, strength + 1)

        # Determine if support or resistance relative to current price
        level_type = "support" if avg_price < current_price else "resistance"

        levels.append({
            "price": round(avg_price, 2),
            "type": level_type,
            "strength": strength,
            "source": "swing",
            "touches": touches,
            "timeframes": timeframes,
        })

    # Fibonacci retracement levels — merge with swing clusters where they coincide
    fib_levels = compute_fibonacci_levels(daily_swings + weekly_swings, current_price)
    for fib in fib_levels:
        merged = False
        for lvl in levels:
            if lvl["source"].startswith("swing") and abs(lvl["price"] - fib["price"]) / lvl["price"] < 0.015:
                # Fibonacci confirms this swing level — boost its strength and note the confluence
                lvl["strength"] = min(3, lvl["strength"] + 1)
                lvl["source"] = f"swing+fib_{int(fib['fib_ratio'] * 1000)}"
                merged = True
                break
        if not merged:
            levels.append(fib)

    # Add MA levels
    if ma_50 is not None:
        level_type = "support" if current_price > ma_50 else "resistance"
        levels.append({
            "price": round(ma_50, 2),
            "type": level_type,
            "strength": 2,
            "source": "ma_50",
            "touches": 0,
            "timeframes": ["daily"],
        })

    if ma_200 is not None:
        level_type = "support" if current_price > ma_200 else "resistance"
        levels.append({
            "price": round(ma_200, 2),
            "type": level_type,
            "strength": 2,
            "source": "ma_200",
            "touches": 0,
            "timeframes": ["daily"],
        })

    # Sort by distance from current price
    levels.sort(key=lambda x: abs(x["price"] - current_price))

    # Keep the most relevant levels (closest 5 support + 5 resistance)
    support = [l for l in levels if l["type"] == "support"][:5]
    resistance = [l for l in levels if l["type"] == "resistance"][:5]

    return support + resistance


# ── Candlestick Pattern Detection ────────────────────────────────────────────

def detect_candlestick_patterns(
    prices: List[Dict[str, Any]],
    levels: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """
    Detect candlestick patterns from the most recent bars.

    Scans the last 10 bars for: bullish/bearish engulfing, hammer,
    shooting star, inside bar, doji.

    Args:
        prices: OHLCV sorted ascending (oldest first).
        levels: Optional S/R levels for context scoring.

    Returns:
        List of detected patterns.
    """
    patterns = []
    n = len(prices)
    if n < 2:
        return patterns

    scan_range = min(10, n - 1)

    for i in range(n - scan_range, n):
        curr = prices[i]
        prev = prices[i - 1] if i > 0 else None

        c_open, c_close = curr["open"], curr["close"]
        c_high, c_low = curr["high"], curr["low"]
        c_body = abs(c_close - c_open)
        c_range = c_high - c_low

        if c_range == 0:
            continue

        c_upper_wick = c_high - max(c_open, c_close)
        c_lower_wick = min(c_open, c_close) - c_low
        c_is_bullish = c_close > c_open

        at_level = _is_at_level(curr, levels) if levels else None

        # ── Bullish Engulfing ──
        if prev:
            p_open, p_close = prev["open"], prev["close"]
            p_is_bearish = p_close < p_open
            p_body = abs(p_close - p_open)

            if (p_is_bearish and c_is_bullish
                    and c_body > p_body
                    and c_close >= p_open
                    and c_open <= p_close):
                strength = 2 if (at_level and at_level["type"] == "support") else 1
                patterns.append({
                    "name": "bullish_engulfing",
                    "direction": "bullish",
                    "bar_index": i,
                    "date": curr["date"],
                    "strength": strength,
                    "at_level": at_level,
                })

            # ── Bearish Engulfing ──
            p_is_bullish = p_close > p_open
            if (p_is_bullish and not c_is_bullish
                    and c_body > p_body
                    and c_open >= p_close
                    and c_close <= p_open):
                strength = 2 if (at_level and at_level["type"] == "resistance") else 1
                patterns.append({
                    "name": "bearish_engulfing",
                    "direction": "bearish",
                    "bar_index": i,
                    "date": curr["date"],
                    "strength": strength,
                    "at_level": at_level,
                })

        # ── Hammer / Bullish Pin Bar ──
        if (c_lower_wick >= 2 * c_body
                and c_upper_wick < c_body * 0.5
                and c_body > 0
                and c_range > 0):
            strength = 2 if (at_level and at_level["type"] == "support") else 1
            patterns.append({
                "name": "hammer",
                "direction": "bullish",
                "bar_index": i,
                "date": curr["date"],
                "strength": strength,
                "at_level": at_level,
            })

        # ── Shooting Star / Bearish Pin Bar ──
        if (c_upper_wick >= 2 * c_body
                and c_lower_wick < c_body * 0.5
                and c_body > 0
                and c_range > 0):
            strength = 2 if (at_level and at_level["type"] == "resistance") else 1
            patterns.append({
                "name": "shooting_star",
                "direction": "bearish",
                "bar_index": i,
                "date": curr["date"],
                "strength": strength,
                "at_level": at_level,
            })

        # ── Inside Bar ──
        if prev:
            if curr["high"] < prev["high"] and curr["low"] > prev["low"]:
                patterns.append({
                    "name": "inside_bar",
                    "direction": "neutral",
                    "bar_index": i,
                    "date": curr["date"],
                    "strength": 1,
                    "at_level": at_level,
                })

        # ── Doji ──
        if c_range > 0 and c_body < 0.10 * c_range:
            patterns.append({
                "name": "doji",
                "direction": "neutral",
                "bar_index": i,
                "date": curr["date"],
                "strength": 1,
                "at_level": at_level,
            })

        # ── Multi-bar patterns (need 2 prior bars) ──
        if i < 2:
            continue
        prev_prev = prices[i - 2]
        pp_open, pp_close = prev_prev["open"], prev_prev["close"]
        pp_body = abs(pp_close - pp_open)
        pp_range = prev_prev["high"] - prev_prev["low"]

        if prev:
            p_open, p_close = prev["open"], prev["close"]
            p_body = abs(p_close - p_open)
            p_range = prev["high"] - prev["low"]

            # ── Three White Soldiers (strong bullish continuation) ──
            if (pp_close > pp_open and p_close > p_open and c_is_bullish
                    and p_close > pp_close and c_close > p_close
                    and pp_body > 0.3 * pp_range if pp_range > 0 else False
                    and p_body > 0.3 * p_range if p_range > 0 else False
                    and c_body > 0.3 * c_range):
                strength = 2 if (at_level and at_level["type"] == "support") else 1
                patterns.append({
                    "name": "three_white_soldiers",
                    "direction": "bullish",
                    "bar_index": i,
                    "date": curr["date"],
                    "strength": strength,
                    "at_level": at_level,
                })

            # ── Three Black Crows (strong bearish continuation) ──
            if (pp_close < pp_open and p_close < p_open and not c_is_bullish
                    and p_close < pp_close and c_close < p_close
                    and pp_body > 0.3 * pp_range if pp_range > 0 else False
                    and p_body > 0.3 * p_range if p_range > 0 else False
                    and c_body > 0.3 * c_range):
                strength = 2 if (at_level and at_level["type"] == "resistance") else 1
                patterns.append({
                    "name": "three_black_crows",
                    "direction": "bearish",
                    "bar_index": i,
                    "date": curr["date"],
                    "strength": strength,
                    "at_level": at_level,
                })

            # ── Morning Star (3-bar bullish reversal) ──
            pp_is_bearish = pp_close < pp_open
            p_small_body = p_body < 0.30 * p_range if p_range > 0 else True
            pp_midpoint = (pp_open + pp_close) / 2
            if (pp_is_bearish and pp_body > 0 and p_small_body
                    and c_is_bullish and c_close > pp_midpoint):
                strength = 2 if (at_level and at_level["type"] == "support") else 1
                patterns.append({
                    "name": "morning_star",
                    "direction": "bullish",
                    "bar_index": i,
                    "date": curr["date"],
                    "strength": strength,
                    "at_level": at_level,
                })

            # ── Evening Star (3-bar bearish reversal) ──
            pp_is_bullish = pp_close > pp_open
            pp_midpoint_e = (pp_open + pp_close) / 2
            if (pp_is_bullish and pp_body > 0 and p_small_body
                    and not c_is_bullish and c_close < pp_midpoint_e):
                strength = 2 if (at_level and at_level["type"] == "resistance") else 1
                patterns.append({
                    "name": "evening_star",
                    "direction": "bearish",
                    "bar_index": i,
                    "date": curr["date"],
                    "strength": strength,
                    "at_level": at_level,
                })

    return patterns


def _is_at_level(
    bar: Dict[str, Any],
    levels: Optional[List[Dict[str, Any]]],
    tolerance_pct: float = 0.015,
) -> Optional[Dict[str, Any]]:
    """Check if a bar's price is near a support/resistance level."""
    if not levels:
        return None

    price = bar["close"]
    for level in levels:
        if abs(price - level["price"]) / level["price"] < tolerance_pct:
            return level
    return None


# ── ATR (Average True Range) ──────────────────────────────────────────────────

def compute_atr(prices: List[Dict[str, Any]], period: int = 14) -> float:
    """
    Compute the current ATR value using Wilder's smoothing.

    ATR measures average daily price range — used for:
      - ATR-relative S/R proximity (replaces fixed 2% threshold)
      - Qualifying gap significance
      - Strategy signal filtering
    """
    if len(prices) < period + 1:
        return 0.0

    tr_values = []
    for i in range(1, len(prices)):
        high = prices[i]["high"]
        low = prices[i]["low"]
        prev_close = prices[i - 1]["close"]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        tr_values.append(tr)

    if len(tr_values) < period:
        return sum(tr_values) / len(tr_values) if tr_values else 0.0

    atr = sum(tr_values[:period]) / period
    for i in range(period, len(tr_values)):
        atr = (atr * (period - 1) + tr_values[i]) / period

    return round(atr, 4)


# ── Gap Detection ────────────────────────────────────────────────────────────

def detect_gaps(
    prices: List[Dict[str, Any]],
    levels: Optional[List[Dict[str, Any]]] = None,
    atr: float = 0.0,
) -> List[Dict[str, Any]]:
    """
    Detect price gaps in the last 10 bars.

    A gap is when the open is significantly above/below the previous close.
    Gaps through S/R levels are especially significant.

    Threshold: 0.5 * ATR if ATR available, else 0.5% of price.
    """
    gaps = []
    n = len(prices)
    if n < 2:
        return gaps

    scan_start = max(1, n - 10)
    for i in range(scan_start, n):
        curr_open = prices[i]["open"]
        prev_close = prices[i - 1]["close"]
        gap_size = curr_open - prev_close

        threshold = 0.5 * atr if atr > 0 else prev_close * 0.005
        if abs(gap_size) < threshold:
            continue

        gap_pct = round(gap_size / prev_close * 100, 2)
        gap_type = "gap_up" if gap_size > 0 else "gap_down"
        direction = "bullish" if gap_size > 0 else "bearish"

        # Check if the gap went through an S/R level
        through_level = None
        if levels:
            for lvl in levels:
                lp = lvl["price"]
                if gap_size > 0 and prev_close < lp <= curr_open:
                    through_level = lvl
                    break
                elif gap_size < 0 and curr_open <= lp < prev_close:
                    through_level = lvl
                    break

        gaps.append({
            "date": prices[i]["date"],
            "type": gap_type,
            "gap_size": round(abs(gap_size), 2),
            "gap_pct": abs(gap_pct),
            "direction": direction,
            "through_level": {
                "price": through_level["price"],
                "type": through_level["type"],
                "strength": through_level.get("strength", 1),
            } if through_level else None,
        })

    return gaps


# ── Risk/Reward Ratio ────────────────────────────────────────────────────────

def compute_risk_reward(
    levels: List[Dict[str, Any]],
    current_price: float,
    atr: float = 0.0,
) -> Dict[str, Any]:
    """
    Compute risk/reward ratio from nearest support (stop) and resistance (target).

    Returns distances, ratio, and a qualitative assessment.
    """
    supports = [l for l in levels if l["type"] == "support" and l["price"] < current_price]
    resistances = [l for l in levels if l["type"] == "resistance" and l["price"] > current_price]

    nearest_support = max(supports, key=lambda l: l["price"]) if supports else None
    nearest_resistance = min(resistances, key=lambda l: l["price"]) if resistances else None

    result: Dict[str, Any] = {
        "nearest_support": nearest_support["price"] if nearest_support else None,
        "nearest_resistance": nearest_resistance["price"] if nearest_resistance else None,
        "risk_pct": None,
        "reward_pct": None,
        "ratio": None,
        "assessment": "unknown",
    }

    if nearest_support:
        result["risk_pct"] = round((current_price - nearest_support["price"]) / current_price * 100, 2)
    if nearest_resistance:
        result["reward_pct"] = round((nearest_resistance["price"] - current_price) / current_price * 100, 2)

    if result["risk_pct"] and result["risk_pct"] > 0 and result["reward_pct"]:
        ratio = round(result["reward_pct"] / result["risk_pct"], 2)
        result["ratio"] = ratio
        if ratio >= 3.0:
            result["assessment"] = "excellent"
        elif ratio >= 2.0:
            result["assessment"] = "favorable"
        elif ratio >= 1.0:
            result["assessment"] = "marginal"
        else:
            result["assessment"] = "unfavorable"

    return result


# ── Volume Analysis ──────────────────────────────────────────────────────────

def analyze_volume(prices: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analyze volume patterns from OHLCV data.

    Args:
        prices: OHLCV sorted ascending (oldest first).

    Returns:
        Volume analysis with averages, ratio, trend, and confirmation status.
    """
    if len(prices) < 20:
        return {
            "avg_20d": 0,
            "current_volume": prices[-1]["volume"] if prices else 0,
            "current_ratio": 0,
            "trend": "insufficient_data",
            "confirming": False,
        }

    volumes = [p["volume"] for p in prices]
    avg_20d = sum(volumes[-20:]) / 20
    current_vol = volumes[-1]
    ratio = round(current_vol / avg_20d, 2) if avg_20d > 0 else 0

    # Volume trend: last 5-day avg vs previous 5-day avg
    if len(volumes) >= 10:
        recent_5 = sum(volumes[-5:]) / 5
        prev_5 = sum(volumes[-10:-5]) / 5
        if prev_5 > 0:
            vol_change = (recent_5 - prev_5) / prev_5
            if vol_change > 0.15:
                trend = "increasing"
            elif vol_change < -0.15:
                trend = "decreasing"
            else:
                trend = "flat"
        else:
            trend = "flat"
    else:
        trend = "flat"

    # Is volume confirming price action?
    # Up move + above-avg volume = bullish confirmation
    # Down move + above-avg volume = bearish confirmation
    last_close = prices[-1]["close"]
    prev_close = prices[-2]["close"] if len(prices) >= 2 else last_close
    price_up = last_close > prev_close
    above_avg = ratio > 1.3

    if above_avg and price_up:
        confirming = True
        confirmation_type = "bullish"
    elif above_avg and not price_up:
        confirming = True
        confirmation_type = "bearish"
    else:
        confirming = False
        confirmation_type = "none"

    return {
        "avg_20d": int(avg_20d),
        "current_volume": current_vol,
        "current_ratio": ratio,
        "trend": trend,
        "confirming": confirming,
        "confirmation_type": confirmation_type,
    }


# ── Confluence Scoring Engine ────────────────────────────────────────────────

SCORE_MAP = {
    "strong_buy": (7, 14),
    "buy": (4, 6),
    "neutral": (-3, 3),
    "sell": (-6, -4),
    "strong_sell": (-14, -7),
}


def compute_confluence_score(
    weekly_structure: Dict[str, Any],
    daily_structure: Dict[str, Any],
    levels: List[Dict[str, Any]],
    patterns: List[Dict[str, Any]],
    volume: Dict[str, Any],
    current_price: float,
    rsi_data: Optional[List[Dict[str, Any]]] = None,
    macd_data: Optional[List[Dict[str, Any]]] = None,
    ma_signals: Optional[Dict[str, Any]] = None,
    rsi_divergence: Optional[Dict[str, Any]] = None,
    atr: float = 0.0,
    gaps: Optional[List[Dict[str, Any]]] = None,
    insider_txns: Optional[List[Dict[str, Any]]] = None,
    institutional: Optional[Dict[str, Any]] = None,
    earnings: Optional[Dict[str, Any]] = None,
    income: Optional[Dict[str, Any]] = None,
    daily_prices: Optional[List[Dict[str, Any]]] = None,
    sector_change_pct: Optional[float] = None,
    market_regime: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Compute the multi-layer confluence score.

    Weights calibrated against academic evidence:
      1. Weekly trend (±3)          — Moderate: Dow Theory, 62.5% continuation
      2. Daily structure (±2)       — Moderate: trend persistence
      3. Key levels (±2)            — Moderate: Osler 2000, 60.8% bounce rate
      4. Candlestick patterns (±1)  — Weak: Duvinage et al, barely above random
      5. Volume confirmation (±1)   — Weak: Karpoff 1987, contemporaneous only
      6. Indicators: RSI+MACD (±2)  — RSI moderate (81% direction), MACD weak
      7. Moving average signals (±2) — Moderate: drawdown reduction value
      8. Price momentum (±3)        — STRONGEST: Jegadeesh & Titman 1993, ~1%/mo alpha
      9. Insider activity (±2)      — Strong: 4.8% excess 12-month returns
     10. Institutional holdings (±1) — Moderate
     11. Revenue acceleration (±1)  — Moderate
     13. Relative strength (±2)     — Strong: momentum anomaly
    + Timeframe alignment modifier (±2)

    Returns:
        {total_score, signal, max_score, layers: [{name, score, max, reasoning}], alignment}
    """
    layers = []
    total = 0

    # ── Layer 1: Weekly Trend (±3) ──
    w_score, w_reason = _score_weekly_trend(weekly_structure)
    layers.append({"name": "Weekly Trend", "score": w_score, "max": 3, "reasoning": w_reason})
    total += w_score

    # ── Layer 2: Daily Structure (±2) — scored independently, alignment handled separately ──
    d_score, d_reason = _score_daily_structure(daily_structure)
    layers.append({"name": "Daily Structure", "score": d_score, "max": 2, "reasoning": d_reason})
    total += d_score

    # ── Layer 3: Key Levels (±2) ──
    l_score, l_reason = _score_key_levels(levels, current_price, daily_structure.get("trend", "ranging"), atr=atr, gaps=gaps)
    layers.append({"name": "Key Levels", "score": l_score, "max": 2, "reasoning": l_reason})
    total += l_score

    # ── Layer 4: Candlestick Patterns (±1) ──
    p_score, p_reason = _score_patterns(patterns)
    layers.append({"name": "Candlestick Patterns", "score": p_score, "max": 1, "reasoning": p_reason})
    total += p_score

    # ── Layer 5: Volume (±1) — filter, not primary signal ──
    v_score, v_reason = _score_volume(volume, daily_structure)
    layers.append({"name": "Volume", "score": v_score, "max": 1, "reasoning": v_reason})
    total += v_score

    # ── Layer 6: RSI Divergence + MACD (±2) ──
    i_score, i_reason = _score_indicators(rsi_data, macd_data, rsi_divergence)
    layers.append({"name": "Indicators", "score": i_score, "max": 2, "reasoning": i_reason})
    total += i_score

    # ── Layer 7: Moving Average Signals (±2) ──
    ma_score, ma_reason = _score_moving_averages(ma_signals)
    layers.append({"name": "Moving Averages", "score": ma_score, "max": 2, "reasoning": ma_reason})
    total += ma_score

    # ── Layer 8: Price Momentum (±3) — strongest academic anomaly ──
    mom_score, mom_reason = _score_momentum(daily_prices)
    layers.append({"name": "Price Momentum", "score": mom_score, "max": 3, "reasoning": mom_reason})
    total += mom_score

    # ── Layer 9: Insider Activity (±2) ──
    ins_score, ins_reason = _score_insider_activity(insider_txns)
    layers.append({"name": "Insider Activity", "score": ins_score, "max": 2, "reasoning": ins_reason})
    total += ins_score

    # ── Layer 10: Institutional Holdings (±1) ──
    inst_score, inst_reason = _score_institutional_holdings(institutional)
    layers.append({"name": "Institutional", "score": inst_score, "max": 1, "reasoning": inst_reason})
    total += inst_score

    # ── Layer 11: Revenue Acceleration (±1) ──
    rev_score, rev_reason = _score_revenue_acceleration(income)
    layers.append({"name": "Revenue", "score": rev_score, "max": 1, "reasoning": rev_reason})
    total += rev_score

    # ── Layer 13: Relative Strength vs Sector (±2) — momentum anomaly ──
    rs_score, rs_reason = _score_relative_strength(daily_prices, sector_change_pct)
    layers.append({"name": "Relative Strength", "score": rs_score, "max": 2, "reasoning": rs_reason})
    total += rs_score

    # ── Timeframe Alignment Modifier (±2) ──
    alignment_score, alignment_reason = _score_alignment(weekly_structure, daily_structure)
    total += alignment_score

    # ── Signal thresholds: adjusted by volume and market regime ──
    # Base thresholds
    buy_thresh, strong_buy_thresh = 4, 7

    # Volume gate: low participation raises the bar.
    vol_ratio = volume.get("current_ratio", 1.0) if volume else 1.0
    vol_note = ""
    if vol_ratio < 0.8:
        buy_thresh += 2
        strong_buy_thresh += 2
        vol_note = "low volume"
    elif vol_ratio > 1.3:
        buy_thresh -= 1
        strong_buy_thresh -= 1
        vol_note = "high volume"

    # Market regime gate: risk-off environment raises the bar for buys.
    regime_note = ""
    if market_regime:
        regime_type = market_regime.get("regime", "neutral")
        if regime_type == "risk_off":
            buy_thresh += 2
            strong_buy_thresh += 2
            regime_note = "risk-off market"
        elif regime_type == "risk_on":
            buy_thresh -= 1
            strong_buy_thresh -= 1
            regime_note = "risk-on market"

    # Combine gate notes
    gate_parts = [n for n in [vol_note, regime_note] if n]
    gate_note = " + ".join(gate_parts)
    if gate_note:
        gate_note += " — threshold adjusted"

    if total >= strong_buy_thresh:
        signal = "strong_buy"
    elif total >= buy_thresh:
        signal = "buy"
    elif total <= -strong_buy_thresh:
        signal = "strong_sell"
    elif total <= -buy_thresh:
        signal = "sell"
    else:
        signal = "neutral"

    rr = compute_risk_reward(levels, current_price, atr)

    return {
        "total_score": total,
        "signal": signal,
        "max_score": 24,
        "buy_threshold": buy_thresh,
        "layers": layers,
        "alignment": {"score": alignment_score, "reasoning": alignment_reason},
        "risk_reward": rr,
        "volume_gate": gate_note,
    }


def _score_weekly_trend(structure: Dict[str, Any]) -> Tuple[int, str]:
    """Score the weekly trend. Returns (score, reasoning)."""
    trend = structure.get("trend", "ranging")
    strength = structure.get("strength", "weak")

    if trend == "uptrend":
        if strength == "strong":
            return 3, "Strong weekly uptrend (consistent HH + HL)"
        elif strength == "moderate":
            return 2, "Moderate weekly uptrend"
        else:
            return 1, "Weak weekly uptrend"
    elif trend == "downtrend":
        if strength == "strong":
            return -3, "Strong weekly downtrend (consistent LH + LL)"
        elif strength == "moderate":
            return -2, "Moderate weekly downtrend"
        else:
            return -1, "Weak weekly downtrend"
    else:
        return 0, "Weekly structure is ranging / no clear trend"


def _score_daily_structure(
    structure: Dict[str, Any],
) -> Tuple[int, str]:
    """
    Score the daily market structure on its own merits (±2).

    Weekly context is handled separately by _score_alignment to avoid
    double-counting. This function scores only the daily trend direction,
    BOS (trend weakening), and CHoCH (trend reversing).
    """
    trend = structure.get("trend", "ranging")
    strength = structure.get("strength", "weak")
    bos = structure.get("bos")
    choch = structure.get("choch")

    base = 0
    reason_parts = []

    if trend == "uptrend":
        base = 2 if strength in ("strong", "moderate") else 1
        reason_parts.append(f"Daily {strength} uptrend")
    elif trend == "downtrend":
        base = -2 if strength in ("strong", "moderate") else -1
        reason_parts.append(f"Daily {strength} downtrend")
    else:
        reason_parts.append("Daily structure is ranging")

    # BOS: trend weakening — pulls score toward neutral
    if bos:
        if bos["type"] == "bearish" and base > 0:
            base -= 1
            reason_parts.append("Bearish BOS — trend weakening")
        elif bos["type"] == "bullish" and base < 0:
            base += 1
            reason_parts.append("Bullish BOS — trend weakening")

    # CHoCH: both highs AND lows violated — strongest structure signal
    if choch:
        if choch["type"] == "bullish":
            base += 1
            reason_parts.append("Bullish CHoCH — potential reversal to upside")
        elif choch["type"] == "bearish":
            base -= 1
            reason_parts.append("Bearish CHoCH — potential reversal to downside")

    base = max(-2, min(2, base))
    return base, "; ".join(reason_parts) if reason_parts else "No clear daily structure"


def _score_key_levels(
    levels: List[Dict[str, Any]],
    current_price: float,
    daily_trend: str,
    atr: float = 0.0,
    gaps: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[int, str]:
    """
    Score price position relative to S/R levels (±2).

    Osler (2000, NY Fed) showed S/R has a real but modest edge
    (60.8% bounce rate vs 56.2% random). Capped at ±2 to reflect this.

    Uses ATR-relative proximity when ATR is available (1.5 * ATR),
    otherwise falls back to 2% of price. Also considers gaps through
    levels as additional conviction.
    """
    if not levels:
        return 0, "No key levels identified"

    supports = [l for l in levels if l["type"] == "support"]
    resistances = [l for l in levels if l["type"] == "resistance"]

    nearest_support = min(supports, key=lambda l: abs(l["price"] - current_price)) if supports else None
    nearest_resistance = min(resistances, key=lambda l: abs(l["price"] - current_price)) if resistances else None

    score = 0
    reasons = []

    # ATR-relative proximity, or 2% fallback
    proximity = 1.5 * atr if atr > 0 else current_price * 0.02

    if nearest_support:
        dist = abs(current_price - nearest_support["price"])
        if dist < proximity:
            strength = nearest_support.get("strength", 1)
            if current_price >= nearest_support["price"]:
                # Price is AT or ABOVE support — bounce expected → bullish
                score += strength
                reasons.append(f"At support ${nearest_support['price']} (strength {strength})")
            else:
                # Price is BELOW support — support broke → bearish
                score -= strength
                reasons.append(f"Broke below support ${nearest_support['price']} (strength {strength}) — now resistance")

    if nearest_resistance:
        dist = abs(nearest_resistance["price"] - current_price)
        if dist < proximity:
            strength = nearest_resistance.get("strength", 1)
            if current_price <= nearest_resistance["price"]:
                # Price is AT or BELOW resistance — rejection expected → bearish
                score -= strength
                reasons.append(f"At resistance ${nearest_resistance['price']} (strength {strength})")
            else:
                # Price is ABOVE resistance — resistance broke → bullish
                score += strength
                reasons.append(f"Broke above resistance ${nearest_resistance['price']} (strength {strength}) — now support")

    # Gap through a level adds conviction (±1)
    if gaps:
        recent_gaps = [g for g in gaps if g.get("through_level")]
        for g in recent_gaps[-1:]:  # only the most recent gap-through-level
            if g["direction"] == "bullish":
                score += 1
                reasons.append(f"Gap up through {g['through_level']['type']} ${g['through_level']['price']}")
            else:
                score -= 1
                reasons.append(f"Gap down through {g['through_level']['type']} ${g['through_level']['price']}")

    score = max(-2, min(2, score))

    if not reasons:
        reasons.append("Price not at any key level")

    return score, "; ".join(reasons)


def _score_patterns(patterns: List[Dict[str, Any]]) -> Tuple[int, str]:
    """Score candlestick patterns from the most recent bars."""
    if not patterns:
        return 0, "No candlestick patterns detected"

    # Focus on the most recent patterns (last 3 bars)
    recent = [p for p in patterns if p.get("bar_index", 0) >= (patterns[-1].get("bar_index", 0) - 2)] if patterns else []

    if not recent:
        return 0, "No recent candlestick patterns"

    score = 0
    names = []

    for p in recent:
        direction = p.get("direction", "neutral")
        strength = p.get("strength", 1)
        name = p.get("name", "unknown")

        if direction == "bullish":
            score += strength
            names.append(f"Bullish {name.replace('_', ' ')}")
        elif direction == "bearish":
            score -= strength
            names.append(f"Bearish {name.replace('_', ' ')}")
        else:
            names.append(name.replace("_", " ").title())

    score = max(-1, min(1, score))
    return score, "; ".join(names)


def _score_volume(
    volume: Dict[str, Any],
    daily_structure: Optional[Dict[str, Any]] = None,
) -> Tuple[int, str]:
    """
    Score volume confirmation, enhanced with structure context (±1).

    Karpoff (1987) showed volume correlates with contemporaneous moves
    but has weak predictive power. Capped at ±1 — useful as filter,
    not primary signal.

    Evaluates: basic volume-price confirmation + structure-event conviction
    on BOS/CHoCH events (high volume = real, low volume = possible fakeout).
    """
    if not volume or volume.get("trend") == "insufficient_data":
        return 0, "Insufficient volume data"

    confirming = volume.get("confirming", False)
    conf_type = volume.get("confirmation_type", "none")
    ratio = volume.get("current_ratio", 0)

    score = 0
    reasons = []

    # ── Basic volume-price confirmation (±1) ──
    if confirming and conf_type == "bullish":
        score += 1
        reasons.append(f"Volume confirming bullish move ({ratio}x avg)")
    elif confirming and conf_type == "bearish":
        score -= 1
        reasons.append(f"Volume confirming bearish move ({ratio}x avg)")
    elif ratio < 0.5:
        reasons.append(f"Very low volume ({ratio}x avg) — weak conviction")
    else:
        reasons.append(f"Volume neutral ({ratio}x avg)")

    # ── Structure-volume alignment (±1) ──
    # A BOS/CHoCH on high volume has conviction; on low volume it's suspect
    if daily_structure:
        d_choch = daily_structure.get("choch")
        d_bos = daily_structure.get("bos")
        event = d_choch or d_bos  # CHoCH takes precedence (more significant)
        event_label = "CHoCH" if d_choch else "BOS"

        if event:
            if ratio > 1.3:
                # High volume on structure break = conviction
                if event["type"] == "bullish":
                    score += 1
                    reasons.append(f"{event_label} (bullish) on high volume — conviction")
                else:
                    score -= 1
                    reasons.append(f"{event_label} (bearish) on high volume — conviction")
            elif ratio < 0.7:
                reasons.append(
                    f"{event_label} ({event['type']}) on low volume ({ratio}x) — "
                    "possible fakeout"
                )

    return max(-1, min(1, score)), "; ".join(reasons)


def _score_indicators(
    rsi_data: Optional[List[Dict[str, Any]]],
    macd_data: Optional[List[Dict[str, Any]]],
    rsi_divergence: Optional[Dict[str, Any]] = None,
) -> Tuple[int, str]:
    """
    Score RSI divergence (primary, ±1.5) + MACD crossover (minor, ±0.25).
    Max ±2.

    RSI predicts direction correctly 81% of the time (academic studies).
    MACD alone has below 50% win rate — essentially noise. Kept at minimal
    weight for crossover confirmation only.
    """
    score: float = 0.0
    reasons: List[str] = []

    # RSI Divergence — primary signal
    if rsi_divergence and (rsi_divergence.get("bullish") or rsi_divergence.get("bearish")):
        pts = 1.5 if rsi_divergence.get("strength") == "strong" else 1.0
        if rsi_divergence["bullish"]:
            score += pts
            reasons.append(rsi_divergence.get("description", "Bullish RSI divergence"))
        else:
            score -= pts
            reasons.append(rsi_divergence.get("description", "Bearish RSI divergence"))
    elif rsi_data:
        # No divergence — absolute RSI as minor fallback signal
        rsi_val = rsi_data[0].get("value", 50)
        if rsi_val < 30:
            score += 0.5
            reasons.append(f"RSI oversold ({rsi_val:.1f}) — no divergence")
        elif rsi_val > 70:
            score -= 0.5
            reasons.append(f"RSI overbought ({rsi_val:.1f}) — no divergence")
        else:
            reasons.append(f"RSI neutral ({rsi_val:.1f})")

    # MACD crossover — confirmation
    if macd_data and len(macd_data) >= 2:
        curr = macd_data[0]
        prev = macd_data[1]
        hist = curr.get("histogram", 0)
        prev_hist = prev.get("histogram", 0)
        if hist > 0 and prev_hist <= 0:
            score += 0.25
            reasons.append("MACD bullish crossover (minor)")
        elif hist < 0 and prev_hist >= 0:
            score -= 0.25
            reasons.append("MACD bearish crossover (minor)")
        elif hist > prev_hist:
            reasons.append("MACD histogram increasing")
        else:
            reasons.append("MACD histogram decreasing")

    final = max(-2, min(2, int(round(score))))
    return final, "; ".join(reasons) if reasons else "No indicator data"


def _score_moving_averages(ma_signals: Optional[Dict[str, Any]]) -> Tuple[int, str]:
    """Score MA signals — price position, alignment, crossovers (max ±2)."""
    if not ma_signals:
        return 0, "No MA data available"

    score: float = 0.0
    reasons: List[str] = []

    # Price vs 200MA (±1) — primary signal
    p200 = ma_signals.get("price_vs_200")
    ma200 = ma_signals.get("ma_200_value")
    if p200 == "above":
        score += 1.0
        reasons.append(f"Price above 200MA (${ma200:.2f})" if ma200 else "Price above 200MA")
    elif p200 == "below":
        score -= 1.0
        reasons.append(f"Price below 200MA (${ma200:.2f})" if ma200 else "Price below 200MA")

    # 50MA vs 200MA alignment (±0.5)
    alignment = ma_signals.get("ma_alignment", "neutral")
    if alignment == "bullish":
        score += 0.5
        reasons.append("50MA above 200MA — bullish alignment")
    elif alignment == "bearish":
        score -= 0.5
        reasons.append("50MA below 200MA — bearish alignment")

    # Recent crossover (±0.5)
    if ma_signals.get("golden_cross"):
        score += 0.5
        reasons.append("Recent golden cross (50MA crossed above 200MA)")
    elif ma_signals.get("death_cross"):
        score -= 0.5
        reasons.append("Recent death cross (50MA crossed below 200MA)")

    final = max(-2, min(2, int(round(score))))
    return final, "; ".join(reasons) if reasons else "No MA signal"


def _score_alignment(
    weekly_structure: Dict[str, Any],
    daily_structure: Dict[str, Any],
) -> Tuple[int, str]:
    """
    Score timeframe alignment between weekly and daily.

    Uses weekly BOS/CHoCH to determine severity of conflict:
    - Aligned → +2 (high confidence continuation)
    - Opposing but weekly intact → 0 (pullback, watch for reversal setup)
    - Opposing + weekly BOS → -1 (early reversal warning)
    - Opposing + weekly CHoCH → -2 (real reversal risk)
    """
    w_trend = weekly_structure.get("trend", "ranging")
    d_trend = daily_structure.get("trend", "ranging")
    w_bos = weekly_structure.get("bos")
    w_choch = weekly_structure.get("choch")

    if w_trend == "ranging" or d_trend == "ranging":
        return 0, "One or both timeframes ranging — no alignment signal"

    if w_trend == d_trend:
        return 2, f"Weekly and daily aligned ({w_trend}) — high confidence continuation"

    # Opposing directions — severity depends on weekly health and CHoCH direction
    if w_choch:
        choch_type = w_choch.get("type", "")
        # CHoCH direction matters:
        # - Bearish CHoCH + daily downtrend = both breaking down → -2
        # - Bullish CHoCH + daily downtrend = weekly recovering, daily lagging → 0
        # - Bearish CHoCH + daily uptrend = weekly breaking, daily still up → -1
        # - Bullish CHoCH + daily uptrend = both turning up → +1
        if choch_type == "bearish" and d_trend == "downtrend":
            return -2, f"Weekly bearish CHoCH + daily downtrend — trend reversal confirmed"
        elif choch_type == "bearish" and d_trend == "uptrend":
            return -1, f"Weekly bearish CHoCH but daily still uptrend — early warning"
        elif choch_type == "bullish" and d_trend == "downtrend":
            return 0, f"Weekly bullish CHoCH but daily still falling — recovery not confirmed"
        elif choch_type == "bullish" and d_trend == "uptrend":
            return 1, f"Weekly bullish CHoCH + daily uptrend — recovery gaining momentum"
    elif w_bos:
        # Weekly has early warning but no full reversal yet
        return -1, f"Weekly BOS ({w_bos['type']}) + daily {d_trend} — early reversal signal"
    else:
        # Weekly trend is intact; daily is just pulling back within it
        return 0, f"Daily {d_trend} is a pullback within weekly {w_trend} — watch for reversal setup"


# ── Price Momentum Scoring ────────────────────────────────────────────────────

def _score_momentum(
    daily_prices: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[int, str]:
    """
    Score pure price momentum (±3).

    Momentum is the single strongest anomaly in academic finance
    (Jegadeesh & Titman 1993, ~1% monthly alpha, survives 30+ years of scrutiny).

    Uses 63-day (3-month) rate of change, skipping the most recent 5 days
    to avoid short-term reversal effects. Also checks 126-day (6-month) for
    stronger confirmation.

    Scoring:
      +3: Strong momentum (3m > 15% AND 6m > 25%)
      +2: Moderate momentum (3m > 8%)
      +1: Mild momentum (3m > 3%)
      -1: Mild weakness (3m < -3%)
      -2: Moderate weakness (3m < -8%)
      -3: Strong weakness (3m < -15% AND 6m < -25%)
       0: Flat or insufficient data
    """
    if not daily_prices or len(daily_prices) < 70:
        return 0, "Insufficient price history for momentum"

    current = daily_prices[-6]["close"]  # skip last 5 days (reversal effect)
    price_63d = daily_prices[-68]["close"] if len(daily_prices) >= 68 else daily_prices[0]["close"]
    roc_3m = (current - price_63d) / price_63d * 100

    # 6-month momentum for strong signal confirmation
    roc_6m = None
    if len(daily_prices) >= 131:
        price_126d = daily_prices[-131]["close"]
        roc_6m = (current - price_126d) / price_126d * 100

    reasons = []

    if roc_6m is not None and roc_3m > 15 and roc_6m > 25:
        reasons.append(f"Strong upward momentum (3m: {roc_3m:+.1f}%, 6m: {roc_6m:+.1f}%)")
        return 3, "; ".join(reasons)
    elif roc_3m > 8:
        reasons.append(f"Moderate upward momentum (3m: {roc_3m:+.1f}%)")
        return 2, "; ".join(reasons)
    elif roc_3m > 3:
        reasons.append(f"Mild upward momentum (3m: {roc_3m:+.1f}%)")
        return 1, "; ".join(reasons)
    elif roc_6m is not None and roc_3m < -15 and roc_6m < -25:
        reasons.append(f"Strong downward momentum (3m: {roc_3m:+.1f}%, 6m: {roc_6m:+.1f}%)")
        return -3, "; ".join(reasons)
    elif roc_3m < -8:
        reasons.append(f"Moderate downward momentum (3m: {roc_3m:+.1f}%)")
        return -2, "; ".join(reasons)
    elif roc_3m < -3:
        reasons.append(f"Mild downward momentum (3m: {roc_3m:+.1f}%)")
        return -1, "; ".join(reasons)

    return 0, f"Momentum flat (3m: {roc_3m:+.1f}%)"


# ── Smart Money & Fundamental Scoring ────────────────────────────────────────

def _score_insider_activity(
    insider_txns: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[int, str]:
    """
    Score insider buying/selling clusters (±2).

    Only fires on clear patterns — absence of activity = 0 (no opinion).
    Buying is always conviction. Selling is ambiguous (taxes, diversification)
    so gets a smaller weight.

    Cluster = 3+ insiders transacting in same direction within 90 days.
    """
    if not insider_txns:
        return 0, "No insider transaction data"

    buys = 0
    sells = 0
    for txn in insider_txns[:20]:  # last 20 transactions
        acq_disp = str(txn.get("acquisition_or_disposal", txn.get("acquisitionOrDisposal", ""))).upper()
        shares = 0
        for key in ("shares", "securitiesTransacted"):
            try:
                val = txn.get(key)
                if val:
                    shares = abs(int(val))
                    break
            except (ValueError, TypeError):
                continue
        if shares == 0:
            continue
        if acq_disp == "A":
            buys += 1
        elif acq_disp == "D":
            sells += 1

    reasons = []
    score = 0

    if buys >= 3:
        score += 2
        reasons.append(f"Insider buying cluster ({buys} purchases) — strong conviction")
    elif buys >= 2:
        score += 1
        reasons.append(f"Multiple insider purchases ({buys}) — moderate conviction")

    if sells >= 5:
        score -= 1
        reasons.append(f"Heavy insider selling ({sells} disposals) — caution")

    if not reasons:
        return 0, f"Insider activity normal ({buys} buys, {sells} sells)"

    return max(-2, min(2, score)), "; ".join(reasons)


def _score_institutional_holdings(
    institutional: Optional[Dict[str, Any]] = None,
) -> Tuple[int, str]:
    """
    Score institutional accumulation/distribution (±1).

    Looks at whether institutional holders increased or decreased overall.
    Only fires on clear signals — no data or no change = 0.
    """
    if not institutional:
        return 0, "No institutional holdings data"

    # Alpha Vantage institutional holdings format
    holders = (institutional.get("holdings")
               or institutional.get("data")
               or institutional.get("institutionalHolders")
               or [])
    if not holders or not isinstance(holders, list):
        # Fallback: use aggregate counts if available
        inc = int(institutional.get("holders_with_increased_holdings", 0) or 0)
        dec = int(institutional.get("holders_with_decreased_holdings", 0) or 0)
        if inc > 0 or dec > 0:
            if inc >= dec * 2 and inc >= 100:
                return 1, f"Institutional accumulation ({inc} increased vs {dec} decreased)"
            elif dec >= inc * 2 and dec >= 100:
                return -1, f"Institutional distribution ({dec} decreased vs {inc} increased)"
            return 0, f"Institutional activity mixed ({inc} increased, {dec} decreased)"
        return 0, "No institutional holdings data"

    increased = 0
    decreased = 0
    for h in holders[:15]:
        change = 0
        for key in ("shares_changed", "change", "sharesChange", "shares_change"):
            try:
                change = float(h.get(key, 0))
                break
            except (ValueError, TypeError):
                continue
        if change > 0:
            increased += 1
        elif change < 0:
            decreased += 1

    if increased == 0 and decreased == 0:
        return 0, "No institutional holding changes detected"

    if increased >= decreased * 2 and increased >= 3:
        return 1, f"Institutional accumulation ({increased} increased vs {decreased} decreased)"
    elif decreased >= increased * 2 and decreased >= 3:
        return -1, f"Institutional distribution ({decreased} decreased vs {increased} increased)"

    return 0, f"Institutional activity mixed ({increased} increased, {decreased} decreased)"


def _score_earnings_momentum(
    earnings: Optional[Dict[str, Any]] = None,
) -> Tuple[int, str]:
    """
    Score earnings surprise momentum (±3).

    PEAD (Post-Earnings Announcement Drift) is one of the most documented
    anomalies in finance: ~6% abnormal 60-day returns (Dechow et al. 2013).
    Consecutive beats predict future beats at 65-70%.

    Weighted higher than candlestick patterns or volume per academic evidence.
    """
    if not earnings:
        return 0, "No earnings data"

    quarterly = earnings.get("quarterly", [])
    if len(quarterly) < 2:
        return 0, "Insufficient earnings history"

    beats = 0
    misses = 0
    streak = []

    for q in quarterly[:4]:
        surprise = 0
        for key in ("surprisePercentage", "surprise_percentage", "surprise"):
            try:
                surprise = float(q.get(key, 0))
                break
            except (ValueError, TypeError):
                continue

        if surprise > 0:
            streak.append("beat")
            beats += 1
        elif surprise < 0:
            streak.append("miss")
            misses += 1
        else:
            streak.append("met")

    reasons = []
    score = 0

    # Count consecutive beats from most recent
    consecutive_beats = 0
    for s in streak:
        if s == "beat":
            consecutive_beats += 1
        else:
            break

    consecutive_misses = 0
    for s in streak:
        if s == "miss":
            consecutive_misses += 1
        else:
            break

    if consecutive_beats >= 4:
        score = 3
        reasons.append(f"4+ consecutive earnings beats — strong PEAD momentum")
    elif consecutive_beats >= 3:
        score = 2
        reasons.append(f"{consecutive_beats} consecutive earnings beats — PEAD momentum")
    elif consecutive_beats >= 2:
        score = 1
        reasons.append(f"{consecutive_beats} consecutive earnings beats")
    elif consecutive_misses >= 4:
        score = -3
        reasons.append(f"{consecutive_misses} consecutive earnings misses — strong negative momentum")
    elif consecutive_misses >= 3:
        score = -2
        reasons.append(f"{consecutive_misses} consecutive earnings misses — negative momentum")
    elif consecutive_misses >= 2:
        score = -1
        reasons.append(f"{consecutive_misses} consecutive earnings misses")

    if not reasons:
        return 0, f"Earnings history mixed ({beats} beats, {misses} misses in last 4Q)"

    return score, "; ".join(reasons)


def _score_revenue_acceleration(
    income: Optional[Dict[str, Any]] = None,
) -> Tuple[int, str]:
    """
    Score revenue growth acceleration/deceleration (±1).

    Revenue growth rate speeding up = positive (the strongest fundamental
    predictor of stock appreciation). Slowing = cautionary.
    """
    if not income:
        return 0, "No income statement data"

    quarterly = income.get("quarterly", [])
    if len(quarterly) < 3:
        return 0, "Insufficient quarterly data"

    # Extract revenue values for 3 most recent quarters
    revenues = []
    for q in quarterly[:3]:
        rev = 0
        for key in ("totalRevenue", "total_revenue", "revenue"):
            try:
                rev = float(q.get(key, 0))
                if rev > 0:
                    break
            except (ValueError, TypeError):
                continue
        revenues.append(rev)

    if not all(r > 0 for r in revenues):
        return 0, "Revenue data incomplete"

    # Growth rates: most recent vs previous
    # revenues[0] = most recent, revenues[1] = prior, revenues[2] = two quarters ago
    growth_recent = (revenues[0] - revenues[1]) / revenues[1] * 100
    growth_prior = (revenues[1] - revenues[2]) / revenues[2] * 100

    acceleration = growth_recent - growth_prior

    if acceleration > 5:
        return 1, f"Revenue growth accelerating ({growth_prior:.1f}% → {growth_recent:.1f}%)"
    elif acceleration < -5:
        return -1, f"Revenue growth decelerating ({growth_prior:.1f}% → {growth_recent:.1f}%)"

    return 0, f"Revenue growth stable ({growth_prior:.1f}% → {growth_recent:.1f}%)"


def _score_relative_strength(
    daily_prices: Optional[List[Dict[str, Any]]] = None,
    sector_change_pct: Optional[float] = None,
) -> Tuple[int, str]:
    """
    Score stock's relative strength vs its sector (±2).

    Momentum is the strongest anomaly in finance (Jegadeesh & Titman 1993).
    Relative strength vs sector captures institutional accumulation/distribution.

    Uses multi-timeframe check: 5-day and 20-day returns vs sector.
    Consistent outperformance across both timeframes = stronger signal.
    """
    if not daily_prices or len(daily_prices) < 6 or sector_change_pct is None:
        return 0, "Insufficient data for relative strength"

    price_now = daily_prices[-1]["close"]

    # 5-day relative strength
    price_5d = daily_prices[-6]["close"]
    stock_5d = (price_now - price_5d) / price_5d * 100
    rel_5d = stock_5d - sector_change_pct

    # 20-day relative strength (if enough data)
    rel_20d = None
    if len(daily_prices) >= 21:
        price_20d = daily_prices[-21]["close"]
        stock_20d = (price_now - price_20d) / price_20d * 100
        # Scale sector change proportionally (we only get daily sector change)
        rel_20d = stock_20d - (sector_change_pct * 4)

    # Both timeframes agree = stronger signal
    if rel_20d is not None and rel_5d > 3.0 and rel_20d > 5.0:
        return 2, f"Consistent outperformance (5d: {rel_5d:+.1f}pp, 20d: {rel_20d:+.1f}pp vs sector)"
    elif rel_5d > 3.0:
        return 1, f"Outperforming sector by {rel_5d:.1f}pp (stock {stock_5d:+.1f}% vs sector {sector_change_pct:+.1f}%)"
    elif rel_20d is not None and rel_5d < -3.0 and rel_20d < -5.0:
        return -2, f"Consistent underperformance (5d: {rel_5d:+.1f}pp, 20d: {rel_20d:+.1f}pp vs sector)"
    elif rel_5d < -3.0:
        return -1, f"Underperforming sector by {abs(rel_5d):.1f}pp (stock {stock_5d:+.1f}% vs sector {sector_change_pct:+.1f}%)"

    return 0, f"In line with sector (stock {stock_5d:+.1f}% vs sector {sector_change_pct:+.1f}%)"


# ── Market Regime Classification ─────────────────────────────────────────────

def classify_market_regime(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """
    Classify the current market regime from a market snapshot.

    Regime determines the overall risk environment:
      - risk_on: growth sectors leading, volatility low/falling, broad strength
      - risk_off: defensive sectors leading, volatility rising, safe havens up
      - neutral: mixed signals, no clear regime
      - transitional: regime is changing (e.g., risk_on → risk_off)

    This is programmatic — no LLM needed. Returns a score (-10 to +10)
    where positive = risk-on and negative = risk-off, plus the classification.
    """
    score = 0
    signals = []

    # ── 1. Volatility (VIX proxy direction) ──
    vix = snapshot.get("vix", {})
    if vix:
        try:
            vix_change = float(str(vix.get("change_percent", "0")).replace("%", ""))
            if vix_change < -2:
                score += 2
                signals.append(f"Volatility falling ({vix_change:+.1f}%) — fear receding")
            elif vix_change > 2:
                score -= 2
                signals.append(f"Volatility rising ({vix_change:+.1f}%) — fear increasing")
            elif vix_change < 0:
                score += 1
                signals.append("Volatility slightly lower — calm")
            elif vix_change > 0:
                score -= 1
                signals.append("Volatility slightly higher — caution")
        except (ValueError, TypeError):
            pass

    # ── 2. Sector rotation pattern ──
    sectors = snapshot.get("sectors", {}).get("realtime", {})
    if sectors:
        growth_sectors = ["Technology", "Consumer Discretionary", "Communication Services"]
        defensive_sectors = ["Utilities", "Consumer Staples", "Healthcare", "Real Estate"]

        growth_avg = 0.0
        defensive_avg = 0.0
        g_count = d_count = 0

        for name, change_str in sectors.items():
            try:
                change = float(str(change_str).replace("%", ""))
            except (ValueError, TypeError):
                continue
            if name in growth_sectors:
                growth_avg += change
                g_count += 1
            elif name in defensive_sectors:
                defensive_avg += change
                d_count += 1

        if g_count > 0:
            growth_avg /= g_count
        if d_count > 0:
            defensive_avg /= d_count

        rotation = growth_avg - defensive_avg
        if rotation > 0.5:
            score += 2
            signals.append(f"Growth sectors leading ({growth_avg:+.2f}% vs defensive {defensive_avg:+.2f}%) — risk-on rotation")
        elif rotation < -0.5:
            score -= 2
            signals.append(f"Defensive sectors leading ({defensive_avg:+.2f}% vs growth {growth_avg:+.2f}%) — risk-off rotation")
        else:
            signals.append("Sector rotation neutral")

    # ── 3. Index breadth ──
    indices = snapshot.get("indices", {})
    if indices:
        up_count = 0
        down_count = 0
        for name, q in indices.items():
            try:
                change = float(str(q.get("change_percent", "0")).replace("%", ""))
                if change > 0:
                    up_count += 1
                else:
                    down_count += 1
            except (ValueError, TypeError):
                continue

        total_idx = up_count + down_count
        if total_idx > 0:
            if up_count == total_idx:
                score += 2
                signals.append("All major indices positive — broad strength")
            elif down_count == total_idx:
                score -= 2
                signals.append("All major indices negative — broad weakness")
            elif up_count > down_count:
                score += 1
                signals.append(f"Most indices positive ({up_count}/{total_idx})")
            else:
                score -= 1
                signals.append(f"Most indices negative ({down_count}/{total_idx})")

    # ── 4. Yield curve ──
    yields = snapshot.get("treasury_yields", {})
    if "2year" in yields and "10year" in yields:
        try:
            spread = float(yields["10year"]["value"]) - float(yields["2year"]["value"])
            if spread < -0.5:
                score -= 2
                signals.append(f"Yield curve deeply inverted ({spread:+.2f}%) — recession risk")
            elif spread < 0:
                score -= 1
                signals.append(f"Yield curve inverted ({spread:+.2f}%) — caution")
            elif spread > 0.5:
                score += 1
                signals.append(f"Yield curve normal ({spread:+.2f}%) — healthy")
        except (ValueError, TypeError):
            pass

    # ── 5. Safe haven flows ──
    commodities = snapshot.get("commodities", {})
    gold = commodities.get("GOLD", {})
    if gold:
        try:
            gold_change = float(str(gold.get("change_pct", "0")).replace("%", ""))
            if gold_change > 1:
                score -= 1
                signals.append(f"Gold rising ({gold_change:+.1f}%) — flight to safety")
            elif gold_change < -1:
                score += 1
                signals.append(f"Gold falling ({gold_change:+.1f}%) — risk appetite")
        except (ValueError, TypeError):
            pass

    # Classify
    if score >= 4:
        regime = "risk_on"
        label = "Risk-On"
        summary = "Investors are confident — money is flowing into growth stocks and away from safe havens. Good environment for buying stocks."
    elif score >= 2:
        regime = "risk_on"
        label = "Mildly Risk-On"
        summary = "Conditions lean positive but signals aren't strong. Okay to buy quality stocks, but be selective."
    elif score <= -4:
        regime = "risk_off"
        label = "Risk-Off"
        summary = "Investors are fearful — money is moving to safe assets (bonds, gold, defensive sectors). Be cautious about new stock purchases."
    elif score <= -2:
        regime = "risk_off"
        label = "Mildly Risk-Off"
        summary = "Conditions lean cautious. The market is nervous but not panicking. Set higher standards for any buy signals."
    else:
        regime = "neutral"
        label = "Neutral"
        # Explain WHY it's neutral (conflicting signals vs. just quiet)
        bullish_count = sum(1 for s in signals if any(w in s for w in ["positive", "strength", "falling", "receding", "risk appetite", "normal", "healthy"]))
        bearish_count = sum(1 for s in signals if any(w in s for w in ["negative", "weakness", "rising", "increasing", "safety", "inverted", "caution"]))
        if bullish_count > 0 and bearish_count > 0:
            summary = "Signals are conflicting — some point to optimism, others to caution. The market doesn't have a clear direction right now. Wait for a clearer picture before acting."
        else:
            summary = "The market is quiet with no strong signals in either direction. No urgency to buy or sell — a wait-and-see environment."

    return {
        "regime": regime,
        "label": label,
        "score": score,
        "max_score": 10,
        "signals": signals,
        "summary": summary,
    }


# ── Utility: Compute Moving Averages from Price Data ─────────────────────────

def compute_sma(prices: List[Dict[str, Any]], period: int) -> List[Dict[str, Any]]:
    """Compute SMA from OHLCV data (prices sorted ascending)."""
    result = []
    for i in range(period - 1, len(prices)):
        window = prices[i - period + 1: i + 1]
        avg = sum(p["close"] for p in window) / period
        result.append({"date": prices[i]["date"], "value": round(avg, 2)})
    return result


def compute_ma_signals(
    ma_50_series: List[Dict[str, Any]],
    ma_200_series: List[Dict[str, Any]],
    current_price: float,
) -> Dict[str, Any]:
    """
    Derive MA-based trading signals from SMA series.

    Returns:
        price_vs_50: "above" | "below" | None
        price_vs_200: "above" | "below" | None
        ma_alignment: "bullish" | "bearish" | "neutral"  (50MA vs 200MA)
        golden_cross: bool  — 50MA crossed above 200MA in last 20 bars
        death_cross: bool   — 50MA crossed below 200MA in last 20 bars
        ma_50_value: float | None
        ma_200_value: float | None
    """
    result: Dict[str, Any] = {
        "price_vs_50": None,
        "price_vs_200": None,
        "ma_alignment": "neutral",
        "golden_cross": False,
        "death_cross": False,
        "ma_50_value": None,
        "ma_200_value": None,
    }

    if ma_50_series:
        val = ma_50_series[-1]["value"]
        result["ma_50_value"] = val
        result["price_vs_50"] = "above" if current_price > val else "below"

    if ma_200_series:
        val = ma_200_series[-1]["value"]
        result["ma_200_value"] = val
        result["price_vs_200"] = "above" if current_price > val else "below"

    if ma_50_series and ma_200_series:
        ma50_val = ma_50_series[-1]["value"]
        ma200_val = ma_200_series[-1]["value"]

        result["ma_alignment"] = "bullish" if ma50_val > ma200_val else "bearish" if ma50_val < ma200_val else "neutral"

        # Detect golden/death cross in last 20 common dates
        ma50_dict = {m["date"]: m["value"] for m in ma_50_series[-30:]}
        ma200_dict = {m["date"]: m["value"] for m in ma_200_series[-30:]}
        common = sorted(set(ma50_dict) & set(ma200_dict))[-20:]

        for i in range(1, len(common)):
            d0, d1 = common[i - 1], common[i]
            prev50, prev200 = ma50_dict[d0], ma200_dict[d0]
            curr50, curr200 = ma50_dict[d1], ma200_dict[d1]
            if prev50 <= prev200 and curr50 > curr200:
                result["golden_cross"] = True
            elif prev50 >= prev200 and curr50 < curr200:
                result["death_cross"] = True

    return result
