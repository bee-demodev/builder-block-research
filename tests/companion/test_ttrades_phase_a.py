"""Phase A of the 2026-11-13 backtest plan (knowledge/ttrades_app_improvement_plan.md).

A1 the stop against the average daily range, A2 its cost in R, A3 where a triggered idea
stands (actionable / late / played out), A4 the label of a blocked trigger, A6 the
intraday reference levels. The played-out demotion itself is in test_ttrades_plan.py.
"""

from __future__ import annotations

import pandas as pd
import pytest

from companion import app_model
from companion.bars import HistoricalBarSource, bar_close_times
from companion.contracts import cost_in_r, root
from companion.styles.ttrades import load_config
from companion.styles.ttrades.context import load_context
from companion.styles.ttrades.style import TTradesStyle, _session_levels, stop_big_enough
from companion.timeframes import make_stack
from test_ttrades_plan import DAILY, EARLY_WINDOW, STACKS, criterion, evaluate, extended
from ttrades_scenarios import _SWING_SLOT, SYMBOL, continuation_scenario, reversal_scenario


def trigger_label(verdict) -> str:  # type: ignore[no-untyped-def]
    return next(item.short for item in verdict.markup if item.label == "Entry trigger")


# --- A2: what a contract costs ----------------------------------------------------------


def test_contract_roots_and_costs() -> None:
    assert [root(name) for name in ("CME_MINI:NQ1!", "MNQZ2026", "es", "COMEX:MGC1!", "XYZ")] == ["NQ", "NQ", "ES", "GC", ""]
    mini, micro = cost_in_r("NQ", 10.0)
    assert mini == pytest.approx((0.25 + 4.50 / 20.0) / 10.0)  # a tick of slippage plus commission in points
    assert micro == pytest.approx((0.25 + 1.50 / 2.0) / 10.0)
    assert micro > 2 * mini  # the micro's commission does not shrink with its point value
    assert cost_in_r("XYZ", 10.0) == (None, None) and cost_in_r("NQ", 0.0) == (None, None)


@STACKS
def test_the_plan_carries_stop_size_and_cost(stack) -> None:  # type: ignore[no-untyped-def]
    plan = evaluate(continuation_scenario(stack), "trigger").plan
    assert plan is not None and plan.risk_adr is not None and plan.risk_adr > 0
    risk = abs(plan.entry - plan.stop)
    assert (plan.cost_r_mini, plan.cost_r_micro) == tuple(pytest.approx(value) for value in cost_in_r(SYMBOL, risk))


# --- A1: the stop-size check -----------------------------------------------------------


@STACKS
def test_stop_size_passes_at_exactly_the_threshold_and_is_information_by_default(stack) -> None:  # type: ignore[no-untyped-def]
    scenario = continuation_scenario(stack)
    base = evaluate(scenario, "trigger")
    share = base.plan.risk_adr  # type: ignore[union-attr]
    side = base.decision
    assert side in ("long", "short")

    at = evaluate(scenario, "trigger", min_stop_adr_frac=share)
    assert criterion(at, "stop_size_ok").passed is True

    under = evaluate(scenario, "trigger", min_stop_adr_frac=share * 1.001)
    check = criterion(under, "stop_size_ok")
    assert (check.passed, check.role) == (False, "advisory")
    assert "costs take a large share" in check.detail
    assert under.decision == side  # advisory: shown, never changes the decision


def test_a_stop_of_exactly_four_percent_passes_despite_float_error() -> None:
    risk, adr = 1019.5 - 1018.2, 32.5  # 1.3 / 32.5 = 0.04, computed as 0.0399999999999986
    assert risk / adr < 0.04 and stop_big_enough(risk, adr, 0.04)
    assert not stop_big_enough(1.29, adr, 0.04)


