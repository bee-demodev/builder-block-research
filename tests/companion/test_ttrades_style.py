"""The TTrades checklist end to end, on synthetic markets with known outcomes.

The markets come from ``ttrades_scenarios`` (same folder); each scenario's docstring
spells out the prices the assertions below rely on.

``OLD_RULES`` holds the config values that put back the rules as they stood before the
trader's answers of 2026-11-12 (rules.md section 12, questions 1, 2, 14, 15, 16, 18),
except the removed "three continuation closes" reversal context, which has no switch.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import pytest

from companion.styles.ttrades import TTradesStyle, load_config
from companion.timeframes import get_stack, make_stack
from companion.types import CriterionResult, Verdict
from ttrades_scenarios import SYMBOL, Scenario, continuation_scenario, reversal_scenario

DAILY = get_stack("1D / 1h / 5m")
FOUR_HOUR = get_stack("4h / 15m / 1m")

OLD_RULES: dict[str, Any] = {
    "entry_mode_continuation": "conservative",
    "entry_mode_reversal": "conservative",
    "target_mode": "structural",
    "reward_check_role": "quality",
    "objective_open_role": "gate",
    "session_filter_role": "quality",
    "reversal_key_levels": ["previous_candle"],
    "reversal_level_tolerance_frac": 0.0,
    "reversal_expansion_test": "off",
}


def evaluate(scenario: Scenario, moment: str, *, until: pd.Timestamp | None = None, **overrides: Any) -> Verdict:
    style = TTradesStyle(load_config(overrides=overrides))
    return style.evaluate(SYMBOL, scenario.times[moment].to_pydatetime(), scenario.stack, scenario.source(until))


def criterion(verdict: Verdict, key: str) -> CriterionResult:
    matches = [item for item in verdict.criteria if item.key == key]
    assert len(matches) == 1, f"{key}: {len(matches)} results"
    return matches[0]


def failed(verdict: Verdict, *roles: str) -> list[str]:
    """Keys of the criteria with one of ``roles`` on the verdict's own path that did not pass."""
    return [
        item.key
        for item in verdict.criteria
        if item.role in roles
        and item.passed is not True
        and (item.group == "shared" or item.group.startswith(verdict.path_family))
    ]


# --- continuation --------------------------------------------------------------


def test_bullish_continuation_reaches_entry_ready() -> None:
    verdict = evaluate(continuation_scenario(DAILY), "trigger")
    assert (verdict.decision, verdict.bias, verdict.path_family, verdict.stage) == (
        "long", "bullish", "continuation", "c4",
    )
    assert failed(verdict, "gate", "step", "quality") == []
    # either mode: the entry CISD confirmed first; the exit is 2R = 97.5 + 2 * 6.5
    assert verdict.entry == pytest.approx(97.5)
    assert verdict.stop == pytest.approx(91.0)
    assert verdict.targets == pytest.approx((110.5,))
    assert "91.00" in verdict.invalidation and "88.00" in verdict.invalidation
    assert "105.00" not in verdict.invalidation  # the previous high being taken no longer ends the path
    # details state what was observed
    assert "84.00" in criterion(verdict, "bias_poi_present").detail
    assert "bias order block 82.00-96.00" in criterion(verdict, "cont_poi_tagged").detail
    assert "97.00" in criterion(verdict, "cont_entry_cisd_confirmed").detail
    trigger = criterion(verdict, "cont_entry_trigger").detail
    assert "mode either (the entry-timeframe CISD is the first to confirm" in trigger and "order block" in trigger
    # the structural levels are reported in R terms and never block
    reward = criterion(verdict, "cont_reward_at_least_2r")
    assert (reward.passed, reward.role) == (False, "advisory")
    assert "2R = 110.50" in reward.detail and "105.00" in reward.detail and "1.15R" in reward.detail
    assert "115.00" in reward.detail


def test_bullish_continuation_markup_carries_the_levels_the_verdict_relies_on() -> None:
    verdict = evaluate(continuation_scenario(DAILY), "trigger")
    by_label = {item.label: item for item in verdict.markup}
    assert by_label["Previous bias candle high"].price == pytest.approx(105.0)
    assert by_label["Previous bias candle low"].price == pytest.approx(80.0)
    assert by_label["Previous bias candle equilibrium"].price == pytest.approx(92.5)
    assert by_label["Respect level (wick midpoint)"].price == pytest.approx(88.0)
    block = by_label["Bias order block"]
    assert (block.kind, block.top, block.bottom) == ("zone", pytest.approx(96.0), pytest.approx(82.0))
    assert by_label["Protected low (stop swing)"].price == pytest.approx(91.0)
    assert by_label["Entry"].price == pytest.approx(97.5)
    assert by_label["Stop"].price == pytest.approx(91.0)
    assert by_label["Target 1"].price == pytest.approx(110.5)
    assert "Target 2" not in by_label
    # the structural levels stay on the chart as information
    assert by_label["Structural level 1"].price == pytest.approx(105.0)
    assert by_label["Structural level 2"].price == pytest.approx(115.0)


