"""The top-down read the TTrades style puts on a verdict.

Assertions are on structure and facts (which timeframe, which status, which prices are
named), never on whole sentences. Markets come from ``ttrades_scenarios``; each
scenario's docstring spells out the prices used below.
"""

from __future__ import annotations

import re
from typing import Any

import pytest

from companion.engine import render_text
from companion.styles.ttrades import TTradesStyle, load_config
from companion.styles.ttrades.checklist import CONTINUATION, REVERSAL, SESSION, SHARED
from companion.timeframes import candle_label, get_stack
from companion.types import ReadStep, TimeframeStack, Verdict
from ttrades_scenarios import SYMBOL, Scenario, continuation_scenario, reversal_scenario

DAILY = get_stack("1D / 1h / 5m")
FOUR_HOUR = get_stack("4h / 15m / 1m")
STACKS = pytest.mark.parametrize("stack", [DAILY, FOUR_HOUR], ids=lambda stack: stack.name)

KEYS = [spec.key for spec in (*SHARED, SESSION, *CONTINUATION, *REVERSAL)]
STAGE_CODE = re.compile(r"\bc[1-4]\b")


def evaluate(scenario: Scenario, moment: str, **overrides: Any) -> Verdict:
    style = TTradesStyle(load_config(overrides=overrides))
    return style.evaluate(SYMBOL, scenario.times[moment].to_pydatetime(), scenario.stack, scenario.source())


def steps(verdict: Verdict) -> dict[str, ReadStep]:
    return {step.role: step for step in verdict.read}


def said(verdict: Verdict) -> str:
    """Everything the read tells the trader, as one text."""
    parts = [verdict.why, verdict.waiting_for]
    for step in verdict.read:
        parts += [step.headline, step.reason]
    return " ".join(parts)


def assert_shape(verdict: Verdict, stack: TimeframeStack) -> None:
    """One step per role, highest timeframe first, in the trader's words only."""
    assert [(step.role, step.timeframe) for step in verdict.read] == [
        ("bias", stack.bias), ("setup", stack.setup), ("entry", stack.entry),
    ]  # fmt: skip
    assert all(step.status in ("confirmed", "waiting", "failed", "not_applicable") for step in verdict.read)
    assert all(step.headline for step in verdict.read)
    assert verdict.why.endswith(".")
    text = said(verdict)
    assert not STAGE_CODE.search(text), "an internal stage code leaked into the read"
    assert not [key for key in KEYS if key in text], "a criterion key leaked into the read"


@STACKS
def test_bullish_continuation_read(stack: TimeframeStack) -> None:
    scenario = continuation_scenario(stack)
    verdict = evaluate(scenario, "trigger")
    assert verdict.decision == "long" and verdict.path_family == "continuation"
    assert_shape(verdict, stack)
    read = steps(verdict)
    assert [step.status for step in verdict.read] == ["confirmed", "confirmed", "confirmed"]
    # bias: bullish, the forming candle is Candle 3, off a Candle 2 closure through the prior low 88 that closed at 97
    assert "Bullish" in read["bias"].headline and "Candle 3" in read["bias"].headline
    assert "88.00" in read["bias"].reason and "97.00" in read["bias"].reason and "Candle 2 closure" in read["bias"].reason
    # setup: the swing candle dipped to 91 into the bias order block 82-96 and closed 97.5; the next candle is Candle 3
    assert "Candle 3" in read["setup"].headline
    assert all(price in read["setup"].reason for price in ("91.00", "82.00", "96.00", "97.50"))
    # entry: the close 97.40 above 97.00 is the CISD; the entry is the 97.50 close
    assert "CISD" in read["entry"].headline
    assert all(price in read["entry"].reason for price in ("97.40", "97.00", "97.50"))
    # the confirming candle is named by the time the chart shows for it
    confirm = next(item for item in verdict.markup if item.label == "Entry CISD")
    assert candle_label(confirm.start, stack.entry, verdict.as_of) in read["entry"].reason
    # why: one sentence that names all three timeframes and the level being respected (wick midpoint 88)
    assert all(label in verdict.why for label in (stack.bias, stack.setup, stack.entry))
    assert "bullish" in verdict.why and "88.00" in verdict.why
    assert verdict.waiting_for == ""


