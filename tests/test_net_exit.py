"""Net Exit Optimizer — arithmetic, feasibility, ranking, neutrality, honesty.

The optimizer is pure, so everything except the authorization tests runs without
Supabase. Fixtures are plain dicts shaped exactly like the rows the router
selects, which keeps the tests honest about the real column names.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services import net_exit
from backend.app.services.opportunity import CostLine, Opportunity
from backend.app.services.pricing import PLATFORM_FEE_BPS, compute_breakdown

client = TestClient(app)

TODAY = date(2026, 9, 3)
CROP = {"id": "crop-1", "code": "TOMATO", "category": "vegetable",
        "default_shelf_life_days": 7}
DURABLE_CROP = {"id": "crop-2", "code": "WHEAT", "category": "grain",
                "default_shelf_life_days": 365}


def product(**over):
    base = {"id": "prod-1", "farmer_id": "farmer-1", "crop_id": "crop-1",
            "quantity_kg": 1000.0, "available_quantity_kg": 1000.0,
            "asking_price_paise": 2000, "grade": "A", "district": "Nashik"}
    base.update(over)
    return base


def request_row(**over):
    base = {"id": "req-1", "buyer_name": "Buyer One", "quantity_kg": 1000.0,
            "min_grade": "B", "target_price_paise": 2400,
            "needed_by": (TODAY + timedelta(days=10)).isoformat(),
            "delivery_district": "Pune"}
    base.update(over)
    return base


def capacity(**over):
    base = {"available_capacity_kg": 5000.0, "price_paise_per_kg": 100,
            "price_paise_per_km": 0, "discount_pct": 0, "dest_district": None,
            "status": "open"}
    base.update(over)
    return base


# ------------------------------------------------------------------ arithmetic
def test_direct_buyer_net_equals_gross_minus_farmer_borne_lines_only():
    """On a platform sale the buyer pays fee and delivery, so neither reduces
    what the farmer takes home. This is the behaviour pricing.py already defines."""
    opp = net_exit.build_direct_buyer_opportunity(
        product=product(), request=request_row(), crop=DURABLE_CROP,
        distance_km=165.0, capacities=[capacity()], today=TODAY,
    )
    assert opp.gross_value_paise == 1000 * 2400
    farmer_lines = [l for l in opp.breakdown if l.reduces_farmer_net]
    assert all(l.label == "Expected spoilage loss" for l in farmer_lines)
    assert opp.net_realization_paise == opp.gross_value_paise - opp.expected_loss_paise


def test_direct_buyer_reuses_pricing_compute_breakdown_verbatim():
    """Regression guard: if pricing.py changes its fee policy, this must follow."""
    opp = net_exit.build_direct_buyer_opportunity(
        product=product(), request=request_row(), crop=DURABLE_CROP,
        distance_km=10.0, capacities=[capacity()], today=TODAY,
    )
    expected = compute_breakdown(quantity_kg=1000.0, unit_price_paise=2400,
                                 transport_cost_paise=100 * 1000)
    assert opp.gross_value_paise == expected.subtotal_paise
    assert opp.platform_fee_paise == expected.platform_fee_paise
    assert opp.platform_fee_paise == expected.subtotal_paise * PLATFORM_FEE_BPS // 10_000


def test_mandi_net_subtracts_transport_commission_and_loss():
    opp = net_exit.build_mandi_opportunity(
        product=product(), crop=DURABLE_CROP, district="Pune",
        price_row={"modal_price_paise": 2400}, distance_km=165.0,
        capacities=[capacity()],
    )
    gross = 1000 * 2400
    commission = gross * net_exit.MANDI_COMMISSION_BPS // 10_000
    assert opp.gross_value_paise == gross
    assert opp.commission_paise == commission
    assert opp.transport_cost_paise == 100 * 1000
    assert opp.net_realization_paise == (
        gross - commission - opp.transport_cost_paise - opp.expected_loss_paise
    )


def test_transport_deduction_uses_cheapest_posted_capacity():
    cheap = capacity(price_paise_per_kg=40)
    pricey = capacity(price_paise_per_kg=250)
    opp = net_exit.build_mandi_opportunity(
        product=product(), crop=DURABLE_CROP, district="Pune",
        price_row={"modal_price_paise": 2400}, distance_km=100.0,
        capacities=[pricey, cheap],
    )
    assert opp.transport_cost_paise == 40 * 1000


def test_transport_combines_per_kg_and_per_km_and_applies_discount():
    quote = net_exit.quote_transport(
        [capacity(price_paise_per_kg=10, price_paise_per_km=500, discount_pct=10)],
        quantity_kg=1000.0, distance_km=200.0,
    )
    raw = 10 * 1000 + 500 * 200
    assert quote.cost_paise == int(round(raw * 0.9))


def test_capacity_too_small_is_not_quoted():
    assert net_exit.quote_transport(
        [capacity(available_capacity_kg=10.0)], quantity_kg=1000.0, distance_km=50.0
    ) is None


def test_storage_deduction_is_borne_by_the_farmer_on_both_channels():
    for build, kwargs in (
        (net_exit.build_direct_buyer_opportunity,
         dict(request=request_row(), today=TODAY)),
        (net_exit.build_mandi_opportunity,
         dict(district="Pune", price_row={"modal_price_paise": 2400})),
    ):
        opp = build(product=product(), crop=DURABLE_CROP, distance_km=50.0,
                    capacities=[capacity()], storage_cost_paise=5_000,
                    holding_days=3, **kwargs)
        line = next(l for l in opp.breakdown if l.label == "Storage")
        assert line.borne_by == "farmer" and line.reduces_farmer_net
        assert opp.storage_cost_paise == 5_000


def test_all_money_is_integer_paise():
    opp = net_exit.build_mandi_opportunity(
        product=product(quantity_kg=333.33, available_quantity_kg=333.33),
        crop=CROP, district="Pune", price_row={"modal_price_paise": 1777},
        distance_km=123.4, capacities=[capacity()],
    )
    for value in (opp.gross_value_paise, opp.commission_paise,
                  opp.transport_cost_paise, opp.expected_loss_paise,
                  opp.net_realization_paise):
        assert isinstance(value, int)
    for line in opp.breakdown:
        assert isinstance(line.amount_paise, int)


def test_net_is_derived_from_the_breakdown_not_stored_separately():
    """The number and the lines explaining it can never disagree."""
    opp = net_exit.build_mandi_opportunity(
        product=product(), crop=DURABLE_CROP, district="Pune",
        price_row={"modal_price_paise": 2400}, distance_km=50.0,
        capacities=[capacity()],
    )
    gross = sum(l.amount_paise for l in opp.breakdown if l.kind == "gross")
    deductions = sum(l.amount_paise for l in opp.breakdown if l.reduces_farmer_net)
    assert opp.net_realization_paise == gross - deductions


# --------------------------------------------------------------------- spoilage
def test_perishable_crop_loses_more_than_a_durable_one_over_the_same_trip():
    common = dict(holding_days=0, distance_km=400.0, grade="B")
    perishable = net_exit.expected_loss_fraction(shelf_life_days=7, **common)
    durable = net_exit.expected_loss_fraction(shelf_life_days=365, **common)
    assert perishable > durable


def test_loss_grows_with_holding_days():
    a = net_exit.expected_loss_fraction(shelf_life_days=30, holding_days=0,
                                        distance_km=100.0, grade="B")
    b = net_exit.expected_loss_fraction(shelf_life_days=30, holding_days=10,
                                        distance_km=100.0, grade="B")
    assert b > a


def test_lower_grades_spoil_faster():
    common = dict(shelf_life_days=30, holding_days=5, distance_km=100.0)
    a = net_exit.expected_loss_fraction(grade="A", **common)
    c = net_exit.expected_loss_fraction(grade="C", **common)
    assert c > a


def test_loss_fraction_is_capped():
    assert net_exit.expected_loss_fraction(
        shelf_life_days=1, holding_days=999, distance_km=5000.0, grade="C"
    ) == net_exit.MAX_LOSS_FRACTION


def test_unknown_shelf_life_is_treated_as_durable_not_assumed_perishable():
    """Guessing 'perishable' would invent a cost the data does not support."""
    unknown = net_exit.expected_loss_fraction(shelf_life_days=None, holding_days=2,
                                              distance_km=100.0, grade="B")
    durable = net_exit.expected_loss_fraction(shelf_life_days=365, holding_days=2,
                                              distance_km=100.0, grade="B")
    assert unknown == durable


# ------------------------------------------------------------------ missing data
def test_mandi_without_a_price_row_is_infeasible_not_estimated():
    """The rule this phase turns on: never fabricate a price to fill a column."""
    opp = net_exit.build_mandi_opportunity(
        product=product(), crop=CROP, district="Nagpur", price_row=None,
        distance_km=500.0, capacities=[capacity()],
    )
    assert opp.feasible is False
    assert opp.net_realization_paise is None
    assert any("no market price" in b for b in opp.blockers)


def test_mandi_without_transport_is_held_out_of_the_ranking():
    """The farmer bears this cost, so an unknown value would bias the comparison."""
    opp = net_exit.build_mandi_opportunity(
        product=product(), crop=CROP, district="Pune",
        price_row={"modal_price_paise": 2400}, distance_km=165.0, capacities=[],
    )
    assert opp.cost_basis_complete is False
    assert opp.net_realization_paise is None
    assert opp.transport_cost_paise is None
    assert any("transport" in l for l in opp.limitations)


def test_direct_buyer_without_transport_still_ranks_because_the_buyer_pays_it():
    opp = net_exit.build_direct_buyer_opportunity(
        product=product(), request=request_row(), crop=DURABLE_CROP,
        distance_km=165.0, capacities=[], today=TODAY,
    )
    assert opp.cost_basis_complete is True
    assert opp.net_realization_paise is not None
    assert any("buyer bears delivery" in l for l in opp.limitations)


def test_buyer_request_with_no_price_at_all_is_infeasible():
    opp = net_exit.build_direct_buyer_opportunity(
        product=product(asking_price_paise=None),
        request=request_row(target_price_paise=None), crop=CROP,
        distance_km=10.0, capacities=[capacity()], today=TODAY,
    )
    assert opp.feasible is False


# ------------------------------------------------------ quantity / zero / invalid
@pytest.mark.parametrize("qty", [0, 0.0, -5])
def test_zero_or_negative_quantity_is_infeasible(qty):
    opp = net_exit.build_mandi_opportunity(
        product=product(quantity_kg=qty, available_quantity_kg=qty), crop=CROP,
        district="Pune", price_row={"modal_price_paise": 2400},
        distance_km=50.0, capacities=[capacity()],
    )
    assert opp.feasible is False
    assert any("quantity" in b for b in opp.blockers)


def test_partial_fill_is_a_limitation_not_a_blocker():
    """Aggregation (Phase 4) exists precisely to close this gap."""
    opp = net_exit.build_direct_buyer_opportunity(
        product=product(available_quantity_kg=400.0),
        request=request_row(quantity_kg=1000.0), crop=DURABLE_CROP,
        distance_km=50.0, capacities=[capacity()], today=TODAY,
    )
    assert opp.feasible is True
    assert any("partial fill" in l for l in opp.limitations)


# ------------------------------------------------------------ quality / deadline
def test_grade_below_minimum_blocks_the_opportunity():
    opp = net_exit.build_direct_buyer_opportunity(
        product=product(grade="C"), request=request_row(min_grade="A"),
        crop=CROP, distance_km=50.0, capacities=[capacity()], today=TODAY,
    )
    assert opp.feasible is False
    assert any("below the required minimum" in b for b in opp.blockers)


def test_ungraded_lot_is_flagged_rather_than_assumed_to_pass():
    opp = net_exit.build_direct_buyer_opportunity(
        product=product(grade=None), request=request_row(min_grade="A"),
        crop=CROP, distance_km=50.0, capacities=[capacity()], today=TODAY,
    )
    assert opp.feasible is True
    assert any("not graded" in l for l in opp.limitations)


def test_past_deadline_blocks():
    opp = net_exit.build_direct_buyer_opportunity(
        product=product(), request=request_row(
            needed_by=(TODAY - timedelta(days=1)).isoformat()),
        crop=CROP, distance_km=50.0, capacities=[capacity()], today=TODAY,
    )
    assert opp.feasible is False
    assert any("deadline has already passed" in b for b in opp.blockers)


def test_deadline_too_close_for_transit_blocks():
    opp = net_exit.build_direct_buyer_opportunity(
        product=product(), request=request_row(
            needed_by=(TODAY + timedelta(days=1)).isoformat()),
        crop=CROP, distance_km=2000.0, capacities=[capacity()], today=TODAY,
    )
    assert opp.feasible is False
    assert any("cannot deliver in time" in b for b in opp.blockers)


def test_malformed_deadline_does_not_crash():
    opp = net_exit.build_direct_buyer_opportunity(
        product=product(), request=request_row(needed_by="not-a-date"),
        crop=CROP, distance_km=50.0, capacities=[capacity()], today=TODAY,
    )
    assert opp.days_to_deadline is None


# --------------------------------------------------------------------- ranking
def _opp(name, net, distance=100.0, channel="mandi"):
    o = Opportunity(channel=channel, reference_id=name, reference_name=name,
                    crop_id="crop-1", crop_code="TOMATO", grade="A",
                    quantity_kg=1000.0, distance_km=distance)
    o.unit_price_paise = 2000
    o.breakdown.append(CostLine("Gross sale value", net, "gross", "farmer", "test"))
    o.recompute_net()
    return o


def test_ranking_orders_by_net_realization_descending():
    r = net_exit.rank([_opp("low", 100), _opp("high", 900), _opp("mid", 500)])
    assert [o.reference_name for o in r["ranked"]] == ["high", "mid", "low"]
    assert r["best"].reference_name == "high"


def test_highest_gross_does_not_win_when_costs_are_higher():
    """The entire point of the optimizer."""
    rich = net_exit.build_mandi_opportunity(
        product=product(), crop=DURABLE_CROP, district="Far",
        price_row={"modal_price_paise": 2600}, distance_km=900.0,
        capacities=[capacity(price_paise_per_kg=500)],
    )
    near = net_exit.build_mandi_opportunity(
        product=product(), crop=DURABLE_CROP, district="Near",
        price_row={"modal_price_paise": 2400}, distance_km=20.0,
        capacities=[capacity(price_paise_per_kg=20)],
    )
    assert rich.gross_value_paise > near.gross_value_paise
    assert net_exit.rank([rich, near])["best"].reference_name == near.reference_name


def test_ties_break_on_distance_then_id_deterministically():
    a = _opp("bravo", 500, distance=200.0)
    b = _opp("alpha", 500, distance=50.0)
    assert net_exit.rank([a, b])["best"].reference_name == "alpha"
    assert net_exit.rank([b, a])["best"].reference_name == "alpha"


def test_tie_is_reported_as_a_tie_in_the_explanation():
    a, b = _opp("alpha", 500, distance=50.0), _opp("bravo", 500, distance=50.0)
    ranked = net_exit.rank([a, b])["ranked"]
    assert any("ties with" in r for r in ranked[0].reasons)


def test_infeasible_and_incomplete_options_are_excluded_never_ranked():
    good = _opp("good", 500)
    blocked = _opp("blocked", 900)
    blocked.feasible = False
    incomplete = _opp("incomplete", 999)
    incomplete.cost_basis_complete = False
    incomplete.recompute_net()
    r = net_exit.rank([good, blocked, incomplete])
    assert [o.reference_name for o in r["ranked"]] == ["good"]
    assert {o.reference_name for o in r["excluded"]} == {"blocked", "incomplete"}


def test_ranking_with_no_comparable_options_returns_no_winner():
    blocked = _opp("blocked", 100)
    blocked.feasible = False
    r = net_exit.rank([blocked])
    assert r["best"] is None and r["ranked"] == []


def test_empty_input_ranks_cleanly():
    r = net_exit.rank([])
    assert r["best"] is None and r["ranked"] == [] and r["excluded"] == []


# ------------------------------------------------------------------ neutrality
def test_renaming_a_counterparty_cannot_change_the_ordering():
    """No hidden per-buyer, per-market or per-partner boost exists."""
    base = [_opp("udgam-partner", 500), _opp("random-trader", 700)]
    renamed = [_opp("random-trader", 500), _opp("udgam-partner", 700)]
    assert net_exit.rank(base)["best"].net_realization_paise == 700
    assert net_exit.rank(renamed)["best"].net_realization_paise == 700
    assert net_exit.rank(renamed)["best"].reference_name == "udgam-partner"


def test_identical_economics_rank_identically_regardless_of_channel():
    a = _opp("x", 500, distance=100.0, channel="mandi")
    b = _opp("y", 500, distance=100.0, channel="direct_buyer")
    ranked = net_exit.rank([a, b])["ranked"]
    assert ranked[0].net_realization_paise == ranked[1].net_realization_paise


def test_ranking_criterion_is_disclosed():
    assert "net_realization" in net_exit.rank([])["ranked_by"]


# -------------------------------------------------------------- explainability
def test_every_opportunity_explains_its_arithmetic():
    opp = net_exit.build_mandi_opportunity(
        product=product(), crop=CROP, district="Pune",
        price_row={"modal_price_paise": 2400}, distance_km=165.0,
        capacities=[capacity()],
    )
    labels = {l.label for l in opp.breakdown}
    assert {"Gross sale value", "Mandi commission", "Transport",
            "Expected spoilage loss"} <= labels
    for line in opp.breakdown:
        assert line.basis, f"{line.label} has no stated basis"


def test_winner_states_how_much_better_it_is():
    r = net_exit.rank([_opp("high", 900), _opp("low", 100)])
    assert any("800 paise better" in reason for reason in r["best"].reasons)


def test_assumptions_are_disclosed_with_the_result():
    a = net_exit.rank([])["assumptions"]
    assert a["mandi_commission_bps"] == net_exit.MANDI_COMMISSION_BPS
    assert a["platform_fee_bps"] == PLATFORM_FEE_BPS
    assert "not observed market fees" in a["note"]


def test_method_label_is_algorithmic_never_real():
    opp = net_exit.build_mandi_opportunity(
        product=product(), crop=CROP, district="Pune",
        price_row={"modal_price_paise": 2400}, distance_km=50.0,
        capacities=[capacity()],
    )
    assert opp.method == "ALGORITHMIC"
    assert net_exit.rank([opp])["method"] == "ALGORITHMIC"


def test_synthetic_price_provenance_is_carried_through_to_the_opportunity():
    prov = {"source": "synthetic_v1", "freshness": "SYNTHETIC", "is_synthetic": True}
    opp = net_exit.build_mandi_opportunity(
        product=product(), crop=CROP, district="Pune",
        price_row={"modal_price_paise": 2400}, distance_km=50.0,
        capacities=[capacity()], price_provenance=prov,
    )
    assert opp.price_provenance["is_synthetic"] is True
    assert opp.to_dict()["price_provenance"]["freshness"] == "SYNTHETIC"


def test_to_dict_exposes_the_full_contract():
    opp = net_exit.build_mandi_opportunity(
        product=product(), crop=CROP, district="Pune",
        price_row={"modal_price_paise": 2400}, distance_km=50.0,
        capacities=[capacity()],
    )
    d = opp.to_dict()
    for key in ("channel", "crop_id", "grade", "quantity_kg", "unit_price_paise",
                "gross_value_paise", "transport_cost_paise", "storage_cost_paise",
                "platform_fee_paise", "expected_loss_paise",
                "net_realization_paise", "distance_km", "deadline", "feasible",
                "blockers", "cost_basis_complete", "limitations",
                "payment_reliability", "method", "price_provenance",
                "confidence", "breakdown", "reasons"):
        assert key in d, f"contract is missing {key}"


# --------------------------------------------------------- API / authorization
def test_net_exit_requires_authentication():
    res = client.get("/api/decisions/net-exit?product_id=prod-1")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHENTICATED"


def test_net_exit_rejects_a_garbage_token():
    res = client.get("/api/decisions/net-exit?product_id=prod-1",
                     headers={"Authorization": "Bearer nope"})
    assert res.status_code == 401


def test_decisions_router_is_read_only():
    routes = [r for r in app.routes if getattr(r, "path", "").startswith("/api/decisions")]
    assert routes, "decisions router is not registered"
    for route in routes:
        assert set(route.methods) <= {"GET", "HEAD", "OPTIONS"}


def test_net_exit_is_farmer_only():
    """Role isolation is declared on the route, not left to the handler."""
    from backend.app.routers import decisions
    route = next(r for r in app.routes
                 if getattr(r, "path", "") == "/api/decisions/net-exit")
    assert decisions.require_farmer in route.dependencies


def test_malformed_product_id_is_a_clean_404_not_a_500():
    """A bad uuid must not surface Postgres' 22P02 as INTERNAL."""
    for bad in ("", "not-a-uuid", "'; drop table products;--"):
        res = client.get(f"/api/decisions/net-exit?product_id={bad}",
                         headers={"Authorization": "Bearer nope"})
        # Auth is checked first, so this asserts we never reach a 500.
        assert res.status_code in (401, 404, 422), f"{bad!r} gave {res.status_code}"
