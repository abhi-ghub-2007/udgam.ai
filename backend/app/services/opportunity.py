"""The shared Opportunity contract (SIH26132).

One representation of "a way for this farmer to sell this lot", used by the Net
Exit Optimizer (Phase 2) and, unchanged, by the Risk-Adjusted Sale Window,
Dynamic Supply Aggregation and Emergency Exit Engine that follow. Those engines
rank and filter Opportunities; they must never recompute the economics
themselves, or the four engines will drift apart and disagree on screen.

WHO BEARS WHICH COST
--------------------
The single most important thing this module encodes. services/pricing.py already
settles it for a platform sale: `farmer_payout = subtotal`, with the buyer paying
the 2% platform fee and the transport on top. A mandi sale is the opposite — the
farmer trucks the lot there and the commission agent takes a cut off the top.

So a cost line is not just an amount, it is an amount *and who pays it*, and only
the farmer's share is subtracted from farmer net realization. This is precisely
why the highest headline price is often not the best exit, which is the whole
point of the optimizer.

HONESTY
-------
Deterministic arithmetic over declared inputs: ALGORITHMIC, never REAL. Where an
input is missing we say so — `limitations` and `cost_basis_complete` exist so the
optimizer can decline to guess rather than fabricate a number to fill a column.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

METHOD = "ALGORITHMIC"

# Channels a lot can leave the farm through. Extended by later phases rather
# than replaced — Emergency Exit ranks over exactly these.
Channel = Literal["direct_buyer", "mandi", "processor", "institutional"]

# Who a cost line falls on. Only 'farmer' lines reduce net realization.
Bearer = Literal["farmer", "buyer", "platform"]


@dataclass(frozen=True)
class CostLine:
    """One line of the explainability breakdown.

    `amount_paise` is always a positive magnitude; `kind` says whether it adds
    to or subtracts from the farmer's position. Rendering code should never have
    to infer a sign from a label.
    """

    label: str
    amount_paise: int
    kind: Literal["gross", "deduction"]
    borne_by: Bearer
    basis: str                      # how this number was arrived at, in words
    source: str | None = None       # table/service it came from, when applicable

    @property
    def reduces_farmer_net(self) -> bool:
        return self.kind == "deduction" and self.borne_by == "farmer"


@dataclass
class Opportunity:
    """One costed way to sell one lot. All money is integer paise."""

    # --- identity -----------------------------------------------------------
    channel: Channel
    reference_id: str | None            # buyer_request.id, or district for a mandi
    reference_name: str | None          # buyer/market display name

    # --- what is being sold -------------------------------------------------
    crop_id: str
    crop_code: str | None
    grade: str | None
    quantity_kg: float

    # --- economics (integer paise; None means "not known", never zero) ------
    unit_price_paise: int | None = None
    gross_value_paise: int = 0
    transport_cost_paise: int | None = None
    storage_cost_paise: int = 0
    platform_fee_paise: int = 0
    commission_paise: int = 0
    expected_loss_paise: int = 0
    net_realization_paise: int | None = None

    # --- context ------------------------------------------------------------
    district: str | None = None
    distance_km: float | None = None
    holding_days: int = 0
    deadline: str | None = None
    days_to_deadline: int | None = None

    # --- feasibility --------------------------------------------------------
    # feasible=False means "do not offer this to the farmer as a live option".
    # Ranking never returns an infeasible opportunity in the ranked list.
    feasible: bool = True
    blockers: list[str] = field(default_factory=list)
    # A cost we could not determine. The opportunity is still described, but it
    # is held out of the ranking rather than compared on an incomplete basis.
    cost_basis_complete: bool = True
    limitations: list[str] = field(default_factory=list)

    # --- trust --------------------------------------------------------------
    payment_reliability: float | None = None    # 0..1, None when unknown
    payment_reliability_basis: str | None = None

    # --- provenance & honesty ----------------------------------------------
    method: str = METHOD
    price_provenance: dict | None = None   # market_data.provenance() of the price
    confidence: float | None = None

    # --- explainability -----------------------------------------------------
    breakdown: list[CostLine] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    # ------------------------------------------------------------------ maths
    def recompute_net(self) -> None:
        """Derive net realization from the breakdown, so the number on screen and
        the lines explaining it can never disagree.

        Returns None (not 0) when any mandatory cost is unknown: a missing
        transport cost must not silently read as free transport.
        """
        if not self.cost_basis_complete or self.unit_price_paise is None:
            self.net_realization_paise = None
            return
        gross = sum(l.amount_paise for l in self.breakdown if l.kind == "gross")
        deductions = sum(l.amount_paise for l in self.breakdown if l.reduces_farmer_net)
        self.net_realization_paise = gross - deductions

    @property
    def farmer_deductions_paise(self) -> int:
        return sum(l.amount_paise for l in self.breakdown if l.reduces_farmer_net)

    def to_dict(self) -> dict:
        """API shape. Flat enough to render, complete enough to audit."""
        return {
            "channel": self.channel,
            "reference_id": self.reference_id,
            "reference_name": self.reference_name,
            "crop_id": self.crop_id,
            "crop_code": self.crop_code,
            "grade": self.grade,
            "quantity_kg": self.quantity_kg,
            "unit_price_paise": self.unit_price_paise,
            "gross_value_paise": self.gross_value_paise,
            "transport_cost_paise": self.transport_cost_paise,
            "storage_cost_paise": self.storage_cost_paise,
            "platform_fee_paise": self.platform_fee_paise,
            "commission_paise": self.commission_paise,
            "expected_loss_paise": self.expected_loss_paise,
            "net_realization_paise": self.net_realization_paise,
            "district": self.district,
            "distance_km": self.distance_km,
            "holding_days": self.holding_days,
            "deadline": self.deadline,
            "days_to_deadline": self.days_to_deadline,
            "feasible": self.feasible,
            "blockers": self.blockers,
            "cost_basis_complete": self.cost_basis_complete,
            "limitations": self.limitations,
            "payment_reliability": self.payment_reliability,
            "payment_reliability_basis": self.payment_reliability_basis,
            "method": self.method,
            "price_provenance": self.price_provenance,
            "confidence": self.confidence,
            "breakdown": [
                {
                    "label": l.label,
                    "amount_paise": l.amount_paise,
                    "kind": l.kind,
                    "borne_by": l.borne_by,
                    "basis": l.basis,
                    "source": l.source,
                    "reduces_farmer_net": l.reduces_farmer_net,
                }
                for l in self.breakdown
            ],
            "reasons": self.reasons,
        }
