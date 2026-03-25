from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import model_assisted_backtest as mab
import train_narrow_pattern_net as tnpn
from runtime.harness import CostModel


def build_demo_model(output_dir: Path) -> Path:
    prepared = {
        "task_name": "continuation_entry_model",
        "positive_label": "continuation_entry_model",
        "negative_label": "other_trade_models",
        "examples": [
            {
                "example_id": "p1",
                "text": "profile trader | topic continuation | trade model continuation_entry_model | relation execution_model | setup equilibrium hold trend resumption | context fractal lower trend continuation | annotation equilibrium respect protected swing",
                "label": 1,
            },
            {
                "example_id": "p2",
                "text": "profile trader | topic continuation | trade model continuation_entry_model | relation execution_model | setup order block retest | context intraday continuation displacement | annotation protected swing confirmation",
                "label": 1,
            },
            {
                "example_id": "p3",
                "text": "profile trader | topic continuation | trade model continuation_entry_model | relation execution_model | setup breaker block retest | context higher intraday continuation | annotation sweep and cisd confirmation",
                "label": 1,
            },
            {
                "example_id": "p4",
                "text": "profile trader | topic continuation | trade model continuation_entry_model | relation execution_model | setup top down aligned continuation | context higher lower continuation alignment | annotation equilibrium hold and continuation",
                "label": 1,
            },
            {
                "example_id": "n1",
                "text": "profile trader | topic reversal | trade model reversal_sequence_model | relation execution_model | setup reversal day rejection | context choppy reversal | annotation no continuation",
                "label": 0,
            },
            {
                "example_id": "n2",
                "text": "profile trader | topic bias | trade model daily_bias_framework | relation bias_framework | setup daily bias framework | context higher lower bias | annotation not an entry model",
                "label": 0,
            },
            {
                "example_id": "n3",
                "text": "profile trader | topic continuation | trade model daily_profile_models | relation session_profile | setup session context only | context new york profile | annotation no trigger",
                "label": 0,
            },
            {
                "example_id": "n4",
                "text": "profile trader | topic continuation | trade model fractal_closure_model | relation confirmation_framework | setup confirmation only | context fractal closure | annotation confirmation without entry",
                "label": 0,
            },
        ],
        "skipped_example_ids": [],
    }

    report = tnpn.train_task_classifier(
        prepared,
        output_dir=output_dir,
        device_preference="cpu",
        validation_ratio=0.25,
        epochs=16,
        learning_rate=0.04,
        seed=11,
    )
    return Path(report["model_path"])


class ModelAssistedBacktestTests(unittest.TestCase):
    def test_build_model_assisted_backtest_routes_accepted_signals_into_harness(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            model_path = build_demo_model(root)
            bars_path = root / "bars.csv"
            states_path = root / "states.json"

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
            states_path.write_text(
                json.dumps(
                    {
                        "states": [
                            {
                                "case_ref": "accepted_case",
                                "profile_slug": "ttrades_curriculum",
                                "topic": "continuation",
                                "trade_model": "continuation_entry_model",
                                "relation_type": "execution_model",
                                "chart_context": {
                                    "setup_variant": "equilibrium_hold_trend_resumption",
                                    "source_kind": "live_bridge",
                                    "timeframe_scope": ["fractal", "lower"],
                                },
                                "annotation": {
                                    "anchor_type": "equilibrium_half_range_respect",
                                    "confirmation": ["protected_swing", "candle_3_closure"],
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
                            },
                            {
                                "case_ref": "rejected_case",
                                "profile_slug": "ttrades_curriculum",
                                "topic": "bias",
                                "trade_model": "daily_bias_framework",
                                "relation_type": "bias_framework",
                                "chart_context": {
                                    "setup_variant": "daily_bias_only",
                                    "source_kind": "live_bridge",
                                    "timeframe_scope": ["higher"],
                                },
                                "annotation": {
                                    "anchor_type": "daily_range_midpoint",
                                    "confirmation": ["bias_only"],
                                },
                                "candidate_signal": {
                                    "timestamp": "2026-03-22T09:30:00-04:00",
                                    "side": "long",
                                    "stop_price": 98.0,
                                    "target_price": 104.0,
                                    "quantity": 1.0,
                                    "session": "new_york",
                                    "thesis": "bias only setup",
                                },
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )

            analysis = mab.build_model_assisted_backtest(
                bars_path=bars_path,
                states_path=states_path,
                model_path=model_path,
                threshold=0.5,
                device_preference="cpu",
                cost_model=CostModel(tick_size=0.25, spread_ticks=0.0, slippage_ticks=0.0),
                session_mode="new_york",
            )

            self.assertEqual(analysis["scoring"]["accepted_signal_count"], 1)
            self.assertEqual(analysis["signals"]["signals"][0]["model_task"], "continuation_entry_model")
            self.assertEqual(analysis["backtest"]["summary"]["trade_count"], 1)
            self.assertEqual(analysis["backtest"]["trades"][0]["exit_reason"], "target")

    def test_build_model_assisted_backtest_can_build_states_from_candidate_events(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            model_path = build_demo_model(root)
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
                                "case_ref": "accepted_case",
                                "profile_slug": "ttrades_curriculum",
                                "topic": "continuation",
                                "trade_model": "continuation_entry_model",
                                "relation_type": "execution_model",
                                "setup_variant": "equilibrium_hold_trend_resumption",
                                "timeframe_scope": ["fractal", "lower"],
                                "session_scope": ["new_york"],
                                "rule_states": {
                                    "entryReadyState": "ready",
                                    "protectedSwingState": "confirmed",
                                },
                                "annotation": {
                                    "anchor_type": "equilibrium_half_range_respect",
                                    "confirmation": ["protected_swing", "candle_3_closure"],
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
                            },
                            {
                                "case_ref": "rejected_case",
                                "profile_slug": "ttrades_curriculum",
                                "topic": "bias",
                                "trade_model": "daily_bias_framework",
                                "relation_type": "bias_framework",
                                "setup_variant": "daily_bias_only",
                                "timeframe_scope": ["higher"],
                                "session_scope": ["new_york"],
                                "rule_states": {
                                    "entryReadyState": "blocked",
                                },
                                "annotation": {
                                    "anchor_type": "daily_range_midpoint",
                                    "confirmation": ["bias_only"],
                                },
                                "candidate_signal": {
                                    "timestamp": "2026-03-22T09:30:00-04:00",
                                    "side": "long",
                                    "stop_price": 98.0,
                                    "target_price": 104.0,
                                    "quantity": 1.0,
                                    "session": "new_york",
                                    "thesis": "bias only setup",
                                },
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )

            analysis = mab.build_model_assisted_backtest(
                bars_path=bars_path,
                candidate_events_path=events_path,
                model_path=model_path,
                threshold=0.5,
                device_preference="cpu",
                cost_model=CostModel(tick_size=0.25, spread_ticks=0.0, slippage_ticks=0.0),
                session_mode="new_york",
                warmup_bars=1,
            )

            self.assertEqual(analysis["state_batch"]["source"], "candidate_events")
            self.assertEqual(analysis["state_batch"]["summary"]["emitted_state_count"], 2)
            self.assertEqual(analysis["scoring"]["accepted_signal_count"], 1)
            self.assertEqual(analysis["backtest"]["summary"]["trade_count"], 1)


if __name__ == "__main__":
    unittest.main()
