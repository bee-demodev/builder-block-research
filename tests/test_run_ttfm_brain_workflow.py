from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import run_ttfm_brain_workflow as rtbw


class RunTtfmBrainWorkflowTests(unittest.TestCase):
    def test_build_workflow_report_computes_deltas_and_benchmark_summary(self) -> None:
        report = rtbw.build_workflow_report(
            prior_history_entry={
                "corpus": {"current_video_count": 15},
                "frozen_benchmark": {
                    "challenger": {
                        "micro_f1": 0.45,
                        "precision": 0.31,
                        "recall": 0.80,
                        "exact_match_ratio": 0.19,
                        "disagreement_count": 8,
                    }
                },
            },
            intake_report={
                "summary": {
                    "video_file_count": 3,
                    "image_file_count": 2,
                    "trainable_video_count": 2,
                    "queued_video_count": 1,
                    "trainable_image_count": 1,
                    "review_only_image_count": 1,
                }
            },
            corpus_refresh_report={
                "active_manifest": {
                    "video_count": 21,
                    "partition_counts": {
                        "seed_curriculum": 6,
                        "trade_review": 9,
                        "educational_youtube": 5,
                        "daily_intake_video": 1,
                    },
                    "discovery_source_counts": {
                        "seed_curriculum": 6,
                        "youtube_channel_inventory": 14,
                        "daily_local_intake": 1,
                    },
                }
            },
            text_embedding_stage={
                "status": "cache_hit",
                "counts": {"item_count": 240},
            },
            visual_embedding_stage={
                "status": "ran",
                "counts": {"item_count": 105},
            },
            multimodal_loop_report={
                "weak_multimodal_dataset": {"row_count": 82, "eligible_for_training_count": 61},
                "blended_multimodal_dataset": {"row_count": 132, "excluded_weak_row_count": 21},
                "multimodal_model": {"validation_micro_f1": 0.55},
            },
            review_queue={
                "summary": {"model_disagreement_count": 6},
                "items": [
                    {
                        "example_id": "review_case::confirmation",
                        "screenshot_path": "results/frame.jpg",
                        "audio_path": "results/audio.wav",
                        "weak_active_labels": ["order_block"],
                        "predicted_labels": ["liquidity_sweep"],
                        "top_predicted_labels": [{"label": "liquidity_sweep", "probability": 0.82}],
                    }
                ],
            },
            benchmark_build_report={"status": "cache_hit", "row_count": 34},
            champion_evaluation={
                "micro_f1": 0.45,
                "precision": 0.31,
                "recall": 0.80,
                "exact_match_ratio": 0.19,
                "disagreement_count": 8,
            },
            challenger_evaluation={
                "micro_f1": 0.55,
                "precision": 0.39,
                "recall": 0.93,
                "exact_match_ratio": 0.22,
                "disagreement_count": 6,
            },
            dense_review_report={"sample_count": 25, "sampled_case_count": 5},
            stages=[
                {"name": "text_embeddings", "status": "cache_hit"},
                {"name": "visual_embeddings", "status": "ran"},
            ],
            outputs={
                "dashboard": "results/ttfm_brain_dashboard.html",
                "snapshot": "results/ttfm_progress_snapshot.md",
            },
        )

        self.assertEqual(report["corpus"]["current_video_count"], 21)
        self.assertEqual(report["corpus"]["delta_video_count"], 6)
        self.assertEqual(report["daily_intake"]["trainable_video_count"], 2)
        self.assertEqual(report["trainability"]["trainable_row_count"], 61)
        self.assertEqual(report["frozen_benchmark"]["benchmark_row_count"], 34)
        self.assertEqual(report["frozen_benchmark"]["comparison"]["winner"], "challenger")
        self.assertAlmostEqual(report["frozen_benchmark"]["comparison"]["delta"]["micro_f1"], 0.10, places=6)
        self.assertEqual(len(report["top_disagreement_cases"]), 1)
        self.assertEqual(report["stages"][0]["status"], "cache_hit")
