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

import export_replay_state_batch as ersb


class ExportReplayStateBatchTests(unittest.TestCase):
    def test_build_state_batch_from_events_enriches_replay_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            bars_path = root / "bars.csv"
            events_path = root / "events.json"

            bars_path.write_text(
                "\n".join(
                    [
                        "timestamp,open,high,low,close,session",
                        "2026-03-22T09:30:00-04:00,99,100,98,99.5,new_york",
                        "2026-03-22T09:35:00-04:00,100,101,99.5,100.5,new_york",
                        "2026-03-22T09:40:00-04:00,101,104.5,100,104,new_york",
                    ]
                ),
                encoding="utf-8",
            )
            events_path.write_text(
                json.dumps(
                    {
                        "events": [
                            {
                                "case_ref": "continuation_ready_case",
                                "profile_slug": "ttrades_curriculum",
                                "topic": "continuation",
                                "trade_model": "continuation_entry_model",
                                "relation_type": "execution_model",
                                "setup_variant": "equilibrium_hold_trend_resumption",
                                "timeframe_scope": ["fractal", "lower"],
                                "session_scope": ["new_york"],
                                "rule_states": {
                                    "entryReadyState": "ready",
                                    "higherTimeframeBiasState": "bullish",
                                    "protectedSwingState": "confirmed",
                                },
                                "annotation": {
                                    "anchor_type": "equilibrium_half_range_respect",
                                },
                                "candidate_signal": {
                                    "timestamp": "2026-03-22T09:30:00-04:00",
                                    "side": "long",
                                    "stop_price": 98.0,
                                    "target_price": 104.0,
                                    "quantity": 1.0,
                                    "session": "new_york",
                                    "thesis": "continuation setup",
                                },
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            payload = ersb.build_state_batch_from_events(
                bars_path=bars_path,
                candidate_events_path=events_path,
                warmup_bars=1,
                session_mode="new_york",
            )

            self.assertEqual(payload["summary"]["event_count"], 1)
            self.assertEqual(payload["summary"]["emitted_state_count"], 1)
            state = payload["states"][0]
            self.assertEqual(state["chart_context"]["source_kind"], "runtime_replay")
            self.assertEqual(state["chart_context"]["replay_window"]["visible_bar_count"], 1)
            self.assertEqual(state["annotation"]["rule_states"]["entryReadyState"], "ready")
            self.assertEqual(state["annotation"]["replay_observation"]["session_bucket"], "new_york")
            self.assertEqual(state["candidate_signal"]["side"], "long")

    def test_build_state_batch_from_events_reports_missing_frames(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            bars_path = root / "bars.csv"
            events_path = root / "events.json"

            bars_path.write_text(
                "\n".join(
                    [
                        "timestamp,open,high,low,close,session",
                        "2026-03-22T09:30:00-04:00,99,100,98,99.5,new_york",
                    ]
                ),
                encoding="utf-8",
            )
            events_path.write_text(
                json.dumps(
                    {
                        "events": [
                            {
                                "case_ref": "missing_case",
                                "profile_slug": "ttrades_curriculum",
                                "topic": "continuation",
                                "trade_model": "continuation_entry_model",
                                "relation_type": "execution_model",
                                "candidate_signal": {
                                    "timestamp": "2026-03-22T09:35:00-04:00",
                                    "side": "long",
                                    "stop_price": 98.0,
                                    "target_price": 104.0,
                                },
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            payload = ersb.build_state_batch_from_events(
                bars_path=bars_path,
                candidate_events_path=events_path,
                warmup_bars=1,
                session_mode="new_york",
            )

            self.assertEqual(payload["summary"]["event_count"], 1)
            self.assertEqual(payload["summary"]["emitted_state_count"], 0)
            self.assertEqual(payload["summary"]["missing_frame_count"], 1)
            self.assertEqual(payload["summary"]["missing_case_refs"], ["missing_case"])


if __name__ == "__main__":
    unittest.main()
