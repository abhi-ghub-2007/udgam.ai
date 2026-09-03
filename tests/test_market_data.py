"""Market data spine — service behaviour, honesty labelling, and API authorization.

The service layer is pure, so everything except the authorization tests runs
without Supabase. The authorization tests use the app's own TestClient and
assert only on the auth boundary, which does not need a live database either.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services import market_data as md

client = TestClient(app)


# --------------------------------------------------------------- generation
def test_series_is_deterministic_for_the_same_crop_and_district():
    """Reseeding the demo must not silently move every number on the screen."""
    a = md.synthesize_series("TOMATO", "Nashik", category="vegetable", days=30,
                             end=date(2026, 9, 1))
    b = md.synthesize_series("TOMATO", "Nashik", category="vegetable", days=30,
                             end=date(2026, 9, 1))
    assert [p.modal_price_paise for p in a] == [p.modal_price_paise for p in b]


def test_different_districts_produce_different_series():
    a = md.synthesize_series("TOMATO", "Nashik", category="vegetable", days=30)
    b = md.synthesize_series("TOMATO", "Nagpur", category="vegetable", days=30)
    assert [p.modal_price_paise for p in a] != [p.modal_price_paise for p in b]


def test_prices_are_integer_paise_and_band_is_ordered():
    """PRD §32: money is integer paise, never floats."""
    for pt in md.synthesize_series("ONION", "Pune", category="vegetable", days=45):
        assert isinstance(pt.modal_price_paise, int)
        assert isinstance(pt.min_price_paise, int)
        assert isinstance(pt.max_price_paise, int)
        assert pt.min_price_paise < pt.modal_price_paise < pt.max_price_paise
        assert pt.modal_price_paise > 0


def test_series_covers_the_requested_window_and_ends_on_the_end_date():
    end = date(2026, 6, 15)
    series = md.synthesize_series("WHEAT", "Solapur", category="grain", days=10, end=end)
    assert len(series) == 10
    assert series[-1].price_date == end
    assert series[0].price_date == end - timedelta(days=9)


def test_zero_or_negative_window_returns_empty_not_an_error():
    assert md.synthesize_series("TOMATO", "Pune", days=0) == []
    assert md.synthesize_series("TOMATO", "Pune", days=-5) == []


def test_walk_stays_bounded_over_a_long_series():
    """A long series must not drift to an absurd price."""
    series = md.synthesize_series("POTATO", "Mumbai", category="vegetable", days=365)
    base = md.base_price_paise("vegetable")
    for pt in series:
        assert base * 0.4 < pt.modal_price_paise < base * 2.5


# ----------------------------------------------------------------- forecast
def test_forecast_band_widens_with_horizon_and_confidence_decays():
    series = md.synthesize_series("TOMATO", "Nashik", category="vegetable", days=60)
    _, low3, high3, conf3 = md.synthesize_forecast(series, horizon_days=3)
    _, low14, high14, conf14 = md.synthesize_forecast(series, horizon_days=14)
    assert (high14 - low14) > (high3 - low3)
    assert conf14 < conf3


def test_forecast_confidence_never_claims_high_certainty():
    """A projection of synthetic history must not read like a validated model."""
    series = md.synthesize_series("COTTON", "Nagpur", category="fibre", days=60)
    for horizon in (1, 3, 7, 14, 30):
        *_, confidence = md.synthesize_forecast(series, horizon_days=horizon)
        assert 0.0 < confidence <= 0.6


def test_forecast_on_empty_series_is_zeroed_not_crashing():
    assert md.synthesize_forecast([], horizon_days=7) == (0, 0, 0, 0.0)


# ---------------------------------------------------------------- freshness
def test_synthetic_never_reports_as_live_however_recent():
    """The core honesty guarantee of this phase."""
    assert md.freshness_of(datetime.now(timezone.utc), method="SYNTHETIC") == md.FRESH_SYNTHETIC


def test_prediction_reports_estimated():
    assert md.freshness_of(date.today(), method="REAL", is_prediction=True) == md.FRESH_ESTIMATED


@pytest.mark.parametrize("age_hours,expected", [
    (1, md.FRESH_LIVE), (23, md.FRESH_LIVE),
    (25, md.FRESH_RECENT), (71, md.FRESH_RECENT),
    (73, md.FRESH_STALE), (24 * 30, md.FRESH_STALE),
])
def test_real_observations_are_graded_by_age(age_hours, expected):
    now = datetime(2026, 9, 3, 12, 0, tzinfo=timezone.utc)
    observed = now - timedelta(hours=age_hours)
    assert md.freshness_of(observed, method="REAL", now=now) == expected


def test_missing_timestamp_is_stale_not_live():
    """Unknown age must fail closed."""
    assert md.freshness_of(None, method="REAL") == md.FRESH_STALE


def test_naive_datetime_is_handled_without_crashing():
    assert md.freshness_of(datetime(2026, 1, 1, 0, 0), method="REAL") == md.FRESH_STALE


# --------------------------------------------------------------- provenance
def test_provenance_exposes_every_required_field():
    row = {
        "data_source": md.SYNTHETIC_SOURCE, "method": "SYNTHETIC",
        "price_date": date(2026, 9, 1), "created_at": "2026-09-01T10:00:00Z",
        "is_prediction": False, "confidence": None,
    }
    p = md.provenance(row)
    for field in ("source", "updated_at", "freshness", "method", "confidence",
                  "is_synthetic", "is_prediction"):
        assert field in p, f"provenance is missing {field}"
    assert p["is_synthetic"] is True
    assert p["source"] == md.SYNTHETIC_SOURCE
    assert p["freshness"] == md.FRESH_SYNTHETIC


def test_provenance_never_claims_agmarknet_for_generated_rows():
    """Guards the exact dishonesty this phase was warned about."""
    row = {"data_source": md.SYNTHETIC_SOURCE, "method": "SYNTHETIC",
           "price_date": date.today(), "is_prediction": False}
    assert md.provenance(row)["source"] != "agmarknet"


def test_provenance_of_malformed_row_degrades_gracefully():
    """A row with nothing useful must not raise — the UI shows 'unavailable'."""
    p = md.provenance({})
    assert p["freshness"] == md.FRESH_STALE
    assert p["is_synthetic"] is False
    assert p["source"] is None


# -------------------------------------------------------------------- trend
def test_trend_directions():
    rising = [{"modal_price_paise": 1000}, {"modal_price_paise": 1200}]
    falling = [{"modal_price_paise": 1200}, {"modal_price_paise": 1000}]
    steady = [{"modal_price_paise": 1000}, {"modal_price_paise": 1010}]
    assert md.trend_of(rising)["direction"] == "rising"
    assert md.trend_of(falling)["direction"] == "falling"
    assert md.trend_of(steady)["direction"] == "steady"


def test_trend_on_empty_or_single_point_is_unknown_not_zero():
    """Reporting 'steady' for no data would be a claim we cannot support."""
    assert md.trend_of([])["direction"] == "unknown"
    assert md.trend_of([{"modal_price_paise": 900}])["direction"] == "unknown"


def test_trend_ignores_rows_with_missing_price():
    assert md.trend_of([{"modal_price_paise": None}])["direction"] == "unknown"


# ----------------------------------------------------------------- distance
def test_distance_between_known_districts_is_plausible():
    km = md.district_distance_km("Nashik", "Pune")
    assert 150 < km < 220        # ~165 km by great circle


def test_distance_is_none_for_unknown_district_rather_than_zero():
    """A guessed zero would make an unknown market look adjacent."""
    assert md.district_distance_km("Nashik", "Atlantis") is None
    assert md.district_distance_km(None, "Pune") is None


# ------------------------------------------------------- API authorization
@pytest.mark.parametrize("path", [
    "/api/market/districts",
    "/api/market/prices?district=Nashik&crop_code=TOMATO",
    "/api/market/compare?crop_code=TOMATO",
])
def test_market_endpoints_reject_anonymous_callers(path):
    res = client.get(path)
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHENTICATED"


@pytest.mark.parametrize("path", [
    "/api/market/districts",
    "/api/market/prices?district=Nashik&crop_code=TOMATO",
])
def test_market_endpoints_reject_a_garbage_bearer_token(path):
    res = client.get(path, headers={"Authorization": "Bearer not-a-real-jwt"})
    assert res.status_code == 401


def test_market_router_exposes_no_write_verbs():
    """RLS grants SELECT only on these tables; the router must not offer writes."""
    market_routes = [r for r in app.routes if getattr(r, "path", "").startswith("/api/market")]
    assert market_routes, "market router is not registered"
    for route in market_routes:
        assert set(route.methods) <= {"GET", "HEAD", "OPTIONS"}, f"{route.path} exposes writes"


# ------------------------------------------- derived confidence (no migration)
def test_confidence_is_derived_for_predictions_without_a_stored_column():
    """`prices` stores an interval, not a scalar confidence. Rather than migrate
    a column that is a pure function of the horizon, the API derives it."""
    row = {"method": "SYNTHETIC", "is_prediction": True, "horizon_days": 7,
           "price_date": date(2026, 9, 10), "data_source": md.SYNTHETIC_SOURCE}
    assert md.provenance(row)["confidence"] == md.confidence_for_horizon(7)


def test_observations_report_no_confidence():
    """An observation is not a prediction and has no confidence to claim."""
    row = {"method": "SYNTHETIC", "is_prediction": False,
           "price_date": date.today(), "data_source": md.SYNTHETIC_SOURCE}
    assert md.provenance(row)["confidence"] is None


def test_derived_confidence_matches_the_stored_band():
    """The band and the reported confidence must not drift apart."""
    series = md.synthesize_series("TOMATO", "Pune", category="vegetable", days=60)
    for horizon in (3, 7, 14):
        *_, confidence = md.synthesize_forecast(series, horizon_days=horizon)
        assert confidence == md.confidence_for_horizon(horizon)


def test_confidence_for_unknown_horizon_is_none_not_a_guess():
    assert md.confidence_for_horizon(None) is None
