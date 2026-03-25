from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "results" / "ttfm_progress_snapshot.md"
DEFAULT_VISUAL_WINDOWS_REPORT = ROOT / "knowledge" / "ttfm_video_corpus" / "visual_windows_report.json"
DEFAULT_WEAK_VISUAL_REPORT = ROOT / "results" / "ttfm_video_weak_visual_dataset_report.json"
DEFAULT_WEAK_VISUAL_DATASET = ROOT / "results" / "ttfm_video_weak_visual_dataset.jsonl"
DEFAULT_WEAK_MULTIMODAL_REPORT = ROOT / "results" / "ttfm_video_multimodal_dataset_report.json"
DEFAULT_BLENDED_MULTIMODAL_REPORT = ROOT / "results" / "ttfm_blended_multimodal_dataset_report.json"
DEFAULT_BLENDED_MULTIMODAL_DATASET = ROOT / "results" / "ttfm_blended_multimodal_dataset.jsonl"
DEFAULT_MULTIMODAL_LOOP_REPORT = ROOT / "results" / "ttfm_multimodal_teacher_loop_report.json"
DEFAULT_MULTIMODAL_MODEL_REPORT = (
    ROOT / "results" / "neural_models" / "ttfm_blended_multimodal" / "ttfm_blended_multimodal_pattern_net_report.json"
)
DEFAULT_REVIEW_QUEUE = ROOT / "results" / "ttfm_multimodal_review_queue.json"
DEFAULT_WORKFLOW_REPORT = ROOT / "results" / "ttfm_brain_workflow_report.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_summary(path: Path) -> dict:
    payload = load_json(path)
    summary = payload.get("summary")
    if isinstance(summary, dict):
        return summary
    return payload


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped:
            rows.append(json.loads(stripped))
    return rows


