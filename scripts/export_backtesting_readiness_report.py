from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from phase_one_focus import (
    build_phase_one_focus,
    filter_extra_training_labels,
    split_training_labels,
)
from export_model_training_surface import (
    build_training_example,
    extract_key_paths,
    flatten_strings,
    load_trader_records,
    summarize_training_surface,
)
from export_topic_model_report import (
    build_topic_entries,
    build_trader_profile_entries,
)
from export_understanding_report import build_understanding_report, grade_from_score


ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "research.db"
DEFAULT_OUTPUT = ROOT / "results" / "backtesting_readiness_report.json"
RESEARCH_BACKLOG_PATH = ROOT / "results" / "research_backlog.json"
TTRADES_MANIFEST_PATH = ROOT / "data" / "ttrades_manifest.json"
TRADER_ANNOTATION_CASES_PATH = ROOT / "data" / "trader_annotation_cases.json"

SPEC_STAGE_SCORES = {
    "candidate": 0.35,
    "draft": 0.6,
    "reviewed": 0.8,
    "validated": 0.9,
    "verified": 0.9,
    "production": 1.0,
    "implemented": 1.0,
    "live": 1.0,
}

ENTRY_MARKERS = (
    "entry",
    "confirmation",
    "confirm",
    "cisd",
    "protected swing",
    "setup",
)
RISK_MARKERS = (
    "invalidation",
    "risk",
    "stop",
    "protected swing",
    "thesis failure",
)
TARGET_MARKERS = (
    "target",
    "objective",
    "liquidity",
    "take profit",
)
ANTI_LOOKAHEAD_MARKERS = (
    "bar close",
    "bar-close",
    "anti repaint",
    "anti-repaint",
    "intrabar",
    "request-security",
)
SESSION_MARKERS = (
    "session",
    "kill zone",
    "kill-zone",
    "timeframe",
    "higher",
    "lower",
    "intraday",
)
COST_MODEL_MARKERS = (
    "slippage",
    "commission",
    "spread",
    "transaction cost",
    "fees",
    "market impact",
)
BACKTEST_SOURCE_MARKERS = ("backtest", "replay")
HISTORICAL_HARNESS_PATTERNS = (
    "scripts/*backtest*.py",
    "scripts/*replay*.py",
    "runtime/*backtest*.py",
    "runtime/*replay*.py",
)
IGNORED_HARNESS_NAME_MARKERS = (
    "export_",
    "readiness_report",
)


def clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def average(values: Iterable[float]) -> float:
    values_list = list(values)
    if not values_list:
        return 0.0
    return sum(values_list) / len(values_list)


def build_text_blob(value: object) -> str:
    return " ".join(flatten_strings(value)).lower()


def contains_any_marker(text: str, markers: Iterable[str]) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in markers)


def count_research_runs(connection: sqlite3.Connection) -> int:
    try:
        return int(connection.execute("SELECT COUNT(*) FROM research_runs").fetchone()[0])
    except sqlite3.OperationalError:
        return 0


def load_manifest_case_refs() -> set[str]:
    payload = json.loads(TRADER_ANNOTATION_CASES_PATH.read_text(encoding="utf-8"))
    return {
        str(case["case_ref"])
        for case in payload.get("cases", [])
        if str(case.get("case_ref", "")).strip()
    }


def build_manifest_sync_snapshot(connection: sqlite3.Connection) -> dict:
    manifest_case_refs = load_manifest_case_refs()
    records = load_trader_records(connection)
    db_case_refs = {str(record["case_ref"]) for record in records}
    missing_in_db = sorted(manifest_case_refs - db_case_refs)
    extra_in_db = sorted(db_case_refs - manifest_case_refs)
    union_count = len(manifest_case_refs | db_case_refs)
    sync_score = (
        1.0
        if union_count == 0
        else 1.0 - ((len(missing_in_db) + len(extra_in_db)) / union_count)
    )
    return {
        "manifest_case_count": len(manifest_case_refs),
        "db_case_count": len(db_case_refs),
        "missing_in_db": missing_in_db,
        "extra_in_db": extra_in_db,
        "sync_score": round(clamp(sync_score), 4),
    }


def build_training_examples(connection: sqlite3.Connection) -> list[dict]:
    records = load_trader_records(connection)
    examples: list[dict] = []
    for record in records:
        for trade_model_link in record.get("annotation_trade_models", []):
            examples.append(build_training_example(record, trade_model_link))
    return examples


def classification_progress(task: dict) -> float:
    total_progress = clamp(
        float(task.get("total_examples", 0))
        / max(1, int(task.get("recommended_total_examples", 1)))
    )
    class_progress = clamp(
        float(task.get("minimum_examples_per_class", 0))
        / max(1, int(task.get("recommended_examples_per_class", 1)))
    )
    diversity_progress = 1.0 if int(task.get("class_count", 0)) >= 2 else 0.0
    return round(average([total_progress, class_progress, diversity_progress]), 4)


