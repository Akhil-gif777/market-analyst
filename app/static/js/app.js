// app.js — Application entry point
import { api, setToastHandler } from './api.js';
import {
  moveTabIndicator, animatePanelIn, staggerTabs, showProgressBar,
  hideProgressBar, staggerIn, animateScoreBar, animateExpand,
  initScrollReveals
} from './transitions.js';
import {
  showToast, skeletonCards, skeletonRows, skeletonText,
  renderEventDetail, renderReport, renderArticle,
  renderStockAnalysis, renderStockCharts, renderNarrative, renderBtResults,
  renderMarketData, renderMarketOverview,
  ptRenderPortfolio, ptRenderTrades,
  tjRenderStats, tjRenderList, tjRenderDetail,
  renderFundamentals,
  escHtml, tag, tickerTag
} from './components.js';

// ── Wire toast handler ─────────────────────────────────────────────────────────

setToastHandler(showToast);

// ── State ──────────────────────────────────────────────────────────────────────

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

// ── Navigation ─────────────────────────────────────────────────────────────────

function showPanel(name) {
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  const panel = document.getElementById(`panel-${name}`);
  if (panel) {
    panel.classList.add('active');
    try { animatePanelIn(panel); } catch (e) { console.error('animatePanelIn error:', e); }
  }

  // Update tab active state
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  const tab = document.querySelector(`.tab[data-panel="${name}"]`);
  if (tab) {
    tab.classList.add('active');
    try { moveTabIndicator(document.getElementById('tab-indicator'), tab); } catch (e) { console.error('moveTabIndicator error:', e); }
  }

  // Auto-load data for certain panels
  if (name === 'trade-journal') tjLoad();
  if (name === 'paper-trading') { ptLoad(); shLoad(); }
}

function initTabs() {
  const tabs = document.querySelectorAll('.tab');
  tabs.forEach(tab => {
    tab.addEventListener('click', () => showPanel(tab.dataset.panel));
  });
  staggerTabs(tabs);
}

// ── Filter buttons ─────────────────────────────────────────────────────────────

function initFilterButtons() {
  document.querySelectorAll('.filter-btn').forEach(btn => {
    btn.addEventListener('click', () => tjFilterHandler(btn.dataset.filter));
  });
}

// ── Health Check ───────────────────────────────────────────────────────────────

async function checkHealth() {
  try {
    const data = await api('GET', '/health');
    const badge = document.getElementById('health-badge');
    badge.textContent = data.status === 'ok' ? 'System OK' : 'Degraded';
    badge.className = `health-badge ${data.status === 'ok' ? 'ok' : 'degraded'}`;
  } catch {
    const badge = document.getElementById('health-badge');
    badge.textContent = 'Offline';
    badge.className = 'health-badge error';
  }
}

// ── Scan ───────────────────────────────────────────────────────────────────────

async function runScan() {
  const container = document.getElementById('scan-result');
  const btn = document.getElementById('btn-scan');
  btn.disabled = true;
  container.innerHTML = skeletonRows(5);
  showProgressBar();

  try {
    const data = await api('POST', '/scan');
    const events = data.events || [];

    if (events.length === 0) {
      container.innerHTML = '<div class="empty"><p>No market-moving events detected.</p></div>';
      return;
    }

    let html = `<div class="meta">
      <span>Articles fetched: <strong>${data.articles_fetched || '?'}</strong></span>
      <span>Events found: <strong>${events.length}</strong></span>
      <span>Duration: <strong>${data.duration_seconds || '?'}s</strong></span>
    </div>`;

    html += '<table><thead><tr><th>ID</th><th>Event</th><th>Category</th><th>Severity</th><th>Tickers</th><th>Action</th></tr></thead><tbody>';
    for (const e of events) {
      const tickers = (e.related_tickers || []).slice(0, 5).map(tickerTag).join(' ');
      html += `<tr>
        <td>${e.event_id}</td>
        <td><strong>${escHtml(e.title)}</strong><br><span style="color:var(--text-dim);font-size:12px">${escHtml((e.summary || '').slice(0, 100))}</span></td>
        <td>${escHtml(e.category || '')}</td>
        <td>${tag(e.severity || 'unknown')}</td>
        <td>${tickers || '<span style="color:var(--text-dim)">none</span>'}</td>
        <td><button class="btn-sm" onclick="runDeepAnalysis(${e.event_id})">Analyze</button></td>
      </tr>`;
    }
    html += '</tbody></table>';
    container.innerHTML = html;
    staggerIn(container.querySelectorAll('tbody tr'));
  } catch {
    container.innerHTML = '<div class="empty"><p>Scan failed. Check that Ollama is running.</p></div>';
  } finally {
    btn.disabled = false;
    hideProgressBar();
  }
}

// ── Deep Analysis ──────────────────────────────────────────────────────────────

async function runDeepAnalysis(eventId, backTo) {
  _backPanel = backTo || 'scan';
  showPanel('event-detail');
  const container = document.getElementById('event-detail-content');
  container.innerHTML = skeletonText();
  showProgressBar();

  try {
    const data = await api('POST', `/events/${eventId}/analyze`);
    container.innerHTML = renderEventDetail(data);
  } catch {
    container.innerHTML = `<span class="back-link" onclick="goBack()">&#8592; Back</span>
      <div class="empty"><p>Analysis failed.</p></div>`;
  } finally {
    hideProgressBar();
  }
}

