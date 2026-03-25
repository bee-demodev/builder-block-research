from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SPEC_DIR = ROOT / "results" / "indicator_specs"
DEFAULT_OUTPUT_DIR = ROOT / "results" / "pine_scripts"
DEFAULT_MANIFEST_OUTPUT = ROOT / "results" / "pine_scripts_manifest.json"
DEFAULT_CANDIDATE_CONTRACT_DIR = ROOT / "results" / "pine_candidate_event_contracts"


def load_spec(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def profile_prefix(spec: dict) -> str:
    display_name = str(spec.get("trader_profile", {}).get("display_name", "")).strip()
    if not display_name:
        return "TTFM"
    return display_name.split()[0]


def build_script_title(spec: dict) -> str:
    trade_model_name = str(spec.get("trade_model", {}).get("name", "Indicator Draft")).strip()
    return f"{profile_prefix(spec)} {trade_model_name} [Draft]"


def get_spec_slug(spec: dict) -> str:
    return str(spec.get("trade_model", {}).get("slug", "")).strip() or "indicator_draft"


def escape_pine_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def path_for_manifest(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def format_default_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return f'"{escape_pine_string(value)}"'
    return str(value)


def build_input_line(group: str, input_spec: dict) -> str:
    key = str(input_spec.get("key", "unnamedInput"))
    variable_name = f"{key}Input"
    title = key
    description = str(input_spec.get("description", "")).strip()
    input_type = str(input_spec.get("type", "string")).strip().lower()
    default_value = format_default_value(input_spec.get("default"))

    common_suffix = f', "{escape_pine_string(title)}", group="{escape_pine_string(group)}"'
    if description:
        common_suffix += f', tooltip="{escape_pine_string(description)}"'

    if input_type == "bool":
        return f"{variable_name} = input.bool({default_value}{common_suffix})"
    if input_type == "int":
        return f"{variable_name} = input.int({default_value}{common_suffix})"
    if input_type == "float":
        return f"{variable_name} = input.float({default_value}{common_suffix})"
    if input_type == "enum":
        options = ", ".join(format_default_value(option) for option in input_spec.get("options", []))
        return (
            f"{variable_name} = input.string({default_value}{common_suffix}, "
            f"options=[{options}])"
        )
    return f"{variable_name} = input.string({default_value}{common_suffix})"


def build_input_block(spec: dict) -> list[str]:
    lines: list[str] = []
    for group_spec in spec.get("input_groups", []):
        group_name = str(group_spec.get("group", "General")).strip() or "General"
        lines.append(f"// {group_name}")
        for input_spec in group_spec.get("inputs", []):
            lines.append(build_input_line(group_name, input_spec))
        lines.append("")
    if lines and not lines[-1]:
        lines.pop()
    return lines


def build_metadata_comment_block(spec: dict) -> list[str]:
    lines = [
        f"// Draft scaffold generated from indicator spec: {get_spec_slug(spec)}",
        f"// {spec.get('implementation_summary', 'Spec-driven Pine draft scaffold.')}",
    ]

    provisional_proxies = spec.get("provisional_proxies", [])
    if provisional_proxies:
        lines.append("// Provisional proxy set:")
        for proxy in provisional_proxies:
            lines.append(
                f"// - {proxy.get('id')}: {proxy.get('logic', 'No proxy logic provided.')}"
            )

    state_models = spec.get("state_models", [])
    if state_models:
        lines.append("// State models:")
        for model in state_models:
            states = ", ".join(str(state) for state in model.get("states", []))
            lines.append(f"// - {model.get('name')}: {states}")

    signal_pipeline = spec.get("signal_pipeline", [])
    if signal_pipeline:
        lines.append("// Signal pipeline:")
        for step in signal_pipeline:
            lines.append(f"// {step.get('step')}. {step.get('name')}: {step.get('logic')}")

    return lines


def build_generic_pine_script(spec: dict) -> str:
    title = build_script_title(spec)
    derived_series = spec.get("derived_series", [])
    rule_trace = spec.get("topic_rule_trace", [])
    lines = [
        "// This Pine Script(TM) code is subject to the terms of the Mozilla Public License 2.0 at https://mozilla.org/MPL/2.0/",
        "// Copyright builder-block-C",
        "//@version=6",
        f'indicator("{escape_pine_string(title)}", overlay=true, max_lines_count=100, max_labels_count=100, max_boxes_count=20)',
        f"// TV_SYNC_SIGNATURE: {title}",
        "",
    ]
    lines.extend(build_metadata_comment_block(spec))
    lines.extend(
        [
            "",
            "// inputs",
        ]
    )
    lines.extend(build_input_block(spec))
    lines.extend(
        [
            "",
            "// helper functions",
            "clamp01(float value) => math.max(0.0, math.min(1.0, value))",
            "midpoint(float highPrice, float lowPrice) => (highPrice + lowPrice) / 2.0",
            "",
            "// calculations",
            "float draftMidpoint = midpoint(high, low)",
            "float draftBody = math.abs(close - open)",
            "float draftRange = math.max(high - low, syminfo.mintick)",
            "float draftPressure = clamp01(draftBody / draftRange)",
            "bool draftMomentum = close > draftMidpoint",
            "string draftState = draftMomentum ? \"bullish_bias\" : \"bearish_bias\"",
            "",
            "// derived series placeholders",
        ]
    )
    for series in derived_series:
        lines.append(f"// - {series.get('series')}: {series.get('description')}")

    lines.extend(
        [
            "",
            "// rule trace references",
        ]
    )
    for topic_trace in rule_trace:
        topic = topic_trace.get("topic")
        for rule in topic_trace.get("rules", []):
            lines.append(f"// - {topic}: {rule.get('rule_ref')} -> {rule.get('name')}")

    lines.extend(
        [
            "",
            "// visuals",
            "plot(draftMidpoint, \"Draft midpoint\", color=color.new(color.orange, 0), linewidth=2)",
            "bgcolor(draftMomentum ? color.new(color.green, 88) : color.new(color.red, 88), title=\"Draft state background\")",
            "var label draftSummaryLabel = na",
            "if barstate.islast",
            "    label.delete(draftSummaryLabel)",
            "    draftSummaryLabel := label.new(bar_index, high, str.format(\"{0} | pressure {1}\", draftState, str.tostring(draftPressure, \"#.##\")), style=label.style_label_down, textcolor=color.white, color=color.new(draftMomentum ? color.green : color.red, 0))",
            "",
            "// alerts",
            "alertcondition(ta.crossover(close, draftMidpoint), \"Draft bullish crossover\", \"Draft scaffold crossed above midpoint.\")",
            "alertcondition(ta.crossunder(close, draftMidpoint), \"Draft bearish crossover\", \"Draft scaffold crossed below midpoint.\")",
        ]
    )
    return "\n".join(lines) + "\n"


def build_daily_bias_pine_script(spec: dict) -> str:
    title = build_script_title(spec)
    lines = [
        "// This Pine Script(TM) code is subject to the terms of the Mozilla Public License 2.0 at https://mozilla.org/MPL/2.0/",
        "// Copyright builder-block-C",
        "//@version=6",
        f'indicator("{escape_pine_string(title)}", overlay=true, max_lines_count=200, max_labels_count=120, max_boxes_count=20)',
        f"// TV_SYNC_SIGNATURE: {title}",
        "// Visual workflow:",
        "// 1. Select the active reference range from the previous day or previous candle.",
        "// 2. Classify continuation vs sweep-back-inside reversal behavior.",
        "// 3. Track equilibrium respect, wick pressure, and lower-timeframe proxy alignment.",
        "",
        "// constants",
        "STATE_NEUTRAL = 0",
        "STATE_CONTINUATION_BULL = 1",
        "STATE_CONTINUATION_BEAR = -1",
        "STATE_REVERSAL_WATCH_BULL = 2",
        "STATE_REVERSAL_WATCH_BEAR = -2",
        "STATE_REVERSAL_CONFIRMED_BULL = 3",
        "STATE_REVERSAL_CONFIRMED_BEAR = -3",
        "STATE_EXHAUSTED = 9",
        "",
        "// inputs",
    ]
    lines.extend(build_input_block(spec))
    lines.extend(
        [
            "",
            "// helper functions",
            "midpoint(float highPrice, float lowPrice) => (highPrice + lowPrice) / 2.0",
            "safeRange(float highPrice, float lowPrice) => math.max(highPrice - lowPrice, syminfo.mintick)",
            "upperWick(float openPrice, float highPrice, float closePrice) => highPrice - math.max(openPrice, closePrice)",
            "lowerWick(float openPrice, float lowPrice, float closePrice) => math.min(openPrice, closePrice) - lowPrice",
            "wickRatio(float wickSize, float totalRange) => wickSize / math.max(totalRange, syminfo.mintick)",
            'priceText(float value) => na(value) ? "na" : str.tostring(value, format.mintick)',
            "biasStateText(int state) => state == STATE_CONTINUATION_BULL ? \"continuation bull\" : state == STATE_CONTINUATION_BEAR ? \"continuation bear\" : state == STATE_REVERSAL_WATCH_BULL ? \"reversal watch bull\" : state == STATE_REVERSAL_WATCH_BEAR ? \"reversal watch bear\" : state == STATE_REVERSAL_CONFIRMED_BULL ? \"reversal confirmed bull\" : state == STATE_REVERSAL_CONFIRMED_BEAR ? \"reversal confirmed bear\" : state == STATE_EXHAUSTED ? \"exhausted\" : \"neutral\"",
            "biasStateColor(int state) => state == STATE_CONTINUATION_BULL ? color.green : state == STATE_CONTINUATION_BEAR ? color.red : state == STATE_REVERSAL_WATCH_BULL or state == STATE_REVERSAL_CONFIRMED_BULL ? color.teal : state == STATE_REVERSAL_WATCH_BEAR or state == STATE_REVERSAL_CONFIRMED_BEAR ? color.orange : color.gray",
            "",
            "// higher-timeframe reference range",
            'string higherTimeframe = alignmentModeInput == "higher_only" ? "D" : "240"',
            "float previousDayHigh = request.security(syminfo.tickerid, higherTimeframe, high[1], lookahead=barmerge.lookahead_off)",
            "float previousDayLow = request.security(syminfo.tickerid, higherTimeframe, low[1], lookahead=barmerge.lookahead_off)",
            "float previousDayClose = request.security(syminfo.tickerid, higherTimeframe, close[1], lookahead=barmerge.lookahead_off)",
            "",
            "// current-frame reference range fallback",
            "float previousCandleHigh = high[1]",
            "float previousCandleLow = low[1]",
            "float previousCandleClose = close[1]",
            "",
            '// active reference range selection',
            'bool preferPreviousDay = biasAnchorModeInput != "previous_candle_only" and not na(previousDayHigh) and not na(previousDayLow)',
            'bool forcePreviousCandle = biasAnchorModeInput == "previous_candle_only"',
            "float referenceRangeHigh = preferPreviousDay and not forcePreviousCandle ? previousDayHigh : previousCandleHigh",
            "float referenceRangeLow = preferPreviousDay and not forcePreviousCandle ? previousDayLow : previousCandleLow",
            "float referenceRangeClose = preferPreviousDay and not forcePreviousCandle ? previousDayClose : previousCandleClose",
            "float referenceRangeSize = safeRange(referenceRangeHigh, referenceRangeLow)",
            "float referenceRangeEquilibrium = midpoint(referenceRangeHigh, referenceRangeLow)",
            "float equilibriumTolerance = referenceRangeSize * equilibriumTolerancePercentOfRangeInput",
            "bool higherTimeframeBullBias = referenceRangeClose >= referenceRangeEquilibrium",
            "int directionalContext = higherTimeframeBullBias ? 1 : -1",
            'string directionalContextText = directionalContext > 0 ? "bullish prior close" : "bearish prior close"',
            "",
            "// structure classification",
            "bool closesAboveRange = close > referenceRangeHigh",
            "bool closesBelowRange = close < referenceRangeLow",
            "bool sweepsHighAndClosesInside = high > referenceRangeHigh and close <= referenceRangeHigh and close >= referenceRangeLow",
            "bool sweepsLowAndClosesInside = low < referenceRangeLow and close >= referenceRangeLow and close <= referenceRangeHigh",
            "int previousRangeInteractionState = closesAboveRange ? 1 : closesBelowRange ? -1 : sweepsLowAndClosesInside ? 2 : sweepsHighAndClosesInside ? -2 : 0",
            "",
            "// wick and equilibrium filters",
            "float currentRange = safeRange(high, low)",
            "float bullishOpposingWickRatio = wickRatio(upperWick(open, high, close), currentRange)",
            "float bearishOpposingWickRatio = wickRatio(lowerWick(open, low, close), currentRange)",
            "bool continuationBullWickOk = bullishOpposingWickRatio <= opposingWickThresholdRatioInput",
            "bool continuationBearWickOk = bearishOpposingWickRatio <= opposingWickThresholdRatioInput",
            "bool equilibriumRespectBull = close >= referenceRangeEquilibrium - equilibriumTolerance",
            "bool equilibriumRespectBear = close <= referenceRangeEquilibrium + equilibriumTolerance",
            "int wickExpectationState = continuationBullWickOk ? 1 : continuationBearWickOk ? -1 : 0",
            "int equilibriumRespectState = equilibriumRespectBull ? 1 : equilibriumRespectBear ? -1 : 0",
            "",
            "// lower-timeframe confirmation proxy",
            "bool lowerTimeframeBullProxy = close > open and close >= referenceRangeEquilibrium",
            "bool lowerTimeframeBearProxy = close < open and close <= referenceRangeEquilibrium",
            "int lowerTimeframeConfirmationState = lowerTimeframeBullProxy ? 1 : lowerTimeframeBearProxy ? -1 : 0",
            "",
            "// alignment proxy",
            "float intermediateOpen = request.security(syminfo.tickerid, \"60\", open, lookahead=barmerge.lookahead_off)",
            "float intermediateClose = request.security(syminfo.tickerid, \"60\", close, lookahead=barmerge.lookahead_off)",
            "bool alignmentBull = higherTimeframe == \"D\" ? referenceRangeClose >= referenceRangeEquilibrium : intermediateClose >= intermediateOpen",
            "bool alignmentBear = higherTimeframe == \"D\" ? referenceRangeClose <= referenceRangeEquilibrium : intermediateClose <= intermediateOpen",
            "int alignmentState = alignmentBull ? 1 : alignmentBear ? -1 : 0",
            "",
            "// framework geometry",
            "float continuationPoiTop = directionalContext > 0 ? referenceRangeHigh : referenceRangeEquilibrium",
            "float continuationPoiBottom = directionalContext > 0 ? referenceRangeEquilibrium : referenceRangeLow",
            "float reversalAnchorPrice = directionalContext > 0 ? referenceRangeHigh : referenceRangeLow",
            "float anchorBandSize = math.max(referenceRangeSize * 0.04, syminfo.mintick * 4.0)",
            "float reversalAnchorBandTop = reversalAnchorPrice + anchorBandSize",
            "float reversalAnchorBandBottom = reversalAnchorPrice - anchorBandSize",
            "float continuationProjection = directionalContext > 0 ? referenceRangeHigh + referenceRangeSize : referenceRangeLow - referenceRangeSize",
            "",
            "// candidate states",
            "bool continuationBullCandidate = directionalContext > 0 and closesAboveRange and continuationBullWickOk and equilibriumRespectBull and alignmentState >= 0",
            "bool continuationBearCandidate = directionalContext < 0 and closesBelowRange and continuationBearWickOk and equilibriumRespectBear and alignmentState <= 0",
            "bool bullishReversalCandidate = sweepsLowAndClosesInside and (reversalModeInput == \"sweep_then_close_back_inside\" or directionalContext < 0)",
            "bool bearishReversalCandidate = sweepsHighAndClosesInside and (reversalModeInput == \"sweep_then_close_back_inside\" or directionalContext > 0)",
            "bool bullishReversalConfirmed = bullishReversalCandidate and (not requireLowerTimeframeConfirmationInput or lowerTimeframeConfirmationState > 0)",
            "bool bearishReversalConfirmed = bearishReversalCandidate and (not requireLowerTimeframeConfirmationInput or lowerTimeframeConfirmationState < 0)",
            "",
            "// phase shift guardrail",
            "var int continuationCount = 0",
            "bool continuationBar = directionalContext > 0 ? closesAboveRange : closesBelowRange",
            "continuationCount := continuationBar ? continuationCount + 1 : 0",
            "bool phaseShiftWarningState = continuationCount >= phaseShiftContinuationCountInput",
            "",
            "// state machine",
            "int dailyBiasState = STATE_NEUTRAL",
            "if continuationBullCandidate",
            "    dailyBiasState := STATE_CONTINUATION_BULL",
            "else if continuationBearCandidate",
            "    dailyBiasState := STATE_CONTINUATION_BEAR",
            "else if bullishReversalCandidate",
            "    dailyBiasState := bullishReversalConfirmed ? STATE_REVERSAL_CONFIRMED_BULL : STATE_REVERSAL_WATCH_BULL",
            "else if bearishReversalCandidate",
            "    dailyBiasState := bearishReversalConfirmed ? STATE_REVERSAL_CONFIRMED_BEAR : STATE_REVERSAL_WATCH_BEAR",
            "if phaseShiftWarningState and (dailyBiasState == STATE_CONTINUATION_BULL or dailyBiasState == STATE_CONTINUATION_BEAR)",
            "    dailyBiasState := STATE_EXHAUSTED",
            "",
            "string biasTargetModel = dailyBiasState == STATE_CONTINUATION_BULL ? \"expansion continuation\" : dailyBiasState == STATE_CONTINUATION_BEAR ? \"expansion continuation\" : dailyBiasState == STATE_REVERSAL_CONFIRMED_BULL ? \"range reversion up\" : dailyBiasState == STATE_REVERSAL_CONFIRMED_BEAR ? \"range reversion down\" : \"neutral\"",
            "string setupTypeText = dailyBiasState == STATE_CONTINUATION_BULL or dailyBiasState == STATE_CONTINUATION_BEAR ? \"continuation\" : dailyBiasState == STATE_REVERSAL_WATCH_BULL or dailyBiasState == STATE_REVERSAL_WATCH_BEAR or dailyBiasState == STATE_REVERSAL_CONFIRMED_BULL or dailyBiasState == STATE_REVERSAL_CONFIRMED_BEAR ? \"reversal\" : dailyBiasState == STATE_EXHAUSTED ? \"phase shift\" : \"neutral\"",
            "string pointOfInterestText = setupTypeText == \"continuation\" ? directionalContext > 0 ? \"equilibrium to prior high\" : \"equilibrium to prior low\" : directionalContext > 0 ? \"prior-day high sweep\" : \"prior-day low sweep\"",
            "string confirmationText = dailyBiasState == STATE_REVERSAL_WATCH_BULL or dailyBiasState == STATE_REVERSAL_WATCH_BEAR ? \"waiting for lower timeframe confirmation\" : dailyBiasState == STATE_REVERSAL_CONFIRMED_BULL or dailyBiasState == STATE_REVERSAL_CONFIRMED_BEAR ? \"lower timeframe confirmed\" : dailyBiasState == STATE_CONTINUATION_BULL or dailyBiasState == STATE_CONTINUATION_BEAR ? \"close outside range with equilibrium respect\" : dailyBiasState == STATE_EXHAUSTED ? \"continuation count exhausted\" : \"stand by\"",
            "string wickReadText = wickExpectationState > 0 ? \"expansion-supporting wick\" : wickExpectationState < 0 ? \"rejection-dominant wick\" : \"mixed wick\"",
            "float targetPrimaryPrice = dailyBiasState == STATE_CONTINUATION_BULL ? referenceRangeHigh : dailyBiasState == STATE_CONTINUATION_BEAR ? referenceRangeLow : dailyBiasState == STATE_REVERSAL_WATCH_BULL or dailyBiasState == STATE_REVERSAL_CONFIRMED_BULL ? referenceRangeEquilibrium : dailyBiasState == STATE_REVERSAL_WATCH_BEAR or dailyBiasState == STATE_REVERSAL_CONFIRMED_BEAR ? referenceRangeEquilibrium : na",
            "float targetSecondaryPrice = dailyBiasState == STATE_CONTINUATION_BULL or dailyBiasState == STATE_CONTINUATION_BEAR ? continuationProjection : dailyBiasState == STATE_REVERSAL_WATCH_BULL or dailyBiasState == STATE_REVERSAL_CONFIRMED_BULL ? referenceRangeHigh : dailyBiasState == STATE_REVERSAL_WATCH_BEAR or dailyBiasState == STATE_REVERSAL_CONFIRMED_BEAR ? referenceRangeLow : na",
            "int executionDirection = dailyBiasState == STATE_CONTINUATION_BULL or dailyBiasState == STATE_REVERSAL_WATCH_BULL or dailyBiasState == STATE_REVERSAL_CONFIRMED_BULL ? 1 : dailyBiasState == STATE_CONTINUATION_BEAR or dailyBiasState == STATE_REVERSAL_WATCH_BEAR or dailyBiasState == STATE_REVERSAL_CONFIRMED_BEAR ? -1 : directionalContext",
            "float activePoiTop = dailyBiasState == STATE_REVERSAL_WATCH_BULL or dailyBiasState == STATE_REVERSAL_CONFIRMED_BULL or dailyBiasState == STATE_REVERSAL_WATCH_BEAR or dailyBiasState == STATE_REVERSAL_CONFIRMED_BEAR ? reversalAnchorBandTop : continuationPoiTop",
            "float activePoiBottom = dailyBiasState == STATE_REVERSAL_WATCH_BULL or dailyBiasState == STATE_REVERSAL_CONFIRMED_BULL or dailyBiasState == STATE_REVERSAL_WATCH_BEAR or dailyBiasState == STATE_REVERSAL_CONFIRMED_BEAR ? reversalAnchorBandBottom : continuationPoiBottom",
            "float activePoiMid = midpoint(activePoiTop, activePoiBottom)",
            "bool activePoiTouched = high >= activePoiBottom and low <= activePoiTop",
            "bool candle2BullAtPoi = executionDirection > 0 and activePoiTouched[1] and low[1] < low[2] and low[1] <= low",
            "bool candle2BearAtPoi = executionDirection < 0 and activePoiTouched[1] and high[1] > high[2] and high[1] >= high",
            "bool bullishCandle3Closure = candle2BullAtPoi and close > open and close > math.max(open[1], close[1])",
            "bool bearishCandle3Closure = candle2BearAtPoi and close < open and close < math.min(open[1], close[1])",
            "string entryModelText = bullishCandle3Closure or bearishCandle3Closure ? \"c3 closure ready\" : candle2BullAtPoi or candle2BearAtPoi ? \"c2 formed at htf poi\" : activePoiTouched ? \"htf poi tagged\" : \"wait for htf poi\"",
            "",
            "// visuals",
            "referenceHighPlot = plot(referenceRangeHigh, \"Reference high\", color=color.new(color.red, 15), linewidth=1, style=plot.style_linebr, show_last=visualLookbackBarsInput)",
            "referenceLowPlot = plot(referenceRangeLow, \"Reference low\", color=color.new(color.green, 15), linewidth=1, style=plot.style_linebr, show_last=visualLookbackBarsInput)",
            "equilibriumPlot = plot(referenceRangeEquilibrium, \"Reference equilibrium\", color=color.new(color.orange, 0), linewidth=2, style=plot.style_linebr, show_last=visualLookbackBarsInput)",
            "activePoiTopPlot = plot(activePoiTop, \"Active HTF POI top\", color=color.new(color.blue, 100), display=display.none, show_last=visualLookbackBarsInput)",
            "activePoiBottomPlot = plot(activePoiBottom, \"Active HTF POI bottom\", color=color.new(color.blue, 100), display=display.none, show_last=visualLookbackBarsInput)",
            "fill(activePoiTopPlot, activePoiBottomPlot, color=color.new(executionDirection > 0 ? color.green : color.red, 82), title=\"Active HTF POI\")",
            "plot(targetPrimaryPrice, \"Primary target\", color=color.new(color.aqua, 0), linewidth=2, style=plot.style_linebr, show_last=visualLookbackBarsInput)",
            "plot(targetSecondaryPrice, \"Secondary target\", color=color.new(color.silver, 0), linewidth=1, style=plot.style_linebr, show_last=visualLookbackBarsInput)",
            "bgcolor(showHistoricalBiasTintInput ? color.new(biasStateColor(dailyBiasState), 95) : na, title=\"Daily bias state background\")",
            "plotshape(sweepsHighAndClosesInside, title=\"Liquidity sweep high\", style=shape.triangledown, location=location.abovebar, color=color.new(color.orange, 0), text=\"sweep\", textcolor=color.white, size=size.tiny, show_last=visualLookbackBarsInput)",
            "plotshape(sweepsLowAndClosesInside, title=\"Liquidity sweep low\", style=shape.triangleup, location=location.belowbar, color=color.new(color.teal, 0), text=\"sweep\", textcolor=color.white, size=size.tiny, show_last=visualLookbackBarsInput)",
            "plotshape(dailyBiasState == STATE_REVERSAL_CONFIRMED_BULL and dailyBiasState[1] != STATE_REVERSAL_CONFIRMED_BULL, title=\"Bull reversal confirmed\", style=shape.labelup, location=location.belowbar, color=color.new(color.teal, 0), text=\"confirm\", textcolor=color.white, size=size.tiny, show_last=visualLookbackBarsInput)",
            "plotshape(dailyBiasState == STATE_REVERSAL_CONFIRMED_BEAR and dailyBiasState[1] != STATE_REVERSAL_CONFIRMED_BEAR, title=\"Bear reversal confirmed\", style=shape.labeldown, location=location.abovebar, color=color.new(color.orange, 0), text=\"confirm\", textcolor=color.white, size=size.tiny, show_last=visualLookbackBarsInput)",
            "plotshape(dailyBiasState == STATE_CONTINUATION_BULL and dailyBiasState[1] != STATE_CONTINUATION_BULL, title=\"Bull continuation active\", style=shape.circle, location=location.abovebar, color=color.new(color.green, 0), text=\"cont\", textcolor=color.white, size=size.tiny, show_last=visualLookbackBarsInput)",
            "plotshape(dailyBiasState == STATE_CONTINUATION_BEAR and dailyBiasState[1] != STATE_CONTINUATION_BEAR, title=\"Bear continuation active\", style=shape.circle, location=location.belowbar, color=color.new(color.red, 0), text=\"cont\", textcolor=color.white, size=size.tiny, show_last=visualLookbackBarsInput)",
            "plotshape(candle2BullAtPoi, title=\"Bull candle 2 at HTF POI\", style=shape.labelup, location=location.belowbar, offset=-1, color=color.new(color.green, 15), text=\"C2\", textcolor=color.white, size=size.tiny, show_last=visualLookbackBarsInput)",
            "plotshape(candle2BearAtPoi, title=\"Bear candle 2 at HTF POI\", style=shape.labeldown, location=location.abovebar, offset=-1, color=color.new(color.red, 15), text=\"C2\", textcolor=color.white, size=size.tiny, show_last=visualLookbackBarsInput)",
            "plotshape(bullishCandle3Closure, title=\"Bull candle 3 closure\", style=shape.labelup, location=location.belowbar, color=color.new(color.teal, 0), text=\"C3\", textcolor=color.white, size=size.tiny, show_last=visualLookbackBarsInput)",
            "plotshape(bearishCandle3Closure, title=\"Bear candle 3 closure\", style=shape.labeldown, location=location.abovebar, color=color.new(color.orange, 0), text=\"C3\", textcolor=color.white, size=size.tiny, show_last=visualLookbackBarsInput)",
            "plotshape(phaseShiftWarningState, title=\"Phase shift warning\", style=shape.diamond, location=location.top, color=color.new(color.fuchsia, 0), text=\"phase\", textcolor=color.white, size=size.tiny, show_last=visualLookbackBarsInput)",
            "var table biasDashboard = table.new(position.top_right, 2, 7, bgcolor=color.new(color.black, 78), frame_color=color.new(color.white, 70), frame_width=1)",
            "var table levelsLadder = table.new(position.middle_right, 2, 6, bgcolor=color.new(color.black, 82), frame_color=color.new(color.white, 70), frame_width=1)",
            "if barstate.islast",
            "    table.cell(biasDashboard, 0, 0, \"Bias\", text_color=color.white)",
            "    table.cell(biasDashboard, 1, 0, biasStateText(dailyBiasState), text_color=color.white, bgcolor=color.new(biasStateColor(dailyBiasState), 35))",
            "    table.cell(biasDashboard, 0, 1, \"Context\", text_color=color.white)",
            "    table.cell(biasDashboard, 1, 1, directionalContextText, text_color=color.white)",
            "    table.cell(biasDashboard, 0, 2, \"POI\", text_color=color.white)",
            "    table.cell(biasDashboard, 1, 2, pointOfInterestText, text_color=color.white)",
            "    table.cell(biasDashboard, 0, 3, \"Confirm\", text_color=color.white)",
            "    table.cell(biasDashboard, 1, 3, confirmationText, text_color=color.white)",
            "    table.cell(biasDashboard, 0, 4, \"Wick\", text_color=color.white)",
            "    table.cell(biasDashboard, 1, 4, wickReadText, text_color=color.white)",
            "    table.cell(biasDashboard, 0, 5, \"Entry\", text_color=color.white)",
            "    table.cell(biasDashboard, 1, 5, entryModelText, text_color=color.white)",
            "    table.cell(biasDashboard, 0, 6, \"Targets\", text_color=color.white)",
            "    table.cell(biasDashboard, 1, 6, str.format(\"{0} / {1}\", priceText(targetPrimaryPrice), priceText(targetSecondaryPrice)), text_color=color.white)",
            "    table.cell(levelsLadder, 0, 0, \"PDH\", text_color=color.white, bgcolor=color.new(color.red, 60))",
            "    table.cell(levelsLadder, 1, 0, priceText(referenceRangeHigh), text_color=color.white)",
            "    table.cell(levelsLadder, 0, 1, \"EQ\", text_color=color.white, bgcolor=color.new(color.orange, 55))",
            "    table.cell(levelsLadder, 1, 1, priceText(referenceRangeEquilibrium), text_color=color.white)",
            "    table.cell(levelsLadder, 0, 2, \"PDL\", text_color=color.white, bgcolor=color.new(color.green, 60))",
            "    table.cell(levelsLadder, 1, 2, priceText(referenceRangeLow), text_color=color.white)",
            "    table.cell(levelsLadder, 0, 3, \"HTF POI\", text_color=color.white, bgcolor=color.new(executionDirection > 0 ? color.green : color.red, 70))",
            "    table.cell(levelsLadder, 1, 3, str.format(\"{0}-{1}\", priceText(activePoiBottom), priceText(activePoiTop)), text_color=color.white)",
            "    table.cell(levelsLadder, 0, 4, \"T1\", text_color=color.white, bgcolor=color.new(color.aqua, 60))",
            "    table.cell(levelsLadder, 1, 4, priceText(targetPrimaryPrice), text_color=color.white)",
            "    table.cell(levelsLadder, 0, 5, \"T2\", text_color=color.white, bgcolor=color.new(color.silver, 60))",
            "    table.cell(levelsLadder, 1, 5, priceText(targetSecondaryPrice), text_color=color.white)",
            "",
            "// alerts",
            "alertcondition(dailyBiasState != dailyBiasState[1], \"Daily bias state changed\", \"Daily bias framework state changed.\")",
            "alertcondition(dailyBiasState == STATE_REVERSAL_CONFIRMED_BULL or dailyBiasState == STATE_REVERSAL_CONFIRMED_BEAR, \"Reversal confirmed\", \"Daily bias framework reversal confirmation fired.\")",
            "alertcondition(dailyBiasState == STATE_CONTINUATION_BULL or dailyBiasState == STATE_CONTINUATION_BEAR, \"Continuation bias active\", \"Daily bias framework continuation state is active.\")",
        ]
    )
    return "\n".join(lines) + "\n"


def default_daily_bias_c123_input_groups() -> list[dict]:
    return [
        {
            "group": "Visibility",
            "inputs": [
                {
                    "key": "showDailyBiasBanner",
                    "type": "bool",
                    "default": True,
                    "description": "Show the current daily bias banner.",
                },
                {
                    "key": "showDailyPoiZone",
                    "type": "bool",
                    "default": True,
                    "description": "Show the active daily POI zone on the hourly chart.",
                },
                {
                    "key": "showHourlySequence",
                    "type": "bool",
                    "default": True,
                    "description": "Show the active 1H C1/C2/C3 labels and entry guide when they form inside the daily POI, otherwise show one small waiting cue.",
                },
            ],
        }
    ]


def build_daily_bias_c123_map_pine_script(spec: dict) -> str:
    title = build_script_title(spec)
    input_groups = spec.get("input_groups") or default_daily_bias_c123_input_groups()
    spec_with_defaults = {**spec, "input_groups": input_groups}
    chart_timeframe = str(spec.get("timeframe_contract", {}).get("chart", "60"))
    bias_timeframe = str(spec.get("timeframe_contract", {}).get("bias", "D"))
    execution_timeframe = str(spec.get("timeframe_contract", {}).get("execution", "5"))

    lines = [
        "// This Pine Script(TM) code is subject to the terms of the Mozilla Public License 2.0 at https://mozilla.org/MPL/2.0/",
        "// Copyright builder-block-C",
        "//@version=6",
        f'indicator("{escape_pine_string(title)}", overlay=true, max_lines_count=20, max_labels_count=20, max_boxes_count=4)',
        f"// TV_SYNC_SIGNATURE: {title}",
        f"// {spec.get('implementation_summary', 'Daily bias active-sequence-only map.')}",
        "",
        "// inputs",
    ]
    lines.extend(build_input_block(spec_with_defaults))
    lines.extend(
        [
            "",
            "// chart guardrail",
            f'bool supportedChart = timeframe.isminutes and timeframe.multiplier == {chart_timeframe}',
            "var label unsupportedTimeframeLabel = na",
            "",
            "// daily bias and POI state",
            f'float dailyPrevClose = request.security(syminfo.tickerid, "{bias_timeframe}", close[1], lookahead=barmerge.lookahead_off)',
            f'float dailyPrevHigh = request.security(syminfo.tickerid, "{bias_timeframe}", high[1], lookahead=barmerge.lookahead_off)',
            f'float dailyPrevLow = request.security(syminfo.tickerid, "{bias_timeframe}", low[1], lookahead=barmerge.lookahead_off)',
            f'float dailyPrev2High = request.security(syminfo.tickerid, "{bias_timeframe}", high[2], lookahead=barmerge.lookahead_off)',
            f'float dailyPrev2Low = request.security(syminfo.tickerid, "{bias_timeframe}", low[2], lookahead=barmerge.lookahead_off)',
            "float dailyMidpoint = (dailyPrevHigh + dailyPrevLow) / 2.0",
            "int dailyBiasDirection = na(dailyPrevClose) or na(dailyPrev2High) or na(dailyPrev2Low) ? 0 : dailyPrevClose > dailyPrev2High ? 1 : dailyPrevClose < dailyPrev2Low ? -1 : dailyPrevClose >= dailyMidpoint ? 1 : -1",
            'string dailyBiasText = dailyBiasDirection > 0 ? "Daily Bias: Bullish" : dailyBiasDirection < 0 ? "Daily Bias: Bearish" : "Daily Bias: Neutral"',
            "color dailyBiasColor = dailyBiasDirection > 0 ? color.new(color.green, 0) : dailyBiasDirection < 0 ? color.new(color.red, 0) : color.new(color.gray, 0)",
            "float dailyPoiTop = dailyBiasDirection > 0 ? dailyMidpoint : dailyBiasDirection < 0 ? dailyPrevHigh : na",
            "float dailyPoiBottom = dailyBiasDirection > 0 ? dailyPrevLow : dailyBiasDirection < 0 ? dailyMidpoint : na",
            "bool priceInsideDailyPoi = dailyBiasDirection != 0 and not na(dailyPoiTop) and not na(dailyPoiBottom) and high >= dailyPoiBottom and low <= dailyPoiTop",
            f'int activeBiasWindowStart = int(time("{bias_timeframe}"))',
            f'int activeBiasWindowEnd = activeBiasWindowStart + int(timeframe.in_seconds("{bias_timeframe}") * 1000)',
            "",
            "// hourly phase 1 sequence",
            "var int activeHourlyDir = 0",
            "var int activeHourlyC1Time = na",
            "var int activeHourlyC2Time = na",
            "var int activeHourlyC3Time = na",
            "var float activeHourlyC1Price = na",
            "var float activeHourlyC2Price = na",
            "var float activeHourlyC3Price = na",
            "var int activeEntryTime = na",
            "var float activeEntryPrice = na",
            "var float activeHourlyInvalidation = na",
            "var int activeLtfDir = 0",
            "var int activeLtfC2Time = na",
            "var int activeLtfC3Time = na",
            "var float activeLtfEntryPrice = na",
            "float candleTwoMidpoint = (high[1] + low[1]) / 2.0",
            "bool bullishHourlyC2 = supportedChart and priceInsideDailyPoi[1] and dailyBiasDirection > 0 and low[1] < low[2] and close[1] > open[1] and close[1] >= candleTwoMidpoint",
            "bool bearishHourlyC2 = supportedChart and priceInsideDailyPoi[1] and dailyBiasDirection < 0 and high[1] > high[2] and close[1] < open[1] and close[1] <= candleTwoMidpoint",
            "bool bullishHourlyC2Trigger = bullishHourlyC2 and (na(activeHourlyC2Time) or activeHourlyC2Time != int(time[1]))",
            "bool bearishHourlyC2Trigger = bearishHourlyC2 and (na(activeHourlyC2Time) or activeHourlyC2Time != int(time[1]))",
            "if supportedChart",
            "    if bullishHourlyC2Trigger",
            "        activeHourlyDir := 1",
            "        activeHourlyC1Time := int(time[2])",
            "        activeHourlyC2Time := int(time[1])",
            "        activeHourlyC3Time := int(time)",
            "        activeHourlyC1Price := math.min(open[2], close[2])",
            "        activeHourlyC2Price := math.min(open[1], close[1])",
            "        activeHourlyC3Price := math.min(open, close)",
            "        activeEntryTime := int(time)",
            "        activeEntryPrice := open",
            "        activeHourlyInvalidation := dailyPoiBottom",
            "    else if bearishHourlyC2Trigger",
            "        activeHourlyDir := -1",
            "        activeHourlyC1Time := int(time[2])",
            "        activeHourlyC2Time := int(time[1])",
            "        activeHourlyC3Time := int(time)",
            "        activeHourlyC1Price := math.max(open[2], close[2])",
            "        activeHourlyC2Price := math.max(open[1], close[1])",
            "        activeHourlyC3Price := math.max(open, close)",
            "        activeEntryTime := int(time)",
            "        activeEntryPrice := open",
            "        activeHourlyInvalidation := dailyPoiTop",
            "bool hourlyInvalidated = activeHourlyDir == 1 ? close < activeHourlyInvalidation : activeHourlyDir == -1 ? close > activeHourlyInvalidation : false",
            "if supportedChart and hourlyInvalidated",
            "    activeHourlyDir := 0",
            "    activeHourlyC1Time := na",
            "    activeHourlyC2Time := na",
            "    activeHourlyC3Time := na",
            "    activeHourlyC1Price := na",
            "    activeHourlyC2Price := na",
            "    activeHourlyC3Price := na",
            "    activeEntryTime := na",
            "    activeEntryPrice := na",
            "    activeHourlyInvalidation := na",
            "    activeLtfDir := 0",
            "    activeLtfC2Time := na",
            "    activeLtfC3Time := na",
            "    activeLtfEntryPrice := na",
            "",
            "// five-minute continuation refinement",
            f'float ltfOpen = request.security(syminfo.tickerid, "{execution_timeframe}", open, lookahead=barmerge.lookahead_off)',
            f'float ltfHigh = request.security(syminfo.tickerid, "{execution_timeframe}", high, lookahead=barmerge.lookahead_off)',
            f'float ltfLow = request.security(syminfo.tickerid, "{execution_timeframe}", low, lookahead=barmerge.lookahead_off)',
            f'float ltfClose = request.security(syminfo.tickerid, "{execution_timeframe}", close, lookahead=barmerge.lookahead_off)',
            f'int ltfTime = int(request.security(syminfo.tickerid, "{execution_timeframe}", time, lookahead=barmerge.lookahead_off))',
            "float ltfCandleTwoMidpoint = (ltfHigh[1] + ltfLow[1]) / 2.0",
            "bool bullishLtfContinuation = supportedChart and activeHourlyDir > 0 and ltfLow[1] < ltfLow[2] and ltfClose[1] > ltfOpen[1] and ltfClose >= ltfCandleTwoMidpoint",
            "bool bearishLtfContinuation = supportedChart and activeHourlyDir < 0 and ltfHigh[1] > ltfHigh[2] and ltfClose[1] < ltfOpen[1] and ltfClose <= ltfCandleTwoMidpoint",
            "bool bullishLtfContinuationTrigger = bullishLtfContinuation and (na(activeLtfC2Time) or activeLtfC2Time != ltfTime[1])",
            "bool bearishLtfContinuationTrigger = bearishLtfContinuation and (na(activeLtfC2Time) or activeLtfC2Time != ltfTime[1])",
            "if supportedChart and activeHourlyDir != 0",
            "    if bullishLtfContinuationTrigger",
            "        activeLtfDir := 1",
            "        activeLtfC2Time := ltfTime[1]",
            "        activeLtfC3Time := ltfTime",
            "        activeLtfEntryPrice := ltfOpen",
            "    else if bearishLtfContinuationTrigger",
            "        activeLtfDir := -1",
            "        activeLtfC2Time := ltfTime[1]",
            "        activeLtfC3Time := ltfTime",
            "        activeLtfEntryPrice := ltfOpen",
            "if supportedChart and activeHourlyDir == 0",
            "    activeLtfDir := 0",
            "    activeLtfC2Time := na",
            "    activeLtfC3Time := na",
            "    activeLtfEntryPrice := na",
            "",
            "// active-sequence-only labels",
            "var label hourlyC1Label = na",
            "var label hourlyC2Label = na",
            "var label hourlyC3Label = na",
            "var label entryGuideLabel = na",
            "var label hourlyWaitingLabel = na",
            "var label dailyBiasLabel = na",
            "var label dailyPoiLabel = na",
            "var box dailyPoiBox = na",
            "if barstate.islast",
            "    if not na(unsupportedTimeframeLabel)",
                "        label.delete(unsupportedTimeframeLabel)",
            "    if not na(dailyPoiBox)",
            "        box.delete(dailyPoiBox)",
            "    if not supportedChart",
            '        unsupportedTimeframeLabel := label.new(bar_index, high, "Unsupported chart timeframe. Load this indicator on a 1H chart.", style=label.style_label_down, color=color.new(color.red, 0), textcolor=color.white)',
            "    else",
            "        if not na(hourlyC1Label)",
            "            label.delete(hourlyC1Label)",
            "        if not na(hourlyC2Label)",
            "            label.delete(hourlyC2Label)",
            "        if not na(hourlyC3Label)",
            "            label.delete(hourlyC3Label)",
            "        if not na(entryGuideLabel)",
            "            label.delete(entryGuideLabel)",
            "        if not na(hourlyWaitingLabel)",
            "            label.delete(hourlyWaitingLabel)",
            "        if not na(dailyBiasLabel)",
            "            label.delete(dailyBiasLabel)",
            "        if not na(dailyPoiLabel)",
            "            label.delete(dailyPoiLabel)",
            "        if showDailyBiasBannerInput and dailyBiasDirection != 0 and not na(dailyPoiTop)",
            '            dailyBiasLabel := label.new(activeBiasWindowEnd, dailyPoiTop, dailyBiasText, xloc=xloc.bar_time, style=label.style_label_left, color=color.new(dailyBiasColor, 15), textcolor=color.white)',
            "        if showDailyPoiZoneInput and dailyBiasDirection != 0 and not na(dailyPoiTop) and not na(dailyPoiBottom)",
            '            dailyPoiBox := box.new(activeBiasWindowStart, dailyPoiTop, activeBiasWindowEnd, dailyPoiBottom, xloc=xloc.bar_time, bgcolor=color.new(dailyBiasDirection > 0 ? color.green : color.red, 86), border_color=color.new(dailyBiasDirection > 0 ? color.green : color.red, 45))',
            '            dailyPoiLabel := label.new(activeBiasWindowEnd, dailyPoiBottom, "Daily POI", xloc=xloc.bar_time, style=label.style_label_left, color=color.new(color.navy, 55), textcolor=color.white)',
            "        if showHourlySequenceInput and activeHourlyDir != 0 and not na(activeHourlyC1Time) and not na(activeHourlyC2Time) and not na(activeHourlyC3Time)",
            f'            hourlyC1Label := label.new(activeHourlyC1Time - int(timeframe.in_seconds("{chart_timeframe}") * 250), activeHourlyC1Price, "C1", xloc=xloc.bar_time, style=activeHourlyDir > 0 ? label.style_label_up : label.style_label_down, color=color.new(activeHourlyDir > 0 ? color.green : color.red, 15), textcolor=color.white)',
            '            hourlyC2Label := label.new(activeHourlyC2Time, activeHourlyC2Price, "C2", xloc=xloc.bar_time, style=activeHourlyDir > 0 ? label.style_label_up : label.style_label_down, color=color.new(activeHourlyDir > 0 ? color.green : color.red, 0), textcolor=color.white)',
            f'            hourlyC3Label := label.new(activeHourlyC3Time + int(timeframe.in_seconds("{chart_timeframe}") * 250), activeHourlyC3Price, "C3", xloc=xloc.bar_time, style=activeHourlyDir > 0 ? label.style_label_up : label.style_label_down, color=color.new(activeHourlyDir > 0 ? color.green : color.red, 35), textcolor=color.white)',
            "        if showHourlySequenceInput and activeHourlyDir != 0 and not na(activeEntryTime) and not na(activeEntryPrice)",
            f'            entryGuideLabel := label.new(activeEntryTime + int(timeframe.in_seconds("{chart_timeframe}") * 500), activeEntryPrice, "Entry", xloc=xloc.bar_time, style=label.style_label_left, color=color.new(color.yellow, 10), textcolor=color.black)',
            "        if showHourlySequenceInput and activeHourlyDir == 0 and dailyBiasDirection != 0 and not na(dailyPoiTop) and not na(dailyPoiBottom)",
            '            hourlyWaitingLabel := label.new(activeBiasWindowEnd, (dailyPoiTop + dailyPoiBottom) / 2.0, dailyBiasDirection > 0 ? "Wait for long C2" : "Wait for short C2", xloc=xloc.bar_time, style=label.style_label_left, color=color.new(dailyBiasColor, 70), textcolor=color.white)',
            "",
            "// alerts",
            'alertcondition(activeHourlyDir != 0 and activeHourlyDir[1] == 0, "Hourly sequence activated", "A new active hourly C1/C2/C3 sequence formed inside the daily POI.")',
            'alertcondition(activeLtfDir != 0 and activeLtfDir[1] == 0, "Five minute continuation activated", "A new 5m continuation confirmation formed inside the active hourly Candle 3 window.")',
        ]
    )
    return "\n".join(lines) + "\n"


def build_pine_script(spec: dict) -> str:
    slug = get_spec_slug(spec)
    if slug == "daily_bias_framework":
        return build_daily_bias_pine_script(spec)
    if slug == "daily_bias_c123_map":
        return build_daily_bias_c123_map_pine_script(spec)
    return build_generic_pine_script(spec)


def extract_alert_titles(script_text: str) -> list[str]:
    titles: list[str] = []
    pattern = re.compile(r'alertcondition\(.*,\s*"([^"]+)"\s*,\s*"[^"]*"\s*\)')
    for line in script_text.splitlines():
        match = pattern.search(line.strip())
        if match:
            titles.append(match.group(1))
    return titles


def default_rule_state_fields(slug: str, spec: dict) -> list[str]:
    derived_series = [
        str(item.get("series", "")).strip()
        for item in spec.get("derived_series", [])
        if str(item.get("series", "")).strip()
    ]
    if derived_series:
        return derived_series
    if slug == "daily_bias_framework":
        return [
            "dailyBiasState",
            "previousRangeInteractionState",
            "wickExpectationState",
            "equilibriumRespectState",
            "lowerTimeframeConfirmationState",
            "alignmentState",
            "phaseShiftWarningState",
            "targetPrimaryPrice",
            "targetSecondaryPrice",
        ]
    if slug == "daily_bias_c123_map":
        return [
            "dailyBiasDirection",
            "dailyPoiTop",
            "dailyPoiBottom",
            "priceInsideDailyPoi",
            "activeHourlyDir",
            "activeHourlyC1Time",
            "activeHourlyC2Time",
            "activeHourlyC3Time",
            "activeEntryTime",
            "activeEntryPrice",
            "activeHourlyInvalidation",
            "activeLtfDir",
            "activeLtfC2Time",
            "activeLtfC3Time",
            "activeLtfEntryPrice",
        ]
    return []


def default_relation_type(slug: str) -> str:
    mapping = {
        "continuation_entry_model": "execution_model",
        "reversal_sequence_model": "execution_model",
        "daily_bias_framework": "bias_framework",
        "daily_bias_c123_map": "execution_model",
        "daily_profile_models": "session_profile",
        "fractal_closure_model": "confirmation_framework",
    }
    return mapping.get(slug, "")


def default_timeframe_scope(spec: dict) -> list[str]:
    timeframe_contract = spec.get("timeframe_contract", {})
    ordered = []
    for key in ("chart", "bias", "structure", "execution", "higher", "intermediate", "lower"):
        value = str(timeframe_contract.get(key, "")).strip()
        if value:
            ordered.append(f"{key}_{value}")
    return ordered


def build_candidate_event_contract(
    spec: dict,
    *,
    script_text: str,
    script_output_path: Path,
) -> dict:
    slug = get_spec_slug(spec)
    alert_titles = extract_alert_titles(script_text)
    primary_topic = ""
    direct_topics = spec.get("direct_topics", [])
    if direct_topics:
        primary_topic = str(direct_topics[0].get("topic", "")).strip()

    rule_state_fields = default_rule_state_fields(slug, spec)
    default_event = {
        "profile_slug": str(spec.get("trader_profile", {}).get("slug", "")).strip(),
        "topic": primary_topic,
        "trade_model": slug,
        "relation_type": default_relation_type(slug),
        "chart_context": {
            "setup_variant": slug,
            "source_kind": "tradingview_pine_alert",
            "timeframe_scope": default_timeframe_scope(spec),
            "session_scope": [],
        },
        "annotation": {
            "fired_alert": "",
            "rule_states": {field: "" for field in rule_state_fields},
        },
        "candidate_signal": {
            "timestamp": "",
            "side": "",
            "stop_price": "",
            "target_price": "",
            "quantity": 1.0,
            "session": "",
            "thesis": "",
        },
    }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "artifact_type": "pine_candidate_event_contract",
        "spec_key": slug,
        "trade_model": {
            "slug": slug,
            "name": str(spec.get("trade_model", {}).get("name", "")).strip(),
        },
        "script_title": build_script_title(spec),
        "script_output_path": path_for_manifest(script_output_path),
        "alert_titles": alert_titles,
        "rule_state_fields": rule_state_fields,
        "required_event_fields": [
            "trade_model",
            "chart_context",
            "annotation",
            "candidate_signal",
        ],
        "candidate_signal_required_fields": [
            "timestamp",
            "side",
            "stop_price",
            "target_price",
        ],
        "default_event": default_event,
    }


def generate_scripts(
    spec_paths: list[Path],
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    candidate_contract_output_dir: Path | None = DEFAULT_CANDIDATE_CONTRACT_DIR,
    manifest_output_path: Path | None = DEFAULT_MANIFEST_OUTPUT,
) -> dict:
    generated_scripts: list[dict] = []
    generated_contracts: list[dict] = []
    output_dir.mkdir(parents=True, exist_ok=True)
    if candidate_contract_output_dir is not None:
        candidate_contract_output_dir.mkdir(parents=True, exist_ok=True)

    for spec_path in spec_paths:
        spec = load_spec(spec_path)
        slug = get_spec_slug(spec)
        output_path = output_dir / f"{slug}.pine"
        script = build_pine_script(spec)
        output_path.write_text(script, encoding="utf-8")
        generated_scripts.append(
            {
                "spec_path": path_for_manifest(spec_path),
                "spec_key": slug,
                "script_title": build_script_title(spec),
                "output_path": path_for_manifest(output_path),
            }
        )
        if candidate_contract_output_dir is not None:
            contract_output_path = candidate_contract_output_dir / f"{slug}.candidate_event_contract.json"
            contract = build_candidate_event_contract(
                spec,
                script_text=script,
                script_output_path=output_path,
            )
            contract_output_path.write_text(json.dumps(contract, indent=2), encoding="utf-8")
            generated_contracts.append(
                {
                    "spec_key": slug,
                    "script_title": build_script_title(spec),
                    "output_path": path_for_manifest(contract_output_path),
                    "alert_count": len(contract["alert_titles"]),
                }
            )

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "generated_script_count": len(generated_scripts),
            "generated_candidate_contract_count": len(generated_contracts),
        },
        "generated_scripts": generated_scripts,
        "candidate_event_contracts": generated_contracts,
    }

    if manifest_output_path is not None:
        manifest_output_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_output_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def collect_spec_paths(spec_dir: Path, selected_spec_paths: list[str]) -> list[Path]:
    if selected_spec_paths:
        return [Path(path) for path in selected_spec_paths]
    return sorted(spec_dir.glob("*.json"))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate Pine draft scripts from repo indicator specs."
    )
    parser.add_argument("--spec-dir", default=str(DEFAULT_SPEC_DIR))
    parser.add_argument("--spec-path", action="append", default=[])
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--manifest-output", default=str(DEFAULT_MANIFEST_OUTPUT))
    args = parser.parse_args()

    spec_paths = collect_spec_paths(Path(args.spec_dir), list(args.spec_path))
    manifest = generate_scripts(
        spec_paths,
        output_dir=Path(args.output_dir),
        manifest_output_path=Path(args.manifest_output),
    )
    print(
        json.dumps(
            {
                "output_dir": str(Path(args.output_dir)),
                "generated_script_count": manifest["summary"]["generated_script_count"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
