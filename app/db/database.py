"""
SQLite database for storing news, events, analyses, and reports.
"""

from __future__ import annotations

import json
import sqlite3
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from app.config import config

logger = logging.getLogger(__name__)

import threading

_local = threading.local()
_tables_init_lock = threading.Lock()
_tables_initialized = False


def get_connection() -> sqlite3.Connection:
    """Get or create a per-thread database connection.

    Each thread gets its own connection to avoid malloc crashes
    on Python 3.9 + macOS when asyncio.to_thread shares a connection.
    WAL mode allows concurrent readers across threads.
    """
    global _tables_initialized
    conn = getattr(_local, "conn", None)
    if conn is None:
        db_path = Path(config.db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        _local.conn = conn

    # Initialize tables once (thread-safe)
    if not _tables_initialized:
        with _tables_init_lock:
            if not _tables_initialized:
                _init_tables(conn)
                _tables_initialized = True

    return conn


def _init_tables(conn: sqlite3.Connection):
    """Create all tables. Uses executescript which runs outside transactions."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            source TEXT,
            url TEXT UNIQUE,
            published_at TEXT,
            source_api TEXT,
            sentiment_score REAL,
            sentiment_label TEXT,
            raw_data TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            summary TEXT,
            category TEXT,
            severity TEXT,
            regions TEXT,
            related_tickers TEXT,
            source_headlines TEXT,
            signal_type TEXT,
            signal_reasoning TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS causal_chains (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            chain TEXT NOT NULL,
            chain_order INTEGER,
            confidence TEXT,
            FOREIGN KEY (event_id) REFERENCES events(id)
        );

        CREATE TABLE IF NOT EXISTS sector_impacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            sector TEXT NOT NULL,
            direction TEXT NOT NULL,
            reason TEXT,
            confidence TEXT,
            FOREIGN KEY (event_id) REFERENCES events(id)
        );

        CREATE TABLE IF NOT EXISTS stock_picks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER,
            report_id INTEGER,
            ticker TEXT NOT NULL,
            direction TEXT NOT NULL,
            action TEXT,
            reason TEXT,
            risk TEXT,
            confidence TEXT,
            exposure TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            overall_sentiment TEXT,
            confidence TEXT,
            key_themes TEXT,
            sector_outlook TEXT,
            conflicting_signals TEXT,
            reinforcing_signals TEXT,
            watchlist TEXT,
            raw_data TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published_at);
        CREATE INDEX IF NOT EXISTS idx_events_created ON events(created_at);
        CREATE INDEX IF NOT EXISTS idx_reports_created ON reports(created_at);
        CREATE INDEX IF NOT EXISTS idx_stock_picks_ticker ON stock_picks(ticker);

        CREATE TABLE IF NOT EXISTS paper_portfolio (
            id INTEGER PRIMARY KEY DEFAULT 1,
            starting_capital REAL NOT NULL DEFAULT 100000,
            current_cash REAL NOT NULL DEFAULT 100000,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS paper_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            strategy TEXT NOT NULL,
            sector TEXT NOT NULL,
            direction TEXT DEFAULT 'long',
            conviction TEXT NOT NULL,
            conviction_score REAL NOT NULL,
            sentiment_score REAL,
            signal_price REAL NOT NULL,
            entry_price REAL NOT NULL,
            shares REAL NOT NULL,
            position_value REAL NOT NULL,
            stop_loss_price REAL NOT NULL,
            trailing_stop_price REAL,
            atr REAL,
            take_profit_price REAL NOT NULL,
            take_profit_type TEXT NOT NULL DEFAULT 'resistance',
            analysis_snapshot TEXT,
            status TEXT NOT NULL DEFAULT 'open',
            current_price REAL,
            unrealized_pnl REAL,
            unrealized_pnl_pct REAL,
            exit_date TEXT,
            exit_price REAL,
            exit_reason TEXT,
            realized_pnl REAL,
            realized_pnl_pct REAL,
            days_held INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS paper_trade_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id INTEGER,
            event_type TEXT NOT NULL,
            description TEXT,
            price REAL,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS scan_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            watchlist_size INTEGER,
            scanned INTEGER,
            signals INTEGER,
            opened INTEGER,
            skipped INTEGER,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS scan_history_details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_id INTEGER NOT NULL,
            ticker TEXT NOT NULL,
            sector TEXT,
            score INTEGER,
            signal TEXT,
            direction TEXT,
            threshold INTEGER,
            price REAL,
            atr REAL,
            action TEXT,
            layers TEXT,
            earnings_warning TEXT,
            trade_id INTEGER,
            FOREIGN KEY (scan_id) REFERENCES scan_history(id)
        );

        CREATE INDEX IF NOT EXISTS idx_scan_history_created ON scan_history(created_at);
        CREATE INDEX IF NOT EXISTS idx_scan_details_scan ON scan_history_details(scan_id);
    """)

    # Migrate existing paper_trades tables that lack new columns
    existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(paper_trades)").fetchall()}
    migrations = [
        ("trailing_stop_price", "ALTER TABLE paper_trades ADD COLUMN trailing_stop_price REAL"),
        ("atr", "ALTER TABLE paper_trades ADD COLUMN atr REAL"),
        ("analysis_snapshot", "ALTER TABLE paper_trades ADD COLUMN analysis_snapshot TEXT"),
        ("direction", "ALTER TABLE paper_trades ADD COLUMN direction TEXT DEFAULT 'long'"),
    ]
    for col_name, sql in migrations:
        if col_name not in existing_cols:
            try:
                conn.execute(sql)
                conn.commit()
            except Exception:
                pass


