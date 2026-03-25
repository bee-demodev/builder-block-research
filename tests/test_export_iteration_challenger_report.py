from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import export_iteration_challenger_report as eicr


def make_example(*, example_id: str, trade_model: str, outcome: str) -> dict:
    return {
        "example_id": example_id,
        "training_text": f"profile demo | trade model {trade_model} | outcome {outcome}",
        "targets": {
            "trade_model": trade_model,
            "relation_type": "execution_model",
            "outcome_decision": outcome,
            "has_outcome_label": True,
        },
    }


class ExportIterationChallengerReportTests(unittest.TestCase):
    def test_build_iteration_challenger_report_compares_champion_and_challenger(self) -> None:
        examples = [
            make_example(
                example_id="base::cont::1",
                trade_model="continuation_entry_model",
                outcome="trade",
            ),
            make_example(
                example_id="base::other::1",
                trade_model="daily_bias_framework",
                outcome="trade",
            ),
            make_example(
                example_id="iteration::episode_1::continuation_entry_model::execution_model",
                trade_model="continuation_entry_model",
                outcome="trade",
            ),
            make_example(
                example_id="iteration::episode_2::daily_bias_framework::bias_framework",
                trade_model="daily_bias_framework",
                outcome="no_trade",
            ),
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            champion_dir = temp_path / "champion"
            challenger_dir = temp_path / "challenger"
            champion_dir.mkdir(parents=True, exist_ok=True)
            challenger_dir.mkdir(parents=True, exist_ok=True)
            (champion_dir / "continuation_entry_model.pt").write_text("champion", encoding="utf-8")
            (challenger_dir / "continuation_entry_model.pt").write_text("challenger", encoding="utf-8")
            (champion_dir / "continuation_entry_model_report.json").write_text(
                '{"metrics":{"validation":{"accuracy":0.75,"f1":0.6667}},"example_count":2}',
                encoding="utf-8",
            )
            (challenger_dir / "continuation_entry_model_report.json").write_text(
                '{"metrics":{"validation":{"accuracy":1.0,"f1":1.0}},"example_count":4}',
                encoding="utf-8",
            )

            def fake_score(
                scored_examples: list[dict],
                model_path: Path,
                *,
                device_preference: str = "auto",
                threshold: float = 0.5,
            ) -> dict:
                del device_preference, threshold
                is_reinforcement_slice = any(
                    str(item["example_id"]).startswith("iteration::") for item in scored_examples
                )
                if model_path.parent.name == "champion":
                    accuracy = 0.5 if is_reinforcement_slice else 0.75
                    f1 = 0.5 if is_reinforcement_slice else 0.6667
                else:
                    accuracy = 1.0
                    f1 = 1.0
                return {
                    "model_path": str(model_path),
                    "device": "cpu",
                    "example_count": len(scored_examples),
                    "threshold": 0.5,
                    "metrics": {
                        "accuracy": accuracy,
                        "precision": accuracy,
                        "recall": accuracy,
                        "f1": f1,
                        "positive_predictions": 1,
                        "positive_labels": 1,
                        "confusion": {
                            "true_positive": 1,
                            "true_negative": max(0, len(scored_examples) - 1),
                            "false_positive": 0,
                            "false_negative": 0,
                        },
                    },
                }

            report = eicr.build_iteration_challenger_report(
                examples=examples,
                iteration_retraining_report={
                    "trained_task_names": ["continuation_entry_model"],
                    "trained_task_count": 1,
                },
                champion_model_dir=champion_dir,
                challenger_model_dir=challenger_dir,
                score_fn=fake_score,
            )

        self.assertEqual(report["summary"]["compared_task_count"], 1)
        self.assertEqual(report["summary"]["challenger_win_count"], 1)
        self.assertEqual(report["summary"]["promotion_candidate_count"], 1)
        task_report = report["task_reports"][0]
        self.assertEqual(task_report["status"], "compared")
        self.assertEqual(task_report["winner"], "challenger")
        self.assertEqual(task_report["recommendation"], "promote_after_review")
        self.assertEqual(task_report["shared_example_count"], 4)
        self.assertEqual(task_report["reinforcement_example_count"], 2)
        self.assertGreater(task_report["full_surface"]["metric_delta"]["f1"], 0.0)
        self.assertGreater(task_report["reinforcement_only"]["metric_delta"]["accuracy"], 0.0)

    def test_build_iteration_challenger_report_handles_missing_champion(self) -> None:
        examples = [
            make_example(
                example_id="base::trade::1",
                trade_model="continuation_entry_model",
                outcome="trade",
            ),
            make_example(
                example_id="base::other::1",
                trade_model="daily_bias_framework",
                outcome="trade",
            ),
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            champion_dir = temp_path / "champion"
            challenger_dir = temp_path / "challenger"
            champion_dir.mkdir(parents=True, exist_ok=True)
            challenger_dir.mkdir(parents=True, exist_ok=True)
            (challenger_dir / "continuation_entry_model.pt").write_text("challenger", encoding="utf-8")

            report = eicr.build_iteration_challenger_report(
                examples=examples,
                iteration_retraining_report={
                    "trained_task_names": ["continuation_entry_model"],
                    "trained_task_count": 1,
                },
                champion_model_dir=champion_dir,
                challenger_model_dir=challenger_dir,
                score_fn=lambda *_args, **_kwargs: {
                    "device": "cpu",
                    "example_count": 2,
                    "threshold": 0.5,
                    "metrics": {
                        "accuracy": 1.0,
                        "precision": 1.0,
                        "recall": 1.0,
                        "f1": 1.0,
                        "positive_predictions": 1,
                        "positive_labels": 1,
                        "confusion": {
                            "true_positive": 1,
                            "true_negative": 1,
                            "false_positive": 0,
                            "false_negative": 0,
                        },
                    },
                },
            )

        self.assertEqual(report["summary"]["missing_champion_count"], 1)
        self.assertEqual(report["summary"]["compared_task_count"], 0)
        self.assertEqual(report["task_reports"][0]["status"], "missing_champion_model")
        self.assertEqual(report["task_reports"][0]["recommendation"], "initialize_champion_review")


if __name__ == "__main__":
    unittest.main()
