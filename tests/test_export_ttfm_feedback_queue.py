from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import export_ttfm_feedback_queue as etfq


class ExportTTFMFeedbackQueueTests(unittest.TestCase):
    def test_merges_pine_feedback_with_tradingview_failures(self) -> None:
        pine_report = {
            "feedback_candidates": [
                {
                    "id": "pine::finding",
                    "target_type": "finding",
                    "target_path": "findings.md",
                    "title": "Pine verification failed for point_of_interest",
                    "body": "Pine could not reproduce the POI markup deterministically.",
                }
            ]
        }
        tradingview_log = {
            "validations": [
                {
                    "spec_key": "daily_bias_framework",
                    "validation_status": "blocked_monaco_sync",
                    "validation_method": "playwriter",
                    "notes": "Editor title changed but Monaco buffer stayed stale.",
                    "script_path": "results/pine_scripts/daily_bias_framework.pine",
                    "chart_symbol": "NQM2026",
                },
                {
                    "spec_key": "reversal_sequence_model",
                    "validation_status": "compile_error",
                    "validation_method": "playwriter",
                    "notes": "Compile failed on line 42.",
                },
                {
                    "spec_key": "continuation_entry_model",
                    "validation_status": "added_to_chart",
                    "validation_method": "playwriter",
                    "qa_status": "fail",
                    "semantic_score": 0.3,
                    "visual_score": 0.2,
                    "scope_score": 0.5,
                    "notes": "Loaded on chart but failed the semantic/visual QA gate.",
                },
            ]
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            spec_dir = Path(tmp_dir)
            (spec_dir / "reversal_sequence_model.json").write_text("{}", encoding="utf-8")
            queue = etfq.build_feedback_queue(
                pine_verification_report=pine_report,
                tradingview_validation_log=tradingview_log,
                spec_dir=spec_dir,
            )

        self.assertEqual(queue["summary"]["pine_feedback_candidate_count"], 1)
        self.assertEqual(queue["summary"]["tradingview_failure_count"], 3)
        self.assertEqual(queue["summary"]["item_count"], 5)
        item_ids = {item["id"] for item in queue["items"]}
        self.assertIn("pine::finding", item_ids)
        self.assertIn("tradingview::daily_bias_framework::blocked_monaco_sync::finding", item_ids)
        self.assertIn("tradingview::reversal_sequence_model::compile_error::finding", item_ids)
        self.assertIn("tradingview::reversal_sequence_model::compile_error::draft-spec", item_ids)
        self.assertIn("tradingview::continuation_entry_model::qa_gate_failed::finding", item_ids)


if __name__ == "__main__":
    unittest.main()
