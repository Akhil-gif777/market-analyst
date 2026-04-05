# UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the Market Analyst UI from a 3059-line single-file HTML into a split-file modern fintech aesthetic with spring animations, skeleton loaders, progress bars, and gradient accents.

**Architecture:** Split `app/static/index.html` into 4 JS modules (`api.js`, `transitions.js`, `components.js`, `app.js`), 1 CSS file (`styles.css`), and a slim HTML shell. Use `motion` library via CDN for spring-based animations. All JS uses ES module syntax with window-attached functions for HTML event handlers. No backend changes.

**Tech Stack:** Vanilla JS (ES modules), CSS custom properties, `motion` (CDN ~15KB), `lightweight-charts@4` (CDN, existing)

---

## File Map

```
app/static/
  index.html           # REWRITE: slim HTML shell, no inline styles/scripts
  css/
    styles.css          # NEW: all styles (~900 lines)
  js/
    api.js              # NEW: centralized fetch layer (~50 lines)
    transitions.js      # NEW: motion wrappers, number counters, scroll reveals (~150 lines)
    components.js       # NEW: render functions, skeletons, toasts (~1100 lines)
    app.js              # NEW: state, routing, panel logic, event wiring, init (~700 lines)
```

**Existing file disposition:**
- `app/static/index.html` — overwritten with new slim shell
- `app/api/routes.py` — no changes (already mounts `/static`)

---

### Task 1: Create directory structure and HTML shell

**Files:**
- Create: `app/static/css/` (directory)
- Create: `app/static/js/` (directory)
- Rewrite: `app/static/index.html`

- [ ] **Step 1: Create directories**

```bash
mkdir -p app/static/css app/static/js
```

- [ ] **Step 2: Write the HTML shell**

Write `app/static/index.html`. This is a slim structural shell — no inline styles, no inline scripts. All styles come from `css/styles.css`, all JS from `js/app.js` (which imports the others).

Key changes from old HTML:
- Remove all `<style>` (moved to styles.css)
- Remove all `<script>` (moved to JS modules)
- Remove inline `style="..."` attributes (replaced with CSS classes)
- Remove inline `onclick="..."` (wired up in app.js via data attributes or window-attached functions)
- Add top progress bar element
- Add toast container element
- Simplify nav to use `data-panel` attributes
- Keep all panel `id="panel-*"` structure for backward compatibility
- Load `motion` and `lightweight-charts` via CDN `<script>` tags before `app.js`

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Market Analyst</title>
<link rel="stylesheet" href="/static/css/styles.css">
</head>
<body>

<!-- Top progress bar (fixed, hidden by default) -->
<div id="progress-bar" class="progress-bar">
  <div class="progress-bar-fill"></div>
</div>

<div class="app">

<header>
  <div class="logo">
    <span class="logo-dot"></span>
    <h1><span class="logo-highlight">Market</span> Analyst</h1>
  </div>
  <span id="health-badge" class="health-badge">checking...</span>
</header>

<nav id="main-nav" class="tab-bar">
  <div class="tab-bar-inner">
    <button class="tab" data-panel="market">Market</button>
    <button class="tab" data-panel="analyze">Analysis</button>
    <button class="tab" data-panel="stock-analysis">Stock</button>
    <button class="tab" data-panel="backtest">Backtest</button>
    <button class="tab" data-panel="paper-trading">Paper Trading</button>
    <button class="tab" data-panel="trade-journal">Journal</button>
  </div>
  <div class="tab-indicator" id="tab-indicator"></div>
</nav>

<!-- Market Overview Panel -->
<div id="panel-market" class="panel">
  <div class="panel-header">
    <h2 class="panel-title">Market Overview</h2>
    <div class="panel-actions">
      <button class="btn btn-secondary" onclick="loadMarket()">Load Market Data</button>
      <button class="btn btn-primary" onclick="runMarketOverview()" id="btn-market-overview">Generate AI Overview</button>
    </div>
  </div>
  <div id="market-overview-content"></div>
  <div id="market-content"></div>
</div>

<!-- Scan Panel (hidden from nav, accessed via Events) -->
<div id="panel-scan" class="panel">
  <div class="panel-header">
    <h2 class="panel-title">Scan News for Market-Moving Events</h2>
  </div>
  <p class="panel-desc">Fetches latest news from Alpha Vantage and uses LLM to extract market-moving events.</p>
  <button onclick="runScan()" id="btn-scan" class="btn btn-primary">Run Scan</button>
  <div id="scan-result"></div>
</div>

<!-- Events Panel -->
<div id="panel-events" class="panel">
  <div class="panel-header">
    <h2 class="panel-title">Recent Events</h2>
    <div class="panel-actions">
      <button class="btn btn-secondary" onclick="loadEvents()">Load Events</button>
    </div>
  </div>
  <div id="events-content"></div>
</div>

<!-- News Panel -->
<div id="panel-news" class="panel">
  <div class="panel-header">
    <h2 class="panel-title">News by Event</h2>
    <div class="panel-actions">
      <button class="btn btn-secondary" onclick="loadNews()">Load News</button>
    </div>
  </div>
  <div id="news-content"></div>
</div>

<!-- Event Detail Panel -->
<div id="panel-event-detail" class="panel">
  <div id="event-detail-content"></div>
</div>

<!-- Report Panel -->
<div id="panel-report" class="panel">
  <div class="panel-header">
    <h2 class="panel-title">Latest Analysis Report</h2>
    <div class="panel-actions">
      <button class="btn btn-secondary" onclick="loadReport()">Load Report</button>
    </div>
  </div>
  <div id="report-content"></div>
</div>

<!-- Sectors Panel -->
<div id="panel-sectors" class="panel">
  <div class="panel-header">
    <h2 class="panel-title">Sector Outlook</h2>
    <div class="panel-actions">
      <button class="btn btn-secondary" onclick="loadSectors()">Load Sectors</button>
    </div>
  </div>
  <div id="sectors-content"></div>
</div>

<!-- Stock Analysis Panel -->
<div id="panel-stock-analysis" class="panel">
  <div class="panel-header">
    <h2 class="panel-title">Stock Price Action Analysis</h2>
  </div>
  <div class="stock-search-bar">
    <input type="text" id="stock-ticker-input" placeholder="Enter ticker (e.g. AAPL)"
           class="input input-ticker" onkeydown="if(event.key==='Enter') runStockAnalysis()">
    <button onclick="runStockAnalysis()" id="btn-stock-analyze" class="btn btn-primary">Analyze</button>
  </div>
  <p class="panel-desc">Multi-timeframe price action analysis with confluence scoring. Uses 6 Alpha Vantage calls + 1 LLM call.</p>
  <div id="stock-analysis-content"></div>
</div>

