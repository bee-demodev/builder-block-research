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
    load_trader_records,
    summarize_training_surface,
)
from export_topic_model_report import (
    build_indicator_spec_entries,
    build_topic_entries,
    build_trade_model_entries,
    build_trader_profile_entries,
)
from export_understanding_report import build_understanding_report, grade_from_score


ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "research.db"
DEFAULT_OUTPUT = ROOT / "results" / "neural_net_readiness_report.json"
RESEARCH_BACKLOG_PATH = ROOT / "results" / "research_backlog.json"
TRADER_ANNOTATION_CASES_PATH = ROOT / "data" / "trader_annotation_cases.json"
TRADINGVIEW_PINE_REPORT_PATH = ROOT / "results" / "tradingview_pine_readiness_report.json"
REINFORCED_TRAINING_REPORT_PATH = ROOT / "results" / "reinforced_model_training_report.json"
ITERATION_RETRAINING_REPORT_PATH = ROOT / "results" / "iteration_retraining_report.json"
ITERATION_CHALLENGER_REPORT_PATH = ROOT / "results" / "iteration_challenger_report.json"
ITERATION_PROMOTION_REPORT_PATH = ROOT / "results" / "iteration_promotion_report.json"
PHASE_ONE_CHART_STATE_REPORT_PATH = ROOT / "results" / "phase_one_chart_state_training_surface_report.json"
RUNTIME_REQUIRED_PATHS = [
    ROOT / "runtime" / "__main__.py",
    ROOT / "runtime" / "harness.py",
    ROOT / "scripts" / "backtest_analyzer.py",
]

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


def clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def average(values: Iterable[float]) -> float:
    values_list = list(values)
    if not values_list:
        return 0.0
    return sum(values_list) / len(values_list)


def count_research_runs(connection: sqlite3.Connection) -> int:
    try:
        return int(connection.execute("SELECT COUNT(*) FROM research_runs").fetchone()[0])
    except sqlite3.OperationalError:
        return 0


def load_backlog_counts() -> dict:
    if not RESEARCH_BACKLOG_PATH.exists():
        return {
            "article_sources_missing_text_artifacts": 0,
            "video_sources_missing_transcripts": 0,
            "topic_groups": 0,
            "trade_model_groups": 0,
            "artifact_present": False,
        }

    payload = json.loads(RESEARCH_BACKLOG_PATH.read_text(encoding="utf-8"))
    counts = dict(payload.get("counts", {}))
    counts["artifact_present"] = True
    return counts


def load_optional_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def load_manifest_case_refs() -> set[str]:
    payload = json.loads(TRADER_ANNOTATION_CASES_PATH.read_text(encoding="utf-8"))
    return {
        str(case["case_ref"])
        for case in payload.get("cases", [])
        if str(case.get("case_ref", "")).strip()
    }


def build_training_examples(connection: sqlite3.Connection) -> list[dict]:
    records = load_trader_records(connection)
    examples: list[dict] = []
    for record in records:
        for trade_model_link in record.get("annotation_trade_models", []):
            examples.append(build_training_example(record, trade_model_link))
    return examples


def build_manifest_sync_snapshot(connection: sqlite3.Connection) -> dict:
    manifest_case_refs = load_manifest_case_refs()
    records = load_trader_records(connection)
    db_case_refs = {str(record["case_ref"]) for record in records}
    missing_in_db = sorted(manifest_case_refs - db_case_refs)
    extra_in_db = sorted(db_case_refs - manifest_case_refs)
    union_count = len(manifest_case_refs | db_case_refs)
    sync_score = 1.0 if union_count == 0 else 1.0 - ((len(missing_in_db) + len(extra_in_db)) / union_count)
    return {
        "manifest_case_count": len(manifest_case_refs),
        "db_case_count": len(db_case_refs),
        "missing_in_db": missing_in_db,
        "extra_in_db": extra_in_db,
        "sync_score": round(clamp(sync_score), 4),
    }


def summarize_indicator_spec_stages(indicator_specs: list[dict]) -> dict:
    status_counts: dict[str, int] = {}
    stage_scores: list[float] = []
    realtime_feature_scores: list[float] = []
    spec_models = {
        str(entry["trade_model_slug"])
        for entry in indicator_specs
        if str(entry.get("trade_model_slug", "")).strip()
    }

    for entry in indicator_specs:
        status = str(entry.get("status", "unknown")).strip().lower() or "unknown"
        status_counts[status] = status_counts.get(status, 0) + 1
        stage_scores.append(SPEC_STAGE_SCORES.get(status, 0.25))

        implementation_scope = entry.get("implementation_scope") or {}
        realtime_feature_scores.append(
            average(
                [
                    1.0 if entry.get("target_language") == "pine" else 0.0,
                    1.0 if implementation_scope.get("anti_repaint_baseline") else 0.0,
                    1.0 if implementation_scope.get("timeframe_stack") else 0.0,
                    1.0 if implementation_scope.get("build_target") else 0.0,
                ]
            )
        )

    non_draft_status_count = sum(
        count
        for status, count in status_counts.items()
        if status not in {"candidate", "draft", "unknown"}
    )
    return {
        "count": len(indicator_specs),
        "status_counts": dict(sorted(status_counts.items())),
        "stage_score": round(average(stage_scores), 4),
        "realtime_feature_score": round(average(realtime_feature_scores), 4),
        "non_draft_status_count": non_draft_status_count,
        "trade_model_slugs": sorted(spec_models),
    }


