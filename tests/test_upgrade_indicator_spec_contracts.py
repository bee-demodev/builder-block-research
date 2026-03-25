from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import upgrade_indicator_spec_contracts as uisc


def make_spec() -> dict:
    return {
        "trade_model": {
            "slug": "daily_bias_framework",
            "name": "Daily Bias Framework",
        },
        "trader_profile": {
            "slug": "ttrades_curriculum",
        },
        "artifact_path": "results/indicator_specs/daily_bias_framework.json",
        "input_groups": [
            {
                "group": "Existing Inputs",
                "inputs": [
                    {
                        "key": "existingToggle",
                        "type": "bool",
                        "default": True,
                        "description": "Existing input that should be preserved.",
                    }
                ],
            }
        ],
        "acceptance_checks": [
            "The script must stay bar-close confirmed and avoid unbounded multi-timeframe requests."
        ],
    }


class ApplyBacktestContractTests(unittest.TestCase):
    def test_apply_backtest_contract_adds_cost_model_inputs_and_acceptance_checks(self) -> None:
        upgraded = uisc.apply_backtest_contract(make_spec())

        self.assertIn("backtest_contract", upgraded)
        self.assertEqual(
            upgraded["backtest_contract"]["transaction_cost_model"]["spread_ticks"],
            1.0,
        )
        self.assertEqual(
            upgraded["backtest_contract"]["transaction_cost_model"]["slippage_ticks"],
            0.5,
        )
        self.assertEqual(
            upgraded["backtest_contract"]["transaction_cost_model"]["commission_per_contract"],
            2.5,
        )

        group_names = [group["group"] for group in upgraded["input_groups"]]
        self.assertIn("Backtest Contract", group_names)

        cost_input_keys = {
            item["key"]
            for group in upgraded["input_groups"]
            if group["group"] == "Backtest Contract"
            for item in group["inputs"]
        }
        self.assertTrue(
            {
                "backtestTickSize",
                "backtestSpreadTicks",
                "backtestSlippageTicks",
                "backtestCommissionPerContract",
            }.issubset(cost_input_keys)
        )
        self.assertTrue(
            any("spread, slippage, commission" in check.lower() for check in upgraded["acceptance_checks"])
        )
        self.assertTrue(
            any("stop and target touch in the same bar" in check.lower() for check in upgraded["acceptance_checks"])
        )


class PromoteStatusFromValidationsTests(unittest.TestCase):
    def test_successful_tradingview_validation_promotes_draft_to_reviewed(self) -> None:
        validations = [
            {
                "spec_key": "daily_bias_framework",
                "validation_status": "blocked_monaco_sync",
                "recorded_at": "2026-03-22T19:46:57.991303+00:00",
            },
            {
                "spec_key": "daily_bias_framework",
                "validation_status": "added_to_chart",
                "validation_method": "playwriter",
                "recorded_at": "2026-03-22T20:26:25.692440+00:00",
            },
        ]

        promoted_status, evidence = uisc.promote_status_from_validations("draft", validations)

        self.assertEqual(promoted_status, "reviewed")
        self.assertEqual(evidence["validation_status"], "added_to_chart")
        self.assertEqual(evidence["validation_method"], "playwriter")

    def test_failed_validation_does_not_promote_status(self) -> None:
        validations = [
            {
                "spec_key": "daily_bias_framework",
                "validation_status": "blocked_monaco_sync",
                "recorded_at": "2026-03-22T19:46:57.991303+00:00",
            }
        ]

        promoted_status, evidence = uisc.promote_status_from_validations("draft", validations)

        self.assertEqual(promoted_status, "draft")
        self.assertIsNone(evidence)


class ApplyStatusMarkersTests(unittest.TestCase):
    def test_apply_status_markers_keeps_translation_stage_in_sync(self) -> None:
        spec = make_spec()
        spec["translation_stage"] = "draft"
        spec["implementation_scope"] = {"translation_stage": "draft"}

        upgraded = uisc.apply_status_markers(spec, "reviewed")

        self.assertEqual(upgraded["translation_stage"], "reviewed")
        self.assertEqual(upgraded["implementation_scope"]["translation_stage"], "reviewed")


if __name__ == "__main__":
    unittest.main()
