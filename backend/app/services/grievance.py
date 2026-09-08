"""grievance.py -- the accountability layer's rules, with no I/O.

WHY THIS FILE EXISTS SEPARATELY FROM THE ROUTER
-----------------------------------------------
A dispute system is only worth anything if its rules are the same no matter who
is asking. Keeping the vocabulary, the state machine and the authority model
here -- pure, dependency-free -- means they can be tested exhaustively without a
database, and means the router has exactly one place to ask "is this allowed?".

THE AUTHORITY MODEL, AND WHY IT IS SHAPED THIS WAY
--------------------------------------------------
UDGAM has no admin role and no staffed support desk. Rather than invent one and
have a judge discover that "Resolved" was set by nobody, the resolution
authority is placed where it is defensible without staff:

  * the RESPONDENT (the counterparty being complained about) may acknowledge,
    investigate, ask for more information, and PROPOSE an outcome;
  * only the COMPLAINANT may mark a case resolved -- you cannot clear yourself,
    and the person who reported the problem is the only one who can say it went
    away;
  * either side's view of events is preserved: proposing an outcome is recorded
    even if the complainant never accepts it.

That asymmetry is the whole point. `can_act` below is the only place it lives.

NEUTRAL LANGUAGE
----------------
A grievance is an allegation until it is settled. Nothing here contains a word
that assigns blame -- categories describe what the complainant observed
("quantity mismatch"), never who caused it.
"""
from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# vocabulary
#
# Two levels, because a farmer holding a phone in a field will not read twenty
# options. The first screen shows six groups; subcategories appear only once a
# group is chosen.
# ---------------------------------------------------------------------------

CATEGORIES: dict[str, tuple[str, ...]] = {
    "order_payment": (
        "order_not_accepted",
        "payment_not_received",
        "payment_amount_dispute",
        "refund_pending",
        "cancellation",
    ),
    "pickup_delivery": (
        "late_pickup",
        "pickup_not_done",
        "late_delivery",
        "delivery_not_done",
        "wrong_location",
    ),
    "transport": (
        "vehicle_problem",
        "route_problem",
        "tracking_not_updating",
        "transporter_unreachable",
    ),
    "produce_quality": (
        "damaged_produce",
        "quality_mismatch",
        "quantity_mismatch",
    ),
    "account_verification": (
        "verification_pending",
        "account_access",
        "profile_incorrect",
    ),
    "other": (
        "communication",
        "other",
    ),
}

ALL_CATEGORIES: tuple[str, ...] = tuple(CATEGORIES)
ALL_SUBCATEGORIES: tuple[str, ...] = tuple(
    s for subs in CATEGORIES.values() for s in subs
)

# Categories that are about the platform rather than about another person.
# These deliberately have NO respondent: there is nobody to answer them, and
# pretending otherwise would put a stranger on the hook for our own bug.
PLATFORM_ONLY_CATEGORIES: frozenset[str] = frozenset({"account_verification"})


# ---------------------------------------------------------------------------
# lifecycle
# ---------------------------------------------------------------------------

OPEN = "OPEN"
ACKNOWLEDGED = "ACKNOWLEDGED"
UNDER_REVIEW = "UNDER_REVIEW"
ACTION_REQUIRED = "ACTION_REQUIRED"
RESOLVED = "RESOLVED"
REOPENED = "REOPENED"
ESCALATED = "ESCALATED"
CLOSED = "CLOSED"

ALL_STATUSES: tuple[str, ...] = (
    OPEN, ACKNOWLEDGED, UNDER_REVIEW, ACTION_REQUIRED,
    RESOLVED, REOPENED, ESCALATED, CLOSED,
)

# A case in one of these is still live: it appears under "Open cases" and can
# still be acted on.
ACTIVE_STATUSES: frozenset[str] = frozenset(
    {OPEN, ACKNOWLEDGED, UNDER_REVIEW, ACTION_REQUIRED, REOPENED, ESCALATED}
)

# Structured outcomes. A free-text resolution cannot be counted, filtered or
# audited, so the outcome is a code and the explanation rides alongside it.
RESOLUTIONS: tuple[str, ...] = (
    "payment_correction",
    "refund_required",
    "order_correction",
    "delivery_review",
    "transport_review",
    "user_guidance",
    "account_correction",
    "warning",
    "no_action_needed",
    "other",
)


# ---------------------------------------------------------------------------
# who may do what
#
# Actions, not statuses. The API never accepts a status from a client, so
# there is no request that can carry {"status": "RESOLVED"} in the first place
# -- the whole class of bug is absent rather than filtered.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Action:
    """One permitted move: who may make it, from where, to where."""
    name: str
    actors: frozenset[str]        # 'complainant' | 'respondent'
    from_statuses: frozenset[str]
    to_status: str


