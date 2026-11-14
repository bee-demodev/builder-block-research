"""Backtest harness extras for the Phase B follow-ups (companion/tools/backtest.py).

The limit-at-plan-entry fill, the outcome horizon, eligibility tracking and switching one
quality check off for a run. None of them changes the companion app: they are opt-in
options of the harness, and the check switch is restored when the run ends.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pandas as pd
import pytest

from companion.styles.ttrades.checklist import ADVISORY, CONTINUATION, QUALITY, Checklist
from companion.timeframes import make_stack
from companion.tools import backtest
from companion.tools.backtest import Simulator, checks_off, scan, variant_config

NY = "America/New_York"
TICK = 0.25  # NQ
COMMISSION = 4.5 / 20.0  # NQ, points per round turn


def bars(rows: list[tuple[float, float, float, float]], start: str = "2025-03-03 09:30") -> pd.DataFrame:
    """5m bars (open, high, low, close) from ``start``, New York time."""
    index = pd.date_range(start, periods=len(rows), freq="5min", tz=NY)
    frame = pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=index)
    frame["volume"] = 1.0
    return frame


def flat(price: float, count: int) -> list[tuple[float, float, float, float]]:
    return [(price, price + 0.5, price - 0.5, price)] * count


def at(frame: pd.DataFrame, position: int) -> pd.Timestamp:
    return frame.index[position]


# --- limit at the plan entry --------------------------------------------------------------


def test_a_limit_fills_at_the_entry_when_price_trades_through_it() -> None:
    frame = bars([(105, 106, 101, 104), (104, 104.5, 99.5, 101), *flat(110, 3), (110, 121, 110, 120), *flat(120, 3)])
    sim = Simulator(frame, "NQ", 10.0)
    out = sim.run_limit("long", at(frame, 0), 100.0, 90.0, at(frame, 3), None)
    assert out["status"] == "filled" and out["at_open"] is False
    assert out["fill"] == 100.0 and out["risk"] == 10.0 and out["minutes_to_fill"] == 5.0
    assert out["first_2r"] == "win"
    assert out["net_2r"] == pytest.approx(2.0 - COMMISSION / 10.0)  # no entry or target slippage


def test_a_touch_of_the_entry_without_trading_through_does_not_fill() -> None:
    frame = bars([(105, 106, 100, 104), *flat(104, 5)])
    out = Simulator(frame, "NQ", 10.0).run_limit("long", at(frame, 0), 100.0, 90.0, at(frame, 5), None)
    assert out == {"status": "no_fill"}


def test_a_limit_is_cancelled_when_its_window_ends() -> None:
    frame = bars([*flat(105, 3), (104, 104, 99, 100), *flat(100, 3)])
    sim = Simulator(frame, "NQ", 10.0)
    assert sim.run_limit("long", at(frame, 0), 100.0, 90.0, at(frame, 3), None) == {"status": "no_fill"}
    assert sim.run_limit("long", at(frame, 0), 100.0, 90.0, at(frame, 4), None)["status"] == "filled"


def test_on_the_fill_bar_the_stop_counts_but_a_target_does_not() -> None:
    sim_up = bars([(105, 125, 99, 101), *flat(101, 4)])  # high of 2R+ before the fill: only the close counts
    out = Simulator(sim_up, "NQ", 10.0).run_limit("long", at(sim_up, 0), 100.0, 90.0, at(sim_up, 2), None)
    assert out["status"] == "filled" and out["first_2r"] == "open"
    sim_down = bars([(105, 106, 89, 95), *flat(95, 4)])  # fills and runs through the stop in one bar
    out = Simulator(sim_down, "NQ", 10.0).run_limit("long", at(sim_down, 0), 100.0, 90.0, at(sim_down, 2), None)
    assert out["first_2r"] == "loss"
    assert out["net_2r"] == pytest.approx(-1.0 - (TICK + COMMISSION) / 10.0)


def test_a_bar_opening_beyond_the_entry_fills_at_its_open_and_beyond_the_stop_does_not() -> None:
    better = bars([(97, 98, 96, 97), *flat(97, 4)])
    out = Simulator(better, "NQ", 10.0).run_limit("long", at(better, 0), 100.0, 90.0, at(better, 2), None)
    assert out["status"] == "filled" and out["at_open"] is True and out["fill"] == 97.0 and out["risk"] == 7.0
    gapped = bars([(89, 90, 88, 89), *flat(89, 4)])
    out = Simulator(gapped, "NQ", 10.0).run_limit("long", at(gapped, 0), 100.0, 90.0, at(gapped, 2), None)
    assert out["status"] == "gap_beyond_stop"


def test_a_short_limit_mirrors_the_long_one() -> None:
    frame = bars([(95, 99, 94, 96), (96, 100.5, 95, 99), *flat(90, 2), (90, 90, 79, 80), *flat(80, 2)])
    out = Simulator(frame, "NQ", 10.0).run_limit("short", at(frame, 0), 100.0, 110.0, at(frame, 3), None)
    assert out["status"] == "filled" and out["fill"] == 100.0 and out["first_2r"] == "win"


# --- market fill and horizon ----------------------------------------------------------------


def test_the_market_fill_is_one_tick_worse_and_a_win_gives_the_stop_tick_back() -> None:
    frame = bars([(100, 101, 99.5, 100.5), *flat(105, 2), (105, 121, 105, 120), *flat(120, 2)])
    out = Simulator(frame, "NQ", 10.0).run("long", at(frame, 0), 90.0, None)
    assert out is not None and out["fill"] == 100.25 and out["risk"] == pytest.approx(10.25)
    assert out["first_2r"] == "win" and out["net_2r"] == pytest.approx(2.0 - COMMISSION / 10.25)


def test_a_longer_horizon_resolves_a_trade_the_default_leaves_open() -> None:
    day = pd.date_range("2025-03-03 09:30", periods=20, freq="1D", tz=NY)
    frame = pd.DataFrame({"open": 100.0, "high": 100.5, "low": 99.5, "close": 100.0, "volume": 1.0}, index=day)
    frame.iloc[15] = [100.0, 125.0, 100.0, 124.0, 1.0]  # +2R on day 15
    sim = Simulator(frame, "NQ", 10.0)
    assert sim.run("long", day[0], 90.0, None)["first_2r"] == "open"
    assert sim.run("long", day[0], 90.0, None, max_days=35)["first_2r"] == "win"


# --- switching one quality check off ---------------------------------------------------------


def test_variant_names_switch_quality_checks_off() -> None:
    assert variant_config("baseline") == ({}, ())
    assert variant_config("off-rev_cisd_swift") == ({}, ("rev_cisd_swift",))
    assert variant_config("off-a+b") == ({}, ("a", "b"))
    assert variant_config("no_clean_wait")[0] == {"wait_for_clean_continuation": False}


def test_a_switched_off_check_is_advisory_only_inside_the_block() -> None:
    stack = make_stack("1D", "1h", "5m")
    key = "cont_entry_window_open"

    def failing() -> tuple[list[str], str]:
        checklist = Checklist(CONTINUATION, stack)
        for spec in CONTINUATION:
            checklist.set(spec.key, spec.key != key, "test")
        return checklist.failing_quality(), checklist.role(key)

    assert failing() == ([key], QUALITY)
    with checks_off([key]):
        assert failing() == ([], ADVISORY)
        gate = Checklist(CONTINUATION, stack)
        assert gate.role("bias_closure_directional") == "gate"  # only quality checks are switched
    assert failing() == ([key], QUALITY)


def test_checks_are_restored_when_the_run_fails() -> None:
    stack = make_stack("1D", "1h", "5m")
    with pytest.raises(RuntimeError), checks_off(["cont_entry_window_open"]):
        raise RuntimeError("boom")
    assert Checklist(CONTINUATION, stack).role("cont_entry_window_open") == QUALITY


# --- eligibility: the first check that reports the trigger long / short ----------------------


class _FakeStyle:
    """Reports one long trigger (entry 100, stop 95) at every check: watch before ``taken_from``,
    long from then on."""

    taken_from: pd.Timestamp

    def __init__(self, config: object = None) -> None:
        pass

    def evaluate(self, symbol, moment, stack, source):  # type: ignore[no-untyped-def]
        start = pd.Timestamp("2025-03-03 09:30", tz=NY)
        markup = [
            SimpleNamespace(role="entry", label="Entry trigger", price=100.0, start=start),
            SimpleNamespace(role="protected", label="Continuation stop swing", price=95.0, start=start),
        ]
        decision = "long" if pd.Timestamp(moment) >= self.taken_from else "watch"
        return SimpleNamespace(
            decision=decision, path_family="continuation", stage="c4", bias="bullish", idea="", plan=None,
            markup=markup, criteria=[], targets=(), why="",
        )


@pytest.mark.parametrize("taken_after", [0, 6])
def test_eligibility_records_the_first_check_reporting_long(monkeypatch, taken_after: int) -> None:  # type: ignore[no-untyped-def]
    frame = bars([*flat(100, 30), *flat(111, 30)])
    _FakeStyle.taken_from = frame.index[0] + pd.Timedelta(minutes=5 * (1 + taken_after))
    monkeypatch.setattr(backtest, "TTradesStyle", _FakeStyle)
    plain, _ = scan("NQ", ("1D", "1h", "5m"), "2025-03-03", "2025-03-04", minute_bars=frame)
    rows, _ = scan("NQ", ("1D", "1h", "5m"), "2025-03-03", "2025-03-04", minute_bars=frame, eligibility=True,
                   limit_windows=(3,))
    assert len(plain) == len(rows) == 1
    row = rows[0]
    same = {k: v for k, v in row.items() if k in plain[0]}
    assert json.dumps(same, sort_keys=True, default=str) == json.dumps(plain[0], sort_keys=True, default=str)
    assert row["taken"] is (taken_after == 0)
    assert row["elig_check"] == _FakeStyle.taken_from.isoformat()
    assert row["elig_fill_time"] == _FakeStyle.taken_from.isoformat()
    assert row["lim3_status"] == "filled" and row["lim3_at_open"] is True  # opens at the entry: fills there
