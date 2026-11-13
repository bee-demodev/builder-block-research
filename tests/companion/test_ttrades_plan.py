"""The bias selector, the steps and the position plan of the TTrades style (rules.md 10.6).

Markets come from ``ttrades_scenarios``; each scenario's docstring spells out the prices
the assertions rely on. Bullish story, 1D / 1h / 5m and 4h / 15m / 1m:

- continuation: entry CISD trigger 97.5, stop 91, exit 110.5 (2R); in conservative mode the
  order block trigger 97.7, stop 95.5, exit 102.1; previous bias candle high 105, its
  bias order block 82-96 (mean threshold 89)
- reversal: key level 55 (previous bias candle low), wick low 54, CISD level 57.0, trigger
  57.4, previous bias candle high 71
"""

from __future__ import annotations

import dataclasses
from typing import Any

import pandas as pd
import pytest

from companion.engine import analyze, render_text
from companion.styles.base import Style, get_style
from companion.styles.ttrades import TTradesStyle, load_config
from companion.timeframes import get_stack, parse_timeframe
from companion.types import CriterionResult, PlanStep, TimeframeStack, Verdict
from ttrades_scenarios import _SWING_SLOT, SYMBOL, Scenario, continuation_scenario, reversal_scenario

DAILY = get_stack("1D / 1h / 5m")
FOUR_HOUR = get_stack("4h / 15m / 1m")
STACKS = pytest.mark.parametrize("stack", [DAILY, FOUR_HOUR], ids=lambda stack: stack.name)
SIDES = ("long", "short")
OPPOSITE = {"long": "short", "short": "long"}
ROLES = ("bias", "setup", "entry")
# the reversal CISD may be read on the entry timeframe from 08:00, so the scenarios have a
# moment where the low is in and nothing has closed through the run yet
EARLY_WINDOW: dict[str, Any] = {"reversal_entry_tf_confirm_window": ["08:00", "11:00"]}


def evaluate(
    scenario: Scenario,
    moment: str | pd.Timestamp,
    direction: str | None = None,
    *,
    until: pd.Timestamp | None = None,
    **overrides: Any,
) -> Verdict:
    style = TTradesStyle(load_config(overrides=overrides))
    when = scenario.times[moment] if isinstance(moment, str) else moment
    return style.evaluate(SYMBOL, when.to_pydatetime(), scenario.stack, scenario.source(until), direction=direction)  # type: ignore[arg-type]


def criterion(verdict: Verdict, key: str) -> CriterionResult:
    return next(item for item in verdict.criteria if item.key == key)


def idea(verdict: Verdict) -> Verdict:
    """The verdict without the side that was asked for and without the reversal checklist:
    with a forced side the checklist shown is that side's, so it can differ from auto's
    even when both tell the same idea."""
    kept = tuple(item for item in verdict.criteria if not item.group.startswith("reversal"))
    return dataclasses.replace(verdict, requested="", criteria=kept)


def statuses(verdict: Verdict) -> list[str]:
    return [step.status for step in verdict.steps]


def upcoming(verdict: Verdict) -> PlanStep:
    found = [step for step in verdict.steps if step.status == "next"]
    assert len(found) == 1, statuses(verdict)
    return found[0]


def marked(verdict: Verdict, label: str) -> float:
    """Price of the markup item with this label: the level the rules themselves put on the chart."""
    return next(item.price for item in verdict.markup if item.label == label and item.price is not None)


def extended(stack: TimeframeStack, rows: list[tuple[float, float, float, float]], mirror: bool = False) -> tuple[Scenario, list[pd.Timestamp]]:
    """The continuation scenario with entry candles added straight after the order block
    trigger; returns it with the close time of each added candle."""
    scenario = continuation_scenario(stack, mirror=mirror)
    slot = _SWING_SLOT[stack.bias] + 1
    scenario.builder.entries(slot, rows, first=3)
    step = pd.Timedelta(minutes=parse_timeframe(stack.entry).nominal_minutes)
    return scenario, [scenario.times["trigger"] + step * (index + 1) for index in range(len(rows))]


# --- the protocol and auto ---------------------------------------------------------