<!-- Full Analysis Panel -->
<div id="panel-analyze" class="panel">
  <div class="panel-header">
    <h2 class="panel-title">Full Market Analysis</h2>
  </div>
  <p class="panel-desc">Runs the complete pipeline: fetch news, extract events, build causal chains, evaluate stocks per event, and synthesize a holistic report.</p>
  <div class="analysis-controls">
    <button onclick="runFullAnalysis()" id="btn-analyze" class="btn btn-primary">Run Full Analysis</button>
    <label class="select-label">
      Max events:
      <select id="max-events" class="input input-select">
        <option value="3">3 (quick)</option>
        <option value="5" selected>5 (default)</option>
        <option value="10">10 (thorough)</option>
      </select>
    </label>
  </div>
  <div id="analyze-content"></div>
</div>

<!-- Backtest Panel -->
<div id="panel-backtest" class="panel">
  <div class="panel-header">
    <h2 class="panel-title">Strategy Backtest</h2>
  </div>
  <div class="bt-config">
    <div class="bt-field">
      <label>Tickers</label>
      <div class="bt-ticker-wrap-container">
        <div class="bt-ticker-wrap" onclick="document.getElementById('bt-ticker-input').focus()">
          <div id="bt-ticker-tags"></div>
          <input type="text" id="bt-ticker-input" placeholder="Add ticker..." autocomplete="off" spellcheck="false" class="input">
        </div>
        <div id="bt-autocomplete" class="bt-autocomplete"></div>
      </div>
    </div>
    <div class="bt-field">
      <label>Date Range</label>
      <div class="bt-date-row">
        <input type="date" id="bt-start" value="2019-01-01" class="input">
        <span>to</span>
        <input type="date" id="bt-end" value="2025-12-31" class="input">
      </div>
    </div>
    <div class="bt-field">
      <label>Strategies</label>
      <div class="bt-checkboxes">
        <label><input type="checkbox" class="bt-strat-check" value="mean_reversion" checked> Mean Reversion</label>
        <label><input type="checkbox" class="bt-strat-check" value="liquidity_sweep" checked> Liquidity Sweep</label>
        <label><input type="checkbox" class="bt-strat-check" value="wyckoff_buy_only" checked> Wyckoff (Buy Only)</label>
        <label><input type="checkbox" class="bt-strat-check" value="ensemble_buy" checked> Ensemble (3 Strategies)</label>
        <label><input type="checkbox" class="bt-strat-check" value="ensemble_strict"> Ensemble Strict (2+ Agree)</label>
        <label><input type="checkbox" class="bt-strat-check" value="confluence_score"> Confluence Score (Baseline)</label>
        <label><input type="checkbox" class="bt-strat-check" value="failed_breakout"> Failed Breakout</label>
      </div>
    </div>
    <div class="bt-field">
      <label>Horizons</label>
      <div class="bt-horizon-row">
        <label><input type="checkbox" class="bt-horizon-check" value="5" checked> 5d</label>
        <label><input type="checkbox" class="bt-horizon-check" value="10" checked> 10d</label>
        <label><input type="checkbox" class="bt-horizon-check" value="20" checked> 20d</label>
      </div>
    </div>
    <button onclick="runBacktest()" id="btn-backtest" class="btn btn-primary btn-run">Run Backtest</button>
  </div>
  <div id="bt-results"></div>
</div>

<!-- Paper Trading Panel -->
<div id="panel-paper-trading" class="panel">
  <div class="panel-header">
    <h2 class="panel-title">Paper Trading</h2>
  </div>
  <div id="pt-content">
    <div class="stat-cards" id="pt-summary-cards">
      <div class="stat-card stat-card-primary"><div class="stat-card-label">Total Value</div><div class="stat-card-value" id="pt-total-value">&#8212;</div></div>
      <div class="stat-card"><div class="stat-card-label">Cash</div><div class="stat-card-value" id="pt-cash">&#8212;</div></div>
      <div class="stat-card"><div class="stat-card-label">Invested</div><div class="stat-card-value" id="pt-invested">&#8212;</div></div>
      <div class="stat-card"><div class="stat-card-label">Total P&amp;L</div><div class="stat-card-value" id="pt-total-pnl">&#8212;</div></div>
      <div class="stat-card"><div class="stat-card-label">Return</div><div class="stat-card-value" id="pt-return">&#8212;</div></div>
      <div class="stat-card"><div class="stat-card-label">Win Rate</div><div class="stat-card-value" id="pt-winrate">&#8212;</div></div>
      <div class="stat-card"><div class="stat-card-label">Open</div><div class="stat-card-value" id="pt-open-count">&#8212;</div></div>
      <div class="stat-card"><div class="stat-card-label">Closed</div><div class="stat-card-value" id="pt-closed-count">&#8212;</div></div>
    </div>
    <div class="pt-actions">
      <button class="btn btn-secondary" onclick="ptLoad()">Load Portfolio</button>
      <button class="btn btn-primary" onclick="ptScan()" id="btn-pt-scan">Scan Watchlist</button>
      <button class="btn btn-secondary" onclick="ptUpdate()" id="btn-pt-update">Update Prices</button>
      <button class="btn btn-secondary" onclick="ptNewsGuard()" id="btn-pt-news">Check News</button>
      <button class="btn btn-danger" onclick="ptReset()" style="margin-left:auto">Reset Portfolio</button>
    </div>
    <div id="pt-scan-status" class="operation-status" style="display:none"></div>
    <div class="section-label">Open Positions (<span id="pt-open-badge">0</span>)</div>
    <div class="table-wrap">
      <table class="data-table">
        <thead><tr>
          <th>Ticker</th><th>Strategy</th><th>Conviction</th><th>Sector</th>
          <th>Entry</th><th>Current</th><th>Trail Stop</th><th>Target</th>
          <th>Unrealized P&amp;L</th><th>Days</th><th></th>
        </tr></thead>
        <tbody id="pt-open-tbody"></tbody>
      </table>
    </div>
    <div class="section-label">Closed Trades (<span id="pt-closed-badge">0</span>)</div>
    <div class="table-wrap">
      <table class="data-table">
        <thead><tr>
          <th>Ticker</th><th>Strategy</th><th>Conviction</th><th>Sector</th>
          <th>Entry</th><th>Exit</th><th>Realized P&amp;L</th><th>Days</th><th>Reason</th>
        </tr></thead>
        <tbody id="pt-closed-tbody"></tbody>
      </table>
    </div>
  </div>
</div>

<!-- Trade Journal Panel -->
<div id="panel-trade-journal" class="panel">
  <div class="panel-header">
    <h2 class="panel-title">Trade Journal</h2>
  </div>
  <div id="tj-content">
    <div class="stat-cards" id="tj-stats"></div>
    <div class="filter-bar">
      <button class="filter-btn active" data-filter="all">All</button>
      <button class="filter-btn" data-filter="open">Open</button>
      <button class="filter-btn" data-filter="closed">Closed</button>
      <button class="filter-btn" data-filter="wins">Wins</button>
      <button class="filter-btn" data-filter="losses">Losses</button>
    </div>
    <div id="tj-list"></div>
  </div>
