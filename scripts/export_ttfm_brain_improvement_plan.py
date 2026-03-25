from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BRAIN_LOOP_REPORT_PATH = ROOT / "results" / "ttfm_brain_loop_report.json"
DEFAULT_REVIEW_QUEUE_PATH = ROOT / "results" / "ttfm_multimodal_review_queue.json"
DEFAULT_REVIEW_PACKETS_PATH = ROOT / "results" / "ttfm_brain_review_packets.json"
DEFAULT_OUTPUT = ROOT / "results" / "ttfm_brain_improvement_plan.json"


def load_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return dict(default or {})
    return json.loads(path.read_text(encoding="utf-8"))


def select_next_action(
    *,
    brain_loop_report: dict[str, Any],
    review_queue: dict[str, Any],
    review_packets: dict[str, Any],
) -> str:
    status = str(brain_loop_report.get("status", "")).strip()
    pine_status = str(brain_loop_report.get("pine_status", "")).strip()
    queue_summary = review_queue.get("summary", {})
    if pine_status == "ready_for_translation":
        return "brain_ready_for_pine"
    if status == "degraded":
        return "report_first"
    if int(queue_summary.get("model_disagreement_count", 0) or 0) > 0:
        return "review_top_disagreements"
    if int(queue_summary.get("ready_to_promote_count", 0) or 0) > 0:
        return "promote_clean_labels"
    if int(review_packets.get("summary", {}).get("packet_count", 0) or 0) > 0:
        return "retrain_after_review"
    return "refresh_brain_loop"


def build_priority_actions(
    *,
    next_action: str,
    review_packets: dict[str, Any],
    review_queue: dict[str, Any],
    brain_loop_report: dict[str, Any],
) -> list[dict[str, Any]]:
    top_packets = list(review_packets.get("packets", []))[:3]
    queue_summary = review_queue.get("summary", {})
    model_summary = brain_loop_report.get("multimodal_model", {})
    actions: list[dict[str, Any]] = []

    if next_action == "report_first":
        actions.append(
            {
                "priority": 1,
                "action": "stabilize_degraded_stage",
                "success_metric": "All hard and soft stages complete in a single run.",
                "details": f"Fix the degraded stage(s): {brain_loop_report.get('failed_optional_stages', [])}.",
            }
        )
    if next_action == "review_top_disagreements":
        actions.append(
            {
                "priority": 1,
                "action": "review_top_disagreements",
                "success_metric": "Top disagreement packets are reviewed and corrected.",
                "details": [packet.get("example_id") for packet in top_packets],
            }
        )
    if next_action == "promote_clean_labels":
        actions.append(
            {
                "priority": 1,
                "action": "promote_clean_labels",
                "success_metric": "Approved packets move into the teacher surface.",
                "details": int(queue_summary.get("ready_to_promote_count", 0) or 0),
            }
        )
    if next_action == "retrain_after_review":
        actions.append(
            {
                "priority": 1,
                "action": "retrain_after_review",
                "success_metric": "Validation precision rises and disagreement falls after review.",
                "details": {
                    "validation_micro_precision": model_summary.get("validation_micro_precision"),
                    "mean_disagreement_count": queue_summary.get("mean_disagreement_count"),
                },
            }
        )
    if next_action == "brain_ready_for_pine":
        actions.append(
            {
                "priority": 1,
                "action": "brain_ready_for_pine",
                "success_metric": "The Pine translation loop consumes stable brain outputs.",
                "details": "The brain loop met the consecutive healthy-run gate for Pine translation.",
            }
        )
    if not actions:
        actions.append(
            {
                "priority": 1,
                "action": "refresh_brain_loop",
                "success_metric": "A fresh brain loop completes with current inputs.",
                "details": "No blocking review packets or degraded stages remain.",
            }
        )
    return actions


def build_brain_improvement_plan(
    *,
    brain_loop_report: dict[str, Any],
    review_queue: dict[str, Any],
    review_packets: dict[str, Any],
) -> dict[str, Any]:
    next_action = select_next_action(
        brain_loop_report=brain_loop_report,
        review_queue=review_queue,
        review_packets=review_packets,
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "framework_slug": str(brain_loop_report.get("framework_slug", "ttfm")).strip() or "ttfm",
        "profile_slug": str(brain_loop_report.get("profile_slug", "ttrades_curriculum")).strip()
        or "ttrades_curriculum",
        "brain_type": str(brain_loop_report.get("brain_type", "setup_scorer")).strip()
        or "setup_scorer",
        "status": str(brain_loop_report.get("status", "unknown")).strip() or "unknown",
        "next_action": next_action,
        "pine_status": str(brain_loop_report.get("pine_status", "deferred")).strip() or "deferred",
        "priority_actions": build_priority_actions(
            next_action=next_action,
            review_packets=review_packets,
            review_queue=review_queue,
            brain_loop_report=brain_loop_report,
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the next-iteration improvement plan for the Gemini-first TTFM brain loop."
    )
    parser.add_argument("--brain-loop-report", default=str(DEFAULT_BRAIN_LOOP_REPORT_PATH))
    parser.add_argument("--review-queue", default=str(DEFAULT_REVIEW_QUEUE_PATH))
    parser.add_argument("--review-packets", default=str(DEFAULT_REVIEW_PACKETS_PATH))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    plan = build_brain_improvement_plan(
        brain_loop_report=load_json(Path(args.brain_loop_report), {}),
        review_queue=load_json(Path(args.review_queue), {"summary": {}, "items": []}),
        review_packets=load_json(Path(args.review_packets), {"summary": {}, "packets": []}),
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "output": str(output_path),
                "next_action": plan["next_action"],
                "status": plan["status"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