def test_bearish_continuation_is_the_mirror() -> None:
    scenario = continuation_scenario(DAILY, mirror=True)
    verdict = evaluate(scenario, "trigger")
    assert (verdict.decision, verdict.bias, verdict.path_family, verdict.stage) == (
        "short", "bearish", "continuation", "c4",
    )
    assert verdict.entry == pytest.approx(scenario.price(97.5))
    assert verdict.stop == pytest.approx(scenario.price(91.0))
    assert verdict.targets == pytest.approx((scenario.price(110.5),))
    assert verdict.stop > verdict.entry > verdict.targets[0]
    assert "took the prior candle's high 112.00" in criterion(verdict, "bias_closure_directional").detail


def test_continuation_stage_follows_the_steps_as_bars_close() -> None:
    scenario = continuation_scenario(DAILY)
    early = evaluate(scenario, "before_setup")  # the swing setup bar has not closed
    assert (early.decision, early.stage) == ("watch", "c1")
    assert criterion(early, "bias_cisd_confirmed").passed is True
    assert criterion(early, "cont_poi_tagged").passed is False
    assert early.entry is None and early.stop is None and early.targets == ()

    # setup closure and entry CISD, no continuation order block yet: conservative still waits
    confirmed = evaluate(scenario, "setup_closed", entry_mode_continuation="conservative")
    assert (confirmed.decision, confirmed.stage) == ("watch", "c3")
    assert criterion(confirmed, "cont_setup_closure").passed is True
    assert criterion(confirmed, "cont_entry_cisd_confirmed").passed is True
    assert criterion(confirmed, "cont_entry_trigger").passed is False
    assert criterion(confirmed, "cont_reward_at_least_2r").passed is None

    late = evaluate(scenario, "window_closed")  # setup Candle 3 closed weak: the window is over
    assert (late.decision, late.stage) == ("watch", "c4")
    assert failed(late, "quality") == ["cont_entry_window_open"]
    assert late.entry is None


def test_neutral_bias_leaves_only_the_reversal_path() -> None:
    scenario = continuation_scenario(DAILY, inside_bias_bar=True)
    # the forming candle's low 91 is 1.0 above the previous low 90: not a key level unless "near" counts
    strict = evaluate(scenario, "trigger", reversal_level_tolerance_frac=0.0)
    assert (strict.decision, strict.bias, strict.path_family, strict.stage) == (
        "no_trade", "neutral", "none", "none",
    )
    closure = criterion(strict, "bias_closure_directional")
    assert closure.passed is False and "inside bar" in closure.detail
    assert strict.entry is None and strict.targets == ()
    near = evaluate(scenario, "trigger")
    assert (near.bias, near.path_family) == ("neutral", "reversal")
    assert "came within 1.00" in criterion(near, "rev_key_level_reached").detail


def test_gate_failure_equilibrium_not_respected_is_no_trade() -> None:
    # the setup bar before the swing bar closes at 87, below the respect level 88
    scenario = continuation_scenario(DAILY, previous_setup_bar=(96.8, 97.8, 86.0, 87.0))
    verdict = evaluate(scenario, "trigger")
    assert (verdict.decision, verdict.path_family, verdict.stage) == ("no_trade", "none", "none")
    assert verdict.bias == "bullish"  # the bias read stands; the path is dead for this candle
    respected = criterion(verdict, "cont_eq_respected")
    assert respected.passed is False
    assert "87.00" in respected.detail and "88.00" in respected.detail
    assert "cont_eq_respected" in verdict.summary


def test_structural_level_closer_than_2r_blocks_only_when_switched_back_to_quality() -> None:
    # previous high 100: 2.3 away against 2.2 of risk on the order-block entry
    scenario = continuation_scenario(DAILY, first_target=100.0)
    verdict = evaluate(scenario, "trigger", entry_mode_continuation="conservative")
    assert verdict.decision == "long"  # the exit is the R multiple, wherever the structural level sits
    assert verdict.targets == pytest.approx((97.7 + 2 * 2.2,))
    reward = criterion(verdict, "cont_reward_at_least_2r")
    assert (reward.passed, reward.role) == (False, "advisory") and "1.05R" in reward.detail

    old = evaluate(scenario, "trigger", **OLD_RULES)
    assert (old.decision, old.path_family, old.stage) == ("watch", "continuation", "c4")
    assert failed(old, "gate", "step") == []
    assert failed(old, "quality") == ["cont_reward_at_least_2r"]
    reward = criterion(old, "cont_reward_at_least_2r")
    assert "1.05R" in reward.detail and "limit entry at 97.00" in reward.detail
    # the numbers are still shown when only the reward (or session) check fails
    assert old.entry == pytest.approx(97.7) and old.stop == pytest.approx(95.5)
    assert old.targets[0] == pytest.approx(100.0)