@STACKS
def test_bearish_continuation_read_is_the_mirror(stack: TimeframeStack) -> None:
    scenario = continuation_scenario(stack, mirror=True)
    verdict = evaluate(scenario, "trigger")
    assert verdict.decision == "short"
    assert_shape(verdict, stack)
    read = steps(verdict)
    assert [step.status for step in verdict.read] == ["confirmed", "confirmed", "confirmed"]
    assert "Bearish" in read["bias"].headline and "Candle 3" in read["bias"].headline
    assert f"{scenario.price(88):.2f}" in read["bias"].reason and "high" in read["bias"].reason
    assert f"{scenario.price(91):.2f}" in read["setup"].reason
    assert f"{scenario.price(97.4):.2f}" in read["entry"].reason and "below" in read["entry"].reason
    assert "bearish" in verdict.why and "Bullish" not in said(verdict)


@STACKS
def test_watch_read_says_what_it_is_waiting_for(stack: TimeframeStack) -> None:
    scenario = continuation_scenario(stack)
    early = evaluate(scenario, "before_setup")
    assert early.decision == "watch"
    assert_shape(early, stack)
    assert [step.status for step in early.read] == ["confirmed", "waiting", "waiting"]
    assert stack.setup in early.waiting_for and "point of interest" in early.waiting_for
    assert "88.00" in early.waiting_for  # the level the pullback has to respect
    assert " but " in early.why

    # the turn has printed, the settings ask for a continuation order block: that is what is waited for
    turned = evaluate(scenario, "setup_closed", entry_mode_continuation="conservative")
    assert turned.decision == "watch"
    assert [step.status for step in turned.read] == ["confirmed", "confirmed", "waiting"]
    assert "97.40" in steps(turned)["entry"].reason
    assert stack.entry in turned.waiting_for and "91.00" in turned.waiting_for

    # entry-ready structure that a quality check blocks: the step is failed and says why
    late = evaluate(scenario, "window_closed")
    assert late.decision == "watch"
    assert [step.status for step in late.read] == ["confirmed", "failed", "confirmed"]
    assert "entry window" in steps(late)["setup"].reason and "entry window" in late.why
    assert "fresh setup" in late.waiting_for


@STACKS
def test_no_trade_read_names_the_timeframe_that_fails(stack: TimeframeStack) -> None:
    # the setup timeframe closes at 87, below the respect level 88: the bias stands, the setup fails
    lost = evaluate(continuation_scenario(stack, previous_setup_bar=(96.8, 97.8, 86.0, 87.0)), "trigger")
    assert lost.decision == "no_trade"
    assert_shape(lost, stack)
    assert [step.status for step in lost.read] == ["confirmed", "failed", "not_applicable"]
    assert "87.00" in steps(lost)["setup"].reason and "88.00" in steps(lost)["setup"].reason
    assert stack.setup in lost.why and lost.waiting_for == ""

    # an inside bias candle gives no bias at all: nothing below it is read
    neutral = evaluate(continuation_scenario(stack, inside_bias_bar=True), "trigger", reversal_level_tolerance_frac=0.0)
    assert neutral.decision == "no_trade"
    assert_shape(neutral, stack)
    assert [step.status for step in neutral.read] == ["failed", "not_applicable", "not_applicable"]
    assert "No bias" in steps(neutral)["bias"].headline and "Candle" not in steps(neutral)["bias"].headline
    assert "key level" in neutral.why  # and no reversal either


