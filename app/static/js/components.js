/**
 * components.js — All render functions, skeleton builders, and toast system.
 *
 * Internal helpers (not exported): changeClass, formatPct, formatTimestamp
 * Exported helpers: escHtml, tag, tickerTag
 * Exported skeletons: skeletonCards, skeletonRows, skeletonText
 * Exported toast: showToast
 * Exported render functions: renderEventDetail, renderReport, renderArticle,
 *   renderStockAnalysis, renderStockCharts, renderBtResults, renderMarketData,
 *   renderMarketOverview, ptRenderPortfolio, ptRenderTrades, tjRenderStats,
 *   tjRenderList, tjRenderDetail
 */

// ── Chart scroll fix ─────────────────────────────────────────────────────────
// Lightweight Charts captures wheel/trackpad events and calls preventDefault(),
// blocking page scrolling. This document-level capture-phase listener fires
// BEFORE the chart's own listeners and stops the event from reaching them.
// Since we don't call preventDefault(), the browser scrolls the page normally.
// Chart interactivity (crosshair, hover, click-drag pan) is unaffected.
document.addEventListener('wheel', function(e) {
  if (e.target.closest && e.target.closest('.tv-lightweight-charts')) {
    e.stopPropagation();
  }
}, true);

// ── Internal helpers ──────────────────────────────────────────────────────────

export function escHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function changeClass(pct) {
  if (!pct) return '';
  const num = parseFloat(String(pct).replace('%', ''));
  return num > 0 ? 'positive' : num < 0 ? 'negative' : '';
}

function formatPct(pct) {
  if (!pct) return 'N/A';
  const s = String(pct);
  return s.includes('%') ? s : s + '%';
}

function formatTimestamp(ts) {
  if (!ts) return '';
  // AV format: "20260331T143000" → readable
  if (ts.length >= 15 && ts.includes('T')) {
    const y = ts.slice(0, 4), mo = ts.slice(4, 6), d = ts.slice(6, 8);
    const h = ts.slice(9, 11), mi = ts.slice(11, 13);
    return `${y}-${mo}-${d} ${h}:${mi}`;
  }
  return ts.slice(0, 16);
}

// ── Exported helpers ──────────────────────────────────────────────────────────

export function tag(value, cls) {
  return `<span class="tag ${cls || value}">${value}</span>`;
}

export function tickerTag(t) {
  return `<span class="ticker">${t}</span>`;
}

// ── Skeleton generators ───────────────────────────────────────────────────────

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

// ── Toast system ──────────────────────────────────────────────────────────────

export function showToast(msg, type = 'error') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `${escHtml(msg)}<div class="toast-progress"></div>`;

  const M = window.Motion;
  if (M && M.animate) {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(20px)';
    container.appendChild(toast);
    M.animate(toast, { opacity: 1, transform: 'translateX(0)' },
      { duration: 0.3, easing: M.spring ? M.spring(0.3) : 'ease-out' });
  } else {
    container.appendChild(toast);
  }

  setTimeout(() => {
    if (M && M.animate) {
      M.animate(toast, { opacity: 0, transform: 'translateX(20px)' }, { duration: 0.2 })
        .then(() => toast.remove());
    } else {
      toast.remove();
    }
  }, 4000);
}

// ── renderEventDetail ─────────────────────────────────────────────────────────

/**
 * Renders event detail HTML and sets it on #event-detail-content.
 * @param {Object} data - API response from /events/:id/analyze
 */
export function renderEventDetail(data) {
  const container = document.getElementById('event-detail-content');
  const event = data.event || {};
  const analysis = data.analysis || {};

  let html = `<span class="back-link" onclick="goBack()">&#8592; Back</span>`;
  html += `<h2 style="margin-bottom:8px">${escHtml(event.title)}</h2>`;
  html += `<div class="meta">
    <span>Category: <strong>${escHtml(event.category || '')}</strong></span>
    <span>Severity: ${tag(event.severity || '')}</span>
    ${analysis.signal_type ? `<span>Signal: ${tag(analysis.signal_type)}</span>` : ''}
    <span>Duration: <strong>${data.duration_seconds || '?'}s</strong></span>
  </div>`;
  html += `<p style="color:var(--text-dim);margin-bottom:20px">${escHtml(event.summary || '')}</p>`;

  if (analysis.signal_reasoning) {
    html += `<div class="card"><h3>Signal Reasoning</h3><p>${escHtml(analysis.signal_reasoning)}</p></div>`;
  }

  // Causal chains
  if (analysis.causal_chains && analysis.causal_chains.length) {
    html += `<div class="report-section"><h3>Causal Chains</h3><div class="chain-tree">`;
    for (const c of analysis.causal_chains) {
      html += `<div class="chain-item">
        <span class="order">${c.order || '?'}°</span>
        <span>${escHtml(c.chain)}</span>
        <span class="tag ${c.confidence}">${c.confidence}</span>
      </div>`;
    }
    html += `</div></div>`;
  }

  // Sectors
  if (analysis.sectors && analysis.sectors.length) {
    html += `<div class="report-section"><h3>Sector Impacts</h3>`;
    for (const s of analysis.sectors) {
      html += `<div class="sector-bar">
        <span class="name">${escHtml(s.name)}</span>
        <span class="signal">${tag(s.direction)}</span>
        <span class="reason">${escHtml(s.reason || '')}</span>
      </div>`;
    }
    html += `</div>`;
  }

  // Top picks
  if (analysis.top_picks && analysis.top_picks.length) {
    html += `<div class="report-section"><h3>Top Picks</h3>`;
    for (const p of analysis.top_picks) {
      html += `<div class="card">
        <h3>${tickerTag(p.ticker)} ${tag(p.action)}</h3>
        <p>${escHtml(p.reason || '')}</p>
        ${p.risk ? `<p style="color:var(--yellow);font-size:12px">Risk: ${escHtml(p.risk)}</p>` : ''}
      </div>`;
    }
    html += `</div>`;
  }

  // Avoid
  if (analysis.avoid && analysis.avoid.length) {
    html += `<div class="report-section"><h3>Avoid</h3>`;
    for (const a of analysis.avoid) {
      html += `<div class="card"><h3 style="color:var(--red)">${tickerTag(a.ticker)}</h3><p>${escHtml(a.reason || '')}</p></div>`;
    }
    html += `</div>`;
  }

  // Ticker data fallback
  if (!analysis.top_picks && data.ticker_data && Object.keys(data.ticker_data).length) {
    html += `<div class="report-section"><h3>Tickers From News (Alpha Vantage)</h3><table>
      <thead><tr><th>Ticker</th><th>Sentiment</th><th>Score</th><th>Mentions</th></tr></thead><tbody>`;
    for (const [ticker, td] of Object.entries(data.ticker_data).slice(0, 8)) {
      html += `<tr><td>${tickerTag(ticker)}</td><td>${tag(td.sentiment_label)}</td><td>${td.avg_sentiment}</td><td>${td.mentions}</td></tr>`;
    }
    html += `</tbody></table></div>`;
  }

  container.innerHTML = html;
}

// ── renderReport ──────────────────────────────────────────────────────────────

/**
 * Renders a synthesis report and returns the HTML string.
 * The caller is responsible for inserting into the DOM.
 * @param {Object} data - API response from /report or /analyze
 * @returns {string} HTML string
 */
export function renderReport(data) {
  let html = '';

  // Sentiment banner
  const sentiment = data.overall_sentiment || 'unknown';
  html += `<div class="sentiment-banner ${sentiment}">
    ${sentiment.replace(/_/g, ' ').toUpperCase()}
    <span style="font-size:13px;font-weight:400;margin-left:12px">Confidence: ${data.confidence || '?'}</span>
  </div>`;

  if (data.events_analyzed) {
    html += `<div class="meta"><span>Events analyzed: <strong>${data.events_analyzed}</strong></span></div>`;
  }

  // Key themes
  if (data.key_themes && data.key_themes.length) {
    html += `<div class="report-section"><h3>Key Themes</h3>`;
    for (const t of data.key_themes) {
      html += `<div class="card">
        <h3>${tag(t.impact)} ${escHtml(t.theme)}</h3>
        <p>${escHtml(t.description || '')}</p>
      </div>`;
    }
    html += `</div>`;
  }

  // Sector outlook
  if (data.sector_outlook && data.sector_outlook.length) {
    html += `<div class="report-section"><h3>Sector Outlook</h3>`;
    for (const s of data.sector_outlook) {
      html += `<div class="sector-bar">
        <span class="name">${escHtml(s.sector)}</span>
        <span class="signal">${tag(s.signal)}</span>
        <span class="reason">${escHtml(s.reason || '')}</span>
      </div>`;
    }
    html += `</div>`;
  }

  // Reinforcing signals
  if (data.reinforcing_signals && data.reinforcing_signals.length) {
    html += `<div class="report-section"><h3>Reinforcing Signals</h3><ul class="signal-list reinforcing">`;
    for (const r of data.reinforcing_signals) html += `<li>${escHtml(r)}</li>`;
    html += `</ul></div>`;
  }

  // Conflicting signals
  if (data.conflicting_signals && data.conflicting_signals.length) {
    html += `<div class="report-section"><h3>Conflicting Signals</h3><ul class="signal-list conflicting">`;
    for (const c of data.conflicting_signals) html += `<li>${escHtml(c)}</li>`;
    html += `</ul></div>`;
  }

  // Top picks
  if (data.top_picks && data.top_picks.length) {
    html += `<div class="report-section"><h3>Top Stock Picks</h3>`;
    for (const p of data.top_picks) {
      html += `<div class="card">
        <h3>${tickerTag(p.ticker)} ${tag(p.action)}</h3>
        <p>${escHtml(p.thesis || p.reason || '')}</p>
        ${p.risk ? `<p style="color:var(--yellow);font-size:12px">Risk: ${escHtml(p.risk)}</p>` : ''}
      </div>`;
    }
    html += `</div>`;
  }

  // Watchlist
  if (data.watchlist && data.watchlist.length) {
    html += `<div class="report-section"><h3>Watchlist</h3><ul class="signal-list watchlist">`;
    for (const w of data.watchlist) html += `<li>${escHtml(w)}</li>`;
    html += `</ul></div>`;
  }

  return html;
}

// ── renderArticle ─────────────────────────────────────────────────────────────

/**
 * Renders a single news article card as an HTML string.
 * @param {Object} a - Article object
 * @returns {string} HTML string
 */
export function renderArticle(a) {
  const tickers = Object.entries(a.ticker_sentiments || {}).slice(0, 5);
  const tickerHtml = tickers.map(([t, s]) => {
    return `<span class="ticker" style="font-size:10px">${t}</span>`;
  }).join(' ');

  const authors = (a.authors || []).join(', ');
  const sentCls = (a.overall_sentiment_label || '').toLowerCase().includes('bull') ? 'bullish'
    : (a.overall_sentiment_label || '').toLowerCase().includes('bear') ? 'bearish' : 'neutral';

  const imgHtml = a.banner_image
    ? `<img class="article-thumb" src="${escHtml(a.banner_image)}" alt="" loading="lazy" onerror="this.style.display='none'">`
    : '';

  return `<div class="article-item">
    ${imgHtml}
    <div class="article-body">
      <h4><a href="${escHtml(a.url || '#')}" target="_blank" rel="noopener">${escHtml(a.title)}</a></h4>
      <div class="article-meta">
        <span>${escHtml(a.source || '')}</span>
        ${authors ? `<span>${escHtml(authors)}</span>` : ''}
        <span>${formatTimestamp(a.published_at)}</span>
        <span class="tag ${sentCls}" style="font-size:10px">${escHtml(a.overall_sentiment_label || '')}</span>
      </div>
      <div class="article-summary">${escHtml((a.summary || '').slice(0, 200))}</div>
      ${tickerHtml ? `<div class="article-tickers">${tickerHtml}</div>` : ''}
    </div>
  </div>`;
}

