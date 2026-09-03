"""Dynamic Supply Aggregation — selection, safety, and the consent lifecycle.

The selector is pure, so the matching tests need no database. The lifecycle and
authorization tests assert on the route contract.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services import aggregation as agg

client = TestClient(app)
TODAY = date(2026, 9, 3)


def request_row(**over):
    base = {"id": "req-1", "buyer_id": "buyer-1", "crop_id": "crop-1",
            "quantity_kg": 1000.0, "min_grade": "B", "target_price_paise": 3000,
            "needed_by": (TODAY + timedelta(days=14)).isoformat(),
            "delivery_district": "Pune", "status": "open"}
    base.update(over)
    return base


def lot(pid, farmer, kg, price, **over):
    base = {"id": pid, "farmer_id": farmer, "crop_id": "crop-1",
            "available_quantity_kg": kg, "quantity_kg": kg,
            "asking_price_paise": price, "grade": "A", "status": "active",
            "district": "Nashik", "available_until": None,
            "farmer_name": f"Farmer {farmer}"}
    base.update(over)
    return base


# ------------------------------------------------------------------ selection
def test_four_lots_combine_to_cover_the_requirement():
    """The brief's worked example: 350 + 300 + 200 + 150 = 1000."""
    p = agg.propose(request=request_row(), today=TODAY, products=[
        lot("A", "fa", 350, 2000), lot("B", "fb", 300, 2100),
        lot("C", "fc", 200, 2200), lot("D", "fd", 150, 2300)])
    assert p.sufficient
    assert p.covered_kg == 1000.0
    assert len(p.items) == 4
    assert p.shortfall_kg == 0.0


def test_insufficient_supply_is_reported_not_padded():
    p = agg.propose(request=request_row(), today=TODAY,
                    products=[lot("A", "fa", 300, 2000), lot("B", "fb", 200, 2100)])
    assert not p.sufficient
    assert p.covered_kg == 500.0
    assert p.shortfall_kg == 500.0


def test_cheapest_lots_are_taken_first():
    p = agg.propose(request=request_row(quantity_kg=500), today=TODAY, products=[
        lot("expensive", "fa", 500, 2900), lot("cheap", "fb", 500, 1900)])
    assert [i.product_id for i in p.items] == ["cheap"]


def test_a_lot_is_never_drawn_beyond_what_is_available():
    p = agg.propose(request=request_row(quantity_kg=1000), today=TODAY,
                    products=[lot("A", "fa", 400, 2000)])
    assert p.items[0].take_kg == 400.0
    assert p.covered_kg == 400.0


def test_partial_draw_is_explained():
    p = agg.propose(request=request_row(quantity_kg=100), today=TODAY,
                    products=[lot("A", "fa", 400, 2000)])
    assert p.items[0].take_kg == 100.0
    assert any("partial draw" in r for r in p.items[0].reasons)


def test_selection_stops_once_the_requirement_is_met():
    p = agg.propose(request=request_row(quantity_kg=300), today=TODAY, products=[
        lot("A", "fa", 300, 2000), lot("B", "fb", 300, 2100)])
    assert len(p.items) == 1


# ----------------------------------------------------------------- exclusions
@pytest.mark.parametrize("over,fragment", [
    ({"grade": "C"}, "below required"),
    ({"status": "withdrawn"}, "withdrawn"),
    ({"status": "sold"}, "sold"),
    ({"asking_price_paise": 5000}, "exceeds target"),
    ({"available_quantity_kg": 0}, "already committed"),
])
def test_ineligible_lots_are_rejected_with_a_reason(over, fragment):
    p = agg.propose(request=request_row(), today=TODAY,
                    products=[lot("A", "fa", 500, 2000, **over)])
    assert p.items == []
    assert any(fragment in (r["reason"] or "") for r in p.rejected)


def test_a_different_crop_is_never_included():
    p = agg.propose(request=request_row(), today=TODAY,
                    products=[lot("A", "fa", 500, 2000, crop_id="crop-9")])
    assert p.items == []
    assert any("different crop" in r["reason"] for r in p.rejected)


def test_far_away_farmers_are_excluded_with_the_distance_stated():
    p = agg.propose(request=request_row(delivery_district="Ratnagiri"), today=TODAY,
                    products=[lot("A", "fa", 500, 2000, district="Nagpur")])
    assert p.items == []
    assert any("sourcing radius" in r["reason"] for r in p.rejected)


