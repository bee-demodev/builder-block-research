from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import build_daily_bias_c123_spec as bdcs
import refresh_daily_bias_c123_rulepack as rdcr


def make_hits() -> dict[str, list[dict]]:
    return {
        "daily_bias": [
            {
                "chunk_id": "fractal_model_fundamentals:0000",
                "video_id": "TNybDCtwBnc",
                "title": "Fractal Model Fundamentals",
                "start": 72.16,
                "end": 109.20,
                "text": "Identify a daily bias before dropping to the hourly timeframe.",
                "topics": ["daily_bias"],
                "score": 0.92,
            }
        ],
        "daily_poi": [
            {
                "chunk_id": "easy_daily_bias_mechanical_framework:0003",
                "video_id": "-KKuZb5Z5aU",
                "title": "Easy Daily Bias - Mechanical Framework",
                "start": 200.239,
                "end": 269.36,
                "text": "Mark the previous day range and equilibrium, then look for price to trade into that daily area before the hourly setup forms.",
                "topics": ["daily_bias", "equilibrium", "poi"],
                "score": 0.9,
            }
        ],
        "hourly_sequence": [
            {
                "chunk_id": "fractal_model_fundamentals:0001",
                "video_id": "TNybDCtwBnc",
                "title": "Fractal Model Fundamentals",
                "start": 5.49,
                "end": 87.44,
                "text": "Candle 2 is the swing point. Candle 3 follows Candle 2.",
                "topics": ["candle_2", "candle_3"],
                "score": 0.88,
            }
        ],
        "daily_to_hourly_gating": [
            {
                "chunk_id": "cisd_validates_swing_points:0003",
                "video_id": "vn1RYjhJUnQ",
                "title": "CISD Validates Swing Points",
                "start": 33.0,
                "end": 61.0,
                "text": "Lower timeframe confirmation validates the swing once higher timeframe context exists.",
                "topics": ["cisd", "swing_validation"],
                "score": 0.85,
            }
        ],
    }


class BuildDailyBiasC123RulepackTests(unittest.TestCase):
    def test_rulepack_contains_canonical_sections_and_citations(self) -> None:
        rulepack = rdcr.build_rulepack(make_hits())

        self.assertEqual(rulepack["trade_model"]["slug"], "daily_bias_c123_map")
        self.assertEqual(rulepack["source_priority"]["primary"], "videos")
        self.assertIn("daily_bias_rules", rulepack)
        self.assertIn("daily_poi_rules", rulepack)
        self.assertIn("hourly_sequence_rules", rulepack)
        self.assertIn("lower_timeframe_refinement_rules", rulepack)
        self.assertIn("gating_rules", rulepack)
        self.assertIn("entry_guidance", rulepack["hourly_sequence_rules"])
        self.assertIn("waiting_guidance", rulepack["hourly_sequence_rules"])
        self.assertIn("entry_guidance", rulepack["lower_timeframe_refinement_rules"])
        self.assertGreaterEqual(len(rulepack["daily_bias_rules"]["citations"]), 1)
        self.assertIn("chunk_id", rulepack["daily_bias_rules"]["citations"][0])

    def test_indicator_spec_is_scoped_to_daily_bias_hourly_structure_and_five_minute_refinement(self) -> None:
        spec = bdcs.build_indicator_spec(rdcr.build_rulepack(make_hits()))

        self.assertEqual(spec["trade_model"]["slug"], "daily_bias_c123_map")
        self.assertEqual(spec["implementation_scope"]["target_language"], "pine")
        self.assertEqual(spec["timeframe_contract"]["chart"], "60")
        self.assertEqual(spec["timeframe_contract"]["bias"], "D")
        self.assertEqual(spec["timeframe_contract"]["structure"], "60")
        self.assertEqual(spec["timeframe_contract"]["execution"], "5")
        self.assertIn("5m continuation refinement", spec["implementation_summary"])
        self.assertIn("daily_poi_rules", spec["sequence_contract"])
        self.assertIn("entry_guidance", spec["sequence_contract"]["hourly_sequence_rules"])
        self.assertIn("lower_timeframe_refinement_rules", spec["sequence_contract"])
        self.assertIn("waiting_guidance", spec["sequence_contract"]["hourly_sequence_rules"])
        self.assertIn(
            "Entry guide appears at the open of hourly Candle 3 when the sequence activates.",
            spec["acceptance_checks"],
        )
        self.assertIn(
            "Five-minute continuation confirmation is derived only after the hourly sequence activates and is emitted through rule states or alerts rather than a second on-chart candle map.",
            spec["acceptance_checks"],
        )
        self.assertIn(
            "When no hourly sequence is active, a single waiting cue shows the next Candle 2 direction to watch for inside the daily POI.",
            spec["acceptance_checks"],
        )


if __name__ == "__main__":
    unittest.main()
