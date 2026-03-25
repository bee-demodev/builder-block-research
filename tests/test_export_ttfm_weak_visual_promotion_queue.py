from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import export_ttfm_weak_visual_promotion_queue as etwvpq


def make_weak_rows() -> list[dict]:
    return [
        {
            "example_id": "approved_case::confirmation",
            "case_ref": "approved_case",
            "video_slug": "approved_video",
            "title": "Approved Video",
            "checkpoint": "confirmation",
            "active_labels": ["order_block", "liquidity_sweep", "fair_value_gap"],
            "weak_label_confidence": 0.8,
            "evidence_refs": ["yt:1", "page:1", "chunk:1"],
            "screenshot_path": "knowledge/ttfm_video_corpus/frames/approved/confirmation.jpg",
            "review_status": "approved_for_teacher",
            "contradiction_status": "resolved",
        },
        {
            "example_id": "pending_case::confirmation",
            "case_ref": "pending_case",
            "video_slug": "pending_video",
            "title": "Pending Video",
            "checkpoint": "confirmation",
            "active_labels": ["order_block", "liquidity_sweep"],
            "weak_label_confidence": 0.35,
            "evidence_refs": ["yt:2", "chunk:2"],
            "screenshot_path": "knowledge/ttfm_video_corpus/frames/pending/confirmation.jpg",
            "review_status": "ready_for_weak_training",
            "contradiction_status": "unreviewed",
        },
        {
            "example_id": "blocked_case::context",
            "case_ref": "blocked_case",
            "video_slug": "blocked_video",
            "title": "Blocked Video",
            "checkpoint": "context",
            "active_labels": ["point_of_interest"],
            "weak_label_confidence": 0.35,
            "evidence_refs": ["yt:3"],
            "screenshot_path": "knowledge/ttfm_video_corpus/frames/blocked/context.jpg",
            "review_status": "approved_for_teacher",
            "contradiction_status": "blocked",
        },
    ]


class WeakVisualPromotionQueueTests(unittest.TestCase):
    def test_build_promotion_queue_ranks_items_and_summarizes_actions(self) -> None:
        queue = etwvpq.build_weak_visual_promotion_queue(make_weak_rows())

        self.assertEqual(queue["summary"]["row_count"], 3)
        self.assertEqual(queue["summary"]["ready_to_promote_count"], 1)
        self.assertEqual(queue["summary"]["review_candidate_count"], 1)
        self.assertEqual(queue["summary"]["blocked_contradiction_count"], 1)
        self.assertEqual(queue["summary"]["recommended_action_counts"]["promote_into_teacher_surface"], 1)
        self.assertEqual(queue["summary"]["recommended_action_counts"]["review_for_teacher_promotion"], 1)
        self.assertEqual(
            queue["summary"]["recommended_action_counts"]["resolve_contradiction_before_review"],
            1,
        )

        items = queue["items"]
        self.assertEqual(items[0]["example_id"], "approved_case::confirmation")
        self.assertEqual(items[0]["recommended_action"], "promote_into_teacher_surface")
        self.assertEqual(items[0]["priority_band"], "high")

        self.assertEqual(items[1]["example_id"], "pending_case::confirmation")
        self.assertEqual(items[1]["recommended_action"], "review_for_teacher_promotion")
        self.assertIn("checkpoint:confirmation", items[1]["priority_reasons"])

        self.assertEqual(items[2]["example_id"], "blocked_case::context")
        self.assertEqual(items[2]["recommended_action"], "resolve_contradiction_before_review")

        self.assertGreater(items[0]["priority_score"], items[1]["priority_score"])
        self.assertGreater(items[1]["priority_score"], items[2]["priority_score"])


if __name__ == "__main__":
    unittest.main()