def test_body_stop_is_used_only_to_rescue_a_blocking_reward_check() -> None:
    # 3.9 to the previous high: 1.77R on the wick stop 95.5, 2.05R on the body stop 95.8
    scenario = continuation_scenario(DAILY, first_target=101.6)
    old = evaluate(scenario, "trigger", **OLD_RULES)
    assert old.decision == "long"
    assert old.stop == pytest.approx(95.8)
    assert "BODY STOP" in old.summary and "BODY STOP" in criterion(old, "cont_reward_at_least_2r").detail
    assert any(item.label == "Stop (body stop)" for item in old.markup)
    # with the advisory reward check the stop stays on the protected swing
    verdict = evaluate(scenario, "trigger", entry_mode_continuation="conservative")
    assert verdict.decision == "long" and verdict.stop == pytest.approx(95.5)
    assert "BODY STOP" not in verdict.summary


def test_same_scenario_on_a_non_default_stack() -> None:
    verdict = evaluate(continuation_scenario(FOUR_HOUR), "trigger")
    assert (verdict.decision, verdict.bias, verdict.path_family, verdict.stage) == (
        "long", "bullish", "continuation", "c4",
    )
    assert verdict.entry == pytest.approx(97.5) and verdict.stop == pytest.approx(91.0)
    assert verdict.targets == pytest.approx((110.5,))
    # the forming 4h candle made its low 63% of the way in: a late wick is "large", so one structural level only
    assert "No second structural level: the forming candle's wick is large" in criterion(
        verdict, "cont_reward_at_least_2r"
    ).detail
    assert {item.timeframe for item in verdict.criteria} >= {"4h", "15m", "1m"}
    mirrored = evaluate(continuation_scenario(FOUR_HOUR, mirror=True), "trigger")
    assert mirrored.decision == "short"


def test_custom_stack_that_ttrades_never_states_runs_and_is_flagged() -> None:
    stack = make_stack("1D", "15m", "1m")
    verdict = evaluate(continuation_scenario(stack), "trigger")
    stated = criterion(verdict, "stack_pairing_stated")
    assert stated.passed is False and stated.role == "advisory"
    blocked = evaluate(continuation_scenario(stack), "trigger", block_unstated_stacks=True)
    assert blocked.decision == "no_trade" and criterion(blocked, "stack_pairing_stated").role == "gate"


def test_session_outside_the_kill_zones_is_shown_but_does_not_block() -> None:
    # the same continuation on 1D / 15m / 1m triggers at 21:45 New York: outside every kill zone
    stack = make_stack("1D", "15m", "1m")
    scenario = continuation_scenario(stack)
    verdict = evaluate(scenario, "trigger")
    session = criterion(verdict, "session_filter_ok")
    assert (session.passed, session.role) == (False, "advisory") and "outside the kill zones" in session.detail
    assert verdict.decision == "long" and "Outside the kill zones" in verdict.summary
    # the reversal's CISD bar closes 08:25, five minutes before the New York window: a long all the same
    reversal = evaluate(reversal_scenario(DAILY), "trigger")
    assert criterion(reversal, "session_filter_ok").passed is False and reversal.decision == "long"
    mirrored = evaluate(reversal_scenario(DAILY, mirror=True), "trigger")
    assert criterion(mirrored, "session_filter_ok").passed is False and mirrored.decision == "short"
    # switched back: the old rule keeps it at watch and still shows the numbers
    old = evaluate(scenario, "trigger", session_filter_role="quality")
    assert (old.decision, old.stage) == ("watch", "c4")
    assert failed(old, "quality") == ["session_filter_ok"]
    assert old.entry == pytest.approx(97.5)


def test_either_mode_fires_on_the_cisd_when_it_confirms_first() -> None:
    scenario = continuation_scenario(DAILY)
    # at the close of the setup closure the entry CISD is there and no order block has formed yet
    verdict = evaluate(scenario, "setup_closed")
    assert (verdict.decision, verdict.stage) == ("long", "c4")
    assert verdict.entry == pytest.approx(97.5) and verdict.stop == pytest.approx(91.0)
    detail = criterion(verdict, "cont_entry_trigger").detail
    assert "the entry-timeframe CISD is the first to confirm)" in detail
    assert "Trigger: entry CISD" in verdict.summary
    # the same trigger is still the one reported after the order block has formed
    later = evaluate(scenario, "trigger")
    assert (later.entry, later.stop) == (verdict.entry, verdict.stop)
    assert "1 other live trigger(s) not chosen: order block" in criterion(later, "cont_entry_trigger").detail
    # ... unless the pick is switched to the latest trigger
    latest = evaluate(scenario, "trigger", entry_either_pick="latest")
    assert latest.entry == pytest.approx(97.7) and latest.stop == pytest.approx(95.5)
    assert "a continuation order block is the latest to confirm" in criterion(latest, "cont_entry_trigger").detail


