from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import export_ttfm_dense_review_samples as etdrs


class ExportTtfmDenseReviewSamplesTests(unittest.TestCase):
    def test_build_dense_review_samples_generates_stable_ids_for_each_offset(self) -> None:
        samples, report = etdrs.build_dense_review_samples(
            review_queue_items=[
                {
                    "example_id": "review_case::confirmation",
                    "case_ref": "review_case",
                    "video_slug": "review_video",
                    "title": "Review Video",
                    "checkpoint": "confirmation",
                    "weak_active_labels": ["order_block"],
                    "predicted_labels": ["liquidity_sweep"],
                    "top_predicted_labels": [{"label": "liquidity_sweep", "probability": 0.82}],
                    "priority_score": 97,
                    "prediction_status": "scored",
                }
            ],
            multimodal_rows=[
                {
                    "example_id": "review_case::confirmation",
                    "video_path": "knowledge/ttfm_video_corpus/videos/review_video.mp4",
                    "midpoint_seconds": 100.0,
                    "screenshot_path": "knowledge/ttfm_video_corpus/frames/review_video/confirmation.jpg",
                    "audio_path": "knowledge/ttfm_video_corpus/audio_clips/review_video/confirmation.wav",
                }
            ],
            offsets_seconds=(-12, -6, 0, 6, 12),
            frame_output_dir=Path("results/ttfm_dense_review/frames"),
            audio_output_dir=Path("results/ttfm_dense_review/audio"),
        )

        self.assertEqual(len(samples), 5)
        self.assertEqual(samples[0]["sample_id"], "review_case__confirmation__minus_12s")
        self.assertEqual(samples[2]["sample_id"], "review_case__confirmation__plus_0s")
        self.assertEqual(samples[-1]["sample_timestamp_seconds"], 112.0)
        self.assertEqual(report["sample_count"], 5)
        self.assertEqual(report["sampled_case_count"], 1)

    def test_build_dense_review_samples_skips_items_without_video_evidence(self) -> None:
        samples, report = etdrs.build_dense_review_samples(
            review_queue_items=[
                {
                    "example_id": "image_case::confirmation",
                    "case_ref": "image_case",
                    "checkpoint": "confirmation",
                }
            ],
            multimodal_rows=[
                {
                    "example_id": "image_case::confirmation",
                    "video_path": None,
                    "midpoint_seconds": None,
                }
            ],
            offsets_seconds=(-12, -6, 0, 6, 12),
            frame_output_dir=Path("results/ttfm_dense_review/frames"),
            audio_output_dir=Path("results/ttfm_dense_review/audio"),
        )

        self.assertEqual(samples, [])
        self.assertEqual(report["skipped_missing_video_count"], 1)
