"""Teacher-grounded switches added for the 5-year backtest (proposed TD rows, decisions.md).

Each is off by default: the default config gives the same verdicts as before. Switched on,
``trade_reversals`` false never reports the reversal path (ENT-6), ``eq_respect_role``
advisory keeps a continuation alive after a close through the respect level (BIAS-1 / RNG-3),
and ``profile_check_role`` quality makes the daily-profile check block (BIAS-9 / PROF-1).
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import pytest

from companion.styles.ttrades import TTradesStyle, load_config
from companion.timeframes import get_stack
from companion.tools.backtest import VARIANTS
from companion.types import CriterionResult, Verdict
from ttrades_scenarios import FILLER, SYMBOL, Scenario, ScenarioBuilder, continuation_scenario, reversal_scenario

DAILY = get_stack("1D / 1h / 5m")


def evaluate(scenario: Scenario, moment: str, **overrides: Any) -> Verdict:
    style = TTradesStyle(load_config(overrides=overrides))
    return style.evaluate(SYMBOL, scenario.times[moment].to_pydatetime(), scenario.stack, scenario.source(None))


def criterion(verdict: Verdict, key: str) -> CriterionResult:
    (match,) = [item for item in verdict.criteria if item.key == key]
    return match


def test_the_defaults_leave_the_rules_as_they_were() -> None:
    config = load_config()
    assert (config.trade_reversals, config.eq_respect_role, config.profile_check_role) == (True, "gate", "advisory")


def test_with_reversals_off_a_reversal_setup_is_not_reported() -> None:
    scenario = reversal_scenario(DAILY)
    assert evaluate(scenario, "trigger").path_family == "reversal"
    off = evaluate(scenario, "trigger", trade_reversals=False)
    assert off.path_family != "reversal" and off.decision not in ("long", "short")
    assert criterion(off, "rev_entry_trigger").passed is True  # still computed and shown


def test_a_close_through_eq_is_a_soft_invalidation_when_the_eq_check_is_advisory() -> None:
    scenario = continuation_scenario(DAILY, previous_setup_bar=(96.8, 97.8, 86.0, 87.0))
    assert evaluate(scenario, "trigger").decision == "no_trade"  # default: the gate kills the path
    soft = evaluate(scenario, "trigger", eq_respect_role="advisory")
    respected = criterion(soft, "cont_eq_respected")
    assert respected.passed is False and respected.role == "advisory"
    # the path stays alive (this fixture's injected bar is not a setup closure, so it waits at watch)
    assert soft.path_family == "continuation" and soft.decision == "watch"


def test_the_profile_check_blocks_only_when_it_is_quality_and_fails() -> None:
    scenario = continuation_scenario(DAILY)
    default = evaluate(scenario, "trigger")
    veto = evaluate(scenario, "trigger", profile_check_role="quality")
    profile = criterion(veto, "cont_opened_against_bias_first")
    assert criterion(default, "cont_opened_against_bias_first").role == "advisory" and profile.role == "quality"
    assert profile.passed is True and veto.decision == default.decision == "long"


def candle4_day(c2_open: float) -> tuple[ScenarioBuilder, pd.Timestamp]:
    """Daily case B: a Candle 2 sweeps the swing low 84 and closes 103, then a Candle 3 closes
    above its high 104. ``c2_open`` sets Candle 2's lower wick: 86 is small (it expanded), 100 large."""
    build = ScenarioBuilder(DAILY)
    build.bias(*[FILLER] * 68)  # 72 closed bias candles in all, as in the shared scenarios
    build.bias((100, 108, 84, 98), (98, 106, 88, 100))  # swing low 84: the point of interest
    build.setup(0, (c2_open, c2_open + 0.5, 83, 83.5))
    build.setup(1, (83.5, 95, 83.4, 94.5))  # the setup CISD: closes above the down-close series
    build.setup(2, (94.5, 104, 94, 103))
    build.next_bias()
    build.setup(0, (103, 106, 102.5, 105.5))
    build.setup(1, (105.5, 112, 105, 111.5))  # Candle 3: closes above Candle 2's high, small wick
    build.next_bias()
    build.setup(0, (111.5, 112, 110, 111))  # the forming Candle 4
    return build, build.at(1)


@pytest.mark.parametrize(("c2_open", "blocked"), [(86, True), (100, False)])
def test_candle_4_after_a_double_expansion_is_skipped_only_when_switched_on(c2_open: float, blocked: bool) -> None:
    build, moment = candle4_day(c2_open)

    def index_ok(**overrides: Any) -> CriterionResult:
        style = TTradesStyle(load_config(overrides=overrides))
        return criterion(style.evaluate(SYMBOL, moment.to_pydatetime(), DAILY, build.source(None)), "bias_candle_index_ok")

    assert index_ok().passed is True and "Candle 4" in index_ok().detail
    assert index_ok(c4_after_double_expansion="skip").passed is (not blocked)


@pytest.mark.parametrize(("early_low", "skipped"), [(89.0, True), (92.0, False)])
def test_the_wick_setup_ignores_a_later_higher_low(early_low: float, skipped: bool) -> None:
    # the forming candle's first setup bar dips to early_low; the setup swing low comes later at 91
    scenario = continuation_scenario(DAILY, first_setup_bar=(97.5, 97.9, early_low, 97.0))
    assert evaluate(scenario, "trigger").decision == "long"
    wick = evaluate(scenario, "trigger", cont_setup_pick="wick_extreme")
    assert (wick.decision == "long") is (not skipped)
    if skipped:
        assert "cont_setup_pick is wick_extreme" in criterion(wick, "cont_setup_closure").detail


@pytest.mark.parametrize("name", ["next_continuation", "eq_soft", "profile_veto", "no_reversals", "ny_window",
                                  "cont_cisd_entry", "stop_gate", "swing_close_break", "no_double_expansion_c4",
                                  "wick_setup"])
def test_every_teacher_variant_is_a_valid_config(name: str) -> None:
    load_config(overrides=VARIANTS[name])