def classification_progress(task: dict) -> float:
    total_progress = clamp(
        float(task.get("total_examples", 0)) / max(1, int(task.get("recommended_total_examples", 1)))
    )
    class_progress = clamp(
        float(task.get("minimum_examples_per_class", 0))
        / max(1, int(task.get("recommended_examples_per_class", 1)))
    )
    diversity_progress = 1.0 if int(task.get("class_count", 0)) >= 2 else 0.0
    return round(average([total_progress, class_progress, diversity_progress]), 4)


def enrich_training_surface_snapshot(
    training_surface: dict,
    *,
    indicator_ready_models: list[str],
) -> dict:
    enriched = dict(training_surface)
    example_count = int(enriched.get("example_count", 0))
    labeled_outcome_count = int(enriched.get("labeled_outcome_count", 0))
    trade_model_task = enriched.get("task_readiness", {}).get("trade_model_classification", {})
    relation_type_task = enriched.get("task_readiness", {}).get("relation_type_classification", {})
    ready_binary_trade_models = sorted(
        {
            str(task["trade_model"])
            for task in enriched.get("trade_model_binary_tasks", [])
            if task.get("ready")
        }
    )
    indicator_ready_set = set(indicator_ready_models)
    ready_indicator_binary_count = len(set(ready_binary_trade_models) & indicator_ready_set)

    enriched["label_volume_score"] = round(clamp(example_count / 25), 4)
    enriched["outcome_label_coverage"] = round(
        labeled_outcome_count / max(1, example_count),
        4,
    )
    enriched["trade_model_classification_progress"] = classification_progress(trade_model_task)
    enriched["relation_type_classification_progress"] = classification_progress(
        relation_type_task
    )
    enriched["ready_indicator_binary_count"] = ready_indicator_binary_count
    enriched["ready_indicator_binary_coverage"] = round(
        (ready_indicator_binary_count / len(indicator_ready_set)) if indicator_ready_set else 0.0,
        4,
    )
    return enriched


def merge_training_surface_snapshot(
    training_surface: dict,
    *,
    reinforced_summary: dict,
    indicator_ready_models: list[str],
) -> dict:
    merged = dict(training_surface)
    for key in (
        "generated_at",
        "example_count",
        "unique_case_count",
        "unique_trade_model_count",
        "unique_relation_type_count",
        "labeled_outcome_count",
        "unknown_outcome_count",
        "trade_model_counts",
        "relation_type_counts",
        "outcome_decision_counts",
        "task_readiness",
        "trade_model_binary_tasks",
        "recommendations",
        "base_example_count",
        "reinforcement_example_count",
        "merged_example_count",
        "graded_episode_count",
        "skipped_episode_count",
    ):
        if key in reinforced_summary:
            merged[key] = reinforced_summary[key]
    return enrich_training_surface_snapshot(
        merged,
        indicator_ready_models=indicator_ready_models,
    )


def build_iteration_retraining_snapshot(iteration_retraining_report: dict) -> dict:
    trained_tasks = list(iteration_retraining_report.get("trained_tasks", []))
    trained_task_names = list(iteration_retraining_report.get("trained_task_names", []))
    if not trained_task_names:
        trained_task_names = [
            str(task.get("task_name"))
            for task in trained_tasks
            if str(task.get("task_name", "")).strip()
        ]
    devices = sorted(
        {
            str(task.get("device"))
            for task in trained_tasks
            if str(task.get("device", "")).strip()
        }
    )
    return {
        "dataset_example_count": int(iteration_retraining_report.get("dataset_example_count", 0)),
        "trained_task_count": int(iteration_retraining_report.get("trained_task_count", 0)),
        "trained_task_names": trained_task_names,
        "output_dir": iteration_retraining_report.get("output_dir"),
        "devices": devices,
    }


def build_iteration_challenger_snapshot(iteration_challenger_report: dict) -> dict:
    summary = iteration_challenger_report.get("summary", {})
    return {
        "compared_task_count": int(summary.get("compared_task_count", 0)),
        "challenger_win_count": int(summary.get("challenger_win_count", 0)),
        "champion_win_count": int(summary.get("champion_win_count", 0)),
        "tie_task_count": int(summary.get("tie_task_count", 0)),
        "promotion_candidate_count": int(summary.get("promotion_candidate_count", 0)),
        "promotion_candidate_tasks": list(summary.get("promotion_candidate_tasks", [])),
    }


