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

import export_tradingview_pine_readiness_report as etprr


class TradingViewPineReadinessReportTests(unittest.TestCase):
    def test_report_requires_qa_pass_not_just_editor_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_root = Path(tmp_dir)
            spec_dir = temp_root / "indicator_specs"
            script_dir = temp_root / "pine_scripts"
            workflow_doc = temp_root / "knowledge" / "tradingview_pine_workflow.md"
            spec_dir.mkdir(parents=True)
            script_dir.mkdir(parents=True)
            workflow_doc.parent.mkdir(parents=True)
            workflow_doc.write_text("# workflow\n", encoding="utf-8")

            for slug in ("daily_bias_framework", "continuation_entry_model"):
                (spec_dir / f"{slug}.json").write_text(
                    json.dumps(
                        {
                            "trade_model": {"slug": slug, "name": slug.replace("_", " ").title()},
                            "implementation_scope": {"target_language": "pine"},
                        }
                    ),
                    encoding="utf-8",
                )

            (script_dir / "daily_bias_framework.pine").write_text("//@version=6\nindicator(\"x\")\n", encoding="utf-8")

            validation_log = {
                "validations": [
                    {
                        "spec_key": "daily_bias_framework",
                        "script_path": "results/pine_scripts/daily_bias_framework.pine",
                        "validation_status": "added_to_chart",
                        "validation_method": "playwriter",
                        "qa_status": "fail",
                        "semantic_score": 0.2,
                        "visual_score": 0.1,
                        "scope_score": 0.4,
                    }
                ]
            }

            report = etprr.build_tradingview_pine_readiness_report(
                spec_dir=spec_dir,
                script_dir=script_dir,
                validation_log=validation_log,
                workflow_doc_path=workflow_doc,
            )

            self.assertEqual(report["summary"]["pine_target_spec_count"], 2)
            self.assertEqual(report["summary"]["generated_script_count"], 1)
            self.assertEqual(report["summary"]["editor_accepted_count"], 1)
            self.assertEqual(report["summary"]["validated_script_count"], 0)
            self.assertEqual(report["summary"]["playwriter_validated_count"], 0)
            self.assertEqual(report["summary"]["qa_gate_pass_count"], 0)
            self.assertGreater(report["summary"]["workflow_score"], 0.0)
            self.assertIn("continuation_entry_model", report["summary"]["pending_spec_keys"])

    def test_report_counts_validation_only_when_qa_scores_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_root = Path(tmp_dir)
            spec_dir = temp_root / "indicator_specs"
            script_dir = temp_root / "pine_scripts"
            workflow_doc = temp_root / "knowledge" / "tradingview_pine_workflow.md"
            spec_dir.mkdir(parents=True)
            script_dir.mkdir(parents=True)
            workflow_doc.parent.mkdir(parents=True)
            workflow_doc.write_text("# workflow\n", encoding="utf-8")

            (spec_dir / "daily_bias_framework.json").write_text(
                json.dumps(
                    {
                        "trade_model": {"slug": "daily_bias_framework", "name": "Daily Bias Framework"},
                        "implementation_scope": {"target_language": "pine"},
                    }
                ),
                encoding="utf-8",
            )
            (script_dir / "daily_bias_framework.pine").write_text("//@version=6\nindicator(\"x\")\n", encoding="utf-8")

            report = etprr.build_tradingview_pine_readiness_report(
                spec_dir=spec_dir,
                script_dir=script_dir,
                validation_log={
                    "validations": [
                        {
                            "spec_key": "daily_bias_framework",
                            "script_path": "results/pine_scripts/daily_bias_framework.pine",
                            "validation_status": "validated",
                            "validation_method": "playwriter",
                            "qa_status": "pass",
                            "semantic_score": 0.92,
                            "visual_score": 0.84,
                            "scope_score": 0.95,
                        }
                    ]
                },
                workflow_doc_path=workflow_doc,
            )

            self.assertEqual(report["summary"]["validated_script_count"], 1)
            self.assertEqual(report["summary"]["playwriter_validated_count"], 1)
            self.assertEqual(report["summary"]["qa_gate_pass_count"], 1)

    def test_compiled_on_chart_counts_as_editor_acceptance_and_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_root = Path(tmp_dir)
            spec_dir = temp_root / "indicator_specs"
            script_dir = temp_root / "pine_scripts"
            workflow_doc = temp_root / "knowledge" / "tradingview_pine_workflow.md"
            spec_dir.mkdir(parents=True)
            script_dir.mkdir(parents=True)
            workflow_doc.parent.mkdir(parents=True)
            workflow_doc.write_text("# workflow\n", encoding="utf-8")

            (spec_dir / "daily_bias_c123_map.json").write_text(
                json.dumps(
                    {
                        "trade_model": {"slug": "daily_bias_c123_map", "name": "Daily Bias C1/C2/C3 Map"},
                        "implementation_scope": {"target_language": "pine"},
                    }
                ),
                encoding="utf-8",
            )
            (script_dir / "daily_bias_c123_map.pine").write_text("//@version=6\nindicator(\"x\")\n", encoding="utf-8")

            report = etprr.build_tradingview_pine_readiness_report(
                spec_dir=spec_dir,
                script_dir=script_dir,
                validation_log={
                    "validations": [
                        {
                            "spec_key": "daily_bias_c123_map",
                            "script_path": "results/pine_scripts/daily_bias_c123_map.pine",
                            "validation_status": "compiled_on_chart",
                            "validation_method": "playwriter",
                            "qa_status": "pass",
                            "semantic_score": 0.9,
                            "visual_score": 0.88,
                            "scope_score": 0.91,
                        }
                    ]
                },
                workflow_doc_path=workflow_doc,
            )

            self.assertEqual(report["summary"]["editor_accepted_count"], 1)
            self.assertEqual(report["summary"]["validated_script_count"], 1)
            self.assertEqual(report["summary"]["playwriter_validated_count"], 1)
            self.assertTrue(report["per_spec_status"][0]["editor_accepted_in_tradingview"])
            self.assertTrue(report["per_spec_status"][0]["validated_in_tradingview"])


if __name__ == "__main__":
    unittest.main()
