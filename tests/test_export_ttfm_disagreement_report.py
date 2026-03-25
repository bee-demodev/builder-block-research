from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import export_ttfm_disagreement_report as etdr


def make_case_packet_report() -> dict:
    return {
        "case_packets": [
            {
                "case_ref": "demo_case",
                "topic": "bias",
                "supporting_topics": ["bias", "equilibrium"],
                "timeframe_stack": {
                    "htf": "higher",
                    "etf": "intraday",
                    "ltf": "lower",
                },
                "checkpoints": [
                    {
                        "checkpoint": "context",
                        "timeframe_role": "htf",
                        "screenshot_status": "attached",
                        "expected_component_labels": ["equilibrium", "point_of_interest"],
                        "active_label_provenance": "anchor_manual",
                        "labels_by_provenance": {
                            "anchor_manual": ["equilibrium", "point_of_interest"]
                        },
                    },
                    {
                        "checkpoint": "sweep",
                        "timeframe_role": "etf",
                        "screenshot_status": "attached",
                        "expected_component_labels": [],
                        "active_label_provenance": "rule_derived",
                        "labels_by_provenance": {"rule_derived": []},
                    },
                    {
                        "checkpoint": "closure",
                        "timeframe_role": "ltf",
                        "screenshot_status": "attached",
                        "expected_component_labels": ["candle_2_closure"],
                        "active_label_provenance": "anchor_manual",
                        "labels_by_provenance": {
                            "anchor_manual": ["candle_2_closure"]
                        },
                    },
                    {
                        "checkpoint": "confirmation",
                        "timeframe_role": "ltf",
                        "screenshot_status": "attached",
                        "expected_component_labels": ["protected_swing"],
                        "active_label_provenance": "rule_derived",
                        "labels_by_provenance": {"rule_derived": ["protected_swing"]},
                    },
                ],
            }
        ]
    }


class BuildDisagreementReportTests(unittest.TestCase):
    def test_report_scores_sequence_timeframe_and_rule_mismatches(self) -> None:
        report = make_case_packet_report()
        predictions = [
            {
                "case_ref": "demo_case",
                "checkpoint": "context",
                "predicted_labels": ["point_of_interest"],
                "label_confidences": {"point_of_interest": 0.9},
            },
            {
                "case_ref": "demo_case",
                "checkpoint": "sweep",
                "predicted_labels": ["candle_2_closure"],
                "label_confidences": {"candle_2_closure": 0.8},
            },
            {
                "case_ref": "demo_case",
                "checkpoint": "confirmation",
                "predicted_labels": ["protected_swing", "order_block"],
                "label_confidences": {"protected_swing": 0.9, "order_block": 0.55},
            },
        ]

        disagreement = etdr.build_disagreement_report(report, predictions)

        self.assertEqual(disagreement["summary"]["evaluated_checkpoint_count"], 4)
        self.assertGreater(disagreement["summary"]["anchor_case_regressions"], 0)
        self.assertLess(disagreement["summary"]["sequence_consistency"], 1.0)
        self.assertLess(disagreement["summary"]["timeframe_consistency"], 1.0)
        self.assertGreater(disagreement["summary"]["rule_mismatch_count"], 0)
        self.assertIn("point_of_interest", disagreement["per_label_metrics"])
        self.assertGreater(len(disagreement["mistake_clusters"]), 0)


if __name__ == "__main__":
    unittest.main()
