"""Guards on the transport offer/accept workflow.

Pure — no database. These pin the properties that a passing happy-path E2E
would not notice going missing: that consent cannot be skipped, that the race
is settled in the database rather than the browser, and that the two RLS
grants a transporter needs stay as narrow as they were written.
"""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from backend.app.routers import transport as tr
from backend.app.services import state_machine as sm


def _schema_sql() -> str:
    root = Path(__file__).resolve().parents[1]
    return (root / "db" / "SCHEMA.sql").read_text(encoding="utf-8")


# ----------------------------------------------------- consent, not assignment
def test_transporter_may_reach_logistics_assigned_by_accepting():
    """Accepting an offer is what causes the transition, so the transporter has
    to be a permitted actor for it."""
    sm.validate_transition("PAYMENT_HELD", "LOGISTICS_ASSIGNED", "transporter")


def test_transporter_cannot_accept_the_order_itself():
    """Agreeing to haul is not agreeing to sell. Only the farmer accepts an order."""
    with pytest.raises(Exception):
        sm.validate_transition("PLACED", "ACCEPTED", "transporter")


def test_farmer_can_accept_or_decline_a_placed_order():
    sm.validate_transition("PLACED", "ACCEPTED", "farmer")
    sm.validate_transition("PLACED", "CANCELLED", "farmer")


def test_buyer_cannot_accept_an_order_on_the_farmers_behalf():
    with pytest.raises(Exception):
        sm.validate_transition("PLACED", "ACCEPTED", "buyer")


def test_assign_transport_no_longer_books_anyone_directly():
    """It used to write shipments with a transporter_id straight off the query
    string. It must now go through the offer flow."""
    src = inspect.getsource(tr.assign_transport)
    assert "create_offers" in src
    assert 'table("shipments").insert' not in src


# ----------------------------------------------------------------- concurrency
def test_one_live_shipment_per_order_is_enforced_by_a_unique_index():
    """Two transporters pressing accept at the same moment is settled here, not
    by a disabled button."""
    sql = _schema_sql()
    assert "uq_shipment_live_per_order" in sql
    assert "on public.shipments(order_id) where status <> 'cancelled'" in sql


def test_accept_claims_only_while_the_shipment_is_unclaimed():
    """The UPDATE is conditioned on transporter_id still being null, so the
    loser of a race updates zero rows instead of overwriting the winner."""
    src = inspect.getsource(tr.accept_offer)
    assert '.is_("transporter_id", "null")' in src
    assert "Duplicate" in src, "the loser must get a 409, not a 500"


def test_accept_rechecks_capacity_and_expiry_at_accept_time():
    """Fitness at offer time does not prove fitness at accept time."""
    src = inspect.getsource(tr.accept_offer)
    assert "available_capacity_kg" in src
    assert "expires_at" in src


def test_offer_creation_refuses_a_vehicle_that_cannot_hold_the_load():
    src = inspect.getsource(tr.create_offers)
    assert "insufficient_capacity" in src


# ------------------------------------------------------- decline does not stall
def test_decline_leaves_the_shipment_offerable():
    """The job must not die with the first no: declining touches the offer
    only, never the shipment."""
    src = inspect.getsource(tr.decline_offer)
    assert 'table("shipments")' not in src
    assert '"status": "rejected"' in src


def test_decline_tells_the_arranger_whether_anything_is_still_open():
    src = inspect.getsource(tr.decline_offer)
    assert "offers_still_open" in src
    assert "notif.transport_none_left_body" in src, (
        "running out of transporters needs its own message, not silence")


# ------------------------------------------------------------ RLS: the two grants
def _policy(name: str) -> str:
    sql = _schema_sql()
    start = sql.index(f"create policy {name} ")
    return sql[start:sql.index(";", start)]


def test_a_transporter_can_read_a_job_only_while_the_offer_is_live():
    """Deciding blind is not deciding. The grant is scoped to a pending,
    unexpired offer addressed to that transporter."""
    sql = _schema_sql()
    fn_start = sql.index("function public.has_open_transport_offer(")
    body = sql[fn_start:sql.index("$$;", fn_start)]
    assert "cr.status = 'pending'" in body
    assert "expires_at is null or cr.expires_at > now()" in body
    assert "c.transporter_id = uid" in body
    assert "public.has_open_transport_offer(id, auth.uid())" in _policy("shipments_select")


def test_claiming_cannot_hand_the_job_to_a_third_party():
    """USING lets an offer-holder claim an unassigned shipment; WITH CHECK
    deliberately does not, so the row they write must name themselves."""
    block = _policy("shipments_update")
    using = block[block.index("using"):block.index("with check")]
    check = block[block.index("with check"):]
    assert "has_open_transport_offer" in using
    assert "has_open_transport_offer" not in check
    assert "transporter_id = auth.uid()" in check


def test_the_order_grant_expires_with_the_offer():
    sql = _schema_sql()
    fn_start = sql.index("function public.has_open_transport_offer_on_order(")
    body = sql[fn_start:sql.index("$$;", fn_start)]
    assert "cr.status = 'pending'" in body
    assert "expires_at is null or cr.expires_at > now()" in body


def test_transport_grants_are_not_given_to_anonymous():
    for name in ("shipments_select", "shipments_update", "orders_select"):
        assert "to authenticated" in _policy(name)
        assert " to anon" not in _policy(name)


# ------------------------------------------------------- invalid logistics
def test_impossible_windows_are_rejected_by_the_database_too():
    """The form is not the security boundary."""
    sql = _schema_sql()
    assert "shipments_window_sane" in sql
    block = sql[sql.index("shipments_window_sane"):]
    block = block[:block.index("exception")]
    assert "pickup_until >= pickup_from" in block
    assert "deliver_by >= pickup_from" in block


def test_router_rejects_a_pickup_window_that_has_already_passed():
    src = inspect.getsource(tr.upsert_shipment_details)
    assert "already passed" in src


def test_terms_cannot_move_under_a_transporter_who_accepted_them():
    src = inspect.getsource(tr.upsert_shipment_details)
    assert "already accepted these terms" in src


# ---------------------------------------------------------------- neutrality
def test_transport_options_do_not_rank_on_reputation():
    """orchestration.py forbids ranking on transporter identity and declares no
    factor for carrier reputation, so reliability may inform a human but must
    not order the list."""
    src = inspect.getsource(tr.transport_options)
    sort_line = next(l for l in src.splitlines() if "options.sort" in l)
    tail = src[src.index("options.sort"):]
    key = tail[:tail.index(")\n")]
    for banned in ("avg_rating", "rating", "reliability", "transporter_name"):
        assert banned not in key, f"ranking must not use {banned}"
    assert "estimated_cost_paise" in key
    assert sort_line is not None


def test_transport_options_still_surface_reliability_for_the_human():
    src = inspect.getsource(tr.transport_options)
    assert '"reliability"' in src
    assert "avg_rating" in src


def test_declared_ranking_is_reported_to_the_caller():
    src = inspect.getsource(tr.transport_options)
    assert '"ranked_by"' in src


# ------------------------------------------------------------------- honesty
def test_cost_is_an_estimate_and_kept_apart_from_settled_earnings():
    sql = _schema_sql()
    assert "transport_cost_estimate_paise" in sql
    src = inspect.getsource(tr._estimate_cost_paise)
    assert "estimate" in src.lower()


def test_distance_reuses_the_existing_haversine():
    """Not a second distance calculation (§28)."""
    src = inspect.getsource(tr._capacity_route_km)
    assert "haversine" in src
