from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import sync_ttfm_market_context_map as stmcm


class MergeMarketContextMapTests(unittest.TestCase):
    def test_merge_market_context_map_updates_existing_case_and_adds_new_case(self) -> None:
        existing_map = {
            "notes": ["keep existing notes"],
            "case_overrides": [
                {
                    "case_ref": "case_a",
                    "symbol": "ES",
                    "anchor_timestamp": "2026-03-03T09:30:00-05:00",
                    "window_minutes_before": 180,
                    "window_minutes_after": 240,
                    "mapping_provenance": "case_manual",
                    "notes": "existing note",
                }
            ],
        }
        source_overrides = [
            {
                "case_ref": "case_a",
                "symbol": "NQ",
                "anchor_timestamp": "",
                "window_minutes_before": 120,
                "window_minutes_after": 180,
                "mapping_provenance": "case_manual",
                "notes": "",
            },
            {
                "case_ref": "case_b",
                "symbol": "GC",
                "anchor_timestamp": "2026-03-04T10:15:00-05:00",
                "window_minutes_before": 180,
                "window_minutes_after": 240,
                "mapping_provenance": "case_manual",
                "notes": "new case",
            },
        ]

        merged = stmcm.merge_market_context_map(existing_map, source_overrides)

        self.assertEqual(merged["notes"], ["keep existing notes"])
        self.assertEqual(len(merged["case_overrides"]), 2)
        case_a = merged["case_overrides"][0]
        case_b = merged["case_overrides"][1]
        self.assertEqual(case_a["case_ref"], "case_a")
        self.assertEqual(case_a["symbol"], "NQ")
        self.assertEqual(case_a["anchor_timestamp"], "2026-03-03T09:30:00-05:00")
        self.assertEqual(case_a["notes"], "existing note")
        self.assertEqual(case_b["case_ref"], "case_b")
        self.assertEqual(case_b["symbol"], "GC")

    def test_normalize_override_skips_empty_template_rows(self) -> None:
        normalized = stmcm.normalize_override(
            {
                "case_ref": "case_empty",
                "symbol": "",
                "anchor_timestamp": "",
                "notes": "",
            }
        )

        self.assertIsNone(normalized)

    def test_write_market_context_map_persists_json(self) -> None:
        payload = {
            "notes": ["note"],
            "case_overrides": [{"case_ref": "case_a", "symbol": "NQ"}],
        }
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "market_context_map.json"
            stmcm.write_market_context_map(payload, output_path)
            written = output_path.read_text(encoding="utf-8")

        self.assertIn('"case_ref": "case_a"', written)
        self.assertIn('"notes": [', written)


if __name__ == "__main__":
    unittest.main()
