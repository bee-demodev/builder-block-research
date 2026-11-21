"""R per week of a backtest grid (``companion.tools.backtest grid``), as a trader would have taken it.

    python -m companion.tools.weekly_r --runs results/backtest_tv_5y --variant baseline
    python -m companion.tools.weekly_r --runs results/backtest_tv_5y --variant no_reversals \
        --stacks 1D-4h-15m --max-per-day 1 --day-scope portfolio --by symbol

The grid records every trigger; this tool turns the taken ones into a trade list:

- **One position at a time** per symbol and stack: a trade whose fill comes before the
  previous trade's exit (target, stop, or the outcome horizon) is skipped.
- **Trade cap** (``--max-per-day``, 0 = none): at most N fills per trading day (the CME day,
  18:00 to 18:00 New York), counted per symbol and stack (``--day-scope stack``) or across
  everything in the run (``portfolio``). TTrades: "max one trade a day" (PSY-1).
- **Target** (``--target``, default 2): the R multiple whose outcome is booked (``net_<m>r``,
  costs included, as the harness measured it).
- **Filters** (``--filter``): post-run screens named in ``FILTERS``. They approximate an engine
  switch on the baseline's triggers; the engine variant of the same rule is the real test.

R per week counts every calendar week (Monday to Sunday by trading day) between the start and
the end, so a week without a trade is 0 R. Max drawdown is peak to trough of the cumulative R in
fill order. Periods are the walk-forward split: choose on ``train``, confirm on ``validate``,
forward-test on ``test``.
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

NY = "America/New_York"
# Walk-forward split (start inclusive, end exclusive), CME trading days. The grid starts on
# Sunday 2021-11-14, whose 18:00 open is trading day Monday 2021-11-15.
PERIODS: dict[str, tuple[str, str]] = {
    "train": ("2021-11-15", "2025-01-01"),
    "validate": ("2025-01-01", "2026-01-01"),
    "test": ("2026-01-01", "2026-11-14"),
}
FIELDS = ("symbol", "stack", "variant", "check", "taken", "direction", "path", "session", "trigger_close",
          "trigger_kind", "fill_time", "risk_adr", "criteria")


def _clock(moment: pd.Timestamp) -> int:
    return moment.hour * 60 + moment.minute


# FOMC statement days (14:00 New York) inside the 5-year window, from the Federal Reserve's
# meeting calendar (federalreserve.gov/monetarypolicy/fomccalendars.htm, read 2026-11-21).
FOMC_DAYS = frozenset(pd.Timestamp(day) for day in (
    "2021-12-15 "
    "2022-01-26 2022-03-16 2022-05-04 2022-06-15 2022-07-27 2022-09-21 2022-11-02 2022-12-14 "
    "2023-02-01 2023-03-22 2023-05-03 2023-06-14 2023-07-26 2023-09-20 2023-11-01 2023-12-13 "
    "2024-01-31 2024-03-20 2024-05-01 2024-06-12 2024-07-31 2024-09-18 2024-11-07 2024-12-18 "
    "2025-01-29 2025-03-19 2025-05-07 2025-06-18 2025-07-30 2025-09-17 2025-10-29 2025-12-10 "
    "2026-01-28 2026-03-18 2026-04-29 2026-06-17 2026-07-29 2026-09-16 2026-10-28"
).split())


# Post-run screens on the taken triggers: name -> row test.
FILTERS: dict[str, Callable[[pd.Series], bool]] = {
    # ENT-6: continuation only
    "cont_only": lambda row: row["path"] == "continuation",
    # SES-1: trigger bar closed 08:00-10:30 New York (both inclusive)
    "ny_0800_1030": lambda row: 8 * 60 <= _clock(row["trigger_close"]) <= 10 * 60 + 30,
    # BIAS-9 / PROF-1: the bias candle moved against the bias first (open, low, then higher)
    "profile_ok": lambda row: row["path"] != "continuation"
    or (row["criteria"] or {}).get("cont_opened_against_bias_first") is True,
    # CISD-19: the order-block trigger, not the CISD itself
    "order_block_trigger": lambda row: row["trigger_kind"] == "order_block",
    # the opposite: a continuation enters on its CISD (entry_mode_continuation 'aggressive')
    "cont_cisd_trigger": lambda row: row["path"] != "continuation" or row["trigger_kind"] == "cisd",
    # stop at least min_stop_adr_frac of the ADR (stop_size_role 'quality')
    "stop_ok": lambda row: (row["criteria"] or {}).get("stop_size_ok") is not False,
    # a continuation triggered inside the kill zones (session_filter_ok)
    "cont_in_session": lambda row: row["path"] != "continuation"
    or (row["criteria"] or {}).get("session_filter_ok") is True,
    # news: no fill on an FOMC statement's trading day ("Don't trade right before it",
    # livestream_20260910 18:40; "I'd like to trade the day after FOMC", livestream_20261028 28:17)
    "no_fomc_day": lambda row: trading_day(row["fill_time"]) not in FOMC_DAYS,
}


def read_rows(paths: Iterable[Path]) -> pd.DataFrame:
    """Taken triggers with a fill from ``*.jsonl.gz`` run files, one row each."""
    rows: list[dict[str, Any]] = []
    for path in paths:
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            meta = json.loads(next(handle))["meta"]
            max_days = float(meta.get("max_days") or 10.0)
            for line in handle:
                trade = json.loads(line)
                if not trade.get("taken") or not trade.get("fill_time"):
                    continue
                row = {key: trade.get(key) for key in FIELDS}
                row["max_days"] = max_days
                for key, value in trade.items():
                    if key.startswith(("net_", "first_", "minutes_")):
                        row[key] = value
                rows.append(row)
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    for key in ("check", "trigger_close", "fill_time"):
        frame[key] = pd.to_datetime(frame[key], utc=True).dt.tz_convert(NY)
    return frame.sort_values("fill_time", kind="stable").reset_index(drop=True)


def load_runs(runs: Path, variant: str, stacks: Sequence[str] = (), symbols: Sequence[str] = ()) -> pd.DataFrame:
    """Every ``<runs>/<year>/<variant>/<SYMBOL>_<stack>.jsonl.gz`` of the variant."""
    paths = []
    for path in sorted(runs.glob(f"*/{variant}/*.jsonl.gz")):
        symbol, stack = path.name.replace(".jsonl.gz", "").split("_", 1)
        if (stacks and stack not in stacks) or (symbols and symbol not in symbols):
            continue
        paths.append(path)
    return read_rows(paths)


def trading_day(moment: pd.Timestamp) -> pd.Timestamp:
    """The CME trading day a moment belongs to (a day opens at 18:00 New York the evening before)."""
    return (moment + pd.Timedelta(hours=6)).normalize().tz_localize(None)


def exit_time(row: pd.Series, target: float) -> pd.Timestamp:
    """Target or stop time; an open trade is held to the outcome horizon (check + max_days)."""
    minutes = row.get(f"minutes_{target:g}r")
    if row.get(f"first_{target:g}r") in ("win", "loss") and minutes is not None and minutes == minutes:
        return row["fill_time"] + pd.Timedelta(minutes=float(minutes))
    return row["check"] + pd.Timedelta(days=float(row["max_days"]))


def take(trades: pd.DataFrame, target: float = 2.0, max_per_day: int = 0, day_scope: str = "stack") -> pd.DataFrame:
    """The trades a trader holding one position per symbol and stack would have taken.

    In fill order: skip a trade while that symbol / stack is still in a position, or when the
    trading day already has ``max_per_day`` fills in its scope (``stack``: per symbol and
    stack; ``portfolio``: across the whole frame). Adds ``r`` (the booked R) and ``exit``."""
    if day_scope not in ("stack", "portfolio"):
        raise ValueError("day_scope must be 'stack' or 'portfolio'")
    if trades.empty:
        return trades.assign(r=[], exit=[])
    busy_until: dict[tuple[str, str], pd.Timestamp] = {}
    per_day: dict[tuple, int] = {}
    kept: list[int] = []
    exits: list[pd.Timestamp] = []
    for index, row in trades.sort_values("fill_time", kind="stable").iterrows():
        book = (row["symbol"], row["stack"])
        if book in busy_until and row["fill_time"] < busy_until[book]:
            continue
        day = trading_day(row["fill_time"])
        scope = (day, *book) if day_scope == "stack" else (day,)
        if max_per_day and per_day.get(scope, 0) >= max_per_day:
            continue
        per_day[scope] = per_day.get(scope, 0) + 1
        out = exit_time(row, target)
        busy_until[book] = out
        kept.append(index)
        exits.append(out)
    taken = trades.loc[kept].copy()
    taken["exit"] = exits
    taken["r"] = taken[f"net_{target:g}r"].astype(float)
    return taken


def max_drawdown(r: Sequence[float]) -> float:
    """Largest peak-to-trough fall of the cumulative R (0 or negative)."""
    if not len(r):
        return 0.0
    curve = np.concatenate([[0.0], np.cumsum(np.asarray(r, dtype=float))])
    return float((curve - np.maximum.accumulate(curve)).min())


def weekly(trades: pd.DataFrame, start: str, end: str) -> pd.Series:
    """R per week (Monday-Sunday trading-day weeks) for every week in [start, end), 0 when idle."""
    first, last = pd.Timestamp(start), pd.Timestamp(end) - pd.Timedelta(days=1)
    weeks = pd.period_range(first, last, freq="W-SUN")
    if trades.empty:
        return pd.Series(0.0, index=weeks)
    days = trades["fill_time"].map(trading_day)
    inside = (days >= first) & (days <= last)
    sums = trades.loc[inside, "r"].groupby(days[inside].dt.to_period("W-SUN")).sum()
    return sums.reindex(weeks, fill_value=0.0)


def stats(trades: pd.DataFrame, start: str, end: str, goal: float = 5.0) -> dict[str, float]:
    """Weekly-R distribution and trade figures of the trades filled in [start, end)."""
    days = trades["fill_time"].map(trading_day) if not trades.empty else pd.Series(dtype="datetime64[ns]")
    inside = trades[(days >= pd.Timestamp(start)) & (days < pd.Timestamp(end))] if not trades.empty else trades
    week = weekly(inside, start, end)
    r = inside["r"].to_numpy(dtype=float) if not inside.empty else np.array([])
    return {
        "weeks": float(len(week)),
        "trades": float(len(r)),
        "trades_per_week": len(r) / len(week) if len(week) else 0.0,
        "r_per_trade": float(r.mean()) if len(r) else 0.0,
        "win_rate": float((r > 0).mean()) if len(r) else 0.0,
        "total_r": float(r.sum()),
        "mean_week": float(week.mean()),
        "median_week": float(week.median()),
        "pct_weeks_ge_goal": float((week >= goal).mean()),
        "worst_week": float(week.min()),
        "best_week": float(week.max()),
        "max_dd": max_drawdown(r),
    }


def apply_filters(trades: pd.DataFrame, names: Sequence[str]) -> pd.DataFrame:
    for name in names:
        if trades.empty:
            break
        trades = trades[trades.apply(FILTERS[name], axis=1)]
    return trades


def table(rows: dict[str, dict[str, float]]) -> str:
    """Markdown table of ``stats`` rows."""
    head = "| | Weeks | Trades | /week | R/trade | Win % | Total R | Mean R/wk | Median | Weeks >= 5R | Worst wk | Max DD |"
    lines = [head, "|---" * 12 + "|"]
    for name, s in rows.items():
        lines.append(
            f"| {name} | {s['weeks']:.0f} | {s['trades']:.0f} | {s['trades_per_week']:.2f} | {s['r_per_trade']:+.3f} | "
            f"{s['win_rate']:.0%} | {s['total_r']:+.1f} | {s['mean_week']:+.2f} | {s['median_week']:+.2f} | "
            f"{s['pct_weeks_ge_goal']:.1%} | {s['worst_week']:+.1f} | {s['max_dd']:+.1f} |"
        )
    return "\n".join(lines)


def ledger_cells(variant: pd.DataFrame, base: pd.DataFrame) -> str:
    """Mean R per week of a variant and its comparison run in each walk-forward period, as the
    train / validate / test cells of the brain's evidence ledger (TTRADES/evidence.md), plus the
    verdict the walk-forward rule gives: it must beat the comparison in both validate and test."""
    cells, wins = [], []
    for name, span in PERIODS.items():
        mine, theirs = stats(variant, *span)["mean_week"], stats(base, *span)["mean_week"]
        cells.append(f"{mine:+.2f} (base {theirs:+.2f})")
        if name != "train":
            wins.append(mine > theirs)
    better_train = stats(variant, *PERIODS["train"])["mean_week"] > stats(base, *PERIODS["train"])["mean_week"]
    verdict = "passes" if better_train and all(wins) else ("fails out of sample" if better_train else "fails on train")
    return "| " + " | ".join(cells) + f" | {verdict} |"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="companion.tools.weekly_r", description=__doc__.splitlines()[0])
    parser.add_argument("--runs", required=True, help="the grid's --out-dir")
    parser.add_argument("--variant", default="baseline")
    parser.add_argument("--stacks", nargs="*", default=[], help="file slugs, e.g. 1D-4h-15m")
    parser.add_argument("--symbols", nargs="*", default=[])
    parser.add_argument("--target", type=float, default=2.0)
    parser.add_argument("--max-per-day", type=int, default=0)
    parser.add_argument("--day-scope", choices=("stack", "portfolio"), default="stack")
    parser.add_argument("--filter", nargs="*", default=[], choices=sorted(FILTERS))
    parser.add_argument("--by", choices=("period", "year", "symbol", "stack"), default="period")
    parser.add_argument("--compare", metavar="VARIANT",
                        help="print the walk-forward against this variant (e.g. baseline) as evidence-ledger cells")
    args = parser.parse_args(argv)
    trades = apply_filters(load_runs(Path(args.runs), args.variant, args.stacks, args.symbols), args.filter)
    taken = take(trades, args.target, args.max_per_day, args.day_scope)
    if args.compare:
        base = take(apply_filters(load_runs(Path(args.runs), args.compare, args.stacks, args.symbols), args.filter),
                    args.target, args.max_per_day, args.day_scope)
        print(ledger_cells(taken, base))
        return 0
    start, end = PERIODS["train"][0], PERIODS["test"][1]
    rows: dict[str, dict[str, float]] = {}
    if args.by == "period":
        rows = {name: stats(taken, *span) for name, span in PERIODS.items()}
    elif args.by == "year":
        for year in range(int(start[:4]), int(end[:4]) + 1):
            span = (max(start, f"{year}-01-01"), min(end, f"{year + 1}-01-01"))
            rows[str(year)] = stats(taken, *span)
    else:
        key = "symbol" if args.by == "symbol" else "stack"
        for name, group in taken.groupby(key):
            rows[str(name)] = stats(group, start, end)
    rows["all"] = stats(taken, start, end)
    print(table(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