</div>

</div><!-- .app -->

<!-- Toast container -->
<div id="toast-container" class="toast-container"></div>

<script src="https://cdn.jsdelivr.net/npm/lightweight-charts@4/dist/lightweight-charts.standalone.production.js"></script>
<script src="https://cdn.jsdelivr.net/npm/motion@11.18/dist/motion.js"></script>
<script type="module" src="/static/js/app.js"></script>
</body>
</html>
```

**Notes on motion CDN:** The `motion` library v11+ provides a global `Motion` object when loaded via script tag. Key APIs: `Motion.animate()`, `Motion.spring()`, `Motion.stagger()`, `Motion.inView()`. If the CDN URL doesn't resolve at implementation time, check https://www.npmjs.com/package/motion for the latest version and CDN path. Fallback: use `https://unpkg.com/motion/dist/motion.js`.

- [ ] **Step 3: Commit**

```bash
git add app/static/index.html app/static/css/ app/static/js/
git commit -m "feat(ui): create HTML shell and directory structure for UI redesign"
```

---

### Task 2: Write the CSS design system

**Files:**
- Create: `app/static/css/styles.css`

This single CSS file contains everything: design tokens, reset, layout, typography, all component styles, animations, and responsive breakpoints. Organized into clearly commented sections.

- [ ] **Step 1: Write styles.css**

Write `app/static/css/styles.css` with these sections (in order):

**Section 1 — Design Tokens (`:root`)**
```css
:root {
  --bg: #0a0e17;
  --surface: #111827;
  --surface-2: #1a2234;
  --border: #1e293b;
  --text: #e2e8f0;
  --text-dim: #64748b;
  --accent: #6366f1;
  --accent-glow: rgba(99, 102, 241, 0.15);
  --green: #22c55e;
  --red: #ef4444;
  --yellow: #eab308;
  --gradient: linear-gradient(135deg, #6366f1, #8b5cf6);
  --shadow-sm: 0 1px 3px rgba(0, 0, 0, 0.3);
  --shadow-md: 0 4px 12px rgba(0, 0, 0, 0.4);
  --shadow-lg: 0 8px 24px rgba(0, 0, 0, 0.5);
  --radius: 12px;
  --radius-sm: 8px;
  --radius-xs: 6px;
  --transition: 150ms ease;
}
```

**Section 2 — Reset & Base**
```css
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Inter', Helvetica, Arial, sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
}
.app { max-width: 1400px; margin: 0 auto; padding: 32px; }
```

**Section 3 — Header**
- Logo with gradient pulse dot (animated `@keyframes pulse`)
- Health badge with glow on `.ok` state
```css
header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 0; margin-bottom: 8px;
}
.logo { display: flex; align-items: center; gap: 12px; }
.logo h1 { font-size: 22px; font-weight: 700; letter-spacing: -0.5px; }
.logo-highlight { background: var(--gradient); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.logo-dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: var(--gradient); box-shadow: 0 0 8px var(--accent);
  animation: pulse 2s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; box-shadow: 0 0 8px var(--accent); }
  50% { opacity: 0.5; box-shadow: 0 0 16px var(--accent); }
}
.health-badge {
  font-size: 12px; padding: 5px 14px; border-radius: 20px;
  background: var(--surface); border: 1px solid var(--border);
  transition: all var(--transition);
}
.health-badge.ok { border-color: var(--green); color: var(--green); box-shadow: 0 0 8px rgba(34, 197, 94, 0.2); }
.health-badge.degraded { border-color: var(--yellow); color: var(--yellow); }
.health-badge.error { border-color: var(--red); color: var(--red); }
```

**Section 4 — Tab Bar Navigation**
- Horizontal tabs with sliding gradient underline
- Tab indicator is absolutely positioned, animated via JS (motion library)
```css
.tab-bar {
  position: relative; margin-bottom: 28px;
  border-bottom: 1px solid var(--border);
}
.tab-bar-inner { display: flex; gap: 4px; }
.tab {
  padding: 12px 20px; border: none; background: none;
  color: var(--text-dim); font-size: 14px; font-weight: 500;
  cursor: pointer; transition: color 200ms ease;
  position: relative; white-space: nowrap;
}
.tab:hover { color: var(--text); background: var(--accent-glow); border-radius: var(--radius-xs) var(--radius-xs) 0 0; }
.tab.active { color: var(--text); }
.tab-indicator {
  position: absolute; bottom: -1px; height: 2px;
  background: var(--gradient); border-radius: 1px;
  transition: left 0.3s cubic-bezier(0.4, 0, 0.2, 1), width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
```

**Section 5 — Panels**
```css
.panel { display: none; min-height: 200px; }
.panel.active {
  display: block;
  animation: panelIn 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
@keyframes panelIn {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}
.panel-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 20px; flex-wrap: wrap; gap: 12px;
}
.panel-title { font-size: 18px; font-weight: 700; }
.panel-actions { display: flex; gap: 8px; }
.panel-desc { color: var(--text-dim); font-size: 13px; margin-bottom: 16px; }
```

**Section 6 — Buttons**
```css
.btn {
  padding: 8px 20px; border-radius: var(--radius-xs); border: 1px solid var(--border);
  background: var(--surface); color: var(--text); cursor: pointer;
  font-size: 13px; font-weight: 500; transition: all var(--transition);
  position: relative; overflow: hidden;
}
.btn:hover { transform: scale(1.02); border-color: var(--accent); color: var(--accent); }
.btn:active { transform: scale(0.97); }
.btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }

.btn-primary {
  background: var(--gradient); border-color: transparent; color: #fff; font-weight: 600;
}
.btn-primary:hover { box-shadow: 0 0 20px var(--accent-glow); transform: scale(1.02); color: #fff; border-color: transparent; }
.btn-primary::after {
  content: ''; position: absolute; top: 0; left: -100%; width: 100%; height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,0.15), transparent);
  transition: left 0.5s;
}
.btn-primary:hover::after { left: 100%; }

.btn-secondary { background: var(--surface); }
.btn-danger { background: rgba(239,68,68,0.1); color: var(--red); border-color: rgba(239,68,68,0.3); }
.btn-danger:hover { background: rgba(239,68,68,0.2); color: var(--red); border-color: var(--red); }
.btn-sm { padding: 4px 12px; font-size: 12px; border-radius: 4px; }
```

**Section 7 — Inputs & Forms**
```css
.input {
  background: var(--bg); color: var(--text); border: 1px solid var(--border);
  border-radius: var(--radius-xs); padding: 8px 14px; font-size: 13px;
  outline: none; transition: border-color var(--transition);
}
.input:focus { border-color: var(--accent); }
.input-ticker { text-transform: uppercase; width: 200px; font-size: 14px; }
.input-select { padding: 6px 10px; }
.select-label { font-size: 13px; color: var(--text-dim); display: flex; align-items: center; gap: 8px; }
.stock-search-bar { display: flex; gap: 10px; margin-bottom: 8px; }
.analysis-controls { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; }
```

