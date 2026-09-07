"""Identity and credential verification.

TWO LEVELS, NEVER CONFLATED
---------------------------
Level 1  FORMAT VALIDATION -- structure, allowed characters, and a real
         checksum where the identifier carries one (Aadhaar's Verhoeff digit,
         GSTIN's mod-36 digit). Cheap, local, and proves nothing about whether
         the holder exists.
Level 2  AUTHENTICITY -- confirming the credential against the authority that
         issued it. Requires an authorised integration.

A credential that passes Level 1 is `pending`, never `verified`. That is the
whole point: a valid-looking PAN is a valid-looking string.

WHAT IS ACTUALLY AVAILABLE, RESEARCHED NOT ASSUMED
--------------------------------------------------
No verification provider credentials exist in this deployment (checked
config.py and the environment: there is no NSDL/Protean, GSP, Sarathi or
DigiLocker key of any kind). And these are not APIs a project can simply sign
up for:

  Aadhaar   UIDAI authentication and e-KYC are restricted to licensed AUA/KUA
            entities under the Aadhaar Act 2016, and since the 2019 amendment
            private entities may authenticate only where permitted by law.
            Not available to this platform, and that is a legal boundary
            rather than a missing API key.
  PAN       Verification runs through Protean/NSDL or the Income Tax
            department under a commercial agreement for authorised entities.
  GSTIN     Taxpayer APIs are served through authorised GST Suvidha Providers.
            The public search portal exists but scraping it would breach its
            terms.
  PM-KISAN
  Farmer ID No public verification API. AgriStack's farmer registry is still
            rolling out, and state farmer identifiers are not one identifier
            with one format -- so this module does NOT enforce a single length
            on them.
  Licence
  Permit    Sarathi/Parivahan and DigiLocker expose issued-document APIs to
            registered partners only.

So every credential here resolves to `pending` (awaiting manual review) or
`unavailable` (no mechanism exists to check it automatically). Nothing is ever
auto-verified, and nothing claims a government source it does not have.

DEMO MODE
---------
UDGAM_VERIFICATION_MODE=demo turns on a clearly-labelled simulator for
demonstrations. It stamps provider='DEMO_SIMULATOR' on every decision so a
simulated result is distinguishable in the database, the API and the UI, and
it refuses to run when APP_ENV is production.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone

# --- credential types ------------------------------------------------------

IDENTITY_TYPES = ("pan", "aadhaar_last4")

ROLE_CREDENTIALS: dict[str, tuple[str, ...]] = {
    "farmer": ("pm_kisan", "farmer_id", "crop_insurance", "land_record"),
    "buyer": ("gstin",),
    "transporter": ("driving_licence", "vehicle_rc", "transport_permit"),
}

ALL_TYPES = IDENTITY_TYPES + tuple(
    t for types in ROLE_CREDENTIALS.values() for t in types)

# Credentials that can lapse. Showing an expired permit as verified would be
# worse than showing nothing, so these carry an expiry the UI grades.
EXPIRING_TYPES = ("transport_permit", "driving_licence", "crop_insurance")

STATUS_PENDING = "pending"
STATUS_VERIFIED = "verified"
STATUS_REJECTED = "rejected"
STATUS_EXPIRED = "expired"
STATUS_UNAVAILABLE = "unavailable"

DEMO_PROVIDER = "DEMO_SIMULATOR"


def verification_mode() -> str:
    """'manual' unless a demo is explicitly switched on outside production."""
    mode = (os.getenv("UDGAM_VERIFICATION_MODE") or "manual").strip().lower()
    if mode == "demo" and (os.getenv("APP_ENV") or "").lower() == "production":
        # Fail safe: a demo simulator must never decide a production identity.
        return "manual"
    return mode if mode in ("manual", "demo") else "manual"


# --- Level 1: format validation -------------------------------------------

_PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
_AADHAAR_RE = re.compile(r"^[0-9]{12}$")
_GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z]$")
_PM_KISAN_RE = re.compile(r"^[A-Z0-9]{6,20}$")
_FARMER_ID_RE = re.compile(r"^[A-Z0-9]{6,20}$")
_DL_RE = re.compile(r"^[A-Z]{2}[0-9]{2}[0-9A-Z]{9,13}$")
_RC_RE = re.compile(r"^[A-Z]{2}[0-9]{1,2}[A-Z]{0,3}[0-9]{1,4}$")

# Verhoeff tables -- Aadhaar's 12th digit is a Verhoeff check digit, so a
# typo'd Aadhaar can be caught locally without contacting anyone.
_VERHOEFF_D = (
    (0,1,2,3,4,5,6,7,8,9), (1,2,3,4,0,6,7,8,9,5), (2,3,4,0,1,7,8,9,5,6),
    (3,4,0,1,2,8,9,5,6,7), (4,0,1,2,3,9,5,6,7,8), (5,9,8,7,6,0,4,3,2,1),
    (6,5,9,8,7,1,0,4,3,2), (7,6,5,9,8,2,1,0,4,3), (8,7,6,5,9,3,2,1,0,4),
    (9,8,7,6,5,4,3,2,1,0))
_VERHOEFF_P = (
    (0,1,2,3,4,5,6,7,8,9), (1,5,7,6,2,8,3,0,9,4), (5,8,0,3,7,9,6,1,4,2),
    (8,9,1,6,0,4,3,5,2,7), (9,4,5,3,1,2,6,8,7,0), (4,2,8,6,5,7,3,9,0,1),
    (2,7,9,3,8,0,6,4,1,5), (7,0,4,6,9,1,3,2,5,8))


def verhoeff_ok(digits: str) -> bool:
    """True when the trailing Verhoeff check digit is consistent."""
    if not digits.isdigit():
        return False
    c = 0
    for i, ch in enumerate(reversed(digits)):
        c = _VERHOEFF_D[c][_VERHOEFF_P[i % 8][int(ch)]]
    return c == 0


_GSTIN_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def gstin_checksum_ok(gstin: str) -> bool:
    """GSTIN's 15th character is a mod-36 check character."""
    if len(gstin) != 15:
        return False
    total = 0
    for i, ch in enumerate(gstin[:14]):
        if ch not in _GSTIN_ALPHABET:
            return False
        value = _GSTIN_ALPHABET.index(ch) * (2 if i % 2 else 1)
        total += value // 36 + value % 36
    return _GSTIN_ALPHABET[(36 - total % 36) % 36] == gstin[14]


