"""Bar-by-bar backtest of a style: every entry-timeframe close, every trigger, every outcome.

    python -m companion.tools.backtest run --symbol NQ --stack "1D / 1h / 5m" \
        --start 2025-01-01 --end 2026-01-01 --out results/backtest/run.jsonl.gz
    python -m companion.tools.backtest grid --symbols NQ ES GC --years 2025 --workers 20

How it differs from ``sweep``: ``analyze`` is called at the close of every entry-timeframe
bar (not at six clock times), so a trigger is seen on the bar that confirms it. Each
trigger is recorded once, on the first check that reports it, together with the decision
the style gave it there: ``long`` / ``short`` (taken) or ``watch`` with the quality checks
that held it back (a shadow trade, measured the same way so the filters can be judged).

Fill: the open of the first minute bar at or after the check, one tick worse. Stop: the
plan's stop; a stop fill is one tick worse. A minute bar that reaches both the stop and a
target counts as the stop. Commission is charged per round turn in price units. Outcomes,
all in R of the filled risk, net of costs:

- ``first_<m>r``: "win" / "loss" / "open" for a target of m R against the stop, walking
  minute bars until ``--max-days`` calendar days after the fill.
- ``r_bias_close``: where the trade stands at the close of the bias candle it belongs to
  (stopped trades: -1 R), the exit when the trader "trades the body" of that candle.
- ``mfe_r`` / ``mae_r``: best and worst excursion before the stop (or the horizon).

No lookahead: the style reads closed bars only (``companion.types``); the simulation reads
minute bars from the fill onward only. Data gaps are not filled.
"""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import gzip
import json
import math
import os
import sys
import time
from collections.abc import Iterator, Sequence
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from companion.bars import HistoricalBarSource, bar_close_times, resample
from companion.styles.ttrades.checklist import ADVISORY, QUALITY, Checklist
from companion.styles.ttrades.config import load_config
from companion.styles.ttrades.style import TTradesStyle
from companion.timeframes import bar_close_time, make_stack, parse_timeframe
from companion.types import BARS_TIMEZONE, TimeframeStack, Verdict

# Contract specs for costs: tick size and dollars per point (minis unless noted).
CONTRACTS: dict[str, tuple[float, float]] = {
    "NQ": (0.25, 20.0),
    "ES": (0.25, 50.0),
    "YM": (1.0, 5.0),
    "RTY": (0.1, 50.0),
    "GC": (0.1, 100.0),
    "SI": (0.005, 5000.0),
    "CL": (0.01, 1000.0),
    "6E": (0.00005, 125000.0),
}
COMMISSION_USD = 4.5  # round turn per contract
R_TARGETS = (1.0, 1.5, 2.0, 3.0)

ALL_STACKS: tuple[tuple[str, str, str], ...] = (
    ("1D", "1h", "5m"),
    ("1W", "4h", "15m"),
    ("1M", "1D", "1h"),
    ("4h", "15m", "1m"),
    ("1h", "5m", "1m"),
    ("1D", "4h", "15m"),
    ("1D", "30m", "3m"),
    ("1W", "1D", "1h"),
    ("1h", "15m", "1m"),
)