@STACKS
def test_stop_size_as_a_quality_check_holds_the_trade_at_watch(stack) -> None:  # type: ignore[no-untyped-def]
    scenario = continuation_scenario(stack)
    share = evaluate(scenario, "trigger").plan.risk_adr  # type: ignore[union-attr]
    held = evaluate(scenario, "trigger", min_stop_adr_frac=share * 1.001, stop_size_role="quality")
    assert held.decision == "watch" and "stop_size_ok" in held.summary
    assert trigger_label(held).endswith("blocked: stop too small")  # A4
    assert held.plan is not None and held.plan.state == "triggered"  # the levels are still told
    assert "of the daily range, so costs take a large share" in held.waiting_for  # the read says why
    entry = [step for step in held.steps if step.role == "entry"][-1]
    assert entry.status == "blocked" and "daily range" in entry.detail


@STACKS
def test_a_played_out_trigger_says_so_in_the_read_and_the_steps(stack) -> None:  # type: ignore[no-untyped-def]
    scenario, (_, second) = extended(stack, [(97.7, 99.0, 97.6, 98.9), (98.9, 111.0, 98.8, 110.8)])
    there = evaluate(scenario, second)
    assert there.decision == "watch" and "already played out (it has reached its target)" in there.waiting_for
    assert (there.entry, there.stop, there.targets) == (None, None, ())
    assert "blocked:." not in there.waiting_for
    entry = [step for step in there.steps if step.role == "entry"][-1]
    assert entry.status == "blocked" and "played out" in entry.detail


def test_stop_size_waits_for_a_trigger() -> None:
    scenario = continuation_scenario(DAILY)
    before = scenario.times["trigger"] - pd.Timedelta(hours=2)
    check = criterion(evaluate(scenario, before), "stop_size_ok")
    assert check.passed is None and "no trigger yet" in check.detail


@STACKS
def test_adr_is_the_mean_range_of_closed_daily_bars(stack) -> None:  # type: ignore[no-untyped-def]
    scenario = continuation_scenario(stack)
    moment = scenario.times["trigger"]
    cfg = load_config()
    source = scenario.source()
    ctx = load_context(SYMBOL, moment, stack, source, cfg)
    daily = source.get_bars(SYMBOL, "1D", moment, cfg.adr_days)
    assert len(daily) and bar_close_times(daily, "1D")[-1] <= moment  # nothing still forming
    assert ctx.adr == pytest.approx(float((daily["high"] - daily["low"]).mean()))


# --- A3: where a triggered idea stands --------------------------------------------------


QUIET = (97.6, 97.9, 97.4, 97.6)  # inside the trade: well away from the stop 91.0 and the target 110.5


@STACKS
def test_a_triggered_idea_is_actionable_for_n_entry_bars_then_late(stack) -> None:  # type: ignore[no-untyped-def]
    at_trigger = evaluate(continuation_scenario(stack), "trigger").plan
    assert at_trigger is not None and at_trigger.age_bars is not None and at_trigger.stage_label == "actionable"
    base = at_trigger.age_bars  # entry bars closed after the trigger bar at the scenario's "trigger" moment
    scenario, closes = extended(stack, [QUIET] * 3)
    plans = [evaluate(scenario, moment, actionable_entry_bars=base + 2).plan for moment in closes]
    assert [(plan.age_bars, plan.stage_label) for plan in plans] == [  # type: ignore[union-attr]
        (base + 1, "actionable"), (base + 2, "actionable"), (base + 3, "late"),
    ]  # fmt: skip
    assert all(plan.outcome == "open" for plan in plans)  # type: ignore[union-attr]


@STACKS
@pytest.mark.parametrize("mirror", [False, True], ids=["bullish", "bearish"])
def test_a_triggered_idea_far_from_its_entry_is_late(stack, mirror: bool) -> None:  # type: ignore[no-untyped-def]
    # entry 97.5, risk 6.5: a close at 101.4 is 0.6 R away, past the 0.5 R allowed
    young = {"actionable_entry_bars": 100}  # age is not what is tested here
    scenario, (first,) = extended(stack, [(97.7, 101.6, 97.6, 101.4)], mirror)
    plan = evaluate(scenario, first, **young).plan
    assert plan is not None and plan.outcome == "open"
    assert plan.stage_label == "late" and plan.r_now == pytest.approx(3.9 / 6.5)
    assert evaluate(scenario, first, actionable_max_r=1.0, **young).plan.stage_label == "actionable"  # type: ignore[union-attr]


