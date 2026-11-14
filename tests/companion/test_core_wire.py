"""The wire contract (version 1): a real verdict through JSON and back, the saved fixtures, client input.

The fixtures are ``snapshot`` messages the core sends from the saved minute history for
NQ (1D / 1h / 5m, ttrades). The UI is built against them:

- ``fixtures/snapshot_v1.json``: 2025-11-11 08:45 New York, side Auto: a WATCH. The short
  triggered Nov 10 19:15 and reached its target at 00:15, so it has played out (rules.md
  question 33).
- ``fixtures/snapshot_v1_triggered.json``: 2025-11-11 08:45, side Short: that triggered plan,
  played out, every step done but the entry step, which is blocked and says why; the risk /
  reward tool on the entry chart.
- ``fixtures/snapshot_v1_planned.json``: 2025-11-19 10:15, side Short: a planned plan
  (nothing triggered), steps blocked / next / later, the next step's level on its chart.

Regenerate them with::

    COMPANION_WRITE_FIXTURE=1 python -m pytest tests/companion/test_core_wire.py
"""

from __future__ import annotations

import json
import os
import types
import typing
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from companion import app_model
from companion.app_model import DATA_HISTORY, Candle, CompanionController, LiveStatus, VerdictView
from companion.bars import DATA_DIR
from companion.core import wire
from companion.core.loop import Core, inline

FIXTURES = Path(__file__).resolve().parent / "fixtures"
MOMENT = {"symbol": "NQ", "stack": "1D / 1h / 5m", "style": "ttrades", "data": DATA_HISTORY, "when": "2025-11-11 08:45"}
TRIGGERED = {**MOMENT, "when": "2025-11-11 08:45", "side": "short"}
PLANNED = {**MOMENT, "when": "2025-11-19 10:15", "side": "short"}
SAVED = {"snapshot_v1.json": MOMENT, "snapshot_v1_triggered.json": TRIGGERED, "snapshot_v1_planned.json": PLANNED}
needs_data = pytest.mark.skipif(not (DATA_DIR / "nq_minute.csv").exists(), reason="minute data not present")


def check_at(state_path: Path, moment: dict[str, str]) -> tuple[dict[str, Any], VerdictView]:
    """The snapshot the core sends for ``moment``, and the view it was made from."""
    controller = CompanionController(state_path=state_path)
    messages: list[dict[str, Any]] = []
    core = Core(controller, run_check=inline, run_watch=inline, listener=messages.append)
    core.begin()
    core.submit(wire.Command("set", dict(moment)))
    core.submit(wire.Command("check"))
    core.step()
    snapshot = core.latest["snapshot"]
    assert snapshot["view"] is not None, snapshot["error"]
    view = controller.present(core._shown)  # noqa: SLF001 - the very outcome the snapshot shows
    return snapshot, view


@pytest.fixture(scope="module")
def all_checked(tmp_path_factory: pytest.TempPathFactory) -> dict[str, tuple[dict[str, Any], VerdictView]]:
    """Every saved moment's snapshot and view, by fixture name."""
    return {name: check_at(tmp_path_factory.mktemp("state") / "ui_state.json", moment) for name, moment in SAVED.items()}


@pytest.fixture(scope="module")
def checked(all_checked: dict[str, tuple[dict[str, Any], VerdictView]]) -> tuple[dict[str, Any], VerdictView]:
    return all_checked["snapshot_v1.json"]


# --- a real verdict, through JSON and back -----------------------------------------


def rebuild(hint: Any, value: Any) -> Any:
    """Turn a wire value back into the Python type ``hint`` names (the test's own reading of the contract)."""
    origin = typing.get_origin(hint)
    if origin in (typing.Union, types.UnionType):
        options = [arg for arg in typing.get_args(hint) if arg is not type(None)]
        return None if value is None else rebuild(options[0], value)
    if origin is tuple:
        item = typing.get_args(hint)[0]
        assert isinstance(value, list)
        return tuple(rebuild(item, entry) for entry in value)
    if hint is pd.Timestamp:
        return pd.Timestamp(value)
    if is_dataclass(hint):
        assert isinstance(value, dict)
        hints = typing.get_type_hints(hint, vars(app_model))
        return hint(**{item.name: rebuild(hints[item.name], value[item.name]) for item in fields(hint)})
    if hint is float:
        return float(value)
    assert isinstance(value, hint), (hint, value)
    return value


