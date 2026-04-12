"""
Trade feedback loop — analyzes closed paper trades to evaluate which scoring
layers are predictive and which aren't.

For each closed trade with an analysis_snapshot, extracts the per-layer scores
recorded at entry time and correlates them with trade outcomes (win/loss, P&L).
Produces layer-by-layer statistics, entry/exit analysis, and plain-English
recommendations for refining the scoring system.
"""
from __future__ import annotations

import json
import logging
from typing import Dict, Any, List, Optional

from app.db import database as db

logger = logging.getLogger(__name__)

# Minimum number of trades in a bucket to consider the statistic meaningful.
MIN_SAMPLE_SIZE = 5


def _parse_snapshot(raw: Optional[str]) -> Optional[Dict[str, Any]]:
    """Safely parse the analysis_snapshot JSON string from a trade row."""
    if not raw:
        return None
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


def _classify_exit_reason(reason: Optional[str]) -> str:
    """Normalize the exit_reason string into a canonical bucket."""
    if not reason:
        return "unknown"
    reason_lower = reason.lower()
    if "news_guard" in reason_lower:
        return "news_guard"
    if "trailing_stop" in reason_lower:
        return "trailing_stop"
    if "stop_loss" in reason_lower:
        return "stop_loss"
    if "take_profit" in reason_lower:
        return "take_profit"
    if "manual" in reason_lower:
        return "manual"
    return "other"


def _safe_avg(values: List[float]) -> float:
    """Return the average of a list, or 0.0 if empty."""
    return round(sum(values) / len(values), 4) if values else 0.0


def _safe_pct(numerator: int, denominator: int) -> float:
    """Return percentage as a float (0-100), or 0.0 if denominator is zero."""
    return round(numerator / denominator * 100, 1) if denominator > 0 else 0.0


