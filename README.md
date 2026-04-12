# Market Analyst

AI-powered market analysis system that combines real-time financial data with local LLM reasoning to produce actionable market insights, price action analysis, and automated paper trading.

All analysis runs locally — no data leaves your machine. The LLM (via Ollama) provides reasoning and narrative; Alpha Vantage provides the market data.

## Features

**Market Overview** — Real-time market snapshot (indices, sectors, movers, yields, forex, crypto) with AI-generated briefing and regime classification.

**Price Action Analysis** — Multi-timeframe confluence scoring engine with 12 layers calibrated against academic research. Swing detection, market structure (HH/HL/LH/LL, BOS/CHoCH), support/resistance, candlestick patterns, volume, momentum, and more. The LLM explains the score — it doesn't decide it.

**Fundamental Analysis** — Standalone 7-silo analysis: valuation, profitability, growth, financial health, earnings quality, ownership, and dividends. Independent from price action scoring.

**Paper Trading** — Automated system that scans a watchlist using the same scoring engine, opens long/short positions, manages support-based stops with structural trailing exits, and tracks full trade lifecycle with analysis snapshots.

**Strategy Backtesting** — Walk-forward analysis with regime stratification, transaction costs, equity curves, and layer ablation across 9 strategies and configurable date ranges.

## Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/) (Python package manager)
- [Ollama](https://ollama.ai/) with a pulled model
- [Alpha Vantage API key](https://www.alphavantage.co/support/#api-key) (free tier works, premium recommended)

## Quick Start

```bash
# Clone and install
git clone <repo-url>
cd market-analyst
uv sync

# Set up environment
cp .env.example .env
# Edit .env and add your ALPHA_VANTAGE_API_KEY

# Start Ollama (separate terminal)
ollama serve
ollama pull 0xroyce/plutus

# Start the app
uv run server --reload
# Open http://localhost:8000
```

## Usage

### Web UI

```bash
uv run server          # http://localhost:8000
uv run server --reload # dev mode with hot reload
```

The UI has 6 tabs:

| Tab | Description |
|-----|-------------|
| Market | Market overview with AI-generated briefing |
| Analysis | Full pipeline: news scan, events, causal chains, synthesis report |
| Stock | Price Action analysis + Fundamental analysis (two buttons, same ticker input) |
| Backtest | Multi-strategy backtester with regime and walk-forward analysis |
| Paper Trading | Portfolio, scan watchlist, manage positions, scan history |
| Journal | Trade journal with full analysis snapshots per trade |

### CLI

```bash
uv run cli scan             # Scan news, list events
uv run cli analyze          # Full pipeline
uv run cli report           # Show latest report
uv run cli events           # List recent events
uv run cli chain <event_id> # Show causal chain
```

### Backtesting

```bash
uv run python -m validation.backtest
uv run python -m validation.backtest --tickers AAPL MSFT --horizons 5 10 20
```

## Configuration

All config via environment variables or `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `ALPHA_VANTAGE_API_KEY` | (required) | API key for market data |
| `OLLAMA_MODEL` | `0xroyce/plutus:latest` | LLM model for analysis |
| `OLLAMA_TEMPERATURE` | `0.3` | Low for structured JSON output |
| `OLLAMA_TIMEOUT` | `1800` | 30 min (local models can be slow) |
| `DB_PATH` | `data/market_analyst.db` | SQLite database path |
| `API_HOST` | `0.0.0.0` | Server bind address |
| `API_PORT` | `8000` | Server port |

## Project Structure

```
app/
  analysis/
    pipeline.py         # Analysis orchestration
    price_action.py     # 12-layer confluence scoring engine
    fundamentals.py     # 7-silo fundamental analysis
  clients/
    alpha_vantage.py    # AV API wrapper
    ollama.py           # LLM client + prompt templates
  api/
    routes.py           # FastAPI endpoints
    server.py           # Uvicorn entry point
  cli/
    main.py             # Rich CLI
  db/
    database.py         # SQLite DAL
  paper_trading/
    scanner.py          # Watchlist scanner
    executor.py         # Position management
    portfolio.py        # Portfolio summary
    feedback.py         # Trade feedback loop
  static/               # Web UI (HTML/JS/CSS)

validation/
  backtest.py           # Multi-strategy backtester
  strategies.py         # 9 trading strategies
  run.py                # LLM validation harness
```

## License

Private project.
