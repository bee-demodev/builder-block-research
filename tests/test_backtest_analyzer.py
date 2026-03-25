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

import backtest_analyzer as bta
from runtime.harness import CostModel


class BacktestAnalyzerTests(unittest.TestCase):
    def test_build_backtest_analysis_summarizes_trade_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            bars_path = root / "bars.csv"
            signals_path = root / "signals.json"

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
            signals_path.write_text(
                json.dumps(
                    {
                        "signals": [
                            {
                                "timestamp": "2026-03-22T09:30:00-04:00",
                                "side": "long",
                                "stop_price": 98.0,
                                "target_price": 104.0,
                                "thesis": "continuation",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            analysis = bta.build_backtest_analysis(
                bars_path=bars_path,
                signals_path=signals_path,
                cost_model=CostModel(tick_size=0.25, spread_ticks=0.0, slippage_ticks=0.0),
                session_mode="new_york",
            )

            self.assertEqual(analysis["summary"]["trade_count"], 1)
            self.assertEqual(analysis["summary"]["win_rate"], 1.0)
            self.assertEqual(analysis["trades"][0]["exit_reason"], "target")


if __name__ == "__main__":
    unittest.main()