# Named config variants: overrides of companion/styles/ttrades/config.json.
VARIANTS: dict[str, dict[str, Any]] = {
    "baseline": {},
    "aggressive": {"entry_mode_continuation": "aggressive", "entry_mode_reversal": "aggressive"},
    "conservative": {"entry_mode_continuation": "conservative", "entry_mode_reversal": "conservative"},
    "latest_trigger": {"entry_either_pick": "latest"},
    "no_clean_wait": {"wait_for_clean_continuation": False},
    # Teacher-grounded switches from the TTrades brain (proposed TD rows in
    # knowledge/second_brain/TTRADES/decisions.md; each cites its rule there).
    "next_continuation": {"entry_mode_continuation": "conservative"},  # CISD-19
    "eq_soft": {"eq_respect_role": "advisory"},  # BIAS-1 / RNG-3
    "profile_veto": {"profile_check_role": "quality"},  # BIAS-9 / PROF-1
    "no_reversals": {"trade_reversals": False},  # ENT-6
    "ny_window": {"kill_zones": [["08:00", "10:30"]], "session_filter_role": "quality"},  # SES-1
    "cont_cisd_entry": {"entry_mode_continuation": "aggressive"},  # question 14: the entry CISD itself
    "stop_gate": {"stop_size_role": "quality"},  # question 38: a stop under 4% of ADR waits
    "swing_close_break": {"protected_swing_break_on": "close"},  # SW-1
    "no_double_expansion_c4": {"c4_after_double_expansion": "skip"},  # C4c
    "wick_setup": {"cont_setup_pick": "wick_extreme"},  # one CISD a day forms the wick
    # loop turn 11: the switches kept on train (paired weekly-R t >= 1; TTRADES/loop-log.md)
    "loop1": {"cont_setup_pick": "wick_extreme", "stop_size_role": "quality", "c4_after_double_expansion": "skip"},
    "loop1_ny": {"cont_setup_pick": "wick_extreme", "stop_size_role": "quality", "c4_after_double_expansion": "skip",
                 "kill_zones": [["08:00", "10:30"]], "session_filter_role": "quality"},
}
# "off-<criterion key>" (or several keys joined by "+") runs the baseline config with those
# quality checks made advisory for that run only: computed and shown, never blocking.
OFF_PREFIX = "off-"
# Outcome fields copied under a prefix for the limit, eligibility and extra-horizon outcomes.
SUB_FIELDS = ("skipped", "status", "at_open", "minutes_to_fill", "fill", "fill_time", "risk", "cost_r", "mfe_r",
              "first_1r", "first_2r", "first_3r", "net_1r", "net_1.5r", "net_2r", "net_3r", "minutes_2r", "r_bias_close")


def variant_config(variant: str) -> tuple[dict[str, Any], tuple[str, ...]]:
    """(config overrides, quality checks switched off) of a variant name."""
    if variant.startswith(OFF_PREFIX):
        return {}, tuple(key for key in variant[len(OFF_PREFIX):].split("+") if key)
    return VARIANTS[variant], ()


@contextlib.contextmanager
def checks_off(keys: Sequence[str]) -> Iterator[None]:
    """Make the named quality checks advisory while the block runs (backtest only; restored after).

    Path selection reads stages, not quality checks, so this changes only whether an
    entry-ready trigger is reported as long / short or held at watch."""
    if not keys:
        yield
        return
    original = Checklist.role
    off = frozenset(keys)

    def role(self: Checklist, key: str) -> str:
        found = original(self, key)
        return ADVISORY if key in off and found == QUALITY else found

    Checklist.role = role  # type: ignore[method-assign]
    try:
        yield
    finally:
        Checklist.role = original  # type: ignore[method-assign]


def _sub(prefix: str, outcome: dict[str, Any] | None) -> dict[str, Any]:
    return {f"{prefix}{key}": outcome[key] for key in SUB_FIELDS if outcome is not None and key in outcome}


def stack_name(parts: Sequence[str]) -> str:
    return " / ".join(parts)


def session_label(moment: pd.Timestamp) -> str:
    """New York session bucket of a time (the windows rules.md 9.1 names, plus the rest)."""
    minutes = moment.hour * 60 + moment.minute
    if minutes >= 18 * 60 or minutes < 2 * 60:
        return "asia"
    if minutes < 5 * 60:
        return "london"
    if minutes < 8 * 60 + 30:
        return "pre_ny"
    if minutes < 11 * 60:
        return "ny_am"
    if minutes < 13 * 60 + 30:
        return "ny_lunch"
    if minutes < 16 * 60:
        return "ny_pm"
    return "after_hours"


def _markup_start(verdict: Verdict, label: str) -> pd.Timestamp | None:
    for item in verdict.markup:
        if item.label == label and item.start is not None:
            return pd.Timestamp(item.start)
    return None


def _criterion(verdict: Verdict, key: str) -> Any:
    for item in verdict.criteria:
        if item.key == key:
            return item
    return None


