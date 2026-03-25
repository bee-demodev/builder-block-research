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

import evaluate_ttfm_frozen_benchmark as etfb


class EvaluateTtfmFrozenBenchmarkTests(unittest.TestCase):
    def test_build_frozen_benchmark_rows_merges_teacher_and_reviewed_disagreements(self) -> None:
        rows = etfb.build_frozen_benchmark_rows(
            teacher_rows=[
                {
                    "example_id": "teacher_case::confirmation",
                    "active_labels": ["order_block"],
                    "screenshot_path": "teacher.jpg",
                }
            ],
            weak_rows=[
                {
                    "example_id": "review_case::confirmation",
                    "active_labels": ["liquidity_sweep"],
                    "screenshot_path": "review.jpg",
                    "review_status": "approved_for_teacher",
                },
                {
                    "example_id": "teacher_case::confirmation",
                    "active_labels": ["order_block"],
                    "screenshot_path": "teacher_duplicate.jpg",
                    "review_status": "approved_for_teacher",
                },
            ],
            review_queue={
                "items": [
                    {
                        "example_id": "review_case::confirmation",
                        "review_status": "approved_for_teacher",
                        "disagreement_count": 2,
                    },
                    {
                        "example_id": "teacher_case::confirmation",
                        "review_status": "approved_for_teacher",
                        "disagreement_count": 3,
                    },
                ]
            },
        )

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["benchmark_source"], "teacher")
        self.assertEqual(rows[1]["benchmark_source"], "reviewed_disagreement")
        self.assertEqual(rows[1]["example_id"], "review_case::confirmation")

    def test_ensure_frozen_benchmark_pack_reuses_existing_pack(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            benchmark_path = Path(temp_dir) / "benchmark.jsonl"
            benchmark_path.write_text(
                json.dumps({"example_id": "existing_case::context"}) + "\n",
                encoding="utf-8",
            )

            report = etfb.ensure_frozen_benchmark_pack(
                benchmark_output=benchmark_path,
                teacher_rows=[],
                weak_rows=[],
                review_queue={"items": []},
                force_rebuild=False,
            )

        self.assertEqual(report["status"], "cache_hit")
        self.assertEqual(report["row_count"], 1)

    def test_compare_benchmark_metrics_reports_deltas(self) -> None:
        comparison = etfb.compare_benchmark_metrics(
            champion={
                "micro_f1": 0.41,
                "precision": 0.30,
                "recall": 0.71,
                "exact_match_ratio": 0.18,
                "disagreement_count": 9,
            },
            challenger={
                "micro_f1": 0.55,
                "precision": 0.39,
                "recall": 0.93,
                "exact_match_ratio": 0.22,
                "disagreement_count": 6,
            },
        )

        self.assertEqual(comparison["winner"], "challenger")
        self.assertAlmostEqual(comparison["delta"]["micro_f1"], 0.14, places=6)
        self.assertAlmostEqual(comparison["delta"]["precision"], 0.09, places=6)
        self.assertAlmostEqual(comparison["delta"]["recall"], 0.22, places=6)
        self.assertAlmostEqual(comparison["delta"]["exact_match_ratio"], 0.04, places=6)
        self.assertEqual(comparison["delta"]["disagreement_count"], -3)
