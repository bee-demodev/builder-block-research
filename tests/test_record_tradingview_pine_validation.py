from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import record_tradingview_pine_validation as rtpv


class RecordTradingViewPineValidationTests(unittest.TestCase):
    def test_append_validation_entry_is_append_only(self) -> None:
        log = {"validations": [{"spec_key": "older", "validation_status": "compiled"}]}

        updated = rtpv.append_validation_entry(
            log,
            spec_key="daily_bias_framework",
            script_path="results/pine_scripts/daily_bias_framework.pine",
            validation_status="added_to_chart",
            validation_method="playwriter",
            notes="Compiled on chart.",
            chart_url="https://www.tradingview.com/chart/demo/",
            chart_symbol="NQM2026",
            qa_status="fail",
            semantic_score=0.2,
            visual_score=0.1,
            scope_score=0.4,
            qa_notes="Overlay loaded but does not match the intended TTrades markup.",
        )

        self.assertEqual(len(updated["validations"]), 2)
        self.assertEqual(updated["validations"][0]["spec_key"], "older")
        self.assertEqual(updated["validations"][-1]["spec_key"], "daily_bias_framework")
        self.assertEqual(updated["validations"][-1]["validation_method"], "playwriter")
        self.assertEqual(updated["validations"][-1]["qa_status"], "fail")
        self.assertEqual(updated["validations"][-1]["semantic_score"], 0.2)
        self.assertEqual(updated["validations"][-1]["visual_score"], 0.1)
        self.assertEqual(updated["validations"][-1]["scope_score"], 0.4)

    def test_write_and_reload_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "validation.json"
            log = rtpv.append_validation_entry(
                {"validations": []},
                spec_key="daily_bias_framework",
                script_path="results/pine_scripts/daily_bias_framework.pine",
                validation_status="compiled",
                validation_method="playwriter",
                qa_status="pending",
            )
            rtpv.write_validation_log(path, log)
            loaded = rtpv.load_validation_log(path)

            self.assertEqual(len(loaded["validations"]), 1)
            self.assertEqual(loaded["validations"][0]["validation_status"], "compiled")
            self.assertEqual(loaded["validations"][0]["qa_status"], "pending")


if __name__ == "__main__":
    unittest.main()