// ── renderStockAnalysis ───────────────────────────────────────────────────────

/**
 * Renders the full stock price action analysis page as an HTML string.
 * Updated colors per design spec.
 * @param {Object} data - API response from /stock/:ticker/price-action
 * @returns {string} HTML string
 */
export function renderStockAnalysis(data) {
  const q = data.quote || {};
  const s = data.score || {};
  const cls = changeClass(q.change_percent);
  const sigCls = s.signal || 'neutral';

  // Score bar percentage (map -max..+max to 0..100)
  const maxScore = s.max_score || 25;
  const pct = Math.round(((s.total_score || 0) + maxScore) / (maxScore * 2) * 100);
  const _bt = s.buy_threshold || 4;
  // Updated colors: green=#22c55e, red=#ef4444, yellow=#eab308
  const barColor = s.total_score >= _bt ? '#22c55e' : s.total_score <= -_bt ? '#ef4444' : '#eab308';

  let html = '';

  // ── Header ──
  const ext = data.extended_hours;
  let extHtml = '';
  if (ext && ext.session && ext.session !== 'regular') {
    const extCls = ext.change_percent >= 0 ? 'positive' : 'negative';
    const extSign = ext.ext_change >= 0 ? '+' : '';
    extHtml = `<span class="ext-hours" style="font-size:13px;color:var(--text-dim);margin-left:8px">
      ${ext.session === 'pre-market' ? 'Pre-Market' : 'After-Hours'}:
      <span class="change ${extCls}" style="font-size:13px">$${ext.price.toFixed(2)} (${extSign}${ext.ext_change_percent?.toFixed(2) || '0.00'}%)</span>
    </span>`;
  }

  html += `<div class="stock-header">
    <span class="ticker">${escHtml(data.ticker)}</span>
    <span class="name">${escHtml(data.name || '')} ${data.sector ? '· ' + escHtml(data.sector) : ''}</span>
    <span class="price change ${cls}">$${escHtml(q.price || 'N/A')} (${escHtml(q.change_percent || 'N/A')})</span>
    ${extHtml}
    <span class="signal-badge ${sigCls}">${(s.signal || 'neutral').replace('_', ' ')}</span>
  </div>`;

  // Market regime context
  const mr = data.market_regime;
  if (mr) {
    // Updated colors: green=#22c55e, red=#ef4444, yellow=#eab308
    const mrColor = mr.regime === 'risk_on' ? '#22c55e' : mr.regime === 'risk_off' ? '#ef4444' : '#eab308';
    html += `<div style="display:flex;align-items:center;gap:8px;margin-top:4px;font-size:11px;color:var(--text-dim)">
      <span>Market: <strong style="color:${mrColor}">${escHtml(mr.label)}</strong></span>
      <span>${mr.signals.slice(0, 2).map(s => escHtml(s)).join(' · ')}</span>
    </div>`;
  }

  // ── Score bar ──
  const buyThresh = s.buy_threshold || 4;
  const volGate = s.volume_gate || '';
  html += `<div class="score-bar-container">
    <span>Confluence Score: <strong>${s.total_score || 0}</strong> / ${s.max_score || 18}
      <span style="font-size:11px;color:var(--text-dim);margin-left:8px">buy ≥ ${buyThresh}${volGate ? ' (' + volGate + ')' : ''}</span>
    </span>
    <div class="score-bar"><div class="score-bar-fill" style="width:${pct}%;background:${barColor}"></div></div>
  </div>`;

  // ── Trade Setup (entry, stop, exit) ──
  const ts = data.trade_setup;
  if (ts && ts.viable !== false) {
    const dirColor = ts.direction === 'short' ? '#ef4444' : '#22c55e';
    const dirLabel = ts.direction === 'short' ? 'SELL / SHORT' : 'BUY / LONG';
    const stopLabel = ts.stop_type === 'support' ? 'Support' : ts.stop_type === 'resistance' ? 'Resistance' : 'ATR';

    html += `<div class="market-section" style="margin-top:12px;padding:14px 16px;border-left:3px solid ${dirColor}">
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:10px">
        <span style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;color:var(--text-dim)">Trade Setup</span>
        <span style="font-size:13px;font-weight:700;color:${dirColor};padding:2px 10px;border:1px solid ${dirColor};border-radius:4px">${dirLabel}</span>
      </div>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;font-size:13px">
        <div><div style="font-size:10px;text-transform:uppercase;color:var(--text-dim);margin-bottom:2px">Entry</div><strong>$${ts.entry.toFixed(2)}</strong></div>
        <div><div style="font-size:10px;text-transform:uppercase;color:var(--text-dim);margin-bottom:2px">Stop Loss <span style="font-size:9px">[${stopLabel}]</span></div><strong style="color:#ef4444">$${ts.stop.toFixed(2)}</strong></div>
        <div><div style="font-size:10px;text-transform:uppercase;color:var(--text-dim);margin-bottom:2px">Exit</div><strong style="color:var(--text-dim)">Trailing stop</strong></div>
        <div><div style="font-size:10px;text-transform:uppercase;color:var(--text-dim);margin-bottom:2px">Risk/Share</div><strong>$${ts.risk_per_share.toFixed(2)}</strong></div>
        ${ts.atr ? `<div><div style="font-size:10px;text-transform:uppercase;color:var(--text-dim);margin-bottom:2px">ATR (14)</div><strong>$${ts.atr.toFixed(2)}</strong></div>` : ''}
      </div>
    </div>`;
  }

  // ── Strategy Signals (right after score bar) ──
  const stratSigsEarly = data.strategy_signals || {};
  const stratKeysEarly = Object.keys(stratSigsEarly);
  if (stratKeysEarly.length) {
    html += `<div class="market-section" style="margin-top:12px;padding:12px 16px">
      <div style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;color:var(--text-dim);margin-bottom:10px">
        Validated Strategy Signals
      </div>
      <div class="strat-signal-row">`;
    for (const k of stratKeysEarly) {
      const st = stratSigsEarly[k];
      const fired = st.fired;
      const sig = st.signal || 'no signal';
      const cls = fired ? 'signal-badge buy' : 'signal-badge neutral';
      html += `<div class="strat-signal-card ${fired ? 'fired' : 'unfired'}">
        <span class="strat-signal-name">${escHtml(st.name)}</span>
        <span class="${cls}" style="font-size:11px">${fired ? sig.replace('_', ' ') : 'no signal'}</span>
      </div>`;
    }
    html += `</div></div>`;
  }

  // ── Charts (tabbed) ──
  const wTrend = data.weekly_structure?.trend || 'ranging';
  const dTrend = data.daily_structure?.trend || 'ranging';
  const wBos = data.weekly_structure?.bos ? ` | BOS: ${data.weekly_structure.bos.type}` : '';
  const dBos = data.daily_structure?.bos ? ` | BOS: ${data.daily_structure.bos.type}` : '';
  const dChoch = data.daily_structure?.choch ? ` | CHoCH: ${data.daily_structure.choch.type}` : '';

  html += `<div class="chart-container" style="margin-top:16px" id="stock-chart-container">
    <div class="chart-tab-bar">
      <button class="chart-tab active" onclick="switchChartTab('daily',this)">Daily</button>
      <button class="chart-tab" onclick="switchChartTab('weekly',this)">Weekly</button>
      <button class="chart-tab" onclick="switchChartTab('indicators',this)">RSI &amp; MACD</button>
      <span style="flex:1"></span>
      <button class="chart-tool-btn" onclick="toggleChartType(this)" title="Switch candlestick / line">&#x1D4C1;</button>
      <button class="chart-tool-btn" onclick="toggleChartFullscreen()" title="Expand chart">&#x26F6;</button>
    </div>
    <div id="chart-panel-daily" class="chart-panel">
      <div class="chart-label">Daily Structure <span class="trend-tag ${dTrend}">${dTrend}${dBos}${dChoch}</span></div>
      <div id="chart-daily" style="height:340px"></div>
    </div>
    <div id="chart-panel-weekly" class="chart-panel">
      <div class="chart-label">Weekly Structure <span class="trend-tag ${wTrend}">${wTrend}${wBos}</span></div>
      <div id="chart-weekly" style="height:340px"></div>
    </div>
    <div id="chart-panel-indicators" class="chart-panel">
      <div class="chart-label">RSI (14)</div>
      <div id="chart-rsi" style="height:150px"></div>
      <div class="chart-label" style="margin-top:1px">MACD (12, 26, 9)</div>
      <div id="chart-macd" style="height:150px"></div>
    </div>
  </div>`;

  // ── Score Breakdown ──
  const layers = s.layers || [];
  html += '<div class="market-grid" style="margin-top:20px">';
  for (const layer of layers) {
    const scoreCls = layer.score > 0 ? 'pos' : layer.score < 0 ? 'neg' : 'zero';
    html += `<div class="market-section score-card">
      <div class="layer-name">${escHtml(layer.name)}</div>
      <div class="layer-score ${scoreCls}">${layer.score > 0 ? '+' : ''}${layer.score}</div>
      <div class="layer-reason">${escHtml(layer.reasoning)}</div>
    </div>`;
  }
  // Alignment card
  const align = s.alignment || {};
  if (align.score !== undefined) {
    const aCls = align.score > 0 ? 'pos' : align.score < 0 ? 'neg' : 'zero';
    html += `<div class="market-section score-card">
      <div class="layer-name">TF Alignment</div>
      <div class="layer-score ${aCls}">${align.score > 0 ? '+' : ''}${align.score}</div>
      <div class="layer-reason">${escHtml(align.reasoning || '')}</div>
    </div>`;
  }
  html += '</div>';

  // ── Risk/Reward + ATR ──
  const rr = s.risk_reward || {};
  if (rr.ratio !== null && rr.ratio !== undefined) {
    // Updated colors: green=#22c55e, yellow=#eab308, red=#ef4444
    const rrColor = rr.assessment === 'excellent' ? '#22c55e' : rr.assessment === 'favorable' ? '#22c55e'
      : rr.assessment === 'marginal' ? '#eab308' : '#ef4444';
    const atrVal = data.atr ? `ATR(14): $${data.atr.toFixed(2)}` : '';
    html += `<div class="market-section" style="margin-top:16px;padding:12px 16px">
      <div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap">
        <div style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;color:var(--text-dim)">Risk / Reward</div>
        <span style="font-size:13px">Support: <strong>$${rr.nearest_support || '—'}</strong> (${rr.risk_pct || '—'}% risk)</span>
        <span style="font-size:13px">Resistance: <strong>$${rr.nearest_resistance || '—'}</strong> (${rr.reward_pct || '—'}% reward)</span>
        <span style="font-size:14px;font-weight:700;color:${rrColor}">${rr.ratio}:1 R:R (${rr.assessment})</span>
        ${atrVal ? `<span style="font-size:11px;color:var(--text-dim);margin-left:auto">${atrVal}</span>` : ''}
      </div>
    </div>`;
  }

  // ── Detected Gaps ──
  const detectedGaps = data.gaps || [];
  if (detectedGaps.length) {
    html += '<div class="market-section" style="margin-top:16px"><h3>Detected Gaps</h3>';
    for (const g of detectedGaps.slice(-5)) {
      const gCls = g.direction === 'bullish' ? 'positive' : 'negative';
      const thru = g.through_level ? ` through ${g.through_level.type} $${g.through_level.price}` : '';
      html += `<div class="mover-row">
        <span class="ticker-name">${g.type.replace('_', ' ')}</span>
        <span>${tag(g.direction, gCls)}</span>
        <span style="font-size:12px;color:var(--text-dim)">${g.gap_pct}%${thru}</span>
        <span class="date">${escHtml(g.date)}</span>
      </div>`;
    }
    html += '</div>';
  }

  // ── Detected Patterns ──
  const patterns = data.patterns || [];
  if (patterns.length) {
    html += '<div class="market-section" style="margin-top:16px"><h3>Detected Patterns</h3>';
    for (const p of patterns.slice(-5)) {
      const pCls = p.direction === 'bullish' ? 'positive' : p.direction === 'bearish' ? 'negative' : '';
      html += `<div class="mover-row">
        <span class="ticker-name">${escHtml(p.name.replace(/_/g, ' '))}</span>
        <span>${tag(p.direction, pCls)}</span>
        <span class="date">${escHtml(p.date)}</span>
      </div>`;
    }
    html += '</div>';
  }

  // ── LLM Narrative (placeholder — loaded async) ──
  html += '<div id="narrative-container" style="margin-top:20px">';
  if (data.narrative) {
    html += _renderNarrativeContent(data.narrative);
  } else {
    html += '<div class="market-overview-box" style="opacity:0.6"><p style="color:var(--muted);font-size:13px">Loading AI narrative...</p></div>';
  }
  html += '</div>';

  // ── Institutional Holdings ──
  const inst = data.institutional;
  if (inst && (inst.holdings || inst.totalInstitutionalOwnership)) {
    const ownPct = inst.totalInstitutionalOwnership || 'N/A';
    const increased = inst.holdersWithIncreasedPositions || inst.holders_with_increased_holdings || '?';
    const decreased = inst.holdersWithDecreasedPositions || inst.holders_with_decreased_holdings || '?';
    const holders = inst.holdings || [];

    html += `<div class="market-section" style="margin-top:16px">
      <div style="cursor:pointer;display:flex;justify-content:space-between;align-items:center" onclick="this.parentElement.querySelector('.collapsible-body').style.display = this.parentElement.querySelector('.collapsible-body').style.display === 'none' ? 'block' : 'none'; this.querySelector('.collapse-arrow').textContent = this.parentElement.querySelector('.collapsible-body').style.display === 'none' ? '▶' : '▼'">
        <div class="section-title" style="margin:0">Institutional Holdings</div>
        <span class="collapse-arrow" style="color:var(--text-dim)">▶</span>
      </div>
      <div class="collapsible-body" style="display:none;margin-top:12px">
        <div style="font-size:13px;color:var(--text-dim);margin-bottom:12px">
          ${escHtml(String(ownPct))}% Institutional Ownership | ${escHtml(String(increased))} holders increasing | ${escHtml(String(decreased))} holders decreasing
        </div>
        <div class="pt-table-wrap">
          <table class="pt-table">
            <thead><tr>
              <th>Holder</th><th>Shares Held</th><th>Change %</th><th>Change Type</th>
            </tr></thead>
            <tbody>`;
    for (const h of holders.slice(0, 10)) {
      const name = h.investor || h.name || '';
      const shares = Number(h.shares || h.sharesHeld || 0);
      const changePct = h.change_percentage || h.changePercentage || '0';
      const changeType = (h.change_type || h.changeType || '').toLowerCase();
      // Updated colors: green=#22c55e, red=#ef4444
      const typeCls = changeType.includes('increase') ? 'color:#22c55e' : changeType.includes('decrease') ? 'color:#ef4444' : '';
      html += `<tr>
        <td>${escHtml(name)}</td>
        <td>${shares.toLocaleString()}</td>
        <td>${escHtml(String(changePct))}%</td>
        <td style="${typeCls};font-weight:600">${escHtml(changeType)}</td>
      </tr>`;
    }
    html += `</tbody></table></div></div></div>`;
  }

  // ── Insider Transactions ──
  const insiderTxns = (data.insider_transactions || []).filter(t => t.share_price !== '0.0' && t.share_price !== '0' && t.share_price !== 0);
  if (insiderTxns.length) {
    html += `<div class="market-section" style="margin-top:16px">
      <div style="cursor:pointer;display:flex;justify-content:space-between;align-items:center" onclick="this.parentElement.querySelector('.collapsible-body').style.display = this.parentElement.querySelector('.collapsible-body').style.display === 'none' ? 'block' : 'none'; this.querySelector('.collapse-arrow').textContent = this.parentElement.querySelector('.collapsible-body').style.display === 'none' ? '▶' : '▼'">
        <div class="section-title" style="margin:0">Insider Transactions</div>
        <span class="collapse-arrow" style="color:var(--text-dim)">▶</span>
      </div>
      <div class="collapsible-body" style="display:none;margin-top:12px">
        <div class="pt-table-wrap">
          <table class="pt-table">
            <thead><tr>
              <th>Date</th><th>Executive</th><th>Title</th><th>Type</th><th>Shares</th><th>Price</th>
            </tr></thead>
            <tbody>`;
    for (const t of insiderTxns) {
      const txnDate = t.transaction_date || t.transactionDate || '';
      const exec = t.executive || t.name || '';
      const title = t.executive_title || t.title || '';
      const acqDisp = (t.acquisition_or_disposal || t.acquisitionOrDisposal || '').toUpperCase();
      const txnLabel = acqDisp === 'A' ? 'Buy' : acqDisp === 'D' ? 'Sell' : acqDisp;
      // Updated colors: green=#22c55e, red=#ef4444
      const txnCls = acqDisp === 'A' ? 'color:#22c55e' : acqDisp === 'D' ? 'color:#ef4444' : '';
      const shares = Number(t.shares || t.securitiesTransacted || 0);
      const price = t.share_price || t.sharePrice || '';
      html += `<tr>
        <td>${escHtml(txnDate)}</td>
        <td>${escHtml(exec)}</td>
        <td>${escHtml(title)}</td>
        <td style="${txnCls};font-weight:600">${escHtml(txnLabel)}</td>
        <td>${shares.toLocaleString()}</td>
        <td>$${escHtml(String(price))}</td>
      </tr>`;
    }
    html += `</tbody></table></div></div></div>`;
  }

  if (data.duration_seconds) {
    html += `<div style="text-align:right;margin-top:12px;font-size:11px;color:var(--text-dim)">Analyzed in ${data.duration_seconds.toFixed(1)}s</div>`;
  }

  return html;
}

