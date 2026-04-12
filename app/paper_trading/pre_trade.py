"""
Pre-trade analysis — earnings proximity check only.

The confluence scoring engine handles everything else.
No news sentiment gate — we trust the score.
Only blocks trades within 5 days of estimated earnings (binary event risk).
"""
from __future__ import annotations
import logging
from datetime import datetime, timedelta
from typing import Dict, Any

logger = logging.getLogger(__name__)

EARNINGS_DANGER_DAYS = 5


def _check_earnings_proximity(ticker: str) -> Dict[str, Any]:
    """
    Check if the ticker has earnings coming within EARNINGS_DANGER_DAYS.

    Buying right before earnings is a binary gamble — the stock could gap
    either direction regardless of score. Better to wait until after earnings
    and capture PEAD drift, which our scoring engine already detects.
    """
    try:
        from app.clients.alpha_vantage import get_earnings
        earnings = get_earnings(ticker)
        quarterly = earnings.get("quarterly", [])
        if not quarterly:
            return {"near_earnings": False, "days_until": None, "date": None}

        today = datetime.utcnow().date()

        for q in quarterly[:1]:
            reported = q.get("reportedDate") or q.get("fiscalDateEnding")
            if not reported:
                continue
            try:
                last_date = datetime.strptime(reported, "%Y-%m-%d").date()
                est_next = last_date + timedelta(days=90)
                days_until = (est_next - today).days

                if 0 <= days_until <= EARNINGS_DANGER_DAYS:
                    return {
                        "near_earnings": True,
                        "days_until": days_until,
                        "date": est_next.isoformat(),
                    }
            except (ValueError, TypeError):
                continue

    except Exception as e:
        logger.debug("[%s] Earnings check failed: %s", ticker, e)

    return {"near_earnings": False, "days_until": None, "date": None}


def analyze_pre_trade(
    ticker: str,
    sector: str,
    confluence_score: Dict[str, Any],
    levels: list,
    direction: str = "long",
) -> Dict[str, Any]:
    """
    Pre-trade check. Only blocks on earnings proximity.
    Score says buy → we buy. No news override.
    """
    score = confluence_score.get("total_score", 0)

    # Earnings proximity check
    earnings = _check_earnings_proximity(ticker)
    if earnings["near_earnings"]:
        return {
            "go": False,
            "reason": f"Earnings too close ({earnings['days_until']} days) — binary event risk",
            "conviction_score": score,
            "sentiment_score": None,
            "earnings_warning": f"Earnings estimated in {earnings['days_until']} days ({earnings['date']})",
        }

    return {
        "go": True,
        "conviction_score": score,
        "sentiment_score": None,
        "earnings_warning": None,
        "reason": "All checks passed",
    }