# ── Articles ──────────────────────────────────────────────────────────────────

def save_articles(articles: List[Dict[str, Any]]) -> int:
    """Save articles, skipping duplicates by URL. Returns count of new articles."""
    conn = get_connection()
    saved = 0
    for a in articles:
        try:
            conn.execute(
                "INSERT OR IGNORE INTO articles (title, description, source, url, published_at, source_api, sentiment_score, sentiment_label, raw_data) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    a.get("title", ""),
                    a.get("description") or a.get("summary", ""),
                    a.get("source", ""),
                    a.get("url", ""),
                    a.get("published_at", ""),
                    a.get("source_api", ""),
                    a.get("overall_sentiment_score"),
                    a.get("overall_sentiment_label"),
                    json.dumps(a),
                ),
            )
            saved += conn.total_changes
        except sqlite3.Error as e:
            logger.error("Failed to save article: %s", e)
    conn.commit()
    return saved


def get_recent_articles(limit: int = 50) -> List[Dict[str, Any]]:
    """Get most recent articles with full data (including ticker_sentiments)."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT raw_data FROM articles ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    result = []
    for r in rows:
        try:
            result.append(json.loads(r["raw_data"]))
        except (json.JSONDecodeError, TypeError):
            pass
    return result


def get_articles_by_headlines(headlines: List[str]) -> List[Dict[str, Any]]:
    """Match stored articles by headline text. Returns full article data."""
    if not headlines:
        return []
    conn = get_connection()
    placeholders = ",".join("?" for _ in headlines)
    rows = conn.execute(
        f"SELECT raw_data FROM articles WHERE title IN ({placeholders})",
        headlines,
    ).fetchall()
    result = []
    for r in rows:
        try:
            result.append(json.loads(r["raw_data"]))
        except (json.JSONDecodeError, TypeError):
            pass
    return result


# ── Events ────────────────────────────────────────────────────────────────────

def save_event(event: Dict[str, Any], signal_type: str = "", signal_reasoning: str = "") -> int:
    """Save an event and return its ID."""
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO events (title, summary, category, severity, regions, related_tickers, source_headlines, signal_type, signal_reasoning) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            event.get("title", ""),
            event.get("summary", ""),
            event.get("category", ""),
            event.get("severity", ""),
            json.dumps(event.get("regions", [])),
            json.dumps(event.get("related_tickers", [])),
            json.dumps(event.get("source_headlines", [])),
            signal_type,
            signal_reasoning,
        ),
    )
    conn.commit()
    return cursor.lastrowid


def update_event_analysis(event_id: int, signal_type: str, signal_reasoning: str):
    """Update an existing event with analysis results."""
    conn = get_connection()
    conn.execute(
        "UPDATE events SET signal_type = ?, signal_reasoning = ? WHERE id = ?",
        (signal_type, signal_reasoning, event_id),
    )
    # Clear previous analysis data for re-analysis
    conn.execute("DELETE FROM causal_chains WHERE event_id = ?", (event_id,))
    conn.execute("DELETE FROM sector_impacts WHERE event_id = ?", (event_id,))
    conn.execute("DELETE FROM stock_picks WHERE event_id = ?", (event_id,))
    conn.commit()


def save_causal_chains(event_id: int, chains: List[Dict[str, Any]]):
    """Save causal chains for an event."""
    conn = get_connection()
    for c in chains:
        conn.execute(
            "INSERT INTO causal_chains (event_id, chain, chain_order, confidence) VALUES (?, ?, ?, ?)",
            (event_id, c.get("chain", ""), c.get("order"), c.get("confidence")),
        )
    conn.commit()


def save_sector_impacts(event_id: int, sectors: List[Dict[str, Any]]):
    """Save sector impacts for an event."""
    conn = get_connection()
    for s in sectors:
        conn.execute(
            "INSERT INTO sector_impacts (event_id, sector, direction, reason, confidence) VALUES (?, ?, ?, ?, ?)",
            (event_id, s.get("name", ""), s.get("direction", ""), s.get("reason", ""), s.get("confidence")),
        )
    conn.commit()


def save_stock_picks(picks: List[Dict[str, Any]], event_id: Optional[int] = None, report_id: Optional[int] = None):
    """Save stock picks."""
    conn = get_connection()
    for p in picks:
        conn.execute(
            "INSERT INTO stock_picks (event_id, report_id, ticker, direction, action, reason, risk, confidence, exposure) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                event_id, report_id,
                p.get("ticker", ""),
                p.get("direction", p.get("action", "")),
                p.get("action", ""),
                p.get("reason") or p.get("thesis", ""),
                p.get("risk", ""),
                p.get("confidence", ""),
                p.get("exposure", ""),
            ),
        )
    conn.commit()


def get_events(limit: int = 20) -> List[Dict[str, Any]]:
    """Get recent events with their chains and impacts."""
    conn = get_connection()
    events = conn.execute(
        "SELECT * FROM events ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()

    result = []
    for e in events:
        event = dict(e)
        event["regions"] = json.loads(event.get("regions", "[]"))
        event["related_tickers"] = json.loads(event.get("related_tickers", "[]"))
        event["source_headlines"] = json.loads(event.get("source_headlines", "[]"))
        event["causal_chains"] = [
            dict(r) for r in conn.execute(
                "SELECT * FROM causal_chains WHERE event_id = ? ORDER BY chain_order", (e["id"],)
            ).fetchall()
        ]
        event["sector_impacts"] = [
            dict(r) for r in conn.execute(
                "SELECT * FROM sector_impacts WHERE event_id = ?", (e["id"],)
            ).fetchall()
        ]
        event["stock_picks"] = [
            dict(r) for r in conn.execute(
                "SELECT * FROM stock_picks WHERE event_id = ?", (e["id"],)
            ).fetchall()
        ]
        result.append(event)

    return result


def get_event(event_id: int) -> Optional[Dict[str, Any]]:
    """Get a single event with full details."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if not row:
        return None

    event = dict(row)
    event["regions"] = json.loads(event.get("regions", "[]"))
    event["related_tickers"] = json.loads(event.get("related_tickers", "[]"))
    event["source_headlines"] = json.loads(event.get("source_headlines", "[]"))
    event["causal_chains"] = [
        dict(r) for r in conn.execute(
            "SELECT * FROM causal_chains WHERE event_id = ? ORDER BY chain_order", (event_id,)
        ).fetchall()
    ]
    event["sector_impacts"] = [
        dict(r) for r in conn.execute(
            "SELECT * FROM sector_impacts WHERE event_id = ?", (event_id,)
        ).fetchall()
    ]
    event["stock_picks"] = [
        dict(r) for r in conn.execute(
            "SELECT * FROM stock_picks WHERE event_id = ?", (event_id,)
        ).fetchall()
    ]
    return event