def load_indicator_specs(connection: sqlite3.Connection) -> list[dict]:
    rows = connection.execute(
        """
        SELECT spec_key, topic_slug, name, status, spec_json
        FROM indicator_specs
        ORDER BY spec_key
        """
    ).fetchall()

    specs: list[dict] = []
    for spec_key, topic_slug, name, status, spec_json in rows:
        payload = json.loads(str(spec_json))
        specs.append(
            {
                "spec_key": str(spec_key),
                "topic": str(topic_slug),
                "name": str(name),
                "status": str(status),
                "trade_model_slug": str(
                    payload.get("trade_model", {}).get("slug", "")
                ).strip(),
                "profile_slug": str(
                    payload.get("trader_profile", {}).get("slug", "")
                ).strip(),
                "spec": payload,
            }
        )
    return specs


def score_backtesting_spec(entry: dict) -> dict:
    spec = entry["spec"]
    spec_blob = build_text_blob(spec)
    input_blob = build_text_blob(spec.get("input_groups", []))
    acceptance_blob = build_text_blob(spec.get("acceptance_checks", []))
    translation_blob = build_text_blob(spec.get("pine_translation_hints", []))
    decision_blob = build_text_blob(spec.get("decision_tables", []))
    implementation_scope = spec.get("implementation_scope", {}) or {}
    pine_outline = spec.get("pine_program_outline", {}) or {}
    direct_topics = spec.get("direct_topics", []) or []
    resolved_topics = spec.get("resolved_requirements", []) or []

    topic_mentions = {
        str(item.get("topic", "")).strip()
        for item in [*direct_topics, *resolved_topics]
        if str(item.get("topic", "")).strip()
    }
    role_mentions = {
        str(item.get("role", "")).strip()
        for item in direct_topics
        if str(item.get("role", "")).strip()
    }

    entry_definition = average(
        [
            1.0 if spec.get("signal_pipeline") else 0.0,
            1.0 if spec.get("decision_tables") else 0.0,
            1.0 if spec.get("state_models") else 0.0,
            1.0 if contains_any_marker(spec_blob, ENTRY_MARKERS) else 0.0,
        ]
    )
    risk_definition = average(
        [
            1.0
            if "invalidation" in topic_mentions or "risk" in role_mentions
            else 0.0,
            1.0 if contains_any_marker(input_blob, RISK_MARKERS) else 0.0,
            1.0 if contains_any_marker(spec_blob, RISK_MARKERS) else 0.0,
            1.0 if contains_any_marker(acceptance_blob, RISK_MARKERS) else 0.0,
        ]
    )
    target_definition = average(
        [
            1.0 if contains_any_marker(input_blob, TARGET_MARKERS) else 0.0,
            1.0 if contains_any_marker(decision_blob, TARGET_MARKERS) else 0.0,
            1.0 if contains_any_marker(spec_blob, TARGET_MARKERS) else 0.0,
        ]
    )
    anti_lookahead = average(
        [
            1.0 if implementation_scope.get("anti_repaint_baseline") else 0.0,
            1.0 if pine_outline.get("anti_repaint_baseline") else 0.0,
            1.0
            if contains_any_marker(
                " ".join([acceptance_blob, translation_blob, spec_blob]),
                ANTI_LOOKAHEAD_MARKERS,
            )
            else 0.0,
        ]
    )
    session_timeframe = average(
        [
            1.0 if implementation_scope.get("timeframe_stack") else 0.0,
            1.0 if contains_any_marker(input_blob, SESSION_MARKERS) else 0.0,
            1.0 if contains_any_marker(spec_blob, SESSION_MARKERS) else 0.0,
        ]
    )
    cost_model = average(
        [
            1.0 if contains_any_marker(input_blob, COST_MODEL_MARKERS) else 0.0,
            1.0 if contains_any_marker(spec_blob, COST_MODEL_MARKERS) else 0.0,
            1.0 if contains_any_marker(acceptance_blob, COST_MODEL_MARKERS) else 0.0,
        ]
    )
    rules_backtestability = average(
        [
            entry_definition,
            risk_definition,
            target_definition,
            anti_lookahead,
            session_timeframe,
        ]
    )

    return {
        "spec_key": entry["spec_key"],
        "topic": entry["topic"],
        "name": entry["name"],
        "status": entry["status"],
        "trade_model_slug": entry["trade_model_slug"],
        "entry_definition_score": round(entry_definition, 4),
        "risk_definition_score": round(risk_definition, 4),
        "target_definition_score": round(target_definition, 4),
        "anti_lookahead_score": round(anti_lookahead, 4),
        "session_timeframe_score": round(session_timeframe, 4),
        "cost_model_score": round(cost_model, 4),
        "rules_backtestability_score": round(rules_backtestability, 4),
    }


