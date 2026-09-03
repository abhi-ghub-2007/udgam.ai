"""Fairness audit (SIH26132 Feature 5 / §14).

Given identical objective conditions, every engine must rank identically no
matter who the counterparties are. These tests exist to fail loudly if a
partner boost, a promoted listing or a house-marketplace tilt is ever
introduced — including by accident.
"""
from __future__ import annotations

import inspect
import itertools
from datetime import date

import pytest

from backend.app.services import aggregation as agg
from backend.app.services import emergency_exit, net_exit, orchestration, sale_window
from backend.app.services.opportunity import CostLine, Opportunity

TODAY = date(2026, 9, 3)

# Names chosen to be exactly the sort of thing a biased implementation would
# privilege. None of them may matter.
LOADED_NAMES = ["UDGAM Marketplace", "Premium Partner Pvt Ltd", "Sponsored Buyer",
                "anonymous smallholder", "zzz last alphabetically"]


def _opp(name, net, distance=100.0, channel="mandi", ref=None):
    o = Opportunity(channel=channel, reference_id=ref or name, reference_name=name,
                    crop_id="c1", crop_code="TOMATO", grade="A",
                    quantity_kg=1000.0, distance_km=distance)
    o.unit_price_paise = 2000
    o.breakdown.append(CostLine("Gross sale value", net, "gross", "farmer", "test"))
    o.recompute_net()
    return o


# ------------------------------------------------------- the declared contract
def test_every_shipped_policy_only_ranks_on_declared_factors():
    for policy in (orchestration.NET_EXIT_POLICY, orchestration.SALE_WINDOW_POLICY,
                   orchestration.AGGREGATION_POLICY):
        policy.validate()


def test_an_undeclared_ranking_factor_is_rejected():
    bad = orchestration.RankingPolicy(primary="vibes", tie_breakers=())
    with pytest.raises(ValueError, match="not a declared ranking factor"):
        bad.validate()


def test_a_forbidden_factor_can_never_be_declared():
    for forbidden in ("is_partner", "commission_rate", "sponsored"):
        assert forbidden in orchestration.FORBIDDEN_FACTORS
        assert forbidden not in orchestration.RANKING_FACTORS


def test_every_declared_factor_carries_a_justification():
    for name, why in orchestration.RANKING_FACTORS.items():
        assert why and len(why) > 15, f"{name} has no stated justification"


def test_disclosure_names_what_is_never_used():
    d = orchestration.disclosure(orchestration.NET_EXIT_POLICY)
    assert "no buyer, market, transporter" in d["statement"].lower()
    assert "is_partner" in d["never_used"]
    assert d["method"] == "ALGORITHMIC"


# ------------------------------------------------ net exit: identity is inert
def test_net_exit_ranking_is_invariant_under_renaming():
    """The core audit. Same economics, every permutation of names."""
    nets = [900_00, 700_00, 500_00]
    baseline = None
    for names in itertools.permutations(LOADED_NAMES[:3]):
        opps = [_opp(n, v, ref=f"ref{i}") for i, (n, v) in enumerate(zip(names, nets))]
        order = [o.reference_id for o in net_exit.rank(opps)["ranked"]]
        if baseline is None:
            baseline = order
        assert order == baseline, f"renaming changed the order: {names}"


def test_net_exit_winner_is_the_highest_net_whatever_it_is_called():
    for name in LOADED_NAMES:
        opps = [_opp(name, 500_00, ref="a"), _opp("plain trader", 900_00, ref="b")]
        assert net_exit.rank(opps)["best"].reference_id == "b"


def test_identical_options_tie_rather_than_one_being_favoured():
    a = _opp("UDGAM Marketplace", 500_00, distance=50.0, ref="a")
    b = _opp("some other market", 500_00, distance=50.0, ref="b")
    ranked = net_exit.rank([a, b])["ranked"]
    assert ranked[0].net_realization_paise == ranked[1].net_realization_paise
    # The tie-break is the declared one (reference_id), not identity.
    assert [o.reference_id for o in ranked] == ["a", "b"]
    assert [o.reference_id for o in net_exit.rank([b, a])["ranked"]] == ["a", "b"]