# ── Reports ───────────────────────────────────────────────────────────────────

def save_report(report: Dict[str, Any]) -> int:
    """Save a synthesis report and return its ID."""
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO reports (overall_sentiment, confidence, key_themes, sector_outlook, conflicting_signals, reinforcing_signals, watchlist, raw_data) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            report.get("overall_sentiment", ""),
            report.get("confidence", ""),
            json.dumps(report.get("key_themes", [])),
            json.dumps(report.get("sector_outlook", [])),
            json.dumps(report.get("conflicting_signals", [])),
            json.dumps(report.get("reinforcing_signals", [])),
            json.dumps(report.get("watchlist", [])),
            json.dumps(report),
        ),
    )
    conn.commit()

    report_id = cursor.lastrowid
    top_picks = report.get("top_picks", [])
    if top_picks:
        save_stock_picks(top_picks, report_id=report_id)

    return report_id


def get_latest_report() -> Optional[Dict[str, Any]]:
    """Get the most recent synthesis report."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM reports ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    if not row:
        return None

    report = dict(row)
    for field in ("key_themes", "sector_outlook", "conflicting_signals", "reinforcing_signals", "watchlist"):
        report[field] = json.loads(report.get(field, "[]"))
    report["top_picks"] = [
        dict(r) for r in conn.execute(
            "SELECT * FROM stock_picks WHERE report_id = ?", (report["id"],)
        ).fetchall()
    ]
    return report


# ── Paper Trading ─────────────────────────────────────────────────────────────

def init_paper_portfolio(starting_capital: float = 100_000.0) -> None:
    conn = get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO paper_portfolio (id, starting_capital, current_cash) VALUES (1, ?, ?)",
        (starting_capital, starting_capital),
    )
    conn.commit()


def get_paper_portfolio() -> Optional[Dict[str, Any]]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM paper_portfolio WHERE id = 1").fetchone()
    return dict(row) if row else None


def deduct_cash(amount: float) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE paper_portfolio SET current_cash = current_cash - ?, updated_at = datetime('now') WHERE id = 1",
        (amount,),
    )
    conn.commit()


def return_cash(amount: float) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE paper_portfolio SET current_cash = current_cash + ?, updated_at = datetime('now') WHERE id = 1",
        (amount,),
    )
    conn.commit()


def open_paper_trade(**kwargs) -> int:
    conn = get_connection()
    cursor = conn.execute(
        """INSERT INTO paper_trades
           (ticker, sector, strategy, direction, conviction, conviction_score, sentiment_score,
            signal_price, entry_price, shares, position_value,
            stop_loss_price, trailing_stop_price, atr, take_profit_price, take_profit_type,
            analysis_snapshot)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            kwargs["ticker"], kwargs["sector"], kwargs["strategy"],
            kwargs.get("direction", "long"),
            kwargs["conviction"], kwargs["conviction_score"], kwargs.get("sentiment_score"),
            kwargs["signal_price"], kwargs["entry_price"], kwargs["shares"], kwargs["position_value"],
            kwargs["stop_loss_price"], kwargs.get("trailing_stop_price"), kwargs.get("atr"),
            kwargs["take_profit_price"], kwargs.get("take_profit_type", "resistance"),
            kwargs.get("analysis_snapshot"),
        ),
    )
    conn.commit()
    return cursor.lastrowid


