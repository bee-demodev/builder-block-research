from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import export_trading_learning_improvement_plan as etlip


class ExportTradingLearningImprovementPlanTests(unittest.TestCase):
    def make_inputs(self) -> tuple[dict, dict, dict, dict, dict, dict, dict]:
        case_packet_report = {
            "summary": {
                "case_count": 14,
                "checkpoint_count": 70,
                "screenshot_coverage": 0.0,
                "anchor_coverage": 0.0,
            }
        }
        feedback_queue = {
            "summary": {
                "item_count": 1,
                "workflow_feedback_count": 1,
                "tradingview_failure_count": 1,
            },
            "items": [
                {
                    "id": "tradingview::daily_bias_framework::blocked_monaco_sync::finding",
                    "target_type": "finding",
                    "title": "TradingView validation blocked for daily_bias_framework",
                    "body": "Monaco buffer stayed stale during Playwriter validation.",
                }
            ],
        }
        training_loop_report = {
            "generated_at": "2026-03-22T19:50:21.753099+00:00",
            "loop_score": 0.3548,
            "grade": "D",
            "verdict": "keep_with_warnings",
            "metrics": {"tradingview_generated_script_coverage": 1.0},
        }
        neural_report = {
            "generated_at": "2026-03-22T19:50:22.254647+00:00",
            "snapshot": {
                "indicator_ready_trade_models": [
                    "continuation_entry_model",
                    "daily_bias_framework",
                    "daily_profile_models",
                    "fractal_closure_model",
                    "reversal_sequence_model",
                ],
                "indicator_specs": {
                    "non_draft_status_count": 0,
                },
                "training_surface": {
                    "ready_indicator_binary_count": 1,
                    "ready_indicator_binary_coverage": 0.2,
                    "reinforcement_example_count": 3,
                    "trade_model_binary_tasks": [
                        {
                            "trade_model": "daily_bias_framework",
                            "additional_positive_examples_needed": 1,
                            "ready": False,
                        },
                        {
                            "trade_model": "daily_profile_models",
                            "additional_positive_examples_needed": 3,
                            "ready": False,
                        },
                    ],
                },
                "label_space": {
                    "extra_training_labels_without_indicator_specs": [
                        "phases_of_price_framework"
                    ]
                },
                "iteration_retraining": {
                    "trained_task_count": 2,
                    "trained_task_names": [
                        "continuation_entry_model",
                        "trade_vs_no_trade",
                    ],
                },
            },
        }
        backtesting_report = {
            "generated_at": "2026-03-22T19:50:22.766737+00:00",
            "snapshot": {
                "historical_harness": {"harness_score": 0.0},
                "backtesting_specs": {"cost_model_average": 0.0},
            },
            "stages": {
                "rules_based_historical_backtesting": {
                    "score": 0.66,
                    "ready": False,
                    "blockers": ["No repeatable historical backtest or replay harness exists yet."],
                },
                "model_assisted_historical_backtesting": {"score": 0.58},
            },
            "next_actions": [
                "Ingest the tracked backtesting methodology source into local artifacts so the historical-testing workflow is grounded in the same repo-native evidence as the strategy rules.",
                "Add a minimal historical replay/backtest harness with next-bar execution, explicit entry/stop/target events, and session-aware rule evaluation.",
            ],
        }
        tradingview_report = {
            "generated_at": "2026-03-22T19:50:21.580809+00:00",
            "summary": {
                "workflow_score": 0.65,
                "validation_coverage": 0.0,
                "generated_script_count": 5,
                "validated_script_count": 0,
                "playwriter_validated_count": 0,
                "pending_spec_keys": ["daily_bias_framework", "continuation_entry_model"],
            }
        }
        iteration_grading_report = {
            "generated_at": "2026-03-22T19:50:23.000000+00:00",
            "summary": {
                "episode_count": 2,
                "graded_episode_count": 2,
                "average_understanding_score": 0.55,
                "trade_model_accuracy": 0.5,
                "relation_type_accuracy": 1.0,
                "checkpoint_component_score": 0.45,
                "latest_understanding_score": 0.7,
                "grade": "C+",
            },
        }
        return (
            case_packet_report,
            feedback_queue,
            training_loop_report,
            neural_report,
            backtesting_report,
            tradingview_report,
            iteration_grading_report,
        )

    def test_build_improvement_plan_prioritizes_translation_blocker(self) -> None:
        inputs = self.make_inputs()

        plan = etlip.build_improvement_plan(
            run_generated_at=inputs[2]["generated_at"],
            case_packet_report=inputs[0],
            feedback_queue=inputs[1],
            training_loop_report=inputs[2],
            neural_report=inputs[3],
            backtesting_report=inputs[4],
            tradingview_report=inputs[5],
            iteration_grading_report=inputs[6],
        )

        self.assertEqual(plan["phase"], "blocked_translation")
        self.assertEqual(plan["status"], "blocked")
        self.assertEqual(plan["priority_actions"][0]["id"], "validate_first_pine_draft")
        self.assertFalse(any(action["id"] == "resolve_out_of_set_labels" for action in plan["priority_actions"]))
        self.assertEqual(plan["phase_one_focus"]["current_training_target"], "daily_bias_framework")
        self.assertTrue(
            any(
                bottleneck["id"] == "missing_historical_harness"
                for bottleneck in plan["bottlenecks"]
            )
        )

    def test_history_write_updates_count_and_delta(self) -> None:
        inputs = self.make_inputs()

        with tempfile.TemporaryDirectory() as tmp_dir:
            history_path = Path(tmp_dir) / "history.jsonl"
            previous_entry = {
                "run_generated_at": "2026-03-21T00:00:00+00:00",
                "phase": "evidence_bootstrap",
                "status": "bootstrapping",
                "metrics": {
                    "loop_score": 0.25,
                    "workflow_score": 0.4,
                    "validation_coverage": 0.0,
                    "screenshot_coverage": 0.0,
                    "anchor_coverage": 0.0,
                    "feedback_item_count": 3,
                    "rules_backtest_score": 0.5,
                    "model_backtest_score": 0.45,
                },
            }
            history_path.write_text(json.dumps(previous_entry) + "\n", encoding="utf-8")

            previous = etlip.find_previous_history_entry(
                etlip.load_history_entries(history_path),
                inputs[2]["generated_at"],
            )
            plan = etlip.build_improvement_plan(
                run_generated_at=inputs[2]["generated_at"],
                case_packet_report=inputs[0],
                feedback_queue=inputs[1],
                training_loop_report=inputs[2],
                neural_report=inputs[3],
                backtesting_report=inputs[4],
                tradingview_report=inputs[5],
                iteration_grading_report=inputs[6],
                previous_entry=previous,
            )
            history_entry = etlip.build_history_entry(
                current_run=plan["current_run"],
                phase=plan["phase"],
                status=plan["status"],
                priority_actions=plan["priority_actions"],
            )
            entry_count = etlip.write_history_entry(history_path, history_entry)

            self.assertEqual(entry_count, 2)
            self.assertAlmostEqual(plan["delta"]["loop_score"], 0.1048, places=4)
            self.assertAlmostEqual(plan["delta"]["workflow_score"], 0.25, places=4)
            self.assertAlmostEqual(plan["current_run"]["metrics"]["iteration_understanding_score"], 0.55, places=4)
            self.assertEqual(plan["current_run"]["metrics"]["reinforcement_example_count"], 3)
            self.assertEqual(plan["current_run"]["metrics"]["retrained_task_count"], 2)
            self.assertTrue(
                any(
                    action["id"] == "benchmark_retrained_challengers"
                    for action in plan["priority_actions"]
                )
            )
            self.assertIn("Loop score improved", " ".join(plan["progress_signals"]))

    def test_build_improvement_plan_switches_to_promotion_review_after_benchmark(self) -> None:
        inputs = list(self.make_inputs())
        inputs[3]["snapshot"]["iteration_challengers"] = {
            "compared_task_count": 2,
            "promotion_candidate_count": 1,
            "promotion_candidate_tasks": ["continuation_entry_model"],
        }

        plan = etlip.build_improvement_plan(
            run_generated_at=inputs[2]["generated_at"],
            case_packet_report=inputs[0],
            feedback_queue=inputs[1],
            training_loop_report=inputs[2],
            neural_report=inputs[3],
            backtesting_report=inputs[4],
            tradingview_report=inputs[5],
            iteration_grading_report=inputs[6],
        )

        action_ids = [action["id"] for action in plan["priority_actions"]]
        self.assertIn("review_promotable_challengers", action_ids)
        self.assertNotIn("benchmark_retrained_challengers", action_ids)

    def test_build_improvement_plan_switches_to_monitoring_after_promotion(self) -> None:
        inputs = list(self.make_inputs())
        inputs[3]["snapshot"]["iteration_challengers"] = {
            "compared_task_count": 2,
            "promotion_candidate_count": 1,
            "promotion_candidate_tasks": ["continuation_entry_model"],
        }
        inputs[3]["snapshot"]["iteration_promotions"] = {
            "promoted_task_count": 1,
            "promoted_tasks": ["continuation_entry_model"],
        }

        plan = etlip.build_improvement_plan(
            run_generated_at=inputs[2]["generated_at"],
            case_packet_report=inputs[0],
            feedback_queue=inputs[1],
            training_loop_report=inputs[2],
            neural_report=inputs[3],
            backtesting_report=inputs[4],
            tradingview_report=inputs[5],
            iteration_grading_report=inputs[6],
        )

        action_ids = [action["id"] for action in plan["priority_actions"]]
        self.assertIn("monitor_promoted_champions", action_ids)
        self.assertNotIn("review_promotable_challengers", action_ids)


if __name__ == "__main__":
    unittest.main()
