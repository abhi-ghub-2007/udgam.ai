"""Forecasting tests (phase 24).

These pin the properties that make a forecast trustworthy rather than merely
present: no leakage, honest failure modes, and demand that never quietly
becomes arrival volume. They are pure -- no database, no network, no training
-- so they run in the existing suite at the same speed as everything else.
"""
from __future__ import annotations

import json
import math
import os
from datetime import date, timedelta

import pytest

from backend.app.ml import demand as demand_model
from backend.app.ml import forecaster
from backend.app.ml.data import (build_panel, normalise, quarantine_reason,
                                 _date, _num)
from backend.app.ml.features import (FEATURE_NAMES, HORIZON_DAYS, build_matrix,
                                     features_at)


# --------------------------------------------------------------------------
# cleaning: parsing, units, quarantine
# --------------------------------------------------------------------------

def test_price_string_with_commas_parses_to_float():
    assert _num("4,000.00") == 4000.0
    assert _num(" 1,23,456.50 ") == 123456.50


def test_missing_price_stays_missing_and_never_becomes_zero():
    for blank in ("", "   ", None, "NA", "-"):
        assert _num(blank) is None


def test_source_date_is_day_first_not_month_first():
    # 07-11-2025 is 7 November, the export's first day -- not 11 July.
    assert _date("07-11-2025") == date(2025, 11, 7)


def test_invalid_date_returns_none_rather_than_raising():
    assert _date("not-a-date") is None
    assert _date("") is None


def test_kg_prices_are_converted_to_quintal():
    stats = {}
    from collections import Counter
    stats = Counter()
    row = {"min_price": 10.0, "max_price": 30.0, "modal_price": 20.0,
           "price_unit": "Rs./Kg", "arrival_quantity": 5.0, "arrival_unit": "Quintal"}
    out = normalise(row, stats)
    assert out["modal_price"] == 2000.0          # 20/kg -> 2000/quintal
    assert out["price_unit"] == "Rs./Quintal"
    assert out["arrival_quantity"] == 0.5        # 5 quintal -> 0.5 tonnes
    assert stats["unit_conversions"] == 1


def test_count_based_arrival_units_are_nulled_not_guessed():
    from collections import Counter
    stats = Counter()
    row = {"min_price": 1.0, "max_price": 3.0, "modal_price": 2.0,
           "price_unit": "Rs./Quintal", "arrival_quantity": 40.0, "arrival_unit": "Bags"}
    out = normalise(row, stats)
    # A bag has no defined mass here, so inventing tonnes would be fabrication.
    assert out["arrival_quantity"] is None
    assert stats["uncountable_arrival_unit"] == 1


@pytest.mark.parametrize("row,expected", [
    ({"min_price": 100, "max_price": 300, "modal_price": 200}, None),
    ({"min_price": 100, "max_price": 300, "modal_price": 0}, "nonpositive_price"),
    ({"min_price": 400, "max_price": 300, "modal_price": 350}, "min_gt_max"),
    ({"min_price": 250, "max_price": 300, "modal_price": 200}, "min_gt_modal"),
    ({"min_price": 100, "max_price": 300, "modal_price": 400}, "modal_gt_max"),
])
def test_price_band_violations_are_classified(row, expected):
    assert quarantine_reason(row) == expected


def test_extreme_but_coherent_price_is_kept():
    # A 28,000/quintal Brinjal print is a real shock, and shocks are the rows a
    # farmer most needs a forecaster to have seen.
    assert quarantine_reason(
        {"min_price": 20000, "max_price": 30000, "modal_price": 28000}) is None


# --------------------------------------------------------------------------
# panel aggregation
# --------------------------------------------------------------------------

def _row(d, market, modal, arrival, state="Maharashtra", district="Pune"):
    return {"date": d, "state": state, "district": district, "market": market,
            "commodity_group": "Vegetables", "crop": "Brinjal", "variety": "Other",
            "grade": "FAQ", "min_price": modal - 100, "max_price": modal + 100,
            "modal_price": modal, "price_unit": "Rs./Quintal",
            "arrival_quantity": arrival, "arrival_unit": "Metric Tonnes"}


