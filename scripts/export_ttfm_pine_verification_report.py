from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from export_ttfm_pine_verification_queue import DEFAULT_OUTPUT as DEFAULT_QUEUE_PATH


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "results" / "ttfm_pine_verification_report.json"


def safe_divide(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_results(path: Path) -> list[dict]:
    if not path.exists():
        return []
    results: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        cleaned = line.strip()
        if cleaned:
            results.append(json.loads(cleaned))
    return results


def build_pine_verification_report(queue: dict, results: list[dict]) -> dict:
    result_lookup = {str(item.get("queue_id", "")).strip(): item for item in results}
    reproducible_count = 0
    partial_count = 0
    not_reproducible_count = 0
    verification_items: list[dict] = []
    feedback_candidates: list[dict] = []

    for item in queue.get("queue_items", []):
        queue_id = str(item.get("queue_id", "")).strip()
        result = result_lookup.get(queue_id, {})
        status = str(result.get("verification_status", "pending")).strip() or "pending"

        if status == "reproducible":
            reproducible_count += 1
        elif status == "partial":
            partial_count += 1
        elif status == "not_reproducible":
            not_reproducible_count += 1
            feedback_candidates.append(
                {
                    "id": f"{queue_id}::open-question",
                    "target_type": "open_question",
                    "target_path": f"topics/{item.get('topic')}/open_questions.md",
                    "question": (
                        result.get("notes")
                        or f"Pine could not reproduce the {item['component_label']} markup deterministically."
                    ),
                }
            )
            if item.get("draft_spec_keys"):
                feedback_candidates.append(
                    {
                        "id": f"{queue_id}::draft-spec",
                        "target_type": "draft_spec",
                        "target_path": f"results/indicator_specs/{item['draft_spec_keys'][0].split('__', 1)[-1]}.json",
                        "question": (
                            result.get("notes")
                            or f"Clarify deterministic Pine translation for {item['component_label']}."
                        ),
                        "affected_component": item["component_label"],
                        "topic_refs": item.get("supporting_topics", []),
                    }
                )
            feedback_candidates.append(
                {
                    "id": f"{queue_id}::finding",
                    "target_type": "finding",
                    "target_path": "findings.md",
                    "title": f"Pine verification failed for {item['component_label']}",
                    "body": result.get("notes")
                    or f"Pine could not deterministically reproduce {item['component_label']} from anchored screenshot markup.",
                }
            )

        verification_items.append(
            {
                **item,
                "verification_status": status,
                "notes": result.get("notes"),
            }
        )

    attempted_item_count = reproducible_count + partial_count + not_reproducible_count
    translatability_score = safe_divide(
        reproducible_count + (0.5 * partial_count),
        attempted_item_count,
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "queue_ready_component_count": queue.get("summary", {}).get("queue_ready_component_count", 0),
            "queue_item_count": queue.get("summary", {}).get("queue_item_count", 0),
            "attempted_item_count": attempted_item_count,
            "reproducible_count": reproducible_count,
            "partial_count": partial_count,
            "not_reproducible_count": not_reproducible_count,
            "translatability_score": round(translatability_score, 4),
            "feedback_candidate_count": len(feedback_candidates),
        },
        "verification_items": verification_items,
        "feedback_candidates": feedback_candidates,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Summarize Pine verification attempts for visually grounded TTFM components."
    )
    parser.add_argument("--queue", default=str(DEFAULT_QUEUE_PATH))
    parser.add_argument("--results")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    queue = load_json(Path(args.queue))
    results = load_results(Path(args.results)) if args.results else []
    report = build_pine_verification_report(queue, results)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output_path),
                "attempted_item_count": report["summary"]["attempted_item_count"],
                "translatability_score": report["summary"]["translatability_score"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
