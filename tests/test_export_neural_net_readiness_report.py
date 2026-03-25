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

import export_neural_net_readiness_report as ennrr


def make_snapshot() -> dict:
    return {
        "understanding": {
            "overall": {
                "overall_understanding_score": 0.933,
                "scenario_average": 0.944,
                "scenario_contract_coverage": 0.625,
            }
        },
        "indicator_spec_machine_checkability_average": 0.8133,
        "indicator_specs": {
            "stage_score": 0.6,
            "realtime_feature_score": 1.0,
            "non_draft_status_count": 0,
        },
        "runtime": {"runtime_score": 0.0},
        "tradingview_pine": {
            "workflow_score": 0.0,
            "generated_script_coverage": 0.0,
            "validation_coverage": 0.0,
            "playwriter_validation_coverage": 0.0,
            "validated_script_count": 0,
            "playwriter_validated_count": 0,
        },
        "annotation_manifest_sync": {
            "sync_score": 0.9286,
            "extra_in_db": ["legacy_case"],
            "missing_in_db": [],
        },
        "research_logging_score": 1.0,
        "backlog_visibility_score": 1.0,
        "topic_coverage_score": 1.0,
        "indicator_spec_coverage": 1.0,
        "annotation_trade_model_coverage": 1.0,
        "indicator_ready_trade_models": [
            "continuation_entry_model",
            "daily_bias_framework",
            "daily_profile_models",
            "fractal_closure_model",
            "reversal_sequence_model",
        ],
        "training_surface": {
            "label_volume_score": 0.64,
            "outcome_label_coverage": 0.9375,
            "ready_indicator_binary_count": 1,
            "ready_indicator_binary_coverage": 0.2,
            "task_readiness": {
                "no_trade_filter": {"ready": True},
                "trade_model_classification": {"ready": False},
                "relation_type_classification": {"ready": False},
            },
            "trade_model_binary_tasks": [
                {
                    "trade_model": "continuation_entry_model",
                    "additional_positive_examples_needed": 0,
                    "ready": True,
                },
                {
                    "trade_model": "daily_bias_framework",
                    "additional_positive_examples_needed": 3,
                    "ready": False,
                },
            ],
        },
        "label_space": {
            "extra_training_labels_without_indicator_specs": ["phases_of_price_framework"],
        },
        "phase_one_chart_state_bootstrap": {
            "exported_example_count": 0,
            "positive_example_count": 0,
            "negative_example_count": 0,
            "outcome_decision_counts": {},
            "source_kind_counts": {},
            "artifact_present": False,
        },
    }


class BuildStageReadinessTests(unittest.TestCase):
    def test_offline_narrow_ml_can_be_cautious_go(self) -> None:
        snapshot = make_snapshot()
        snapshot["tradingview_pine"]["workflow_score"] = 0.72
        snapshot["tradingview_pine"]["generated_script_coverage"] = 1.0
        stages = ennrr.build_stage_readiness(snapshot)

        offline = stages["offline_narrow_ml"]
        self.assertTrue(offline["ready"])
        self.assertEqual(offline["verdict"], "cautious_go")
        self.assertLessEqual(offline["score"], 0.76)

    def test_real_time_stages_are_capped_by_missing_runtime_and_multiclass_readiness(self) -> None:
        stages = ennrr.build_stage_readiness(make_snapshot())

        assist = stages["real_time_neural_assist"]
        execution = stages["real_time_neural_execution"]

        self.assertFalse(assist["ready"])
        self.assertLessEqual(assist["score"], 0.58)
        self.assertFalse(execution["ready"])
        self.assertEqual(execution["verdict"], "hard_no")
        self.assertLessEqual(execution["score"], 0.42)


