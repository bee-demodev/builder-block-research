from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import export_ttfm_training_loop_report as ettlr


class BuildTrainingLoopReportTests(unittest.TestCase):
    def test_strong_loop_is_kept(self) -> None:
        report = ettlr.build_training_loop_report(
            {
                "data_quality": 0.92,
                "label_quality": 0.9,
                "model_quality": 0.88,
                "research_yield": 0.81,
                "regression_safety": 0.95,
                "anchor_case_regressions": 0,
                "rule_mismatch_delta": -0.08,
                "relabel_churn": 0.08,
            }
        )

        self.assertEqual(report["verdict"], "keep")
        self.assertGreaterEqual(report["loop_score"], 0.85)
        self.assertIn(report["grade"], {"A", "A-"})

    def test_regression_heavy_loop_is_not_accepted_even_if_average_is_okay(self) -> None:
        report = ettlr.build_training_loop_report(
            {
                "data_quality": 0.84,
                "label_quality": 0.8,
                "model_quality": 0.83,
                "research_yield": 0.75,
                "regression_safety": 0.42,
                "anchor_case_regressions": 3,
                "rule_mismatch_delta": 0.11,
                "relabel_churn": 0.44,
            }
        )

        self.assertIn(report["verdict"], {"discard", "investigate"})
        self.assertGreater(len(report["warnings"]), 0)
        self.assertLess(report["bucket_scores"]["regression_safety"], 0.5)

    def test_metrics_can_be_built_from_disagreement_and_pine_reports(self) -> None:
        case_packet_report = {
            "summary": {
                "case_count": 12,
                "checkpoint_count": 60,
                "missing_screenshot_count": 6,
                "missing_anchor_label_count": 12,
                "missing_evidence_ref_count": 10,
                "screenshot_coverage": 0.9,
                "anchor_coverage": 0.8,
                "multi_timeframe_case_ratio": 0.75,
            }
        }
        disagreement_report = {
            "summary": {
                "evaluated_checkpoint_count": 24,
                "macro_f1": 0.82,
                "timeframe_consistency": 0.86,
                "sequence_consistency": 0.8,
                "anchor_case_regressions": 1,
                "anchor_checkpoint_count": 20,
                "rule_mismatch_count": 2,
                "rule_mismatch_rate": 0.08,
                "mistake_cluster_count": 4,
            }
        }
        pine_verification_report = {
            "summary": {
                "queue_ready_component_count": 3,
                "attempted_item_count": 4,
                "translatability_score": 0.65,
                "feedback_candidate_count": 3,
            }
        }
        tradingview_pine_report = {
            "summary": {
                "workflow_score": 0.78,
                "generated_script_coverage": 0.8,
                "validation_coverage": 0.5,
                "playwriter_validated_count": 2,
            }
        }

        metrics = ettlr.build_metrics_from_reports(
            case_packet_report,
            disagreement_report=disagreement_report,
            pine_verification_report=pine_verification_report,
            tradingview_pine_report=tradingview_pine_report,
        )
        report = ettlr.build_training_loop_report(metrics)

        self.assertGreater(metrics["model_quality"], 0.0)
        self.assertGreater(metrics["research_yield"], 0.0)
        self.assertGreater(metrics["label_quality"], 0.0)
        self.assertIn("rule_mismatch_rate", metrics)
        self.assertIn("tradingview_workflow_score", metrics)
        self.assertIn(report["verdict"], {"keep_with_warnings", "investigate", "keep"})

    def test_empty_disagreement_report_does_not_fake_model_progress(self) -> None:
        case_packet_report = {
            "summary": {
                "case_count": 14,
                "checkpoint_count": 70,
                "missing_screenshot_count": 70,
                "missing_anchor_label_count": 70,
                "missing_evidence_ref_count": 0,
                "screenshot_coverage": 0.0,
                "anchor_coverage": 0.0,
                "multi_timeframe_case_ratio": 0.7857,
            }
        }
        disagreement_report = {
            "summary": {
                "evaluated_checkpoint_count": 0,
                "anchor_checkpoint_count": 0,
                "anchor_case_regressions": 0,
                "anchor_label_agreement": 1.0,
                "macro_f1": 0.0,
                "timeframe_consistency": 1.0,
                "sequence_consistency": 1.0,
                "rule_mismatch_rate": 0.0,
                "mistake_cluster_count": 0,
            }
        }

        metrics = ettlr.build_metrics_from_reports(
            case_packet_report,
            disagreement_report=disagreement_report,
            pine_verification_report={"summary": {}},
            tradingview_pine_report={"summary": {}},
        )

        self.assertEqual(metrics["model_quality"], 0.0)
        self.assertTrue(metrics["bootstrap_only"])


if __name__ == "__main__":
    unittest.main()
