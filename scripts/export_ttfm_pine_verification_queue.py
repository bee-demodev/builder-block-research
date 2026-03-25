from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from export_ttfm_case_packets import DEFAULT_OUTPUT as DEFAULT_CASE_PACKET_PATH


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "results" / "ttfm_pine_verification_queue.json"
MIN_MATURE_EXAMPLES = 2


def load_case_packet_report(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_pine_verification_queue(
    case_packet_report: dict,
    *,
    min_mature_examples: int = MIN_MATURE_EXAMPLES,
) -> dict:
    candidate_items: dict[str, list[dict]] = defaultdict(list)

    for packet in case_packet_report.get("case_packets", []):
        for checkpoint in packet.get("checkpoints", []):
            if checkpoint.get("screenshot_status") != "attached":
                continue
            if checkpoint.get("active_label_provenance") != "anchor_manual":
                continue
            if not checkpoint.get("evidence_refs"):
                continue

            for label in checkpoint.get("expected_component_labels", []):
                candidate_items[label].append(
                    {
                        "queue_id": f"{packet['case_ref']}::{checkpoint['checkpoint']}::{label}",
                        "case_ref": packet["case_ref"],
                        "checkpoint": checkpoint["checkpoint"],
                        "component_label": label,
                        "topic": packet.get("topic"),
                        "supporting_topics": packet.get("supporting_topics", []),
                        "draft_spec_keys": packet.get("draft_spec_keys", []),
                        "screenshot_path": checkpoint.get("screenshot_path"),
                        "annotation_notes": checkpoint.get("annotation_notes", []),
                        "evidence_refs": checkpoint.get("evidence_refs", []),
                    }
                )

    queue_items: list[dict] = []
    component_maturity: dict[str, dict] = {}
    for label, items in sorted(candidate_items.items()):
        eligible_example_count = len(items)
        queue_ready = eligible_example_count >= min_mature_examples
        component_maturity[label] = {
            "eligible_example_count": eligible_example_count,
            "queue_ready": queue_ready,
        }
        if queue_ready:
            queue_items.extend(items)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "queue_ready_component_count": sum(
                1 for item in component_maturity.values() if item["queue_ready"]
            ),
            "queue_item_count": len(queue_items),
            "min_mature_examples": min_mature_examples,
        },
        "component_maturity": component_maturity,
        "queue_items": queue_items,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Queue visually grounded TTFM components for Pine verification."
    )
    parser.add_argument("--case-packets", default=str(DEFAULT_CASE_PACKET_PATH))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--min-mature-examples", type=int, default=MIN_MATURE_EXAMPLES)
    args = parser.parse_args()

    case_packet_report = load_case_packet_report(Path(args.case_packets))
    queue = build_pine_verification_queue(
        case_packet_report,
        min_mature_examples=args.min_mature_examples,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(queue, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output_path),
                "queue_ready_component_count": queue["summary"]["queue_ready_component_count"],
                "queue_item_count": queue["summary"]["queue_item_count"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
