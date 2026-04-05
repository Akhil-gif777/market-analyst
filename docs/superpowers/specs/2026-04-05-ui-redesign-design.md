# UI Redesign: Modern Fintech Aesthetic

## Overview

Redesign the Market Analyst UI from a functional dark-theme single-file HTML into a polished, modern fintech application inspired by Robinhood/Webull. The focus is on clean spacing, gradient accents, spring-based animations, skeleton loaders, and progress bars for long operations.

## Decisions

- **Vibe:** Modern fintech (Robinhood/Webull) -- clean, spacious, gradient accents, smooth transitions
- **File structure:** Split into separate HTML/CSS/JS files
- **Navigation:** Horizontal tab bar with animated gradient underline
- **Loading:** Skeleton loaders for fast loads, top progress bar for long operations
- **Animation library:** `motion` (~15KB, loaded via CDN from jsdelivr) for spring physics, staggered reveals, number counters
- **Existing deps:** `lightweight-charts@4` stays (also CDN)
- **No build step:** all JS uses vanilla ES modules or IIFE bundles from CDN

## File Structure

```
app/static/
  index.html          # Slim HTML shell -- structure only, no inline styles/scripts
  css/
    styles.css         # All styles (design tokens, components, layouts, animations)
  js/
    app.js             # App state, routing, panel switching, event wiring
    api.js             # All fetch() calls to the backend, centralized
    components.js      # Render functions (cards, tables, skeletons, toasts)
    transitions.js     # Motion library wrappers, staggered reveals, number counters
```

## Design Tokens

```css
:root {
  --bg:          #0a0e17;
  --surface:     #111827;
  --surface-2:   #1a2234;
  --border:      #1e293b;
  --text:        #e2e8f0;
  --text-dim:    #64748b;
  --accent:      #6366f1;
  --accent-glow: rgba(99,102,241,0.15);
  --green:       #22c55e;
  --red:         #ef4444;
  --yellow:      #eab308;
  --gradient:    linear-gradient(135deg, #6366f1, #8b5cf6);
}
```

Shift from GitHub's gray-blue to an indigo/violet gradient accent. All interactive elements (buttons, active tabs, progress bars) use the gradient.

## Navigation & Layout

### Top Bar
- Logo left: "Market Analyst" with a small gradient pulse dot (live indicator)
- Health badge right: pill-shaped with subtle glow when healthy

### Tab Bar
- Tabs: `Market | Analysis | Stock | Backtest | Paper Trading | Journal`
- Active tab has a gradient underline that slides to the selected tab using `motion`'s spring animation (tracks position + width)
- Tabs transition between `--text-dim` and `--text` (200ms)
- Hover: text brightens + faint `--accent-glow` background

### Panel Transitions
- Outgoing panel: fades out + slides down slightly (150ms)
- Incoming panel: fades in + slides up from 12px below (300ms, spring easing)
- `min-height` on panels to prevent content reflow

### Layout
- Max-width: 1400px (up from 1200px)
- Content padding: 32px

## Cards & Data Display

### Stat Cards
- Rounded corners (12px), subtle `box-shadow` instead of borders
- Background: `--surface` with faint top-border gradient on the primary card (total value)
- Numbers animate up/down using `motion`'s spring counter on data load
- Positive values pulse green briefly on update, negative pulse red
- Hover: card lifts (`translateY(-2px)`), shadow deepens

### Tables
- Rows fade in with staggered delay (30ms per row) on load
- Hover: subtle `--accent-glow` left border + background shift
- Sortable column headers with chevron indicator
- Ticker symbols in pill badges with faint gradient background

### Event Cards
- Severity badge has a soft glow matching its color (high = red glow, medium = yellow)
- Expand/collapse uses `motion` spring animation for height (no `display:none` toggle)
- Causal chain tree lines animate drawing downward on expand

### Score Bars
- Bar fills animate with spring easing from 0 to value
- Color transitions across red-yellow-green spectrum based on score
- Score number counts up beside the bar

## Loading States

### Skeleton Loaders (fast loads: market data, events, portfolio)
- Gray placeholder shapes matching the actual layout (card rectangles, table rows, text lines)
- Shimmer animation: gradient highlight sweeps left-to-right on loop (`@keyframes shimmer`, 1.5s)
- Base: `--surface`, shimmer highlight: `--surface-2`
- 3-4 skeleton rows/cards shown by default

### Top Progress Bar (long operations: full analysis, paper scan, backtest)
- Thin (3px) bar fixed to top of viewport
- Gradient fill (indigo to violet)
- Indeterminate mode only (backend has no progress events): bar oscillates with pulsing glow
- Completes with brief flash + fade out when the API call returns

### Operation Status Panel
- Dark card below action button during long ops
- Pulsing dot + status text: "Scanning news...", "Building causal chains...", "Evaluating stocks..."
- Elapsed time counter ticking up

### Toasts
- Slide in from bottom-right with spring animation
- Color-coded left border: green (success), red (error), indigo (info)
- Auto-dismiss after 4s with shrinking progress line at bottom
- Stack multiple toasts with 8px gap

## Motion & Micro-interactions

### Page Load
- Logo fades in, tabs stagger in left-to-right (50ms delay each)
- Default panel (Market) content fades up

### Buttons
- Hover: scale(1.02), background brightens
- Active/press: scale(0.97) for tactile click feel
- Primary buttons: gradient background with shimmer sweep on hover
- Disabled: desaturated, no pointer events

### Charts
- Container fades in, chart data crossfades on timeframe switch (200ms)

### Scroll Reveals
- Cards below the fold fade in + slide up on scroll into view (IntersectionObserver + `motion`)
- Trigger once only, no re-animation

### Number Transitions
- All monetary values, percentages, and counts animate between old and new values
- Spring easing, ~400ms duration
- Color flashes green/red on change direction

### Hover States
- Cards, table rows, buttons, badges, ticker pills: all have 150ms transitions
- No element feels "dead" on mouseover

## Scope Boundaries

This redesign covers:
- Visual design (colors, spacing, typography, shadows)
- Animation and transition layer
- File structure split (HTML/CSS/JS)
- Loading states (skeletons, progress bars, toasts)

This redesign does NOT change:
- API endpoints or backend logic
- Data flow or business logic
- Feature set (no new panels or features added)
- lightweight-charts configuration (beyond container styling)

## Migration Strategy

The existing `index.html` (3059 lines) is replaced by the new file structure. All existing functionality is preserved -- every panel, every API call, every render function. The JavaScript is reorganized but functionally equivalent.

The static file serving in `routes.py` already mounts `/static`, so `css/` and `js/` subdirectories will be served automatically. Only `index.html` is served via the root `GET /` route -- no backend changes needed.
