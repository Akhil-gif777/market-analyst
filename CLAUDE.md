# Market Analyst

AI-powered market analysis system that combines real-time financial data with local LLM reasoning to produce actionable market insights, price action analysis, and automated paper trading.

## Architecture Overview

The system has three complementary analysis modes:

1. **Market Analyst** (proactive, macro) — Scans news, extracts market-moving events, builds causal chains, evaluates stocks against macro thesis, and synthesizes a holistic report.
2. **Stock Analyst** (on-demand, per-ticker) — Multi-timeframe price action analysis with a 13-layer confluence scoring engine and LLM narrative.
3. **Fundamental Analyst** (on-demand, per-ticker, standalone) — 7-silo fundamental analysis (valuation, profitability, growth, financial health, earnings quality, ownership, dividend). Completely independent from price action scoring — not used in signals or paper trading.

A **paper trading system** connects Market Analyst and Stock Analyst: it scans a dynamic watchlist using the same 13-layer scoring engine (price action only, no fundamentals), gates trades through earnings proximity, manages positions with support-based stops and trailing stops.

A **feedback loop** analyzes closed trades to evaluate which scoring layers predicted correctly and recommends weight adjustments.

## Tech Stack

- **Language**: Python 3.9+
- **Package Manager**: uv — `uv sync` to install, `uv run` to execute, `pyproject.toml` for deps
- **LLM**: Ollama (local) — default model `0xroyce/plutus:latest` (finance-specialized), also tested with `deepseek-r1:32b`, `qwen2.5:72b`
- **Data**: Alpha Vantage API (live), yfinance (backtesting historical data)
- **API**: FastAPI + uvicorn
- **Database**: SQLite with WAL mode (per-thread connections via `threading.local()` for async safety)
- **CLI**: argparse + rich (tables, trees, panels)
- **Frontend**: Multi-file — `index.html` + `js/app.js` + `js/components.js` + `js/transitions.js` + `js/api.js` + `css/styles.css`
- **Validation**: scipy for statistical tests (t-tests, Spearman correlation)

## Running the App

```bash
# Install dependencies (requires uv — https://docs.astral.sh/uv/getting-started/installation/)
uv sync

# Ensure Ollama is running with a model pulled
ollama serve  # in another terminal
ollama pull 0xroyce/plutus

# Start the API server
uv run server          # default: http://localhost:8000
uv run server --reload # dev mode with hot reload

# CLI usage
uv run cli scan             # Scan news, list events (fast, 1 LLM call)
uv run cli deep <event_id>  # Deep-analyze a specific event
uv run cli analyze          # Full pipeline (scan + analyze all)
uv run cli report           # Show latest saved report
uv run cli events           # List recent events
uv run cli chain <event_id> # Show causal chain tree

# Validation harness (LLM historical test cases)
uv run python -m validation.run                          # All cases, all models
uv run python -m validation.run --model deepseek-r1:32b  # Specific model
uv run python -m validation.run --case svb --verbose     # Specific case, detailed output

# Backtesting (price action strategies)
uv run python -m validation.backtest                                # All strategies, all tickers
uv run python -m validation.backtest --tickers AAPL MSFT --horizons 5 10 20
```

## Configuration

All config via environment variables or `.env` file (see `.env.example`):
- `ALPHA_VANTAGE_API_KEY` — required for live data (news, quotes, fundamentals)
- `OLLAMA_MODEL` — default `0xroyce/plutus:latest`
- `OLLAMA_TEMPERATURE` — default `0.3` (low for structured JSON output)
- `OLLAMA_TIMEOUT` — default `1800` (30 min, these models are slow locally)
- `DB_PATH` — default `data/market_analyst.db`

- `API_HOST` — default `127.0.0.1` (localhost only; set to `0.0.0.0` for network access)
- `API_PORT` — default `8000`

Config is loaded as a singleton in `app/config.py` via `Config.from_env()`.

## Project Structure

