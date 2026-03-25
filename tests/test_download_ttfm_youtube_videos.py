from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import download_ttfm_youtube_videos as dtyv


def make_video_manifest() -> dict:
    return {
        "videos": [
            {
                "slug": "fractal_model_fundamentals",
                "video_id": "TNybDCtwBnc",
                "url": "https://youtu.be/TNybDCtwBnc",
            }
        ]
    }


class DownloadTtfmYoutubeVideosTests(unittest.TestCase):
    def test_build_download_command_uses_slug_output_template(self) -> None:
        command = dtyv.build_download_command(
            yt_dlp_bin="yt-dlp",
            url="https://youtu.be/TNybDCtwBnc",
            output_template=Path("videos/fractal_model_fundamentals.%(ext)s"),
        )

        self.assertEqual(command[0], "yt-dlp")
        self.assertIn("--js-runtimes", command)
        self.assertIn("node", command)
        self.assertIn(dtyv.DEFAULT_FORMAT_SELECTOR, command)
        self.assertEqual(command[-1], "https://youtu.be/TNybDCtwBnc")
        self.assertIn(
            "videos/fractal_model_fundamentals.%(ext)s",
            [Path(value).as_posix() for value in command],
        )

    def test_download_videos_skips_existing_video_when_overwrite_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            video_dir = Path(temp_dir)
            existing_path = video_dir / "fractal_model_fundamentals.mp4"
            existing_path.write_bytes(b"fake-video")

            report = dtyv.download_videos(
                make_video_manifest(),
                video_dir=video_dir,
                yt_dlp_bin="yt-dlp",
                overwrite=False,
            )

        self.assertEqual(report["summary"]["status_counts"]["skipped_exists"], 1)
        self.assertEqual(report["videos"][0]["status"], "skipped_exists")
        self.assertTrue(report["videos"][0]["video_path"].endswith("fractal_model_fundamentals.mp4"))


if __name__ == "__main__":
    unittest.main()
