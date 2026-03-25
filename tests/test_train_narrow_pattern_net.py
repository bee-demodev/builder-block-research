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

import train_narrow_pattern_net as tnpn

try:
    import torch
except ImportError:  # pragma: no cover
    torch = None


def make_surface_example(
    *,
    example_id: str,
    text: str,
    trade_model: str,
    outcome_decision: str,
    has_outcome_label: bool = True,
    outcome_segment_only: bool = False,
) -> dict:
    return {
        "example_id": example_id,
        "trade_model": trade_model,
        "training_text": text,
        "targets": {
            "trade_model": trade_model,
            "outcome_decision": outcome_decision,
            "has_outcome_label": has_outcome_label,
            "outcome_segment_only": outcome_segment_only,
        },
    }


class PrepareTaskExamplesTests(unittest.TestCase):
    def test_prepare_task_examples_builds_one_vs_rest_labels(self) -> None:
        examples = [
            make_surface_example(
                example_id="case_1",
                text="continuation equilibrium retest",
                trade_model="continuation_entry_model",
                outcome_decision="trade",
            ),
            make_surface_example(
                example_id="case_2",
                text="daily bias reversal framework",
                trade_model="daily_bias_framework",
                outcome_decision="trade",
            ),
        ]

        prepared = tnpn.prepare_task_examples(examples, task_name="continuation_entry_model")

        self.assertEqual(prepared["task_name"], "continuation_entry_model")
        self.assertEqual(prepared["positive_label"], "continuation_entry_model")
        self.assertEqual(prepared["negative_label"], "other_trade_models")
        self.assertEqual(len(prepared["examples"]), 2)
        self.assertEqual(
            [item["label"] for item in prepared["examples"]],
            [1, 0],
        )
        self.assertEqual(prepared["skipped_example_ids"], [])

    def test_prepare_task_examples_skips_unknown_outcomes_for_trade_filter(self) -> None:
        examples = [
            make_surface_example(
                example_id="case_1",
                text="continuation equilibrium retest",
                trade_model="continuation_entry_model",
                outcome_decision="trade",
            ),
            make_surface_example(
                example_id="case_2",
                text="continuation failed confirmation",
                trade_model="continuation_entry_model",
                outcome_decision="no_trade",
            ),
            make_surface_example(
                example_id="case_3",
                text="daily bias unresolved context",
                trade_model="daily_bias_framework",
                outcome_decision="unknown",
                has_outcome_label=False,
            ),
            make_surface_example(
                example_id="case_4",
                text="cisd invalidation segment",
                trade_model="daily_bias_c123_map",
                outcome_decision="no_trade",
                outcome_segment_only=True,
            ),
        ]

        prepared = tnpn.prepare_task_examples(examples, task_name="trade_vs_no_trade")

        self.assertEqual(prepared["task_name"], "trade_vs_no_trade")
        self.assertEqual(prepared["positive_label"], "trade")
        self.assertEqual(prepared["negative_label"], "no_trade")
        self.assertEqual(len(prepared["examples"]), 3)
        self.assertEqual(
            [item["label"] for item in prepared["examples"]],
            [1, 0, 0],
        )
        self.assertEqual(prepared["skipped_example_ids"], ["case_3"])

    def test_prepare_task_examples_skips_outcome_only_segments_for_one_vs_rest_tasks(self) -> None:
        examples = [
            make_surface_example(
                example_id="case_1",
                text="daily bias execution map",
                trade_model="daily_bias_c123_map",
                outcome_decision="trade",
            ),
            make_surface_example(
                example_id="case_2",
                text="segmented cisd invalidation",
                trade_model="daily_bias_c123_map",
                outcome_decision="no_trade",
                outcome_segment_only=True,
            ),
            make_surface_example(
                example_id="case_3",
                text="fractal closure confirmation",
                trade_model="fractal_closure_model",
                outcome_decision="trade",
            ),
        ]

        prepared = tnpn.prepare_task_examples(examples, task_name="daily_bias_c123_map")

        self.assertEqual(
            [item["example_id"] for item in prepared["examples"]],
            ["case_1", "case_3"],
        )
        self.assertEqual(prepared["skipped_example_ids"], ["case_2"])


class FeatureTokenTests(unittest.TestCase):
    def test_build_vocabulary_includes_bigram_phrase_tokens(self) -> None:
        examples = [
            {"example_id": "case_1", "text": "continuations fail near equilibrium", "label": 0},
            {"example_id": "case_2", "text": "seek and destroy session profile", "label": 0},
        ]

        vocabulary = tnpn.build_vocabulary(examples)

        self.assertIn("continuations__fail", vocabulary)
        self.assertIn("seek__and", vocabulary)
        self.assertIn("and__destroy", vocabulary)


