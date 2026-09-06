"""Guards on reputation.

Pure — no database. A rating is only worth reading if it cannot be
manufactured, so these pin the cases from §19: reviewing a stranger, reviewing
yourself, reviewing twice, reviewing a deal that never completed, and naming
somebody else as the author.
"""
from __future__ import annotations

import inspect
from pathlib import Path

from backend.app.routers import reviews as rv
from scripts import seed_demo as sd


def _schema_sql() -> str:
    root = Path(__file__).resolve().parents[1]
    return (root / "db" / "SCHEMA.sql").read_text(encoding="utf-8")


def _policy(name: str) -> str:
    sql = _schema_sql()
    start = sql.index(f"create policy {name} ")
    return sql[start:sql.index(";", start)]


# ------------------------------------------------------- who may review whom
def test_both_parties_must_have_been_on_the_order():
    """Reviewer participation alone let a genuine buyer review a transporter
    who never carried for them, or any stranger named as ratee."""
    check = _policy("feedback_insert")
    assert "rater_id = auth.uid()" in check
    assert "is_order_participant(order_id, auth.uid())" in check
    assert "is_order_participant(order_id, ratee_id)" in check


def test_self_review_is_impossible_in_the_table_itself():
    sql = _schema_sql()
    assert "check (rater_id <> ratee_id)" in sql


def test_one_review_per_counterparty_per_order():
    sql = _schema_sql()
    assert "unique (order_id, rater_id, ratee_id)" in sql


def test_the_author_is_never_taken_from_the_request_body():
    """A forged rater_id must not be able to file a review as somebody else."""
    src = inspect.getsource(rv.leave_feedback)
    assert '"rater_id": user.id' in src
    assert "body.rater_id" not in src


def test_the_reviewed_role_is_derived_not_declared():
    """Otherwise a caller could file a farmer's review under 'transporter' and
    poison a reputation the person never earned."""
    src = inspect.getsource(rv.leave_feedback)
    assert "ratee_role = _role_on_order(" in src
    assert "body.ratee_role" not in src


def test_role_on_order_reads_the_order_and_its_shipment():
    src = inspect.getsource(rv._role_on_order)
    for token in ("buyer_id", "farmer_id", "shipments", "transporter_id"):
        assert token in src


# --------------------------------------------------------- only completed deals
def test_only_delivered_or_closed_orders_can_be_reviewed():
    assert rv.REVIEWABLE_STATUSES == ("DELIVERED", "CLOSED")
    assert "CANCELLED" not in rv.REVIEWABLE_STATUSES, (
        "a cancelled order produced no performance to judge")


def test_the_status_gate_is_enforced_in_the_write_path():
    src = inspect.getsource(rv.leave_feedback)
    assert "REVIEWABLE_STATUSES" in src


def test_self_review_is_also_refused_with_a_sentence():
    src = inspect.getsource(rv.leave_feedback)
    assert "cannot review yourself" in src


def test_duplicate_review_is_reported_not_five_hundred():
    src = inspect.getsource(rv.leave_feedback)
    assert "already reviewed them" in src


# ----------------------------------------------- aggregates cannot be authored
def test_rating_is_only_ever_derived_from_the_reviews():
    """Nothing writes avg_rating directly; it is recomputed from feedback rows,
    so the headline number cannot disagree with the reviews behind it."""
    src = inspect.getsource(rv._recompute_rating)
    assert 'table("feedback")' in src
    assert "sum(r[\"rating\"] for r in rows)" in src

    write_src = inspect.getsource(rv.leave_feedback)
    assert "_recompute_rating(body.ratee_id)" in write_src


def test_a_user_cannot_edit_their_own_headline_rating():
    """profiles_update_self keeps a profile row to its owner, and the aggregate
    is written by the service role instead — so a reviewer cannot bump the
    person they reviewed, and nobody can bump themselves."""
    block = _policy("profiles_update_self")
    assert "id = auth.uid()" in block
    assert "admin_client" in inspect.getsource(rv._recompute_rating)


