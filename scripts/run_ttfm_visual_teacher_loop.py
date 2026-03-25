from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from export_ttfm_market_context_review_dashboard import (
    build_override_seed_map,
    build_review_dashboard_report,
    write_outputs as write_review_dashboard_outputs,
)
from export_ttfm_market_context_review_queue import build_market_context_review_queue
from export_ttfm_weak_visual_promotion_queue import build_weak_visual_promotion_queue
from export_ttfm_teacher_visual_dataset import (
    DEFAULT_BARS_MANIFEST_PATH,
    DEFAULT_DATASET_OUTPUT,
    DEFAULT_MARKET_MAP_PATH,
    DEFAULT_REPORT_OUTPUT,
    DEFAULT_VALIDATION_PATH,
    build_teacher_visual_dataset_report,
    load_case_packet_report,
    load_optional_json,
)
from export_ttfm_case_packets import DEFAULT_OUTPUT as DEFAULT_CASE_PACKET_PATH
from export_ttfm_market_context_review_dashboard import (
    DEFAULT_HTML_OUTPUT as DEFAULT_REVIEW_DASHBOARD_OUTPUT,
    DEFAULT_OVERRIDE_OUTPUT as DEFAULT_OVERRIDE_TEMPLATE_OUTPUT,
)
from export_ttfm_market_context_review_queue import DEFAULT_OUTPUT as DEFAULT_REVIEW_QUEUE_OUTPUT
from export_ttfm_phase_one_replay_dataset import (
    DEFAULT_DATASET_OUTPUT as DEFAULT_PHASE_ONE_REPLAY_DATASET_OUTPUT,
    DEFAULT_REPORT_OUTPUT as DEFAULT_PHASE_ONE_REPLAY_REPORT_OUTPUT,
    export_phase_one_replay_dataset,
)
from sync_ttfm_market_context_map import (
    DEFAULT_SOURCE_PATH as DEFAULT_SYNC_SOURCE_PATH,
    merge_market_context_map,
    write_market_context_map,
)
from train_ttfm_visual_pattern_net import (
    DEFAULT_MODEL_NAME,
    DEFAULT_OUTPUT_DIR as DEFAULT_MODEL_OUTPUT_DIR,
    build_examples,
    load_teacher_visual_rows,
    select_label_space,
    train_visual_classifier,
)


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LOOP_REPORT_OUTPUT = ROOT / "results" / "ttfm_visual_teacher_loop_report.json"
DEFAULT_REVIEWED_WEAK_DATASET_PATH = ROOT / "results" / "ttfm_video_weak_visual_dataset.jsonl"
DEFAULT_AUGMENTED_DATASET_OUTPUT = ROOT / "results" / "ttfm_teacher_augmented_visual_dataset.jsonl"
DEFAULT_WEAK_PROMOTION_REPORT_OUTPUT = ROOT / "results" / "ttfm_reviewed_weak_visual_promotion_report.json"
DEFAULT_WEAK_PROMOTION_QUEUE_OUTPUT = ROOT / "results" / "ttfm_weak_visual_promotion_queue.json"
PROMOTABLE_WEAK_REVIEW_STATUSES = {
    "approved_for_teacher",
    "teacher_approved",
    "promoted_to_teacher",
}
BLOCKED_WEAK_CONTRADICTION_STATUSES = {
    "blocked",
    "contradiction_confirmed",
    "needs_reconciliation",
}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row) for row in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )


def load_jsonl_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        cleaned = line.strip()
        if cleaned:
            rows.append(json.loads(cleaned))
    return rows


def normalize_string_list(values: object) -> list[str]:
    if values is None:
        return []
    if isinstance(values, list):
        return [str(value).strip() for value in values if str(value).strip()]
    if isinstance(values, str):
        cleaned = values.strip()
        return [cleaned] if cleaned else []
    return []