def test_a_planned_idea_is_forming() -> None:
    scenario = reversal_scenario(DAILY)
    moment = scenario.builder.at(_SWING_SLOT["1D"], 4)  # the low is in; no close through the run yet
    plan = evaluate(scenario, moment, **EARLY_WINDOW).plan
    assert plan is not None and (plan.state, plan.stage_label, plan.age_bars) == ("planned", "forming", None)


# --- A6: intraday reference levels ------------------------------------------------------


@STACKS
def test_session_levels_are_information_markup(stack) -> None:  # type: ignore[no-untyped-def]
    verdict = evaluate(continuation_scenario(stack), "trigger")
    session = [item for item in verdict.markup if item.role == "session"]
    names = {"Asia H", "Asia L", "London H", "London L", "Midnight open", "09:30 open", "PDH", "PDL"}
    assert {item.short for item in session} <= names
    assert all(item.kind == "level" and item.price is not None and item.timeframe == stack.entry for item in session)


NY = "America/New_York"
AS_OF = pd.Timestamp("2024-04-04 10:00", tz=NY)


def minute_source() -> HistoricalBarSource:
    """Flat 1-minute bars around 100 with known session prices on the trading day of 2024-04-04:
    Asia high 120 at 18:30 the evening before, London low 80 at 03:00, midnight open 101,
    09:30 open 102. The trading day before (Apr 2 18:00 to Apr 3 17:00) spans 99.5-100.5."""
    index = pd.date_range(pd.Timestamp("2024-03-25 18:00", tz=NY), AS_OF, freq="1min", inclusive="left")
    frame = pd.DataFrame({"open": 100.0, "high": 100.5, "low": 99.5, "close": 100.0, "volume": 1.0}, index=index)
    frame.index.name = "timestamp"
    frame.loc[pd.Timestamp("2024-04-03 18:30", tz=NY), "high"] = 120.0
    frame.loc[pd.Timestamp("2024-04-04 03:00", tz=NY), "low"] = 80.0
    frame.loc[pd.Timestamp("2024-04-04 00:00", tz=NY), "open"] = 101.0
    frame.loc[pd.Timestamp("2024-04-04 09:30", tz=NY), "open"] = 102.0
    return HistoricalBarSource(minute_bars={SYMBOL: frame})


@pytest.mark.parametrize("parts", [("4h", "15m", "1m"), ("1D", "1h", "5m"), ("1M", "1D", "1h"), ("1W", "4h", "15m")])
def test_session_levels_read_the_whole_trading_day(parts: tuple[str, str, str]) -> None:
    stack = make_stack(*parts)
    ctx = load_context(SYMBOL, AS_OF, stack, minute_source(), load_config())
    levels = {item.short: item.price for item in _session_levels(ctx)}
    expected = {"Asia H": 120.0, "Asia L": 99.5, "London H": 100.5, "London L": 80.0, "Midnight open": 101.0, "09:30 open": 102.0}
    if stack.entry == "1h":
        del expected["09:30 open"]  # no 1h bar opens at 09:30; a finer series would go stale live
    if stack.bias != "1D":
        expected |= {"PDH": 100.5, "PDL": 99.5}
    assert levels == pytest.approx(expected)


def test_no_session_levels_above_an_hourly_entry() -> None:
    ctx = load_context(SYMBOL, AS_OF, make_stack("1W", "1D", "4h"), minute_source(), load_config())
    assert ctx.sess is None and _session_levels(ctx) == []


def test_session_levels_reach_the_entry_chart_of_a_stack_without_a_daily_pane() -> None:
    stack, source = make_stack("4h", "15m", "1m"), minute_source()
    verdict = TTradesStyle().evaluate(SYMBOL, AS_OF.to_pydatetime(), stack, source)
    charts = app_model.build_charts(source, SYMBOL, stack, AS_OF, verdict.markup)
    entry = next(chart for chart in charts if chart.role == "entry")
    drawn = {mark.label for mark in entry.marks if mark.role == "session"}
    assert {"PDH", "PDL", "Asia H", "London L"} <= drawn