def test_either_mode_fires_on_the_order_block_when_it_is_the_first_allowed_trigger() -> None:
    # closed_wick_large_frac 0.7 makes the bias Candle 2 (wick 64% of range) an expansion candle:
    # rules.md section 6 then demands a continuation, so the CISD entry is not available
    scenario = continuation_scenario(DAILY)
    waiting = evaluate(scenario, "setup_closed", closed_wick_large_frac=0.7)
    assert (waiting.decision, waiting.stage) == ("watch", "c3")
    assert criterion(waiting, "bias_c2_not_expanded").passed is False
    assert "the CISD entry is not allowed" in criterion(waiting, "cont_entry_trigger").detail
    verdict = evaluate(scenario, "trigger", closed_wick_large_frac=0.7)
    assert (verdict.decision, verdict.stage) == ("long", "c4")
    assert verdict.entry == pytest.approx(97.7) and verdict.stop == pytest.approx(95.5)
    assert verdict.targets == pytest.approx((97.7 + 2 * 2.2,))
    detail = criterion(verdict, "cont_entry_trigger").detail
    assert "mode either (a continuation order block is the first to confirm)" in detail
    assert "Trigger: continuation order block" in verdict.summary


def test_entry_mode_can_be_set_back_to_one_kind_of_trigger() -> None:
    scenario = continuation_scenario(DAILY)
    conservative = evaluate(scenario, "setup_closed", entry_mode_continuation="conservative")
    assert conservative.decision == "watch"
    conservative = evaluate(scenario, "trigger", entry_mode_continuation="conservative")
    assert conservative.decision == "long"
    assert conservative.entry == pytest.approx(97.7) and conservative.stop == pytest.approx(95.5)
    assert "mode conservative" in criterion(conservative, "cont_entry_trigger").detail
    # aggressive: the entry CISD is the trigger, entry at the close of the setup closure
    aggressive = evaluate(scenario, "trigger", entry_mode_continuation="aggressive")
    assert aggressive.decision == "long"
    assert aggressive.entry == pytest.approx(97.5) and aggressive.stop == pytest.approx(91.0)
    assert "mode aggressive" in criterion(aggressive, "cont_entry_trigger").detail
    # under the old reward rule the CISD entry is 1.15R from the previous high: watch
    old_reward = evaluate(scenario, "setup_closed", entry_mode_continuation="aggressive", reward_check_role="quality")
    assert old_reward.decision == "watch" and failed(old_reward, "quality") == ["cont_reward_at_least_2r"]


@pytest.mark.parametrize(("target_rr", "continuation_exit", "reversal_exit"), [(1.0, 104.0, 60.8), (2.0, 110.5, 64.2)])
def test_exit_is_the_configured_multiple_of_risk(target_rr: float, continuation_exit: float, reversal_exit: float) -> None:
    # continuation: entry 97.5, risk 6.5; reversal: entry 57.4, risk 3.4
    continuation = evaluate(continuation_scenario(DAILY), "trigger", target_rr=target_rr)
    assert continuation.decision == "long" and continuation.targets == pytest.approx((continuation_exit,))
    assert f"{target_rr:.2f}R" in continuation.summary
    reversal = evaluate(reversal_scenario(DAILY), "trigger", target_rr=target_rr)
    assert reversal.decision == "long" and reversal.targets == pytest.approx((reversal_exit,))
    short_scenario = reversal_scenario(DAILY, mirror=True)
    short = evaluate(short_scenario, "trigger", target_rr=target_rr)
    assert short.decision == "short" and short.targets == pytest.approx((short_scenario.price(reversal_exit),))


def test_target_mode_structural_puts_the_structural_levels_back_as_targets() -> None:
    continuation = evaluate(continuation_scenario(DAILY), "trigger", target_mode="structural")
    assert continuation.decision == "long" and continuation.targets == pytest.approx((105.0, 115.0))
    assert not any(item.label.startswith("Structural level") for item in continuation.markup)
    reversal = evaluate(reversal_scenario(DAILY), "trigger", target_mode="structural")
    assert reversal.decision == "long" and reversal.targets == pytest.approx((63.0, 71.0))


def test_previous_high_already_taken_ends_the_continuation_only_as_a_gate() -> None:
    # previous bias candle high 98; the forming candle trades 99 before the setup forms
    scenario = continuation_scenario(DAILY, first_target=98.0, previous_setup_bar=(96.8, 99.0, 96.5, 97.0))
    verdict = evaluate(scenario, "trigger")
    taken = criterion(verdict, "cont_objective_open")
    assert (taken.passed, taken.role) == (False, "advisory") and "already taken" in taken.detail
    # the path stays alive, but the higher-timeframe target was met before the trigger: late, so watch
    assert (verdict.decision, verdict.path_family, verdict.stage) == ("watch", "continuation", "c4")
    assert failed(verdict, "quality") == ["cont_objective_open_at_trigger"]
    assert "already taken" in criterion(verdict, "cont_objective_open_at_trigger").detail
    advisory = evaluate(scenario, "trigger", objective_at_trigger_role="advisory")
    assert (advisory.decision, advisory.path_family, advisory.stage) == ("long", "continuation", "c4")
    old = evaluate(scenario, "trigger", objective_open_role="gate")
    assert criterion(old, "cont_objective_open").role == "gate"
    assert old.decision != "long" and old.path_family != "continuation"
    assert "98.00 being taken before entry" not in verdict.invalidation


