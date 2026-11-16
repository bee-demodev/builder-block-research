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

The odds board (``odds``): how often the stack, the setup (path and trigger) and the session
of the trigger reached 2R before the stop, the win rate needed to break even after costs,
and how long a target or a stop took, each row on its own (never all of them combined:
the cells would be too small to mean anything).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

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
    odds: Odds | None = None  # the odds board for this trigger


@dataclass(frozen=True)
class OddsRow:
    label: str  # "1D / 1h / 5m", "Continuation, CISD", "NY AM"
    n: int
    win: int  # percent of trades that reached 2R before the stop
    breakeven: int  # percent needed to break even at 2R after costs
    win_1r: int  # percent that reached 1R before the stop
    to_target: str  # median time to the target, "4.6 h" ("" when none)
    to_stop: str  # median time to the stop
    note: str = ""  # "Many still open after 10 days" and the like
    current: bool = False  # this trigger's row


@dataclass(frozen=True)
class Odds:
    line: str  # "This setup wins 33% to 2R (breakeven 34%), target ~3 h, stop ~1.7 h, 666 trades"
    stacks: tuple[OddsRow, ...]
    setups: tuple[OddsRow, ...]  # on this trigger's stack
    sessions: tuple[OddsRow, ...]


SESSIONS = {
    "asia": "Asia",
    "london": "London",
    "pre_ny": "Pre-NY",
    "ny_am": "NY AM",
    "ny_lunch": "NY lunch",
    "ny_pm": "NY PM",
    "after_hours": "After hours",
}
SETUPS = {"continuation": "Continuation", "reversal": "Reversal", "cisd": "CISD", "order_block": "order block"}
MANY_OPEN = 0.2  # a row with this share still open at the 10-day horizon has no honest win rate
MIN_TRADES = 30  # fewer trades than this in a row: no win rate shown


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


def session_label(moment: pd.Timestamp) -> str:
    """New York session of a time, as the backtest buckets it (companion.tools.backtest.session_label)."""
    minutes = moment.hour * 60 + moment.minute
    if minutes >= 18 * 60 or minutes < 2 * 60:
        return "asia"
    if minutes < 5 * 60:
        return "london"
    if minutes < 8 * 60 + 30:
        return "pre_ny"
    if minutes < 11 * 60:
        return "ny_am"
    if minutes < 13 * 60 + 30:
        return "ny_lunch"
    if minutes < 16 * 60:
        return "ny_pm"
    return "after_hours"


def setup_key(path: str, kind: str) -> str:
    return f"{path}/{kind}" if path and kind else ""


def _setup_label(key: str) -> str:
    path, _, kind = key.partition("/")
    return f"{SETUPS.get(path, path)}, {SETUPS.get(kind, kind)}"


def _hours(value: float | None) -> str:
    if value is None:
        return ""
    if value < 1:
        return f"{max(1, round(value * 60))} min"
    if value < 48:
        return f"{value:.1f} h".replace(".0 h", " h")
    return f"{value / 24:.1f} d".replace(".0 d", " d")


def _row(label: str, entry: dict[str, Any], current: bool) -> OddsRow:
    note = ""
    if entry["n"] < MIN_TRADES:
        note = f"Too few trades to say ({entry['n']})"
    elif entry.get("open", 0) >= MANY_OPEN:
        note = "Many still open after 10 days"
    return OddsRow(
        label=label,
        n=int(entry["n"]),
        win=round(100 * entry["win"]),
        breakeven=round(100 * entry["breakeven"]),
        win_1r=round(100 * entry["win_1r"]),
        to_target=_hours(entry.get("hours_to_target")),
        to_stop=_hours(entry.get("hours_to_stop")),
        note=note,
        current=current,
    )


def odds(stack: str, setup: str, session: str, data: dict[str, Any] | None = None) -> Odds | None:
    """The odds board for a trigger on ``stack`` with ``setup`` ("continuation/cisd") in ``session``."""
    data = data if data is not None else load()
    board = (data or {}).get("odds")
    if not board:
        return None
    stacks = tuple(_row(name, entry, name == stack) for name, entry in board.get("stacks", {}).items())
    own = board.get("setups", {}).get(stack, {})
    setups = tuple(_row(_setup_label(key), entry, key == setup) for key, entry in own.items())
    sessions = tuple(_row(SESSIONS.get(key, key), board["sessions"][key], key == session) for key in SESSIONS if key in board.get("sessions", {}))
    pick = own.get(setup) or board.get("stacks", {}).get(stack)
    if pick is None:
        line = "This stack was not backtested on complete data."
    else:
        row = _row("", pick, True)
        what = "This setup" if setup in own else "This stack"
        if row.note:
            line = f"{what}: {row.note[0].lower()}{row.note[1:]}, so no honest win rate ({row.n:,} trades)"
        else:
            parts = [f"{what} wins {row.win}% to 2R (breakeven {row.breakeven}%)"]
            parts += [f"target ~{row.to_target}"] if row.to_target else []
            parts += [f"stop ~{row.to_stop}"] if row.to_stop else []
            line = ", ".join(parts) + f", {row.n:,} trades"
    return Odds(line, stacks, setups, sessions)


def _r(value: float) -> str:
    return f"{'−' if value < 0 else '+'}{abs(value):.2f}R"


def _record(entry: dict[str, Any]) -> str:
    """"+0.07R a trade over 1,325 taken trades (2021-26), up in 5 of 6 years tested"."""
    return (
        f"{_r(entry['r'])} a trade over {entry['n']:,} taken trades ({entry['span']}), "
        f"up in {entry['years_up']} of {entry['years']} years tested"
    )


def grade(
    stack: str, kind: str, risk_adr: float | None, data: dict[str, Any] | None = None, path: str = "", session: str = ""
) -> Evidence | None:
    """The grade of a triggered plan on ``stack`` (``"1D / 4h / 15m"``). None without the file."""
    data = data if data is not None else load()
    if not data:
        return None
    return replace(_grade(stack, kind, risk_adr, data), odds=odds(stack, setup_key(path, kind), session, data))


def _grade(stack: str, kind: str, risk_adr: float | None, data: dict[str, Any]) -> Evidence:
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
