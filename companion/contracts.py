"""Futures contract specs used to say what one trade costs, in multiples of its risk.

Cost of a round turn, in price points: one tick of slippage on the entry plus the
commission converted to points (``commission / point_value``). The same move costs a
micro about twice as much per point as a mini, because its commission does not shrink
with its point value. Figures are typical retail rates (2026), not a broker quote.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Contract:
    tick: float  # smallest price step
    point_value: float  # dollars per 1.0 of price, one contract
    commission: float  # dollars per round turn, all fees


# mini / micro pairs by root symbol
CONTRACTS: dict[str, tuple[Contract, Contract]] = {
    "NQ": (Contract(0.25, 20.0, 4.50), Contract(0.25, 2.0, 1.50)),
    "ES": (Contract(0.25, 50.0, 4.50), Contract(0.25, 5.0, 1.50)),
    "YM": (Contract(1.0, 5.0, 4.50), Contract(1.0, 0.5, 1.50)),
    "RTY": (Contract(0.1, 50.0, 4.50), Contract(0.1, 5.0, 1.50)),
    "GC": (Contract(0.1, 100.0, 4.50), Contract(0.1, 10.0, 1.50)),
    "SI": (Contract(0.005, 5000.0, 4.50), Contract(0.005, 1000.0, 1.50)),
    "CL": (Contract(0.01, 1000.0, 4.50), Contract(0.01, 100.0, 1.50)),
}


def root(symbol: str) -> str:
    """``"CME_MINI:NQ1!"``, ``"NQZ2026"``, ``"nq"`` -> ``"NQ"``; ``""`` when unknown."""
    text = symbol.upper().split(":")[-1]
    for name in sorted(CONTRACTS, key=len, reverse=True):
        if text.startswith(name) or text.startswith("M" + name):
            return name
    return ""


def cost_points(contract: Contract) -> float:
    return contract.tick + contract.commission / contract.point_value


def cost_in_r(symbol: str, risk: float) -> tuple[float | None, float | None]:
    """``(mini, micro)``: the round-turn cost of one contract as a share of ``risk`` (price points)."""
    pair = CONTRACTS.get(root(symbol))
    if pair is None or not risk > 0:
        return None, None
    return cost_points(pair[0]) / risk, cost_points(pair[1]) / risk
