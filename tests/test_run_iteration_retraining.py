from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import run_iteration_retraining as rir


def make_example(*, case_ref: str, trade_model: str, relation_type: str, outcome: str) -> dict:
    return {
        "example_id": f"{case_ref}::{trade_model}::{relation_type}",
        "case_ref": case_ref,
        "trade_model": trade_model,
        "relation_type": relation_type,
        "targets": {
            "trade_model": trade_model,
            "relation_type": relation_type,
            "outcome_decision": outcome,
            "has_outcome_label": True,
        },
        "training_text": f"profile demo | trade model {trade_model} | relation {relation_type} | outcome {outcome}",
    }


class RunIterationRetrainingTests(unittest.TestCase):
    def test_build_retraining_plan_selects_ready_tasks(self) -> None:
        examples = []
        for index in range(6):
            examples.append(
                make_example(
                    case_ref=f"cont_{index}",
                    trade_model="continuation_entry_model",
                    relation_type="execution_model",
                    outcome="trade" if index < 4 else "no_trade",
                )
            )
        for index in range(6):
            examples.append(
                make_example(
                    case_ref=f"other_{index}",
                    trade_model="daily_bias_framework",
                    relation_type="bias_framework",
                    outcome="trade",
                )
            )

        plan = rir.build_retraining_plan(examples)

        self.assertIn("continuation_entry_model", plan["task_names"])
        self.assertIn("daily_bias_framework", plan["task_names"])
        self.assertIn("trade_vs_no_trade", plan["task_names"])

    def test_run_iteration_retraining_calls_trainer_for_each_ready_task(self) -> None:
        examples = []
        for index in range(5):
            examples.append(
                make_example(
                    case_ref=f"cont_{index}",
                    trade_model="continuation_entry_model",
                    relation_type="execution_model",
                    outcome="trade" if index < 3 else "no_trade",
                )
            )
        for index in range(5):
            examples.append(
                make_example(
                    case_ref=f"other_{index}",
                    trade_model="daily_bias_framework",
                    relation_type="bias_framework",
                    outcome="trade",
                )
            )

        trained: list[str] = []
        requested_groupings: list[str] = []

        def fake_train(prepared_task: dict, **_: object) -> dict:
            trained.append(str(prepared_task["task_name"]))
            requested_groupings.append(str(_.get("validation_grouping")))
            return {
                "task_name": prepared_task["task_name"],
                "device": "cpu",
                "example_count": len(prepared_task["examples"]),
                "metrics": {"validation": {"accuracy": 1.0}},
                "source_holdout_evaluation": {
                    "group_field": "source_group",
                    "group_count": 3,
                    "evaluated_group_count": 2,
                    "skipped_group_count": 1,
                    "evaluated_positive_group_count": 1,
                    "evaluated_negative_only_group_count": 1,
                    "micro_metrics": {"f1": 0.75},
                    "positive_group_macro_metrics": {"f1": 0.8, "recall": 1.0},
                    "negative_only_group_macro_metrics": {
                        "specificity": 0.5,
                        "false_positive_rate": 0.5,
                    },
                },
                "model_path": f"fake/{prepared_task['task_name']}.pt",
                "report_path": f"fake/{prepared_task['task_name']}_report.json",
            }

        with tempfile.TemporaryDirectory() as temp_dir:
            report = rir.run_iteration_retraining_on_examples(
                examples=examples,
                output_dir=Path(temp_dir),
                train_fn=fake_train,
            )

        self.assertEqual(report["trained_task_count"], len(trained))
        self.assertIn("continuation_entry_model", trained)
        self.assertIn("daily_bias_framework", trained)
        self.assertIn("trade_vs_no_trade", trained)
        self.assertTrue(all(grouping == "source_group" for grouping in requested_groupings))
        self.assertEqual(report["validation_grouping_requested"], "source_group")
        self.assertEqual(len(report["source_holdout_task_summaries"]), len(trained))
        self.assertEqual(
            report["source_holdout_task_summaries"][0]["positive_group_macro_f1"],
            0.8,
        )
        self.assertEqual(
            report["source_holdout_task_summaries"][0]["negative_only_group_mean_specificity"],
            0.5,
        )

    def test_export_iteration_retraining_with_retries_recovers_after_transient_failure(self) -> None:
        calls: list[int] = []

        def fake_export_iteration_retraining(
            *,
            dataset_path: Path,
            output_dir: Path,
            report_output: Path,
            **_: object,
        ) -> dict:
            calls.append(len(calls) + 1)
            output_dir.mkdir(parents=True, exist_ok=True)
            if len(calls) == 1:
                (output_dir / "partial.txt").write_text("partial", encoding="utf-8")
                report_output.parent.mkdir(parents=True, exist_ok=True)
                report_output.write_text(
                    json.dumps({"attempt": 1, "dataset_path": str(dataset_path)}),
                    encoding="utf-8",
                )
                raise RuntimeError("transient export failure")

            report_output.parent.mkdir(parents=True, exist_ok=True)
            report_output.write_text(
                json.dumps({"attempt": 2, "dataset_path": str(dataset_path)}),
                encoding="utf-8",
            )
            (output_dir / "model.pt").write_text("ok", encoding="utf-8")
            return {
                "dataset_path": str(dataset_path),
                "output_dir": str(output_dir),
                "report_output": str(report_output),
                "trained_task_count": 0,
                "trained_task_names": [],
                "trained_tasks": [],
            }

        with tempfile.TemporaryDirectory() as temp_dir:
            dataset_path = Path(temp_dir) / "dataset.jsonl"
            output_dir = Path(temp_dir) / "models"
            report_output = Path(temp_dir) / "report.json"
            with mock.patch.object(
                rir,
                "export_iteration_retraining",
                side_effect=fake_export_iteration_retraining,
            ):
                report = rir.export_iteration_retraining_with_retries(
                    dataset_path=dataset_path,
                    output_dir=output_dir,
                    report_output=report_output,
                    max_attempts=3,
                )

            self.assertEqual(len(calls), 2)
            self.assertEqual(report["retry_summary"]["attempt_count"], 2)
            self.assertTrue(report["retry_summary"]["succeeded"])
            self.assertEqual(report["retry_summary"]["failed_attempt_count"], 1)
            self.assertEqual(report["retry_summary"]["attempts"][0]["status"], "failed")
            self.assertEqual(report["retry_summary"]["attempts"][1]["status"], "succeeded")
            self.assertFalse((output_dir / "partial.txt").exists())
            self.assertTrue(report_output.exists())
            persisted = json.loads(report_output.read_text(encoding="utf-8"))
            self.assertEqual(persisted["retry_summary"]["attempt_count"], 2)
            self.assertTrue(persisted["retry_summary"]["succeeded"])

    def test_export_iteration_retraining_with_retries_writes_failure_report_on_exhaustion(self) -> None:
        calls: list[int] = []

        def always_fail_export_iteration_retraining(
            *,
            output_dir: Path,
            report_output: Path,
            **_: object,
        ) -> dict:
            calls.append(len(calls) + 1)
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / f"attempt-{len(calls)}.txt").write_text(
                "failed",
                encoding="utf-8",
            )
            report_output.parent.mkdir(parents=True, exist_ok=True)
            report_output.write_text(
                json.dumps({"attempt": len(calls)}),
                encoding="utf-8",
            )
            raise RuntimeError(f"failure-{len(calls)}")

        with tempfile.TemporaryDirectory() as temp_dir:
            dataset_path = Path(temp_dir) / "dataset.jsonl"
            output_dir = Path(temp_dir) / "models"
            report_output = Path(temp_dir) / "report.json"
            with mock.patch.object(
                rir,
                "export_iteration_retraining",
                side_effect=always_fail_export_iteration_retraining,
            ):
                with self.assertRaises(RuntimeError) as context:
                    rir.export_iteration_retraining_with_retries(
                        dataset_path=dataset_path,
                        output_dir=output_dir,
                        report_output=report_output,
                        max_attempts=2,
                    )

            self.assertIn("failure-2", str(context.exception))
            self.assertEqual(len(calls), 2)
            self.assertTrue(report_output.exists())
            persisted = json.loads(report_output.read_text(encoding="utf-8"))
            self.assertFalse(persisted["retry_summary"]["succeeded"])
            self.assertEqual(persisted["retry_summary"]["attempt_count"], 2)
            self.assertEqual(persisted["retry_summary"]["last_error_message"], "failure-2")

    def test_build_retraining_plan_bootstraps_daily_bias_phase_one_task(self) -> None:
        examples = []
        for index in range(8):
            examples.append(
                make_example(
                    case_ref=f"cont_{index}",
                    trade_model="continuation_entry_model",
                    relation_type="execution_model",
                    outcome="trade" if index < 5 else "no_trade",
                )
            )
        for index in range(4):
            examples.append(
                make_example(
                    case_ref=f"bias_{index}",
                    trade_model="daily_bias_framework",
                    relation_type="bias_framework",
                    outcome="trade",
                )
            )

        plan = rir.build_retraining_plan(examples)

        self.assertIn("daily_bias_framework", plan["task_names"])
        self.assertEqual(plan["phase_one_focus"]["status"], "bootstrap_ready")
        self.assertEqual(plan["phase_one_bootstrap_tasks"][0]["trade_model"], "daily_bias_framework")


if __name__ == "__main__":
    unittest.main()
