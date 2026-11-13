"""Timeframe labels and the selectable top-down stacks.

Labels are case-sensitive: ``1m`` is one minute, ``1M`` is one month.

Futures conventions used for bar boundaries (all in ``America/New_York``):

- the trading day runs 18:00 -> 17:00, so intraday bars are anchored to 18:00
- a ``1D`` bar opens at 18:00 on the prior calendar evening
- a ``1W`` bar opens Sunday 18:00
- a ``1M`` bar holds the trading days of one calendar month and opens at 18:00 on the
  evening before the month's first weekday

The stacks a user can pick live in ``companion/config/stacks.json``; adding a stack is a
JSON edit only.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from companion import paths as _paths
from companion.types import BARS_TIMEZONE, TimeframeStack

TimeframeKind = Literal["minute", "hour", "day", "week", "month"]

STACKS_PATH = _paths.resource("config", "stacks.json")


@dataclass(frozen=True)
class Timeframe:
    label: str
    kind: TimeframeKind
    count: int

    @property
    def is_intraday(self) -> bool:
        return self.kind in ("minute", "hour")

    @property
    def minutes(self) -> int | None:
        """Exact bar length in minutes for intraday timeframes, ``None`` otherwise."""
        if self.kind == "minute":
            return self.count
        if self.kind == "hour":
            return self.count * 60
        return None

    @property
    def nominal_minutes(self) -> int:
        """Approximate length, only for ordering timeframes against each other."""
        per_unit = {"minute": 1, "hour": 60, "day": 1440, "week": 10080, "month": 43200}
        return self.count * per_unit[self.kind]


_TIMEFRAMES: dict[str, Timeframe] = {
    tf.label: tf
    for tf in (
        Timeframe("1m", "minute", 1),
        Timeframe("3m", "minute", 3),
        Timeframe("5m", "minute", 5),
        Timeframe("15m", "minute", 15),
        Timeframe("30m", "minute", 30),
        Timeframe("1h", "hour", 1),
        Timeframe("4h", "hour", 4),
        Timeframe("1D", "day", 1),
        Timeframe("1W", "week", 1),
        Timeframe("1M", "month", 1),
    )
}

SUPPORTED_TIMEFRAMES: tuple[str, ...] = tuple(_TIMEFRAMES)


def parse_timeframe(label: str | Timeframe) -> Timeframe:
    """Return the ``Timeframe`` for a label; raise ``ValueError`` for unknown labels."""
    if isinstance(label, Timeframe):
        return label
    try:
        return _TIMEFRAMES[label]
    except (KeyError, TypeError):
        raise ValueError(
            f"Unknown timeframe {label!r}; supported: {', '.join(SUPPORTED_TIMEFRAMES)}"
        ) from None


def to_new_york(value: str | datetime | pd.Timestamp) -> pd.Timestamp:
    """Coerce to a tz-aware New York timestamp. Naive values are read as New York time."""
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        return ts.tz_localize(BARS_TIMEZONE)
    return ts.tz_convert(BARS_TIMEZONE)


def candle_label(
    open_time: str | datetime | pd.Timestamp,
    timeframe: str | Timeframe,
    relative_to: str | datetime | pd.Timestamp | None = None,
) -> str:
    """How a candle is named to the trader, from its open time.

    Intraday candles are named by their open, ``09:55``, with the date in front
    (``Feb 17 20:00``) when that is not the calendar day of ``relative_to``. A daily
    candle is named by its trading date (it opens at 18:00 the evening before), a weekly
    one by the Monday it starts trading, a monthly one by its month.
    """
    tf = parse_timeframe(timeframe)
    opened = to_new_york(open_time)
    if tf.is_intraday:
        clock = opened.strftime("%H:%M")
        if relative_to is not None and to_new_york(relative_to).date() == opened.date():
            return clock
        return f"{opened.strftime('%b')} {opened.day} {clock}"
    trading_day = opened.tz_localize(None) + pd.Timedelta(hours=6)
    if tf.kind == "month":
        return trading_day.strftime("%b %Y")
    name = f"{trading_day.strftime('%b')} {trading_day.day}"
    return f"week of {name}" if tf.kind == "week" else name


def _evening_before(day: pd.Timestamp) -> pd.Timestamp:
    """18:00 New York on the calendar day before ``day`` (a naive midnight)."""
    return (day - pd.Timedelta(hours=6)).tz_localize(BARS_TIMEZONE)


def _month_open(first_of_month: pd.Timestamp) -> pd.Timestamp:
    """Open of the month bar: the session open of the month's first weekday."""
    weekday = first_of_month.weekday()
    first_weekday = first_of_month + pd.Timedelta(days={5: 2, 6: 1}.get(weekday, 0))
    return _evening_before(first_weekday)


