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

import generate_pine_from_spec as gpfs


class BuildPineScriptTests(unittest.TestCase):
    def test_daily_bias_spec_renders_compile_shaped_script(self) -> None:
        spec = json.loads((ROOT / "results" / "indicator_specs" / "daily_bias_framework.json").read_text())

        script = gpfs.build_pine_script(spec)

        self.assertIn("//@version=6", script)
        self.assertIn('indicator("TTrades Daily Bias Framework [Draft]"', script)
        self.assertIn("request.security(", script)
        self.assertIn("alertcondition(", script)
        self.assertIn("biasAnchorModeInput", script)
        self.assertIn("continuationPoiTop", script)
        self.assertIn("reversalAnchorBandTop", script)
        self.assertIn("targetPrimaryPrice", script)
        self.assertIn("plotshape(sweepsHighAndClosesInside", script)
        self.assertIn("table.new(position.top_right", script)
        self.assertIn("visualLookbackBarsInput", script)
        self.assertIn("showHistoricalBiasTintInput", script)
        self.assertIn('plot(activePoiTop, "Active HTF POI top"', script)
        self.assertIn('table.new(position.middle_right', script)
        self.assertIn('table.cell(levelsLadder, 0, 0, "PDH"', script)
        self.assertIn("candle2BullAtPoi", script)
        self.assertIn("bullishCandle3Closure", script)
        self.assertIn("entryModelText", script)
        self.assertIn("show_last=visualLookbackBarsInput", script)

    def test_daily_bias_c123_map_renders_narrow_sequence_script(self) -> None:
        spec = {
            "trader_profile": {"display_name": "TTrades Curriculum"},
            "trade_model": {
                "slug": "daily_bias_c123_map",
                "name": "Daily Bias C1/C2/C3 Map",
            },
            "implementation_summary": "Daily bias phase 1 map for D bias, active 1H C1/C2/C3 structure near the daily POI, and 5m continuation refinement inside hourly Candle 3.",
            "timeframe_contract": {
                "chart": "60",
                "bias": "D",
                "structure": "60",
                "execution": "5",
            },
            "input_groups": [],
        }

        script = gpfs.build_pine_script(spec)

        self.assertIn('indicator("TTrades Daily Bias C1/C2/C3 Map [Draft]"', script)
        self.assertIn('request.security(syminfo.tickerid, "D"', script)
        self.assertIn("dailyPoiTop", script)
        self.assertIn("dailyPoiBottom", script)
        self.assertIn("priceInsideDailyPoi", script)
        self.assertIn("activeBiasWindowStart", script)
        self.assertIn("box.new(activeBiasWindowStart", script)
        self.assertIn("activeEntryPrice", script)
        self.assertIn("entryGuideLabel", script)
        self.assertIn("hourlyWaitingLabel", script)
        self.assertIn("dailyBiasLabel", script)
        self.assertIn("activeHourlyC2Time", script)
        self.assertIn('"Entry"', script)
        self.assertIn('"C2"', script)
        self.assertIn("Wait for short C2", script)
        self.assertIn("Wait for long C2", script)
        self.assertIn('request.security(syminfo.tickerid, "5"', script)
        self.assertIn("activeLtfDir", script)
        self.assertIn("activeLtfC2Time", script)
        self.assertIn("activeLtfC3Time", script)
        self.assertIn("activeLtfEntryPrice", script)
        self.assertIn("Five minute continuation activated", script)
        self.assertIn("math.max(open[2], close[2])", script)
        self.assertIn("math.min(open[2], close[2])", script)
        self.assertIn("activeHourlyC1Time - int(timeframe.in_seconds(\"60\") * 250)", script)
        self.assertIn("activeHourlyC3Time + int(timeframe.in_seconds(\"60\") * 250)", script)
        self.assertIn("activeEntryTime + int(timeframe.in_seconds(\"60\") * 500)", script)
        self.assertIn("Unsupported chart timeframe", script)
        self.assertIn("xloc=xloc.bar_time", script)
        self.assertIn("max_boxes_count=4", script)
        self.assertNotIn("fill(dailyPoiTopPlot", script)
        self.assertNotIn("table.new(position.top_right", script)
        self.assertNotIn('"1H C2"', script)
        self.assertNotIn("activeHourlyC3Price := close", script)
        self.assertNotIn("showFiveMinuteSequenceInput", script)
        self.assertNotIn("levelsLadder", script)
        self.assertNotIn("targetPrimaryPrice", script)
        self.assertNotIn('"5m C2"', script)

    def test_generic_spec_still_renders_editor_ready_scaffold(self) -> None:
        spec = json.loads((ROOT / "results" / "indicator_specs" / "continuation_entry_model.json").read_text())

        script = gpfs.build_pine_script(spec)

        self.assertIn("//@version=6", script)
        self.assertIn('indicator("TTrades Continuation Entry Model [Draft]"', script)
        self.assertIn("Draft scaffold generated from indicator spec", script)
        self.assertIn("Signal pipeline", script)
        self.assertIn("provisional proxy", script.lower())

    def test_build_candidate_event_contract_extracts_alerts_and_runtime_fields(self) -> None:
        spec = {
            "trader_profile": {"display_name": "TTrades Curriculum"},
            "trade_model": {
                "slug": "daily_bias_c123_map",
                "name": "Daily Bias C1/C2/C3 Map",
            },
            "implementation_summary": "Daily bias phase 1 map for D bias, active 1H C1/C2/C3 structure near the daily POI, and 5m continuation refinement inside hourly Candle 3.",
            "timeframe_contract": {
                "chart": "60",
                "bias": "D",
                "structure": "60",
                "execution": "5",
            },
            "input_groups": [],
        }

        script = gpfs.build_pine_script(spec)
        contract = gpfs.build_candidate_event_contract(
            spec,
            script_text=script,
            script_output_path=Path("results/pine_scripts/daily_bias_c123_map.pine"),
        )

        self.assertEqual(contract["spec_key"], "daily_bias_c123_map")
        self.assertIn("Hourly sequence activated", contract["alert_titles"])
        self.assertIn("Five minute continuation activated", contract["alert_titles"])
        self.assertIn("activeHourlyC2Time", contract["rule_state_fields"])
        self.assertIn("activeLtfC2Time", contract["rule_state_fields"])
        self.assertEqual(contract["default_event"]["trade_model"], "daily_bias_c123_map")
        self.assertEqual(contract["default_event"]["chart_context"]["source_kind"], "tradingview_pine_alert")
        self.assertEqual(
            contract["default_event"]["chart_context"]["timeframe_scope"],
            ["chart_60", "bias_D", "structure_60", "execution_5"],
        )
        self.assertEqual(contract["default_event"]["candidate_signal"]["session"], "")