def summarize_indicator_spec_backtesting(spec_entries: list[dict]) -> dict:
    scored_entries = [score_backtesting_spec(entry) for entry in spec_entries]
    status_counts: dict[str, int] = {}
    stage_scores: list[float] = []
    spec_models: set[str] = set()

    for entry in spec_entries:
        status = str(entry.get("status", "unknown")).strip().lower() or "unknown"
        status_counts[status] = status_counts.get(status, 0) + 1
        stage_scores.append(SPEC_STAGE_SCORES.get(status, 0.25))
        trade_model_slug = str(entry.get("trade_model_slug", "")).strip()
        if trade_model_slug:
            spec_models.add(trade_model_slug)

    non_draft_status_count = sum(
        count
        for status, count in status_counts.items()
        if status not in {"candidate", "draft", "unknown"}
    )
    weakest_specs = sorted(
        scored_entries,
        key=lambda item: item["rules_backtestability_score"],
    )[:3]

    return {
        "count": len(scored_entries),
        "status_counts": dict(sorted(status_counts.items())),
        "stage_score": round(average(stage_scores), 4),
        "non_draft_status_count": non_draft_status_count,
        "trade_model_slugs": sorted(spec_models),
        "entry_definition_average": round(
            average(entry["entry_definition_score"] for entry in scored_entries), 4
        ),
        "risk_definition_average": round(
            average(entry["risk_definition_score"] for entry in scored_entries), 4
        ),
        "target_definition_average": round(
            average(entry["target_definition_score"] for entry in scored_entries), 4
        ),
        "anti_lookahead_average": round(
            average(entry["anti_lookahead_score"] for entry in scored_entries), 4
        ),
        "session_timeframe_average": round(
            average(entry["session_timeframe_score"] for entry in scored_entries), 4
        ),
        "cost_model_average": round(
            average(entry["cost_model_score"] for entry in scored_entries), 4
        ),
        "rules_backtestability_average": round(
            average(entry["rules_backtestability_score"] for entry in scored_entries), 4
        ),
        "weakest_specs": weakest_specs,
    }


def summarize_case_backtesting(records: list[dict]) -> dict:
    case_count = len(records)
    decision_count = 0
    reason_count = 0
    entry_logic_count = 0
    trade_case_count = 0
    no_trade_case_count = 0
    trade_case_exit_count = 0
    filter_case_reason_count = 0
    invalidation_case_count = 0
    target_case_count = 0

    for record in records:
        annotation = record.get("annotation") or {}
        outcome = record.get("outcome") or {}
        notes = str(record.get("notes", ""))
        key_blob = " ".join(extract_key_paths(annotation)).lower()
        annotation_blob = build_text_blob(annotation)
        combined_blob = " ".join([key_blob, annotation_blob, notes.lower()])

        decision = str(outcome.get("decision", "")).strip().lower()
        reason = str(outcome.get("reason", "")).strip()

        has_decision = bool(decision)
        has_reason = bool(reason)
        has_entry_logic = contains_any_marker(combined_blob, ENTRY_MARKERS)
        has_invalidation = contains_any_marker(combined_blob, RISK_MARKERS)
        has_target = contains_any_marker(combined_blob, TARGET_MARKERS)

        if has_decision:
            decision_count += 1
        if has_reason:
            reason_count += 1
        if has_entry_logic:
            entry_logic_count += 1
        if has_invalidation:
            invalidation_case_count += 1
        if has_target:
            target_case_count += 1

        if decision == "trade":
            trade_case_count += 1
            if has_invalidation and has_target:
                trade_case_exit_count += 1
        elif decision == "no_trade":
            no_trade_case_count += 1
            if has_reason and (has_entry_logic or "model_action" in key_blob or "preferred_action" in key_blob):
                filter_case_reason_count += 1

    decision_coverage = decision_count / max(1, case_count)
    reason_coverage = reason_count / max(1, case_count)
    entry_logic_coverage = entry_logic_count / max(1, case_count)
    trade_case_exit_coverage = trade_case_exit_count / max(1, trade_case_count)
    filter_case_reason_coverage = (
        filter_case_reason_count / max(1, no_trade_case_count)
        if no_trade_case_count
        else 1.0
    )
    case_backtestability_score = average(
        [
            decision_coverage,
            reason_coverage,
            entry_logic_coverage,
            trade_case_exit_coverage,
            filter_case_reason_coverage,
        ]
    )

    return {
        "case_count": case_count,
        "trade_case_count": trade_case_count,
        "no_trade_case_count": no_trade_case_count,
        "decision_coverage": round(decision_coverage, 4),
        "reason_coverage": round(reason_coverage, 4),
        "entry_logic_coverage": round(entry_logic_coverage, 4),
        "trade_case_exit_coverage": round(trade_case_exit_coverage, 4),
        "filter_case_reason_coverage": round(filter_case_reason_coverage, 4),
        "invalidation_case_count": invalidation_case_count,
        "target_case_count": target_case_count,
        "case_backtestability_score": round(case_backtestability_score, 4),
    }


