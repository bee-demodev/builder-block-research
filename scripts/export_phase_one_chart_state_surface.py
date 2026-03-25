from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from export_model_training_surface import (
    build_training_text,
    extract_key_paths,
    flatten_strings,
    normalize_token,
)
from export_tradingview_pine_readiness_report import validation_passed_qa_gate
from phase_one_focus import PHASE_ONE_EXECUTION_SPEC, PHASE_ONE_TIMEFRAME_STACK


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REPLAY_STATE_PATH = ROOT / "results" / "neural_models" / "sample_tradingview_replay_state_batch.json"
DEFAULT_VALIDATION_LOG_PATH = ROOT / "data" / "tradingview_pine_validation.json"
DEFAULT_DATASET_OUTPUT = ROOT / "results" / "phase_one_chart_state_training_surface.jsonl"
DEFAULT_REPORT_OUTPUT = ROOT / "results" / "phase_one_chart_state_training_surface_report.json"
PHASE_ONE_RELATION_TYPE = "execution_model"
DEFAULT_PROFILE_SLUG = "ttrades_curriculum"
DEFAULT_PROFILE_NAME = "TTrades Curriculum"
DEFAULT_PROFILE_FRAMEWORKS = ["ttfm"]
NO_SEQUENCE_MARKERS = (
    "no-sequence state",
    "no sequence state",
    "no active hourly sequence",
    "wait-for-short-c2",
    "wait for short c2",
    "wait-for-long-c2",
    "wait for long c2",
)
ACTIVE_SEQUENCE_MARKERS = (
    "active hourly sequence is visible",
    "c1/c2/c3 are active",
    "c1, c2, and c3 are active",
)


def load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_string(value: object) -> str:
    return str(value or "").strip()


def normalize_string_list(values: object) -> list[str]:
    if values is None:
        return []
    if isinstance(values, list):
        return [str(value).strip() for value in values if str(value).strip()]
    if isinstance(values, str):
        cleaned = values.strip()
        return [cleaned] if cleaned else []
    return []


def sorted_normalized_tokens(value: object) -> list[str]:
    return sorted(
        {
            normalize_token(item)
            for item in flatten_strings(value)
            if normalize_token(item)
        }
    )


def build_phase_one_timeframe_scope() -> list[str]:
    return [
        f"chart_{PHASE_ONE_TIMEFRAME_STACK['structure']}",
        f"bias_{PHASE_ONE_TIMEFRAME_STACK['bias']}",
        f"structure_{PHASE_ONE_TIMEFRAME_STACK['structure']}",
        f"execution_{PHASE_ONE_TIMEFRAME_STACK['execution']}",
    ]


def build_surface_example(
    *,
    example_id: str,
    case_ref: str,
    profile_slug: str,
    profile_name: str,
    profile_type: str,
    topic: str,
    trade_model: str,
    relation_type: str,
    source_url: str,
    notes: str,
    chart_context: dict[str, Any],
    annotation_payload: dict[str, Any],
    outcome_decision: str,
    outcome_reason: str,
    confidence: float = 1.0,
) -> dict[str, Any]:
    setup_variant = normalize_string(chart_context.get("setup_variant"))
    source_kind = normalize_string(chart_context.get("source_kind"))
    timeframe_scope = normalize_string_list(chart_context.get("timeframe_scope"))
    session_scope = normalize_string_list(chart_context.get("session_scope"))
    annotation_key_paths = sorted(set(extract_key_paths(annotation_payload)))
    annotation_value_tokens = sorted_normalized_tokens(annotation_payload)
    chart_context_tokens = sorted_normalized_tokens(chart_context)

    training_text = build_training_text(
        [
            f"profile {profile_slug}" if profile_slug else "",
            f"topic {topic}" if topic else "",
            f"trade model {trade_model}" if trade_model else "",
            f"relation {relation_type}" if relation_type else "",
            f"setup {normalize_token(setup_variant)}" if setup_variant else "",
            f"context {' '.join(chart_context_tokens)}" if chart_context_tokens else "",
            f"annotation {' '.join(annotation_value_tokens)}" if annotation_value_tokens else "",
            f"outcome {outcome_decision}",
        ]
    )

    return {
        "example_id": example_id,
        "profile_slug": profile_slug,
        "profile_name": profile_name,
        "profile_type": profile_type,
        "topic": topic,
        "case_ref": case_ref,
        "source_url": source_url,
        "notes": notes,
        "trade_model": trade_model,
        "relation_type": relation_type,
        "confidence": confidence,
        "indicator_ready_in_profile": True,
        "features": {
            "topic": topic,
            "setup_variant": setup_variant,
            "source_kind": source_kind,
            "timeframe_scope": timeframe_scope,
            "session_scope": session_scope,
            "profile_frameworks": list(DEFAULT_PROFILE_FRAMEWORKS),
            "profile_topics": [topic] if topic else [],
            "profile_trade_model_roles": [f"{trade_model}:{relation_type}"],
            "annotation_key_paths": annotation_key_paths,
            "annotation_value_tokens": annotation_value_tokens,
            "chart_context_tokens": chart_context_tokens,
        },
        "targets": {
            "trade_model": trade_model,
            "relation_type": relation_type,
            "outcome_decision": outcome_decision,
            "is_no_trade": outcome_decision == "no_trade",
            "has_outcome_label": True,
            "outcome_reason": outcome_reason,
        },
        "training_text": training_text,
    }


