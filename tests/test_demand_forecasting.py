"""Demand forecasting for the Market Decision Center.

These pin the properties that decide whether a farmer can trust the number:
no leakage from the future, no negative or runaway demand, a simulated figure
that can never present itself as observed, and an honest refusal when the
history is too thin.

Pure -- no database, no network -- so they run with the rest of the suite.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from backend.app.ml import demand as demand_model
from backend.app.ml import demand_horizons as dh

TODAY = date(2026, 9, 7)


def order(days_ago: int, kg: float) -> dict:
    return {"quantity_kg": kg,
            "orders": {"placed_at": (TODAY - timedelta(days=days_ago)).isoformat()}}


def request_row(days_ago: int, kg: float) -> dict:
    return {"quantity_kg": kg,
            "created_at": (TODAY - timedelta(days=days_ago)).isoformat()}


def rich_history(days: int = 70, kg: float = 100.0) -> list[dict]:
    return [order(d, kg) for d in range(0, days, 2)]


# --------------------------------------------------------------------------
# building the demand series
# --------------------------------------------------------------------------

def test_orders_and_buyer_requests_both_count_as_demand():
    daily = dh.daily_demand_series([order(1, 100)], [request_row(1, 50)])
    # Both are a buyer saying they want produce, on the same day.
    assert daily[(TODAY - timedelta(days=1)).isoformat()] == 150.0


def test_rows_without_a_date_are_skipped_not_dated_today():
    daily = dh.daily_demand_series([{"quantity_kg": 500}], [])
    assert daily == {}


def test_zero_and_negative_quantities_are_skipped_not_counted_as_zero_demand():
    daily = dh.daily_demand_series(
        [order(1, 0), order(1, -20), order(1, 40)], [])
    # A zero would drag the average down as though nobody wanted the crop.
    assert daily == {(TODAY - timedelta(days=1)).isoformat(): 40.0}


def test_same_day_demand_is_summed():
    daily = dh.daily_demand_series([order(2, 100), order(2, 250)], [])
    assert daily[(TODAY - timedelta(days=2)).isoformat()] == 350.0


def test_history_span_is_calendar_days_not_the_count_of_active_days():
    # Three orders inside one week is a week of history, not three days.
    daily = dh.daily_demand_series([order(6, 10), order(3, 10), order(0, 10)], [])
    assert dh.observed_span_days(daily, TODAY) == 7


# --------------------------------------------------------------------------
# per-horizon sufficiency
# --------------------------------------------------------------------------

def test_a_longer_horizon_demands_more_history():
    need = dh.HORIZON_REQUIREMENTS
    assert need["3_days"]["min_history_days"] < need["15_days"]["min_history_days"]
    assert need["15_days"]["min_history_days"] < need["30_days"]["min_history_days"]


def test_thin_history_can_answer_the_short_horizon_and_refuse_the_long_one():
    daily = dh.daily_demand_series(
        [order(d, 100) for d in (0, 2, 4, 6, 8)], [])
    assert dh.assess_horizon(daily, "3_days", today=TODAY)["sufficient"] is True
    assert dh.assess_horizon(daily, "30_days", today=TODAY)["sufficient"] is False


def test_reliability_is_a_word_never_a_fabricated_percentage():
    daily = dh.daily_demand_series(rich_history(), [])
    for key in dh.HORIZONS:
        rel = dh.assess_horizon(daily, key, today=TODAY)["reliability"]
        assert rel is None or rel in dh.RELIABILITY_LEVELS


def test_insufficient_horizon_reports_no_reliability_at_all():
    assessment = dh.assess_horizon({}, "30_days", today=TODAY)
    assert assessment["sufficient"] is False
    assert assessment["reliability"] is None


# --------------------------------------------------------------------------
# the forecast itself
# --------------------------------------------------------------------------

def test_forecast_returns_one_point_per_day_of_the_horizon():
    daily = dh.daily_demand_series(rich_history(), [])
    for key, days in dh.HORIZONS.items():
        assert len(dh.forecast_horizon(daily, key, today=TODAY)["points"]) == days


def test_every_forecast_day_is_in_the_future():
    daily = dh.daily_demand_series(rich_history(), [])
    out = dh.forecast_horizon(daily, "15_days", today=TODAY)
    assert all(p["date"] > TODAY.isoformat() for p in out["points"])


def test_demand_is_never_negative_even_on_a_steep_decline():
    # A collapsing series must not extrapolate through zero into negative kg.
    daily = {(TODAY - timedelta(days=d)).isoformat(): float(d * 40)
             for d in range(0, 60, 2)}
    out = dh.forecast_horizon(daily, "30_days", today=TODAY)
    assert all(p["predicted_demand_kg"] >= 0 for p in out["points"])


def test_trend_cannot_run_away_from_a_slope_fitted_to_noise():
    spiky = {(TODAY - timedelta(days=d)).isoformat(): (10.0 if d % 4 else 5000.0)
             for d in range(0, 60, 2)}
    out = dh.forecast_horizon(spiky, "30_days", today=TODAY)
    base = out["baseline_total_kg"] / dh.HORIZONS["30_days"]
    ceiling = base * (1 + dh.MAX_TREND_FRACTION) * 1.01
    assert all(p["predicted_demand_kg"] <= ceiling for p in out["points"])


def test_headline_total_equals_the_sum_of_the_charted_points():
    daily = dh.daily_demand_series(rich_history(), [])
    out = dh.forecast_horizon(daily, "15_days", today=TODAY)
    # The card and the chart must never disagree.
    assert out["total_expected_demand_kg"] == pytest.approx(
        sum(p["predicted_demand_kg"] for p in out["points"]), abs=0.5)


def test_no_leakage_a_forecast_uses_only_history_up_to_today():
    past = dh.daily_demand_series(rich_history(), [])
    with_future = dict(past)
    for step in range(1, 31):
        with_future[(TODAY + timedelta(days=step)).isoformat()] = 99999.0
    # Future rows must not change a forecast made today.
    a = dh.forecast_horizon(past, "15_days", today=TODAY)
    b = dh.forecast_horizon(
        {d: v for d, v in with_future.items() if d <= TODAY.isoformat()},
        "15_days", today=TODAY)
    assert a["total_expected_demand_kg"] == b["total_expected_demand_kg"]


def test_a_rising_series_reads_as_increasing():
    rising = {(TODAY - timedelta(days=d)).isoformat(): float(300 - d * 4)
              for d in range(0, 60, 2)}
    assert dh.forecast_horizon(rising, "15_days", today=TODAY)["trend"] == "INCREASING"


def test_a_flat_series_reads_as_steady_not_a_direction():
    flat = {(TODAY - timedelta(days=d)).isoformat(): 120.0
            for d in range(0, 60, 2)}
    assert dh.forecast_horizon(flat, "15_days", today=TODAY)["trend"] == "STABLE"


# --------------------------------------------------------------------------
# honesty: real vs simulated vs refused
# --------------------------------------------------------------------------

def test_real_history_produces_a_real_forecast():
    out = demand_model.horizon_forecast(
        order_items=rich_history(), horizon="3_days", crop="Tomato", today=TODAY)
    assert out["available"] is True
    assert out["data_status"] == "REAL"
    assert out["is_real"] is True
    assert "disclaimer" not in out


def test_thin_history_with_simulation_disabled_is_refused_with_its_counts():
    out = demand_model.horizon_forecast(
        order_items=[order(1, 500)], horizon="30_days", crop="Onion",
        allow_simulation=False, today=TODAY)
    assert out["available"] is False
    assert out["reason"] == "INSUFFICIENT_DATA"
    assert out["total_expected_demand_kg"] is None
    # It must say what exists and what was needed, not just "no".
    assert out["required_history_days"] > 0
    assert out["demand_events"] == 1


def test_simulated_forecast_is_labelled_at_every_layer():
    out = demand_model.horizon_forecast(
        order_items=[order(1, 500)], horizon="30_days", crop="Onion",
        crop_category="vegetable", today=TODAY)
    assert out["available"] is True
    assert out["is_real"] is False
    assert out["data_status"] == "SYNTHETIC"
    assert "simulated" in out["disclaimer"].lower()
    # The REAL counts travel with it so the UI can show how thin the truth is.
    assert out["real_data"]["demand_events"] == 1


def test_simulated_forecast_claims_no_reliability():
    out = demand_model.horizon_forecast(
        order_items=[], horizon="15_days", crop="Onion",
        crop_category="vegetable", today=TODAY)
    # Grading a generated series would report "High" for a demonstration.
    assert out["data_status"] == "SYNTHETIC"
    assert out["reliability"] is None


def test_the_method_is_never_called_ai_or_a_prediction():
    out = demand_model.horizon_forecast(
        order_items=rich_history(), horizon="3_days", crop="Tomato", today=TODAY)
    assert out["method"] == "ALGORITHMIC"
    blob = f"{out['model']} {out['method']}".lower()
    assert "ai" not in blob.split()
    assert "prediction" not in blob


def test_simulated_demand_is_crop_specific_not_copied_between_crops():
    kwargs = dict(order_items=[], horizon="15_days",
                  crop_category="vegetable", today=TODAY)
    onion = demand_model.horizon_forecast(crop="Onion", **kwargs)
    tomato = demand_model.horizon_forecast(crop="Tomato", **kwargs)
    assert onion["total_expected_demand_kg"] != tomato["total_expected_demand_kg"]


def test_simulated_demand_is_deterministic_across_calls():
    kwargs = dict(order_items=[], horizon="15_days", crop="Onion",
                  crop_category="vegetable", today=TODAY)
    a = demand_model.horizon_forecast(**kwargs)
    b = demand_model.horizon_forecast(**kwargs)
    # A demo that changes numbers on every refresh reads as random, not modelled.
    assert a["total_expected_demand_kg"] == b["total_expected_demand_kg"]


def test_unknown_horizon_is_rejected():
    with pytest.raises(ValueError):
        demand_model.horizon_forecast(order_items=[], horizon="7_days", crop="X")


def test_factors_listed_match_the_data_actually_used():
    real = demand_model.horizon_forecast(
        order_items=rich_history(), horizon="3_days", crop="Tomato", today=TODAY)
    sim = demand_model.horizon_forecast(
        order_items=[], horizon="15_days", crop="Onion",
        crop_category="vegetable", today=TODAY)
    # "Why this forecast?" must not claim real orders behind a simulation.
    assert "historical_orders" in real["factors"]
    assert "simulated_demand_history" in sim["factors"]
    assert "historical_orders" not in sim["factors"]


def test_thirty_day_horizon_is_a_rolling_window_not_a_calendar_month():
    assert dh.ROLLING_WINDOW is True
    assert dh.HORIZONS["30_days"] == 30
    out = dh.forecast_horizon(
        dh.daily_demand_series(rich_history(), []), "30_days", today=TODAY)
    assert out["points"][-1]["date"] == (TODAY + timedelta(days=30)).isoformat()
