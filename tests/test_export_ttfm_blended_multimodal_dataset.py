from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import export_ttfm_blended_multimodal_dataset as etbmd


def make_teacher_rows() -> list[dict]:
    return [
        {
            "example_id": "teacher::context",
            "case_ref": "teacher_case",
            "checkpoint": "context",
            "active_labels": ["equilibrium"],
            "screenshot_path": "artifacts/teacher/context.png",
        },
        {
            "example_id": "shared::confirmation",
            "case_ref": "shared_case",
            "checkpoint": "confirmation",
            "active_labels": ["order_block"],
            "screenshot_path": "artifacts/teacher/confirmation.png",
            "sample_weight": 1.0,
        },
    ]


def make_multimodal_rows() -> list[dict]:
    return [
        {
            "example_id": "shared::confirmation",
            "case_ref": "shared_case",
            "checkpoint": "confirmation",
            "active_labels": ["order_block"],
            "screenshot_path": "knowledge/ttfm_video_corpus/frames/shared/confirmation.jpg",
            "audio_path": "knowledge/ttfm_video_corpus/audio_clips/shared/confirmation.wav",
            "video_path": "knowledge/ttfm_video_corpus/videos/shared.mp4",
            "transcript_text": "Order block confirmation transcript",
            "embedding_text": "Order block confirmation embedding",
            "clip_duration_seconds": 6.0,
            "sample_weight": 0.35,
            "eligible_for_training": True,
            "review_status": "ready_for_weak_training",
            "contradiction_status": "unreviewed",
            "training_blockers": [],
            "transcript_source": "aligned_youtube_transcript",
        },
        {
            "example_id": "weak::sweep",
            "case_ref": "weak_case",
            "checkpoint": "sweep",
            "active_labels": ["liquidity_sweep"],
            "screenshot_path": "knowledge/ttfm_video_corpus/frames/weak/sweep.jpg",
            "audio_path": "knowledge/ttfm_video_corpus/audio_clips/weak/sweep.wav",
            "video_path": "knowledge/ttfm_video_corpus/videos/weak.mp4",
            "transcript_text": "Sweep transcript",
            "embedding_text": "Sweep embedding",
            "clip_duration_seconds": 6.0,
            "sample_weight": 0.35,
            "eligible_for_training": True,
            "review_status": "ready_for_weak_training",
            "contradiction_status": "unreviewed",
            "training_blockers": [],
            "transcript_source": "aligned_youtube_transcript",
        },
    ]


