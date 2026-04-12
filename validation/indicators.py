"""
Local indicator computation for backtesting.

Computes RSI, MACD, and ATR from OHLCV data without API calls.
Output formats match what price_action.py's scoring functions expect.
"""

from __future__ import annotations

from typing import List, Dict, Any


def compute_rsi(
    prices: List[Dict[str, Any]],
    period: int = 14,
) -> List[Dict[str, Any]]:
    """
    Compute RSI from OHLCV list (sorted ascending).

    Uses Wilder's smoothing method (exponential moving average).

    Returns list sorted DESCENDING (most recent first) with:
        [{date, value}, ...] — matches Alpha Vantage RSI format.
    """
    if len(prices) < period + 1:
        return []

    closes = [p["close"] for p in prices]
    dates = [p["date"] for p in prices]

    # Price changes
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]

    # Separate gains and losses
    gains = [max(d, 0) for d in deltas]
    losses = [abs(min(d, 0)) for d in deltas]

    # First average: simple mean of first `period` values
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    rsi_values = []

    # RSI for the first complete period
    if avg_loss == 0:
        rsi_values.append(100.0)
    else:
        rs = avg_gain / avg_loss
        rsi_values.append(100 - (100 / (1 + rs)))

    # Subsequent values using Wilder's smoothing
    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0:
            rsi_values.append(100.0)
        else:
            rs = avg_gain / avg_loss
            rsi_values.append(100 - (100 / (1 + rs)))

    # Build result — dates offset by 1 because deltas start at index 1
    result = []
    for i, rsi in enumerate(rsi_values):
        date_idx = period + i  # index into original prices list
        result.append({
            "date": dates[date_idx],
            "value": round(rsi, 2),
        })

    # Return descending (most recent first)
    result.reverse()
    return result


def compute_macd(
    prices: List[Dict[str, Any]],
    fast: int = 12,
    slow: int = 26,
    signal_period: int = 9,
) -> List[Dict[str, Any]]:
    """
    Compute MACD from OHLCV list (sorted ascending).

    Returns list sorted DESCENDING (most recent first) with:
        [{date, macd, signal, histogram}, ...] — matches Alpha Vantage MACD format.
    """
    if len(prices) < slow + signal_period:
        return []

    closes = [p["close"] for p in prices]
    dates = [p["date"] for p in prices]

    # Compute EMAs
    ema_fast = _ema(closes, fast)
    ema_slow = _ema(closes, slow)

    # MACD line: align to slow EMA start
    # ema_fast has (len - fast + 1) values, ema_slow has (len - slow + 1) values
    # We need them aligned at the end
    offset = slow - fast
    macd_line = [
        ema_fast[offset + i] - ema_slow[i]
        for i in range(len(ema_slow))
    ]

    # Signal line: EMA of MACD line
    signal_line = _ema(macd_line, signal_period)

    # Histogram
    signal_offset = len(macd_line) - len(signal_line)
    histogram = [
        macd_line[signal_offset + i] - signal_line[i]
        for i in range(len(signal_line))
    ]

    # Build result — dates align to the end of the original series
    date_start = len(dates) - len(signal_line)
    result = []
    for i in range(len(signal_line)):
        result.append({
            "date": dates[date_start + i],
            "macd": round(macd_line[signal_offset + i], 4),
            "signal": round(signal_line[i], 4),
            "histogram": round(histogram[i], 4),
        })

    # Return descending (most recent first)
    result.reverse()
    return result


def compute_atr(
    prices: List[Dict[str, Any]],
    period: int = 14,
) -> float:
    """
    Compute the current ATR (Average True Range) value.

    Uses Wilder's smoothing. Returns a single float (the most recent ATR value).
    """
    if len(prices) < period + 1:
        return 0.0

    # True Range for each bar (starting from index 1)
    tr_values = []
    for i in range(1, len(prices)):
        high = prices[i]["high"]
        low = prices[i]["low"]
        prev_close = prices[i - 1]["close"]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        tr_values.append(tr)

    if len(tr_values) < period:
        return sum(tr_values) / len(tr_values) if tr_values else 0.0

    # First ATR: simple average
    atr = sum(tr_values[:period]) / period

    # Subsequent: Wilder's smoothing
    for i in range(period, len(tr_values)):
        atr = (atr * (period - 1) + tr_values[i]) / period

    return round(atr, 4)


def _ema(values: list, period: int) -> list:
    """Compute EMA of a value series. Returns list of length (len - period + 1)."""
    if len(values) < period:
        return []

    multiplier = 2 / (period + 1)

    # Seed with SMA
    sma = sum(values[:period]) / period
    result = [sma]

    for i in range(period, len(values)):
        ema_val = (values[i] - result[-1]) * multiplier + result[-1]
        result.append(ema_val)

    return result
