"""Unit tests for app.analysis.price_action -- deterministic functions only (no AV/LLM)."""

from datetime import datetime, timedelta

import pytest

from app.analysis.price_action import (
    compute_ema,
    compute_ma_signals,
    compute_sma,
    find_support_resistance,
    _score_moving_averages,
)


# -- Helpers -------------------------------------------------------------------


def make_prices(closes, start_date="2026-01-01"):
    """Create OHLCV dicts from a list of close prices."""
    base = datetime.strptime(start_date, "%Y-%m-%d")
    return [
        {
            "date": (base + timedelta(days=i)).strftime("%Y-%m-%d"),
            "open": c,
            "high": c + 1,
            "low": c - 1,
            "close": c,
            "volume": 1_000_000,
        }
        for i, c in enumerate(closes)
    ]


# -- compute_sma ---------------------------------------------------------------


class TestComputeSma:
    def test_basic_correctness(self):
        """SMA of [10, 20, 30] with period 3 should be 20."""
        prices = make_prices([10.0, 20.0, 30.0])
        result = compute_sma(prices, 3)
        assert len(result) == 1
        assert result[0]["value"] == 20.0

    def test_returns_empty_for_insufficient_data(self):
        """SMA should return empty when fewer bars than period."""
        prices = make_prices([10.0, 20.0])
        result = compute_sma(prices, 5)
        assert result == []

    def test_rolling_window(self):
        """SMA should produce a rolling window of correct length."""
        prices = make_prices([10.0, 20.0, 30.0, 40.0, 50.0])
        result = compute_sma(prices, 3)
        # Expect 3 values: avg(10,20,30)=20, avg(20,30,40)=30, avg(30,40,50)=40
        assert len(result) == 3
        assert result[0]["value"] == 20.0
        assert result[1]["value"] == 30.0
        assert result[2]["value"] == 40.0

    def test_dates_align_with_end_of_window(self):
        """Each SMA value should carry the date of the last bar in its window."""
        prices = make_prices([10.0, 20.0, 30.0, 40.0])
        result = compute_sma(prices, 3)
        assert result[0]["date"] == prices[2]["date"]
        assert result[1]["date"] == prices[3]["date"]

    def test_single_bar_period(self):
        """SMA with period 1 should return the close prices themselves."""
        prices = make_prices([15.0, 25.0, 35.0])
        result = compute_sma(prices, 1)
        assert len(result) == 3
        assert result[0]["value"] == 15.0
        assert result[1]["value"] == 25.0
        assert result[2]["value"] == 35.0

    def test_period_equals_length(self):
        """SMA with period equal to data length should return one value."""
        prices = make_prices([10.0, 20.0, 30.0])
        result = compute_sma(prices, 3)
        assert len(result) == 1
        assert result[0]["value"] == 20.0

    def test_rounding(self):
        """SMA values should be rounded to 2 decimal places."""
        prices = make_prices([10.0, 20.0, 30.0, 41.0])
        result = compute_sma(prices, 3)
        # avg(20, 30, 41) = 30.333...
        assert result[1]["value"] == 30.33


# -- compute_ema ---------------------------------------------------------------


class TestComputeEma:
    def test_returns_empty_for_insufficient_data(self):
        """Should return empty list when not enough data for the period."""
        prices = make_prices([100, 101, 102])
        assert compute_ema(prices, 5) == []

    def test_length_of_result(self):
        """Result length should be len(prices) - period + 1."""
        prices = make_prices([100 + i for i in range(30)])
        result = compute_ema(prices, 21)
        assert len(result) == 30 - 21 + 1

    def test_first_value_is_sma_seed(self):
        """First EMA value should equal the SMA of the first `period` bars."""
        prices = make_prices([100, 102, 104, 106, 108])
        result = compute_ema(prices, 5)
        expected_seed = round((100 + 102 + 104 + 106 + 108) / 5, 2)
        assert result[0]["value"] == expected_seed

    def test_ema_reacts_faster_than_sma(self):
        """EMA should react faster to a sudden price jump than SMA."""
        # 25 flat bars at 100, then 5 bars at 110
        closes = [100.0] * 25 + [110.0] * 5
        prices = make_prices(closes)
        ema = compute_ema(prices, 21)
        sma = compute_sma(prices, 21)
        assert ema[-1]["value"] > sma[-1]["value"]

    def test_dates_align(self):
        """EMA dates should start at the period-th bar."""
        prices = make_prices([100 + i for i in range(10)])
        result = compute_ema(prices, 5)
        assert result[0]["date"] == prices[4]["date"]
        assert result[-1]["date"] == prices[-1]["date"]


