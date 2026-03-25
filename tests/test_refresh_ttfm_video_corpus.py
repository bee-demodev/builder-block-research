from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import refresh_ttfm_video_corpus as rtvc


class RefreshTtfmVideoCorpusTests(unittest.TestCase):
    def test_merge_video_manifests_dedupes_by_video_id(self) -> None:
        merged = rtvc.merge_video_manifests(
            {"videos": [{"video_id": "seed1", "slug": "seed"}]},
            {"videos": [{"video_id": "seed1", "slug": "duplicate"}, {"video_id": "review1", "slug": "review"}]},
        )

        self.assertEqual(merged["video_count"], 2)
        self.assertEqual([video["slug"] for video in merged["videos"]], ["seed", "review"])

    def test_merge_video_manifests_dedupes_local_intake_assets_by_path(self) -> None:
        merged = rtvc.merge_video_manifests(
            {"videos": [{"slug": "seed", "local_video_path": "intake/videos/seed.mp4"}]},
            {"videos": [{"slug": "duplicate", "local_video_path": "intake/videos/seed.mp4"}]},
        )

        self.assertEqual(merged["video_count"], 1)
        self.assertEqual(merged["videos"][0]["slug"], "seed")

    def test_refresh_corpus_writes_report_with_educational_and_intake_counts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir)
            corpus_dir = base_dir / "knowledge" / "ttfm_video_corpus"
            results_dir = base_dir / "results"
            chunks_path = corpus_dir / "chunks.jsonl"
            chunks_path.parent.mkdir(parents=True, exist_ok=True)
            chunks_path.write_text('{"video_slug":"seed_video","video_id":"seed1","title":"Seed","start":0,"end":10,"text":"seed"}\n', encoding="utf-8")
            intake_manifest_path = corpus_dir / "daily_intake_video_manifest.json"
            intake_manifest_path.write_text(
                json.dumps(
                    {
                        "video_count": 1,
                        "videos": [
                            {
                                "slug": "local_bias",
                                "video_id": "local_local_bias",
                                "corpus_partition": "daily_intake_video",
                                "discovery_source": "daily_local_intake",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with (
                patch.object(rtvc.dtrv, "fetch_channel_inventory", return_value={"title": "TTrades - Videos", "entries": []}),
                patch.object(
                    rtvc.dtrv,
                    "build_channel_corpus_manifests",
                    return_value=(
                        {
                            "entry_count": 5,
                            "educational_candidate_count": 4,
                            "trade_review_candidate_count": 2,
                            "category_counts": {"chart_lesson": 1, "trade_review": 1},
                            "educational_category_counts": {"bias_framework": 1, "timeframe_alignment": 1},
                            "selected_partition_counts": {"educational_youtube": 2, "trade_review": 2},
                        },
                        {
                            "video_count": 4,
                            "videos": [
                                {"video_id": "edu1", "slug": "daily_bias", "corpus_partition": "educational_youtube"},
                                {"video_id": "edu2", "slug": "cisd", "corpus_partition": "educational_youtube"},
                                {"video_id": "review1", "slug": "review_one", "corpus_partition": "trade_review"},
                                {"video_id": "review2", "slug": "review_two", "corpus_partition": "trade_review"},
                            ],
                        },
                        {
                            "video_count": 2,
                            "videos": [
                                {"video_id": "review1", "slug": "review_one", "corpus_partition": "trade_review"},
                                {"video_id": "review2", "slug": "review_two", "corpus_partition": "trade_review"},
                            ],
                        },
                    ),
                ),
                patch.object(
                    rtvc.btvc,
                    "build_corpus",
                    return_value={
                        "video_count": 3,
                        "transcript_fetch_count": 1,
                        "transcript_reuse_count": 2,
                    },
                ),
                patch.object(rtvc.dtyv, "download_videos", return_value={"summary": {"video_count": 3, "status_counts": {"downloaded": 1}}}),
                patch.object(rtvc.btvw, "load_jsonl", return_value=[{"chunk_id": "seed_video:0000"}]),
                patch.object(rtvc.btvw, "load_component_taxonomy", return_value={}),
                patch.object(
                    rtvc.btvw,
                    "build_visual_windows_dataset",
                    return_value=(
                        [{"example_id": "review_case::context", "video_slug": "review_one"}],
                        {"summary": {"window_count": 1, "video_count": 1, "frame_status_counts": {"extracted": 1}}},
                    ),
                ),
                patch.object(
                    rtvc.etvwvd,
                    "build_video_weak_visual_dataset_report",
                    return_value=(
                        [{"example_id": "review_case::context", "video_slug": "review_one"}],
                        {"summary": {"row_count": 1, "video_count": 1}},
                    ),
                ),
                patch.object(rtvc.vtvc, "validate_corpus", return_value={"ok": True, "video_count": 3, "chunk_count": 1}),
            ):
                report = rtvc.refresh_corpus(
                    channel_url=rtvc.dtrv.DEFAULT_CHANNEL_URL,
                    yt_dlp_bin="yt-dlp",
                    include_review_categories={"trade_review", "chart_lesson"},
                    include_educational_categories={"bias_framework", "timeframe_alignment"},
                    output_dir=corpus_dir,
                    inventory_output=corpus_dir / "channel_inventory.json",
                    trade_review_manifest_output=corpus_dir / "trade_review_video_manifest.json",
                    educational_manifest_output=corpus_dir / "educational_video_manifest.json",
                    active_manifest_output=corpus_dir / "video_manifest.json",
                    intake_video_manifest_path=intake_manifest_path,
                    video_dir=corpus_dir / "videos",
                    video_download_report_output=corpus_dir / "video_download_report.json",
                    windows_output=corpus_dir / "visual_windows.jsonl",
                    windows_report_output=corpus_dir / "visual_windows_report.json",
                    weak_dataset_output=results_dir / "ttfm_video_weak_visual_dataset.jsonl",
                    weak_dataset_report_output=results_dir / "ttfm_video_weak_visual_dataset_report.json",
                    report_output=corpus_dir / "corpus_refresh_report.json",
                    ffmpeg_bin="ffmpeg",
                    extract_frames=True,
                    overwrite_transcripts=False,
                    overwrite_videos=False,
                )

            self.assertEqual(report["channel_inventory"]["educational_candidate_count"], 4)
            self.assertEqual(report["channel_inventory"]["trade_review_candidate_count"], 2)
            self.assertEqual(report["trade_review_manifest"]["video_count"], 2)
            self.assertEqual(report["educational_manifest"]["video_count"], 4)
            self.assertEqual(report["daily_intake_video_manifest"]["video_count"], 1)
            self.assertEqual(report["active_manifest"]["video_count"], 11)
            self.assertEqual(report["active_manifest"]["partition_counts"]["educational_youtube"], 2)
            self.assertEqual(report["active_manifest"]["partition_counts"]["trade_review"], 2)
            self.assertEqual(report["active_manifest"]["partition_counts"]["daily_intake_video"], 1)
            saved = json.loads((corpus_dir / "corpus_refresh_report.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["weak_visual_dataset"]["row_count"], 1)


if __name__ == "__main__":
    unittest.main()
