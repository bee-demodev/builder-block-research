from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import export_ttfm_blended_visual_dataset as etbvd


def make_teacher_rows() -> list[dict]:
    return [
        {
            "example_id": "teacher::context",
            "case_ref": "teacher_case",
            "checkpoint": "context",
            "active_labels": ["equilibrium"],
            "screenshot_path": "artifacts/teacher/context.png",
        }
    ]


def make_weak_rows() -> list[dict]:
    return [
        {
            "example_id": "weak::closure",
            "case_ref": "weak_case",
            "checkpoint": "closure",
            "active_labels": ["candle_2_closure"],
            "screenshot_path": "knowledge/ttfm_video_corpus/frames/weak/closure.jpg",
            "weak_label_confidence": 0.35,
            "review_status": "ready_for_weak_training",
            "contradiction_status": "unreviewed",
        }
    ]


class BuildBlendedVisualDatasetTests(unittest.TestCase):
    def test_build_blended_visual_dataset_rows_assigns_source_tiers_and_weights(self) -> None:
        rows = etbvd.build_blended_visual_dataset_rows(
            teacher_rows=make_teacher_rows(),
            weak_rows=make_weak_rows(),
        )

        self.assertEqual(len(rows), 2)
        teacher_row = rows[0]
        weak_row = rows[1]
        self.assertEqual(teacher_row["source_tier"], "teacher")
        self.assertEqual(teacher_row["sample_weight"], 1.0)
        self.assertEqual(weak_row["source_tier"], "weak")
        self.assertEqual(weak_row["sample_weight"], 0.35)
        self.assertEqual(weak_row["review_status"], "ready_for_weak_training")
        self.assertEqual(weak_row["contradiction_status"], "unreviewed")

    def test_build_blended_visual_dataset_report_summarizes_sources(self) -> None:
        rows, report = etbvd.build_blended_visual_dataset_report(
            teacher_rows=make_teacher_rows(),
            weak_rows=make_weak_rows(),
        )

        self.assertEqual(len(rows), 2)
        self.assertEqual(report["summary"]["row_count"], 2)
        self.assertEqual(report["summary"]["source_tier_counts"]["teacher"], 1)
        self.assertEqual(report["summary"]["source_tier_counts"]["weak"], 1)
        self.assertEqual(report["summary"]["teacher_row_count"], 1)
        self.assertEqual(report["summary"]["weak_row_count"], 1)
        self.assertEqual(report["summary"]["ready_for_weak_training_count"], 1)
        self.assertEqual(report["summary"]["excluded_weak_row_count"], 0)
        self.assertEqual(report["summary"]["deduped_overlap_count"], 0)

    def test_build_blended_visual_dataset_filters_ineligible_weak_rows(self) -> None:
        weak_rows = make_weak_rows() + [
            {
                "example_id": "weak::synthetic",
                "case_ref": "weak_case",
                "checkpoint": "context",
                "active_labels": ["equilibrium"],
                "screenshot_path": "knowledge/ttfm_video_corpus/frames/weak/context.jpg",
                "weak_label_confidence": 0.35,
                "eligible_for_training": False,
                "review_status": "needs_teacher_review",
                "contradiction_status": "unreviewed",
                "training_blockers": ["synthetic_transcript"],
                "transcript_source": "synthetic_from_video_metadata",
            }
        ]

        rows, report = etbvd.build_blended_visual_dataset_report(
            teacher_rows=make_teacher_rows(),
            weak_rows=weak_rows,
        )

        self.assertEqual(len(rows), 2)
        self.assertEqual(report["summary"]["weak_row_count"], 1)
        self.assertEqual(report["summary"]["excluded_weak_row_count"], 1)
        self.assertNotIn("weak::synthetic", {row["example_id"] for row in rows})

    def test_build_blended_visual_dataset_dedupes_teacher_overlap(self) -> None:
        weak_rows = [
            {
                "example_id": "teacher::context",
                "case_ref": "teacher_case",
                "checkpoint": "context",
                "active_labels": ["equilibrium"],
                "screenshot_path": "knowledge/ttfm_video_corpus/frames/teacher/context.jpg",
                "weak_label_confidence": 0.35,
                "eligible_for_training": True,
                "review_status": "ready_for_weak_training",
                "contradiction_status": "unreviewed",
                "training_blockers": [],
                "transcript_source": "aligned_youtube_transcript",
            }
        ]

        rows, report = etbvd.build_blended_visual_dataset_report(
            teacher_rows=make_teacher_rows(),
            weak_rows=weak_rows,
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(report["summary"]["weak_row_count"], 0)
        self.assertEqual(report["summary"]["excluded_weak_row_count"], 0)
        self.assertEqual(report["summary"]["deduped_overlap_count"], 1)


if __name__ == "__main__":
    unittest.main()
