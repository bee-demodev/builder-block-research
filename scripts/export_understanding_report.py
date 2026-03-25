from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from evaluate_rulebook import evaluate
from export_topic_model_report import build_topic_entries


ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "research.db"
DEFAULT_OUTPUT = ROOT / "results" / "understanding_report.json"
TRADER_ANNOTATION_CASES_PATH = ROOT / "data" / "trader_annotation_cases.json"


SCENARIO_EXPECTATIONS: dict[tuple[str, str], list[str]] = {
    ("ttrades_daily_bias_continuation_baseline_v1", "daily_bias_framework"): [
        "previous_day",
        "equilibrium",
        "continuation",
        "lower_timeframe_confirmation",
        "external_liquidity",
    ],
    ("ttrades_daily_bias_reversal_baseline_v1", "daily_bias_framework"): [
        "previous_day_extreme",
        "reversal",
        "wick_rejection",
        "lower_timeframe_confirmation",
        "equilibrium_target",
    ],
    ("ttrades_continuation_equilibrium_hold_baseline_v1", "continuation_entry_model"): [
        "equilibrium",
        "continuation",
        "opposing_series_close",
        "protected_swing",
        "external_liquidity",
    ],
    ("ttrades_continuation_failure_baseline_v1", "continuation_entry_model"): [
        "continuation_failure",
        "consolidation",
        "rotation",
        "stand_aside",
        "objective_complete",
    ],
    ("ttrades_new_york_reversal_profile_baseline_v1", "daily_profile_models"): [
        "london_session",
        "new_york_session",
        "session_reversal",
        "cisd",
        "session_extreme",
    ],
    ("ttrades_new_york_reversal_profile_baseline_v1", "reversal_sequence_model"): [
        "reversal",
        "liquidity_sweep",
        "cisd",
        "invalidation",
        "liquidity_target",
    ],
    ("ttrades_seek_and_destroy_profile_filter_baseline_v1", "daily_profile_models"): [
        "asia_session",
        "london_session",
        "new_york_session",
        "seek_and_destroy",
        "equilibrium",
    ],
    ("ttrades_candle_3_closure_continuation_baseline_v1", "fractal_closure_model"): [
        "candle_3",
        "candle_2",
        "point_of_interest",
        "equilibrium",
        "candle_4",
    ],
    ("ttrades_candle_2_closure_reversal_baseline_v1", "fractal_closure_model"): [
        "candle_2",
        "point_of_interest",
        "lower_timeframe_refinement",
        "confirmed_swing",
        "reversal",
    ],
    ("ttrades_candle_2_closure_reversal_baseline_v1", "reversal_sequence_model"): [
        "candle_2",
        "reversal",
        "point_of_interest",
        "invalidation",
        "opposing_liquidity",
    ],
    ("ttrades_continuation_order_block_retest_baseline_v1", "continuation_entry_model"): [
        "order_block",
        "fair_value_gap_or_sweep",
        "closure_confirmation",
        "protected_swing_invalidation",
        "external_liquidity",
    ],
    ("ttrades_continuation_breaker_block_retest_baseline_v1", "continuation_entry_model"): [
        "breaker_block",
        "liquidity_sweep_or_smt",
        "higher_timeframe_bias",
        "retest_entry",
        "previous_high_low_liquidity",
    ],
    ("ttrades_continuation_top_down_alignment_baseline_v1", "continuation_entry_model"): [
        "higher_timeframe_bias",
        "intermediate_structure_confirmation",
        "lower_timeframe_confirmation",
        "protected_swing_or_order_block",
        "higher_timeframe_liquidity",
    ],
    ("ttrades_continuation_large_wick_filter_baseline_v1", "continuation_entry_model"): [
        "large_opposing_wick",
        "bias_support",
        "stand_aside",
        "daily_open_or_nearby_liquidity",
        "wait_for_small_wick_alignment",
    ],
    ("ttrades_retracement_missing_confirmation_filter_baseline_v1", "continuation_entry_model"): [
        "retracement",
        "no_sweep",
        "no_fair_value_gap",
        "no_new_protected_swing",
        "wait_for_confirmation",
    ],
}