```
app/
  analysis/
    pipeline.py       # Main analysis orchestration
                      # - run_full_analysis(): news → events → causal chains → stock picks → synthesis
                      # - analyze_stock_price_action(): per-ticker scoring + LLM narrative
                      # - analyze_stock_fundamentals(): 7-silo fundamental analysis (8 AV + 1 LLM)
                      # - _compute_trade_setup(): entry/stop/exit params for UI
                      # - scan_news(): lightweight event extraction
                      # - _build_market_snapshot(): indices, sectors, movers, macro data
    price_action.py   # Deterministic price action engine (NO LLM)
    fundamentals.py   # Standalone fundamental analysis engine (NO LLM)
                      # - 7 silos: valuation, profitability, growth, financial health,
                      #   earnings quality, ownership, dividend
                      # - Each silo: metrics + rating + score + reasons
                      # - Not connected to scoring/signaling system
                      # - Swing detection, market structure (HH/HL/LH/LL, BOS/CHoCH)
                      # - Support/resistance from swing clusters + MAs
                      # - Candlestick patterns (engulfing, pin bar, inside, doji, 3-bar patterns)
                      # - Volume analysis, gap detection, RSI divergence
                      # - 13-layer confluence scoring with academic-calibrated weights
                      # - Price momentum (3m/6m rate of change)
                      # - Market regime classification (risk-on/off/neutral)
  clients/
    alpha_vantage.py  # AV API wrapper: news sentiment, quotes, fundamentals,
                      # technicals (RSI/MACD), commodities, economic indicators,
                      # sector ETFs, market movers, treasury yields, forex,
                      # insider transactions, institutional holdings, earnings
                      # API key sanitized from error logs to prevent leakage
    ollama.py         # Ollama client + ALL prompt templates:
                      # EVENT_EXTRACTION, CAUSAL_ANALYSIS, STOCK_SELECTION,
                      # SYNTHESIS, MARKET_OVERVIEW, PRICE_ACTION_NARRATIVE,
                      # FUNDAMENTAL_ANALYSIS
                      # Also: JSON extraction with fallback parsing (fences, brace matching)
  api/
    routes.py         # FastAPI routes — all endpoints
                      # CSRF middleware requires Content-Type: application/json on POSTs
                      # Ticker validation via _validate_ticker() (regex ^[A-Za-z0-9.\-]{1,10}$)
                      # BacktestRequest validates ticker format, date format, max 30 tickers
    server.py         # Uvicorn entry point
  cli/
    main.py           # Rich CLI with scan/deep/analyze/report/events/chain/sectors
  db/
    database.py       # SQLite DAL — per-thread connections via threading.local()
                      # Tables: articles, events, causal_chains, sector_impacts,
                      # stock_picks, reports, paper_portfolio, paper_trades,
                      # paper_trade_log, scan_history, scan_history_details
                      # Auto-migration for new columns
  paper_trading/
    scanner.py        # Scans dynamic watchlist (~10 AV calls per ticker, identical
                      # inputs to Stock Analysis tab), opens long/short trades
    executor.py       # Support-based stops, trailing stops, continuous position sizing,
                      # portfolio risk budget (15% max), slippage, long+short support
                      # _trade_lock (threading.Lock) guards open_trade/close_trade against
                      # concurrent access from background poller, API, and scanner
    pre_trade.py      # News sentiment gate + earnings proximity check (blocks within 5 days)
    portfolio.py      # Portfolio summary (P&L, win rate, risk metrics)
    news_guard.py     # Defensive: closes positions when high-severity events hit sectors
    watchlist.py      # Core 10 tickers + dynamic expansion from market movers
    feedback.py       # Analyzes closed trades: per-layer accuracy, weight recommendations
  static/
    index.html        # HTML shell — panels and layout
    js/app.js         # Application logic, navigation, API calls
    js/components.js  # All render functions (stock analysis, paper trading, journal, etc.)
    js/transitions.js # Animations and scroll reveals
    js/api.js         # API client with error handling
    css/styles.css    # Dark theme styles
  config.py           # Dataclass config from env vars

validation/
  run.py              # LLM validation harness — tests against historical events
  cases.py            # Historical test cases with known outcomes
  prompts.py          # Prompt template for validation
  scorer.py           # Scores LLM output: sectors (35%), stocks (40%), chains (25%)
  llm.py              # Ollama interface for validation
  backtest.py         # Multi-strategy backtester with walk-forward analysis,
                      # regime-stratified metrics, transaction costs, equity curves
  strategies.py       # 9 strategies: confluence_score, mean_reversion, liquidity_sweep,
                      # demand_zone, wyckoff_spring, failed_breakout, wyckoff_buy_only,
                      # ensemble_buy, ensemble_strict
  metrics.py          # Forward returns, hit rates, monotonicity, equity curves,
                      # regime tagging, layer ablation, transaction costs,
                      # Sharpe/Sortino/Calmar ratios, max drawdown
  indicators.py       # Local RSI/MACD/ATR computation (no API calls)
  data_loader.py      # yfinance downloader with CSV caching (ticker/date sanitized, path traversal guard)
  data/               # Cached OHLCV CSVs (gitignored via validation/results/)

research/             # Academic evidence documents
  academic_evidence_price_action.md  # Peer-reviewed studies on each signal type
  backtesting_best_practices.md
  price_action_trading_research.md

data/
  market_analyst.db   # SQLite database (gitignored)

pyproject.toml        # Project metadata, dependencies, script entry points (uv)
uv.lock               # Lockfile for reproducible installs (committed)
.python-version       # Python version pin for uv (3.9)
```