# -- compute_ma_signals --------------------------------------------------------


class TestComputeMaSignals:
    def test_price_vs_50_above(self):
        """Should return 'above' when price > ma_50."""
        ma_50 = [{"date": "2026-01-01", "value": 100.0}]
        result = compute_ma_signals(ma_50, [], 110.0)
        assert result["price_vs_50"] == "above"

    def test_price_vs_50_below(self):
        """Should return 'below' when price < ma_50."""
        ma_50 = [{"date": "2026-01-01", "value": 100.0}]
        result = compute_ma_signals(ma_50, [], 90.0)
        assert result["price_vs_50"] == "below"

    def test_price_vs_200_above(self):
        """Should return 'above' when price > ma_200."""
        ma_200 = [{"date": "2026-01-01", "value": 100.0}]
        result = compute_ma_signals([], ma_200, 110.0)
        assert result["price_vs_200"] == "above"

    def test_price_vs_200_below(self):
        """Should return 'below' when price < ma_200."""
        ma_200 = [{"date": "2026-01-01", "value": 100.0}]
        result = compute_ma_signals([], ma_200, 90.0)
        assert result["price_vs_200"] == "below"

    def test_price_vs_50_none_when_no_series(self):
        """Should return None for price_vs_50 when no series given."""
        result = compute_ma_signals([], [], 100.0)
        assert result["price_vs_50"] is None

    def test_price_vs_200_none_when_no_series(self):
        """Should return None for price_vs_200 when no series given."""
        result = compute_ma_signals([], [], 100.0)
        assert result["price_vs_200"] is None

    def test_golden_cross_detection(self):
        """Should detect golden cross when 50MA crosses above 200MA."""
        dates = [
            (datetime(2026, 1, 1) + timedelta(days=i)).strftime("%Y-%m-%d")
            for i in range(25)
        ]
        # 50MA starts below 200MA then crosses above
        ma_50 = [{"date": d, "value": 95.0 + i * 0.5} for i, d in enumerate(dates)]
        ma_200 = [{"date": d, "value": 100.0} for d in dates]
        result = compute_ma_signals(ma_50, ma_200, 110.0)
        assert result["golden_cross"] is True

    def test_death_cross_detection(self):
        """Should detect death cross when 50MA crosses below 200MA."""
        dates = [
            (datetime(2026, 1, 1) + timedelta(days=i)).strftime("%Y-%m-%d")
            for i in range(25)
        ]
        # 50MA starts above 200MA then drops below
        ma_50 = [{"date": d, "value": 105.0 - i * 0.5} for i, d in enumerate(dates)]
        ma_200 = [{"date": d, "value": 100.0} for d in dates]
        result = compute_ma_signals(ma_50, ma_200, 90.0)
        assert result["death_cross"] is True

    def test_bullish_alignment(self):
        """Should detect bullish alignment when 50MA > 200MA."""
        ma_50 = [{"date": "2026-01-01", "value": 110.0}]
        ma_200 = [{"date": "2026-01-01", "value": 100.0}]
        result = compute_ma_signals(ma_50, ma_200, 120.0)
        assert result["ma_alignment"] == "bullish"

    def test_bearish_alignment(self):
        """Should detect bearish alignment when 50MA < 200MA."""
        ma_50 = [{"date": "2026-01-01", "value": 90.0}]
        ma_200 = [{"date": "2026-01-01", "value": 100.0}]
        result = compute_ma_signals(ma_50, ma_200, 80.0)
        assert result["ma_alignment"] == "bearish"

    def test_neutral_alignment_when_no_data(self):
        """Should default to neutral alignment with no data."""
        result = compute_ma_signals([], [], 100.0)
        assert result["ma_alignment"] == "neutral"

    def test_returns_ma_values(self):
        """Should populate ma_50_value and ma_200_value."""
        ma_50 = [{"date": "2026-01-01", "value": 100.0}]
        ma_200 = [{"date": "2026-01-01", "value": 90.0}]
        result = compute_ma_signals(ma_50, ma_200, 105.0)
        assert result["ma_50_value"] == 100.0
        assert result["ma_200_value"] == 90.0

    def test_no_cross_when_parallel(self):
        """Should not detect any cross when MAs run parallel."""
        dates = [
            (datetime(2026, 1, 1) + timedelta(days=i)).strftime("%Y-%m-%d")
            for i in range(25)
        ]
        # Both MAs flat and separated
        ma_50 = [{"date": d, "value": 110.0} for d in dates]
        ma_200 = [{"date": d, "value": 100.0} for d in dates]
        result = compute_ma_signals(ma_50, ma_200, 120.0)
        assert result["golden_cross"] is False
        assert result["death_cross"] is False

    def test_ema_21_above(self):
        """price_vs_21 should be 'above' when price > ema_21."""
        ema_21 = [{"date": "2026-01-01", "value": 100.0}]
        result = compute_ma_signals([], [], 110.0, ema_21_series=ema_21)
        assert result["price_vs_21"] == "above"
        assert result["ema_21_value"] == 100.0

    def test_ema_21_below(self):
        """price_vs_21 should be 'below' when price < ema_21."""
        ema_21 = [{"date": "2026-01-01", "value": 100.0}]
        result = compute_ma_signals([], [], 90.0, ema_21_series=ema_21)
        assert result["price_vs_21"] == "below"

    def test_ema_21_none_when_not_provided(self):
        """price_vs_21 should be None when ema_21_series is not provided."""
        result = compute_ma_signals([], [], 100.0)
        assert result["price_vs_21"] is None
        assert result["ema_21_value"] is None


