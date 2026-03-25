from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import export_ttfm_case_packets as etcp


def make_record() -> dict:
    return {
        "profile_slug": "ttrades_curriculum",
        "profile_name": "TTrades Curriculum",
        "profile_type": "teacher_style",
        "topic": "daily_profiles",
        "case_ref": "ttfm_demo_case_001",
        "source_url": "https://example.com/ttfm-demo",
        "notes": "Demo TTFM case",
        "timeframe": "15m",
        "chart_context": {
            "setup_variant": "new_york_reversal_after_london_falls_short",
            "source_kind": "article",
            "session_scope": ["london", "new_york_am"],
            "timeframe_scope": ["higher", "intraday", "lower"],
        },
        "annotation": {
            "point_of_interest": "fair_value_gap_at_key_zone",
            "liquidity_event": "liquidity_sweep_into_key_level",
            "confirmation": "candle_2_closure_then_cisd",
            "invalidation": "beyond_new_york_session_extreme",
            "zone_type": "breaker_retest",
        },
        "outcome": {
            "decision": "trade",
            "reason": "new_york_reversal_profile_execution",
        },
        "annotation_trade_models": [
            {
                "trade_model": "daily_profile_models",
                "relation_type": "session_profile",
                "confidence": 1.0,
            },
            {
                "trade_model": "reversal_sequence_model",
                "relation_type": "execution_model",
                "confidence": 0.95,
            },
        ],
    }


class BuildCasePacketTests(unittest.TestCase):
    def test_build_case_packet_is_timeframe_aware_and_component_rich(self) -> None:
        record = make_record()

        packet = etcp.build_case_packet(record)

        self.assertEqual(packet["framework_slug"], "ttfm")
        self.assertEqual(packet["framework_name"], "TTrades Fractal Model")
        self.assertEqual(packet["timeframe_stack"]["htf"], "higher")
        self.assertEqual(packet["timeframe_stack"]["etf"], "intraday")
        self.assertEqual(packet["timeframe_stack"]["ltf"], "lower")
        self.assertEqual(len(packet["checkpoints"]), 5)
        self.assertEqual(packet["checkpoints"][0]["checkpoint"], "context")
        self.assertEqual(packet["checkpoints"][-1]["checkpoint"], "outcome")
        self.assertIn("fair_value_gap", packet["component_labels"])
        self.assertIn("breaker", packet["component_labels"])
        self.assertIn("point_of_interest", packet["component_labels"])
        self.assertIn("liquidity_sweep", packet["component_labels"])
        self.assertIn("candle_2_closure", packet["component_labels"])

    def test_build_case_packet_merges_screenshots_and_anchor_labels(self) -> None:
        record = make_record()
        screenshot_manifest = {
            "attachments": [
                {
                    "case_ref": "ttfm_demo_case_001",
                    "checkpoint": "context",
                    "screenshot_path": "artifacts/ttfm/demo/context.png",
                    "annotation_notes": ["HTF POI marked"],
                    "zone_geometry": {"kind": "box", "timeframe": "higher"},
                    "evidence_refs": ["topics/equilibrium/rulebook.json#eq"],
                },
                {
                    "case_ref": "ttfm_demo_case_001",
                    "checkpoint": "confirmation",
                    "screenshot_path": "artifacts/ttfm/demo/confirmation.png",
                    "annotation_notes": ["Closure confirmed"],
                    "evidence_refs": ["topics/candle_2_closure/examples.md#demo"],
                },
            ]
        }
        anchor_label_manifest = {
            "labels": [
                {
                    "case_ref": "ttfm_demo_case_001",
                    "checkpoint": "context",
                    "provenance": "anchor_manual",
                    "labels": ["point_of_interest", "equilibrium"],
                },
                {
                    "case_ref": "ttfm_demo_case_001",
                    "checkpoint": "confirmation",
                    "provenance": "model_corrected",
                    "labels": ["protected_swing", "candle_2_closure"],
                },
            ]
        }

        packet = etcp.build_case_packet(
            record,
            screenshot_manifest=screenshot_manifest,
            anchor_label_manifest=anchor_label_manifest,
        )

        context_checkpoint = next(
            checkpoint
            for checkpoint in packet["checkpoints"]
            if checkpoint["checkpoint"] == "context"
        )
        confirmation_checkpoint = next(
            checkpoint
            for checkpoint in packet["checkpoints"]
            if checkpoint["checkpoint"] == "confirmation"
        )

        self.assertEqual(context_checkpoint["screenshot_status"], "attached")
        self.assertEqual(
            context_checkpoint["screenshot_path"],
            "artifacts/ttfm/demo/context.png",
        )
        self.assertEqual(context_checkpoint["active_label_provenance"], "anchor_manual")
        self.assertEqual(
            context_checkpoint["expected_component_labels"],
            ["equilibrium", "point_of_interest"],
        )
        self.assertEqual(
            context_checkpoint["labels_by_provenance"]["anchor_manual"],
            ["equilibrium", "point_of_interest"],
        )
        self.assertEqual(context_checkpoint["annotation_notes"], ["HTF POI marked"])
        self.assertEqual(context_checkpoint["zone_geometry"]["kind"], "box")
        self.assertGreaterEqual(len(context_checkpoint["evidence_refs"]), 1)

        self.assertEqual(confirmation_checkpoint["active_label_provenance"], "model_corrected")
        self.assertEqual(
            confirmation_checkpoint["expected_component_labels"],
            ["candle_2_closure", "protected_swing"],
        )
        self.assertIn("protected_swing", packet["component_labels"])