## Key Design Decisions & Nuances

### Data flow: "AV provides the WHAT, LLM provides the WHY"

Alpha Vantage gives tickers, sentiment scores, sector ETF performance, and fundamentals. The LLM never invents ticker symbols — it reasons over data it's given. Prompts explicitly say "do NOT invent or guess ticker symbols." This is a core design principle enforced across all prompt templates in `ollama.py`.

### 12-Layer Confluence Scoring Engine (price_action.py)

The scoring engine is fully programmatic — no LLM calls. Weights are calibrated against academic evidence (documented in `research/academic_evidence_price_action.md`):

| # | Layer | Max | Evidence |
|---|-------|-----|----------|
| 1 | Weekly trend | ±3 | Dow Theory, 62.5% continuation rate |
| 2 | Daily structure | ±2 | Trend persistence, BOS/CHoCH detection |
| 3 | Key levels (S/R) | ±2 | Osler 2000, 60.8% bounce rate |
| 4 | Candlestick patterns | ±1 | Weak — Duvinage et al, barely above random |
| 5 | Volume | ±1 | Weak — Karpoff 1987, contemporaneous only |
| 6 | RSI + MACD | ±2 | RSI 81% direction; MACD below 50% alone |
| 7 | Moving averages | ±2 | Drawdown reduction value |
| 8 | Price momentum | ±3 | **Strongest** — Jegadeesh & Titman 1993, ~1%/mo alpha |
| 9 | Insider activity | ±2 | 4.8% excess 12-month returns |
| 10 | Institutional holdings | ±1 | Moderate |
| 11 | Revenue acceleration | ±1 | Moderate |
| 12 | Relative strength vs sector | ±2 | Multi-timeframe (5d + 20d) |
| | + Alignment modifier | ±2 | Weekly/daily confluence (direction-aware CHoCH) |

**Max score: 24.** Dynamic thresholds adjust buy/sell threshold based on:
- **Volume gate**: low volume (<0.8x avg) raises buy threshold
- **Market regime gate**: risk-off raises buy threshold by +2

### Paper Trading System

**Entry logic:**
- **Confluence score IS the strategy** — pattern strategies (mean reversion, liquidity sweep, wyckoff) run alongside for labeling only, they don't gate trades
- **Score says buy → we buy.** No R:R gate, no resistance blocking
- **Scanner uses identical inputs to Stock Analysis tab** (~10 AV calls per ticker: daily, weekly, RSI, MACD, earnings, insider, institutional, income, sector ETF, VIX)
- **Supports long AND short** — sell/strong_sell signals open short positions

**Stop loss:**
- **Support-based stops (long)**: stop at nearest support level below entry. If support breaks, thesis is wrong.
- **Resistance-based stops (short)**: stop at nearest resistance above entry.
- **Fallback**: ATR-based (2.5 × ATR) if no structural level found
- **Small buffer** added below/above the level (0.5 × ATR or 0.5%)

**Exit logic:**
- **Structural trailing stop** — broken resistance becomes new support (long), broken support becomes new resistance (short)
- As price breaks through each resistance level, stop ratchets up to that level (with small buffer)
- No hard take profit target — let winners run until price reverses to the last broken level
- Every trailing stop movement is logged as an event
- Fallback: ATR-based trailing if no structural levels available