def test_the_side_is_an_optional_argument_of_the_style_protocol() -> None:
    style = get_style("ttrades")
    assert isinstance(style, Style)
    scenario = continuation_scenario(DAILY)
    when = scenario.times["trigger"].to_pydatetime()
    plain = style.evaluate(SYMBOL, when, DAILY, scenario.source())  # the call every style has always had
    assert plain == style.evaluate(SYMBOL, when, DAILY, scenario.source(), direction=None)
    assert plain.requested == "" and plain.auto_note == ""
    with pytest.raises(ValueError):
        style.evaluate(SYMBOL, when, DAILY, scenario.source(), direction="sideways")  # type: ignore[arg-type]


def test_engine_passes_the_side_through() -> None:
    scenario = continuation_scenario(DAILY)
    when = scenario.times["trigger"]
    auto = analyze(SYMBOL, when, DAILY, source=scenario.source())
    assert analyze(SYMBOL, when, DAILY, source=scenario.source(), direction="auto") == auto
    forced = analyze(SYMBOL, when, DAILY, source=scenario.source(), direction="short")
    assert (auto.decision, auto.requested, forced.decision, forced.requested) == ("long", "", "no_trade", "short")
    with pytest.raises(ValueError, match="long, short or auto"):
        analyze(SYMBOL, when, DAILY, source=scenario.source(), direction="up")
    text = render_text(forced)
    assert "Side asked for: short" in text and "[NEXT]" in text and text.isascii()


@STACKS
def test_auto_still_proposes_what_it_did(stack: TimeframeStack) -> None:
    """The decisions, levels and reads the existing tests pin, with the new fields beside them."""
    long = evaluate(continuation_scenario(stack), "trigger")
    assert (long.decision, long.path_family, long.stage, long.entry, long.stop, long.targets) == (
        "long", "continuation", "c4", pytest.approx(97.5), pytest.approx(91.0), (pytest.approx(110.5),),
    )  # fmt: skip
    assert (long.requested, long.idea, long.auto_note) == ("", "long", "")
    short = evaluate(continuation_scenario(stack, mirror=True), "trigger")
    assert (short.decision, short.idea, short.entry) == ("short", "short", pytest.approx(102.5))
    watch = evaluate(continuation_scenario(stack), "before_setup")
    assert (watch.decision, watch.stage, watch.idea, watch.entry) == ("watch", "c1", "long", None)
    assert watch.waiting_for  # the sentence is still produced; the steps say the same thing in order


def test_auto_reversal_is_unchanged() -> None:
    verdict = evaluate(reversal_scenario(DAILY), "trigger")
    assert (verdict.decision, verdict.path_family, verdict.entry, verdict.stop) == ("long", "reversal", pytest.approx(57.4), pytest.approx(54.0))
    nothing = evaluate(reversal_scenario(DAILY, previous_low=50.0), "trigger")
    assert (nothing.decision, nothing.path_family, nothing.idea, nothing.plan) == ("no_trade", "none", "", None)


# --- a forced side ------------------------------------------------------------------


@STACKS
@pytest.mark.parametrize("mirror", [False, True], ids=["bullish", "bearish"])
def test_forced_side_the_bias_agrees_with_is_the_continuation(stack: TimeframeStack, mirror: bool) -> None:
    scenario = continuation_scenario(stack, mirror=mirror)
    side = "short" if mirror else "long"
    for moment in ("before_setup", "trigger", "window_closed"):
        auto = evaluate(scenario, moment)
        forced = evaluate(scenario, moment, side)
        assert idea(forced) == idea(auto)  # the same idea, told the same way
        assert (forced.requested, forced.path_family, forced.idea, forced.auto_note) == (side, "continuation", side, "")


@STACKS
@pytest.mark.parametrize("mirror", [False, True], ids=["bullish", "bearish"])
def test_forced_side_against_the_bias_with_no_key_level_has_no_route(stack: TimeframeStack, mirror: bool) -> None:
    scenario = continuation_scenario(stack, mirror=mirror)
    side, other = ("long", "short") if mirror else ("short", "long")
    auto = evaluate(scenario, "trigger")
    forced = evaluate(scenario, "trigger", side)
    assert auto.decision == other
    assert (forced.decision, forced.path_family, forced.stage, forced.idea) == ("no_trade", "none", "none", "")
    assert (forced.entry, forced.stop, forced.targets, forced.plan) == (None, None, (), None)
    assert not [item for item in forced.markup if item.role in ("entry", "stop", "target")]
    assert forced.auto_note == f"Auto reads this as a {other} setup (continuation)."
    # said plainly, with the nearest thing that would open a route: the previous bias candle's high (105)
    level = scenario.price(105.0)
    bias_word = "bearish" if mirror else "bullish"
    assert f"The {stack.bias} is {bias_word}, so a {side} here is a reversal" in forced.why
    assert f"{level:,.2f}" in forced.why
    assert [(row.role, row.status) for row in forced.read] == [("bias", "waiting"), ("setup", "not_applicable"), ("entry", "not_applicable")]
    step = upcoming(forced)
    assert (step.role, step.timeframe, step.price) == ("bias", stack.bias, pytest.approx(level))
    assert step.price == pytest.approx(marked(forced, "Previous bias candle low" if mirror else "Previous bias candle high"))
    assert f"{level:,.2f}" in step.detail and statuses(forced) == ["next", "later", "later"]
    assert forced.summary.startswith(f"No {side} route.")