def test_input_order_cannot_influence_the_result():
    opps = [_opp("x", 300_00, ref="x"), _opp("y", 800_00, ref="y"), _opp("z", 500_00, ref="z")]
    for perm in itertools.permutations(opps):
        assert [o.reference_id for o in net_exit.rank(list(perm))["ranked"]] == ["y", "z", "x"]


def test_channel_type_confers_no_advantage():
    """A platform sale must not outrank a mandi on identical economics."""
    platform = _opp("UDGAM direct", 500_00, distance=50.0, channel="direct_buyer", ref="a")
    mandi = _opp("Public mandi", 500_00, distance=50.0, channel="mandi", ref="b")
    ranked = net_exit.rank([platform, mandi])["ranked"]
    assert ranked[0].net_realization_paise == ranked[1].net_realization_paise


# --------------------------------------------- sale window: identity is inert
def test_sale_window_scenarios_rank_on_risk_adjusted_value_only():
    def run(**kw):
        return sale_window.evaluate(
            product={"crop_id": "c", "quantity_kg": 1000.0,
                     "available_quantity_kg": 1000.0, "grade": "A",
                     "asking_price_paise": 2000, "district": "Nashik"},
            crop={"default_shelf_life_days": 365}, district="Nashik",
            distance_km=10.0,
            capacities=[{"available_capacity_kg": 5000.0, "price_paise_per_kg": 50,
                         "price_paise_per_km": 0, "discount_pct": 0}],
            storage_listings=[{"id": "s", "name": "Godown", "storage_type": "dry",
                               "available_capacity_kg": 50000.0,
                               "price_paise_per_kg_day": 4}], **kw)

    result = run(price_rows={0: {"modal_price_paise": 2000},
                             7: {"modal_price_paise": 2100, "confidence_low_paise": 1000,
                                 "confidence_high_paise": 3200, "is_prediction": True,
                                 "horizon_days": 7}})
    assert result["recommendation"] == "sell_now"
    assert "risk_adjusted" in result["ranked_by"]


# ------------------------------------------ aggregation: identity is inert
def test_aggregation_selection_is_invariant_under_farmer_renaming():
    def lots(names):
        return [{"id": f"p{i}", "farmer_id": n, "crop_id": "crop-1",
                 "available_quantity_kg": 300, "quantity_kg": 300,
                 "asking_price_paise": 2000 + i * 100, "grade": "A",
                 "status": "active", "district": "Nashik", "available_until": None,
                 "farmer_name": n}
                for i, n in enumerate(names)]

    req = {"id": "r", "crop_id": "crop-1", "quantity_kg": 900, "min_grade": "C",
           "target_price_paise": 9000, "delivery_district": "Pune", "status": "open"}
    baseline = None
    for names in itertools.permutations(LOADED_NAMES[:3]):
        chosen = [i.product_id for i in
                  agg.propose(request=req, products=lots(names), today=TODAY).items]
        if baseline is None:
            baseline = chosen
        assert chosen == baseline


def test_aggregation_prefers_the_cheaper_lot_regardless_of_who_owns_it():
    req = {"id": "r", "crop_id": "c", "quantity_kg": 300, "min_grade": "C",
           "target_price_paise": 9000, "delivery_district": "Pune", "status": "open"}
    def lot(pid, farmer, price):
        return {"id": pid, "farmer_id": farmer, "crop_id": "c",
                "available_quantity_kg": 300, "quantity_kg": 300,
                "asking_price_paise": price, "grade": "A", "status": "active",
                "district": "Nashik", "available_until": None, "farmer_name": farmer}
    picked = agg.propose(request=req, today=TODAY, products=[
        lot("partner", "Premium Partner Pvt Ltd", 2500),
        lot("stranger", "anonymous smallholder", 2000)]).items
    assert [i.product_id for i in picked] == ["stranger"]


# ------------------------------------- emergency exit reuses the same ranking
def test_emergency_exit_does_not_define_its_own_ranking():
    """An emergency must not be an excuse for a different notion of 'best'."""
    src = inspect.getsource(emergency_exit)
    assert "sort(" not in src, "emergency exit must not order options itself"
    assert "def rank" not in src
    assert "net_exit.rank" in inspect.getsource(
        __import__("backend.app.routers.decisions", fromlist=["x"]).emergency_exit)


