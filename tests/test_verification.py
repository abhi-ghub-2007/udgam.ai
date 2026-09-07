"""Identity and credential verification.

The properties worth pinning here are security properties: a user must not be
able to award themselves a status, format validation must never be mistaken
for identity verification, and a raw credential must never survive the request
that carried it.

Pure -- no database, no network.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from backend.app.services import verification as vs


# --------------------------------------------------------------------------
# format validation is real, and is only format validation
# --------------------------------------------------------------------------

@pytest.mark.parametrize("value,ok", [
    ("ABCDE1234F", True),
    ("abcde1234f", True),      # normalised before checking
    ("ABCD1234F", False),      # too few letters
    ("ABCDE12345", False),     # last character must be a letter
    ("", False),
])
def test_pan_format(value, ok):
    assert vs.validate_format("pan", value).valid is ok


def test_aadhaar_requires_a_valid_verhoeff_check_digit():
    # A 12-digit string is not enough: the last digit is a checksum, so a
    # typo is caught locally without contacting anybody.
    assert vs.validate_format("aadhaar_last4", "999999990019").valid is True
    assert vs.validate_format("aadhaar_last4", "123456789012").valid is False
    assert vs.validate_format("aadhaar_last4", "99999999001").valid is False


def test_gstin_requires_a_valid_mod36_check_character():
    assert vs.validate_format("gstin", "27AAPFU0939F1ZV").valid is True
    assert vs.validate_format("gstin", "27AAPFU0939F1ZZ").valid is False


def test_farmer_identifiers_are_not_pinned_to_one_length():
    """State farmer IDs differ and AgriStack is still rolling out. Forcing a
    single length would reject legitimate holders."""
    for value in ("MH2024001", "MH20240012345", "UP1234567890123456"):
        assert vs.validate_format("farmer_id", value).valid is True


def test_passing_format_validation_is_not_verification():
    # The whole point: a well-formed PAN is a well-formed string.
    assert vs.validate_format("pan", "ABCDE1234F").valid is True
    assert vs.verify("pan", "ABCDE1234F", mode="manual").status == vs.STATUS_PENDING


# --------------------------------------------------------------------------
# masking and data minimisation
# --------------------------------------------------------------------------

def test_masks_never_contain_the_full_value():
    for doc_type, value in [("pan", "ABCDE1234F"),
                            ("aadhaar_last4", "999999990019"),
                            ("gstin", "27AAPFU0939F1ZV"),
                            ("driving_licence", "MH1220110012345")]:
        masked = vs.mask(doc_type, value)
        assert value not in masked
        assert masked != value


def test_aadhaar_mask_keeps_only_the_last_four_digits():
    assert vs.mask("aadhaar_last4", "999999990019") == "XXXX XXXX 0019"


def test_normalisation_does_not_change_an_identifier():
    # Case and separators are formatting; the identifier underneath is the same.
    assert vs.normalise("pan", " abcde-1234f ") == "ABCDE1234F"
    assert vs.normalise("aadhaar_last4", "9999 9999 0019") == "999999990019"


# --------------------------------------------------------------------------
# no fabricated government verification
# --------------------------------------------------------------------------

def test_no_credential_claims_an_authority_this_deployment_lacks():
    # There is no authorised integration configured for anything.
    for doc_type in vs.ALL_TYPES:
        assert vs.authority_available(doc_type) is False


def test_manual_mode_returns_pending_and_names_no_provider():
    out = vs.verify("gstin", "27AAPFU0939F1ZV", mode="manual")
    assert out.status == vs.STATUS_PENDING
    assert out.provider is None
    assert "not available" in (out.message or "")


def test_demo_mode_is_labelled_and_never_claims_a_government_source():
    out = vs.verify("pan", "ABCDE1234F", mode="demo")
    assert out.provider == vs.DEMO_PROVIDER
    blob = f"{out.provider} {out.message}".lower()
    for forbidden in ("government", "uidai", "income tax", "gstn", "official"):
        assert forbidden not in blob


def test_demo_mode_refuses_to_run_in_production(monkeypatch):
    monkeypatch.setenv("UDGAM_VERIFICATION_MODE", "demo")
    monkeypatch.setenv("APP_ENV", "production")
    # A simulator must never decide a production identity.
    assert vs.verification_mode() == "manual"


def test_unknown_mode_falls_back_to_manual(monkeypatch):
    monkeypatch.setenv("UDGAM_VERIFICATION_MODE", "whatever")
    monkeypatch.delenv("APP_ENV", raising=False)
    assert vs.verification_mode() == "manual"


# --------------------------------------------------------------------------
# the universal identity requirement
# --------------------------------------------------------------------------

def test_identity_verified_needs_a_verified_credential_not_a_submitted_one():
    submitted = [{"doc_type": "pan", "status": vs.STATUS_PENDING}]
    assert vs.identity_verified(submitted) is False
    verified = [{"doc_type": "pan", "status": vs.STATUS_VERIFIED}]
    assert vs.identity_verified(verified) is True


def test_a_verified_role_credential_is_not_identity_verification():
    # A verified GSTIN says a business exists, not who this account holder is.
    creds = [{"doc_type": "gstin", "status": vs.STATUS_VERIFIED}]
    assert vs.identity_verified(creds) is False


def test_either_pan_or_aadhaar_satisfies_identity():
    for doc_type in ("pan", "aadhaar_last4"):
        assert vs.identity_verified(
            [{"doc_type": doc_type, "status": vs.STATUS_VERIFIED}]) is True


# --------------------------------------------------------------------------
# role scoping
# --------------------------------------------------------------------------

def test_each_role_is_asked_only_for_its_own_credentials():
    farmer = vs.relevant_types("farmer")
    buyer = vs.relevant_types("buyer")
    transporter = vs.relevant_types("transporter")

    assert "pm_kisan" in farmer and "gstin" not in farmer
    assert "gstin" in buyer and "transport_permit" not in buyer
    assert "transport_permit" in transporter and "pm_kisan" not in transporter
    # Identity is asked of everyone.
    for role in (farmer, buyer, transporter):
        assert "pan" in role and "aadhaar_last4" in role


def test_role_change_does_not_carry_role_credentials_across():
    """Identity survives a role change; role credentials do not apply."""
    creds = [{"doc_type": "pan", "status": vs.STATUS_VERIFIED},
             {"doc_type": "pm_kisan", "status": vs.STATUS_VERIFIED}]
    as_buyer = vs.progress("buyer", creds)
    # Identity still holds...
    assert as_buyer["identity_verified"] is True
    # ...but a farmer credential counts for nothing against a buyer's list.
    assert as_buyer["role_credentials_verified"] == 0
    assert as_buyer["role_credentials_total"] == len(vs.ROLE_CREDENTIALS["buyer"])


# --------------------------------------------------------------------------
# expiry
# --------------------------------------------------------------------------

def test_expired_credentials_are_graded_expired():
    today = date(2026, 9, 7)
    past = datetime(2026, 8, 1, tzinfo=timezone.utc)
    assert vs.grade_expiry(past, today=today) == "expired"


def test_credentials_expiring_within_a_month_are_flagged():
    today = date(2026, 9, 7)
    soon = datetime(2026, 9, 20, tzinfo=timezone.utc)
    assert vs.grade_expiry(soon, today=today) == "expiring_soon"


def test_a_credential_with_no_expiry_is_not_graded():
    assert vs.grade_expiry(None) is None


def test_iso_string_expiry_is_accepted():
    assert vs.grade_expiry("2026-08-01", today=date(2026, 9, 7)) == "expired"


# --------------------------------------------------------------------------
# progress reporting: counts, not a trust score
# --------------------------------------------------------------------------

def test_progress_reports_counts_and_never_a_percentage_score():
    creds = [{"doc_type": "pan", "status": vs.STATUS_VERIFIED},
             {"doc_type": "pm_kisan", "status": vs.STATUS_PENDING}]
    p = vs.progress("farmer", creds)
    assert p["identity_verified"] is True
    assert p["role_credentials_submitted"] == 1
    assert p["role_credentials_verified"] == 0     # pending is not verified
    assert not any("score" in k for k in p)


def test_account_status_maps_onto_the_existing_enum():
    assert vs.account_status([]) == "self_declared"
    assert vs.account_status(
        [{"doc_type": "pan", "status": vs.STATUS_PENDING}]) == "document_submitted"
    assert vs.account_status(
        [{"doc_type": "pan", "status": vs.STATUS_VERIFIED}]) == "verified"


# --------------------------------------------------------------------------
# the database must not let a user decide their own status
# --------------------------------------------------------------------------

def test_schema_locks_self_verification_with_triggers():
    """RLS is row-level and this requirement is column-level, so triggers are
    what stop a user PATCHing their own status through PostgREST. Verified
    live: before these existed, a demo buyer self-elevated and got HTTP 200."""
    from pathlib import Path
    schema = (Path(__file__).resolve().parents[1] / "db" / "SCHEMA.sql").read_text(
        encoding="utf-8")
    assert "trg_kyc_no_self_verify" in schema
    assert "trg_profile_verification_locked" in schema
    # SECURITY DEFINER would run as the owner, making the service-role
    # exemption unmatchable and verification ungrantable by anyone.
    for fn in ("kyc_user_cannot_self_verify", "profile_verification_is_system_owned"):
        start = schema.index(f"function public.{fn}()")
        body = schema[start:start + 400]
        assert "security definer" not in body.lower()


def test_verification_events_have_no_client_insert_policy():
    """The audit trail is written by the system. A client that could write to
    it could forge its own history."""
    from pathlib import Path
    schema = (Path(__file__).resolve().parents[1] / "db" / "SCHEMA.sql").read_text(
        encoding="utf-8")
    block = schema[schema.index("verification_events_own"):]
    assert "for select to authenticated" in block
    assert "for insert" not in block[:300]