def validation_is_no_sequence_wait_state(entry: dict[str, Any]) -> bool:
    combined_text = normalize_token(
        " ".join(
            [
                normalize_string(entry.get("notes")),
                normalize_string(entry.get("qa_notes")),
            ]
        )
    )
    if not combined_text:
        return False
    if any(marker in combined_text for marker in ACTIVE_SEQUENCE_MARKERS):
        return False
    return any(marker in combined_text for marker in NO_SEQUENCE_MARKERS)


def build_phase_one_replay_example(state: dict[str, Any]) -> dict[str, Any]:
    case_ref = normalize_string(state.get("case_ref")) or "unknown_phase_one_case"
    chart_context = dict(state.get("chart_context") or {})
    annotation = dict(state.get("annotation") or {})
    candidate_signal = dict(state.get("candidate_signal") or {})
    topic = normalize_string(state.get("topic")) or "continuation"
    trade_model = normalize_string(state.get("trade_model")) or PHASE_ONE_EXECUTION_SPEC
    relation_type = normalize_string(state.get("relation_type")) or PHASE_ONE_RELATION_TYPE
    profile_slug = normalize_string(state.get("profile_slug")) or DEFAULT_PROFILE_SLUG
    notes = normalize_string(candidate_signal.get("thesis")) or normalize_string(
        annotation.get("fired_alert")
    )

    annotation_payload = {
        "annotation": annotation,
        "candidate_signal": candidate_signal,
    }
    return build_surface_example(
        example_id=f"phase_one_replay::{case_ref}::{trade_model}::{relation_type}",
        case_ref=case_ref,
        profile_slug=profile_slug,
        profile_name=DEFAULT_PROFILE_NAME,
        profile_type="phase_one_replay_state",
        topic=topic,
        trade_model=trade_model,
        relation_type=relation_type,
        source_url="",
        notes=notes or "Phase-one replay sequence example.",
        chart_context=chart_context,
        annotation_payload=annotation_payload,
        outcome_decision="trade",
        outcome_reason="phase_one_sequence_activated",
    )


def build_phase_one_no_trade_validation_example(entry: dict[str, Any]) -> dict[str, Any]:
    recorded_at = normalize_string(entry.get("recorded_at")) or "unknown_time"
    trade_model = normalize_string(entry.get("spec_key")) or PHASE_ONE_EXECUTION_SPEC
    relation_type = PHASE_ONE_RELATION_TYPE
    chart_context = {
        "setup_variant": "validated_tradingview_pine_overlay",
        "source_kind": "tradingview_validation",
        "timeframe_scope": build_phase_one_timeframe_scope(),
        "session_scope": [],
        "chart_symbol": normalize_string(entry.get("chart_symbol")),
    }
    annotation_payload = {
        "validation_status": normalize_string(entry.get("validation_status")),
        "validation_method": normalize_string(entry.get("validation_method")),
        "qa_status": normalize_string(entry.get("qa_status")),
        "semantic_score": entry.get("semantic_score"),
        "visual_score": entry.get("visual_score"),
        "scope_score": entry.get("scope_score"),
        "notes": normalize_string(entry.get("notes")),
        "qa_notes": normalize_string(entry.get("qa_notes")),
    }
    return build_surface_example(
        example_id=f"phase_one_validation::{recorded_at}::{trade_model}::{relation_type}",
        case_ref=f"phase_one_validation::{recorded_at}::{trade_model}",
        profile_slug=DEFAULT_PROFILE_SLUG,
        profile_name=DEFAULT_PROFILE_NAME,
        profile_type="tradingview_validation",
        topic="bias",
        trade_model=trade_model,
        relation_type=relation_type,
        source_url=normalize_string(entry.get("chart_url")),
        notes=normalize_string(entry.get("notes"))
        or "Phase-one validated no-sequence wait state.",
        chart_context=chart_context,
        annotation_payload=annotation_payload,
        outcome_decision="no_trade",
        outcome_reason="phase_one_wait_state_without_hourly_sequence",
    )