class TrainTaskClassifierTests(unittest.TestCase):
    def test_train_task_classifier_writes_model_and_report(self) -> None:
        prepared = {
            "task_name": "demo_pattern_task",
            "positive_label": "trade",
            "negative_label": "no_trade",
            "examples": [
                {
                    "example_id": "trade_1",
                    "text": "trend continuation equilibrium hold",
                    "label": 1,
                    "split_group": "split_pos_a",
                    "source_group": "source_pos_a",
                },
                {
                    "example_id": "trade_2",
                    "text": "trend continuation protected swing",
                    "label": 1,
                    "split_group": "split_pos_a",
                    "source_group": "source_pos_a",
                },
                {
                    "example_id": "trade_3",
                    "text": "bullish continuation order block retest",
                    "label": 1,
                    "split_group": "split_pos_b",
                    "source_group": "source_pos_b",
                },
                {
                    "example_id": "trade_4",
                    "text": "continuation entry with displacement",
                    "label": 1,
                    "split_group": "split_pos_b",
                    "source_group": "source_pos_b",
                },
                {
                    "example_id": "skip_1",
                    "text": "failed reversal choppy rotation",
                    "label": 0,
                    "split_group": "split_neg_c",
                    "source_group": "source_neg_c",
                },
                {
                    "example_id": "skip_2",
                    "text": "no trade consolidation drift",
                    "label": 0,
                    "split_group": "split_neg_c",
                    "source_group": "source_neg_c",
                },
                {
                    "example_id": "skip_3",
                    "text": "range rotation invalidation break",
                    "label": 0,
                    "split_group": "split_neg_d",
                    "source_group": "source_neg_d",
                },
                {
                    "example_id": "skip_4",
                    "text": "messy session no confirmation",
                    "label": 0,
                    "split_group": "split_neg_d",
                    "source_group": "source_neg_d",
                },
            ],
            "skipped_example_ids": [],
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir)
            report = tnpn.train_task_classifier(
                prepared,
                output_dir=output_dir,
                device_preference="cpu",
                validation_ratio=0.25,
                epochs=12,
                learning_rate=0.05,
                seed=9,
            )

            report_path = Path(report["report_path"])
            model_path = Path(report["model_path"])

            self.assertEqual(report["task_name"], "demo_pattern_task")
            self.assertEqual(report["device"], "cpu")
            self.assertEqual(report["example_count"], 8)
            self.assertTrue(report_path.exists())
            self.assertTrue(model_path.exists())
            self.assertIn("accuracy", report["metrics"]["train"])
            self.assertIn("accuracy", report["metrics"]["validation"])
            self.assertIn("best_prediction_threshold", report)
            self.assertIn("train_positive_class_weight", report)
            self.assertIn("validation_grouping_used", report)
            self.assertIn("source_holdout_evaluation", report)
            self.assertEqual(report["source_holdout_evaluation"]["group_field"], "source_group")
            self.assertEqual(report["source_holdout_evaluation"]["group_count"], 4)
            self.assertEqual(report["source_holdout_evaluation"]["evaluated_group_count"], 4)
            self.assertEqual(report["source_holdout_evaluation"]["skipped_group_count"], 0)
            self.assertEqual(
                report["source_holdout_evaluation"]["evaluated_positive_group_count"],
                2,
            )
            self.assertEqual(
                report["source_holdout_evaluation"]["evaluated_negative_only_group_count"],
                2,
            )

            saved_report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(saved_report["task_name"], "demo_pattern_task")
            self.assertEqual(saved_report["model_path"], str(model_path))
            self.assertIn("source_holdout_evaluation", saved_report)

    def test_evaluate_source_holdout_report_marks_untrainable_positive_group(self) -> None:
        prepared = {
            "task_name": "demo_pattern_task",
            "positive_label": "trade",
            "negative_label": "no_trade",
            "examples": [
                {
                    "example_id": "trade_only_source",
                    "text": "trend continuation equilibrium hold",
                    "label": 1,
                    "split_group": "split_pos_a",
                    "source_group": "source_pos_a",
                },
                {
                    "example_id": "neg_1",
                    "text": "failed reversal choppy rotation",
                    "label": 0,
                    "split_group": "split_neg_b",
                    "source_group": "source_neg_b",
                },
                {
                    "example_id": "neg_2",
                    "text": "range rotation invalidation break",
                    "label": 0,
                    "split_group": "split_neg_c",
                    "source_group": "source_neg_c",
                },
            ],
            "skipped_example_ids": [],
        }

        report = tnpn.evaluate_source_holdout_report(
            prepared,
            device_preference="cpu",
            epochs=8,
            learning_rate=0.05,
            hidden_dim=8,
            seed=11,
        )

        self.assertEqual(report["group_count"], 3)
        self.assertEqual(report["evaluated_group_count"], 2)
        self.assertEqual(report["skipped_group_count"], 1)
        self.assertEqual(len(report["skipped_groups"]), 1)
        self.assertEqual(report["skipped_groups"][0]["held_out_group"], "source_pos_a")
        self.assertEqual(
            report["skipped_groups"][0]["reason"],
            "training_split_missing_positive_examples",
        )
        self.assertEqual(report["evaluated_positive_group_count"], 0)
        self.assertEqual(report["evaluated_negative_only_group_count"], 2)