def test_forced_side_against_the_bias_at_a_key_level_is_the_reversal() -> None:
    scenario = reversal_scenario(DAILY)  # the daily closed bearish (late); price turned up off the previous low
    auto = evaluate(scenario, "trigger")
    long = evaluate(scenario, "trigger", "long")
    assert auto.bias == "bearish"
    assert long == dataclasses.replace(auto, requested="long")  # the reversal checklist too: it is the long side's
    assert (long.decision, long.path_family, long.idea) == ("long", "reversal", "long")

    short = evaluate(scenario, "trigger", "short")  # the bias agrees, but its continuation is dead (late) and no high is near
    assert (short.decision, short.idea, short.plan) == ("no_trade", "", None)
    assert short.auto_note == "Auto reads this as a long setup (reversal)."
    assert "A short reversal is not open either" in short.why and "71.00" in short.why
    assert statuses(short) == ["blocked", "next", "later", "later"]
    assert (short.steps[0].role, upcoming(short).price) == ("bias", pytest.approx(71.0))
    assert short.read[0].status == "failed"  # the blocked step and the read say the same thing


def test_forced_side_picks_that_sides_path_when_auto_prefers_the_other() -> None:
    """After the trigger the market runs both ways (the aftermath): auto reads a short
    reversal off an old high; a trader who wants the long is told the long."""
    scenario = continuation_scenario(DAILY, with_aftermath=True)
    moment = scenario.times["trigger"] + pd.Timedelta(minutes=10)
    auto = evaluate(scenario, moment)
    long = evaluate(scenario, moment, "long")
    short = evaluate(scenario, moment, "short")
    assert (auto.idea, auto.path_family) == ("short", "reversal")
    assert short == dataclasses.replace(auto, requested="short")
    assert long.idea in ("", "long") and long.decision != "short"
    assert long.auto_note == "Auto reads this as a short setup (reversal)."
    assert long.plan is None or long.plan.direction == "long"


def _all_cases() -> list[tuple[str, Scenario, pd.Timestamp, dict[str, Any]]]:
    cases: list[tuple[str, Scenario, pd.Timestamp, dict[str, Any]]] = []
    for stack in (DAILY, FOUR_HOUR):
        for mirror in (False, True):
            scenario = continuation_scenario(stack, mirror=mirror, with_aftermath=True)
            for name, moment in scenario.times.items():
                cases.append((f"continuation {stack.bias} {'bear' if mirror else 'bull'} {name}", scenario, moment, {}))
            for minutes in (5, 10, 65):
                cases.append((f"aftermath {stack.bias} +{minutes}", scenario, scenario.times["trigger"] + pd.Timedelta(minutes=minutes), {}))
    for mirror in (False, True):
        for kwargs in ({}, {"previous_low": 50.0}, {"wick_low": 55.05}):
            scenario = reversal_scenario(DAILY, mirror=mirror, **kwargs)
            for name, moment in scenario.times.items():
                cases.append((f"reversal {'bear' if mirror else 'bull'} {kwargs} {name}", scenario, moment, {}))
            cases.append((f"reversal early {kwargs}", scenario, scenario.builder.at(_SWING_SLOT["1D"], 4), EARLY_WINDOW))
    return cases


