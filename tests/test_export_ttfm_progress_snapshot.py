from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import export_ttfm_progress_snapshot as etps


class ExportTtfmProgressSnapshotTests(unittest.TestCase):
    def test_build_workflow_snapshot_renders_v2_operator_summary(self) -> None:
        report = {
            "generated_at": "2026-03-24T00:00:00Z",
            "corpus": {
                "current_video_count": 21,
                "delta_video_count": 6,
                "partition_counts": {"seed_curriculum": 6, "trade_review": 9, "educational_youtube": 5},
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
                "blocked_reason_counts": {"missing_context_notes": 8},
            },
            "frozen_benchmark": {
                "benchmark_row_count": 34,
                "comparison": {
                    "winner": "challenger",
                    "delta": {"micro_f1": 0.10, "precision": 0.08, "recall": 0.13, "exact_match_ratio": 0.03, "disagreement_count": -2},
                },
                "challenger": {"micro_f1": 0.55, "precision": 0.39, "recall": 0.93, "exact_match_ratio": 0.22, "disagreement_count": 6},
            },
            "top_disagreement_cases": [
                {
                    "example_id": "review_case::confirmation",
                    "screenshot_path": "results/frame.jpg",
                    "audio_path": "results/audio.wav",
                    "weak_active_labels": ["order_block"],
                    "predicted_labels": ["liquidity_sweep"],
                }
            ],
            "outputs": {
                "dashboard": "results/ttfm_brain_dashboard.html",
                "report": "results/ttfm_brain_workflow_report.json",
            },
        }

        snapshot = etps.build_workflow_snapshot(report)

        self.assertIn("TTFM Brain Workflow V2 Snapshot", snapshot)
        self.assertIn("Corpus Coverage", snapshot)
        self.assertIn("Frozen Benchmark", snapshot)
        self.assertIn("Daily Intake", snapshot)
        self.assertIn("review_case::confirmation", snapshot)
        self.assertIn("results/ttfm_brain_dashboard.html", snapshot)