function goBack() {
  showPanel(_backPanel);
  if (_backPanel === 'events') loadEvents();
}

// ── Full Analysis ──────────────────────────────────────────────────────────────

async function runFullAnalysis() {
  if (_analysisRunning) return;
  _analysisRunning = true;

  const btn = document.getElementById('btn-analyze');
  const container = document.getElementById('analyze-content');
  btn.disabled = true;

  const startTime = Date.now();
  container.innerHTML = `<div class="operation-status"><span class="status-dot"></span><span>Running full market analysis...</span><span class="elapsed-timer">0:00</span></div>`;
  const timer = setInterval(() => {
    const elapsed = Math.floor((Date.now() - startTime) / 1000);
    const min = Math.floor(elapsed / 60);
    const sec = String(elapsed % 60).padStart(2, '0');
    const el = container.querySelector('.elapsed-timer');
    if (el) el.textContent = `${min}:${sec}`;
  }, 1000);

  showProgressBar();

  try {
    const maxEvents = document.getElementById('max-events').value;
    const data = await api('POST', `/analyze?max_events=${maxEvents}`);
    clearInterval(timer);
    container.innerHTML = renderReport(data);
    showToast('Analysis complete!', 'success');
  } catch {
    clearInterval(timer);
    container.innerHTML = '<div class="empty"><p>Full analysis failed. Check that Ollama is running.</p></div>';
  } finally {
    _analysisRunning = false;
    btn.disabled = false;
    hideProgressBar();
  }
}

// ── Events List ───────────────────────────────────────────────────────────────

async function loadEvents() {
  const container = document.getElementById('events-content');
  container.innerHTML = skeletonRows(8);

  try {
    const data = await api('GET', '/events?limit=30');
    const events = data.events || [];

    if (events.length === 0) {
      container.innerHTML = '<div class="empty"><p>No events yet.</p><p>Run a Scan or Full Analysis first.</p></div>';
      return;
    }

    let html = '<table><thead><tr><th>ID</th><th>Event</th><th>Category</th><th>Severity</th><th>Sectors</th><th>Date</th><th></th></tr></thead><tbody>';
    for (const e of events) {
      const sectors = (e.sector_impacts || []).slice(0, 3).map(s => {
        const arrow = s.direction === 'bullish' ? '&#9650;' : s.direction === 'bearish' ? '&#9660;' : '~';
        return `${s.sector} ${arrow}`;
      }).join(', ');

      html += `<tr>
        <td>${e.id}</td>
        <td><strong>${escHtml(e.title)}</strong></td>
        <td>${escHtml(e.category || '')}</td>
        <td>${tag(e.severity || '')}</td>
        <td style="font-size:12px">${sectors || '<span style="color:var(--text-dim)">-</span>'}</td>
        <td style="font-size:12px">${(e.created_at || '').slice(0, 16)}</td>
        <td><button class="btn-sm" onclick="viewEvent(${e.id})">View</button> <button class="btn-sm" onclick="runDeepAnalysis(${e.id}, 'events')" style="margin-left:4px">Analyze</button></td>
      </tr>`;
    }
    html += '</tbody></table>';
    container.innerHTML = html;
    staggerIn(container.querySelectorAll('tbody tr'));
  } catch {
    container.innerHTML = '<div class="empty"><p>Failed to load events.</p></div>';
  }
}

async function viewEvent(eventId) {
  showPanel('event-detail');
  const container = document.getElementById('event-detail-content');
  container.innerHTML = skeletonText();

  try {
    const event = await api('GET', `/events/${eventId}`);
    let html = `<span class="back-link" onclick="showPanel('events'); loadEvents()">&#8592; Back to Events</span>`;
    html += `<h2 style="margin-bottom:8px">${escHtml(event.title)}</h2>`;
    html += `<div class="meta">
      <span>Category: <strong>${escHtml(event.category || '')}</strong></span>
      <span>Severity: ${tag(event.severity || '')}</span>
    </div>`;
    html += `<p style="color:var(--text-dim);margin-bottom:16px">${escHtml(event.summary || '')}</p>`;
    html += `<button class="btn-sm" onclick="runDeepAnalysis(${eventId}, 'events')" style="margin-bottom:20px">Re-analyze this event</button>`;

    // Causal chains
    if (event.causal_chains && event.causal_chains.length) {
      html += `<div class="report-section"><h3>Causal Chains</h3><div class="chain-tree">`;
      for (const c of event.causal_chains) {
        html += `<div class="chain-item">
          <span class="order">${c.order || '?'}°</span>
          <span>${escHtml(c.chain)}</span>
          <span class="tag ${c.confidence}">${c.confidence}</span>
        </div>`;
      }
      html += `</div></div>`;
    }

    // Sector impacts
    if (event.sector_impacts && event.sector_impacts.length) {
      html += `<div class="report-section"><h3>Sector Impacts</h3>`;
      for (const s of event.sector_impacts) {
        html += `<div class="sector-bar">
          <span class="name">${escHtml(s.sector)}</span>
          <span class="signal">${tag(s.direction)}</span>
          <span class="reason">${escHtml(s.reason || '')}</span>
        </div>`;
      }
      html += `</div>`;
    }

    // Stock picks
    if (event.stock_picks && event.stock_picks.length) {
      html += `<div class="report-section"><h3>Stock Picks</h3>`;
      for (const p of event.stock_picks) {
        const dir = p.direction || p.action || '';
        html += `<div class="card">
          <h3>${tickerTag(p.ticker)} ${tag(dir)}</h3>
          <p>${escHtml(p.reason || '')}</p>
        </div>`;
      }
      html += `</div>`;
    }

    container.innerHTML = html;
  } catch {
    container.innerHTML = `<span class="back-link" onclick="showPanel('events'); loadEvents()">&#8592; Back</span>
      <div class="empty"><p>Failed to load event.</p></div>`;
  }
}

