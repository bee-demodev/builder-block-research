from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import build_ttfm_video_visual_windows as btvvw


def make_video_manifest() -> dict:
    return {
        "video_count": 1,
        "videos": [
            {
                "slug": "fractal_model_fundamentals",
                "title": "Fractal Model Fundamentals",
                "video_id": "TNybDCtwBnc",
                "url": "https://youtu.be/TNybDCtwBnc",
                "source_page": "https://ttrades.com/fractal-model-playbook-aligning-daily-hourly-and-5-minute-charts/",
                "transcript_source": "aligned_youtube_transcript",
                "topics": ["daily_bias", "equilibrium", "cisd", "continuation"],
            }
        ],
    }


def make_chunk_rows() -> list[dict]:
    return [
        {
            "video_slug": "fractal_model_fundamentals",
            "video_id": "TNybDCtwBnc",
            "title": "Fractal Model Fundamentals",
            "topics": ["daily_bias", "equilibrium", "cisd", "continuation"],
            "start": 0.0,
            "end": 24.0,
            "text": "Daily bias and equilibrium on the higher timeframe create the context framework.",
        },
        {
            "video_slug": "fractal_model_fundamentals",
            "video_id": "TNybDCtwBnc",
            "title": "Fractal Model Fundamentals",
            "topics": ["daily_bias", "equilibrium", "cisd", "continuation"],
            "start": 24.0,
            "end": 48.0,
            "text": "Price runs the highs and performs a liquidity sweep before continuation.",
        },
        {
            "video_slug": "fractal_model_fundamentals",
            "video_id": "TNybDCtwBnc",
            "title": "Fractal Model Fundamentals",
            "topics": ["daily_bias", "equilibrium", "cisd", "continuation"],
            "start": 48.0,
            "end": 72.0,
            "text": "The candle 2 closure and CISD confirm the change in state.",
        },
        {
            "video_slug": "fractal_model_fundamentals",
            "video_id": "TNybDCtwBnc",
            "title": "Fractal Model Fundamentals",
            "topics": ["daily_bias", "equilibrium", "cisd", "continuation"],
            "start": 72.0,
            "end": 96.0,
            "text": "The entry returns to the order block and fair value gap with a protected swing.",
        },
        {
            "video_slug": "fractal_model_fundamentals",
            "video_id": "TNybDCtwBnc",
            "title": "Fractal Model Fundamentals",
            "topics": ["daily_bias", "equilibrium", "cisd", "continuation"],
            "start": 96.0,
            "end": 120.0,
            "text": "The target expands and the invalidation stays below the structure.",
        },
    ]


def make_taxonomy() -> dict:
    return {
        "components": [
            {
                "label": "equilibrium",
                "markers": ["equilibrium"],
                "checkpoints": ["context", "confirmation"],
                "supporting_topics": ["equilibrium"],
            },
            {
                "label": "liquidity_sweep",
                "markers": ["liquidity sweep", "sweep"],
                "checkpoints": ["sweep", "confirmation"],
                "supporting_topics": ["continuation"],
            },
            {
                "label": "candle_2_closure",
                "markers": ["candle 2", "cisd"],
                "checkpoints": ["closure", "confirmation"],
                "supporting_topics": ["cisd"],
            },
            {
                "label": "order_block",
                "markers": ["order block"],
                "checkpoints": ["confirmation"],
                "supporting_topics": ["continuation"],
            },
            {
                "label": "fair_value_gap",
                "markers": ["fair value gap"],
                "checkpoints": ["confirmation"],
                "supporting_topics": ["continuation"],
            },
            {
                "label": "invalidation",
                "markers": ["invalidation"],
                "checkpoints": ["confirmation", "outcome"],
                "supporting_topics": ["continuation"],
            },
        ]
    }


class BuildVisualWindowsDatasetTests(unittest.TestCase):
    def test_build_visual_windows_dataset_selects_checkpoint_specific_chunks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            rows, report = btvvw.build_visual_windows_dataset(
                make_video_manifest(),
                make_chunk_rows(),
                taxonomy=make_taxonomy(),
                video_dir=Path(temp_dir) / "videos",
                frame_dir=Path(temp_dir) / "frames",
                extract_frames=False,
                ffmpeg_bin="ffmpeg",
            )

        self.assertEqual(len(rows), 5)
        self.assertEqual(report["summary"]["window_count"], 5)
        self.assertEqual(
            {row["checkpoint"] for row in rows},
            {"context", "sweep", "closure", "confirmation", "outcome"},
        )
        self.assertEqual(report["summary"]["frame_status_counts"]["missing_video"], 5)

        rows_by_checkpoint = {row["checkpoint"]: row for row in rows}
        self.assertIn("equilibrium", rows_by_checkpoint["context"]["candidate_labels"])
        self.assertIn("liquidity_sweep", rows_by_checkpoint["sweep"]["candidate_labels"])
        self.assertIn("candle_2_closure", rows_by_checkpoint["closure"]["candidate_labels"])
        self.assertIn("order_block", rows_by_checkpoint["confirmation"]["candidate_labels"])
        self.assertIn("invalidation", rows_by_checkpoint["outcome"]["candidate_labels"])
        self.assertEqual(rows_by_checkpoint["context"]["transcript_source"], "aligned_youtube_transcript")
        self.assertIn("Checkpoint: confirmation", rows_by_checkpoint["confirmation"]["embedding_text"])

    def test_build_visual_windows_dataset_falls_back_when_no_checkpoint_cues_exist(self) -> None:
        generic_rows = [
            {
                "video_slug": "fractal_model_fundamentals",
                "video_id": "TNybDCtwBnc",
                "title": "Fractal Model Fundamentals",
                "topics": ["daily_bias"],
                "start": float(index * 30),
                "end": float((index + 1) * 30),
                "text": f"Generic educational narration section {index}.",
            }
            for index in range(5)
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            rows, report = btvvw.build_visual_windows_dataset(
                make_video_manifest(),
                generic_rows,
                taxonomy={"components": []},
                video_dir=Path(temp_dir) / "videos",
                frame_dir=Path(temp_dir) / "frames",
                extract_frames=False,
                ffmpeg_bin="ffmpeg",
            )

        self.assertEqual(len(rows), 5)
        self.assertEqual(report["summary"]["checkpoint_counts"]["context"], 1)
        self.assertEqual(len({row["source_chunk_id"] for row in rows}), 5)


if __name__ == "__main__":
    unittest.main()
