"""Entry point of the decision layer: ``analyze`` and the plain-text / JSON renderers."""

from __future__ import annotations

import dataclasses
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from companion.bars import BarSource, HistoricalBarSource, TimeLike
from companion.styles.base import get_style
from companion.timeframes import parse_timeframe, to_new_york
from companion.types import CriterionResult, TimeframeStack, Verdict


class OnDemandHistoricalSource:
    """``BarSource`` over the minute CSVs that loads only the history a request needs.

    ``HistoricalBarSource`` cleans the whole file by default, which takes a while. This
    wrapper opens it on a window ending at the latest ``as_of`` asked for and reaching
    back far enough for the largest lookback asked for, and widens the window when a
    later request needs more. Rows at or after ``as_of`` are never read.
    """

    _MARGIN = 1.6  # calendar time per bar of nominal length (weekends, holidays, gaps)
    description = HistoricalBarSource.description

    def __init__(self, data_dir: Path | None = None) -> None:
        self._data_dir = data_dir
        self._loaded: dict[str, tuple[pd.Timestamp, pd.Timestamp, HistoricalBarSource]] = {}

    def get_bars(self, symbol: str, timeframe: str, as_of: TimeLike, lookback: int) -> pd.DataFrame:
        moment = to_new_york(as_of)
        nominal = pd.Timedelta(minutes=parse_timeframe(timeframe).nominal_minutes)
        start = moment - nominal * (lookback + 2) * self._MARGIN - pd.Timedelta(days=10)
        key = symbol.upper()
        current = self._loaded.get(key)
        if current is None or current[0] > start or current[1] < moment:
            if current is not None:
                start, moment_end = min(start, current[0]), max(moment, current[1])
            else:
                moment_end = moment
            source = HistoricalBarSource(self._data_dir, start=start, end=moment_end)
            current = (start, moment_end, source)
            self._loaded[key] = current
        return current[2].get_bars(symbol, timeframe, as_of, lookback)


def analyze(
    symbol: str,
    as_of: TimeLike,
    stack: TimeframeStack,
    style_name: str = "ttrades",
    source: BarSource | None = None,
    direction: str | None = None,
) -> Verdict:
    """Run ``style_name`` on ``symbol`` at ``as_of`` (naive values are New York time).

    Without a ``source`` the cleaned minute CSVs are used. Pass one source to many calls
    (a replay) to load the data once. ``direction`` "long" / "short" asks the style for
    ideas on that side only; None (or "", "auto") lets the style choose.
    """
    style = get_style(style_name)
    moment = to_new_york(as_of)
    bars = source if source is not None else OnDemandHistoricalSource()
    side = (direction or "").strip().lower()
    if side in ("", "auto"):
        return style.evaluate(symbol, moment.to_pydatetime(), stack, bars)
    if side not in ("long", "short"):
        raise ValueError(f"The side to look for must be long, short or auto, not {direction!r}")
    return style.evaluate(symbol, moment.to_pydatetime(), stack, bars, direction=side)  # type: ignore[arg-type]


# --- rendering --------------------------------------------------------------------

_MARKS = {True: "[PASS]", False: "[FAIL]", None: "[ -- ]"}
_READ_MARKS = {"confirmed": "[ok]", "waiting": "[..]", "failed": "[XX]", "not_applicable": "[--]"}
_STEP_MARKS = {"done": "[done]", "next": "[NEXT]", "later": "[    ]", "blocked": "[STOP]"}
_OUTCOMES = {"open": "still open", "target_reached": "target reached", "stopped": "stopped"}


def _plan_line(verdict: Verdict) -> str:
    plan = verdict.plan
    if plan is None:
        return ""
    text = (
        f"Plan ({plan.state} {plan.direction}): entry {_price(plan.entry)}, stop {_price(plan.stop)}, "
        f"target {_price(plan.target)} ({plan.r_multiple:.2f}R)"
    )
    if plan.state == "triggered":
        text += f"; {_OUTCOMES.get(plan.outcome, plan.outcome)}"
        if plan.r_now is not None:
            text += f", last close {plan.r_now:+.2f}R from entry"
    return f"{text}. {plan.note}".strip()


