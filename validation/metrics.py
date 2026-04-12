"""
Metrics for evaluating price action signal quality.

Measures forward returns, hit rates, monotonicity, and statistical significance.
All metrics use volatility-relative (ATR-normalized) and raw returns.
"""

from __future__ import annotations

import math
from typing import List, Dict, Any, Optional, Tuple

from scipy import stats


SIGNAL_ORDER = ["strong_sell", "sell", "neutral", "buy", "strong_buy"]


def attach_forward_returns(
    signals: List[Dict[str, Any]],
    daily_prices_map: Dict[str, List[Dict[str, Any]]],
    horizons: List[int],
    benchmark_prices: Optional[List[Dict[str, Any]]] = None,
) -> None:
    """
    Attach forward returns to each signal in-place.

    For each signal at date T, computes:
      - fwd_{h}d: raw return at T+N
      - fwd_{h}d_atr: ATR-normalized return
      - fwd_{h}d_excess: return minus benchmark (SPY) return over same period

    benchmark_prices: SPY (or other benchmark) OHLCV list for excess return calc.
    """
    # Build date→index lookup per ticker
    index_map = {}
    for ticker, prices in daily_prices_map.items():
        index_map[ticker] = {p["date"]: i for i, p in enumerate(prices)}

    # Benchmark lookup
    bench_idx = {}
    if benchmark_prices:
        bench_idx = {p["date"]: i for i, p in enumerate(benchmark_prices)}

    for sig in signals:
        ticker = sig["ticker"]
        prices = daily_prices_map[ticker]
        date_idx = index_map[ticker].get(sig["date"])

        if date_idx is None:
            for h in horizons:
                sig[f"fwd_{h}d"] = None
                sig[f"fwd_{h}d_atr"] = None
                sig[f"fwd_{h}d_excess"] = None
            continue

        atr = sig.get("atr", 0) or 1e-9  # avoid division by zero
        price = sig["price"]

        for h in horizons:
            future_idx = date_idx + h
            if future_idx < len(prices):
                future_price = prices[future_idx]["close"]
                raw_return = (future_price - price) / price
                sig[f"fwd_{h}d"] = round(raw_return, 6)
                sig[f"fwd_{h}d_atr"] = round((future_price - price) / atr, 4)

                # Excess return over benchmark
                bench_date_idx = bench_idx.get(sig["date"])
                if bench_date_idx is not None and bench_date_idx + h < len(benchmark_prices):
                    bench_price = benchmark_prices[bench_date_idx]["close"]
                    bench_future = benchmark_prices[bench_date_idx + h]["close"]
                    bench_return = (bench_future - bench_price) / bench_price
                    sig[f"fwd_{h}d_excess"] = round(raw_return - bench_return, 6)
                else:
                    sig[f"fwd_{h}d_excess"] = None
            else:
                sig[f"fwd_{h}d"] = None
                sig[f"fwd_{h}d_atr"] = None
                sig[f"fwd_{h}d_excess"] = None


