from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import export_ttfm_teacher_visual_dataset as etvd


def make_case_packet_report() -> dict:
    return {
        "summary": {
            "case_count": 3,
            "checkpoint_count": 4,
            "missing_screenshot_count": 1,
        },
        "case_packets": [
            {
                "case_ref": "case_manual",
                "topic": "bias",
                "trade_models": ["daily_bias_framework"],
                "relation_types": ["bias_framework"],
                "source_url": "https://example.com/manual",
                "draft_spec_keys": ["ttrades_curriculum__daily_bias_framework"],
                "supporting_topics": ["bias"],
                "outcome": {"decision": "trade", "reason": "manual"},
                "timeframe_stack": {"htf": "higher", "etf": "intraday", "ltf": "lower"},
                "checkpoints": [
                    {
                        "checkpoint": "context",
                        "timeframe": "higher",
                        "timeframe_role": "htf",
                        "screenshot_path": "artifacts/ttfm/case_manual/context.png",
                        "expected_component_labels": ["equilibrium"],
                        "active_label_provenance": "rule_derived",
                        "labels_by_provenance": {"rule_derived": ["equilibrium"]},
                        "annotation_notes": ["manual anchor"],
                        "evidence_refs": ["https://example.com/manual"],
                    }
                ],
            },
            {
                "case_ref": "case_proxy",
                "topic": "bias",
                "trade_models": ["daily_bias_framework"],
                "relation_types": ["bias_framework"],
                "source_url": "https://example.com/proxy",
                "draft_spec_keys": ["ttrades_curriculum__daily_bias_framework"],
                "supporting_topics": ["bias"],
                "outcome": {"decision": "trade", "reason": "proxy"},
                "timeframe_stack": {"htf": "higher", "etf": "intraday", "ltf": "lower"},
                "checkpoints": [
                    {
                        "checkpoint": "confirmation",
                        "timeframe": "lower",
                        "timeframe_role": "ltf",
                        "screenshot_path": "artifacts/ttfm/case_proxy/confirmation.png",
                        "expected_component_labels": ["equilibrium"],
                        "active_label_provenance": "rule_derived",
                        "labels_by_provenance": {"rule_derived": ["equilibrium"]},
                        "annotation_notes": ["proxy"],
                        "evidence_refs": ["https://example.com/proxy"],
                    }
                ],
            },
            {
                "case_ref": "case_unmapped",
                "topic": "continuation",
                "trade_models": ["continuation_entry_model"],
                "relation_types": ["execution_model"],
                "source_url": "https://example.com/unmapped",
                "draft_spec_keys": ["ttrades_curriculum__continuation_entry_model"],
                "supporting_topics": ["continuation"],
                "outcome": {"decision": "trade", "reason": "unmapped"},
                "timeframe_stack": {"htf": "higher", "etf": "intraday", "ltf": "lower"},
                "checkpoints": [
                    {
                        "checkpoint": "context",
                        "timeframe": "higher",
                        "timeframe_role": "htf",
                        "screenshot_path": "artifacts/ttfm/case_unmapped/context.png",
                        "expected_component_labels": ["point_of_interest"],
                        "active_label_provenance": "rule_derived",
                        "labels_by_provenance": {"rule_derived": ["point_of_interest"]},
                        "annotation_notes": ["unmapped"],
                        "evidence_refs": ["https://example.com/unmapped"],
                    },
                    {
                        "checkpoint": "outcome",
                        "timeframe": "intraday",
                        "timeframe_role": "etf",
                        "screenshot_path": None,
                        "expected_component_labels": [],
                        "active_label_provenance": "unlabeled",
                        "labels_by_provenance": {},
                        "annotation_notes": [],
                        "evidence_refs": [],
                    },
                ],
            },
        ],
    }


def make_bars_manifest() -> dict:
    return {
        "files": [
            {
                "symbol": "NQ",
                "timeframe": "1m",
                "normalized_csv_path": "data/databento/bars/nq_minute.csv",
                "first_timestamp": "2021-01-03T18:00:00-05:00",
                "last_timestamp": "2026-03-04T18:59:00-05:00",
                "row_count": 1828857,
            },
            {
                "symbol": "ES",
                "timeframe": "1m",
                "normalized_csv_path": "data/databento/bars/es_minute.csv",
                "first_timestamp": "2021-01-03T18:00:00-05:00",
                "last_timestamp": "2026-03-04T18:59:00-05:00",
                "row_count": 1828489,
            },
        ]
    }


def make_validation_manifest() -> dict:
    return {
        "validations": [
            {
                "recorded_at": "2026-03-23T20:11:15.798292+00:00",
                "spec_key": "daily_bias_framework",
                "chart_symbol": "CME_MINI:NQM2026",
                "validation_status": "compiled_on_chart",
            }
        ]
    }


