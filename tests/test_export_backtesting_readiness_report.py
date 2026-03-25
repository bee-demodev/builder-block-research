from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import export_backtesting_readiness_report as ebrr


def make_snapshot() -> dict:
    return {
        "understanding": {
            "overall": {
                "overall_understanding_score": 0.9256,
                "scenario_average": 0.9193,
                "scenario_contract_coverage": 0.9375,
            }
        },
        "indicator_spec_machine_checkability_average": 0.8133,
        "topic_coverage_score": 1.0,
        "research_logging_score": 1.0,
        "backlog_visibility_score": 1.0,
        "indicator_spec_coverage": 1.0,
        "backtesting_sources": {
            "presence_score": 1.0,
            "artifact_coverage_score": 0.0,
        },
        "historical_harness": {"harness_score": 0.0},
        "annotation_manifest_sync": {"sync_score": 1.0},
        "backtesting_cases": {
            "case_backtestability_score": 0.885,
            "decision_coverage": 0.9375,
            "reason_coverage": 0.9375,
            "entry_logic_coverage": 0.875,
            "trade_case_exit_coverage": 0.8182,
            "filter_case_reason_coverage": 1.0,
        },
        "backtesting_specs": {
            "rules_backtestability_average": 0.8667,
            "risk_definition_average": 1.0,
            "target_definition_average": 0.8667,
            "anti_lookahead_average": 1.0,
            "session_timeframe_average": 1.0,
            "cost_model_average": 0.0,
            "stage_score": 0.6,
            "non_draft_status_count": 0,
        },
        "training_surface": {
            "label_volume_score": 0.64,
            "outcome_label_coverage": 0.9375,
            "ready_indicator_binary_count": 1,
            "ready_indicator_binary_coverage": 0.2,
            "trade_model_classification_progress": 0.5467,
            "relation_type_classification_progress": 0.5467,
            "task_readiness": {
                "no_trade_filter": {"ready": True},
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
        "indicator_ready_trade_models": [
            "continuation_entry_model",
            "daily_bias_framework",
            "daily_profile_models",
            "fractal_closure_model",
            "reversal_sequence_model",
        ],
        "label_space": {
            "extra_training_labels_without_indicator_specs": ["phases_of_price_framework"],
        },
    }


class SpecBacktestingSummaryTests(unittest.TestCase):
    def test_spec_summary_rewards_explicit_risk_target_and_anti_lookahead(self) -> None:
        specs = [
            {
                "spec_key": "demo",
                "topic": "continuation",
                "name": "Demo",
                "status": "draft",
                "trade_model_slug": "continuation_entry_model",
                "spec": {
                    "direct_topics": [{"topic": "invalidation", "role": "risk"}],
                    "resolved_requirements": [{"topic": "continuation"}],
                    "signal_pipeline": [{"name": "entry"}],
                    "decision_tables": [{"name": "objective_open_filter"}],
                    "state_models": [{"name": "continuationState"}],
                    "input_groups": [
                        {
                            "group": "Risk",
                            "inputs": [
                                {"key": "minimumRewardRisk", "description": "reward to risk"},
                                {"key": "objectiveCompletionMode", "description": "target logic"},
                            ],
                        }
                    ],
                    "acceptance_checks": [
                        "The script must remain bar-close confirmed and avoid intrabar-only transitions.",
                    ],
                    "implementation_scope": {
                        "anti_repaint_baseline": "bar_close_confirmation",
                        "timeframe_stack": {"higher": "D", "lower": "15"},
                    },
                },
            }
        ]

        summary = ebrr.summarize_indicator_spec_backtesting(specs)

        self.assertGreaterEqual(summary["risk_definition_average"], 0.75)
        self.assertGreaterEqual(summary["target_definition_average"], 0.66)
        self.assertGreaterEqual(summary["anti_lookahead_average"], 0.66)
        self.assertGreaterEqual(summary["rules_backtestability_average"], 0.75)


class StageReadinessTests(unittest.TestCase):
    def test_manual_replay_can_be_ready_while_structured_backtesting_is_blocked(self) -> None:
        stages = ebrr.build_stage_readiness(make_snapshot())

        manual_replay = stages["manual_chart_replay_understanding"]
        rules_backtest = stages["rules_based_historical_backtesting"]

        self.assertTrue(manual_replay["ready"])
        self.assertFalse(rules_backtest["ready"])
        self.assertLessEqual(rules_backtest["score"], 0.66)
        self.assertEqual(rules_backtest["verdict"], "not_yet")

    def test_model_assisted_backtesting_is_capped_without_harness(self) -> None:
        stages = ebrr.build_stage_readiness(make_snapshot())

        model_backtest = stages["model_assisted_historical_backtesting"]

        self.assertFalse(model_backtest["ready"])
        self.assertLessEqual(model_backtest["score"], 0.58)


class GlobalBlockerTests(unittest.TestCase):
    def test_global_blockers_surface_harness_and_cost_issues_but_ignore_deferred_label(self) -> None:
        blockers = ebrr.build_global_blockers(make_snapshot())

        self.assertTrue(any("harness" in blocker.lower() for blocker in blockers))
        self.assertTrue(any("slippage" in blocker.lower() or "commission" in blocker.lower() for blocker in blockers))
        self.assertFalse(any("indicator-spec set" in blocker.lower() for blocker in blockers))


if __name__ == "__main__":
    unittest.main()
