from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import export_ttfm_video_weak_visual_dataset as etvwvd


def make_window_rows() -> list[dict]:
    return [
        {
            "example_id": "youtube_case::context",
            "case_ref": "youtube_case",
            "source_type": "youtube_visual_window",
            "video_slug": "fractal_model_fundamentals",
            "video_id": "TNybDCtwBnc",
            "title": "Fractal Model Fundamentals",
            "source_url": "https://youtu.be/TNybDCtwBnc",
            "source_page": "https://ttrades.com/fractal-model-playbook/",
            "corpus_partition": "trade_review",
            "review_categories": ["chart_lesson"],
            "checkpoint": "context",
            "timeframe": "htf",
            "timeframe_role": "htf",
            "topics": ["daily_bias", "equilibrium"],
            "supporting_topics": ["daily_bias", "equilibrium"],
            "candidate_labels": ["equilibrium", "point_of_interest"],
            "candidate_label_provenance": "youtube_transcript_checkpoint_heuristic",
            "cue_terms": ["equilibrium", "poi"],
            "nearby_transcript_text": "Equilibrium creates the higher timeframe context.",
            "transcript_source": "aligned_youtube_transcript",
            "source_chunk_id": "fractal_model_fundamentals:0001",
            "frame_path": "knowledge/ttfm_video_corpus/frames/fractal_model_fundamentals/context_00119280.jpg",
            "frame_status": "extracted",
            "market_context": {"confidence": 0.35},
            "embedding_text": "Title: Fractal Model Fundamentals\nCheckpoint: context",
        },
        {
            "example_id": "youtube_case::outcome",
            "case_ref": "youtube_case",
            "video_slug": "fractal_model_fundamentals",
            "video_id": "TNybDCtwBnc",
            "title": "Fractal Model Fundamentals",
            "checkpoint": "outcome",
            "candidate_labels": ["invalidation"],
            "frame_path": None,
            "frame_status": "missing_video",
            "market_context": {"confidence": 0.35},
        },
    ]


class BuildVideoWeakVisualDatasetRowsTests(unittest.TestCase):
    def test_build_video_weak_visual_dataset_rows_maps_windows_to_training_shape(self) -> None:
        rows = etvwvd.build_video_weak_visual_dataset_rows(make_window_rows())

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["example_id"], "youtube_case::context")
        self.assertEqual(rows[0]["active_labels"], ["equilibrium", "point_of_interest"])
        self.assertEqual(
            rows[0]["screenshot_path"],
            "knowledge/ttfm_video_corpus/frames/fractal_model_fundamentals/context_00119280.jpg",
        )
        self.assertEqual(rows[0]["review_status"], "ready_for_weak_training")
        self.assertEqual(rows[0]["eligible_for_training"], True)
        self.assertEqual(rows[0]["training_blockers"], [])
        self.assertEqual(rows[0]["transcript_source"], "aligned_youtube_transcript")
        self.assertEqual(rows[0]["corpus_partition"], "trade_review")
        self.assertEqual(rows[0]["review_categories"], ["chart_lesson"])
        self.assertIn("https://youtu.be/TNybDCtwBnc", rows[0]["evidence_refs"])
        self.assertEqual(rows[1]["review_status"], "missing_frame")

    def test_build_video_weak_visual_dataset_report_summarizes_training_readiness(self) -> None:
        rows, report = etvwvd.build_video_weak_visual_dataset_report(make_window_rows())

        self.assertEqual(len(rows), 2)
        self.assertEqual(report["summary"]["row_count"], 2)
        self.assertEqual(report["summary"]["video_count"], 1)
        self.assertEqual(report["summary"]["ready_for_weak_training_count"], 1)
        self.assertEqual(report["summary"]["skipped_missing_frame_count"], 1)
        self.assertEqual(report["summary"]["checkpoint_counts"]["context"], 1)
        self.assertEqual(report["summary"]["active_label_counts"]["equilibrium"], 1)
        self.assertEqual(report["summary"]["active_label_counts"]["invalidation"], 1)

    def test_build_video_weak_visual_dataset_rows_marks_synthetic_and_unlabeled_rows_ineligible(self) -> None:
        rows = etvwvd.build_video_weak_visual_dataset_rows(
            [
                {
                    "example_id": "youtube_case::synthetic",
                    "video_slug": "fractal_model_fundamentals",
                    "checkpoint": "context",
                    "candidate_labels": ["equilibrium"],
                    "frame_path": "knowledge/ttfm_video_corpus/frames/fractal_model_fundamentals/context_00119280.jpg",
                    "frame_status": "extracted",
                    "transcript_source": "synthetic_from_video_metadata",
                },
                {
                    "example_id": "youtube_case::needs_labels",
                    "video_slug": "fractal_model_fundamentals",
                    "checkpoint": "confirmation",
                    "candidate_labels": [],
                    "frame_path": "knowledge/ttfm_video_corpus/frames/fractal_model_fundamentals/confirmation_00150000.jpg",
                    "frame_status": "extracted",
                    "transcript_source": "aligned_youtube_transcript",
                },
            ]
        )

        rows_by_id = {row["example_id"]: row for row in rows}
        synthetic_row = rows_by_id["youtube_case::synthetic"]
        unlabeled_row = rows_by_id["youtube_case::needs_labels"]

        self.assertEqual(synthetic_row["training_blockers"], ["synthetic_transcript"])
        self.assertEqual(synthetic_row["review_status"], "needs_teacher_review")
        self.assertFalse(synthetic_row["eligible_for_training"])
        self.assertEqual(unlabeled_row["training_blockers"], ["missing_weak_labels"])
        self.assertEqual(unlabeled_row["review_status"], "needs_label_review")
        self.assertFalse(unlabeled_row["eligible_for_training"])


if __name__ == "__main__":
    unittest.main()