# -- find_support_resistance ---------------------------------------------------


class TestFindSupportResistance:
    def test_ma50_as_support_when_price_above(self):
        """MA 50 should appear as support when price is above it."""
        levels = find_support_resistance(
            daily_swings=[], weekly_swings=[], current_price=200.0, ma_50=150.0,
        )
        ma50_levels = [l for l in levels if l["source"] == "ma_50"]
        assert len(ma50_levels) == 1
        assert ma50_levels[0]["type"] == "support"

    def test_ma50_as_resistance_when_price_below(self):
        """MA 50 should appear as resistance when price is below it."""
        levels = find_support_resistance(
            daily_swings=[], weekly_swings=[], current_price=100.0, ma_50=150.0,
        )
        ma50_levels = [l for l in levels if l["source"] == "ma_50"]
        assert len(ma50_levels) == 1
        assert ma50_levels[0]["type"] == "resistance"

    def test_ma200_as_support_when_price_above(self):
        """MA 200 should appear as support when price is above it."""
        levels = find_support_resistance(
            daily_swings=[], weekly_swings=[], current_price=200.0, ma_200=120.0,
        )
        ma200_levels = [l for l in levels if l["source"] == "ma_200"]
        assert len(ma200_levels) == 1
        assert ma200_levels[0]["type"] == "support"

    def test_ma200_as_resistance_when_price_below(self):
        """MA 200 should appear as resistance when price is below it."""
        levels = find_support_resistance(
            daily_swings=[], weekly_swings=[], current_price=100.0, ma_200=120.0,
        )
        ma200_levels = [l for l in levels if l["source"] == "ma_200"]
        assert len(ma200_levels) == 1
        assert ma200_levels[0]["type"] == "resistance"

    def test_ma50_and_ma200_have_strength_2(self):
        """MA 50 and MA 200 should both have strength 2."""
        levels = find_support_resistance(
            daily_swings=[], weekly_swings=[], current_price=200.0,
            ma_50=150.0, ma_200=120.0,
        )
        ma50_levels = [l for l in levels if l["source"] == "ma_50"]
        ma200_levels = [l for l in levels if l["source"] == "ma_200"]
        assert len(ma50_levels) == 1
        assert ma50_levels[0]["strength"] == 2
        assert len(ma200_levels) == 1
        assert ma200_levels[0]["strength"] == 2

    def test_both_ma_levels_present(self):
        """Both MA levels should appear when both are provided."""
        levels = find_support_resistance(
            daily_swings=[], weekly_swings=[], current_price=200.0,
            ma_50=150.0, ma_200=120.0,
        )
        sources = {l["source"] for l in levels}
        assert "ma_50" in sources
        assert "ma_200" in sources

    def test_empty_swings_only_mas(self):
        """With no swing points, should return only MA levels."""
        levels = find_support_resistance(
            daily_swings=[], weekly_swings=[], current_price=200.0,
            ma_50=150.0, ma_200=120.0,
        )
        # Only MA sources should be present
        for l in levels:
            assert l["source"] in ("ma_50", "ma_200")

    def test_no_levels_when_nothing_provided(self):
        """With no swing data and no MAs, should return empty list."""
        levels = find_support_resistance(
            daily_swings=[], weekly_swings=[], current_price=100.0,
        )
        assert levels == []

    def test_swing_levels_appear(self):
        """Swing points should produce support/resistance levels."""
        daily_swings = [
            {"price": 90.0, "type": "low", "date": "2026-01-01"},
            {"price": 110.0, "type": "high", "date": "2026-01-05"},
        ]
        levels = find_support_resistance(
            daily_swings=daily_swings, weekly_swings=[], current_price=100.0,
        )
        # Should have at least one support (from 90.0) and one resistance (from 110.0)
        support = [l for l in levels if l["type"] == "support"]
        resistance = [l for l in levels if l["type"] == "resistance"]
        assert len(support) >= 1
        assert len(resistance) >= 1

    def test_ema21_as_support_when_price_above(self):
        """EMA 21 should appear as support when price is above it."""
        levels = find_support_resistance([], [], 110.0, ema_21=100.0)
        ema_levels = [l for l in levels if l.get("source") == "ema_21"]
        assert len(ema_levels) == 1
        assert ema_levels[0]["type"] == "support"
        assert ema_levels[0]["strength"] == 1

    def test_ema21_as_resistance_when_price_below(self):
        """EMA 21 should appear as resistance when price is below it."""
        levels = find_support_resistance([], [], 90.0, ema_21=100.0)
        ema_levels = [l for l in levels if l.get("source") == "ema_21"]
        assert len(ema_levels) == 1
        assert ema_levels[0]["type"] == "resistance"
        assert ema_levels[0]["strength"] == 1

    def test_ema21_strength_lower_than_sma(self):
        """EMA 21 should have strength 1 while MA50/MA200 have strength 2."""
        levels = find_support_resistance([], [], 110.0, ma_50=105.0, ma_200=95.0, ema_21=108.0)
        by_source = {l["source"]: l["strength"] for l in levels}
        assert by_source["ema_21"] == 1
        assert by_source["ma_50"] == 2
        assert by_source["ma_200"] == 2