class SummarizeCasePacketsTests(unittest.TestCase):
    def test_summary_reports_timeframe_coverage_and_screenshot_gaps(self) -> None:
        summary = etcp.summarize_case_packets(
            [
                etcp.build_case_packet(make_record()),
                etcp.build_case_packet(
                    {
                        **make_record(),
                        "case_ref": "ttfm_demo_case_002",
                        "chart_context": {
                            "setup_variant": "equilibrium_hold_trend_resumption",
                            "source_kind": "article",
                            "timeframe_scope": ["higher", "lower"],
                        },
                        "annotation": {
                            "point_of_interest": "equilibrium",
                            "confirmation": "protected_swing_after_close_through_series",
                        },
                        "annotation_trade_models": [
                            {
                                "trade_model": "continuation_entry_model",
                                "relation_type": "execution_model",
                                "confidence": 1.0,
                            }
                        ],
                    }
                ),
            ]
        )

        self.assertEqual(summary["case_count"], 2)
        self.assertEqual(summary["checkpoint_count"], 10)
        self.assertEqual(summary["framework_slug"], "ttfm")
        self.assertGreater(summary["multi_timeframe_case_ratio"], 0.0)
        self.assertEqual(summary["missing_screenshot_count"], 10)
        self.assertIn("candle_2_closure", summary["component_counts"])
        self.assertIn("point_of_interest", summary["component_counts"])

    def test_summary_reports_anchor_and_screenshot_coverage(self) -> None:
        screenshot_manifest = {
            "attachments": [
                {
                    "case_ref": "ttfm_demo_case_001",
                    "checkpoint": "context",
                    "screenshot_path": "artifacts/ttfm/demo/context.png",
                }
            ]
        }
        anchor_label_manifest = {
            "labels": [
                {
                    "case_ref": "ttfm_demo_case_001",
                    "checkpoint": "context",
                    "provenance": "anchor_manual",
                    "labels": ["point_of_interest"],
                }
            ]
        }

        packet = etcp.build_case_packet(
            make_record(),
            screenshot_manifest=screenshot_manifest,
            anchor_label_manifest=anchor_label_manifest,
        )
        summary = etcp.summarize_case_packets([packet])

        self.assertAlmostEqual(summary["screenshot_coverage"], 0.2, places=4)
        self.assertAlmostEqual(summary["anchor_coverage"], 0.2, places=4)
        self.assertEqual(summary["missing_anchor_label_count"], 4)
        self.assertEqual(summary["active_label_provenance_counts"]["anchor_manual"], 1)
        self.assertIn("evidence_refs", summary["remaining_missing_evidence_counts"])


if __name__ == "__main__":
    unittest.main()
