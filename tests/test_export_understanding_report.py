from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import export_understanding_report as eur


class ScoreIndicatorSpecUnderstandingTests(unittest.TestCase):
    def test_rule_reference_validity_penalizes_missing_refs(self) -> None:
        spec = {
            "spec_key": "demo_missing_refs",
            "scope_topics": ["continuation"],
            "direct_topics": [{"topic": "continuation"}],
            "resolved_requirements": [{"topic": "continuation"}],
            "topic_rule_trace": [
                {
                    "topic": "continuation",
                    "rules": [
                        {"rule_ref": "continuation.continuation_definition"},
                    ],
                }
            ],
            "input_groups": [{"group": "A", "inputs": [{"key": "foo"}]}],
            "derived_series": [{"series": "s1"}],
            "state_models": [{"name": "fsm"}],
            "signal_pipeline": [
                {
                    "step": 1,
                    "name": "Demo",
                    "logic": "demo",
                    "rule_refs": [
                        "continuation.continuation_definition",
                        "continuation.missing_rule",
                    ],
                }
            ],
            "visuals": ["v1"],
            "alerts": [{"name": "a1"}],
            "provisional_proxies": [{"id": "p1"}],
            "acceptance_checks": ["c1"],
            "open_implementation_questions": [],
            "implementation_scope": {"translation_stage": "draft"},
        }

        scored = eur.score_indicator_spec_understanding(spec)

        self.assertLess(scored["dimensions"]["rule_reference_validity"], 1.0)
        self.assertTrue(
            any("missing_rule" in issue for issue in scored["issues"]),
            msg=scored["issues"],
        )

    def test_strong_spec_scores_as_high_understanding(self) -> None:
        spec = {
            "spec_key": "demo_strong_spec",
            "scope_topics": ["continuation", "expansion"],
            "direct_topics": [{"topic": "continuation"}],
            "resolved_requirements": [
                {"topic": "continuation"},
                {"topic": "expansion"},
            ],
            "topic_rule_trace": [
                {
                    "topic": "continuation",
                    "rules": [
                        {"rule_ref": "continuation.continuation_definition"},
                        {"rule_ref": "continuation.continuation_failure_filters"},
                    ],
                },
                {
                    "topic": "expansion",
                    "rules": [
                        {"rule_ref": "expansion.expansion_definition"},
                    ],
                },
            ],
            "input_groups": [
                {
                    "group": "A",
                    "inputs": [
                        {"key": "foo_threshold", "type": "float", "description": "threshold"},
                        {"key": "bar_mode", "type": "enum", "description": "mode"},
                        {"key": "baz_count", "type": "int", "description": "count"},
                    ],
                },
                {
                    "group": "B",
                    "inputs": [
                        {"key": "alpha_ratio", "type": "float", "description": "ratio"},
                        {"key": "beta_score", "type": "int", "description": "score"},
                        {"key": "gamma_tolerance", "type": "float", "description": "tolerance"},
                    ],
                },
                {
                    "group": "C",
                    "inputs": [
                        {"key": "delta_mode", "type": "enum", "description": "mode"},
                        {"key": "epsilon_fraction", "type": "float", "description": "fraction"},
                    ],
                },
            ],
            "derived_series": [
                {"series": "s1"},
                {"series": "s2"},
                {"series": "s3"},
                {"series": "s4"},
                {"series": "s5"},
            ],
            "state_models": [{"name": "fsm"}],
            "signal_pipeline": [
                {
                    "step": 1,
                    "name": "Context",
                    "logic": "demo",
                    "rule_refs": [
                        "continuation.continuation_definition",
                        "expansion.expansion_definition",
                    ],
                },
                {
                    "step": 2,
                    "name": "Failure",
                    "logic": "demo",
                    "rule_refs": ["continuation.continuation_failure_filters"],
                },
            ],
            "decision_tables": [{"name": "d1"}, {"name": "d2"}],
            "visuals": ["v1", "v2", "v3", "v4"],
            "alerts": [{"name": "a1"}, {"name": "a2"}, {"name": "a3"}, {"name": "a4"}],
            "provisional_proxies": [{"id": "p1"}, {"id": "p2"}, {"id": "p3"}, {"id": "p4"}],
            "acceptance_checks": ["c1", "c2", "c3", "c4", "c5", "c6"],
            "open_implementation_questions": [{"question": "narrow gap"}, {"question": "threshold tune"}],
            "implementation_scope": {
                "translation_stage": "draft",
                "build_target": "indicator",
                "candidate_preservation_rule": "keep_draft",
            },
        }

        scored = eur.score_indicator_spec_understanding(spec)

        self.assertGreaterEqual(scored["understanding_score"], 0.8)
        self.assertIn(scored["grade"], {"A", "A-"})
        self.assertEqual(scored["dimensions"]["rule_reference_validity"], 1.0)


