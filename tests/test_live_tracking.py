"""Guards on the farmer-confirm-pickup / live-tracking / buyer-confirm-delivery
workflow. Pure -- no database. Pin the properties a green happy-path click-
through would not notice missing.
"""
from __future__ import annotations

import inspect
from pathlib import Path

from backend.app.routers import transport as tr
from backend.app.services import state_machine as sm


def _schema_sql() -> str:
    root = Path(__file__).resolve().parents[1]
    return (root / "db" / "SCHEMA.sql").read_text(encoding="utf-8")


# ------------------------------------------------------- farmer confirms pickup
def test_transporter_cannot_mark_picked_up_without_farmer_confirmation():
    src = inspect.getsource(tr.update_shipment_status)
    assert 'body.status == "picked_up" and not s.get("pickup_confirmed_at")' in src
    assert "has not confirmed the pickup" in src


def test_confirm_pickup_is_farmer_only():
    src = inspect.getsource(tr.confirm_pickup)
    assert 'order.get("farmer_id") != user.id' in src
    assert "Forbidden" in src


def test_confirm_pickup_requires_an_assigned_shipment():
    src = inspect.getsource(tr.confirm_pickup)
    assert 's["status"] != "assigned"' in src


def test_confirm_pickup_is_not_repeatable():
    src = inspect.getsource(tr.confirm_pickup)
    assert "already confirmed" in src


def test_confirm_pickup_notifies_the_transporter():
    src = inspect.getsource(tr.confirm_pickup)
    assert "notif.pickup_confirmed_body" in src


# --------------------------------------------------- buyer confirms delivery
def test_transporter_can_never_set_delivered_directly():
    """This is the exact anti-pattern the spec calls out: a transporter
    reaching the destination must not, by itself, complete the order."""
    assert "delivered" not in tr.ShipmentUpdateIn.model_fields["status"].metadata[0].pattern
    src = inspect.getsource(tr.update_shipment_status)
    assert '"status": "delivered"' not in src


def test_confirm_delivery_is_buyer_only():
    src = inspect.getsource(tr.confirm_delivery)
    assert 'order.get("buyer_id") != user.id' in src
    assert "Forbidden" in src


def test_confirm_delivery_requires_arrived_or_in_transit():
    src = inspect.getsource(tr.confirm_delivery)
    assert '"arrived", "in_transit"' in src


def test_delivered_is_reachable_only_by_the_buyer_role_in_the_state_machine():
    assert sm.TRANSITIONS["IN_TRANSIT"]["DELIVERED"] == ["buyer"]
    assert "transporter" not in sm.TRANSITIONS["IN_TRANSIT"]["DELIVERED"]


def test_confirm_delivery_notifies_both_transporter_and_farmer():
    src = inspect.getsource(tr.confirm_delivery)
    assert "notif.delivery_confirmed_body_transporter" in src
    assert "notif.delivery_confirmed_body_farmer" in src


# ------------------------------------------------------------- live location
def test_location_updates_are_transporter_only_and_role_gated():
    src = inspect.getsource(tr.update_location)
    assert "require_transporter" in src
    assert '.eq("transporter_id", user.id)' in src


def test_location_updates_only_accepted_mid_shipment():
    src = inspect.getsource(tr.update_location)
    assert '"picked_up", "in_transit"' in src


def test_location_updates_are_throttled_server_side():
    """The frontend throttles too, but a client cannot be trusted to actually
    do that -- this is the guarantee that holds regardless."""
    src = inspect.getsource(tr.update_location)
    assert "MIN_LOCATION_UPDATE_INTERVAL_S" in src
    assert '"throttled": True' in src


def test_location_write_goes_to_both_the_fast_path_and_the_history_table():
    src = inspect.getsource(tr.update_location)
    assert 'table("shipments").update' in src
    assert 'table("shipment_locations").insert' in src


