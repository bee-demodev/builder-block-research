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

import export_phase_one_chart_state_surface as epcss


def make_phase_one_replay_state() -> dict:
    return {
        "case_ref": "sample_tv_hourly_sequence_case",
        "profile_slug": "",
        "topic": "continuation",
        "trade_model": "daily_bias_c123_map",
        "relation_type": "execution_model",
        "chart_context": {
            "setup_variant": "daily_bias_c123_map",
            "source_kind": "tradingview_pine_alert",
            "timeframe_scope": ["chart_60", "bias_D", "execution_60"],
            "session_scope": ["new_york"],
        },
        "annotation": {
            "fired_alert": "Hourly sequence activated",
            "rule_states": {
                "dailyBiasDirection": "bullish",
                "activeHourlyDir": "bullish",
                "activeHourlyC1Time": "2026-03-23T08:00:00-04:00",
                "activeHourlyC2Time": "2026-03-23T09:00:00-04:00",
                "activeHourlyC3Time": "2026-03-23T10:00:00-04:00",
            },
        },
        "candidate_signal": {
            "timestamp": "2026-03-23T10:00:00-04:00",
            "side": "long",
            "stop_price": 21320.0,
            "target_price": 21480.0,
            "quantity": 1.0,
            "session": "new_york",
            "thesis": "hourly sequence activated inside daily poi",
        },
    }


def make_passed_no_sequence_validation() -> dict:
    return {
        "recorded_at": "2026-03-23T20:11:15.798292+00:00",
        "spec_key": "daily_bias_c123_map",
        "validation_status": "compiled_on_chart",
        "validation_method": "playwriter",
        "qa_status": "pass",
        "semantic_score": 0.9,
        "visual_score": 0.88,
        "scope_score": 0.9,
        "notes": (
            "Playwriter visual QA on the live 1H chart showed the phase-1 contract "
            "behaving correctly for a no-sequence state: bearish daily bias banner, "
            "single active daily POI zone, and a wait-for-short-C2 cue."
        ),
        "qa_notes": (
            "No active hourly sequence is present, so C1/C2/C3 labels are absent "
            "while the waiting cue remains visible."
        ),
        "chart_url": "https://www.tradingview.com/chart/demo/",
        "chart_symbol": "CME_MINI:NQM2026",
    }


class BuildPhaseOneChartStateSurfaceTests(unittest.TestCase):
    def test_build_surface_exports_trade_and_no_trade_examples(self) -> None:
        surface = epcss.build_phase_one_chart_state_surface(
            replay_state_batch={"states": [make_phase_one_replay_state()]},
            validation_log={"validations": [make_passed_no_sequence_validation()]},
        )

        self.assertEqual(surface["summary"]["exported_example_count"], 2)
        self.assertEqual(surface["summary"]["positive_example_count"], 1)
        self.assertEqual(surface["summary"]["negative_example_count"], 1)
        self.assertEqual(
            surface["summary"]["outcome_decision_counts"],
            {"no_trade": 1, "trade": 1},
        )

        trade_example = next(
            example
            for example in surface["examples"]
            if example["targets"]["outcome_decision"] == "trade"
        )
        self.assertEqual(trade_example["trade_model"], "daily_bias_c123_map")
        self.assertEqual(trade_example["relation_type"], "execution_model")
        self.assertEqual(trade_example["features"]["source_kind"], "tradingview_pine_alert")
        self.assertTrue(trade_example["targets"]["has_outcome_label"])
        self.assertIn("hourly sequence activated", trade_example["training_text"])
        self.assertIn("outcome trade", trade_example["training_text"])

        no_trade_example = next(
            example
            for example in surface["examples"]
            if example["targets"]["outcome_decision"] == "no_trade"
        )
        self.assertEqual(no_trade_example["trade_model"], "daily_bias_c123_map")
        self.assertEqual(no_trade_example["relation_type"], "execution_model")
        self.assertEqual(no_trade_example["features"]["source_kind"], "tradingview_validation")
        self.assertTrue(no_trade_example["targets"]["is_no_trade"])
        self.assertTrue(no_trade_example["targets"]["has_outcome_label"])
        self.assertIn("wait for short c2", no_trade_example["training_text"])
        self.assertIn("outcome no_trade", no_trade_example["training_text"])

    def test_build_surface_reports_skip_reasons_for_non_phase_one_noise(self) -> None:
        surface = epcss.build_phase_one_chart_state_surface(
            replay_state_batch={
                "states": [
                    make_phase_one_replay_state(),
                    {
                        **make_phase_one_replay_state(),
                        "case_ref": "wrong_spec",
                        "trade_model": "continuation_entry_model",
                    },
                ]
            },
            validation_log={
                "validations": [
                    make_passed_no_sequence_validation(),
                    {
                        **make_passed_no_sequence_validation(),
                        "recorded_at": "2026-03-23T20:15:00+00:00",
                        "spec_key": "daily_bias_framework",
                    },
                    {
                        **make_passed_no_sequence_validation(),
                        "recorded_at": "2026-03-23T20:20:00+00:00",
                        "qa_status": "fail",
                    },
                    {
                        **make_passed_no_sequence_validation(),
                        "recorded_at": "2026-03-23T20:25:00+00:00",
                        "notes": "Active hourly sequence is visible and fully labeled.",
                        "qa_notes": "C1, C2, and C3 are active on the live chart.",
                    },
                ]
            },
        )

        self.assertEqual(surface["summary"]["exported_example_count"], 2)
        self.assertEqual(
            surface["summary"]["skipped_replay_state_counts"],
            {"not_phase_one_execution_spec": 1},
        )
        self.assertEqual(
            surface["summary"]["skipped_validation_counts"],
            {
                "not_no_sequence_state": 1,
                "not_phase_one_execution_spec": 1,
                "qa_not_passed": 1,
            },
        )

    def test_export_surface_writes_jsonl_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            replay_state_path = tmp_path / "replay_state.json"
            validation_log_path = tmp_path / "validation_log.json"
            output_path = tmp_path / "phase_one_chart_state_surface.jsonl"
            report_path = tmp_path / "phase_one_chart_state_surface_report.json"

            replay_state_path.write_text(
                json.dumps({"states": [make_phase_one_replay_state()]}),
                encoding="utf-8",
            )
            validation_log_path.write_text(
                json.dumps({"validations": [make_passed_no_sequence_validation()]}),
                encoding="utf-8",
            )

            report = epcss.export_phase_one_chart_state_surface(
                replay_state_path=replay_state_path,
                validation_log_path=validation_log_path,
                dataset_output_path=output_path,
                report_output_path=report_path,
            )

            self.assertTrue(output_path.exists())
            self.assertTrue(report_path.exists())
            self.assertEqual(report["summary"]["exported_example_count"], 2)

            exported_lines = [
                json.loads(line)
                for line in output_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(len(exported_lines), 2)

            saved_report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(
                saved_report["summary"]["outcome_decision_counts"],
                {"no_trade": 1, "trade": 1},
            )


if __name__ == "__main__":
    unittest.main()
