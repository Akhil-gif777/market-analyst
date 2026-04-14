"""
End-to-end browser tests for the Market Analyst web UI.

Prerequisites:
  - The server must already be running at http://localhost:8000
    Start it with: uv run server
  - Playwright browsers must be installed: uv run playwright install chromium

Run:
  uv run pytest tests/test_e2e.py --run-e2e             # all E2E tests
  uv run pytest tests/test_e2e.py --run-e2e -m "not slow"  # skip LLM-dependent tests
"""

import re

import pytest
from playwright.sync_api import Page, expect

BASE_URL = "http://localhost:8000"

# All tests in this file require a running server.
pytestmark = pytest.mark.e2e

# Tab names as they appear in the nav, mapped to their data-panel attribute.
TAB_MAP = {
    "Market": "market",
    "Analysis": "analyze",
    "Stock": "stock-analysis",
    "Backtest": "backtest",
    "Paper Trading": "paper-trading",
    "Journal": "trade-journal",
}

# Reusable regex for matching a CSS class list that contains "active".
_RE_ACTIVE = re.compile(r"active")


# ---------------------------------------------------------------------------
# 1. Home page loads with all tabs
# ---------------------------------------------------------------------------
def test_home_page_loads(page: Page):
    """Verify the page title and all 6 navigation tabs are present."""
    page.goto(BASE_URL)

    # Page title is "Market Analyst"
    expect(page).to_have_title("Market Analyst")

    # Main nav exists
    nav = page.locator("#main-nav")
    expect(nav).to_be_visible()

    # All 6 tab buttons are present
    for label, panel_id in TAB_MAP.items():
        tab_btn = page.locator(f'button.tab[data-panel="{panel_id}"]')
        expect(tab_btn).to_be_visible()
        expect(tab_btn).to_have_text(label)


# ---------------------------------------------------------------------------
# 2. Stock analysis renders score, charts, and layers
# ---------------------------------------------------------------------------
def test_stock_analysis_renders(page: Page):
    """Enter AAPL, run Price Action analysis. Verify score, charts, and layers."""
    page.goto(BASE_URL)

    # Navigate to Stock tab
    page.click('button.tab[data-panel="stock-analysis"]')
    expect(page.locator("#panel-stock-analysis")).to_have_class(_RE_ACTIVE)

    # Enter ticker and click analyze
    page.fill("#stock-ticker-input", "AAPL")
    page.click("#btn-stock-analyze")

    # Wait for the skeleton to disappear and real content to appear.
    # The score bar container is rendered once the API returns.
    score_bar = page.locator(".score-bar-container")
    score_bar.wait_for(state="visible", timeout=30_000)

    # Score section is visible — contains "Confluence Score:"
    expect(score_bar).to_contain_text("Confluence Score:")

    # Chart containers exist (rendered by renderStockCharts)
    expect(page.locator("#chart-daily")).to_be_attached()
    expect(page.locator("#chart-weekly")).to_be_attached()

    # Layer/scoring breakdown is rendered — score-card elements inside market-grid
    layer_cards = page.locator(".score-card")
    expect(layer_cards.first).to_be_visible()
    # Should have multiple layer cards (12 layers + alignment)
    assert layer_cards.count() >= 5, (
        f"Expected at least 5 layer cards, got {layer_cards.count()}"
    )

    # "Analyzed in" duration text appears
    analyzed_text = page.locator("text=Analyzed in")
    expect(analyzed_text).to_be_visible()