def build_timeframe_stack_from_weak_row(row: dict[str, Any]) -> dict[str, Any]:
    timeframe = str(row.get("timeframe", "")).strip() or None
    timeframe_role = str(row.get("timeframe_role", "")).strip() or None
    stack = {"htf": None, "etf": None, "ltf": None}
    if timeframe and timeframe_role in stack:
        stack[timeframe_role] = timeframe
    elif timeframe:
        stack["etf"] = timeframe
    labels = [value for value in [stack["htf"], stack["etf"], stack["ltf"]] if value]
    return {
        **stack,
        "labels": sorted(set(labels)),
        "is_multi_timeframe": len(set(labels)) > 1,
    }


def dedupe_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            output.append(value)
    return output


def promote_reviewed_weak_visual_rows(
    weak_rows: list[dict[str, Any]],
    *,
    promotable_review_statuses: set[str] | None = None,
    blocked_contradiction_statuses: set[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    promotable_review_statuses = promotable_review_statuses or PROMOTABLE_WEAK_REVIEW_STATUSES
    blocked_contradiction_statuses = (
        blocked_contradiction_statuses or BLOCKED_WEAK_CONTRADICTION_STATUSES
    )

    promoted_rows: list[dict[str, Any]] = []
    review_status_counts: Counter[str] = Counter()
    contradiction_status_counts: Counter[str] = Counter()
    blocked_review_status_count = 0
    blocked_contradiction_count = 0
    missing_screenshot_count = 0
    missing_label_count = 0

    for row in weak_rows:
        review_status = str(row.get("review_status", "")).strip() or "unknown"
        contradiction_status = str(row.get("contradiction_status", "")).strip() or "unknown"
        review_status_counts[review_status] += 1
        contradiction_status_counts[contradiction_status] += 1

        if review_status not in promotable_review_statuses:
            blocked_review_status_count += 1
            continue
        if contradiction_status in blocked_contradiction_statuses:
            blocked_contradiction_count += 1
            continue

        screenshot_path = str(row.get("screenshot_path", "")).strip()
        if not screenshot_path:
            missing_screenshot_count += 1
            continue

        active_labels = normalize_string_list(row.get("active_labels"))
        if not active_labels:
            missing_label_count += 1
            continue

        evidence_refs = dedupe_preserving_order(
            normalize_string_list(row.get("evidence_refs"))
            + normalize_string_list(row.get("source_url"))
            + normalize_string_list(row.get("source_page"))
            + normalize_string_list(row.get("source_chunk_id"))
        )
        annotation_notes = normalize_string_list(row.get("annotation_notes"))
        annotation_notes.append(
            "Promoted from reviewed weak YouTube visual evidence into the teacher training surface."
        )

        promoted_rows.append(
            {
                "example_id": str(row.get("example_id", "")).strip(),
                "case_ref": str(row.get("case_ref", "")).strip()
                or str(row.get("video_slug", "")).strip(),
                "topic": normalize_string_list(row.get("topics"))[0]
                if normalize_string_list(row.get("topics"))
                else str(row.get("video_slug", "")).strip() or None,
                "trade_models": [],
                "relation_types": [],
                "checkpoint": str(row.get("checkpoint", "")).strip() or "unknown",
                "timeframe": str(row.get("timeframe", "")).strip() or None,
                "timeframe_role": str(row.get("timeframe_role", "")).strip() or None,
                "timeframe_stack": build_timeframe_stack_from_weak_row(row),
                "active_labels": active_labels,
                "active_label_provenance": "weak_visual_review_promoted",
                "labels_by_provenance": {"weak_visual_review_promoted": active_labels},
                "supporting_topics": normalize_string_list(row.get("supporting_topics")),
                "draft_spec_keys": [],
                "outcome": {
                    "decision": "teacher_promotion",
                    "reason": "reviewed_weak_visual_evidence",
                },
                "annotation_notes": annotation_notes,
                "evidence_refs": evidence_refs,
                "zone_geometry": None,
                "source_url": str(row.get("source_url", "")).strip()
                or str(row.get("source_page", "")).strip()
                or None,
                "screenshot_path": screenshot_path,
                "market_context": row.get("market_context", {}),
                "sample_weight": 1.0,
                "source_tier": "teacher_promoted_weak",
                "review_status": review_status,
                "contradiction_status": contradiction_status,
                "weak_label_confidence": row.get("weak_label_confidence"),
            }
        )

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "input_row_count": len(weak_rows),
            "promoted_row_count": len(promoted_rows),
            "pending_review_count": review_status_counts.get("ready_for_weak_training", 0),
            "blocked_review_status_count": blocked_review_status_count,
            "blocked_contradiction_count": blocked_contradiction_count,
            "missing_screenshot_count": missing_screenshot_count,
            "missing_label_count": missing_label_count,
            "review_status_counts": dict(sorted(review_status_counts.items())),
            "contradiction_status_counts": dict(sorted(contradiction_status_counts.items())),
        },
    }
    return promoted_rows, report