# --- entries: "Why Your Continuations Fail", timing, stepping stones (rules.md 6, 2026-11-12) --

# the dip to 91 is fine, but the entry CISD needs 5 bars to close back above 97.0: not a V
SLOW_SWING = [
    (97.0, 97.2, 95.0, 95.2),
    (95.2, 95.5, 93.0, 93.2),
    (93.2, 93.5, 91.0, 91.5),  # the setup swing low
    (91.5, 94.0, 91.2, 93.8),
    (93.8, 95.0, 93.0, 94.5),
    (94.5, 96.5, 94.0, 95.0),
    (95.0, 96.8, 94.8, 96.6),
    (96.6, 97.6, 96.5, 97.4),  # the slow close-through: range 91.00-97.80 (97.80 = the leg's top)
]
# after the slow close-through: a close above the range high, a pullback, a quick close-through
BREAKOUT_CONTINUATION = [
    (97.5, 98.4, 97.4, 98.2),  # breakout: closes above 97.80
    (98.2, 98.3, 97.2, 97.3),
    (97.3, 97.4, 96.9, 97.0),  # pullback into the entry order block
    (97.0, 98.35, 96.95, 98.3),  # new continuation: closes above 98.2 one bar after the low
]
# after the pullback low 95.5 price chops for three bars and closes above 97.5 on the fourth: slow
SLOW_TRIGGER = [
    (97.5, 97.8, 96.5, 96.6),
    (96.6, 96.8, 95.5, 95.8),
    (95.8, 96.9, 95.7, 96.5),
    (96.5, 97.0, 96.0, 96.6),
    (96.6, 97.1, 96.1, 96.8),
    (96.8, 97.9, 96.7, 97.7),
]
# then another pullback into the entry order block and a quick close above 97.7
NEXT_CONTINUATION = [(97.7, 97.8, 97.1, 97.2), (97.2, 97.25, 96.9, 97.0), (97.0, 97.85, 96.95, 97.8)]
ORDER_BLOCK_ONLY = {"closed_wick_large_frac": 0.7}  # bias Candle 2 expanded: only the order-block entry


def test_a_slow_close_through_makes_a_range_and_internal_triggers_are_not_taken() -> None:
    verdict = evaluate(continuation_scenario(DAILY, swing_rows=SLOW_SWING), "trigger")
    assert (verdict.decision, verdict.stage) == ("watch", "c4")
    assert "cont_not_inside_consolidation" in failed(verdict, "quality")
    detail = criterion(verdict, "cont_not_inside_consolidation").detail
    assert "consolidating between 91.00 and 97.80" in detail and "internal to the range" in detail
    swift = criterion(verdict, "cont_entry_cisd_swift")
    assert (swift.passed, swift.role) == (False, "advisory")


def test_a_breakout_of_the_range_with_a_new_continuation_is_taken() -> None:
    scenario = continuation_scenario(DAILY, swing_rows=SLOW_SWING, trigger_rows=BREAKOUT_CONTINUATION)
    verdict = evaluate(scenario, "trigger")
    assert verdict.decision == "long"
    assert verdict.entry == pytest.approx(98.3) and verdict.stop == pytest.approx(96.9)
    check = criterion(verdict, "cont_not_inside_consolidation")
    assert check.passed is True and "Breakout" in check.detail
    assert "not a clean continuation" in criterion(verdict, "cont_entry_trigger").detail


def test_a_slow_trigger_is_skipped_for_the_next_clean_continuation() -> None:
    alone = evaluate(continuation_scenario(DAILY, trigger_rows=SLOW_TRIGGER), "trigger", **ORDER_BLOCK_ONLY)
    assert (alone.decision, alone.stage) == ("watch", "c4")
    assert failed(alone, "quality") == ["cont_trigger_v_shape"]
    assert "Wait for another continuation" in criterion(alone, "cont_trigger_v_shape").detail
    scenario = continuation_scenario(DAILY, trigger_rows=[*SLOW_TRIGGER, *NEXT_CONTINUATION])
    verdict = evaluate(scenario, "trigger", **ORDER_BLOCK_ONLY)
    assert verdict.decision == "long" and criterion(verdict, "cont_trigger_v_shape").passed is True
    assert verdict.entry == pytest.approx(97.8) and verdict.stop == pytest.approx(96.9)
    old = evaluate(scenario, "trigger", wait_for_clean_continuation=False, **ORDER_BLOCK_ONLY)
    assert old.decision == "watch" and failed(old, "quality") == ["cont_trigger_v_shape"]


