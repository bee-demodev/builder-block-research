from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TEACHER_DATASET_PATH = ROOT / "results" / "ttfm_teacher_visual_dataset.jsonl"
DEFAULT_WEAK_DATASET_PATH = ROOT / "results" / "ttfm_video_weak_visual_dataset.jsonl"
DEFAULT_DATASET_OUTPUT = ROOT / "results" / "ttfm_blended_visual_dataset.jsonl"
DEFAULT_REPORT_OUTPUT = ROOT / "results" / "ttfm_blended_visual_dataset_report.json"
DEFAULT_WEAK_SAMPLE_WEIGHT = 0.35


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
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
    if not str(row.get("screenshot_path", "")).strip():
        return False
    return str(row.get("transcript_source", "")).strip() != "synthetic_from_video_metadata"


def build_blended_visual_dataset_rows(
    *,
    teacher_rows: list[dict],
    weak_rows: list[dict],
) -> list[dict]:
    rows: list[dict] = []
    teacher_example_ids: set[str] = set()

    for row in teacher_rows:
        blended_row = dict(row)
        example_id = str(blended_row.get("example_id", "")).strip()
        if example_id:
            teacher_example_ids.add(example_id)
        blended_row["source_tier"] = "teacher"
        blended_row["source_dataset"] = "ttfm_teacher_visual_dataset"
        blended_row["sample_weight"] = normalize_sample_weight(
            blended_row.get("sample_weight"),
            default=1.0,
        )
        blended_row.setdefault("review_status", "teacher_visual_baseline")
        blended_row.setdefault("contradiction_status", "not_applicable")
        rows.append(blended_row)

    for row in weak_rows:
        example_id = str(row.get("example_id", "")).strip()
        if example_id and example_id in teacher_example_ids:
            continue
        if not weak_row_is_training_eligible(row):
            continue
        blended_row = dict(row)
        blended_row["source_tier"] = "weak"
        blended_row["source_dataset"] = "ttfm_video_weak_visual_dataset"
        blended_row["sample_weight"] = normalize_sample_weight(
            blended_row.get("sample_weight", blended_row.get("weak_label_confidence")),
            default=DEFAULT_WEAK_SAMPLE_WEIGHT,
        )
        blended_row.setdefault("review_status", "ready_for_weak_training")
        blended_row.setdefault("contradiction_status", "unreviewed")
        rows.append(blended_row)

    return rows


def summarize_blended_visual_dataset(
    rows: list[dict],
    *,
    deduped_overlap_count: int,
    excluded_weak_row_count: int,
) -> dict:
    source_tier_counts: Counter[str] = Counter()
    review_status_counts: Counter[str] = Counter()
    contradiction_status_counts: Counter[str] = Counter()

    for row in rows:
        source_tier_counts[str(row.get("source_tier", "unknown"))] += 1
        review_status_counts[str(row.get("review_status", "unknown"))] += 1
        contradiction_status_counts[str(row.get("contradiction_status", "unknown"))] += 1

    return {
        "row_count": len(rows),
        "teacher_row_count": source_tier_counts.get("teacher", 0),
        "weak_row_count": source_tier_counts.get("weak", 0),
        "excluded_weak_row_count": excluded_weak_row_count,
        "deduped_overlap_count": deduped_overlap_count,
        "source_tier_counts": dict(sorted(source_tier_counts.items())),
        "review_status_counts": dict(sorted(review_status_counts.items())),
        "contradiction_status_counts": dict(sorted(contradiction_status_counts.items())),
        "ready_for_weak_training_count": review_status_counts.get("ready_for_weak_training", 0),
    }


def build_blended_visual_dataset_report(
    *,
    teacher_rows: list[dict],
    weak_rows: list[dict],
) -> tuple[list[dict], dict]:
    teacher_example_ids = {
        str(row.get("example_id", "")).strip()
        for row in teacher_rows
        if str(row.get("example_id", "")).strip()
    }
    deduped_overlap_count = sum(
        1
        for row in weak_rows
        if str(row.get("example_id", "")).strip() in teacher_example_ids
    )
    excluded_weak_row_count = sum(
        1
        for row in weak_rows
        if (
            str(row.get("example_id", "")).strip() not in teacher_example_ids
            and not weak_row_is_training_eligible(row)
        )
    )
    rows = build_blended_visual_dataset_rows(
        teacher_rows=teacher_rows,
        weak_rows=weak_rows,
    )
    return rows, {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": summarize_blended_visual_dataset(
            rows,
            deduped_overlap_count=deduped_overlap_count,
            excluded_weak_row_count=excluded_weak_row_count,
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Blend the teacher screenshot dataset with the weak YouTube visual dataset "
            "to produce a retrain-ready corpus with explicit sample weights."
        )
    )
    parser.add_argument("--teacher-dataset", default=str(DEFAULT_TEACHER_DATASET_PATH))
    parser.add_argument("--weak-dataset", default=str(DEFAULT_WEAK_DATASET_PATH))
    parser.add_argument("--output", default=str(DEFAULT_DATASET_OUTPUT))
    parser.add_argument("--report-output", default=str(DEFAULT_REPORT_OUTPUT))
    args = parser.parse_args()

    teacher_rows = load_jsonl(Path(args.teacher_dataset))
    weak_rows = load_jsonl(Path(args.weak_dataset))
    rows, report = build_blended_visual_dataset_report(
        teacher_rows=teacher_rows,
        weak_rows=weak_rows,
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
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