@pytest.mark.parametrize("side", SIDES)
def test_a_forced_side_never_tells_the_other_direction_and_changes_no_rule(side: str) -> None:
    other = OPPOSITE[side]
    for name, scenario, moment, overrides in _all_cases():
        auto = evaluate(scenario, moment, **overrides)
        forced = evaluate(scenario, moment, side, **overrides)
        assert forced.requested == side, name
        assert forced.decision != other and forced.idea in ("", side), name
        assert forced.plan is None or forced.plan.direction == side, name
        if forced.idea == "":
            assert forced.decision == "no_trade" and (forced.entry, forced.plan) == (None, None), name
            assert not [item for item in forced.markup if item.role in ("entry", "stop", "target", "poi", "confirm")], name
        text = " ".join([forced.why, forced.waiting_for, *(f"{step.label} {step.detail}" for step in forced.steps)])
        assert f"a {other} opens" not in text.lower(), name
        # no rule passes or fails differently: the shared and continuation results are the same
        # objects' worth, and so are the reversal's whenever both tell the same side
        for item in forced.criteria:
            if item.group.startswith("reversal") or item.key == "session_filter_ok":
                continue
            assert item == criterion(auto, item.key), (name, item.key)
        if auto.idea == side:
            assert idea(forced) == idea(auto), name
            assert forced.auto_note == "", name
            if auto.path_family == "reversal":
                assert forced == dataclasses.replace(auto, requested=side), name
        elif auto.idea:
            assert other in forced.auto_note, name


@STACKS
@pytest.mark.parametrize("side", SIDES)
def test_no_lookahead_with_a_forced_side(stack: TimeframeStack, side: str) -> None:
    scenario = continuation_scenario(stack, with_aftermath=True)
    for name, moment in scenario.times.items():
        assert evaluate(scenario, name, side) == evaluate(scenario, name, side, until=moment), name
    late = scenario.times["trigger"] + pd.Timedelta(minutes=2 * parse_timeframe(stack.entry).nominal_minutes)
    assert evaluate(scenario, late, side) == evaluate(scenario, late, side, until=late)


@pytest.mark.parametrize("side", SIDES)
def test_no_lookahead_on_the_reversal_path_with_a_forced_side(side: str) -> None:
    quiet = reversal_scenario(DAILY)
    loud = reversal_scenario(DAILY)
    loud.builder.entries(_SWING_SLOT["1D"] + 1, [(57.8, 90.0, 30.0, 31.0)], first=3)  # one wild candle after the trigger
    for name in quiet.times:
        assert evaluate(quiet, name, side) == evaluate(loud, name, side), name


# --- the steps ----------------------------------------------------------------------

# the continuation's step criteria in the order the steps tell them (entry mode "either")
CONTINUATION_STEPS = ("bias_cisd_confirmed", "cont_poi_tagged", "cont_setup_closure", "cont_entry_trigger")
REVERSAL_STEPS = ("rev_key_level_reached", "rev_reclaim", "rev_entry_trigger")


def assert_steps_shape(verdict: Verdict, stack: TimeframeStack) -> None:
    steps = verdict.steps
    assert 1 <= len(steps) <= 6
    assert all(step.status in ("done", "next", "later", "blocked") and step.label for step in steps)
    assert [ROLES.index(step.role) for step in steps] == sorted(ROLES.index(step.role) for step in steps)  # bias -> entry
    assert all(step.timeframe in (stack.bias, stack.setup, stack.entry) for step in steps)
    ahead = [step.status for step in steps if step.status in ("next", "later")]
    assert ahead.count("next") <= 1
    if verdict.idea or verdict.requested:  # an idea, or a side asked for: nothing is "later" without a "next" before it
        assert ahead[:1] in ([], ["next"])
    else:  # no idea at all: dead, so nothing is next
        assert "next" not in ahead
    for step in steps:
        if step.status == "next":
            assert step.detail, "the next step says its condition"
        if step.price is not None:
            assert f"{step.price:,.2f}" in step.detail and step.level_label
    # never against the read: a role the read confirmed has no step still ahead, and a blocked step sits on a failed line
    read = {row.role: row.status for row in verdict.read}
    for step in steps:
        if read.get(step.role) == "confirmed":
            assert step.status == "done", (step.label, step.status)
        if step.status == "blocked":
            assert read.get(step.role) in ("failed", "not_applicable"), step.label