def build_phase_one_chart_state_surface(
    *,
    replay_state_batch: dict[str, Any],
    validation_log: dict[str, Any],
) -> dict[str, Any]:
    examples: list[dict[str, Any]] = []
    skipped_replay_state_counts: Counter[str] = Counter()
    skipped_validation_counts: Counter[str] = Counter()

    for state in replay_state_batch.get("states", []):
        if not isinstance(state, dict):
            skipped_replay_state_counts["invalid_payload"] += 1
            continue
        if normalize_string(state.get("trade_model")) != PHASE_ONE_EXECUTION_SPEC:
            skipped_replay_state_counts["not_phase_one_execution_spec"] += 1
            continue
        if normalize_string(state.get("relation_type")) != PHASE_ONE_RELATION_TYPE:
            skipped_replay_state_counts["not_execution_model"] += 1
            continue
        if not isinstance(state.get("candidate_signal"), dict):
            skipped_replay_state_counts["missing_candidate_signal"] += 1
            continue
        examples.append(build_phase_one_replay_example(state))

    for entry in validation_log.get("validations", []):
        if not isinstance(entry, dict):
            skipped_validation_counts["invalid_payload"] += 1
            continue
        if normalize_string(entry.get("spec_key")) != PHASE_ONE_EXECUTION_SPEC:
            skipped_validation_counts["not_phase_one_execution_spec"] += 1
            continue
        if not validation_passed_qa_gate(entry):
            skipped_validation_counts["qa_not_passed"] += 1
            continue
        if not validation_is_no_sequence_wait_state(entry):
            skipped_validation_counts["not_no_sequence_state"] += 1
            continue
        examples.append(build_phase_one_no_trade_validation_example(entry))

    outcome_counts = Counter(example["targets"]["outcome_decision"] for example in examples)
    trade_model_counts = Counter(example["trade_model"] for example in examples)
    source_kind_counts = Counter(
        normalize_string(example.get("features", {}).get("source_kind"))
        for example in examples
        if normalize_string(example.get("features", {}).get("source_kind"))
    )
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "replay_state_input_count": len(replay_state_batch.get("states", [])),
        "validation_input_count": len(validation_log.get("validations", [])),
        "exported_example_count": len(examples),
        "positive_example_count": int(outcome_counts.get("trade", 0)),
        "negative_example_count": int(outcome_counts.get("no_trade", 0)),
        "outcome_decision_counts": dict(sorted(outcome_counts.items())),
        "trade_model_counts": dict(sorted(trade_model_counts.items())),
        "source_kind_counts": dict(sorted(source_kind_counts.items())),
        "skipped_replay_state_counts": dict(sorted(skipped_replay_state_counts.items())),
        "skipped_validation_counts": dict(sorted(skipped_validation_counts.items())),
    }
    return {
        "examples": examples,
        "summary": summary,
    }


def write_jsonl(path: Path, examples: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for example in examples:
            handle.write(json.dumps(example, sort_keys=True))
            handle.write("\n")


def export_phase_one_chart_state_surface(
    *,
    replay_state_path: Path = DEFAULT_REPLAY_STATE_PATH,
    validation_log_path: Path = DEFAULT_VALIDATION_LOG_PATH,
    dataset_output_path: Path = DEFAULT_DATASET_OUTPUT,
    report_output_path: Path = DEFAULT_REPORT_OUTPUT,
) -> dict[str, Any]:
    surface = build_phase_one_chart_state_surface(
        replay_state_batch=load_json(replay_state_path, {"states": []}),
        validation_log=load_json(validation_log_path, {"validations": []}),
    )
    write_jsonl(dataset_output_path, surface["examples"])

    report = {
        **surface,
        "dataset_output_path": str(dataset_output_path),
        "report_output_path": str(report_output_path),
    }
    report_output_path.parent.mkdir(parents=True, exist_ok=True)
    report_output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Export a tiny phase-one chart-state training surface from the current "
            "TradingView replay and live validation artifacts."
        )
    )
    parser.add_argument("--replay-state-path", default=str(DEFAULT_REPLAY_STATE_PATH))
    parser.add_argument("--validation-log-path", default=str(DEFAULT_VALIDATION_LOG_PATH))
    parser.add_argument("--dataset-output", default=str(DEFAULT_DATASET_OUTPUT))
    parser.add_argument("--report-output", default=str(DEFAULT_REPORT_OUTPUT))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = export_phase_one_chart_state_surface(
        replay_state_path=Path(args.replay_state_path),
        validation_log_path=Path(args.validation_log_path),
        dataset_output_path=Path(args.dataset_output),
        report_output_path=Path(args.report_output),
    )
    print(
        json.dumps(
            {
                "exported_example_count": report["summary"]["exported_example_count"],
                "positive_example_count": report["summary"]["positive_example_count"],
                "negative_example_count": report["summary"]["negative_example_count"],
                "dataset_output_path": report["dataset_output_path"],
                "report_output_path": report["report_output_path"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
