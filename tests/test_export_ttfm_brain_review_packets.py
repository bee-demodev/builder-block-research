from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import export_ttfm_brain_review_packets as etbrp


class BrainReviewPacketsTests(unittest.TestCase):
    def test_build_brain_review_packets_ranks_by_disagreement_then_checkpoint_weight(self) -> None:
        queue = {
            "summary": {"row_count": 3},
            "items": [
                {
                    "example_id": "case_low",
                    "checkpoint": "context",
                    "disagreement_count": 1,
                    "priority_score": 55,
                    "priority_band": "medium",
                    "priority_reasons": ["demo"],
                    "recommended_action": "review_model_disagreement",
                    "weak_active_labels": ["order_block"],
                    "predicted_labels": ["fair_value_gap"],
                    "label_probabilities": {"order_block": 0.22, "fair_value_gap": 0.81},
                    "prediction_threshold_mode": "per_label",
                    "prediction_thresholds": {"order_block": 0.45, "fair_value_gap": 0.5},
                    "prediction_threshold": 0.475,
                    "missing_weak_labels": ["order_block"],
                    "extra_predicted_labels": ["fair_value_gap"],
                    "uncertainty_labels": ["order_block"],
                    "weak_label_confidence": 0.35,
                    "sample_weight": 0.35,
                    "screenshot_path": "a.png",
                    "audio_path": "a.wav",
                    "evidence_refs": ["chunk:a"],
                },
                {
                    "example_id": "case_high",
                    "checkpoint": "confirmation",
                    "disagreement_count": 2,
                    "priority_score": 90,
                    "priority_band": "high",
                    "priority_reasons": ["demo"],
                    "recommended_action": "review_model_disagreement",
                    "weak_active_labels": ["order_block"],
                    "predicted_labels": ["fair_value_gap", "breaker"],
                    "label_probabilities": {"order_block": 0.18, "fair_value_gap": 0.84, "breaker": 0.72},
                    "prediction_threshold_mode": "global",
                    "prediction_threshold": 0.5,
                    "missing_weak_labels": ["order_block"],
                    "extra_predicted_labels": ["breaker", "fair_value_gap"],
                    "uncertainty_labels": [],
                    "weak_label_confidence": 0.35,
                    "sample_weight": 0.35,
                    "screenshot_path": "b.png",
                    "audio_path": "b.wav",
                    "evidence_refs": ["chunk:b"],
                },
                {
                    "example_id": "case_same_disagreement",
                    "checkpoint": "sweep",
                    "disagreement_count": 2,
                    "priority_score": 88,
                    "priority_band": "high",
                    "priority_reasons": ["demo"],
                    "recommended_action": "review_model_disagreement",
                    "weak_active_labels": ["liquidity_sweep"],
                    "predicted_labels": ["liquidity_sweep", "order_block"],
                    "label_probabilities": {"liquidity_sweep": 0.91, "order_block": 0.66},
                    "prediction_threshold_mode": "global",
                    "prediction_threshold": 0.5,
                    "missing_weak_labels": [],
                    "extra_predicted_labels": ["order_block"],
                    "uncertainty_labels": [],
                    "weak_label_confidence": 0.35,
                    "sample_weight": 0.35,
                    "screenshot_path": "c.png",
                    "audio_path": None,
                    "evidence_refs": ["chunk:c"],
                },
            ],
        }
        dataset_rows = [
            {"example_id": "case_high", "transcript_text": "highest disagreement transcript"},
            {"example_id": "case_same_disagreement", "transcript_text": "sweep transcript"},
            {"example_id": "case_low", "transcript_text": "low disagreement transcript"},
        ]

        packets = etbrp.build_brain_review_packets(queue, dataset_rows=dataset_rows, limit=2)

        self.assertEqual(packets["summary"]["packet_count"], 2)
        self.assertEqual(packets["packets"][0]["example_id"], "case_high")
        self.assertEqual(packets["packets"][1]["example_id"], "case_same_disagreement")
        self.assertEqual(packets["packets"][0]["reviewer_action"], "Compare weak labels against model probabilities and correct the label set.")
        self.assertEqual(packets["packets"][0]["transcript_snippet"], "highest disagreement transcript")
        self.assertEqual(packets["packets"][0]["recommended_action"], "review_model_disagreement")
        self.assertEqual(packets["packets"][0]["prediction_threshold_mode"], "global")


if __name__ == "__main__":
    unittest.main()
