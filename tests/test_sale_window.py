"""Risk-Adjusted Sale Window — scenarios, risk charge, and the anti-greed rule.

The rule under test throughout: a higher forecast price is never on its own a
reason to wait.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services import net_exit, sale_window

client = TestClient(app)

PERISHABLE = {"id": "c1", "code": "TOMATO", "category": "vegetable",
              "default_shelf_life_days": 7}
DURABLE = {"id": "c2", "code": "WHEAT", "category": "grain",
           "default_shelf_life_days": 365}


def product(**over):
    base = {"id": "p1", "farmer_id": "f1", "crop_id": "c2", "quantity_kg": 1000.0,
            "available_quantity_kg": 1000.0, "asking_price_paise": 2000,
            "grade": "A", "district": "Nashik"}
    base.update(over)
    return base


def capacity(**over):
    base = {"available_capacity_kg": 5000.0, "price_paise_per_kg": 50,
            "price_paise_per_km": 0, "discount_pct": 0, "dest_district": None}
    base.update(over)
    return base


def storage(**over):
    base = {"id": "s1", "name": "Nashik Dry Godown", "storage_type": "dry",
            "available_capacity_kg": 50000.0, "price_paise_per_kg_day": 4}
    base.update(over)
    return base


def price(modal, low=None, high=None, prediction=False, horizon=None):
    return {"modal_price_paise": modal, "confidence_low_paise": low,
            "confidence_high_paise": high, "is_prediction": prediction,
            "horizon_days": horizon, "method": "SYNTHETIC",
            "data_source": "synthetic_v1"}


# ------------------------------------------------------------------- storage
def test_storage_is_priced_from_the_cheapest_listing_with_room():
    q = sale_window.quote_storage(
        [storage(price_paise_per_kg_day=9), storage(id="s2", price_paise_per_kg_day=4)],
        quantity_kg=1000.0, days=7,
    )
    assert q.cost_paise == 4 * 1000 * 7
    assert q.rate_paise_per_kg_day == 4


def test_storage_listing_without_room_is_not_quoted():
    assert sale_window.quote_storage(
        [storage(available_capacity_kg=10.0)], quantity_kg=1000.0, days=7
    ) is None


def test_selling_now_needs_no_storage():
    assert sale_window.quote_storage([storage()], quantity_kg=1000.0, days=0) is None


def test_waiting_without_storage_is_not_comparable_rather_than_free():
    """An uncosted holding cost must not let waiting win by omission."""
    opp = sale_window.build_scenario(
        product=product(), crop=DURABLE, district="Nashik", horizon_days=7,
        price_row=price(2400, 2200, 2600, True, 7), distance_km=10.0,
        capacities=[capacity()], storage_listings=[],
    )
    assert opp.cost_basis_complete is False
    assert opp.net_realization_paise is None
    assert any("cannot be determined" in l for l in opp.limitations)


def test_storage_cost_scales_with_days_held():
    costs = []
    for days in (3, 7, 14):
        opp = sale_window.build_scenario(
            product=product(), crop=DURABLE, district="Nashik", horizon_days=days,
            price_row=price(2400, 2200, 2600, True, days), distance_km=10.0,
            capacities=[capacity()], storage_listings=[storage()],
        )
        costs.append(opp.storage_cost_paise)
    assert costs == sorted(costs) and costs[0] < costs[-1]


# ---------------------------------------------------------------- risk charge
def test_risk_penalty_comes_from_the_forecast_downside_band():
    penalty, basis = sale_window.risk_penalty_paise(
        expected_unit_paise=2400, confidence_low_paise=2000, quantity_kg=1000.0)
    assert penalty == int(sale_window.RISK_AVERSION * 400 * 1000)
    assert "downside" in basis


def test_wider_band_costs_more():
    narrow, _ = sale_window.risk_penalty_paise(
        expected_unit_paise=2400, confidence_low_paise=2300, quantity_kg=1000.0)
    wide, _ = sale_window.risk_penalty_paise(
        expected_unit_paise=2400, confidence_low_paise=1500, quantity_kg=1000.0)
    assert wide > narrow


def test_no_band_means_no_penalty_not_an_invented_one():
    penalty, basis = sale_window.risk_penalty_paise(
        expected_unit_paise=2400, confidence_low_paise=None, quantity_kg=1000.0)
    assert penalty == 0 and "no downside band" in basis


def test_risk_charge_sits_outside_net_realization():
    """net_realization stays the honest economics; RAEV carries the charge."""
    opp = sale_window.build_scenario(
        product=product(), crop=DURABLE, district="Nashik", horizon_days=7,
        price_row=price(2400, 1800, 3000, True, 7), distance_km=10.0,
        capacities=[capacity()], storage_listings=[storage()],
    )
    assert opp.risk_penalty_paise > 0
    assert opp.risk_adjusted_paise == opp.net_realization_paise - opp.risk_penalty_paise
    assert not any(l.label.startswith("Risk") for l in opp.breakdown)


def test_selling_now_carries_no_risk_charge():
    opp = sale_window.build_scenario(
        product=product(), crop=DURABLE, district="Nashik", horizon_days=0,
        price_row=price(2400), distance_km=10.0,
        capacities=[capacity()], storage_listings=[storage()],
    )
    assert opp.risk_penalty_paise == 0
    assert opp.risk_adjusted_paise == opp.net_realization_paise
    assert any("no forecast uncertainty" in n for n in opp.risk_notes)


def test_low_confidence_is_communicated():
    opp = sale_window.build_scenario(
        product=product(), crop=DURABLE, district="Nashik", horizon_days=14,
        price_row=price(2400, 1500, 3300, True, 14), distance_km=10.0,
        capacities=[capacity()], storage_listings=[storage()],
        price_provenance={"confidence": 0.18, "source": "synthetic_v1"},
    )
    assert any("uncertainty is substantial" in n for n in opp.risk_notes)


# ------------------------------------------------------- the anti-greed rule
def test_higher_forecast_price_alone_does_not_win():
    """The rule this whole module exists for."""
    result = sale_window.evaluate(
        product=product(), crop=DURABLE, district="Nashik",
        price_rows={
            0: price(2400),
            7: price(2500, 1600, 3400, True, 7),   # higher, but very uncertain
        },
        distance_km=10.0, capacities=[capacity()], storage_listings=[storage()],
    )
    assert result["recommendation"] == "sell_now"
    assert result["best"].holding_days == 0


def test_waiting_wins_when_the_gain_genuinely_clears_the_costs():
    result = sale_window.evaluate(
        product=product(), crop=DURABLE, district="Nashik",
        price_rows={
            0: price(2000),
            7: price(2900, 2850, 2950, True, 7),   # much higher and tight band
        },
        distance_km=10.0, capacities=[capacity()], storage_listings=[storage()],
    )
    assert result["recommendation"] == "wait"
    assert result["best"].holding_days == 7
    assert any("better than selling today" in r for r in result["best"].reasons)


def test_high_storage_cost_can_flip_the_answer_back_to_selling_now():
    common = dict(product=product(), crop=DURABLE, district="Nashik",
                  price_rows={0: price(2000), 7: price(2300, 2250, 2350, True, 7)},
                  distance_km=10.0, capacities=[capacity()])
    cheap = sale_window.evaluate(**common, storage_listings=[storage(price_paise_per_kg_day=1)])
    dear = sale_window.evaluate(**common, storage_listings=[storage(price_paise_per_kg_day=90)])
    assert cheap["recommendation"] == "wait"
    assert dear["recommendation"] == "sell_now"


def test_perishable_crop_cannot_be_held_beyond_its_shelf_life():
    result = sale_window.evaluate(
        product=product(crop_id="c1"), crop=PERISHABLE, district="Nashik",
        price_rows={0: price(2000), 14: price(4000, 3900, 4100, True, 14)},
        distance_km=10.0, capacities=[capacity()], storage_listings=[storage()],
    )
    # Even at double the price, a 7-day crop cannot wait 14 days.
    assert result["recommendation"] == "sell_now"
    blocked = [o for o in result["excluded"] if o.holding_days == 14]
    assert blocked and any("would not keep" in b for b in blocked[0].blockers)


def test_spoilage_grows_with_holding_and_is_charged():
    now = sale_window.build_scenario(
        product=product(), crop=PERISHABLE, district="Nashik", horizon_days=0,
        price_row=price(2400), distance_km=10.0,
        capacities=[capacity()], storage_listings=[storage()])
    later = sale_window.build_scenario(
        product=product(), crop=PERISHABLE, district="Nashik", horizon_days=3,
        price_row=price(2400, 2300, 2500, True, 3), distance_km=10.0,
        capacities=[capacity()], storage_listings=[storage()])
    assert later.expected_loss_paise > now.expected_loss_paise


# --------------------------------------------------------------- missing data
def test_horizon_without_a_forecast_row_is_skipped_not_extrapolated():
    result = sale_window.evaluate(
        product=product(), crop=DURABLE, district="Nashik",
        price_rows={0: price(2000)},          # no forecasts at all
        distance_km=10.0, capacities=[capacity()], storage_listings=[storage()],
    )
    assert [s.holding_days for s in result["ranked"]] == [0]
    assert result["recommendation"] == "sell_now"


def test_no_price_data_at_all_yields_no_recommendation():
    result = sale_window.evaluate(
        product=product(), crop=DURABLE, district="Nashik", price_rows={},
        distance_km=10.0, capacities=[capacity()], storage_listings=[storage()],
    )
    assert result["best"] is None and result["recommendation"] is None


def test_zero_quantity_is_infeasible_everywhere():
    result = sale_window.evaluate(
        product=product(quantity_kg=0, available_quantity_kg=0), crop=DURABLE,
        district="Nashik", price_rows={0: price(2000)},
        distance_km=10.0, capacities=[capacity()], storage_listings=[storage()],
    )
    assert result["best"] is None


def test_synthetic_provenance_is_carried_into_every_scenario():
    result = sale_window.evaluate(
        product=product(), crop=DURABLE, district="Nashik",
        price_rows={0: price(2000), 7: price(2100, 2000, 2200, True, 7)},
        distance_km=10.0, capacities=[capacity()], storage_listings=[storage()],
        provenances={0: {"is_synthetic": True, "freshness": "SYNTHETIC"},
                     7: {"is_synthetic": True, "freshness": "SYNTHETIC"}},
    )
    for s in result["ranked"]:
        assert s.price_provenance["is_synthetic"] is True


# ------------------------------------------------------------------- contract
def test_ranking_key_is_risk_adjusted_and_disclosed():
    result = sale_window.evaluate(
        product=product(), crop=DURABLE, district="Nashik",
        price_rows={0: price(2000)}, distance_km=10.0,
        capacities=[capacity()], storage_listings=[storage()],
    )
    assert "risk_adjusted" in result["ranked_by"]
    assert result["method"] == "ALGORITHMIC"


def test_assumptions_disclose_the_risk_model():
    a = sale_window.evaluate(
        product=product(), crop=DURABLE, district="Nashik", price_rows={},
        distance_km=10.0, capacities=[], storage_listings=[])["assumptions"]
    assert a["risk_aversion"] == sale_window.RISK_AVERSION
    assert "RISK_AVERSION" in a["risk_penalty_formula"]
    assert "never on the headline" in a["note"]
    # Net Exit's own assumptions remain visible alongside.
    assert a["mandi_commission_bps"] == net_exit.MANDI_COMMISSION_BPS


def test_scenarios_are_named_for_a_farmer_not_a_developer():
    result = sale_window.evaluate(
        product=product(), crop=DURABLE, district="Nashik",
        price_rows={0: price(2000), 3: price(2100, 2000, 2200, True, 3)},
        distance_km=10.0, capacities=[capacity()], storage_listings=[storage()],
    )
    names = {s.reference_name for s in result["ranked"]}
    assert "Sell now" in names and "Wait 3 days" in names


def test_all_money_stays_integer_paise():
    opp = sale_window.build_scenario(
        product=product(quantity_kg=333.33, available_quantity_kg=333.33),
        crop=DURABLE, district="Nashik", horizon_days=7,
        price_row=price(1777, 1600, 1900, True, 7), distance_km=123.4,
        capacities=[capacity()], storage_listings=[storage()],
    )
    for v in (opp.storage_cost_paise, opp.risk_penalty_paise,
              opp.net_realization_paise, opp.risk_adjusted_paise):
        assert isinstance(v, int)


# ------------------------------------------------------------ API / security
def test_sale_window_requires_authentication():
    res = client.get("/api/decisions/sale-window?product_id=p1")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHENTICATED"


@pytest.mark.parametrize("bad", ["", "not-a-uuid"])
def test_malformed_product_id_never_500s(bad):
    res = client.get(f"/api/decisions/sale-window?product_id={bad}",
                     headers={"Authorization": "Bearer nope"})
    assert res.status_code in (401, 404, 422)


def test_sale_window_is_farmer_only_and_read_only():
    from backend.app.routers import decisions
    route = next(r for r in app.routes
                 if getattr(r, "path", "") == "/api/decisions/sale-window")
    assert decisions.require_farmer in route.dependencies
    assert set(route.methods) <= {"GET", "HEAD", "OPTIONS"}


# ------------------------------------------ defence against self-posted capacity
def test_capacity_is_filtered_to_real_transporters():
    """The capacity_write RLS policy has no role check, so a farmer can post a
    capacity row for themselves. The engine must not price transport from it."""
    from backend.app.routers import decisions

    class FakeQuery:
        def __init__(self, table): self.table_name = table; self.filters = {}
        def select(self, *_a, **_k): return self
        def eq(self, k, v): self.filters[k] = v; return self
        def in_(self, k, v): self.filters[k] = v; return self
        def limit(self, _n): return self
        def execute(self):
            class R: pass
            r = R()
            if self.table_name == "transport_capacity":
                r.data = [
                    {"transporter_id": "real-t", "available_capacity_kg": 5000,
                     "price_paise_per_kg": 100, "price_paise_per_km": 0,
                     "discount_pct": 0, "dest_district": None, "status": "open"},
                    {"transporter_id": "sneaky-farmer", "available_capacity_kg": 5000,
                     "price_paise_per_kg": 1, "price_paise_per_km": 0,
                     "discount_pct": 0, "dest_district": None, "status": "open"},
                ]
            else:                                   # profiles
                r.data = [{"id": "real-t", "role": "transporter"}]
            return r

    class FakeDB:
        def table(self, name): return FakeQuery(name)

    rows = decisions._posted_capacity(FakeDB())
    assert [r["transporter_id"] for r in rows] == ["real-t"]
    assert all(r["price_paise_per_kg"] != 1 for r in rows)