def test_emergency_exit_severity_ignores_value_and_identity():
    """Urgency is perishability and time, never who or how much money."""
    perishable = emergency_exit.severity_of(
        stranded_kg=10, days_to_deadline=30, shelf_life_days=5)
    durable_big = emergency_exit.severity_of(
        stranded_kg=100000, days_to_deadline=30, shelf_life_days=365)
    assert perishable == emergency_exit.SEVERITY_HIGH
    assert durable_big == emergency_exit.SEVERITY_LOW


def test_emergency_exit_is_recommendation_only():
    payload = emergency_exit.summarise(
        emergency_exit.Disruption(
            kind="cancelled", detail="the order was cancelled", order_id="o1",
            stranded_kg=500.0, crop_id="c1", grade="A", days_to_deadline=5,
            severity="medium"),
        {"best": None, "ranked": [], "excluded": [], "ranked_by": "x",
         "assumptions": {}})
    assert payload["original_order_untouched"] is True
    assert payload["requires_confirmation"] is True
    assert payload["recommended_action"] == "no_alternative_found"


# --------------------------------------------- no forbidden term in any engine
@pytest.mark.parametrize("module", [net_exit, sale_window, agg, emergency_exit])
def test_no_engine_mentions_a_forbidden_ranking_factor(module):
    """A grep-level guard: if someone adds `is_partner` to a sort key, this fails."""
    src = inspect.getsource(module)
    for forbidden in ("is_partner", "is_promoted", "sponsored", "account_tier",
                      "commission_rate"):
        assert forbidden not in src, f"{module.__name__} references {forbidden}"


@pytest.mark.parametrize("module", [net_exit, agg])
def test_no_engine_sorts_on_a_display_name(module):
    """Ordering on a name is ordering on identity."""
    src = inspect.getsource(module)
    assert "key=lambda" in src
    for line in src.splitlines():
        if "key=lambda" in line or ("sort(" in line and "key" in line):
            assert "reference_name" not in line and "farmer_name" not in line


# ------------------------------------------------- emergency exit: disruptions
def _order(status="CANCELLED", **over):
    base = {"id": "o1", "status": status, "farmer_id": "f1", "buyer_id": "b1"}
    base.update(over)
    return base


def _items(kg=500.0, grade="A"):
    return [{"order_id": "o1", "farmer_id": "f1", "crop_id": "c1",
             "quantity_kg": kg, "unit_price_paise": 2000, "grade": grade}]


def test_a_healthy_order_is_not_a_disruption():
    assert emergency_exit.classify(order=_order("CONFIRMED"), items=_items()) is None


@pytest.mark.parametrize("status", ["CANCELLED", "DISPUTED"])
def test_cancelled_and_disputed_orders_are_disruptions(status):
    d = emergency_exit.classify(order=_order(status), items=_items(), today=TODAY)
    assert d is not None and d.stranded_kg == 500.0


def test_a_cancelled_shipment_is_a_disruption():
    d = emergency_exit.classify(order=_order("CONFIRMED"), items=_items(),
                                shipment={"status": "cancelled"}, today=TODAY)
    assert d is not None and d.kind.startswith("shipment_")


def test_stranded_quantity_comes_from_the_order_not_the_listing():
    d = emergency_exit.classify(order=_order(), items=_items(kg=137.5), today=TODAY)
    assert d.stranded_kg == 137.5


def test_perishable_stranded_lots_are_high_severity():
    d = emergency_exit.classify(order=_order(), items=_items(), today=TODAY,
                                shelf_life_days=5)
    assert d.severity == emergency_exit.SEVERITY_HIGH


def test_malformed_deadline_does_not_crash_classification():
    d = emergency_exit.classify(order=_order(delivery_deadline="soon"),
                                items=_items(), today=TODAY)
    assert d is not None and d.days_to_deadline is None


def test_summary_headline_names_the_quantity_and_the_best_option():
    best = _opp("Processor", 3_180_000, ref="p1")
    payload = emergency_exit.summarise(
        emergency_exit.classify(order=_order(), items=_items(), today=TODAY),
        net_exit.rank([best]))
    assert "500 kg" in payload["headline"]
    assert "Processor" in payload["headline"]
    assert payload["recommended_action"] == "review_alternatives"
    assert payload["original_order_untouched"] is True