// ── Report ────────────────────────────────────────────────────────────────────

async function loadReport() {
  const container = document.getElementById('report-content');
  container.innerHTML = skeletonText();

  try {
    const data = await api('GET', '/report');
    container.innerHTML = renderReport(data);
  } catch {
    container.innerHTML = '<div class="empty"><p>No reports yet.</p><p>Run a Full Analysis to generate one.</p></div>';
  }
}

// ── Sectors ───────────────────────────────────────────────────────────────────

async function loadSectors() {
  const container = document.getElementById('sectors-content');
  container.innerHTML = skeletonRows(5);

  try {
    const data = await api('GET', '/sectors');

    if (!data.sector_outlook || data.sector_outlook.length === 0) {
      container.innerHTML = '<div class="empty"><p>No sector data yet. Run a Full Analysis first.</p></div>';
      return;
    }

    let html = '';
    if (data.overall_sentiment) {
      const sentiment = data.overall_sentiment;
      html += `<div class="sentiment-banner ${sentiment}">
        ${sentiment.replace(/_/g, ' ').toUpperCase()}
      </div>`;
    }

    for (const s of data.sector_outlook) {
      html += `<div class="sector-bar">
        <span class="name">${escHtml(s.sector)}</span>
        <span class="signal">${tag(s.signal)}</span>
        <span class="reason">${escHtml(s.reason || '')}</span>
      </div>`;
    }

    container.innerHTML = html;
  } catch {
    container.innerHTML = '<div class="empty"><p>No sector data yet.</p></div>';
  }
}

// ── News ──────────────────────────────────────────────────────────────────────

function toggleEventGroup(el) {
  el.closest('.event-group').classList.toggle('open');
}

async function loadNews() {
  const container = document.getElementById('news-content');
  container.innerHTML = skeletonRows(6);

  try {
    const data = await api('GET', '/news?limit=30');
    const events = data.events || [];

    if (events.length === 0) {
      container.innerHTML = '<div class="empty"><p>No news yet.</p><p>Run a Scan or Full Analysis first.</p></div>';
      return;
    }

    let html = '';
    for (const item of events) {
      const e = item.event;
      const articles = item.articles || [];
      const tickers = (e.related_tickers || []).slice(0, 5).map(tickerTag).join(' ');

      html += `<div class="event-group">
        <div class="event-group-header" onclick="toggleEventGroup(this)">
          <div>
            <h3><span class="chevron" style="display:inline-block;margin-right:6px;font-size:11px">&#9654;</span>${escHtml(e.title)}</h3>
            <div style="font-size:12px;color:var(--text-dim);margin-top:2px">${escHtml(e.summary || '')}</div>
          </div>
          <div class="group-meta">
            ${tag(e.severity || '')}
            <span>${articles.length} article${articles.length !== 1 ? 's' : ''}</span>
            ${tickers ? `<span>${tickers}</span>` : ''}
          </div>
        </div>
        <div class="event-group-body">`;

      if (articles.length === 0) {
        html += `<div style="padding:16px;color:var(--text-dim);font-size:13px">No matched articles found in database.</div>`;
      } else {
        // Sort by published_at descending
        articles.sort((a, b) => (b.published_at || '').localeCompare(a.published_at || ''));
        for (const a of articles) {
          html += renderArticle(a);
        }
      }

      html += `</div></div>`;
    }

    container.innerHTML = html;
  } catch {
    container.innerHTML = '<div class="empty"><p>Failed to load news.</p></div>';
  }
}

// ── Market ────────────────────────────────────────────────────────────────────

async function loadMarket() {
  const container = document.getElementById('market-content');
  container.innerHTML = skeletonCards(4);
  showProgressBar();

  try {
    const data = await api('GET', '/market');
    container.innerHTML = renderMarketData(data);
  } catch {
    container.innerHTML = '<div class="empty"><p>Failed to load market data. Check API keys.</p></div>';
  } finally {
    hideProgressBar();
  }
}

// ── LLM Market Overview ───────────────────────────────────────────────────────

async function runMarketOverview() {
  if (_overviewRunning) return;
  _overviewRunning = true;

  const btn = document.getElementById('btn-market-overview');
  const container = document.getElementById('market-overview-content');
  btn.disabled = true;
  btn.textContent = 'Generating...';
  container.innerHTML = skeletonText();
  showProgressBar();

  try {
    const data = await api('POST', '/market/analyze');
    container.innerHTML = renderMarketOverview(data);
  } catch (e) {
    container.innerHTML = `<div class="empty"><p>Failed to generate overview: ${escHtml(e.message)}</p></div>`;
  } finally {
    _overviewRunning = false;
    btn.disabled = false;
    btn.textContent = 'Generate AI Overview';
    hideProgressBar();
  }
}

// ── Stock Price Action Analysis ───────────────────────────────────────────────

function _destroyStockCharts() {
  for (const c of _stockCharts) { try { c.remove(); } catch (e) {} }
  _stockCharts = [];
}