**Section 8 — Stat Cards**
```css
.stat-cards {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 12px; margin-bottom: 24px;
}
.stat-card {
  background: var(--surface); border-radius: var(--radius);
  padding: 16px 18px; box-shadow: var(--shadow-sm);
  transition: transform var(--transition), box-shadow var(--transition);
}
.stat-card:hover { transform: translateY(-2px); box-shadow: var(--shadow-md); }
.stat-card-primary { border-top: 2px solid transparent; border-image: var(--gradient) 1; }
.stat-card-label {
  font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px;
  color: var(--text-dim); font-weight: 600; margin-bottom: 6px;
}
.stat-card-value { font-size: 20px; font-weight: 700; color: var(--text); }
.stat-card-value.pos { color: var(--green); }
.stat-card-value.neg { color: var(--red); }
```

**Section 9 — Data Tables**
```css
.table-wrap { overflow-x: auto; margin-bottom: 24px; }
.data-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.data-table th {
  text-align: left; padding: 10px 12px; border-bottom: 2px solid var(--border);
  color: var(--text-dim); font-size: 11px; text-transform: uppercase;
  letter-spacing: 0.5px; font-weight: 600;
}
.data-table td { padding: 10px 12px; border-bottom: 1px solid var(--border); vertical-align: middle; }
.data-table tr { transition: background var(--transition); }
.data-table tr:hover td { background: var(--accent-glow); }
.data-table tr.stagger-in {
  animation: rowIn 0.3s cubic-bezier(0.4, 0, 0.2, 1) both;
}
@keyframes rowIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
.section-label {
  font-size: 13px; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.5px; color: var(--text-dim); margin-bottom: 12px; margin-top: 8px;
}
```

**Section 10 — Tags, Badges, Ticker pills**
Migrate all existing `.tag`, `.ticker`, `.signal-badge` styles with updated colors. Same class names, new color values using the design tokens.

**Section 11 — Cards**
```css
.card {
  background: var(--surface); border-radius: var(--radius);
  padding: 18px; margin-bottom: 12px; box-shadow: var(--shadow-sm);
  transition: transform var(--transition), box-shadow var(--transition);
}
.card:hover { transform: translateY(-1px); box-shadow: var(--shadow-md); }
.card h3 { font-size: 14px; margin-bottom: 8px; }
.card p { font-size: 13px; color: var(--text-dim); margin-bottom: 6px; line-height: 1.5; }
```

**Section 12 — Causal chain tree, sector bars, report sections, sentiment banner**
Migrate from existing styles, updated colors. Use `var(--border)`, `var(--green)`, etc.

**Section 13 — Market overview components**
Migrate `.indices-bar`, `.index-card`, `.market-grid`, `.market-section`, `.mover-row`, `.indicator-row` styles — same structure, updated colors/shadows.

**Section 14 — Stock analysis components**
Migrate `.stock-header`, `.score-bar-container`, `.score-bar`, `.chart-container`, `.chart-tab-bar`, `.chart-tab`, `.score-card`, `.strat-signal-card` styles.

Update chart background colors in CSS variable for chart containers:
```css
.chart-container {
  background: var(--bg); border: 1px solid var(--border);
  border-radius: var(--radius-sm); margin-bottom: 16px; overflow: hidden;
}
```

**Section 15 — Backtest components**
Migrate all `.bt-*` styles. Key changes:
- `.bt-config` uses `var(--surface)` background, `var(--radius)` corners, `var(--shadow-sm)` shadow
- `.bt-run-btn` replaced by `.btn.btn-primary.btn-run`
- Colors updated to design tokens

**Section 16 — Paper trading components**
Migrate `.pt-*` styles. Replace `.pt-card` with `.stat-card`, `.pt-table` with `.data-table`.
Keep `.pt-actions`, `.pt-close-btn`, `.pt-badge`, `.pt-pnl` with updated colors.

**Section 17 — Trade journal components**
Migrate `.tj-*` styles. Replace `.tj-stat` with `.stat-card`, `.tj-filter-btn` with `.filter-btn`.
```css
.filter-bar { display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }
.filter-btn {
  padding: 6px 16px; border: 1px solid var(--border); border-radius: 20px;
  background: var(--surface); color: var(--text-dim); cursor: pointer;
  font-size: 13px; transition: all var(--transition);
}
.filter-btn:hover { border-color: var(--accent); color: var(--accent); }
.filter-btn.active { background: var(--gradient); color: #fff; border-color: transparent; }
```

Keep `.tj-trade-row`, `.tj-trade-header`, `.tj-detail`, `.tj-detail-grid`, `.tj-section`, `.tj-layer-row`, `.tj-log-entry` etc. with updated colors.

**Section 18 — News / Article styles**
Migrate `.event-group`, `.event-group-header`, `.article-item`, `.article-thumb`, etc.

**Section 19 — Progress Bar**
```css
.progress-bar {
  position: fixed; top: 0; left: 0; right: 0; height: 3px;
  z-index: 1000; opacity: 0; transition: opacity 0.3s;
}
.progress-bar.active { opacity: 1; }
.progress-bar-fill {
  height: 100%; width: 30%; background: var(--gradient);
  border-radius: 0 2px 2px 0; box-shadow: 0 0 10px var(--accent);
  animation: progressIndeterminate 1.5s ease-in-out infinite;
}
@keyframes progressIndeterminate {
  0% { width: 10%; margin-left: 0; }
  50% { width: 40%; margin-left: 30%; }
  100% { width: 10%; margin-left: 90%; }
}
.progress-bar.complete .progress-bar-fill {
  width: 100%; margin-left: 0; animation: none;
  transition: width 0.3s; box-shadow: 0 0 20px var(--accent);
}
```

**Section 20 — Skeleton Loaders**
```css
.skeleton { background: var(--surface); border-radius: var(--radius-sm); overflow: hidden; position: relative; }
.skeleton::after {
  content: ''; position: absolute; top: 0; left: 0; right: 0; bottom: 0;
  background: linear-gradient(90deg, transparent 0%, var(--surface-2) 50%, transparent 100%);
  animation: shimmer 1.5s ease-in-out infinite;
}
@keyframes shimmer { 0% { transform: translateX(-100%); } 100% { transform: translateX(100%); } }
.skeleton-card { height: 80px; margin-bottom: 12px; }
.skeleton-row { height: 44px; margin-bottom: 4px; }
.skeleton-text { height: 14px; margin-bottom: 8px; border-radius: 4px; }
.skeleton-text.short { width: 60%; }
.skeleton-text.medium { width: 80%; }
```

