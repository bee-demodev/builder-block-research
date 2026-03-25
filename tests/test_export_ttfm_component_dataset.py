from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import export_ttfm_component_dataset as etcd


def make_case_packet_report() -> dict:
    return {
        "summary": {
            "case_count": 1,
            "checkpoint_count": 2,
            "missing_screenshot_count": 1,
        },
        "case_packets": [
            {
                "case_ref": "demo_case",
                "topic": "continuation",
                "timeframe_stack": {
                    "htf": "higher",
                    "etf": "intraday",
                    "ltf": "lower",
                    "labels": ["higher", "intraday", "lower"],
                    "is_multi_timeframe": True,
                },
                "supporting_topics": ["continuation", "equilibrium"],
                "draft_spec_keys": ["ttrades_curriculum__continuation_entry_model"],
                "outcome": {"decision": "trade", "reason": "demo"},
                "checkpoints": [
                    {
                        "checkpoint": "context",
                        "timeframe": "higher",
                        "timeframe_role": "htf",
                        "screenshot_status": "attached",
                        "screenshot_path": "artifacts/ttfm/demo/context.png",
                        "expected_component_labels": ["point_of_interest"],
                        "active_label_provenance": "anchor_manual",
                        "labels_by_provenance": {
                            "anchor_manual": ["point_of_interest"],
                            "rule_derived": ["point_of_interest", "equilibrium"],
                        },
                        "annotation_notes": ["HTF POI marked"],
                        "evidence_refs": ["topics/continuation/examples.md#demo"],
                    },
                    {
                        "checkpoint": "closure",
                        "timeframe": "lower",
                        "timeframe_role": "ltf",
                        "screenshot_status": "missing",
                        "screenshot_path": None,
                        "expected_component_labels": ["candle_2_closure"],
                        "active_label_provenance": "rule_derived",
                        "labels_by_provenance": {
                            "rule_derived": ["candle_2_closure"]
                        },
                        "annotation_notes": [],
                        "evidence_refs": [],
                    },
                ],
            }
        ],
    }


class BuildComponentDatasetRowsTests(unittest.TestCase):
    def test_rows_include_only_attached_screenshot_checkpoints(self) -> None:
        report = make_case_packet_report()

        rows = etcd.build_component_dataset_rows(report)
        summary = etcd.summarize_component_dataset(rows, report)

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["case_ref"], "demo_case")
        self.assertEqual(row["checkpoint"], "context")
        self.assertEqual(row["timeframe_role"], "htf")
        self.assertEqual(row["active_labels"], ["point_of_interest"])
        self.assertEqual(row["active_label_provenance"], "anchor_manual")
        self.assertIn("anchor_manual", row["labels_by_provenance"])
        self.assertEqual(row["annotation_notes"], ["HTF POI marked"])
        self.assertEqual(row["screenshot_path"], "artifacts/ttfm/demo/context.png")
        self.assertEqual(summary["row_count"], 1)
        self.assertEqual(summary["skipped_missing_screenshot_count"], 1)


if __name__ == "__main__":
    unittest.main()