class ReinforcedTrainingSnapshotTests(unittest.TestCase):
    def test_merge_training_surface_snapshot_prefers_reinforced_counts(self) -> None:
        snapshot = make_snapshot()
        merged = ennrr.merge_training_surface_snapshot(
            snapshot["training_surface"],
            reinforced_summary={
                "example_count": 19,
                "unique_case_count": 14,
                "unique_trade_model_count": 6,
                "unique_relation_type_count": 5,
                "labeled_outcome_count": 18,
                "unknown_outcome_count": 1,
                "trade_model_counts": {
                    "continuation_entry_model": 8,
                    "daily_bias_framework": 4,
                },
                "relation_type_counts": {
                    "bias_framework": 4,
                    "execution_model": 10,
                },
                "outcome_decision_counts": {
                    "trade": 14,
                    "no_trade": 4,
                },
                "task_readiness": {
                    "no_trade_filter": {
                        "ready": True,
                        "total_examples": 18,
                        "recommended_total_examples": 12,
                        "minimum_examples_per_class": 4,
                        "recommended_examples_per_class": 4,
                        "class_count": 2,
                    },
                    "trade_model_classification": {
                        "ready": False,
                        "total_examples": 19,
                        "recommended_total_examples": 25,
                        "minimum_examples_per_class": 1,
                        "recommended_examples_per_class": 5,
                        "class_count": 6,
                    },
                    "relation_type_classification": {
                        "ready": False,
                        "total_examples": 19,
                        "recommended_total_examples": 25,
                        "minimum_examples_per_class": 1,
                        "recommended_examples_per_class": 5,
                        "class_count": 5,
                    },
                },
                "trade_model_binary_tasks": [
                    {
                        "trade_model": "continuation_entry_model",
                        "additional_positive_examples_needed": 0,
                        "ready": True,
                    },
                    {
                        "trade_model": "daily_bias_framework",
                        "additional_positive_examples_needed": 1,
                        "ready": False,
                    },
                ],
                "recommendations": [
                    "The fastest narrow-task path is one-vs-rest scoring for daily_bias_framework once it gains 1 more positive examples."
                ],
                "reinforcement_example_count": 3,
                "merged_example_count": 19,
                "base_example_count": 16,
                "graded_episode_count": 3,
            },
            indicator_ready_models=snapshot["indicator_ready_trade_models"],
        )

        self.assertEqual(merged["example_count"], 19)
        self.assertEqual(merged["reinforcement_example_count"], 3)
        self.assertEqual(merged["trade_model_binary_tasks"][1]["additional_positive_examples_needed"], 1)
        self.assertEqual(merged["ready_indicator_binary_count"], 1)


class GlobalBlockerTests(unittest.TestCase):
    def test_global_blockers_ignore_deferred_phase_of_price_label(self) -> None:
        blockers = ennrr.build_global_blockers(make_snapshot())

        self.assertTrue(any("runtime" in blocker.lower() for blocker in blockers))
        self.assertTrue(any("draft" in blocker.lower() for blocker in blockers))
        self.assertFalse(any("indicator-spec set" in blocker.lower() for blocker in blockers))
        self.assertTrue(any("tradingview" in blocker.lower() or "pine validation" in blocker.lower() for blocker in blockers))


class PhaseOneChartStateBootstrapSnapshotTests(unittest.TestCase):
    def test_load_phase_one_chart_state_bootstrap_snapshot_defaults_when_missing(self) -> None:
        original_path = ennrr.PHASE_ONE_CHART_STATE_REPORT_PATH
        try:
            ennrr.PHASE_ONE_CHART_STATE_REPORT_PATH = Path("C:/definitely/missing/phase_one_chart_state_report.json")
            snapshot = ennrr.load_phase_one_chart_state_bootstrap_snapshot()
        finally:
            ennrr.PHASE_ONE_CHART_STATE_REPORT_PATH = original_path

        self.assertEqual(snapshot["exported_example_count"], 0)
        self.assertEqual(snapshot["positive_example_count"], 0)
        self.assertEqual(snapshot["negative_example_count"], 0)
        self.assertFalse(snapshot["artifact_present"])

    def test_load_phase_one_chart_state_bootstrap_snapshot_reads_summary(self) -> None:
        original_path = ennrr.PHASE_ONE_CHART_STATE_REPORT_PATH
        with tempfile.TemporaryDirectory() as tmp_dir:
            report_path = Path(tmp_dir) / "phase_one_chart_state_training_surface_report.json"
            report_path.write_text(
                json.dumps(
                    {
                        "summary": {
                            "exported_example_count": 2,
                            "positive_example_count": 1,
                            "negative_example_count": 1,
                            "outcome_decision_counts": {"trade": 1, "no_trade": 1},
                            "source_kind_counts": {
                                "tradingview_pine_alert": 1,
                                "tradingview_validation": 1,
                            },
                        }
                    }
                ),
                encoding="utf-8",
            )
            try:
                ennrr.PHASE_ONE_CHART_STATE_REPORT_PATH = report_path
                snapshot = ennrr.load_phase_one_chart_state_bootstrap_snapshot()
            finally:
                ennrr.PHASE_ONE_CHART_STATE_REPORT_PATH = original_path

        self.assertEqual(snapshot["exported_example_count"], 2)
        self.assertEqual(snapshot["positive_example_count"], 1)
        self.assertEqual(snapshot["negative_example_count"], 1)
        self.assertEqual(snapshot["outcome_decision_counts"]["trade"], 1)
        self.assertTrue(snapshot["artifact_present"])