**Section 21 — Toasts**
```css
.toast-container {
  position: fixed; bottom: 20px; right: 20px; z-index: 1001;
  display: flex; flex-direction: column-reverse; gap: 8px;
}
.toast {
  padding: 14px 20px; border-radius: var(--radius-sm);
  background: var(--surface); border: 1px solid var(--border);
  box-shadow: var(--shadow-lg); font-size: 13px; color: var(--text);
  border-left: 3px solid var(--accent); position: relative; overflow: hidden;
  min-width: 280px;
}
.toast.success { border-left-color: var(--green); }
.toast.error { border-left-color: var(--red); }
.toast.info { border-left-color: var(--accent); }
.toast-progress {
  position: absolute; bottom: 0; left: 0; height: 2px;
  background: var(--accent); animation: toastProgress 4s linear forwards;
}
.toast.success .toast-progress { background: var(--green); }
.toast.error .toast-progress { background: var(--red); }
@keyframes toastProgress { from { width: 100%; } to { width: 0%; } }
```

**Section 22 — Operation Status Panel**
```css
.operation-status {
  margin-bottom: 16px; padding: 14px 18px; background: var(--surface);
  border-radius: var(--radius-sm); font-size: 13px; color: var(--text-dim);
  display: flex; align-items: center; gap: 10px;
  border: 1px solid var(--border);
}
.status-dot {
  width: 8px; height: 8px; border-radius: 50%; background: var(--accent);
  animation: pulse 1.5s ease-in-out infinite;
}
.elapsed-timer { margin-left: auto; font-variant-numeric: tabular-nums; }
```

**Section 23 — Scroll reveal animations**
```css
.reveal { opacity: 0; transform: translateY(16px); transition: opacity 0.5s, transform 0.5s cubic-bezier(0.4, 0, 0.2, 1); }
.reveal.visible { opacity: 1; transform: translateY(0); }
```

**Section 24 — Number transition flash**
```css
.value-flash-green { animation: flashGreen 0.6s ease; }
.value-flash-red { animation: flashRed 0.6s ease; }
@keyframes flashGreen { 0% { color: var(--green); } 100% { color: inherit; } }
@keyframes flashRed { 0% { color: var(--red); } 100% { color: inherit; } }
```

**Section 25 — Misc (back-link, meta, empty state)**
Migrate `.back-link`, `.meta`, `.empty` with updated styles.

**Section 26 — Market Overview Box**
Migrate `.market-overview-box` with updated colors/radius.

**Section 27 — Responsive breakpoints**
```css
@media (max-width: 1024px) {
  .app { padding: 20px; }
  .market-grid { grid-template-columns: 1fr 1fr; }
}
@media (max-width: 768px) {
  .app { padding: 12px; }
  .tab { padding: 10px 14px; font-size: 13px; }
  .market-grid { grid-template-columns: 1fr; }
  .stat-cards { grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); }
  .data-table th, .data-table td { padding: 8px 6px; font-size: 12px; }
}
```

- [ ] **Step 2: Commit**

```bash
git add app/static/css/styles.css
git commit -m "feat(ui): add complete CSS design system with fintech aesthetic"
```

---

### Task 3: Write the API layer (api.js)

**Files:**
- Create: `app/static/js/api.js`

Extract the `api()` fetch helper into its own module. Simple, focused, one purpose.

- [ ] **Step 1: Write api.js**

```javascript
// api.js — Centralized fetch layer for all backend calls
// Exports: api(method, path, body) and setToastHandler(fn)

const API_BASE = '';

let _toastFn = null;

/**
 * Register a toast handler so API errors show visual feedback.
 * Called once from app.js after toast system is initialized.
 */
export function setToastHandler(fn) {
  _toastFn = fn;
}

/**
 * Make an API call. Returns parsed JSON on success.
 * Shows toast on error and re-throws.
 */
export async function api(method, path, body) {
  try {
    const opts = {
      method,
      headers: { 'Content-Type': 'application/json' },
    };
    if (body) opts.body = JSON.stringify(body);

    const resp = await fetch(API_BASE + path, opts);

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: resp.statusText }));
      throw new Error(err.detail || `HTTP ${resp.status}`);
    }

    return await resp.json();
  } catch (e) {
    if (_toastFn) _toastFn(e.message, 'error');
    throw e;
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add app/static/js/api.js
git commit -m "feat(ui): add centralized API layer"
```

---

### Task 4: Write the transitions layer (transitions.js)

**Files:**
- Create: `app/static/js/transitions.js`

Wraps the `motion` library (global `Motion` object from CDN) to provide:
- Tab indicator animation
- Panel transitions
- Number counting animation
- Staggered row reveals
- Scroll-triggered reveals
- Progress bar control
- Toast animation

- [ ] **Step 1: Write transitions.js**