// ── renderStockCharts ─────────────────────────────────────────────────────────

/**
 * Creates lightweight-charts for the stock analysis page.
 * Charts are pushed into the provided stockCharts array so app.js can destroy them.
function _renderNarrativeContent(n) {
  let html = '<div class="market-overview-box">';
  if (n.headline) html += `<div class="one-liner">${escHtml(n.headline)}</div>`;
  const sections = [
    ['Market Structure', n.structure_analysis],
    ['Pattern Context', n.pattern_context],
    ['Key Levels', n.level_analysis],
    ['Volume', n.volume_read],
  ];
  for (const [title, text] of sections) {
    if (text) html += `<h4>${escHtml(title)}</h4><p>${escHtml(text)}</p>`;
  }
  if (n.risk_factors?.length) {
    html += '<h4>Risk Factors</h4><ul>';
    for (const r of n.risk_factors) html += `<li style="font-size:13px;color:var(--text);margin-bottom:4px">${escHtml(r)}</li>`;
    html += '</ul>';
  }
  if (n.watch_for?.length) {
    html += '<h4>Watch For</h4><ul>';
    for (const w of n.watch_for) html += `<li style="font-size:13px;color:var(--text);margin-bottom:4px">${escHtml(w)}</li>`;
    html += '</ul>';
  }
  html += '</div>';
  return html;
}

/** Render narrative into the existing placeholder container. Self-contained — no external helper. */
export function renderNarrative(narrative) {
  const el = document.getElementById('narrative-container');
  if (!el) return;
  if (!narrative) {
    el.innerHTML = '<div class="market-overview-box" style="opacity:0.5"><p style="color:var(--muted);font-size:13px">AI narrative unavailable.</p></div>';
    return;
  }
  const n = narrative;
  let h = '<div class="market-overview-box">';
  if (n.headline) h += `<div class="one-liner">${escHtml(n.headline)}</div>`;
  for (const [title, text] of [['Market Structure', n.structure_analysis], ['Pattern Context', n.pattern_context], ['Key Levels', n.level_analysis], ['Volume', n.volume_read]]) {
    if (text) h += `<h4>${escHtml(title)}</h4><p>${escHtml(text)}</p>`;
  }
  if (n.risk_factors?.length) {
    h += '<h4>Risk Factors</h4><ul>';
    for (const r of n.risk_factors) h += `<li style="font-size:13px;color:var(--text);margin-bottom:4px">${escHtml(r)}</li>`;
    h += '</ul>';
  }
  if (n.watch_for?.length) {
    h += '<h4>Watch For</h4><ul>';
    for (const w of n.watch_for) h += `<li style="font-size:13px;color:var(--text);margin-bottom:4px">${escHtml(w)}</li>`;
    h += '</ul>';
  }
  h += '</div>';
  el.innerHTML = h;
}

/**
 * Updated colors per design spec.
 * @param {Object} data - API response from /stock/:ticker/price-action
 * @param {Array} stockCharts - Mutable array; created charts are pushed here
 */