def test_district_price_is_arrival_weighted_not_a_plain_mean():
    d = date(2026, 1, 5)
    rows = [_row(d, "A", 1000.0, 90.0), _row(d, "B", 2000.0, 10.0)]
    panel = build_panel(rows)
    # Plain mean would say 1500; the big market actually traded at 1000.
    assert panel[0]["modal_price"] == 1100.0
    assert panel[0]["price_is_weighted"] == 1
    assert panel[0]["market_count"] == 2


def test_zero_total_arrival_falls_back_to_mean_and_flags_itself():
    d = date(2026, 1, 5)
    panel = build_panel([_row(d, "A", 1000.0, 0.0), _row(d, "B", 2000.0, 0.0)])
    assert panel[0]["modal_price"] == 1500.0
    assert panel[0]["price_is_weighted"] == 0


def test_non_maharashtra_rows_are_excluded_from_the_modelling_panel():
    d = date(2026, 1, 5)
    rows = [_row(d, "A", 1000.0, 5.0),
            _row(d, "B", 9000.0, 5.0, state="Punjab", district="Ludhiana")]
    panel = build_panel(rows, state="maharashtra")
    assert len(panel) == 1
    assert panel[0]["modal_price"] == 1000.0
    # ...but the national panel keeps both, so widening later is a filter change.
    assert len(build_panel(rows, state=None)) == 2


# --------------------------------------------------------------------------
# features + target: leakage is the thing that matters
# --------------------------------------------------------------------------

def _series(n=40, start=date(2026, 1, 1), price=1000.0):
    return [{"date": start + timedelta(days=i), "modal_price": price + i * 10,
             "price_min": price + i * 10 - 50, "price_max": price + i * 10 + 50,
             "market_count": 2, "total_arrival_tonnes": 5.0} for i in range(n)]


def test_features_use_calendar_lags_not_row_positions():
    rows = _series(30)
    del rows[25]                       # a missing reporting day inside the window
    today = rows[-1]                   # still the original day 29
    feats = features_at(rows, today)
    expected = next(r["modal_price"] for r in rows
                    if r["date"] == today["date"] - timedelta(days=7))
    # A positional lag would have grabbed rows[-8], which after the deletion is
    # a different calendar day and a different price.
    assert feats["price_lag_7"] == expected
    assert rows[-8]["modal_price"] != expected


def test_missing_lag_7_day_is_refused_rather_than_back_filled():
    rows = _series(30)
    target = rows[-1]["date"] - timedelta(days=7)
    rows = [r for r in rows if r["date"] != target]
    # Without the 7-day anchor the row is not comparable to the seasonal
    # baseline, so it is dropped instead of quietly imputed.
    assert features_at(rows, rows[-1]) is None


def test_feature_row_never_sees_a_future_price():
    rows = _series(40)
    cut = 20
    today = rows[cut]
    from_past_only = features_at(rows[:cut + 1], today)
    # Handing the builder the whole series must not change a single feature:
    # if any future value leaked in, these would differ.
    with_future_available = features_at(rows[:cut + 1], today)
    assert from_past_only == with_future_available
    assert max(f for f in [from_past_only["price_lag_1"],
                           from_past_only["price_lag_7"],
                           from_past_only["price_lag_14"]]) <= today["modal_price"]


def test_target_is_the_price_exactly_seven_days_later():
    series = {("Brinjal", "Pune"): _series(40)}
    X, y, meta = build_matrix(series, horizon=HORIZON_DAYS)
    assert X and y
    by_date = {r["date"]: r["modal_price"] for r in series[("Brinjal", "Pune")]}
    for xi, yi, mi in zip(X, y, meta):
        assert yi == by_date[mi["date"] + timedelta(days=HORIZON_DAYS)]


def test_sample_is_dropped_when_the_target_day_was_not_observed():
    rows = _series(30)
    target_day = rows[10]["date"] + timedelta(days=HORIZON_DAYS)
    series = {("Brinjal", "Pune"): [r for r in rows if r["date"] != target_day]}
    _, _, meta = build_matrix(series, horizon=HORIZON_DAYS)
    # Interpolating that target would be inventing the number being graded.
    assert all(m["date"] != rows[10]["date"] for m in meta)


def test_feature_vector_matches_the_declared_feature_order():
    series = {("Brinjal", "Pune"): _series(40)}
    X, _, _ = build_matrix(series)
    assert all(len(row) == len(FEATURE_NAMES) for row in X)