async function runStockAnalysis() {
  const input = document.getElementById('stock-ticker-input');
  const ticker = input.value.trim().toUpperCase();
  if (!ticker) return;

  const container = document.getElementById('stock-analysis-content');
  const funContainer = document.getElementById('stock-fundamentals-content');
  const btn = document.getElementById('btn-stock-analyze');
  window._chartType = 'candlestick';
  btn.disabled = true;
  _destroyStockCharts();
  funContainer.innerHTML = '';
  container.innerHTML = skeletonCards(4);
  showProgressBar();

  try {
    const data = await api('GET', `/stock/${ticker}/price-action`);
    container.innerHTML = renderStockAnalysis(data);
    const charts = renderStockCharts(data);
    if (charts) _stockCharts = charts;
    switchChartTab('daily'); // hide non-active panels after charts are initialized

    // Animate score bar fill
    const fillEl = container.querySelector('.score-bar-fill');
    if (fillEl) {
      const pctStr = fillEl.style.width;
      const pct = parseFloat(pctStr) || 0;
      animateScoreBar(fillEl, pct);
    }

    // Load LLM narrative in background — analysis is already rendered
    _loadNarrative(ticker, container);
  } catch (e) {
    container.innerHTML = `<div class="empty"><p>Analysis failed: ${escHtml(e.message)}</p></div>`;
  } finally {
    btn.disabled = false;
    hideProgressBar();
  }
}

async function _loadNarrative(ticker, container) {
  try {
    const resp = await fetch(`/stock/${ticker}/narrative`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const { narrative } = await resp.json();
    if (container.querySelector('#narrative-container')) {
      renderNarrative(narrative);
    }
  } catch (_) {
    if (container.querySelector('#narrative-container')) {
      renderNarrative(null);
    }
  }
}

async function runFundamentals() {
  const input = document.getElementById('stock-ticker-input');
  const ticker = input.value.trim().toUpperCase();
  if (!ticker) return;

  const container = document.getElementById('stock-fundamentals-content');
  const paContainer = document.getElementById('stock-analysis-content');
  const btn = document.getElementById('btn-stock-fundamentals');
  btn.disabled = true;
  paContainer.innerHTML = '';
  _destroyStockCharts();
  container.innerHTML = skeletonCards(4);
  showProgressBar();

  try {
    const data = await api('GET', `/stock/${ticker}/fundamentals`);
    container.innerHTML = renderFundamentals(data);
  } catch (e) {
    container.innerHTML = `<div class="empty"><p>Fundamental analysis failed: ${escHtml(e.message)}</p></div>`;
  } finally {
    btn.disabled = false;
    hideProgressBar();
  }
}

function switchChartTab(tab, btn) {
  for (const t of ['daily', 'weekly', 'indicators']) {
    const panel = document.getElementById(`chart-panel-${t}`);
    if (panel) panel.style.display = t === tab ? '' : 'none';
  }
  if (btn) {
    const bar = btn.closest('.chart-tab-bar');
    if (bar) {
      for (const b of bar.querySelectorAll('.chart-tab')) b.classList.remove('active');
      btn.classList.add('active');
    }
  }
}

function toggleChartFullscreen() {
  const container = document.getElementById('stock-chart-container');
  if (!container) return;
  container.classList.toggle('chart-fullscreen');
  const isFs = container.classList.contains('chart-fullscreen');
  const fsH = window.innerHeight - 60;
  for (const c of _stockCharts) {
    try {
      const el = c.chartElement();
      const pId = el.parentElement?.id || '';
      const normalH = pId === 'chart-daily' ? 500 : pId === 'chart-weekly' ? 400 : pId === 'chart-rsi' ? 100 : pId === 'chart-macd' ? 100 : 400;
      c.applyOptions({ height: isFs ? fsH : normalH });
      c.timeScale().fitContent();
    } catch (_) {}
  }
}

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    const container = document.getElementById('stock-chart-container');
    if (container?.classList.contains('chart-fullscreen')) toggleChartFullscreen();
  }
});

function toggleChartType(btn) {
  if (!window._chartData) return;
  const newType = window._chartType === 'candlestick' ? 'line' : 'candlestick';
  window._chartType = newType;
  btn.textContent = newType === 'candlestick' ? '\u{1D4C1}' : '\u{1D4C1}';
  btn.title = newType === 'candlestick' ? 'Switch to line' : 'Switch to candlestick';
  // Destroy and recreate charts with new type
  _destroyStockCharts();
  const charts = renderStockCharts({ chart_data: window._chartData });
  if (charts) _stockCharts = charts;
  // Re-show the active tab
  const activeTab = document.querySelector('.chart-tab.active');
  if (activeTab) {
    const panel = activeTab.textContent.trim().toLowerCase();
    const tab = panel.includes('daily') ? 'daily' : panel.includes('weekly') ? 'weekly' : 'indicators';
    switchChartTab(tab);
  }
}

// ── Backtest ──────────────────────────────────────────────────────────────────

