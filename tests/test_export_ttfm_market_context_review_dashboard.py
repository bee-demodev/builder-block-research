from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import export_ttfm_market_context_review_dashboard as etmcrd


def make_queue() -> dict:
    return {
        "generated_at": "2026-03-23T21:00:00+00:00",
        "summary": {
            "case_count": 1,
            "alignment_status_counts": {
                "market_context_only": 1,
            },
            "recommended_action_counts": {
                "confirm_anchor_timestamp": 1,
            },
            "source_image_kind_counts": {
                "source_article_image": 1,
            },
        },
        "items": [
            {
                "case_ref": "case_a",
                "topic": "bias",
                "trade_models": ["daily_bias_framework"],
                "relation_types": ["bias_framework"],
                "source_url": "https://example.com/article",
                "alignment_status": "market_context_only",
                "mapping_provenance": "tradingview_validation_proxy",
                "recommended_action": "find_alternate_chart_evidence",
                "source_image_kind": "source_article_image",
                "symbol_suggestion": "NQ",
                "source_chart_symbol": "CME_MINI:NQM2026",
                "bars_path_suggestion": str(ROOT / "data" / "databento" / "bars" / "nq_minute.csv"),
                "anchor_timestamp": None,
                "market_context_notes": "Needs timestamp review.",
                "confidence": 0.35,
                "checkpoint_samples": [
                    {
                        "checkpoint": "context",
                        "timeframe": "higher",
                        "timeframe_role": "htf",
                        "active_labels": ["equilibrium"],
                        "screenshot_path": "artifacts/ttfm/screenshots/case_a/context.png",
                        "annotation_notes": ["Requires visual review."],
                    }
                ],
                "evidence_refs": ["https://example.com/article", "topic:bias"],
                "override_template": {
                    "case_ref": "case_a",
                    "symbol": "NQ",
                    "anchor_timestamp": None,
                    "window_minutes_before": 180,
                    "window_minutes_after": 240,
                    "mapping_provenance": "case_manual",
                    "notes": "Source is still an article image; attach alternate chart evidence before setting anchor_timestamp.",
                },
            }
        ],
    }


class ReviewDashboardTests(unittest.TestCase):
    def test_build_review_dashboard_report_resolves_relative_image_path(self) -> None:
        queue = make_queue()
        html_output = ROOT / "results" / "ttfm_market_context_review_dashboard.html"

        report = etmcrd.build_review_dashboard_report(queue, html_output_path=html_output)

        sample = report["items"][0]["checkpoint_samples"][0]
        self.assertEqual(sample["image_src"], "../artifacts/ttfm/screenshots/case_a/context.png")
        self.assertIn('"case_ref": "case_a"', report["items"][0]["override_template_json"])
        self.assertEqual(report["items"][0]["source_image_kind"], "source_article_image")

    def test_build_override_seed_map_matches_market_context_schema(self) -> None:
        queue = make_queue()

        seed_map = etmcrd.build_override_seed_map(queue)

        self.assertIn("notes", seed_map)
        self.assertEqual(len(seed_map["case_overrides"]), 1)
        self.assertEqual(seed_map["case_overrides"][0]["case_ref"], "case_a")
        self.assertEqual(seed_map["case_overrides"][0]["symbol"], "NQ")
        self.assertIn("find_alternate_chart_evidence", " ".join(seed_map["notes"]))

    def test_write_outputs_persists_dashboard_and_override_pack(self) -> None:
        queue = make_queue()
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            html_output = tmp_root / "dashboard.html"
            override_output = tmp_root / "overrides.json"
            report = etmcrd.build_review_dashboard_report(queue, html_output_path=html_output)
            seed_map = etmcrd.build_override_seed_map(queue)

            etmcrd.write_outputs(
                report,
                seed_map,
                html_output_path=html_output,
                override_output_path=override_output,
            )

            dashboard_html = html_output.read_text(encoding="utf-8")
            override_json = override_output.read_text(encoding="utf-8")

        self.assertIn("case_a", dashboard_html)
        self.assertIn("artifacts/ttfm/screenshots/case_a/context.png", dashboard_html)
        self.assertIn("source_article_image", dashboard_html)
        self.assertIn('"case_ref": "case_a"', override_json)


if __name__ == "__main__":
    unittest.main()
