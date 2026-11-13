"""The companion window's logic, tested without a display.

Only ``companion.app_model`` is exercised: the Tk widgets in ``companion.app`` hold no
decisions. Bars come from the in-memory scenarios, never from the CSV files.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from companion import app_model
from companion.app_model import (
    CUSTOM_CHOICE,
    Candle,
    ChartMark,
    ChartView,
    CheckRequest,
    CompanionController,
    UiState,
    UserError,
    build_charts,
    chart_price_range,
    chart_window,
    format_when,
    load_state,
    nice_ticks,
    present,
    save_state,
    step_moment,
)
from companion.bars import HISTORICAL_SOURCE_NOTE, bar_close_times
from companion.timeframes import get_stack, make_stack
from companion.types import CriterionResult, MarkupItem, PlanStep, PositionPlan, ReadStep, TimeframeStack, Verdict
from ttrades_scenarios import _SWING_SLOT, SYMBOL, continuation_scenario, reversal_scenario

DAILY = get_stack("1D / 1h / 5m")


def make_controller(tmp_path: Path, **kwargs: object) -> CompanionController:
    kwargs.setdefault("coverage", lambda symbol: None)
    return CompanionController(state_path=tmp_path / "state" / "ui_state.json", **kwargs)  # type: ignore[arg-type]


def sample_verdict(**changes: object) -> Verdict:
    criteria = (
        CriterionResult("data_ok", "Enough history", True, "71 bars", None, "shared", "gate"),
        CriterionResult("stack_ok", "Stack is taught", True, "stated", None, "shared", "advisory"),
        CriterionResult("cont_gate", "Bias closed with a direction", True, "case A", "1D", "continuation c1", "gate"),
        CriterionResult("cont_trigger", "Entry trigger has formed", False, "waiting", "5m", "continuation c4", "step"),
        CriterionResult("rev_taken", "Ran the previous high", True, "taken", "1D", "reversal c1", "step"),
        CriterionResult("rev_note", "Wick formed early", None, "Not evaluated", "1D", "reversal c1", "advisory"),
        CriterionResult("rev_trigger", "Entry trigger has formed", None, "Not evaluated", "5m", "reversal c4", "step"),
    )
    values: dict[str, object] = dict(
        style="ttrades", symbol="NQ", as_of=pd.Timestamp("2026-02-18 10:15", tz="America/New_York").to_pydatetime(),
        stack=DAILY, decision="long", bias="bullish", path_family="continuation", stage="c4", criteria=criteria,
        entry=100.0, stop=98.0, targets=(104.0, 109.0), invalidation="Invalid below 98.00.", summary="Long at c4.",
    )  # fmt: skip
    values.update(changes)
    return Verdict(**values)  # type: ignore[arg-type]


# --- drop-downs come from the registries ------------------------------------------


def test_choices_come_from_the_registries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    invented = [TimeframeStack("Swing", "1W", "1D", "4h"), TimeframeStack("Scalp", "30m", "3m", "1m")]
    monkeypatch.setattr("companion.timeframes.list_stacks", lambda path=None: list(invented))
    monkeypatch.setattr("companion.timeframes.default_stack", lambda path=None: invented[1])
    monkeypatch.setattr("companion.timeframes.available_timeframes", lambda path=None: ["3m", "30m", "1D"])
    monkeypatch.setattr("companion.styles.base.list_styles", lambda: ["alpha", "zeta"])
    monkeypatch.setattr("companion.bars.SUPPORTED_SYMBOLS", ("CL", "NQ"))

    controller = make_controller(tmp_path)

    assert controller.stack_choices() == ["Swing", "Scalp", CUSTOM_CHOICE]
    assert controller.timeframe_choices() == ["3m", "30m", "1D"]
    assert controller.style_choices() == ["alpha", "zeta"]
    assert controller.symbols() == ["CL", "NQ"]
    # a fresh window preselects the configured default stack and an offered style / symbol
    assert controller.state.stack == "Scalp"
    assert controller.state.style == "alpha"
    assert controller.state.symbol == "CL"
    assert controller.resolve_stack() == invented[1]


def test_real_default_stack_is_preselected(tmp_path: Path) -> None:
    controller = make_controller(tmp_path)
    assert controller.state.stack == DAILY.name
    assert controller.resolve_stack() == DAILY
    assert CUSTOM_CHOICE in controller.stack_choices()


# --- stack selection --------------------------------------------------------------


def test_custom_stack_is_built_through_make_stack(tmp_path: Path) -> None:
    controller = make_controller(tmp_path)
    controller.state.stack = CUSTOM_CHOICE
    controller.state.custom_bias, controller.state.custom_setup, controller.state.custom_entry = "4h", "30m", "3m"
    assert controller.is_custom
    assert controller.resolve_stack() == make_stack("4h", "30m", "3m")
    assert controller.stack_problem() == ""


def test_invalid_custom_stack_gives_a_plain_message(tmp_path: Path) -> None:
    controller = make_controller(tmp_path)
    controller.state.stack = CUSTOM_CHOICE
    controller.state.custom_bias, controller.state.custom_setup, controller.state.custom_entry = "5m", "1h", "1D"
    with pytest.raises(UserError) as caught:
        controller.resolve_stack()
    message = str(caught.value)
    assert "5m / 1h / 1D" in message and "bias the largest" in message
    assert "Traceback" not in message and "ValueError" not in message
    assert controller.stack_problem() == message
    with pytest.raises(UserError):
        controller.build_request()  # an invalid stack never reaches the engine

    controller.state.custom_entry = ""
    assert "all three" in controller.stack_problem()


def test_a_stack_removed_from_the_config_falls_back_to_the_default(tmp_path: Path) -> None:
    path = tmp_path / "ui_state.json"
    save_state(UiState(stack="9h / 2h / 7m", style="gone", symbol="ZZ", custom_bias="7h"), path)
    controller = CompanionController(state_path=path, coverage=lambda symbol: None)
    assert controller.state.stack == DAILY.name
    assert controller.state.style in controller.style_choices()
    assert controller.state.symbol in controller.symbols()
    assert controller.state.custom_bias in controller.timeframe_choices()


# --- verdict -> rows ---------------------------------------------------------------


def test_verdict_rows_are_grouped_in_style_order() -> None:
    view = present(sample_verdict())
    assert [group.name for group in view.groups] == ["shared", "continuation c1", "continuation c4", "reversal c1", "reversal c4"]
    assert view.groups[0].title == "SHARED"
    shared = view.groups[0]
    assert [row.key for row in shared.rows] == ["data_ok", "stack_ok"]
    assert (shared.passed, shared.failed, shared.not_evaluated) == (2, 0, 0)
    reversal = view.groups[3]
    assert [(row.status, row.mark) for row in reversal.rows] == [("pass", "PASS"), ("na", "N/A")]
    assert reversal.tally == "1 of 2 passed, 1 not evaluated"
    trigger = view.groups[2].rows[0]
    assert (trigger.status, trigger.mark, trigger.label, trigger.detail, trigger.tags) == (
        "fail", "FAIL", "Entry trigger has formed", "waiting", "step · 5m",
    )  # fmt: skip


def test_decision_levels_and_context() -> None:
    view = present(sample_verdict())
    assert (view.decision_word, view.tone) == ("TRADE LONG", "long")
    assert (view.bias, view.path, view.stage) == ("BULLISH", "CONTINUATION", "C4")
    assert view.headline == "NQ  ·  2026-02-18 10:15 New York  ·  1D / 1h / 5m  ·  ttrades"
    assert [(level.name, level.price, level.note) for level in view.levels] == [
        ("Entry", "100.00", ""),
        ("Stop", "98.00", "risk 2.00"),
        ("Target 1", "104.00", "2.00R"),
        ("Target 2", "109.00", "4.50R"),
    ]
    assert view.invalidation == "Invalid below 98.00." and view.summary == "Long at c4."

    waiting = present(sample_verdict(decision="no_trade", path_family="none", stage="none", entry=None, stop=None, targets=()))
    assert (waiting.decision_word, waiting.tone, waiting.path, waiting.stage) == ("DON'T TRADE", "no_trade", "—", "—")
    assert waiting.levels == () and not waiting.has_levels
    # every decision the contract allows has its own wording; the verdict's own value is untouched
    words = {name: present(sample_verdict(decision=name)) for name in ("long", "short", "watch", "no_trade")}
    assert {name: view.decision_word for name, view in words.items()} == {
        "long": "TRADE LONG", "short": "TRADE SHORT", "watch": "WATCH", "no_trade": "DON'T TRADE",
    }  # fmt: skip
    assert all(view.decision == name for name, view in words.items())
    # an unknown one still shows a word
    unknown = present(sample_verdict(decision="stand_aside"))
    assert (unknown.decision_word, unknown.tone) == ("STAND ASIDE", "neutral")


def test_inactive_path_groups_collapse_and_can_be_reopened() -> None:
    view = present(sample_verdict())
    state = {group.name: (group.active, group.collapsed) for group in view.groups}
    assert state == {
        "shared": (True, False),
        "continuation c1": (True, False),
        "continuation c4": (True, False),
        "reversal c1": (False, True),
        "reversal c4": (False, True),
    }
    flipped = present(sample_verdict(path_family="reversal"))
    assert [group.name for group in flipped.groups if not group.active] == ["continuation c1", "continuation c4"]

    assert not any(group.collapsed for group in present(sample_verdict(), collapse_inactive=False).groups)
    by_hand = present(sample_verdict(), collapsed={"reversal c1": False, "shared": True})
    assert {group.name for group in by_hand.groups if group.collapsed} == {"shared", "reversal c4"}
    # with no path in play nothing is treated as dead
    assert all(group.active for group in present(sample_verdict(path_family="none")).groups)


def test_advisory_rows_can_be_hidden() -> None:
    shown = present(sample_verdict())
    assert [row.key for group in shown.groups for row in group.rows if row.advisory] == ["stack_ok", "rev_note"]
    hidden = present(sample_verdict(), hide_advisory=True)
    assert hidden.hidden_advisory == 2
    assert not any(row.advisory for group in hidden.groups for row in group.rows)
    assert [row.key for row in hidden.groups[0].rows] == ["data_ok"]

    only_advisory = sample_verdict(criteria=(CriterionResult("a", "A", True, "d", None, "notes", "advisory"),))
    assert present(only_advisory, hide_advisory=True).groups == ()  # an emptied group disappears


# --- time stepping ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("start", "timeframe", "direction", "expected"),
    [
        ("2026-02-18 10:15", "5m", 1, "2026-02-18 10:20"),
        ("2026-02-18 10:15", "5m", -1, "2026-02-18 10:10"),
        ("2026-02-18 10:17", "5m", 1, "2026-02-18 10:20"),  # off the grid: snap to the next close
        ("2026-02-18 10:17", "5m", -1, "2026-02-18 10:15"),
        ("2026-02-18 10:15", "1m", 1, "2026-02-18 10:16"),
        ("2026-02-18 10:15", "1h", 1, "2026-02-18 11:00"),
        ("2026-02-18 10:15", "4h", 1, "2026-02-18 14:00"),  # 4h bars open at 18, 22, 02, 06, 10, 14
        ("2026-02-18 10:15", "4h", -1, "2026-02-18 10:00"),
        ("2026-02-18 17:00", "5m", 1, "2026-02-18 18:05"),  # over the daily break
        ("2026-02-18 18:05", "5m", -1, "2026-02-18 17:00"),
        ("2026-02-20 17:00", "5m", 1, "2026-02-22 18:05"),  # Friday close -> Sunday evening
        ("2026-02-22 18:05", "5m", -1, "2026-02-20 17:00"),
        ("2026-02-20 17:00", "1h", 1, "2026-02-22 19:00"),
        ("2026-02-18 10:15", "1D", 1, "2026-02-18 18:00"),
        ("2026-02-20 18:00", "1D", 1, "2026-02-23 18:00"),  # no daily bar closes on Saturday or Sunday
        ("2026-02-23 18:00", "1D", -1, "2026-02-20 18:00"),
    ],
)
def test_step_moment(start: str, timeframe: str, direction: int, expected: str) -> None:
    assert format_when(step_moment(pd.Timestamp(start), timeframe, direction)) == expected


def test_stepping_uses_the_entry_timeframe_of_the_selected_stack(tmp_path: Path) -> None:
    controller = make_controller(tmp_path)
    controller.state.when = "2026-02-18 10:00"
    controller.state.stack = "1D / 1h / 5m"
    assert controller.step(1) == "2026-02-18 10:05"
    controller.state.stack = "1W / 4h / 15m"
    assert controller.step(1) == "2026-02-18 10:15"
    controller.state.stack = CUSTOM_CHOICE
    controller.state.custom_bias, controller.state.custom_setup, controller.state.custom_entry = "1D", "4h", "1h"
    assert controller.step(-1) == "2026-02-18 10:00"
    assert controller.state.when == "2026-02-18 10:00"

    controller.state.custom_entry = "1W"  # not a usable stack: stepping says so, time stays put
    with pytest.raises(UserError):
        controller.step(1)
    assert controller.state.when == "2026-02-18 10:00"


def test_time_defaults_to_and_stops_at_the_end_of_the_data(tmp_path: Path) -> None:
    covered = (pd.Timestamp("2021-01-03 18:00"), pd.Timestamp("2026-03-04 19:00"))
    controller = make_controller(tmp_path, coverage=lambda symbol: covered)
    assert controller.state.when == "2026-03-04 19:00"  # nothing saved: the last moment covered

    with pytest.raises(UserError, match="end of the NQ data"):
        controller.step(1)
    assert controller.step(-1) == "2026-03-04 18:55"
    assert controller.step(1) == "2026-03-04 19:00"

    controller.state.when = "2026-03-09 10:00"
    with pytest.raises(UserError, match="data ends at 2026-03-04 19:00"):
        controller.build_request()
    assert controller.jump_to_latest() == "2026-03-04 19:00"
    assert controller.build_request().when == covered[1]

    controller.state.when = "2020-06-01 10:00"
    with pytest.raises(UserError, match="data starts at"):
        controller.build_request()


def test_unreadable_time_is_reported_in_plain_words(tmp_path: Path) -> None:
    controller = make_controller(tmp_path)
    for typed in ("half past ten", ""):
        controller.state.when = typed
        with pytest.raises(UserError) as caught:
            controller.build_request()
        assert "2026-02-18 10:15" in str(caught.value)  # shows the form to use


# --- state ------------------------------------------------------------------------


def test_state_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "home" / ".trading_companion" / "ui_state.json"
    first = CompanionController(state_path=path, coverage=lambda symbol: None)
    first.state.symbol = "ES"
    first.state.stack = CUSTOM_CHOICE
    first.state.custom_bias, first.state.custom_setup, first.state.custom_entry = "4h", "15m", "1m"
    first.state.when = "2025-11-12 10:45"
    first.state.hide_advisory = True
    first.state.collapse_inactive = False
    first.state.show_details = False
    first.state.geometry = "1200x900+10+10"
    assert first.save() is True
    assert json.loads(path.read_text(encoding="utf-8"))["symbol"] == "ES"

    second = CompanionController(state_path=path, coverage=lambda symbol: None)
    assert second.state == first.state
    assert second.resolve_stack() == make_stack("4h", "15m", "1m")


def test_state_path_follows_the_home_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(app_model.STATE_DIR_ENV, str(tmp_path / "elsewhere"))
    assert CompanionController(coverage=lambda symbol: None).state_path == tmp_path / "elsewhere" / "ui_state.json"
    monkeypatch.delenv(app_model.STATE_DIR_ENV)
    assert app_model.state_dir() == Path.home() / ".trading_companion"


@pytest.mark.parametrize("content", ["{ not json", "[1, 2]", '{"symbol": 7, "hide_advisory": "yes", "unknown": 1}'])
def test_damaged_state_file_gives_defaults(tmp_path: Path, content: str) -> None:
    path = tmp_path / "ui_state.json"
    path.write_text(content, encoding="utf-8")
    assert load_state(path) == UiState()
    assert load_state(tmp_path / "missing.json") == UiState()


# --- running a check --------------------------------------------------------------


def test_check_runs_the_engine_on_the_shared_source(tmp_path: Path) -> None:
    scenario = continuation_scenario(DAILY)
    source = scenario.source()
    controller = make_controller(tmp_path, source=source)
    controller.state.symbol = SYMBOL
    controller.state.stack = DAILY.name
    controller.state.style = "ttrades"
    controller.state.when = format_when(scenario.times["trigger"].tz_localize(None))

    request = controller.build_request()
    assert request == CheckRequest(SYMBOL, scenario.times["trigger"].tz_localize(None), DAILY, "ttrades")
    outcome = controller.run_check(request)
    assert outcome.ok and outcome.error == ""
    assert controller.source is source  # one source for the session, reused by the next check

    view = controller.present(outcome)
    assert (outcome.verdict.decision, view.decision_word) == ("long", "TRADE LONG")
    assert view.headline.startswith(f"{SYMBOL}  ·  {controller.state.when} New York")
    assert sum(len(group.rows) for group in view.groups) == len(outcome.verdict.criteria)
    assert [group.name for group in view.groups] == list(dict.fromkeys(item.group for item in outcome.verdict.criteria))
    assert view.has_levels == (outcome.verdict.entry is not None)

    earlier = controller.step(-1)  # walking the session candle by candle re-uses the same bars
    assert earlier == format_when(scenario.times["trigger"].tz_localize(None) - pd.Timedelta(minutes=5))
    assert controller.run_check(controller.build_request()).ok


def test_check_passes_the_selection_to_analyze(tmp_path: Path) -> None:
    calls: list[tuple[object, ...]] = []

    def fake_analyze(symbol: str, as_of: str, stack: TimeframeStack, style: str, source: object) -> Verdict:
        calls.append((symbol, as_of, stack, style, source))
        return sample_verdict()

    marker = object()
    controller = make_controller(tmp_path, source=marker, analyze_fn=fake_analyze)
    controller.state.symbol, controller.state.when = "ES", "2026-02-18 10:15"
    outcome = controller.run_check(controller.build_request())
    assert outcome.ok
    assert calls == [("ES", "2026-02-18 10:15", DAILY, controller.state.style, marker)]
    assert controller.will_load(outcome.request) is False  # a source that cannot say is not announced as loading


@pytest.mark.parametrize(
    ("raised", "expected"),
    [
        (ValueError("Unknown symbol 'XX'; supported: NQ, ES, GC"), "The check could not run: Unknown symbol 'XX'; supported: NQ, ES, GC"),
        (KeyError("No style named 'nope'"), "The check could not run: No style named 'nope'"),
    ],
)
def test_expected_engine_errors_become_sentences(tmp_path: Path, raised: Exception, expected: str) -> None:
    def failing(*args: object) -> Verdict:
        raise raised

    controller = make_controller(tmp_path, analyze_fn=failing)
    outcome = controller.run_check(controller.build_request())
    assert not outcome.ok and outcome.verdict is None
    assert outcome.error == expected
    with pytest.raises(ValueError):
        controller.present(outcome)


def test_unexpected_error_is_readable_and_logged(tmp_path: Path) -> None:
    def failing(*args: object) -> Verdict:
        raise RuntimeError("index 3 is out of bounds\nsecond line")

    controller = make_controller(tmp_path, analyze_fn=failing)
    outcome = controller.run_check(controller.build_request())  # does not raise
    assert not outcome.ok
    assert "Something went wrong while checking" in outcome.error and "index 3 is out of bounds" in outcome.error
    assert "Traceback" not in outcome.error and "second line" not in outcome.error
    log = controller.state_path.parent / app_model.ERROR_LOG_NAME
    assert "RuntimeError" in log.read_text(encoding="utf-8")  # the traceback is kept for whoever supports the tool


def test_missing_data_file_is_explained(tmp_path: Path) -> None:
    def failing(*args: object) -> Verdict:
        raise FileNotFoundError(2, "No such file", "C:/data/nq_minute.csv")

    outcome = make_controller(tmp_path, analyze_fn=failing).run_check(
        CheckRequest("NQ", pd.Timestamp("2026-02-18 10:15"), DAILY, "ttrades")
    )
    assert outcome.error == "No historical data found for NQ (looked for C:/data/nq_minute.csv)."


def test_unreliable_data_is_flagged(tmp_path: Path) -> None:
    controller = make_controller(tmp_path)
    when = pd.Timestamp("2026-02-18 10:15")
    assert controller.notes_for(CheckRequest("NQ", when, DAILY, "ttrades")) == ()
    assert controller.notes_for(CheckRequest("GC", when, get_stack("1M / 1D / 1h"), "ttrades")) == ()
    (note,) = controller.notes_for(CheckRequest("GC", when, DAILY, "ttrades"))
    assert "only reliable at 1h and above" in note and "5m" in note


def test_model_needs_no_display() -> None:
    assert "tkinter" not in Path(app_model.__file__).read_text(encoding="utf-8")


# --- the top-down read -------------------------------------------------------------


def told(stack: TimeframeStack, order: tuple[str, ...] = ("bias", "setup", "entry")) -> tuple[ReadStep, ...]:
    return tuple(ReadStep(role, getattr(stack, role), "confirmed", f"{role} headline", f"{role} reason.") for role in order)


@pytest.mark.parametrize("stack", [DAILY, get_stack("4h / 15m / 1m"), make_stack("1W", "1D", "30m")], ids=lambda stack: stack.name)
def test_read_is_passed_through_highest_timeframe_first(stack: TimeframeStack) -> None:
    verdict = sample_verdict(stack=stack, read=told(stack), why="Because.", waiting_for="A close.")
    view = present(verdict)
    assert [(row.role, row.timeframe) for row in view.read] == [("bias", stack.bias), ("setup", stack.setup), ("entry", stack.entry)]
    assert [(row.headline, row.reason) for row in view.read] == [(step.headline, step.reason) for step in verdict.read]
    assert (view.why, view.waiting_for) == ("Because.", "A close.")
    # a style that hands the steps over in another order is still shown top down
    shuffled = present(sample_verdict(stack=stack, read=told(stack, ("entry", "bias", "setup"))))
    assert [row.timeframe for row in shuffled.read] == [stack.bias, stack.setup, stack.entry]


def test_read_status_is_shown_as_a_word_as_well() -> None:
    steps = tuple(ReadStep("bias", "1D", status, "h", "r") for status in ("confirmed", "waiting", "failed", "not_applicable"))
    assert [row.word for row in present(sample_verdict(read=steps)).read] == ["Confirmed", "Waiting", "Failed", "Not read"]
    assert present(sample_verdict()).read == ()  # a style without a read: nothing invented


def checked(tmp_path: Path, scenario: object, moment: str, **source_kwargs: object):  # type: ignore[no-untyped-def]
    source = scenario.source(**source_kwargs)  # type: ignore[attr-defined]
    controller = make_controller(tmp_path, source=source)
    controller.state.symbol = SYMBOL
    controller.state.stack = scenario.stack.name  # type: ignore[attr-defined]
    controller.state.style = "ttrades"
    controller.state.when = format_when(scenario.times[moment].tz_localize(None))  # type: ignore[attr-defined]
    outcome = controller.run_check(controller.build_request())
    assert outcome.ok, outcome.error
    return controller, outcome


def test_summary_tells_only_the_path_in_play(tmp_path: Path) -> None:
    controller, outcome = checked(tmp_path, continuation_scenario(DAILY), "trigger")
    view = controller.present(outcome)
    summary = " ".join([view.why, view.waiting_for, *(f"{row.headline} {row.reason}" for row in view.read)])
    assert view.decision_word == "TRADE LONG" and [row.status for row in view.read] == ["confirmed"] * 3
    assert "reversal" not in summary.lower() and "key level" not in summary
    assert not any(code in summary.split() for code in ("c1", "c2", "c3", "c4"))
    # the same holds the other way round
    controller, outcome = checked(tmp_path, reversal_scenario(DAILY), "trigger")
    view = controller.present(outcome)
    summary = " ".join([view.why, *(f"{row.headline} {row.reason}" for row in view.read)])
    assert outcome.verdict.path_family == "reversal" and "point of interest" not in summary


def test_details_list_is_still_there_and_still_filterable(tmp_path: Path) -> None:
    controller, outcome = checked(tmp_path, continuation_scenario(DAILY), "trigger")
    view = controller.present(outcome)
    assert sum(len(group.rows) for group in view.groups) == len(outcome.verdict.criteria)
    folded = {group.name for group in view.groups if group.collapsed}
    assert folded and all(name.startswith("reversal") for name in folded)  # only the path in play is open by default
    controller.state.hide_advisory = True
    controller.state.collapse_inactive = False
    opened = controller.present(outcome)
    assert opened.hidden_advisory > 0 and not any(group.collapsed for group in opened.groups)
    assert not any(row.advisory for group in opened.groups for row in group.rows)
    assert view.summary == outcome.verdict.summary and view.invalidation == outcome.verdict.invalidation


def test_source_note_comes_from_the_bar_source(tmp_path: Path) -> None:
    controller, outcome = checked(tmp_path, continuation_scenario(DAILY), "trigger")
    assert controller.present(outcome).source_note == HISTORICAL_SOURCE_NOTE
    assert "not live" in HISTORICAL_SOURCE_NOTE

    class LiveFeed:
        description = "Live TradingView bars"

        def get_bars(self, symbol: str, timeframe: str, as_of: object, lookback: int) -> pd.DataFrame:
            raise AssertionError("not used")

    assert make_controller(tmp_path, source=LiveFeed()).source_note() == "Live TradingView bars"
    assert make_controller(tmp_path, source=object()).source_note() == "Bars from object"


# --- charts ----------------------------------------------------------------------


@pytest.mark.parametrize("stack", [DAILY, get_stack("4h / 15m / 1m")], ids=lambda stack: stack.name)
def test_charts_run_highest_timeframe_first_and_never_past_the_analysis_time(tmp_path: Path, stack: TimeframeStack) -> None:
    scenario = continuation_scenario(stack, with_aftermath=True)  # the minute data runs on well past the trigger
    moment = scenario.times["trigger"]
    controller, outcome = checked(tmp_path, scenario, "trigger")
    charts = outcome.charts
    assert [(chart.role, chart.timeframe) for chart in charts] == [("bias", stack.bias), ("setup", stack.setup), ("entry", stack.entry)]
    entry = controller.source.get_bars(SYMBOL, stack.entry, moment, 10_000)
    for chart in charts:
        closed = [candle for candle in chart.candles if not candle.forming]
        frame = pd.DataFrame(index=pd.DatetimeIndex([candle.time for candle in closed]))
        assert (bar_close_times(frame, chart.timeframe) <= moment).all()  # every closed candle had closed by then
        assert [candle.forming for candle in chart.candles].count(True) <= 1
        assert all(candle.time < moment for candle in chart.candles)
    bias, setup, entry_chart = charts
    assert not any(candle.forming for candle in entry_chart.candles)
    assert entry_chart.candles[-1].time == entry.index[-1]
    # the forming bias candle is exactly the aggregate of the closed entry bars inside it: 97.5 open, 98.0 high, 91.0 low
    forming = bias.candles[-1]
    inside = entry[entry.index >= forming.time]
    closed_bias = pd.DataFrame(index=pd.DatetimeIndex([candle.time for candle in bias.candles[:-1]]))
    assert forming.forming and forming.time == bar_close_times(closed_bias, stack.bias)[-1]  # it opens where the last one closed
    assert (forming.open, forming.high, forming.low, forming.close) == (
        pytest.approx(97.5), pytest.approx(inside["high"].max()), pytest.approx(inside["low"].min()), pytest.approx(97.7),
    )  # fmt: skip
    assert forming.high == pytest.approx(98.0) and forming.low == pytest.approx(91.0)  # not the 120 / 79 that come later
    # the forming setup candle likewise: the three entry candles of the slot after the swing candle
    assert setup.candles[-1].forming and setup.candles[-1].low == pytest.approx(95.5)
    assert setup.candles[-1].high == pytest.approx(97.9)


def test_markup_items_go_to_the_chart_of_their_timeframe(tmp_path: Path) -> None:
    scenario = continuation_scenario(DAILY)
    controller, outcome = checked(tmp_path, scenario, "trigger")
    view = controller.present(outcome)
    bias, setup, entry = view.charts
    labels = {chart.role: {mark.title for mark in chart.marks} for chart in view.charts}
    assert {"Previous bias candle high", "Previous bias candle low", "Previous bias candle equilibrium"} <= labels["bias"]
    assert {"Setup swing low", "Setup closure (Candle 2 closure)", "Respect level on the setup timeframe"} <= labels["setup"]
    assert {"Entry CISD", "Entry trigger"} <= labels["entry"]
    # entry, stop and target are drawn once, by the risk / reward tool, not as three more lines
    assert not {"Entry", "Stop", "Target 1"} & labels["entry"] and entry.tool is not None
    shared = {item.label for item in outcome.verdict.markup if item.shared}
    for chart in view.charts:  # from another timeframe, only the shared levels the whole chain is read against
        wanted = {item.label for item in outcome.verdict.markup if item.timeframe == chart.timeframe} | shared
        assert {mark.title for mark in chart.marks} <= wanted
    # the same levels, under the same names, on all three charts: the chain reads as one idea
    for price in (105.0, 88.0):  # PDH and the respect level (the wick midpoint here)
        names = {mark.label for chart in view.charts for mark in chart.marks if mark.kind == "level" and mark.price == pytest.approx(price)}
        assert len(names) == 1, (price, names)
    # the protected low is a line on the bias and setup charts; on the entry chart the risk / reward tool's stop is that line
    assert all(any(m.title == "Protected low (stop swing)" for m in chart.marks) for chart in (bias, setup))
    assert entry.tool.stop == pytest.approx(91.0)
    assert next(m.label for m in bias.marks if m.title == "Previous bias candle high") == "PDH"
    # the bias swing's candles carry their numbers on the bias chart only
    assert {"Bias Candle 1", "Bias Candle 2"} <= labels["bias"] and not {"Bias Candle 1", "Bias Candle 2"} & labels["setup"]
    assert "Forming bias candle open" not in labels["bias"]  # context a chart leaves out
    # a marked candle is the one the style named: the CISD marker sits on the candle that closed at 97.40
    cisd = next(mark for mark in entry.marks if mark.title == "Entry CISD")
    assert entry.candles[cisd.start].close == pytest.approx(97.4)
    assert entry.candles[cisd.start].time == next(item.start for item in outcome.verdict.markup if item.label == "Entry CISD")
    trigger = next(mark for mark in entry.marks if mark.title == "Entry trigger")
    assert entry.candles[trigger.start].close == pytest.approx(outcome.verdict.entry)
    # the tool carries the prices of the verdict
    assert (entry.tool.entry, entry.tool.stop, entry.tool.target) == (
        pytest.approx(outcome.verdict.entry), pytest.approx(outcome.verdict.stop), pytest.approx(outcome.verdict.targets[0]),
    )  # fmt: skip
    # each chart is headed with the read's line for its timeframe
    assert [(chart.status, chart.headline) for chart in view.charts] == [(row.status, row.headline) for row in view.read]
    assert view.last is not None and view.last.price == "97.70" and "R from entry" in view.last.note


def test_chart_marks_are_placed_on_candles_by_time() -> None:
    scenario = continuation_scenario(DAILY)
    moment = scenario.times["trigger"]
    first = scenario.source().get_bars(SYMBOL, "5m", moment, 4).index[0]  # the open of a candle that is on the chart
    items = (
        MarkupItem("marker", "Old", "5m", price=1.0, start=moment - pd.Timedelta(days=30)),  # before the candles shown
        MarkupItem("marker", "Now", "5m", price=97.0, start=first, role="confirm", short="CISD"),
        MarkupItem("level", "Line", "5m", price=97.0, start=moment - pd.Timedelta(days=30)),
        MarkupItem("level", "Other frame", "1h", price=97.0),
        MarkupItem("level", "Hidden", "5m", price=97.0, role="info"),
        MarkupItem("zone", "Box", "5m", top=98.0, bottom=96.0, end=first),
    )
    entry = build_charts(scenario.source(), SYMBOL, DAILY, moment, items, bars=20)[2]
    marks = {mark.title: mark for mark in entry.marks}
    assert set(marks) == {"Now", "Line", "Box"}
    assert entry.candles[marks["Now"].start].time == first and marks["Now"].label == "CISD"
    assert marks["Line"].start is None and marks["Line"].role == "reference"  # began before the first candle: drawn from the edge
    assert entry.candles[marks["Box"].end].time == first


def test_chart_zoom_keeps_what_was_marked_in_view() -> None:
    candles = tuple(Candle(pd.Timestamp("2026-02-18 09:00") + pd.Timedelta(minutes=5 * index), 100, 101, 99, 100.5) for index in range(100))
    plain = ChartView("entry", "5m", candles, ())
    assert chart_window(plain, 40) == 60  # the last 40 candles
    assert chart_window(ChartView("entry", "5m", candles[:10], ()), 40) == 0
    marked = ChartView("entry", "5m", candles, (ChartMark("marker", "confirm", "CISD", "CISD", price=100.0, start=30),))
    assert chart_window(marked, 40, 80) <= 30  # reaches back to the marked candle
    assert chart_window(ChartView("entry", "5m", candles, (ChartMark("marker", "confirm", "x", "x", price=1.0, start=2),)), 40, 80) == 20

    low, high = chart_price_range(plain)
    assert low < 99 and high > 101
    plan = ChartView("entry", "5m", candles, (
        ChartMark("level", "target", "Target 1", "Target 1", price=140.0),
        ChartMark("level", "stop", "Stop", "Stop", price=90.0),
        ChartMark("level", "reference", "Far", "Far", price=500.0),
        ChartMark("level", "reference", "Near", "Near", price=103.0),
        ChartMark("zone", "poi", "Gap", "Gap", top=400.0, bottom=101.5),
    ))  # fmt: skip
    low, high = chart_price_range(plan)
    assert low < 90 and 140 < high < 400  # the plan and near levels are in view; a far reference and a far zone edge are not
    assert nice_ticks(24_400, 25_300, 5) == [24_400, 24_600, 24_800, 25_000, 25_200]
    assert nice_ticks(5, 5) == []


def test_a_chart_fault_does_not_cost_the_verdict(tmp_path: Path) -> None:
    scenario = continuation_scenario(DAILY)

    class NoBars:
        def get_bars(self, *args: object) -> pd.DataFrame:
            raise RuntimeError("feed down")

    def analyze(symbol: str, when: str, stack: TimeframeStack, style: str, source: object) -> Verdict:
        return sample_verdict()

    controller = make_controller(tmp_path, source=NoBars(), analyze_fn=analyze)
    controller.state.symbol, controller.state.when = SYMBOL, format_when(scenario.times["trigger"].tz_localize(None))
    outcome = controller.run_check(controller.build_request())
    assert outcome.ok and outcome.charts == () and "could not be drawn" in outcome.chart_problem
    view = controller.present(outcome)
    assert view.decision_word == "TRADE LONG" and view.charts == () and view.chart_problem


# --- the bias selector --------------------------------------------------------------


def test_bias_selection_is_remembered_and_cleaned(tmp_path: Path) -> None:
    path = tmp_path / "home" / "ui_state.json"
    first = CompanionController(state_path=path, coverage=lambda symbol: None)
    assert first.state.direction == "" and first.side_choices() == [("", "Auto"), ("long", "Long"), ("short", "Short")]
    first.set_direction("Long")  # a label or a value
    assert first.state.direction == "long" and first.save()
    assert CompanionController(state_path=path, coverage=lambda symbol: None).state.direction == "long"
    first.set_direction("short")
    assert first.state.direction == "short"
    first.set_direction("Auto")
    assert first.state.direction == ""
    first.set_direction("sideways")  # anything else is Auto
    assert first.state.direction == ""
    path.write_text(json.dumps({"direction": "up"}), encoding="utf-8")
    assert CompanionController(state_path=path, coverage=lambda symbol: None).state.direction == ""


def test_bias_selection_is_passed_to_the_engine(tmp_path: Path) -> None:
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def fake_analyze(*args: object, **kwargs: object) -> Verdict:
        calls.append((args, kwargs))
        return sample_verdict()

    controller = make_controller(tmp_path, source=object(), analyze_fn=fake_analyze)
    controller.state.symbol, controller.state.when = "ES", "2026-02-18 10:15"
    for side in ("", "long", "short"):
        controller.set_direction(side)
        request = controller.build_request()
        assert request.direction == side
        assert controller.run_check(request).ok
    assert [kwargs for _args, kwargs in calls] == [{}, {"direction": "long"}, {"direction": "short"}]
    assert all(len(args) == 5 for args, _kwargs in calls)


def checked_side(tmp_path: Path, scenario: object, moment: object, side: str = ""):  # type: ignore[no-untyped-def]
    source = scenario.source()  # type: ignore[attr-defined]
    controller = make_controller(tmp_path, source=source)
    controller.state.symbol = SYMBOL
    controller.state.stack = scenario.stack.name  # type: ignore[attr-defined]
    controller.state.style = "ttrades"
    when = scenario.times[moment] if isinstance(moment, str) else moment  # type: ignore[attr-defined]
    controller.state.when = format_when(when.tz_localize(None))
    controller.set_direction(side)
    outcome = controller.run_check(controller.build_request())
    assert outcome.ok, outcome.error
    return controller, outcome, controller.present(outcome)


@pytest.mark.parametrize("stack", [DAILY, get_stack("4h / 15m / 1m")], ids=lambda stack: stack.name)
def test_a_forced_side_reaches_the_style_and_comes_back_in_the_view(tmp_path: Path, stack: TimeframeStack) -> None:
    scenario = continuation_scenario(stack)
    _controller, outcome, view = checked_side(tmp_path, scenario, "trigger", "short")
    assert (outcome.request.direction, outcome.verdict.requested, outcome.verdict.decision) == ("short", "short", "no_trade")
    assert (view.requested, view.idea, view.suggestion, view.suggestion_tone) == ("short", "", "NO SHORT SETUP", "no_trade")
    assert view.auto_note == "Auto reads this as a long setup (continuation)."
    assert view.plan is None and all(chart.tool is None for chart in view.charts)
    assert [row.status for row in view.steps] == ["next", "later", "later"]
    # the next step's level is on the chart of its timeframe (the bias chart), named with the step's words
    step = next(item for item in outcome.verdict.steps if item.status == "next")
    bias, setup, entry = view.charts
    marks = [mark for mark in bias.marks if mark.role == "next"]
    assert len(marks) == 1 and marks[0].price == pytest.approx(105.0) == pytest.approx(step.price)
    assert marks[0].label == f"Next: {step.level_label}" == f"Next: {stack.bias} trades to"
    assert not [mark for chart in (setup, entry) for mark in chart.marks if mark.role == "next"]
    low, high = chart_price_range(bias, chart_window(bias, 60))
    assert low < 105.0 < high  # and it is on the scale


# --- the steps and the plan ---------------------------------------------------------


def test_steps_and_plan_are_presented(tmp_path: Path) -> None:
    scenario = continuation_scenario(DAILY)
    _controller, outcome, view = checked_side(tmp_path, scenario, "trigger")
    assert [(row.number, row.status, row.word, row.timeframe) for row in view.steps] == [
        (1, "done", "Done", "1D"), (2, "done", "Done", "1h"), (3, "done", "Done", "1h"), (4, "done", "Done", "5m"),
    ]  # fmt: skip
    assert [row.label for row in view.steps] == [step.label for step in outcome.verdict.steps]
    plan = view.plan
    assert plan is not None and (plan.title, plan.state, plan.outcome, plan.direction) == ("LONG", "triggered", "open", "long")
    assert [(level.name, level.price, level.note) for level in plan.levels] == [
        ("Entry", "97.50", ""), ("Stop", "91.00", "risk 6.50"), ("Target", "110.50", "2.00R  ·  13.00"),
    ]  # fmt: skip
    assert (view.suggestion, view.suggestion_tone, view.idea_alert) == ("TRADE LONG", "long", False)
    assert view.idea_state == "Triggered 08:25 · open · last close +0.03R from the entry."  # the entry CISD's candle

    _controller, outcome, waiting = checked_side(tmp_path, scenario, "before_setup")
    assert [row.status for row in waiting.steps] == ["done", "next", "later", "later"]
    upcoming = waiting.steps[1]
    assert upcoming.word == "Next" and "89.00" in upcoming.detail
    assert (waiting.suggestion, waiting.plan) == ("WATCH · LONG", None) and "nothing to enter yet" in waiting.idea_state
    setup = waiting.charts[1]
    mark = next(mark for mark in setup.marks if mark.role == "next")
    assert (mark.price, mark.label, mark.title) == (pytest.approx(89.0), "Next: 1h close above", upcoming.detail)
    assert not [mark for chart in (waiting.charts[0], waiting.charts[2]) for mark in chart.marks if mark.role == "next"]


@pytest.mark.parametrize("mirror", [False, True], ids=["long", "short"])
@pytest.mark.parametrize("stack", [DAILY, get_stack("4h / 15m / 1m")], ids=lambda stack: stack.name)
def test_risk_reward_tool_geometry_for_a_triggered_plan(tmp_path: Path, stack: TimeframeStack, mirror: bool) -> None:
    scenario = continuation_scenario(stack, mirror=mirror)
    _controller, outcome, view = checked_side(tmp_path, scenario, "trigger")
    entry_chart = view.charts[2]
    tool = entry_chart.tool
    assert tool is not None and [chart.tool for chart in view.charts[:2]] == [None, None]  # the entry chart only
    assert (tool.direction, tool.planned, tool.outcome) == ("short" if mirror else "long", False, "open")
    entry, stop, target = (scenario.price(price) for price in (97.5, 91.0, 110.5))
    assert (tool.entry, tool.stop, tool.target) == (pytest.approx(entry), pytest.approx(stop), pytest.approx(target))
    # risk between entry and stop, reward between entry and target, on opposite sides of the entry
    assert tool.risk_zone == (pytest.approx(max(entry, stop)), pytest.approx(min(entry, stop)))
    assert tool.reward_zone == (pytest.approx(max(entry, target)), pytest.approx(min(entry, target)))
    if mirror:
        assert tool.reward_zone[0] == pytest.approx(tool.entry) == pytest.approx(tool.risk_zone[1])  # reward below, risk above
    else:
        assert tool.reward_zone[1] == pytest.approx(tool.entry) == pytest.approx(tool.risk_zone[0])  # reward above, risk below
    assert (tool.risk_points, tool.reward_points, tool.r_multiple) == (pytest.approx(6.5), pytest.approx(13.0), pytest.approx(2.0))
    # it starts on the trigger candle, never left of it, and that candle stays on screen
    trigger = next(mark for mark in entry_chart.marks if mark.title == "Entry trigger")
    assert tool.start == trigger.start and entry_chart.candles[tool.start].close == pytest.approx(entry)
    assert chart_window(entry_chart, 2) <= tool.start
    low, high = chart_price_range(entry_chart, len(entry_chart.candles) - 1)  # even zoomed on the last candle
    assert low < min(stop, target) and max(stop, target) < high


@pytest.mark.parametrize("mirror", [False, True], ids=["long", "short"])
def test_risk_reward_tool_for_a_planned_plan_starts_at_the_current_candle(tmp_path: Path, mirror: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    from companion.styles import ttrades

    early = ttrades.load_config(overrides={"reversal_entry_tf_confirm_window": ["08:00", "11:00"]})
    monkeypatch.setattr(ttrades.style, "load_config", lambda path=None: early)
    scenario = reversal_scenario(DAILY, mirror=mirror)
    moment = scenario.builder.at(_SWING_SLOT["1D"], 4)  # the low is in, nothing has closed through the run yet
    _controller, outcome, view = checked_side(tmp_path, scenario, moment)
    assert outcome.verdict.plan is not None and outcome.verdict.plan.state == "planned"
    entry_chart = view.charts[2]
    tool = entry_chart.tool
    assert tool is not None and tool.planned and tool.start == len(entry_chart.candles) - 1
    entry, stop, target = (scenario.price(price) for price in (57.0, 54.0, 63.0))
    assert (tool.entry, tool.stop, tool.target) == (pytest.approx(entry), pytest.approx(stop), pytest.approx(target))
    assert tool.risk_zone == (pytest.approx(max(entry, stop)), pytest.approx(min(entry, stop)))
    assert tool.reward_zone == (pytest.approx(max(entry, target)), pytest.approx(min(entry, target)))
    # the level a close has to clear is the planned entry: one line, the tool's, not a second one on the same price
    assert not [mark for mark in entry_chart.marks if mark.kind == "level" and mark.price == pytest.approx(entry)]
    assert view.plan is not None and view.plan.title == f"PLANNED {'SHORT' if mirror else 'LONG'}"
    assert view.plan.levels[0].note == "trigger level"
    assert view.suggestion == f"WATCH · {'SHORT' if mirror else 'LONG'}" and view.idea_state.startswith("Planned")


def planned_verdict(**plan_changes: object) -> Verdict:
    """A long: entry 100, stop 98, target 104 (2R), triggered at 09:55, checked at 10:15."""
    day = "2026-02-18"
    values: dict[str, object] = dict(
        direction="long", state="triggered", entry=100.0, stop=98.0, target=104.0, r_multiple=2.0, timeframe="5m",
        since=pd.Timestamp(f"{day} 09:55", tz="America/New_York").to_pydatetime(), outcome="open", last=100.5, r_now=0.25,
    )  # fmt: skip
    values.update(plan_changes)
    steps = (PlanStep("bias", "1D", "done", "1D bias is bullish"), PlanStep("entry", "5m", "done", "5m turns up: the entry"))
    return sample_verdict(idea="long", targets=(104.0,), steps=steps, plan=PositionPlan(**values))  # type: ignore[arg-type]


def test_the_state_of_the_idea_is_shown_with_the_suggestion() -> None:
    hit = pd.Timestamp("2026-02-18 10:05", tz="America/New_York").to_pydatetime()
    fresh = present(planned_verdict())
    assert (fresh.suggestion, fresh.suggestion_tone, fresh.idea_alert) == ("TRADE LONG", "long", False)
    assert fresh.idea_state == "Triggered 09:55 · open · last close +0.25R from the entry."

    # the last close is 1.2R past the entry, 60 % of the way to the target: no longer an unqualified TRADE LONG
    late = present(planned_verdict(last=102.4, r_now=1.2))
    assert (late.suggestion, late.suggestion_tone, late.idea_alert) == ("LONG · LATE", "long", True)
    assert "+1.20R" in late.idea_state and "60%" in late.idea_state and "2.40 past it" in late.idea_state
    almost = present(planned_verdict(last=101.9, r_now=0.95))
    assert (almost.suggestion, almost.idea_alert) == ("TRADE LONG", False)

    reached = present(planned_verdict(outcome="target_reached", outcome_at=hit, last=103.0, r_now=1.5))
    assert (reached.suggestion, reached.suggestion_tone, reached.idea_alert) == ("LONG · TARGET REACHED", "no_trade", True)
    assert reached.idea_state == "Finished: the 2.00R target 104.00 traded at 10:05. Triggered 09:55; this is not an entry now."
    assert reached.decision == "long" and reached.decision_word == "TRADE LONG"  # the style's decision itself is untouched

    stopped = present(planned_verdict(outcome="stopped", outcome_at=hit, last=97.5, r_now=-1.25))
    assert (stopped.suggestion, stopped.suggestion_tone, stopped.idea_alert) == ("LONG · STOPPED", "no_trade", True)
    assert "the stop 98.00 traded at 10:05" in stopped.idea_state

    watch = sample_verdict(decision="watch", idea="short", entry=None, stop=None, targets=())
    assert (present(watch).suggestion, present(watch).idea_alert) == ("WATCH · SHORT", False)
    nothing = sample_verdict(decision="no_trade", entry=None, stop=None, targets=())
    assert (present(nothing).suggestion, present(nothing).idea_state) == ("DON'T TRADE", "")
    asked = sample_verdict(decision="no_trade", requested="long", entry=None, stop=None, targets=())
    assert present(asked).suggestion == "NO LONG SETUP" and "no route to a long" in present(asked).idea_state


def test_a_reached_target_from_a_real_check_qualifies_the_suggestion(tmp_path: Path) -> None:
    scenario = continuation_scenario(DAILY)
    scenario.builder.entries(_SWING_SLOT["1D"] + 1, [(97.7, 111.0, 97.6, 110.8)], first=3)
    moment = scenario.times["trigger"] + pd.Timedelta(minutes=5)
    _controller, outcome, view = checked_side(tmp_path, scenario, moment)
    assert outcome.verdict.decision == "long"
    assert (view.suggestion, view.idea_alert) == ("LONG · TARGET REACHED", True) and "110.50 traded at 09:15" in view.idea_state
    tool = view.charts[2].tool
    assert tool is not None and tool.outcome == "target_reached"
    assert view.charts[2].candles[tool.outcome_at].high >= tool.target  # the candle that got there


def test_a_trigger_older_than_the_candles_shown_starts_the_tool_at_the_first_candle() -> None:
    opens = pd.date_range("2026-02-18 09:00", periods=6, freq="5min", tz="America/New_York")
    candles = tuple(Candle(when, 100.0, 101.0, 99.0, 100.5) for when in opens)
    chart = ChartView("entry", "5m", candles, ())
    plan = planned_verdict(since=pd.Timestamp("2026-02-18 08:00", tz="America/New_York").to_pydatetime()).plan
    tool = app_model.risk_reward_tool(plan, chart)
    assert tool is not None and tool.start == 0
    on_chart = app_model.risk_reward_tool(planned_verdict(since=opens[3].to_pydatetime()).plan, chart)
    assert on_chart is not None and on_chart.start == 3
    assert app_model.risk_reward_tool(None, chart) is None


def test_one_line_per_price_when_the_next_level_is_a_reference_or_the_planned_entry() -> None:
    opens = pd.date_range("2026-02-18 09:00", periods=6, freq="5min", tz="America/New_York")
    candles = tuple(Candle(when, 100.0, 101.0, 99.0, 100.5) for when in opens)
    plain = (ChartMark("level", "reference", "Prev high", "Previous bias candle high", price=104.0), ChartMark("level", "waiting", "Close above = CISD", "CISD level", price=102.0))
    charts = (ChartView("bias", "1D", candles, plain[:1]), ChartView("setup", "1h", candles, ()), ChartView("entry", "5m", candles, plain[1:]))

    # the next step waits on the previous high: the bias chart shows that price once, as the next step
    reach = sample_verdict(decision="no_trade", requested="short", entry=None, stop=None, targets=(), steps=(
        PlanStep("bias", "1D", "next", "1D reaches a key level", "1D candle trades to 104.00", 104.0, "1D trades to"),
    ))  # fmt: skip
    bias = present(reach, charts=charts).charts[0]
    assert [(mark.role, mark.label, mark.price) for mark in bias.marks] == [("next", "Next: 1D trades to", 104.0)]

    # the next step waits on the planned entry: the tool's entry line carries the step's words, and nothing else sits there
    plan = PositionPlan("long", "planned", 102.0, 99.0, 108.0, 2.0, "5m", since=opens[-1].to_pydatetime(), last=100.5)
    turn = sample_verdict(decision="watch", idea="long", entry=None, stop=None, targets=(), plan=plan, steps=(
        PlanStep("entry", "5m", "next", "5m turns up: the entry", "5m close above 102.00", 102.0, "5m close above"),
    ))  # fmt: skip
    entry = present(turn, charts=charts).charts[2]
    assert entry.tool is not None and entry.tool.entry_note == "Next: 5m close above" and entry.tool.planned
    assert not [mark for mark in entry.marks if mark.kind == "level"]
