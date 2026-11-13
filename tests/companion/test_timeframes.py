from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from companion.timeframes import (
    SUPPORTED_TIMEFRAMES,
    available_timeframes,
    bar_close_time,
    default_stack,
    get_stack,
    list_stacks,
    make_stack,
    parse_timeframe,
)
from companion.types import TimeframeStack

NY = "America/New_York"


def ny(text: str) -> pd.Timestamp:
    return pd.Timestamp(text, tz=NY)


# --- labels -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("label", "kind", "count", "minutes"),
    [
        ("1m", "minute", 1, 1),
        ("3m", "minute", 3, 3),
        ("5m", "minute", 5, 5),
        ("15m", "minute", 15, 15),
        ("30m", "minute", 30, 30),
        ("1h", "hour", 1, 60),
        ("4h", "hour", 4, 240),
        ("1D", "day", 1, None),
        ("1W", "week", 1, None),
        ("1M", "month", 1, None),
    ],
)
def test_parse_timeframe_reads_every_supported_label(
    label: str, kind: str, count: int, minutes: int | None
) -> None:
    timeframe = parse_timeframe(label)

    assert (timeframe.label, timeframe.kind, timeframe.count) == (label, kind, count)
    assert timeframe.minutes == minutes
    assert timeframe.is_intraday == (minutes is not None)


def test_minute_and_month_labels_differ_only_by_case() -> None:
    assert parse_timeframe("1m").kind == "minute"
    assert parse_timeframe("1M").kind == "month"


@pytest.mark.parametrize("label", ["", "m", "1", "2h", "1d", "1H", "1w", "60", "1 h", None, 5])
def test_parse_timeframe_rejects_unknown_labels(label: object) -> None:
    with pytest.raises(ValueError, match="Unknown timeframe"):
        parse_timeframe(label)  # type: ignore[arg-type]


def test_supported_timeframes_are_ordered_shortest_to_longest() -> None:
    lengths = [parse_timeframe(label).nominal_minutes for label in SUPPORTED_TIMEFRAMES]

    assert lengths == sorted(lengths)
    assert len(set(lengths)) == len(lengths)


# --- close times ------------------------------------------------------------


@pytest.mark.parametrize(
    ("label", "opened", "closed"),
    [
        ("1m", "2025-06-02 09:30", "2025-06-02 09:31"),
        ("5m", "2025-06-02 09:30", "2025-06-02 09:35"),
        ("1h", "2025-06-02 09:00", "2025-06-02 10:00"),
        ("4h", "2025-06-01 22:00", "2025-06-02 02:00"),
        ("1D", "2025-06-01 18:00", "2025-06-02 18:00"),
        ("1W", "2025-06-01 18:00", "2025-06-08 18:00"),
        # June 2025 starts on a Sunday, so its bar opens that evening; July 1 is a Tuesday
        ("1M", "2025-06-01 18:00", "2025-06-30 18:00"),
        # February 2025 starts on a Saturday, March 2025 too
        ("1M", "2025-02-02 18:00", "2025-03-02 18:00"),
        # December rolls into the next year
        ("1M", "2024-12-01 18:00", "2024-12-31 18:00"),
    ],
)
def test_bar_close_time(label: str, opened: str, closed: str) -> None:
    assert bar_close_time(ny(opened), label) == ny(closed)


def test_weekly_close_keeps_the_18_00_wall_clock_across_dst() -> None:
    # Clocks go forward on Sunday 2025-03-09, so this week is 167 hours long.
    opened = ny("2025-03-02 18:00")

    closed = bar_close_time(opened, "1W")

    assert closed == ny("2025-03-09 18:00")
    assert closed - opened == pd.Timedelta(hours=167)
    # ...and back on Sunday 2025-11-02: 169 hours.
    assert bar_close_time(ny("2025-10-26 18:00"), "1W") - ny("2025-10-26 18:00") == pd.Timedelta(hours=169)


def test_bar_close_time_reads_naive_input_as_new_york_and_converts_other_zones() -> None:
    assert bar_close_time("2025-06-02 09:30", "5m") == ny("2025-06-02 09:35")
    assert bar_close_time(pd.Timestamp("2025-06-02 13:30", tz="UTC"), "5m") == ny("2025-06-02 09:35")


# --- stacks -----------------------------------------------------------------