def test_a_trigger_late_in_its_setup_candle_waits_for_the_next_one() -> None:
    scenario = continuation_scenario(DAILY)
    on_time = evaluate(scenario, "trigger", **ORDER_BLOCK_ONLY)  # closes 08:15, 25% into the 08:00 candle
    assert on_time.decision == "long"
    assert "25% into the 1h candle" in criterion(on_time, "cont_entry_early_in_candle").detail
    late = evaluate(scenario, "trigger", entry_latest_candle_frac=0.2, **ORDER_BLOCK_ONLY)
    assert late.decision == "watch" and failed(late, "quality") == ["cont_entry_early_in_candle"]


def test_a_newer_protected_low_after_the_entry_is_reported_for_the_stop_only() -> None:
    # the CISD entry (stop 91) fires first; the order block that follows leaves a higher protected low 95.5
    verdict = evaluate(continuation_scenario(DAILY), "trigger")
    assert verdict.decision == "long" and verdict.stop == pytest.approx(91.0)
    check = criterion(verdict, "cont_newer_protected_low")
    assert (check.passed, check.role) == (True, "advisory") and "95.50" in check.detail


# --- reversal ------------------------------------------------------------------


def test_bullish_reversal_reaches_entry_ready() -> None:
    verdict = evaluate(reversal_scenario(DAILY), "trigger")
    # the bias keeps its closure-based value; the reversal fades it (rules.md 7.1)
    assert (verdict.decision, verdict.bias, verdict.path_family, verdict.stage) == (
        "long", "bearish", "reversal", "c4",
    )
    assert failed(verdict, "gate", "step", "quality") == []
    # either mode: the CISD bar is the trigger, the stop is the wick low, the exit 2R
    assert verdict.entry == pytest.approx(57.4)
    assert verdict.stop == pytest.approx(54.0)
    assert verdict.targets == pytest.approx((64.2,))
    reached = criterion(verdict, "rev_key_level_reached")
    assert "traded below the previous 1D candle's low 55.00 by 1.00" in reached.detail
    expansion = criterion(verdict, "rev_expansion_into_level")
    assert expansion.role == "quality" and "down-close 1h candle(s)" in expansion.detail
    assert "above the previous 1D candle's low 55.00" in criterion(verdict, "rev_reclaim").detail
    confirmation = criterion(verdict, "rev_cisd_confirmed")
    assert confirmation.timeframe == "5m"  # daily bias inside the New York window: entry frame accepted
    assert "series of 3 down-close 5m bar(s)" in confirmation.detail
    assert "63.00" in criterion(verdict, "rev_reward_at_least_2r").detail
    assert criterion(verdict, "bias_candle_index_ok").passed is False  # continuation is blocked (case D)


def test_bearish_reversal_is_the_mirror() -> None:
    scenario = reversal_scenario(DAILY, mirror=True)
    verdict = evaluate(scenario, "trigger")
    assert (verdict.decision, verdict.bias, verdict.path_family, verdict.stage) == (
        "short", "bullish", "reversal", "c4",
    )
    assert verdict.entry == pytest.approx(scenario.price(57.4))
    assert verdict.stop == pytest.approx(scenario.price(54.0))
    assert verdict.targets == pytest.approx((scenario.price(64.2),))
    assert verdict.stop > verdict.entry > verdict.targets[0]
    assert "traded above the previous 1D candle's high 145.00 by 1.00" in criterion(
        verdict, "rev_key_level_reached"
    ).detail
    assert "up-close candles" in criterion(verdict, "rev_cisd_confirmed").label


def test_reversal_waits_for_the_reclaim_after_the_level_is_reached() -> None:
    verdict = evaluate(reversal_scenario(DAILY), "level_taken")
    assert (verdict.decision, verdict.path_family, verdict.stage) == ("watch", "reversal", "c1")
    assert criterion(verdict, "rev_key_level_reached").passed is True
    assert criterion(verdict, "rev_reclaim").passed is False
    assert "rev_reclaim" in verdict.summary


def test_reversal_near_a_key_level_without_trading_through_it() -> None:
    # the low 55.05 stops 0.05 above the previous low 55
    scenario = reversal_scenario(DAILY, wick_low=55.05)
    verdict = evaluate(scenario, "trigger")
    assert (verdict.decision, verdict.path_family, verdict.stage) == ("long", "reversal", "c4")
    reached = criterion(verdict, "rev_key_level_reached")
    assert reached.passed is True
    assert "came within 0.05" in reached.detail and "the previous 1D candle's low 55.00" in reached.detail
    assert "without trading through it" in reached.detail and "tolerance 10%" in reached.detail
    assert verdict.entry == pytest.approx(57.4) and verdict.stop == pytest.approx(55.05)
    # tolerance 0 is the old test: the level has to be traded through
    old = evaluate(scenario, "trigger", reversal_level_tolerance_frac=0.0)
    assert old.decision == "no_trade" and criterion(old, "rev_key_level_reached").passed is False
    assert "price has not reached a key level" in old.summary