def test_arrival_is_auto_detected_by_geofence_not_claimed_by_the_client():
    """The client sends a raw GPS reading; the SERVER decides whether that
    reading is within the geofence, not a client-supplied 'arrived' flag."""
    src = inspect.getsource(tr.update_location)
    assert "ARRIVAL_GEOFENCE_M" in src
    assert "haversine" in src
    assert "arrived_now" in src


def test_geofence_arrival_does_not_skip_the_buyer_confirmation():
    """Auto-detected arrival only ever sets shipment status 'arrived', never
    'delivered' -- the buyer confirmation gate still applies regardless of
    how arrival was detected."""
    src = inspect.getsource(tr.update_location)
    assert '"status"] = "arrived"' in src
    assert '"delivered"' not in src


# --------------------------------------------------------------- checkpoints
def test_checkpoints_are_derived_from_real_timestamps_not_invented():
    src = inspect.getsource(tr.shipment_checkpoints)
    for col in ("pickup_confirmed_at", "journey_started_at", "arrived_at", "delivered_at"):
        assert col in src


def test_near_destination_checkpoint_is_explicitly_marked_ephemeral():
    """It is not persisted -- distance-to-destination is computed live, not
    stored as a fake milestone the frontend could get stuck showing."""
    src = inspect.getsource(tr.shipment_checkpoints)
    assert "ephemeral" in src.lower()


# ---------------------------------------------------- pickup/drop coordinates
def test_shipment_details_accept_coordinates_from_places_autocomplete():
    fields = tr.ShipmentDetailsIn.model_fields
    for f in ("pickup_lat", "pickup_lon", "pickup_place_id",
              "drop_lat", "drop_lon", "drop_place_id"):
        assert f in fields


def test_coordinates_are_stored_as_given_never_re_geocoded():
    src = inspect.getsource(tr.upsert_shipment_details)
    assert '"pickup_lat": body.pickup_lat' in src
    assert '"drop_lat": body.drop_lat' in src


# ------------------------------------------------------------------- schema
def test_shipment_status_has_an_arrived_state_between_transit_and_delivered():
    sql = _schema_sql()
    assert "add value if not exists 'arrived' after 'in_transit'" in sql


def test_pickup_and_drop_coordinate_columns_exist():
    sql = _schema_sql()
    for col in ("pickup_lat", "pickup_lon", "pickup_place_id",
                "drop_lat", "drop_lon", "drop_place_id"):
        assert f"add column if not exists {col}" in sql


def test_fast_path_live_location_columns_exist():
    sql = _schema_sql()
    for col in ("current_lat", "current_lon", "current_heading",
                "current_speed_kmph", "location_updated_at", "is_tracking"):
        assert f"add column if not exists {col}" in sql


def test_shipments_table_is_added_to_the_realtime_publication():
    sql = _schema_sql()
    assert "alter publication supabase_realtime add table public.shipments" in sql


def test_realtime_is_documented_as_still_subject_to_rls():
    """The whole point of adding this table to the publication rather than
    reaching for a second realtime service: RLS keeps applying."""
    sql = _schema_sql()
    idx = sql.index("alter publication supabase_realtime add table public.shipments")
    comment = sql[max(0, idx - 700):idx]
    assert "RLS still applies to realtime" in comment


# -------------------------------------------------------- config plumbing
def test_google_maps_key_is_server_side_only_like_the_supabase_anon_key():
    """Must reach the browser via GET /api/config at runtime, the same A-16
    pattern as the Supabase anon key -- never a VITE_* build-time var baked
    into the committed bundle."""
    import backend.app.routers.auth as auth_router
    src = inspect.getsource(auth_router.get_config)
    assert "google_maps_api_key" in src
    assert "settings.GOOGLE_MAPS_API_KEY" in src


def test_google_maps_key_is_not_hardcoded_anywhere_in_source():
    root = Path(__file__).resolve().parents[1]
    offenders = []
    for p in (root / "backend").rglob("*.py"):
        if "config.py" in str(p) or "__pycache__" in str(p):
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        if "AIza" in text:
            offenders.append(str(p))
    assert not offenders, f"a real-looking Google API key literal was found in: {offenders}"
