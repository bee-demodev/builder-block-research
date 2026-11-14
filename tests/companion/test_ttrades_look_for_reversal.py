"""What to look for while a reversal waits for its key level, and for its setup there
(display only).

Prices from ``reversal_scenario`` (bullish story): previous bias candle O 70 H 71 L
``previous_low`` C 58, forming candle low 54 at ``level_taken``. Bearish fair value gaps
71-80 and 86-90 sit above. The mirror reflects every price around the scenario's pivot.
"""

from __future__ import annotations

import dataclasses
import math

import pytest

import companion.styles.ttrades.plan as plan
import companion.styles.ttrades.style as style
from companion.timeframes import get_stack
from companion.types import TimeframeStack, Verdict
from test_ttrades_plan import evaluate
from ttrades_scenarios import _SWING_SLOT, reversal_scenario

DAILY = get_stack("1D / 1h / 5m")
FOUR_HOUR = get_stack("4h / 15m / 1m")
STACKS = pytest.mark.parametrize("stack", [DAILY, FOUR_HOUR], ids=lambda stack: stack.name)
MIRROR = pytest.mark.parametrize("mirror", [False, True], ids=["long", "short"])


def _turn(stack: TimeframeStack) -> str:
    # the CISD that confirms the wick: the setup timeframe, and the entry timeframe too with a 1D bias,
    # only inside its clock window (rules.md 4.3, reversal.py stage c3)
    return f"{stack.setup} (or {stack.entry} from 08:30 to 11:00)" if stack.bias == "1D" else stack.setup


def _reach_band(verdict: Verdict) -> float:
    """The reach band the reversal check states in its detail ("... range = 2.15)")."""
    detail = next(item.detail for item in verdict.criteria if item.key == "rev_key_level_reached")
    return float(detail.split("range = ")[1].split(")")[0].replace(",", ""))


@STACKS
@MIRROR
def test_waiting_for_the_key_level_says_what_to_look_for(stack: TimeframeStack, mirror: bool) -> None:
    # previous low 50: the forming low 54 is 4 away, outside the reach band, so no key level is reached
    scenario = reversal_scenario(stack, mirror=mirror, previous_low=50.0)
    verdict = evaluate(scenario, "level_taken")
    look = verdict.look_for
    assert verdict.decision == "no_trade" and look is not None
    assert (look.kind, look.direction, look.timeframe, look.entry_timeframe) == (
        "reversal", "short" if mirror else "long", stack.setup, stack.entry,
    )  # fmt: skip

    lo, toward, back = ("high", "up", "below") if mirror else ("low", "down", "above")
    run = "up-close" if mirror else "down-close"
    assert [(step.label, step.status) for step in look.steps] == [
        (f"{stack.bias} trades {toward} into the previous {stack.bias} {lo}", "next"),
        (f"{stack.setup} C1 / C2 there, closing back {back} it", "later"),
        (f"{_turn(stack)} turns {'down' if mirror else 'up'}: a close {back} the {run} run, the entry", "later"),
    ]
    # option A is the level with the band the rules count as reaching it, to its last NQ tick (0.25), real prices
    (a,) = look.options
    far = math.floor((50.0 + _reach_band(verdict)) / 0.25) * 0.25
    top, bottom = sorted((scenario.price(50.0), scenario.price(far)), reverse=True)
    assert (a.key, a.name, a.condition) == ("A", f"Previous {stack.bias} {lo}", "")
    assert (a.top, a.bottom) == (pytest.approx(top), pytest.approx(bottom))
    assert look.entry == f"{_turn(stack)} close {back} the run" and look.entry_during
    assert look.stop == f"{'above' if mirror else 'below'} the reversal wick {lo}"
    # the exit is in words (2R depends on a wick not formed yet); the structural level is the previous candle's EQ
    name = "previous day EQ" if stack.bias == "1D" else f"previous {stack.bias} EQ"
    assert look.target == f"2R, then {name}"
    assert look.target_price == pytest.approx(scenario.price((71.0 + 50.0) / 2))


@STACKS
def test_the_nearer_side_is_the_one_shown_with_the_next_level_beyond_as_b(stack: TimeframeStack) -> None:
    # previous low 20 is far below; the previous high 71 is nearer, with the gaps 71-80 and 86-90 above it
    scenario = reversal_scenario(stack, previous_low=20.0)
    verdict = evaluate(scenario, "level_taken")
    look = verdict.look_for
    assert verdict.decision == "no_trade" and look is not None and look.direction == "short"
    a, b = look.options
    assert (a.name, a.top) == (f"Previous {stack.bias} high", 71.0) and a.bottom < 71.0
    # the gap 71-80 touches A, so it is the same place; B is the next one wholly beyond
    assert (b.key, b.name, b.top, b.bottom) == ("B", f"{stack.bias} fair value gap", 90.0, 86.0)
    assert b.condition == "if price trades through A first"  # rules.md 7.1 counts a trade into a level, not a close
    # the steps still name both routes; the look-for has one direction
    assert [step.label for step in verdict.steps[-2:]] == [
        f"A long opens if the {stack.bias} reaches a key level", f"A short opens if the {stack.bias} reaches a key level",
    ]  # fmt: skip


