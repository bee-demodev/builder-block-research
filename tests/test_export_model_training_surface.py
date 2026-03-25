from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import export_model_training_surface as emts


def make_record() -> dict:
    return {
        "profile_slug": "ttrades_curriculum",
        "profile_name": "TTrades Curriculum",
        "profile_type": "teacher_style",
        "profile_frameworks": [{"framework": "canonical_price_action"}],
        "profile_topics": [{"topic": "continuation"}, {"topic": "equilibrium"}],
        "profile_trade_models": [
            {
                "trade_model": "continuation_entry_model",
                "role": "execution_model",
                "indicator_ready": True,
            },
            {
                "trade_model": "daily_bias_framework",
                "role": "bias_filter",
                "indicator_ready": True,
            },
        ],
        "topic": "continuation",
        "case_ref": "demo_case_001",
        "source_url": "https://example.com/demo",
        "notes": "Demo case",
        "chart_context": {
            "setup_variant": "equilibrium_hold_trend_resumption",
            "source_kind": "article",
            "timeframe_scope": ["fractal"],
            "session_scope": ["new_york_am"],
        },
        "annotation": {
            "anchor_type": "equilibrium_half_range_respect",
            "warning_signals": ["slow_recovery", "range_rotation"],
        },
        "outcome": {"decision": "no_trade", "reason": "continuation_failure_filter"},
    }


class BuildTrainingExampleTests(unittest.TestCase):
    def test_build_training_example_derives_labels_and_features(self) -> None:
        record = make_record()
        link = {
            "trade_model": "continuation_entry_model",
            "relation_type": "execution_model",
            "confidence": 1.0,
        }

        example = emts.build_training_example(record, link)

        self.assertEqual(
            example["example_id"],
            "demo_case_001::continuation_entry_model::execution_model",
        )
        self.assertTrue(example["indicator_ready_in_profile"])
        self.assertEqual(example["targets"]["outcome_decision"], "no_trade")
        self.assertTrue(example["targets"]["is_no_trade"])
        self.assertTrue(example["targets"]["has_outcome_label"])
        self.assertIn("anchor_type", example["features"]["annotation_key_paths"])
        self.assertIn("warning_signals[]", example["features"]["annotation_key_paths"])
        self.assertIn("fractal", example["features"]["timeframe_scope"])
        self.assertIn(
            "equilibrium half range respect",
            example["features"]["annotation_value_tokens"],
        )
        self.assertIn("trade model continuation_entry_model", example["training_text"])


class SummarizeTrainingSurfaceTests(unittest.TestCase):
    def test_small_surface_is_not_marked_ready(self) -> None:
        examples = [
            {
                "case_ref": "case_1",
                "trade_model": "continuation_entry_model",
                "targets": {
                    "trade_model": "continuation_entry_model",
                    "relation_type": "execution_model",
                    "outcome_decision": "unknown",
                    "has_outcome_label": False,
                },
            },
            {
                "case_ref": "case_2",
                "trade_model": "daily_bias_framework",
                "targets": {
                    "trade_model": "daily_bias_framework",
                    "relation_type": "bias_framework",
                    "outcome_decision": "no_trade",
                    "has_outcome_label": True,
                },
            },
        ]

        summary = emts.summarize_training_surface(examples)

        self.assertFalse(summary["task_readiness"]["trade_model_classification"]["ready"])
        self.assertFalse(summary["task_readiness"]["no_trade_filter"]["ready"])
        self.assertGreater(len(summary["recommendations"]), 0)

    def test_binary_task_gap_is_reported(self) -> None:
        examples = []
        for index in range(4):
            examples.append(
                {
                    "case_ref": f"case_a_{index}",
                    "trade_model": "continuation_entry_model",
                    "targets": {
                        "trade_model": "continuation_entry_model",
                        "relation_type": "execution_model",
                        "outcome_decision": "trade",
                        "has_outcome_label": True,
                    },
                }
            )
        for index in range(6):
            examples.append(
                {
                    "case_ref": f"case_b_{index}",
                    "trade_model": "daily_bias_framework",
                    "targets": {
                        "trade_model": "daily_bias_framework",
                        "relation_type": "bias_framework",
                        "outcome_decision": "trade",
                        "has_outcome_label": True,
                    },
                }
            )

        summary = emts.summarize_training_surface(examples)
        continuation_gap = next(
            task
            for task in summary["trade_model_binary_tasks"]
            if task["trade_model"] == "continuation_entry_model"
        )

        self.assertEqual(continuation_gap["additional_positive_examples_needed"], 1)
        self.assertFalse(continuation_gap["ready"])


if __name__ == "__main__":
    unittest.main()
