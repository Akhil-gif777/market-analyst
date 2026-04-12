"""
Paper trading watchlist — core stocks + dynamic additions from market movers.

Core: 10 top S&P 500 stocks by market cap, across sectors (always scanned).
Dynamic: top gainers + most active from Alpha Vantage (institutional interest).
"""
from __future__ import annotations
import logging
from typing import Dict

logger = logging.getLogger(__name__)

# Core watchlist — always scanned
CORE_WATCHLIST: Dict[str, str] = {
    "AAPL": "Technology",
    "MSFT": "Technology",
    "NVDA": "Technology",
    "AMZN": "Consumer Discretionary",
    "GOOGL": "Communication Services",
    "META": "Communication Services",
    "JPM": "Financials",
    "UNH": "Healthcare",
    "XOM": "Energy",
    "TSLA": "Consumer Discretionary",
}

# Sector lookup for dynamic tickers
SECTOR_LOOKUP: Dict[str, str] = {
    # Technology
    "AMD": "Technology", "INTC": "Technology", "CRM": "Technology",
    "ORCL": "Technology", "ADBE": "Technology", "CSCO": "Technology",
    "AVGO": "Technology", "QCOM": "Technology", "NOW": "Technology",
    "PANW": "Technology", "SNPS": "Technology", "MU": "Technology",
    # Healthcare
    "JNJ": "Healthcare", "LLY": "Healthcare", "PFE": "Healthcare",
    "ABBV": "Healthcare", "MRK": "Healthcare", "TMO": "Healthcare",
    "ABT": "Healthcare", "AMGN": "Healthcare", "GILD": "Healthcare",
    "ISRG": "Healthcare", "VRTX": "Healthcare",
    # Financials
    "BAC": "Financials", "WFC": "Financials", "GS": "Financials",
    "MS": "Financials", "C": "Financials", "BLK": "Financials",
    "SCHW": "Financials", "AXP": "Financials",
    # Consumer Discretionary
    "HD": "Consumer Discretionary", "MCD": "Consumer Discretionary",
    "NKE": "Consumer Discretionary", "SBUX": "Consumer Discretionary",
    "LOW": "Consumer Discretionary", "BKNG": "Consumer Discretionary",
    # Communication Services
    "NFLX": "Communication Services", "DIS": "Communication Services",
    "CMCSA": "Communication Services", "T": "Communication Services",
    # Energy
    "CVX": "Energy", "COP": "Energy", "EOG": "Energy",
    "SLB": "Energy", "OXY": "Energy",
    # Consumer Staples
    "PG": "Consumer Staples", "KO": "Consumer Staples",
    "PEP": "Consumer Staples", "COST": "Consumer Staples",
    "WMT": "Consumer Staples",
    # Industrials
    "CAT": "Industrials", "DE": "Industrials", "HON": "Industrials",
    "UPS": "Industrials", "BA": "Industrials", "GE": "Industrials",
    "RTX": "Industrials", "LMT": "Industrials",
}


def guess_sector(ticker: str) -> str:
    """Best-effort sector guess for a ticker."""
    return SECTOR_LOOKUP.get(ticker, "Unknown")


def get_dynamic_watchlist(include_movers: bool = True) -> Dict[str, str]:
    """
    Build watchlist: core stocks + top movers from Alpha Vantage.
    Filters out penny stocks (<$10) and OTC tickers (>5 chars).
    """
    watchlist = dict(CORE_WATCHLIST)

    if not include_movers:
        return watchlist

    try:
        from app.clients.alpha_vantage import get_market_movers
        movers = get_market_movers()

        # Top gainers — momentum plays (up to 5)
        for m in (movers.get("top_gainers") or [])[:5]:
            ticker = m.get("ticker", "")
            if ticker and ticker not in watchlist and len(ticker) <= 5:
                try:
                    price = float(m.get("price", 0))
                except (ValueError, TypeError):
                    continue
                if price >= 10:
                    watchlist[ticker] = guess_sector(ticker)

        # Most active — high volume = institutional interest (up to 5)
        for m in (movers.get("most_active") or movers.get("most_actively_traded") or [])[:5]:
            ticker = m.get("ticker", "")
            if ticker and ticker not in watchlist and len(ticker) <= 5:
                try:
                    price = float(m.get("price", 0))
                except (ValueError, TypeError):
                    continue
                if price >= 10:
                    watchlist[ticker] = guess_sector(ticker)

    except Exception as e:
        logger.debug("Dynamic watchlist expansion failed: %s", e)

    return watchlist


# Backward compatibility
WATCHLIST = CORE_WATCHLIST
SECTORS = sorted(set(CORE_WATCHLIST.values()))