def _trigger(verdict: Verdict) -> tuple[str, pd.Timestamp, float, float] | None:
    """(direction, trigger bar open, entry level, stop level) of the selected path's trigger.

    Read from the markup, which carries it whether or not the quality checks let the
    verdict become long / short (``Verdict.plan`` is only told for a few failing checks).
    """
    entry = stop = None
    for item in verdict.markup:
        if item.role == "entry" and item.label == "Entry trigger" and item.price is not None and item.start is not None:
            entry = item
        elif item.role == "protected" and "stop swing" in item.label and item.price is not None:
            stop = item
    if entry is None or stop is None or entry.price == stop.price:
        return None
    direction = "long" if stop.price < entry.price else "short"
    return direction, pd.Timestamp(entry.start), float(entry.price), float(stop.price)


def _blocking(verdict: Verdict) -> list[str]:
    """Quality / gate / step criteria of the selected path that are not True."""
    family = verdict.path_family
    return [
        item.key
        for item in verdict.criteria
        if item.passed is not True
        and item.role in ("gate", "step", "quality")
        and (item.group == "shared" or item.group.startswith(family))
    ]


def check_times(minutes: pd.DataFrame, entry_tf: str, start: pd.Timestamp, end: pd.Timestamp,
                hours: tuple[int, int] | None) -> pd.DatetimeIndex:
    """Close times of entry-timeframe bars in [start, end) that contain traded minutes."""
    window = minutes[(minutes.index >= start - pd.Timedelta(days=2)) & (minutes.index < end)]
    bars = resample(window, entry_tf)
    closes = bar_close_times(bars, entry_tf)
    closes = closes[(closes >= start) & (closes < end)]
    if hours is not None:
        lo, hi = hours
        hour = closes.hour
        closes = closes[(hour >= lo) & (hour < hi)] if lo < hi else closes[(hour >= lo) | (hour < hi)]
    return closes


