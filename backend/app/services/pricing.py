"""Pricing service — transparent price breakdown (PRD §3.1).

Builds the breakdown shown on F-12 / B-M price breakdown screen:
  subtotal, transport, platform fee, facilitation fee, buyer total, farmer payout.
"""
from __future__ import annotations

from dataclasses import dataclass

# Platform fee: 2% of subtotal, paid by buyer.
PLATFORM_FEE_BPS = 200  # basis points
# Logistics facilitation: 1% of transport cost, deducted from transporter payout.
LOGISTICS_FEE_BPS = 100


@dataclass
class PriceBreakdown:
    subtotal_paise: int
    transport_cost_paise: int
    platform_fee_paise: int
    logistics_facilitation_fee_paise: int
    buyer_total_paise: int
    farmer_payout_paise: int
    traditional_chain_price_paise: int | None


def compute_breakdown(
    quantity_kg: float,
    unit_price_paise: int,
    transport_cost_paise: int = 0,
    traditional_chain_price_paise: int | None = None,
) -> PriceBreakdown:
    subtotal = int(round(quantity_kg * unit_price_paise))
    platform_fee = subtotal * PLATFORM_FEE_BPS // 10_000
    logistics_fee = transport_cost_paise * LOGISTICS_FEE_BPS // 10_000

    buyer_total = subtotal + transport_cost_paise + platform_fee
    farmer_payout = subtotal  # farmer gets the full subtotal

    return PriceBreakdown(
        subtotal_paise=subtotal,
        transport_cost_paise=transport_cost_paise,
        platform_fee_paise=platform_fee,
        logistics_facilitation_fee_paise=logistics_fee,
        buyer_total_paise=buyer_total,
        farmer_payout_paise=farmer_payout,
        traditional_chain_price_paise=traditional_chain_price_paise,
    )
