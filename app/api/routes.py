"""
FastAPI routes for the market analyst API.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query, Request, Path as PathParam
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, field_validator

from app.analysis.pipeline import run_full_analysis, scan_news, analyze_event_by_id, generate_market_overview, analyze_stock_price_action, analyze_stock_fundamentals
from app.db import database as db
from app.clients import ollama

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

logger = logging.getLogger(__name__)

# ── Background price poller ──────────────────────────────────────────────────

POLL_INTERVAL_SECONDS = 300  # 5 minutes
_poll_task = None

def _is_market_hours() -> bool:
    """Check if US stock market is open (9:30 AM - 4:00 PM ET, weekdays)."""
    et = datetime.now(timezone(timedelta(hours=-4)))  # EDT (summer) — close enough
    if et.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    market_open = et.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = et.replace(hour=16, minute=0, second=0, microsecond=0)
    return market_open <= et <= market_close

async def _poll_open_positions():
    """Background task: update open positions every 5 minutes during market hours."""
    while True:
        try:
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
            if not _is_market_hours():
                logger.debug("[POLLER] Market closed — skipping")
                continue
            open_trades = db.get_paper_trades(status="open")
            if not open_trades:
                logger.debug("[POLLER] No open positions — skipping")
                continue
            logger.info("[POLLER] Market open, updating %d positions...", len(open_trades))
            from app.paper_trading.executor import update_open_positions
            result = await asyncio.to_thread(update_open_positions)
            logger.info("[POLLER] Updated %d, closed %d", result.get("updated", 0), result.get("closed", 0))
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("[POLLER] Error: %s", e)

@asynccontextmanager
async def lifespan(app):
    """Start background poller on startup, cancel on shutdown."""
    global _poll_task
    _poll_task = asyncio.create_task(_poll_open_positions())
    print(f"[POLLER] Background price poller started (every {POLL_INTERVAL_SECONDS}s during market hours)")
    logger.info("[POLLER] Background price poller started (every %ds during market hours)", POLL_INTERVAL_SECONDS)
    yield
    _poll_task.cancel()
    try:
        await _poll_task
    except asyncio.CancelledError:
        pass
    logger.info("[POLLER] Background price poller stopped")

app = FastAPI(
    title="Market Analyst",
    description="AI-powered market analysis — news-driven causal reasoning with stock picks",
    version="0.1.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def csrf_guard(request: Request, call_next):
    """Block cross-origin form POSTs by requiring Content-Type: application/json on mutations."""
    if request.method == "POST":
        ct = request.headers.get("content-type", "")
        if "application/json" not in ct:
            return JSONResponse(
                status_code=403,
                content={"detail": "POST requests must include Content-Type: application/json"},
            )
    return await call_next(request)


@app.get("/", include_in_schema=False)
def root():
    """Serve the UI."""
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/health")
def health():
    """Health check — verifies Ollama and database are accessible."""
    ollama_ok = ollama.check_available()
    return {
        "status": "ok" if ollama_ok else "degraded",
        "ollama": "connected" if ollama_ok else "unavailable",
        "database": "connected",
    }


@app.post("/scan")
def scan():
    """
    Scan news and extract market-moving events (fast, lightweight).

    Returns a list of detected events with IDs. Use POST /events/{id}/analyze
    to run deep analysis on specific events.
    """
    result = scan_news()
    if result.get("error") and not result.get("events"):
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@app.post("/events/{event_id}/analyze")
def deep_analyze_event(event_id: int):
    """Run deep analysis on a previously scanned event."""
    result = analyze_event_by_id(event_id)
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@app.post("/analyze")
def analyze(max_events: int = Query(default=5, ge=1, le=50)):
    """
    Trigger a full analysis cycle.

    Fetches news, extracts events, builds causal chains,
    enriches with market data, and produces a holistic report with stock picks.
    Only the top max_events (by severity) are deeply analyzed.
    """
    result = run_full_analysis(max_events=max_events)
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])
    return result



@app.get("/report")
def get_report():
    """Get the latest synthesis report."""
    report = db.get_latest_report()
    if not report:
        raise HTTPException(status_code=404, detail="No reports yet — run POST /analyze first")
    return report


@app.get("/events")
def get_events(limit: int = Query(default=20, le=100)):
    """Get recent market-moving events with causal chains and stock picks."""
    events = db.get_events(limit=limit)
    return {"events": events, "count": len(events)}


@app.get("/events/{event_id}")
def get_event(event_id: int):
    """Get a single event with full causal chain details."""
    event = db.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")
    return event


@app.get("/events/{event_id}/chain")
def get_event_chain(event_id: int):
    """Get the causal chain for a specific event."""
    event = db.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")
    return {
        "event": event["title"],
        "causal_chains": event["causal_chains"],
        "sector_impacts": event["sector_impacts"],
        "stock_picks": event["stock_picks"],
    }


@app.get("/events/{event_id}/articles")
def get_event_articles(event_id: int):
    """Get news articles that sourced a specific event."""
    event = db.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")
    headlines = event.get("source_headlines", [])
    articles = db.get_articles_by_headlines(headlines)
    return {
        "event_id": event_id,
        "event_title": event["title"],
        "articles": articles,
        "count": len(articles),
    }


@app.get("/news")
def get_news(limit: int = Query(default=20, le=100)):
    """Get recent events with their source articles."""
    events = db.get_events(limit=limit)
    result = []
    for event in events:
        headlines = event.get("source_headlines", [])
        articles = db.get_articles_by_headlines(headlines)
        result.append({
            "event": {
                "id": event["id"],
                "title": event["title"],
                "summary": event.get("summary", ""),
                "category": event.get("category", ""),
                "severity": event.get("severity", ""),
                "related_tickers": event.get("related_tickers", []),
                "created_at": event.get("created_at", ""),
            },
            "articles": articles,
        })
    return {"events": result, "count": len(result)}


@app.get("/market")
def get_market_overview():
    """Get current market snapshot — indices, sectors, movers, yields, forex, crypto, indicators, commodities. No LLM calls."""
    from app.analysis.pipeline import _build_market_snapshot
    snapshot = _build_market_snapshot()
    return snapshot


@app.post("/market/analyze")
def analyze_market():
    """Generate an LLM-powered market overview using all available market data."""
    result = generate_market_overview()
    if result.get("error") and not result.get("overview"):
        raise HTTPException(status_code=500, detail=result["error"])
    return result


_TICKER_RE = re.compile(r"^[A-Za-z0-9.\-]{1,10}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _validate_ticker(ticker: str) -> str:
    """Validate and normalize a ticker symbol."""
    ticker = ticker.strip().upper()
    if not _TICKER_RE.match(ticker):
        raise HTTPException(status_code=400, detail=f"Invalid ticker format: {ticker!r}")
    return ticker


@app.get("/stock/{ticker}/price-action")
def get_stock_price_action(ticker: str):
    """Run price action analysis on a single stock — multi-timeframe confluence scoring + LLM narrative."""
    ticker = _validate_ticker(ticker)
    result = analyze_stock_price_action(ticker)
    if result.get("error") and not result.get("score"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.get("/stock/{ticker}/fundamentals")
def get_stock_fundamentals(ticker: str):
    """Run standalone fundamental analysis — 7 silos (valuation, profitability, growth, health, earnings, ownership, dividend) + LLM narrative."""
    ticker = _validate_ticker(ticker)
    result = analyze_stock_fundamentals(ticker)
    if result.get("error") and not result.get("valuation"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


class BacktestRequest(BaseModel):
    tickers: List[str] = ["AAPL", "MSFT", "GOOGL"]
    start: str = "2022-01-01"
    end: str = "2025-12-31"
    horizons: List[int] = [5, 10, 20]
    strategies: Optional[List[str]] = None
    warmup: int = 252

    @field_validator("tickers")
    @classmethod
    def validate_tickers(cls, v):
        if len(v) > 30:
            raise ValueError("Maximum 30 tickers allowed")
        for t in v:
            if not _TICKER_RE.match(t.strip()):
                raise ValueError(f"Invalid ticker format: {t!r}")
        return [t.strip().upper() for t in v]

    @field_validator("start", "end")
    @classmethod
    def validate_dates(cls, v):
        if not _DATE_RE.match(v):
            raise ValueError(f"Date must be YYYY-MM-DD format, got: {v!r}")
        return v


@app.post("/backtest")
async def run_backtest_endpoint(req: BacktestRequest):
    """
    Run multi-strategy price action backtest.

    Downloads historical OHLCV, runs selected strategies across all tickers,
    computes forward returns vs SPY benchmark, and returns a comparative report.
    Long-running (~15-30s depending on tickers/date range).
    """
    from validation.backtest import run_backtest, build_backtest_report
    from validation.strategies import ALL_STRATEGIES

    invalid = [s for s in (req.strategies or []) if s not in ALL_STRATEGIES]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Unknown strategies: {invalid}. Valid: {list(ALL_STRATEGIES.keys())}")

    t_start = time.time()
    try:
        strategy_signals = await asyncio.to_thread(
            run_backtest,
            tickers=req.tickers,
            start=req.start,
            end=req.end,
            warmup=req.warmup,
            horizons=req.horizons,
            strategy_names=req.strategies,
        )
    except Exception as e:
        logger.exception("Backtest failed")
        raise HTTPException(status_code=500, detail="Backtest failed — check server logs for details")

    elapsed = time.time() - t_start

    if not strategy_signals:
        raise HTTPException(status_code=500, detail="No data returned — check ticker symbols and date range")

    report = build_backtest_report(strategy_signals, req.horizons, req.tickers, elapsed)
    return report


@app.get("/search/tickers")
def search_tickers_endpoint(q: str = Query(default="")):
    """Search for ticker symbols via Alpha Vantage SYMBOL_SEARCH."""
    if not q or len(q.strip()) < 1:
        return {"results": []}
    from app.clients.alpha_vantage import search_tickers
    return {"results": search_tickers(q.strip())}


# ── Paper Trading ─────────────────────────────────────────────────────────────

@app.get("/paper/portfolio")
def get_paper_portfolio():
    """Get paper trading portfolio summary."""
    from app.paper_trading.portfolio import get_portfolio_summary
    return get_portfolio_summary()


@app.get("/paper/trades")
def get_paper_trades_endpoint(status: Optional[str] = Query(default=None)):
    """Get paper trades. Filter by status=open|closed."""
    return {"trades": db.get_paper_trades(status=status)}


@app.get("/paper/trades/{trade_id}")
def get_paper_trade_endpoint(trade_id: int):
    """Get a single paper trade with its event log and analysis snapshot."""
    import json as _json
    trade = db.get_paper_trade(trade_id)
    if not trade:
        raise HTTPException(status_code=404, detail=f"Trade {trade_id} not found")
    log = db.get_trade_log(trade_id)
    result = {**trade, "log": log}
    # Deserialize the analysis snapshot from JSON string
    if result.get("analysis_snapshot") and isinstance(result["analysis_snapshot"], str):
        try:
            result["analysis_snapshot"] = _json.loads(result["analysis_snapshot"])
        except (ValueError, TypeError):
            pass
    return result


@app.post("/paper/scan")
async def paper_scan():
    """
    Scan the watchlist for strategy signals and open trades automatically.
    Long-running (~3-5 min for full 60-ticker scan). Runs in background thread.
    """
    from app.paper_trading.scanner import run_scan
    try:
        result = await asyncio.to_thread(run_scan)
        return result
    except Exception as e:
        logger.exception("Paper scan failed")
        raise HTTPException(status_code=500, detail="Paper scan failed — check server logs for details")


@app.post("/paper/update")
async def paper_update():
    """Update all open positions with current prices, close on stop/target/time."""
    from app.paper_trading.executor import update_open_positions
    try:
        result = await asyncio.to_thread(update_open_positions)
        return result
    except Exception as e:
        logger.exception("Paper update failed")
        raise HTTPException(status_code=500, detail="Paper update failed — check server logs for details")


@app.post("/paper/trades/{trade_id}/close")
def paper_close_trade(trade_id: int):
    """Manually close a paper trade at current market price."""
    from app.paper_trading.executor import close_trade
    from app.clients.alpha_vantage import get_stock_quote
    trade = db.get_paper_trade(trade_id)
    if not trade:
        raise HTTPException(status_code=404, detail=f"Trade {trade_id} not found")
    if trade["status"] != "open":
        raise HTTPException(status_code=400, detail="Trade is already closed")
    quote = get_stock_quote(trade["ticker"])
    if not quote or not quote.get("price"):
        raise HTTPException(status_code=500, detail=f"Could not fetch current price for {trade['ticker']}")
    result = close_trade(trade_id, float(quote["price"]), "manual")
    return result


@app.post("/paper/news-guard")
async def paper_news_guard():
    """Run news scan and defensively close positions in affected sectors."""
    from app.paper_trading.news_guard import check_and_defend
    try:
        result = await asyncio.to_thread(check_and_defend)
        return result
    except Exception as e:
        logger.exception("News guard failed")
        raise HTTPException(status_code=500, detail="News guard failed — check server logs for details")


@app.get("/paper/feedback")
def get_trade_feedback():
    """
    Analyze closed trades to evaluate per-layer predictive accuracy.

    Returns layer-by-layer win rates, entry score effectiveness,
    exit reason breakdown, and plain-English recommendations for
    refining the scoring system.
    """
    from app.paper_trading.feedback import analyze_trade_feedback
    return analyze_trade_feedback()


@app.get("/paper/scans")
def get_scan_history(limit: int = Query(default=20)):
    """Get recent scan history (summary list)."""
    return {"scans": db.get_scan_history(limit=limit)}


@app.get("/paper/scans/{scan_id}")
def get_scan_detail(scan_id: int):
    """Get a single scan with all per-ticker details and reasoning."""
    result = db.get_scan_details(scan_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Scan {scan_id} not found")
    return result


@app.post("/paper/reset")
def paper_reset():
    """Reset paper trading portfolio — clears all trades and restores starting capital."""
    db.reset_paper_portfolio()
    return {"status": "reset", "message": "Portfolio reset to $100,000"}


@app.get("/sectors")
def get_sectors():
    """Get sector outlook from the latest report."""
    report = db.get_latest_report()
    if not report:
        raise HTTPException(status_code=404, detail="No reports yet — run POST /analyze first")
    return {
        "overall_sentiment": report.get("overall_sentiment"),
        "sector_outlook": report.get("sector_outlook", []),
    }
