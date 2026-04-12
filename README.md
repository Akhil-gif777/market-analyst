# Market Analyst

AI-powered market analysis system that combines real-time financial data with local LLM reasoning to produce actionable market insights, price action analysis, and automated paper trading.

All analysis runs locally — no data leaves your machine. The LLM (via Ollama) provides reasoning and narrative; Alpha Vantage provides the market data.

## Features

### Market Overview
> Real-time market snapshot with AI-generated briefing and regime classification

- Indices, sectors, movers, yields, forex, crypto — all in one view
- LLM-powered narrative that reads the macro picture and classifies the current regime
- Sector ETF performance across 11 sectors

---

### Price Action Analysis
> 12-layer confluence scoring engine calibrated against academic research

- Multi-timeframe: weekly trend + daily structure
- Market structure detection — HH/HL/LH/LL, BOS/CHoCH with invalidation logic
- Support/resistance from swing clusters + moving averages
- Candlestick patterns, volume analysis, RSI divergence, gap detection
- Momentum, insider activity, institutional holdings, revenue acceleration
- **The LLM explains the score — it doesn't decide it**

---

### Fundamental Analysis
> Standalone 7-silo analysis, independent from price action scoring

| Silo | What it covers |
|------|---------------|
| Valuation | P/E, PEG, P/S, P/B, EV/EBITDA, analyst targets |
| Profitability | Margins, ROE, ROA, quarterly trends |
| Growth | Revenue/EPS YoY, acceleration/deceleration |
| Financial Health | D/E, current ratio, FCF, net cash/debt |
| Earnings Quality | Beat rate, surprise %, consistency |
| Ownership | Insider buys/sells, institutional holders |
| Dividend | Yield, payout ratio, FCF coverage |

---

### Paper Trading
> Automated long/short system with structural stop management

- Scans a dynamic watchlist using the same 12-layer scoring engine
- Support-based stops (long) / resistance-based stops (short), ATR fallback
- Structural trailing stops — broken resistance becomes new support
- Continuous position sizing proportional to score
- Earnings proximity gate blocks trades within 5 days of earnings
- Full trade lifecycle with analysis snapshots and event logs

---

### Strategy Backtesting
> Walk-forward analysis across 9 strategies with regime stratification

- 9 strategies: confluence score, mean reversion, liquidity sweep, demand zone, Wyckoff, and more
- Walk-forward efficiency with rolling in-sample / out-of-sample windows
- Regime-stratified metrics: bull/bear x high/low volatility
- Transaction costs, equity curves, Sharpe/Sortino/Calmar ratios
- Layer ablation — measure each layer's marginal contribution

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