def build_iteration_promotion_snapshot(iteration_promotion_report: dict) -> dict:
    summary = iteration_promotion_report.get("summary", {})
    return {
        "candidate_task_count": int(summary.get("candidate_task_count", 0)),
        "promoted_task_count": int(summary.get("promoted_task_count", 0)),
        "skipped_task_count": int(summary.get("skipped_task_count", 0)),
        "promoted_tasks": list(summary.get("promoted_tasks", [])),
        "skipped_tasks": list(summary.get("skipped_tasks", [])),
    }


def build_runtime_snapshot() -> dict:
    artifacts = [
        {
            "path": str(path),
            "exists": path.exists(),
        }
        for path in RUNTIME_REQUIRED_PATHS
    ]
    return {
        "required_artifacts": artifacts,
        "runtime_score": round(
            average(1.0 if artifact["exists"] else 0.0 for artifact in artifacts),
            4,
        ),
    }


def load_tradingview_pine_snapshot() -> dict:
    if not TRADINGVIEW_PINE_REPORT_PATH.exists():
        return {
            "workflow_score": 0.0,
            "generated_script_coverage": 0.0,
            "validation_coverage": 0.0,
            "playwriter_validation_coverage": 0.0,
            "validated_script_count": 0,
            "playwriter_validated_count": 0,
            "workflow_doc_present": False,
            "pending_spec_keys": [],
        }

    summary = json.loads(TRADINGVIEW_PINE_REPORT_PATH.read_text(encoding="utf-8")).get("summary", {})
    return {
        "workflow_score": round(clamp(float(summary.get("workflow_score", 0.0))), 4),
        "generated_script_coverage": round(clamp(float(summary.get("generated_script_coverage", 0.0))), 4),
        "validation_coverage": round(clamp(float(summary.get("validation_coverage", 0.0))), 4),
        "playwriter_validation_coverage": round(
            clamp(float(summary.get("playwriter_validation_coverage", 0.0))),
            4,
        ),
        "validated_script_count": int(summary.get("validated_script_count", 0)),
        "playwriter_validated_count": int(summary.get("playwriter_validated_count", 0)),
        "workflow_doc_present": bool(summary.get("workflow_doc_present", False)),
        "pending_spec_keys": list(summary.get("pending_spec_keys", [])),
    }