# ---------------------------------------------------------------------------
# 3. Narrative loads asynchronously
# ---------------------------------------------------------------------------
@pytest.mark.slow
def test_narrative_loads_async(page: Page):
    """Verify the narrative placeholder appears and eventually loads LLM content."""
    page.goto(BASE_URL)

    # Navigate to Stock tab and run analysis
    page.click('button.tab[data-panel="stock-analysis"]')
    page.fill("#stock-ticker-input", "AAPL")
    page.click("#btn-stock-analyze")

    # Wait for the initial analysis to render
    page.locator(".score-bar-container").wait_for(state="visible", timeout=30_000)

    # Narrative container should exist
    narrative = page.locator("#narrative-container")
    expect(narrative).to_be_attached()

    # Initially shows the loading placeholder text (or content if already loaded).
    # The loading text is "Loading AI narrative..." — check it appeared at some point
    # by the time analysis rendered, or the narrative already replaced it.

    # Wait for the narrative to finish loading (up to 120s for LLM).
    # Once loaded, the container will have a .market-overview-box with actual sections
    # (headline, Market Structure, etc.) instead of just the loading text.
    page.locator("#narrative-container .one-liner").wait_for(
        state="visible", timeout=120_000
    )

    # Verify narrative has expected section headings
    narrative_text = narrative.inner_text()
    # The narrative should contain at least one of these sections
    expected_sections = ["Market Structure", "Key Levels", "Pattern Context", "Volume"]
    found_sections = [s for s in expected_sections if s in narrative_text]
    assert len(found_sections) >= 1, (
        f"Expected at least one narrative section from {expected_sections}, "
        f"but found none in narrative text"
    )


# ---------------------------------------------------------------------------
# 4. Daily chart has MA lines rendered
# ---------------------------------------------------------------------------
def test_chart_has_ma_lines(page: Page):
    """After stock analysis, verify daily chart has canvas and no JS errors."""
    page.goto(BASE_URL)

    js_errors = []
    page.on("pageerror", lambda err: js_errors.append(str(err)))

    # Navigate to Stock tab and run analysis
    page.click('button.tab[data-panel="stock-analysis"]')
    page.fill("#stock-ticker-input", "AAPL")
    page.click("#btn-stock-analyze")

    # Wait for analysis to render
    page.locator(".score-bar-container").wait_for(state="visible", timeout=30_000)

    # The daily chart panel should be visible (it is the default active tab)
    daily_panel = page.locator("#chart-panel-daily")
    expect(daily_panel).to_be_visible()

    # The daily chart div should contain a canvas element (Lightweight Charts renders
    # to canvas)
    daily_canvas = page.locator("#chart-daily canvas")
    expect(daily_canvas.first).to_be_attached()

    # Verify no JS errors occurred during rendering
    assert len(js_errors) == 0, f"JS errors during chart rendering: {js_errors}"

    # The chart-daily container should have at least one canvas if the chart was created.
    canvas_count = daily_canvas.count()
    assert canvas_count >= 1, (
        f"Expected at least 1 canvas in daily chart, got {canvas_count}"
    )


# ---------------------------------------------------------------------------
# 5. Weekly chart has 10W SMA
# ---------------------------------------------------------------------------
def test_weekly_chart_has_10w_sma(page: Page):
    """After stock analysis, verify weekly chart has canvas and 10W SMA data."""
    page.goto(BASE_URL)

    # Navigate to Stock tab and run analysis
    page.click('button.tab[data-panel="stock-analysis"]')
    page.fill("#stock-ticker-input", "AAPL")
    page.click("#btn-stock-analyze")

    # Wait for analysis to render
    page.locator(".score-bar-container").wait_for(state="visible", timeout=30_000)

    # Switch to weekly chart tab
    page.click("text=Weekly")

    weekly_panel = page.locator("#chart-panel-weekly")
    expect(weekly_panel).to_be_visible()

    # Weekly chart should have a canvas element
    weekly_canvas = page.locator("#chart-weekly canvas")
    expect(weekly_canvas.first).to_be_attached()

    # Check that the API response had weekly_ma_10 data by evaluating JS.
    # We fetch the price-action endpoint directly and check the response shape.
    has_weekly_ma = page.evaluate(
        """() => {
        return fetch('/stock/AAPL/price-action')
            .then(r => r.json())
            .then(data => {
                const cd = data.chart_data || {};
                return {
                    has_weekly_ma_10: Array.isArray(cd.weekly_ma_10) && cd.weekly_ma_10.length > 0,
                    has_weekly_candles: Array.isArray(cd.weekly_candles) && cd.weekly_candles.length > 0,
                };
            });
    }"""
    )
    assert has_weekly_ma["has_weekly_candles"], (
        "Expected weekly candles in API response"
    )
    assert has_weekly_ma["has_weekly_ma_10"], (
        "Expected weekly_ma_10 data in API response"
    )


