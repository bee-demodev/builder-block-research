from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def split_csv_list(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def resolve_path(root_dir: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root_dir / path


def relative_or_absolute(path: Path, root_dir: Path) -> str:
    try:
        return str(path.resolve().relative_to(root_dir.resolve()))
    except ValueError:
        return str(path)


@dataclass(frozen=True)
class BenchmarkFailureConfig:
    root_dir: Path
    queue_path: Path
    output_batch_path: Path
    output_answers_path: Path
    run_id: str


def recommended_action_for(row: dict[str, str]) -> str:
    reasons = set(split_csv_list(row.get("reasons")))
    hard_negative = str(row.get("hard_negative", "")).lower() == "true"
    if hard_negative or "hard_negative_false_positive" in reasons:
        return "review_hard_negative_false_positive"
    if "weak_class_miss" in reasons:
        return "review_weak_class_miss"
    if "false_positive" in reasons:
        return "review_class_confusion"
    return "review_positive_miss"


def build_item(row: dict[str, str], *, root_dir: Path) -> tuple[dict[str, Any] | None, str | None]:
    image_path = resolve_path(root_dir, row.get("image_path", ""))
    overlay_path = resolve_path(root_dir, row.get("overlay_path", ""))
    if not image_path.exists():
        return None, "missing_image_path"
    if not overlay_path.exists():
        return None, "missing_overlay_path"

    predicted_classes = split_csv_list(row.get("predicted_classes"))
    reasons = split_csv_list(row.get("reasons"))
    false_negative_classes = split_csv_list(row.get("false_negative_classes"))
    false_positive_classes = split_csv_list(row.get("false_positive_classes"))
    expected_classes = split_csv_list(row.get("expected_classes"))
    rank = int(row.get("rank") or 0)
    priority = float(row.get("priority") or 0.0)
    action = recommended_action_for(row)
    candidate_labels = sorted(set(predicted_classes))
    hard_negative = str(row.get("hard_negative", "")).lower() == "true"

    return (
        {
            "example_id": row.get("example_id", ""),
            "safe_name": row.get("safe_name", ""),
            "review_rank": rank,
            "score": priority,
            "review_priority_reason": reasons[0] if reasons else action,
            "recommended_action": action,
            "hard_negative": hard_negative,
            "image_path": str(image_path),
            "relative_image_path": relative_or_absolute(image_path, root_dir),
            "overlay_path": str(overlay_path),
            "relative_overlay_path": relative_or_absolute(overlay_path, root_dir),
            "candidate_labels": candidate_labels,
            "selection_reasons": [f"benchmark_failure:{reason}" for reason in reasons],
            "max_prediction_confidence": float(row.get("max_prediction_confidence") or 0.0),
            "benchmark_context": {
                "source": "runpod_benchmark_failure_queue",
                "expected_classes": expected_classes,
                "predicted_classes": predicted_classes,
                "false_negative_classes": false_negative_classes,
                "false_positive_classes": false_positive_classes,
                "matched_count": int(row.get("matched_count") or 0),
                "label_count": int(row.get("label_count") or 0),
                "prediction_count": int(row.get("prediction_count") or 0),
                "reasons": reasons,
            },
        },
        None,
    )


def build_answer_seed(batch: dict[str, Any]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for item in batch.get("items", []):
        note_bits = [
            "Benchmark failure review only; do not promote without manual review.",
            f"recommended_action={item.get('recommended_action', '')}",
        ]
        candidate_labels = [str(label) for label in item.get("candidate_labels", [])]
        if candidate_labels:
            note_bits.append(f"candidate_labels={','.join(candidate_labels)}")
        items.append(
            {
                "example_id": str(item.get("example_id", "")),
                "detections": [],
                "review_outcome": "ambiguous",
                "note": " ".join(bit for bit in note_bits if bit.strip()),
                "source": "benchmark_failure_review",
                "image_path": str(item.get("image_path", "")),
                "overlay_path": str(item.get("overlay_path", "")),
                "candidate_labels": candidate_labels,
                "recommended_action": str(item.get("recommended_action", "")),
                "score": item.get("score"),
            }
        )
    return {
        "generated_at": batch.get("generated_at"),
        "mode": "benchmark_failure_review_answers_seed",
        "source_packet_mode": batch.get("mode"),
        "instructions": (
            "Rows left as ambiguous are ignored by Phase 2 loaders. Copy reviewed rows into "
            "the normal supervision answer files only after adding manual detections or marking "
            "true hard negatives as no_setup."
        ),
        "items": items,
    }


def build_review_packet(config: BenchmarkFailureConfig) -> tuple[dict[str, Any], dict[str, Any]]:
    root_dir = config.root_dir.resolve()
    rows = list(csv.DictReader(config.queue_path.open(newline="", encoding="utf-8")))
    items: list[dict[str, Any]] = []
    exclusions: Counter[str] = Counter()
    action_counts: Counter[str] = Counter()
    candidate_counts: Counter[str] = Counter()

    for row in rows:
        item, exclusion = build_item(row, root_dir=root_dir)
        if item is None:
            exclusions[str(exclusion or "unknown")] += 1
            continue
        items.append(item)
        action_counts[str(item["recommended_action"])] += 1
        for label in item["candidate_labels"]:
            candidate_counts[str(label)] += 1

    generated_at = datetime.now(timezone.utc).isoformat()
    packet = {
        "generated_at": generated_at,
        "mode": "benchmark_failure_review",
        "run_id": config.run_id,
        "source_queue": str(config.queue_path),
        "instructions": (
            "Review benchmark failures without feeding held-out truth back into labels. "
            "Candidate labels come only from model predictions. Benchmark truth and misses "
            "are stored under benchmark_context for audit."
        ),
        "input_row_count": len(rows),
        "item_count": len(items),
        "exclusion_counts": dict(exclusions),
        "recommended_action_counts": dict(action_counts),
        "candidate_label_counts": dict(candidate_counts),
        "items": items,
    }
    return packet, build_answer_seed(packet)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert benchmark failure queue CSV into a safe review packet.")
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--output-batch", type=Path, required=True)
    parser.add_argument("--output-answers", type=Path, required=True)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--root-dir", type=Path, default=Path("."))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = BenchmarkFailureConfig(
        root_dir=args.root_dir,
        queue_path=resolve_path(args.root_dir, str(args.queue)),
        output_batch_path=resolve_path(args.root_dir, str(args.output_batch)),
        output_answers_path=resolve_path(args.root_dir, str(args.output_answers)),
        run_id=args.run_id,
    )
    packet, answer_seed = build_review_packet(config)
    config.output_batch_path.parent.mkdir(parents=True, exist_ok=True)
    config.output_answers_path.parent.mkdir(parents=True, exist_ok=True)
    config.output_batch_path.write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")
    config.output_answers_path.write_text(json.dumps(answer_seed, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "input_row_count": packet["input_row_count"],
                "item_count": packet["item_count"],
                "exclusion_counts": packet["exclusion_counts"],
                "recommended_action_counts": packet["recommended_action_counts"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