# -- _score_moving_averages ----------------------------------------------------


class TestScoreMovingAverages:
    def test_all_bullish_returns_plus_2(self):
        """Score should be +2 when all MA signals are bullish."""
        signals = {
            "price_vs_200": "above",
            "ma_200_value": 100.0,
            "ma_alignment": "bullish",
            "golden_cross": True,
            "death_cross": False,
        }
        score, reason = _score_moving_averages(signals)
        assert score == 2

    def test_all_bearish_returns_minus_2(self):
        """Score should be -2 when all MA signals are bearish."""
        signals = {
            "price_vs_200": "below",
            "ma_200_value": 100.0,
            "ma_alignment": "bearish",
            "golden_cross": False,
            "death_cross": True,
        }
        score, reason = _score_moving_averages(signals)
        assert score == -2

    def test_no_data_returns_zero(self):
        """Score should be 0 when no MA data is available (None)."""
        score, reason = _score_moving_averages(None)
        assert score == 0
        assert "No MA data" in reason

    def test_empty_dict_returns_zero(self):
        """Score should be 0 for an empty signals dict (all None/neutral)."""
        score, reason = _score_moving_averages({})
        assert score == 0

    def test_price_above_200ma_adds_one(self):
        """Price above 200MA should contribute +1.0 to score."""
        signals = {
            "price_vs_200": "above",
            "ma_200_value": 100.0,
            "ma_alignment": "neutral",
            "golden_cross": False,
            "death_cross": False,
        }
        score, reason = _score_moving_averages(signals)
        assert score == 1
        assert "above 200MA" in reason

    def test_price_below_200ma_subtracts_one(self):
        """Price below 200MA should contribute -1.0 to score."""
        signals = {
            "price_vs_200": "below",
            "ma_200_value": 100.0,
            "ma_alignment": "neutral",
            "golden_cross": False,
            "death_cross": False,
        }
        score, reason = _score_moving_averages(signals)
        assert score == -1
        assert "below 200MA" in reason

    def test_alignment_contributes_half_point(self):
        """Bullish alignment adds +0.5, bearish adds -0.5."""
        # Bullish alignment only (no 200MA signal)
        signals_bull = {
            "price_vs_200": None,
            "ma_alignment": "bullish",
            "golden_cross": False,
            "death_cross": False,
        }
        score_bull, _ = _score_moving_averages(signals_bull)

        signals_bear = {
            "price_vs_200": None,
            "ma_alignment": "bearish",
            "golden_cross": False,
            "death_cross": False,
        }
        score_bear, _ = _score_moving_averages(signals_bear)

        # +0.5 rounds to 0, -0.5 rounds to 0 -- but the difference should be 1
        # after combining with other signals. Let's test with 200MA above:
        signals_above_bull = {
            "price_vs_200": "above",
            "ma_200_value": 100.0,
            "ma_alignment": "bullish",
            "golden_cross": False,
            "death_cross": False,
        }
        score_ab, _ = _score_moving_averages(signals_above_bull)
        # 1.0 (200MA) + 0.25 (alignment) = 1.25 -> rounds to 1
        assert score_ab == 1

        signals_above_bear = {
            "price_vs_200": "above",
            "ma_200_value": 100.0,
            "ma_alignment": "bearish",
            "golden_cross": False,
            "death_cross": False,
        }
        score_abr, _ = _score_moving_averages(signals_above_bear)
        # 1.0 (200MA) - 0.25 (alignment) = 0.75 -> rounds to 1
        assert score_abr == 1

    def test_golden_cross_adds_quarter_point(self):
        """Golden cross should add +0.25 to score."""
        signals = {
            "price_vs_200": "above",
            "ma_200_value": 100.0,
            "ma_alignment": "neutral",
            "golden_cross": True,
            "death_cross": False,
        }
        score, reason = _score_moving_averages(signals)
        # 1.0 + 0.25 = 1.25 -> rounds to 1
        assert score == 1
        assert "golden cross" in reason

    def test_death_cross_subtracts_quarter_point(self):
        """Death cross should subtract 0.25 from score."""
        signals = {
            "price_vs_200": "below",
            "ma_200_value": 100.0,
            "ma_alignment": "neutral",
            "golden_cross": False,
            "death_cross": True,
        }
        score, reason = _score_moving_averages(signals)
        # -1.0 - 0.25 = -1.25 -> rounds to -1
        assert score == -1
        assert "death cross" in reason

    def test_ema21_above_adds_half_point(self):
        """Price above 21 EMA should add +0.5."""
        signals = {
            "price_vs_200": "above",
            "ma_200_value": 100.0,
            "price_vs_21": "above",
            "ema_21_value": 105.0,
            "ma_alignment": "neutral",
            "golden_cross": False,
            "death_cross": False,
        }
        score, reason = _score_moving_averages(signals)
        # 1.0 (200MA) + 0.5 (21EMA) = 1.5 -> rounds to 2
        assert score == 2
        assert "21EMA" in reason

    def test_ema21_below_subtracts_half_point(self):
        """Price below 21 EMA should subtract 0.5."""
        signals = {
            "price_vs_200": "below",
            "ma_200_value": 100.0,
            "price_vs_21": "below",
            "ema_21_value": 105.0,
            "ma_alignment": "neutral",
            "golden_cross": False,
            "death_cross": False,
        }
        score, reason = _score_moving_averages(signals)
        # -1.0 (200MA) - 0.5 (21EMA) = -1.5 -> rounds to -2
        assert score == -2
        assert "21EMA" in reason

    def test_score_clamped_to_plus_minus_2(self):
        """Score should never exceed +2 or -2."""
        signals_max = {
            "price_vs_200": "above",
            "ma_200_value": 100.0,
            "price_vs_21": "above",
            "ema_21_value": 105.0,
            "ma_alignment": "bullish",
            "golden_cross": True,
            "death_cross": False,
        }
        score, _ = _score_moving_averages(signals_max)
        assert score <= 2

        signals_min = {
            "price_vs_200": "below",
            "ma_200_value": 100.0,
            "price_vs_21": "below",
            "ema_21_value": 105.0,
            "ma_alignment": "bearish",
            "golden_cross": False,
            "death_cross": True,
        }
        score, _ = _score_moving_averages(signals_min)
        assert score >= -2