@STACKS
def test_continuation_steps_follow_the_criteria(stack: TimeframeStack) -> None:
    scenario = continuation_scenario(stack)
    expected = {
        "before_setup": ["done", "next", "later", "later"],
        "setup_closed": ["done", "done", "done", "done"],
        "trigger": ["done", "done", "done", "done"],
    }
    for moment, wanted in expected.items():
        verdict = evaluate(scenario, moment)
        assert_steps_shape(verdict, stack)
        assert statuses(verdict) == wanted, moment
        for step, key in zip(verdict.steps, CONTINUATION_STEPS):
            assert (step.status == "done") == (criterion(verdict, key).passed is True), (moment, key)
        assert [step.timeframe for step in verdict.steps] == [stack.bias, stack.setup, stack.setup, stack.entry]
        assert (verdict.decision in ("long", "short")) == (statuses(verdict).count("next") == 0), moment

    waiting = evaluate(scenario, "before_setup")
    step = upcoming(waiting)
    # the forming setup candle is already in the bias order block 82-96: it has to close at or above its mean threshold
    assert (step.role, step.timeframe, step.price, step.level_label) == ("setup", stack.setup, pytest.approx(89.0), f"{stack.setup} close above")
    top, bottom = next((item.top, item.bottom) for item in waiting.markup if item.label == "Bias order block")
    assert step.price == pytest.approx((top + bottom) / 2)

    # complete, but the entry window has passed: nothing is next, and the step of that timeframe says why
    late = evaluate(scenario, "window_closed")
    assert_steps_shape(late, stack)
    assert (late.decision, statuses(late)) == ("watch", ["done", "done", "blocked", "done"])
    assert "entry window has passed" in late.steps[2].detail


@STACKS
def test_next_closure_level_once_a_setup_candle_is_at_the_point_of_interest(stack: TimeframeStack) -> None:
    """The setup candle before the swing dips into the bias order block (low 95.5) without a
    closure. The candle now forming has taken that low (91.0): closing back above 95.5 makes
    it the Candle 2 closure, which is what the rules then find when it closes at 97.5."""
    scenario = continuation_scenario(stack, previous_setup_bar=(96.8, 97.8, 95.5, 96.0))
    waiting = evaluate(scenario, "before_setup")
    assert_steps_shape(waiting, stack)
    assert statuses(waiting) == ["done", "done", "next", "later"]
    assert criterion(waiting, "cont_poi_tagged").passed is True and criterion(waiting, "cont_setup_closure").passed is False
    step = upcoming(waiting)
    assert (step.timeframe, step.price, step.level_label) == (stack.setup, pytest.approx(95.5), f"{stack.setup} close above")
    assert "Candle 2 closure" in step.detail
    closed = evaluate(scenario, "setup_closed")
    assert "Candle 2 closure" in criterion(closed, "cont_setup_closure").detail and statuses(closed)[2] == "done"


@STACKS
def test_conservative_entry_adds_its_own_step_with_the_order_block_level(stack: TimeframeStack) -> None:
    scenario = continuation_scenario(stack)
    verdict = evaluate(scenario, "setup_closed", entry_mode_continuation="conservative")
    assert_steps_shape(verdict, stack)
    assert (verdict.decision, statuses(verdict)) == ("watch", ["done", "done", "done", "done", "next"])
    step = upcoming(verdict)
    # the pullback has to come back into the entry order block, whose top is the CISD level 97.0
    assert (step.timeframe, step.price, step.level_label) == (stack.entry, pytest.approx(97.0), f"{stack.entry} pullback to")
    top = next(item.top for item in verdict.markup if item.label == "Entry order block (entry CISD)")
    assert step.price == pytest.approx(top)
    assert verdict.plan is None  # the pullback's low is not known yet, so the rules cannot give levels


@pytest.mark.parametrize("mirror", [False, True], ids=["bullish", "bearish"])
def test_reversal_steps_and_the_next_level(mirror: bool) -> None:
    scenario = reversal_scenario(DAILY, mirror=mirror)
    waiting = evaluate(scenario, "level_taken")
    assert_steps_shape(waiting, DAILY)
    assert statuses(waiting) == ["done", "next", "later"]
    for step, key in zip(waiting.steps, REVERSAL_STEPS):
        assert (step.status == "done") == (criterion(waiting, key).passed is True), key
    step = upcoming(waiting)
    assert (step.role, step.timeframe, step.price) == ("setup", "1h", pytest.approx(scenario.price(55.0)))
    assert step.price == pytest.approx(marked(waiting, "Key level on the setup timeframe"))
    assert step.level_label == f"1h close {'below' if mirror else 'above'}"

    done = evaluate(scenario, "trigger")
    assert_steps_shape(done, DAILY)
    assert (done.decision, statuses(done)) == ("short" if mirror else "long", ["done", "done", "done"])