def load_backtesting_source_snapshot() -> dict:
    source_count = 0
    source_titles: list[str] = []
    missing_text_artifacts: list[str] = []

    if TTRADES_MANIFEST_PATH.exists():
        manifest_payload = json.loads(TTRADES_MANIFEST_PATH.read_text(encoding="utf-8"))
        for item in manifest_payload.get("items", []):
            haystack = " ".join(
                [
                    str(item.get("title", "")),
                    str(item.get("url", "")),
                    str(item.get("canonical_url", "")),
                ]
            ).lower()
            if contains_any_marker(haystack, BACKTEST_SOURCE_MARKERS):
                source_count += 1
                source_titles.append(str(item.get("title", "")))

    if RESEARCH_BACKLOG_PATH.exists():
        backlog_payload = json.loads(RESEARCH_BACKLOG_PATH.read_text(encoding="utf-8"))
        for item in backlog_payload.get("article_sources_missing_text_artifacts", []):
            haystack = " ".join(
                [
                    str(item.get("slug", "")),
                    str(item.get("title", "")),
                    str(item.get("canonical_url", "")),
                ]
            ).lower()
            if contains_any_marker(haystack, BACKTEST_SOURCE_MARKERS):
                missing_text_artifacts.append(str(item.get("title", "")))

    artifact_coverage_score = (
        clamp((source_count - len(missing_text_artifacts)) / max(1, source_count))
        if source_count
        else 0.0
    )

    return {
        "source_count": source_count,
        "source_titles": sorted(source_titles),
        "missing_text_artifacts": sorted(missing_text_artifacts),
        "presence_score": 1.0 if source_count else 0.0,
        "artifact_coverage_score": round(artifact_coverage_score, 4),
    }


def build_historical_harness_snapshot() -> dict:
    discovered: list[str] = []
    for pattern in HISTORICAL_HARNESS_PATTERNS:
        for path in ROOT.glob(pattern):
            name = path.name.lower()
            if any(marker in name for marker in IGNORED_HARNESS_NAME_MARKERS):
                continue
            discovered.append(str(path))

    discovered = sorted(set(discovered))
    runner_present = any("backtest" in Path(path).name.lower() for path in discovered)
    analyzer_present = any("analy" in Path(path).name.lower() for path in discovered)
    replay_present = any("replay" in Path(path).name.lower() for path in discovered)

    return {
        "discovered_artifacts": discovered,
        "runner_present": runner_present,
        "analyzer_present": analyzer_present,
        "replay_present": replay_present,
        "harness_score": round(
            average(
                [
                    1.0 if runner_present else 0.0,
                    1.0 if analyzer_present else 0.0,
                    1.0 if replay_present else 0.0,
                ]
            ),
            4,
        ),
    }


def finalize_stage(
    *,
    name: str,
    base_score: float,
    score_breakdown: dict[str, float],
    threshold: float,
    caps: list[tuple[bool, float, str]],
    blockers: list[str],
    recommendation: str,
) -> dict:
    final_score = clamp(base_score)
    caps_applied: list[dict] = []
    for condition, cap_score, reason in caps:
        if condition and final_score > cap_score:
            final_score = cap_score
            caps_applied.append({"cap": round(cap_score, 4), "reason": reason})

    ready = final_score >= threshold and not blockers
    if ready and final_score >= 0.86:
        verdict = "go"
    elif ready:
        verdict = "cautious_go"
    elif final_score >= 0.58:
        verdict = "not_yet"
    else:
        verdict = "hard_no"

    return {
        "stage": name,
        "base_score": round(base_score, 4),
        "score": round(final_score, 4),
        "grade": grade_from_score(final_score),
        "readiness_threshold": threshold,
        "ready": ready,
        "verdict": verdict,
        "score_breakdown": {key: round(value, 4) for key, value in score_breakdown.items()},
        "caps_applied": caps_applied,
        "blockers": blockers,
        "recommendation": recommendation,
    }