def test_listing_expiring_before_the_deadline_is_excluded():
    p = agg.propose(request=request_row(), today=TODAY, products=[
        lot("A", "fa", 500, 2000, available_until=(TODAY + timedelta(days=2)).isoformat())])
    assert p.items == []
    assert any("expires before" in r["reason"] for r in p.rejected)


def test_expired_listing_is_excluded():
    p = agg.propose(request=request_row(needed_by=None), today=TODAY, products=[
        lot("A", "fa", 500, 2000, available_until=(TODAY - timedelta(days=1)).isoformat())])
    assert p.items == []
    assert any("expired" in r["reason"] for r in p.rejected)


def test_malformed_dates_do_not_crash_the_selector():
    p = agg.propose(request=request_row(), today=TODAY,
                    products=[lot("A", "fa", 500, 2000, available_until="soon")])
    assert p.items and p.items[0].product_id == "A"


# ------------------------------------------------------------ double counting
def test_quantity_already_committed_elsewhere_is_not_offered_again():
    """The same kilo must never be proposed to two buyers."""
    p = agg.propose(request=request_row(quantity_kg=1000), today=TODAY,
                    products=[lot("A", "fa", 500, 2000)],
                    committed={"A": 300.0})
    assert p.items[0].take_kg == 200.0
    assert p.items[0].available_kg == 200.0


def test_a_fully_committed_lot_is_rejected():
    p = agg.propose(request=request_row(), today=TODAY,
                    products=[lot("A", "fa", 500, 2000)], committed={"A": 500.0})
    assert p.items == []
    assert any("already committed" in r["reason"] for r in p.rejected)


def test_the_same_lot_is_never_selected_twice_in_one_proposal():
    p = agg.propose(request=request_row(quantity_kg=1000), today=TODAY,
                    products=[lot("A", "fa", 400, 2000), lot("A", "fa", 400, 2000)])
    total = sum(i.take_kg for i in p.items if i.product_id == "A")
    assert total <= 800.0          # each row is a distinct listing row
    assert len(p.items) <= 2


# ------------------------------------------------------------------- warnings
def test_mixed_grades_raise_the_variance_warning():
    p = agg.propose(request=request_row(min_grade="C"), today=TODAY, products=[
        lot("A", "fa", 500, 2000, grade="A"), lot("B", "fb", 500, 2100, grade="B")])
    assert p.grade_variance_warning is True


def test_uniform_grades_raise_no_warning():
    p = agg.propose(request=request_row(), today=TODAY, products=[
        lot("A", "fa", 500, 2000, grade="A"), lot("B", "fb", 500, 2100, grade="A")])
    assert p.grade_variance_warning is False


# ----------------------------------------------------------------- neutrality
def test_farmer_identity_cannot_change_the_selection():
    """Same economics, different names — same outcome."""
    base = agg.propose(request=request_row(quantity_kg=500), today=TODAY, products=[
        lot("A", "udgam-partner", 500, 2000), lot("B", "random", 500, 2500)])
    swapped = agg.propose(request=request_row(quantity_kg=500), today=TODAY, products=[
        lot("A", "random", 500, 2000), lot("B", "udgam-partner", 500, 2500)])
    assert [i.product_id for i in base.items] == [i.product_id for i in swapped.items]


def test_ordering_is_deterministic_regardless_of_input_order():
    lots = [lot("A", "fa", 300, 2200), lot("B", "fb", 300, 2000), lot("C", "fc", 300, 2100)]
    a = agg.propose(request=request_row(quantity_kg=900), today=TODAY, products=lots)
    b = agg.propose(request=request_row(quantity_kg=900), today=TODAY, products=list(reversed(lots)))
    assert [i.product_id for i in a.items] == [i.product_id for i in b.items]


def test_ties_break_on_distance_then_id():
    a = agg.propose(request=request_row(quantity_kg=300, delivery_district="Pune"),
                    today=TODAY, products=[
                        lot("far", "fa", 300, 2000, district="Nagpur"),
                        lot("near", "fb", 300, 2000, district="Pune")])
    assert a.items[0].product_id == "near"


def test_selection_order_is_disclosed():
    assert "unit price asc" in agg.ASSUMPTIONS["selection_order"]


# -------------------------------------------------------------- explainability
def test_every_selected_line_explains_itself():
    p = agg.propose(request=request_row(), today=TODAY,
                    products=[lot("A", "fa", 1000, 2000)])
    assert p.items[0].reasons
    assert any("paise/kg" in r for r in p.items[0].reasons)