@unittest.skipIf(torch is None, "PyTorch is required for threshold selection tests.")
class ThresholdSelectionTests(unittest.TestCase):
    def test_select_prediction_threshold_prefers_recall_preserving_cutoff(self) -> None:
        logits = torch.tensor([-0.2, -0.1, 0.05, 0.4], dtype=torch.float32)
        labels = torch.tensor([0.0, 0.0, 1.0, 1.0], dtype=torch.float32)

        threshold, metrics = tnpn.select_prediction_threshold(
            logits,
            labels,
            candidate_thresholds=(0.2, 0.4, 0.5, 0.6),
        )

        self.assertEqual(threshold, 0.5)
        self.assertGreater(metrics["f1"], 0.0)
        self.assertGreater(metrics["recall"], 0.0)


class StratifiedSplitTests(unittest.TestCase):
    def test_stratified_split_keeps_group_members_together(self) -> None:
        examples = [
            {"example_id": "pos_a_1", "text": "alpha", "label": 1, "split_group": "video_a"},
            {"example_id": "pos_a_2", "text": "alpha two", "label": 1, "split_group": "video_a"},
            {"example_id": "pos_b_1", "text": "beta", "label": 1, "split_group": "video_b"},
            {"example_id": "neg_c_1", "text": "gamma", "label": 0, "split_group": "video_c"},
            {"example_id": "neg_c_2", "text": "gamma two", "label": 0, "split_group": "video_c"},
            {"example_id": "neg_d_1", "text": "delta", "label": 0, "split_group": "video_d"},
        ]

        train_examples, validation_examples = tnpn.stratified_split(
            examples,
            validation_ratio=0.5,
            seed=7,
        )

        train_groups = {example["split_group"] for example in train_examples}
        validation_groups = {example["split_group"] for example in validation_examples}
        self.assertTrue(train_groups.isdisjoint(validation_groups))
        self.assertEqual(train_groups | validation_groups, {"video_a", "video_b", "video_c", "video_d"})

    def test_select_validation_grouping_falls_back_to_split_group(self) -> None:
        examples = [
            {
                "example_id": "pos_a_1",
                "text": "alpha",
                "label": 1,
                "split_group": "bucket_a",
                "source_group": "single_positive_source",
            },
            {
                "example_id": "pos_b_1",
                "text": "beta",
                "label": 1,
                "split_group": "bucket_b",
                "source_group": "single_positive_source",
            },
            {
                "example_id": "neg_c_1",
                "text": "gamma",
                "label": 0,
                "split_group": "bucket_c",
                "source_group": "negative_source_a",
            },
            {
                "example_id": "neg_d_1",
                "text": "delta",
                "label": 0,
                "split_group": "bucket_d",
                "source_group": "negative_source_b",
            },
        ]

        grouping, reason = tnpn.select_validation_grouping(
            examples,
            requested_grouping="source_group",
        )

        self.assertEqual(grouping, "split_group")
        self.assertIsNotNone(reason)

    def test_exact_group_holdout_split_respects_requested_source_group(self) -> None:
        examples = [
            {
                "example_id": "pos_a",
                "text": "alpha",
                "label": 1,
                "split_group": "bucket_a",
                "source_group": "source_a",
            },
            {
                "example_id": "neg_a",
                "text": "alpha neg",
                "label": 0,
                "split_group": "bucket_a_neg",
                "source_group": "source_a",
            },
            {
                "example_id": "pos_b",
                "text": "beta",
                "label": 1,
                "split_group": "bucket_b",
                "source_group": "source_b",
            },
            {
                "example_id": "neg_c",
                "text": "gamma",
                "label": 0,
                "split_group": "bucket_c",
                "source_group": "source_c",
            },
        ]

        train_examples, validation_examples = tnpn.exact_group_holdout_split(
            examples,
            held_out_group="source_a",
            group_field="source_group",
        )

        self.assertEqual({item["example_id"] for item in validation_examples}, {"pos_a", "neg_a"})
        self.assertEqual({item["example_id"] for item in train_examples}, {"pos_b", "neg_c"})


if __name__ == "__main__":
    unittest.main()
