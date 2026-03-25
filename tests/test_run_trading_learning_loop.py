from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import run_trading_learning_loop as rtll


class RunTradingLearningLoopTests(unittest.TestCase):
    def test_build_loop_steps_includes_optional_phases(self) -> None:
        steps = rtll.build_loop_steps(
            "python",
            bootstrap_screenshots=True,
            apply_safe_feedback=True,
        )

        step_ids = [step["id"] for step in steps]
        self.assertIn("bootstrap_ttfm_screenshot_manifest", step_ids)
        self.assertIn("apply_ttfm_feedback", step_ids)
        self.assertIn("export_reinforced_training_surface", step_ids)
        self.assertIn("run_iteration_retraining", step_ids)
        self.assertIn("export_iteration_challenger_report", step_ids)
        self.assertIn("promote_iteration_challengers", step_ids)
        self.assertEqual(step_ids[0], "import_trader_annotation_cases")
        self.assertEqual(step_ids[-1], "export_trading_learning_improvement_plan")

    def test_build_loop_summary_surfaces_core_scores(self) -> None:
        summary = rtll.build_loop_summary(
            bootstrap_screenshots=False,
            apply_safe_feedback=False,
            step_results=[{"id": "demo", "result": {"ok": True}}],
            case_packet_report={
                "summary": {
                    "case_count": 14,
                    "checkpoint_count": 70,
                    "screenshot_coverage": 0.4,
                    "anchor_coverage": 0.2,
                    "missing_screenshot_count": 42,
                    "missing_anchor_label_count": 56,
                }
            },
            pine_verification_report={
                "summary": {
                    "queue_item_count": 3,
                    "attempted_item_count": 1,
                    "translatability_score": 0.5,
                    "feedback_candidate_count": 2,
                }
            },
            tradingview_pine_report={
                "summary": {
                    "generated_script_count": 5,
                    "validated_script_count": 0,
                    "playwriter_validated_count": 0,
                    "workflow_score": 0.68,
                    "validation_coverage": 0.0,
                    "pending_spec_keys": ["daily_bias_framework"],
                }
            },
            feedback_queue={
                "summary": {
                    "item_count": 4,
                    "tradingview_failure_count": 1,
                    "workflow_feedback_count": 1,
                    "spec_feedback_count": 1,
                }
            },
            training_loop_report={
                "loop_score": 0.33,
                "grade": "D",
                "verdict": "keep_with_warnings",
                "warnings": ["No TradingView-validated Pine drafts are present in the current loop."],
            },
            neural_report={
                "phase_one_focus": {
                    "current_training_target": "daily_bias_framework",
                    "status": "bootstrap_ready",
                    "additional_positive_examples_needed": 1,
                    "execution_spec": "daily_bias_c123_map",
                },
                "stages": {
                    "karpathy_style_autoresearch_loop": {"grade": "B+"},
                    "offline_narrow_ml": {"grade": "B"},
                    "real_time_neural_assist": {"grade": "C"},
                    "real_time_neural_execution": {"grade": "D"},
                },
                "global_blockers": ["No Pine drafts have been validated in TradingView yet."],
                "next_actions": ["Validate more spec-generated Pine drafts in TradingView."],
            },
            backtesting_report={
                "current_priority": "historical_backtesting_understanding_before_real_time_trading",
                "stages": {
                    "rules_based_historical_backtesting": {
                        "score": 0.66,
                        "grade": "B-",
                        "ready": False,
                        "verdict": "not_yet",
                    }
                },
            },
            iteration_grading_report={
                "summary": {
                    "episode_count": 3,
                    "graded_episode_count": 2,
                    "average_understanding_score": 0.625,
                    "trade_model_accuracy": 0.5,
                    "relation_type_accuracy": 1.0,
                    "checkpoint_component_score": 0.5833,
                    "latest_understanding_score": 0.75,
                    "grade": "B-",
                }
            },
            reinforced_training_report={
                "summary": {
                    "base_example_count": 16,
                    "reinforcement_example_count": 3,
                    "merged_example_count": 19,
                    "graded_episode_count": 3,
                }
            },
            iteration_retraining_report={
                "trained_task_count": 2,
                "trained_task_names": ["continuation_entry_model", "trade_vs_no_trade"],
            },
            iteration_challenger_report={
                "summary": {
                    "compared_task_count": 2,
                    "challenger_win_count": 1,
                    "champion_win_count": 1,
                    "tie_task_count": 0,
                    "promotion_candidate_count": 1,
                }
            },
            iteration_promotion_report={
                "summary": {
                    "promoted_task_count": 1,
                    "promoted_tasks": ["continuation_entry_model"],
                    "skipped_task_count": 1,
                }
            },
            improvement_plan_report={
                "phase": "blocked_translation",
                "status": "blocked",
                "priority_actions": [
                    {
                        "id": "validate_first_pine_draft",
                        "title": "Fix the TradingView editor sync path and validate the first spec-generated Pine draft.",
                    }
                ],
                "history": {"entry_count": 1},
            },
        )

        self.assertEqual(summary["step_count"], 1)
        self.assertEqual(summary["training_loop"]["grade"], "D")
        self.assertEqual(summary["tradingview_pine"]["workflow_score"], 0.68)
        self.assertEqual(summary["feedback_queue"]["tradingview_failure_count"], 1)
        self.assertEqual(summary["neural_net"]["real_time_execution_grade"], "D")
        self.assertEqual(summary["iteration_learning"]["episode_count"], 3)
        self.assertEqual(summary["iteration_learning"]["grade"], "B-")
        self.assertEqual(summary["iteration_retraining"]["reinforcement_example_count"], 3)
        self.assertEqual(summary["iteration_retraining"]["trained_task_count"], 2)
        self.assertEqual(summary["iteration_challengers"]["compared_task_count"], 2)
        self.assertEqual(summary["iteration_challengers"]["promotion_candidate_count"], 1)
        self.assertEqual(summary["iteration_promotions"]["promoted_task_count"], 1)
        self.assertEqual(summary["phase_one_focus"]["current_training_target"], "daily_bias_framework")
        self.assertEqual(summary["improvement_plan"]["phase"], "blocked_translation")
        self.assertEqual(summary["improvement_plan"]["priority_action_count"], 1)


if __name__ == "__main__":
    unittest.main()