# ---------------------------------------------------------------------------
# 6. Fundamentals tab renders silos, metrics, and score
# ---------------------------------------------------------------------------
def test_fundamentals_tab(page: Page):
    """Enter GOOGL, click Fundamentals. Verify silo cards, metrics, and score."""
    page.goto(BASE_URL)

    # Navigate to Stock tab
    page.click('button.tab[data-panel="stock-analysis"]')
    expect(page.locator("#panel-stock-analysis")).to_have_class(_RE_ACTIVE)

    # Enter ticker and click Fundamentals
    page.fill("#stock-ticker-input", "GOOGL")
    page.click("#btn-stock-fundamentals")

    # Wait for fundamental content to render (the skeleton disappears, cards appear)
    fundamentals_container = page.locator("#stock-fundamentals-content")
    fundamentals_container.locator(".fundamental-card").first.wait_for(
        state="visible", timeout=30_000
    )

    # Fundamental silo cards are rendered (valuation, profitability, etc.)
    cards = fundamentals_container.locator(".fundamental-card")
    assert cards.count() >= 3, (
        f"Expected at least 3 fundamental cards, got {cards.count()}"
    )

    # Check that expected silo titles are present
    card_text = fundamentals_container.inner_text()
    expected_silos = ["Valuation", "Profitability", "Growth", "Financial Health"]
    for silo in expected_silos:
        assert silo in card_text, (
            f"Expected silo '{silo}' in fundamentals output"
        )

    # Metrics grid appears
    metrics_grid = fundamentals_container.locator(".metrics-grid")
    expect(metrics_grid).to_be_visible()

    # Score badge appears (the Fundamental Score badge)
    score_badge = fundamentals_container.locator(".badge")
    expect(score_badge.first).to_be_visible()


# ---------------------------------------------------------------------------
# 7. Ticker validation shows error for invalid input
# ---------------------------------------------------------------------------
def test_ticker_validation(page: Page):
    """Enter an invalid ticker and verify an error message appears."""
    page.goto(BASE_URL)

    # Navigate to Stock tab
    page.click('button.tab[data-panel="stock-analysis"]')

    # Enter invalid ticker
    page.fill("#stock-ticker-input", "!!!")
    page.click("#btn-stock-analyze")

    # The API returns 400 for invalid ticker format, which triggers the error toast
    # and renders an error message in the content container.
    # Wait for the error to appear — either as a toast or in the content div.
    error_visible = page.locator(
        "#stock-analysis-content .empty, .toast.error, .toast-container .toast"
    )
    error_visible.first.wait_for(state="visible", timeout=10_000)

    # Verify the error message is present somewhere on the page
    page_text = page.locator("body").inner_text()
    assert (
        "failed" in page_text.lower()
        or "invalid" in page_text.lower()
        or "error" in page_text.lower()
    ), "Expected an error message on the page for invalid ticker"


# ---------------------------------------------------------------------------
# 8. Tab navigation works for all 6 tabs
# ---------------------------------------------------------------------------
def test_tab_navigation(page: Page):
    """Click through all 6 tabs and verify the correct panel becomes visible."""
    page.goto(BASE_URL)

    for label, panel_id in TAB_MAP.items():
        # Click the tab button
        page.click(f'button.tab[data-panel="{panel_id}"]')

        # The corresponding panel should have the 'active' class
        panel = page.locator(f"#panel-{panel_id}")
        expect(panel).to_have_class(_RE_ACTIVE)

        # The tab button should also have 'active' class
        tab_btn = page.locator(f'button.tab[data-panel="{panel_id}"]')
        expect(tab_btn).to_have_class(_RE_ACTIVE)

        # Other panels should not be active
        for other_label, other_id in TAB_MAP.items():
            if other_id != panel_id:
                other_panel = page.locator(f"#panel-{other_id}")
                expect(other_panel).not_to_have_class(_RE_ACTIVE)
