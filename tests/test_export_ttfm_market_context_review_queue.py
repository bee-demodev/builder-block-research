from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import export_ttfm_market_context_review_queue as etmcrq


def make_teacher_rows() -> list[dict]:
    return [
        {
            "case_ref": "case_proxy",
            "topic": "bias",
            "trade_models": ["daily_bias_framework"],
            "relation_types": ["bias_framework"],
            "checkpoint": "context",
            "timeframe": "higher",
            "timeframe_role": "htf",
            "active_labels": ["equilibrium"],
            "source_url": "https://example.com/proxy",
            "screenshot_path": "artifacts/ttfm/case_proxy/context.png",
            "annotation_notes": ["proxy context"],
            "evidence_refs": ["https://example.com/proxy"],
            "market_context": {
                "alignment_status": "market_context_only",
                "mapping_provenance": "tradingview_validation_proxy",
                "symbol": "NQ",
                "bars_path": "data/databento/bars/nq_minute.csv",
                "source_chart_symbol": "CME_MINI:NQM2026",
                "source_spec_key": "daily_bias_framework",
                "anchor_timestamp": None,
                "window_minutes_before": None,
                "window_minutes_after": None,
                "confidence": 0.35,
                "notes": "Proxy match from TradingView validation.",
            },
        },
        {
            "case_ref": "case_proxy",
            "topic": "bias",
            "trade_models": ["daily_bias_framework"],
            "relation_types": ["bias_framework"],
            "checkpoint": "confirmation",
            "timeframe": "lower",
            "timeframe_role": "ltf",
            "active_labels": ["equilibrium"],
            "source_url": "https://example.com/proxy",
            "screenshot_path": "artifacts/ttfm/case_proxy/confirmation.png",
            "annotation_notes": ["proxy confirm"],
            "evidence_refs": ["https://example.com/proxy"],
            "market_context": {
                "alignment_status": "market_context_only",
                "mapping_provenance": "tradingview_validation_proxy",
                "symbol": "NQ",
                "bars_path": "data/databento/bars/nq_minute.csv",
                "source_chart_symbol": "CME_MINI:NQM2026",
                "source_spec_key": "daily_bias_framework",
                "anchor_timestamp": None,
                "window_minutes_before": None,
                "window_minutes_after": None,
                "confidence": 0.35,
                "notes": "Proxy match from TradingView validation.",
            },
        },
        {
            "case_ref": "case_unmapped",
            "topic": "continuation",
            "trade_models": ["continuation_entry_model"],
            "relation_types": ["execution_model"],
            "checkpoint": "context",
            "timeframe": "higher",
            "timeframe_role": "htf",
            "active_labels": ["point_of_interest"],
            "source_url": "https://example.com/unmapped",
            "screenshot_path": "artifacts/ttfm/case_unmapped/context.png",
            "annotation_notes": ["needs symbol"],
            "evidence_refs": ["https://example.com/unmapped"],
            "market_context": {
                "alignment_status": "unmapped",
                "mapping_provenance": "unmapped",
                "symbol": None,
                "bars_path": None,
                "source_chart_symbol": None,
                "source_spec_key": None,
                "anchor_timestamp": None,
                "window_minutes_before": None,
                "window_minutes_after": None,
                "confidence": None,
                "notes": "No market mapping yet.",
            },
        },
    ]


class BuildReviewQueueTests(unittest.TestCase):
    def test_build_review_queue_groups_rows_by_case_and_sets_actions(self) -> None:
        queue = etmcrq.build_market_context_review_queue(make_teacher_rows())

        self.assertEqual(queue["summary"]["case_count"], 2)
        self.assertEqual(queue["summary"]["alignment_status_counts"]["market_context_only"], 1)
        self.assertEqual(queue["summary"]["alignment_status_counts"]["unmapped"], 1)
        self.assertEqual(queue["summary"]["recommended_action_counts"]["confirm_anchor_timestamp"], 1)
        self.assertEqual(
            queue["summary"]["recommended_action_counts"]["identify_symbol_and_anchor_timestamp"],
            1,
        )
        self.assertEqual(queue["summary"]["source_image_kind_counts"]["unknown"], 2)

        items_by_case = {item["case_ref"]: item for item in queue["items"]}
        proxy_item = items_by_case["case_proxy"]
        unmapped_item = items_by_case["case_unmapped"]

        self.assertEqual(proxy_item["recommended_action"], "confirm_anchor_timestamp")
        self.assertEqual(proxy_item["symbol_suggestion"], "NQ")
        self.assertEqual(proxy_item["source_chart_symbol"], "CME_MINI:NQM2026")
        self.assertEqual(len(proxy_item["checkpoint_samples"]), 2)
        self.assertEqual(proxy_item["source_image_kind"], "unknown")
        self.assertEqual(
            proxy_item["override_template"]["symbol"],
            "NQ",
        )
        self.assertEqual(
            proxy_item["override_template"]["mapping_provenance"],
            "case_manual",
        )
        self.assertEqual(proxy_item["override_template"]["notes"], "")

        self.assertEqual(unmapped_item["recommended_action"], "identify_symbol_and_anchor_timestamp")
        self.assertIsNone(unmapped_item["symbol_suggestion"])
        self.assertEqual(len(unmapped_item["checkpoint_samples"]), 1)
        self.assertIsNone(unmapped_item["override_template"]["symbol"])

    def test_source_article_images_are_flagged_for_alternate_chart_evidence(self) -> None:
        rows = make_teacher_rows()
        rows[0]["annotation_notes"] = ["Bootstrapped from source article image hero.png; requires visual review before anchor promotion."]
        rows[1]["annotation_notes"] = ["Bootstrapped from source article image detail.png; requires visual review before anchor promotion."]

        queue = etmcrq.build_market_context_review_queue(rows)
        proxy_item = {item["case_ref"]: item for item in queue["items"]}["case_proxy"]

        self.assertEqual(proxy_item["source_image_kind"], "source_article_image")
        self.assertEqual(proxy_item["recommended_action"], "find_alternate_chart_evidence")
        self.assertIn("alternate chart evidence", proxy_item["override_template"]["notes"])
        self.assertEqual(
            queue["summary"]["source_image_kind_counts"]["source_article_image"],
            1,
        )


if __name__ == "__main__":
    unittest.main()