def test_a_quality_check_blocks_the_step_of_its_timeframe() -> None:
    drift = evaluate(reversal_scenario(DAILY, run_into_level=False), "trigger")
    assert_steps_shape(drift, DAILY)
    assert (drift.decision, drift.read[1].status) == ("watch", "failed")
    assert statuses(drift) == ["done", "blocked", "done"] and "drift" in drift.steps[1].detail


def test_no_idea_steps_say_where_it_stops_and_what_would_open_one() -> None:
    nothing = evaluate(reversal_scenario(DAILY, previous_low=50.0), "trigger")
    assert_steps_shape(nothing, DAILY)
    assert statuses(nothing) == ["blocked", "later", "later"]  # dead: nothing is "next"
    opens = {step.label: step.price for step in nothing.steps[1:]}
    assert opens == {"A long opens if the 1D reaches a key level": pytest.approx(50.0), "A short opens if the 1D reaches a key level": pytest.approx(71.0)}
    short_of = evaluate(continuation_scenario(DAILY), START_OF_DATA)
    assert statuses(short_of) == ["blocked"] and short_of.plan is None


START_OF_DATA = pd.Timestamp("2024-04-03 09:00", tz="America/New_York")  # two bias candles in: not enough history


# --- the position plan ----------------------------------------------------------------


@STACKS
@pytest.mark.parametrize("mirror", [False, True], ids=["bullish", "bearish"])
def test_triggered_plan_is_the_rules_own_trade(stack: TimeframeStack, mirror: bool) -> None:
    scenario = continuation_scenario(stack, mirror=mirror)
    verdict = evaluate(scenario, "trigger")
    plan = verdict.plan
    assert plan is not None
    assert (plan.direction, plan.state, plan.outcome, plan.timeframe) == ("short" if mirror else "long", "triggered", "open", stack.entry)
    assert (plan.entry, plan.stop, plan.target) == (pytest.approx(verdict.entry), pytest.approx(verdict.stop), pytest.approx(verdict.targets[0]))
    assert (plan.entry, plan.stop, plan.target) == tuple(pytest.approx(scenario.price(price)) for price in (97.5, 91.0, 110.5))
    assert plan.r_multiple == pytest.approx(2.0)
    assert (plan.target > plan.entry > plan.stop) is (not mirror)
    trigger_bar = next(item.start for item in verdict.markup if item.label == "Entry trigger")
    assert plan.since == trigger_bar and plan.outcome_at is None
    # the last close is the order block candle's 97.7: 0.2 past an entry with 6.5 of risk
    assert (plan.last, plan.r_now) == (pytest.approx(scenario.price(97.7)), pytest.approx(0.2 / 6.5))


@STACKS
def test_target_rr_sets_the_planned_and_triggered_target(stack: TimeframeStack) -> None:
    plan = evaluate(continuation_scenario(stack), "trigger", target_rr=1.0).plan
    assert plan is not None and (plan.target, plan.r_multiple) == (pytest.approx(104.0), pytest.approx(1.0))


@STACKS
@pytest.mark.parametrize("mirror", [False, True], ids=["bullish", "bearish"])
def test_target_reached_is_reported_and_the_decision_is_left_alone(stack: TimeframeStack, mirror: bool) -> None:
    scenario, (first, second) = extended(stack, [(97.7, 99.0, 97.6, 98.9), (98.9, 111.0, 98.8, 110.8)], mirror)
    side = "short" if mirror else "long"
    running = evaluate(scenario, first)
    assert (running.decision, running.plan.outcome, running.plan.r_now) == (side, "open", pytest.approx(1.4 / 6.5))  # type: ignore[union-attr]
    there = evaluate(scenario, second)
    plan = there.plan
    assert plan is not None
    assert there.decision == side  # open question 33: finished ideas are the trader's call, the rules do not expire them
    assert (plan.state, plan.outcome, plan.outcome_at) == ("triggered", "target_reached", first.to_pydatetime())
    assert plan.r_now == pytest.approx((110.8 - 97.5) / 6.5)
    assert statuses(there).count("next") == 0