def build_stage_readiness(snapshot: dict) -> dict[str, dict]:
    understanding_overall = float(snapshot["understanding"]["overall"]["overall_understanding_score"])
    scenario_average = float(snapshot["understanding"]["overall"]["scenario_average"])
    scenario_contract_coverage = float(snapshot["understanding"]["overall"]["scenario_contract_coverage"])
    machine_checkability_average = float(snapshot["indicator_spec_machine_checkability_average"])
    topic_coverage_score = float(snapshot["topic_coverage_score"])
    research_logging_score = float(snapshot["research_logging_score"])
    backlog_visibility_score = float(snapshot["backlog_visibility_score"])
    indicator_spec_coverage = float(snapshot["indicator_spec_coverage"])
    source_presence_score = float(snapshot["backtesting_sources"]["presence_score"])
    source_artifact_score = float(snapshot["backtesting_sources"]["artifact_coverage_score"])
    harness_score = float(snapshot["historical_harness"]["harness_score"])
    manifest_sync_score = float(snapshot["annotation_manifest_sync"]["sync_score"])
    case_snapshot = snapshot["backtesting_cases"]
    spec_snapshot = snapshot["backtesting_specs"]
    training_surface = snapshot["training_surface"]

    rules_backtestability = float(spec_snapshot["rules_backtestability_average"])
    risk_definition = float(spec_snapshot["risk_definition_average"])
    target_definition = float(spec_snapshot["target_definition_average"])
    anti_lookahead = float(spec_snapshot["anti_lookahead_average"])
    session_timeframe = float(spec_snapshot["session_timeframe_average"])
    cost_model = float(spec_snapshot["cost_model_average"])
    case_backtestability = float(case_snapshot["case_backtestability_score"])
    decision_coverage = float(case_snapshot["decision_coverage"])
    reason_coverage = float(case_snapshot["reason_coverage"])
    entry_logic_coverage = float(case_snapshot["entry_logic_coverage"])
    trade_case_exit_coverage = float(case_snapshot["trade_case_exit_coverage"])
    filter_case_reason_coverage = float(case_snapshot["filter_case_reason_coverage"])
    indicator_spec_stage_score = float(spec_snapshot["stage_score"])
    label_volume_score = float(training_surface["label_volume_score"])
    outcome_label_coverage = float(training_surface["outcome_label_coverage"])
    no_trade_filter_score = 1.0 if training_surface["task_readiness"]["no_trade_filter"]["ready"] else 0.0
    ready_indicator_binary_coverage = float(training_surface["ready_indicator_binary_coverage"])
    trade_model_multiclass_progress = float(training_surface["trade_model_classification_progress"])
    relation_type_multiclass_progress = float(training_surface["relation_type_classification_progress"])
    ready_indicator_binary_count = int(training_surface["ready_indicator_binary_count"])

    foundation_breakdown = {
        "understanding": understanding_overall * 0.25,
        "scenario_contract_coverage": scenario_contract_coverage * 0.15,
        "topic_coverage": topic_coverage_score * 0.10,
        "indicator_spec_coverage": indicator_spec_coverage * 0.10,
        "machine_checkability": machine_checkability_average * 0.10,
        "research_logging": research_logging_score * 0.10,
        "backlog_visibility": backlog_visibility_score * 0.05,
        "backtesting_source_presence": source_presence_score * 0.10,
        "case_decision_coverage": decision_coverage * 0.05,
    }
    foundation_blockers: list[str] = []
    if research_logging_score == 0.0:
        foundation_blockers.append("No research runs are logged yet.")
    if source_presence_score == 0.0:
        foundation_blockers.append("No explicit backtesting methodology source is tracked in the corpus yet.")
    historical_foundation = finalize_stage(
        name="historical_backtesting_research_foundation",
        base_score=sum(foundation_breakdown.values()),
        score_breakdown=foundation_breakdown,
        threshold=0.73,
        caps=[],
        blockers=foundation_blockers,
        recommendation="The rules and cases are already strong enough to focus the next loop on historical replay discipline instead of live-trading ambition.",
    )

    manual_breakdown = {
        "understanding": understanding_overall * 0.18,
        "scenario_quality": scenario_average * 0.15,
        "scenario_contract_coverage": scenario_contract_coverage * 0.10,
        "rules_backtestability": rules_backtestability * 0.12,
        "risk_definition": risk_definition * 0.08,
        "target_definition": target_definition * 0.08,
        "anti_lookahead": anti_lookahead * 0.10,
        "entry_logic_coverage": entry_logic_coverage * 0.06,
        "trade_case_exit_coverage": trade_case_exit_coverage * 0.05,
        "filter_case_reason_coverage": filter_case_reason_coverage * 0.05,
        "case_reason_coverage": reason_coverage * 0.08,
        "source_artifact_coverage": source_artifact_score * 0.05,
    }
    manual_blockers: list[str] = []
    if scenario_contract_coverage < 0.8:
        manual_blockers.append("Scenario expectation contracts do not yet cover most case-model links.")
    manual_replay = finalize_stage(
        name="manual_chart_replay_understanding",
        base_score=sum(manual_breakdown.values()),
        score_breakdown=manual_breakdown,
        threshold=0.73,
        caps=[],
        blockers=manual_blockers,
        recommendation="Use the current specs and durable cases for bar-by-bar manual replay worksheets: bias, anchor, confirmation, invalidation, target, and stand-aside reasoning.",
    )

    rules_backtest_breakdown = {
        "understanding": understanding_overall * 0.08,
        "scenario_quality": scenario_average * 0.07,
        "machine_checkability": machine_checkability_average * 0.12,
        "rules_backtestability": rules_backtestability * 0.14,
        "risk_definition": risk_definition * 0.08,
        "target_definition": target_definition * 0.08,
        "anti_lookahead": anti_lookahead * 0.10,
        "case_backtestability": case_backtestability * 0.10,
        "outcome_label_coverage": outcome_label_coverage * 0.08,
        "indicator_spec_stage": indicator_spec_stage_score * 0.05,
        "manifest_sync": manifest_sync_score * 0.05,
        "source_artifact_coverage": source_artifact_score * 0.05,
        "cost_model": cost_model * 0.04,
        "historical_harness": harness_score * 0.04,
        "session_timeframe": session_timeframe * 0.05,
    }
    rules_backtest_blockers: list[str] = []
    if harness_score == 0.0:
        rules_backtest_blockers.append("No repeatable historical backtest or replay harness exists yet.")
    if cost_model == 0.0:
        rules_backtest_blockers.append("No commission, spread, slippage, or transaction-cost assumptions are encoded yet.")
    if source_artifact_score == 0.0 and source_presence_score > 0.0:
        rules_backtest_blockers.append("The backtesting methodology article exists in the corpus manifest but is still missing a local text artifact.")
    if spec_snapshot["non_draft_status_count"] == 0:
        rules_backtest_blockers.append("All indicator specs are still draft-only.")
    rules_backtest_caps = [
        (
            harness_score == 0.0,
            0.66,
            "Historical rules are strong, but without a repeatable harness there is still no honest structured backtest stage.",
        ),
        (
            cost_model == 0.0,
            0.66,
            "A rules backtest without transaction costs would overstate quality immediately.",
        ),
        (
            spec_snapshot["non_draft_status_count"] == 0,
            0.69,
            "Draft-only specs are enough for replay practice, not enough for confident structured backtesting claims.",
        ),
    ]
    rules_backtest = finalize_stage(
        name="rules_based_historical_backtesting",
        base_score=sum(rules_backtest_breakdown.values()),
        score_breakdown=rules_backtest_breakdown,
        threshold=0.73,
        caps=rules_backtest_caps,
        blockers=rules_backtest_blockers,
        recommendation="Build a minimal event-driven historical harness next: bar-close rules only, explicit entry/stop/target events, session filters, and configurable transaction costs.",
    )

    model_backtest_breakdown = {
        "understanding": understanding_overall * 0.05,
        "rules_backtestability": rules_backtestability * 0.08,
        "anti_lookahead": anti_lookahead * 0.08,
        "case_backtestability": case_backtestability * 0.07,
        "historical_harness": harness_score * 0.12,
        "cost_model": cost_model * 0.05,
        "label_volume": label_volume_score * 0.10,
        "outcome_label_coverage": outcome_label_coverage * 0.12,
        "no_trade_filter": no_trade_filter_score * 0.12,
        "ready_binary_coverage": ready_indicator_binary_coverage * 0.12,
        "ready_binary_count": clamp(ready_indicator_binary_count / 3) * 0.08,
        "trade_model_multiclass_progress": trade_model_multiclass_progress * 0.05,
        "relation_type_multiclass_progress": relation_type_multiclass_progress * 0.04,
        "indicator_spec_stage": indicator_spec_stage_score * 0.05,
        "manifest_sync": manifest_sync_score * 0.05,
    }
    model_backtest_blockers: list[str] = []
    if harness_score == 0.0:
        model_backtest_blockers.append("No historical backtest harness exists to score model outputs against market reality.")
    if cost_model == 0.0:
        model_backtest_blockers.append("No transaction-cost model is encoded yet.")
    if spec_snapshot["non_draft_status_count"] == 0:
        model_backtest_blockers.append("All indicator specs remain draft-only.")
    if ready_indicator_binary_count == 0:
        model_backtest_blockers.append("No indicator-ready trade model is baseline-ready for narrow historical model tests.")
    model_backtest_caps = [
        (
            harness_score == 0.0,
            0.58,
            "Model-assisted historical testing should wait for a rules-first harness, otherwise the score has nothing durable to compare against.",
        ),
        (
            cost_model == 0.0,
            0.62,
            "A model backtest without spreads, slippage, or fees would be structurally misleading.",
        ),
        (
            spec_snapshot["non_draft_status_count"] == 0,
            0.64,
            "Draft-only specs should stay in historical exploration mode, not in claimed model-validation mode.",
        ),
    ]
    model_backtest = finalize_stage(
        name="model_assisted_historical_backtesting",
        base_score=sum(model_backtest_breakdown.values()),
        score_breakdown=model_backtest_breakdown,
        threshold=0.73,
        caps=model_backtest_caps,
        blockers=model_backtest_blockers,
        recommendation="Once the harness exists, keep model-assisted historical tests narrow: `continuation_entry_model` one-vs-rest plus the `trade` vs `no_trade` filter before any broader label-space work.",
    )

    return {
        "historical_backtesting_research_foundation": historical_foundation,
        "manual_chart_replay_understanding": manual_replay,
        "rules_based_historical_backtesting": rules_backtest,
        "model_assisted_historical_backtesting": model_backtest,
    }