def get_paper_trade(trade_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM paper_trades WHERE id = ?", (trade_id,)).fetchone()
    return dict(row) if row else None


def get_paper_trades(status: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_connection()
    if status:
        rows = conn.execute(
            "SELECT * FROM paper_trades WHERE status = ? ORDER BY created_at DESC", (status,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM paper_trades ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def close_paper_trade(trade_id: int, exit_price: float, exit_reason: str,
                       realized_pnl: float, realized_pnl_pct: float, days_held: int) -> None:
    conn = get_connection()
    conn.execute(
        """UPDATE paper_trades SET
           status = 'closed', exit_date = datetime('now'), exit_price = ?,
           exit_reason = ?, realized_pnl = ?, realized_pnl_pct = ?,
           days_held = ?, updated_at = datetime('now')
           WHERE id = ?""",
        (exit_price, exit_reason, realized_pnl, realized_pnl_pct, days_held, trade_id),
    )
    conn.commit()


def update_trade_price(trade_id: int, current_price: float,
                        unrealized_pnl: float, unrealized_pnl_pct: float, days_held: int,
                        stop_loss_price: float = None, trailing_stop_price: float = None) -> None:
    conn = get_connection()
    if stop_loss_price is not None:
        conn.execute(
            """UPDATE paper_trades SET
               current_price = ?, unrealized_pnl = ?, unrealized_pnl_pct = ?,
               days_held = ?, stop_loss_price = ?, trailing_stop_price = ?,
               updated_at = datetime('now')
               WHERE id = ?""",
            (current_price, unrealized_pnl, unrealized_pnl_pct, days_held,
             stop_loss_price, trailing_stop_price, trade_id),
        )
    else:
        conn.execute(
            """UPDATE paper_trades SET
               current_price = ?, unrealized_pnl = ?, unrealized_pnl_pct = ?,
               days_held = ?, updated_at = datetime('now')
               WHERE id = ?""",
            (current_price, unrealized_pnl, unrealized_pnl_pct, days_held, trade_id),
        )
    conn.commit()


def log_trade_event(trade_id: int, event_type: str, description: str, price: Optional[float] = None) -> None:
    conn = get_connection()
    conn.execute(
        "INSERT INTO paper_trade_log (trade_id, event_type, description, price) VALUES (?, ?, ?, ?)",
        (trade_id, event_type, description, price),
    )
    conn.commit()


def get_trade_log(trade_id: int) -> List[Dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM paper_trade_log WHERE trade_id = ? ORDER BY created_at ASC", (trade_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def reset_paper_portfolio() -> None:
    conn = get_connection()
    conn.execute("DELETE FROM paper_trade_log")
    conn.execute("DELETE FROM paper_trades")
    conn.execute("UPDATE paper_portfolio SET current_cash = starting_capital, updated_at = datetime('now') WHERE id = 1")
    conn.commit()


# ── Scan History ─────────────────────────────────────────────────────────────

def save_scan(summary: Dict[str, Any], details: List[Dict[str, Any]]) -> int:
    """Save a complete scan with per-ticker details. Returns scan_id."""
    conn = get_connection()
    cursor = conn.execute(
        """INSERT INTO scan_history (watchlist_size, scanned, signals, opened, skipped)
           VALUES (?, ?, ?, ?, ?)""",
        (summary.get("watchlist_size", 0), summary.get("scanned", 0),
         summary.get("signals", 0), summary.get("opened", 0), summary.get("skipped", 0)),
    )
    scan_id = cursor.lastrowid

    for d in details:
        layers_json = json.dumps(d.get("layers")) if d.get("layers") else None
        conn.execute(
            """INSERT INTO scan_history_details
               (scan_id, ticker, sector, score, signal, direction, threshold, price,
                atr, action, layers, earnings_warning, trade_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (scan_id, d.get("ticker"), d.get("sector"), d.get("score"),
             d.get("signal"), d.get("direction"), d.get("threshold"),
             d.get("price"), d.get("atr"), d.get("action"),
             layers_json, d.get("earnings_warning"), d.get("trade_id")),
        )

    conn.commit()
    return scan_id


def get_scan_history(limit: int = 20) -> List[Dict[str, Any]]:
    """Get recent scans (summary only)."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM scan_history ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


def get_scan_details(scan_id: int) -> Dict[str, Any]:
    """Get a single scan with all per-ticker details."""
    conn = get_connection()
    scan = conn.execute("SELECT * FROM scan_history WHERE id = ?", (scan_id,)).fetchone()
    if not scan:
        return {}
    details = conn.execute(
        "SELECT * FROM scan_history_details WHERE scan_id = ? ORDER BY ticker", (scan_id,)
    ).fetchall()
    result = dict(scan)
    parsed_details = []
    for d in details:
        dd = dict(d)
        if dd.get("layers") and isinstance(dd["layers"], str):
            try:
                dd["layers"] = json.loads(dd["layers"])
            except (ValueError, TypeError):
                pass
        parsed_details.append(dd)
    result["details"] = parsed_details
    return result