class SummarizeUnderstandingTests(unittest.TestCase):
    def test_summary_aggregates_topic_and_spec_scores(self) -> None:
        summary = eur.summarize_understanding(
            topic_scores=[
                {"topic": "bias", "understanding_score": 0.9},
                {"topic": "continuation", "understanding_score": 0.8},
            ],
            indicator_spec_scores=[
                {"spec_key": "a", "understanding_score": 0.7},
                {"spec_key": "b", "understanding_score": 0.9},
            ],
        )

        self.assertAlmostEqual(summary["topic_average"], 0.85, places=4)
        self.assertAlmostEqual(summary["indicator_spec_average"], 0.8, places=4)
        self.assertAlmostEqual(summary["overall_understanding_score"], 0.8225, places=4)
        self.assertIn("grade", summary)


class ScenarioScoringTests(unittest.TestCase):
    def test_scenario_case_without_contract_is_marked_ungraded(self) -> None:
        case = {
            "case_ref": "uncontracted_case",
            "topic": "continuation",
            "chart_context": {"timeframe_scope": ["fractal"]},
            "annotation": {"mode": "continuation"},
        }
        spec = {
            "trade_model": {"slug": "continuation_entry_model"},
            "scope_topics": ["continuation"],
            "direct_topics": [{"topic": "continuation"}],
            "resolved_requirements": [{"topic": "continuation"}],
            "implementation_scope": {"timeframe_stack": {"higher": "daily_frame"}},
        }

        scored = eur.score_scenario_case(case, spec, "continuation_entry_model")

        self.assertFalse(scored["contract_defined"])
        self.assertIsNone(scored["scenario_score"])
        self.assertEqual(scored["grade"], "ungraded")
        self.assertIsNone(scored["dimensions"]["concept_match"])

    def test_scenario_case_scores_low_when_expected_concepts_are_missing(self) -> None:
        case = {
            "case_ref": "ttrades_continuation_equilibrium_hold_baseline_v1",
            "topic": "continuation",
            "chart_context": {"timeframe_scope": ["fractal"]},
            "annotation": {
                "anchor_type": "equilibrium_half_range_respect",
                "confirmation": "fast_close_through_opposing_series",
                "objective": "next_external_liquidity",
            },
        }
        spec = {
            "trade_model": {"slug": "continuation_entry_model"},
            "scope_topics": ["continuation"],
            "direct_topics": [{"topic": "continuation"}],
            "resolved_requirements": [{"topic": "continuation"}],
            "implementation_scope": {"timeframe_stack": {"higher": "daily_frame"}},
            "implementation_summary": "Generic continuation note.",
            "signal_pipeline": [],
            "derived_series": [],
            "input_groups": [],
            "visuals": [],
            "alerts": [],
            "acceptance_checks": [],
            "provisional_proxies": [],
            "decision_tables": [],
            "state_models": [],
            "open_implementation_questions": [],
        }

        scored = eur.score_scenario_case(case, spec, "continuation_entry_model")

        self.assertLess(scored["scenario_score"], 0.6)
        self.assertGreater(len(scored["missing_concepts"]), 0)

    def test_scenario_case_scores_high_when_spec_supports_expected_case(self) -> None:
        case = {
            "case_ref": "ttrades_daily_bias_continuation_baseline_v1",
            "topic": "bias",
            "chart_context": {"timeframe_scope": ["higher", "lower"]},
            "annotation": {
                "mode": "continuation_day",
                "reference_range": "previous_day_range",
                "equilibrium_role": "continuation_area_of_interest",
                "lower_timeframe_confirmation": "required",
                "objective": "previous_day_directional_objective_then_external_liquidity",
            },
        }
        spec = {
            "trade_model": {"slug": "daily_bias_framework"},
            "scope_topics": ["bias", "equilibrium", "continuation"],
            "direct_topics": [{"topic": "bias"}],
            "resolved_requirements": [
                {"topic": "bias"},
                {"topic": "equilibrium"},
                {"topic": "continuation"},
            ],
            "implementation_scope": {
                "timeframe_stack": {
                    "higher": "daily_or_4h_context_frame",
                    "lower": "15m_or_5m_confirmation_frame",
                }
            },
            "implementation_summary": "Daily bias framework using previous-day range, equilibrium respect, continuation framing, lower timeframe confirmation, and external liquidity objectives.",
            "signal_pipeline": [
                {
                    "name": "Bias",
                    "logic": "Use previous-day range and equilibrium to frame continuation day bias and lower timeframe confirmation.",
                }
            ],
            "derived_series": [{"series": "previousDayRange"}, {"series": "equilibriumState"}],
            "input_groups": [
                {"group": "Context", "inputs": [{"key": "previousDayRange"}, {"key": "lowerTimeframeConfirmation"}]}
            ],
            "visuals": ["previous day range", "equilibrium", "external liquidity"],
            "alerts": [{"name": "continuation_day"}],
            "acceptance_checks": ["Lower timeframe confirmation is required before bias is promoted."],
            "provisional_proxies": [{"id": "equilibrium_hold"}],
            "decision_tables": [{"name": "continuation_day"}],
            "state_models": [{"name": "biasState"}],
            "open_implementation_questions": [],
        }

        scored = eur.score_scenario_case(case, spec, "daily_bias_framework")

        self.assertGreaterEqual(scored["scenario_score"], 0.85)
        self.assertEqual(scored["missing_concepts"], [])


if __name__ == "__main__":
    unittest.main()