export function renderStockCharts(data, stockCharts = null) {
  const cd = data.chart_data;
  if (!cd) return;
  if (!stockCharts) stockCharts = [];
  // Store chart data for toggle functions (line/candle, fullscreen)
  window._chartData = cd;
  if (!window._chartType) window._chartType = 'candlestick';

  // Updated chart colors:
  // bg: #0a0e17, text-dim: #64748b, grid: #1e293b, borders: #1e293b
  const chartOpts = {
    layout: { background: { color: '#0a0e17' }, textColor: '#64748b' },
    grid: { vertLines: { color: '#1e293b' }, horzLines: { color: '#1e293b' } },
    timeScale: { borderColor: '#1e293b' },
    rightPriceScale: { borderColor: '#1e293b' },
    crosshair: { mode: 0 },
    handleScroll: { mouseWheel: false, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: false },
    handleScale: { mouseWheel: false, pinch: false, axisPressedMouseMove: true },
  };

  // Updated candle colors: green=#22c55e, red=#ef4444
  const candleColors = {
    upColor: '#22c55e', downColor: '#ef4444',
    borderUpColor: '#22c55e', borderDownColor: '#ef4444',
    wickUpColor: '#22c55e', wickDownColor: '#ef4444',
  };

  const useLines = window._chartType === 'line';

  // ── Weekly chart ──
  const wEl = document.getElementById('chart-weekly');
  if (wEl && cd.weekly_candles?.length) {
    const wChart = LightweightCharts.createChart(wEl, { ...chartOpts, height: 400 });
    stockCharts.push(wChart);
    let wCandle;
    if (useLines) {
      wCandle = wChart.addLineSeries({ color: '#64748b', lineWidth: 2, priceLineVisible: true });
      wCandle.setData(cd.weekly_candles.map(c => ({ time: c.time, value: c.close })));
    } else {
      wCandle = wChart.addCandlestickSeries(candleColors);
      wCandle.setData(cd.weekly_candles);
    }

    // Weekly S/R lines — axis label with S/R prefix
    for (const s of (cd.support_lines || [])) {
      wCandle.createPriceLine({ price: s.price, color: '#22c55e', lineWidth: s.strength >= 2 ? 2 : 1, lineStyle: 2, axisLabelVisible: true, title: `S ${s.price.toFixed(2)}` });
    }
    for (const r of (cd.resistance_lines || [])) {
      wCandle.createPriceLine({ price: r.price, color: '#ef4444', lineWidth: r.strength >= 2 ? 2 : 1, lineStyle: 2, axisLabelVisible: true, title: `R ${r.price.toFixed(2)}` });
    }

    // 10-week SMA overlay — indigo, visual aid for weekly structure
    if (cd.weekly_ma_10?.length) {
      const wMa10 = wChart.addLineSeries({ color: '#6366f1', lineWidth: 1, title: '10W SMA', lastValueVisible: false, priceLineVisible: false });
      wMa10.setData(cd.weekly_ma_10);
    }

    // Weekly swing markers
    if (cd.weekly_markers?.length) wCandle.setMarkers(cd.weekly_markers.sort((a, b) => a.time < b.time ? -1 : 1));
    wChart.timeScale().fitContent();
  }

  // ── Daily chart ──
  const dEl = document.getElementById('chart-daily');
  if (dEl && cd.daily_candles?.length) {
    const dChart = LightweightCharts.createChart(dEl, { ...chartOpts, height: 500 });
    stockCharts.push(dChart);
    let dCandle;
    if (useLines) {
      dCandle = dChart.addLineSeries({ color: '#64748b', lineWidth: 2, priceLineVisible: true });
      dCandle.setData(cd.daily_candles.map(c => ({ time: c.time, value: c.close })));
    } else {
      dCandle = dChart.addCandlestickSeries(candleColors);
      dCandle.setData(cd.daily_candles);
    }

    // 21 EMA overlay — short-term momentum, teal
    if (cd.ema_21?.length) {
      const ema21 = dChart.addLineSeries({ color: '#2dd4bf', lineWidth: 1, title: '21EMA', lastValueVisible: false, priceLineVisible: false });
      ema21.setData(cd.ema_21);
    }

    // MA50 overlay — accent color updated to #6366f1
    if (cd.ma_50?.length) {
      const ma50 = dChart.addLineSeries({ color: '#6366f1', lineWidth: 1, title: 'MA50', lastValueVisible: false, priceLineVisible: false });
      ma50.setData(cd.ma_50);
    }

    // MA200 line series — violet updated to #8b5cf6
    if (cd.ma_200?.length) {
      const ma200 = dChart.addLineSeries({ color: '#8b5cf6', lineWidth: 1, title: 'MA200', lastValueVisible: false, priceLineVisible: false });
      ma200.setData(cd.ma_200);
    }

    // S/R lines — green=support, red=resistance, axis label with S/R prefix
    for (const s of (cd.support_lines || [])) {
      dCandle.createPriceLine({ price: s.price, color: '#22c55e', lineWidth: s.strength >= 2 ? 2 : 1, lineStyle: 2, axisLabelVisible: true, title: `S ${s.price.toFixed(2)}` });
    }
    for (const r of (cd.resistance_lines || [])) {
      dCandle.createPriceLine({ price: r.price, color: '#ef4444', lineWidth: r.strength >= 2 ? 2 : 1, lineStyle: 2, axisLabelVisible: true, title: `R ${r.price.toFixed(2)}` });
    }

    // Fibonacci levels — yellow updated to #eab308
    const fibLabels = { 0.382: 'Fib 38.2%', 0.5: 'Fib 50%', 0.618: 'Fib 61.8%' };
    for (const f of (cd.fib_lines || [])) {
      const label = fibLabels[f.ratio] || `Fib ${(f.ratio * 100).toFixed(1)}%`;
      dCandle.createPriceLine({ price: f.price, color: '#eab308', lineWidth: f.ratio === 0.618 ? 2 : 1, lineStyle: 1, axisLabelVisible: false, title: label });
    }

    // Combine swing + pattern markers, sort by time
    const allMarkers = [...(cd.daily_markers || []), ...(cd.pattern_markers || [])];
    allMarkers.sort((a, b) => a.time < b.time ? -1 : 1);
    if (allMarkers.length) dCandle.setMarkers(allMarkers);
    dChart.timeScale().fitContent();
  }

  // ── RSI chart ──
  const rEl = document.getElementById('chart-rsi');
  if (rEl && cd.rsi?.length) {
    const rChart = LightweightCharts.createChart(rEl, { ...chartOpts, height: 100, rightPriceScale: { scaleMargins: { top: 0.1, bottom: 0.1 } } });
    stockCharts.push(rChart);
    // RSI line updated to violet #8b5cf6
    const rsiSeries = rChart.addLineSeries({ color: '#8b5cf6', lineWidth: 1.5 });
    rsiSeries.setData(cd.rsi);
    // Overbought/oversold lines — semi-transparent red/green
    rsiSeries.createPriceLine({ price: 70, color: '#ef444460', lineWidth: 1, lineStyle: 2, title: '70' });
    rsiSeries.createPriceLine({ price: 30, color: '#22c55e60', lineWidth: 1, lineStyle: 2, title: '30' });
    rChart.timeScale().fitContent();
  }

  // ── MACD chart ──
  const mEl = document.getElementById('chart-macd');
  if (mEl && cd.macd?.length) {
    const mChart = LightweightCharts.createChart(mEl, { ...chartOpts, height: 100, rightPriceScale: { scaleMargins: { top: 0.1, bottom: 0.1 } } });
    stockCharts.push(mChart);

    // Histogram
    if (cd.macd_histogram?.length) {
      const hist = mChart.addHistogramSeries({ priceScaleId: '', priceLineVisible: false });
      hist.setData(cd.macd_histogram);
    }

    // MACD line — accent updated to #6366f1
    const macdLine = mChart.addLineSeries({ color: '#6366f1', lineWidth: 1.5, priceLineVisible: false });
    macdLine.setData(cd.macd);

    // Signal line — orange updated to #f97316
    if (cd.macd_signal?.length) {
      const sigLine = mChart.addLineSeries({ color: '#f97316', lineWidth: 1, priceLineVisible: false });
      sigLine.setData(cd.macd_signal);
    }

    mChart.timeScale().fitContent();
  }

  return stockCharts;
}

// ── renderBtResults ───────────────────────────────────────────────────────────

/**
 * Renders backtest results and sets innerHTML on #bt-results.
 * @param {Object} d - API response from /backtest
 */
export function renderBtResults(d) {
  const ph = d.primary_horizon;
  const horizons = d.horizons;

  // ── Summary bar ──
  const totalSigs = Object.values(d.strategies).reduce((a, s) => a + s.total_signals, 0);
  let html = `
  <div class="bt-summary-bar">
    <div class="bt-summary-card"><div class="bt-summary-val">${d.tickers.length}</div><div class="bt-summary-label">Tickers</div></div>
    <div class="bt-summary-card"><div class="bt-summary-val">${Object.keys(d.strategies).length}</div><div class="bt-summary-label">Strategies</div></div>
    <div class="bt-summary-card"><div class="bt-summary-val">${totalSigs.toLocaleString()}</div><div class="bt-summary-label">Total Signals</div></div>
    <div class="bt-summary-card"><div class="bt-summary-val">${d.elapsed}s</div><div class="bt-summary-label">Elapsed</div></div>
    <div class="bt-summary-card"><div class="bt-summary-val">${d.start || ''} → ${d.end || ''}</div><div class="bt-summary-label">Period</div></div>
  </div>`;

  // ── Ranking table ──
  html += `
  <div class="bt-section-title">Strategy Ranking <span class="bt-dim">(${ph}d excess returns over SPY)</span></div>
  <table class="bt-table">
    <thead><tr>
      <th>#</th><th>Strategy</th><th>Signals</th><th>Hit Rate</th>
      <th>Mean Excess</th><th>t-stat</th><th>p-value</th><th>Verdict</th>
    </tr></thead><tbody>`;

  for (const row of d.ranking) {
    const vc = { PROMISING: 'bt-promising', WEAK: 'bt-weak', 'LOW N': 'bt-dim', 'NO EDGE': 'bt-no-edge' }[row.verdict] || '';
    html += `<tr>
      <td>${row.rank}</td>
      <td><strong>${escHtml(row.name)}</strong></td>
      <td>${row.n.toLocaleString()}</td>
      <td class="${row.hit_rate > 55 ? 'bt-green' : row.hit_rate > 50 ? 'bt-yellow' : 'bt-red'}">${row.hit_rate.toFixed(1)}%</td>
      <td class="${row.mean_excess > 0 ? 'bt-green' : 'bt-red'}">${row.mean_excess > 0 ? '+' : ''}${row.mean_excess.toFixed(3)}%</td>
      <td>${row.t_stat.toFixed(2)}</td>
      <td class="${row.p_value < 0.05 ? 'bt-green' : 'bt-dim'}">${row.p_value < 0.001 ? '<0.001' : row.p_value.toFixed(3)}</td>
      <td><span class="bt-verdict ${vc}">${row.verdict}</span></td>
    </tr>`;
  }
  html += `</tbody></table>`;

  // ── Horizon comparison tabs ──
  html += `
  <div class="bt-section-title" style="margin-top:28px">Comparison by Horizon</div>
  <div class="bt-horizon-tabs">
    ${horizons.map((h, i) => `<button class="bt-htab${i === 0 ? ' bt-htab-active' : ''}" onclick="btSwitchHorizon(${h}, this)">${h}d</button>`).join('')}
  </div>`;

  for (const h of horizons) {
    html += `<div class="bt-horizon-panel" id="bt-hp-${h}" style="${h === horizons[0] ? '' : 'display:none'}">
    <table class="bt-table">
      <thead><tr>
        <th>Strategy</th><th>Signals</th>
        <th>Buy Hit%</th><th>Buy Mean</th>
        <th>Excess Buy</th><th>Excess Sell</th>
        <th>t-stat</th><th>p-value</th>
      </tr></thead><tbody>`;

    for (const [key, s] of Object.entries(d.strategies)) {
      const st = s.by_horizon[String(h)];
      if (!st) continue;
      const bhr = st.buy_hit_rate, bmean = st.buy_mean, ebmean = st.excess_buy_mean, esmean = st.excess_sell_mean;
      html += `<tr>
        <td><strong>${escHtml(s.name)}</strong></td>
        <td>${st.n_signals.toLocaleString()}</td>
        <td class="${bhr > 55 ? 'bt-green' : bhr > 50 ? 'bt-yellow' : 'bt-red'}">${st.buy_count > 0 ? bhr.toFixed(1) + '%' : '—'}</td>
        <td class="${bmean > 0 ? 'bt-green' : 'bt-red'}">${st.buy_count > 0 ? (bmean > 0 ? '+' : '') + bmean.toFixed(2) + '%' : '—'}</td>
        <td class="${ebmean > 0 ? 'bt-green' : 'bt-red'}">${st.excess_buy_count > 0 ? (ebmean > 0 ? '+' : '') + ebmean.toFixed(2) + '%' : '—'}</td>
        <td class="${esmean < 0 ? 'bt-green' : 'bt-red'}">${st.excess_sell_count > 0 ? (esmean > 0 ? '+' : '') + esmean.toFixed(2) + '%' : '—'}</td>
        <td>${st.t_stat.toFixed(2)}</td>
        <td class="${st.p_value < 0.05 ? 'bt-green' : 'bt-dim'}">${st.p_value < 0.001 ? '<0.001' : st.p_value.toFixed(3)}</td>
      </tr>`;
    }
    html += `</tbody></table></div>`;
  }

  // ── Per-strategy accordion ──
  html += `<div class="bt-section-title" style="margin-top:28px">Per-Strategy Detail</div>`;

  for (const [key, s] of Object.entries(d.strategies)) {
    html += `
    <div class="bt-accordion">
      <div class="bt-accordion-head" onclick="btToggleAccordion(this)">
        <span>${escHtml(s.name)}</span>
        <span class="bt-dim">${s.buy_signals} buy · ${s.sell_signals} sell</span>
        <span class="bt-accordion-arrow">▶</span>
      </div>
      <div class="bt-accordion-body" style="display:none">
        <p class="bt-dim" style="margin-bottom:12px">${escHtml(s.description)}</p>
        <table class="bt-table">
          <thead><tr>
            <th>Horizon</th>
            <th>Buy n</th><th>Buy Hit%</th><th>Buy Mean</th>
            <th>Sell n</th><th>Sell Hit%</th><th>Sell Mean</th>
            <th>Excess Buy</th><th>Excess Sell</th>
            <th>t-stat</th><th>p-value</th>
          </tr></thead><tbody>`;

    for (const h of horizons) {
      const st = s.by_horizon[String(h)];
      if (!st) continue;
      const bm = st.buy_mean, sm = st.sell_mean;
      const ebm = st.excess_buy_mean, esm = st.excess_sell_mean;
      html += `<tr>
        <td><strong>${h}d</strong></td>
        <td>${st.buy_count}</td>
        <td class="${st.buy_hit_rate > 55 ? 'bt-green' : st.buy_hit_rate > 50 ? 'bt-yellow' : 'bt-red'}">${st.buy_count > 0 ? st.buy_hit_rate.toFixed(1) + '%' : '—'}</td>
        <td class="${bm > 0 ? 'bt-green' : 'bt-red'}">${st.buy_count > 0 ? (bm > 0 ? '+' : '') + bm.toFixed(2) + '%' : '—'}</td>
        <td>${st.sell_count}</td>
        <td class="${st.sell_hit_rate > 55 ? 'bt-green' : st.sell_hit_rate > 50 ? 'bt-yellow' : 'bt-red'}">${st.sell_count > 0 ? st.sell_hit_rate.toFixed(1) + '%' : '—'}</td>
        <td class="${sm < 0 ? 'bt-green' : 'bt-red'}">${st.sell_count > 0 ? (sm > 0 ? '+' : '') + sm.toFixed(2) + '%' : '—'}</td>
        <td class="${ebm > 0 ? 'bt-green' : 'bt-red'}">${st.excess_buy_count > 0 ? (ebm > 0 ? '+' : '') + ebm.toFixed(2) + '%' : '—'}</td>
        <td class="${esm < 0 ? 'bt-green' : 'bt-red'}">${st.excess_sell_count > 0 ? (esm > 0 ? '+' : '') + esm.toFixed(2) + '%' : '—'}</td>
        <td>${st.t_stat.toFixed(2)}</td>
        <td class="${st.p_value < 0.05 ? 'bt-green' : 'bt-dim'}">${st.p_value < 0.001 ? '<0.001' : st.p_value.toFixed(3)}</td>
      </tr>`;
    }
    html += `</tbody></table></div></div>`;
  }

  return html;
}

