from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TEACHER_DATASET_PATH = ROOT / "results" / "ttfm_teacher_augmented_visual_dataset.jsonl"
DEFAULT_MULTIMODAL_DATASET_PATH = ROOT / "results" / "ttfm_video_multimodal_dataset.jsonl"
DEFAULT_DATASET_OUTPUT = ROOT / "results" / "ttfm_blended_multimodal_dataset.jsonl"
DEFAULT_REPORT_OUTPUT = ROOT / "results" / "ttfm_blended_multimodal_dataset_report.json"
DEFAULT_WEAK_SAMPLE_WEIGHT = 0.35


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            cleaned = line.strip()
            if cleaned:
                rows.append(json.loads(cleaned))
    return rows


def normalize_sample_weight(value: object, *, default: float) -> float:
    try:
        weight = float(value)
    except (TypeError, ValueError):
        return default
    if weight <= 0.0:
        return default
    return weight


def normalize_optional_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def normalize_string_list(values: object) -> list[str]:
    if values is None:
        return []
    if isinstance(values, list):
        return [str(value).strip() for value in values if str(value).strip()]
    if isinstance(values, str):
        cleaned = values.strip()
        return [cleaned] if cleaned else []
    return []


def weak_row_is_training_eligible(row: dict) -> bool:
    if "eligible_for_training" in row and not bool(row.get("eligible_for_training")):
        return False
    if normalize_string_list(row.get("training_blockers")):
        return False
    if str(row.get("review_status", "")).strip() != "ready_for_weak_training":
        return False
    if not normalize_string_list(row.get("active_labels")):
        return False
    if not normalize_optional_text(row.get("screenshot_path")):
        return False
    return normalize_optional_text(row.get("transcript_source")) != "synthetic_from_video_metadata"


def merge_teacher_with_multimodal_row(
    teacher_row: dict,
    multimodal_row: dict | None,
) -> dict:
    merged_row = dict(teacher_row)
    merged_row["source_tier"] = str(teacher_row.get("source_tier", "")).strip() or "teacher"
    merged_row["source_dataset"] = str(teacher_row.get("source_dataset", "")).strip() or (
        "ttfm_teacher_augmented_visual_dataset"
    )
    merged_row["sample_weight"] = normalize_sample_weight(
        teacher_row.get("sample_weight"),
        default=1.0,
    )
    merged_row["framework_slug"] = str(teacher_row.get("framework_slug", "ttfm")).strip() or "ttfm"
    merged_row["profile_slug"] = (
        str(teacher_row.get("profile_slug", "ttrades_curriculum")).strip()
        or "ttrades_curriculum"
    )
    merged_row["brain_type"] = str(teacher_row.get("brain_type", "setup_scorer")).strip() or "setup_scorer"
    merged_row["embedding_backend"] = (
        str(teacher_row.get("embedding_backend", "google_gemini")).strip() or "google_gemini"
    )
    merged_row.setdefault("review_status", "teacher_visual_baseline")
    merged_row.setdefault("contradiction_status", "not_applicable")

    merged_row["audio_path"] = None
    merged_row["video_path"] = None
    merged_row["clip_duration_seconds"] = None
    merged_row["midpoint_seconds"] = None
    merged_row["window_start_seconds"] = None
    merged_row["window_end_seconds"] = None
    merged_row["transcript_text"] = ""
    merged_row["embedding_text"] = str(teacher_row.get("embedding_text", "")).strip()

    if multimodal_row is None:
        return merged_row

    merged_row["audio_path"] = multimodal_row.get("audio_path")
    merged_row["video_path"] = multimodal_row.get("video_path")
    merged_row["clip_duration_seconds"] = multimodal_row.get("clip_duration_seconds")
    merged_row["midpoint_seconds"] = multimodal_row.get("midpoint_seconds")
    merged_row["window_start_seconds"] = multimodal_row.get("window_start_seconds")
    merged_row["window_end_seconds"] = multimodal_row.get("window_end_seconds")
    merged_row["transcript_text"] = str(multimodal_row.get("transcript_text", "")).strip()
    merged_row["embedding_text"] = str(
        multimodal_row.get("embedding_text", merged_row.get("embedding_text", ""))
    ).strip()
    merged_row["source_url"] = merged_row.get("source_url") or multimodal_row.get("source_url")
    merged_row["source_page"] = merged_row.get("source_page") or multimodal_row.get("source_page")
    merged_row["source_chunk_id"] = multimodal_row.get("source_chunk_id")
    return merged_row