def make_market_map() -> dict:
    return {
        "case_overrides": [
            {
                "case_ref": "case_manual",
                "symbol": "ES",
                "anchor_timestamp": "2026-03-03T09:30:00-05:00",
                "window_minutes_before": 180,
                "window_minutes_after": 240,
                "mapping_provenance": "case_manual",
                "notes": "Confirmed manually from teacher screenshot and replay.",
            }
        ]
    }


class ResolveMarketContextTests(unittest.TestCase):
    def test_case_override_takes_precedence_and_marks_fully_aligned(self) -> None:
        bars_lookup = etvd.index_bars_manifest(make_bars_manifest())
        validation_defaults = etvd.build_trade_model_defaults_from_validation(
            make_validation_manifest(),
            bars_lookup,
        )
        override_lookup = etvd.index_case_overrides(make_market_map())

        market_context = etvd.resolve_market_context(
            make_case_packet_report()["case_packets"][0],
            bars_lookup=bars_lookup,
            case_override_lookup=override_lookup,
            trade_model_defaults=validation_defaults,
        )

        self.assertEqual(market_context["alignment_status"], "fully_aligned")
        self.assertEqual(market_context["symbol"], "ES")
        self.assertEqual(market_context["mapping_provenance"], "case_manual")
        self.assertEqual(market_context["bars_path"], "data/databento/bars/es_minute.csv")
        self.assertEqual(market_context["anchor_timestamp"], "2026-03-03T09:30:00-05:00")
        self.assertEqual(market_context["window_minutes_before"], 180)

    def test_trade_model_validation_proxy_maps_when_no_case_override_exists(self) -> None:
        bars_lookup = etvd.index_bars_manifest(make_bars_manifest())
        validation_defaults = etvd.build_trade_model_defaults_from_validation(
            make_validation_manifest(),
            bars_lookup,
        )

        market_context = etvd.resolve_market_context(
            make_case_packet_report()["case_packets"][1],
            bars_lookup=bars_lookup,
            case_override_lookup={},
            trade_model_defaults=validation_defaults,
        )

        self.assertEqual(market_context["alignment_status"], "market_context_only")
        self.assertEqual(market_context["symbol"], "NQ")
        self.assertEqual(market_context["mapping_provenance"], "tradingview_validation_proxy")
        self.assertEqual(market_context["source_chart_symbol"], "CME_MINI:NQM2026")

    def test_unmapped_case_stays_unmapped(self) -> None:
        bars_lookup = etvd.index_bars_manifest(make_bars_manifest())
        validation_defaults = etvd.build_trade_model_defaults_from_validation(
            make_validation_manifest(),
            bars_lookup,
        )

        market_context = etvd.resolve_market_context(
            make_case_packet_report()["case_packets"][2],
            bars_lookup=bars_lookup,
            case_override_lookup={},
            trade_model_defaults=validation_defaults,
        )

        self.assertEqual(market_context["alignment_status"], "unmapped")
        self.assertIsNone(market_context["symbol"])
        self.assertEqual(market_context["mapping_provenance"], "unmapped")


class BuildTeacherVisualDatasetTests(unittest.TestCase):
    def test_rows_only_include_screenshot_backed_checkpoints_and_report_alignment_counts(self) -> None:
        rows, report = etvd.build_teacher_visual_dataset_report(
            make_case_packet_report(),
            bars_manifest=make_bars_manifest(),
            validation_manifest=make_validation_manifest(),
            market_map=make_market_map(),
        )

        self.assertEqual(len(rows), 3)
        self.assertEqual(report["summary"]["row_count"], 3)
        self.assertEqual(report["summary"]["alignment_status_counts"]["fully_aligned"], 1)
        self.assertEqual(report["summary"]["alignment_status_counts"]["market_context_only"], 1)
        self.assertEqual(report["summary"]["alignment_status_counts"]["unmapped"], 1)
        self.assertEqual(report["summary"]["mapped_case_count"], 2)
        self.assertEqual(report["summary"]["skipped_missing_screenshot_count"], 1)

        manual_row = next(row for row in rows if row["case_ref"] == "case_manual")
        proxy_row = next(row for row in rows if row["case_ref"] == "case_proxy")
        unmapped_row = next(row for row in rows if row["case_ref"] == "case_unmapped")

        self.assertEqual(manual_row["market_context"]["symbol"], "ES")
        self.assertEqual(proxy_row["market_context"]["symbol"], "NQ")
        self.assertEqual(unmapped_row["market_context"]["alignment_status"], "unmapped")


if __name__ == "__main__":
    unittest.main()