def load_phase_one_chart_state_bootstrap_snapshot() -> dict:
    if not PHASE_ONE_CHART_STATE_REPORT_PATH.exists():
        return {
            "exported_example_count": 0,
            "positive_example_count": 0,
            "negative_example_count": 0,
            "outcome_decision_counts": {},
            "source_kind_counts": {},
            "artifact_present": False,
        }

    payload = json.loads(PHASE_ONE_CHART_STATE_REPORT_PATH.read_text(encoding="utf-8"))
    summary = payload.get("summary", {})
    return {
        "exported_example_count": int(summary.get("exported_example_count", 0)),
        "positive_example_count": int(summary.get("positive_example_count", 0)),
        "negative_example_count": int(summary.get("negative_example_count", 0)),
        "outcome_decision_counts": dict(summary.get("outcome_decision_counts", {})),
        "source_kind_counts": dict(summary.get("source_kind_counts", {})),
        "artifact_present": True,
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
    indicator_spec_stage_score = float(snapshot["indicator_specs"]["stage_score"])
    realtime_feature_score = float(snapshot["indicator_specs"]["realtime_feature_score"])
    runtime_score = float(snapshot["runtime"]["runtime_score"])
    tradingview_workflow_score = float(snapshot["tradingview_pine"]["workflow_score"])
    generated_script_coverage = float(snapshot["tradingview_pine"]["generated_script_coverage"])
    validation_coverage = float(snapshot["tradingview_pine"]["validation_coverage"])
    playwriter_validation_coverage = float(snapshot["tradingview_pine"]["playwriter_validation_coverage"])
    manifest_sync_score = float(snapshot["annotation_manifest_sync"]["sync_score"])
    research_logging_score = float(snapshot["research_logging_score"])
    backlog_visibility_score = float(snapshot["backlog_visibility_score"])
    topic_coverage_score = float(snapshot["topic_coverage_score"])
    indicator_spec_coverage = float(snapshot["indicator_spec_coverage"])
    annotation_trade_model_coverage = float(snapshot["annotation_trade_model_coverage"])
    label_volume_score = float(snapshot["training_surface"]["label_volume_score"])
    outcome_label_coverage = float(snapshot["training_surface"]["outcome_label_coverage"])
    no_trade_filter_score = 1.0 if snapshot["training_surface"]["task_readiness"]["no_trade_filter"]["ready"] else 0.0
    ready_binary_coverage = float(snapshot["training_surface"]["ready_indicator_binary_coverage"])
    trade_model_multiclass_ready = (
        1.0 if snapshot["training_surface"]["task_readiness"]["trade_model_classification"]["ready"] else 0.0
    )
    relation_type_multiclass_ready = (
        1.0 if snapshot["training_surface"]["task_readiness"]["relation_type_classification"]["ready"] else 0.0
    )

    autoresearch_breakdown = {
        "understanding": understanding_overall * 0.22,
        "research_logging": research_logging_score * 0.13,
        "backlog_visibility": backlog_visibility_score * 0.08,
        "topic_coverage": topic_coverage_score * 0.08,
        "indicator_spec_coverage": indicator_spec_coverage * 0.08,
        "annotation_trade_model_coverage": annotation_trade_model_coverage * 0.08,
        "scenario_contract_coverage": scenario_contract_coverage * 0.10,
        "manifest_sync": manifest_sync_score * 0.08,
        "tradingview_workflow": tradingview_workflow_score * 0.15,
    }
    autoresearch_blockers: list[str] = []
    if research_logging_score == 0.0:
        autoresearch_blockers.append("No research runs are logged yet.")
    if backlog_visibility_score == 0.0:
        autoresearch_blockers.append("Research backlog artifact is missing.")
    if tradingview_workflow_score == 0.0:
        autoresearch_blockers.append("TradingView and Pine workflow artifact is missing or not yet operational.")
    autoresearch = finalize_stage(
        name="karpathy_style_autoresearch_loop",
        base_score=sum(autoresearch_breakdown.values()),
        score_breakdown=autoresearch_breakdown,
        threshold=0.73,
        caps=[],
        blockers=autoresearch_blockers,
        recommendation="Keep the loop focused on backlog burn-down, scenario contracts, and label density instead of adding new abstract graph layers.",
    )

    offline_breakdown = {
        "understanding": understanding_overall * 0.14,
        "scenario_quality": scenario_average * 0.09,
        "scenario_contract_coverage": scenario_contract_coverage * 0.09,
        "machine_checkability": machine_checkability_average * 0.14,
        "label_volume": label_volume_score * 0.10,
        "outcome_label_coverage": outcome_label_coverage * 0.09,
        "no_trade_filter": no_trade_filter_score * 0.14,
        "ready_binary_trade_models": ready_binary_coverage * 0.10,
        "manifest_sync": manifest_sync_score * 0.05,
        "generated_pine_scripts": generated_script_coverage * 0.03,
        "tradingview_validation": validation_coverage * 0.03,
    }
    offline_blockers: list[str] = []
    if no_trade_filter_score == 0.0:
        offline_blockers.append("The no-trade filter task is not ready yet.")
    if snapshot["training_surface"]["ready_indicator_binary_count"] == 0:
        offline_blockers.append("No indicator-ready trade model has enough positives for one-vs-rest training.")
    if generated_script_coverage == 0.0:
        offline_blockers.append("No Pine draft scripts have been generated from the current indicator specs.")
    offline_caps = [
        (
            snapshot["training_surface"]["ready_indicator_binary_count"] < 2,
            0.76,
            "Only one indicator-ready trade model is currently baseline-ready, so offline ML should stay narrow and single-task.",
        ),
    ]
    offline = finalize_stage(
        name="offline_narrow_ml",
        base_score=sum(offline_breakdown.values()),
        score_breakdown=offline_breakdown,
        threshold=0.73,
        caps=offline_caps,
        blockers=offline_blockers,
        recommendation="Train only narrow offline baselines now: `continuation_entry_model` one-vs-rest and the `trade` vs `no_trade` filter.",
    )

    assist_breakdown = {
        "understanding": understanding_overall * 0.10,
        "scenario_quality": scenario_average * 0.08,
        "scenario_contract_coverage": scenario_contract_coverage * 0.08,
        "machine_checkability": machine_checkability_average * 0.09,
        "indicator_spec_stage": indicator_spec_stage_score * 0.09,
        "indicator_realtime_features": realtime_feature_score * 0.07,
        "indicator_spec_coverage": indicator_spec_coverage * 0.06,
        "runtime_infrastructure": runtime_score * 0.10,
        "ready_binary_trade_models": ready_binary_coverage * 0.10,
        "no_trade_filter": no_trade_filter_score * 0.10,
        "manifest_sync": manifest_sync_score * 0.05,
        "tradingview_workflow": tradingview_workflow_score * 0.05,
        "generated_pine_scripts": generated_script_coverage * 0.02,
        "tradingview_validation": validation_coverage * 0.01,
    }
    assist_blockers: list[str] = []
    if runtime_score == 0.0:
        assist_blockers.append("No live or paper-trading runtime/backtest harness is present in the repo.")
    if snapshot["indicator_specs"]["non_draft_status_count"] == 0:
        assist_blockers.append("All indicator specs are still draft-only.")
    if snapshot["training_surface"]["ready_indicator_binary_count"] < 3:
        assist_blockers.append("Fewer than three indicator-ready trade models are baseline-ready for one-vs-rest scoring.")
    if scenario_contract_coverage < 0.8:
        assist_blockers.append("Scenario contracts do not yet cover most case-model links.")
    if validation_coverage == 0.0:
        assist_blockers.append("No generated Pine drafts have been validated in TradingView yet.")
    assist_caps = [
        (
            runtime_score == 0.0,
            0.58,
            "Without runtime or paper-trade infrastructure, the repo cannot honestly claim real-time neural assistance readiness.",
        ),
        (
            snapshot["indicator_specs"]["non_draft_status_count"] == 0,
            0.58,
            "Draft-only indicator specs are not enough to trust a real-time assist layer.",
        ),
        (
            snapshot["training_surface"]["ready_indicator_binary_count"] < 3,
            0.58,
            "Real-time assist should wait until several trade-model scorers, not just one, are ready.",
        ),
        (
            validation_coverage == 0.0,
            0.58,
            "Real-time assist should not advance until spec-generated Pine drafts have been checked in TradingView.",
        ),
    ]
    assist = finalize_stage(
        name="real_time_neural_assist",
        base_score=sum(assist_breakdown.values()),
        score_breakdown=assist_breakdown,
        threshold=0.73,
        caps=assist_caps,
        blockers=assist_blockers,
        recommendation="Do not deploy real-time neural assistance yet; use the rules engine live and keep the neural layer offline until specs graduate beyond draft and more model-specific scorers are ready.",
    )

    execution_breakdown = {
        "understanding": understanding_overall * 0.06,
        "scenario_quality": scenario_average * 0.06,
        "scenario_contract_coverage": scenario_contract_coverage * 0.06,
        "machine_checkability": machine_checkability_average * 0.06,
        "indicator_spec_stage": indicator_spec_stage_score * 0.06,
        "indicator_realtime_features": realtime_feature_score * 0.06,
        "runtime_infrastructure": runtime_score * 0.10,
        "trade_model_multiclass": trade_model_multiclass_ready * 0.13,
        "relation_type_multiclass": relation_type_multiclass_ready * 0.09,
        "ready_binary_trade_models": ready_binary_coverage * 0.09,
        "no_trade_filter": no_trade_filter_score * 0.04,
        "manifest_sync": manifest_sync_score * 0.05,
        "tradingview_workflow": tradingview_workflow_score * 0.05,
        "tradingview_validation": validation_coverage * 0.05,
        "playwriter_validation": playwriter_validation_coverage * 0.04,
    }
    execution_blockers: list[str] = []
    if runtime_score == 0.0:
        execution_blockers.append("No live execution or paper-trade runtime exists.")
    if trade_model_multiclass_ready == 0.0:
        execution_blockers.append("Trade-model classification is not ready.")
    if relation_type_multiclass_ready == 0.0:
        execution_blockers.append("Relation-type classification is not ready.")
    if snapshot["indicator_specs"]["non_draft_status_count"] == 0:
        execution_blockers.append("All indicator specs remain draft-only.")
    if snapshot["training_surface"]["ready_indicator_binary_count"] < 4:
        execution_blockers.append("Too few trade-model scorers are ready to support autonomous real-time execution.")
    if manifest_sync_score < 1.0:
        execution_blockers.append("Durable annotation manifest and DB are out of sync.")
    if validation_coverage == 0.0:
        execution_blockers.append("No Pine drafts have been validated inside TradingView.")
    if playwriter_validation_coverage == 0.0:
        execution_blockers.append("No TradingView Pine workflow has been exercised through Playwriter automation.")
    execution_caps = [
        (
            runtime_score == 0.0,
            0.42,
            "A real-time neural trading system needs runtime and paper-trade infrastructure before model quality even matters.",
        ),
        (
            trade_model_multiclass_ready == 0.0 or relation_type_multiclass_ready == 0.0,
            0.42,
            "Autonomous execution is capped hard until the label space is trainable beyond single-task binaries.",
        ),
        (
            snapshot["indicator_specs"]["non_draft_status_count"] == 0,
            0.42,
            "Draft translation scaffolds are insufficient for autonomous trading decisions.",
        ),
        (
            validation_coverage == 0.0 or playwriter_validation_coverage == 0.0,
            0.42,
            "Autonomous execution cannot be claimed before Pine drafts are validated in TradingView, preferably through the repo's Playwriter workflow.",
        ),
    ]
    execution = finalize_stage(
        name="real_time_neural_execution",
        base_score=sum(execution_breakdown.values()),
        score_breakdown=execution_breakdown,
        threshold=0.73,
        caps=execution_caps,
        blockers=execution_blockers,
        recommendation="Keep autonomous real-time trading as a hard no for now. The correct path is still rules live, neural offline, then paper-trade assist, then execution only after the label space, specs, and runtime are all mature.",
    )

    return {
        "karpathy_style_autoresearch_loop": autoresearch,
        "offline_narrow_ml": offline,
        "real_time_neural_assist": assist,
        "real_time_neural_execution": execution,
    }


def build_snapshot(connection: sqlite3.Connection) -> dict:
    topic_entries = build_topic_entries(connection)
    trade_model_entries = build_trade_model_entries(connection)
    trader_profile_entries = build_trader_profile_entries(connection)
    indicator_spec_entries = build_indicator_spec_entries(connection)
    understanding_report = build_understanding_report(connection)
    training_examples = build_training_examples(connection)
    training_surface = summarize_training_surface(training_examples)
    reinforced_training_report = load_optional_json(REINFORCED_TRAINING_REPORT_PATH, {"summary": {}})
    iteration_retraining_report = load_optional_json(ITERATION_RETRAINING_REPORT_PATH, {})
    iteration_challenger_report = load_optional_json(ITERATION_CHALLENGER_REPORT_PATH, {"summary": {}})
    iteration_promotion_report = load_optional_json(ITERATION_PROMOTION_REPORT_PATH, {"summary": {}})
    research_run_count = count_research_runs(connection)
    backlog_counts = load_backlog_counts()
    manifest_sync = build_manifest_sync_snapshot(connection)
    runtime_snapshot = build_runtime_snapshot()
    tradingview_pine_snapshot = load_tradingview_pine_snapshot()
    phase_one_chart_state_bootstrap = load_phase_one_chart_state_bootstrap_snapshot()

    indicator_ready_models = sorted(
        {
            str(trade_model["trade_model"])
            for profile in trader_profile_entries
            for trade_model in profile.get("trade_models", [])
            if trade_model.get("indicator_ready")
        }
    )
    training_surface = merge_training_surface_snapshot(
        training_surface,
        reinforced_summary=reinforced_training_report.get("summary", {}),
        indicator_ready_models=indicator_ready_models,
    )
    active_trade_models = sorted(str(entry["slug"]) for entry in trade_model_entries)
    spec_trade_models = set(indicator_spec_entries and summarize_indicator_spec_stages(indicator_spec_entries)["trade_model_slugs"] or [])
    training_trade_models = set(str(label) for label in training_surface.get("trade_model_counts", {}).keys())
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
    indicator_spec_stage_snapshot = summarize_indicator_spec_stages(indicator_spec_entries)
    indicator_spec_coverage = (
        len(spec_trade_models & set(indicator_ready_models)) / len(indicator_ready_models)
        if indicator_ready_models
        else 0.0
    )
    all_extra_training_labels = filter_extra_training_labels(
        training_trade_models - set(indicator_spec_stage_snapshot["trade_model_slugs"])
    )
    active_extra_training_labels_value, deferred_extra_training_labels_value = split_training_labels(
        all_extra_training_labels
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_run_count": research_run_count,
        "research_logging_score": round(
            clamp(research_run_count / max(1, len(topic_entries))),
            4,
        ),
        "backlog_counts": backlog_counts,
        "backlog_visibility_score": 1.0 if backlog_counts.get("artifact_present") else 0.0,
        "topic_count": len(topic_entries),
        "topic_coverage_score": round(clamp(len(topic_entries) / 14), 4),
        "trade_model_count": len(active_trade_models),
        "active_trade_models": active_trade_models,
        "indicator_ready_trade_models": indicator_ready_models,
        "indicator_spec_coverage": round(indicator_spec_coverage, 4),
        "annotation_trade_model_coverage": round(
            clamp(training_surface["unique_trade_model_count"] / max(1, len(indicator_ready_models))),
            4,
        ),
        "indicator_specs": indicator_spec_stage_snapshot,
        "indicator_spec_machine_checkability_average": round(machine_checkability_average, 4),
        "training_surface": training_surface,
        "iteration_retraining": build_iteration_retraining_snapshot(iteration_retraining_report),
        "iteration_challengers": build_iteration_challenger_snapshot(iteration_challenger_report),
        "iteration_promotions": build_iteration_promotion_snapshot(iteration_promotion_report),
        "understanding": {
            "overall": understanding_report["overall"],
            "weakest_topics": understanding_report["weakest_topics"],
            "weakest_indicator_specs": understanding_report["weakest_indicator_specs"],
            "weakest_scenarios": understanding_report["weakest_scenarios"],
            "uncontracted_scenarios": understanding_report["uncontracted_scenarios"],
        },
        "annotation_manifest_sync": manifest_sync,
        "runtime": runtime_snapshot,
        "tradingview_pine": tradingview_pine_snapshot,
        "phase_one_chart_state_bootstrap": phase_one_chart_state_bootstrap,
        "label_space": {
            "training_trade_models": sorted(training_trade_models),
            "indicator_spec_trade_models": indicator_spec_stage_snapshot["trade_model_slugs"],
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


def deferred_extra_training_labels(snapshot: dict) -> list[str]:
    label_space = snapshot.get("label_space", {})
    labels = label_space.get("all_extra_training_labels_without_indicator_specs")
    if labels is None:
        labels = label_space.get("extra_training_labels_without_indicator_specs", [])
    _, deferred_labels = split_training_labels(labels)
    return deferred_labels


def build_global_blockers(snapshot: dict) -> list[str]:
    blockers: list[str] = []
    if snapshot["runtime"]["runtime_score"] == 0.0:
        blockers.append("No runtime, paper-trade, or backtest harness is present for real-time model validation.")
    if snapshot["training_surface"]["task_readiness"]["trade_model_classification"]["ready"] is False:
        blockers.append("Trade-model multiclass classification is still under-labeled.")
    if snapshot["training_surface"]["task_readiness"]["relation_type_classification"]["ready"] is False:
        blockers.append("Relation-type classification is still under-labeled.")
    if snapshot["indicator_specs"]["non_draft_status_count"] == 0:
        blockers.append("All indicator specs are still draft translation scaffolds.")
    if snapshot["tradingview_pine"]["workflow_score"] == 0.0:
        blockers.append("TradingView + Pine workflow is not yet documented and operationalized in the repo.")
    if snapshot["tradingview_pine"]["validation_coverage"] == 0.0:
        blockers.append("No Pine drafts have been validated in TradingView yet.")
    if snapshot["understanding"]["overall"]["scenario_contract_coverage"] < 0.8:
        blockers.append("Scenario expectation contracts do not yet cover most labeled case-model links.")
    if snapshot["annotation_manifest_sync"]["extra_in_db"] or snapshot["annotation_manifest_sync"]["missing_in_db"]:
        blockers.append("Durable annotation manifest and DB contents are not perfectly aligned.")
    if active_extra_training_labels(snapshot):
        blockers.append(
            "Training labels include models outside the indicator-spec set: "
            + ", ".join(active_extra_training_labels(snapshot))
        )
    return blockers


def build_next_actions(snapshot: dict) -> list[str]:
    actions: list[str] = []
    uncontracted = snapshot.get("understanding", {}).get("uncontracted_scenarios", [])
    if uncontracted:
        actions.append(
            "Backfill scenario expectation contracts for the ungraded case-model links so new labels strengthen the strict understanding harness instead of bypassing it."
        )
    if snapshot["annotation_manifest_sync"]["extra_in_db"] or snapshot["annotation_manifest_sync"]["missing_in_db"]:
        actions.append(
            "Reconcile the durable annotation manifest with SQLite so readiness reports are driven by one canonical labeled surface."
        )

    additional_positive_needs = [
        task
        for task in snapshot["training_surface"]["trade_model_binary_tasks"]
        if task["trade_model"] in snapshot["indicator_ready_trade_models"] and not task["ready"]
    ]
    if additional_positive_needs:
        prioritized = ", ".join(
            f"{task['trade_model']} (+{task['additional_positive_examples_needed']})"
            for task in additional_positive_needs
        )
        actions.append(
            "Collect more positive labeled cases for the next indicator-ready scorers: " + prioritized + "."
        )

    challenger_snapshot = snapshot.get("iteration_challengers", {})
    compared_task_count = int(challenger_snapshot.get("compared_task_count", 0))
    promotion_candidate_tasks = list(challenger_snapshot.get("promotion_candidate_tasks", []))
    trained_task_count = int(snapshot.get("iteration_retraining", {}).get("trained_task_count", 0))
    promotion_snapshot = snapshot.get("iteration_promotions", {})
    promoted_tasks = list(promotion_snapshot.get("promoted_tasks", []))
    pending_promotion_reviews = [
        task for task in promotion_candidate_tasks if task not in set(promoted_tasks)
    ]

    if promoted_tasks:
        actions.append(
            "Track the newly promoted champion"
            + ("s" if len(promoted_tasks) > 1 else "")
            + f" ({', '.join(promoted_tasks)})"
            + " through the next reinforcement batch to confirm the promotion holds up under fresh loop pressure."
        )
    elif pending_promotion_reviews:
        actions.append(
            "Review the winning challenger benchmark"
            + f" ({', '.join(pending_promotion_reviews)})"
            + " and decide whether to promote the new artifact after a manual sanity check."
        )
    elif trained_task_count > compared_task_count and trained_task_count > 0:
        trained_task_names = ", ".join(
            snapshot.get("iteration_retraining", {}).get("trained_task_names", [])
        )
        actions.append(
            "Benchmark the latest iteration-retrained challengers"
            + (f" ({trained_task_names})" if trained_task_names else "")
            + " against the current offline baselines before promoting any new model artifact."
        )
    elif compared_task_count > 0:
        actions.append(
            "The latest challenger benchmark did not produce a clean promotion winner beyond the current champions, so collect more reinforcement examples before the next retraining pass."
        )

    if snapshot["indicator_specs"]["non_draft_status_count"] == 0:
        actions.append(
            "Graduate at least a few indicator specs beyond `draft` by resolving the current machine-checkability gaps and locking their acceptance checks."
        )
    if snapshot["tradingview_pine"]["generated_script_coverage"] < 1.0:
        actions.append(
            "Generate Pine draft scripts for every Pine-target indicator spec so TradingView validation becomes part of the core learning loop."
        )
    if snapshot["tradingview_pine"]["validation_coverage"] < 1.0:
        actions.append(
            "Validate more spec-generated Pine drafts in TradingView and log the outcome so readiness is grounded in editor-checked scripts, not prose alone."
        )
    if snapshot["runtime"]["runtime_score"] == 0.0:
        actions.append(
            "Add a paper-trade/backtest/runtime harness before talking about real-time neural assistance or execution."
        )

    phase_one_chart_state_bootstrap = snapshot.get("phase_one_chart_state_bootstrap", {})
    bootstrap_example_count = int(
        phase_one_chart_state_bootstrap.get("exported_example_count", 0) or 0
    )
    if bootstrap_example_count > 0:
        bootstrap_positive_count = int(
            phase_one_chart_state_bootstrap.get("positive_example_count", 0) or 0
        )
        bootstrap_negative_count = int(
            phase_one_chart_state_bootstrap.get("negative_example_count", 0) or 0
        )
        actions.append(
            "Phase 1 chart-state bootstrap is now live with "
            f"{bootstrap_example_count} labeled example"
            + ("s" if bootstrap_example_count != 1 else "")
            + f" ({bootstrap_positive_count} trade, {bootstrap_negative_count} no-trade), "
            + "so keep using it as the seed surface for narrow chart-state experiments."
        )
        if bootstrap_example_count < 10:
            actions.append(
                "Expand the phase-one chart-state bootstrap surface beyond the current tiny seed set before treating the resulting `trade_vs_no_trade` model as meaningful."
            )

    phase_one_focus = snapshot.get("phase_one_focus") or build_phase_one_focus(
        snapshot.get("training_surface", {}),
        indicator_ready_trade_models=snapshot.get("indicator_ready_trade_models", []),
    )
    phase_one_status = str(phase_one_focus.get("status", "")).strip()
    phase_one_gap = int(phase_one_focus.get("additional_positive_examples_needed", 0) or 0)
    if phase_one_status == "bootstrap_ready":
        actions.append(
            "Phase 1 training focus is `daily_bias_framework`: the current surface is bootstrap-ready for daily bias, higher-time-frame levels, and 1H-to-5m C1/C2/C3 alignment."
        )
    elif phase_one_gap > 0:
        actions.append(
            "Phase 1 training focus is `daily_bias_framework`, so keep collecting daily-bias cases until the remaining positive-example gap is closed."
        )
    else:
        actions.append(
            "Phase 1 training focus is `daily_bias_framework`, anchored to daily bias, higher-time-frame levels, and 1H-to-5m C1/C2/C3 alignment."
        )
    return actions


def build_readiness_report(connection: sqlite3.Connection) -> dict:
    snapshot = build_snapshot(connection)
    stages = build_stage_readiness(snapshot)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "methodology": {
            "purpose": "Separate strong research-loop maturity from true neural-trading readiness so ontology quality cannot be mistaken for live execution readiness.",
            "stage_threshold": 0.73,
            "indicator_spec_stage_scores": SPEC_STAGE_SCORES,
            "hard_cap_policy": "Real-time stages are capped when runtime infrastructure is absent, specs are draft-only, or the label space is not broadly trainable.",
        },
        "snapshot": snapshot,
        "phase_one_focus": snapshot.get("phase_one_focus", {}),
        "stages": stages,
        "global_blockers": build_global_blockers(snapshot),
        "next_actions": build_next_actions(snapshot),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export staged readiness gates for autoresearch, offline ML, and real-time neural trading."
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
                "autoresearch_grade": report["stages"]["karpathy_style_autoresearch_loop"]["grade"],
                "offline_ml_grade": report["stages"]["offline_narrow_ml"]["grade"],
                "real_time_assist_grade": report["stages"]["real_time_neural_assist"]["grade"],
                "real_time_execution_grade": report["stages"]["real_time_neural_execution"]["grade"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