def analyze_trade_feedback() -> Dict[str, Any]:
    """
    Analyze all closed trades to evaluate layer-by-layer predictive accuracy.

    For each closed trade with an analysis_snapshot:
    1. Extract the layer scores at entry time
    2. Check if the trade was a win or loss
    3. Compute per-layer statistics:
       - How often does a positive layer score correspond to a winning trade?
       - How often does a negative layer score correspond to a losing trade?
       - What's the average P&L when each layer is positive vs negative vs zero?

    Returns a dict with total_trades_analyzed, win_rate, avg_pnl_pct,
    layer_analysis, entry_analysis, exit_analysis, and recommendations.
    """
    closed_trades = db.get_paper_trades(status="closed")

    if not closed_trades:
        return {
            "total_trades_analyzed": 0,
            "trades_with_snapshot": 0,
            "trades_without_snapshot": 0,
            "win_rate": 0.0,
            "avg_pnl_pct": 0.0,
            "layer_analysis": {},
            "entry_analysis": {},
            "exit_analysis": {},
            "recommendations": [
                "No closed trades yet. Run paper/scan and paper/update to generate trades, "
                "then re-run this analysis once trades have been closed."
            ],
        }

    # ── Parse trades and separate those with/without snapshots ──
    trades_with_snapshot: List[Dict[str, Any]] = []
    trades_without_snapshot = 0

    for trade in closed_trades:
        snapshot = _parse_snapshot(trade.get("analysis_snapshot"))
        if snapshot is None:
            trades_without_snapshot += 1
            continue

        pnl = trade.get("realized_pnl") or 0
        pnl_pct = trade.get("realized_pnl_pct") or 0
        is_win = pnl > 0

        # Extract layers from the snapshot's score object
        score_data = snapshot.get("score", {})
        layers = score_data.get("layers", [])
        total_score = score_data.get("total_score", 0)
        alignment = score_data.get("alignment", {})

        trades_with_snapshot.append({
            "trade": trade,
            "snapshot": snapshot,
            "layers": layers,
            "total_score": total_score,
            "alignment_score": alignment.get("score", 0) if isinstance(alignment, dict) else 0,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "is_win": is_win,
        })

    if not trades_with_snapshot:
        all_pnl = [(t.get("realized_pnl") or 0) for t in closed_trades]
        all_wins = sum(1 for p in all_pnl if p > 0)
        return {
            "total_trades_analyzed": len(closed_trades),
            "trades_with_snapshot": 0,
            "trades_without_snapshot": trades_without_snapshot,
            "win_rate": _safe_pct(all_wins, len(closed_trades)),
            "avg_pnl_pct": _safe_avg([(t.get("realized_pnl_pct") or 0) for t in closed_trades]),
            "layer_analysis": {},
            "entry_analysis": {},
            "exit_analysis": {},
            "recommendations": [
                f"All {trades_without_snapshot} closed trades lack analysis_snapshot data. "
                "Layer-level feedback requires trades opened with the current scanner "
                "(which records the snapshot at entry time)."
            ],
        }

    # ── Overall stats ──
    total_analyzed = len(trades_with_snapshot)
    wins = [t for t in trades_with_snapshot if t["is_win"]]
    losses = [t for t in trades_with_snapshot if not t["is_win"]]
    overall_win_rate = _safe_pct(len(wins), total_analyzed)
    overall_avg_pnl = _safe_avg([t["pnl_pct"] for t in trades_with_snapshot])

    # ── Layer-by-layer analysis ──
    # Collect all layer names across trades (handles slight naming variations)
    layer_names: Dict[str, Dict[str, Any]] = {}
    for tw in trades_with_snapshot:
        for layer in tw["layers"]:
            name = layer.get("name", "Unknown")
            if name not in layer_names:
                layer_names[name] = {
                    "max_weight": layer.get("max", 0),
                    "positive_wins": 0,
                    "positive_losses": 0,
                    "positive_pnl": [],
                    "negative_wins": 0,
                    "negative_losses": 0,
                    "negative_pnl": [],
                    "zero_wins": 0,
                    "zero_losses": 0,
                    "zero_pnl": [],
                }

            stats = layer_names[name]
            score_val = layer.get("score", 0)
            # Track the max weight seen (in case it varies across trades)
            stats["max_weight"] = max(stats["max_weight"], layer.get("max", 0))

            if score_val > 0:
                if tw["is_win"]:
                    stats["positive_wins"] += 1
                else:
                    stats["positive_losses"] += 1
                stats["positive_pnl"].append(tw["pnl_pct"])
            elif score_val < 0:
                if tw["is_win"]:
                    stats["negative_wins"] += 1
                else:
                    stats["negative_losses"] += 1
                stats["negative_pnl"].append(tw["pnl_pct"])
            else:
                if tw["is_win"]:
                    stats["zero_wins"] += 1
                else:
                    stats["zero_losses"] += 1
                stats["zero_pnl"].append(tw["pnl_pct"])

    layer_analysis = {}
    for name, stats in layer_names.items():
        times_positive = stats["positive_wins"] + stats["positive_losses"]
        times_negative = stats["negative_wins"] + stats["negative_losses"]
        times_zero = stats["zero_wins"] + stats["zero_losses"]

        win_rate_positive = _safe_pct(stats["positive_wins"], times_positive)
        win_rate_negative = _safe_pct(stats["negative_wins"], times_negative)
        avg_pnl_positive = _safe_avg(stats["positive_pnl"])
        avg_pnl_negative = _safe_avg(stats["negative_pnl"])

        # Determine if the layer is predictive:
        # A positive score should lead to a higher win rate than a negative score.
        # Only judge if we have enough samples in both buckets.
        has_enough_positive = times_positive >= MIN_SAMPLE_SIZE
        has_enough_negative = times_negative >= MIN_SAMPLE_SIZE

        if has_enough_positive and has_enough_negative:
            predictive = win_rate_positive > win_rate_negative
        elif has_enough_positive:
            # Only positive data available — is it better than overall?
            predictive = win_rate_positive > overall_win_rate
        else:
            predictive = None  # insufficient data to judge

        # Suggest weight adjustment
        if not has_enough_positive and not has_enough_negative:
            suggested = "insufficient_data"
        elif predictive is True:
            # Positive score predicts wins well
            win_rate_delta = win_rate_positive - (win_rate_negative if has_enough_negative else overall_win_rate)
            if win_rate_delta > 15:
                suggested = "increase"
            else:
                suggested = "keep"
        elif predictive is False:
            # Layer is not helping or is inverted
            if has_enough_positive and has_enough_negative:
                if win_rate_negative > win_rate_positive + 10:
                    suggested = "decrease"  # actively misleading
                else:
                    suggested = "decrease"
            else:
                suggested = "keep"
        else:
            suggested = "insufficient_data"

        layer_analysis[name] = {
            "times_positive": times_positive,
            "times_negative": times_negative,
            "times_zero": times_zero,
            "win_rate_when_positive": win_rate_positive,
            "win_rate_when_negative": win_rate_negative,
            "avg_pnl_when_positive": avg_pnl_positive,
            "avg_pnl_when_negative": avg_pnl_negative,
            "predictive": predictive,
            "current_weight": stats["max_weight"],
            "suggested_adjustment": suggested,
        }

    # ── Entry analysis: do higher scores produce better outcomes? ──
    winner_scores = [t["total_score"] for t in wins]
    loser_scores = [t["total_score"] for t in losses]
    avg_score_winners = _safe_avg(winner_scores)
    avg_score_losers = _safe_avg(loser_scores)

    # Consider score "separating" if winners average at least 1.5 points higher
    score_separates = (avg_score_winners - avg_score_losers) >= 1.5 if losses else False

    # Score-to-P&L correlation (simple: bucket by score quartiles)
    score_buckets: Dict[str, List[float]] = {"low": [], "medium": [], "high": []}
    all_scores = [t["total_score"] for t in trades_with_snapshot]
    if all_scores:
        score_range = max(all_scores) - min(all_scores)
        if score_range > 0:
            low_bound = min(all_scores) + score_range / 3
            high_bound = min(all_scores) + 2 * score_range / 3
            for t in trades_with_snapshot:
                if t["total_score"] <= low_bound:
                    score_buckets["low"].append(t["pnl_pct"])
                elif t["total_score"] >= high_bound:
                    score_buckets["high"].append(t["pnl_pct"])
                else:
                    score_buckets["medium"].append(t["pnl_pct"])

    entry_analysis = {
        "avg_score_winners": avg_score_winners,
        "avg_score_losers": avg_score_losers,
        "score_separates": score_separates,
        "score_pnl_buckets": {
            k: {"count": len(v), "avg_pnl_pct": _safe_avg(v)}
            for k, v in score_buckets.items()
        },
    }

    # ── Exit analysis: how are trades closing? ──
    exit_buckets: Dict[str, int] = {
        "stop_loss": 0, "trailing_stop": 0, "take_profit": 0,
        "news_guard": 0, "manual": 0, "other": 0, "unknown": 0,
    }
    days_winners: List[float] = []
    days_losers: List[float] = []

    for tw in trades_with_snapshot:
        trade = tw["trade"]
        reason = _classify_exit_reason(trade.get("exit_reason"))
        exit_buckets[reason] = exit_buckets.get(reason, 0) + 1

        days = trade.get("days_held") or 0
        if tw["is_win"]:
            days_winners.append(days)
        else:
            days_losers.append(days)

    exit_analysis = {
        "stop_loss_count": exit_buckets["stop_loss"],
        "trailing_stop_count": exit_buckets["trailing_stop"],
        "take_profit_count": exit_buckets["take_profit"],
        "news_guard_count": exit_buckets["news_guard"],
        "manual_count": exit_buckets["manual"],
        "other_count": exit_buckets.get("other", 0) + exit_buckets.get("unknown", 0),
        "avg_days_winners": _safe_avg(days_winners),
        "avg_days_losers": _safe_avg(days_losers),
    }

    # ── Generate plain-English recommendations ──
    recommendations = _generate_recommendations(
        layer_analysis=layer_analysis,
        entry_analysis=entry_analysis,
        exit_analysis=exit_analysis,
        overall_win_rate=overall_win_rate,
        total_analyzed=total_analyzed,
        wins_count=len(wins),
        losses_count=len(losses),
    )

    return {
        "total_trades_analyzed": total_analyzed,
        "trades_with_snapshot": len(trades_with_snapshot),
        "trades_without_snapshot": trades_without_snapshot,
        "win_rate": overall_win_rate,
        "avg_pnl_pct": overall_avg_pnl,
        "layer_analysis": layer_analysis,
        "entry_analysis": entry_analysis,
        "exit_analysis": exit_analysis,
        "recommendations": recommendations,
    }


