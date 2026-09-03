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


# --------------------------------------------------- RLS: capacity_write policy
def _schema_sql() -> str:
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    return (root / "db" / "SCHEMA.sql").read_text(encoding="utf-8")


def _policy_block(name: str) -> str:
    sql = _schema_sql()
    start = sql.index(f"create policy {name} ")
    return sql[start:sql.index(";", start)]


def test_capacity_write_requires_the_transporter_role():
    """Ownership alone let any authenticated user post capacity for themselves.
    The WITH CHECK must gate on profiles.role, not just transporter_id."""
    block = _policy_block("capacity_write")
    assert "with check" in block
    check = block[block.index("with check"):]
    assert "transporter_id = auth.uid()" in check, "ownership must be enforced"
    assert "public.profiles p" in check, "role must be verified against profiles"
    assert "p.role = 'transporter'" in check, "only transporters may write capacity"


def test_capacity_write_still_scopes_rows_to_their_owner():
    block = _policy_block("capacity_write")
    using = block[block.index("using"):block.index("with check")]
    assert "transporter_id = auth.uid()" in using


def test_capacity_write_follows_the_storage_listings_convention():
    """One authorization pattern, not two: ownership in USING, ownership plus
    the capability gate in WITH CHECK."""
    for name, gate in (("capacity_write", "p.role = 'transporter'"),
                       ("storage_listings_write", "p.is_storage_provider")):
        block = _policy_block(name)
        assert "for all to authenticated" in block
        assert "exists (select 1 from public.profiles p" in block
        assert gate in block


def test_capacity_write_is_not_granted_to_anonymous():
    assert "to authenticated" in _policy_block("capacity_write")
    assert " to anon" not in _policy_block("capacity_write")


def test_capacity_select_was_not_touched_by_the_hardening():
    """The marketplace stays readable — F-7 depends on open capacity being public
    to authenticated users."""
    block = _policy_block("capacity_select")
    assert "for select to authenticated" in block
    assert "status in ('open','partially_booked')" in block


# ------------------------------------------------ RLS: aggregations_write policy
def test_aggregations_write_requires_the_buyer_role():
    """An aggregation is buyer-owned by construction (buyer_request_id is NOT
    NULL; a farmer participates via aggregation_items). Ownership alone let a
    farmer or transporter create one naming themselves as the buyer."""
    block = _policy_block("aggregations_write")
    check = block[block.index("with check"):]
    assert "buyer_id = auth.uid()" in check, "ownership must be enforced"
    assert "public.profiles p" in check, "role must be verified against profiles"
    assert "p.role = 'buyer'" in check, "only buyers may create aggregations"


def test_aggregations_write_requires_owning_the_buyer_request():
    """Without this a buyer could aggregate against another buyer's requirement."""
    check = _policy_block("aggregations_write")
    assert "public.buyer_requests r" in check
    assert "r.id = buyer_request_id" in check
    assert "r.buyer_id = auth.uid()" in check


def test_aggregations_write_still_scopes_rows_to_their_owner():
    block = _policy_block("aggregations_write")
    using = block[block.index("using"):block.index("with check")]
    assert "buyer_id = auth.uid()" in using


def test_aggregations_write_follows_the_project_authorization_convention():
    """Same shape as capacity_write and storage_listings_write: ownership in
    USING, ownership plus the capability gate in WITH CHECK."""
    block = _policy_block("aggregations_write")
    assert "for all to authenticated" in block
    assert "exists (select 1 from public.profiles p" in block


def test_aggregations_write_is_not_granted_to_anonymous():
    block = _policy_block("aggregations_write")
    assert "to authenticated" in block and " to anon" not in block


def test_aggregation_select_policies_do_not_reference_each_other():
    """The 42P17 regression guard.

    aggregations_select once queried aggregation_items while agg_items_select
    queried aggregations, which is a mutual RLS reference: Postgres raised
    "infinite recursion detected in policy" on every select/update/delete of
    both tables. Each direction must go through a SECURITY DEFINER helper.
    """
    sel = _policy_block("aggregations_select")
    assert "buyer_id = auth.uid()" in sel
    assert "is_aggregation_participant" in sel
    assert "from public.aggregation_items" not in sel, "direct reference re-opens the cycle"

    items = _policy_block("agg_items_select")
    assert "farmer_id = auth.uid()" in items
    assert "is_aggregation_buyer" in items
    assert "from public.aggregations" not in items, "direct reference re-opens the cycle"


def test_aggregation_cycle_breakers_are_security_definer():
    """A plain function would still evaluate the target table's RLS and recurse."""
    sql = _schema_sql()
    for fn in ("is_aggregation_participant", "is_aggregation_buyer"):
        i = sql.index(f"create or replace function public.{fn}")
        body = sql[i:sql.index("$$;", i)]
        assert "security definer" in body, f"{fn} must be SECURITY DEFINER"
        assert "set search_path = public" in body, f"{fn} must pin search_path"


def test_farmer_may_only_update_their_own_aggregation_line():
    """Consent is an UPDATE on your own row — never INSERT (join a group unasked)
    and never DELETE (remove someone else)."""
    block = _policy_block("agg_items_farmer_consent")
    assert "for update to authenticated" in block, "must be UPDATE-only, not FOR ALL"
    assert "farmer_id = auth.uid()" in block


def test_aggregation_items_carry_per_farmer_consent_state():
    """aggregations.status is group-level and cannot record that farmer A agreed
    while farmer B has not answered."""
    sql = _schema_sql()
    ddl = sql[sql.index("create table if not exists public.aggregation_items"):]
    ddl = ddl[:ddl.index(");")]
    assert "consent_status" in ddl and "consent_at" in ddl
    assert "add column if not exists consent_status" in sql, "must be additive for existing DBs"


def test_no_farmer_owned_aggregation_exists_in_the_schema():
    """Pins the design fact the policy rests on: aggregations carry a buyer_id
    and a NOT NULL buyer_request_id, so 'farmer INSERT denied' is correct rather
    than an oversight. A farmer's stake is an aggregation_items row."""
    sql = _schema_sql()
    ddl = sql[sql.index("create table if not exists public.aggregations"):]
    ddl = ddl[:ddl.index(");")]
    assert "buyer_id" in ddl and "buyer_request_id" in ddl
    assert "farmer_id" not in ddl, "aggregations has no farmer owner column"
    items = sql[sql.index("create table if not exists public.aggregation_items"):]
    items = items[:items.index(");")]
    assert "farmer_id" in items
