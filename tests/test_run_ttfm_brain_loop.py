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

import run_ttfm_brain_loop as rtbl


class BrainLoopHelpersTests(unittest.TestCase):
    def test_compute_healthy_streak_requires_two_consecutive_healthy_runs(self) -> None:
        history_entries = [
            {"healthy": False},
            {"healthy": True},
        ]

        self.assertEqual(rtbl.compute_healthy_streak(history_entries, False), 0)
        self.assertEqual(rtbl.compute_healthy_streak(history_entries, True), 2)

    def test_select_fallback_next_action_returns_pine_handoff_when_ready(self) -> None:
        action = rtbl.select_fallback_next_action(
            status="ok",
            review_queue={"summary": {}},
            pine_status="ready_for_translation",
        )

        self.assertEqual(action, "brain_ready_for_pine")

    def test_compute_health_flags_defers_when_trade_review_rows_exist_without_review(self) -> None:
        healthy, status = rtbl.compute_health_flags(
            status="ok",
            review_queue={
                "summary": {
                    "reviewed_row_count": 5,
                    "reviewed_alignment_precision": 0.9,
                    "mean_disagreement_count": 0.4,
                }
            },
            multimodal_loop_report={"multimodal_model": {"validation_micro_precision": 0.86}},
            trade_review_readiness={
                "row_count": 3,
                "reviewed_row_count": 0,
                "reviewed_alignment_precision": 0.0,
                "mean_disagreement_count": 0.6,
            },
        )

        self.assertFalse(healthy)
        self.assertEqual(status, "deferred")

    def test_compute_health_flags_defers_when_reviewed_rows_are_below_minimum(self) -> None:
        healthy, status = rtbl.compute_health_flags(
            status="ok",
            review_queue={
                "summary": {
                    "reviewed_row_count": 2,
                    "reviewed_alignment_precision": 0.95,
                    "mean_disagreement_count": 0.1,
                }
            },
            multimodal_loop_report={"multimodal_model": {"validation_micro_precision": 0.9}},
            trade_review_readiness={
                "row_count": 0,
                "reviewed_row_count": 0,
                "reviewed_alignment_precision": 0.0,
                "mean_disagreement_count": 0.0,
            },
        )

        self.assertFalse(healthy)
        self.assertEqual(status, "deferred")


class BrainLoopMainTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.base_dir = Path(self.temp_dir.name)
        self.corpus_report_path = self.base_dir / "corpus_refresh_report.json"
        self.visual_report_path = self.base_dir / "ttfm_visual_teacher_loop_report.json"
        self.multimodal_report_path = self.base_dir / "ttfm_multimodal_teacher_loop_report.json"
        self.review_queue_path = self.base_dir / "ttfm_multimodal_review_queue.json"
        self.review_packets_path = self.base_dir / "ttfm_brain_review_packets.json"
        self.improvement_plan_path = self.base_dir / "ttfm_brain_improvement_plan.json"
        self.output_path = self.base_dir / "ttfm_brain_loop_report.json"
        self.history_path = self.base_dir / "ttfm_brain_loop_history.jsonl"

    def patch_default_paths(self) -> dict[str, Path]:
        return {
            "DEFAULT_CORPUS_REFRESH_REPORT_PATH": self.corpus_report_path,
            "DEFAULT_VISUAL_LOOP_REPORT_PATH": self.visual_report_path,
            "DEFAULT_MULTIMODAL_LOOP_REPORT_PATH": self.multimodal_report_path,
            "DEFAULT_REVIEW_QUEUE_PATH": self.review_queue_path,
            "DEFAULT_REVIEW_PACKETS_PATH": self.review_packets_path,
            "DEFAULT_IMPROVEMENT_PLAN_PATH": self.improvement_plan_path,
        }

    def fake_stage_runner(self, calls: list[str], fail_review_packets: bool = False):
        def runner(*, python_executable: str, script_name: str, args: list[str]) -> dict[str, object]:
            calls.append(script_name)
            if script_name == "refresh_ttfm_video_corpus.py":
                self.corpus_report_path.write_text(
                    json.dumps(
                        {
                            "active_manifest": {
                                "video_count": 9,
                                "partition_counts": {"seed_curriculum": 6, "trade_review": 3},
                            }
                        }
                    ),
                    encoding="utf-8",
                )
            elif script_name == "run_ttfm_visual_teacher_loop.py":
                self.visual_report_path.write_text(
                    json.dumps({"generated_at": "2026-03-24T00:00:00Z", "summary": "visual"}),
                    encoding="utf-8",
                )
            elif script_name == "run_ttfm_multimodal_teacher_loop.py":
                self.multimodal_report_path.write_text(
                    json.dumps(
                        {
                            "multimodal_model": {
                                "model_path": "results/neural_models/demo.pt",
                                "validation_micro_precision": 0.86,
                                "validation_micro_f1": 0.81,
                            }
                        }
                    ),
                    encoding="utf-8",
                )
                self.review_queue_path.write_text(
                    json.dumps(
                        {
                            "summary": {
                                "row_count": 6,
                                "model_disagreement_count": 0,
                                "ready_to_promote_count": 2,
                                "reviewed_row_count": 5,
                                "reviewed_alignment_precision": 0.91,
                                "mean_disagreement_count": 0.4,
                            },
                            "items": [
                                {
                                    "example_id": "trade_review_case::confirmation",
                                    "video_slug": "review_one",
                                    "corpus_partition": "trade_review",
                                    "review_status": "approved_for_teacher",
                                    "recommended_action": "promote_into_teacher_surface",
                                    "disagreement_count": 0,
                                    "label_jaccard": 1.0,
                                },
                                {
                                    "example_id": "trade_review_case::closure",
                                    "video_slug": "review_two",
                                    "corpus_partition": "trade_review",
                                    "review_status": "approved_for_teacher",
                                    "recommended_action": "promote_into_teacher_surface",
                                    "disagreement_count": 0,
                                    "label_jaccard": 1.0,
                                },
                                {
                                    "example_id": "trade_review_case::outcome",
                                    "video_slug": "review_three",
                                    "corpus_partition": "trade_review",
                                    "review_status": "approved_for_teacher",
                                    "recommended_action": "promote_into_teacher_surface",
                                    "disagreement_count": 0,
                                    "label_jaccard": 1.0,
                                },
                            ],
                        }
                    ),
                    encoding="utf-8",
                )
            elif script_name == "export_ttfm_brain_review_packets.py":
                if fail_review_packets:
                    raise rtbl.subprocess.CalledProcessError(1, script_name)
                self.review_packets_path.write_text(
                    json.dumps({"summary": {"packet_count": 2}, "packets": []}),
                    encoding="utf-8",
                )
            elif script_name == "export_ttfm_brain_improvement_plan.py":
                self.improvement_plan_path.write_text(
                    json.dumps(
                        {
                            "next_action": "promote_clean_labels",
                            "priority_actions": [{"action": "promote_clean_labels"}],
                        }
                    ),
                    encoding="utf-8",
                )
            return {"script_name": script_name, "status": "ok"}

        return runner

    def test_main_writes_brain_loop_report_without_touching_downstream_pine_loop(self) -> None:
        calls: list[str] = []
        argv = [
            "run_ttfm_brain_loop.py",
            "--output",
            str(self.output_path),
            "--history-output",
            str(self.history_path),
        ]

        with (
            patch.multiple(rtbl, **self.patch_default_paths()),
            patch.object(rtbl, "maybe_refresh_text_embedding_index", return_value={"status": "reused"}),
            patch.object(rtbl, "maybe_refresh_visual_embedding_index", return_value={"status": "reused"}),
            patch.object(rtbl, "run_script_stage", side_effect=self.fake_stage_runner(calls)),
            patch.object(sys, "argv", argv),
        ):
            rtbl.main()

        report = json.loads(self.output_path.read_text(encoding="utf-8"))
        history_lines = self.history_path.read_text(encoding="utf-8").splitlines()

        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["next_action"], "promote_clean_labels")
        self.assertEqual(report["pine_status"], "not_ready")
        self.assertEqual(report["video_corpus_stage"]["active_manifest"]["video_count"], 9)
        self.assertEqual(report["trade_review_readiness"]["row_count"], 3)
        self.assertEqual(report["trade_review_readiness"]["reviewed_row_count"], 3)
        self.assertIn("refresh_ttfm_video_corpus.py", calls)
        self.assertIn("run_ttfm_visual_teacher_loop.py", calls)
        self.assertIn("run_ttfm_multimodal_teacher_loop.py", calls)
        self.assertIn("export_ttfm_brain_review_packets.py", calls)
        self.assertIn("export_ttfm_brain_improvement_plan.py", calls)
        self.assertNotIn("run_trading_learning_loop.py", calls)
        self.assertEqual(len(history_lines), 1)

    def test_main_writes_degraded_report_when_optional_export_fails(self) -> None:
        calls: list[str] = []
        argv = [
            "run_ttfm_brain_loop.py",
            "--output",
            str(self.output_path),
            "--history-output",
            str(self.history_path),
            "--skip-improvement-plan",
        ]

        with (
            patch.multiple(rtbl, **self.patch_default_paths()),
            patch.object(rtbl, "maybe_refresh_text_embedding_index", return_value={"status": "reused"}),
            patch.object(rtbl, "maybe_refresh_visual_embedding_index", return_value={"status": "reused"}),
            patch.object(
                rtbl,
                "run_script_stage",
                side_effect=self.fake_stage_runner(calls, fail_review_packets=True),
            ),
            patch.object(sys, "argv", argv),
        ):
            rtbl.main()

        report = json.loads(self.output_path.read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "degraded")
        self.assertIn("review_packets", report["failed_optional_stages"])
        self.assertEqual(report["next_action"], "report_first")


if __name__ == "__main__":
    unittest.main()
