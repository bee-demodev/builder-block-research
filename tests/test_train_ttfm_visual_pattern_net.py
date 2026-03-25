from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import train_ttfm_visual_pattern_net as tvpn


def make_rows(base_dir: Path) -> list[dict]:
    image_a = base_dir / "a.png"
    image_b = base_dir / "b.png"
    Image.new("RGB", (32, 32), color=(255, 0, 0)).save(image_a)
    Image.new("RGB", (32, 32), color=(0, 255, 0)).save(image_b)

    return [
        {
            "example_id": "row_a",
            "case_ref": "case_a",
            "checkpoint": "context",
            "active_labels": ["equilibrium", "point_of_interest"],
            "screenshot_path": str(image_a),
            "market_context": {"alignment_status": "unmapped"},
            "sample_weight": 1.0,
        },
        {
            "example_id": "row_b",
            "case_ref": "case_b",
            "checkpoint": "confirmation",
            "active_labels": ["equilibrium"],
            "screenshot_path": str(image_b),
            "market_context": {"alignment_status": "market_context_only"},
            "sample_weight": 0.35,
        },
        {
            "example_id": "row_c",
            "case_ref": "case_c",
            "checkpoint": "outcome",
            "active_labels": ["wick_logic"],
            "screenshot_path": str(base_dir / "missing.png"),
            "market_context": {"alignment_status": "fully_aligned"},
        },
    ]


class SelectLabelSpaceTests(unittest.TestCase):
    def test_select_label_space_applies_min_positive_threshold(self) -> None:
        rows = [
            {"active_labels": ["equilibrium", "point_of_interest"]},
            {"active_labels": ["equilibrium"]},
            {"active_labels": ["wick_logic"]},
        ]

        selected_labels, label_counts, skipped_labels = tvpn.select_label_space(
            rows,
            min_positive_examples=2,
        )

        self.assertEqual(selected_labels, ["equilibrium"])
        self.assertEqual(label_counts["equilibrium"], 2)
        self.assertEqual(label_counts["point_of_interest"], 1)
        self.assertIn("point_of_interest", skipped_labels)
        self.assertIn("wick_logic", skipped_labels)


class BuildExamplesTests(unittest.TestCase):
    def test_build_examples_resolves_images_and_multihot_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            rows = make_rows(Path(tmp_dir))
            label_to_index = {"equilibrium": 0, "point_of_interest": 1}

            examples, skipped = tvpn.build_examples(rows, label_to_index=label_to_index)

        self.assertEqual(len(examples), 2)
        self.assertEqual(len(skipped), 1)
        self.assertEqual(skipped[0]["reason"], "missing_image")

        first = examples[0]
        second = examples[1]
        self.assertEqual(first["example_id"], "row_a")
        self.assertEqual(first["target"], [1.0, 1.0])
        self.assertEqual(first["sample_weight"], 1.0)
        self.assertEqual(second["example_id"], "row_b")
        self.assertEqual(second["target"], [1.0, 0.0])
        self.assertEqual(second["sample_weight"], 0.35)


@unittest.skipIf(tvpn.torch is None, "PyTorch is required for trainer tests.")
class TrainingUtilityTests(unittest.TestCase):
    def test_compute_pos_weight_upweights_sparse_positive_labels(self) -> None:
        labels = tvpn.torch.tensor(
            [
                [1.0, 0.0],
                [0.0, 0.0],
                [1.0, 1.0],
            ],
            dtype=tvpn.torch.float32,
        )

        pos_weight = tvpn.compute_pos_weight(labels)

        self.assertEqual(pos_weight.tolist(), [1.0, 2.0])

    def test_reduce_weighted_multilabel_loss_respects_example_weights(self) -> None:
        per_label_loss = tvpn.torch.tensor(
            [
                [1.0, 3.0],
                [2.0, 4.0],
            ],
            dtype=tvpn.torch.float32,
        )
        example_weights = tvpn.torch.tensor([1.0, 0.5], dtype=tvpn.torch.float32)

        reduced = tvpn.reduce_weighted_multilabel_loss(per_label_loss, example_weights)

        self.assertAlmostEqual(reduced.item(), (2.0 * 1.0 + 3.0 * 0.5) / 1.5, places=6)

    def test_select_prediction_threshold_prefers_f1_over_default_half_threshold(self) -> None:
        logits = tvpn.torch.tensor(
            [
                [-0.2, -1.2],
                [-1.2, -0.3],
            ],
            dtype=tvpn.torch.float32,
        )
        labels = tvpn.torch.tensor(
            [
                [1.0, 0.0],
                [0.0, 1.0],
            ],
            dtype=tvpn.torch.float32,
        )

        best_threshold, metrics = tvpn.select_prediction_threshold(
            logits,
            labels,
            candidate_thresholds=[0.3, 0.5],
        )

        self.assertEqual(best_threshold, 0.3)
        self.assertGreater(metrics["micro_f1"], 0.0)
        default_metrics = tvpn.compute_multilabel_metrics(
            logits=logits,
            labels=labels,
            loss_value=None,
            threshold=0.5,
        )
        self.assertLess(default_metrics["micro_f1"], metrics["micro_f1"])

    def test_compute_multilabel_metrics_supports_per_label_thresholds(self) -> None:
        logits = tvpn.torch.tensor(
            [
                [-0.405465, 0.405465],
                [-1.386294, 1.386294],
            ],
            dtype=tvpn.torch.float32,
        )
        labels = tvpn.torch.tensor(
            [
                [1.0, 0.0],
                [0.0, 1.0],
            ],
            dtype=tvpn.torch.float32,
        )

        metrics = tvpn.compute_multilabel_metrics(
            logits=logits,
            labels=labels,
            loss_value=None,
            threshold=[0.3, 0.7],
        )

        self.assertAlmostEqual(metrics["micro_f1"], 1.0, places=6)
        self.assertEqual(metrics["positive_predictions"], 2)

    def test_select_per_label_prediction_thresholds_can_outperform_global_threshold(self) -> None:
        logits = tvpn.torch.tensor(
            [
                [-0.405465, 0.405465],
                [-1.386294, 1.386294],
            ],
            dtype=tvpn.torch.float32,
        )
        labels = tvpn.torch.tensor(
            [
                [1.0, 0.0],
                [0.0, 1.0],
            ],
            dtype=tvpn.torch.float32,
        )

        global_threshold, global_metrics = tvpn.select_prediction_threshold(
            logits,
            labels,
            candidate_thresholds=[0.3, 0.5, 0.7],
        )
        per_label_thresholds, per_label_metrics = tvpn.select_per_label_prediction_thresholds(
            logits,
            labels,
            candidate_thresholds=[0.3, 0.5, 0.7],
        )

        self.assertEqual(global_threshold, 0.3)
        self.assertEqual(per_label_thresholds, [0.3, 0.7])
        self.assertGreater(per_label_metrics["micro_f1"], global_metrics["micro_f1"])


if __name__ == "__main__":
    unittest.main()
