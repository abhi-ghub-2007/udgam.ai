"""Neutral Market Orchestration (SIH26132 Feature 5) — ALGORITHMIC.

Not a sixth engine. This is the single, declared statement of what UDGAM is
allowed to rank on, imported by every engine that orders anything, plus the
audit that proves no hidden preference has crept in.

THE RULE
--------
A recommendation may be ordered only by the factors named in RANKING_FACTORS.
Identity is not among them. Whether a counterparty is a paying partner, a large
buyer, UDGAM's own marketplace or a stranger must make no difference to where
they appear in a list. If two options are objectively identical they must rank
identically, and the tie must break on something declared and neutral.

WHY IT LIVES IN ONE FILE
------------------------
The Net Exit Optimizer, the Sale Window, Aggregation and the Emergency Exit
Engine each order things. Four private notions of "best" would drift apart and
would each need auditing separately. They all sort on values this module names,
and tests/test_neutrality.py audits them together.
"""
from __future__ import annotations

from dataclasses import dataclass

METHOD = "ALGORITHMIC"

# Everything the platform is permitted to rank on, and why each is legitimate.
RANKING_FACTORS: dict[str, str] = {
    "expected_farmer_net_realization_paise":
        "what the farmer actually banks, after every cost they bear",
    "risk_adjusted_paise":
        "net realization less a penalty taken from the forecast's own downside band",
    "unit_price_paise":
        "the price of supply, used when filling a requirement at lowest cost",
    "distance_km":
        "haulage distance, an objective cost and feasibility input",
    "quantity_fit":
        "how much of the requirement an option actually covers",
    "quality_fit":
        "whether the grade meets the buyer's stated minimum",
    "deadline_fit":
        "whether delivery is physically possible in the time left",
    "payment_reliability":
        "verification status and completed ratings, where they exist",
    "reference_id":
        "final deterministic tie-break so identical options order stably",
}

# Attributes that must NEVER influence an ordering. The audit asserts that
# permuting any of these leaves every ranking unchanged.
FORBIDDEN_FACTORS: tuple[str, ...] = (
    "buyer_name", "farmer_name", "reference_name", "transporter_id",
    "is_partner", "is_promoted", "commission_rate", "account_tier",
    "marketplace", "sponsored",
)

DISCLOSURE = (
    "Options are ordered only by declared, objectively measurable factors. "
    "No buyer, market, transporter, marketplace or commercial partner receives "
    "a ranking boost, and UDGAM's own channels are ranked on the same terms as "
    "any other."
)


@dataclass(frozen=True)
class RankingPolicy:
    """The ordering contract an engine declares when it returns a ranked list."""

    primary: str
    tie_breakers: tuple[str, ...]

    def describe(self) -> str:
        parts = [f"{self.primary} desc"] + [f"{t} asc" for t in self.tie_breakers]
        return ", then ".join(parts)

    def validate(self) -> None:
        """Raise if an engine ever tries to rank on something undeclared."""
        for field in (self.primary, *self.tie_breakers):
            if field not in RANKING_FACTORS:
                raise ValueError(
                    f"'{field}' is not a declared ranking factor; add it to "
                    "RANKING_FACTORS with a justification, or do not rank on it."
                )
            if field in FORBIDDEN_FACTORS:
                raise ValueError(f"'{field}' may never influence a ranking.")


# The policies the shipped engines use. Each is validated at import time, so a
# module that starts ranking on something undeclared fails immediately.
NET_EXIT_POLICY = RankingPolicy(
    primary="expected_farmer_net_realization_paise",
    tie_breakers=("distance_km", "reference_id"),
)
SALE_WINDOW_POLICY = RankingPolicy(
    primary="risk_adjusted_paise",
    tie_breakers=("distance_km", "reference_id"),
)
AGGREGATION_POLICY = RankingPolicy(
    primary="unit_price_paise",
    tie_breakers=("distance_km", "reference_id"),
)

for _p in (NET_EXIT_POLICY, SALE_WINDOW_POLICY, AGGREGATION_POLICY):
    _p.validate()


def disclosure(policy: RankingPolicy) -> dict:
    """The block an API attaches so a reader can audit the ordering themselves."""
    return {
        "ranked_by": policy.describe(),
        "factors": {k: RANKING_FACTORS[k] for k in
                    (policy.primary, *policy.tie_breakers)},
        "never_used": list(FORBIDDEN_FACTORS),
        "statement": DISCLOSURE,
        "method": METHOD,
    }
