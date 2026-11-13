"""Replay the companion over a year of fixed check times and tabulate what it said.

    python -m companion.tools.sweep --symbol NQ --year 2025 --out sweep.json

For every business day of the year and every check time (New York), on every stack, one
``analyze`` call against a single shared ``HistoricalBarSource``. A check is skipped when
no minute bar closed in the hour before it (the market was shut).

For the long / short verdicts of ``--outcome-stack`` a first outcome is measured with
entry-timeframe bars that open at or after the check time and before the bias candle
closes: did price reach entry +/- N times the risk before the stop? A bar that holds
both counts as the stop. Checks on the same trading day that report the same direction,
path, entry and stop are one trade, measured from the first of them.

The entry is the trigger bar's close, which can be hours before the check that first
reports it. Price may already have travelled to the target by then, and such a trade
then "wins" on the first bar after the check. So two more reads are printed: the same
outcome leaving those trades out, and the outcome measured from the trigger bar's close
(every bar after the signal printed, which is what a trader watching live would get).

This is a sanity read, not a backtest: no costs, no slippage, and the minute data has gaps.

    python -m companion.tools.sweep --from-json sweep.json     # outcome tables again, no replay
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Sequence
from typing import Any

import pandas as pd

from companion.bars import HistoricalBarSource, resample
from companion.engine import analyze
from companion.timeframes import bar_close_time, get_stack
from companion.types import BARS_TIMEZONE, TimeframeStack, Verdict

DEFAULT_TIMES = ("03:30", "08:45", "09:45", "10:30", "11:30", "14:00")
DEFAULT_STACKS = ("1D / 1h / 5m", "4h / 15m / 1m", "1h / 5m / 1m")
MULTIPLES = (1.0, 2.0)


def check_moments(year: int, times: Sequence[str], minutes: pd.DataFrame) -> list[pd.Timestamp]:
    """Business-day check times of ``year`` at which the market had traded in the last hour."""
    moments: list[pd.Timestamp] = []
    index = minutes.index
    for day in pd.bdate_range(f"{year}-01-01", f"{year}-12-31"):
        for clock in times:
            moment = pd.Timestamp(f"{day.date()} {clock}", tz=BARS_TIMEZONE)
            first = int(index.searchsorted(moment - pd.Timedelta(hours=1), side="left"))
            last = int(index.searchsorted(moment - pd.Timedelta(minutes=1), side="right"))
            if last > first:
                moments.append(moment)
    return moments


def _criterion(verdict: Verdict, key: str) -> Any:
    for item in verdict.criteria:
        if item.key == key:
            return item
    return None


def _forming_open(verdict: Verdict) -> pd.Timestamp | None:
    for item in verdict.markup:
        if item.label == "Forming bias candle open" and item.start is not None:
            return pd.Timestamp(item.start)
    return None


def _trigger_close(verdict: Verdict) -> pd.Timestamp | None:
    for item in verdict.markup:
        if item.label == "Entry" and item.start is not None:
            return pd.Timestamp(item.start)
    return None


def record(verdict: Verdict) -> dict[str, Any]:
    """The parts of a verdict the tables need."""
    row: dict[str, Any] = {
        "as_of": pd.Timestamp(verdict.as_of).isoformat(),
        "decision": verdict.decision,
        "bias": verdict.bias,
        "path": verdict.path_family,
        "stage": verdict.stage,
        "entry": verdict.entry,
        "stop": verdict.stop,
        "failed": [
            item.key
            for item in verdict.criteria
            if item.passed is not True
            and item.role in ("gate", "step", "quality")
            and (item.group == "shared" or item.group.startswith(verdict.path_family))
        ],
    }
    if verdict.decision in ("long", "short"):
        trigger_key = "cont_entry_trigger" if verdict.path_family == "continuation" else "rev_entry_trigger"
        detail = _criterion(verdict, trigger_key).detail
        row["trigger_kind"] = "cisd" if "CISD is the trigger" in detail else "order_block"
        opened, closed = _forming_open(verdict), _trigger_close(verdict)
        row["bias_open"] = opened.isoformat() if opened is not None else None
        row["trigger_close"] = closed.isoformat() if closed is not None else None
        session = _criterion(verdict, "session_filter_ok")
        row["in_kill_zone"] = session.passed if session is not None else None
        if verdict.path_family == "reversal":
            row["key_level"] = _criterion(verdict, "rev_key_level_reached").detail
    return row


def first_outcome(
    bars: pd.DataFrame, direction: str, entry: float, stop: float, multiple: float
) -> tuple[str, pd.Timestamp | None]:
    """("win" | "loss" | "unresolved", bar open time) walking ``bars`` in order."""
    risk = abs(entry - stop)
    sign = 1.0 if direction == "long" else -1.0
    target = entry + sign * multiple * risk
    for moment, high, low in zip(bars.index, bars["high"].to_numpy(), bars["low"].to_numpy()):
        hit_stop = low <= stop if direction == "long" else high >= stop
        hit_target = high >= target if direction == "long" else low <= target
        if hit_stop:  # a bar holding both counts as the stop
            return "loss", moment
        if hit_target:
            return "win", moment
    return "unresolved", None


def measure(rows: list[dict[str, Any]], stack: TimeframeStack, minutes: pd.DataFrame) -> list[dict[str, Any]]:
    """One row per trade (repeated signals collapsed) with its first outcome per multiple."""
    trades: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        if row["decision"] not in ("long", "short") or row["entry"] is None or row["stop"] is None:
            continue
        key = (row.get("bias_open"), row["decision"], row["path"], round(row["entry"], 4), round(row["stop"], 4))
        if key in trades:
            trades[key]["checks"] += 1
            continue
        trades[key] = {**row, "checks": 1}
    measured: list[dict[str, Any]] = []
    for trade in trades.values():
        as_of = pd.Timestamp(trade["as_of"])
        if trade.get("bias_open") is None:
            continue
        end = bar_close_time(pd.Timestamp(trade["bias_open"]), stack.bias)
        window = minutes[(minutes.index >= as_of) & (minutes.index < end)]
        bars = resample(window, stack.entry)
        entry, stop = float(trade["entry"]), float(trade["stop"])
        risk = abs(entry - stop)
        sign = 1.0 if trade["decision"] == "long" else -1.0
        before = minutes[minutes.index < as_of]
        last_price = float(before["close"].iloc[-1]) if len(before) else entry
        trade["risk"] = risk
        trade["r_at_check"] = sign * (last_price - entry) / risk if risk > 0 else None
        trigger_close = pd.Timestamp(trade["trigger_close"]) if trade.get("trigger_close") else as_of
        trade["minutes_since_trigger"] = (as_of - trigger_close) / pd.Timedelta(minutes=1)
        trade["bars_after"] = len(bars)
        # what happened between the trigger bar's close and the check (already history at the check)
        earlier = resample(minutes[(minutes.index >= trigger_close) & (minutes.index < as_of)], stack.entry)
        whole = resample(minutes[(minutes.index >= trigger_close) & (minutes.index < end)], stack.entry)
        for multiple in MULTIPLES:
            result, moment = first_outcome(bars, trade["decision"], entry, stop, multiple)
            trade[f"outcome_{multiple:g}r"] = result
            trade[f"outcome_{multiple:g}r_at"] = moment.isoformat() if moment is not None else None
            reached, _ = first_outcome(earlier, trade["decision"], entry, stop, multiple)
            trade[f"before_check_{multiple:g}r"] = reached
            trade[f"from_trigger_{multiple:g}r"], _ = first_outcome(whole, trade["decision"], entry, stop, multiple)
        measured.append(trade)
    return measured


def _table(title: str, counter: Counter[Any]) -> list[str]:
    lines = [title]
    for key, count in sorted(counter.items(), key=lambda item: str(item[0])):
        label = " / ".join(str(part) for part in key) if isinstance(key, tuple) else str(key)
        lines.append(f"  {label:<40} {count}")
    return lines


def summarise(name: str, rows: list[dict[str, Any]]) -> list[str]:
    lines = [f"=== {name}: {len(rows)} checks ==="]
    lines += _table("decisions", Counter(row["decision"] for row in rows))
    lines += _table(
        "long / short by path", Counter((row["decision"], row["path"]) for row in rows if row["decision"] in ("long", "short"))
    )
    lines += _table("trigger kind", Counter((row["decision"], row["path"], row["trigger_kind"]) for row in rows if "trigger_kind" in row))
    lines += _table("stage", Counter(row["stage"] for row in rows))
    lines += _table("path / stage", Counter((row["path"], row["stage"]) for row in rows))
    lines += _table("bias", Counter(row["bias"] for row in rows))
    watch_c4 = Counter(key for row in rows if row["decision"] == "watch" and row["stage"] == "c4" for key in row["failed"])
    lines += _table("watch at c4: failing quality checks", watch_c4)
    return lines


def summarise_outcomes(name: str, trades: list[dict[str, Any]]) -> list[str]:
    lines = [f"=== outcomes on {name}: {len(trades)} trades after collapsing repeated signals ==="]
    for multiple in MULTIPLES:
        key = f"outcome_{multiple:g}r"
        lines += _table(f"target {multiple:g}R, by direction and path (after the first check)",
                        Counter((trade["decision"], trade["path"], trade[key]) for trade in trades))
        lines += _table(f"target {multiple:g}R, all", Counter(trade[key] for trade in trades))
        lines += _table(
            f"target {multiple:g}R: what had already happened between the trigger close and the first check",
            Counter(trade[f"before_check_{multiple:g}r"] for trade in trades),
        )
        fresh = [trade for trade in trades if trade[f"before_check_{multiple:g}r"] == "unresolved"]
        lines += _table(
            f"target {multiple:g}R, after the first check, only the {len(fresh)} trades whose target had not traded yet",
            Counter((trade["decision"], trade["path"], trade[key]) for trade in fresh),
        )
        lines += _table(
            f"target {multiple:g}R, measured from the trigger bar's close",
            Counter((trade["decision"], trade["path"], trade[f"from_trigger_{multiple:g}r"]) for trade in trades),
        )
        lines += _table(
            f"target {multiple:g}R, measured from the trigger bar's close, all",
            Counter(trade[f"from_trigger_{multiple:g}r"] for trade in trades),
        )
    stale = [trade["minutes_since_trigger"] for trade in trades]
    if stale:
        series = pd.Series(stale)
        lines.append(
            f"minutes between trigger close and first check: median {series.median():.0f}, "
            f"max {series.max():.0f}; {int((series > 60).sum())} trades over 60"
        )
    return lines


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="companion.tools.sweep", description=__doc__.splitlines()[0])
    parser.add_argument("--symbol", default="NQ")
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--stacks", nargs="*", default=list(DEFAULT_STACKS))
    parser.add_argument("--times", nargs="*", default=list(DEFAULT_TIMES))
    parser.add_argument("--outcome-stack", default=DEFAULT_STACKS[0])
    parser.add_argument("--style", default="ttrades")
    parser.add_argument("--out", help="write every check and trade as JSON to this file")
    parser.add_argument("--from-json", help="skip the replay: read the checks from an earlier --out file")
    args = parser.parse_args(argv)

    source = HistoricalBarSource(start=f"{args.year - 1}-06-01", end=f"{args.year + 1}-01-10")
    minutes = source.minute_bars(args.symbol)
    if args.from_json:
        with open(args.from_json, encoding="utf-8") as handle:
            saved = json.load(handle)
        stack = get_stack(args.outcome_stack)
        rows = saved["stacks"][args.outcome_stack]["checks"]
        print("\n".join(summarise_outcomes(args.outcome_stack, measure(rows, stack, minutes))), flush=True)
        return 0
    moments = check_moments(args.year, args.times, minutes)
    result: dict[str, Any] = {"symbol": args.symbol, "year": args.year, "times": args.times, "stacks": {}}
    for name in args.stacks:
        stack = get_stack(name)
        rows = [record(analyze(args.symbol, moment, stack, style_name=args.style, source=source)) for moment in moments]
        print("\n".join(summarise(name, rows)), flush=True)
        entry: dict[str, Any] = {"checks": rows}
        if name == args.outcome_stack:
            trades = measure(rows, stack, minutes)
            entry["trades"] = trades
            print("\n".join(summarise_outcomes(name, trades)), flush=True)
        result["stacks"][name] = entry
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            json.dump(result, handle, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