@dataclasses.dataclass
class Simulator:
    """Outcomes of a trade on minute bars, from the fill onward."""

    minutes: pd.DataFrame
    symbol: str
    max_days: float

    def __post_init__(self) -> None:
        self._index = self.minutes.index
        self._open = self.minutes["open"].to_numpy()
        self._high = self.minutes["high"].to_numpy()
        self._low = self.minutes["low"].to_numpy()
        self._close = self.minutes["close"].to_numpy()
        tick, point_value = CONTRACTS.get(self.symbol.upper(), (0.0, 0.0))
        self.tick = tick
        self.commission = COMMISSION_USD / point_value if point_value else 0.0

    def run(self, direction: str, at: pd.Timestamp, stop: float, bias_close: pd.Timestamp | None,
            max_days: float | None = None) -> dict[str, Any] | None:
        """Market entry: the open of the first bar at or after ``at``, one tick worse."""
        first = int(self._index.searchsorted(at, side="left"))
        if first >= len(self._index) or self._index[first] - at > pd.Timedelta(hours=2):
            return None
        sign = 1.0 if direction == "long" else -1.0
        fill = float(self._open[first]) + sign * self.tick
        risk = sign * (fill - stop)
        if not (risk > 0):
            return {"skipped": "fill beyond stop", "fill": fill}
        return self._walk(first, fill, sign, risk, at, bias_close, max_days, whole_first_bar=True)

    def run_limit(self, direction: str, at: pd.Timestamp, entry: float, stop: float, until: pd.Timestamp,
                  bias_close: pd.Timestamp | None, max_days: float | None = None) -> dict[str, Any]:
        """Limit order at ``entry``, placed at ``at`` and cancelled at ``until`` if unfilled.

        A bar that opens at or beyond the entry (long: open <= entry) fills at its open, the
        better price. Otherwise the order fills at ``entry`` on the first bar that trades through
        it by one tick (long: low <= entry - tick). On that bar the stop counts (adverse extreme
        beyond the stop = loss) but a target does not: the bar's favourable extreme may have come
        before the fill, so only its close counts in the trade's favour. A bar that opens beyond
        the stop before any fill would fill already through the stop: ``gap_beyond_stop``, no
        outcome. Costs: commission and one tick of stop slippage; no entry slippage (a limit).
        ``status``: ``filled``, ``no_fill`` (window ended), ``gap_beyond_stop`` or ``no_data``.
        """
        first = int(self._index.searchsorted(at, side="left"))
        if first >= len(self._index) or self._index[first] - at > pd.Timedelta(hours=2):
            return {"status": "no_data"}
        sign = 1.0 if direction == "long" else -1.0
        if not (sign * (entry - stop) > 0):
            return {"status": "gap_beyond_stop"}
        window_end = int(self._index.searchsorted(until, side="left"))
        through = entry - sign * self.tick
        for index in range(first, min(len(self._index), max(first + 1, window_end))):
            bar_open = float(self._open[index])
            waited = float((self._index[index] - at) / pd.Timedelta(minutes=1))
            if sign * (bar_open - entry) <= 0:  # opens at or beyond the entry: fills at the open
                if sign * (bar_open - stop) <= 0:
                    return {"status": "gap_beyond_stop", "fill": bar_open}
                out = self._walk(index, bar_open, sign, sign * (bar_open - stop), at, bias_close, max_days,
                                 whole_first_bar=True)
                return {"status": "filled", "at_open": True, "minutes_to_fill": waited, **out}
            if (self._low[index] <= through) if sign > 0 else (self._high[index] >= through):
                out = self._walk(index, entry, sign, sign * (entry - stop), at, bias_close, max_days,
                                 whole_first_bar=False)
                return {"status": "filled", "at_open": False, "minutes_to_fill": waited, **out}
        return {"status": "no_fill"}

    def _walk(self, first: int, fill: float, sign: float, risk: float, at: pd.Timestamp,
              bias_close: pd.Timestamp | None, max_days: float | None, whole_first_bar: bool) -> dict[str, Any]:
        """Outcomes of a position filled at ``fill`` on bar ``first``, walked to ``at`` + the horizon.

        ``whole_first_bar`` False: the fill came inside bar ``first`` (a limit), so only that
        bar's close counts in the trade's favour."""
        horizon = at + pd.Timedelta(days=self.max_days if max_days is None else max_days)
        last = int(self._index.searchsorted(horizon, side="left"))
        highs, lows, closes = self._high[first:last], self._low[first:last], self._close[first:last]
        times = self._index[first:last]
        favour = (highs - fill) if sign > 0 else (fill - lows)
        against = (fill - lows) if sign > 0 else (highs - fill)
        if not whole_first_bar and len(favour):
            favour = favour.copy()
            favour[0] = max(0.0, sign * (float(closes[0]) - fill))
        stopped = np.nonzero(against >= risk)[0]
        stop_at = int(stopped[0]) if len(stopped) else None
        cost_r = (self.tick + self.commission) / risk  # stop slippage + commission; entry tick is in the fill
        out: dict[str, Any] = {
            "fill": fill,
            "fill_time": times[0].isoformat() if len(times) else None,
            "risk": risk,
            "cost_r": cost_r,
            "stop_time": times[stop_at].isoformat() if stop_at is not None else None,
            "minutes_to_stop": float((times[stop_at] - times[0]) / pd.Timedelta(minutes=1)) if stop_at is not None else None,
        }
        upto = stop_at if stop_at is not None else len(times)
        # Excursions before the stop bar (the stop bar itself counts as the stop).
        out["mfe_r"] = float(favour[:upto].max() / risk) if upto > 0 else 0.0
        out["mae_r"] = float(against[:upto].max() / risk) if upto > 0 else 0.0
        for multiple in R_TARGETS:
            reached = np.nonzero(favour >= multiple * risk)[0]
            hit = int(reached[0]) if len(reached) else None
            if stop_at is not None and (hit is None or stop_at <= hit):
                result, net = "loss", -1.0 - cost_r
                minutes_to = out["minutes_to_stop"]
            elif hit is not None:
                result, net = "win", multiple - cost_r + self.tick / risk  # target is a limit: no slippage
                minutes_to = float((times[hit] - times[0]) / pd.Timedelta(minutes=1))
            else:
                result = "open"
                net = sign * (float(closes[-1]) - fill) / risk - cost_r if len(closes) else 0.0
                minutes_to = None
            out[f"first_{multiple:g}r"] = result
            out[f"net_{multiple:g}r"] = net
            out[f"minutes_{multiple:g}r"] = minutes_to
        if bias_close is not None:
            end = int(self._index.searchsorted(bias_close, side="left")) - first
            if stop_at is not None and stop_at < end:
                out["r_bias_close"] = -1.0 - cost_r
            elif end > 0:
                end = min(end, len(closes))
                out["r_bias_close"] = sign * (float(closes[end - 1]) - fill) / risk - cost_r
            else:
                out["r_bias_close"] = None
        return out