ACTIONS: dict[str, Action] = {
    a.name: a
    for a in (
        # The respondent engaging with the case.
        Action("acknowledge", frozenset({"respondent"}),
               frozenset({OPEN, REOPENED}), ACKNOWLEDGED),
        Action("start_review", frozenset({"respondent"}),
               frozenset({OPEN, ACKNOWLEDGED, REOPENED}), UNDER_REVIEW),
        Action("request_information", frozenset({"respondent"}),
               frozenset({ACKNOWLEDGED, UNDER_REVIEW, REOPENED}), ACTION_REQUIRED),
        # The respondent PROPOSES an outcome; it does not become RESOLVED.
        # Only the complainant can do that, below.
        Action("propose_resolution", frozenset({"respondent"}),
               frozenset({ACKNOWLEDGED, UNDER_REVIEW, ACTION_REQUIRED, REOPENED}),
               ACTION_REQUIRED),

        # The complainant supplying what was asked for.
        Action("provide_information", frozenset({"complainant"}),
               frozenset({ACTION_REQUIRED}), UNDER_REVIEW),

        # Resolution authority: the person who raised it, and only them.
        Action("resolve", frozenset({"complainant"}),
               frozenset({OPEN, ACKNOWLEDGED, UNDER_REVIEW,
                          ACTION_REQUIRED, REOPENED, ESCALATED}), RESOLVED),
        Action("reopen", frozenset({"complainant"}),
               frozenset({RESOLVED, CLOSED}), REOPENED),
        Action("escalate", frozenset({"complainant"}),
               frozenset({OPEN, ACKNOWLEDGED, UNDER_REVIEW,
                          ACTION_REQUIRED, REOPENED}), ESCALATED),
        Action("close", frozenset({"complainant"}),
               frozenset({RESOLVED}), CLOSED),
    )
}

# Actions that only make sense when somebody is on the other side. A case about
# our own verification queue has no respondent, so nothing here is offered.
RESPONDENT_ACTIONS: frozenset[str] = frozenset(
    name for name, a in ACTIONS.items() if "respondent" in a.actors
)


def party(grievance: dict, user_id: str) -> str | None:
    """Which side of this case the caller is on, if either."""
    if str(grievance.get("created_by")) == str(user_id):
        return "complainant"
    if grievance.get("respondent_id") and str(grievance["respondent_id"]) == str(user_id):
        return "respondent"
    return None


def can_act(grievance: dict, user_id: str, action: str) -> bool:
    """The single authority check. Everything else defers to this."""
    spec = ACTIONS.get(action)
    if spec is None:
        return False
    role = party(grievance, user_id)
    if role is None or role not in spec.actors:
        return False
    return grievance.get("status") in spec.from_statuses


def available_actions(grievance: dict, user_id: str) -> list[str]:
    """What this caller may do right now. Drives the UI; not trusted by it."""
    return [name for name in ACTIONS if can_act(grievance, user_id, name)]


def next_status(action: str) -> str:
    return ACTIONS[action].to_status


# ---------------------------------------------------------------------------
# validation
# ---------------------------------------------------------------------------

MIN_DESCRIPTION = 10
MAX_DESCRIPTION = 2000
MAX_MESSAGE = 2000


def validate_category(category: str, subcategory: str) -> str | None:
    """None when the pair is one we actually collect, else why not."""
    if category not in CATEGORIES:
        return "Choose what kind of problem this is."
    if subcategory not in CATEGORIES[category]:
        return "Choose which of these best describes the problem."
    return None


def validate_description(text: str) -> str | None:
    stripped = (text or "").strip()
    if len(stripped) < MIN_DESCRIPTION:
        return "Please describe what happened in a sentence or two."
    if len(stripped) > MAX_DESCRIPTION:
        return "Please keep the description under 2000 characters."
    return None


# ---------------------------------------------------------------------------
# evidence
# ---------------------------------------------------------------------------

MAX_EVIDENCE_BYTES = 8 * 1024 * 1024
MAX_EVIDENCE_PER_CASE = 6

# Magic bytes, not the Content-Type header. A browser sends whatever it is told
# to send, so sniffing the actual bytes is the only check that means anything.
_SIGNATURES: tuple[tuple[bytes, str, str], ...] = (
    (b"\xff\xd8\xff", "image/jpeg", "jpg"),
    (b"\x89PNG\r\n\x1a\n", "image/png", "png"),
    (b"%PDF-", "application/pdf", "pdf"),
)


def sniff_evidence(data: bytes) -> tuple[str, str] | None:
    """(mime, extension) for a file we accept, or None. WEBP needs its own
    check because the signature is split across two ranges."""
    for magic, mime, ext in _SIGNATURES:
        if data.startswith(magic):
            return mime, ext
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", "webp"
    return None


def validate_evidence(data: bytes) -> str | None:
    if not data:
        return "That file was empty."
    if len(data) > MAX_EVIDENCE_BYTES:
        return "Each file must be under 8 MB."
    if sniff_evidence(data) is None:
        return "Attach a photo (JPG, PNG or WEBP) or a PDF."
    return None


# ---------------------------------------------------------------------------
# summarising a list of cases
# ---------------------------------------------------------------------------

def summarise(cases: list[dict]) -> dict:
    """Counts for the dashboard header. Plain arithmetic over real rows --
    there is no estimate here and nothing is inferred."""
    open_count = sum(1 for c in cases if c.get("status") in ACTIVE_STATUSES)
    resolved = sum(1 for c in cases
                   if c.get("status") in (RESOLVED, CLOSED))
    return {"open": open_count, "resolved": resolved, "total": len(cases)}