function btInitTickers() {
  renderBtTickers();
  const inp = document.getElementById('bt-ticker-input');
  if (!inp) return;

  inp.addEventListener('keydown', e => {
    const dd = document.getElementById('bt-autocomplete');
    const items = dd.querySelectorAll('.bt-ac-item');

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      _btAcIdx = Math.min(_btAcIdx + 1, items.length - 1);
      btHighlightAc(items); return;
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      _btAcIdx = Math.max(_btAcIdx - 1, 0);
      btHighlightAc(items); return;
    }
    if (e.key === 'Escape') { btHideAc(); return; }

    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      if (_btAcIdx >= 0 && items[_btAcIdx]) {
        btSelectTicker(items[_btAcIdx].dataset.symbol);
      } else {
        const v = inp.value.trim().toUpperCase().replace(/,/g, '');
        if (v && !btTickers.includes(v)) { btTickers.push(v); renderBtTickers(); }
        inp.value = ''; btHideAc();
      }
      return;
    }
    if (e.key === 'Backspace' && inp.value === '' && btTickers.length) {
      btTickers.pop(); renderBtTickers();
    }
  });

  inp.addEventListener('input', () => {
    clearTimeout(_btAcTimer);
    const q = inp.value.trim();
    if (q.length < 1) { btHideAc(); return; }
    _btAcTimer = setTimeout(() => btFetchSuggestions(q), 300);
  });

  document.addEventListener('click', e => {
    if (!e.target.closest('#bt-ticker-input') && !e.target.closest('#bt-autocomplete')) btHideAc();
  });
}

async function btFetchSuggestions(q) {
  try {
    const data = await api('GET', `/search/tickers?q=${encodeURIComponent(q)}`);
    // Prefer US equities and ETFs; fall back to showing everything
    let results = data.results || [];
    const usOnly = results.filter(r => r.region === 'United States');
    btShowAc(usOnly.length ? usOnly.slice(0, 8) : results.slice(0, 8));
  } catch (_) { btHideAc(); }
}

function btShowAc(results) {
  const dd = document.getElementById('bt-autocomplete');
  if (!results.length) { dd.style.display = 'none'; return; }
  _btAcIdx = -1;
  dd.innerHTML = results.map(r => `
    <div class="bt-ac-item" data-symbol="${escHtml(r.symbol)}" onclick="btSelectTicker('${escHtml(r.symbol)}')">
      <span class="bt-ac-symbol">${escHtml(r.symbol)}</span>
      <span class="bt-ac-name">${escHtml(r.name)}</span>
      <span class="bt-ac-type">${escHtml(r.type)}</span>
    </div>`).join('');
  dd.style.display = 'block';
}

function btHideAc() {
  const dd = document.getElementById('bt-autocomplete');
  if (dd) { dd.style.display = 'none'; _btAcIdx = -1; }
}

function btHighlightAc(items) {
  items.forEach((el, i) => el.classList.toggle('bt-ac-active', i === _btAcIdx));
}

function btSelectTicker(symbol) {
  if (symbol && !btTickers.includes(symbol)) { btTickers.push(symbol); renderBtTickers(); }
  const inp = document.getElementById('bt-ticker-input');
  inp.value = ''; btHideAc(); inp.focus();
}

function renderBtTickers() {
  const wrap = document.getElementById('bt-ticker-tags');
  if (!wrap) return;
  wrap.innerHTML = btTickers.map(t =>
    `<span class="bt-tag">${escHtml(t)}<span class="bt-tag-x" onclick="btRemoveTicker('${escHtml(t)}')">&times;</span></span>`
  ).join('');
}

function btRemoveTicker(t) {
  btTickers = btTickers.filter(x => x !== t);
  renderBtTickers();
}

function btGetStrategies() {
  return [...document.querySelectorAll('.bt-strat-check:checked')].map(c => c.value);
}

function btGetHorizons() {
  return [...document.querySelectorAll('.bt-horizon-check:checked')].map(c => parseInt(c.value));
}

async function runBacktest() {
  const strategies = btGetStrategies();
  const horizons = btGetHorizons();
  if (!btTickers.length) return alert('Add at least one ticker.');
  if (!strategies.length) return alert('Select at least one strategy.');
  if (!horizons.length) return alert('Select at least one horizon.');

  const btn = document.getElementById('btn-backtest');
  const results = document.getElementById('bt-results');
  btn.disabled = true;
  btn.textContent = 'Running\u2026';
  results.innerHTML = `<div class="bt-loading">
    <div class="bt-spinner"></div>
    <div style="color:var(--text-dim);font-size:13px;margin-top:12px;">
      Downloading data &amp; running strategies \u2014 this takes 15\u201330s\u2026
    </div>
  </div>`;
  showProgressBar();

  const payload = {
    tickers: btTickers,
    start: document.getElementById('bt-start').value,
    end: document.getElementById('bt-end').value,
    horizons,
    strategies,
    warmup: 252,
  };

  try {
    const data = await api('POST', '/backtest', payload);
    results.innerHTML = renderBtResults(data);
  } catch (e) {
    results.innerHTML = `<div style="color:var(--red);padding:20px">${escHtml(String(e))}</div>`;
  } finally {
    btn.disabled = false;
    btn.textContent = '\u25b6 Run Backtest';
    hideProgressBar();
  }
}

function btSwitchHorizon(h, btn) {
  document.querySelectorAll('.bt-horizon-panel').forEach(p => p.style.display = 'none');
  document.querySelectorAll('.bt-htab').forEach(b => b.classList.remove('bt-htab-active'));
  document.getElementById('bt-hp-' + h).style.display = '';
  btn.classList.add('bt-htab-active');
}

function btToggleAccordion(head) {
  const body = head.nextElementSibling;
  const arrow = head.querySelector('.bt-accordion-arrow');
  const open = body.style.display !== 'none';
  body.style.display = open ? 'none' : 'block';
  arrow.textContent = open ? '▶' : '▼';
}