def filter_signal_transitions(
    signals: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Filter to only signal transitions — when the signal changes for a ticker.

    E.g., neutral→buy, buy→sell, etc. Removes consecutive identical signals
    to eliminate autocorrelation and test whether the transition itself
    has predictive power.
    """
    # Group by ticker, preserving order
    by_ticker: Dict[str, List[Dict[str, Any]]] = {}
    for sig in signals:
        by_ticker.setdefault(sig["ticker"], []).append(sig)

    transitions = []
    for ticker, ticker_signals in by_ticker.items():
        prev_signal = None
        for sig in ticker_signals:
            if sig["signal"] != prev_signal:
                sig_copy = dict(sig)
                sig_copy["prev_signal"] = prev_signal
                transitions.append(sig_copy)
                prev_signal = sig["signal"]

    # Sort by date for consistent output
    transitions.sort(key=lambda s: (s["date"], s["ticker"]))
    return transitions


def signal_distribution(signals: List[Dict[str, Any]]) -> Dict[str, int]:
    """Count signals per bucket."""
    dist = {s: 0 for s in SIGNAL_ORDER}
    for sig in signals:
        bucket = sig["signal"]
        if bucket in dist:
            dist[bucket] += 1
    return dist


def returns_by_bucket(
    signals: List[Dict[str, Any]],
    horizon: int,
) -> Dict[str, Dict[str, Any]]:
    """
    Compute return statistics per signal bucket.

    Returns dict of {bucket: {count, mean, median, std, hit_rate, t_stat, p_value}}.
    Hit rate = directional accuracy:
      - buy/strong_buy: % with positive return
      - sell/strong_sell: % with negative return
      - neutral: % with positive return (just for reference)
    """
    buckets = {s: [] for s in SIGNAL_ORDER}

    for sig in signals:
        ret = sig.get(f"fwd_{horizon}d")
        if ret is not None:
            buckets[sig["signal"]].append(ret)

    result = {}
    for bucket in SIGNAL_ORDER:
        returns = buckets[bucket]
        if not returns:
            result[bucket] = {
                "count": 0, "mean": 0, "median": 0, "std": 0,
                "hit_rate": 0, "t_stat": 0, "p_value": 1.0,
            }
            continue

        mean_ret = sum(returns) / len(returns)
        sorted_ret = sorted(returns)
        median_ret = sorted_ret[len(sorted_ret) // 2]
        std_ret = _std(returns) if len(returns) > 1 else 0

        # Hit rate: directional accuracy
        if bucket in ("buy", "strong_buy"):
            hits = sum(1 for r in returns if r > 0)
        elif bucket in ("sell", "strong_sell"):
            hits = sum(1 for r in returns if r < 0)
        else:
            hits = sum(1 for r in returns if r > 0)
        hit_rate = hits / len(returns) if returns else 0

        # One-sample t-test: is mean return different from zero?
        if len(returns) >= 2 and std_ret > 0:
            t_stat, p_value = stats.ttest_1samp(returns, 0)
        else:
            t_stat, p_value = 0, 1.0

        result[bucket] = {
            "count": len(returns),
            "mean": round(mean_ret * 100, 3),       # as percentage
            "median": round(median_ret * 100, 3),
            "std": round(std_ret * 100, 3),
            "hit_rate": round(hit_rate * 100, 1),
            "t_stat": round(t_stat, 2),
            "p_value": round(p_value, 4),
        }

    return result


def atr_returns_by_bucket(
    signals: List[Dict[str, Any]],
    horizon: int,
) -> Dict[str, Dict[str, float]]:
    """Compute ATR-normalized return stats per signal bucket."""
    buckets = {s: [] for s in SIGNAL_ORDER}

    for sig in signals:
        ret = sig.get(f"fwd_{horizon}d_atr")
        if ret is not None:
            buckets[sig["signal"]].append(ret)

    result = {}
    for bucket in SIGNAL_ORDER:
        returns = buckets[bucket]
        if not returns:
            result[bucket] = {"count": 0, "mean_atr": 0, "median_atr": 0}
            continue

        result[bucket] = {
            "count": len(returns),
            "mean_atr": round(sum(returns) / len(returns), 3),
            "median_atr": round(sorted(returns)[len(returns) // 2], 3),
        }

    return result


def score_monotonicity(
    signals: List[Dict[str, Any]],
    horizon: int,
) -> Dict[str, Any]:
    """
    Test score monotonicity: does higher score predict higher return?

    Uses Spearman rank correlation between score and forward return.
    """
    scores = []
    returns = []

    for sig in signals:
        ret = sig.get(f"fwd_{horizon}d")
        if ret is not None:
            scores.append(sig["score"])
            returns.append(ret)

    if len(scores) < 10:
        return {"correlation": 0, "p_value": 1.0, "n": len(scores), "pass": False}

    corr, p_value = stats.spearmanr(scores, returns)

    return {
        "correlation": round(corr, 4),
        "p_value": round(p_value, 6),
        "n": len(scores),
        "pass": p_value < 0.05 and corr > 0,
    }


def layer_ablation(
    signals: List[Dict[str, Any]],
    horizon: int,
) -> List[Dict[str, Any]]:
    """
    Measure each layer's contribution by computing monotonicity without it.

    For each layer, recomputes the score excluding that layer and measures
    how much the score-vs-return correlation drops.
    """
    # Baseline: full score correlation
    baseline = score_monotonicity(signals, horizon)
    baseline_corr = baseline["correlation"]

    layer_names = set()
    for sig in signals:
        for layer in sig.get("layers", []):
            layer_names.add(layer["name"])

    results = []
    for layer_name in sorted(layer_names):
        # Recompute scores without this layer
        ablated_scores = []
        returns = []

        for sig in signals:
            ret = sig.get(f"fwd_{horizon}d")
            if ret is None:
                continue

            layer_score = 0
            for layer in sig.get("layers", []):
                if layer["name"] == layer_name:
                    layer_score = layer["score"]
                    break

            ablated = sig["score"] - layer_score
            ablated_scores.append(ablated)
            returns.append(ret)

        if len(ablated_scores) < 10:
            results.append({"layer": layer_name, "corr_drop": 0, "importance": "N/A"})
            continue

        corr, _ = stats.spearmanr(ablated_scores, returns)
        drop = baseline_corr - corr

        results.append({
            "layer": layer_name,
            "baseline_corr": round(baseline_corr, 4),
            "ablated_corr": round(corr, 4),
            "corr_drop": round(drop, 4),
        })

    # Sort by importance (biggest drop = most important)
    results.sort(key=lambda x: x.get("corr_drop", 0), reverse=True)
    return results


def buy_vs_sell_test(
    signals: List[Dict[str, Any]],
    horizon: int,
) -> Dict[str, Any]:
    """
    Two-sample t-test: are buy signal returns significantly higher than sell signal returns?
    """
    buy_returns = []
    sell_returns = []

    for sig in signals:
        ret = sig.get(f"fwd_{horizon}d")
        if ret is None:
            continue
        if sig["signal"] in ("buy", "strong_buy"):
            buy_returns.append(ret)
        elif sig["signal"] in ("sell", "strong_sell"):
            sell_returns.append(ret)

    if len(buy_returns) < 5 or len(sell_returns) < 5:
        return {
            "buy_mean": 0, "sell_mean": 0,
            "t_stat": 0, "p_value": 1.0,
            "significant": False,
        }

    t_stat, p_value = stats.ttest_ind(buy_returns, sell_returns, alternative="greater")

    return {
        "buy_count": len(buy_returns),
        "sell_count": len(sell_returns),
        "buy_mean": round(sum(buy_returns) / len(buy_returns) * 100, 3),
        "sell_mean": round(sum(sell_returns) / len(sell_returns) * 100, 3),
        "t_stat": round(t_stat, 2),
        "p_value": round(p_value, 4),
        "significant": p_value < 0.05,
    }


def excess_returns_by_bucket(
    signals: List[Dict[str, Any]],
    horizon: int,
) -> Dict[str, Dict[str, Any]]:
    """
    Same as returns_by_bucket but using excess returns (over SPY benchmark).

    This removes the bull/bear market bias — a buy signal should outperform
    the market, not just go up.
    """
    buckets = {s: [] for s in SIGNAL_ORDER}

    for sig in signals:
        ret = sig.get(f"fwd_{horizon}d_excess")
        if ret is not None:
            buckets[sig["signal"]].append(ret)

    result = {}
    for bucket in SIGNAL_ORDER:
        returns = buckets[bucket]
        if not returns:
            result[bucket] = {
                "count": 0, "mean": 0, "median": 0, "std": 0,
                "hit_rate": 0, "t_stat": 0, "p_value": 1.0,
            }
            continue

        mean_ret = sum(returns) / len(returns)
        sorted_ret = sorted(returns)
        median_ret = sorted_ret[len(sorted_ret) // 2]
        std_ret = _std(returns) if len(returns) > 1 else 0

        # Hit rate for excess: buy should outperform market (excess > 0)
        # sell should underperform market (excess < 0)
        if bucket in ("buy", "strong_buy"):
            hits = sum(1 for r in returns if r > 0)
        elif bucket in ("sell", "strong_sell"):
            hits = sum(1 for r in returns if r < 0)
        else:
            hits = sum(1 for r in returns if r > 0)
        hit_rate = hits / len(returns) if returns else 0

        if len(returns) >= 2 and std_ret > 0:
            t_stat, p_value = stats.ttest_1samp(returns, 0)
        else:
            t_stat, p_value = 0, 1.0

        result[bucket] = {
            "count": len(returns),
            "mean": round(mean_ret * 100, 3),
            "median": round(median_ret * 100, 3),
            "std": round(std_ret * 100, 3),
            "hit_rate": round(hit_rate * 100, 1),
            "t_stat": round(t_stat, 2),
            "p_value": round(p_value, 4),
        }

    return result


def excess_score_monotonicity(
    signals: List[Dict[str, Any]],
    horizon: int,
) -> Dict[str, Any]:
    """Score monotonicity using excess returns instead of raw returns."""
    scores = []
    returns = []

    for sig in signals:
        ret = sig.get(f"fwd_{horizon}d_excess")
        if ret is not None:
            scores.append(sig["score"])
            returns.append(ret)

    if len(scores) < 10:
        return {"correlation": 0, "p_value": 1.0, "n": len(scores), "pass": False}

    corr, p_value = stats.spearmanr(scores, returns)

    return {
        "correlation": round(corr, 4),
        "p_value": round(p_value, 6),
        "n": len(scores),
        "pass": p_value < 0.05 and corr > 0,
    }


def excess_buy_vs_sell_test(
    signals: List[Dict[str, Any]],
    horizon: int,
) -> Dict[str, Any]:
    """Buy vs sell test using excess returns."""
    buy_returns = []
    sell_returns = []

    for sig in signals:
        ret = sig.get(f"fwd_{horizon}d_excess")
        if ret is None:
            continue
        if sig["signal"] in ("buy", "strong_buy"):
            buy_returns.append(ret)
        elif sig["signal"] in ("sell", "strong_sell"):
            sell_returns.append(ret)

    if len(buy_returns) < 5 or len(sell_returns) < 5:
        return {
            "buy_mean": 0, "sell_mean": 0,
            "t_stat": 0, "p_value": 1.0,
            "significant": False,
        }

    t_stat, p_value = stats.ttest_ind(buy_returns, sell_returns, alternative="greater")

    return {
        "buy_count": len(buy_returns),
        "sell_count": len(sell_returns),
        "buy_mean": round(sum(buy_returns) / len(buy_returns) * 100, 3),
        "sell_mean": round(sum(sell_returns) / len(sell_returns) * 100, 3),
        "t_stat": round(t_stat, 2),
        "p_value": round(p_value, 4),
        "significant": p_value < 0.05,
    }


def attach_transaction_costs(
    signals: List[Dict[str, Any]],
    horizons: List[int],
    cost_bps: float = 15.0,  # 15 bps round-trip default
) -> None:
    """Subtract transaction costs from forward returns. Modifies in-place.

    Adds net_fwd_{h}d fields = fwd_{h}d - cost.
    Also adds net_fwd_{h}d_excess = fwd_{h}d_excess - cost.
    cost_bps: round-trip cost in basis points (1 bp = 0.01%).
    """
    cost = cost_bps / 10000  # convert bps to decimal
    for sig in signals:
        for h in horizons:
            raw = sig.get(f"fwd_{h}d")
            if raw is not None:
                sig[f"net_fwd_{h}d"] = round(raw - cost, 6)
            else:
                sig[f"net_fwd_{h}d"] = None

            excess = sig.get(f"fwd_{h}d_excess")
            if excess is not None:
                sig[f"net_fwd_{h}d_excess"] = round(excess - cost, 6)
            else:
                sig[f"net_fwd_{h}d_excess"] = None


def tag_signal_regimes(
    signals: List[Dict[str, Any]],
    benchmark_prices: List[Dict[str, Any]],
) -> None:
    """Tag each signal with market regime based on benchmark (SPY) state.

    Regime is determined by:
    - Trend: price vs 200-day SMA (bull/bear)
    - Volatility: 20-day ATR/price ratio vs median (high/low vol)

    Adds 'regime' field: 'bull_low_vol', 'bull_high_vol', 'bear_low_vol', 'bear_high_vol'
    """
    if not benchmark_prices or len(benchmark_prices) < 200:
        for sig in signals:
            sig["regime"] = "unknown"
        return

    # Pre-compute 200 SMA and 20-day ATR ratio for each date
    bench_date_map = {}
    for i, bar in enumerate(benchmark_prices):
        if i < 200:
            continue
        sma_200 = sum(b["close"] for b in benchmark_prices[i-199:i+1]) / 200

        # 20-day ATR ratio (volatility proxy)
        if i >= 20:
            atr_sum = 0
            for j in range(i-19, i+1):
                tr = max(
                    benchmark_prices[j]["high"] - benchmark_prices[j]["low"],
                    abs(benchmark_prices[j]["high"] - benchmark_prices[j-1]["close"]),
                    abs(benchmark_prices[j]["low"] - benchmark_prices[j-1]["close"]),
                )
                atr_sum += tr
            atr_20 = atr_sum / 20
            atr_ratio = atr_20 / bar["close"]
        else:
            atr_ratio = 0

        bench_date_map[bar["date"]] = {
            "price": bar["close"],
            "sma_200": sma_200,
            "atr_ratio": atr_ratio,
        }

    # Compute median ATR ratio for threshold
    atr_ratios = [v["atr_ratio"] for v in bench_date_map.values() if v["atr_ratio"] > 0]
    median_atr = sorted(atr_ratios)[len(atr_ratios) // 2] if atr_ratios else 0.01

    for sig in signals:
        info = bench_date_map.get(sig["date"])
        if not info:
            sig["regime"] = "unknown"
            continue

        trend = "bull" if info["price"] > info["sma_200"] else "bear"
        vol = "high_vol" if info["atr_ratio"] > median_atr else "low_vol"
        sig["regime"] = f"{trend}_{vol}"


def returns_by_regime(
    signals: List[Dict[str, Any]],
    horizon: int,
    use_net: bool = False,
) -> Dict[str, Dict[str, Any]]:
    """Compute return stats stratified by market regime.

    Returns dict of {regime: {buy_count, buy_mean, buy_hit_rate, sell_count, sell_mean, sell_hit_rate, ...}}.
    """
    ret_key = f"net_fwd_{horizon}d" if use_net else f"fwd_{horizon}d"

    regimes: Dict[str, Dict[str, list]] = {}

    for sig in signals:
        regime = sig.get("regime", "unknown")
        if regime not in regimes:
            regimes[regime] = {"buy": [], "sell": []}

        ret = sig.get(ret_key)
        if ret is None:
            continue

        if sig["signal"] in ("buy", "strong_buy"):
            regimes[regime]["buy"].append(ret)
        elif sig["signal"] in ("sell", "strong_sell"):
            regimes[regime]["sell"].append(ret)

    result = {}
    for regime, data in sorted(regimes.items()):
        buy_rets = data["buy"]
        sell_rets = data["sell"]

        buy_mean = sum(buy_rets) / len(buy_rets) * 100 if buy_rets else 0
        sell_mean = sum(sell_rets) / len(sell_rets) * 100 if sell_rets else 0
        buy_hit = sum(1 for r in buy_rets if r > 0) / len(buy_rets) * 100 if buy_rets else 0
        sell_hit = sum(1 for r in sell_rets if r < 0) / len(sell_rets) * 100 if sell_rets else 0

        result[regime] = {
            "buy_count": len(buy_rets),
            "buy_mean": round(buy_mean, 3),
            "buy_hit_rate": round(buy_hit, 1),
            "sell_count": len(sell_rets),
            "sell_mean": round(sell_mean, 3),
            "sell_hit_rate": round(sell_hit, 1),
        }

    return result


def compute_equity_curve(
    signals: List[Dict[str, Any]],
    horizon: int,
    use_net: bool = False,
) -> Dict[str, Any]:
    """Compute equity curve metrics from sequential signals.

    Simulates equal-weight positions held for `horizon` days.
    Returns max_drawdown, sharpe, sortino, calmar, total_return.
    """
    ret_key = f"net_fwd_{horizon}d" if use_net else f"fwd_{horizon}d"

    # Get returns in chronological order, flipping sell returns
    returns = []
    for sig in sorted(signals, key=lambda s: s["date"]):
        ret = sig.get(ret_key)
        if ret is None:
            continue
        if sig["signal"] in ("sell", "strong_sell"):
            ret = -ret  # shorting: profit when price falls
        returns.append(ret)

    if len(returns) < 2:
        return {"total_return": 0, "max_drawdown": 0, "sharpe": 0, "sortino": 0, "calmar": 0, "n_trades": 0, "annual_return": 0}

    # Equity curve
    equity = [1.0]
    for r in returns:
        equity.append(equity[-1] * (1 + r))

    # Max drawdown
    peak = equity[0]
    max_dd = 0
    for e in equity:
        if e > peak:
            peak = e
        dd = (peak - e) / peak
        if dd > max_dd:
            max_dd = dd

    # Annualized metrics (assume horizon-day holding, ~252/horizon trades per year)
    trades_per_year = 252 / horizon
    mean_ret = sum(returns) / len(returns)
    std_ret = (sum((r - mean_ret) ** 2 for r in returns) / (len(returns) - 1)) ** 0.5 if len(returns) > 1 else 1e-9

    # Downside deviation (for Sortino)
    downside = [r for r in returns if r < 0]
    downside_std = (sum(r ** 2 for r in downside) / len(downside)) ** 0.5 if downside else 1e-9

    annual_return = mean_ret * trades_per_year
    annual_std = std_ret * math.sqrt(trades_per_year)
    annual_downside = downside_std * math.sqrt(trades_per_year)

    sharpe = annual_return / annual_std if annual_std > 0 else 0
    sortino = annual_return / annual_downside if annual_downside > 0 else 0
    calmar = annual_return / max_dd if max_dd > 0 else 0
    total_return = (equity[-1] / equity[0] - 1) * 100

    return {
        "n_trades": len(returns),
        "total_return": round(total_return, 2),
        "max_drawdown": round(max_dd * 100, 2),
        "sharpe": round(sharpe, 3),
        "sortino": round(sortino, 3),
        "calmar": round(calmar, 3),
        "annual_return": round(annual_return * 100, 2),
    }


def _std(values: list) -> float:
    """Compute sample standard deviation."""
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(variance)