CONCEPT_ALIASES: dict[str, list[str]] = {
    "previous_day": ["previous day", "previous-day", "prior day", "previousDay"],
    "previous_day_extreme": ["previous day extreme", "previous-day extreme", "previous day high", "previous day low", "previous-day high", "previous-day low"],
    "equilibrium": ["equilibrium", "midpoint", "correct half"],
    "equilibrium_target": ["equilibrium", "midpoint"],
    "continuation": ["continuation", "trend resumption", "continuation day"],
    "lower_timeframe_confirmation": ["lower timeframe", "execution timeframe", "15m", "5m", "1m", "confirmation"],
    "external_liquidity": ["external liquidity", "next external liquidity", "external high", "external low"],
    "reversal": ["reversal", "reclaim", "kill zone"],
    "wick_rejection": ["wick", "rejection", "midpoint respect"],
    "opposing_series_close": ["opposing candle series", "close through", "closure through"],
    "protected_swing": ["protected swing", "swing confirmation", "structural invalidation"],
    "continuation_failure": ["failure", "invalid", "late continuation", "degrade"],
    "consolidation": ["consolidation", "range", "breakout-resolution", "breakout continuation"],
    "rotation": ["rotation", "whipsaw", "two-sided", "seek-and-destroy"],
    "stand_aside": ["stand aside", "avoid", "no trade", "wait"],
    "objective_complete": ["objective complete", "target is complete", "target complete", "objective is already complete", "target-open"],
    "london_session": ["london", "0200-0500"],
    "new_york_session": ["new york", "new_york", "0830-1200", "09:30", "08:30"],
    "asia_session": ["asia", "1900-0000"],
    "session_reversal": ["session profile", "new york reversal", "reversal profile", "london reversal"],
    "cisd": ["cisd", "change in state of delivery", "close through", "displacement"],
    "session_extreme": ["session extreme", "new york session extreme", "session high", "session low"],
    "liquidity_sweep": ["sweep", "liquidity", "external anchor", "swept"],
    "invalidation": ["invalidation", "stop", "session extreme", "protected swing"],
    "liquidity_target": ["liquidity", "external liquidity", "opposing liquidity", "target"],
    "seek_and_destroy": ["seek-and-destroy", "seek and destroy", "false breakout", "daily open", "range magnets"],
    "candle_3": ["candle 3", "candle_three", "candle-three"],
    "candle_2": ["candle 2", "candle_two", "candle-two"],
    "point_of_interest": ["point of interest", "poi", "order block", "fair value gap", "key level"],
    "candle_4": ["candle 4", "candle_four", "candle-four", "follow-through"],
    "lower_timeframe_refinement": ["lower timeframe refinement", "refine lower timeframe", "execution timeframe", "5m", "15m", "1m"],
    "confirmed_swing": ["confirmed swing", "protected swing", "valid swing"],
    "opposing_liquidity": ["opposing liquidity", "opposite liquidity", "opposing side", "low resistance liquidity"],
    "order_block": ["order block", "validated order block"],
    "fair_value_gap_or_sweep": ["fair value gap", "fvg", "liquidity sweep", "sweep", "smt divergence proxy"],
    "closure_confirmation": ["closure through", "close through", "closes through", "opposing candle series"],
    "protected_swing_invalidation": ["protected swing", "invalidation", "beyond validated order block and protected swing"],
    "breaker_block": ["breaker block", "breaker structure", "breaker structure completion"],
    "liquidity_sweep_or_smt": ["liquidity sweep", "sweep", "smt", "smt divergence"],
    "higher_timeframe_bias": ["higher timeframe bias", "daily closure sets direction", "bias supports direction", "higher timeframe bias and protected swing alignment"],
    "retest_entry": ["retest", "enter on breaker block retest", "enter on validated order block retest"],
    "previous_high_low_liquidity": ["previous high", "previous low", "previous high or low liquidity", "hourly or previous day liquidity"],
    "intermediate_structure_confirmation": ["hourly cisd", "intermediate structure", "15m structure", "protected swing at point of interest"],
    "protected_swing_or_order_block": ["new protected swing", "continuation order block", "protected swing", "order block"],
    "higher_timeframe_liquidity": ["higher timeframe liquidity", "higher timeframe liquidity target"],
    "large_opposing_wick": ["large opposing wick", "large wick", "opposing wick"],
    "bias_support": ["bias supports direction", "higher timeframe context"],
    "daily_open_or_nearby_liquidity": ["daily open", "nearby intraday liquidity", "nearby liquidity"],
    "wait_for_small_wick_alignment": ["wait for next small wick alignment", "small wick alignment", "wait"],
    "no_sweep": ["no sweep", "missing direct sweep"],
    "no_fair_value_gap": ["no fair value gap", "missing fair value gap"],
    "no_new_protected_swing": ["no new protected swing", "no_new_protected_swing"],
    "wait_for_confirmation": ["wait for protected swing or candle 2 closure", "wait for confirmation", "wait"],
}


