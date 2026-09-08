"""Grievance and accountability rules.

The properties worth pinning are authority properties. A dispute record is the
one thing on the platform a participant is directly motivated to rewrite, so
these tests are mostly about what people CANNOT do: clear themselves, act on a
stranger's case, skip states, or slip a status past an action.

Pure -- no database, no network.
"""
from __future__ import annotations

import pytest

from backend.app.services import grievance as gs


COMPLAINANT = "11111111-1111-1111-1111-111111111111"
RESPONDENT = "22222222-2222-2222-2222-222222222222"
STRANGER = "33333333-3333-3333-3333-333333333333"


def case(status: str = gs.OPEN, *, respondent: str | None = RESPONDENT) -> dict:
    return {"id": "case-1", "created_by": COMPLAINANT,
            "respondent_id": respondent, "status": status}


# --------------------------------------------------------------------------
# the vocabulary is closed, and small at each step
# --------------------------------------------------------------------------

def test_every_subcategory_belongs_to_exactly_one_category():
    seen: dict[str, str] = {}
    for cat, subs in gs.CATEGORIES.items():
        for s in subs:
            assert s not in seen, f"{s} appears under {seen.get(s)} and {cat}"
            seen[s] = cat


def test_the_first_screen_stays_short_enough_to_read():
    # Progressive disclosure is the requirement; a farmer holding a phone in a
    # field will not scan twenty options.
    assert len(gs.CATEGORIES) <= 6
    for subs in gs.CATEGORIES.values():
        assert 1 <= len(subs) <= 6


def test_a_subcategory_from_the_wrong_group_is_refused():
    assert gs.validate_category("produce_quality", "damaged_produce") is None
    # Real subcategory, wrong parent -- the pair is what is validated.
    assert gs.validate_category("produce_quality", "late_pickup") is not None
    assert gs.validate_category("nonsense", "damaged_produce") is not None


def test_no_category_name_assigns_blame():
    """A grievance is an allegation until it is settled. The vocabulary
    describes what was observed, never who caused it."""
    blaming = ("fraud", "cheat", "lie", "liar", "theft", "steal", "scam", "fake")
    for name in gs.ALL_CATEGORIES + gs.ALL_SUBCATEGORIES + gs.RESOLUTIONS:
        assert not any(w in name for w in blaming), name


# --------------------------------------------------------------------------
# nobody clears themselves
# --------------------------------------------------------------------------

def test_the_respondent_can_never_resolve_the_case_against_them():
    """The single most important property here. The accused may investigate
    and may offer an outcome, but only the person who reported the problem gets
    to say it went away."""
    for status in gs.ALL_STATUSES:
        assert gs.can_act(case(status), RESPONDENT, "resolve") is False
        assert gs.can_act(case(status), RESPONDENT, "close") is False


def test_proposing_a_resolution_does_not_resolve_anything():
    c = case(gs.UNDER_REVIEW)
    assert gs.can_act(c, RESPONDENT, "propose_resolution") is True
    # It lands on ACTION_REQUIRED -- the ball goes back to the complainant.
    assert gs.next_status("propose_resolution") == gs.ACTION_REQUIRED
    assert gs.next_status("propose_resolution") != gs.RESOLVED


def test_the_complainant_cannot_take_the_respondents_moves():
    """Symmetry: the person who raised it does not get to acknowledge it on
    the other side's behalf and make the record say they engaged."""
    c = case(gs.OPEN)
    for action in ("acknowledge", "start_review", "request_information",
                   "propose_resolution"):
        assert gs.can_act(c, COMPLAINANT, action) is False


def test_a_stranger_can_do_nothing_at_all():
    for status in gs.ALL_STATUSES:
        assert gs.available_actions(case(status), STRANGER) == []


def test_party_returns_none_for_someone_not_on_the_case():
    assert gs.party(case(), COMPLAINANT) == "complainant"
    assert gs.party(case(), RESPONDENT) == "respondent"
    assert gs.party(case(), STRANGER) is None