```javascript
// transitions.js — Animation helpers using Motion library (global `Motion` from CDN)
// Falls back gracefully if Motion is unavailable.

const M = window.Motion;

/**
 * Animate the tab indicator to slide under the active tab.
 * @param {HTMLElement} indicator - The indicator element
 * @param {HTMLElement} tab - The target tab button
 */
export function moveTabIndicator(indicator, tab) {
  if (!indicator || !tab) return;
  const rect = tab.getBoundingClientRect();
  const parentRect = tab.parentElement.getBoundingClientRect();
  const left = rect.left - parentRect.left;
  const width = rect.width;

  if (M) {
    M.animate(indicator, { left: `${left}px`, width: `${width}px` }, { duration: 0.35, easing: M.spring({ stiffness: 300, damping: 30 }) });
  } else {
    indicator.style.left = `${left}px`;
    indicator.style.width = `${width}px`;
  }
}

/**
 * Animate a panel entering (fade in + slide up).
 * @param {HTMLElement} panel - The panel element
 */
export function animatePanelIn(panel) {
  if (!panel || !M) return;
  M.animate(panel, { opacity: [0, 1], transform: ['translateY(12px)', 'translateY(0)'] }, { duration: 0.3, easing: M.spring({ stiffness: 200, damping: 25 }) });
}

/**
 * Animate a number counting from old value to new value.
 * @param {HTMLElement} el - The element to update
 * @param {number} from - Start value
 * @param {number} to - End value
 * @param {object} opts - { prefix, suffix, decimals, duration }
 */
export function animateNumber(el, from, to, opts = {}) {
  const { prefix = '', suffix = '', decimals = 2, duration = 0.4 } = opts;

  if (!M || from === to) {
    el.textContent = `${prefix}${to.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}${suffix}`;
    return;
  }

  const obj = { val: from };
  M.animate(obj, { val: to }, {
    duration,
    easing: M.spring({ stiffness: 150, damping: 20 }),
    onUpdate: () => {
      el.textContent = `${prefix}${obj.val.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}${suffix}`;
    },
  });

  // Flash color based on direction
  if (to > from) {
    el.classList.add('value-flash-green');
    setTimeout(() => el.classList.remove('value-flash-green'), 600);
  } else if (to < from) {
    el.classList.add('value-flash-red');
    setTimeout(() => el.classList.remove('value-flash-red'), 600);
  }
}

/**
 * Apply staggered fade-in to table rows or card elements.
 * @param {NodeList|HTMLElement[]} elements - Elements to stagger
 * @param {number} delayMs - Delay between each element in ms
 */
export function staggerIn(elements, delayMs = 30) {
  if (!elements || !elements.length) return;

  for (let i = 0; i < elements.length; i++) {
    const el = elements[i];
    el.style.opacity = '0';
    el.style.transform = 'translateY(8px)';

    if (M) {
      M.animate(el,
        { opacity: [0, 1], transform: ['translateY(8px)', 'translateY(0)'] },
        { delay: i * (delayMs / 1000), duration: 0.3, easing: 'ease-out' }
      );
    } else {
      setTimeout(() => {
        el.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
        el.style.opacity = '1';
        el.style.transform = 'translateY(0)';
      }, i * delayMs);
    }
  }
}

/**
 * Animate a score bar filling from 0 to the given percentage.
 * @param {HTMLElement} fillEl - The .score-bar-fill element
 * @param {number} pct - Target percentage (0-100)
 */
export function animateScoreBar(fillEl, pct) {
  if (!fillEl) return;
  fillEl.style.width = '0%';

  if (M) {
    M.animate(fillEl, { width: `${pct}%` }, { duration: 0.6, easing: M.spring({ stiffness: 100, damping: 20 }) });
  } else {
    setTimeout(() => { fillEl.style.transition = 'width 0.6s ease'; fillEl.style.width = `${pct}%`; }, 50);
  }
}

/**
 * Set up scroll-triggered reveal for elements with .reveal class.
 * Call once after DOM is ready.
 */
export function initScrollReveals() {
  const observer = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
        observer.unobserve(entry.target);
      }
    }
  }, { threshold: 0.1 });

  document.querySelectorAll('.reveal').forEach(el => observer.observe(el));
}

/**
 * Show the top progress bar (indeterminate).
 */
export function showProgressBar() {
  const bar = document.getElementById('progress-bar');
  if (bar) { bar.classList.add('active'); bar.classList.remove('complete'); }
}

/**
 * Complete and hide the top progress bar with a flash effect.
 */
export function hideProgressBar() {
  const bar = document.getElementById('progress-bar');
  if (!bar) return;
  bar.classList.add('complete');
  setTimeout(() => { bar.classList.remove('active', 'complete'); }, 500);
}

/**
 * Animate expand/collapse of an element's height using spring physics.
 * Used for event card expand, accordion expand, trade journal detail.
 * @param {HTMLElement} el - The element to expand/collapse
 * @param {boolean} open - true to expand, false to collapse
 */
export function animateExpand(el, open) {
  if (!el) return;

  if (open) {
    el.style.display = 'block';
    const height = el.scrollHeight;
    el.style.height = '0px';
    el.style.overflow = 'hidden';

    if (M) {
      M.animate(el, { height: `${height}px`, opacity: [0, 1] }, {
        duration: 0.35, easing: M.spring({ stiffness: 200, damping: 25 }),
      }).then(() => { el.style.height = 'auto'; el.style.overflow = ''; });
    } else {
      el.style.height = `${height}px`;
      el.style.opacity = '1';
      setTimeout(() => { el.style.height = 'auto'; el.style.overflow = ''; }, 350);
    }
  } else {
    const height = el.scrollHeight;
    el.style.height = `${height}px`;
    el.style.overflow = 'hidden';

    if (M) {
      M.animate(el, { height: '0px', opacity: 0 }, { duration: 0.25, easing: 'ease-in' })
        .then(() => { el.style.display = 'none'; el.style.height = ''; el.style.overflow = ''; });
    } else {
      el.style.height = '0px';
      setTimeout(() => { el.style.display = 'none'; el.style.height = ''; el.style.overflow = ''; }, 250);
    }
  }
}

/**
 * Stagger tabs in on page load.
 * @param {NodeList} tabs - Tab button elements
 */
export function staggerTabs(tabs) {
  if (!tabs) return;
  for (let i = 0; i < tabs.length; i++) {
    const tab = tabs[i];
    tab.style.opacity = '0';
    if (M) {
      M.animate(tab, { opacity: [0, 1], transform: ['translateY(-4px)', 'translateY(0)'] },
        { delay: i * 0.05, duration: 0.3, easing: 'ease-out' });
    } else {
      setTimeout(() => { tab.style.opacity = '1'; }, i * 50);
    }
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add app/static/js/transitions.js
git commit -m "feat(ui): add transitions layer with motion library wrappers"
```

---

### Task 5: Write the components layer (components.js)

**Files:**
- Create: `app/static/js/components.js`

All render functions, skeleton builders, and toast system. This is the largest JS file — it contains every function that generates HTML strings.

- [ ] **Step 1: Write components.js**

The file exports these functions (organized by section):

**Helpers (not exported, internal):**
- `escHtml(str)` — HTML entity escape
- `tag(value, cls)` — tag/badge HTML
- `tickerTag(t)` — ticker pill HTML
- `changeClass(pct)` — 'positive'/'negative'/'' from a percent string
- `formatPct(pct)` — format percent with % suffix
- `formatTimestamp(ts)` — AV timestamp to readable format

**Exported — Skeleton generators:**
- `skeletonCards(n)` — returns HTML for n skeleton stat cards
- `skeletonRows(n)` — returns HTML for n skeleton table rows
- `skeletonText(n)` — returns HTML for n skeleton text lines

**Exported — Toast system:**
- `showToast(msg, type)` — create and append a toast to `#toast-container`

**Exported — Render functions (migrate from existing, same logic, same HTML output):**
- `renderEventDetail(data)` — event detail page
- `renderReport(data, container)` — synthesis report
- `renderArticle(a)` — single article card
- `renderStockAnalysis(data)` — stock analysis page
- `renderStockCharts(data, stockCharts)` — lightweight-charts rendering
- `renderBtResults(d, horizons)` — backtest results
- `renderMarketData(data)` — market overview data grid
- `renderMarketOverview(data)` — LLM market overview box
- `ptRenderPortfolio(p)` — paper trading portfolio cards
- `ptRenderTrades(trades)` — paper trading trade tables
- `tjRenderStats(p)` — trade journal stat cards
- `tjRenderList(trades, filter, expandedId)` — trade journal list
- `tjRenderDetail(t)` — trade journal expanded detail

**Implementation approach:**

Each render function is migrated directly from the existing `index.html` JavaScript. The function bodies are identical — same HTML generation, same conditionals, same data access patterns. The only changes are:

1. Use `escHtml()` from this module (not global)
2. Use `tag()`, `tickerTag()` from this module (not global)
3. Return HTML strings instead of setting `.innerHTML` directly (the caller in `app.js` handles DOM insertion)
4. Chart colors updated to match new design tokens (`#0a0e17` instead of `#0d1117`, etc.)

