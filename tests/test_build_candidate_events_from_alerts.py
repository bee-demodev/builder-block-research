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

import build_candidate_events_from_alerts as bcfa


def make_contract() -> dict:
    return {
        "spec_key": "daily_bias_c123_map",
        "trade_model": {
            "slug": "daily_bias_c123_map",
            "name": "Daily Bias C1/C2/C3 Map",
        },
        "alert_titles": ["Hourly sequence activated", "Five minute continuation activated"],
        "rule_state_fields": [
            "activeHourlyDir",
            "activeHourlyC2Time",
            "activeEntryPrice",
            "activeLtfC2Time",
        ],
        "default_event": {
            "profile_slug": "",
            "topic": "",
            "trade_model": "daily_bias_c123_map",
            "relation_type": "execution_model",
            "chart_context": {
                "setup_variant": "daily_bias_c123_map",
                "source_kind": "tradingview_pine_alert",
                "timeframe_scope": ["chart_60", "bias_D", "structure_60", "execution_5"],
                "session_scope": [],
            },
            "annotation": {
                "fired_alert": "",
                "rule_states": {
                    "activeHourlyDir": "",
                    "activeHourlyC2Time": "",
                    "activeEntryPrice": "",
                    "activeLtfC2Time": "",
                },
            },
            "candidate_signal": {
                "timestamp": "",
                "side": "",
                "stop_price": "",
                "target_price": "",
                "quantity": 1.0,
                "session": "",
                "thesis": "",
            },
        },
    }


class BuildCandidateEventsFromAlertsTests(unittest.TestCase):
    def test_build_candidate_event_merges_contract_defaults_with_alert_payload(self) -> None:
        contract = make_contract()
        alert_payload = {
            "case_ref": "tv_alert_case",
            "alert_title": "Hourly sequence activated",
            "topic": "continuation",
            "chart_context": {
                "session_scope": ["new_york"],
            },
            "rule_states": {
                "activeHourlyDir": "bullish",
                "activeHourlyC2Time": "2026-03-23T09:00:00-04:00",
                "activeEntryPrice": "21234.5",
                "activeLtfC2Time": "2026-03-23T09:15:00-04:00",
            },
            "candidate_signal": {
                "timestamp": "2026-03-23T09:00:00-04:00",
                "side": "long",
                "stop_price": 21200.0,
                "target_price": 21320.0,
                "session": "new_york",
                "thesis": "hourly sequence activated inside daily poi",
            },
        }

        event = bcfa.build_candidate_event(contract, alert_payload)

        self.assertEqual(event["case_ref"], "tv_alert_case")
        self.assertEqual(event["trade_model"], "daily_bias_c123_map")
        self.assertEqual(event["relation_type"], "execution_model")
        self.assertEqual(event["annotation"]["fired_alert"], "Hourly sequence activated")
        self.assertEqual(event["annotation"]["rule_states"]["activeHourlyDir"], "bullish")
        self.assertEqual(event["annotation"]["rule_states"]["activeLtfC2Time"], "2026-03-23T09:15:00-04:00")
        self.assertEqual(event["chart_context"]["source_kind"], "tradingview_pine_alert")
        self.assertEqual(event["chart_context"]["session_scope"], ["new_york"])
        self.assertEqual(event["candidate_signal"]["side"], "long")

    def test_build_candidate_event_rejects_unknown_alert_title(self) -> None:
        contract = make_contract()

        with self.assertRaises(ValueError):
            bcfa.build_candidate_event(
                contract,
                {
                    "alert_title": "Unknown alert",
                    "candidate_signal": {
                        "timestamp": "2026-03-23T09:00:00-04:00",
                        "side": "long",
                        "stop_price": 1,
                        "target_price": 2,
                    },
                },
            )

    def test_build_candidate_events_from_alerts_supports_batch_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            contract_path = root / "contract.json"
            alerts_path = root / "alerts.json"

            contract_path.write_text(json.dumps(make_contract()), encoding="utf-8")
            alerts_path.write_text(
                json.dumps(
                    {
                        "alerts": [
                            {
                                "case_ref": "tv_alert_case",
                                "alert_title": "Hourly sequence activated",
                                "candidate_signal": {
                                    "timestamp": "2026-03-23T09:00:00-04:00",
                                    "side": "long",
                                    "stop_price": 21200.0,
                                    "target_price": 21320.0,
                                },
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            payload = bcfa.build_candidate_events_from_alerts(
                contract_path=contract_path,
                alerts_path=alerts_path,
            )

            self.assertEqual(payload["summary"]["alert_count"], 1)
            self.assertEqual(payload["summary"]["candidate_event_count"], 1)
            self.assertEqual(payload["events"][0]["trade_model"], "daily_bias_c123_map")


if __name__ == "__main__":
    unittest.main()