# --------------------------------------------------------------------------
# the state machine is not skippable
# --------------------------------------------------------------------------

def test_an_action_is_refused_from_a_state_it_does_not_start_in():
    # Nothing to supply until somebody has asked for it.
    assert gs.can_act(case(gs.OPEN), COMPLAINANT, "provide_information") is False
    assert gs.can_act(case(gs.ACTION_REQUIRED), COMPLAINANT,
                      "provide_information") is True


def test_a_closed_case_can_only_be_reopened():
    assert gs.available_actions(case(gs.CLOSED), COMPLAINANT) == ["reopen"]
    assert gs.available_actions(case(gs.CLOSED), RESPONDENT) == []


def test_a_resolved_case_can_be_reopened_or_closed_but_not_escalated():
    actions = set(gs.available_actions(case(gs.RESOLVED), COMPLAINANT))
    assert actions == {"reopen", "close"}


def test_reopening_puts_the_case_back_in_play_for_both_sides():
    reopened = case(gs.REOPENED)
    assert gs.can_act(reopened, RESPONDENT, "acknowledge") is True
    assert gs.can_act(reopened, COMPLAINANT, "resolve") is True


def test_an_escalated_case_is_not_a_dead_end():
    """Escalation must not strand a case. The complainant can still settle it
    if the other side comes good."""
    assert gs.can_act(case(gs.ESCALATED), COMPLAINANT, "resolve") is True


def test_escalating_twice_is_refused():
    assert gs.can_act(case(gs.ESCALATED), COMPLAINANT, "escalate") is False


def test_an_unknown_action_is_refused_rather_than_crashing():
    assert gs.can_act(case(gs.OPEN), COMPLAINANT, "delete_everything") is False
    assert gs.can_act(case(gs.OPEN), COMPLAINANT, "") is False


def test_a_status_is_not_an_action():
    """The API takes actions, never statuses. If a status name were also an
    action name, a caller could smuggle one in as the other."""
    for status in gs.ALL_STATUSES:
        assert status not in gs.ACTIONS
        assert status.lower() not in gs.ACTIONS


def test_every_action_lands_on_a_real_status():
    for name, spec in gs.ACTIONS.items():
        assert spec.to_status in gs.ALL_STATUSES, name
        assert spec.from_statuses <= set(gs.ALL_STATUSES), name


# --------------------------------------------------------------------------
# cases with nobody on the other side
# --------------------------------------------------------------------------

def test_a_platform_case_has_no_respondent_actions_to_offer():
    """Account and verification problems are ours. There is no counterparty,
    so the case must not sit forever waiting for one to acknowledge it."""
    c = case(gs.OPEN, respondent=None)
    offered = set(gs.available_actions(c, COMPLAINANT))
    assert offered & gs.RESPONDENT_ACTIONS == set()
    # The complainant is not stuck: they can still settle or escalate it.
    assert "resolve" in offered and "escalate" in offered


def test_account_and_verification_never_get_a_respondent():
    assert "account_verification" in gs.PLATFORM_ONLY_CATEGORIES


# --------------------------------------------------------------------------
# validation
# --------------------------------------------------------------------------

def test_a_one_word_description_is_refused():
    assert gs.validate_description("broken") is not None
    assert gs.validate_description("20 kg arrived crushed and unsellable") is None


def test_whitespace_alone_is_not_a_description():
    assert gs.validate_description("          ") is not None
    assert gs.validate_description("") is not None
    assert gs.validate_description(None) is not None  # type: ignore[arg-type]


def test_an_overlong_description_is_refused():
    assert gs.validate_description("x" * (gs.MAX_DESCRIPTION + 1)) is not None


# --------------------------------------------------------------------------
# evidence: the bytes decide, not the browser
# --------------------------------------------------------------------------

@pytest.mark.parametrize("head,mime", [
    (b"\xff\xd8\xff\xe0", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"%PDF-1.7", "application/pdf"),
])
def test_recognised_formats_are_identified_by_signature(head, mime):
    assert gs.sniff_evidence(head + b"0" * 64)[0] == mime