def build_blended_multimodal_dataset_rows(
    *,
    teacher_rows: list[dict],
    multimodal_rows: list[dict],
) -> list[dict]:
    rows: list[dict] = []
    multimodal_lookup = {
        str(row.get("example_id", "")).strip(): row
        for row in multimodal_rows
        if str(row.get("example_id", "")).strip()
    }
    consumed_example_ids: set[str] = set()

    for teacher_row in teacher_rows:
        example_id = str(teacher_row.get("example_id", "")).strip()
        matching_multimodal = multimodal_lookup.get(example_id)
        if matching_multimodal is not None and weak_row_is_training_eligible(matching_multimodal):
            consumed_example_ids.add(example_id)
        else:
            matching_multimodal = None
        rows.append(merge_teacher_with_multimodal_row(teacher_row, matching_multimodal))

    for multimodal_row in multimodal_rows:
        example_id = str(multimodal_row.get("example_id", "")).strip()
        if not example_id or example_id in consumed_example_ids:
            continue
        if not weak_row_is_training_eligible(multimodal_row):
            continue

        blended_row = dict(multimodal_row)
        blended_row["source_tier"] = "weak"
        blended_row["source_dataset"] = "ttfm_video_multimodal_dataset"
        blended_row["sample_weight"] = normalize_sample_weight(
            blended_row.get("sample_weight", blended_row.get("weak_label_confidence")),
            default=DEFAULT_WEAK_SAMPLE_WEIGHT,
        )
        blended_row["framework_slug"] = str(blended_row.get("framework_slug", "ttfm")).strip() or "ttfm"
        blended_row["profile_slug"] = (
            str(blended_row.get("profile_slug", "ttrades_curriculum")).strip()
            or "ttrades_curriculum"
        )
        blended_row["brain_type"] = str(blended_row.get("brain_type", "setup_scorer")).strip() or "setup_scorer"
        blended_row["embedding_backend"] = (
            str(blended_row.get("embedding_backend", "google_gemini")).strip() or "google_gemini"
        )
        blended_row.setdefault("review_status", "ready_for_weak_training")
        blended_row.setdefault("contradiction_status", "unreviewed")
        rows.append(blended_row)

    return rows


def summarize_blended_multimodal_dataset(
    rows: list[dict],
    *,
    teacher_row_count: int,
    deduped_overlap_count: int,
    excluded_weak_row_count: int,
) -> dict:
    source_tier_counts: Counter[str] = Counter()
    review_status_counts: Counter[str] = Counter()
    contradiction_status_counts: Counter[str] = Counter()
    audio_enabled_row_count = 0
    text_enabled_row_count = 0

    for row in rows:
        source_tier_counts[str(row.get("source_tier", "unknown"))] += 1
        review_status_counts[str(row.get("review_status", "unknown"))] += 1
        contradiction_status_counts[str(row.get("contradiction_status", "unknown"))] += 1
        if normalize_optional_text(row.get("audio_path")):
            audio_enabled_row_count += 1
        if normalize_optional_text(row.get("transcript_text")):
            text_enabled_row_count += 1

    return {
        "row_count": len(rows),
        "teacher_row_count": source_tier_counts.get("teacher", 0)
        + source_tier_counts.get("teacher_promoted_weak", 0),
        "weak_row_count": source_tier_counts.get("weak", 0),
        "excluded_weak_row_count": excluded_weak_row_count,
        "source_tier_counts": dict(sorted(source_tier_counts.items())),
        "review_status_counts": dict(sorted(review_status_counts.items())),
        "contradiction_status_counts": dict(sorted(contradiction_status_counts.items())),
        "audio_enabled_row_count": audio_enabled_row_count,
        "text_enabled_row_count": text_enabled_row_count,
        "deduped_overlap_count": deduped_overlap_count,
    }


def build_blended_multimodal_dataset_report(
    *,
    teacher_rows: list[dict],
    multimodal_rows: list[dict],
) -> tuple[list[dict], dict]:
    teacher_example_ids = {
        str(row.get("example_id", "")).strip()
        for row in teacher_rows
        if str(row.get("example_id", "")).strip()
    }
    deduped_overlap_count = sum(
        1
        for row in multimodal_rows
        if (
            str(row.get("example_id", "")).strip() in teacher_example_ids
            and weak_row_is_training_eligible(row)
        )
    )
    excluded_weak_row_count = sum(
        1
        for row in multimodal_rows
        if not weak_row_is_training_eligible(row)
    )
    rows = build_blended_multimodal_dataset_rows(
        teacher_rows=teacher_rows,
        multimodal_rows=multimodal_rows,
    )
    return rows, {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": summarize_blended_multimodal_dataset(
            rows,
            teacher_row_count=len(teacher_rows),
            deduped_overlap_count=deduped_overlap_count,
            excluded_weak_row_count=excluded_weak_row_count,
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Blend teacher visual rows with the video multimodal dataset so teacher examples keep "
            "full weight while matching video-backed examples retain transcript and audio evidence."
        )
    )
    parser.add_argument("--teacher-dataset", default=str(DEFAULT_TEACHER_DATASET_PATH))
    parser.add_argument("--multimodal-dataset", default=str(DEFAULT_MULTIMODAL_DATASET_PATH))
    parser.add_argument("--output", default=str(DEFAULT_DATASET_OUTPUT))
    parser.add_argument("--report-output", default=str(DEFAULT_REPORT_OUTPUT))
    args = parser.parse_args()

    teacher_rows = load_jsonl(Path(args.teacher_dataset))
    multimodal_rows = load_jsonl(Path(args.multimodal_dataset))
    rows, report = build_blended_multimodal_dataset_report(
        teacher_rows=teacher_rows,
        multimodal_rows=multimodal_rows,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "\n".join(json.dumps(row) for row in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )

    report_path = Path(args.report_output)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "dataset_output": str(output_path),
                "report_output": str(report_path),
                "row_count": report["summary"]["row_count"],
                "teacher_row_count": report["summary"]["teacher_row_count"],
                "weak_row_count": report["summary"]["weak_row_count"],
                "audio_enabled_row_count": report["summary"]["audio_enabled_row_count"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