class NextActionTests(unittest.TestCase):
    def test_build_next_actions_mentions_retrained_challengers_and_updated_gap(self) -> None:
        snapshot = make_snapshot()
        snapshot["tradingview_pine"]["generated_script_coverage"] = 1.0
        snapshot["training_surface"]["reinforcement_example_count"] = 3
        snapshot["training_surface"]["trade_model_binary_tasks"][1][
            "additional_positive_examples_needed"
        ] = 1
        snapshot["iteration_retraining"] = {
            "trained_task_count": 2,
            "trained_task_names": ["continuation_entry_model", "trade_vs_no_trade"],
        }

        actions = ennrr.build_next_actions(snapshot)

        self.assertTrue(any("daily_bias_framework (+1)" in action for action in actions))
        self.assertTrue(any("iteration-retrained challengers" in action for action in actions))
        self.assertTrue(any("Phase 1 training focus" in action for action in actions))

    def test_build_next_actions_mentions_phase_one_chart_state_bootstrap_when_present(self) -> None:
        snapshot = make_snapshot()
        snapshot["phase_one_chart_state_bootstrap"] = {
            "exported_example_count": 2,
            "positive_example_count": 1,
            "negative_example_count": 1,
            "outcome_decision_counts": {"trade": 1, "no_trade": 1},
            "source_kind_counts": {
                "tradingview_pine_alert": 1,
                "tradingview_validation": 1,
            },
            "artifact_present": True,
        }

        actions = ennrr.build_next_actions(snapshot)

        self.assertTrue(any("chart-state bootstrap is now live with 2 labeled examples" in action for action in actions))
        self.assertTrue(any("tiny seed set" in action for action in actions))

    def test_build_next_actions_mentions_promotable_challenger_when_benchmark_exists(self) -> None:
        snapshot = make_snapshot()
        snapshot["iteration_retraining"] = {
            "trained_task_count": 2,
            "trained_task_names": ["continuation_entry_model", "trade_vs_no_trade"],
        }
        snapshot["iteration_challengers"] = {
            "compared_task_count": 2,
            "promotion_candidate_count": 1,
            "promotion_candidate_tasks": ["continuation_entry_model"],
        }

        actions = ennrr.build_next_actions(snapshot)

        self.assertTrue(any("continuation_entry_model" in action for action in actions))
        self.assertFalse(any("Benchmark the latest iteration-retrained challengers" in action for action in actions))

    def test_build_next_actions_switches_from_review_to_monitoring_after_promotion(self) -> None:
        snapshot = make_snapshot()
        snapshot["iteration_retraining"] = {
            "trained_task_count": 2,
            "trained_task_names": ["continuation_entry_model", "trade_vs_no_trade"],
        }
        snapshot["iteration_challengers"] = {
            "compared_task_count": 2,
            "promotion_candidate_count": 1,
            "promotion_candidate_tasks": ["continuation_entry_model"],
        }
        snapshot["iteration_promotions"] = {
            "promoted_task_count": 1,
            "promoted_tasks": ["continuation_entry_model"],
        }

        actions = ennrr.build_next_actions(snapshot)

        self.assertTrue(any("newly promoted champion" in action for action in actions))
        self.assertFalse(any("Review the winning challenger benchmark" in action for action in actions))


if __name__ == "__main__":
    unittest.main()