def load_review_queue_rows(path: Path) -> list[dict]:
    payload = load_json(path)
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("items", "review_queue", "rows"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return []


def bullet_list(items: Iterable[str]) -> str:
    cleaned = [item for item in items if item]
    return "\n".join(f"- {item}" for item in cleaned)


def shorten(text: str, limit: int = 240) -> str:
    compact = " ".join(str(text).split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


def format_labels(labels: Iterable[str]) -> str:
    values = [str(label).strip() for label in labels if str(label).strip()]
    return ", ".join(values) if values else "(none)"


def format_probabilities(row: dict, limit: int = 5) -> str:
    top_labels = row.get("top_predicted_labels", [])[:limit]
    parts: list[str] = []
    for item in top_labels:
        label = str(item.get("label", "")).strip()
        probability = item.get("probability")
        if not label or probability is None:
            continue
        parts.append(f"{label}={probability:.3f}")
    return ", ".join(parts) if parts else "(none)"


def build_case_section(title: str, rows: list[dict], include_predictions: bool = False) -> str:
    sections = [f"## {title}", ""]
    if not rows:
        sections.append("No rows available.")
        sections.append("")
        return "\n".join(sections)

    for row in rows:
        sections.append(f"### {row.get('example_id', '(missing example_id)')}")
        sections.append(
            bullet_list(
                [
                    f"Title: {row.get('title') or row.get('case_ref') or '(missing title)'}",
                    f"Checkpoint: {row.get('checkpoint', '(missing checkpoint)')}",
                    f"Review status: {row.get('review_status', '(missing review status)')}",
                    f"Active labels: {format_labels(row.get('active_labels', row.get('weak_active_labels', [])))}",
                    f"Screenshot: {row.get('screenshot_path', '(missing screenshot)')}",
                    f"Audio: {row.get('audio_path', '(none)')}",
                    f"Embedding excerpt: {shorten(row.get('embedding_text', '') or row.get('transcript_window', ''))}",
                ]
            )
        )
        if include_predictions:
            sections.append(
                bullet_list(
                    [
                        f"Weak labels: {format_labels(row.get('weak_active_labels', []))}",
                        f"Predicted labels: {format_labels(row.get('predicted_labels', []))}",
                        f"Top probabilities: {format_probabilities(row)}",
                        f"Recommended action: {row.get('recommended_action', '(missing action)')}",
                        f"Priority band: {row.get('priority_band', '(missing priority)')}",
                        f"Label Jaccard: {row.get('label_jaccard', 0.0):.3f}",
                        f"Disagreement count: {row.get('disagreement_count', 0)}",
                    ]
                )
            )
        sections.append("")
    return "\n".join(sections)


def build_workflow_snapshot(report: dict[str, Any]) -> str:
    corpus = report.get("corpus", {})
    daily_intake = report.get("daily_intake", {})
    embeddings = report.get("embeddings", {})
    trainability = report.get("trainability", {})
    benchmark = report.get("frozen_benchmark", {})
    comparison = benchmark.get("comparison", {})
    challenger = benchmark.get("challenger", {})
    cases = report.get("top_disagreement_cases", [])
    outputs = report.get("outputs", {})

    lines = [
        "# TTFM Brain Workflow V2 Snapshot",
        "",
        f"Generated at: {report.get('generated_at', datetime.now(timezone.utc).isoformat())}",
        "",
        "## Corpus Coverage",
        "",
        bullet_list(
            [
                f"Active corpus videos: {corpus.get('current_video_count', 0)}",
                f"Delta vs prior run: {corpus.get('delta_video_count', 0)}",
                f"Partition counts: {json.dumps(corpus.get('partition_counts', {}), sort_keys=True)}",
            ]
        ),
        "",
        "## Daily Intake",
        "",
        bullet_list(
            [
                f"Video files scanned: {daily_intake.get('video_file_count', 0)}",
                f"Image files scanned: {daily_intake.get('image_file_count', 0)}",
                f"Trainable videos added: {daily_intake.get('trainable_video_count', 0)}",
                f"Queued videos: {daily_intake.get('queued_video_count', 0)}",
                f"Trainable image rows: {daily_intake.get('trainable_image_count', 0)}",
                f"Review-only image rows: {daily_intake.get('review_only_image_count', 0)}",
            ]
        ),
        "",
        "## Embeddings",
        "",
        bullet_list(
            [
                f"Text embeddings: {embeddings.get('text', {}).get('item_count', 0)} ({embeddings.get('text', {}).get('status', 'unknown')})",
                f"Visual embeddings: {embeddings.get('visual', {}).get('item_count', 0)} ({embeddings.get('visual', {}).get('status', 'unknown')})",
            ]
        ),
        "",
        "## Trainability",
        "",
        bullet_list(
            [
                f"Trainable rows: {trainability.get('trainable_row_count', 0)}",
                f"Blocked rows: {trainability.get('blocked_row_count', 0)}",
                f"Blocked reasons: {json.dumps(trainability.get('blocked_reason_counts', {}), sort_keys=True)}",
            ]
        ),
        "",
        "## Frozen Benchmark",
        "",
        bullet_list(
            [
                f"Benchmark rows: {benchmark.get('benchmark_row_count', 0)}",
                f"Winner: {comparison.get('winner', 'unknown')}",
                f"Challenger micro F1: {challenger.get('micro_f1', 0.0):.3f}" if challenger else "Challenger micro F1: n/a",
                f"Challenger precision/recall: {challenger.get('precision', 0.0):.3f} / {challenger.get('recall', 0.0):.3f}" if challenger else "Challenger precision/recall: n/a",
                f"Benchmark deltas: {json.dumps(comparison.get('delta', {}), sort_keys=True)}",
            ]
        ),
        "",
        build_case_section("Top Disagreement Cases", cases, include_predictions=True),
        "## Operator Artifacts",
        "",
        bullet_list([str(value) for value in outputs.values() if value]),
        "",
    ]
    return "\n".join(lines)


def build_snapshot() -> str:
    if DEFAULT_WORKFLOW_REPORT.exists():
        return build_workflow_snapshot(load_json(DEFAULT_WORKFLOW_REPORT))

    generated_at = datetime.now(timezone.utc).isoformat()
    visual_windows_report = load_summary(DEFAULT_VISUAL_WINDOWS_REPORT)
    weak_visual_report = load_summary(DEFAULT_WEAK_VISUAL_REPORT)
    weak_multimodal_report = load_summary(DEFAULT_WEAK_MULTIMODAL_REPORT)
    blended_multimodal_report = load_summary(DEFAULT_BLENDED_MULTIMODAL_REPORT)
    multimodal_loop_report = load_json(DEFAULT_MULTIMODAL_LOOP_REPORT)
    multimodal_model_report = load_json(DEFAULT_MULTIMODAL_MODEL_REPORT)
    weak_visual_rows = load_jsonl(DEFAULT_WEAK_VISUAL_DATASET)
    blended_multimodal_rows = load_jsonl(DEFAULT_BLENDED_MULTIMODAL_DATASET)
    review_queue_rows = load_review_queue_rows(DEFAULT_REVIEW_QUEUE)

    weak_examples = [
        row
        for row in weak_visual_rows
        if row.get("eligible_for_training") and row.get("review_status") == "ready_for_weak_training"
    ][:3]
    teacher_examples = [row for row in blended_multimodal_rows if row.get("source_tier") == "teacher"][:3]
    review_examples = [row for row in review_queue_rows if row.get("prediction_status") == "scored"][:5]

    validation_metrics = multimodal_model_report.get("validation_metrics", {})
    embedding_prep = multimodal_model_report.get("embedding_prep", {})
    training_blockers = weak_visual_report.get("training_blocker_counts", {})
    review_status_counts = weak_visual_report.get("review_status_counts", {})
    frame_status_counts = visual_windows_report.get("frame_status_counts", {})

    model_path = multimodal_loop_report.get("multimodal_model", {}).get(
        "model_path",
        str(DEFAULT_MULTIMODAL_MODEL_REPORT.with_suffix(".pt")),
    )

    lines = [
        "# TTFM Neural Brain Progress Snapshot",
        "",
        f"Generated at: {generated_at}",
        "",
        "## Corpus Status",
        "",
        bullet_list(
            [
                f"YouTube visual windows: {visual_windows_report.get('window_count', 0)} across {visual_windows_report.get('video_count', 0)} videos",
                f"Frame extraction: extracted={frame_status_counts.get('extracted', 0)}, failed={frame_status_counts.get('extract_failed', 0)}",
                f"Weak visual dataset: {weak_visual_report.get('row_count', 0)} rows, eligible_for_training={weak_visual_report.get('eligible_for_training_count', 0)}",
                f"Weak multimodal dataset: {weak_multimodal_report.get('row_count', 0)} rows, eligible_for_training={weak_multimodal_report.get('eligible_for_training_count', 0)}",
                f"Blended multimodal dataset: {blended_multimodal_report.get('row_count', 0)} rows ({blended_multimodal_report.get('teacher_row_count', 0)} teacher + {blended_multimodal_report.get('weak_row_count', 0)} weak)",
                f"Excluded weak rows from blended set: {blended_multimodal_report.get('excluded_weak_row_count', 0)}",
            ]
        ),
        "",
        "## Neural Model Status",
        "",
        bullet_list(
            [
                f"Model path: {model_path}",
                f"Device: {multimodal_model_report.get('device', '(unknown)')}",
                f"Label space size: {multimodal_model_report.get('label_space_size', 0)}",
                f"Best epoch: {multimodal_model_report.get('best_epoch', 0)}",
                f"Validation micro F1: {multimodal_model_report.get('best_validation_f1', 0.0):.3f}",
                f"Validation precision: {validation_metrics.get('micro_precision', 0.0):.3f}",
                f"Validation recall: {validation_metrics.get('micro_recall', 0.0):.3f}",
                f"Validation positive predictions vs labels: {validation_metrics.get('positive_predictions', 0)} vs {validation_metrics.get('positive_labels', 0)}",
                f"Audio-enabled examples: {multimodal_model_report.get('audio_enabled_example_count', 0)}",
                f"Text-enabled examples: {multimodal_model_report.get('text_enabled_example_count', 0)}",
                f"Visual embeddings: index_hits={embedding_prep.get('visual_index_hit_count', 0)}, on_demand={embedding_prep.get('visual_on_demand_count', 0)}",
                f"Transcript embeddings: {embedding_prep.get('transcript_embedding_count', 0)}",
                f"Audio semantic embeddings: {embedding_prep.get('audio_semantic_embedding_count', 0)}",
            ]
        ),
        "",
        "Current read: the model is training on real TTrades/Youtube/chart cases now, but it is still recall-heavy and overpredicts labels. It is finding many candidate setup signals, but it needs review to become precise.",
        "",
        "## Current Blockers",
        "",
        bullet_list(
            [
                f"Weak visual review status counts: {json.dumps(review_status_counts, sort_keys=True)}",
                f"Weak visual training blocker counts: {json.dumps(training_blockers, sort_keys=True)}",
                f"Multimodal review candidates: {multimodal_loop_report.get('multimodal_review_queue', {}).get('review_candidate_count', 0)}",
                f"High-priority disagreement cases: {multimodal_loop_report.get('multimodal_review_queue', {}).get('priority_band_counts', {}).get('high', 0)}",
                f"Ready to promote into teacher set: {multimodal_loop_report.get('multimodal_review_queue', {}).get('ready_to_promote_count', 0)}",
            ]
        ),
        "",
        build_case_section("Real Weak Training Examples", weak_examples),
        build_case_section("Teacher Baseline Examples In The Blended Set", teacher_examples),
        build_case_section("Top Neural Disagreement Cases", review_examples, include_predictions=True),
        "## Reference Files",
        "",
        bullet_list(
            [
                str(DEFAULT_WEAK_VISUAL_DATASET.relative_to(ROOT)),
                str(DEFAULT_BLENDED_MULTIMODAL_DATASET.relative_to(ROOT)),
                str(DEFAULT_REVIEW_QUEUE.relative_to(ROOT)),
                str(DEFAULT_MULTIMODAL_LOOP_REPORT.relative_to(ROOT)),
                str(DEFAULT_MULTIMODAL_MODEL_REPORT.relative_to(ROOT)),
            ]
        ),
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export a readable snapshot of TTFM neural training progress.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Markdown output path.")
    args = parser.parse_args()

    output_path = args.output
    if not output_path.is_absolute():
        output_path = (ROOT / output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_snapshot(), encoding="utf-8")
    print(output_path)


if __name__ == "__main__":
    main()