// ── Paper Trading ─────────────────────────────────────────────────────────────

async function ptLoad() {
  try {
    const [portfolio, trades] = await Promise.all([
      api('GET', '/paper/portfolio'),
      api('GET', '/paper/trades'),
    ]);
    ptRenderPortfolio(portfolio);
    ptRenderTrades(trades.trades || []);
  } catch (e) {
    console.error('ptLoad failed', e);
  }
}

async function ptScan() {
  const btn = document.getElementById('btn-pt-scan');
  const status = document.getElementById('pt-scan-status');
  btn.disabled = true;
  btn.textContent = 'Scanning\u2026';
  status.style.display = 'block';
  showProgressBar();

  const startTime = Date.now();
  status.innerHTML = `<div class="operation-status"><span class="status-dot"></span><span>Scanning watchlist\u2026 this takes 3-5 minutes. Please wait.</span><span class="elapsed-timer">0:00</span></div>`;
  const timer = setInterval(() => {
    const elapsed = Math.floor((Date.now() - startTime) / 1000);
    const min = Math.floor(elapsed / 60);
    const sec = String(elapsed % 60).padStart(2, '0');
    const el = status.querySelector('.elapsed-timer');
    if (el) el.textContent = `${min}:${sec}`;
  }, 1000);

  try {
    const r = await api('POST', '/paper/scan');
    clearInterval(timer);

    // Summary line
    let html = `<div style="margin-bottom:12px;font-weight:600">Scan complete: ${r.watchlist_size || r.scanned} tickers in watchlist, ${r.scanned} analyzed, ${r.signals} signals, ${r.opened} opened, ${r.skipped} skipped.</div>`;

    // Detailed results per ticker
    const details = r.details || [];
    if (details.length) {
      html += '<div style="display:flex;flex-direction:column;gap:6px">';
      for (const d of details) {
        const action = d.action || '';
        let color = 'var(--text-dim)';
        let icon = '';
        if (action.startsWith('OPENED')) { color = '#3fb950'; icon = '+'; }
        else if (action.startsWith('BLOCKED')) { color = '#d29922'; icon = '!'; }
        else if (action.startsWith('REJECTED')) { color = '#f85149'; icon = 'x'; }
        else if (action.startsWith('NO SIGNAL')) { color = 'var(--text-dim)'; icon = '-'; }
        else if (action.startsWith('SKIPPED')) { color = 'var(--text-dim)'; icon = '~'; }
        else if (action.startsWith('ERROR')) { color = '#f85149'; icon = '!'; }

        const score = d.score != null ? `score: ${d.score}` : '';
        const thresh = d.threshold != null ? ` (need ${d.threshold})` : '';
        const price = d.price ? ` @ $${Number(d.price).toFixed(2)}` : '';

        html += `<div style="padding:8px 12px;border:1px solid var(--border);border-radius:6px;border-left:3px solid ${color}">`;
        const vol = d.volatility;
        const volBadge = vol === 'high' ? '<span style="font-size:10px;font-weight:600;color:#ef4444;background:rgba(239,68,68,0.15);padding:1px 5px;border-radius:3px;margin-left:2px">HIGH VOL</span>'
          : vol === 'medium' ? '<span style="font-size:10px;font-weight:600;color:#eab308;background:rgba(234,179,8,0.15);padding:1px 5px;border-radius:3px;margin-left:2px">MED VOL</span>'
          : '';

        html += `<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">`;
        html += `<strong style="min-width:50px">${escHtml(d.ticker || '?')}</strong>`;
        html += volBadge;
        html += `<span style="font-size:12px;color:var(--text-dim)">${escHtml(d.sector || '')}</span>`;
        if (score) html += `<span style="font-size:12px">${score}${thresh}</span>`;
        if (price) html += `<span style="font-size:12px">${price}</span>`;
        html += `<span style="font-size:12px;color:${color};margin-left:auto;font-weight:600">${escHtml(action)}</span>`;
        html += `</div>`;

        // Show top layers if available
        const layers = d.layers || [];
        if (layers.length) {
          html += `<div style="display:flex;gap:8px;margin-top:6px;flex-wrap:wrap">`;
          for (const l of layers) {
            const lc = l.score > 0 ? '#3fb950' : l.score < 0 ? '#f85149' : 'var(--text-dim)';
            html += `<span style="font-size:11px;color:${lc}">${escHtml(l.name)}: ${l.score > 0 ? '+' : ''}${l.score}</span>`;
          }
          html += '</div>';
        }

        if (d.earnings_warning) {
          html += `<div style="font-size:11px;color:#d29922;margin-top:4px">${escHtml(d.earnings_warning)}</div>`;
        }
        html += '</div>';
      }
      html += '</div>';
    }

    status.innerHTML = html;
    await ptLoad();
  } catch (e) {
    clearInterval(timer);
    status.textContent = 'Scan failed: ' + e.message;
  } finally {
    btn.disabled = false;
    btn.textContent = 'Scan Watchlist';
    hideProgressBar();
  }
}

async function ptUpdate() {
  const btn = document.getElementById('btn-pt-update');
  btn.disabled = true;
  btn.textContent = 'Updating\u2026';
  showProgressBar();
  try {
    const r = await api('POST', '/paper/update');
    showToast(`Updated ${r.updated} positions, closed ${r.closed}`, 'success');
    await ptLoad();
  } catch (e) {
    // error shown by api()
  } finally {
    btn.disabled = false;
    btn.textContent = '\u21bb Update Prices';
    hideProgressBar();
  }
}