@STACKS
@pytest.mark.parametrize("mirror", [False, True], ids=["bullish", "bearish"])
def test_stopped_is_reported_and_the_stop_wins_a_shared_bar(stack: TimeframeStack, mirror: bool) -> None:
    """Conservative mode: order block entry 97.7, stop 95.5, exit 102.1 (2R)."""
    conservative = {"entry_mode_continuation": "conservative"}
    side = "short" if mirror else "long"
    clean = evaluate(continuation_scenario(stack, mirror=mirror), "trigger", **conservative)
    assert (clean.decision, clean.plan.outcome) == (side, "open")  # type: ignore[union-attr]
    assert (clean.plan.entry, clean.plan.stop, clean.plan.target) == tuple(  # type: ignore[union-attr]
        pytest.approx(clean_price) for clean_price in (clean.entry, clean.stop, clean.targets[0])
    )

    # one candle trades through the stop (95.0) and the target (103.0): it counts as stopped
    scenario, (both,) = extended(stack, [(97.7, 103.0, 95.0, 96.0)], mirror)
    shared = evaluate(scenario, both, **conservative)
    plan = shared.plan
    assert plan is not None
    assert (plan.entry, plan.stop, plan.target) == tuple(pytest.approx(scenario.price(price)) for price in (97.7, 95.5, 102.1))
    assert (plan.state, plan.outcome, plan.outcome_at) == ("triggered", "stopped", scenario.times["trigger"].to_pydatetime())
    assert shared.decision == "watch" and criterion(shared, "cont_protected_swing_intact").passed is False
    assert statuses(shared).count("next") == 0 and "blocked" in statuses(shared)
    assert shared.entry is None  # the legacy level fields keep their rule: only told for a trade

    # the target first, the stop a candle later: the target was reached
    scenario, (_, later) = extended(stack, [(97.7, 103.0, 97.6, 102.5), (102.5, 102.6, 95.0, 95.2)], mirror)
    assert evaluate(scenario, later, **conservative).plan.outcome == "target_reached"  # type: ignore[union-attr]
    # the stop first: stopped, and it stays stopped
    scenario, (_, later) = extended(stack, [(97.7, 97.8, 95.0, 95.2), (95.2, 96.0, 95.1, 95.5)], mirror)
    assert evaluate(scenario, later, **conservative).plan.outcome == "stopped"  # type: ignore[union-attr]


@pytest.mark.parametrize("mirror", [False, True], ids=["bullish", "bearish"])
def test_planned_plan_projects_from_the_level_the_trigger_has_to_clear(mirror: bool) -> None:
    scenario = reversal_scenario(DAILY, mirror=mirror)
    moment = scenario.builder.at(_SWING_SLOT["1D"], 4)  # the low 54 is in; no close above 57.0 yet
    verdict = evaluate(scenario, moment, **EARLY_WINDOW)
    plan = verdict.plan
    assert plan is not None and verdict.decision == "watch"
    assert (plan.direction, plan.state, plan.outcome) == ("short" if mirror else "long", "planned", "open")
    # entry = the CISD level 57.0, stop = the wick low 54.0, target = 2R = 63.0
    assert (plan.entry, plan.stop, plan.target) == tuple(pytest.approx(scenario.price(price)) for price in (57.0, 54.0, 63.0))
    assert plan.entry == pytest.approx(marked(verdict, "Reversal CISD level (no close through it yet)"))
    assert plan.stop == pytest.approx(marked(verdict, f"Reversal wick {'high' if mirror else 'low'}"))
    assert (plan.r_multiple, plan.r_now, plan.outcome_at) == (pytest.approx(2.0), None, None)
    assert "Planned, not triggered" in plan.note and "move if price makes a new" in plan.note
    assert (verdict.entry, verdict.stop, verdict.targets) == (None, None, ())  # nothing has triggered
    assert_steps_shape(verdict, DAILY)
    assert statuses(verdict) == ["done", "next", "later"]
    assert verdict.plan == evaluate(scenario, moment, plan.direction, **EARLY_WINDOW).plan


@STACKS
def test_no_plan_when_the_rules_cannot_compute_its_levels(stack: TimeframeStack) -> None:
    scenario = continuation_scenario(stack)
    assert evaluate(scenario, "before_setup").plan is None  # no setup closure: no level to clear, no low to stop under
    assert evaluate(scenario, "trigger", "short").plan is None  # no route
    if stack == DAILY:
        waiting = evaluate(reversal_scenario(DAILY), "level_taken")  # 08:15: the reversal turn is not read on the 5m yet
        assert waiting.plan is None and upcoming(waiting).price is not None