**Position sizing:**
- **Continuous, proportional to score**: `score/max_score × (1% to 5% of $100K)`
- No conviction buckets — score of 15 gets bigger position than score of 8

**Pre-trade gates:**
- **Earnings proximity**: blocks trades within 5 trading days of estimated earnings (binary event risk)
- No news sentiment gate — we trust the score. No news guard — pure price action exits only.

**Risk management:**
- **Position limits**: max 20 total, max 3 per sector
- **Slippage**: 0.1% applied at both entry and exit
- **Volatility labeling**: each stock tagged as HIGH/MEDIUM/LOW vol based on ATR % of price

**Dynamic watchlist:**
- Core: AAPL, MSFT, NVDA, AMZN, GOOGL, META, JPM, UNH, XOM, TSLA
- Dynamic: up to 10 additional from AV market movers (top gainers + most active, filtered for price ≥ $10)

**Background price poller:**
- Runs every 5 minutes during US market hours (9:30 AM - 4:00 PM ET, weekdays)
- Automatically updates open positions, checks stops, closes trades
- Starts on server boot via FastAPI lifespan

**Paper trail:**
- Every trade stores a full `analysis_snapshot` JSON: all 12 layer scores + reasoning, market structure, patterns, volume, levels, regime, sector relative, direction
- Event log tracks every open, trailing stop move, and close with timestamps
- Every scan is persisted in `scan_history` + `scan_history_details` with per-ticker reasoning

**Feedback loop** (`GET /paper/feedback`):
- Analyzes closed trades to evaluate per-layer predictive accuracy
- Computes win rate when each layer is positive vs negative
- Generates plain-English recommendations for weight adjustments

### Validation Framework (Two Systems)

1. **LLM Validation** (`validation/run.py`): Tests LLM market reasoning against historical events (e.g., SVB collapse, Russia-Ukraine). Scores sector identification (35%), stock picks (40%), causal chain quality (25%). Verdict threshold: >=60% = viable, >=40% = promising, <40% = rethink.

2. **Strategy Backtesting** (`validation/backtest.py`): Runs 9 price action strategies across multi-year data for 10 tickers. Measures forward returns at 5/10/20-day horizons vs SPY benchmark. Uses yfinance (not AV) for unlimited historical data. Includes:
   - **Walk-forward analysis**: rolling IS/OOS windows, Walk-Forward Efficiency metric
   - **Regime-stratified metrics**: performance split by bull/bear × high/low volatility
   - **Transaction costs**: 15 bps round-trip deducted, tested at 1x/2x/3x
   - **Equity curves**: Sharpe, Sortino, Calmar ratios, max drawdown
   - **Layer ablation**: measures each layer's marginal contribution

### Alpha Vantage API Rate Limits

AV has strict rate limits (5 calls/min on free tier, 75/min on premium). The code handles this:
- Scanner makes ~10 calls per ticker with `SCAN_DELAY = 0.5s` between calls
- `get_full_stock_profile()` uses 5+ calls per ticker — comment warns "be mindful of rate limits"
- `get_sector_performance()` makes 11 ETF quote calls (one per sector)
- Weekly prices have split-week bar repair logic (`get_weekly_prices` in alpha_vantage.py)
- AV returns sector names in ALL CAPS — code normalizes with `.title()` for ETF map lookup

### Database Schema

SQLite with WAL mode for concurrent reads. **Per-thread connections** via `threading.local()` to avoid macOS malloc crashes with `asyncio.to_thread()`. Tables:
- `articles` — news with sentiment, deduped by URL
- `events` — LLM-extracted market events
- `causal_chains` — per-event cause→effect chains
- `sector_impacts` — per-event sector directions
- `stock_picks` — tied to events or reports
- `reports` — synthesis reports
- `paper_portfolio` — single-row portfolio state
- `paper_trades` — open/closed trades with full lifecycle, includes `direction`, `atr`, `trailing_stop_price`, `analysis_snapshot`
- `paper_trade_log` — audit trail per trade (open, trailing_stop, close events)
- `scan_history` — scan summary (count, signals, opened)
- `scan_history_details` — per-ticker detail per scan (score, layers, action, reasoning)

Auto-migration handles adding new columns to existing databases.

### BOS/CHoCH Detection (price_action.py)