class BuildBlendedMultimodalDatasetTests(unittest.TestCase):
    def test_build_blended_multimodal_dataset_merges_teacher_with_matching_multimodal_rows(self) -> None:
        rows = etbmd.build_blended_multimodal_dataset_rows(
            teacher_rows=make_teacher_rows(),
            multimodal_rows=make_multimodal_rows(),
        )

        self.assertEqual(len(rows), 3)
        by_example_id = {row["example_id"]: row for row in rows}

        teacher_only = by_example_id["teacher::context"]
        merged_teacher = by_example_id["shared::confirmation"]
        weak_only = by_example_id["weak::sweep"]

        self.assertEqual(teacher_only["source_tier"], "teacher")
        self.assertEqual(teacher_only["sample_weight"], 1.0)
        self.assertIsNone(teacher_only["audio_path"])
        self.assertEqual(teacher_only["transcript_text"], "")

        self.assertEqual(merged_teacher["source_tier"], "teacher")
        self.assertEqual(merged_teacher["sample_weight"], 1.0)
        self.assertEqual(
            merged_teacher["audio_path"],
            "knowledge/ttfm_video_corpus/audio_clips/shared/confirmation.wav",
        )
        self.assertEqual(
            merged_teacher["transcript_text"],
            "Order block confirmation transcript",
        )

        self.assertEqual(weak_only["source_tier"], "weak")
        self.assertEqual(weak_only["sample_weight"], 0.35)
        self.assertEqual(weak_only["review_status"], "ready_for_weak_training")

    def test_build_blended_multimodal_dataset_report_summarizes_modalities_and_dedupes(self) -> None:
        rows, report = etbmd.build_blended_multimodal_dataset_report(
            teacher_rows=make_teacher_rows(),
            multimodal_rows=make_multimodal_rows(),
        )

        self.assertEqual(len(rows), 3)
        self.assertEqual(report["summary"]["row_count"], 3)
        self.assertEqual(report["summary"]["teacher_row_count"], 2)
        self.assertEqual(report["summary"]["weak_row_count"], 1)
        self.assertEqual(report["summary"]["audio_enabled_row_count"], 2)
        self.assertEqual(report["summary"]["text_enabled_row_count"], 2)
        self.assertEqual(report["summary"]["deduped_overlap_count"], 1)
        self.assertEqual(report["summary"]["excluded_weak_row_count"], 0)

    def test_build_blended_multimodal_dataset_filters_ineligible_weak_rows(self) -> None:
        multimodal_rows = make_multimodal_rows() + [
            {
                "example_id": "weak::synthetic",
                "case_ref": "weak_case",
                "checkpoint": "context",
                "active_labels": ["equilibrium"],
                "screenshot_path": "knowledge/ttfm_video_corpus/frames/weak/context.jpg",
                "audio_path": "knowledge/ttfm_video_corpus/audio_clips/weak/context.wav",
                "video_path": "knowledge/ttfm_video_corpus/videos/weak.mp4",
                "transcript_text": "Synthetic transcript",
                "embedding_text": "Synthetic embedding",
                "clip_duration_seconds": 6.0,
                "sample_weight": 0.35,
                "eligible_for_training": False,
                "review_status": "needs_teacher_review",
                "contradiction_status": "unreviewed",
                "training_blockers": ["synthetic_transcript"],
                "transcript_source": "synthetic_from_video_metadata",
            }
        ]

        rows, report = etbmd.build_blended_multimodal_dataset_report(
            teacher_rows=make_teacher_rows(),
            multimodal_rows=multimodal_rows,
        )

        self.assertEqual(len(rows), 3)
        self.assertEqual(report["summary"]["weak_row_count"], 1)
        self.assertEqual(report["summary"]["excluded_weak_row_count"], 1)
        self.assertNotIn("weak::synthetic", {row["example_id"] for row in rows})

    def test_build_blended_multimodal_dataset_does_not_merge_ineligible_overlap(self) -> None:
        multimodal_rows = [
            {
                "example_id": "shared::confirmation",
                "case_ref": "shared_case",
                "checkpoint": "confirmation",
                "active_labels": ["order_block"],
                "screenshot_path": "knowledge/ttfm_video_corpus/frames/shared/confirmation.jpg",
                "audio_path": "knowledge/ttfm_video_corpus/audio_clips/shared/confirmation.wav",
                "video_path": "knowledge/ttfm_video_corpus/videos/shared.mp4",
                "transcript_text": "Synthetic transcript",
                "embedding_text": "Synthetic embedding",
                "clip_duration_seconds": 6.0,
                "sample_weight": 0.35,
                "eligible_for_training": False,
                "review_status": "needs_teacher_review",
                "contradiction_status": "unreviewed",
                "training_blockers": ["synthetic_transcript"],
                "transcript_source": "synthetic_from_video_metadata",
            }
        ]

        rows, report = etbmd.build_blended_multimodal_dataset_report(
            teacher_rows=make_teacher_rows(),
            multimodal_rows=multimodal_rows,
        )

        by_example_id = {row["example_id"]: row for row in rows}
        merged_teacher = by_example_id["shared::confirmation"]

        self.assertIsNone(merged_teacher["audio_path"])
        self.assertEqual(merged_teacher["transcript_text"], "")
        self.assertEqual(report["summary"]["excluded_weak_row_count"], 1)
        self.assertEqual(report["summary"]["deduped_overlap_count"], 0)


if __name__ == "__main__":
    unittest.main()
