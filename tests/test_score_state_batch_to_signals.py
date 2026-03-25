from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import score_state_batch_to_signals as ssbts
import train_narrow_pattern_net as tnpn


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


class ScoreStateBatchToSignalsTests(unittest.TestCase):
    def test_batch_scoring_collects_only_accepted_signals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            model_path = build_demo_model(Path(tmp_dir))
            states = [
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
                        "timestamp": "2026-03-23T09:35:00-04:00",
                        "side": "long",
                        "stop_price": 99.0,
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
                        "timestamp": "2026-03-23T09:40:00-04:00",
                        "side": "long",
                        "stop_price": 99.0,
                        "target_price": 104.0,
                        "quantity": 1.0,
                        "session": "new_york",
                        "thesis": "bias only setup",
                    },
                },
            ]

            result = ssbts.score_states_to_signals(
                states,
                model_path=model_path,
                device_preference="cpu",
                threshold=0.5,
            )

            self.assertEqual(result["state_count"], 2)
            self.assertEqual(result["accepted_signal_count"], 1)
            self.assertEqual(len(result["signals"]), 1)
            self.assertEqual(result["signals"][0]["model_task"], "continuation_entry_model")
            self.assertEqual(result["scores"][0]["case_ref"], "accepted_case")
            self.assertTrue(result["scores"][0]["prediction"])
            self.assertFalse(result["scores"][1]["prediction"])


if __name__ == "__main__":
    unittest.main()
