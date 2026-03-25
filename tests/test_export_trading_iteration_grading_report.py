from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import export_trading_iteration_grading_report as etigr


def make_case_packet_report() -> dict:
    return {
        "summary": {"case_count": 2},
        "case_packets": [
            {
                "case_ref": "bias_case",
                "trade_models": ["daily_bias_framework"],
                "relation_types": ["bias_framework"],
                "checkpoints": [
                    {
                        "checkpoint": "context",
                        "expected_component_labels": ["equilibrium"],
                    },
                    {
                        "checkpoint": "confirmation",
                        "expected_component_labels": ["equilibrium", "top_down_alignment"],
                    },
                    {
                        "checkpoint": "outcome",
                        "expected_component_labels": [],
                    },
                ],
            },
            {
                "case_ref": "continuation_case",
                "trade_models": ["continuation_entry_model"],
                "relation_types": ["execution_model"],
                "checkpoints": [
                    {
                        "checkpoint": "context",
                        "expected_component_labels": ["equilibrium"],
                    }
                ],
            },
        ],
    }


class ExportTradingIterationGradingReportTests(unittest.TestCase):
    def test_build_iteration_grading_report_scores_learning_episodes(self) -> None:
        report = etigr.build_iteration_grading_report(
            case_packet_report=make_case_packet_report(),
            episodes_payload={
                "episodes": [
                    {
                        "episode_id": "episode_good",
                        "case_ref": "bias_case",
                        "trade_model": "daily_bias_framework",
                        "relation_type": "bias_framework",
                        "checkpoint_predictions": [
                            {"checkpoint": "context", "component_labels": ["equilibrium"]},
                            {
                                "checkpoint": "confirmation",
                                "component_labels": ["equilibrium", "top_down_alignment"],
                            },
                            {"checkpoint": "outcome", "component_labels": []},
                        ],
                    },
                    {
                        "episode_id": "episode_bad",
                        "case_ref": "bias_case",
                        "trade_model": "continuation_entry_model",
                        "relation_type": "execution_model",
                        "checkpoint_predictions": [
                            {"checkpoint": "context", "component_labels": ["liquidity_sweep"]},
                            {"checkpoint": "confirmation", "component_labels": []},
                            {"checkpoint": "outcome", "component_labels": ["breaker"]},
                        ],
                    },
                ]
            },
        )

        summary = report["summary"]
        self.assertEqual(summary["episode_count"], 2)
        self.assertEqual(summary["graded_episode_count"], 2)
        self.assertAlmostEqual(summary["trade_model_accuracy"], 0.5, places=4)
        self.assertAlmostEqual(summary["relation_type_accuracy"], 0.5, places=4)
        self.assertGreater(summary["average_understanding_score"], 0.4)
        self.assertEqual(report["episodes"][0]["episode_id"], "episode_good")
        self.assertTrue(report["episodes"][0]["trade_model_correct"])
        self.assertGreater(
            report["episodes"][0]["understanding_score"],
            report["episodes"][1]["understanding_score"],
        )

    def test_build_iteration_grading_report_tracks_unknown_cases_without_fake_scores(self) -> None:
        report = etigr.build_iteration_grading_report(
            case_packet_report=make_case_packet_report(),
            episodes_payload={
                "episodes": [
                    {
                        "episode_id": "episode_unknown",
                        "case_ref": "missing_case",
                        "trade_model": "daily_bias_framework",
                        "relation_type": "bias_framework",
                        "checkpoint_predictions": [],
                    }
                ]
            },
        )

        summary = report["summary"]
        self.assertEqual(summary["episode_count"], 1)
        self.assertEqual(summary["graded_episode_count"], 0)
        self.assertEqual(summary["unknown_case_count"], 1)
        self.assertAlmostEqual(summary["average_understanding_score"], 0.0, places=4)
        self.assertEqual(report["episodes"][0]["status"], "unknown_case_ref")


if __name__ == "__main__":
    unittest.main()
