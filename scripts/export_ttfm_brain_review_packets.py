from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from export_ttfm_multimodal_review_queue import CHECKPOINT_WEIGHTS, load_jsonl_rows


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_QUEUE_PATH = ROOT / "results" / "ttfm_multimodal_review_queue.json"
DEFAULT_DATASET_PATH = ROOT / "results" / "ttfm_video_multimodal_dataset.jsonl"
DEFAULT_OUTPUT = ROOT / "results" / "ttfm_brain_review_packets.json"
DEFAULT_LIMIT = 10


def load_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return dict(default or {})
    return json.loads(path.read_text(encoding="utf-8"))


def build_dataset_lookup(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("example_id", "")).strip(): row
        for row in rows
        if str(row.get("example_id", "")).strip()
    }


def transcript_snippet(value: object, *, max_chars: int = 320) -> str | None:
    cleaned = str(value or "").strip()
    if not cleaned:
        return None
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 3].rstrip() + "..."


def recommended_reviewer_action(queue_item: dict[str, Any]) -> str:
    action = str(queue_item.get("recommended_action", "")).strip()
    if action == "review_model_disagreement":
        return "Compare weak labels against model probabilities and correct the label set."
    if action == "promote_into_teacher_surface":
        return "Verify the agreement and promote this example into the teacher surface."
    if action == "resolve_contradiction_before_review":
        return "Resolve contradiction status before using this example for training."
    if action == "collect_more_multimodal_evidence":
        return "Gather more context before trusting this example."
    return "Review this example and decide whether to keep, relabel, or defer it."


def build_review_packet(
    queue_item: dict[str, Any],
    *,
    dataset_row: dict[str, Any] | None,
) -> dict[str, Any]:
    dataset_row = dataset_row or {}
    return {
        "example_id": str(queue_item.get("example_id", "")).strip(),
        "case_ref": str(queue_item.get("case_ref", "")).strip() or None,
        "title": str(queue_item.get("title", "")).strip() or None,
        "checkpoint": str(queue_item.get("checkpoint", "")).strip() or "unknown",
        "framework_slug": str(queue_item.get("framework_slug", "ttfm")).strip() or "ttfm",
        "profile_slug": str(queue_item.get("profile_slug", "ttrades_curriculum")).strip()
        or "ttrades_curriculum",
        "brain_type": str(queue_item.get("brain_type", "setup_scorer")).strip() or "setup_scorer",
        "embedding_backend": str(queue_item.get("embedding_backend", "google_gemini")).strip()
        or "google_gemini",
        "priority_score": int(queue_item.get("priority_score", 0) or 0),
        "priority_band": str(queue_item.get("priority_band", "low")).strip() or "low",
        "priority_reasons": list(queue_item.get("priority_reasons", [])),
        "recommended_action": str(queue_item.get("recommended_action", "")).strip() or "review",
        "reviewer_action": recommended_reviewer_action(queue_item),
        "weak_labels": list(queue_item.get("weak_active_labels", [])),
        "predicted_labels": list(queue_item.get("predicted_labels", [])),
        "label_probabilities": dict(queue_item.get("label_probabilities", {})),
        "prediction_threshold_mode": str(
            queue_item.get("prediction_threshold_mode", "global")
        ).strip()
        or "global",
        "prediction_thresholds": queue_item.get("prediction_thresholds"),
        "prediction_threshold": queue_item.get("prediction_threshold"),
        "disagreement_count": int(queue_item.get("disagreement_count", 0) or 0),
        "missing_weak_labels": list(queue_item.get("missing_weak_labels", [])),
        "extra_predicted_labels": list(queue_item.get("extra_predicted_labels", [])),
        "uncertainty_labels": list(queue_item.get("uncertainty_labels", [])),
        "weak_label_confidence": float(queue_item.get("weak_label_confidence", 0.35) or 0.35),
        "sample_weight": float(queue_item.get("sample_weight", 0.35) or 0.35),
        "screenshot_path": queue_item.get("screenshot_path") or dataset_row.get("screenshot_path"),
        "audio_path": queue_item.get("audio_path") or dataset_row.get("audio_path"),
        "transcript_snippet": transcript_snippet(
            dataset_row.get("transcript_text", queue_item.get("transcript_text"))
        ),
        "evidence_refs": list(queue_item.get("evidence_refs", [])),
    }


def build_brain_review_packets(
    queue: dict[str, Any],
    *,
    dataset_rows: list[dict[str, Any]],
    limit: int = DEFAULT_LIMIT,
) -> dict[str, Any]:
    dataset_lookup = build_dataset_lookup(dataset_rows)
    queue_items = list(queue.get("items", []))
    queue_items.sort(
        key=lambda item: (
            -int(item.get("disagreement_count", 0) or 0),
            -CHECKPOINT_WEIGHTS.get(str(item.get("checkpoint", "")).strip(), 0),
            str(item.get("example_id", "")),
        )
    )
    selected_items = queue_items[: max(0, int(limit))]
    packets = [
        build_review_packet(
            item,
            dataset_row=dataset_lookup.get(str(item.get("example_id", "")).strip()),
        )
        for item in selected_items
    ]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "packet_count": len(packets),
            "source_queue_row_count": int(queue.get("summary", {}).get("row_count", 0) or 0),
            "requested_limit": int(limit),
        },
        "packets": packets,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export top-priority TTFM brain review packets from the multimodal review queue."
    )
    parser.add_argument("--queue", default=str(DEFAULT_QUEUE_PATH))
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET_PATH))
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    packets = build_brain_review_packets(
        load_json(Path(args.queue), {"items": [], "summary": {}}),
        dataset_rows=load_jsonl_rows(Path(args.dataset)),
        limit=args.limit,
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(packets, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "output": str(output_path),
                "packet_count": packets["summary"]["packet_count"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