@pytest.mark.parametrize("mirror", [False, True], ids=["bullish", "bearish"])
def test_reversal_read(mirror: bool) -> None:
    scenario = reversal_scenario(DAILY, mirror=mirror)
    verdict = evaluate(scenario, "trigger")
    assert verdict.decision == ("short" if mirror else "long") and verdict.path_family == "reversal"
    assert_shape(verdict, DAILY)
    read = steps(verdict)
    assert [step.status for step in verdict.read] == ["confirmed", "confirmed", "confirmed"]
    # the forming bias candle is the swing candle of the reversal: Candle 2, at the previous candle's extreme 55 (low 54)
    assert "reversal" in read["bias"].headline and "Candle 2" in read["bias"].headline
    assert ("Bearish" if mirror else "Bullish") in read["bias"].headline
    assert f"{scenario.price(55):.2f}" in read["bias"].reason and f"{scenario.price(54):.2f}" in read["bias"].reason
    # the setup timeframe closed back on the trade's side of the level; the rules give it no candle number
    assert f"{scenario.price(55):.2f}" in read["setup"].reason and "Candle" not in read["setup"].headline
    # the entry timeframe: the close 57.40 through 57.00
    assert f"{scenario.price(57.4):.2f}" in read["entry"].reason and f"{scenario.price(57):.2f}" in read["entry"].reason
    # only the path in play is told: nothing about a pullback into a point of interest or the equilibrium
    assert "point of interest" not in said(verdict) and "equilibrium" not in said(verdict)
    assert "key level" in verdict.why


@STACKS
def test_reversal_watch_read(stack: TimeframeStack) -> None:
    verdict = evaluate(reversal_scenario(stack), "level_taken")
    assert (verdict.decision, verdict.path_family) == ("watch", "reversal")
    assert_shape(verdict, stack)
    read = steps(verdict)
    assert read["setup"].status == "waiting" and read["entry"].status == "waiting"
    assert "55.00" in read["setup"].reason  # the level a setup candle has to close back above
    assert stack.setup in verdict.waiting_for and "55.00" in verdict.waiting_for


def test_a_blocked_reversal_says_which_timeframe_blocks_it() -> None:
    verdict = evaluate(reversal_scenario(DAILY, run_into_level=False), "trigger")
    assert verdict.decision == "watch"
    assert [step.status for step in verdict.read] == ["confirmed", "failed", "confirmed"]
    assert "drift" in steps(verdict)["setup"].reason and "drift" in verdict.why and "1h" in verdict.why


def test_continuation_read_never_mentions_the_reversal_path() -> None:
    verdict = evaluate(continuation_scenario(DAILY), "trigger")
    assert "reversal" not in said(verdict).lower() and "key level" not in said(verdict)


def test_not_enough_history_read() -> None:
    scenario = continuation_scenario(DAILY)
    style = TTradesStyle(load_config())
    early = scenario.builder.bias_open(20).to_pydatetime()
    verdict = style.evaluate(SYMBOL, early, DAILY, scenario.source())
    assert verdict.decision == "no_trade"
    assert [step.status for step in verdict.read] == ["not_applicable"] * 3
    assert [step.timeframe for step in verdict.read] == ["1D", "1h", "5m"]
    assert "history" in verdict.why


def test_markup_gives_every_chart_its_items_and_marks_the_confirming_candles() -> None:
    verdict = evaluate(continuation_scenario(DAILY), "trigger")
    by_frame: dict[str, list[str]] = {}
    for item in verdict.markup:
        by_frame.setdefault(item.timeframe, []).append(item.role)
    assert {"reference", "protected"} <= set(by_frame["1D"])
    assert {"reference", "confirm", "protected"} <= set(by_frame["1h"])
    assert {"confirm", "protected", "entry", "stop", "target"} <= set(by_frame["5m"])
    markers = {item.label: item for item in verdict.markup if item.kind == "marker"}
    # the candles that confirmed, by the time they opened: the setup closure, the entry CISD, the trigger
    assert markers["Setup closure (Candle 2 closure)"].price == pytest.approx(97.5)
    assert markers["Entry CISD"].price == pytest.approx(97.4)
    assert markers["Entry CISD"].start < markers["Entry trigger"].start
    assert markers["Entry trigger"].price == pytest.approx(verdict.entry)
    assert all(item.short for item in verdict.markup)

    waiting = evaluate(reversal_scenario(DAILY), "level_taken")
    assert not any(item.role in ("entry", "stop", "target") for item in waiting.markup)


def test_render_text_carries_the_read() -> None:
    verdict = evaluate(continuation_scenario(DAILY), "trigger")
    text = render_text(verdict)
    assert text.isascii()
    assert "Top-down read" in text and " 1D [ok] " in text and " 5m [ok] " in text
    assert "Why: " in text