def test_reversal_with_no_key_level_nearby_has_no_context() -> None:
    # previous low 50: the forming candle's low 54 is 4.0 away, against a tolerance of 2.0
    verdict = evaluate(reversal_scenario(DAILY, previous_low=50.0), "trigger")
    assert (verdict.decision, verdict.path_family, verdict.stage) == ("no_trade", "none", "none")
    reached = criterion(verdict, "rev_key_level_reached")
    assert reached.passed is False
    assert "the nearest key level, the previous 1D candle's low 50.00, is still 4.00 away" in reached.detail
    assert criterion(verdict, "rev_cisd_confirmed").passed is False  # a CISD away from a level confirms nothing
    assert verdict.entry is None


def test_reversal_no_longer_needs_continuation_closes_in_a_row() -> None:
    # B[-2] becomes an inside bar: one continuation close in a row, where the old context rule asked for three
    scenario = reversal_scenario(DAILY)
    builder = scenario.builder
    builder._rows[builder.bias_open(builder._count - 2)] = (85.0, 90.0, 81.0, 84.0)
    verdict = evaluate(scenario, "trigger")
    assert (verdict.decision, verdict.path_family) == ("long", "reversal")


def test_reversal_into_the_level_must_be_a_directional_run() -> None:
    # the setup candle before the low closes up: nothing ran into the level
    scenario = reversal_scenario(DAILY, run_into_level=False)
    verdict = evaluate(scenario, "trigger")
    assert (verdict.decision, verdict.path_family, verdict.stage) == ("watch", "reversal", "c4")
    assert failed(verdict, "quality") == ["rev_expansion_into_level"]
    assert "no down-close 1h candle leads into it" in criterion(verdict, "rev_expansion_into_level").detail
    # switched off, reaching the level is sufficient
    off = evaluate(scenario, "trigger", reversal_expansion_test="off")
    assert off.decision == "long" and criterion(off, "rev_expansion_into_level").role == "advisory"


def test_reversal_entry_modes() -> None:
    scenario = reversal_scenario(DAILY)
    aggressive = evaluate(scenario, "trigger", entry_mode_reversal="aggressive")
    assert aggressive.decision == "long"
    assert aggressive.entry == pytest.approx(57.4) and aggressive.stop == pytest.approx(54.0)
    conservative = evaluate(scenario, "trigger", entry_mode_reversal="conservative")
    assert conservative.decision == "long"
    assert conservative.entry == pytest.approx(57.8) and conservative.stop == pytest.approx(56.2)
    assert conservative.targets == pytest.approx((57.8 + 2 * 1.6,))
    latest = evaluate(scenario, "trigger", entry_either_pick="latest")
    assert latest.entry == pytest.approx(57.8)
    assert "a continuation order block is the latest to confirm" in criterion(latest, "rev_entry_trigger").detail


def test_old_rules_switches_restore_the_previous_reversal_verdict() -> None:
    old = evaluate(reversal_scenario(DAILY), "trigger", **OLD_RULES)
    assert (old.decision, old.path_family, old.stage) == ("long", "reversal", "c4")
    assert old.entry == pytest.approx(57.8) and old.stop == pytest.approx(56.2)
    assert old.targets == pytest.approx((63.0, 71.0))
    # the old session rule on the CISD entry, which closes 08:25, outside the kill zones
    session = evaluate(
        reversal_scenario(DAILY), "trigger", **{**OLD_RULES, "entry_mode_reversal": "aggressive", "min_rr": 1.5}
    )
    assert (session.decision, session.stage) == ("watch", "c4")
    assert failed(session, "quality") == ["session_filter_ok"]
    assert session.entry == pytest.approx(57.4) and session.stop == pytest.approx(54.0)


def test_wick_yardstick_body_measures_the_wick_against_the_candle_body() -> None:
    scenario = reversal_scenario(DAILY)
    default = criterion(evaluate(scenario, "trigger"), "rev_opposing_run_small")
    assert default.passed is True and "20% of the 20-candle average 1D range" in default.detail
    # body so far |57.8 - 58.0| = 0.2 against an opposing run of 4.0
    verdict = evaluate(scenario, "trigger", wick_yardstick="body")
    body = criterion(verdict, "rev_opposing_run_small")
    assert body.passed is False and "20.00 times the candle's body so far 0.20" in body.detail
    assert verdict.decision == "watch" and failed(verdict, "quality") == ["rev_opposing_run_small"]
    loose = evaluate(scenario, "trigger", wick_yardstick="body", wick_body_small_frac=25.0, wick_body_large_frac=30.0)
    assert criterion(loose, "rev_opposing_run_small").passed is True and loose.decision == "long"


