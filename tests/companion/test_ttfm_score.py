"""Readiness scorecard of a TTFM variant (companion/tools/ttfm_score.py)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from companion.tools.ttfm_score import (
    agreement,
    coverage,
    keep,
    map_symbol,
    paired,
    period_score,
    scorecard,
    teacher_trades,
)
from companion.tools.weekly_r import take

NY = "America/New_York"


def trade(fill: str, r: float, symbol: str = "NQ", direction: str = "long") -> dict:
    moment = pd.Timestamp(fill, tz=NY)
    return {"symbol": symbol, "stack": "1D / 4h / 15m", "direction": direction, "check": moment, "fill_time": moment,
            "max_days": 10.0, "net_2r": r, "first_2r": "win" if r > 0 else "loss", "minutes_2r": 30.0}


def test_stream_tickers_map_to_the_backtest_symbols() -> None:
    assert [map_symbol(t) for t in ("MNQ1!", "NQ1!", "NAS100USD", "MESZ2025", "ES", "GC1!", "EURUSD", "indices", "HG")] == [
        "NQ", "NQ", "NQ", "ES", "ES", "GC", "6E", None, None]


def test_teacher_trades_are_read_from_the_livestream_trades_section(tmp_path: Path) -> None:
    (tmp_path / "livestream_20260902_new_york_open_x.md").write_text(
        "# x\n\n## Trades\n- **NQ1! short** (10:30): continuation. Outcome: win.\n"
        "- **MNQ1! short** (12:00): same idea again. Outcome: loss.\n- **HG1! long** (14:00): copper.\n\n"
        "## Q&A\n- **ES long** is only discussed here\n", encoding="utf-8")
    (tmp_path / "livestream_20260906_new_york_open_y.md").write_text(  # a Sunday: a recap, not a live trade
        "## Trades\n- **ES short** (10:00): recap of Friday. Outcome: win.\n", encoding="utf-8")
    (tmp_path / "livestream_20260903_q_a_with_a_guest_z.md").write_text(
        "## Trades\n- **ES long** (10:00): the guest's trade. Outcome: win.\n", encoding="utf-8")
    rows = teacher_trades(tmp_path)
    assert rows[["symbol", "direction"]].values.tolist() == [["NQ", "short"]]  # deduped; copper is not traded here
    assert rows["day"].iloc[0] == pd.Timestamp("2026-09-02")


def test_agreement_needs_the_same_trading_day_symbol_and_direction() -> None:
    teacher = pd.DataFrame({"day": [pd.Timestamp("2026-09-02")] * 2, "symbol": ["NQ", "ES"], "direction": ["short", "short"]})
    taken = take(pd.DataFrame([trade("2026-09-01 20:00", 2.0, "NQ", "short"), trade("2026-09-02 09:40", 2.0, "ES", "long")]))
    assert agreement(taken, teacher, "2026-01-01", "2026-11-14") == (1, 2)  # Tuesday 20:00 is Wednesday's trading day
    assert agreement(taken, teacher, "2025-01-01", "2026-01-01") == (0, 0)


def test_coverage_counts_the_status_column_of_the_gap_tables(tmp_path: Path) -> None:
    page = tmp_path / "gaps.md"
    page.write_text("| Gap | Teacher | Engine | Switch | Status |\n|---|---|---|---|---|\n| a | x | y | z | tested |\n"
                    "| b | x | y | z | open |\n| c | x | y | z | tested (screen) |\n| d | x | - | - | — |\n", encoding="utf-8")
    assert coverage(page) == (2, 3)


def test_a_steady_winner_scores_full_edge_and_a_loser_none() -> None:
    weeks = pd.date_range("2023-01-03", "2024-12-24", freq="7D")
    winner = take(pd.DataFrame([trade(str(day.date()) + " 09:30", 2.0 if i % 4 else -1.0) for i, day in enumerate(weeks)]))
    loser = take(pd.DataFrame([trade(str(day.date()) + " 09:30", -1.0) for day in weeks]))
    good, bad = period_score(winner, "2023-01-02", "2025-01-01"), period_score(loser, "2023-01-02", "2025-01-01")
    assert good.edge == 10.0 and good.robustness == 10.0 and good.drawdown > 5.0
    assert bad.edge == 0.0 and bad.robustness == 0.0 and bad.drawdown == 0.0


def test_the_keep_rule_reads_only_the_paired_train_difference() -> None:
    weeks = pd.date_range("2021-11-16", "2026-11-03", freq="7D")
    base = take(pd.DataFrame([trade(str(day.date()) + " 09:30", -1.0 if i % 2 else 1.0) for i, day in enumerate(weeks)]))
    # better by about 0.5 R in most train weeks, worse afterwards: kept all the same
    better = take(pd.DataFrame([trade(str(day.date()) + " 09:30", (-1.0 if i % 2 else 1.0) + (0.5 if day.year < 2025 and i % 3 else -0.5))
                                for i, day in enumerate(weeks)]))
    diff = paired(better, base)
    assert diff["train"][0] > 0 and diff["train"][1] >= 1.0 and diff["test"][0] < 0
    assert keep(diff) and not keep(paired(base, better))


def test_ready_needs_the_out_of_sample_score_and_edge(tmp_path: Path) -> None:
    gaps = tmp_path / "gaps.md"
    gaps.write_text("| Gap | a | b | c | Status |\n|---|---|---|---|---|\n| g | x | y | z | tested |\n", encoding="utf-8")
    weeks = pd.date_range("2021-11-16", "2026-11-03", freq="7D")
    rows = [trade(str(day.date()) + " 09:30", 2.0 if i % 4 else -1.0, symbol) for i, day in enumerate(weeks)
            for symbol in ("NQ", "ES")]
    card = scorecard(take(pd.DataFrame(rows)), pd.DataFrame(columns=["day", "symbol", "direction"]), gaps)
    assert card["ready"] and card["oos_edge"] == 10.0
    flat = scorecard(take(pd.DataFrame(rows[:10])), pd.DataFrame(columns=["day", "symbol", "direction"]), gaps)
    assert not flat["ready"]
