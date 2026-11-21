"""Weekly R of a backtest grid (companion/tools/weekly_r.py): positions, trade cap, weeks, drawdown."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pandas as pd
import pytest

from companion.tools.backtest import grid_jobs
from companion.tools.weekly_r import (
    FILTERS,
    apply_filters,
    ledger_cells,
    load_runs,
    max_drawdown,
    stats,
    take,
    trading_day,
    weekly,
)

NY = "America/New_York"


def trade(fill: str, r: float, minutes: float | None = 30.0, symbol: str = "NQ", stack: str = "1D / 1h / 5m",
          outcome: str = "win", **extra) -> dict:
    moment = pd.Timestamp(fill, tz=NY)
    return {
        "symbol": symbol, "stack": stack, "check": moment, "fill_time": moment, "max_days": 10.0,
        "net_2r": r, "first_2r": outcome, "minutes_2r": minutes, "net_1r": r / 2, "first_1r": outcome,
        "minutes_1r": minutes, "path": "continuation", "trigger_close": moment, "trigger_kind": "cisd",
        "criteria": {}, **extra,
    }


def frame(*rows: dict) -> pd.DataFrame:
    return pd.DataFrame(list(rows))


def test_a_trade_inside_an_open_position_is_skipped_but_other_books_are_not() -> None:
    trades = frame(
        trade("2025-03-03 09:00", 2.0, minutes=60),
        trade("2025-03-03 09:30", -1.0),  # same book, still in the first trade until 10:00
        trade("2025-03-03 09:30", 2.0, symbol="ES"),  # another symbol: its own position
        trade("2025-03-03 10:00", -1.0),  # the first trade has exited at 10:00
    )
    taken = take(trades)
    assert list(zip(taken["symbol"], taken["r"])) == [("NQ", 2.0), ("ES", 2.0), ("NQ", -1.0)]


def test_an_open_trade_holds_its_book_until_the_outcome_horizon() -> None:
    trades = frame(trade("2025-03-03 09:00", 0.4, minutes=None, outcome="open"), trade("2025-03-10 09:00", 2.0),
                   trade("2025-03-14 09:00", 2.0))
    assert take(trades)["r"].tolist() == [0.4, 2.0]  # the 03-10 fill is inside the 10-day horizon


def test_the_trade_cap_counts_per_book_or_across_the_portfolio() -> None:
    trades = frame(
        trade("2025-03-03 03:00", 2.0, minutes=5), trade("2025-03-03 09:00", -1.0, minutes=5),
        trade("2025-03-03 09:30", 2.0, symbol="ES", minutes=5),
        trade("2025-03-02 19:00", -1.0, symbol="GC", minutes=5),  # Sunday evening: Monday's trading day
    )
    per_book = take(trades, max_per_day=1)
    assert sorted(per_book["symbol"]) == ["ES", "GC", "NQ"] and per_book["r"].sum() == 3.0
    portfolio = take(trades, max_per_day=1, day_scope="portfolio")
    assert portfolio["symbol"].tolist() == ["GC"]
    assert trading_day(pd.Timestamp("2025-03-02 19:00", tz=NY)) == pd.Timestamp("2025-03-03")


def test_the_target_picks_which_outcome_is_booked() -> None:
    assert take(frame(trade("2025-03-03 09:00", 2.0)), target=1.0)["r"].tolist() == [1.0]


def test_every_week_counts_even_without_a_trade() -> None:
    taken = take(frame(trade("2025-03-04 09:00", 2.0), trade("2025-03-05 09:00", 2.0), trade("2025-03-18 09:00", -1.0)))
    week = weekly(taken, "2025-03-03", "2025-03-24")
    assert week.tolist() == [4.0, 0.0, -1.0]
    out = stats(taken, "2025-03-03", "2025-03-24", goal=4.0)
    assert out["weeks"] == 3 and out["trades"] == 3 and out["mean_week"] == pytest.approx(1.0)
    assert out["median_week"] == 0.0 and out["pct_weeks_ge_goal"] == pytest.approx(1 / 3)
    assert out["worst_week"] == -1.0 and out["max_dd"] == -1.0


def test_max_drawdown_is_peak_to_trough_of_cumulative_r() -> None:
    assert max_drawdown([2, -1, -1, -1, 3, -2]) == -3.0
    assert max_drawdown([-1, -1]) == -2.0
    assert max_drawdown([]) == 0.0


def test_the_screens_read_path_trigger_time_and_profile() -> None:
    rows = frame(
        trade("2025-03-03 09:00", 1.0, criteria={"cont_opened_against_bias_first": True}),
        trade("2025-03-03 11:00", 1.0, criteria={"cont_opened_against_bias_first": True}),
        trade("2025-03-03 09:05", 1.0, path="reversal"),
        trade("2025-03-03 09:10", 1.0, criteria={"cont_opened_against_bias_first": False}),
    )
    assert len(apply_filters(rows, ["ny_0800_1030"])) == 3
    assert len(apply_filters(rows, ["cont_only"])) == 3
    assert len(apply_filters(rows, ["profile_ok"])) == 3
    assert len(apply_filters(rows, ["cont_only", "profile_ok", "ny_0800_1030"])) == 1
    assert set(FILTERS) >= {"cont_only", "ny_0800_1030", "profile_ok"}


def test_load_runs_reads_taken_filled_triggers_of_one_variant(tmp_path: Path) -> None:
    folder = tmp_path / "2025" / "baseline"
    folder.mkdir(parents=True)
    rows = [
        {"meta": {"max_days": 5.0}},
        {**{k: str(v) if isinstance(v, pd.Timestamp) else v for k, v in trade("2025-03-03 09:00", 2.0).items()},
         "taken": True},
        {**{k: str(v) if isinstance(v, pd.Timestamp) else v for k, v in trade("2025-03-03 10:00", 2.0).items()},
         "taken": False},
    ]
    with gzip.open(folder / "NQ_1D-1h-5m.jsonl.gz", "wt", encoding="utf-8") as handle:
        handle.write("\n".join(json.dumps(row) for row in rows) + "\n")
    loaded = load_runs(tmp_path, "baseline")
    assert len(loaded) == 1 and loaded["max_days"].iloc[0] == 5.0
    assert str(loaded["fill_time"].iloc[0].tz) == NY
    assert load_runs(tmp_path, "baseline", stacks=["1D-4h-15m"]).empty


def test_ledger_cells_pass_only_when_the_variant_wins_train_validate_and_test() -> None:
    base = take(frame(trade("2023-03-06 09:00", -1.0), trade("2025-03-04 09:00", -1.0), trade("2026-03-03 09:00", -1.0)))
    better = take(frame(trade("2023-03-06 09:00", 2.0), trade("2025-03-04 09:00", 2.0), trade("2026-03-03 09:00", 2.0)))
    mixed = take(frame(trade("2023-03-06 09:00", 2.0), trade("2025-03-04 09:00", 2.0), trade("2026-03-03 09:00", -1.0)))
    assert ledger_cells(better, base).endswith("| passes |")
    assert ledger_cells(mixed, base).endswith("| fails out of sample |")
    assert ledger_cells(base, better).endswith("| fails on train |")
    assert ledger_cells(better, base).startswith("| +0.01 (base -0.01) |")  # 2 R over the 164 train weeks


def test_no_fomc_day_drops_fills_on_a_statement_day_only() -> None:
    rows = frame(trade("2025-03-19 09:00", 1.0), trade("2025-03-18 19:00", 1.0), trade("2025-03-20 09:00", 1.0))
    kept = apply_filters(rows, ["no_fomc_day"])  # 03-18 19:00 is the 03-19 trading day
    assert kept["fill_time"].dt.day.tolist() == [20]


def test_the_grid_can_clip_its_first_and_last_year() -> None:
    jobs = list(grid_jobs(["NQ"], [2021, 2022, 2026], [("1D", "1h", "5m")], ["baseline"], Path("out"),
                          clip_start="2021-11-14", clip_end="2026-11-14"))
    assert [(job["start"], job["end"]) for job in jobs] == [
        ("2021-11-14", "2022-01-01"), ("2022-01-01", "2023-01-01"), ("2026-01-01", "2026-11-14"),
    ]
    assert list(grid_jobs(["NQ"], [2027], [("1D", "1h", "5m")], ["baseline"], Path("out"), clip_end="2026-11-14")) == []