**CHoCH invalidation** is critical: a CHoCH that happened before a new trend-confirming swing (HH for uptrend, LL for downtrend) is invalidated. The code checks:
- Bearish CHoCH: requires LH + LL AFTER the last HH, with no newer HH, and last low must be LL
- Bullish CHoCH: requires HH + HL AFTER the last LL, with no newer LL, and last high must be HH
- If both could fire, the more recent pivot point wins

**Alignment is direction-aware**: a bullish weekly CHoCH + daily downtrend = 0 (recovery not confirmed), NOT -2. Only bearish weekly CHoCH + daily downtrend = -2 (breakdown confirmed).

### Fundamental Analysis Engine (fundamentals.py)

Fundamental analysis is **completely standalone** — not connected to price action scoring, not used in paper trading, not gated by any confluence layer.

**Pipeline**: 8 AV calls (overview, income statement, balance sheet, cash flow, earnings, insider transactions, institutional holdings, quote) + 1 LLM call for narrative.

**7 silos**, each with metrics + rating + score + reasons:
1. **Valuation** — P/E, Forward P/E, PEG, P/S, P/B, EV/EBITDA, analyst ratings/target
2. **Profitability** — Gross/operating/net margins, ROE, ROA, quarterly margin trends
3. **Growth** — Revenue YoY, EPS YoY, revenue acceleration/deceleration
4. **Financial Health** — D/E, current ratio, interest coverage, FCF, net cash/debt
5. **Earnings Quality** — Beat rate (last 8 quarters), avg surprise %, consistency
6. **Ownership** — Insider buys/sells, institutional top holders
7. **Dividend** — Yield, payout ratio, FCF coverage

`get_company_overview()` returns extended fields for fundamentals: `price_to_book`, `price_to_sales`, `ev_to_ebitda`, `peg_ratio`, `roe`, `roa`, `operating_margin`, `analyst_target_price`, `analyst_strong_buy/buy/hold/sell/strong_sell`, `shares_outstanding`. These fields are used only by fundamentals, not by the scoring engine.

### FastAPI Async Pattern

Long-running operations (paper scan, backtest) use `asyncio.to_thread()` to avoid blocking the event loop. The paper scan takes 5-10 minutes for the full watchlist (~10 AV calls per ticker). A background price poller runs every 5 minutes during market hours via FastAPI lifespan. A `threading.Lock` (`_trade_lock` in `executor.py`) guards `open_trade()` and `close_trade()` against concurrent access from the poller, scanner, and API endpoints.

**Security middleware**: A CSRF guard middleware rejects POST requests without `Content-Type: application/json`, preventing cross-origin form submissions. Error responses use generic messages (full traces logged server-side only). Server binds to `127.0.0.1` by default.

### Price Data Conventions

- Price data from AV comes **descending** (newest first) — code reverses to ascending for the engine
- All price action analysis expects **ascending** (oldest first) order
- Scanner uses `compact=False` (full daily history) to ensure MA200 computes correctly
- Display window = last 252 bars; full buffer = 452 bars (200 extra for MA200 warmup)
- Weekly data: last ~4 years (200 bars) for weekly analysis

### LLM JSON Parsing

`ollama.py._extract_json()` has 3-stage fallback:
1. Direct `json.loads()` on full response
2. Code fence extraction (```json ... ```)
3. Brace-matching (finds first `{`, counts depth to matching `}`)

This is critical because local models often wrap JSON in explanation text.

## UI Tabs

