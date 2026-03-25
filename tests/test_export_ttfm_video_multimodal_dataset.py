from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import export_ttfm_video_multimodal_dataset as etvmd


def make_window_rows() -> list[dict]:
    return [
        {
            "example_id": "youtube_case::confirmation",
            "video_slug": "fractal_model_fundamentals",
            "video_path": "knowledge/ttfm_video_corpus/videos/fractal_model_fundamentals.mp4",
            "frame_path": "knowledge/ttfm_video_corpus/frames/fractal_model_fundamentals/confirmation_00100000.jpg",
            "midpoint_seconds": 100.0,
            "start": 95.0,
            "end": 105.0,
            "corpus_partition": "trade_review",
            "review_categories": ["trade_review"],
            "nearby_transcript_text": "This is the confirmation transcript window.",
            "transcript_source": "aligned_youtube_transcript",
            "embedding_text": "Embedding text block",
        },
        {
            "example_id": "youtube_case::context",
            "video_slug": "fractal_model_fundamentals",
            "video_path": "knowledge/ttfm_video_corpus/videos/fractal_model_fundamentals.mp4",
            "frame_path": "knowledge/ttfm_video_corpus/frames/fractal_model_fundamentals/context_00050000.jpg",
            "midpoint_seconds": 50.0,
            "start": 40.0,
            "end": 60.0,
            "nearby_transcript_text": "Context transcript.",
        },
    ]


def make_weak_rows() -> list[dict]:
    return [
        {
            "example_id": "youtube_case::confirmation",
            "case_ref": "youtube_case",
            "checkpoint": "confirmation",
            "active_labels": ["order_block", "liquidity_sweep"],
            "weak_label_confidence": 0.35,
            "eligible_for_training": True,
            "review_status": "ready_for_weak_training",
            "contradiction_status": "unreviewed",
            "training_blockers": [],
            "screenshot_path": "knowledge/ttfm_video_corpus/frames/fractal_model_fundamentals/confirmation_00100000.jpg",
        },
        {
            "example_id": "youtube_case::missing_window",
            "case_ref": "youtube_case",
            "checkpoint": "outcome",
            "active_labels": ["invalidation"],
            "weak_label_confidence": 0.35,
            "review_status": "ready_for_weak_training",
            "contradiction_status": "unreviewed",
            "screenshot_path": "knowledge/ttfm_video_corpus/frames/fractal_model_fundamentals/outcome_00150000.jpg",
        },
    ]


class BuildVideoMultimodalDatasetTests(unittest.TestCase):
    def test_build_rows_joins_weak_labels_to_windows_and_audio_paths(self) -> None:
        rows, report = etvmd.build_video_multimodal_dataset_report(
            weak_rows=make_weak_rows(),
            window_rows=make_window_rows(),
            audio_output_dir=Path("knowledge/ttfm_video_corpus/audio_clips"),
            clip_duration_seconds=6.0,
        )

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["example_id"], "youtube_case::confirmation")
        self.assertEqual(row["active_labels"], ["order_block", "liquidity_sweep"])
        self.assertEqual(row["sample_weight"], 0.35)
        self.assertEqual(row["transcript_text"], "This is the confirmation transcript window.")
        self.assertEqual(
            row["audio_path"],
            "knowledge/ttfm_video_corpus/audio_clips/fractal_model_fundamentals/confirmation_00100000.wav",
        )
        self.assertTrue(row["eligible_for_training"])
        self.assertEqual(row["training_blockers"], [])
        self.assertEqual(row["transcript_source"], "aligned_youtube_transcript")
        self.assertEqual(row["corpus_partition"], "trade_review")
        self.assertEqual(row["review_categories"], ["trade_review"])
        self.assertEqual(row["clip_duration_seconds"], 6.0)
        self.assertEqual(report["summary"]["row_count"], 1)
        self.assertEqual(report["summary"]["skipped_missing_window_count"], 1)
        self.assertEqual(report["summary"]["ready_for_weak_training_count"], 1)
        self.assertEqual(report["summary"]["eligible_for_training_count"], 1)


if __name__ == "__main__":
    unittest.main()