def build_snapshot(connection: sqlite3.Connection) -> dict:
    topic_entries = build_topic_entries(connection)
    trader_profile_entries = build_trader_profile_entries(connection)
    understanding_report = build_understanding_report(connection)
    training_examples = build_training_examples(connection)
    training_surface = summarize_training_surface(training_examples)
    research_run_count = count_research_runs(connection)
    manifest_sync = build_manifest_sync_snapshot(connection)
    records = load_trader_records(connection)
    loaded_specs = load_indicator_specs(connection)
    backtesting_specs = summarize_indicator_spec_backtesting(loaded_specs)
    backtesting_cases = summarize_case_backtesting(records)
    backtesting_sources = load_backtesting_source_snapshot()
    historical_harness = build_historical_harness_snapshot()

    indicator_ready_models = sorted(
        {
            str(trade_model["trade_model"])
            for profile in trader_profile_entries
            for trade_model in profile.get("trade_models", [])
            if trade_model.get("indicator_ready")
        }
    )
    spec_trade_models = set(backtesting_specs["trade_model_slugs"])
    training_trade_models = set(
        str(label) for label in training_surface.get("trade_model_counts", {}).keys()
    )
    ready_binary_trade_models = sorted(
        {
            str(task["trade_model"])
            for task in training_surface.get("trade_model_binary_tasks", [])
            if task.get("ready")
        }
    )
    machine_checkability_average = average(
        float(entry["dimensions"]["machine_checkability"])
        for entry in understanding_report.get("indicator_specs", [])
    )
    indicator_spec_coverage = (
        len(spec_trade_models & set(indicator_ready_models)) / len(indicator_ready_models)
        if indicator_ready_models
        else 0.0
    )
    all_extra_training_labels = filter_extra_training_labels(
        training_trade_models - set(backtesting_specs["trade_model_slugs"])
    )
    active_extra_training_labels_value, deferred_extra_training_labels_value = split_training_labels(
        all_extra_training_labels
    )
    ready_indicator_binary_coverage = (
        len(set(ready_binary_trade_models) & set(indicator_ready_models))
        / len(indicator_ready_models)
        if indicator_ready_models
        else 0.0
    )

    training_surface["label_volume_score"] = round(
        clamp(training_surface["example_count"] / 25),
        4,
    )
    training_surface["outcome_label_coverage"] = round(
        training_surface["labeled_outcome_count"] / max(1, training_surface["example_count"]),
        4,
    )
    training_surface["trade_model_classification_progress"] = classification_progress(
        training_surface["task_readiness"]["trade_model_classification"]
    )
    training_surface["relation_type_classification_progress"] = classification_progress(
        training_surface["task_readiness"]["relation_type_classification"]
    )
    training_surface["ready_indicator_binary_count"] = len(
        set(ready_binary_trade_models) & set(indicator_ready_models)
    )
    training_surface["ready_indicator_binary_coverage"] = round(
        ready_indicator_binary_coverage,
        4,
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_run_count": research_run_count,
        "research_logging_score": round(
            clamp(research_run_count / max(1, len(topic_entries))),
            4,
        ),
        "backlog_visibility_score": 1.0 if RESEARCH_BACKLOG_PATH.exists() else 0.0,
        "topic_count": len(topic_entries),
        "topic_coverage_score": round(clamp(len(topic_entries) / 14), 4),
        "indicator_ready_trade_models": indicator_ready_models,
        "indicator_spec_coverage": round(indicator_spec_coverage, 4),
        "indicator_spec_machine_checkability_average": round(machine_checkability_average, 4),
        "training_surface": training_surface,
        "understanding": {
            "overall": understanding_report["overall"],
            "weakest_topics": understanding_report["weakest_topics"],
            "weakest_indicator_specs": understanding_report["weakest_indicator_specs"],
            "weakest_scenarios": understanding_report["weakest_scenarios"],
            "uncontracted_scenarios": understanding_report["uncontracted_scenarios"],
        },
        "backtesting_specs": backtesting_specs,
        "backtesting_cases": backtesting_cases,
        "backtesting_sources": backtesting_sources,
        "historical_harness": historical_harness,
        "annotation_manifest_sync": manifest_sync,
        "label_space": {
            "training_trade_models": sorted(training_trade_models),
            "indicator_spec_trade_models": backtesting_specs["trade_model_slugs"],
            "all_extra_training_labels_without_indicator_specs": all_extra_training_labels,
            "extra_training_labels_without_indicator_specs": active_extra_training_labels_value,
            "deferred_training_labels_without_indicator_specs": deferred_extra_training_labels_value,
            "ready_binary_trade_models": ready_binary_trade_models,
        },
        "phase_one_focus": build_phase_one_focus(
            training_surface,
            indicator_ready_trade_models=indicator_ready_models,
        ),
    }