**Example — showToast (new):**
```javascript
export function showToast(msg, type = 'error') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `${escHtml(msg)}<div class="toast-progress"></div>`;

  // Spring animation for entry
  const M = window.Motion;
  if (M) {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(20px)';
    container.appendChild(toast);
    M.animate(toast, { opacity: 1, transform: 'translateX(0)' }, { duration: 0.3, easing: M.spring({ stiffness: 300, damping: 25 }) });
  } else {
    container.appendChild(toast);
  }

  setTimeout(() => {
    if (M) {
      M.animate(toast, { opacity: 0, transform: 'translateX(20px)' }, { duration: 0.2 }).then(() => toast.remove());
    } else {
      toast.remove();
    }
  }, 4000);
}
```

**Example — skeletonCards (new):**
```javascript
export function skeletonCards(n = 4) {
  return `<div class="stat-cards">${Array(n).fill('<div class="skeleton skeleton-card"></div>').join('')}</div>`;
}

export function skeletonRows(n = 4) {
  return Array(n).fill('<div class="skeleton skeleton-row"></div>').join('');
}

export function skeletonText(n = 3) {
  const widths = ['medium', '', 'short'];
  return Array(n).fill(0).map((_, i) => `<div class="skeleton skeleton-text ${widths[i % 3]}"></div>`).join('');
}
```

**Example — renderStockCharts (updated colors):**
```javascript
export function renderStockCharts(data, stockCharts) {
  const cd = data.chart_data;
  if (!cd) return;

  const chartOpts = {
    layout: { background: { color: '#0a0e17' }, textColor: '#64748b' },
    grid: { vertLines: { color: '#1e293b' }, horzLines: { color: '#1e293b' } },
    timeScale: { borderColor: '#1e293b' },
    rightPriceScale: { borderColor: '#1e293b' },
    crosshair: { mode: 0 },
  };

  // ... rest identical to existing, using updated green (#22c55e) and red (#ef4444)
}
```

For all other render functions: copy the function body from existing `index.html` lines 1173-3048, updating:
- Color references: `#0d1117` -> `#0a0e17`, `#3fb950` -> `#22c55e`, `#f85149` -> `#ef4444`, `#d29922` -> `#eab308`, `#8b949e` -> `#64748b`, `#58a6ff` -> `#6366f1`
- `var(--card-bg)` -> `var(--surface)`
- CSS class names for tables: `pt-table` -> `data-table` where applicable
- Add `stagger-in` class to table rows for animation

- [ ] **Step 2: Commit**

```bash
git add app/static/js/components.js
git commit -m "feat(ui): add components layer with render functions, skeletons, toasts"
```

---

### Task 6: Write the app entry point (app.js)

**Files:**
- Create: `app/static/js/app.js`

App state, routing, panel switching, all event wiring, and initialization. Imports from the other three modules. Attaches public functions to `window` for HTML `onclick` handlers.

- [ ] **Step 1: Write app.js**

Structure:

```javascript
// app.js — Application entry point
import { api, setToastHandler } from './api.js';
import { moveTabIndicator, animatePanelIn, staggerTabs, showProgressBar, hideProgressBar, staggerIn, animateScoreBar, animateExpand, initScrollReveals } from './transitions.js';
import { showToast, skeletonCards, skeletonRows, skeletonText, renderEventDetail, renderReport, renderArticle, renderStockAnalysis, renderStockCharts, renderBtResults, renderMarketData, renderMarketOverview, ptRenderPortfolio, ptRenderTrades, tjRenderStats, tjRenderList, tjRenderDetail, escHtml, tag, tickerTag } from './components.js';

// ── State ──
let _backPanel = 'scan';
let _analysisRunning = false;
let _overviewRunning = false;
let _stockCharts = [];
let _tjTrades = [];
let _tjFilter = 'all';
let _tjExpandedId = null;

// Backtest state
const BT_DEFAULT_TICKERS = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'JPM', 'XOM', 'UNH', 'PG', 'TSLA'];
let btTickers = [...BT_DEFAULT_TICKERS];
let _btAcTimer = null;
let _btAcIdx = -1;

// ── Toast wiring ──
setToastHandler(showToast);

// ── Navigation ──
function showPanel(name) {
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  const panel = document.getElementById(`panel-${name}`);
  if (panel) {
    panel.classList.add('active');
    animatePanelIn(panel);
  }

  // Update tab active state
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  const tab = document.querySelector(`.tab[data-panel="${name}"]`);
  if (tab) {
    tab.classList.add('active');
    moveTabIndicator(document.getElementById('tab-indicator'), tab);
  }

  // Auto-load data for certain panels
  if (name === 'trade-journal') tjLoad();
  if (name === 'paper-trading') ptLoad();
}

// ── Tab bar setup ──
function initTabs() {
  const tabs = document.querySelectorAll('.tab');
  tabs.forEach(tab => {
    tab.addEventListener('click', () => showPanel(tab.dataset.panel));
  });
  // Stagger tabs in on load
  staggerTabs(tabs);
}

// ── Health Check ──
// (migrate checkHealth from existing — same logic, uses api())

// ── Scan ──
// (migrate runScan — same logic, add showProgressBar/hideProgressBar around the call,
//  use skeletonRows for loading state instead of spinner)

// ── Deep Analysis ──
// (migrate runDeepAnalysis, goBack, renderEventDetail — show progress bar for long ops)

// ── Full Analysis ──
// (migrate runFullAnalysis — add progress bar, operation status with elapsed timer)

// ── Events ──
// (migrate loadEvents, viewEvent — use skeleton loading, stagger table rows)

// ── Report ──
// (migrate loadReport — use skeleton loading)

// ── Sectors ──
// (migrate loadSectors)

// ── News ──
// (migrate toggleEventGroup, loadNews)

// ── Market ──
// (migrate loadMarket, runMarketOverview — skeleton cards for loading)

// ── Stock Analysis ──
// (migrate runStockAnalysis, switchChartTab, _destroyStockCharts — score bar animation)

// ── Backtest ──
// (migrate ALL bt* functions — btInitTickers, btFetchSuggestions, btShowAc, btHideAc,
//  btHighlightAc, btSelectTicker, renderBtTickers, btRemoveTicker, btGetStrategies,
//  btGetHorizons, runBacktest, btSwitchHorizon, btToggleAccordion)

// ── Paper Trading ──
// (migrate ALL pt* functions — ptLoad, ptScan, ptUpdate, ptNewsGuard, ptCloseTrade, ptReset)

// ── Trade Journal ──
// (migrate ALL tj* functions — tjLoad, tjFilter, tjToggle)

// ── Window Attachments ──
// Every function referenced by onclick in the HTML must be on window
Object.assign(window, {
  showPanel, loadMarket, runMarketOverview, runScan, runDeepAnalysis,
  loadEvents, viewEvent, loadReport, loadSectors, loadNews,
  runStockAnalysis, switchChartTab, runFullAnalysis, runBacktest,
  btRemoveTicker, btSelectTicker, btSwitchHorizon, btToggleAccordion,
  ptLoad, ptScan, ptUpdate, ptNewsGuard, ptCloseTrade, ptReset,
  tjFilter: tjFilterHandler, tjToggle, toggleEventGroup, goBack,
});

// ── Init ──
function init() {
  initTabs();
  checkHealth();
  setInterval(checkHealth, 30000);
  showPanel('market');
  btInitTickers();
  initScrollReveals();
}

init();
```

