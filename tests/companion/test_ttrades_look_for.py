"""What to look for while a continuation waits on its setup (display only).

Prices from ``continuation_scenario`` (bullish story): bias order block 82-96, previous
bias candle high 105 (the structural level). ``before_setup`` is the forming setup candle
before any closure; the mirror reflects every price around the scenario's pivot.
"""

from __future__ import annotations

import dataclasses

import pandas as pd
import pytest

import companion.styles.ttrades.plan as plan
import companion.styles.ttrades.style as style
from companion.styles.ttrades.plan import _Poi, look_options
from companion.styles.ttrades.primitives import BEAR, BULL
from companion.timeframes import get_stack
from companion.types import TimeframeStack, Verdict
from test_ttrades_plan import evaluate
from ttrades_scenarios import continuation_scenario

DAILY = get_stack("1D / 1h / 5m")
FOUR_HOUR = get_stack("4h / 15m / 1m")
STACKS = pytest.mark.parametrize("stack", [DAILY, FOUR_HOUR], ids=lambda stack: stack.name)


@STACKS
@pytest.mark.parametrize("mirror", [False, True], ids=["long", "short"])
def test_a_waiting_continuation_says_what_to_look_for(stack: TimeframeStack, mirror: bool) -> None:
    scenario = continuation_scenario(stack, mirror=mirror)
    verdict = evaluate(scenario, "before_setup")
    look = verdict.look_for
    assert verdict.decision == "watch" and look is not None
    assert (look.direction, look.timeframe, look.entry_timeframe) == ("short" if mirror else "long", stack.setup, stack.entry)

    # the forming setup candle has dipped into the order block and taken the low of the one
    # before it: C2 is forming, so its entry is what comes now (the rules' steps wait for the close)
    assert [step.status for step in look.steps] == ["done", "done", "next"]
    assert [step.status for step in verdict.steps] == ["done", "next", "later", "later"]
    hi = "high" if mirror else "low"
    assert [step.label for step in look.steps] == [
        f"{stack.setup} C1 pushes into the POI",
        f"{stack.setup} C2 sweeps C1's {hi}",
        f"While that C2 forms: a {stack.entry} close {'below' if mirror else 'above'} the {'up-close' if mirror else 'down-close'} run",
    ]

    # option A is the nearest point of interest, as real prices
    (a,) = look.options
    top, bottom = sorted((scenario.price(96.0), scenario.price(82.0)), reverse=True)
    assert (a.key, a.name, a.top, a.bottom, a.condition) == ("A", "Bias order block", pytest.approx(top), pytest.approx(bottom), "")

    assert look.entry == f"{stack.entry} close {'below' if mirror else 'above'} the run" and look.entry_during
    assert look.stop == f"{'above' if mirror else 'below'} the {stack.setup} C2 {hi}"
    # no 2R price: it depends on a candle that has not formed; the structural level is named and priced
    name = ("PDL" if mirror else "PDH") if stack.bias == "1D" else f"previous {stack.bias} {'low' if mirror else 'high'}"
    assert look.target == f"2R, then {name}"
    assert look.target_price == pytest.approx(scenario.price(105.0))


@STACKS
def test_nothing_to_look_for_once_the_setup_has_closed_or_the_trade_is_on(stack: TimeframeStack) -> None:
    scenario = continuation_scenario(stack)
    for moment in ("setup_closed", "trigger", "after_trigger", "window_closed"):
        assert evaluate(scenario, moment).look_for is None, moment


@STACKS
def test_the_sequence_moves_on_inside_the_forming_setup_candle(stack: TimeframeStack) -> None:
    """At the open of the setup candle nothing has been swept: C1 into the zone is next. Once
    closed entry bars inside it take C1's low at the zone, C2 is forming and the entry is next.
    The rules' own steps do not move until the candle closes."""
    scenario = continuation_scenario(stack)
    opened = scenario.times["before_setup"].floor(f"{60 if stack.setup == '1h' else 15}min")
    at_open = evaluate(scenario, opened).look_for
    assert at_open is not None and [step.status for step in at_open.steps] == ["next", "later", "later"]
    later = evaluate(scenario, scenario.times["before_setup"])
    assert later.look_for is not None and [step.status for step in later.look_for.steps] == ["done", "done", "next"]
    assert [step.status for step in later.steps] == [step.status for step in evaluate(scenario, opened).steps]