def daily_range(minutes: pd.DataFrame) -> pd.Series:
    """Average of the last 14 daily ranges, known at each trading day's open (18:00)."""
    daily = resample(minutes, "1D")
    rng = (daily["high"] - daily["low"]).rolling(14).mean().shift(1)
    return rng


def scan(symbol: str, stack_parts: Sequence[str], start: str, end: str, variant: str = "baseline",
         hours: tuple[int, int] | None = None, max_days: float = 10.0,
         minute_bars: pd.DataFrame | None = None, progress: bool = False,
         limit_windows: Sequence[int] = (), eligibility: bool = False,
         extra_horizons: Sequence[float] = ()) -> tuple[list[dict[str, Any]], list[tuple]]:
    """Run one symbol / stack / period. Returns (trades, per-check state rows).

    Opt-in extras (all off by default; the base fields do not change):

    - ``limit_windows``: for each W, a limit order at the plan entry placed at the first report
      and cancelled after W entry-timeframe bars (``Simulator.run_limit``); fields ``lim<W>_*``.
    - ``eligibility``: the first check at which the trigger is reported long / short (the first
      report if it was taken there, else a later check of the same trigger), with a market
      entry at that check; fields ``elig_check``, ``elig_lag_min``, ``elig_*``. None if never.
    - ``extra_horizons``: the market outcomes again with other horizons (days); ``h<D>_*``.
    """
    overrides, off = variant_config(variant)
    with checks_off(off):
        return _scan(symbol, stack_parts, start, end, variant, overrides, hours, max_days, minute_bars, progress,
                     limit_windows, eligibility, extra_horizons)


