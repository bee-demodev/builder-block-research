"""What the backtest measured for the setup on screen.

Reads ``companion/config/evidence.json``, which ``scripts/phase_b_evidence.py`` writes from the
pre-registered Phase B runs (``results/phase_b``). Nothing here is typed in by hand, so the
numbers move when the runs are redone. Information only: no rule reads it.

A triggered plan gets one grade:

- ``small_stop``: the stop is under the small-stop share of the daily range, the one cut
  that lost in every test.
- ``best_measured``: the setup that passed its pre-registered test (CISD trigger, stop at
  least the minimum share of the daily range, on the stacks it was tested on). Weak.
- ``no_edge``: any other trigger on a backtested stack: the stack's own record.
- ``untested``: a stack the backtest did not cover on complete data.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from companion import paths
from companion.types import Verdict

EVIDENCE_PATH = paths.resource("config", "evidence.json")
_TRIGGER_KEYS = ("cont_entry_trigger", "rev_entry_trigger")


@dataclass(frozen=True)
class Evidence:
    grade: str  # small_stop | best_measured | no_edge | untested
    label: str  # "Best-measured setup"
    line: str  # the record in one sentence
    exits: str = ""  # how the exits compared on this stack ("" when not measured)
    source: str = ""  # where the numbers come from, for a tooltip


@lru_cache(maxsize=4)
def _load(path: str) -> dict[str, Any] | None:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def load(path: Path | None = None) -> dict[str, Any] | None:
    """The evidence file, or None when it is missing or unreadable (the panel then shows nothing)."""
    return _load(str(path or EVIDENCE_PATH))


def trigger_kind(verdict: Verdict) -> str:
    """``"cisd"`` or ``"order_block"`` for the selected path's trigger, as the backtest labels it."""
    for item in verdict.criteria:
        if item.key in _TRIGGER_KEYS and item.passed:
            return "cisd" if "CISD is the trigger" in item.detail else "order_block"
    return ""


def _r(value: float) -> str:
    return f"{'−' if value < 0 else '+'}{abs(value):.2f}R"


def _record(entry: dict[str, Any]) -> str:
    """"+0.07R a trade over 1,325 taken trades (2021-26), up in 5 of 6 years tested"."""
    return (
        f"{_r(entry['r'])} a trade over {entry['n']:,} taken trades ({entry['span']}), "
        f"up in {entry['years_up']} of {entry['years']} years tested"
    )


def grade(stack: str, kind: str, risk_adr: float | None, data: dict[str, Any] | None = None) -> Evidence | None:
    """The grade of a triggered plan on ``stack`` (``"1D / 4h / 15m"``). None without the file."""
    data = data if data is not None else load()
    if not data:
        return None
    source = data.get("source", "")
    record = data.get("stacks", {}).get(stack)
    exits = record.get("exits_line", "") if record else ""
    small = data.get("setups", {}).get("small_stop")
    if small and risk_adr is not None and risk_adr < small["max_risk_adr"]:
        tail = " Costs eat them." if small["r"] < 0 else ""
        line = f"Stops under {small['max_risk_adr']:.0%} of the daily range: {_record(small)}.{tail}"
        return Evidence("small_stop", "Small stop", line, exits, source)
    best = data.get("setups", {}).get("best_measured")
    if (
        best
        and best.get("retest") != "FAIL"  # a setup that failed its re-test is not shown as the best one
        and stack in best["stacks"]
        and kind == best["trigger"]
        and risk_adr is not None
        and risk_adr >= best["min_risk_adr"]
    ):
        line = f"{_record(best)}. {best['caveat']}"
        return Evidence("best_measured", "Best-measured setup", line, exits, source)
    if record is None:
        return Evidence("untested", "Not backtested", "This stack was not backtested on complete data.", "", source)
    return Evidence("no_edge", "No edge measured", f"This stack: {_record(record)}.", exits, source)