@needs_data
def test_a_real_verdict_view_survives_the_wire(checked: tuple[dict[str, Any], VerdictView]) -> None:
    snapshot, view = checked
    sent = json.loads(wire.dumps(snapshot))["view"]
    assert rebuild(VerdictView, sent) == view  # every field, nested ones too, under its own name

    # the short triggered Nov 10 19:15 and reached its target at 00:15: played out, so watch (rules.md question 33)
    assert view.decision == "watch" and not view.has_levels and view.charts and view.groups  # levels live on the plan
    assert view.plan is not None and view.plan.stage_label == "played_out" and view.plan.outcome == "target_reached"
    for group, original in zip(sent["groups"], view.groups):
        assert group["tally"] == original.tally
    candle = sent["charts"][2]["candles"][-1]
    opened = view.charts[2].candles[-1].time
    assert candle["time"] == opened.isoformat() and candle["time"].endswith("-05:00")  # New York, standard time in November
    assert candle["t"] == int(pd.Timestamp(opened.tz_localize(None), tz="UTC").timestamp())  # wall clock read as UTC


@needs_data
@pytest.mark.parametrize("name", list(SAVED))
def test_the_snapshot_keeps_the_shape_of_the_saved_fixture(all_checked: dict[str, tuple[dict[str, Any], VerdictView]], name: str) -> None:
    snapshot = json.loads(wire.dumps(all_checked[name][0]))
    path = FIXTURES / name
    if os.environ.get("COMPANION_WRITE_FIXTURE"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(snapshot, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert shape(snapshot) == shape(saved)
    assert set(saved) == {"type", "seq", "view", "error", "offer_history", "status", "timing"}
    assert set(saved["status"]) == {"state", "text", "stale"}
    assert set(saved["timing"]) == {"bar_closed_at", "detected_at", "fetch_ms", "compute_ms", "lag_ms", "load_ms"}
    assert set(saved["view"]["charts"][0]["candles"][0]) == {"time", "t", "open", "high", "low", "close", "forming", "label"}


# --- a forced side: the plan, its steps and the risk / reward tool ------------------------


@needs_data
@pytest.mark.parametrize(("name", "state"), [("snapshot_v1_triggered.json", "triggered"), ("snapshot_v1_planned.json", "planned")])
def test_a_forced_side_sends_a_plan_its_steps_and_a_tool_that_agree(
    all_checked: dict[str, tuple[dict[str, Any], VerdictView]], name: str, state: str
) -> None:
    sent = json.loads(wire.dumps(all_checked[name][0]))["view"]
    plan = sent["plan"]
    assert sent["requested"] == "short" and plan["direction"] == "short" and plan["state"] == state
    # the worded levels the window prints are the numbers a client draws
    assert [level["price"] for level in plan["levels"]] == [f"{plan[key]:,.2f}" for key in ("entry", "stop", "target")]

    tools = {chart["role"]: chart["tool"] for chart in sent["charts"]}
    assert tools["bias"] is None and tools["setup"] is None  # the entry chart only
    tool = tools["entry"]
    assert tool["planned"] is (state == "planned")
    lines = {line["role"]: line for line in tool["lines"]}
    assert {role: line["price"] for role, line in lines.items()} == {role: plan[role] for role in ("entry", "stop", "target")}
    assert all(line["names"][-1] == role.capitalize() for role, line in lines.items())  # the bare word, kept when names are off
    assert lines["stop"]["names_worded"][0].startswith("Stop · risk") and lines["target"]["names_worded"][0].startswith("Target · reward")
    assert tool["captions"]["reward"].startswith("PLANNED") is (state == "planned")
    assert tool["risk_zone"] == {"top": plan["stop"], "bottom": plan["entry"]}  # a short: the stop is above
    assert tool["reward_zone"] == {"top": plan["entry"], "bottom": plan["target"]}
    assert tool["risk_points"] == pytest.approx(plan["stop"] - plan["entry"])

    steps = sent["steps"]
    assert [step["number"] for step in steps] == list(range(1, len(steps) + 1))
    upcoming = [step for step in steps if step["status"] == "next"]
    if state == "triggered":
        # this short reached its target at 00:15: played out, so its entry step is blocked and says why
        assert not upcoming and [step["status"] for step in steps][-1] == "blocked"
        assert {step["status"] for step in steps[:-1]} == {"done"} and "played out" in steps[-1]["detail"]
        return
    assert {"next", "later"} <= {step["status"] for step in steps} and len(upcoming) == 1
    step = upcoming[0]
    assert isinstance(step["price"], float) and f"{step['price']:,.2f}" in step["detail"]
    # the next step's level is on the chart of its timeframe: as its own line, or as the tool's entry
    chart = next(chart for chart in sent["charts"] if chart["timeframe"] == step["timeframe"])
    if chart["tool"] is not None and chart["tool"]["entry_note"]:
        assert chart["tool"]["entry"] == step["price"] and lines["entry"]["names"][0].startswith(chart["tool"]["entry_note"])
    else:
        on_chart = [mark for mark in chart["marks"] if mark["role"] == "next"]
        assert [mark["price"] for mark in on_chart] == [step["price"]] and (step["level_label"] or step["label"]) in on_chart[0]["label"]


@needs_data
def test_loading_the_minute_file_is_timed_apart_from_the_rules(tmp_path: Path) -> None:
    controller = CompanionController(state_path=tmp_path / "ui_state.json")
    core = Core(controller, run_check=inline, run_watch=inline)
    core.begin()
    core.submit(wire.Command("set", dict(MOMENT)))
    core.submit(wire.Command("check"))
    core.step()
    first = core.latest["snapshot"]["timing"]
    core.submit(wire.Command("step", direction=1))
    core.step()
    second = core.latest["snapshot"]["timing"]
    assert core.latest["snapshot"]["view"] is not None
    assert first["load_ms"] > 0 and second["load_ms"] == 0  # the next bar lies inside what was loaded


def shape(value: Any, path: str = "") -> set[str]:
    """Every key path in a JSON value, with the kind of each non-null leaf; list entries are merged."""
    if isinstance(value, dict):
        return {path + "{}"} | {entry for key, item in value.items() for entry in shape(item, f"{path}.{key}")}
    if isinstance(value, list):
        return {path + "[]"} | {entry for item in value for entry in shape(item, path + "[]")}
    if value is None:
        return set()
    kind = "number" if isinstance(value, (int, float)) and not isinstance(value, bool) else type(value).__name__
    return {f"{path}:{kind}"}


# --- values ---------------------------------------------------------------------------


def test_prices_that_are_not_numbers_go_out_as_null() -> None:
    candle = Candle(pd.Timestamp("2026-03-10 09:30", tz="America/New_York"), float("nan"), 2.0, float("inf"), 1.5)
    message = wire.tick("5m", candle, float("nan"))
    text = wire.dumps(message)
    assert json.loads(text)["candle"]["open"] is None and json.loads(text)["last"] is None
    assert json.loads(text)["candle"]["t"] == int(pd.Timestamp("2026-03-10 09:30", tz="UTC").timestamp())
    with pytest.raises(ValueError):
        wire.dumps({"type": "tick", "last": float("nan")})  # nothing slips through unconverted


def test_naive_times_are_new_york_and_carry_its_offset() -> None:
    assert wire.iso(pd.Timestamp("2026-03-10 10:45")) == "2026-03-10T10:45:00-04:00"
    assert wire.iso(pd.Timestamp("2026-01-10 10:45")) == "2026-01-10T10:45:00-05:00"
    assert wire.iso(None) is None
    status = wire.status(LiveStatus("live", "LIVE", False))
    assert status == {"state": "live", "text": "LIVE", "stale": False}


# --- client input ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("not json", "not JSON"),
        ("[1, 2]", "JSON object"),
        ('{"kind": "check"}', "Unknown message type"),
        ('{"type": "explode"}', "Unknown message type"),
        ('{"type": "step"}', "direction"),
        ('{"type": "step", "direction": true}', "direction"),
        ('{"type": "step", "direction": 2}', "direction"),
        ('{"type": "pause", "paused": "yes"}', "paused"),
        ('{"type": "set"}', "at least one"),
        ('{"type": "set", "symbol": 5}', "string"),
        ('{"type": "set", "side": null}', "string"),
        ('{"type": "set", "colour": "red"}', "does not take: colour"),
        ('{"type": "check", "now": true}', "does not take: now"),
        (b"\xff\xfe", "UTF-8"),
        # the id keeps pytest from putting 100,000 characters in an environment variable (Windows refuses)
        pytest.param("[" * 100_000, "not JSON", id="deeply-nested-brackets"),
    ],
)
def test_messages_that_cannot_be_used_are_refused_with_a_reason(text: str | bytes, reason: str) -> None:
    with pytest.raises(wire.WireError) as caught:
        wire.parse_command(text)
    assert reason in str(caught.value)


def test_commands_are_read_as_the_contract_writes_them() -> None:
    assert wire.parse_command('{"type": "set", "symbol": "ES", "when": "2026-03-10 10:00"}') == wire.Command("set", {"symbol": "ES", "when": "2026-03-10 10:00"})
    assert wire.parse_command('{"type": "set", "side": ""}') == wire.Command("set", {"side": ""})
    assert wire.parse_command('{"type": "step", "direction": -1}') == wire.Command("step", direction=-1)
    assert wire.parse_command('{"type": "pause", "paused": false}') == wire.Command("pause", paused=False)
    assert [wire.parse_command(json.dumps({"type": kind})).type for kind in ("check", "latest", "use_history")] == ["check", "latest", "use_history"]