# --- data and lookahead --------------------------------------------------------


def test_not_enough_history_is_no_trade_with_nothing_else_evaluated() -> None:
    scenario = continuation_scenario(DAILY)
    builder = scenario.builder
    recent = builder.frame()[builder.frame().index >= builder.bias_open() - pd.Timedelta(days=10)]
    from companion.bars import HistoricalBarSource

    style = TTradesStyle()
    verdict = style.evaluate(
        SYMBOL, scenario.times["trigger"].to_pydatetime(), DAILY, HistoricalBarSource(minute_bars={SYMBOL: recent})
    )
    assert verdict.decision == "no_trade"
    sufficient = criterion(verdict, "data_sufficient")
    assert sufficient.passed is False and "need 69" in sufficient.detail
    assert all(item.passed is None for item in verdict.criteria if item.group != "shared")
    assert criterion(verdict, "session_filter_ok").passed is None


@pytest.mark.parametrize("stack_name", ["1D / 1h / 5m", "4h / 15m / 1m"])
def test_no_lookahead_later_bars_do_not_change_the_verdict(stack_name: str) -> None:
    stack = get_stack(stack_name)
    scenario = continuation_scenario(stack, with_aftermath=True)
    assert scenario.builder.frame().index[-1] > scenario.times["window_closed"]
    moments = dict(scenario.times)
    moments["mid_pullback"] = scenario.times["trigger"] - pd.Timedelta(minutes=1)
    for name, moment in moments.items():
        scenario.times[name] = moment
        with_future = evaluate(scenario, name)
        only_past = evaluate(scenario, name, until=moment)
        assert with_future == only_past, name
    # and the aftermath itself changes nothing that was knowable at the trigger
    assert evaluate(scenario, "trigger") == evaluate(continuation_scenario(stack), "trigger")
    assert evaluate(scenario, "trigger").decision == "long"


def test_no_lookahead_on_the_reversal_path() -> None:
    scenario = reversal_scenario(DAILY)
    builder = scenario.builder
    # an aftermath: the wick low is taken out and the day collapses
    slot = 15
    builder.entries(slot, [(57.8, 57.9, 40.0, 41.0), (41.0, 80.0, 39.0, 79.0)], first=3)
    builder.setup(slot + 1, (79.0, 81.0, 30.0, 31.0))
    moments = dict(scenario.times)
    moments["cisd_bar_closed"] = scenario.times["trigger"] - pd.Timedelta(minutes=45)
    for name, moment in moments.items():
        scenario.times[name] = moment
        assert evaluate(scenario, name) == evaluate(scenario, name, until=moment), name
    assert evaluate(scenario, "trigger") == evaluate(reversal_scenario(DAILY), "trigger")
    assert evaluate(scenario, "trigger").decision == "long"


def test_every_documented_criterion_is_returned_once() -> None:
    verdict = evaluate(continuation_scenario(DAILY), "trigger")
    keys = [item.key for item in verdict.criteria]
    assert len(keys) == len(set(keys))
    expected = {
        "data_sufficient", "stack_pairing_stated", "session_filter_ok",
        "bias_closure_directional", "bias_poi_present", "bias_cisd_confirmed", "bias_candle_index_ok",
        "bias_swing_intact", "cont_objective_open", "bias_c2_not_expanded", "cont_eq_respected",
        "cont_poi_tagged", "cont_opened_against_bias_first", "cont_setup_closure",
        "cont_setup_closure_body_aligned", "cont_entry_cisd_confirmed", "cont_entry_cisd_swift",
        "cont_entry_window_open", "cont_entry_trigger", "cont_protected_swing_intact",
        "cont_trigger_clear_of_liquidity", "cont_reward_at_least_2r",
        "cont_not_inside_consolidation", "cont_trigger_v_shape", "cont_objective_open_at_trigger",
        "cont_entry_early_in_candle", "cont_newer_protected_low",
        "rev_key_level_reached", "rev_expansion_into_level", "rev_opposing_run_small", "rev_formed_early",
        "rev_reclaim", "rev_cisd_confirmed", "rev_cisd_swift", "rev_entry_trigger", "rev_wick_intact",
        "rev_reward_at_least_2r",
    }  # fmt: skip
    assert set(keys) == expected
    assert all(item.label and item.detail and item.group and item.role for item in verdict.criteria)
    roles = {item.key: item.role for item in verdict.criteria}
    # the classes the trader's answers changed (rules.md section 12)
    assert roles["session_filter_ok"] == roles["cont_objective_open"] == "advisory"
    assert roles["cont_reward_at_least_2r"] == roles["rev_reward_at_least_2r"] == "advisory"
    assert (roles["rev_key_level_reached"], roles["rev_expansion_into_level"]) == ("step", "quality")