| Tab | Description |
|-----|-------------|
| Market | Market overview — raw data + AI-generated briefing with regime classification |
| Analysis | Full pipeline — news scan → events → causal chains → synthesis report |
| Stock | Per-ticker analysis — Price Action (confluence score, trade setup, charts) + Fundamentals (7-silo analysis, metrics, LLM narrative) |
| Backtest | Multi-strategy backtester with regime and walk-forward analysis |
| Paper Trading | Portfolio, open/closed positions, scan watchlist (with per-ticker reasoning), scan history |
| Journal | Trade journal — click any trade to see full analysis snapshot, layer scores, event log |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Serve UI |
| GET | `/health` | Health check (Ollama + DB) |
| POST | `/scan` | Scan news, extract events (fast) |
| POST | `/events/{id}/analyze` | Deep-analyze a scanned event |
| POST | `/analyze` | Full pipeline (scan + analyze + synthesize) |
| GET | `/report` | Latest synthesis report |
| GET | `/events` | Recent events with chains/impacts/picks |
| GET | `/events/{id}` | Single event detail |
| GET | `/events/{id}/chain` | Causal chain for event |
| GET | `/events/{id}/articles` | Source articles for event |
| GET | `/news` | Events with their source articles |
| GET | `/market` | Raw market snapshot (no LLM) |
| POST | `/market/analyze` | LLM-powered market overview |
| GET | `/stock/{ticker}/price-action` | Per-ticker confluence analysis + narrative + trade setup |
| GET | `/stock/{ticker}/fundamentals` | Standalone fundamental analysis — 7 silos + LLM narrative |
| POST | `/backtest` | Multi-strategy backtester |
| GET | `/search/tickers` | Ticker symbol search |
| GET | `/paper/portfolio` | Paper trading portfolio summary (incl. risk metrics) |
| GET | `/paper/trades` | Paper trades (filter by status) |
| GET | `/paper/trades/{id}` | Single trade with log + analysis snapshot |
| POST | `/paper/scan` | Scan watchlist, open trades (long-running) |
| POST | `/paper/update` | Update open positions, check stops/trailing |
| POST | `/paper/trades/{id}/close` | Manual close at market price |
| POST | `/paper/news-guard` | Defensive scan, close affected positions |
| GET | `/paper/feedback` | Analyze closed trades, layer accuracy, recommendations |
| GET | `/paper/scans` | Scan history list |
| GET | `/paper/scans/{id}` | Single scan with per-ticker details |
| POST | `/paper/reset` | Reset portfolio to $100K |
| GET | `/sectors` | Sector outlook from latest report |

## Change Protocol — MANDATORY

Every code change MUST follow this protocol. No exceptions.

### 1. Understand Before Touching

- **Read all relevant code first.** Before changing a function, read the function, its callers, and anything it calls. Trace the data flow end-to-end.
- **Understand the ask fully.** Restate what the user wants in your own words before writing code. If the request is ambiguous, ask — don't guess.
- **Map the blast radius.** Identify every file, function, and data path affected by the change. This codebase is tightly coupled — `pipeline.py` calls `price_action.py`, `ollama.py`, `alpha_vantage.py`, and `database.py`. A change in one often ripples to others.

### 2. Verify the Change Works

- **Run the code** after making changes. Don't just write it and move on. If it's a function change, call it. If it's an API route, hit it. If it's a CLI command, run it.
- **Check the actual output.** Don't assume correctness from the absence of errors. Verify that the output matches what was intended — correct values, correct format, correct behavior.
- **Test edge cases** relevant to the change. Null/empty inputs, missing API keys, missing data, zero-division scenarios — this codebase deals with live financial data that can be incomplete or malformed.
- **UI changes must be visually verified.** Use Puppeteer (MCP tools: `puppeteer_navigate`, `puppeteer_click`, `puppeteer_fill`, `puppeteer_evaluate`, `puppeteer_screenshot`) to navigate to `http://localhost:8000`, interact with the UI, and take screenshots to confirm the change renders correctly. Don't assume HTML/JS changes work — render them and look. Check for: broken layouts, raw JSON leaking into display, missing data, JS errors preventing rendering. **Always close the Chromium instance after testing** by running `pkill -f Chromium` — Puppeteer leaves headless browsers running otherwise.

### 3. Verify Nothing Broke

- **Check callers and dependents.** If you changed a function's signature, return type, or behavior, find every caller and confirm they still work. Use grep — don't rely on memory.
- **Check the data flow.** Changes in `price_action.py` affect `pipeline.py`, which affects `routes.py` and `cli/main.py`. Changes in `database.py` affect everything that reads/writes trades, events, or reports. Changes in `executor.py` affect `scanner.py` and `portfolio.py`.
- **Check the database.** If you added/renamed columns, verify the migration logic in `database.py._init_tables()` handles existing databases. SQLite ALTER TABLE is limited — you can only ADD columns, not rename or remove them.
- **Don't break the JSON contract.** The API returns JSON consumed by `js/components.js`. The LLM prompts in `ollama.py` expect specific JSON response schemas. The scorer in `validation/scorer.py` expects specific prediction formats. Changing any of these structures is a breaking change across multiple consumers.

