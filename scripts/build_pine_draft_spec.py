from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "research.db"
TOPICS_DIR = ROOT / "topics"
OUTPUT_DIR = ROOT / "results" / "indicator_specs"


def load_indicator_spec(connection: sqlite3.Connection, spec_key: str) -> dict:
    row = connection.execute(
        """
        SELECT topic_slug, spec_key, name, target_language, status, spec_json
        FROM indicator_specs
        WHERE spec_key = ?
        """,
        (spec_key,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Indicator spec not found: {spec_key}")

    return {
        "topic_slug": str(row[0]),
        "spec_key": str(row[1]),
        "name": str(row[2]),
        "target_language": str(row[3]),
        "status": str(row[4]),
        "spec_json": json.loads(str(row[5])),
    }


def load_rulebook(topic_slug: str) -> dict:
    path = TOPICS_DIR / topic_slug / "rulebook.json"
    if not path.exists():
        raise FileNotFoundError(f"Rulebook not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            output.append(item)
    return output


def collect_scope_topics(base_spec: dict) -> list[str]:
    direct_topics = [str(topic["topic"]) for topic in base_spec.get("direct_topics", [])]
    support_topics = [
        str(topic["topic"])
        for topic in base_spec.get("resolved_requirements", [])
        if int(topic.get("minimum_depth", 99)) <= 1
    ]
    return dedupe(direct_topics + support_topics)


def build_rule_trace(rulebooks: dict[str, dict]) -> list[dict]:
    trace: list[dict] = []
    for topic_slug in rulebooks:
        rulebook = rulebooks[topic_slug]
        trace.append(
            {
                "topic": topic_slug,
                "open_questions": rulebook.get("openQuestions", []),
                "rules": [
                    {
                        "rule_ref": f"{topic_slug}.{rule['id']}",
                        "name": rule["name"],
                        "machine_checks": rule.get("machineChecks", []),
                        "pine_inputs_needed": rule.get("pineInputsNeeded", []),
                    }
                    for rule in rulebook.get("rules", [])
                ],
            }
        )
    return trace


def collect_unique_inputs(rulebooks: dict[str, dict]) -> list[dict]:
    per_topic: list[dict] = []
    for topic_slug in rulebooks:
        topic_inputs = dedupe(
            [
                str(input_name)
                for rule in rulebooks[topic_slug].get("rules", [])
                for input_name in rule.get("pineInputsNeeded", [])
            ]
        )
        per_topic.append(
            {
                "topic": topic_slug,
                "inputs": topic_inputs,
            }
        )
    return per_topic


def build_daily_bias_framework_draft(base_spec: dict) -> dict:
    scope_topics = collect_scope_topics(base_spec)
    rulebooks = {topic_slug: load_rulebook(topic_slug) for topic_slug in scope_topics}
    artifact_path = OUTPUT_DIR / f"{base_spec['trade_model']['slug']}.json"

    implementation_scope = dict(base_spec.get("implementation_scope", {}))
    implementation_scope.update(
        {
            "translation_stage": "draft",
            "build_target": "bias_overlay_indicator",
            "max_request_calls_budget": 5,
            "candidate_preservation_rule": "materializer_refreshes_candidate_fields_without_downgrading_draft_status",
            "timeframe_stack": {
                "higher": "daily_or_4h_bias_frame",
                "intermediate": "1h_or_15m_structure_frame",
                "lower": "5m_or_1m_confirmation_frame",
            },
        }
    )

    pine_sections = [
        "version",
        "indicator_declaration",
        "imports",
        "constants",
        "inputs",
        "functions",
        "calculations",
        "visuals",
        "alerts",
    ]

    input_groups = [
        {
            "group": "Reference Range",
            "inputs": [
                {
                    "key": "biasAnchorMode",
                    "type": "enum",
                    "default": "auto_daily_then_previous_candle",
                    "options": [
                        "auto_daily_then_previous_candle",
                        "previous_day_only",
                        "previous_candle_only",
                    ],
                    "description": "Select whether the bias framework prioritizes previous-day range logic, previous-candle range logic, or an automatic fallback sequence.",
                },
                {
                    "key": "equilibriumSource",
                    "type": "enum",
                    "default": "wick_to_wick",
                    "options": ["wick_to_wick"],
                    "description": "Keep equilibrium measured from wick high to wick low for the active reference range.",
                },
                {
                    "key": "phaseShiftContinuationCount",
                    "type": "int",
                    "default": 3,
                    "description": "Warn that continuation may be exhausted after this many same-direction continuation candles in sequence.",
                },
            ],
        },
        {
            "group": "Bias Classification",
            "inputs": [
                {
                    "key": "continuationCloseMode",
                    "type": "enum",
                    "default": "close_outside_previous_range",
                    "options": ["close_outside_previous_range"],
                    "description": "Continuation bias uses a close outside the selected reference range.",
                },
                {
                    "key": "reversalMode",
                    "type": "enum",
                    "default": "sweep_then_close_back_inside",
                    "options": [
                        "sweep_then_close_back_inside",
                        "prior_day_extreme_with_lower_timeframe_confirmation",
                    ],
                    "description": "Select whether reversal bias is framed from a generic sweep-and-close-back-inside event or the prior-day-extreme workflow with lower-timeframe confirmation.",
                },
                {
                    "key": "requireLowerTimeframeConfirmation",
                    "type": "bool",
                    "default": True,
                    "description": "Require a lower-timeframe confirmation proxy before promoting reversal watch into confirmed reversal bias.",
                },
            ],
        },
        {
            "group": "Wick and Equilibrium Filters",
            "inputs": [
                {
                    "key": "opposingWickThresholdRatio",
                    "type": "float",
                    "default": 0.35,
                    "description": "Provisional threshold used to separate small opposing wicks from large rejection wicks.",
                },
                {
                    "key": "equilibriumTolerancePercentOfRange",
                    "type": "float",
                    "default": 0.05,
                    "description": "Provisional tolerance band around equilibrium before a close is treated as a true wrong-side failure.",
                },
                {
                    "key": "requireCorrectHalfRespect",
                    "type": "bool",
                    "default": True,
                    "description": "Require continuation bias to keep lower-timeframe closes on the correct side of equilibrium.",
                },
            ],
        },
        {
            "group": "Alignment and Execution",
            "inputs": [
                {
                    "key": "alignmentMode",
                    "type": "enum",
                    "default": "higher_plus_intermediate",
                    "options": ["higher_only", "higher_plus_intermediate"],
                    "description": "Choose whether bias filtering uses the higher timeframe alone or requires intermediate-timeframe structure agreement.",
                },
                {
                    "key": "executionSessionMode",
                    "type": "enum",
                    "default": "all",
                    "options": ["all", "london", "new_york", "both"],
                    "description": "Restrict lower-timeframe confirmation to specific execution windows when desired.",
                },
                {
                    "key": "lowerTimeframeConfirmationMode",
                    "type": "enum",
                    "default": "directional_close_or_cisd_proxy",
                    "options": [
                        "directional_close_only",
                        "directional_close_or_cisd_proxy",
                    ],
                    "description": "First-pass lower-timeframe confirmation mode used for reversal confirmation.",
                },
            ],
        },
        {
            "group": "Visual Presentation",
            "inputs": [
                {
                    "key": "visualLookbackBars",
                    "type": "int",
                    "default": 120,
                    "description": "Limit reference geometry and target guides to the most recent bars so the active daily model stays readable.",
                },
                {
                    "key": "showHistoricalBiasTint",
                    "type": "bool",
                    "default": False,
                    "description": "Optionally tint historical bars by bias state, but keep the default focused on current-session teaching geometry.",
                },
            ],
        },
    ]

    derived_series = [
        {
            "series": "referenceRangeHigh",
            "description": "The active higher-timeframe or previous-candle range high used to frame bias.",
        },
        {
            "series": "referenceRangeLow",
            "description": "The active higher-timeframe or previous-candle range low used to frame bias.",
        },
        {
            "series": "referenceRangeEquilibrium",
            "description": "The wick-to-wick midpoint of the active reference range.",
        },
        {
            "series": "previousRangeInteractionState",
            "description": "Continuation versus sweep-back-inside classification relative to the active reference range.",
        },
        {
            "series": "dailyBiasState",
            "description": "Neutral, continuation bias, reversal watch, reversal confirmed, or exhausted/degraded state for the current session.",
        },
        {
            "series": "wickExpectationState",
            "description": "Expansion-supporting versus rejection-dominant wick classification for the bias candle.",
        },
        {
            "series": "equilibriumRespectState",
            "description": "Whether lower-timeframe closes remain in the correct half of the range for continuation bias.",
        },
        {
            "series": "alignmentState",
            "description": "Higher-timeframe and intermediate-timeframe agreement state used to gate lower-timeframe execution context.",
        },
        {
            "series": "lowerTimeframeConfirmationState",
            "description": "First-pass lower-timeframe directional close or CISD proxy used for reversal confirmation.",
        },
        {
            "series": "phaseShiftWarningState",
            "description": "Guardrail flag that warns when repeated same-direction continuation candles imply likely phase transition risk.",
        },
        {
            "series": "biasTargetModel",
            "description": "Target expectation state that points toward expansion continuation, previous-day equilibrium, opposite side of range, or reversion toward the open.",
        },
        {
            "series": "continuationPoiTop",
            "description": "Top boundary of the correct-half continuation point-of-interest band.",
        },
        {
            "series": "continuationPoiBottom",
            "description": "Bottom boundary of the correct-half continuation point-of-interest band.",
        },
        {
            "series": "reversalAnchorPrice",
            "description": "Previous-day extreme used as the reversal anchor when price sweeps and rejects.",
        },
        {
            "series": "targetPrimaryPrice",
            "description": "First target guide, typically equilibrium on reversals or the prior-day objective on continuation.",
        },
        {
            "series": "targetSecondaryPrice",
            "description": "Second target guide, typically the opposite side of range on reversals or external-liquidity projection on continuation.",
        },
    ]

    state_models = [
        {
            "name": "dailyBiasStateMachine",
            "state_type": "finite_state_machine",
            "states": [
                "neutral",
                "continuation_bias",
                "reversal_watch",
                "reversal_confirmed",
                "exhausted_or_degraded",
            ],
            "transitions": [
                {
                    "from": "neutral",
                    "to": "continuation_bias",
                    "condition": "Price closes outside the active reference range in the directional mode and wick plus alignment filters do not block continuation.",
                },
                {
                    "from": "neutral",
                    "to": "reversal_watch",
                    "condition": "Price sweeps a prior range extreme and closes back inside or rejects from a prior-day extreme with reversal potential.",
                },
                {
                    "from": "reversal_watch",
                    "to": "reversal_confirmed",
                    "condition": "The lower timeframe confirms the reversal workflow according to the selected confirmation mode.",
                },
                {
                    "from": ["continuation_bias", "reversal_watch", "reversal_confirmed"],
                    "to": "exhausted_or_degraded",
                    "condition": "Equilibrium fails in the wrong direction, wick behavior shifts to strong rejection, or repeated continuation warns of phase exhaustion.",
                },
            ],
        }
    ]

    signal_pipeline = [
        {
            "step": 1,
            "name": "Reference Range Selection",
            "logic": "Select the previous-day wick range when available, otherwise fall back to the prior candle range, then compute the wick-to-wick equilibrium midpoint for that reference.",
            "rule_refs": [
                "bias.previous_candle_close_bias",
                "bias.daily_continuation_framework",
                "equilibrium.equilibrium_is_wick_to_wick_midpoint",
            ],
        },
        {
            "step": 2,
            "name": "Continuation versus Reversal Classification",
            "logic": "Classify continuation bias when price closes outside the reference range, and classify reversal watch when price sweeps the range and closes back inside or rejects from the previous-day extreme.",
            "rule_refs": [
                "bias.previous_candle_close_bias",
                "bias.daily_reversal_framework",
                "bias.daily_continuation_framework",
            ],
        },
        {
            "step": 3,
            "name": "Wick Expectation Filter",
            "logic": "Measure opposing wick dominance to decide whether the bias candle supports directional expansion or favors reduced targets and reversion expectations.",
            "rule_refs": [
                "bias.wick_size_bias_filter",
                "wick_logic.small_opposing_run_supports_expansion",
                "wick_logic.large_opposing_wick_favors_reversion",
            ],
        },
        {
            "step": 4,
            "name": "Equilibrium Hold or Failure",
            "logic": "Project the previous-day or active reference equilibrium into the session and keep continuation bias active only while closes remain on the correct side within the configured tolerance.",
            "rule_refs": [
                "equilibrium.previous_day_equilibrium_filters_continuation_day",
                "equilibrium.equilibrium_respect_sets_directional_half",
                "bias.daily_continuation_framework",
            ],
        },
        {
            "step": 5,
            "name": "Top-Down Alignment Gate",
            "logic": "Use higher-timeframe direction and optional intermediate-timeframe structure agreement to filter lower-timeframe execution and downgrade unresolved setups.",
            "rule_refs": [
                "bias.bias_precedes_execution",
                "top_down_alignment.higher_timeframe_sets_direction",
                "top_down_alignment.intermediate_timeframe_confirms_structure",
            ],
        },
        {
            "step": 6,
            "name": "Lower-Timeframe Reversal Confirmation",
            "logic": "Promote reversal watch into reversal-confirmed only after a lower-timeframe directional close or CISD proxy appears at the prior-day extreme workflow.",
            "rule_refs": [
                "bias.daily_reversal_framework",
                "top_down_alignment.lower_timeframe_refines_entry_only_after_alignment",
            ],
        },
        {
            "step": 7,
            "name": "Target Model and Phase Shift Guard",
            "logic": "Choose expansion continuation targets, equilibrium return, opposite-side range targets, or open-price reversion according to the bias state, wick read, and continuation-exhaustion guard.",
            "rule_refs": [
                "bias.previous_candle_close_bias",
                "bias.daily_continuation_framework",
                "bias.wick_size_bias_filter",
            ],
        },
    ]

    visuals = [
        "Previous-day or prior-candle high, low, and equilibrium reference lines clipped to a recent lookback window",
        "A stable PDH, EQ, PDL, HTF POI, T1, and T2 levels ladder so the daily model reads like a chart lesson instead of raw code output",
        "Correct-half continuation point-of-interest band from equilibrium toward the directional objective",
        "Prior-day-extreme reversal anchor band showing the sweep and rejection zone",
        "Candle 2 and Candle 3 closure markers when lower-timeframe structure forms inside the active higher-timeframe POI",
        "Sweep markers, continuation activation markers, and lower-timeframe reversal confirmation markers",
        "Optional historical bias tinting, disabled by default to avoid overpowering the teaching geometry",
        "Phase-shift warning marker after repeated same-direction continuation candles",
        "On-chart dashboard summarizing bias, context, point of interest, confirmation, wick read, entry state, and targets",
    ]

    alerts = [
        {
            "name": "bias_continuation_set",
            "condition": "A continuation bias is established from the active reference range.",
        },
        {
            "name": "bias_reversal_watch",
            "condition": "A reversal-watch state is established after a sweep and rejection workflow.",
        },
        {
            "name": "bias_reversal_confirmed",
            "condition": "Lower-timeframe confirmation promotes reversal watch into reversal-confirmed.",
        },
        {
            "name": "bias_equilibrium_failed",
            "condition": "Continuation bias fails because lower-timeframe closes print beyond equilibrium in the wrong direction.",
        },
        {
            "name": "bias_phase_shift_warning",
            "condition": "Repeated same-direction continuation implies likely phase exhaustion or transition risk.",
        },
    ]

    provisional_proxies = [
        {
            "id": "wick_ratio_threshold_v1",
            "status": "provisional",
            "default_mode": "opposing_wick_to_full_range_ratio",
            "logic": "Treat small opposing wicks as expansion-supporting when the opposing wick remains below the configured ratio and the close remains near the directional extreme.",
        },
        {
            "id": "equilibrium_tolerance_v1",
            "status": "provisional",
            "default_mode": "percent_of_reference_range",
            "logic": "Allow minor probing around equilibrium until a close exceeds the configured percentage band on the wrong side of the midpoint.",
        },
        {
            "id": "lower_timeframe_confirmation_v1",
            "status": "provisional",
            "default_mode": "directional_close_or_cisd_proxy",
            "logic": "Confirm reversal bias with either a directional lower-timeframe close at the extreme or a first-pass CISD proxy when available.",
        },
    ]

    acceptance_checks = [
        "No continuation bias can appear without a close outside the active reference range.",
        "No reversal-confirmed state can appear without a prior sweep or prior-day-extreme interaction plus the selected lower-timeframe confirmation mode.",
        "Equilibrium must always be computed wick to wick rather than body to body.",
        "A large opposing wick must downgrade target expectations even when bias remains directionally intact.",
        "Continuation bias must fail once wrong-side equilibrium closes exceed the configured tolerance.",
        "The script must stay bar-close confirmed and avoid unbounded multi-timeframe requests.",
        "The chart must expose continuation point-of-interest geometry, prior-day reversal anchor geometry, and first-versus-second target path guidance for the active state.",
        "Reference levels must make PDH, EQ, PDL, HTF POI, T1, and T2 readable through an on-chart levels panel instead of depending on clipped right-edge labels or legend text alone.",
        "The chart must explicitly surface Candle 2 and Candle 3 closure progression inside the active higher-timeframe POI before calling the setup entry-ready.",
    ]

    open_implementation_questions = [
        {
            "question": "What numeric threshold best separates small and large opposing wicks for the daily bias framework across the main timeframe pairs?",
            "affected_component": "wick_ratio_threshold",
            "topic_refs": ["bias", "wick_logic"],
        },
        {
            "question": "How much tolerance around equilibrium should count as valid respect versus a true close-through failure?",
            "affected_component": "equilibrium_tolerance",
            "topic_refs": ["bias", "equilibrium"],
        },
        {
            "question": "What is the strictest first-pass lower-timeframe confirmation proxy that remains useful across the main execution timeframes?",
            "affected_component": "lower_timeframe_confirmation",
            "topic_refs": ["bias", "top_down_alignment"],
        },
    ]

    return {
        **base_spec,
        "spec_version": 2,
        "translation_stage": "draft",
        "artifact_path": str(artifact_path.relative_to(ROOT)),
        "implementation_summary": "Teacher-style Pine overlay for the TTrades daily bias framework using prior-range classification, clipped reference geometry, an active HTF-POI band, a stable on-chart PDH/EQ/PDL plus HTF-POI and target levels ladder, recent-window Candle 2 and Candle 3 closure markers, wick-based expectation filters, and lower-timeframe reversal confirmation markers.",
        "implementation_scope": implementation_scope,
        "pine_program_outline": {
            "script_kind": "indicator",
            "overlay": True,
            "sections": pine_sections,
            "anti_repaint_baseline": "bar_close_confirmation",
        },
        "scope_topics": scope_topics,
        "topic_rule_trace": build_rule_trace(rulebooks),
        "topic_input_catalog": collect_unique_inputs(rulebooks),
        "input_groups": input_groups,
        "derived_series": derived_series,
        "state_models": state_models,
        "signal_pipeline": signal_pipeline,
        "visuals": visuals,
        "alerts": alerts,
        "provisional_proxies": provisional_proxies,
        "acceptance_checks": acceptance_checks,
        "open_implementation_questions": open_implementation_questions,
        "future_extensions": [
            "Session-specific execution mappings once the preferred timeframe pair per session is formalized more tightly.",
            "A stricter CISD implementation once the lower-timeframe confirmation proxy is stabilized across the bias and reversal topics.",
            "A more explicit exhaustion model after the continuation phase-shift guard is grounded in more chart examples.",
        ],
    }


def build_fractal_closure_model_draft(base_spec: dict) -> dict:
    scope_topics = collect_scope_topics(base_spec)
    rulebooks = {topic_slug: load_rulebook(topic_slug) for topic_slug in scope_topics}
    artifact_path = OUTPUT_DIR / f"{base_spec['trade_model']['slug']}.json"

    implementation_scope = dict(base_spec.get("implementation_scope", {}))
    implementation_scope.update(
        {
            "translation_stage": "draft",
            "build_target": "fractal_sequence_overlay_indicator",
            "max_request_calls_budget": 5,
            "candidate_preservation_rule": "materializer_refreshes_candidate_fields_without_downgrading_draft_status",
            "timeframe_stack": {
                "higher": "daily_or_4h_context_frame",
                "intermediate": "1h_or_15m_structure_frame",
                "lower": "15m_or_5m_refinement_frame",
            },
        }
    )

    pine_sections = [
        "version",
        "indicator_declaration",
        "imports",
        "constants",
        "inputs",
        "functions",
        "calculations",
        "visuals",
        "alerts",
    ]

    input_groups = [
        {
            "group": "Context and Point of Interest",
            "inputs": [
                {
                    "key": "pointOfInterestMode",
                    "type": "enum",
                    "default": "swing_then_fvg_then_opposing_candle",
                    "options": [
                        "swing_then_fvg_then_opposing_candle",
                        "swing_only",
                        "fvg_then_opposing_candle",
                    ],
                    "description": "Provisional ranking order for valid fractal points of interest.",
                },
                {
                    "key": "requireHigherTimeframeBias",
                    "type": "bool",
                    "default": True,
                    "description": "Require the mapped point of interest and closure sequence to agree with the higher-timeframe directional idea.",
                },
                {
                    "key": "alignmentMode",
                    "type": "enum",
                    "default": "higher_plus_intermediate",
                    "options": ["higher_only", "higher_plus_intermediate"],
                    "description": "Choose whether the fractal sequence needs intermediate-timeframe structure agreement in addition to higher-timeframe bias.",
                },
            ],
        },
        {
            "group": "Closure Detection",
            "inputs": [
                {
                    "key": "candleTwoMode",
                    "type": "enum",
                    "default": "sweep_then_close_back_inside",
                    "options": ["sweep_then_close_back_inside"],
                    "description": "A Candle 2 closure requires a sweep of the prior candle and a close back inside its range.",
                },
                {
                    "key": "preferCandleTwoWhenValid",
                    "type": "bool",
                    "default": True,
                    "description": "If Candle 2 already qualifies as the valid reversal closure, stop the delayed Candle 3 path.",
                },
                {
                    "key": "candleThreeEngulfThresholdRatio",
                    "type": "float",
                    "default": 0.5,
                    "description": "Provisional body-engulf threshold used to decide when Candle 3 truly closes through Candle 2 in the new direction.",
                },
            ],
        },
        {
            "group": "Midpoint and Equilibrium Refinement",
            "inputs": [
                {
                    "key": "requireCandleTwoMidpointRespect",
                    "type": "bool",
                    "default": True,
                    "description": "Require Candle 3 to respect the Candle 2 wick midpoint when Candle 2 prints a large rejection wick.",
                },
                {
                    "key": "candleTwoMidpointTolerancePercent",
                    "type": "float",
                    "default": 0.05,
                    "description": "Provisional tolerance band for saying Candle 3 respected or disrespected the Candle 2 wick midpoint.",
                },
                {
                    "key": "requireCandleThreeHalfRetest",
                    "type": "bool",
                    "default": True,
                    "description": "Require Candle 4 to retest and respect the correct half of Candle 3 for the refined continuation path.",
                },
                {
                    "key": "candleThreeHalfTolerancePercent",
                    "type": "float",
                    "default": 0.05,
                    "description": "Provisional tolerance band used when deciding whether Candle 4 respected the intended half of Candle 3.",
                },
            ],
        },
        {
            "group": "Lower-Timeframe Refinement",
            "inputs": [
                {
                    "key": "requireLowerTimeframeDisplacement",
                    "type": "bool",
                    "default": True,
                    "description": "Require lower-timeframe displacement after the qualifying closure before promoting the sequence into entry-ready state.",
                },
                {
                    "key": "lowerTimeframeDisplacementMode",
                    "type": "enum",
                    "default": "directional_displacement_proxy",
                    "options": [
                        "directional_displacement_proxy",
                        "protected_swing_proxy",
                    ],
                    "description": "First-pass lower-timeframe refinement mode for the fractal sequence.",
                },
                {
                    "key": "executionTimeframe",
                    "type": "timeframe",
                    "default": "15",
                    "description": "Execution timeframe used for the lower-timeframe displacement proxy.",
                },
            ],
        },
    ]

    derived_series = [
        {
            "series": "pointOfInterestState",
            "description": "Mapped point-of-interest state ranked from swing, fair value gap, or fallback opposing candle.",
        },
        {
            "series": "higherTimeframeBiasState",
            "description": "Higher-timeframe directional state used to filter the fractal sequence.",
        },
        {
            "series": "candleTwoClosureState",
            "description": "Bullish or bearish Candle 2 reversal-closure detection state.",
        },
        {
            "series": "candleTwoMidpointState",
            "description": "Respect or failure state for the Candle 2 wick midpoint when large-wick filtering applies.",
        },
        {
            "series": "candleThreeClosureState",
            "description": "Delayed Candle 3 closure state when Candle 2 did not qualify.",
        },
        {
            "series": "candleThreeEquilibriumState",
            "description": "Correct-half respect versus failure state for Candle 3 equilibrium during Candle 4 refinement.",
        },
        {
            "series": "validatedSwingState",
            "description": "Whether the active swing is still descriptive only, validated, refined, entry-ready, or invalidated.",
        },
        {
            "series": "lowerTimeframeDisplacementState",
            "description": "Directional lower-timeframe displacement or protected-swing refinement state after the qualifying closure.",
        },
        {
            "series": "candleFourExpectationState",
            "description": "Expected Candle 4 continuation and expansion state after Candle 2 or Candle 3 confirmation.",
        },
    ]

    state_models = [
        {
            "name": "fractalClosureStateMachine",
            "state_type": "finite_state_machine",
            "states": [
                "idle",
                "poi_ready",
                "candle2_confirmed",
                "candle3_confirmed",
                "refinement_ready",
                "entry_ready",
                "invalidated",
            ],
            "transitions": [
                {
                    "from": "idle",
                    "to": "poi_ready",
                    "condition": "A valid point of interest is mapped and higher-timeframe context does not reject the setup.",
                },
                {
                    "from": "poi_ready",
                    "to": "candle2_confirmed",
                    "condition": "A valid Candle 2 reversal closure appears at the point of interest.",
                },
                {
                    "from": "poi_ready",
                    "to": "candle3_confirmed",
                    "condition": "Candle 2 does not qualify and Candle 3 closes through the Candle 2 body in the new direction.",
                },
                {
                    "from": ["candle2_confirmed", "candle3_confirmed"],
                    "to": "refinement_ready",
                    "condition": "The enabled midpoint or equilibrium refinement checks hold after the qualifying closure.",
                },
                {
                    "from": "refinement_ready",
                    "to": "entry_ready",
                    "condition": "Lower-timeframe displacement confirms the refined path when that mode is enabled.",
                },
                {
                    "from": [
                        "poi_ready",
                        "candle2_confirmed",
                        "candle3_confirmed",
                        "refinement_ready",
                        "entry_ready",
                    ],
                    "to": "invalidated",
                    "condition": "The closure path fails, the midpoint or half-respect filter breaks, or the lower-timeframe refinement never develops in the intended direction.",
                },
            ],
        }
    ]

    signal_pipeline = [
        {
            "step": 1,
            "name": "Context and Point-of-Interest Gate",
            "logic": "Map the higher-timeframe point of interest first, then require higher-timeframe bias and optional intermediate-timeframe structure to support the fractal closure path.",
            "rule_refs": [
                "candle_2_closure.candle_two_requires_point_of_interest",
                "candle_3_closure.candle_three_requires_context_and_poi",
                "bias.bias_precedes_execution",
                "top_down_alignment.higher_timeframe_sets_direction",
            ],
        },
        {
            "step": 2,
            "name": "Candle 2 Reversal Closure Detection",
            "logic": "Detect the Candle 2 sweep and close-back-inside event first and prefer that path whenever it already produces the valid reversal closure.",
            "rule_refs": [
                "candle_2_closure.candle_two_reversal_closure_definition",
                "candle_2_closure.candle_two_starts_candle_three_sequence",
            ],
        },
        {
            "step": 3,
            "name": "Candle 3 Delayed Closure Fallback",
            "logic": "If Candle 2 does not qualify, require Candle 3 to close through the Candle 2 body in the new direction before validating the delayed closure path.",
            "rule_refs": [
                "candle_3_closure.candle_three_closure_definition",
                "candle_3_closure.valid_swing_requires_poi_and_closure",
            ],
        },
        {
            "step": 4,
            "name": "Midpoint and Equilibrium Refinement",
            "logic": "Apply Candle 2 wick-midpoint respect when large-wick rejection exists, then apply Candle 3 equilibrium-half respect for the Candle 4 refinement path.",
            "rule_refs": [
                "candle_2_closure.candle_two_eq_and_wick_filter",
                "candle_3_closure.candle_three_equilibrium_refinement",
                "equilibrium.equilibrium_is_wick_to_wick_midpoint",
                "wick_logic.wick_midpoint_respect_vs_disrespect",
            ],
        },
        {
            "step": 5,
            "name": "Lower-Timeframe Displacement Gate",
            "logic": "Require lower-timeframe displacement after the qualifying closure before treating the swing as refined and entry-ready.",
            "rule_refs": [
                "candle_3_closure.valid_swing_requires_poi_and_closure",
                "top_down_alignment.lower_timeframe_refines_entry_only_after_alignment",
            ],
        },
        {
            "step": 6,
            "name": "Candle 4 Expectation and Failure Management",
            "logic": "Once refinement holds, project Candle 4 continuation and expansion in the new direction and invalidate the model when the closure or refinement path breaks first.",
            "rule_refs": [
                "candle_2_closure.candle_two_starts_candle_three_sequence",
                "candle_3_closure.candle_three_equilibrium_refinement",
            ],
        },
    ]

    visuals = [
        "Point-of-interest zone or anchor marker for the active setup",
        "Candle 2 range box with sweep and close-back-inside labels",
        "Candle 2 wick-midpoint line when the large-wick filter is active",
        "Candle 3 body-engulf marker and equilibrium-half refinement box",
        "State labels showing whether the live path is Candle 2, Candle 3, refinement-ready, or invalidated",
        "Lower-timeframe displacement marker after the qualifying closure",
        "Candle 4 expectation arrow or target band in the confirmed direction",
    ]

    alerts = [
        {
            "name": "fractal_candle2_confirmed",
            "condition": "A valid Candle 2 closure is detected at the mapped point of interest.",
        },
        {
            "name": "fractal_candle3_confirmed",
            "condition": "A valid Candle 3 closure confirms the delayed fractal path.",
        },
        {
            "name": "fractal_refinement_ready",
            "condition": "Midpoint or equilibrium refinement checks pass after the qualifying closure.",
        },
        {
            "name": "fractal_entry_ready",
            "condition": "Lower-timeframe displacement confirms the refined fractal path.",
        },
        {
            "name": "fractal_invalidated",
            "condition": "The fractal closure path fails before or after refinement.",
        },
    ]

    provisional_proxies = [
        {
            "id": "poi_ranking_v1",
            "status": "provisional",
            "default_mode": "swing_then_fvg_then_opposing_candle",
            "logic": "Rank point-of-interest anchors by preferring swing highs or lows first, then fair value gap proxies, then fallback opposing candles only when no cleaner anchor exists.",
        },
        {
            "id": "candle_three_body_engulf_v1",
            "status": "provisional",
            "default_mode": "close_through_candle_two_body_ratio",
            "logic": "Treat Candle 3 as a valid delayed closure only when its close exceeds the Candle 2 body by the configured engulf threshold in the new direction.",
        },
        {
            "id": "midpoint_and_half_tolerance_v1",
            "status": "provisional",
            "default_mode": "percent_of_reference_range",
            "logic": "Use configurable tolerance bands for Candle 2 midpoint respect and Candle 3 correct-half respect until the narrative filters are grounded numerically.",
        },
        {
            "id": "lower_timeframe_displacement_v1",
            "status": "provisional",
            "default_mode": "directional_displacement_proxy",
            "logic": "Require a first-pass lower-timeframe impulse or protected-swing proxy after the qualifying closure before promoting the sequence into entry-ready state.",
        },
    ]

    acceptance_checks = [
        "No valid fractal swing can exist without both a mapped point of interest and a qualifying Candle 2 or Candle 3 closure.",
        "If Candle 2 already qualifies as the valid closure, the model must stop the delayed Candle 3 path instead of double-counting both.",
        "No Candle 3 closure can qualify unless Candle 2 first failed to produce the valid reversal closure.",
        "Midpoint and equilibrium refinement gates must be explicit and configurable whenever the draft claims to use them.",
        "Lower-timeframe refinement must stay bar-close confirmed and remain gated behind the higher-timeframe and point-of-interest path.",
        "The script must keep multi-timeframe requests finite and below the configured request budget.",
    ]

    open_implementation_questions = [
        {
            "question": "What body-overlap threshold is the best first numeric proxy for saying Candle 3 truly engulfed Candle 2 when Candle 2 is small or doji-like?",
            "affected_component": "candle_three_body_engulf",
            "topic_refs": ["candle_3_closure"],
        },
        {
            "question": "What is the first useful numeric tolerance for saying Candle 3 respected the Candle 2 midpoint or Candle 4 respected the correct half of Candle 3?",
            "affected_component": "midpoint_and_half_tolerance",
            "topic_refs": ["candle_2_closure", "candle_3_closure", "equilibrium"],
        },
        {
            "question": "How should the fallback opposing-candle point of interest be ranked against clearer swing or fair-value-gap anchors?",
            "affected_component": "poi_ranking",
            "topic_refs": ["candle_2_closure", "candle_3_closure"],
        },
        {
            "question": "What is the minimum lower-timeframe displacement strength needed before the refined fractal path is truly entry-ready?",
            "affected_component": "lower_timeframe_displacement",
            "topic_refs": ["candle_3_closure", "top_down_alignment"],
        },
    ]

    return {
        **base_spec,
        "spec_version": 2,
        "translation_stage": "draft",
        "artifact_path": str(artifact_path.relative_to(ROOT)),
        "implementation_summary": "First-pass Pine overlay draft for the TTrades fractal closure model using point-of-interest gating, Candle 2 or Candle 3 closure detection, midpoint and equilibrium refinement, and provisional lower-timeframe displacement confirmation.",
        "implementation_scope": implementation_scope,
        "pine_program_outline": {
            "script_kind": "indicator",
            "overlay": True,
            "sections": pine_sections,
            "anti_repaint_baseline": "bar_close_confirmation",
        },
        "scope_topics": scope_topics,
        "topic_rule_trace": build_rule_trace(rulebooks),
        "topic_input_catalog": collect_unique_inputs(rulebooks),
        "input_groups": input_groups,
        "derived_series": derived_series,
        "state_models": state_models,
        "signal_pipeline": signal_pipeline,
        "visuals": visuals,
        "alerts": alerts,
        "provisional_proxies": provisional_proxies,
        "acceptance_checks": acceptance_checks,
        "open_implementation_questions": open_implementation_questions,
        "future_extensions": [
            "A stricter point-of-interest ranking rule once the fallback opposing-candle path is more explicitly formalized.",
            "A more precise body-engulf calculation once small-body and doji edge cases are grounded with more examples.",
            "A richer Candle 4 expansion and target model once the lower-timeframe displacement proxy is strong enough to support execution logic directly.",
        ],
    }


def build_daily_profile_models_draft(base_spec: dict) -> dict:
    scope_topics = collect_scope_topics(base_spec)
    rulebooks = {topic_slug: load_rulebook(topic_slug) for topic_slug in scope_topics}
    artifact_path = OUTPUT_DIR / f"{base_spec['trade_model']['slug']}.json"

    implementation_scope = dict(base_spec.get("implementation_scope", {}))
    implementation_scope.update(
        {
            "translation_stage": "draft",
            "build_target": "session_profile_overlay_indicator",
            "max_request_calls_budget": 6,
            "candidate_preservation_rule": "materializer_refreshes_candidate_fields_without_downgrading_draft_status",
            "timeframe_stack": {
                "higher": "daily_or_4h_context_frame",
                "intermediate": "15m_structure_frame",
                "lower": "5m_or_1m_confirmation_frame",
            },
        }
    )

    pine_sections = [
        "version",
        "indicator_declaration",
        "imports",
        "constants",
        "inputs",
        "functions",
        "calculations",
        "visuals",
        "alerts",
    ]

    input_groups = [
        {
            "group": "Sessions",
            "inputs": [
                {
                    "key": "asiaSession",
                    "type": "session",
                    "default": "1900-0000",
                    "description": "Session window used to define the Asia range for seek-and-destroy and session-profile context.",
                },
                {
                    "key": "londonSession",
                    "type": "session",
                    "default": "0200-0500",
                    "description": "Session window used to measure London reversal and pre-New-York structure conditions.",
                },
                {
                    "key": "newYorkSession",
                    "type": "session",
                    "default": "0830-1200",
                    "description": "Session window used to detect New York continuation, manipulation, or reversal delivery.",
                },
                {
                    "key": "newYorkOpenMarkers",
                    "type": "string_list",
                    "default": ["08:30", "09:30"],
                    "description": "Key New York timestamps that matter most for manipulation and reversal profiles.",
                },
            ],
        },
        {
            "group": "Profile Detection",
            "inputs": [
                {
                    "key": "enabledProfiles",
                    "type": "string_list",
                    "default": [
                        "london_reversal_new_york_continuation",
                        "new_york_manipulation",
                        "new_york_reversal",
                        "seek_and_destroy",
                    ],
                    "description": "Profiles that remain active in the overlay classification engine.",
                },
                {
                    "key": "requireHigherTimeframeAnchorForNyReversal",
                    "type": "bool",
                    "default": True,
                    "description": "Require an explicit higher-timeframe PD array or key level before allowing the New York reversal profile.",
                },
                {
                    "key": "allowLondonContinuationProfile",
                    "type": "bool",
                    "default": True,
                    "description": "Allow the London reversal -> New York continuation profile when London forms the wick and New York is still needed for body delivery.",
                },
            ],
        },
        {
            "group": "Confirmation Proxies",
            "inputs": [
                {
                    "key": "cisdMode",
                    "type": "enum",
                    "default": "directional_close_through_opposing_series",
                    "options": [
                        "directional_close_through_opposing_series",
                        "directional_close_plus_displacement",
                    ],
                    "description": "First-pass CISD proxy used across the session profiles.",
                },
                {
                    "key": "sweepMode",
                    "type": "enum",
                    "default": "direct_range_sweep_only",
                    "options": [
                        "direct_range_sweep_only",
                        "direct_or_smt_substitute",
                    ],
                    "description": "Choose whether a direct range sweep is mandatory or an SMT-style substitute may qualify for manipulation logic.",
                },
                {
                    "key": "requireProtectedSwingAfterShift",
                    "type": "bool",
                    "default": True,
                    "description": "Require a protected swing after the session shift before promoting the profile to confirmed status.",
                },
                {
                    "key": "executionTimeframe",
                    "type": "timeframe",
                    "default": "15",
                    "description": "Primary intraday timeframe used for session-structure confirmation.",
                },
            ],
        },
        {
            "group": "Range and Rotation Filters",
            "inputs": [
                {
                    "key": "londonRangeCompletionThreshold",
                    "type": "float",
                    "default": 0.7,
                    "description": "Provisional threshold for deciding whether London already completed too much of the day's expected expansion for New York continuation to remain valid.",
                },
                {
                    "key": "seekAndDestroyRotationCount",
                    "type": "int",
                    "default": 2,
                    "description": "Number of two-sided range rotations required before the day is treated as seek-and-destroy instead of directional delivery.",
                },
                {
                    "key": "equilibriumTolerancePercentOfRange",
                    "type": "float",
                    "default": 0.05,
                    "description": "Tolerance used when treating equilibrium or daily open as a reversion magnet during rotational conditions.",
                },
                {
                    "key": "requireOutsideRangeHold",
                    "type": "bool",
                    "default": True,
                    "description": "Require a true outside-range hold before abandoning the seek-and-destroy or consolidative classification.",
                },
            ],
        },
    ]

    derived_series = [
        {
            "series": "dailyOpen",
            "description": "Daily open used as a core reference for profile framing and rotational reversion expectations.",
        },
        {
            "series": "asiaRangeState",
            "description": "Asia high, Asia low, and Asia equilibrium used for seek-and-destroy and London context.",
        },
        {
            "series": "londonRangeState",
            "description": "London session high, low, equilibrium, and sweep behavior used to classify early-session intent.",
        },
        {
            "series": "newYorkRangeInteractionState",
            "description": "New York sweep, manipulation, reversal, or continuation interaction state around session ranges and higher-timeframe anchors.",
        },
        {
            "series": "higherTimeframeAnchorState",
            "description": "Higher-timeframe PD array or missed level state required for the New York reversal profile.",
        },
        {
            "series": "sessionCisdState",
            "description": "First-pass session CISD proxy after London or New York sweeps.",
        },
        {
            "series": "sessionProtectedSwingState",
            "description": "Post-shift protected swing state used to validate continuation or reversal session profiles.",
        },
        {
            "series": "rotationState",
            "description": "Range rotation count and equilibrium reversion behavior used to classify seek-and-destroy conditions.",
        },
        {
            "series": "dailyProfileState",
            "description": "Profile classification state: London reversal/New York continuation, New York manipulation, New York reversal, seek-and-destroy, or unresolved.",
        },
        {
            "series": "profileTargetModel",
            "description": "Target expectation state pointing toward continuation delivery, previous-day liquidity, failed swing targets, or rotational equilibrium.",
        },
    ]

    state_models = [
        {
            "name": "dailyProfileStateMachine",
            "state_type": "finite_state_machine",
            "states": [
                "unresolved",
                "london_reversal_watch",
                "london_reversal_new_york_continuation_confirmed",
                "new_york_manipulation_watch",
                "new_york_manipulation_confirmed",
                "new_york_reversal_watch",
                "new_york_reversal_confirmed",
                "seek_and_destroy_filter",
                "resolved_breakout_override",
            ],
            "transitions": [
                {
                    "from": "unresolved",
                    "to": "london_reversal_watch",
                    "condition": "London forms the daily wick away from the intended close and begins the shift needed for a New York continuation profile.",
                },
                {
                    "from": "london_reversal_watch",
                    "to": "london_reversal_new_york_continuation_confirmed",
                    "condition": "London confirms the shift and New York continues in the same direction without London already completing too much of the day's range.",
                },
                {
                    "from": "unresolved",
                    "to": "new_york_manipulation_watch",
                    "condition": "London stays mainly consolidative and New York approaches the live day's range for a sweep setup.",
                },
                {
                    "from": "new_york_manipulation_watch",
                    "to": "new_york_manipulation_confirmed",
                    "condition": "New York sweeps the day's range and confirms the opposing delivery path through the selected shift proxy.",
                },
                {
                    "from": "unresolved",
                    "to": "new_york_reversal_watch",
                    "condition": "London fails to reach a higher-timeframe anchor that New York is still positioned to complete.",
                },
                {
                    "from": "new_york_reversal_watch",
                    "to": "new_york_reversal_confirmed",
                    "condition": "New York completes the missed run into the higher-timeframe anchor and confirms the reversal shift.",
                },
                {
                    "from": "unresolved",
                    "to": "seek_and_destroy_filter",
                    "condition": "London and New York keep rotating across the same session range without directional hold.",
                },
                {
                    "from": "seek_and_destroy_filter",
                    "to": "resolved_breakout_override",
                    "condition": "Price stops rotating and holds outside the active range with structural confirmation.",
                },
            ],
        }
    ]

    signal_pipeline = [
        {
            "step": 1,
            "name": "Session Range Build",
            "logic": "Track daily open, Asia range, London range, and the earliest New York interaction points so the day can be classified by session sequence instead of isolated candles.",
            "rule_refs": [
                "daily_profiles.london_reversal_new_york_continuation_profile",
                "daily_profiles.new_york_manipulation_profile",
                "daily_profiles.seek_and_destroy_profile_filter",
            ],
        },
        {
            "step": 2,
            "name": "London Reversal and Completion Filter",
            "logic": "Detect when London forms the daily wick and shifts direction, then reject the continuation path if London already appears to have completed most of the expected daily expansion.",
            "rule_refs": [
                "daily_profiles.london_reversal_new_york_continuation_profile",
                "wick_logic.higher_timeframe_wick_guides_lower_timeframe_expectation",
            ],
        },
        {
            "step": 3,
            "name": "New York Manipulation and Reversal Branch",
            "logic": "Split the New York path into manipulation versus reversal depending on whether the session is sweeping the current day's range or finishing a missed higher-timeframe run first.",
            "rule_refs": [
                "daily_profiles.new_york_manipulation_profile",
                "daily_profiles.new_york_reversal_profile",
                "top_down_alignment.higher_timeframe_sets_direction",
            ],
        },
        {
            "step": 4,
            "name": "Session Shift Confirmation",
            "logic": "Require a first-pass CISD or directional close-through-opposing-series event, then require a protected swing when that filter is enabled before treating the profile as confirmed.",
            "rule_refs": [
                "daily_profiles.london_reversal_new_york_continuation_profile",
                "daily_profiles.new_york_manipulation_profile",
                "daily_profiles.new_york_reversal_profile",
                "protected_swings.protected_swing_confirmation_gate",
            ],
        },
        {
            "step": 5,
            "name": "Seek-and-Destroy and Rotation Filter",
            "logic": "When the day keeps sweeping both sides of the range and returning toward equilibrium or the daily open, demote directional expectations into a seek-and-destroy filter until a true outside hold appears.",
            "rule_refs": [
                "daily_profiles.seek_and_destroy_profile_filter",
                "consolidation.equilibrium_and_whipsaw_filters",
                "equilibrium.equilibrium_respect_sets_directional_half",
            ],
        },
        {
            "step": 6,
            "name": "Profile Targets and Failure Management",
            "logic": "Use the confirmed profile to choose continuation delivery, previous-day liquidity, failure swing targets, or rotational mean-reversion expectations, and invalidate the profile when the corresponding session structure breaks.",
            "rule_refs": [
                "daily_profiles.london_reversal_new_york_continuation_profile",
                "daily_profiles.new_york_manipulation_profile",
                "daily_profiles.new_york_reversal_profile",
                "daily_profiles.seek_and_destroy_profile_filter",
            ],
        },
    ]

    visuals = [
        "Daily open plus Asia, London, and New York session range bands",
        "Profile state label showing unresolved, confirmed session profile, seek-and-destroy, or breakout override",
        "London shift marker and New York sweep marker for the active path",
        "Higher-timeframe anchor marker for the New York reversal profile",
        "Session CISD and protected-swing markers after the qualifying shift",
        "Equilibrium and daily-open reversion bands during rotational conditions",
        "Target markers for previous-day liquidity, failed swings, or continuation delivery",
    ]

    alerts = [
        {
            "name": "daily_profile_london_reversal_watch",
            "condition": "London forms the wick and session shift for a possible New York continuation profile.",
        },
        {
            "name": "daily_profile_ny_manipulation_confirmed",
            "condition": "New York manipulation confirms after a current-day range sweep and post-sweep shift.",
        },
        {
            "name": "daily_profile_ny_reversal_confirmed",
            "condition": "New York reversal confirms after completing a missed higher-timeframe run and shifting away from it.",
        },
        {
            "name": "daily_profile_seek_and_destroy",
            "condition": "The session sequence degrades into seek-and-destroy rotation rather than directional delivery.",
        },
        {
            "name": "daily_profile_breakout_override",
            "condition": "The day breaks out of rotational behavior and holds outside the active range with structural confirmation.",
        },
    ]

    provisional_proxies = [
        {
            "id": "session_cisd_proxy_v1",
            "status": "provisional",
            "default_mode": "directional_close_through_opposing_series",
            "logic": "Use a directional close through the opposing candle series as the first session-shift proxy, optionally strengthened with displacement.",
        },
        {
            "id": "london_range_completion_proxy_v1",
            "status": "provisional",
            "default_mode": "percent_of_expected_daily_range",
            "logic": "Treat London as having completed too much of the day once it consumes more than the configured portion of the expected daily expansion window.",
        },
        {
            "id": "profile_overlap_ranking_v1",
            "status": "provisional",
            "default_mode": "higher_timeframe_anchor_then_current_day_sweep_then_rotation",
            "logic": "Break profile conflicts by preferring the higher-timeframe-anchor path first, then the direct current-day sweep path, then the rotational seek-and-destroy filter.",
        },
        {
            "id": "seek_and_destroy_rotation_proxy_v1",
            "status": "provisional",
            "default_mode": "two_sided_sweep_plus_equilibrium_reversion",
            "logic": "Classify the day as seek-and-destroy once the range sweeps both sides and returns toward equilibrium or the daily open at least the configured number of times.",
        },
    ]

    acceptance_checks = [
        "No daily profile can be confirmed without the required session context being present for that profile.",
        "The New York reversal profile cannot appear unless London first failed to reach the relevant higher-timeframe anchor.",
        "The New York manipulation profile cannot confirm without a current-day range sweep plus the selected post-sweep shift proxy.",
        "Seek-and-destroy must block directional expansion-style expectations until price truly holds outside the range.",
        "The script must keep the session logic bar-close confirmed and avoid unbounded multi-timeframe requests.",
        "Profile overlap handling must remain explicit and configurable rather than silently favoring the last branch evaluated.",
    ]

    open_implementation_questions = [
        {
            "question": "What is the cleanest first-pass rule for deciding whether London already completed too much of the day's expansion for New York continuation to remain valid?",
            "affected_component": "london_range_completion",
            "topic_refs": ["daily_profiles"],
        },
        {
            "question": "How should overlapping session features be ranked when a day partially resembles both New York manipulation and New York reversal?",
            "affected_component": "profile_overlap_ranking",
            "topic_refs": ["daily_profiles"],
        },
        {
            "question": "What is the strictest useful first-pass CISD proxy for session-profile confirmation without relying on discretionary chart reading?",
            "affected_component": "session_cisd_proxy",
            "topic_refs": ["daily_profiles", "top_down_alignment"],
        },
    ]

    return {
        **base_spec,
        "spec_version": 2,
        "translation_stage": "draft",
        "artifact_path": str(artifact_path.relative_to(ROOT)),
        "implementation_summary": "First-pass Pine overlay draft for the TTrades daily profile models using session-range sequencing, London and New York profile classification, rotational seek-and-destroy filtering, and provisional session-shift confirmation.",
        "implementation_scope": implementation_scope,
        "pine_program_outline": {
            "script_kind": "indicator",
            "overlay": True,
            "sections": pine_sections,
            "anti_repaint_baseline": "bar_close_confirmation",
        },
        "scope_topics": scope_topics,
        "topic_rule_trace": build_rule_trace(rulebooks),
        "topic_input_catalog": collect_unique_inputs(rulebooks),
        "input_groups": input_groups,
        "derived_series": derived_series,
        "state_models": state_models,
        "signal_pipeline": signal_pipeline,
        "visuals": visuals,
        "alerts": alerts,
        "provisional_proxies": provisional_proxies,
        "acceptance_checks": acceptance_checks,
        "open_implementation_questions": open_implementation_questions,
        "future_extensions": [
            "A stronger overlap-ranking rule once more session examples clarify borderline New York manipulation versus New York reversal days.",
            "A more explicit session-range completion model once the project formalizes expected daily-range completion rules.",
            "An execution-layer handoff once the session CISD proxy is strong enough to support direct intraday entries rather than profile classification only.",
        ],
    }


def build_reversal_sequence_draft(base_spec: dict) -> dict:
    scope_topics = collect_scope_topics(base_spec)
    rulebooks = {topic_slug: load_rulebook(topic_slug) for topic_slug in scope_topics}
    artifact_path = OUTPUT_DIR / f"{base_spec['trade_model']['slug']}.json"

    implementation_scope = dict(base_spec.get("implementation_scope", {}))
    implementation_scope.update(
        {
            "translation_stage": "draft",
            "build_target": "first_pass_overlay_indicator",
            "max_request_calls_budget": 6,
            "candidate_preservation_rule": "materializer_refreshes_candidate_fields_without_downgrading_draft_status",
            "timeframe_stack": {
                "higher": "daily_or_4h_anchor",
                "intermediate": "1h_or_15m_structure",
                "lower": "chart_execution_timeframe",
            },
        }
    )

    pine_sections = [
        "version",
        "indicator_declaration",
        "imports",
        "constants",
        "inputs",
        "functions",
        "calculations",
        "visuals",
        "alerts",
    ]

    input_groups = [
        {
            "group": "Sessions and Timeframes",
            "inputs": [
                {
                    "key": "killZoneMode",
                    "type": "enum",
                    "default": "both",
                    "options": ["off", "london", "new_york", "both"],
                    "description": "Restrict reversal detection to London, New York, or both session windows.",
                },
                {
                    "key": "anchorTimeframe",
                    "type": "timeframe",
                    "default": "D",
                    "description": "Primary higher timeframe used to pull previous-day range anchors and bias context.",
                },
                {
                    "key": "structureTimeframe",
                    "type": "timeframe",
                    "default": "60",
                    "description": "Intermediate timeframe used for reclaim and protected-swing confirmation.",
                },
            ],
        },
        {
            "group": "Liquidity Anchors",
            "inputs": [
                {
                    "key": "usePreviousDayLevels",
                    "type": "bool",
                    "default": True,
                    "description": "Track previous-day high and low as external reversal anchors.",
                },
                {
                    "key": "usePreviousWeekLevels",
                    "type": "bool",
                    "default": True,
                    "description": "Track previous-week high and low as slower external reversal anchors.",
                },
                {
                    "key": "useSessionLevels",
                    "type": "bool",
                    "default": True,
                    "description": "Track current-session highs and lows for intraday reversal anchors.",
                },
                {
                    "key": "swingLookbackBars",
                    "type": "int",
                    "default": 8,
                    "description": "Lookback used to mark local swing extremes when no higher anchor is present.",
                },
                {
                    "key": "anchorPriorityMode",
                    "type": "enum",
                    "default": "higher_timeframe_first",
                    "options": ["higher_timeframe_first", "nearest_price_first"],
                    "description": "Priority rule when previous-day, previous-week, session, and swing anchors overlap.",
                },
            ],
        },
        {
            "group": "Confirmation Proxies",
            "inputs": [
                {
                    "key": "reclaimMode",
                    "type": "enum",
                    "default": "close_back_through_swept_reference",
                    "options": [
                        "close_back_through_swept_reference",
                        "close_back_inside_source_range",
                    ],
                    "description": "First-pass reclaim proxy after a sweep.",
                },
                {
                    "key": "cisdMode",
                    "type": "enum",
                    "default": "body_break_impulse_cluster",
                    "options": [
                        "body_break_reference_candle",
                        "body_break_impulse_cluster",
                    ],
                    "description": "First-pass CISD proxy used after reclaim.",
                },
                {
                    "key": "requireWickMidpointRespect",
                    "type": "bool",
                    "default": True,
                    "description": "Require wick-midpoint respect before the reversal state can advance to entry-ready.",
                },
                {
                    "key": "requireProtectedSwingConfirmation",
                    "type": "bool",
                    "default": True,
                    "description": "Require a new protected swing before marking the sequence as structurally valid.",
                },
            ],
        },
        {
            "group": "Entry Families and Risk",
            "inputs": [
                {
                    "key": "enableFvgRetest",
                    "type": "bool",
                    "default": True,
                    "description": "Allow fair-value-gap retests as the main post-CISD entry family.",
                },
                {
                    "key": "enableCandleThreeEquilibrium",
                    "type": "bool",
                    "default": True,
                    "description": "Allow candle-three equilibrium as a delayed reversal-entry fallback.",
                },
                {
                    "key": "enableBreakerRetest",
                    "type": "bool",
                    "default": False,
                    "description": "Allow breaker-style retests as an optional later-stage entry family.",
                },
                {
                    "key": "invalidationMode",
                    "type": "enum",
                    "default": "protected_swing",
                    "options": ["protected_swing", "body_aggressive"],
                    "description": "Structural invalidation mode for the plotted stop reference.",
                },
                {
                    "key": "minimumRewardRisk",
                    "type": "float",
                    "default": 1.5,
                    "description": "Minimum reward-to-risk threshold required before an entry-ready setup is shown.",
                },
            ],
        },
    ]

    derived_series = [
        {
            "series": "higherTimeframeBias",
            "description": "Continuation versus reversal bias pulled from the higher timeframe and used as the first execution gate.",
        },
        {
            "series": "trackedLiquidityAnchors",
            "description": "Previous-day, previous-week, session, and local swing anchors stored as candidate reversal references.",
        },
        {
            "series": "anchorSweepDirection",
            "description": "Bullish or bearish sweep event when price trades beyond a tracked external reference.",
        },
        {
            "series": "wickMidpointState",
            "description": "Respected versus disrespected midpoint state for the higher-timeframe rejection wick.",
        },
        {
            "series": "reclaimState",
            "description": "First-pass reclaim or inversion flag after price closes back through the swept reference or inside the source range.",
        },
        {
            "series": "cisdState",
            "description": "First-pass CISD proxy after reclaim, used to confirm the reversal structure shift.",
        },
        {
            "series": "protectedSwingState",
            "description": "Anticipated versus confirmed opposite-direction protected swing used for structural confirmation and invalidation.",
        },
        {
            "series": "entryFamilyReady",
            "description": "Fair-value-gap, candle-three-equilibrium, or breaker-style entry family readiness after CISD.",
        },
        {
            "series": "targetContext",
            "description": "Previous-day equilibrium, nearest opposing liquidity, and external-liquidity extension targets.",
        },
    ]

    state_models = [
        {
            "name": "reversalSequenceState",
            "state_type": "finite_state_machine",
            "states": [
                "idle",
                "anchor_swept",
                "reclaimed",
                "cisd_confirmed",
                "entry_ready",
                "invalidated",
            ],
            "transitions": [
                {
                    "from": "idle",
                    "to": "anchor_swept",
                    "condition": "A tracked external liquidity anchor is swept during the active kill zone and higher-timeframe bias does not block the reversal hypothesis.",
                },
                {
                    "from": "anchor_swept",
                    "to": "reclaimed",
                    "condition": "Price closes back through the swept reference or back inside the source range according to the selected reclaim proxy.",
                },
                {
                    "from": "reclaimed",
                    "to": "cisd_confirmed",
                    "condition": "A first-pass CISD proxy confirms after reclaim while wick-midpoint logic is still supportive.",
                },
                {
                    "from": "cisd_confirmed",
                    "to": "entry_ready",
                    "condition": "A new protected swing confirms and at least one enabled entry family becomes valid with acceptable reward-to-risk.",
                },
                {
                    "from": [
                        "anchor_swept",
                        "reclaimed",
                        "cisd_confirmed",
                        "entry_ready",
                    ],
                    "to": "invalidated",
                    "condition": "Price fails the active invalidation level, loses directional follow-through, or degrades into range behavior before target progression.",
                },
            ],
        }
    ]

    signal_pipeline = [
        {
            "step": 1,
            "name": "Higher-Timeframe Bias Gate",
            "logic": "Compute higher-timeframe continuation or reversal bias first and reject lower-timeframe reversal setups that directly fight a clean higher-timeframe continuation state.",
            "rule_refs": [
                "bias.previous_candle_close_bias",
                "bias.daily_reversal_framework",
                "bias.bias_precedes_execution",
                "top_down_alignment.higher_timeframe_sets_direction",
            ],
        },
        {
            "step": 2,
            "name": "Anchor Selection and Sweep Detection",
            "logic": "Track previous-day, previous-week, session, and swing anchors, prioritize the higher-timeframe anchor on overlap, and mark a reversal candidate only after an external sweep.",
            "rule_refs": [
                "reversal.reversal_definition",
                "reversal.reversal_confirmation_stack",
            ],
        },
        {
            "step": 3,
            "name": "Wick and Reclaim Filter",
            "logic": "Require the rejection wick to remain valid by midpoint logic, then require a reclaim back through the swept reference or back inside the source range.",
            "rule_refs": [
                "wick_logic.wick_midpoint_respect_vs_disrespect",
                "reversal.reversal_confirmation_stack",
                "reversal.reversal_sequence_entry_model",
            ],
        },
        {
            "step": 4,
            "name": "CISD and Protected-Swing Confirmation",
            "logic": "After reclaim, require a first-pass CISD proxy and then a newly confirmed opposite-direction protected swing before advancing the sequence to structural validity.",
            "rule_refs": [
                "reversal.reversal_confirmation_stack",
                "reversal.reversal_sequence_entry_model",
                "protected_swings.protected_swing_definition",
                "protected_swings.protected_swing_confirmation_gate",
            ],
        },
        {
            "step": 5,
            "name": "Entry Family and Risk Filter",
            "logic": "Enable fair-value-gap, candle-three-equilibrium, or breaker-style entries only after structural confirmation, then screen them by the selected invalidation mode and minimum reward-to-risk.",
            "rule_refs": [
                "reversal.candle_three_reversal_fallback",
                "reversal.reversal_sequence_entry_model",
                "invalidation.protected_swing_is_default_invalidation",
                "invalidation.body_invalidation_is_conditional_risk_tightening",
                "invalidation.wait_for_new_protected_swing_if_rr_is_poor",
            ],
        },
        {
            "step": 6,
            "name": "Target and Failure Management",
            "logic": "Plot previous-day equilibrium or nearby opposing liquidity as the first target, extend to external liquidity when momentum stays intact, and invalidate the setup when structure degrades into range or opposite follow-through.",
            "rule_refs": [
                "reversal.reversal_definition",
                "invalidation.continuation_or_reversal_is_invalid_when_structure_turns_into_range_or_target_is_already_met",
            ],
        },
    ]

    visuals = [
        "Tracked external-liquidity lines for previous-day, previous-week, session, and swing anchors",
        "Anchor-sweep labels with bullish or bearish direction",
        "Reclaim and CISD state markers on the execution timeframe",
        "Protected-swing line and invalidation line with aggressive or structural mode coloring",
        "Entry-zone box for enabled fair-value-gap, candle-three-equilibrium, or breaker retest families",
        "Target bands for previous-day equilibrium and next opposing liquidity",
    ]

    alerts = [
        {
            "name": "reversal_anchor_swept",
            "condition": "A tracked external anchor is swept during an enabled kill zone.",
        },
        {
            "name": "reversal_reclaimed",
            "condition": "Price reclaims the swept reference according to the selected reclaim proxy.",
        },
        {
            "name": "reversal_cisd_confirmed",
            "condition": "The first-pass CISD proxy confirms after reclaim.",
        },
        {
            "name": "reversal_entry_ready",
            "condition": "Protected swing, entry family, and reward-to-risk filters all pass.",
        },
        {
            "name": "reversal_invalidated",
            "condition": "The active reversal sequence fails its selected invalidation or degrades into range.",
        },
    ]

    provisional_proxies = [
        {
            "id": "reclaim_proxy_v1",
            "status": "provisional",
            "default_mode": "close_back_through_swept_reference",
            "logic": "After a bullish low sweep, require a close back above the swept anchor; after a bearish high sweep, require a close back below the swept anchor. Alternate mode allows a close back inside the source range instead.",
        },
        {
            "id": "cisd_proxy_v1",
            "status": "provisional",
            "default_mode": "body_break_impulse_cluster",
            "logic": "Define the impulse into the sweep as the contiguous run of same-direction candles ending at the sweep bar. Bullish CISD fires on the first close above the highest body edge of the last bearish impulse bar in that cluster; bearish CISD is the mirror rule below the lowest body edge of the last bullish impulse bar.",
        },
        {
            "id": "body_invalidation_proxy_v1",
            "status": "provisional",
            "default_mode": "wick_dominance_blocks_aggressive_mode",
            "logic": "Allow body-based invalidation only when the confirming swing candle is not wick-dominant and reward-to-risk at the structural stop is below the minimum threshold.",
        },
    ]

    acceptance_checks = [
        "No reversal signal can appear before an external anchor sweep is detected.",
        "No entry-ready state can appear without a reclaim and CISD sequence in that order.",
        "When wick-midpoint respect is enabled, a midpoint breach cancels or downgrades the reversal path before entry-ready.",
        "Aggressive body-based invalidation must be visibly labeled as tighter-risk mode and cannot replace the stored structural invalidation anchor.",
        "The script must stay bar-close confirmed and avoid intrabar-only transitions.",
        "The implementation should stay within the configured request-security budget and avoid unbounded multi-timeframe fan-out.",
    ]

    open_implementation_questions = [
        {
            "question": "What is the cleanest first-pass CISD definition for reversal confirmation without discretionary candle reading?",
            "affected_component": "cisd_proxy",
            "topic_refs": ["reversal", "top_down_alignment", "bias", "protected_swings"],
        },
        {
            "question": "What is the cleanest first-pass reclaim or inversion rule when the move back through the extreme is shallow or fast?",
            "affected_component": "reclaim_proxy",
            "topic_refs": ["reversal"],
        },
        {
            "question": "What machine proxy best separates bulk opposing candles from wick-dominant swings before allowing body-based invalidation?",
            "affected_component": "aggressive_invalidation_mode",
            "topic_refs": ["invalidation", "wick_logic"],
        },
    ]

    return {
        **base_spec,
        "spec_version": 2,
        "translation_stage": "draft",
        "artifact_path": str(artifact_path.relative_to(ROOT)),
        "implementation_summary": "First-pass Pine overlay draft for the TTrades reversal sequence using external-anchor sweeps, reclaim, CISD, protected-swing confirmation, and configurable post-shift entry families.",
        "implementation_scope": implementation_scope,
        "pine_program_outline": {
            "script_kind": "indicator",
            "overlay": True,
            "sections": pine_sections,
            "anti_repaint_baseline": "bar_close_confirmation",
        },
        "scope_topics": scope_topics,
        "topic_rule_trace": build_rule_trace(rulebooks),
        "topic_input_catalog": collect_unique_inputs(rulebooks),
        "input_groups": input_groups,
        "derived_series": derived_series,
        "state_models": state_models,
        "signal_pipeline": signal_pipeline,
        "visuals": visuals,
        "alerts": alerts,
        "provisional_proxies": provisional_proxies,
        "acceptance_checks": acceptance_checks,
        "open_implementation_questions": open_implementation_questions,
        "future_extensions": [
            "Numeric wick-ratio thresholds once wick-logic cutoffs are finalized.",
            "A stricter CISD proxy once the reversal and alignment topics settle on one candle-series algorithm.",
            "Optional breaker-specific entry family once reclaim and CISD logic are stable enough to support it.",
        ],
    }


def build_continuation_entry_model_draft(base_spec: dict) -> dict:
    scope_topics = collect_scope_topics(base_spec)
    rulebooks = {topic_slug: load_rulebook(topic_slug) for topic_slug in scope_topics}
    artifact_path = OUTPUT_DIR / f"{base_spec['trade_model']['slug']}.json"

    implementation_scope = dict(base_spec.get("implementation_scope", {}))
    implementation_scope.update(
        {
            "translation_stage": "draft",
            "build_target": "continuation_execution_overlay_indicator",
            "max_request_calls_budget": 6,
            "candidate_preservation_rule": "materializer_refreshes_candidate_fields_without_downgrading_draft_status",
            "timeframe_stack": {
                "higher": "daily_or_4h_bias_frame",
                "intermediate": "1h_or_15m_anchor_frame",
                "lower": "5m_or_1m_execution_frame",
            },
        }
    )

    pine_sections = [
        "version",
        "indicator_declaration",
        "imports",
        "constants",
        "inputs",
        "functions",
        "calculations",
        "visuals",
        "alerts",
    ]

    input_groups = [
        {
            "group": "Timeframes and Context",
            "inputs": [
                {
                    "key": "anchorBiasTimeframe",
                    "type": "timeframe",
                    "default": "D",
                    "description": "Higher timeframe used to determine whether continuation logic is allowed at all.",
                },
                {
                    "key": "anchorStructureTimeframe",
                    "type": "timeframe",
                    "default": "60",
                    "description": "Intermediate timeframe used to identify pullback anchors, equilibrium holds, and continuation structure.",
                },
                {
                    "key": "executionTimeframe",
                    "type": "timeframe",
                    "default": "15",
                    "description": "Lower timeframe used to confirm the continuation reaction and protected swing.",
                },
                {
                    "key": "activeKillZone",
                    "type": "enum",
                    "default": "both",
                    "options": ["off", "london", "new_york", "both"],
                    "description": "Optional session filter for continuation execution logic.",
                },
                {
                    "key": "requireAlignmentAcrossFrames",
                    "type": "bool",
                    "default": True,
                    "description": "Require higher, intermediate, and execution timeframes to agree before continuation logic can advance.",
                },
            ],
        },
        {
            "group": "Continuation Anchors",
            "inputs": [
                {
                    "key": "enabledAnchorFamilies",
                    "type": "string_list",
                    "default": [
                        "equilibrium_half",
                        "order_block",
                        "fair_value_gap",
                        "breaker_block",
                        "range_resolution",
                    ],
                    "description": "Continuation anchor families that may qualify once bias and pullback context are valid.",
                },
                {
                    "key": "requirePoiTouch",
                    "type": "bool",
                    "default": True,
                    "description": "Require price to tag an explicit point of interest before continuation confirmation is allowed.",
                },
                {
                    "key": "anchorPriorityMode",
                    "type": "enum",
                    "default": "equilibrium_then_confirmed_structure",
                    "options": [
                        "equilibrium_then_confirmed_structure",
                        "nearest_confirmed_structure",
                        "bias_aligned_sweep_first",
                    ],
                    "description": "Priority rule when equilibrium, order blocks, imbalances, and breakout-resolution anchors overlap.",
                },
                {
                    "key": "minimumAnchorScore",
                    "type": "int",
                    "default": 4,
                    "description": "Minimum first-pass score required before an anchor family can arm the continuation workflow.",
                },
                {
                    "key": "preferredAnchorScore",
                    "type": "int",
                    "default": 6,
                    "description": "Score at which one anchor clearly outranks nearby alternatives instead of remaining a tie candidate.",
                },
                {
                    "key": "retracementDepthMode",
                    "type": "enum",
                    "default": "shallow_or_moderate",
                    "options": ["shallow_only", "shallow_or_moderate"],
                    "description": "Choose how strict the pullback depth filter should be before continuation logic is disabled.",
                },
                {
                    "key": "shallowRetracementMaxFraction",
                    "type": "float",
                    "default": 0.5,
                    "description": "First-pass upper bound for a clean shallow retracement as a fraction of the prior expansion leg.",
                },
                {
                    "key": "moderateRetracementMaxFraction",
                    "type": "float",
                    "default": 0.62,
                    "description": "First-pass upper bound for a still-usable moderate retracement before the setup is treated as late or degraded.",
                },
                {
                    "key": "allowConsolidationBreakoutContinuation",
                    "type": "bool",
                    "default": True,
                    "description": "Allow continuation entries that come from post-consolidation resolution instead of a clean single-leg pullback.",
                },
            ],
        },
        {
            "group": "Confirmation Proxies",
            "inputs": [
                {
                    "key": "cisdMode",
                    "type": "enum",
                    "default": "close_through_opposing_series",
                    "options": [
                        "close_through_opposing_series",
                        "close_through_series_plus_displacement",
                    ],
                    "description": "First-pass continuation confirmation proxy after the anchor reaction begins.",
                },
                {
                    "key": "reactionBarLimit",
                    "type": "int",
                    "default": 3,
                    "description": "Maximum number of bars allowed for the continuation reaction before quality is downgraded.",
                },
                {
                    "key": "requireProtectedSwingConfirmation",
                    "type": "bool",
                    "default": True,
                    "description": "Require a new protected swing before the continuation state can become entry-ready.",
                },
                {
                    "key": "requireCorrectHalfRespect",
                    "type": "bool",
                    "default": True,
                    "description": "Require the continuation to hold the correct side of equilibrium before the reaction is accepted.",
                },
                {
                    "key": "equilibriumTolerancePercentOfRange",
                    "type": "float",
                    "default": 0.05,
                    "description": "First-pass tolerance around the equilibrium midpoint before a close is treated as a real wrong-side failure instead of minor probing.",
                },
                {
                    "key": "requireCandleThreeClosureAssist",
                    "type": "bool",
                    "default": False,
                    "description": "Optional extra filter that requires candle-three-style closure behavior before continuation is marked high quality.",
                },
            ],
        },
        {
            "group": "Failure and Exhaustion Filters",
            "inputs": [
                {
                    "key": "oneMoreCandleFilter",
                    "type": "bool",
                    "default": True,
                    "description": "Require one extra follow-through candle after the initial reaction before entry-ready status appears.",
                },
                {
                    "key": "localRotationThreshold",
                    "type": "int",
                    "default": 2,
                    "description": "Maximum tolerated local two-sided rotations before the setup is treated as consolidation instead of continuation.",
                },
                {
                    "key": "requireHigherTimeframeObjectiveOpen",
                    "type": "bool",
                    "default": True,
                    "description": "Block late continuations once the higher-timeframe target is already considered complete.",
                },
                {
                    "key": "expansionExhaustionBarCount",
                    "type": "int",
                    "default": 3,
                    "description": "Provisional higher-timeframe expansion count beyond which continuation expectations should be reduced.",
                },
                {
                    "key": "maxOpposingWickRatio",
                    "type": "float",
                    "default": 0.35,
                    "description": "Provisional opposing-wick ratio used to downgrade continuation quality when rejection grows too large.",
                },
            ],
        },
        {
            "group": "Risk and Targets",
            "inputs": [
                {
                    "key": "invalidationMode",
                    "type": "enum",
                    "default": "protected_swing",
                    "options": ["protected_swing", "body_conditional"],
                    "description": "Structural invalidation mode for the displayed continuation stop reference.",
                },
                {
                    "key": "minimumRewardRisk",
                    "type": "float",
                    "default": 1.5,
                    "description": "Minimum reward-to-risk threshold required before a continuation entry is shown.",
                },
                {
                    "key": "firstTargetMode",
                    "type": "enum",
                    "default": "nearest_external_liquidity",
                    "options": [
                        "nearest_external_liquidity",
                        "previous_day_objective_first",
                    ],
                    "description": "Choose whether the first target should prioritize the nearest external liquidity or previous-day objective logic first.",
                },
                {
                    "key": "objectiveCompletionMode",
                    "type": "enum",
                    "default": "wick_touch_or_close_through",
                    "options": [
                        "wick_touch_or_close_through",
                        "close_through_only",
                    ],
                    "description": "Choose how the first target is marked complete before blocking late continuation setups.",
                },
                {
                    "key": "showAggressiveStopPreview",
                    "type": "bool",
                    "default": True,
                    "description": "Display the tighter body-based stop preview when conditional invalidation logic allows it.",
                },
            ],
        },
    ]

    derived_series = [
        {
            "series": "higherTimeframeBiasState",
            "description": "Higher-timeframe continuation bias state used to enable or block the entire continuation sequence.",
        },
        {
            "series": "higherTimeframeObjectiveState",
            "description": "Open versus completed higher-timeframe objective state used to block late continuations.",
        },
        {
            "series": "expansionContextState",
            "description": "Expansion versus non-expansion context across the higher and intermediate frames.",
        },
        {
            "series": "retracementState",
            "description": "Controlled pullback depth, location, and completion state before the continuation reaction begins.",
        },
        {
            "series": "continuationAnchorState",
            "description": "Selected continuation anchor family and its active zone boundaries.",
        },
        {
            "series": "anchorPriorityScore",
            "description": "Explicit first-pass score used to rank competing continuation anchors inside the same pullback region.",
        },
        {
            "series": "equilibriumHalfState",
            "description": "Whether price is holding the correct half of the selected range around equilibrium.",
        },
        {
            "series": "retracementDepthBand",
            "description": "Shallow, moderate, deep, or invalid retracement classification relative to the prior expansion leg.",
        },
        {
            "series": "wickQualityState",
            "description": "Continuation quality score based on opposing-wick growth during the reaction and follow-through bars.",
        },
        {
            "series": "consolidationResolutionState",
            "description": "Whether the setup is a valid post-consolidation continuation or still rotating inside a local range.",
        },
        {
            "series": "cisdState",
            "description": "First-pass continuation CISD proxy after the pullback anchor reacts.",
        },
        {
            "series": "candleThreeAssistState",
            "description": "Optional candle-three closure assist used as a quality gate rather than as the main trigger.",
        },
        {
            "series": "protectedSwingState",
            "description": "Most recent protected swing used for continuation confirmation and invalidation.",
        },
        {
            "series": "continuationQualityState",
            "description": "Composite quality state that degrades on slow reactions, deep pullbacks, large opposing wicks, or late objectives.",
        },
        {
            "series": "entryReadyState",
            "description": "Final state showing whether the continuation is context-ready, structurally confirmed, and risk-acceptable.",
        },
    ]

    state_models = [
        {
            "name": "continuationEntryState",
            "state_type": "finite_state_machine",
            "states": [
                "idle",
                "context_ready",
                "anchor_tagged",
                "reaction_confirmed",
                "protected_swing_confirmed",
                "entry_ready",
                "exhausted_or_invalid",
            ],
            "transitions": [
                {
                    "from": "idle",
                    "to": "context_ready",
                    "condition": "Higher-timeframe bias, expansion context, and alignment filters all agree and the higher-timeframe objective is still open.",
                },
                {
                    "from": "context_ready",
                    "to": "anchor_tagged",
                    "condition": "A valid continuation point of interest is tagged through equilibrium respect, a structure anchor, or qualified post-consolidation resolution.",
                },
                {
                    "from": "anchor_tagged",
                    "to": "reaction_confirmed",
                    "condition": "Price reacts within the allowed bar limit and confirms through the selected continuation CISD proxy while still respecting the correct half of the range.",
                },
                {
                    "from": "reaction_confirmed",
                    "to": "protected_swing_confirmed",
                    "condition": "A new protected swing forms in the direction of bias and any optional candle-three assist has passed.",
                },
                {
                    "from": "protected_swing_confirmed",
                    "to": "entry_ready",
                    "condition": "Risk, target-open, and one-more-candle filters all pass after structural confirmation.",
                },
                {
                    "from": [
                        "context_ready",
                        "anchor_tagged",
                        "reaction_confirmed",
                        "protected_swing_confirmed",
                        "entry_ready",
                    ],
                    "to": "exhausted_or_invalid",
                    "condition": "The pullback becomes too deep, the setup rotates back into consolidation, the protected swing fails, or the higher-timeframe objective is already complete.",
                },
            ],
        }
    ]

    signal_pipeline = [
        {
            "step": 1,
            "name": "Bias and Alignment Gate",
            "logic": "Enable continuation logic only when the higher timeframe is still in a continuation framework, the expansion context is intact, and the intermediate plus execution frames do not fight that direction.",
            "rule_refs": [
                "bias.daily_continuation_framework",
                "bias.bias_precedes_execution",
                "expansion.multi_timeframe_alignment",
                "top_down_alignment.higher_timeframe_sets_direction",
                "top_down_alignment.intermediate_timeframe_confirms_structure",
                "top_down_alignment.lower_timeframe_refines_entry_only_after_alignment",
            ],
        },
        {
            "step": 2,
            "name": "Expansion and Retracement Gate",
            "logic": "Require prior expansion, then demand a controlled retracement or local consolidation-resolution context instead of chasing a move that is already extended or structurally late.",
            "rule_refs": [
                "expansion.expansion_definition",
                "retracement.retracement_phase_definition",
                "retracement.retracement_location_and_depth",
                "retracement.retracement_completion_confirmation",
                "continuation.continuation_definition",
            ],
        },
        {
            "step": 3,
            "name": "Anchor Selection and Equilibrium Filter",
            "logic": "Rank equilibrium, order-block, breaker, fair-value-gap, and breakout-resolution anchors, then allow continuation only if the correct side of equilibrium and the selected point of interest are still respected.",
            "rule_refs": [
                "continuation.equilibrium_respect_continuation",
                "continuation.continuation_structure_variants",
                "equilibrium.equilibrium_is_wick_to_wick_midpoint",
                "equilibrium.equilibrium_respect_sets_directional_half",
                "equilibrium.equilibrium_requires_poi_and_confirmation",
                "consolidation.manipulation_then_resolution",
                "consolidation.breakout_continuation_from_consolidation",
            ],
        },
        {
            "step": 4,
            "name": "Reaction and Structure Confirmation",
            "logic": "After the anchor reacts, require a bar-close continuation shift through the opposing candle series, optionally add candle-three-style closure assistance, and then require a newly protected swing before continuation is treated as structurally valid.",
            "rule_refs": [
                "continuation.continuation_definition",
                "expansion.expansion_entry_workflow",
                "candle_3_closure.candle_three_requires_context_and_poi",
                "candle_3_closure.valid_swing_requires_poi_and_closure",
                "protected_swings.protected_swing_definition",
                "protected_swings.protected_swing_confirmation_gate",
            ],
        },
        {
            "step": 5,
            "name": "Risk, Failure, and Rotation Filter",
            "logic": "Keep the protected swing as the default stop, allow tighter body invalidation only conditionally, and reject continuation candidates that degrade into local range rotation, deep pullback failure, or poor reward-to-risk.",
            "rule_refs": [
                "invalidation.protected_swing_is_default_invalidation",
                "invalidation.body_invalidation_is_conditional_risk_tightening",
                "invalidation.wait_for_new_protected_swing_if_rr_is_poor",
                "continuation.continuation_failure_filters",
                "retracement.retracement_absence_and_failure_filters",
            ],
        },
        {
            "step": 6,
            "name": "Target Open and Exhaustion Management",
            "logic": "Only show continuation entries while the higher-timeframe objective remains open, reduce expectations after repeated expansion, and invalidate the setup once structure turns back into range or the objective is already complete.",
            "rule_refs": [
                "continuation.continuation_failure_filters",
                "expansion.expansion_exhaustion_guard",
                "equilibrium.previous_day_equilibrium_filters_continuation_day",
                "invalidation.continuation_or_reversal_is_invalid_when_structure_turns_into_range_or_target_is_already_met",
            ],
        },
    ]

    visuals = [
        "Higher-timeframe bias banner and objective-open status tag",
        "Selected continuation anchor zones for equilibrium, order block, fair value gap, breaker, or breakout-resolution paths",
        "Equilibrium midpoint plus correct-half shading for the active anchor range",
        "Reaction, CISD, and protected-swing markers on the execution timeframe",
        "Structural invalidation line with optional aggressive body-stop preview",
        "First-target and next-external-liquidity bands with exhausted-state labels",
    ]

    alerts = [
        {
            "name": "continuation_context_ready",
            "condition": "Higher-timeframe bias, alignment, and expansion context all permit continuation logic.",
        },
        {
            "name": "continuation_anchor_tagged",
            "condition": "A valid continuation anchor or post-consolidation resolution zone has been tagged.",
        },
        {
            "name": "continuation_reaction_confirmed",
            "condition": "The continuation reaction confirms through the selected CISD proxy within the allowed bar limit.",
        },
        {
            "name": "continuation_entry_ready",
            "condition": "Protected swing, risk, target-open, and one-more-candle filters all pass.",
        },
        {
            "name": "continuation_exhausted_or_invalid",
            "condition": "The continuation setup degrades into range, fails its invalidation, or is blocked by completed higher-timeframe objectives.",
        },
    ]

    decision_tables = [
        {
            "name": "anchor_priority_score_v1",
            "description": "First-pass ranking table for competing continuation anchors before lower-timeframe execution.",
            "scoring": [
                {
                    "condition": "Anchor remains inside the respected equilibrium half after the tag.",
                    "score": 3,
                },
                {
                    "condition": "Retracement depth is shallow or moderate instead of deep.",
                    "score": 2,
                },
                {
                    "condition": "A sweep, failure swing, or breakout-retest hold appears at the anchor before confirmation.",
                    "score": 2,
                },
                {
                    "condition": "Continuation CISD confirms within the configured reaction-bar limit.",
                    "score": 2,
                },
                {
                    "condition": "A new protected swing forms without first revisiting the wrong side of equilibrium.",
                    "score": 1,
                },
            ],
            "interpretation": {
                "below_4": "context_only_anchor",
                "4_to_5": "usable_anchor",
                "6_or_more": "preferred_anchor",
            },
        },
        {
            "name": "retracement_depth_bands_v1",
            "description": "Explicit depth classification used by the continuation draft before continuation quality is promoted or demoted.",
            "bands": [
                {
                    "label": "shallow",
                    "condition": "pullback_fraction <= 0.50",
                    "effect": "highest_quality_if_other_filters_hold",
                },
                {
                    "label": "moderate",
                    "condition": "0.50 < pullback_fraction <= 0.62",
                    "effect": "still_usable_but_requires_clean_confirmation",
                },
                {
                    "label": "deep",
                    "condition": "0.62 < pullback_fraction and protected_swing_intact",
                    "effect": "downgrade_quality_and_block_aggressive_entries",
                },
                {
                    "label": "invalid",
                    "condition": "protected_swing_broken_or_wrong_side_equilibrium_close",
                    "effect": "cancel_continuation_path",
                },
            ],
        },
        {
            "name": "objective_open_filter_v1",
            "description": "First-pass rule for deciding whether continuation targets are still open enough to justify a new entry.",
            "rules": [
                "When firstTargetMode is nearest_external_liquidity, track the nearest unswept external high or low in the direction of bias.",
                "When firstTargetMode is previous_day_objective_first, track the relevant previous-day high or low before broader external liquidity.",
                "When objectiveCompletionMode is wick_touch_or_close_through, mark the target complete on the first wick touch or close through.",
                "When objectiveCompletionMode is close_through_only, require a bar close through the active target before marking it complete.",
                "Once the first target is complete, block fresh continuation entries until a new higher-timeframe objective is promoted.",
            ],
        },
    ]

    provisional_proxies = [
        {
            "id": "anchor_family_proxy_v2",
            "status": "provisional",
            "default_mode": "equilibrium_then_confirmed_structure",
            "logic": "Create candidate continuation anchors from equilibrium hold zones, fair value gaps, order blocks, breaker blocks, and post-consolidation resolution zones. Score each anchor using the explicit ranking table: +3 for correct-half equilibrium respect, +2 for shallow-or-moderate retracement depth, +2 for sweep or breakout-retest evidence, +2 for CISD within the reaction-bar limit, and +1 for protected-swing confirmation without wrong-side equilibrium failure. Require a score of at least 4 to arm an anchor and 6 or more to prefer it over nearby alternatives.",
        },
        {
            "id": "retracement_depth_proxy_v2",
            "status": "provisional",
            "default_mode": "leg_fraction_with_equilibrium_hold",
            "logic": "Measure retracement depth as the pullback distance versus the prior expansion leg. Classify pullbacks as shallow at or below 0.50 of the prior leg, moderate up to 0.62, deep above 0.62 while the protected swing still survives, and invalid once the protected swing breaks or a close exceeds the wrong-side equilibrium tolerance band.",
        },
        {
            "id": "continuation_cisd_proxy_v1",
            "status": "provisional",
            "default_mode": "close_through_opposing_series",
            "logic": "Bullish continuation confirmation fires on the first close above the highest body edge of the last bearish candle cluster inside the pullback; bearish continuation confirmation mirrors the rule below the lowest body edge of the last bullish cluster. Optional displacement mode also requires the confirming candle to exceed a recent body percentile threshold.",
        },
        {
            "id": "objective_open_and_rotation_proxy_v2",
            "status": "provisional",
            "default_mode": "external_target_unreached_and_overlap_limited",
            "logic": "Treat the higher-timeframe objective as still open until the selected first target is completed by wick touch or close through according to objectiveCompletionMode. Reject the continuation if local rotation count exceeds the configured limit before that objective is reached, or immediately block fresh entries once the active first target has already been completed.",
        },
        {
            "id": "equilibrium_respect_proxy_v1",
            "status": "provisional",
            "default_mode": "correct_half_with_5_percent_tolerance",
            "logic": "Treat equilibrium respect as intact while closes remain in the correct half of the active range or only probe the midpoint within a 5% tolerance band of the full wick range. Any close beyond that tolerance in the wrong direction cancels continuation quality until the correct half is reclaimed.",
        },
    ]

    acceptance_checks = [
        "No continuation entry-ready state can appear before higher-timeframe bias and expansion context are both active.",
        "No anchor with a score below the configured minimum can arm the continuation workflow or outrank a higher-scoring competing anchor.",
        "No anchor zone may trigger entry-ready status on its own without a continuation reaction and, when enabled, a protected-swing confirmation.",
        "When correct-half respect is enabled, any close through the wrong side of equilibrium must downgrade or cancel the continuation path before entry-ready.",
        "A deep pullback classification may stay visible as context, but it must block aggressive continuation entry-ready status until structure improves.",
        "Once the active first target is already complete under the selected objective-completion mode, no fresh continuation entry-ready state may appear until a new higher-timeframe objective is defined.",
        "Aggressive body-based invalidation must remain a preview overlay and cannot replace the stored protected-swing invalidation anchor.",
        "When the one-more-candle filter is enabled, entry-ready status must wait for a follow-through bar after the first structural confirmation.",
        "The script must remain bar-close confirmed, avoid intrabar-only state transitions, and stay within the configured request-security budget.",
    ]

    open_implementation_questions = [
        {
            "question": "What numeric displacement threshold should the optional close_through_series_plus_displacement mode use before it materially improves continuation quality over the simpler close-through proxy?",
            "affected_component": "continuation_cisd_displacement_filter",
            "topic_refs": ["continuation", "expansion", "wick_logic"],
        },
        {
            "question": "When SMT evidence is available, how much should it upgrade breaker-block and range-resolution anchors relative to direct sweep evidence in the first-pass anchor score?",
            "affected_component": "smt_anchor_upgrade",
            "topic_refs": ["continuation", "consolidation", "protected_swings"],
        },
    ]

    return {
        **base_spec,
        "spec_version": 2,
        "translation_stage": "draft",
        "artifact_path": str(artifact_path.relative_to(ROOT)),
        "implementation_summary": "First-pass Pine overlay draft for the TTrades continuation entry model using higher-timeframe bias, controlled retracement anchors, equilibrium respect, continuation CISD, protected-swing confirmation, and exhaustion filters.",
        "implementation_scope": implementation_scope,
        "pine_program_outline": {
            "script_kind": "indicator",
            "overlay": True,
            "sections": pine_sections,
            "anti_repaint_baseline": "bar_close_confirmation",
        },
        "scope_topics": scope_topics,
        "topic_rule_trace": build_rule_trace(rulebooks),
        "topic_input_catalog": collect_unique_inputs(rulebooks),
        "input_groups": input_groups,
        "derived_series": derived_series,
        "state_models": state_models,
        "signal_pipeline": signal_pipeline,
        "visuals": visuals,
        "alerts": alerts,
        "decision_tables": decision_tables,
        "provisional_proxies": provisional_proxies,
        "acceptance_checks": acceptance_checks,
        "open_implementation_questions": open_implementation_questions,
        "future_extensions": [
            "A calibrated anchor-scoring model once more annotated continuation cases are available for threshold tuning.",
            "A stricter displacement threshold once continuation quality cutoffs are benchmarked beyond the current first-pass scaffold.",
            "Optional SMT and breaker-specific continuation branches once the anchor-family proxy is stable enough to support more granular execution paths.",
        ],
    }


def build_draft_spec(spec_row: dict) -> dict:
    base_spec = spec_row["spec_json"]
    trade_model_slug = str(base_spec["trade_model"]["slug"])

    if trade_model_slug == "daily_bias_framework":
        return build_daily_bias_framework_draft(base_spec)

    if trade_model_slug == "fractal_closure_model":
        return build_fractal_closure_model_draft(base_spec)

    if trade_model_slug == "daily_profile_models":
        return build_daily_profile_models_draft(base_spec)

    if trade_model_slug == "reversal_sequence_model":
        return build_reversal_sequence_draft(base_spec)

    if trade_model_slug == "continuation_entry_model":
        return build_continuation_entry_model_draft(base_spec)

    raise ValueError(f"No Pine draft builder is defined for trade model: {trade_model_slug}")


def write_artifact(spec_json: dict) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    artifact_path = ROOT / str(spec_json["artifact_path"])
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(spec_json, indent=2), encoding="utf-8")
    return artifact_path


def save_indicator_spec(
    connection: sqlite3.Connection,
    spec_key: str,
    topic_slug: str,
    name: str,
    target_language: str,
    status: str,
    spec_json: dict,
) -> None:
    connection.execute(
        """
        UPDATE indicator_specs
        SET topic_slug = ?,
            name = ?,
            target_language = ?,
            status = ?,
            spec_json = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE spec_key = ?
        """,
        (
            topic_slug,
            name,
            target_language,
            status,
            json.dumps(spec_json, sort_keys=True),
            spec_key,
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Promote an indicator candidate into a first-pass Pine draft spec.")
    parser.add_argument("--spec-key", required=True)
    parser.add_argument("--status", default="draft")
    args = parser.parse_args()

    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        spec_row = load_indicator_spec(connection, args.spec_key)
        if spec_row["target_language"] != "pine":
            raise ValueError(f"Unsupported target language for draft builder: {spec_row['target_language']}")

        spec_json = build_draft_spec(spec_row)
        artifact_path = write_artifact(spec_json)
        save_indicator_spec(
            connection,
            spec_row["spec_key"],
            spec_row["topic_slug"],
            spec_row["name"],
            spec_row["target_language"],
            args.status,
            spec_json,
        )
        connection.commit()

    print(
        json.dumps(
            {
                "spec_key": spec_row["spec_key"],
                "status": args.status,
                "artifact_path": str(artifact_path),
                "translation_stage": spec_json["translation_stage"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