// ── renderMarketData ──────────────────────────────────────────────────────────

/**
 * Renders the raw market snapshot data as an HTML string.
 * Extracted from the loadMarket() function in the original index.html.
 * Updated colors per design spec.
 * @param {Object} data - API response from /market
 * @returns {string} HTML string
 */
export function renderMarketData(data) {
  let html = '';

  // ── Major Indices bar ──
  const indices = data.indices || {};
  if (Object.keys(indices).length) {
    html += '<div class="indices-bar">';
    for (const [name, q] of Object.entries(indices)) {
      const cls = changeClass(q.change_percent);
      html += `<div class="index-card">
        <div class="name">${escHtml(name)}</div>
        <div class="price">$${escHtml(q.price)}</div>
        <div class="change ${cls}">${escHtml(q.change_percent || 'N/A')}</div>
      </div>`;
    }
    // VIX card — yellow border updated to var(--yellow) which stays the same
    const vix = data.vix;
    if (vix) {
      const cls = changeClass(vix.change_percent);
      html += `<div class="index-card" style="border-color:var(--yellow)">
        <div class="name">VIX (VIXY)</div>
        <div class="price">$${escHtml(vix.price)}</div>
        <div class="change ${cls}">${escHtml(vix.change_percent || 'N/A')}</div>
      </div>`;
    }
    html += '</div>';
  }

  // ── Market Regime ──
  const regime = data.regime;
  if (regime) {
    // Updated colors: green=#22c55e, red=#ef4444, yellow=#eab308
    const rColor = regime.regime === 'risk_on' ? '#22c55e' : regime.regime === 'risk_off' ? '#ef4444' : '#eab308';
    html += `<div class="market-section" style="margin-bottom:16px;padding:12px 16px;border-left:3px solid ${rColor}">
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:8px">
        <span style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;color:var(--text-dim)">Market Regime</span>
        <span style="font-size:14px;font-weight:700;color:${rColor}">${escHtml(regime.label)}</span>
        <span style="font-size:11px;color:var(--text-dim)">score: ${regime.score}/${regime.max_score}</span>
      </div>
      ${regime.summary ? `<div style="font-size:13px;color:var(--text-primary);margin-bottom:8px;line-height:1.5">${escHtml(regime.summary)}</div>` : ''}
      <div style="font-size:12px;color:var(--text-dim)">
        ${regime.signals.map(s => `<div style="margin-bottom:2px">• ${escHtml(s)}</div>`).join('')}
      </div>
    </div>`;
  }

  html += '<div class="market-grid">';

  // ── Sector Performance ──
  const sectors = data.sectors?.realtime || {};
  if (Object.keys(sectors).length) {
    html += `<div class="market-section"><h3>Sector Performance</h3>`;
    for (const [name, perf] of Object.entries(sectors)) {
      const cls = changeClass(perf);
      html += `<div class="mover-row">
        <span class="ticker-name">${escHtml(name)}</span>
        <span class="change ${cls}">${escHtml(String(perf))}</span>
      </div>`;
    }
    html += `</div>`;
  }

  // ── Top Gainers ──
  const gainers = data.movers?.top_gainers || [];
  if (gainers.length) {
    html += `<div class="market-section"><h3>Top Gainers</h3>`;
    for (const m of gainers) {
      html += `<div class="mover-row">
        <span class="ticker-name">${tickerTag(m.ticker)}</span>
        <span class="price">$${escHtml(m.price)}</span>
        <span class="change positive">${escHtml(m.change_pct)}</span>
      </div>`;
    }
    html += `</div>`;
  }

  // ── Top Losers ──
  const losers = data.movers?.top_losers || [];
  if (losers.length) {
    html += `<div class="market-section"><h3>Top Losers</h3>`;
    for (const m of losers) {
      html += `<div class="mover-row">
        <span class="ticker-name">${tickerTag(m.ticker)}</span>
        <span class="price">$${escHtml(m.price)}</span>
        <span class="change negative">${escHtml(m.change_pct)}</span>
      </div>`;
    }
    html += `</div>`;
  }

  // ── Most Active ──
  const active = data.movers?.most_active || [];
  if (active.length) {
    html += `<div class="market-section"><h3>Most Active</h3>`;
    for (const m of active) {
      const cls = changeClass(m.change_pct);
      html += `<div class="mover-row">
        <span class="ticker-name">${tickerTag(m.ticker)}</span>
        <span class="price">$${escHtml(m.price)}</span>
        <span class="change ${cls}">${escHtml(m.change_pct)}</span>
      </div>`;
    }
    html += `</div>`;
  }

  // Notice when movers are empty
  if (!gainers.length && !losers.length && !active.length) {
    html += `<div class="market-section" style="grid-column:1/-1"><h3>Market Movers</h3>
      <p style="color:var(--text-dim);font-size:13px">Movers data is only available during/after US market hours (9:30 AM – 4:00 PM ET, weekdays).</p></div>`;
  }

  // ── Treasury Yields ──
  const yields = data.treasury_yields || {};
  if (Object.keys(yields).length) {
    html += `<div class="market-section"><h3>Treasury Yields</h3>`;
    const labels = { '2year': '2-Year', '5year': '5-Year', '10year': '10-Year', '30year': '30-Year' };
    for (const [mat, val] of Object.entries(yields)) {
      html += `<div class="indicator-row">
        <span class="label">${labels[mat] || mat}</span>
        <span><span class="value">${escHtml(String(val.value))}%</span> <span class="date">(${escHtml(val.date)})</span></span>
      </div>`;
    }
    // Yield curve spread
    if (yields['2year'] && yields['10year']) {
      try {
        const spread = (parseFloat(yields['10year'].value) - parseFloat(yields['2year'].value)).toFixed(2);
        const status = parseFloat(spread) >= 0 ? 'NORMAL' : 'INVERTED';
        const cls = parseFloat(spread) >= 0 ? 'positive' : 'negative';
        html += `<div class="indicator-row" style="border-top:1px solid var(--border);margin-top:4px;padding-top:8px">
          <span class="label">10Y-2Y Spread</span>
          <span><span class="value change ${cls}">${spread > 0 ? '+' : ''}${spread}%</span> <span class="date">(${status})</span></span>
        </div>`;
      } catch (e) { /* ignore */ }
    }
    html += `</div>`;
  }

  // ── Forex ──
  const forex = data.forex || {};
  if (Object.keys(forex).length) {
    html += `<div class="market-section"><h3>Forex</h3>`;
    for (const [pair, val] of Object.entries(forex)) {
      const rate = parseFloat(val.rate || 0);
      const display = rate > 100 ? rate.toFixed(2) : rate.toFixed(4);
      html += `<div class="indicator-row">
        <span class="label">${escHtml(pair)}</span>
        <span><span class="value">${display}</span></span>
      </div>`;
    }
    html += `</div>`;
  }

  // ── Crypto ──
  const crypto = data.crypto || {};
  if (Object.keys(crypto).length) {
    html += `<div class="market-section"><h3>Crypto</h3>`;
    for (const [symbol, val] of Object.entries(crypto)) {
      const rate = parseFloat(val.rate || 0);
      html += `<div class="indicator-row">
        <span class="label">${escHtml(symbol)}/USD</span>
        <span><span class="value">$${rate.toLocaleString(undefined, { maximumFractionDigits: 2 })}</span></span>
      </div>`;
    }
    html += `</div>`;
  }

  // ── Economic Indicators ──
  const indicators = data.indicators || {};
  if (Object.keys(indicators).length) {
    html += `<div class="market-section"><h3>Economic Indicators</h3>`;
    const labels = {
      CPI: 'CPI', FEDERAL_FUNDS_RATE: 'Fed Funds Rate', UNEMPLOYMENT: 'Unemployment',
      REAL_GDP: 'Real GDP (Quarterly)', NONFARM_PAYROLL: 'Nonfarm Payroll'
    };
    for (const [key, val] of Object.entries(indicators)) {
      html += `<div class="indicator-row">
        <span class="label">${labels[key] || key}</span>
        <span><span class="value">${escHtml(String(val.value))}</span> <span class="date">(${escHtml(val.date)})</span></span>
      </div>`;
    }
    html += `<p style="color:var(--text-dim);font-size:11px;margin-top:8px">Government data has natural lag — CPI/jobs are monthly (released ~2 weeks after period ends), GDP is quarterly. These dates are normal.</p>`;
    html += `</div>`;
  }

  // ── Commodities ──
  const commodities = data.commodities || {};
  if (Object.keys(commodities).length) {
    html += `<div class="market-section"><h3>Commodities</h3>`;
    const labels = { WTI: 'WTI Crude Oil', NATURAL_GAS: 'Natural Gas', COPPER: 'Copper', GOLD: 'Gold (GLD)' };
    for (const [key, val] of Object.entries(commodities)) {
      let extra = '';
      if (val.change_pct) {
        const cls = changeClass(val.change_pct);
        extra = ` <span class="change ${cls}" style="font-size:12px">${escHtml(val.change_pct)}</span>`;
      }
      const dateStr = val.date ? ` <span class="date">(${escHtml(val.date)})</span>` : '';
      html += `<div class="indicator-row">
        <span class="label">${labels[key] || key}</span>
        <span><span class="value">$${escHtml(String(val.value))}</span>${extra}${dateStr}</span>
      </div>`;
    }
    html += `</div>`;
  }

  html += '</div>';

  if (data.movers?.last_updated) {
    html += `<div style="text-align:right;margin-top:12px;font-size:11px;color:var(--text-dim)">Last updated: ${escHtml(data.movers.last_updated)}</div>`;
  }

  return html;
}

// ── renderMarketOverview ──────────────────────────────────────────────────────

/**
 * Renders the LLM market overview box as an HTML string.
 * Extracted from the runMarketOverview() function in the original index.html.
 * @param {Object} data - API response from /market/analyze
 * @returns {string} HTML string
 */