def enrich_training_report(
    training_report: dict[str, Any],
    *,
    dataset_path: Path,
    rows: list[dict[str, Any]],
    selected_labels: list[str],
    label_counts: dict[str, int],
    skipped_labels: list[str],
    skipped_examples: list[dict[str, Any]],
) -> dict[str, Any]:
    report = dict(training_report)
    report["dataset_path"] = str(dataset_path.resolve())
    report["raw_row_count"] = len(rows)
    report["selected_label_counts"] = {label: label_counts[label] for label in selected_labels}
    report["skipped_labels"] = skipped_labels
    report["skipped_examples"] = skipped_examples
    return report


def build_visual_teacher_loop_report(
    *,
    sync_applied: bool,
    teacher_dataset_report: dict[str, Any],
    review_queue: dict[str, Any],
    training_report: dict[str, Any],
    weak_promotion_report: dict[str, Any] | None = None,
    weak_promotion_queue_report: dict[str, Any] | None = None,
    phase_one_replay_report: dict[str, Any],
    review_dashboard_path: Path,
    override_template_path: Path,
    model_path: Path,
    model_report_path: Path,
) -> dict[str, Any]:
    teacher_summary = teacher_dataset_report.get("summary", {})
    validation_metrics = training_report.get("validation_metrics", {})
    train_metrics = training_report.get("train_metrics", {})
    weak_promotion_report = weak_promotion_report or {"summary": {}}
    weak_promotion_queue_report = weak_promotion_queue_report or {"summary": {}}
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sync_applied": sync_applied,
        "teacher_dataset": {
            "row_count": teacher_summary.get("row_count", 0),
            "mapped_case_count": teacher_summary.get("mapped_case_count", 0),
            "fully_aligned_case_count": teacher_summary.get("fully_aligned_case_count", 0),
            "alignment_status_counts": teacher_summary.get("alignment_status_counts", {}),
            "mapping_provenance_counts": teacher_summary.get("mapping_provenance_counts", {}),
        },
        "review_queue": review_queue.get("summary", {}),
        "weak_promotions": weak_promotion_report.get("summary", {}),
        "weak_promotion_queue": weak_promotion_queue_report.get("summary", {}),
        "phase_one_replay_dataset": {
            "dataset_output": phase_one_replay_report.get("dataset_output"),
            "report_output": phase_one_replay_report.get("report_output"),
            "phase_one_case_count": phase_one_replay_report.get("summary", {}).get("phase_one_case_count", 0),
            "exported_case_count": phase_one_replay_report.get("summary", {}).get("exported_case_count", 0),
            "skipped_case_counts": phase_one_replay_report.get("summary", {}).get("skipped_case_counts", {}),
        },
        "visual_model": {
            "model_path": str(model_path),
            "model_report_path": str(model_report_path),
            "device": training_report.get("device"),
            "label_space_size": training_report.get("label_space_size", 0),
            "best_epoch": training_report.get("best_epoch"),
            "best_validation_f1": training_report.get("best_validation_f1"),
            "best_prediction_threshold": training_report.get("best_prediction_threshold"),
            "validation_micro_f1": validation_metrics.get("micro_f1"),
            "validation_micro_precision": validation_metrics.get("micro_precision"),
            "validation_micro_recall": validation_metrics.get("micro_recall"),
            "validation_positive_predictions": validation_metrics.get("positive_predictions"),
            "validation_positive_labels": validation_metrics.get("positive_labels"),
            "train_micro_f1": train_metrics.get("micro_f1"),
        },
        "review_artifacts": {
            "dashboard_path": str(review_dashboard_path),
            "override_template_path": str(override_template_path),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the TTFM visual teacher loop: optional override sync, teacher dataset rebuild, review refresh, and visual model retraining."
    )
    parser.add_argument("--sync-reviewed-overrides", action="store_true")
    parser.add_argument("--override-source", default=str(DEFAULT_SYNC_SOURCE_PATH))
    parser.add_argument("--case-packets", default=str(DEFAULT_CASE_PACKET_PATH))
    parser.add_argument("--bars-manifest", default=str(DEFAULT_BARS_MANIFEST_PATH))
    parser.add_argument("--validation-manifest", default=str(DEFAULT_VALIDATION_PATH))
    parser.add_argument("--market-map", default=str(DEFAULT_MARKET_MAP_PATH))
    parser.add_argument("--dataset-output", default=str(DEFAULT_DATASET_OUTPUT))
    parser.add_argument("--dataset-report-output", default=str(DEFAULT_REPORT_OUTPUT))
    parser.add_argument("--review-queue-output", default=str(DEFAULT_REVIEW_QUEUE_OUTPUT))
    parser.add_argument("--review-dashboard-output", default=str(DEFAULT_REVIEW_DASHBOARD_OUTPUT))
    parser.add_argument("--override-template-output", default=str(DEFAULT_OVERRIDE_TEMPLATE_OUTPUT))
    parser.add_argument("--reviewed-weak-dataset", default=str(DEFAULT_REVIEWED_WEAK_DATASET_PATH))
    parser.add_argument("--augmented-training-dataset-output", default=str(DEFAULT_AUGMENTED_DATASET_OUTPUT))
    parser.add_argument("--weak-promotion-report-output", default=str(DEFAULT_WEAK_PROMOTION_REPORT_OUTPUT))
    parser.add_argument("--weak-promotion-queue-output", default=str(DEFAULT_WEAK_PROMOTION_QUEUE_OUTPUT))
    parser.add_argument("--phase-one-replay-dataset-output", default=str(DEFAULT_PHASE_ONE_REPLAY_DATASET_OUTPUT))
    parser.add_argument("--phase-one-replay-report-output", default=str(DEFAULT_PHASE_ONE_REPLAY_REPORT_OUTPUT))
    parser.add_argument("--model-output-dir", default=str(DEFAULT_MODEL_OUTPUT_DIR))
    parser.add_argument("--model-name", default=DEFAULT_MODEL_NAME)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--validation-ratio", type=float, default=0.2)
    parser.add_argument("--epochs", type=int, default=18)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--image-size", type=int, default=128)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--min-positive-examples", type=int, default=2)
    parser.add_argument("--loop-report-output", default=str(DEFAULT_LOOP_REPORT_OUTPUT))
    args = parser.parse_args()

    market_map_path = Path(args.market_map)
    market_map = load_optional_json(market_map_path, {"case_overrides": []})
    if args.sync_reviewed_overrides:
        source_payload = load_optional_json(Path(args.override_source), {"case_overrides": []})
        market_map = merge_market_context_map(market_map, source_payload.get("case_overrides", []))
        write_market_context_map(market_map, market_map_path)

    case_packet_report = load_case_packet_report(Path(args.case_packets))
    bars_manifest = load_optional_json(Path(args.bars_manifest), {"files": []})
    validation_manifest = load_optional_json(Path(args.validation_manifest), {"validations": []})
    rows, teacher_dataset_report = build_teacher_visual_dataset_report(
        case_packet_report,
        bars_manifest=bars_manifest,
        validation_manifest=validation_manifest,
        market_map=market_map,
    )

    dataset_output_path = Path(args.dataset_output)
    write_jsonl(dataset_output_path, rows)
    dataset_report_output_path = Path(args.dataset_report_output)
    write_json(dataset_report_output_path, teacher_dataset_report)

    review_queue = build_market_context_review_queue(rows)
    review_queue_output_path = Path(args.review_queue_output)
    write_json(review_queue_output_path, review_queue)

    review_dashboard_output_path = Path(args.review_dashboard_output)
    review_report = build_review_dashboard_report(
        review_queue,
        html_output_path=review_dashboard_output_path,
    )
    override_seed_map = build_override_seed_map(review_queue)
    override_template_output_path = Path(args.override_template_output)
    write_review_dashboard_outputs(
        review_report,
        override_seed_map,
        html_output_path=review_dashboard_output_path,
        override_output_path=override_template_output_path,
    )

    phase_one_replay_report = export_phase_one_replay_dataset(
        dataset_path=dataset_output_path,
        dataset_output=Path(args.phase_one_replay_dataset_output),
        report_output=Path(args.phase_one_replay_report_output),
    )

    weak_rows = load_jsonl_rows(Path(args.reviewed_weak_dataset))
    weak_promotion_queue_report = build_weak_visual_promotion_queue(weak_rows)
    weak_promotion_queue_output_path = Path(args.weak_promotion_queue_output)
    write_json(weak_promotion_queue_output_path, weak_promotion_queue_report)

    promoted_weak_rows, weak_promotion_report = promote_reviewed_weak_visual_rows(weak_rows)
    weak_promotion_report_output_path = Path(args.weak_promotion_report_output)
    write_json(weak_promotion_report_output_path, weak_promotion_report)

    training_rows = list(rows) + promoted_weak_rows
    augmented_training_dataset_output_path = Path(args.augmented_training_dataset_output)
    write_jsonl(augmented_training_dataset_output_path, training_rows)

    selected_labels, label_counts, skipped_labels = select_label_space(
        training_rows,
        min_positive_examples=args.min_positive_examples,
    )
    label_to_index = {label: index for index, label in enumerate(selected_labels)}
    examples, skipped_examples = build_examples(training_rows, label_to_index=label_to_index)
    training_report = train_visual_classifier(
        examples,
        label_to_index=label_to_index,
        output_dir=Path(args.model_output_dir),
        model_name=args.model_name,
        device_preference=args.device,
        validation_ratio=args.validation_ratio,
        epochs=args.epochs,
        learning_rate=args.learning_rate,
        batch_size=args.batch_size,
        image_size=args.image_size,
        seed=args.seed,
    )
    training_report = enrich_training_report(
        training_report,
        dataset_path=augmented_training_dataset_output_path,
        rows=training_rows,
        selected_labels=selected_labels,
        label_counts=label_counts,
        skipped_labels=skipped_labels,
        skipped_examples=skipped_examples,
    )

    model_path = Path(training_report["model_path"])
    model_report_path = model_path.with_name(f"{args.model_name}_report.json")
    write_json(model_report_path, training_report)

    loop_report = build_visual_teacher_loop_report(
        sync_applied=args.sync_reviewed_overrides,
        teacher_dataset_report=teacher_dataset_report,
        review_queue=review_queue,
        training_report=training_report,
        weak_promotion_report=weak_promotion_report,
        weak_promotion_queue_report=weak_promotion_queue_report,
        phase_one_replay_report=phase_one_replay_report,
        review_dashboard_path=review_dashboard_output_path,
        override_template_path=override_template_output_path,
        model_path=model_path,
        model_report_path=model_report_path,
    )
    loop_report_output_path = Path(args.loop_report_output)
    write_json(loop_report_output_path, loop_report)

    print(
        json.dumps(
            {
                "loop_report_output": str(loop_report_output_path),
                "teacher_row_count": teacher_dataset_report["summary"].get("row_count", 0),
                "promoted_weak_row_count": weak_promotion_report["summary"].get("promoted_row_count", 0),
                "fully_aligned_case_count": teacher_dataset_report["summary"].get("fully_aligned_case_count", 0),
                "validation_micro_f1": training_report.get("validation_metrics", {}).get("micro_f1"),
                "review_dashboard_output": str(review_dashboard_output_path),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