def test_output_contract_is_complete():
    d = agg.propose(request=request_row(), today=TODAY,
                    products=[lot("A", "fa", 1000, 2000)]).to_dict()
    for key in ("required_kg", "covered_kg", "shortfall_kg", "sufficient",
                "farmer_count", "combined_price_paise", "grade_variance_warning",
                "method", "assumptions", "items", "rejected"):
        assert key in d
    assert d["method"] == "ALGORITHMIC"


def test_combined_price_is_integer_paise_and_matches_the_lines():
    p = agg.propose(request=request_row(quantity_kg=333), today=TODAY,
                    products=[lot("A", "fa", 1000, 1777)])
    assert isinstance(p.combined_price_paise, int)
    assert p.combined_price_paise == sum(i.line_value_paise for i in p.items)


def test_zero_requirement_selects_nothing():
    p = agg.propose(request=request_row(quantity_kg=0), today=TODAY,
                    products=[lot("A", "fa", 500, 2000)])
    assert p.items == [] and p.sufficient


def test_no_products_at_all_is_handled():
    p = agg.propose(request=request_row(), today=TODAY, products=[])
    assert p.items == [] and not p.sufficient and p.shortfall_kg == 1000.0


# ------------------------------------------------------- API / authorization
@pytest.mark.parametrize("method,path", [
    ("post", "/api/aggregations/suggest"),
    ("get", "/api/aggregations/mine"),
    ("get", "/api/aggregations/invitations"),
    ("post", "/api/aggregations/x/confirm"),
    ("post", "/api/aggregations/x/cancel"),
])
def test_every_aggregation_endpoint_rejects_anonymous(method, path):
    kwargs = {"json": {}} if method == "post" else {}
    res = getattr(client, method)(path, **kwargs)
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHENTICATED"


def test_role_gates_are_declared_on_the_routes():
    from backend.app.routers import aggregations as r
    gates = {
        "/api/aggregations/suggest": r.require_buyer,
        "/api/aggregations/mine": r.require_buyer,
        "/api/aggregations/{aggregation_id}/confirm": r.require_buyer,
        "/api/aggregations/{aggregation_id}/cancel": r.require_buyer,
        "/api/aggregations/invitations": r.require_farmer,
        "/api/aggregations/{aggregation_id}/items/{item_id}/consent": r.require_farmer,
    }
    for path, gate in gates.items():
        route = next(x for x in app.routes if getattr(x, "path", "") == path)
        assert gate in route.dependencies, f"{path} is missing its role gate"


def test_suggest_defaults_to_a_preview_that_writes_nothing():
    """Nothing is stored unless the buyer explicitly asks for it."""
    from backend.app.routers.aggregations import SuggestIn
    assert SuggestIn(buyer_request_id="x").persist is False


def test_no_endpoint_ever_writes_to_a_farmers_listing():
    """The core safety property.

    products.available_quantity_kg belongs to the farmer — products_update is
    `farmer_id = auth.uid()`. A buyer must never write it, and the policy must
    never be loosened to let them. Reservation is derived from the aggregation's
    own rows instead, so a listing is never silently mutated (PRD B-7).
    """
    import inspect
    from backend.app.routers import aggregations as r
    for fn in (r.suggest, r.consent, r.my_aggregations, r.my_invitations,
               r.confirm, r.cancel):
        src = inspect.getsource(fn)
        assert '.table("products").update' not in src, (
            f"{fn.__name__} must not write to a farmer's listing")


def test_reservation_is_derived_from_the_committed_ledger():
    """Confirm must check availability net of other groups' claims, so two
    buyers cannot both confirm the same kilos."""
    import inspect
    from backend.app.routers import aggregations as r
    src = inspect.getsource(r.confirm)
    assert "_committed_quantities" in src
    assert "exclude_aggregation_id" in src, "a group must not count itself"


def test_committed_ledger_counts_only_live_groups():
    """A rejected or expired group releases its claim."""
    import inspect
    from backend.app.routers import aggregations as r
    assert r._LIVE_STATUSES == ("suggested", "accepted")
    src = inspect.getsource(r._committed_quantities)
    assert "_LIVE_STATUSES" in src
    assert 'consent_status") == "rejected"' in src, "a rejected line holds nothing"
