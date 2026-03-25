from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATASET_PATH = ROOT / "results" / "ttfm_video_weak_visual_dataset.jsonl"
DEFAULT_OUTPUT = ROOT / "results" / "ttfm_weak_visual_promotion_queue.json"

PROMOTABLE_REVIEW_STATUSES = {
    "approved_for_teacher",
    "teacher_approved",
    "promoted_to_teacher",
}
BLOCKED_CONTRADICTION_STATUSES = {
    "blocked",
    "contradiction_confirmed",
    "needs_reconciliation",
}
CHECKPOINT_WEIGHTS = {
    "confirmation": 18,
    "closure": 15,
    "sweep": 10,
    "outcome": 8,
    "context": 6,
}


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


def classify_recommended_action(row: dict[str, Any]) -> str:
    review_status = str(row.get("review_status", "")).strip() or "unknown"
    contradiction_status = str(row.get("contradiction_status", "")).strip() or "unknown"
    screenshot_path = str(row.get("screenshot_path", "")).strip()
    active_labels = normalize_string_list(row.get("active_labels"))

    if not screenshot_path:
        return "skip_missing_frame"
    if not active_labels:
        return "collect_more_label_evidence"
    if contradiction_status in BLOCKED_CONTRADICTION_STATUSES:
        return "resolve_contradiction_before_review"
    if review_status in PROMOTABLE_REVIEW_STATUSES:
        return "promote_into_teacher_surface"
    return "review_for_teacher_promotion"


def compute_priority_score(row: dict[str, Any], *, recommended_action: str) -> tuple[int, list[str]]:
    checkpoint = str(row.get("checkpoint", "")).strip() or "unknown"
    active_labels = normalize_string_list(row.get("active_labels"))
    evidence_refs = normalize_string_list(row.get("evidence_refs"))
    confidence = float(row.get("weak_label_confidence", 0.35) or 0.35)

    action_base = {
        "promote_into_teacher_surface": 80,
        "review_for_teacher_promotion": 50,
        "resolve_contradiction_before_review": 10,
        "collect_more_label_evidence": 5,
        "skip_missing_frame": 0,
    }.get(recommended_action, 0)
    checkpoint_bonus = CHECKPOINT_WEIGHTS.get(checkpoint, 4)
    label_bonus = min(len(active_labels), 4) * 4
    evidence_bonus = min(len(evidence_refs), 3) * 2
    confidence_bonus = int(round(confidence * 10))

    score = action_base + checkpoint_bonus + label_bonus + evidence_bonus + confidence_bonus
    reasons = [
        f"action:{recommended_action}",
        f"checkpoint:{checkpoint}",
        f"labels:{len(active_labels)}",
        f"confidence:{confidence:.2f}",
    ]
    if evidence_refs:
        reasons.append(f"evidence_refs:{len(evidence_refs)}")
    return score, reasons


def classify_priority_band(score: int) -> str:
    if score >= 80:
        return "high"
    if score >= 50:
        return "medium"
    return "low"


def build_queue_item(row: dict[str, Any]) -> dict[str, Any]:
    recommended_action = classify_recommended_action(row)
    priority_score, priority_reasons = compute_priority_score(
        row,
        recommended_action=recommended_action,
    )
    return {
        "example_id": str(row.get("example_id", "")).strip(),
        "case_ref": str(row.get("case_ref", "")).strip(),
        "video_slug": str(row.get("video_slug", "")).strip() or None,
        "title": str(row.get("title", "")).strip() or None,
        "checkpoint": str(row.get("checkpoint", "")).strip() or "unknown",
        "active_labels": normalize_string_list(row.get("active_labels")),
        "weak_label_confidence": float(row.get("weak_label_confidence", 0.35) or 0.35),
        "review_status": str(row.get("review_status", "")).strip() or "unknown",
        "contradiction_status": str(row.get("contradiction_status", "")).strip() or "unknown",
        "screenshot_path": str(row.get("screenshot_path", "")).strip() or None,
        "evidence_refs": normalize_string_list(row.get("evidence_refs")),
        "recommended_action": recommended_action,
        "priority_score": priority_score,
        "priority_band": classify_priority_band(priority_score),
        "priority_reasons": priority_reasons,
    }


def build_weak_visual_promotion_queue(rows: list[dict[str, Any]]) -> dict[str, Any]:
    items = [build_queue_item(row) for row in rows]
    items.sort(
        key=lambda item: (
            -int(item["priority_score"]),
            str(item["checkpoint"]),
            str(item["example_id"]),
        )
    )

    action_counts: Counter[str] = Counter()
    priority_band_counts: Counter[str] = Counter()
    for item in items:
        action_counts[str(item["recommended_action"])] += 1
        priority_band_counts[str(item["priority_band"])] += 1

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "row_count": len(items),
            "ready_to_promote_count": action_counts.get("promote_into_teacher_surface", 0),
            "review_candidate_count": action_counts.get("review_for_teacher_promotion", 0),
            "blocked_contradiction_count": action_counts.get(
                "resolve_contradiction_before_review",
                0,
            ),
            "missing_frame_count": action_counts.get("skip_missing_frame", 0),
            "recommended_action_counts": dict(sorted(action_counts.items())),
            "priority_band_counts": dict(sorted(priority_band_counts.items())),
        },
        "items": items,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Rank weak visual rows into a promotion queue for teacher review and future "
            "promotion into the visual training surface."
        )
    )
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET_PATH))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    queue = build_weak_visual_promotion_queue(load_jsonl_rows(Path(args.dataset)))
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(queue, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output_path),
                "row_count": queue["summary"]["row_count"],
                "review_candidate_count": queue["summary"]["review_candidate_count"],
                "ready_to_promote_count": queue["summary"]["ready_to_promote_count"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