def test_presets_cover_the_required_stacks_and_default() -> None:
    stacks = {stack.name: stack for stack in list_stacks()}

    for bias, setup, entry in [
        ("1D", "1h", "5m"),
        ("1W", "4h", "15m"),
        ("1M", "1D", "1h"),
        ("4h", "15m", "1m"),
        ("1h", "5m", "1m"),
    ]:
        name = f"{bias} / {setup} / {entry}"
        assert stacks[name] == TimeframeStack(name=name, bias=bias, setup=setup, entry=entry)
    assert default_stack() == stacks["1D / 1h / 5m"]


def test_config_lists_every_supported_timeframe_for_custom_stacks() -> None:
    assert available_timeframes() == list(SUPPORTED_TIMEFRAMES)


def test_get_stack_by_name_and_unknown_name() -> None:
    assert get_stack("1W / 4h / 15m").setup == "4h"
    with pytest.raises(KeyError):
        get_stack("nope")


def test_make_stack_builds_a_named_custom_stack() -> None:
    assert make_stack("4h", "30m", "3m") == TimeframeStack("4h / 30m / 3m", "4h", "30m", "3m")
    assert make_stack("1D", "1h", "5m", name="swing").name == "swing"


@pytest.mark.parametrize(
    ("bias", "setup", "entry"),
    [
        ("5m", "1h", "1D"),  # reversed
        ("1D", "5m", "1h"),  # setup below entry
        ("1h", "1h", "5m"),  # bias equals setup
        ("1D", "1h", "1h"),  # setup equals entry
        ("1M", "1m", "1m"),
    ],
)
def test_make_stack_requires_bias_above_setup_above_entry(bias: str, setup: str, entry: str) -> None:
    with pytest.raises(ValueError, match="highest to lowest"):
        make_stack(bias, setup, entry)


def test_make_stack_rejects_unknown_labels() -> None:
    with pytest.raises(ValueError, match="Unknown timeframe"):
        make_stack("1D", "2h", "5m")


def write_config(path: Path, stacks: list[dict[str, str]], **extra: object) -> Path:
    path.write_text(json.dumps({"stacks": stacks, **extra}), encoding="utf-8")
    return path


def test_a_stack_added_to_the_json_file_becomes_selectable(tmp_path: Path) -> None:
    config = write_config(
        tmp_path / "stacks.json",
        [
            {"name": "1D / 1h / 5m", "bias": "1D", "setup": "1h", "entry": "5m"},
            {"name": "My scalp", "bias": "30m", "setup": "3m", "entry": "1m"},
            {"bias": "1W", "setup": "1D", "entry": "4h"},
        ],
        default="My scalp",
        timeframes=["1m", "3m", "30m"],
    )

    assert [stack.name for stack in list_stacks(config)] == ["1D / 1h / 5m", "My scalp", "1W / 1D / 4h"]
    assert get_stack("My scalp", config) == TimeframeStack("My scalp", "30m", "3m", "1m")
    assert default_stack(config).name == "My scalp"
    assert available_timeframes(config) == ["1m", "3m", "30m"]


def test_default_falls_back_to_the_first_stack(tmp_path: Path) -> None:
    config = write_config(tmp_path / "stacks.json", [{"bias": "4h", "setup": "15m", "entry": "1m"}])

    assert default_stack(config).name == "4h / 15m / 1m"
    assert available_timeframes(config) == list(SUPPORTED_TIMEFRAMES)


@pytest.mark.parametrize(
    ("stacks", "message"),
    [
        ([{"bias": "1h", "setup": "1D", "entry": "5m"}], "highest to lowest"),
        ([{"bias": "1D", "setup": "90m", "entry": "5m"}], "Unknown timeframe"),
        ([{"bias": "1D", "setup": "1h"}], "needs bias, setup and entry"),
        (
            [
                {"name": "same", "bias": "1D", "setup": "1h", "entry": "5m"},
                {"name": "same", "bias": "1W", "setup": "4h", "entry": "15m"},
            ],
            "Duplicate stack name",
        ),
        ([], "No stacks configured"),
    ],
)
def test_invalid_config_is_rejected(tmp_path: Path, stacks: list[dict[str, str]], message: str) -> None:
    config = write_config(tmp_path / "stacks.json", stacks)

    with pytest.raises(ValueError, match=message):
        list_stacks(config)


def test_config_with_an_unknown_timeframe_option_is_rejected(tmp_path: Path) -> None:
    config = write_config(
        tmp_path / "stacks.json",
        [{"bias": "1D", "setup": "1h", "entry": "5m"}],
        timeframes=["1m", "2h"],
    )

    with pytest.raises(ValueError, match="Unknown timeframe"):
        available_timeframes(config)
