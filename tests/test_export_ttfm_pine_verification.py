from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import export_ttfm_pine_verification_queue as etpvq
import export_ttfm_pine_verification_report as etpvr


def make_case_packet_report() -> dict:
    packets = []
    for index in range(2):
        packets.append(
            {
                "case_ref": f"demo_case_{index}",
                "topic": "continuation",
                "supporting_topics": ["continuation", "equilibrium"],
                "draft_spec_keys": ["ttrades_curriculum__continuation_entry_model"],
                "checkpoints": [
                    {
                        "checkpoint": "context",
                        "timeframe_role": "htf",
                        "screenshot_status": "attached",
                        "screenshot_path": f"artifacts/ttfm/demo/context_{index}.png",
                        "expected_component_labels": ["point_of_interest"],
                        "active_label_provenance": "anchor_manual",
                        "labels_by_provenance": {
                            "anchor_manual": ["point_of_interest"]
                        },
                        "annotation_notes": ["HTF POI marked"],
                        "evidence_refs": ["topics/continuation/examples.md#poi"],
                    }
                ],
            }
        )
    packets.append(
        {
            "case_ref": "single_case",
            "topic": "continuation",
            "supporting_topics": ["continuation"],
            "draft_spec_keys": ["ttrades_curriculum__continuation_entry_model"],
            "checkpoints": [
                {
                    "checkpoint": "confirmation",
                    "timeframe_role": "ltf",
                    "screenshot_status": "attached",
                    "screenshot_path": "artifacts/ttfm/demo/confirmation.png",
                    "expected_component_labels": ["protected_swing"],
                    "active_label_provenance": "anchor_manual",
                    "labels_by_provenance": {
                        "anchor_manual": ["protected_swing"]
                    },
                    "annotation_notes": ["Protected swing confirmed"],
                    "evidence_refs": ["topics/protected_swings/examples.md#demo"],
                }
            ],
        }
    )
    return {"case_packets": packets}


class PineVerificationQueueTests(unittest.TestCase):
    def test_queue_only_includes_mature_components(self) -> None:
        queue = etpvq.build_pine_verification_queue(make_case_packet_report())

        labels = {item["component_label"] for item in queue["queue_items"]}
        self.assertIn("point_of_interest", labels)
        self.assertNotIn("protected_swing", labels)
        self.assertGreaterEqual(
            queue["component_maturity"]["point_of_interest"]["eligible_example_count"],
            2,
        )


class PineVerificationReportTests(unittest.TestCase):
    def test_report_surfaces_open_questions_and_findings_candidates(self) -> None:
        queue = etpvq.build_pine_verification_queue(make_case_packet_report())
        results = [
            {
                "queue_id": queue["queue_items"][0]["queue_id"],
                "verification_status": "not_reproducible",
                "notes": "POI boundary depends on discretionary drawing.",
            }
        ]

        report = etpvr.build_pine_verification_report(queue, results)

        self.assertEqual(report["summary"]["attempted_item_count"], 1)
        self.assertEqual(report["summary"]["not_reproducible_count"], 1)
        self.assertLess(report["summary"]["translatability_score"], 1.0)
        self.assertGreater(len(report["feedback_candidates"]), 0)
        self.assertIn(
            report["feedback_candidates"][0]["target_type"],
            {"finding", "open_question", "draft_spec"},
        )


if __name__ == "__main__":
    unittest.main()