class GenerateScriptsTests(unittest.TestCase):
    def test_generate_scripts_writes_manifest_and_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "pine_scripts"
            contract_dir = Path(tmp_dir) / "candidate_event_contracts"
            manifest_path = Path(tmp_dir) / "manifest.json"
            spec_paths = [
                ROOT / "results" / "indicator_specs" / "daily_bias_framework.json",
                ROOT / "results" / "indicator_specs" / "continuation_entry_model.json",
            ]

            manifest = gpfs.generate_scripts(
                spec_paths,
                output_dir=output_dir,
                candidate_contract_output_dir=contract_dir,
                manifest_output_path=manifest_path,
            )

            self.assertEqual(manifest["summary"]["generated_script_count"], 2)
            self.assertEqual(manifest["summary"]["generated_candidate_contract_count"], 2)
            self.assertTrue((output_dir / "daily_bias_framework.pine").exists())
            self.assertTrue((output_dir / "continuation_entry_model.pine").exists())
            self.assertTrue((contract_dir / "daily_bias_framework.candidate_event_contract.json").exists())
            self.assertTrue((contract_dir / "continuation_entry_model.candidate_event_contract.json").exists())
            self.assertEqual(len(manifest["candidate_event_contracts"]), 2)
            self.assertTrue(manifest_path.exists())


if __name__ == "__main__":
    unittest.main()
