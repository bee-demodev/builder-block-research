from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from export_ttfm_blended_multimodal_dataset import (
    DEFAULT_DATASET_OUTPUT as DEFAULT_BLENDED_DATASET_OUTPUT,
    DEFAULT_MULTIMODAL_DATASET_PATH,
    DEFAULT_REPORT_OUTPUT as DEFAULT_BLENDED_DATASET_REPORT_OUTPUT,
    DEFAULT_TEACHER_DATASET_PATH,
    build_blended_multimodal_dataset_report,
    load_jsonl as load_blended_jsonl,
)
from export_ttfm_multimodal_review_queue import (
    DEFAULT_OUTPUT as DEFAULT_REVIEW_QUEUE_OUTPUT,
    build_multimodal_review_queue,
    score_multimodal_rows,
)
from export_ttfm_video_multimodal_dataset import (
    DEFAULT_AUDIO_OUTPUT_DIR,
    DEFAULT_CLIP_DURATION_SECONDS,
    DEFAULT_DATASET_OUTPUT as DEFAULT_VIDEO_MULTIMODAL_DATASET_OUTPUT,
    DEFAULT_REPORT_OUTPUT as DEFAULT_VIDEO_MULTIMODAL_REPORT_OUTPUT,
    DEFAULT_WEAK_DATASET_PATH,
    DEFAULT_WINDOW_DATASET_PATH,
    build_video_multimodal_dataset_report,
    load_jsonl_rows,
    materialize_audio_clips,
    write_jsonl as write_multimodal_jsonl,
)
from train_ttfm_video_multimodal_pattern_net import (
    DEFAULT_BRAIN_TYPE,
    build_examples,
    load_multimodal_rows,
    train_multimodal_classifier,
)
from train_ttfm_visual_pattern_net import select_label_space
from ttfm_brain_embeddings import (
    DEFAULT_AUDIO_SEMANTIC_CACHE_PATH,
    DEFAULT_AUDIO_UNDERSTANDING_MODEL,
    DEFAULT_TEXT_EMBEDDING_CACHE_PATH,
    DEFAULT_VISUAL_INDEX_PATH,
)
from ttfm_video_embeddings import DEFAULT_MODEL as DEFAULT_TEXT_EMBEDDING_MODEL
from ttfm_video_embeddings import DEFAULT_MULTIMODAL_MODEL as DEFAULT_VISUAL_EMBEDDING_MODEL
from ttfm_video_embeddings import DEFAULT_OUTPUT_DIMENSIONALITY


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LOOP_REPORT_OUTPUT = ROOT / "results" / "ttfm_multimodal_teacher_loop_report.json"
DEFAULT_LOOP_MODEL_NAME = "ttfm_blended_multimodal_pattern_net"
DEFAULT_LOOP_MODEL_OUTPUT_DIR = ROOT / "results" / "neural_models" / "ttfm_blended_multimodal"