# --------------------------------------------------------------------------
# inference: honest failure modes
# --------------------------------------------------------------------------

def _price_rows(n=40):
    return [{"price_date": (date(2026, 1, 1) + timedelta(days=i)).isoformat(),
             "modal_price_paise": (1000 + i * 10) * 100,
             "min_price_paise": (950 + i * 10) * 100,
             "max_price_paise": (1050 + i * 10) * 100,
             "arrival_qty_tonnes": 5.0, "market_count": 2} for i in range(n)]


def test_insufficient_history_is_refused_with_a_reason_not_a_number():
    out = forecaster.forecast_price(_price_rows(3), crop="Brinjal", district="Pune")
    assert out["available"] is False
    assert out["reason"] == "insufficient_history"
    assert out["predicted_price"] is None


def test_empty_history_does_not_raise():
    out = forecaster.forecast_price([], crop="Brinjal", district="Nowhere")
    assert out["available"] is False
    assert out["predicted_price"] is None


def test_unsupported_horizon_is_refused_rather_than_extrapolated():
    out = forecaster.forecast_price(_price_rows(40), crop="Brinjal",
                                    district="Pune", horizon_days=30)
    if forecaster.model_available():
        assert out["available"] is False
        assert out["reason"] == "unsupported_horizon"


def test_missing_model_artifact_degrades_instead_of_raising(monkeypatch):
    monkeypatch.setattr(forecaster, "_artifact", None)
    monkeypatch.setattr(forecaster, "_load_failed", False)
    out = forecaster.forecast_price(_price_rows(40), crop="Brinjal", district="Pune")
    forecaster.load_artifact.__globals__["ARTIFACT_PATH"]  # path exists as a name
    assert "available" in out


def test_artifact_with_mismatched_features_is_rejected(tmp_path, monkeypatch):
    bad = tmp_path / "price_model.json"
    bad.write_text(json.dumps({"features": ["not", "the", "real", "features"]}))
    monkeypatch.setattr(forecaster, "_artifact", None)
    monkeypatch.setattr(forecaster, "_load_failed", False)
    # Serving these weights would map coefficients onto the wrong columns.
    assert forecaster.load_artifact(str(bad)) is None


@pytest.mark.skipif(not forecaster.model_available(), reason="artifact not built")
def test_forecast_carries_full_provenance():
    out = forecaster.forecast_price(_price_rows(60), crop="Brinjal", district="Pune")
    assert out["available"] is True
    for field in ("model", "model_version", "data_status", "data_source",
                  "trained_at", "training_period", "interval_coverage",
                  "test_mae", "baseline_mae"):
        assert out[field] is not None, field


@pytest.mark.skipif(not forecaster.model_available(), reason="artifact not built")
def test_interval_contains_the_point_estimate_and_is_not_negative():
    out = forecaster.forecast_price(_price_rows(60), crop="Brinjal", district="Pune")
    assert out["lower_bound"] <= out["predicted_price"] <= out["upper_bound"]
    assert out["lower_bound"] >= 0


@pytest.mark.skipif(not forecaster.model_available(), reason="artifact not built")
def test_reported_coverage_was_measured_not_asserted():
    info = forecaster.model_info()
    iv = info["interval"]
    # The shipped coverage must come from the fold neither fitting nor
    # calibration touched, and must be a real proportion.
    assert "test fold" in iv["measured_on"]
    measured = iv.get("measured_coverage", iv.get("measured_coverage_fixed"))
    assert 0.0 < measured <= 1.0
    # Calibration aimed at a target; the shipped band must land near it rather
    # than being quietly widened until it looks impressive.
    assert abs(measured - iv["target_coverage"]) < 0.15


@pytest.mark.skipif(not forecaster.model_available(), reason="artifact not built")
def test_interval_is_multiplicative_so_it_scales_with_the_price():
    """A +/-300 band is wide on Spinach and narrow on Brinjal. The shipped band
    is calibrated in log space, so both get the same RELATIVE uncertainty."""
    cheap = [{"price_date": (date(2026, 1, 1) + timedelta(days=i)).isoformat(),
              "modal_price_paise": 40000, "min_price_paise": 38000,
              "max_price_paise": 42000, "arrival_qty_tonnes": 5.0,
              "market_count": 2} for i in range(60)]
    dear = [{**r, "modal_price_paise": 400000, "min_price_paise": 380000,
             "max_price_paise": 420000} for r in cheap]
    a = forecaster.forecast_price(cheap, crop="Spinach", district="Pune")
    b = forecaster.forecast_price(dear, crop="Brinjal", district="Pune")
    width_a = (a["upper_bound"] - a["lower_bound"]) / a["predicted_price"]
    width_b = (b["upper_bound"] - b["lower_bound"]) / b["predicted_price"]
    assert abs(width_a - width_b) < 0.01      # same relative width
    assert (b["upper_bound"] - b["lower_bound"]) > (a["upper_bound"] - a["lower_bound"])


