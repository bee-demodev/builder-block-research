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

import build_ttfm_daily_intake as btdi


class BuildTtfmDailyIntakeTests(unittest.TestCase):
    def test_build_video_manifest_row_marks_transcript_backed_assets_trainable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            video_path = Path(temp_dir) / "bias_review.mp4"
            video_path.write_bytes(b"video")
            video_path.with_suffix(".json").write_text(
                json.dumps(
                    {
                        "title": "Bias Review",
                        "transcript_text": "Teacher explains the daily bias and alignment.",
                        "topics": ["daily_bias"],
                    }
                ),
                encoding="utf-8",
            )

            row = btdi.build_video_manifest_row(video_path)

        self.assertEqual(row["title"], "Bias Review")
        self.assertEqual(row["intake_status"], "trainable_after_refresh")
        self.assertEqual(row["topics"], ["daily_bias"])
        self.assertTrue(str(row["local_video_path"]).endswith("bias_review.mp4"))

    def test_build_image_case_row_routes_unlabeled_assets_to_review_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "case.png"
            image_path.write_bytes(b"png")
            image_path.with_suffix(".json").write_text(
                json.dumps(
                    {
                        "title": "Case Study",
                        "notes": "Possible confirmation frame for later review.",
                    }
                ),
                encoding="utf-8",
            )

            row = btdi.build_image_case_row(image_path)

        self.assertFalse(row["eligible_for_training"])
        self.assertEqual(row["review_status"], "review_only")
        self.assertIn("missing_active_labels", row["training_blockers"])
        self.assertEqual(row["transcript_source"], "daily_intake_image_metadata")

    def test_scan_daily_intake_exports_video_and_image_reports(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir)
            videos_dir = base_dir / "videos"
            images_dir = base_dir / "images"
            videos_dir.mkdir(parents=True, exist_ok=True)
            images_dir.mkdir(parents=True, exist_ok=True)

            video_path = videos_dir / "alignment.mp4"
            video_path.write_bytes(b"video")
            video_path.with_suffix(".json").write_text(
                json.dumps({"transcript_text": "Higher timeframe alignment."}),
                encoding="utf-8",
            )

            image_path = images_dir / "confirmation.png"
            image_path.write_bytes(b"image")
            image_path.with_suffix(".json").write_text(
                json.dumps(
                    {
                        "active_labels": ["order_block"],
                        "notes": "Reviewed chart evidence.",
                        "review_status": "ready_for_weak_training",
                    }
                ),
                encoding="utf-8",
            )

            video_manifest_output = base_dir / "daily_videos.json"
            image_cases_output = base_dir / "daily_images.jsonl"
            report_output = base_dir / "daily_report.json"

            report = btdi.scan_daily_intake(
                intake_videos_dir=videos_dir,
                intake_images_dir=images_dir,
                video_manifest_output=video_manifest_output,
                image_cases_output=image_cases_output,
                report_output=report_output,
            )

            manifest = json.loads(video_manifest_output.read_text(encoding="utf-8"))
            image_rows = [json.loads(line) for line in image_cases_output.read_text(encoding="utf-8").splitlines() if line]

        self.assertEqual(manifest["video_count"], 1)
        self.assertEqual(report["summary"]["trainable_video_count"], 1)
        self.assertEqual(report["summary"]["trainable_image_count"], 1)
        self.assertEqual(len(image_rows), 1)
        self.assertTrue(image_rows[0]["eligible_for_training"])