def load_optional_jsonl(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.exists():
        return []
    return load_jsonl_rows(path)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def enrich_training_report(
    training_report: dict[str, Any],
    *,
    dataset_path: Path,
    rows: list[dict[str, Any]],
    selected_labels: list[str],
    label_counts: dict[str, int],
    skipped_labels: list[str],
    skipped_examples: list[dict[str, Any]],
    embedding_prep_report: dict[str, Any],
) -> dict[str, Any]:
    report = dict(training_report)
    report["dataset_path"] = str(dataset_path.resolve())
    report["raw_row_count"] = len(rows)
    report["selected_label_counts"] = {label: label_counts[label] for label in selected_labels}
    report["skipped_labels"] = skipped_labels
    report["skipped_examples"] = skipped_examples
    report["embedding_prep"] = embedding_prep_report
    return report


def merge_additional_weak_multimodal_rows(
    *,
    primary_rows: list[dict[str, Any]],
    additional_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    merged_rows = [dict(row) for row in primary_rows]
    seen_example_ids = {
        str(row.get("example_id", "")).strip()
        for row in primary_rows
        if str(row.get("example_id", "")).strip()
    }
    additional_source_type_counts: Counter[str] = Counter()
    added_additional_row_count = 0
    duplicate_example_id_count = 0
    skipped_missing_example_id_count = 0

    for row in additional_rows:
        example_id = str(row.get("example_id", "")).strip()
        source_type = str(row.get("source_type", "")).strip() or "unknown"
        additional_source_type_counts[source_type] += 1
        if not example_id:
            skipped_missing_example_id_count += 1
            continue
        if example_id in seen_example_ids:
            duplicate_example_id_count += 1
            continue
        seen_example_ids.add(example_id)
        merged_rows.append(dict(row))
        added_additional_row_count += 1

    return merged_rows, {
        "primary_row_count": len(primary_rows),
        "additional_row_count": len(additional_rows),
        "added_additional_row_count": added_additional_row_count,
        "duplicate_example_id_count": duplicate_example_id_count,
        "skipped_missing_example_id_count": skipped_missing_example_id_count,
        "additional_source_type_counts": dict(sorted(additional_source_type_counts.items())),
    }


def enrich_weak_multimodal_report(
    weak_multimodal_report: dict[str, Any],
    *,
    merged_rows: list[dict[str, Any]],
    merge_report: dict[str, Any],
) -> dict[str, Any]:
    report = dict(weak_multimodal_report)
    summary = dict(report.get("summary", {}))
    review_status_counts: Counter[str] = Counter()
    for row in merged_rows:
        review_status = str(row.get("review_status", "")).strip() or "unknown"
        review_status_counts[review_status] += 1
    summary.update(
        {
            "row_count": len(merged_rows),
            "eligible_for_training_count": sum(1 for row in merged_rows if bool(row.get("eligible_for_training"))),
            "ready_for_weak_training_count": review_status_counts.get("ready_for_weak_training", 0),
            "review_status_counts": dict(sorted(review_status_counts.items())),
            "additional_row_count": merge_report["additional_row_count"],
            "added_additional_row_count": merge_report["added_additional_row_count"],
            "duplicate_example_id_count": merge_report["duplicate_example_id_count"],
            "additional_source_type_counts": merge_report["additional_source_type_counts"],
        }
    )
    report["summary"] = summary
    report["merge"] = merge_report
    return report


def build_multimodal_teacher_loop_report(
    *,
    weak_multimodal_report: dict[str, Any],
    blended_multimodal_report: dict[str, Any],
    training_report: dict[str, Any],
    review_queue: dict[str, Any],
    weak_multimodal_dataset_path: Path,
    blended_multimodal_dataset_path: Path,
    review_queue_output_path: Path,
    model_path: Path,
    model_report_path: Path,
) -> dict[str, Any]:
    validation_metrics = training_report.get("validation_metrics", {})
    train_metrics = training_report.get("train_metrics", {})
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "weak_multimodal_dataset": {
            "dataset_output": str(weak_multimodal_dataset_path),
            **weak_multimodal_report.get("summary", {}),
        },
        "blended_multimodal_dataset": {
            "dataset_output": str(blended_multimodal_dataset_path),
            **blended_multimodal_report.get("summary", {}),
        },
        "multimodal_review_queue": {
            "queue_output": str(review_queue_output_path),
            **review_queue.get("summary", {}),
        },
        "multimodal_model": {
            "model_path": str(model_path),
            "model_report_path": str(model_report_path),
            "device": training_report.get("device"),
            "brain_type": training_report.get("brain_type"),
            "embedding_backend": training_report.get("embedding_backend"),
            "visual_embedding_model": training_report.get("visual_embedding_model"),
            "text_embedding_model": training_report.get("text_embedding_model"),
            "audio_semantic_mode": training_report.get("audio_semantic_mode"),
            "label_space_size": training_report.get("label_space_size", 0),
            "audio_enabled_example_count": training_report.get("audio_enabled_example_count", 0),
            "audio_semantic_example_count": training_report.get("audio_semantic_example_count", 0),
            "text_enabled_example_count": training_report.get("text_enabled_example_count", 0),
            "best_epoch": training_report.get("best_epoch"),
            "best_validation_f1": training_report.get("best_validation_f1"),
            "best_prediction_threshold": training_report.get("best_prediction_threshold"),
            "best_prediction_threshold_mode": training_report.get("best_prediction_threshold_mode"),
            "best_prediction_thresholds": training_report.get("best_prediction_thresholds"),
            "validation_micro_f1": validation_metrics.get("micro_f1"),
            "validation_micro_precision": validation_metrics.get("micro_precision"),
            "validation_micro_recall": validation_metrics.get("micro_recall"),
            "validation_positive_predictions": validation_metrics.get("positive_predictions"),
            "validation_positive_labels": validation_metrics.get("positive_labels"),
            "validation_average_setup_confidence": validation_metrics.get("average_setup_confidence"),
            "train_micro_f1": train_metrics.get("micro_f1"),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run the TTFM multimodal teacher loop: rebuild the weak video multimodal dataset, "
            "blend it with the teacher screenshot dataset, and retrain the multimodal model."
        )
    )
    parser.add_argument("--teacher-dataset", default=str(DEFAULT_TEACHER_DATASET_PATH))
    parser.add_argument("--weak-dataset", default=str(DEFAULT_WEAK_DATASET_PATH))
    parser.add_argument("--window-dataset", default=str(DEFAULT_WINDOW_DATASET_PATH))
    parser.add_argument("--audio-output-dir", default=str(DEFAULT_AUDIO_OUTPUT_DIR))
    parser.add_argument("--weak-multimodal-dataset-output", default=str(DEFAULT_VIDEO_MULTIMODAL_DATASET_OUTPUT))
    parser.add_argument("--weak-multimodal-report-output", default=str(DEFAULT_VIDEO_MULTIMODAL_REPORT_OUTPUT))
    parser.add_argument("--blended-dataset-output", default=str(DEFAULT_BLENDED_DATASET_OUTPUT))
    parser.add_argument("--blended-dataset-report-output", default=str(DEFAULT_BLENDED_DATASET_REPORT_OUTPUT))
    parser.add_argument("--clip-duration-seconds", type=float, default=DEFAULT_CLIP_DURATION_SECONDS)
    parser.add_argument("--ffmpeg-bin", default="ffmpeg")
    parser.add_argument("--model-output-dir", default=str(DEFAULT_LOOP_MODEL_OUTPUT_DIR))
    parser.add_argument("--model-name", default=DEFAULT_LOOP_MODEL_NAME)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--validation-ratio", type=float, default=0.2)
    parser.add_argument("--epochs", type=int, default=16)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--embedding-dim", type=int, default=DEFAULT_OUTPUT_DIMENSIONALITY)
    parser.add_argument("--text-embedding-model", default=DEFAULT_TEXT_EMBEDDING_MODEL)
    parser.add_argument("--visual-embedding-model", default=DEFAULT_VISUAL_EMBEDDING_MODEL)
    parser.add_argument("--audio-understanding-model", default=DEFAULT_AUDIO_UNDERSTANDING_MODEL)
    parser.add_argument("--visual-index", default=str(DEFAULT_VISUAL_INDEX_PATH))
    parser.add_argument("--audio-semantic-cache", default=str(DEFAULT_AUDIO_SEMANTIC_CACHE_PATH))
    parser.add_argument("--text-embedding-cache", default=str(DEFAULT_TEXT_EMBEDDING_CACHE_PATH))
    parser.add_argument("--framework-slug", default="ttfm")
    parser.add_argument("--profile-slug", default="ttrades_curriculum")
    parser.add_argument("--brain-type", default=DEFAULT_BRAIN_TYPE)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--min-positive-examples", type=int, default=2)
    parser.add_argument("--review-queue-output", default=str(DEFAULT_REVIEW_QUEUE_OUTPUT))
    parser.add_argument("--loop-report-output", default=str(DEFAULT_LOOP_REPORT_OUTPUT))
    parser.add_argument(
        "--additional-weak-multimodal-dataset",
        default=None,
        help="Optional JSONL of additional weak multimodal rows, such as daily intake image cases.",
    )
    args = parser.parse_args()

    weak_multimodal_rows, weak_multimodal_report = build_video_multimodal_dataset_report(
        weak_rows=load_jsonl_rows(Path(args.weak_dataset)),
        window_rows=load_jsonl_rows(Path(args.window_dataset)),
        audio_output_dir=Path(args.audio_output_dir),
        clip_duration_seconds=args.clip_duration_seconds,
    )
    weak_clip_stats = materialize_audio_clips(weak_multimodal_rows, ffmpeg_bin=args.ffmpeg_bin)
    weak_multimodal_report["summary"].update(weak_clip_stats)

    weak_multimodal_dataset_output_path = Path(args.weak_multimodal_dataset_output)
    weak_multimodal_report_output_path = Path(args.weak_multimodal_report_output)
    additional_weak_rows = load_optional_jsonl(
        Path(args.additional_weak_multimodal_dataset)
        if args.additional_weak_multimodal_dataset
        else None
    )
    merged_weak_multimodal_rows, merge_report = merge_additional_weak_multimodal_rows(
        primary_rows=weak_multimodal_rows,
        additional_rows=additional_weak_rows,
    )
    weak_multimodal_report = enrich_weak_multimodal_report(
        weak_multimodal_report,
        merged_rows=merged_weak_multimodal_rows,
        merge_report=merge_report,
    )
    write_multimodal_jsonl(weak_multimodal_dataset_output_path, merged_weak_multimodal_rows)
    write_json(weak_multimodal_report_output_path, weak_multimodal_report)

    blended_rows, blended_report = build_blended_multimodal_dataset_report(
        teacher_rows=load_blended_jsonl(Path(args.teacher_dataset)),
        multimodal_rows=merged_weak_multimodal_rows,
    )
    blended_dataset_output_path = Path(args.blended_dataset_output)
    write_multimodal_jsonl(blended_dataset_output_path, blended_rows)
    blended_report_output_path = Path(args.blended_dataset_report_output)
    write_json(blended_report_output_path, blended_report)

    rows = load_multimodal_rows(blended_dataset_output_path)
    selected_labels, label_counts, skipped_labels = select_label_space(
        rows,
        min_positive_examples=args.min_positive_examples,
    )
    label_to_index = {label: index for index, label in enumerate(selected_labels)}
    examples, skipped_examples, embedding_prep_report = build_examples(
        rows,
        label_to_index=label_to_index,
        output_dimensionality=args.embedding_dim,
        text_embedding_model=args.text_embedding_model,
        visual_embedding_model=args.visual_embedding_model,
        audio_understanding_model=args.audio_understanding_model,
        visual_index_path=Path(args.visual_index),
        audio_semantic_cache_path=Path(args.audio_semantic_cache),
        text_embedding_cache_path=Path(args.text_embedding_cache),
    )
    training_report = train_multimodal_classifier(
        examples,
        label_to_index=label_to_index,
        output_dir=Path(args.model_output_dir),
        model_name=args.model_name,
        device_preference=args.device,
        validation_ratio=args.validation_ratio,
        epochs=args.epochs,
        learning_rate=args.learning_rate,
        batch_size=args.batch_size,
        embedding_dim=args.embedding_dim,
        seed=args.seed,
        brain_type=args.brain_type,
        framework_slug=args.framework_slug,
        profile_slug=args.profile_slug,
    )
    training_report["framework_slug"] = args.framework_slug
    training_report["profile_slug"] = args.profile_slug
    training_report = enrich_training_report(
        training_report,
        dataset_path=blended_dataset_output_path,
        rows=rows,
        selected_labels=selected_labels,
        label_counts=label_counts,
        skipped_labels=skipped_labels,
        skipped_examples=skipped_examples,
        embedding_prep_report=embedding_prep_report,
    )

    model_path = Path(training_report["model_path"])
    model_report_path = model_path.with_name(f"{args.model_name}_report.json")
    write_json(model_report_path, training_report)

    review_predictions, review_score_report = score_multimodal_rows(
        merged_weak_multimodal_rows,
        model_path=model_path,
        device_preference=args.device,
    )
    review_queue = build_multimodal_review_queue(
        merged_weak_multimodal_rows,
        predictions_by_example_id=review_predictions,
        threshold=review_score_report.get("prediction_threshold", 0.5) or 0.5,
    )
    review_queue_output_path = Path(args.review_queue_output)
    write_json(review_queue_output_path, review_queue)

    loop_report = build_multimodal_teacher_loop_report(
        weak_multimodal_report=weak_multimodal_report,
        blended_multimodal_report=blended_report,
        training_report=training_report,
        review_queue=review_queue,
        weak_multimodal_dataset_path=weak_multimodal_dataset_output_path,
        blended_multimodal_dataset_path=blended_dataset_output_path,
        review_queue_output_path=review_queue_output_path,
        model_path=model_path,
        model_report_path=model_report_path,
    )
    loop_report_output_path = Path(args.loop_report_output)
    write_json(loop_report_output_path, loop_report)

    print(
        json.dumps(
            {
                "loop_report_output": str(loop_report_output_path),
                "weak_multimodal_row_count": weak_multimodal_report["summary"].get("row_count", 0),
                "blended_multimodal_row_count": blended_report["summary"].get("row_count", 0),
                "review_candidate_count": review_queue["summary"].get("review_candidate_count", 0),
                "validation_micro_f1": training_report.get("validation_metrics", {}).get("micro_f1"),
                "model_path": str(model_path),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