def active_extra_training_labels(snapshot: dict) -> list[str]:
    label_space = snapshot.get("label_space", {})
    labels = label_space.get("all_extra_training_labels_without_indicator_specs")
    if labels is None:
        labels = label_space.get("extra_training_labels_without_indicator_specs", [])
    active_labels, _ = split_training_labels(labels)
    return active_labels


def build_global_blockers(snapshot: dict) -> list[str]:
    blockers: list[str] = []
    if snapshot["historical_harness"]["harness_score"] == 0.0:
        blockers.append("No repeatable historical backtest or replay harness exists in the repo.")
    if snapshot["backtesting_sources"]["presence_score"] > 0.0 and snapshot["backtesting_sources"]["artifact_coverage_score"] == 0.0:
        blockers.append("The TTrades backtesting primer is known in the corpus but still missing a local text artifact.")
    if snapshot["backtesting_specs"]["cost_model_average"] == 0.0:
        blockers.append("No slippage, commission, spread, or transaction-cost model is encoded across the current specs.")
    if snapshot["backtesting_specs"]["non_draft_status_count"] == 0:
        blockers.append("All indicator specs are still draft scaffolds rather than validated backtest contracts.")
    if snapshot["training_surface"]["ready_indicator_binary_count"] < 2:
        blockers.append("Only one indicator-ready trade model is currently baseline-ready for narrow historical model scoring.")
    if snapshot["understanding"]["overall"]["scenario_contract_coverage"] < 1.0:
        blockers.append("Scenario expectation contracts are not fully closed yet.")
    if active_extra_training_labels(snapshot):
        blockers.append(
            "Training labels still include models outside the indicator-spec set: "
            + ", ".join(active_extra_training_labels(snapshot))
        )
    return blockers