export function renderMarketOverview(data) {
  const ov = data.overview;

  if (!ov) {
    return `<div class="empty"><p>LLM overview failed: ${escHtml(data.error || 'unknown error')}</p></div>`;
  }

  let html = '<div class="market-overview-box">';
  if (ov.one_liner) {
    html += `<div class="one-liner">${escHtml(ov.one_liner)}</div>`;
  }

  const sections = [
    ['Market Pulse', ov.market_pulse],
    ['Key Movers', ov.key_movers],
    ['News & Events', ov.news_and_events],
    ['Macro Landscape', ov.macro_landscape],
    ['Commodities & Crypto', ov.commodities_crypto],
    ['Risk Assessment', ov.risk_assessment],
    ['Outlook', ov.outlook],
  ];

  for (const [title, text] of sections) {
    if (text) {
      html += `<h4>${escHtml(title)}</h4><p>${escHtml(text)}</p>`;
    }
  }

  if (data.duration_seconds) {
    html += `<div style="text-align:right;margin-top:12px;font-size:11px;color:var(--text-dim)">Generated in ${data.duration_seconds.toFixed(1)}s</div>`;
  }

  html += '</div>';
  return html;
}

// ── ptRenderPortfolio ─────────────────────────────────────────────────────────

/**
 * Updates paper trading portfolio stat elements directly in the DOM.
 * @param {Object} p - Portfolio object from /paper/portfolio
 */