def _price(value: float) -> str:
    return f"{value:.2f}"


def _levels_line(verdict: Verdict) -> str:
    if verdict.entry is None or verdict.stop is None:
        return "Entry: -   Stop: -   Targets: -"
    risk = abs(verdict.entry - verdict.stop)
    parts = [f"Entry: {_price(verdict.entry)}", f"Stop: {_price(verdict.stop)} (risk {_price(risk)})"]
    for number, target in enumerate(verdict.targets, start=1):
        multiple = f"{abs(target - verdict.entry) / risk:.2f}R" if risk > 0 else "n/a"
        parts.append(f"T{number}: {_price(target)} ({multiple})")
    if not verdict.targets:
        parts.append("Targets: -")
    return "   ".join(parts)


def render_text(verdict: Verdict) -> str:
    """The verdict as plain ASCII text: decision, levels, then the checklist by stage."""
    as_of = pd.Timestamp(verdict.as_of).strftime("%Y-%m-%d %H:%M")
    lines = [
        f"{verdict.symbol}  {as_of} New York  stack {verdict.stack.name}  style {verdict.style}",
        f"DECISION: {verdict.decision.upper()}",
        f"Bias: {verdict.bias}   Path: {verdict.path_family}   Stage: {verdict.stage}",
        _levels_line(verdict),
    ]
    if verdict.invalidation:
        lines.append(verdict.invalidation)
    if verdict.read:
        lines.append("")
        lines.append("Top-down read   [ok] confirmed   [..] waiting   [XX] failed   [--] not read")
        for step in verdict.read:
            lines.append(f"  {step.timeframe:>3} {_READ_MARKS.get(step.status, '[??]')} {step.headline}")
            if step.reason:
                lines.append(f"           {step.reason}")
    if verdict.why:
        lines.append(f"Why: {verdict.why}")
    if verdict.waiting_for:
        lines.append(f"Waiting for: {verdict.waiting_for}")
    if verdict.requested:
        lines.append(f"Side asked for: {verdict.requested}{'. ' + verdict.auto_note if verdict.auto_note else ''}")
    if verdict.steps:
        lines.append("")
        lines.append("What has to happen")
        for step in verdict.steps:
            detail = f": {step.detail}" if step.detail else ""
            lines.append(f"  {_STEP_MARKS.get(step.status, '[??]')} {step.timeframe:>3} {step.label}{detail}")
    if verdict.plan is not None:
        lines.append(_plan_line(verdict))
    if verdict.summary:
        lines.append(f"Summary: {verdict.summary}")
    lines.append("")
    lines.append("Checklist   [PASS] passed   [FAIL] failed   [ -- ] not evaluated")
    groups: dict[str, list[CriterionResult]] = {}
    for criterion in verdict.criteria:
        groups.setdefault(criterion.group or "checklist", []).append(criterion)
    for group, criteria in groups.items():
        lines.append("")
        lines.append(f"{group.upper()}")
        for criterion in criteria:
            tags = ", ".join(tag for tag in (criterion.role, criterion.timeframe) if tag)
            lines.append(f"  {_MARKS[criterion.passed]} {criterion.label}  ({criterion.key}{'; ' + tags if tags else ''})")
            lines.append(f"         {criterion.detail}")
    text = "\n".join(lines)
    for mark, plain in (("·", "-"), ("–", "-"), ("—", "-"), ("…", "...")):  # the read's punctuation, in ASCII
        text = text.replace(mark, plain)
    return text.encode("ascii", "replace").decode("ascii")


def _jsonable(value: Any) -> Any:
    if isinstance(value, (datetime, pd.Timestamp)):
        return pd.Timestamp(value).isoformat()
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {item.name: _jsonable(getattr(value, item.name)) for item in dataclasses.fields(value)}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return value


def verdict_to_dict(verdict: Verdict) -> dict[str, Any]:
    """The verdict as JSON-ready data (datetimes as ISO strings)."""
    data: dict[str, Any] = _jsonable(verdict)
    return data


def render_json(verdict: Verdict) -> str:
    return json.dumps(verdict_to_dict(verdict), indent=2)