def test_structural_target_mode_names_the_level_alone() -> None:
    look = evaluate(continuation_scenario(DAILY), "before_setup", target_mode="structural").look_for
    assert look is not None and look.target == "PDH"


def test_conservative_entry_is_worded_as_its_own_sequence() -> None:
    look = evaluate(continuation_scenario(DAILY), "before_setup", entry_mode_continuation="conservative").look_for
    assert look is not None
    assert look.steps[-1].label == "After that C2: a 5m turn up, a pullback that holds, and a close back up"
    # the trade if it plays says the same: not the single close of the aggressive entry, and not during C2
    assert look.entry == "5m close back up after a pullback that holds" and not look.entry_during


def _strip(verdict: Verdict) -> Verdict:
    return dataclasses.replace(verdict, look_for=None)


@STACKS
@pytest.mark.parametrize("moment", ["before_setup", "setup_closed", "trigger", "window_closed"])
def test_look_for_changes_nothing_else(stack: TimeframeStack, moment: str, monkeypatch: pytest.MonkeyPatch) -> None:
    scenario = continuation_scenario(stack)
    with_it = evaluate(scenario, moment)
    monkeypatch.setattr(style, "build_look_for", lambda *args, **kwargs: None)
    without = evaluate(scenario, moment)
    assert _strip(with_it) == without


def test_no_point_of_interest_ahead_means_nothing_to_look_for(monkeypatch: pytest.MonkeyPatch) -> None:
    scenario = continuation_scenario(DAILY)
    before = evaluate(scenario, "before_setup")
    monkeypatch.setattr(plan, "_pois", lambda *args, **kwargs: [])
    after = evaluate(scenario, "before_setup")
    assert before.look_for is not None and after.look_for is None
    # points of interest only feed what is shown: the decision and every check stay the same
    assert (after.decision, after.stage, after.criteria) == (before.decision, before.stage, before.criteria)


# --- option A and option B -----------------------------------------------------------

GAP = _Poi(near=100.0, top=100.0, bottom=99.0, name="the unfilled 1h fair value gap", short="1h fair value gap", mid=None)
OB = _Poi(near=96.0, top=96.0, bottom=82.0, name="the bias order block", short="Bias order block", mid=89.0)
INSIDE_OB = _Poi(near=90.0, top=90.0, bottom=89.0, name="the unfilled 1h fair value gap", short="1h fair value gap", mid=None)


def test_option_b_is_the_next_level_beyond_a_with_its_condition() -> None:
    a, b = look_options([GAP, OB], BULL, "1h")
    assert (a.key, a.name, a.top, a.bottom, a.condition) == ("A", "1h fair value gap", 100.0, 99.0, "")
    assert (b.key, b.name, b.top, b.bottom) == ("B", "Bias order block", 96.0, 82.0)
    assert b.condition == "only after a 1h close below the POI"


def test_option_b_is_mirrored_for_a_short() -> None:
    # mirrored space: the same zones read as real prices -100..-99 and -96..-82
    a, b = look_options([GAP, OB], BEAR, "1h")
    assert (a.top, a.bottom) == (-99.0, -100.0)
    assert (b.top, b.bottom) == (-82.0, -96.0)
    assert b.condition == "only after a 1h close above the POI"


def test_a_level_inside_a_is_not_option_b() -> None:
    assert [option.key for option in look_options([OB, INSIDE_OB], BULL, "1h")] == ["A"]
    assert look_options([], BULL, "1h") == ()


def test_nearest_poi_is_unchanged_by_the_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(plan, "_pois", lambda *args, **kwargs: [GAP, OB])
    assert plan._nearest_poi(None, None, 0.0) == (100.0, "the unfilled 1h fair value gap", None)  # type: ignore[arg-type]
