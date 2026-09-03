"""Guards on the demo seed.

Written after a real incident: the logistics seed was once run against
whichever transporter a query happened to return first, which attached demo
inventory to a genuine account and flipped its is_storage_provider flag. These
tests pin the properties that stop that recurring. They are pure — no database.
"""
from __future__ import annotations

import inspect

from backend.app.services import market_data as md
from scripts import seed_demo as sd


# ------------------------------------------------ stable identity, not ordering
def test_demo_transporter_is_resolved_from_a_declared_email():
    assert sd.DEMO_TRANSPORTER_EMAIL == "demo.transporter@udgam.test"
    assert any(u["email"] == sd.DEMO_TRANSPORTER_EMAIL and u["key"] == "transporter"
               for u in sd.DEMO_USERS)


def test_logistics_seed_takes_no_caller_supplied_owner():
    """The incident happened because an id could be passed in. It cannot now."""
    params = inspect.signature(sd.seed_logistics_and_storage).parameters
    assert not params, f"seed_logistics_and_storage must take no arguments, got {list(params)}"


def test_logistics_seed_refuses_a_non_transporter_owner():
    """The role check is present in the source, guarding against a mis-typed email
    resolving to some other account."""
    src = inspect.getsource(sd.seed_logistics_and_storage)
    assert 'role' in src and 'refusing to seed' in src


def test_logistics_seed_scopes_its_deletes_to_the_demo_owner():
    """Idempotency must never be achieved by clearing the whole table."""
    src = inspect.getsource(sd.seed_logistics_and_storage)
    for table in ("transport_capacity", "storage_listings"):
        assert f'table("{table}").delete().eq(' in src, (
            f"the {table} delete must be scoped with .eq(), not unfiltered"
        )


# ----------------------------------------------------------- declared demo data
def test_transport_routes_are_well_formed_and_use_known_districts():
    assert sd.TRANSPORT_ROUTES
    for origin, dest, per_kg, per_km, cap, discount, ctype in sd.TRANSPORT_ROUTES:
        assert origin in md.MARKET_DISTRICTS, origin
        assert dest in md.MARKET_DISTRICTS, dest
        assert per_kg > 0 and per_km > 0
        assert cap > 0
        assert 0 <= discount < 100
        assert ctype in ("scheduled_route", "empty_leg", "on_demand")


def test_storage_sites_are_well_formed_and_use_known_districts():
    assert sd.STORAGE_SITES
    for name, district, stype, cap, rate, temp in sd.STORAGE_SITES:
        assert district in md.MARKET_DISTRICTS, district
        assert stype in ("cold", "dry", "controlled_atmosphere")
        assert cap > 0 and rate > 0
        assert name and not name.endswith("(demo)"), "the suffix is added at write time"


def test_cold_storage_costs_more_than_dry():
    """Sanity on the demo economics: refrigeration is not cheaper than a shed."""
    cold = [r for *_x, t, _c, r, _tc in [(n, d, t, c, r, tc) for n, d, t, c, r, tc in sd.STORAGE_SITES] if t == "cold"]
    dry = [r for n, d, t, c, r, tc in sd.STORAGE_SITES if t == "dry"]
    assert min(cold) > max(dry)


# ---------------------------------------------------------------------- honesty
def test_seeded_rows_are_labelled_as_demo_data():
    """transport_capacity.notes is the only provenance field that table has;
    storage_listings has none, so its name carries the label."""
    src = inspect.getsource(sd.seed_logistics_and_storage)
    assert "DEMO/SYNTHETIC" in src
    assert '(demo)' in src


def _code_without_docstring(func) -> str:
    """Source with the docstring stripped, so prose explaining what we avoid is
    not mistaken for doing it."""
    src = inspect.getsource(func)
    doc = inspect.getdoc(func)
    if doc:
        for line in doc.splitlines():
            src = src.replace(line, "")
    return src


def test_market_seed_never_claims_agmarknet_or_real():
    code = _code_without_docstring(sd.seed_market_prices)
    assert '"SYNTHETIC"' in code
    assert "SYNTHETIC_SOURCE" in code
    assert '"REAL"' not in code
    assert "agmarknet" not in code, "the seed must never write the agmarknet source"


def test_auth_user_lookup_is_idempotent_by_construction():
    """It must consult existing records before attempting to create, and page
    through list_users rather than scanning only the first page."""
    src = inspect.getsource(sd._ensure_auth_user)
    assert 'table("profiles")' in src, "must look up the existing profile first"
    assert "for page in range" in src, "list_users is paginated; page through it"