### 4. Think Holistically

- **Scanner and Stock Analysis must agree.** Both call `compute_confluence_score()` with identical inputs (~10 AV calls each). If you add a new data source to one, add it to both. The scanner uses `compact=False` for daily data to match the pipeline.
- **Consider the paper trading lifecycle.** Changes to scoring affect what trades get opened. Changes to levels affect stop placement. Changes to the executor affect P&L calculation. All of these feed into `portfolio.py` summary stats.
- **Consider the validation framework.** If you change how strategies work in `price_action.py` or `strategies.py`, the backtester results will change. The strategies in `validation/strategies.py` are also imported by `scanner.py` for pattern labeling.
- **Consider AV rate limits.** The scanner makes ~10 AV calls per ticker. With 10-20 tickers, that's 100-200 calls per scan. Rate limits matter.

## Context Management — Best Practices

This codebase is large (~6000+ lines of Python across 20+ files). Manage context carefully.

### Use Sub-Agents

- **Delegate research and exploration to sub-agents.** When you need to search across multiple files, understand a data flow, or investigate how something works — spawn a sub-agent instead of reading everything into the main conversation.
- **Parallelize independent work.** If you need to check callers in `pipeline.py` AND verify the database schema AND read test cases — launch multiple agents simultaneously, don't do it sequentially.
- **Use sub-agents for verification.** After making a change, spawn an agent to grep for all callers, check for breakage, or run tests — keeps the main context focused on the task.

### Be Surgical With Reads

- **Don't read entire large files.** `pipeline.py` and `price_action.py` are too big to read fully. Use `offset`/`limit` to read specific sections, or grep for the function you need.
- **Read only what the task requires.** If fixing a bug in the scanner, you don't need to read the validation framework. If changing a prompt, you don't need to read the database layer.
- **Use grep before read.** Find the exact line/function first, then read just that section with context.

### Key File Relationships (to avoid unnecessary exploration)

These are the hot paths — know them so you don't have to re-discover them:
- **Scoring**: `price_action.py:compute_confluence_score()` → called by `pipeline.py:analyze_stock_price_action()` AND `scanner.py:_analyze()`
- **Trading**: `scanner.py:run_scan()` → `pre_trade.py:analyze_pre_trade()` → `executor.py:open_trade()`
- **Closing**: `executor.py:update_open_positions()` checks trailing stop → `close_trade()`
- **API layer**: `routes.py` → `pipeline.py` functions → `alpha_vantage.py` + `ollama.py`
- **Prompts**: ALL prompt templates live in `ollama.py`, not scattered across files
- **UI rendering**: `js/components.js` has all render functions; `js/app.js` has logic and API calls
- **Sector ETF lookup**: AV returns sectors in ALL CAPS; code normalizes with `.title()` — both `pipeline.py` and `scanner.py` have their own `_sector_etf_map`

## Development Notes

- Package management uses `uv` — run `uv sync` to install, `uv run` to execute. The `uv.lock` lockfile is committed for reproducibility. Dependencies live in `pyproject.toml`, not `requirements.txt`.
- Never commit `.env` — it contains the Alpha Vantage API key
- `data/`, `validation/results/`, and `.venv/` are gitignored
- The Ollama timeout is 30 minutes because local models can take several minutes per inference
- VIXY is used as a VIX proxy in market overview — its dollar price is meaningless, only the % change matters (this is called out in the MARKET_OVERVIEW_PROMPT)
- Sector performance uses ETF proxies (XLK, XLV, XLF, etc.) because the AV SECTOR endpoint is deprecated
- SQLite uses per-thread connections via `threading.local()` — do NOT use a singleton connection (causes malloc crashes on macOS with asyncio.to_thread)
- Scanner uses `compact=False` for daily prices — `compact=True` only returns 100 bars, not enough for MA200
- Server binds to `127.0.0.1` by default — set `API_HOST=0.0.0.0` to expose on the network (no authentication layer exists)
- Ticker inputs are validated via regex (`^[A-Za-z0-9.\-]{1,10}$`) in routes and data_loader to prevent path traversal
- Error responses to clients use generic messages — never expose `str(e)` which may leak file paths or API keys
- `executor.py` uses `_trade_lock` to prevent TOCTOU races between the background poller, scanner, and manual API calls