async function ptNewsGuard() {
  const btn = document.getElementById('btn-pt-news');
  btn.disabled = true;
  btn.textContent = 'Checking\u2026';
  showProgressBar();
  try {
    const r = await api('POST', '/paper/news-guard');
    const msg = r.positions_closed > 0
      ? `News Guard: closed ${r.positions_closed} positions due to ${r.dangerous_events} dangerous events`
      : `News Guard: ${r.events_scanned} events scanned \u2014 no threats detected`;
    showToast(msg, 'success');
    await ptLoad();
  } catch (e) {
    // error shown by api()
  } finally {
    btn.disabled = false;
    btn.textContent = '\u26a0 Check News';
    hideProgressBar();
  }
}

async function ptCloseTrade(tradeId, ticker) {
  if (!confirm(`Close ${ticker} position at current market price?`)) return;
  try {
    await api('POST', `/paper/trades/${tradeId}/close`);
    showToast(`${ticker} position closed`, 'success');
    await ptLoad();
  } catch (e) {
    // error shown by api()
  }
}

async function ptReset() {
  if (!confirm('Reset portfolio? This will clear ALL trades and restore $100,000 starting capital.')) return;
  try {
    await api('POST', '/paper/reset');
    showToast('Portfolio reset to $100,000', 'success');
    await ptLoad();
  } catch (e) {
    // error shown by api()
  }
}

// ── Trade Journal ─────────────────────────────────────────────────────────────

async function tjLoad() {
  try {
    const [portfolio, tradesRes] = await Promise.all([
      api('GET', '/paper/portfolio'),
      api('GET', '/paper/trades'),
    ]);
    _tjTrades = tradesRes.trades || [];
    tjRenderStats(portfolio);
    tjRenderListInner();
  } catch (e) {
    document.getElementById('tj-list').innerHTML = `<div class="tj-empty">Failed to load trades</div>`;
  }
}

function tjGetFiltered() {
  if (_tjFilter === 'all') return _tjTrades;
  if (_tjFilter === 'open') return _tjTrades.filter(t => t.status === 'open');
  if (_tjFilter === 'closed') return _tjTrades.filter(t => t.status === 'closed');
  if (_tjFilter === 'wins') return _tjTrades.filter(t => t.status === 'closed' && (t.realized_pnl || 0) > 0);
  if (_tjFilter === 'losses') return _tjTrades.filter(t => t.status === 'closed' && (t.realized_pnl || 0) <= 0);
  return _tjTrades;
}

function tjRenderListInner() {
  tjRenderList(tjGetFiltered(), _tjFilter, _tjExpandedId);
}

function tjFilterHandler(f) {
  _tjFilter = f;
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  const btn = document.querySelector(`.filter-btn[data-filter="${f}"]`);
  if (btn) btn.classList.add('active');
  tjRenderListInner();
}

async function tjToggle(tradeId) {
  const detail = document.getElementById(`tj-detail-${tradeId}`);
  if (_tjExpandedId === tradeId) {
    detail.classList.remove('open');
    _tjExpandedId = null;
    return;
  }
  // Collapse previous
  if (_tjExpandedId !== null) {
    const prev = document.getElementById(`tj-detail-${_tjExpandedId}`);
    if (prev) prev.classList.remove('open');
  }
  _tjExpandedId = tradeId;
  detail.innerHTML = '<div style="padding:20px;text-align:center;color:var(--text-dim)">Loading analysis...</div>';
  detail.classList.add('open');

  try {
    const data = await api('GET', `/paper/trades/${tradeId}`);
    detail.innerHTML = tjRenderDetail(data);
  } catch (e) {
    detail.innerHTML = '<div style="padding:16px;color:#f85149">Failed to load trade details</div>';
  }
}

// ── Scan History ─────────────────────────────────────────────────────────────

async function shLoad() {
  const list = document.getElementById('sh-list');
  const detail = document.getElementById('sh-detail');
  detail.style.display = 'none';
  list.style.display = '';

  try {
    const res = await api('GET', '/paper/scans?limit=30');
    const scans = res.scans || [];
    if (!scans.length) {
      list.innerHTML = '<div class="empty"><p>No scans yet — run "Scan Watchlist" on the Paper Trading tab.</p></div>';
      return;
    }

    let html = '<div style="display:flex;flex-direction:column;gap:8px">';
    for (const s of scans) {
      const date = s.created_at ? new Date(s.created_at.replace(' ', 'T') + 'Z').toLocaleString() : '';
      const openedColor = s.opened > 0 ? '#22c55e' : 'var(--text-dim)';
      const signalColor = s.signals > 0 ? '#eab308' : 'var(--text-dim)';
      html += `<div onclick="shViewScan(${s.id})" style="padding:12px 16px;border:1px solid var(--border);border-radius:8px;cursor:pointer;transition:border-color 0.15s" onmouseover="this.style.borderColor='var(--accent)'" onmouseout="this.style.borderColor='var(--border)'">
        <div style="display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap">
          <div>
            <span style="font-weight:600">Scan #${s.id}</span>
            <span style="font-size:12px;color:var(--text-dim);margin-left:8px">${date}</span>
          </div>
          <div style="display:flex;gap:16px;font-size:13px">
            <span>${s.watchlist_size || s.scanned} tickers</span>
            <span style="color:${signalColor}">${s.signals} signals</span>
            <span style="color:${openedColor}">${s.opened} opened</span>
            <span style="color:var(--text-dim)">${s.skipped} skipped</span>
          </div>
        </div>
      </div>`;
    }
    html += '</div>';
    list.innerHTML = html;
  } catch (e) {
    list.innerHTML = `<div class="empty"><p>Failed to load scan history</p></div>`;
  }
}

