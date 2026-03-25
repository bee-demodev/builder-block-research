from __future__ import annotations

import sys
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo


ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.harness import Bar, CostModel, Side, TradeSignal, run_backtest
from runtime.replay_harness import build_replay_frames


TZ = ZoneInfo("America/New_York")


class BacktestHarnessTests(unittest.TestCase):
    def test_backtest_uses_next_bar_execution_and_applies_costs(self) -> None:
        bars = [
            Bar(datetime(2026, 3, 22, 9, 30, tzinfo=TZ), 99.0, 100.0, 98.0, 99.5, session="new_york"),
            Bar(datetime(2026, 3, 22, 9, 35, tzinfo=TZ), 100.0, 101.0, 99.5, 100.5, session="new_york"),
            Bar(datetime(2026, 3, 22, 9, 40, tzinfo=TZ), 101.0, 104.5, 100.0, 104.0, session="new_york"),
        ]
        signals = [
            TradeSignal(
                timestamp=datetime(2026, 3, 22, 9, 30, tzinfo=TZ),
                side=Side.LONG,
                stop_price=98.0,
                target_price=104.0,
                thesis="daily bias continuation",
            )
        ]

        result = run_backtest(
            bars,
            signals,
            cost_model=CostModel(tick_size=0.25, spread_ticks=1.0, slippage_ticks=1.0),
            session_mode="new_york",
        )

        trade = result["trades"][0]
        self.assertEqual(result["summary"]["trade_count"], 1)
        self.assertEqual(trade["entry_timestamp"], bars[1].timestamp.isoformat())
        self.assertEqual(trade["exit_reason"], "target")
        self.assertAlmostEqual(trade["entry_price"], 100.375, places=6)
        self.assertAlmostEqual(trade["exit_price"], 103.625, places=6)
        self.assertAlmostEqual(trade["net_pnl"], 3.25, places=6)

    def test_intrabar_conflict_uses_worst_case_stop(self) -> None:
        bars = [
            Bar(datetime(2026, 3, 22, 9, 30, tzinfo=TZ), 99.0, 100.0, 98.0, 99.5, session="new_york"),
            Bar(datetime(2026, 3, 22, 9, 35, tzinfo=TZ), 100.0, 101.0, 99.0, 100.0, session="new_york"),
            Bar(datetime(2026, 3, 22, 9, 40, tzinfo=TZ), 100.0, 105.0, 95.0, 102.0, session="new_york"),
        ]
        signals = [
            TradeSignal(
                timestamp=datetime(2026, 3, 22, 9, 30, tzinfo=TZ),
                side=Side.LONG,
                stop_price=96.0,
                target_price=104.0,
            )
        ]

        result = run_backtest(bars, signals, cost_model=CostModel(tick_size=0.25, spread_ticks=0.0, slippage_ticks=0.0))

        trade = result["trades"][0]
        self.assertEqual(trade["exit_reason"], "stop")
        self.assertAlmostEqual(trade["raw_exit_price"], 96.0, places=6)

    def test_replay_frames_filter_by_session(self) -> None:
        bars = [
            Bar(datetime(2026, 3, 22, 3, 0, tzinfo=TZ), 100.0, 101.0, 99.0, 100.5),
            Bar(datetime(2026, 3, 22, 8, 30, tzinfo=TZ), 101.0, 102.0, 100.0, 101.5),
            Bar(datetime(2026, 3, 22, 13, 0, tzinfo=TZ), 102.0, 103.0, 101.0, 102.5),
        ]

        frames = build_replay_frames(bars, warmup_bars=1, session_mode="both")

        self.assertEqual(len(frames), 2)
        self.assertEqual(frames[0].session_bucket, "london")
        self.assertEqual(frames[1].session_bucket, "new_york")


if __name__ == "__main__":
    unittest.main()