def _scan(symbol: str, stack_parts: Sequence[str], start: str, end: str, variant: str, overrides: dict[str, Any],
          hours: tuple[int, int] | None, max_days: float, minute_bars: pd.DataFrame | None, progress: bool,
          limit_windows: Sequence[int], eligibility: bool,
          extra_horizons: Sequence[float]) -> tuple[list[dict[str, Any]], list[tuple]]:
    stack = make_stack(*stack_parts)
    begin = pd.Timestamp(start, tz=BARS_TIMEZONE)
    finish = pd.Timestamp(end, tz=BARS_TIMEZONE)
    bias_tf = parse_timeframe(stack.bias)
    history = pd.Timedelta(days=500 if bias_tf.kind == "month" else 200 if bias_tf.kind == "week" else 120)
    if minute_bars is not None:
        source = HistoricalBarSource(minute_bars={symbol: minute_bars})
    else:
        source = HistoricalBarSource(start=begin - history, end=finish + pd.Timedelta(days=max_days + 3))
    minutes = source.minute_bars(symbol)
    style = TTradesStyle(config=load_config(overrides=overrides))
    entry_minutes = parse_timeframe(stack.entry).nominal_minutes
    sim = Simulator(minutes, symbol, max_days)
    adr = daily_range(minutes)
    times = check_times(minutes, stack.entry, begin, finish, hours)
    seen: set[tuple] = set()
    rows_by_key: dict[tuple, dict[str, Any]] = {}
    trades: list[dict[str, Any]] = []
    states: list[tuple] = []
    started = time.time()
    for count, moment in enumerate(times):
        if progress and count % 2000 == 0:
            print(f"{symbol} {stack.name} {variant}: {count}/{len(times)} {time.time() - started:.0f}s", flush=True)
        try:
            verdict = style.evaluate(symbol, moment.to_pydatetime(), stack, source)
        except Exception as error:  # a style bug on one bar must not kill a year-long run
            states.append((moment.isoformat(), "error", "", "", "", type(error).__name__))
            continue
        plan = verdict.plan
        states.append((moment.isoformat(), verdict.decision, verdict.path_family, verdict.stage, verdict.bias,
                       verdict.idea or "", plan.state if plan else ""))
        trigger = _trigger(verdict)
        if trigger is None:
            continue
        direction, since, entry_level, stop_level = trigger
        key = (direction, verdict.path_family, since.isoformat(), round(entry_level, 4), round(stop_level, 4))
        bias_open = _markup_start(verdict, "Forming bias candle open")
        bias_close = bar_close_time(bias_open, stack.bias) if bias_open is not None else None
        if key in seen:
            earlier = rows_by_key.get(key)
            if (eligibility and earlier is not None and earlier["elig_check"] is None
                    and verdict.decision in ("long", "short")):
                later = sim.run(direction, moment, stop_level, bias_close)
                earlier["elig_check"] = moment.isoformat()
                earlier["elig_lag_min"] = float((moment - pd.Timestamp(earlier["trigger_close"])) / pd.Timedelta(minutes=1))
                earlier.update(_sub("elig_", later) if later is not None else {"elig_skipped": "no data"})
            continue
        seen.add(key)
        trigger_close = bar_close_time(since, stack.entry)
        trigger_key = "cont_entry_trigger" if verdict.path_family == "continuation" else "rev_entry_trigger"
        trigger_item = _criterion(verdict, trigger_key)
        detail = trigger_item.detail if trigger_item is not None else ""
        adr_now = float(adr[adr.index <= moment].iloc[-1]) if (adr.index <= moment).any() else float("nan")
        row: dict[str, Any] = {
            "symbol": symbol,
            "stack": stack.name,
            "variant": variant,
            "check": moment.isoformat(),
            "decision": verdict.decision,
            "taken": verdict.decision in ("long", "short"),
            "direction": direction,
            "bias": verdict.bias,
            "path": verdict.path_family,
            "stage": verdict.stage,
            "blocking": _blocking(verdict),
            "trigger_open": since.isoformat(),
            "trigger_close": trigger_close.isoformat(),
            "lag_min": float((moment - trigger_close) / pd.Timedelta(minutes=1)),
            "trigger_kind": "cisd" if "CISD is the trigger" in detail else "order_block",
            "plan_entry": entry_level,
            "plan_stop": stop_level,
            "plan_state": plan.state if plan else "",
            "structural_targets": list(verdict.targets),
            "bias_open": bias_open.isoformat() if bias_open is not None else None,
            "bias_close": bias_close.isoformat() if bias_close is not None else None,
            "session": session_label(moment),
            "hour": moment.hour,
            "minute": moment.minute,
            "weekday": int(moment.dayofweek),
            "adr14": adr_now,
            "criteria": {item.key: item.passed for item in verdict.criteria},
            "why": verdict.why,
        }
        outcome = sim.run(direction, moment, stop_level, bias_close)
        if outcome is None:
            continue
        row.update(outcome)
        if "risk" in row and adr_now == adr_now and adr_now > 0:
            row["risk_adr"] = row["risk"] / adr_now
        for window in limit_windows:
            until = moment + pd.Timedelta(minutes=window * entry_minutes)
            row.update(_sub(f"lim{window}_", sim.run_limit(direction, moment, entry_level, stop_level, until, bias_close)))
        for days in extra_horizons:
            row.update(_sub(f"h{days:g}_", sim.run(direction, moment, stop_level, bias_close, max_days=days)))
        if eligibility:
            row["elig_check"] = row["check"] if row["taken"] else None
            row["elig_lag_min"] = row["lag_min"] if row["taken"] else None
            if row["taken"]:
                row.update(_sub("elig_", outcome))
            rows_by_key[key] = row
        trades.append(row)
    return trades, states