export function ptRenderPortfolio(p) {
  const fmt = (n) => n >= 0
    ? `+$${Math.abs(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
    : `-$${Math.abs(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  const fmtDollar = (n) => '$' + (n || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const pnl = p.total_pnl || 0;
  const ret = p.total_return_pct || 0;

  document.getElementById('pt-total-value').textContent = fmtDollar(p.total_value);
  document.getElementById('pt-cash').textContent = fmtDollar(p.current_cash);
  document.getElementById('pt-invested').textContent = fmtDollar(p.invested);

  const pnlEl = document.getElementById('pt-total-pnl');
  pnlEl.textContent = fmt(pnl);
  pnlEl.className = 'pt-card-value ' + (pnl >= 0 ? 'pos' : 'neg');

  const retEl = document.getElementById('pt-return');
  retEl.textContent = (ret >= 0 ? '+' : '') + ret + '%';
  retEl.className = 'pt-card-value ' + (ret >= 0 ? 'pos' : 'neg');

  document.getElementById('pt-winrate').textContent = p.win_rate + '%';
  document.getElementById('pt-open-count').textContent = p.open_positions;
  document.getElementById('pt-closed-count').textContent = p.closed_positions;
}

// ── ptRenderTrades ────────────────────────────────────────────────────────────

/**
 * Renders paper trading open/closed trade tables directly in the DOM.
 * @param {Array} trades - Array of trade objects from /paper/trades
 */
export function ptRenderTrades(trades) {
  const open = trades.filter(t => t.status === 'open');
  const closed = trades.filter(t => t.status === 'closed');

  document.getElementById('pt-open-badge').textContent = open.length;
  document.getElementById('pt-closed-badge').textContent = closed.length;

  const fmtPrice = n => n != null ? '$' + Number(n).toFixed(2) : '&#8212;';
  const fmtPnl = (n, pct) => {
    if (n == null) return '<span class="pt-pnl">&#8212;</span>';
    const cls = n >= 0 ? 'pos' : 'neg';
    const sign = n >= 0 ? '+' : '';
    return `<span class="pt-pnl ${cls}">${sign}$${Math.abs(n).toFixed(2)} (${sign}${Number(pct || 0).toFixed(2)}%)</span>`;
  };
  const stratName = k => ({ mean_reversion: 'Mean Rev', liquidity_sweep: 'Liq. Sweep', wyckoff_buy_only: 'Wyckoff' }[k] || k);
  const reasonLabel = r => {
    if (!r) return '&#8212;';
    const key = r.split(':')[0];
    return { stop_loss: 'Stop', trailing_stop: 'Trail Stop', take_profit: 'Target', manual: 'Manual', news_guard: 'News' }[key] || escHtml(r);
  };

  const openBody = document.getElementById('pt-open-tbody');
  if (!open.length) {
    openBody.innerHTML = `<tr><td colspan="11" class="pt-empty">No open positions &#8212; run a scan to find opportunities</td></tr>`;
  } else {
    // Updated inline colors: red=#ef4444, green=#22c55e
    openBody.innerHTML = open.map(t => {
      const dir = t.direction || 'long';
      const dirBadge = dir === 'short'
        ? '<span style="font-size:10px;font-weight:700;color:#ef4444;background:rgba(239,68,68,0.15);padding:1px 5px;border-radius:3px;margin-left:4px">SHORT</span>'
        : '<span style="font-size:10px;font-weight:700;color:#22c55e;background:rgba(34,197,94,0.15);padding:1px 5px;border-radius:3px;margin-left:4px">LONG</span>';
      return `<tr>
        <td><strong>${escHtml(t.ticker)}</strong>${dirBadge}</td>
        <td>${escHtml(stratName(t.strategy))}</td>
        <td><span class="pt-badge ${t.conviction}">${t.conviction}</span></td>
        <td style="font-size:11px;color:var(--text-dim)">${escHtml(t.sector)}</td>
        <td>${fmtPrice(t.entry_price)}</td>
        <td>${fmtPrice(t.current_price)}</td>
        <td style="color:#ef4444">${fmtPrice(t.stop_loss_price)}</td>
        <td style="color:#22c55e">${t.take_profit_type === 'trailing' ? '<span style="font-size:11px">Trailing ∞</span>' : fmtPrice(t.take_profit_price)}</td>
        <td>${fmtPnl(t.unrealized_pnl, t.unrealized_pnl_pct)}</td>
        <td>${t.days_held || 0}d</td>
        <td><button class="pt-close-btn" onclick="ptCloseTrade(${t.id}, '${escHtml(t.ticker)}')">Close</button></td>
      </tr>`;
    }).join('');
  }

  const closedBody = document.getElementById('pt-closed-tbody');
  if (!closed.length) {
    closedBody.innerHTML = `<tr><td colspan="9" class="pt-empty">No closed trades yet</td></tr>`;
  } else {
    closedBody.innerHTML = closed.map(t => {
      const dir = t.direction || 'long';
      const dirBadge = dir === 'short'
        ? '<span style="font-size:10px;font-weight:700;color:#ef4444;background:rgba(239,68,68,0.15);padding:1px 5px;border-radius:3px;margin-left:4px">SHORT</span>'
        : '<span style="font-size:10px;font-weight:700;color:#22c55e;background:rgba(34,197,94,0.15);padding:1px 5px;border-radius:3px;margin-left:4px">LONG</span>';
      return `<tr>
        <td><strong>${escHtml(t.ticker)}</strong>${dirBadge}</td>
        <td>${escHtml(stratName(t.strategy))}</td>
        <td><span class="pt-badge ${t.conviction}">${t.conviction}</span></td>
        <td style="font-size:11px;color:var(--text-dim)">${escHtml(t.sector)}</td>
        <td>${fmtPrice(t.entry_price)}</td>
        <td>${fmtPrice(t.exit_price)}</td>
        <td>${fmtPnl(t.realized_pnl, t.realized_pnl_pct)}</td>
        <td>${t.days_held || 0}d</td>
        <td style="font-size:12px">${reasonLabel(t.exit_reason)}</td>
      </tr>`;
    }).join('');
  }
}

// ── tjRenderStats ─────────────────────────────────────────────────────────────

/**
 * Renders trade journal summary stats directly into #tj-stats.
 * Updated colors per design spec.
 * @param {Object} p - Portfolio object from /paper/portfolio
 */
export function tjRenderStats(p) {
  // Updated colors: green=#22c55e, red=#ef4444
  const pnlColor = (p.total_pnl || 0) >= 0 ? '#22c55e' : '#ef4444';
  const retColor = (p.total_return_pct || 0) >= 0 ? '#22c55e' : '#ef4444';
  document.getElementById('tj-stats').innerHTML = `
    <div class="stat-card"><div class="stat-card-label">Total Trades</div><div class="stat-card-value">${p.open_positions + p.closed_positions}</div></div>
    <div class="stat-card"><div class="stat-card-label">Open</div><div class="stat-card-value">${p.open_positions}</div></div>
    <div class="stat-card"><div class="stat-card-label">Closed</div><div class="stat-card-value">${p.closed_positions}</div></div>
    <div class="stat-card"><div class="stat-card-label">Return</div><div class="stat-card-value" style="color:${retColor}">${(p.total_return_pct || 0) >= 0 ? '+' : ''}${p.total_return_pct || 0}%</div></div>
    <div class="stat-card"><div class="stat-card-label">Total P&L</div><div class="stat-card-value" style="color:${pnlColor}">$${Math.abs(p.total_pnl || 0).toFixed(2)}</div></div>
    <div class="stat-card"><div class="stat-card-label">Win Rate</div><div class="stat-card-value">${p.win_rate || 0}%</div></div>
    <div class="stat-card"><div class="stat-card-label">W / L</div><div class="stat-card-value">${p.wins || 0}/${p.losses || 0}</div></div>
  `;
}

// ── tjRenderList ──────────────────────────────────────────────────────────────

/**
 * Renders the trade journal list into #tj-list.
 * Updated colors per design spec.
 * @param {Array} trades - Array of all trade objects
 * @param {string} filter - Current filter: 'all'|'open'|'closed'|'wins'|'losses'
 * @param {number|null} expandedId - Currently expanded trade ID (for toggling)
 */
export function tjRenderList(trades, filter, expandedId) {
  const el = document.getElementById('tj-list');
  if (!trades.length) {
    el.innerHTML = `<div class="tj-empty">No trades${filter !== 'all' ? ` matching "${filter}"` : ''} — run a scan to start trading</div>`;
    return;
  }

  // Updated inline colors: yellow=#eab308, green=#22c55e, red=#ef4444
  el.innerHTML = trades.map(t => {
    const pnl = t.status === 'closed' ? t.realized_pnl : (t.unrealized_pnl || 0);
    const pnlPct = t.status === 'closed' ? t.realized_pnl_pct : (t.unrealized_pnl_pct || 0);
    const pnlCls = t.status === 'open' ? 'open' : pnl >= 0 ? 'win' : 'loss';
    const sign = pnl >= 0 ? '+' : '';
    const statusBadge = t.status === 'open'
      ? '<span style="color:#eab308;font-weight:600">OPEN</span>'
      : (pnl >= 0 ? '<span style="color:#22c55e;font-weight:600">WIN</span>' : '<span style="color:#ef4444;font-weight:600">LOSS</span>');
    const exitInfo = t.status === 'closed' ? `Exit: $${Number(t.exit_price).toFixed(2)} (${t.exit_reason || ''})` : `Days: ${t.days_held || 0}`;
    const date = (t.created_at || '').split('T')[0] || t.created_at || '';

    return `
      <div class="tj-trade-row" id="tj-row-${t.id}">
        <div class="tj-trade-header" onclick="tjToggle(${t.id})">
          <span class="tj-ticker">${escHtml(t.ticker)}</span>
          <div class="tj-meta">
            ${statusBadge}
            <span>${escHtml(t.strategy)}</span>
            <span>${escHtml(t.sector)}</span>
            <span>Score: ${t.conviction_score || '?'}</span>
            <span>Entry: $${Number(t.entry_price).toFixed(2)}</span>
            <span>${exitInfo}</span>
            <span>${date}</span>
          </div>
          <span class="tj-pnl ${pnlCls}">${sign}$${Math.abs(pnl).toFixed(2)} (${sign}${Number(pnlPct).toFixed(2)}%)</span>
        </div>
        <div class="tj-detail" id="tj-detail-${t.id}"></div>
      </div>`;
  }).join('');
}

// ── tjRenderDetail ────────────────────────────────────────────────────────────

/**
 * Renders the expanded trade detail panel as an HTML string.
 * Updated colors per design spec.
 * @param {Object} t - Trade object with log and analysis_snapshot from /paper/trades/:id
 * @returns {string} HTML string
 */
export function tjRenderDetail(t) {
  const snapshot = t.analysis_snapshot || {};
  const scoreData = snapshot.score || {};
  const layers = scoreData.layers || [];
  const alignment = scoreData.alignment || {};
  const logs = t.log || [];

  let html = '<div class="tj-detail-grid">';

  // ── Left column: Score Breakdown ──
  html += '<div>';

  // Score layers
  html += '<div class="tj-section"><h4>Score Breakdown</h4>';
  if (layers.length) {
    for (const l of layers) {
      const cls = l.score > 0 ? 'pos' : l.score < 0 ? 'neg' : 'zero';
      html += `<div class="tj-layer-row">
        <span class="tj-layer-name">${escHtml(l.name)}</span>
        <span class="tj-layer-score ${cls}">${l.score > 0 ? '+' : ''}${l.score} / ${l.max}</span>
      </div>
      <div style="font-size:11px;color:var(--text-dim);padding:0 0 4px 0">${escHtml(l.reasoning || '')}</div>`;
    }
    if (alignment.score !== undefined) {
      const aCls = alignment.score > 0 ? 'pos' : alignment.score < 0 ? 'neg' : 'zero';
      html += `<div class="tj-layer-row" style="border-top:1px solid var(--border);margin-top:4px;padding-top:6px">
        <span class="tj-layer-name">Alignment</span>
        <span class="tj-layer-score ${aCls}">${alignment.score > 0 ? '+' : ''}${alignment.score}</span>
      </div>
      <div style="font-size:11px;color:var(--text-dim);padding:0 0 4px 0">${escHtml(alignment.reasoning || '')}</div>`;
    }
    // Updated accent color in border-top: use var(--accent) which maps to #6366f1 in new design
    html += `<div class="tj-layer-row" style="border-top:1px solid var(--accent);margin-top:6px;padding-top:6px;font-weight:700">
      <span>Total</span>
      <span>${scoreData.total_score || t.conviction_score || '?'} / ${scoreData.max_score || 27}</span>
    </div>`;
  } else {
    html += '<div style="font-size:12px;color:var(--text-dim)">No snapshot available (trade opened before journal feature)</div>';
  }
  html += '</div>';

  // Market structure
  const ws = snapshot.weekly_structure || {};
  const ds = snapshot.daily_structure || {};
  if (ws.trend || ds.trend) {
    html += '<div class="tj-section" style="margin-top:12px"><h4>Market Structure at Entry</h4>';
    html += `<div class="tj-kv"><span class="k">Weekly</span><span class="v">${ws.trend || '?'} (${ws.strength || '?'})</span></div>`;
    // Updated inline colors: yellow=#eab308, red=#ef4444
    if (ws.bos) html += `<div class="tj-kv"><span class="k">Weekly BOS</span><span class="v" style="color:#eab308">${ws.bos.type || 'yes'}</span></div>`;
    if (ws.choch) html += `<div class="tj-kv"><span class="k">Weekly CHoCH</span><span class="v" style="color:#ef4444">${ws.choch.type || 'yes'}</span></div>`;
    html += `<div class="tj-kv"><span class="k">Daily</span><span class="v">${ds.trend || '?'} (${ds.strength || '?'})</span></div>`;
    if (ds.bos) html += `<div class="tj-kv"><span class="k">Daily BOS</span><span class="v" style="color:#eab308">${ds.bos.type || 'yes'}</span></div>`;
    if (ds.choch) html += `<div class="tj-kv"><span class="k">Daily CHoCH</span><span class="v" style="color:#ef4444">${ds.choch.type || 'yes'}</span></div>`;
    html += '</div>';
  }

  html += '</div>';

  // ── Right column: Trade details + Event log ──
  html += '<div>';

  // Trade parameters
  html += '<div class="tj-section"><h4>Trade Parameters</h4>';
  html += `<div class="tj-kv"><span class="k">Entry Price</span><span class="v">$${Number(t.entry_price).toFixed(2)}</span></div>`;
  html += `<div class="tj-kv"><span class="k">Signal Price</span><span class="v">$${Number(t.signal_price).toFixed(2)}</span></div>`;
  html += `<div class="tj-kv"><span class="k">Position Size</span><span class="v">$${Number(t.position_value).toFixed(0)} (${(t.position_value / 1000).toFixed(1)}%)</span></div>`;
  html += `<div class="tj-kv"><span class="k">Shares</span><span class="v">${Number(t.shares).toFixed(4)}</span></div>`;
  // Updated inline color: red=#ef4444, green=#22c55e
  html += `<div class="tj-kv"><span class="k">Stop Loss</span><span class="v" style="color:#ef4444">$${Number(t.stop_loss_price).toFixed(2)}</span></div>`;
  if (t.atr) html += `<div class="tj-kv"><span class="k">ATR</span><span class="v">$${Number(t.atr).toFixed(2)}</span></div>`;
  const tpDisplay = t.take_profit_type === 'trailing' ? 'Trailing (no ceiling)' : `$${Number(t.take_profit_price).toFixed(2)} [${t.take_profit_type}]`;
  html += `<div class="tj-kv"><span class="k">Target</span><span class="v" style="color:#22c55e">${tpDisplay}</span></div>`;
  if (t.status === 'closed') {
    html += `<div class="tj-kv" style="border-top:1px solid var(--border);margin-top:6px;padding-top:6px"><span class="k">Exit Price</span><span class="v">$${Number(t.exit_price).toFixed(2)}</span></div>`;
    html += `<div class="tj-kv"><span class="k">Exit Reason</span><span class="v">${escHtml(t.exit_reason || '')}</span></div>`;
    const rpnl = t.realized_pnl || 0;
    // Updated inline colors: green=#22c55e, red=#ef4444
    const rpCls = rpnl >= 0 ? 'color:#22c55e' : 'color:#ef4444';
    html += `<div class="tj-kv"><span class="k">Realized P&L</span><span class="v" style="${rpCls}">${rpnl >= 0 ? '+' : ''}$${Math.abs(rpnl).toFixed(2)} (${rpnl >= 0 ? '+' : ''}${Number(t.realized_pnl_pct || 0).toFixed(2)}%)</span></div>`;
    html += `<div class="tj-kv"><span class="k">Days Held</span><span class="v">${t.days_held || 0}</span></div>`;
  }
  html += '</div>';

  // Context at entry
  const vol = snapshot.volume || {};
  const patterns = snapshot.patterns_detected || [];
  const matched = snapshot.matched_patterns || [];
  if (vol.ratio || patterns.length || matched.length) {
    html += '<div class="tj-section" style="margin-top:12px"><h4>Context at Entry</h4>';
    if (vol.ratio) html += `<div class="tj-kv"><span class="k">Volume</span><span class="v">${vol.ratio}x avg (${vol.confirming ? 'confirming' : 'not confirming'})</span></div>`;
    if (patterns.length) html += `<div class="tj-kv"><span class="k">Patterns</span><span class="v">${patterns.map(p => p.name).join(', ')}</span></div>`;
    if (matched.length) html += `<div class="tj-kv"><span class="k">Strategies</span><span class="v">${matched.join(', ')}</span></div>`;
    const levels = snapshot.key_levels || [];
    if (levels.length) {
      const supports = levels.filter(l => l.type === 'support').slice(0, 2).map(l => '$' + Number(l.price).toFixed(2));
      const resists = levels.filter(l => l.type === 'resistance').slice(0, 2).map(l => '$' + Number(l.price).toFixed(2));
      if (supports.length) html += `<div class="tj-kv"><span class="k">Support</span><span class="v">${supports.join(', ')}</span></div>`;
      if (resists.length) html += `<div class="tj-kv"><span class="k">Resistance</span><span class="v">${resists.join(', ')}</span></div>`;
    }
    html += '</div>';
  }

  // Event log
  html += '<div class="tj-section" style="margin-top:12px"><h4>Event Log</h4>';
  if (logs.length) {
    for (const log of logs) {
      const typeCls = log.event_type || 'open';
      const time = (log.created_at || '').replace('T', ' ').substring(0, 19);
      html += `<div class="tj-log-entry">
        <span class="tj-log-type ${typeCls}">${escHtml(log.event_type)}</span>
        <span style="color:var(--text-dim);font-size:11px">${time}</span>
        <div style="margin-top:2px">${escHtml(log.description || '')}</div>
      </div>`;
    }
  } else {
    html += '<div style="font-size:12px;color:var(--text-dim)">No events recorded</div>';
  }
  html += '</div>';

  html += '</div></div>';
  return html;
}


// ── renderFundamentals ──────────────────────────────────────────────────────

function _fmtMetric(val, suffix = '') {
  if (val === null || val === undefined || val === '') return '<span style="color:var(--text-dim)">N/A</span>';
  if (typeof val === 'number') return val.toFixed(val % 1 === 0 ? 0 : 1) + suffix;
  return escHtml(String(val));
}

function _ratingBadge(rating) {
  if (!rating) return '';
  const cls = {
    'strong': 'positive', 'healthy': 'positive', 'attractive': 'positive', 'reasonable': 'positive',
    'high growth': 'positive', 'growing': 'positive', 'excellent': 'positive', 'reliable': 'positive',
    'bullish': 'positive', 'positive': 'positive', 'sustainable': 'positive',
    'weak': 'negative', 'expensive': 'negative', 'concerning': 'negative', 'declining': 'negative',
    'unreliable': 'negative', 'at risk': 'negative',
  }[rating.toLowerCase()] || '';
  return `<span class="badge ${cls}">${escHtml(rating.toUpperCase())}</span>`;
}

function _siloCard(title, silo) {
  if (!silo) return '';
  let html = `<div class="fundamental-card">`;
  html += `<div class="fundamental-card-header"><h4>${escHtml(title)}</h4>${_ratingBadge(silo.rating)}</div>`;

  // Reasons
  if (silo.reasons && silo.reasons.length) {
    html += '<ul class="fundamental-reasons">';
    for (const r of silo.reasons) html += `<li>${escHtml(r)}</li>`;
    html += '</ul>';
  }

  html += '</div>';
  return html;
}

export function renderFundamentals(data) {
  if (!data) return '<div class="empty"><p>No data</p></div>';

  let html = '';

  // Header
  const price = data.current_price ? '$' + Number(data.current_price).toFixed(2) : '';
  const changePct = data.quote?.change_percent || '';
  const chgCls = changeClass(changePct);
  html += `<div class="stock-header">
    <div class="stock-title">
      <h3>${escHtml(data.ticker || '')} — ${escHtml(data.name || '')}</h3>
      <span class="stock-meta">${escHtml(data.sector || '')} · ${escHtml(data.industry || '')}</span>
    </div>
    <div class="stock-price-group">
      <span class="stock-price">${price}</span>
      <span class="stock-change ${chgCls}">${formatPct(changePct)}</span>
    </div>
  </div>`;

  // Overall score badge
  const overallScore = data.overall_score || 0;
  const overallCls = overallScore >= 5 ? 'positive' : overallScore >= 0 ? '' : 'negative';
  html += `<div style="margin:12px 0 16px;display:flex;align-items:center;gap:8px">
    <span style="font-size:13px;color:var(--text-dim)">Fundamental Score</span>
    <span class="badge ${overallCls}" style="font-size:14px;padding:4px 12px">${overallScore >= 0 ? '+' : ''}${overallScore}</span>
  </div>`;

  // Silo cards in 2-column grid
  html += '<div class="fundamental-grid">';
  html += _siloCard('Valuation', data.valuation);
  html += _siloCard('Profitability', data.profitability);
  html += _siloCard('Growth', data.growth);
  html += _siloCard('Financial Health', data.financial_health);
  html += _siloCard('Earnings Quality', data.earnings_quality);
  html += _siloCard('Ownership', data.ownership);
  html += _siloCard('Dividend', data.dividend);
  html += '</div>';

  // Key metrics table
  html += '<div class="fundamental-metrics">';
  html += '<h4 style="margin:16px 0 8px">Key Metrics</h4>';
  html += '<div class="metrics-grid">';

  // Valuation metrics
  const v = data.valuation?.metrics || {};
  html += _metricRow('P/E', v.pe_ratio, 'x');
  html += _metricRow('Forward P/E', v.forward_pe, 'x');
  html += _metricRow('PEG', v.peg_ratio, '');
  html += _metricRow('P/B', v.price_to_book, 'x');
  html += _metricRow('P/S', v.price_to_sales, 'x');
  html += _metricRow('EV/EBITDA', v.ev_to_ebitda, 'x');
  html += _metricRow('Market Cap', v.market_cap_fmt, '');

  // Profitability
  const p = data.profitability?.metrics || {};
  html += _metricRow('Gross Margin', p.gross_margin, '%');
  html += _metricRow('Operating Margin', p.operating_margin, '%');
  html += _metricRow('Net Margin', p.net_margin, '%');
  html += _metricRow('ROE', p.roe, '%');
  html += _metricRow('ROA', p.roa, '%');

  // Growth
  const g = data.growth?.metrics || {};
  html += _metricRow('Revenue YoY', g.revenue_yoy, '%');
  html += _metricRow('EPS YoY', g.eps_yoy, '%');
  html += _metricRow('Revenue (Annual)', g.revenue_current, '');

  // Financial Health
  const h = data.financial_health?.metrics || {};
  html += _metricRow('Debt/Equity', h.debt_to_equity, '');
  html += _metricRow('Current Ratio', h.current_ratio, '');
  html += _metricRow('Interest Coverage', h.interest_coverage, 'x');
  html += _metricRow('Free Cash Flow', h.free_cash_flow_fmt, '');
  html += _metricRow('Net Position', h.net_position, '');

  // Earnings
  const eq = data.earnings_quality?.metrics || {};
  html += _metricRow('Beat Rate', eq.beat_rate, '%');
  html += _metricRow('Avg Surprise', eq.avg_surprise_pct, '%');

  // Dividend
  const dv = data.dividend?.metrics || {};
  html += _metricRow('Div Yield', dv.yield, '%');
  html += _metricRow('Payout Ratio', dv.payout_ratio, '%');

  html += '</div></div>';

  // Analyst ratings
  if (v.analyst_ratings) {
    html += '<div style="margin-top:16px"><h4>Analyst Ratings</h4>';
    html += '<div style="font-size:11px;color:var(--text-dim);margin-bottom:6px">Aggregated from major Wall Street brokerages via Alpha Vantage. Includes ratings from Goldman Sachs, Morgan Stanley, JP Morgan, Bank of America, Citi, and others. Updated as analysts publish new coverage.</div>';
    html += '<div class="analyst-bar">';
    const total = v.analyst_ratings_total || 1;
    for (const [label, count] of Object.entries(v.analyst_ratings)) {
      const pct = Math.round(count / total * 100);
      const cls = label.includes('Buy') ? 'buy' : label.includes('Sell') ? 'sell' : 'hold';
      html += `<div class="analyst-segment analyst-${cls}" style="width:${Math.max(pct, 5)}%" title="${label}: ${count} analysts">${count}</div>`;
    }
    html += '</div>';
    html += `<div style="font-size:11px;margin-top:4px;color:var(--text-dim);display:flex;justify-content:space-between">`;
    html += `<span>${total} analysts covering this stock</span>`;
    if (v.target_upside_pct !== undefined) {
      const upCls = v.target_upside_pct >= 0 ? 'positive' : 'negative';
      html += `<span>Consensus target: $${v.analyst_target?.toFixed(2) || '?'} <span class="${upCls}">(${v.target_upside_pct >= 0 ? '+' : ''}${v.target_upside_pct}%)</span></span>`;
    }
    html += '</div>';
    html += '</div>';
  }

  // Earnings history
  if (eq.history && eq.history.length) {
    html += '<div style="margin-top:16px"><h4>Earnings History</h4>';
    html += '<div class="table-wrap"><table class="data-table"><thead><tr><th>Date</th><th>Reported</th><th>Estimate</th><th>Surprise</th><th>Result</th></tr></thead><tbody>';
    for (const e of eq.history.slice(0, 8)) {
      const resCls = e.result === 'beat' ? 'positive' : e.result === 'miss' ? 'negative' : '';
      const surStr = e.surprise_pct !== null && e.surprise_pct !== undefined ? (e.surprise_pct >= 0 ? '+' : '') + e.surprise_pct.toFixed(1) + '%' : 'N/A';
      html += `<tr>
        <td>${escHtml(e.date || '')}</td>
        <td>${e.reported_eps !== null ? '$' + e.reported_eps.toFixed(2) : 'N/A'}</td>
        <td>${e.estimated_eps !== null ? '$' + e.estimated_eps.toFixed(2) : 'N/A'}</td>
        <td class="${resCls}">${surStr}</td>
        <td><span class="badge ${resCls}">${escHtml((e.result || '').toUpperCase())}</span></td>
      </tr>`;
    }
    html += '</tbody></table></div></div>';
  }

  // Margin trend
  if (p.margin_trend && p.margin_trend.length) {
    html += '<div style="margin-top:16px"><h4>Margin Trend (Quarterly)</h4>';
    html += '<div class="table-wrap"><table class="data-table"><thead><tr><th>Period</th><th>Gross</th><th>Operating</th><th>Net</th></tr></thead><tbody>';
    for (const m of p.margin_trend) {
      html += `<tr>
        <td>${escHtml(m.period || '')}</td>
        <td>${m.gross_margin !== undefined ? m.gross_margin.toFixed(1) + '%' : 'N/A'}</td>
        <td>${m.operating_margin !== undefined ? m.operating_margin.toFixed(1) + '%' : 'N/A'}</td>
        <td>${m.net_margin !== undefined ? m.net_margin.toFixed(1) + '%' : 'N/A'}</td>
      </tr>`;
    }
    html += '</tbody></table></div></div>';
  }

  // LLM Narrative
  const n = data.narrative;
  if (n) {
    html += '<div class="market-overview-box" style="margin-top:20px">';
    html += '<h4>Fundamental Analysis</h4>';
    if (n.summary) html += `<p>${escHtml(n.summary)}</p>`;

    if (n.strengths && n.strengths.length) {
      html += '<h5 style="margin-top:10px;color:var(--green)">Strengths</h5><ul>';
      for (const s of n.strengths) {
        const text = typeof s === 'string' ? s : (s.name || s.metric || Object.values(s).join(' — '));
        html += `<li>${escHtml(String(text))}</li>`;
      }
      html += '</ul>';
    }

    if (n.concerns && n.concerns.length) {
      html += '<h5 style="margin-top:10px;color:var(--red)">Concerns</h5><ul>';
      for (const c of n.concerns) {
        const text = typeof c === 'string' ? c : (c.name || c.metric || Object.values(c).join(' — '));
        html += `<li>${escHtml(String(text))}</li>`;
      }
      html += '</ul>';
    }

    const takes = [
      ['Valuation', n.valuation_take],
      ['Profitability', n.profitability_take],
      ['Growth', n.growth_take],
      ['Financial Health', n.health_take],
      ['Earnings', n.earnings_take],
      ['Ownership', n.ownership_take],
      ['Dividend', n.dividend_take],
    ];
    for (const [label, take] of takes) {
      if (take && take !== 'N/A') {
        html += `<div style="margin-top:8px"><strong>${label}:</strong> ${escHtml(take)}</div>`;
      }
    }
    html += '</div>';
  }

  // Duration
  if (data.duration_seconds) {
    html += `<div style="margin-top:12px;font-size:11px;color:var(--text-dim)">Analyzed in ${data.duration_seconds}s</div>`;
  }

  return html;
}

const _METRIC_DEFS = {
  'P/E': 'Price-to-Earnings ratio. Stock price divided by earnings per share. Lower = cheaper relative to earnings. S&P 500 avg ~20-25x.',
  'Forward P/E': 'P/E using next year\'s estimated earnings. Lower than trailing P/E means analysts expect earnings growth.',
  'PEG': 'P/E divided by earnings growth rate. PEG < 1 suggests the stock is undervalued relative to its growth. PEG > 2 is expensive.',
  'P/B': 'Price-to-Book ratio. Stock price divided by book value (assets minus liabilities) per share. Below 1 means trading below asset value.',
  'P/S': 'Price-to-Sales ratio. Market cap divided by annual revenue. Useful for unprofitable companies. Lower = cheaper.',
  'EV/EBITDA': 'Enterprise Value divided by EBITDA (earnings before interest, taxes, depreciation, amortization). Accounts for debt. Below 10 is generally cheap.',
  'Market Cap': 'Total market value of all outstanding shares. Large cap > $10B, Mid cap $2-10B, Small cap < $2B.',
  'Gross Margin': 'Revenue minus cost of goods sold, as a percentage of revenue. Higher = better pricing power and lower production costs.',
  'Operating Margin': 'Operating income as a percentage of revenue. Shows profitability from core business operations after operating expenses.',
  'Net Margin': 'Net income as a percentage of revenue. The bottom line — what percentage of every dollar in revenue becomes profit.',
  'ROE': 'Return on Equity. Net income divided by shareholder equity. How efficiently the company generates profit from shareholders\' investment. Above 15% is strong.',
  'ROA': 'Return on Assets. Net income divided by total assets. How efficiently the company uses all its assets to generate profit.',
  'Revenue YoY': 'Year-over-year revenue growth. Compares the most recent annual revenue to the prior year.',
  'EPS YoY': 'Year-over-year earnings per share growth. Compares the most recent annual EPS to the prior year.',
  'Revenue (Annual)': 'Total revenue for the most recent fiscal year.',
  'Debt/Equity': 'Total debt divided by shareholder equity. Below 1 means more equity than debt. Above 2 is heavily leveraged.',
  'Current Ratio': 'Current assets divided by current liabilities. Above 1 means the company can cover short-term obligations. Below 1 is a liquidity risk.',
  'Interest Coverage': 'Operating income divided by interest expense. How easily the company can pay interest on debt. Above 5x is comfortable.',
  'Free Cash Flow': 'Operating cash flow minus capital expenditures. The cash a company generates after maintaining its assets. Positive FCF = self-funding.',
  'Net Position': 'Cash minus total debt. "Net cash" means more cash than debt. "Net debt" means more debt than cash.',
  'Beat Rate': 'Percentage of recent quarters where reported EPS exceeded analyst estimates. 75%+ is reliable.',
  'Avg Surprise': 'Average earnings surprise percentage. Positive means the company consistently beats estimates.',
  'Div Yield': 'Annual dividend per share divided by stock price. The income return from holding the stock.',
  'Payout Ratio': 'Dividends paid as a percentage of earnings. Below 60% is sustainable. Above 90% may be at risk of cuts.',
};

function _metricRow(label, value, suffix) {
  if (value === null || value === undefined || value === '' || value === 'None') return '';
  let display;
  if (typeof value === 'number') {
    display = value.toFixed(Math.abs(value) < 10 ? 2 : 1) + suffix;
  } else {
    display = escHtml(String(value)) + suffix;
  }
  const def = _METRIC_DEFS[label];
  const infoBtn = def ? `<span class="metric-info" data-tip="${escHtml(def)}">?</span>` : '';
  return `<div class="metric-item"><span class="metric-label">${escHtml(label)}${infoBtn}</span><span class="metric-value">${display}</span></div>`;
}