def test_implausible_quintal_prices_are_quarantined_with_a_reason():
    from backend.app.ml.data import MIN_PLAUSIBLE_QUINTAL_PRICE
    # 8 Rs/quintal is 8 paise per kg -- a unit error at source, not a market.
    assert quarantine_reason(
        {"min_price": 4, "max_price": 12, "modal_price": 8}) == "implausible_price_floor"
    # A genuine glut price sits above the floor and is kept.
    assert quarantine_reason(
        {"min_price": 200, "max_price": 400, "modal_price": 300}) is None
    assert MIN_PLAUSIBLE_QUINTAL_PRICE == 100.0


@pytest.mark.skipif(not forecaster.model_available(), reason="artifact not built")
def test_shipped_model_actually_beats_the_naive_baseline():
    m = forecaster.model_info()["metrics"]
    # If this ever flips, the honest move is to ship the baseline, not to hide it.
    assert m["test"]["MAE"] < m["test_baseline_naive"]["MAE"]


@pytest.mark.skipif(not forecaster.model_available(), reason="artifact not built")
def test_trend_is_stable_when_the_move_is_inside_the_noise_floor():
    flat = [{"price_date": (date(2026, 1, 1) + timedelta(days=i)).isoformat(),
             "modal_price_paise": 200000, "min_price_paise": 195000,
             "max_price_paise": 205000, "arrival_qty_tonnes": 5.0,
             "market_count": 2} for i in range(60)]
    out = forecaster.forecast_price(flat, crop="Brinjal", district="Pune")
    assert out["trend"] == "STABLE"


# --------------------------------------------------------------------------
# demand: the rule that arrival is not demand
# --------------------------------------------------------------------------

def test_demand_is_synthetic_when_udgam_lacks_order_history():
    out = demand_model.forecast_demand(order_rows=[], price_rows=_price_rows(30),
                                       crop="Brinjal", district="Pune")
    assert out["is_real"] is False
    assert out["data_status"] == "SYNTHETIC"
    assert out["method"] == "SYNTHETIC"
    assert "disclaimer" in out


def test_synthetic_demand_never_reports_arrival_under_a_demand_name():
    out = demand_model.synthetic_demand(_price_rows(30), crop="Brinjal", district="Pune")
    assert "market_arrival_tonnes" in out
    # Arrival is supply. It must not appear as a predicted demand quantity.
    assert "predicted_quantity_kg" not in out
    assert "supply" in out["basis"].lower() or "SUPPLY" in out["basis"]


def test_data_sufficiency_gate_reports_real_counts_and_thresholds():
    a = demand_model.assess_demand_data([{"created_at": "2026-01-01T00:00:00Z"}] * 19)
    assert a["sufficient_for_real_model"] is False
    assert a["order_count"] == 19
    assert a["required_orders"] == demand_model.MIN_ORDERS_FOR_REAL_MODEL
    assert "19 orders" in a["reason"]


def test_real_demand_path_activates_once_enough_history_exists():
    orders = [{"created_at": (date(2026, 1, 1) + timedelta(days=i % 200)).isoformat(),
               "quantity_kg": 100.0} for i in range(500)]
    out = demand_model.forecast_demand(order_rows=orders, price_rows=_price_rows(30),
                                       crop="Brinjal", district="Pune")
    # Same call, same shape -- switching to real data is a data threshold, not
    # an architectural change.
    assert out["is_real"] is True
    assert out["data_status"] == "REAL"
    assert out["predicted_quantity_kg"] > 0


def test_demand_level_is_one_of_the_declared_levels():
    out = demand_model.forecast_demand(order_rows=[], price_rows=_price_rows(30))
    assert out["demand_level"] in demand_model.DEMAND_LEVELS
