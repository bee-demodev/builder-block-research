from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import subprocess


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import build_ttfm_video_corpus as btvc


class _BrokenTranscriptApi:
    def fetch(self, video_id: str, languages: list[str]) -> None:  # pragma: no cover - test double
        raise RuntimeError(f"transcript disabled for {video_id}")


class BuildTtfmVideoCorpusTests(unittest.TestCase):
    def test_default_video_manifest_tags_seed_rows_with_partition_metadata(self) -> None:
        manifest = btvc.default_video_manifest()

        self.assertEqual(manifest["manifest_source"], "seed_curriculum")
        self.assertTrue(all(video["corpus_partition"] == "seed_curriculum" for video in manifest["videos"]))
        self.assertTrue(all(video["discovery_source"] == "seed_curriculum" for video in manifest["videos"]))

    def test_fetch_video_duration_seconds_returns_fallback_when_yt_dlp_times_out(self) -> None:
        with patch.object(
            btvc.subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired(cmd=["yt-dlp"], timeout=15),
        ):
            duration = btvc.fetch_video_duration_seconds(
                {
                    "url": "https://youtu.be/example",
                    "allow_remote_duration_probe": True,
                }
            )

        self.assertEqual(duration, 300.0)

    def test_build_corpus_falls_back_to_synthetic_transcript_when_captions_are_unavailable(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            output_dir = Path(temp_dir) / "corpus"
            manifest = {
                "videos": [
                    {
                        "slug": "review_video",
                        "title": "MARA Trade Review",
                        "video_id": "abc123",
                        "url": "https://youtu.be/abc123",
                        "topics": ["trade_review", "mmxm"],
                        "corpus_partition": "trade_review",
                        "review_categories": ["trade_review"],
                    }
                ]
            }
            with patch.object(btvc, "fetch_video_duration_seconds", return_value=200.0):
                report = btvc.build_corpus(
                    output_dir,
                    video_manifest=manifest,
                    youtube_api_factory=_BrokenTranscriptApi,
                )

            self.assertEqual(report["synthetic_transcript_count"], 1)
            written_manifest = json.loads((output_dir / "video_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(written_manifest["videos"][0]["transcript_source"], "synthetic_from_video_metadata")
            chunk_rows = [
                json.loads(line)
                for line in (output_dir / "chunks.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(len(chunk_rows), len(btvc.FALLBACK_TRANSCRIPT_SEGMENTS))
            self.assertTrue(all(row["corpus_partition"] == "trade_review" for row in chunk_rows))


if __name__ == "__main__":
    unittest.main()
