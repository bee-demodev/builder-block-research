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

import export_phase_one_daily_bias_gap_report as epdbg


class ExportPhaseOneDailyBiasGapReportTests(unittest.TestCase):
    def test_report_identifies_daily_bias_gap_and_honest_evidence_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            report_output = tmp_path / "daily_bias_gap_report.json"

            report = epdbg.export_phase_one_daily_bias_gap_report(
                report_output=report_output,
            )

            self.assertTrue(report_output.exists())
            self.assertEqual(report["target_trade_model"], "daily_bias_framework")
            self.assertEqual(report["current_counts"]["positive"], 4)
            self.assertEqual(report["current_counts"]["negative"], 16)
            self.assertEqual(report["recommended_positive_examples"], 5)
            self.assertEqual(report["additional_positive_examples_needed"], 1)
            self.assertEqual(report["blocker"]["type"], "missing_chart_state_alignment")
            self.assertTrue(report["blocker"]["missing_replay_evidence"])
            self.assertFalse(report["blocker"]["missing_tradingview_validation"])
            self.assertEqual(report["candidate_summary"]["teacher_visual_candidate_count"], 10)
            self.assertEqual(report["candidate_summary"]["promotable_candidate_count"], 0)
            self.assertEqual(report["candidate_summary"]["blocked_candidate_count"], 10)
            self.assertEqual(report["candidate_summary"]["alignment_status_counts"]["market_context_only"], 10)
            self.assertEqual(report["candidate_summary"]["source_image_kind_counts"]["source_article_image"], 10)
            self.assertEqual(report["fastest_positive_candidates"], [])
            self.assertGreaterEqual(len(report["blocked_teacher_visual_candidates"]), 1)

            fastest = report["blocked_teacher_visual_candidates"][0]
            self.assertEqual(
                fastest["example_id"],
                "ttrades_daily_bias_reversal_baseline_v1::context",
            )
            self.assertEqual(
                fastest["source_file"],
                "results/ttfm_teacher_visual_dataset.jsonl",
            )
            self.assertEqual(fastest["source_url"], "https://ttrades.com/next-day-model-a-fractal-way-to-build-trading-bias/")
            self.assertIn("equilibrium", fastest["active_labels"])
            self.assertIn("zone_boundary", fastest["active_labels"])
            self.assertEqual(fastest["active_label_provenance"], "rule_derived")
            self.assertEqual(fastest["source_image_kind"], "source_article_image")
            self.assertFalse(fastest["promotion_ready"])
            self.assertIn("missing_fully_aligned_market_context", fastest["promotion_blockers"])
            self.assertIn("source_article_image_only", fastest["promotion_blockers"])
            self.assertIn(
                "ttrades_daily_bias_reversal_baseline_v1::context",
                report["next_step"],
            )

            saved_report = json.loads(report_output.read_text(encoding="utf-8"))
            self.assertEqual(saved_report["target_trade_model"], "daily_bias_framework")
            self.assertEqual(saved_report["current_counts"]["positive"], 4)


if __name__ == "__main__":
    unittest.main()