def normalise(doc_type: str, raw: str) -> str:
    """Canonical form. Trims and upper-cases; never changes meaning.

    Separators are stripped only from identifiers where they are pure
    formatting (Aadhaar is often written in groups of four). Nothing here
    rewrites an identifier into a different one.
    """
    value = (raw or "").strip().upper()
    value = re.sub(r"\s+", "", value)
    if doc_type in ("aadhaar_last4", "pan", "gstin", "driving_licence",
                    "vehicle_rc", "pm_kisan", "farmer_id"):
        value = value.replace("-", "").replace("/", "")
    return value


@dataclass
class FormatResult:
    valid: bool
    message: str | None = None


def validate_format(doc_type: str, value: str) -> FormatResult:
    """Level 1 only. A True here means 'well-formed', NOT 'genuine'."""
    v = normalise(doc_type, value)
    if not v:
        return FormatResult(False, "This field cannot be empty.")

    if doc_type == "pan":
        if not _PAN_RE.match(v):
            return FormatResult(False, "A PAN looks like ABCDE1234F.")
        return FormatResult(True)

    if doc_type == "aadhaar_last4":
        if not _AADHAAR_RE.match(v):
            return FormatResult(False, "An Aadhaar number has 12 digits.")
        if not verhoeff_ok(v):
            return FormatResult(False, "That Aadhaar number does not look right. Please re-check it.")
        return FormatResult(True)

    if doc_type == "gstin":
        if not _GSTIN_RE.match(v):
            return FormatResult(False, "A GSTIN has 15 characters, like 27ABCDE1234F1Z5.")
        if not gstin_checksum_ok(v):
            return FormatResult(False, "That GSTIN does not look right. Please re-check it.")
        return FormatResult(True)

    if doc_type == "driving_licence":
        if not _DL_RE.match(v):
            return FormatResult(False, "A licence number looks like MH12 20110012345.")
        return FormatResult(True)

    if doc_type == "vehicle_rc":
        if not _RC_RE.match(v):
            return FormatResult(False, "A registration number looks like MH12AB1234.")
        return FormatResult(True)

    if doc_type in ("pm_kisan", "farmer_id"):
        # Deliberately NOT pinned to one length. Farmer identifiers differ by
        # state and AgriStack's registry is still rolling out, so inventing a
        # single format would reject legitimate holders.
        if not _PM_KISAN_RE.match(v):
            return FormatResult(False, "Enter the identifier exactly as printed on your record.")
        return FormatResult(True)

    if doc_type in ("crop_insurance", "transport_permit", "land_record"):
        if len(v) < 4:
            return FormatResult(False, "Enter the number exactly as printed on your document.")
        return FormatResult(True)

    return FormatResult(False, "Unsupported credential type.")


# --- masking ---------------------------------------------------------------