@STACKS
@pytest.mark.parametrize("mirror", [False, True], ids=["bullish", "bearish"])
def test_a_stopped_trigger_whose_swing_still_holds_is_played_out(stack, mirror: bool) -> None:  # type: ignore[no-untyped-def]
    # a wick through the stop 91.0 that closes back above it: stopped for the plan, while the
    # protected swing (broken on a close here) still holds, so the demotion itself says why
    scenario, (bar,) = extended(stack, [(97.7, 98.0, 90.5, 97.0)], mirror)
    verdict = evaluate(scenario, bar, protected_swing_break_on="close")
    assert criterion(verdict, "cont_protected_swing_intact").passed is True
    assert verdict.decision == "watch" and "it has been stopped" in verdict.summary
    assert verdict.plan is not None and (verdict.plan.outcome, verdict.plan.stage_label) == ("stopped", "played_out")
    assert (verdict.entry, verdict.stop, verdict.targets) == (None, None, ())  # legacy fields are for a trade (10.3)
    assert "it has been stopped" in verdict.waiting_for


def test_a_played_out_trigger_that_also_fails_a_quality_check_says_both() -> None:
    scenario, (_, second) = extended(DAILY, [(97.7, 99.0, 97.6, 98.9), (98.9, 111.0, 98.8, 110.8)])
    outside = {"session_filter_role": "quality", "kill_zones": [["02:00", "03:00"]]}  # the trigger is outside them
    there = evaluate(scenario, second, **outside)
    assert there.decision == "watch" and "session_filter_ok" in there.summary and "already played out" in there.summary
    assert (there.entry, there.stop, there.targets) == (None, None, ())  # played out: no legacy levels (10.3)
    assert "kill zones" in there.waiting_for and "played out" in there.waiting_for
    assert trigger_label(there).endswith("blocked: outside kill zone, played out")
    assert there.plan is not None and there.plan.stage_label == "played_out"


@pytest.mark.parametrize("parts", [("1D", "4h", "15m"), ("1h", "5m", "1m")], ids=["entry frame reused", "longer lookback"])
def test_live_session_levels_keep_up_with_each_refresh(tmp_path, parts: tuple[str, str, str]) -> None:  # type: ignore[no-untyped-def]
    from companion.tradingview.source import TradingViewBarSource
    from tradingview_fakes import FakeTradingView, market_minutes, write_symbols

    minutes = market_minutes()
    tv = FakeTradingView(minutes, "2026-03-10 09:01:10")
    source = TradingViewBarSource(tv, symbols_path=write_symbols(tmp_path / "symbols.json"), clock=tv.clock)
    stack, style = make_stack(*parts), TTradesStyle()

    def levels() -> dict[str, float]:
        update = source.refresh("NQ", stack.entry)
        verdict = style.evaluate("NQ", update.last_close.to_pydatetime(), stack, source)
        return {item.short: item.price for item in verdict.markup if item.role == "session"}  # type: ignore[misc]

    def at(clock: str) -> pd.Timestamp:
        return pd.Timestamp(f"2026-03-10 {clock}", tz=NY)

    asia = minutes[(minutes.index >= pd.Timestamp("2026-03-09 18:00", tz=NY)) & (minutes.index < at("00:00"))]
    first = levels()
    assert first["Asia H"] == pytest.approx(float(asia["high"].max())) and "09:30 open" not in first
    tv.now = at("10:00:10")
    later = levels()  # the same series the live feed refreshes: the 09:30 bar is there now
    assert later["09:30 open"] == pytest.approx(float(minutes.loc[at("09:30"), "open"]))
    assert later["Asia H"] == first["Asia H"]


def test_pdh_and_pdl_do_not_need_the_session_bars() -> None:
    ctx = load_context(SYMBOL, AS_OF, make_stack("4h", "15m", "1m"), minute_source(), load_config())
    ctx.sess = None  # the session request failed
    assert {item.short for item in _session_levels(ctx)} == {"PDH", "PDL"}
