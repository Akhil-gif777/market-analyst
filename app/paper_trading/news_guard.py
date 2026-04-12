"""
News guard — monitors market events and closes positions in affected sectors
when high-severity events directly threaten them.

Key principle: only close a position if the event SPECIFICALLY affects its sector.
A Ford tariff story shouldn't close an Apple position just because both fall under
a broad "trade" category. The event must mention the sector or related keywords.
"""
from __future__ import annotations
import logging
from typing import Dict, Any, List

from app.analysis.pipeline import scan_news
from app.db import database as db
from app.paper_trading import executor

logger = logging.getLogger(__name__)

# Only truly systemic events warrant blanket action
SYSTEMIC_KEYWORDS = [
    "market crash", "stock market crash", "financial crisis",
    "recession declared", "pandemic", "war declared",
]

# Sector-specific threat keywords — an event must mention BOTH a danger word
# AND a sector keyword to trigger closure for that sector
SECTOR_KEYWORDS = {
    "Technology": ["tech", "semiconductor", "chip", "software", "apple", "microsoft", "google", "nvidia", "ai ban"],
    "Healthcare": ["healthcare", "pharma", "drug", "fda", "hospital", "medical"],
    "Financials": ["bank", "financial", "interest rate", "fed ", "credit", "lending"],
    "Energy": ["oil", "gas", "energy", "opec", "drilling", "pipeline", "crude"],
    "Consumer Discretionary": ["consumer", "retail", "auto", "car ", "vehicle", "housing", "amazon", "tesla"],
    "Consumer Staples": ["food", "grocery", "staple", "agriculture"],
    "Industrials": ["manufacturing", "industrial", "factory", "supply chain", "shipping", "transport"],
    "Communication Services": ["telecom", "media", "streaming", "social media", "google", "meta"],
    "Materials": ["mining", "steel", "aluminum", "commodity", "raw material"],
    "Utilities": ["utility", "power grid", "electricity", "nuclear"],
    "Real Estate": ["real estate", "housing", "mortgage", "property"],
}

DANGER_KEYWORDS = [
    "war", "military", "invasion", "attack", "sanctions", "tariff",
    "recession", "crash", "default", "pandemic", "crisis", "collapse",
    "bankruptcy", "ban", "shutdown", "explosion", "terrorist",
]


def _is_dangerous(event: Dict[str, Any]) -> bool:
    """Check if an event warrants defensive action."""
    severity = event.get("severity", "").lower()
    if severity in ("high", "critical"):
        return True
    title = event.get("title", "").lower()
    summary = event.get("summary", "").lower()
    text = title + " " + summary
    return any(kw in text for kw in DANGER_KEYWORDS)


def _is_systemic(event: Dict[str, Any]) -> bool:
    """Check if an event is systemic (affects ALL sectors)."""
    text = (event.get("title", "") + " " + event.get("summary", "")).lower()
    return any(kw in text for kw in SYSTEMIC_KEYWORDS)


def _event_affects_sector(event: Dict[str, Any], sector: str) -> bool:
    """Check if a dangerous event specifically affects a given sector."""
    text = (event.get("title", "") + " " + event.get("summary", "")).lower()

    # Check sector-specific keywords
    keywords = SECTOR_KEYWORDS.get(sector, [])
    return any(kw in text for kw in keywords)


def check_and_defend() -> Dict[str, Any]:
    """
    Run news scan, identify dangerous events, close only directly affected positions.
    """
    logger.info("[NEWS GUARD] Scanning news for threats")

    result = scan_news()
    events = result.get("events", [])

    actions = []
    closed_trade_ids = set()

    open_trades = db.get_paper_trades(status="open")
    if not open_trades:
        return {"events_scanned": len(events), "dangerous_events": 0, "positions_closed": 0, "actions": []}

    for event in events:
        if not _is_dangerous(event):
            continue

        systemic = _is_systemic(event)
        title = event.get("title", "")

        for trade in open_trades:
            if trade["id"] in closed_trade_ids:
                continue

            sector = trade["sector"]

            # Systemic events close everything. Sector events only close matching sectors.
            if not systemic and not _event_affects_sector(event, sector):
                continue

            reason_prefix = "systemic" if systemic else "sector_threat"
            logger.warning("[NEWS GUARD] %s: closing %s (%s) due to: %s",
                          reason_prefix, trade["ticker"], sector, title)

            try:
                from app.clients.alpha_vantage import get_stock_quote
                quote = get_stock_quote(trade["ticker"])
                current_price = float(quote.get("price", trade["entry_price"])) if quote else trade["entry_price"]
                executor.close_trade(trade["id"], current_price, f"news_guard: {title[:60]}")
                closed_trade_ids.add(trade["id"])
                actions.append({
                    "ticker": trade["ticker"],
                    "sector": sector,
                    "reason": title[:80],
                    "type": reason_prefix,
                })
            except Exception as e:
                logger.error("[NEWS GUARD] Failed to close %s: %s", trade["ticker"], e)

    return {
        "events_scanned": len(events),
        "dangerous_events": len([e for e in events if _is_dangerous(e)]),
        "positions_closed": len(actions),
        "actions": actions,
    }