def test_reviews_are_publicly_readable_so_they_can_be_weighed_first():
    assert "using (true)" in _policy("feedback_select")


# ------------------------------------------------- three reputations, not one
def test_reputation_is_scoped_by_the_role_that_earned_it():
    sql = _schema_sql()
    assert "ratee_role user_role not null" in sql
    src = inspect.getsource(rv.profile_reviews)
    assert 'eq("ratee_role", role)' in src
    assert '"by_role"' in src


def test_tags_are_role_specific():
    assert set(rv.ALLOWED_TAGS) == {"farmer", "buyer", "transporter"}
    assert "paid_promptly" in rv.ALLOWED_TAGS["buyer"]
    assert "paid_promptly" not in rv.ALLOWED_TAGS["transporter"]
    assert "damaged_goods" in rv.ALLOWED_TAGS["transporter"]


def test_unknown_tags_are_rejected():
    src = inspect.getsource(rv.leave_feedback)
    assert "Unknown tag" in src


# --------------------------------------------------------------- §44 honesty
def test_performance_counts_are_counted_not_stored():
    src = inspect.getsource(rv._performance_stats)
    assert 'table("shipments")' in src and 'table("orders")' in src
    assert "delivered_at" in src and "deliver_by" in src


def test_on_time_only_counts_shipments_that_had_a_deadline():
    """A shipment with no deadline cannot be late; counting it either way would
    be inventing a statistic."""
    src = inspect.getsource(rv._performance_stats)
    assert "judgeable" in src


# -------------------------------------------------------------- demo cast
def test_demo_cast_is_five_of_each_role():
    for role in ("farmer", "buyer", "transporter"):
        n = sum(1 for u in sd.DEMO_USERS if u["role"] == role)
        assert n == 5, f"expected 5 {role}s, found {n}"


def test_the_original_demo_logins_are_preserved():
    """The landing-page role picker signs into exactly these."""
    for email in ("demo.farmer@udgam.test", "demo.buyer@udgam.test",
                  "demo.transporter@udgam.test"):
        assert any(u["email"] == email for u in sd.DEMO_USERS)


def test_demo_ratings_are_not_all_perfect():
    """A demo where everyone scores five stars demonstrates nothing."""
    stars = [h[6] for h in sd.DEMO_HISTORY] + [h[7] for h in sd.DEMO_HISTORY] \
        + [h[8] for h in sd.DEMO_HISTORY]
    assert min(stars) < 4, "some demo reviews must be genuinely poor"
    assert len(set(stars)) > 1


def test_some_demo_deliveries_are_late_so_on_time_is_a_real_ratio():
    late = [h for h in sd.DEMO_HISTORY if h[9]]
    assert late, "on-time counts need at least one late delivery to be meaningful"
    assert len(late) < len(sd.DEMO_HISTORY)


def test_demo_history_only_references_declared_demo_accounts():
    keys = {u["key"] for u in sd.DEMO_USERS}
    for fk, bk, tk, *_ in sd.DEMO_HISTORY:
        assert fk in keys and bk in keys and tk in keys
        assert fk != bk


def test_demo_reviews_are_labelled_as_demo_data():
    src = inspect.getsource(sd.seed_reputation)
    assert "[DEMO]" in src


def test_seeded_ratings_are_recomputed_never_typed_in():
    src = inspect.getsource(sd.seed_demo_users)
    assert '"avg_rating"' not in src, (
        "profiles must not be seeded with a rating; it comes from feedback")
    assert "recompute_all_ratings" in inspect.getsource(sd.seed_reputation)


def test_demo_history_is_idempotent_by_construction():
    """Re-running the seed must update the same orders, not grow a second history."""
    src = inspect.getsource(sd.seed_reputation)
    assert "UDG-DEMO" in src
    assert 'eq("order_no", order_no)' in src
    assert "DEMO-HIST-" in src, "demo listings need a stable marker too"