TIMEFRAME_ALIASES: dict[str, list[str]] = {
    "higher": ["higher", "daily", "4h", "previous day"],
    "lower": ["lower", "execution", "15m", "5m", "1m", "refine"],
    "intraday": ["intraday", "session", "15m", "5m", "1m", "london", "new york", "asia"],
    "fractal": ["fractal", "higher", "intermediate", "lower"],
    "daily": ["daily", "previous day", "session"],
    "lower_timeframe_refinement": ["lower timeframe", "refinement", "execution timeframe", "15m", "5m", "1m"],
}


def clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def average(values: Iterable[float]) -> float:
    values_list = list(values)
    if not values_list:
        return 0.0
    return sum(values_list) / len(values_list)


def flatten_strings(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        output: list[str] = []
        for item in value.values():
            output.extend(flatten_strings(item))
        return output
    if isinstance(value, list):
        output: list[str] = []
        for item in value:
            output.extend(flatten_strings(item))
        return output
    if isinstance(value, (int, float, bool)):
        return [str(value)]
    return []


def grade_from_score(score: float) -> str:
    if score >= 0.93:
        return "A"
    if score >= 0.86:
        return "A-"
    if score >= 0.80:
        return "B+"
    if score >= 0.73:
        return "B"
    if score >= 0.66:
        return "B-"
    if score >= 0.58:
        return "C"
    return "D"


def build_spec_text_blob(spec: dict) -> str:
    return " ".join(flatten_strings(spec)).lower()


def load_trader_annotation_cases() -> list[dict]:
    payload = json.loads(TRADER_ANNOTATION_CASES_PATH.read_text(encoding="utf-8"))
    return list(payload.get("cases", []))


def collect_rule_refs(spec: dict) -> list[str]:
    refs: list[str] = []
    for step in spec.get("signal_pipeline", []):
        refs.extend(str(rule_ref) for rule_ref in step.get("rule_refs", []))
    return refs


def build_rule_index(spec: dict) -> set[str]:
    rule_index: set[str] = set()
    for topic_trace in spec.get("topic_rule_trace", []):
        for rule in topic_trace.get("rules", []):
            rule_ref = rule.get("rule_ref")
            if rule_ref:
                rule_index.add(str(rule_ref))
    return rule_index


def score_scope_fidelity(spec: dict) -> tuple[float, list[str]]:
    issues: list[str] = []
    scope_topics = {str(topic) for topic in spec.get("scope_topics", [])}
    direct_topics = {str(topic.get("topic")) for topic in spec.get("direct_topics", []) if topic.get("topic")}
    resolved_topics = {str(topic.get("topic")) for topic in spec.get("resolved_requirements", []) if topic.get("topic")}
    traced_topics = {str(topic.get("topic")) for topic in spec.get("topic_rule_trace", []) if topic.get("topic")}

    if not scope_topics:
        issues.append("No scope_topics were exported for the spec.")
        return 0.0, issues

    trace_coverage = len(scope_topics & traced_topics) / len(scope_topics)
    resolved_coverage = len(scope_topics & (resolved_topics | direct_topics)) / len(scope_topics)
    direct_presence = 1.0 if direct_topics else 0.0

    missing_in_trace = sorted(scope_topics - traced_topics)
    if missing_in_trace:
        issues.append(f"Scope topics missing from topic_rule_trace: {', '.join(missing_in_trace)}")

    missing_in_requirements = sorted(scope_topics - (resolved_topics | direct_topics))
    if missing_in_requirements:
        issues.append(f"Scope topics missing from direct/resolved requirements: {', '.join(missing_in_requirements)}")

    score = clamp((trace_coverage * 0.5) + (resolved_coverage * 0.4) + (direct_presence * 0.1))
    return score, issues


def score_rule_reference_validity(spec: dict) -> tuple[float, list[str]]:
    issues: list[str] = []
    rule_index = build_rule_index(spec)
    refs = collect_rule_refs(spec)

    if not refs:
        issues.append("No signal_pipeline rule_refs were exported for the spec.")
        return 0.0, issues

    valid_refs = [rule_ref for rule_ref in refs if rule_ref in rule_index]
    missing_refs = sorted(set(refs) - rule_index)
    if missing_refs:
        issues.append(f"Missing rule_refs in topic_rule_trace: {', '.join(missing_refs)}")

    score = len(valid_refs) / len(refs)
    return round(score, 4), issues


def score_implementation_richness(spec: dict) -> float:
    input_group_count = len(spec.get("input_groups", []))
    input_count = sum(len(group.get("inputs", [])) for group in spec.get("input_groups", []))
    derived_series_count = len(spec.get("derived_series", []))
    state_model_count = len(spec.get("state_models", []))
    signal_step_count = len(spec.get("signal_pipeline", []))
    visuals_count = len(spec.get("visuals", []))
    alerts_count = len(spec.get("alerts", []))
    proxy_count = len(spec.get("provisional_proxies", []))
    acceptance_check_count = len(spec.get("acceptance_checks", []))

    component_scores = [
        clamp(input_group_count / 4),
        clamp(input_count / 12),
        clamp(derived_series_count / 8),
        clamp(state_model_count / 1),
        clamp(signal_step_count / 6),
        clamp(visuals_count / 4),
        clamp(alerts_count / 4),
        clamp(proxy_count / 4),
        clamp(acceptance_check_count / 6),
    ]
    return round(average(component_scores), 4)


def score_machine_checkability(spec: dict) -> float:
    input_count = sum(len(group.get("inputs", [])) for group in spec.get("input_groups", []))
    threshold_like_inputs = 0
    for group in spec.get("input_groups", []):
        for item in group.get("inputs", []):
            key = str(item.get("key", "")).lower()
            description = str(item.get("description", "")).lower()
            input_type = str(item.get("type", "")).lower()
            if input_type in {"int", "float", "enum"}:
                threshold_like_inputs += 1
                continue
            if any(marker in key or marker in description for marker in ("threshold", "tolerance", "ratio", "score", "fraction", "count", "mode")):
                threshold_like_inputs += 1

    component_scores = [
        clamp(len(spec.get("decision_tables", [])) / 2),
        clamp(len(spec.get("provisional_proxies", [])) / 4),
        clamp(len(spec.get("acceptance_checks", [])) / 6),
        clamp(len(spec.get("state_models", [])) / 1),
        clamp(len(spec.get("signal_pipeline", [])) / 6),
        clamp(threshold_like_inputs / max(1, min(input_count, 10))),
    ]
    return round(average(component_scores), 4)


def score_ambiguity_awareness(spec: dict) -> float:
    open_questions = len(spec.get("open_implementation_questions", []))
    proxies = len(spec.get("provisional_proxies", []))
    checks = len(spec.get("acceptance_checks", []))

    if open_questions == 0:
        question_score = 0.75
    elif 1 <= open_questions <= 3:
        question_score = 1.0
    elif open_questions <= 5:
        question_score = 0.85
    else:
        question_score = 0.65

    structure_score = average(
        [
            clamp(proxies / 4),
            clamp(checks / 6),
        ]
    )
    return round(clamp((question_score * 0.6) + (structure_score * 0.4)), 4)


def score_indicator_spec_understanding(spec: dict) -> dict:
    scope_score, scope_issues = score_scope_fidelity(spec)
    ref_score, ref_issues = score_rule_reference_validity(spec)
    richness_score = score_implementation_richness(spec)
    machine_score = score_machine_checkability(spec)
    ambiguity_score = score_ambiguity_awareness(spec)

    understanding_score = clamp(
        (scope_score * 0.2)
        + (ref_score * 0.3)
        + (richness_score * 0.2)
        + (machine_score * 0.2)
        + (ambiguity_score * 0.1)
    )

    issues = scope_issues + ref_issues
    return {
        "understanding_score": round(understanding_score, 4),
        "grade": grade_from_score(understanding_score),
        "dimensions": {
            "scope_fidelity": round(scope_score, 4),
            "rule_reference_validity": round(ref_score, 4),
            "implementation_richness": round(richness_score, 4),
            "machine_checkability": round(machine_score, 4),
            "ambiguity_awareness": round(ambiguity_score, 4),
        },
        "issues": issues,
    }


def score_timeframe_support(case: dict, spec: dict, spec_blob: str) -> float:
    timeframe_stack = spec.get("implementation_scope", {}).get("timeframe_stack", {})
    timeframe_blob = " ".join(flatten_strings(timeframe_stack)).lower()
    scopes = [str(scope) for scope in case.get("chart_context", {}).get("timeframe_scope", [])]
    if not scopes:
        return 1.0

    matches: list[float] = []
    for scope in scopes:
        if scope == "fractal" and timeframe_stack:
            matches.append(1.0)
            continue
        aliases = TIMEFRAME_ALIASES.get(scope, [scope.replace("_", " ")])
        matches.append(1.0 if any(alias in spec_blob or alias in timeframe_blob for alias in aliases) else 0.0)
    return round(average(matches), 4)


def score_scenario_case(case: dict, spec: dict, trade_model_slug: str) -> dict:
    spec_trade_model_slug = str(spec.get("trade_model", {}).get("slug", ""))
    spec_blob = build_spec_text_blob(spec)
    expected_concepts = SCENARIO_EXPECTATIONS.get((str(case["case_ref"]), trade_model_slug), [])
    contract_defined = bool(expected_concepts)

    model_match = 1.0 if spec_trade_model_slug == trade_model_slug else 0.0
    scope_topics = {str(topic) for topic in spec.get("scope_topics", [])}
    direct_topics = {str(topic.get("topic")) for topic in spec.get("direct_topics", []) if topic.get("topic")}
    resolved_topics = {str(topic.get("topic")) for topic in spec.get("resolved_requirements", []) if topic.get("topic")}
    case_topic = str(case.get("topic", ""))
    topic_match = 1.0 if case_topic in (scope_topics | direct_topics | resolved_topics) else 0.0
    timeframe_match = score_timeframe_support(case, spec, spec_blob)

    matched_concepts: list[str] = []
    missing_concepts: list[str] = []
    for concept in expected_concepts:
        aliases = CONCEPT_ALIASES.get(concept, [concept.replace("_", " ")])
        if any(alias.lower() in spec_blob for alias in aliases):
            matched_concepts.append(concept)
        else:
            missing_concepts.append(concept)

    if not contract_defined:
        return {
            "contract_defined": False,
            "scenario_score": None,
            "grade": "ungraded",
            "dimensions": {
                "model_match": round(model_match, 4),
                "topic_match": round(topic_match, 4),
                "timeframe_match": round(timeframe_match, 4),
                "concept_match": None,
            },
            "expected_concepts": [],
            "matched_concepts": [],
            "missing_concepts": [],
        }

    concept_match = len(matched_concepts) / len(expected_concepts)
    scenario_score = clamp(
        (model_match * 0.1)
        + (topic_match * 0.15)
        + (timeframe_match * 0.1)
        + (concept_match * 0.65)
    )

    return {
        "contract_defined": True,
        "scenario_score": round(scenario_score, 4),
        "grade": grade_from_score(scenario_score),
        "dimensions": {
            "model_match": round(model_match, 4),
            "topic_match": round(topic_match, 4),
            "timeframe_match": round(timeframe_match, 4),
            "concept_match": round(concept_match, 4),
        },
        "expected_concepts": expected_concepts,
        "matched_concepts": matched_concepts,
        "missing_concepts": missing_concepts,
    }


def summarize_understanding(
    topic_scores: list[dict],
    indicator_spec_scores: list[dict],
    scenario_scores: list[dict] | None = None,
) -> dict:
    scenario_scores = scenario_scores or []
    graded_scenarios = [
        float(entry["scenario_score"])
        for entry in scenario_scores
        if entry.get("contract_defined") and entry.get("scenario_score") is not None
    ]
    scenario_contract_count = sum(1 for entry in scenario_scores if entry.get("contract_defined"))
    scenario_total_count = len(scenario_scores)
    topic_average = average(float(entry["understanding_score"]) for entry in topic_scores)
    indicator_spec_average = average(float(entry["understanding_score"]) for entry in indicator_spec_scores)
    scenario_average = average(graded_scenarios)
    scenario_contract_coverage = (
        scenario_contract_count / scenario_total_count if scenario_total_count else 0.0
    )

    if graded_scenarios:
        overall = clamp((topic_average * 0.35) + (indicator_spec_average * 0.35) + (scenario_average * 0.30))
    else:
        overall = clamp((topic_average * 0.45) + (indicator_spec_average * 0.55))

    return {
        "topic_average": round(topic_average, 4),
        "indicator_spec_average": round(indicator_spec_average, 4),
        "scenario_average": round(scenario_average, 4),
        "overall_understanding_score": round(overall, 4),
        "grade": grade_from_score(overall),
        "topic_count": len(topic_scores),
        "indicator_spec_count": len(indicator_spec_scores),
        "scenario_case_count": len(graded_scenarios),
        "scenario_contract_count": scenario_contract_count,
        "scenario_total_count": scenario_total_count,
        "scenario_contract_coverage": round(scenario_contract_coverage, 4),
    }


def build_topic_understanding_entries(connection: sqlite3.Connection) -> list[dict]:
    entries: list[dict] = []
    for topic in build_topic_entries(connection):
        score = evaluate(topic["slug"])
        entries.append(
            {
                "topic": topic["slug"],
                "name": topic["name"],
                "status": topic["status"],
                "source_count": topic["source_count"],
                "rule_count": score.rule_count,
                "understanding_score": score.weighted_score,
                "grade": grade_from_score(score.weighted_score),
                "dimensions": {
                    "grounding": score.grounding_score,
                    "determinism": score.determinism_score,
                    "visual_verification": score.visual_verification_score,
                    "pine_translatability": score.pine_translatability_score,
                },
                "contradiction_penalty": score.contradiction_penalty,
            }
        )
    return entries


def build_indicator_spec_understanding_entries(connection: sqlite3.Connection) -> list[dict]:
    rows = connection.execute(
        """
        SELECT spec_key, topic_slug, name, target_language, status, spec_json
        FROM indicator_specs
        ORDER BY spec_key
        """
    ).fetchall()

    entries: list[dict] = []
    for row in rows:
        spec = json.loads(str(row[5]))
        score = score_indicator_spec_understanding(spec)
        entries.append(
            {
                "spec_key": str(row[0]),
                "name": str(row[2]),
                "topic": str(row[1]),
                "target_language": str(row[3]),
                "status": str(row[4]),
                "profile_slug": spec.get("trader_profile", {}).get("slug"),
                "trade_model_slug": spec.get("trade_model", {}).get("slug"),
                "translation_stage": spec.get("translation_stage"),
                "artifact_path": spec.get("artifact_path"),
                **score,
            }
        )
    return entries


def build_scenario_case_entries(connection: sqlite3.Connection) -> list[dict]:
    rows = connection.execute(
        """
        SELECT spec_key, spec_json
        FROM indicator_specs
        ORDER BY spec_key
        """
    ).fetchall()
    spec_lookup: dict[tuple[str, str], dict] = {}
    spec_key_lookup: dict[tuple[str, str], str] = {}
    for row in rows:
        spec = json.loads(str(row[1]))
        profile_slug = str(spec.get("trader_profile", {}).get("slug", ""))
        trade_model_slug = str(spec.get("trade_model", {}).get("slug", ""))
        spec_lookup[(profile_slug, trade_model_slug)] = spec
        spec_key_lookup[(profile_slug, trade_model_slug)] = str(row[0])

    entries: list[dict] = []
    for case in load_trader_annotation_cases():
        profile_slug = str(case.get("profile_slug", ""))
        for link in case.get("trade_model_links", []):
            trade_model_slug = str(link.get("trade_model", ""))
            spec = spec_lookup.get((profile_slug, trade_model_slug))
            spec_key = spec_key_lookup.get((profile_slug, trade_model_slug))
            if spec is None or spec_key is None:
                entries.append(
                    {
                        "case_ref": case["case_ref"],
                        "profile_slug": profile_slug,
                        "trade_model_slug": trade_model_slug,
                        "relation_type": link.get("relation_type"),
                        "topic": case.get("topic"),
                        "spec_key": None,
                        "scenario_score": 0.0,
                        "grade": "D",
                        "dimensions": {
                            "model_match": 0.0,
                            "topic_match": 0.0,
                            "timeframe_match": 0.0,
                            "concept_match": 0.0,
                        },
                        "expected_concepts": SCENARIO_EXPECTATIONS.get((str(case["case_ref"]), trade_model_slug), []),
                        "matched_concepts": [],
                        "missing_concepts": SCENARIO_EXPECTATIONS.get((str(case["case_ref"]), trade_model_slug), []),
                        "issues": ["No indicator spec exists for this profile + trade-model link."],
                    }
                )
                continue

            scored = score_scenario_case(case, spec, trade_model_slug)
            issues: list[str] = []
            if not scored["contract_defined"]:
                issues.append("No scenario expectation contract defined for this case-model link.")
            if scored["missing_concepts"]:
                issues.append(
                    f"Missing scenario concepts: {', '.join(scored['missing_concepts'])}"
                )
            entries.append(
                {
                    "case_ref": case["case_ref"],
                    "profile_slug": profile_slug,
                    "trade_model_slug": trade_model_slug,
                    "relation_type": link.get("relation_type"),
                    "topic": case.get("topic"),
                    "spec_key": spec_key,
                    **scored,
                    "issues": issues,
                }
            )
    return entries


def build_understanding_report(connection: sqlite3.Connection) -> dict:
    topic_scores = build_topic_understanding_entries(connection)
    indicator_spec_scores = build_indicator_spec_understanding_entries(connection)
    scenario_scores = build_scenario_case_entries(connection)
    summary = summarize_understanding(topic_scores, indicator_spec_scores, scenario_scores)

    weakest_topics = sorted(topic_scores, key=lambda entry: entry["understanding_score"])[:3]
    weakest_specs = sorted(indicator_spec_scores, key=lambda entry: entry["understanding_score"])[:3]
    graded_scenarios = [
        entry for entry in scenario_scores if entry.get("scenario_score") is not None
    ]
    weakest_scenarios = sorted(graded_scenarios, key=lambda entry: entry["scenario_score"])[:5]
    uncontracted_scenarios = [
        entry for entry in scenario_scores if not entry.get("contract_defined")
    ]

    scenario_scores_by_spec: dict[str, list[float]] = {}
    for entry in scenario_scores:
        if entry.get("spec_key") and entry.get("scenario_score") is not None:
            scenario_scores_by_spec.setdefault(str(entry["spec_key"]), []).append(float(entry["scenario_score"]))
    for entry in indicator_spec_scores:
        values = scenario_scores_by_spec.get(entry["spec_key"], [])
        entry["scenario_case_count"] = len(values)
        entry["scenario_average"] = round(average(values), 4) if values else 0.0

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "methodology": {
            "topic_understanding_basis": "rulebook grounding, determinism, visual verification, and Pine translatability via evaluate_rulebook.py",
            "indicator_spec_dimensions": [
                "scope_fidelity",
                "rule_reference_validity",
                "implementation_richness",
                "machine_checkability",
                "ambiguity_awareness",
            ],
            "scenario_case_basis": "Each labeled trader annotation baseline is matched against the linked indicator spec and scored for topic match, timeframe support, and explicit concept coverage.",
            "scenario_contract_policy": "Scenario links without an explicit expectation contract are marked `ungraded` instead of receiving free credit.",
            "overall_weighting": {
                "topics": 0.35,
                "indicator_specs": 0.35,
                "scenario_cases": 0.30,
            },
        },
        "overall": summary,
        "weakest_topics": weakest_topics,
        "weakest_indicator_specs": weakest_specs,
        "weakest_scenarios": weakest_scenarios,
        "uncontracted_scenarios": uncontracted_scenarios,
        "topics": topic_scores,
        "indicator_specs": indicator_spec_scores,
        "scenario_cases": scenario_scores,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Export a repo-native understanding report for topics and indicator specs.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        report = build_understanding_report(connection)

    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output_path),
                "overall_understanding_score": report["overall"]["overall_understanding_score"],
                "grade": report["overall"]["grade"],
                "topic_count": report["overall"]["topic_count"],
                "indicator_spec_count": report["overall"]["indicator_spec_count"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