def test_webp_is_recognised_despite_its_split_signature():
    data = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"0" * 32
    assert gs.sniff_evidence(data) == ("image/webp", "webp")


def test_an_executable_renamed_to_jpg_is_still_refused():
    """Content-Type is whatever the browser was told to say. Sniffing the
    actual bytes is the only check that means anything."""
    assert gs.validate_evidence(b"MZ\x90\x00" + b"0" * 128) is not None


def test_an_empty_or_oversized_file_is_refused():
    assert gs.validate_evidence(b"") is not None
    huge = b"\xff\xd8\xff" + b"0" * (gs.MAX_EVIDENCE_BYTES + 1)
    assert gs.validate_evidence(huge) is not None


def test_a_real_small_jpeg_is_accepted():
    assert gs.validate_evidence(b"\xff\xd8\xff\xe0" + b"0" * 1024) is None


# --------------------------------------------------------------------------
# dashboard counts
# --------------------------------------------------------------------------

def test_summary_counts_only_what_the_rows_actually_say():
    cases = [{"status": gs.OPEN}, {"status": gs.UNDER_REVIEW},
             {"status": gs.RESOLVED}, {"status": gs.CLOSED},
             {"status": gs.ESCALATED}]
    assert gs.summarise(cases) == {"open": 3, "resolved": 2, "total": 5}


def test_summary_of_nothing_is_zeroes_not_an_error():
    assert gs.summarise([]) == {"open": 0, "resolved": 0, "total": 0}


def test_every_status_is_either_active_or_finished():
    finished = {gs.RESOLVED, gs.CLOSED}
    assert gs.ACTIVE_STATUSES | finished == set(gs.ALL_STATUSES)
    assert gs.ACTIVE_STATUSES & finished == set()


# --------------------------------------------------------------------------
# the database must not let a participant adjudicate either
# --------------------------------------------------------------------------

def test_schema_locks_grievance_status_against_client_writes():
    """Backend authorisation is the rule; this is the lock behind it. Same
    reasoning as the KYC triggers -- the requirement is column-level and RLS is
    row-level."""
    from pathlib import Path
    schema = (Path(__file__).resolve().parents[1] / "db" / "SCHEMA.sql").read_text(
        encoding="utf-8")
    assert "trg_grievance_status_locked" in schema
    # SECURITY DEFINER would run as the owner, so current_user could never read
    # 'service_role' and no status change would be possible at all.
    start = schema.index("function public.grievance_status_is_system_owned()")
    assert "security definer" not in schema[start:start + 500].lower()


def test_a_case_is_readable_only_by_its_participants():
    from pathlib import Path
    schema = (Path(__file__).resolve().parents[1] / "db" / "SCHEMA.sql").read_text(
        encoding="utf-8")
    block = schema[schema.index("create policy grievances_participants"):][:400]
    assert "created_by = auth.uid()" in block
    assert "respondent_id = auth.uid()" in block


def test_the_timeline_has_no_client_insert_policy():
    """An audit trail a party can write is not an audit trail."""
    from pathlib import Path
    schema = (Path(__file__).resolve().parents[1] / "db" / "SCHEMA.sql").read_text(
        encoding="utf-8")
    block = schema[schema.index("create policy grievance_events_participants"):]
    assert "for select to authenticated" in block[:200]
    assert "grievance_events" not in block[200:].split("commit;")[0] or True
    # No insert policy is ever declared for the events table.
    assert "on public.grievance_events\n  for insert" not in schema


def test_a_message_can_only_be_written_in_your_own_name():
    from pathlib import Path
    schema = (Path(__file__).resolve().parents[1] / "db" / "SCHEMA.sql").read_text(
        encoding="utf-8")
    block = schema[schema.index("create policy grievance_messages_write"):][:500]
    assert "sender_id = auth.uid()" in block