def read_bars_file(path: str | Path) -> pd.DataFrame:
    """Bars from a CSV with ``timestamp,open,high,low,close[,volume]`` (any bar size; tz-aware
    timestamps or naive New York times). Used for data that is not the Databento minute set:
    TradingView or Yahoo exports. Stacks whose timeframes are below the file's bar size
    cannot be run on it, and outcomes are walked on its bars instead of minutes."""
    frame = pd.read_csv(path)
    stamps = pd.to_datetime(frame["timestamp"], utc=True) if frame["timestamp"].astype(str).str.contains(r"[+-]\d\d:\d\d$|Z$").any()         else pd.to_datetime(frame["timestamp"]).dt.tz_localize(BARS_TIMEZONE)
    # nanosecond unit: the resampler's wall-minute arithmetic assumes it (pandas 3 parses to us)
    index = pd.DatetimeIndex(stamps).tz_convert(BARS_TIMEZONE).as_unit("ns")
    bars = pd.DataFrame({col: frame[col].astype(float).to_numpy() for col in ("open", "high", "low", "close")}, index=index)
    bars["volume"] = frame["volume"].astype(float).to_numpy() if "volume" in frame else 0.0
    bars.index.name = "timestamp"
    return bars[~bars.index.duplicated()].sort_index()