def bar_close_time(
    open_time: str | datetime | pd.Timestamp, timeframe: str | Timeframe
) -> pd.Timestamp:
    """Close time of the bar that opens at ``open_time``.

    A bar is closed at ``as_of`` when ``bar_close_time(open) <= as_of``. Daily and
    weekly closes keep the 18:00 wall clock across DST changes; a month bar closes when
    the next month bar opens.
    """
    tf = parse_timeframe(timeframe)
    opened = to_new_york(open_time)
    if tf.minutes is not None:
        return opened + pd.Timedelta(minutes=tf.minutes)
    wall = opened.tz_localize(None)
    if tf.kind == "day":
        return (wall + pd.Timedelta(days=tf.count)).tz_localize(BARS_TIMEZONE)
    if tf.kind == "week":
        return (wall + pd.Timedelta(days=7 * tf.count)).tz_localize(BARS_TIMEZONE)
    # month: the bar's trading days start the morning after the 18:00 open
    trading_day = (wall + pd.Timedelta(hours=6)).normalize()
    next_first = (trading_day.replace(day=1) + pd.DateOffset(months=tf.count)).normalize()
    return _month_open(next_first)


# --- stacks -----------------------------------------------------------------


def make_stack(bias: str, setup: str, entry: str, name: str | None = None) -> TimeframeStack:
    """Build a validated stack from three labels (bias > setup > entry)."""
    frames = [parse_timeframe(label) for label in (bias, setup, entry)]
    if not frames[0].nominal_minutes > frames[1].nominal_minutes > frames[2].nominal_minutes:
        raise ValueError(
            f"Stack must run from highest to lowest timeframe (bias > setup > entry), "
            f"got {bias} / {setup} / {entry}"
        )
    return TimeframeStack(
        name=name if name else f"{bias} / {setup} / {entry}", bias=bias, setup=setup, entry=entry
    )


def _read_config(path: Path | None) -> dict[str, Any]:
    config_path = Path(path) if path is not None else STACKS_PATH
    with config_path.open(encoding="utf-8") as handle:
        config = json.load(handle)
    if not isinstance(config, dict) or not isinstance(config.get("stacks"), list):
        raise ValueError(f"{config_path}: expected an object with a 'stacks' list")
    return config


def list_stacks(path: Path | None = None) -> list[TimeframeStack]:
    """All stacks from the config file, in file order, validated."""
    stacks: list[TimeframeStack] = []
    seen: set[str] = set()
    for entry in _read_config(path)["stacks"]:
        try:
            stack = make_stack(entry["bias"], entry["setup"], entry["entry"], entry.get("name"))
        except (KeyError, TypeError) as error:
            raise ValueError(f"Stack entry {entry!r} needs bias, setup and entry") from error
        if stack.name in seen:
            raise ValueError(f"Duplicate stack name {stack.name!r}")
        seen.add(stack.name)
        stacks.append(stack)
    if not stacks:
        raise ValueError("No stacks configured")
    return stacks


def get_stack(name: str, path: Path | None = None) -> TimeframeStack:
    for stack in list_stacks(path):
        if stack.name == name:
            return stack
    raise KeyError(f"No stack named {name!r}")


def default_stack(path: Path | None = None) -> TimeframeStack:
    """The stack named by ``default`` in the config, else the first one listed."""
    name = _read_config(path).get("default")
    return get_stack(name, path) if name else list_stacks(path)[0]


def available_timeframes(path: Path | None = None) -> list[str]:
    """Labels a UI may offer for custom stacks (the config's ``timeframes`` list)."""
    labels = _read_config(path).get("timeframes", list(SUPPORTED_TIMEFRAMES))
    return [parse_timeframe(label).label for label in labels]