def mask(doc_type: str, value: str) -> str:
    """The ONLY form stored or returned. Raw values are never persisted.

    Aadhaar keeps its last four digits, the form UIDAI itself uses publicly.
    Everything else keeps a short tail so the holder can recognise their own
    entry without the value being reusable by anyone who sees it.
    """
    v = normalise(doc_type, value)
    if doc_type == "aadhaar_last4":
        return f"XXXX XXXX {v[-4:]}"
    if doc_type == "pan":
        return f"XXXXX{v[-5:]}" if len(v) >= 5 else "XXXXX"
    if doc_type == "gstin":
        return f"{v[:2]}XXXXXXXXXX{v[-3:]}" if len(v) >= 15 else "XXXXX"
    if len(v) <= 4:
        return "X" * len(v)
    return "X" * (len(v) - 4) + v[-4:]


# --- Level 2: authenticity -------------------------------------------------

@dataclass
class VerificationOutcome:
    status: str
    provider: str | None = None
    reference: str | None = None
    expires_at: datetime | None = None
    message: str | None = None


def authority_available(doc_type: str) -> bool:
    """Is there an authorised mechanism this deployment can actually call?

    False for everything today, and honestly so -- see the module docstring.
    When a real integration is added this is the one function that changes.
    """
    return False


def verify(doc_type: str, value: str, *, mode: str | None = None) -> VerificationOutcome:
    """Level 2. Returns a status the backend then writes; never 'verified'
    unless something authoritative actually said so.
    """
    mode = mode or verification_mode()

    if mode == "demo":
        # A simulator, and it says so. Deterministic on the value so a demo
        # repeats identically, and stamped with a provider name no one could
        # mistake for a government source.
        digitsum = sum(ord(c) for c in normalise(doc_type, value))
        if digitsum % 10 == 7:
            return VerificationOutcome(
                STATUS_REJECTED, DEMO_PROVIDER,
                message="Simulated rejection (demonstration only).")
        return VerificationOutcome(
            STATUS_VERIFIED, DEMO_PROVIDER,
            reference=f"demo-{digitsum:06d}",
            message="Verified by the demonstration simulator, not by an authority.")

    if not authority_available(doc_type):
        # No authorised integration exists. The credential is on file and
        # awaiting review -- it is not verified, and the API says which.
        return VerificationOutcome(
            STATUS_PENDING, None,
            message="Submitted. Awaiting manual review -- automated verification "
                    "is not available for this credential.")

    raise NotImplementedError(
        "authority_available() reported a provider that verify() cannot call")


def grade_expiry(expires_at, *, today: date | None = None) -> str | None:
    """'valid' | 'expiring_soon' | 'expired'. None when nothing expires."""
    if not expires_at:
        return None
    today = today or date.today()
    if isinstance(expires_at, datetime):
        expiry = expires_at.date()
    elif isinstance(expires_at, str):
        try:
            expiry = date.fromisoformat(expires_at[:10])
        except ValueError:
            return None
    else:
        expiry = expires_at
    days = (expiry - today).days
    if days < 0:
        return "expired"
    if days <= 30:
        return "expiring_soon"
    return "valid"


def identity_verified(credentials: list[dict]) -> bool:
    """The universal requirement: at least one VERIFIED PAN or Aadhaar.

    Deliberately reads `status`, not presence. Submitting a PAN is not being
    identity-verified, which is the distinction this whole module exists for.
    """
    return any(c.get("doc_type") in IDENTITY_TYPES
               and c.get("status") == STATUS_VERIFIED
               for c in credentials)


def relevant_types(role: str) -> tuple[str, ...]:
    """Which credentials a role is actually asked for. A buyer is never shown
    a permit field, and a transporter is never shown PM-KISAN."""
    return IDENTITY_TYPES + ROLE_CREDENTIALS.get((role or "").lower(), ())


def progress(role: str, credentials: list[dict]) -> dict:
    """Verification progress -- counts, never an invented trust score.

    Identity and role credentials are reported separately because they are
    different claims: one is "we know who this is", the other is "this person
    holds that credential".
    """
    by_type = {c["doc_type"]: c for c in credentials}
    role_types = ROLE_CREDENTIALS.get((role or "").lower(), ())

    verified_role = sum(
        1 for t in role_types
        if by_type.get(t, {}).get("status") == STATUS_VERIFIED)
    submitted_role = sum(1 for t in role_types if t in by_type)

    return {
        "identity_verified": identity_verified(credentials),
        "identity_submitted": any(t in by_type for t in IDENTITY_TYPES),
        "role_credentials_total": len(role_types),
        "role_credentials_submitted": submitted_role,
        "role_credentials_verified": verified_role,
        "credentials_verified_total": sum(
            1 for c in credentials if c.get("status") == STATUS_VERIFIED),
    }


def account_status(credentials: list[dict]) -> str:
    """Maps to the existing profiles.verification_status enum.

    Kept to the three values already in the schema so nothing that reads that
    column has to change.
    """
    if identity_verified(credentials):
        return "verified"
    if credentials:
        return "document_submitted"
    return "self_declared"
