"""Order state machine (PRD §8).

Enforces the transition graph from the order_status enum. Every transition is
recorded in order_status_history (append-only audit log). The actor's role is
checked — a transporter cannot accept an order, only a farmer can.

DRAFT → PLACED → ACCEPTED → PAYMENT_HELD → LOGISTICS_ASSIGNED
  → PICKED_UP → IN_TRANSIT → DELIVERED → CLOSED

Cancel/dispute branches:
  any pre-DELIVERED → CANCELLED
  DELIVERED → DISPUTED (buyer only)
"""
from __future__ import annotations

from ..errors import InvalidStateTransition, Forbidden

# Allowed transitions: {from_status: {to_status: [allowed_roles]}}
TRANSITIONS: dict[str, dict[str, list[str]]] = {
    "DRAFT":              {"PLACED": ["buyer", "farmer"], "CANCELLED": ["buyer", "farmer"]},
    "PLACED":             {"ACCEPTED": ["farmer"], "CANCELLED": ["buyer", "farmer"]},
    "ACCEPTED":           {"PAYMENT_HELD": ["buyer"], "CANCELLED": ["buyer", "farmer"]},
    # A transporter reaches LOGISTICS_ASSIGNED by ACCEPTING an offer, so they
    # are a legitimate actor for this one transition. They cannot start it:
    # only the buyer or farmer named by orders.logistics_arranged_by can send
    # the offer that makes accepting possible, and the accept endpoint checks
    # the offer was addressed to this transporter. Without them here, nobody
    # could take a job -- the party who arranges transport is not the party
    # who agrees to carry it.
    "PAYMENT_HELD":       {"LOGISTICS_ASSIGNED": ["buyer", "farmer", "transporter"],
                            "CANCELLED": ["buyer"]},
    "LOGISTICS_ASSIGNED": {"PICKED_UP": ["transporter"], "CANCELLED": ["buyer", "farmer"]},
    "PICKED_UP":          {"IN_TRANSIT": ["transporter"], "CANCELLED": ["buyer", "farmer"]},
    "IN_TRANSIT":         {"DELIVERED": ["transporter"]},
    "DELIVERED":          {"CLOSED": ["buyer", "farmer"], "DISPUTED": ["buyer"]},
    "CLOSED":             {},
    "CANCELLED":          {},
    "DISPUTED":           {"CLOSED": ["buyer", "farmer"]},
}


def validate_transition(from_status: str, to_status: str, actor_role: str) -> None:
    """Raise if the transition is not valid for the given actor role."""
    allowed = TRANSITIONS.get(from_status, {})
    if to_status not in allowed:
        raise InvalidStateTransition(
            f"Cannot move from {from_status} to {to_status}."
        )
    if actor_role not in allowed[to_status]:
        raise Forbidden(
            f"A {actor_role} cannot move an order from {from_status} to {to_status}."
        )


def record_transition(db, order_id: str, from_status: str, to_status: str,
                       actor_id: str, actor_role: str, note: str | None = None) -> None:
    """Append to order_status_history (audit log)."""
    db.table("order_status_history").insert({
        "order_id": order_id,
        "from_status": from_status,
        "to_status": to_status,
        "actor_id": actor_id,
        "actor_role": actor_role,
        "note": note,
    }).execute()