def build_next_actions(snapshot: dict) -> list[str]:
    actions: list[str] = []
    if snapshot["backtesting_sources"]["artifact_coverage_score"] < 1.0 and snapshot["backtesting_sources"]["source_count"] > 0:
        actions.append(
            "Ingest the tracked backtesting methodology source into local artifacts so the historical-testing workflow is grounded in the same repo-native evidence as the strategy rules."
        )
    if snapshot["historical_harness"]["harness_score"] == 0.0:
        actions.append(
            "Add a minimal historical replay/backtest harness with next-bar execution, explicit entry/stop/target events, and session-aware rule evaluation."
        )
    if snapshot["backtesting_specs"]["cost_model_average"] == 0.0:
        actions.append(
            "Encode realistic transaction-cost assumptions explicitly: spread, slippage, commission or fees, and session/liquidity constraints."
        )
    if snapshot["backtesting_specs"]["non_draft_status_count"] == 0:
        actions.append(
            "Graduate at least one or two draft specs beyond `draft` by locking acceptance checks and clarifying any remaining objective-completion or invalidation edge cases."
        )
    if snapshot["training_surface"]["ready_indicator_binary_count"] < 2:
        prioritized = ", ".join(
            f"{task['trade_model']} (+{task['additional_positive_examples_needed']})"
            for task in snapshot["training_surface"]["trade_model_binary_tasks"]
            if task["trade_model"] in snapshot["indicator_ready_trade_models"] and not task["ready"]
        )
        actions.append(
            "Collect more positive labeled cases for the next narrow historical-model candidates: "
            + prioritized
            + "."
        )
    if active_extra_training_labels(snapshot):
        actions.append(
            "Either materialize an indicator spec for the remaining out-of-set training label or remove it from the active trainable surface so historical evaluation stays coherent."
        )
    actions.append(
        "Keep real-time trading deferred; the clean path is manual replay first, then rules-based historical backtests, then narrow model-assisted backtests."
    )
    return actions


def build_readiness_report(connection: sqlite3.Connection) -> dict:
    snapshot = build_snapshot(connection)
    stages = build_stage_readiness(snapshot)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "current_priority": "historical_backtesting_understanding_before_real_time_trading",
        "deferred_scope": {
            "real_time_neural_assist": "intentionally deferred until historical replay and structured backtests are solid",
            "real_time_neural_execution": "intentionally deferred and not part of the current readiness target",
        },
        "methodology": {
            "purpose": "Measure whether the repo is ready for honest historical replay and backtesting work before talking about any live or real-time trading system.",
            "stage_threshold": 0.73,
            "indicator_spec_stage_scores": SPEC_STAGE_SCORES,
            "hard_cap_policy": "Historical stages are capped when the repo lacks a repeatable harness, a transaction-cost model, or any specs beyond draft status.",
            "historical_bias_checks": [
                "anti_lookahead",
                "risk_and_target_definition",
                "transaction_costs",
                "manual_replay_case_quality",
            ],
        },
        "snapshot": snapshot,
        "stages": stages,
        "global_blockers": build_global_blockers(snapshot),
        "next_actions": build_next_actions(snapshot),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export staged readiness gates for historical replay, rules-based backtesting, and narrow model-assisted backtests."
    )
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        report = build_readiness_report(connection)

    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output_path),
                "foundation_grade": report["stages"]["historical_backtesting_research_foundation"]["grade"],
                "manual_replay_grade": report["stages"]["manual_chart_replay_understanding"]["grade"],
                "rules_backtest_grade": report["stages"]["rules_based_historical_backtesting"]["grade"],
                "model_backtest_grade": report["stages"]["model_assisted_historical_backtesting"]["grade"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