**Key changes from existing code in each migrated function:**

1. **Loading states:** Replace `loading('msg')` spinner with:
   - `skeletonCards(4)` for card-based panels (market, portfolio)
   - `skeletonRows(5)` for table-based panels (events, trades)
   - `skeletonText(3)` for text-based panels (report)

2. **Long operations:** Add `showProgressBar()` before and `hideProgressBar()` after:
   - `runScan()`, `runDeepAnalysis()`, `runFullAnalysis()`, `runStockAnalysis()`
   - `runBacktest()`, `ptScan()`, `ptUpdate()`, `ptNewsGuard()`
   - `runMarketOverview()`

3. **Operation status:** For `runFullAnalysis()` and `ptScan()`, show elapsed timer:
   ```javascript
   const startTime = Date.now();
   const statusEl = document.getElementById('pt-scan-status');
   statusEl.style.display = 'flex';
   statusEl.innerHTML = '<span class="status-dot"></span><span>Scanning watchlist...</span><span class="elapsed-timer">0:00</span>';
   const timer = setInterval(() => {
     const elapsed = Math.floor((Date.now() - startTime) / 1000);
     const min = Math.floor(elapsed / 60);
     const sec = String(elapsed % 60).padStart(2, '0');
     statusEl.querySelector('.elapsed-timer').textContent = `${min}:${sec}`;
   }, 1000);
   // ... after completion:
   clearInterval(timer);
   ```

4. **Stagger table rows:** After inserting table HTML, call:
   ```javascript
   staggerIn(container.querySelectorAll('tbody tr'));
   ```

5. **Score bar animation:** After rendering stock analysis:
   ```javascript
   const fillEl = document.querySelector('.score-bar-fill');
   animateScoreBar(fillEl, pct);
   ```

6. **Trade journal filters:** Use event delegation instead of inline onclick:
   ```javascript
   function tjFilterHandler(f) {
     _tjFilter = f;
     document.querySelectorAll('.filter-btn').forEach(b => {
       b.classList.toggle('active', b.dataset.filter === f);
     });
     tjRenderListInner();
   }
   // Setup in init:
   document.querySelectorAll('.filter-btn').forEach(btn => {
     btn.addEventListener('click', () => tjFilterHandler(btn.dataset.filter));
   });
   ```

- [ ] **Step 2: Commit**

```bash
git add app/static/js/app.js
git commit -m "feat(ui): add app entry point with state, routing, and all panel logic"
```

---

### Task 7: Integration verification

**Files:**
- Verify: all files created in Tasks 1-6
- Possibly fix: any cross-file import/reference issues

- [ ] **Step 1: Verify the server starts and serves the new UI**

```bash
cd /Users/agil/Desktop/dev/market-analyst
python -m app.api.server
```

Open `http://localhost:8000` in a browser. Expected:
- Page loads without JS console errors
- Header shows "Market Analyst" with gradient dot and health badge
- Tab bar renders with 6 tabs
- Gradient underline indicator appears under "Market" tab
- Clicking tabs switches panels with fade-in animation
- Dark theme with indigo/violet accent is visible

- [ ] **Step 2: Verify each panel works**

Test each tab manually:
1. **Market** — Click "Load Market Data", verify skeleton loader shows then data appears with staggered animation
2. **Analysis** — Click "Run Full Analysis", verify progress bar appears at top, operation status shows elapsed timer
3. **Stock** — Type "AAPL" and click Analyze, verify charts render with new color scheme
4. **Backtest** — Verify ticker autocomplete works, run a backtest, check results render
5. **Paper Trading** — Click "Load Portfolio", verify stat cards animate, tables stagger in
6. **Journal** — Verify filters work, trade detail expands

- [ ] **Step 3: Fix any issues found**

Common issues to check:
- Functions referenced by `onclick` in HTML are attached to `window`
- `Motion` global is available (CDN loaded before module)
- `LightweightCharts` global is available
- CSS class name mismatches between HTML and CSS
- Import paths are correct (relative `./api.js` etc.)

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat(ui): complete UI redesign with fintech aesthetic, animations, and split file structure"
```

---

## Implementation Notes

### Motion Library Fallback
Every function in `transitions.js` checks `if (M)` before using Motion APIs. If the CDN fails to load, the UI still works — just without spring animations. CSS transitions and keyframes provide baseline animation.

### Chart Color Mapping
Old → New color mapping for lightweight-charts:
| Old | New | Usage |
|-----|-----|-------|
| `#0d1117` | `#0a0e17` | Chart background |
| `#8b949e` | `#64748b` | Chart text |
| `#21262d` | `#1e293b` | Grid lines |
| `#30363d` | `#1e293b` | Scale borders |
| `#3fb950` | `#22c55e` | Up candles |
| `#f85149` | `#ef4444` | Down candles |
| `#58a6ff` | `#6366f1` | Accent lines |
| `#d2a8ff` | `#8b5cf6` | MA200, RSI |
| `#d29922` | `#eab308` | Fibonacci |
| `#f0883e` | `#f97316` | MACD signal |

### Functions Attached to Window
These functions must be on `window` because HTML onclick handlers reference them:
`showPanel`, `loadMarket`, `runMarketOverview`, `runScan`, `runDeepAnalysis`, `loadEvents`, `viewEvent`, `loadReport`, `loadSectors`, `loadNews`, `runStockAnalysis`, `switchChartTab`, `runFullAnalysis`, `runBacktest`, `btRemoveTicker`, `btSelectTicker`, `btSwitchHorizon`, `btToggleAccordion`, `ptLoad`, `ptScan`, `ptUpdate`, `ptNewsGuard`, `ptCloseTrade`, `ptReset`, `tjFilter`, `tjToggle`, `toggleEventGroup`, `goBack`

### Sortable Columns
The spec mentions "sortable column headers with chevron indicator." This is deferred — add CSS for `.sortable-th` with a chevron but do NOT implement sort logic. The visual indicator is enough for now; sort functionality can be added later without changing the design.

### Expand/Collapse Animation
Use `animateExpand()` from transitions.js for:
- Event group body toggle (replace `display:none` toggle in `toggleEventGroup`)
- Backtest accordion toggle (replace `display:none` toggle in `btToggleAccordion`)
- Trade journal detail expand (replace `classList.toggle('open')` in `tjToggle`)

### No Backend Changes
`routes.py` already has `app.mount("/static", StaticFiles(directory=STATIC_DIR))` which serves all files under `app/static/` including subdirectories. The root `GET /` route serves `index.html` via `FileResponse`. No changes needed.
