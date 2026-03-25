from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import export_ttfm_brain_dashboard as etbd


class ExportTtfmBrainDashboardTests(unittest.TestCase):
    def test_build_dashboard_html_contains_required_sections(self) -> None:
        report = {
            "generated_at": "2026-03-24T00:00:00Z",
            "corpus": {
                "current_video_count": 21,
                "delta_video_count": 6,
                "partition_counts": {"seed_curriculum": 6, "trade_review": 9},
            },
            "daily_intake": {
                "video_file_count": 3,
                "image_file_count": 2,
                "trainable_video_count": 2,
                "queued_video_count": 1,
                "trainable_image_count": 1,
                "review_only_image_count": 1,
            },
            "embeddings": {
                "text": {"status": "cache_hit", "item_count": 240},
                "visual": {"status": "ran", "item_count": 105},
            },
            "trainability": {
                "trainable_row_count": 61,
                "blocked_row_count": 21,
            },
            "frozen_benchmark": {
                "benchmark_row_count": 34,
                "comparison": {
                    "winner": "challenger",
                    "delta": {"micro_f1": 0.10, "precision": 0.08, "recall": 0.13, "exact_match_ratio": 0.03, "disagreement_count": -2},
                },
                "champion": {"micro_f1": 0.45, "precision": 0.31, "recall": 0.80, "exact_match_ratio": 0.19, "disagreement_count": 8},
                "challenger": {"micro_f1": 0.55, "precision": 0.39, "recall": 0.93, "exact_match_ratio": 0.22, "disagreement_count": 6},
            },
            "top_disagreement_cases": [
                {
                    "example_id": "review_case::confirmation",
                    "screenshot_path": "results/frame.jpg",
                    "audio_path": "results/audio.wav",
                    "weak_active_labels": ["order_block"],
                    "predicted_labels": ["liquidity_sweep"],
                    "top_predicted_labels": [{"label": "liquidity_sweep", "probability": 0.82}],
                }
            ],
            "stages": [
                {"name": "text_embeddings", "status": "cache_hit"},
                {"name": "visual_embeddings", "status": "ran"},
            ],
        }

        html = etbd.build_dashboard_html(report, history_entries=[{"generated_at": "2026-03-23T00:00:00Z"}])

        self.assertIn("Corpus Size and Deltas", html)
        self.assertIn("Embedding Counts and Cache Behavior", html)
        self.assertIn("Trainable vs Blocked Rows", html)
        self.assertIn("Frozen Benchmark Results", html)
        self.assertIn("Top Disagreement Cases", html)
        self.assertIn("Daily Intake Summary", html)
        self.assertIn("review_case::confirmation", html)
        self.assertIn("results/frame.jpg", html)