def _generate_recommendations(
    layer_analysis: Dict[str, Dict[str, Any]],
    entry_analysis: Dict[str, Any],
    exit_analysis: Dict[str, Any],
    overall_win_rate: float,
    total_analyzed: int,
    wins_count: int,
    losses_count: int,
) -> List[str]:
    """Generate plain-English recommendations from the analysis results."""
    recs: List[str] = []

    # ── Sample size caveat ──
    if total_analyzed < 10:
        recs.append(
            f"Only {total_analyzed} closed trades analyzed — results are preliminary. "
            "Aim for 30+ trades before making weight adjustments."
        )

    # ── Layer-specific recommendations ──
    strong_predictors = []
    weak_predictors = []
    inverted_predictors = []

    for name, stats in layer_analysis.items():
        tp = stats["times_positive"]
        tn = stats["times_negative"]
        wrp = stats["win_rate_when_positive"]
        wrn = stats["win_rate_when_negative"]
        predictive = stats["predictive"]
        suggested = stats["suggested_adjustment"]

        if suggested == "insufficient_data":
            continue

        if predictive is True and tp >= MIN_SAMPLE_SIZE:
            if wrp >= 70:
                strong_predictors.append((name, wrp, tp))
            elif suggested == "increase":
                delta = wrp - (wrn if tn >= MIN_SAMPLE_SIZE else overall_win_rate)
                recs.append(
                    f"{name} correctly predicted {wrp:.0f}% of winners "
                    f"(+{delta:.0f}pp vs baseline) across {tp} trades — "
                    f"consider increasing weight (currently +/-{stats['current_weight']})"
                )

        if predictive is False and tp >= MIN_SAMPLE_SIZE and tn >= MIN_SAMPLE_SIZE:
            if wrn > wrp:
                inverted_predictors.append((name, wrp, wrn))
            else:
                weak_predictors.append((name, wrp))

    # Summarize strong predictors
    for name, wr, count in strong_predictors:
        recs.append(
            f"{name} was positive in {count} trades with {wr:.0f}% win rate — "
            f"strong predictor, current weight is appropriate or could increase"
        )

    # Summarize weak/inverted
    for name, wrp, wrn in inverted_predictors:
        recs.append(
            f"{name} showed INVERTED correlation: {wrn:.0f}% win rate when negative "
            f"vs {wrp:.0f}% when positive — consider reducing weight or reviewing the scoring logic"
        )

    for name, wrp in weak_predictors:
        recs.append(
            f"{name} showed no meaningful correlation with outcomes "
            f"(win rate {wrp:.0f}% when positive vs overall {overall_win_rate:.0f}%) — "
            f"consider reducing weight"
        )

    # ── Entry score effectiveness ──
    avg_w = entry_analysis.get("avg_score_winners", 0)
    avg_l = entry_analysis.get("avg_score_losers", 0)
    if avg_w > 0 or avg_l > 0:
        if entry_analysis.get("score_separates"):
            recs.append(
                f"Average winning score was {avg_w:.1f} vs losing score {avg_l:.1f} — "
                f"score threshold is effective at separating winners from losers"
            )
        else:
            delta = avg_w - avg_l
            recs.append(
                f"Average winning score ({avg_w:.1f}) vs losing score ({avg_l:.1f}) — "
                f"delta is only {delta:.1f}, consider raising the buy threshold"
            )

    # ── Exit analysis insights ──
    total_exits = (
        exit_analysis["stop_loss_count"] + exit_analysis["trailing_stop_count"]
        + exit_analysis["take_profit_count"] + exit_analysis["news_guard_count"]
        + exit_analysis["manual_count"] + exit_analysis.get("other_count", 0)
    )

    if total_exits > 0:
        sl_pct = exit_analysis["stop_loss_count"] / total_exits * 100
        if sl_pct > 60:
            recs.append(
                f"Most losses exited via stop_loss ({sl_pct:.0f}%) — "
                f"stops may be too tight. Consider widening ATR multiplier from 2.5x."
            )

        ts_pct = exit_analysis["trailing_stop_count"] / total_exits * 100
        tp_pct = exit_analysis["take_profit_count"] / total_exits * 100
        if tp_pct > 0 and ts_pct > tp_pct * 2:
            recs.append(
                f"Trailing stop exits ({ts_pct:.0f}%) significantly outnumber take profit "
                f"({tp_pct:.0f}%) — trailing stop is giving back gains; "
                f"consider tightening the trailing multiplier for high-conviction trades"
            )

        ng_pct = exit_analysis["news_guard_count"] / total_exits * 100
        if ng_pct > 20:
            recs.append(
                f"News guard forced {ng_pct:.0f}% of exits — "
                f"external events are a significant factor; ensure pre-trade news gate is strict"
            )

    # ── Holding period insights ──
    avg_dw = exit_analysis.get("avg_days_winners", 0)
    avg_dl = exit_analysis.get("avg_days_losers", 0)
    if avg_dw > 0 and avg_dl > 0:
        if avg_dw > avg_dl * 1.5:
            recs.append(
                f"Winners held {avg_dw:.0f} days on average vs losers {avg_dl:.0f} days — "
                f"trailing stop is working well, letting winners run"
            )
        elif avg_dl > avg_dw:
            recs.append(
                f"Losers held longer ({avg_dl:.0f} days) than winners ({avg_dw:.0f} days) — "
                f"consider tightening time-based exit for trades that haven't moved"
            )

    if not recs:
        recs.append("Insufficient data to generate meaningful recommendations yet.")

    return recs
