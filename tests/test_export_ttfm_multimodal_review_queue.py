from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import export_ttfm_multimodal_review_queue as etmrq


def make_weak_multimodal_rows() -> list[dict]:
    return [
        {
            "example_id": "approved_case::confirmation",
            "case_ref": "approved_case",
            "video_slug": "approved_video",
            "title": "Approved Video",
            "checkpoint": "confirmation",
            "corpus_partition": "trade_review",
            "review_categories": ["trade_review"],
            "active_labels": ["fair_value_gap", "order_block"],
            "weak_label_confidence": 0.8,
            "sample_weight": 0.95,
            "review_status": "approved_for_teacher",
            "contradiction_status": "resolved",
            "screenshot_path": "knowledge/ttfm_video_corpus/frames/approved/confirmation.jpg",
            "audio_path": "knowledge/ttfm_video_corpus/audio_clips/approved/confirmation.wav",
            "transcript_text": "fair value gap order block confirmation",
            "evidence_refs": ["yt:1", "page:1", "chunk:1"],
        },
        {
            "example_id": "disagreement_case::confirmation",
            "case_ref": "disagreement_case",
            "video_slug": "disagreement_video",
            "title": "Disagreement Video",
            "checkpoint": "confirmation",
            "corpus_partition": "trade_review",
            "review_categories": ["weekly_recap"],
            "active_labels": ["liquidity_sweep", "order_block"],
            "weak_label_confidence": 0.35,
            "sample_weight": 0.35,
            "review_status": "ready_for_weak_training",
            "contradiction_status": "unreviewed",
            "screenshot_path": "knowledge/ttfm_video_corpus/frames/disagreement/confirmation.jpg",
            "audio_path": "knowledge/ttfm_video_corpus/audio_clips/disagreement/confirmation.wav",
            "transcript_text": "sweep setup with possible invalidation",
            "evidence_refs": ["yt:2", "chunk:2"],
        },
        {
            "example_id": "blocked_case::context",
            "case_ref": "blocked_case",
            "video_slug": "blocked_video",
            "title": "Blocked Video",
            "checkpoint": "context",
            "corpus_partition": "seed_curriculum",
            "review_categories": [],
            "active_labels": ["point_of_interest"],
            "weak_label_confidence": 0.35,
            "sample_weight": 0.35,
            "review_status": "ready_for_weak_training",
            "contradiction_status": "blocked",
            "screenshot_path": "knowledge/ttfm_video_corpus/frames/blocked/context.jpg",
            "audio_path": "knowledge/ttfm_video_corpus/audio_clips/blocked/context.wav",
            "transcript_text": "poi context",
            "evidence_refs": ["yt:3"],
        },
    ]


def make_predictions() -> dict[str, dict]:
    return {
        "approved_case::confirmation": {
            "label_probabilities": {
                "fair_value_gap": 0.91,
                "order_block": 0.88,
                "liquidity_sweep": 0.09,
            }
        },
        "disagreement_case::confirmation": {
            "label_probabilities": {
                "liquidity_sweep": 0.24,
                "order_block": 0.39,
                "point_of_interest": 0.83,
            }
        },
        "blocked_case::context": {
            "label_probabilities": {
                "point_of_interest": 0.65,
                "fair_value_gap": 0.28,
            }
        },
    }


class MultimodalReviewQueueTests(unittest.TestCase):
    def test_build_review_queue_prioritizes_disagreement_and_summarizes_actions(self) -> None:
        queue = etmrq.build_multimodal_review_queue(
            make_weak_multimodal_rows(),
            predictions_by_example_id=make_predictions(),
            threshold=0.35,
        )

        self.assertEqual(queue["summary"]["row_count"], 3)
        self.assertEqual(queue["summary"]["ready_to_promote_count"], 1)
        self.assertEqual(queue["summary"]["blocked_contradiction_count"], 1)
        self.assertEqual(queue["summary"]["model_disagreement_count"], 1)
        self.assertAlmostEqual(queue["summary"]["mean_disagreement_count"], 2 / 3, places=6)
        self.assertEqual(queue["summary"]["reviewed_row_count"], 1)
        self.assertAlmostEqual(queue["summary"]["reviewed_alignment_precision"], 1.0, places=6)
        self.assertEqual(queue["summary"]["recommended_action_counts"]["promote_into_teacher_surface"], 1)
        self.assertEqual(queue["summary"]["recommended_action_counts"]["review_model_disagreement"], 1)
        self.assertEqual(
            queue["summary"]["recommended_action_counts"]["resolve_contradiction_before_review"],
            1,
        )

        items = queue["items"]
        self.assertEqual(items[0]["example_id"], "disagreement_case::confirmation")
        self.assertEqual(items[0]["recommended_action"], "review_model_disagreement")
        self.assertEqual(items[0]["missing_weak_labels"], ["liquidity_sweep"])
        self.assertEqual(items[0]["extra_predicted_labels"], ["point_of_interest"])
        self.assertLess(items[0]["label_jaccard"], 0.5)
        self.assertEqual(items[0]["framework_slug"], "ttfm")
        self.assertEqual(items[0]["brain_type"], "setup_scorer")
        self.assertEqual(items[0]["embedding_backend"], "google_gemini")
        self.assertEqual(items[0]["prediction_threshold_mode"], "global")
        self.assertEqual(items[0]["corpus_partition"], "trade_review")
        self.assertEqual(items[0]["review_categories"], ["weekly_recap"])

        self.assertEqual(items[1]["example_id"], "blocked_case::context")
        self.assertEqual(items[1]["recommended_action"], "resolve_contradiction_before_review")

        self.assertEqual(items[2]["example_id"], "approved_case::confirmation")
        self.assertEqual(items[2]["recommended_action"], "promote_into_teacher_surface")
        self.assertGreaterEqual(items[2]["label_jaccard"], 1.0)
        self.assertEqual(items[2]["predicted_labels"], ["fair_value_gap", "order_block"])


if __name__ == "__main__":
    unittest.main()
