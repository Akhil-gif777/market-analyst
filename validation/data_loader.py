"""
Data loader for backtesting — downloads OHLCV from yfinance, caches locally.

yfinance is used instead of Alpha Vantage because:
  - No API key / rate limits for historical data
  - Full history in a single call
  - Free for daily OHLCV
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import List, Dict, Any, Optional

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

CACHE_DIR = Path("validation/data")

_SAFE_TICKER = re.compile(r"^[A-Za-z0-9.\-]{1,10}$")
_SAFE_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def download_ticker(
    ticker: str,
    start: str,
    end: str,
    cache_dir: Optional[Path] = None,
) -> pd.DataFrame:
    """
    Download daily OHLCV from yfinance, caching to CSV.

    Returns DataFrame with columns: Date, Open, High, Low, Close, Volume
    sorted ascending by date.
    """
    if not _SAFE_TICKER.match(ticker):
        raise ValueError(f"Invalid ticker format: {ticker!r}")
    if not _SAFE_DATE.match(start) or not _SAFE_DATE.match(end):
        raise ValueError(f"Invalid date format: start={start!r}, end={end!r}")

    cache_dir = cache_dir or CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{ticker}_{start}_{end}.csv"

    # Verify resolved path stays under cache_dir
    if not cache_path.resolve().is_relative_to(cache_dir.resolve()):
        raise ValueError(f"Invalid cache path for ticker {ticker!r}")

    if cache_path.exists():
        logger.info("Loading cached data for %s", ticker)
        df = pd.read_csv(cache_path, parse_dates=["Date"])
        return df

    logger.info("Downloading %s from %s to %s", ticker, start, end)
    df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)

    if df.empty:
        raise ValueError(f"No data returned for {ticker} ({start} to {end})")

    df = df.reset_index()

    # yfinance may return MultiIndex columns for single ticker — flatten
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] if col[1] == "" or col[1] == ticker else col[0] for col in df.columns]

    # Standardize column names
    df = df.rename(columns={
        "Datetime": "Date",
    })

    # Keep only what we need
    required = ["Date", "Open", "High", "Low", "Close", "Volume"]
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Missing column {col} in {ticker} data. Got: {list(df.columns)}")

    df = df[required].copy()
    df = df.sort_values("Date").reset_index(drop=True)

    # Cache
    df.to_csv(cache_path, index=False)
    logger.info("Cached %d bars for %s", len(df), ticker)

    return df


def resample_weekly(daily_df: pd.DataFrame) -> pd.DataFrame:
    """
    Resample daily OHLCV to weekly bars.

    Uses business-week resampling (Friday close).
    """
    df = daily_df.set_index("Date")
    weekly = df.resample("W-FRI").agg({
        "Open": "first",
        "High": "max",
        "Low": "min",
        "Close": "last",
        "Volume": "sum",
    }).dropna()

    weekly = weekly.reset_index()
    return weekly


def df_to_ohlcv_list(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Convert DataFrame to List[Dict] format expected by price_action.py.

    Returns list sorted ascending (oldest first) with keys:
    date (str), open, high, low, close (float), volume (int).
    """
    records = []
    for _, row in df.iterrows():
        records.append({
            "date": row["Date"].strftime("%Y-%m-%d") if hasattr(row["Date"], "strftime") else str(row["Date"]),
            "open": float(row["Open"]),
            "high": float(row["High"]),
            "low": float(row["Low"]),
            "close": float(row["Close"]),
            "volume": int(row["Volume"]),
        })
    return records