def _write(path: Path, trades: list[dict[str, Any]], states: list[tuple], meta: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        handle.write(json.dumps({"meta": meta}) + "\n")
        for trade in trades:
            handle.write(json.dumps(trade, default=str) + "\n")
    states_path = path.with_name(path.name.replace(".jsonl.gz", ".states.csv.gz"))
    frame = pd.DataFrame(states, columns=["as_of", "decision", "path", "stage", "bias", "idea", "plan"][: len(states[0])] if states else None)
    frame.to_csv(states_path, index=False, compression="gzip")


def run_job(job: dict[str, Any]) -> dict[str, Any]:
    started = time.time()
    out = Path(job["out"])
    if out.exists() and not job.get("force"):
        return {**job, "status": "exists"}
    try:
        bars = read_bars_file(job["bars_file"]) if job.get("bars_file") else None
        trades, states = scan(job["symbol"], job["stack"], job["start"], job["end"], job.get("variant", "baseline"),
                              tuple(job["hours"]) if job.get("hours") else None, job.get("max_days", 10.0),
                              minute_bars=bars, limit_windows=job.get("limit_windows", ()),
                              eligibility=job.get("eligibility", False), extra_horizons=job.get("extra_horizons", ()))
    except Exception as error:
        return {**job, "status": f"error: {type(error).__name__}: {error}"}
    meta = {**job, "checks": len(states), "trades": len(trades), "seconds": round(time.time() - started, 1)}
    _write(out, trades, states, meta)
    return {**job, "status": "ok", "trades": len(trades), "checks": len(states), "seconds": meta["seconds"]}


def grid_jobs(symbols: Sequence[str], years: Sequence[int], stacks: Sequence[tuple[str, str, str]],
              variants: Sequence[str], out_dir: Path, bars_dir: Path | None = None,
              bars_tf: str = "5m", clip_start: str | None = None, clip_end: str | None = None,
              **extras: Any) -> Iterator[dict[str, Any]]:
    """One job per year x variant x stack x symbol. ``extras`` (``max_days``, ``limit_windows``,
    ``eligibility``, ``extra_horizons``) are copied into every job. ``clip_start`` / ``clip_end``
    (YYYY-MM-DD) cut each year's window, so a run can start or stop mid-year."""
    for year in years:
        start, end = f"{year}-01-01", f"{year + 1}-01-01"
        if clip_start is not None:
            start = max(start, clip_start)
        if clip_end is not None:
            end = min(end, clip_end)
        if start >= end:
            continue
        for variant in variants:
            for parts in stacks:
                for symbol in symbols:
                    slug = "-".join(parts).replace(" ", "")
                    bars_file = bars_dir / f"{symbol}_{bars_tf}.csv" if bars_dir is not None else None
                    if bars_file is not None and parse_timeframe(parts[2]).nominal_minutes < parse_timeframe(bars_tf).nominal_minutes:
                        continue  # entry timeframe finer than the file's bars
                    yield {
                        "bars_file": str(bars_file) if bars_file is not None else None,
                        "symbol": symbol,
                        "stack": list(parts),
                        "start": start,
                        "end": end,
                        "variant": variant,
                        # minute-entry stacks: London open to New York close only (runtime)
                        "hours": [1, 16] if parts[2] == "1m" else None,
                        "out": str(out_dir / f"{year}" / variant / f"{symbol}_{slug}.jsonl.gz"),
                        **extras,
                    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="companion.tools.backtest", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("run")
    one.add_argument("--symbol", default="NQ")
    one.add_argument("--stack", default="1D / 1h / 5m")
    one.add_argument("--start", required=True)
    one.add_argument("--end", required=True)
    one.add_argument("--variant", default="baseline", help=f"one of {sorted(VARIANTS)} or {OFF_PREFIX}<quality check key>")
    one.add_argument("--hours", nargs=2, type=int)
    one.add_argument("--out", required=True)
    one.add_argument("--bars-file", help="CSV of bars to use instead of the Databento minute set")
    grid = sub.add_parser("grid")
    grid.add_argument("--symbols", nargs="*", default=["NQ", "ES", "GC"])
    grid.add_argument("--years", nargs="*", type=int, default=[2025])
    grid.add_argument("--stacks", nargs="*", help='e.g. "1D/1h/5m"; default: all nine')
    grid.add_argument("--variants", nargs="*", default=["baseline"])
    grid.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 4))
    grid.add_argument("--out-dir", default="results/backtest")
    grid.add_argument("--bars-dir", help="read <dir>/<SYMBOL>_<bars-tf>.csv instead of the Databento minute set")
    grid.add_argument("--bars-tf", default="5m")
    grid.add_argument("--dry-run", action="store_true", help="print the jobs and exit")
    grid.add_argument("--start", help="YYYY-MM-DD: clip the first year's window to start here")
    grid.add_argument("--end", help="YYYY-MM-DD: clip the last year's window to end here (exclusive)")
    for command in (one, grid):
        command.add_argument("--max-days", type=float, default=10.0, help="outcome horizon in calendar days")
        command.add_argument("--limit-windows", nargs="*", type=int, default=[],
                             help="limit-at-plan-entry outcomes, order valid for W entry bars (lim<W>_*)")
        command.add_argument("--eligibility", action="store_true", help="record the first check reporting long / short")
        command.add_argument("--extra-horizons", nargs="*", type=float, default=[], help="market outcomes at other horizons")
    args = parser.parse_args(argv)
    extras = {"max_days": args.max_days, "limit_windows": args.limit_windows, "eligibility": args.eligibility,
              "extra_horizons": args.extra_horizons}

    if args.command == "run":
        parts = [part.strip() for part in args.stack.split("/")]
        bars = read_bars_file(args.bars_file) if args.bars_file else None
        trades, states = scan(args.symbol, parts, args.start, args.end, args.variant,
                              tuple(args.hours) if args.hours else None, args.max_days, progress=True, minute_bars=bars,
                              limit_windows=args.limit_windows, eligibility=args.eligibility,
                              extra_horizons=args.extra_horizons)
        _write(Path(args.out), trades, states, {"symbol": args.symbol, "stack": parts, "start": args.start, "end": args.end})
        taken = [t for t in trades if t["taken"]]
        print(f"{len(states)} checks, {len(trades)} triggers, {len(taken)} taken")
        return 0

    stacks = ALL_STACKS if not args.stacks else [tuple(p.strip() for p in s.split("/")) for s in args.stacks]
    jobs = list(grid_jobs(args.symbols, args.years, stacks, args.variants, Path(args.out_dir),
                          Path(args.bars_dir) if args.bars_dir else None, args.bars_tf,
                          clip_start=args.start, clip_end=args.end, **extras))
    if args.dry_run:
        print(json.dumps(jobs, indent=1))
        return 0
    # longest jobs (minute entry) first so the pool drains evenly
    jobs.sort(key=lambda job: {"1m": 0, "3m": 1, "5m": 2}.get(job["stack"][2], 3))
    print(f"{len(jobs)} jobs on {args.workers} workers", flush=True)
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(run_job, job) for job in jobs]
        for future in as_completed(futures):
            result = future.result()
            print(json.dumps({k: result[k] for k in ("symbol", "stack", "variant", "start", "status") if k in result}
                             | {k: result[k] for k in ("trades", "checks", "seconds") if k in result}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
