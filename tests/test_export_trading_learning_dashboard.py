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

import export_trading_learning_dashboard as etd


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


class ExportTradingLearningDashboardTests(unittest.TestCase):
    def test_build_dashboard_report_surfaces_current_loop_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            results_dir = temp_path / "results"
            history_path = results_dir / "trading_learning_history.jsonl"
            output_path = results_dir / "trading_learning_dashboard.html"

            write_json(
                results_dir / "trading_learning_loop_summary.json",
                {
                    "generated_at": "2026-03-23T18:50:40.975949+00:00",
                    "step_count": 15,
                    "training_loop": {"grade": "D", "verdict": "keep_with_warnings"},
                    "iteration_learning": {"grade": "B-", "average_understanding_score": 0.6433},
                    "iteration_retraining": {
                        "trained_task_count": 2,
                        "trained_task_names": [
                            "continuation_entry_model",
                            "trade_vs_no_trade",
                        ],
                    },
                    "iteration_challengers": {
                        "compared_task_count": 2,
                        "challenger_win_count": 1,
                        "champion_win_count": 0,
                        "tie_task_count": 1,
                        "promotion_candidate_count": 1,
                        "promotion_candidate_tasks": ["continuation_entry_model"],
                    },
                    "iteration_promotions": {
                        "promoted_task_count": 1,
                        "promoted_tasks": ["continuation_entry_model"],
                        "skipped_task_count": 1,
                    },
                    "phase_one_focus": {
                        "current_training_target": "daily_bias_framework",
                        "status": "bootstrap_ready",
                        "additional_positive_examples_needed": 1,
                        "execution_spec": "daily_bias_c123_map",
                    },
                    "neural_net": {
                        "autoresearch_grade": "A",
                        "offline_ml_grade": "B",
                        "real_time_assist_grade": "C",
                        "real_time_execution_grade": "D",
                        "global_blockers": [
                            "Trade-model multiclass classification is still under-labeled.",
                            "No Pine drafts have been validated in TradingView yet.",
                        ],
                        "next_actions": [
                            "Review the winning challenger benchmark (continuation_entry_model) and decide whether to promote the new artifact after a manual sanity check."
                        ],
                    },
                    "backtesting": {
                        "current_priority": "historical_backtesting_understanding_before_real_time_trading",
                        "stages": {
                            "historical_backtesting_research_foundation": {
                                "grade": "A",
                                "ready": True,
                                "verdict": "go",
                            }
                        },
                    },
                    "improvement_plan": {
                        "phase": "blocked_translation",
                        "status": "blocked",
                        "priority_action_count": 6,
                        "top_priority_action": "Fix the TradingView editor sync path and validate the first spec-generated Pine draft.",
                        "history_entry_count": 10,
                    },
                    "next_actions": [
                        "Review the winning challenger benchmark (continuation_entry_model) and decide whether to promote the new artifact after a manual sanity check."
                    ],
                },
            )
            write_json(
                results_dir / "neural_net_readiness_report.json",
                {
                    "generated_at": "2026-03-23T18:50:39.944918+00:00",
                    "stages": {
                        "karpathy_style_autoresearch_loop": {"grade": "A"},
                        "offline_narrow_ml": {"grade": "B"},
                        "real_time_neural_assist": {"grade": "C"},
                        "real_time_neural_execution": {"grade": "D"},
                    },
                    "global_blockers": [
                        "Trade-model multiclass classification is still under-labeled.",
                        "No Pine drafts have been validated in TradingView yet.",
                    ],
                    "next_actions": [
                        "Review the winning challenger benchmark (continuation_entry_model) and decide whether to promote the new artifact after a manual sanity check."
                    ],
                },
            )
            write_json(
                results_dir / "trading_learning_improvement_plan.json",
                {
                    "generated_at": "2026-03-23T18:50:40.939934+00:00",
                    "phase": "blocked_translation",
                    "status": "blocked",
                    "priority_actions": [
                        {
                            "id": "review_promotable_challengers",
                            "lane": "model_evaluation",
                            "title": "Review the winning challenger benchmarks for possible promotion.",
                            "why_now": "continuation_entry_model",
                        }
                    ],
                    "history": {"entry_count": 10},
                },
            )
            write_json(
                results_dir / "iteration_challenger_report.json",
                {
                    "summary": {
                        "compared_task_count": 2,
                        "challenger_win_count": 1,
                        "champion_win_count": 0,
                        "tie_task_count": 1,
                        "promotion_candidate_count": 1,
                        "promotion_candidate_tasks": ["continuation_entry_model"],
                    }
                },
            )
            write_json(
                results_dir / "iteration_promotion_report.json",
                {
                    "summary": {
                        "promoted_task_count": 1,
                        "promoted_tasks": ["continuation_entry_model"],
                        "skipped_task_count": 1,
                    }
                },
            )
            history_path.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "recorded_at": "2026-03-22T19:58:44.783424+00:00",
                                "metrics": {"loop_score": 0.3548, "workflow_score": 0.65},
                                "phase": "blocked_translation",
                                "status": "blocked",
                            }
                        ),
                        json.dumps(
                            {
                                "recorded_at": "2026-03-23T18:50:40.975949+00:00",
                                "metrics": {"loop_score": 0.4731, "workflow_score": 0.75},
                                "phase": "blocked_translation",
                                "status": "blocked",
                            }
                        ),
                    ]
                ),
                encoding="utf-8",
            )

            etd.ROOT = temp_path
            etd.DEFAULT_OUTPUT = output_path
            etd.LOOP_SUMMARY_PATH = results_dir / "trading_learning_loop_summary.json"
            etd.NEURAL_REPORT_PATH = results_dir / "neural_net_readiness_report.json"
            etd.IMPROVEMENT_PLAN_PATH = results_dir / "trading_learning_improvement_plan.json"
            etd.ITERATION_CHALLENGER_REPORT_PATH = results_dir / "iteration_challenger_report.json"
            etd.ITERATION_PROMOTION_REPORT_PATH = results_dir / "iteration_promotion_report.json"
            etd.HISTORY_PATH = history_path

            report = etd.build_dashboard_report()

        self.assertEqual(report["title"], "Trading Learning Dashboard")
        self.assertEqual(report["summary"]["training_loop_grade"], "D")
        self.assertEqual(report["summary"]["iteration_challenger_wins"], 1)
        self.assertEqual(report["summary"]["promotion_candidate_tasks"], ["continuation_entry_model"])
        self.assertEqual(report["summary"]["promoted_tasks"], ["continuation_entry_model"])
        self.assertEqual(report["summary"]["phase_one_target"], "daily_bias_framework")
        self.assertEqual(report["history"]["entry_count"], 2)
        self.assertEqual(report["history"]["latest_loop_score"], 0.4731)
        self.assertEqual(report["improvement_plan"]["phase"], "blocked_translation")

    def test_render_dashboard_html_includes_primary_sections(self) -> None:
        report = {
            "title": "Trading Learning Dashboard",
            "generated_at": "2026-03-23T18:50:40.975949+00:00",
            "summary": {
                "step_count": 15,
                "workflow_score": 0.75,
                "training_loop_grade": "D",
                "training_loop_verdict": "keep_with_warnings",
                "iteration_understanding_grade": "B-",
                "retrained_task_count": 2,
                "promotion_candidate_count": 1,
                "promotion_candidate_tasks": ["continuation_entry_model"],
                "phase_one_target": "daily_bias_framework",
                "phase_one_status": "bootstrap_ready",
                "phase_one_gap": 1,
                "phase_one_execution_spec": "daily_bias_c123_map",
            },
            "phase_one_focus": {
                "current_training_target": "daily_bias_framework",
                "status": "bootstrap_ready",
                "execution_spec": "daily_bias_c123_map",
            },
            "stage_grades": [
                {"name": "Autoresearch", "grade": "A"},
                {"name": "Offline Narrow ML", "grade": "B"},
                {"name": "Real-Time Assist", "grade": "C"},
                {"name": "Real-Time Execution", "grade": "D"},
            ],
            "blockers": ["No Pine drafts have been validated in TradingView yet."],
            "next_actions": ["Review the winning challenger benchmark (continuation_entry_model)."],
            "challengers": {
                "compared_task_count": 2,
                "challenger_win_count": 1,
                "champion_win_count": 0,
                "tie_task_count": 1,
                "promotion_candidate_count": 1,
                "promotion_candidate_tasks": ["continuation_entry_model"],
            },
            "promotions": {
                "promoted_task_count": 1,
                "promoted_tasks": ["continuation_entry_model"],
            },
            "history": {
                "entry_count": 2,
                "recent_loop_scores": [0.3548, 0.4731],
            },
        }

        html = etd.render_dashboard_html(report)

        self.assertIn("<title>Trading Learning Dashboard</title>", html)
        self.assertIn("Training Loop", html)
        self.assertIn("Iteration Challengers", html)
        self.assertIn("Promoted Champions", html)
        self.assertIn("continuation_entry_model", html)
        self.assertIn("daily_bias_framework", html)
        self.assertIn("No Pine drafts have been validated in TradingView yet.", html)
        self.assertIn("0.4731", html)


if __name__ == "__main__":
    unittest.main()
