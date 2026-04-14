"""API endpoint tests for FastAPI routes.

Most endpoints make real API calls to Alpha Vantage and/or Ollama.
Tests that require external services are marked with @pytest.mark.integration
(for AV) or @pytest.mark.slow (for LLM) and are skipped by default.

Run with --run-integration and/or --run-slow to include them:
    uv run pytest tests/test_api.py --run-integration --run-slow -v
"""

import pytest
from fastapi.testclient import TestClient

from app.api.routes import app

# All tests in this module that hit AV are marked integration
pytestmark = pytest.mark.integration

client = TestClient(app)


# -- Health (pings Ollama) -----------------------------------------------------


def test_health_returns_200():
    """GET /health should return 200 with status, ollama, and database keys."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "ollama" in data
    assert "database" in data


# -- Stock Price Action (requires AV + Ollama) ---------------------------------


@pytest.mark.slow
def test_stock_price_action_returns_200():
    """GET /stock/AAPL/price-action should return 200 with score, chart_data, levels, narrative."""
    resp = client.get("/stock/AAPL/price-action")
    assert resp.status_code == 200
    data = resp.json()
    assert "score" in data
    assert "chart_data" in data
    assert "levels" in data
    assert "narrative" in data


def test_stock_price_action_invalid_ticker():
    """GET /stock/INVALID!!!/price-action should return 400 (ticker validation)."""
    resp = client.get("/stock/INVALID!!!/price-action")
    assert resp.status_code == 400


# -- Fundamentals (requires AV + Ollama) ---------------------------------------


@pytest.mark.slow
def test_stock_fundamentals_returns_200():
    """GET /stock/AAPL/fundamentals should return 200 with silos key."""
    resp = client.get("/stock/AAPL/fundamentals")
    assert resp.status_code == 200
    data = resp.json()
    assert "silos" in data


# -- CSRF Guard ----------------------------------------------------------------


def test_post_without_json_content_type_returns_403():
    """POST /scan without Content-Type: application/json should be blocked by CSRF guard."""
    resp = client.post("/scan", headers={"Content-Type": "text/plain"})
    assert resp.status_code == 403
    data = resp.json()
    assert "Content-Type" in data.get("detail", "")