async function shViewScan(scanId) {
  const list = document.getElementById('sh-list');
  const detail = document.getElementById('sh-detail');
  list.style.display = 'none';
  detail.style.display = '';
  detail.innerHTML = '<div class="empty"><p>Loading scan details...</p></div>';

  try {
    const data = await api('GET', `/paper/scans/${scanId}`);
    const date = data.created_at ? new Date(data.created_at.replace(' ', 'T') + 'Z').toLocaleString() : '';
    const details = data.details || [];

    let html = `<div style="margin-bottom:16px;display:flex;align-items:center;gap:12px;flex-wrap:wrap">
      <button class="btn btn-secondary" onclick="shLoad()" style="font-size:12px">Back to list</button>
      <span style="font-weight:600;font-size:15px">Scan #${data.id}</span>
      <span style="font-size:12px;color:var(--text-dim)">${date}</span>
      <span style="font-size:12px">${data.scanned} analyzed, ${data.signals} signals, ${data.opened} opened</span>
    </div>`;

    html += '<div style="display:flex;flex-direction:column;gap:6px">';
    for (const d of details) {
      const action = d.action || '';
      let borderColor = 'var(--border)';
      if (action.includes('OPENED')) borderColor = '#22c55e';
      else if (action.includes('BLOCKED')) borderColor = '#eab308';
      else if (action.includes('REJECTED')) borderColor = '#ef4444';

      const score = d.score != null ? `score: ${d.score}` : '';
      const thresh = d.threshold != null ? ` (need ${d.threshold})` : '';
      const price = d.price ? ` @ $${Number(d.price).toFixed(2)}` : '';
      const dir = d.direction ? ` [${d.direction.toUpperCase()}]` : '';

      html += `<div style="padding:10px 14px;border:1px solid var(--border);border-radius:6px;border-left:3px solid ${borderColor}">`;
      const vol = d.volatility;
      const volBadge = vol === 'high' ? '<span style="font-size:10px;font-weight:600;color:#ef4444;background:rgba(239,68,68,0.15);padding:1px 5px;border-radius:3px;margin-left:2px">HIGH VOL</span>'
        : vol === 'medium' ? '<span style="font-size:10px;font-weight:600;color:#eab308;background:rgba(234,179,8,0.15);padding:1px 5px;border-radius:3px;margin-left:2px">MED VOL</span>'
        : '';

      html += `<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">`;
      html += `<strong style="min-width:55px">${escHtml(d.ticker || '?')}</strong>`;
      html += volBadge;
      html += `<span style="font-size:12px;color:var(--text-dim)">${escHtml(d.sector || '')}</span>`;
      if (score) html += `<span style="font-size:12px">${score}${thresh}</span>`;
      if (price) html += `<span style="font-size:12px">${price}</span>`;
      html += `<span style="font-size:12px;color:${borderColor};margin-left:auto;font-weight:600">${escHtml(action)}${dir}</span>`;
      html += `</div>`;

      // Layer scores
      const layers = d.layers || [];
      if (layers.length) {
        html += `<div style="display:flex;gap:8px;margin-top:6px;flex-wrap:wrap">`;
        for (const l of layers) {
          const lc = l.score > 0 ? '#22c55e' : l.score < 0 ? '#ef4444' : 'var(--text-dim)';
          html += `<span style="font-size:11px;color:${lc}">${escHtml(l.name)}: ${l.score > 0 ? '+' : ''}${l.score}</span>`;
        }
        html += '</div>';
      }

      if (d.earnings_warning) {
        html += `<div style="font-size:11px;color:#eab308;margin-top:4px">${escHtml(d.earnings_warning)}</div>`;
      }
      html += '</div>';
    }
    html += '</div>';
    detail.innerHTML = html;
  } catch (e) {
    detail.innerHTML = `<div class="empty"><p>Failed to load scan #${scanId}</p></div>`;
  }
}

// ── Window Attachments ────────────────────────────────────────────────────────
// Every function referenced by onclick in the HTML must be on window.

Object.assign(window, {
  showPanel,
  loadMarket,
  runMarketOverview,
  runScan,
  runDeepAnalysis,
  loadEvents,
  viewEvent,
  loadReport,
  loadSectors,
  loadNews,
  runStockAnalysis,
  runFundamentals,
  switchChartTab,
  runFullAnalysis,
  runBacktest,
  btRemoveTicker,
  btSelectTicker,
  btSwitchHorizon,
  btToggleAccordion,
  ptLoad,
  ptScan,
  ptUpdate,
  ptNewsGuard,
  ptCloseTrade,
  ptReset,
  tjFilter: tjFilterHandler,
  tjToggle,
  toggleEventGroup,
  goBack,
  shLoad,
  shViewScan,
  toggleChartFullscreen,
  toggleChartType,
});

// ── Init ──────────────────────────────────────────────────────────────────────

function init() {
  initTabs();
  initFilterButtons();
  checkHealth();
  setInterval(checkHealth, 30000);
  showPanel('market');
  btInitTickers();
  initScrollReveals();
}

init();