def test_a_forced_side_shows_its_own_level_even_when_the_other_is_nearer() -> None:
    look = evaluate(reversal_scenario(DAILY, previous_low=20.0), "level_taken", "long").look_for
    assert look is not None and look.direction == "long"
    assert [(option.name, option.bottom) for option in look.options] == [("Previous 1D low", 20.0)]


def test_without_a_tolerance_the_band_is_the_level_and_one_tick_through_it() -> None:
    look = evaluate(reversal_scenario(DAILY, previous_low=20.0), "level_taken", reversal_level_tolerance_frac=0.0).look_for
    assert look is not None
    # the previous high 71 must itself trade: the box is 71 to one NQ tick above, all of it counting as reached
    assert (look.options[0].top, look.options[0].bottom) == (71.25, 71.0)


@STACKS
def test_no_key_level_means_nothing_to_look_for(stack: TimeframeStack, monkeypatch: pytest.MonkeyPatch) -> None:
    scenario = reversal_scenario(stack, previous_low=50.0)
    before = evaluate(scenario, "level_taken")
    monkeypatch.setattr(plan, "nearest_level", lambda *args, **kwargs: None)
    after = evaluate(scenario, "level_taken")
    assert before.look_for is not None and after.look_for is None
    assert (after.decision, after.stage, after.criteria) == (before.decision, before.stage, before.criteria)


@STACKS
@MIRROR
def test_at_the_level_the_setup_is_next(stack: TimeframeStack, mirror: bool) -> None:
    scenario = reversal_scenario(stack, mirror=mirror)
    verdict = evaluate(scenario, "level_taken")
    look = verdict.look_for
    assert verdict.decision == "watch" and verdict.path_family == "reversal" and verdict.plan is None and look is not None
    assert look.direction == ("short" if mirror else "long")
    # the first line keeps what the rules' own step says (a quality check can block it)
    assert verdict.steps[0].status in ("done", "blocked")
    assert [step.status for step in look.steps] == [verdict.steps[0].status, "next", "later"]
    (a,) = look.options
    assert a.name == f"Previous {stack.bias} {'high' if mirror else 'low'}"
    assert scenario.price(55.0) in (a.top, a.bottom)
    # the band's far edge (55 + 10% of the average range, 1.975) is the last tick that counts, not a raw 56.975
    assert scenario.price(56.75) in (a.top, a.bottom)


@STACKS
def test_the_conservative_turn_and_entry_are_one_line(stack: TimeframeStack) -> None:
    scenario = reversal_scenario(stack)
    after_reclaim = scenario.builder.at(_SWING_SLOT[stack.bias] + 1, 1)
    verdict = evaluate(scenario, after_reclaim, entry_mode_reversal="conservative")
    look = verdict.look_for
    assert verdict.plan is None and look is not None
    assert [step.status for step in look.steps][1:] == ["done", "next"]
    assert look.steps[2].label == f"After the turn: a {stack.entry} pullback that holds, then a close back up"
    assert (look.entry, look.stop, look.entry_during) == (
        f"{stack.entry} close back up after a pullback that holds", f"below the {stack.entry} pullback low", False,
    )  # fmt: skip


@STACKS
def test_nothing_to_look_for_once_the_rules_price_the_turn(stack: TimeframeStack) -> None:
    scenario = reversal_scenario(stack)
    for moment in ("trigger", scenario.builder.at(_SWING_SLOT[stack.bias] + 1, 1)):
        verdict = evaluate(scenario, moment)
        assert verdict.plan is not None and verdict.look_for is None, moment


def _strip(verdict: Verdict) -> Verdict:
    return dataclasses.replace(verdict, look_for=None)


@STACKS
@MIRROR
@pytest.mark.parametrize("previous_low", [50.0, 20.0, 55.0], ids=["route-near", "route-far", "reached"])
@pytest.mark.parametrize("moment", ["level_taken", "trigger"])
def test_look_for_changes_nothing_else(
    stack: TimeframeStack, mirror: bool, previous_low: float, moment: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    scenario = reversal_scenario(stack, mirror=mirror, previous_low=previous_low)
    with_it = evaluate(scenario, moment)
    monkeypatch.setattr(style, "build_reversal_look_for", lambda *args, **kwargs: None)
    monkeypatch.setattr(style, "build_route_look_for", lambda *args, **kwargs: None)
    without = evaluate(scenario, moment)
    assert _strip(with_it) == without


def test_a_conservative_reversal_waiting_on_its_setup_changes_nothing_else(monkeypatch: pytest.MonkeyPatch) -> None:
    scenario = reversal_scenario(FOUR_HOUR)
    moment = scenario.builder.at(_SWING_SLOT["4h"] + 1, 1)
    with_it = evaluate(scenario, moment, entry_mode_reversal="conservative")
    monkeypatch.setattr(style, "build_reversal_look_for", lambda *args, **kwargs: None)
    without = evaluate(scenario, moment, entry_mode_reversal="conservative")
    assert with_it.look_for is not None and _strip(with_it) == without
