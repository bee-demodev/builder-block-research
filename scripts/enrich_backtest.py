"""Add bar-derived context features and alternative exits to every backtest trigger.

    .venv/Scripts/python scripts/enrich_backtest.py --source tv        # -> results/backtest_tv/report/trades_enriched.pkl
    .venv/Scripts/python scripts/enrich_backtest.py --source databento # -> results/backtest/report/trades_enriched.pkl

Sources. ``tv`` (primary): TradingView 5m front-month bars, data/external/tradingview/<SYM>_5m.csv, read with
``companion.tools.backtest.read_bars_file``; the backtest walked its outcomes on the same 5m bars.
``databento``: the cleaned Databento minutes (partial: many NY-session minutes are missing), used only for
the 1m/3m-entry stacks and labelled low confidence.

Reads the raw ``*.jsonl.gz`` files of ``companion.tools.backtest`` under
``<root>/<year>/<variant>/`` (years 2024-2026 when present), applies the same row filters as
``scripts/analyze_backtest.py`` (skipped fills, stops under two ticks) and adds two kinds of
columns.

FEATURES (known at ``check``; no lookahead)
------------------------------------------
Every feature reads only bars that CLOSED by ``check`` (a bar of length L opened at t is used
only when t + L <= check), plus the plan levels the verdict reported at ``check``. The code
asserts this per row (``_assert_causal``). The reference price ``px`` is the close of the last
bar closed by ``check``. The trading day starts 18:00 New York.

- ``adr_used``: (today's high - today's low so far) / adr14.
- ``pd_pos``: (px - PDL) / (PDH - PDL), PDH/PDL = previous trading day's high/low.
  ``pd_pos_dir``: the same seen from the trade (long: pd_pos, short: 1 - pd_pos), so low =
  buying in discount / selling in premium.
- ``tgt_dist_r`` / ``tgt_dist_adr``: distance from px to the previous-day level ahead of the
  trade (long: PDH, short: PDL), in R (risk) and in ADR. Negative = already beyond it.
  ``behind_dist_r``: same to the level behind the trade.
- ``pd_target_taken`` (long: PDH already exceeded today), ``pd_stop_swept`` (long: PDL
  already taken today).
- ``bias_rel``: "with" / "against" / "neutral" (direction vs the ``bias`` field).
- ``on_target_taken`` / ``on_stop_swept``: overnight (18:00-09:30) high / low exceeded after
  09:30 and before check, ahead of / behind the trade. NaN when check is before 09:30.
- ``smt``: symbol vs its partner (TradingView: NQ/ES, YM->ES, RTY->ES, GC/SI; Databento: NQ/ES). Swing = 15m 2-left/2-right fractal of the traded symbol, confirmed (bar
  i+2 closed) before check, the most recent within 24h. Comparable level in the partner = its
  extreme over the same 15m bars i-1..i+1. "Taken" = any minute from the open of bar i+2 to
  check beyond the level. Bearish SMT = exactly one of the two took its swing high; bullish SMT
  = exactly one took its swing low. ``smt_with`` = SMT in the trade's direction (long + bullish,
  short + bearish), ``smt_against`` the reverse. No partner (CL, 6E; GC on Databento): NaN.
- ``rs_self_stronger``: % change from today's 18:00 open at check, traded symbol vs partner;
  long -> self higher, short -> self lower. No partner: NaN.
- ``min_since_930``: minutes from 09:30 to check (negative before 09:30).
- ``setup_min_in`` / ``setup_frac``: position of check inside the setup-timeframe candle that
  contains the check minute (0 = first minute of a new setup candle). ``bias_frac``: same for
  the forming bias candle (``bias_open``/``bias_close`` fields).
- ``day_move_dir``: (px - today's open) / adr14, signed in the trade direction.
  ``opp_run_adr``: today's run against the trade from the open (long: open - low) / adr14.
- ``inside_prev_day``: yesterday's range inside the day before. ``first_day_of_month``.
- ``news_day``: FOMC / CPI / NFP release day, 2024-2025 only (NaN in 2026). ``fomc_day``: 2024-2026.
  Dates typed from public calendars; see NEWS.
- ``trade_seq_day``: 1 for the first trigger of the trading day for that symbol/stack/variant
  (in check order), 2 for the second, ...

OUTCOMES (read minute bars from the fill onward; these are labels, never features)
----------------------------------------------------------------------------------
- ``reached_1r``: +1R touched before the stop. ``mae_after_1r``: lowest R reached after the
  bar that touched +1R and before +2R (or the horizon). ``be_after_1r``: that low is <= 0
  (price came back to the entry before 2R).
- ``net_be2r``: 2R target with the stop moved to the entry once +1R is touched (from the next
  bar). ``net_partial``: half off at +1R, the rest to 2R with the stop at the entry.
- ``r_t1000`` / ``r_t1100`` / ``r_t1600``: time exit at 10:00 / 11:00 / 16:00 New York on the
  fill's trading day (stop stays live; fills at or after that time: NaN). ``r_t1100_2r``: the
  same with a 2R target that can fill first.
All net of the trade's ``cost_r``. Same bar conventions as the harness: a bar reaching the
adverse level and a target counts as adverse.
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from companion.bars import load_minute_bars  # noqa: E402
from companion.tools.backtest import CONTRACTS, read_bars_file  # noqa: E402

TICKS = {symbol: spec[0] for symbol, spec in CONTRACTS.items()}
TV_DIR = ROOT / "data/external/tradingview"
PARTNERS = {"tv": {"NQ": "ES", "ES": "NQ", "YM": "ES", "RTY": "ES", "GC": "SI", "SI": "GC"},
            "databento": {"NQ": "ES", "ES": "NQ"}}
DAY_START = 18 * 60  # minutes after midnight
OPEN_930 = (9 * 60 + 30 - DAY_START) % 1440  # offset of 09:30 inside the trading day (930)
HORIZON_MIN = 10 * 1440

# Release days (New York date). FOMC = statement day (14:00). CPI and NFP 08:30.
# Typed from the Fed / BLS release calendars; 2025 Oct-Dec shifted by the federal shutdown.
NEWS = {
    "fomc": "2024-01-31 2024-03-20 2024-05-01 2024-06-12 2024-07-31 2024-09-18 2024-11-07 2024-12-18 "
            "2025-01-29 2025-03-19 2025-05-07 2025-06-18 2025-07-30 2025-09-17 2025-10-29 2025-12-10 "
            "2026-01-28 2026-03-18 2026-04-29 2026-06-17 2026-07-29 2026-09-16 2026-10-28",
    "cpi": "2024-01-11 2024-02-13 2024-03-12 2024-04-10 2024-05-15 2024-06-12 2024-07-11 2024-08-14 2024-09-11 "
           "2024-10-10 2024-11-13 2024-12-11 2025-01-15 2025-02-12 2025-03-12 2025-04-10 2025-05-13 2025-06-11 "
           "2025-07-15 2025-08-12 2025-09-11 2025-10-24 2025-12-18",
    "nfp": "2024-01-05 2024-02-02 2024-03-08 2024-04-05 2024-05-03 2024-06-07 2024-07-05 2024-08-02 2024-09-06 "
           "2024-10-04 2024-11-01 2024-12-06 2025-01-10 2025-02-07 2025-03-07 2025-04-04 2025-05-02 2025-06-06 "
           "2025-07-03 2025-08-01 2025-09-05 2025-11-20 2025-12-16",
}

RAW_KEEP = (
    "symbol stack variant check decision taken direction bias path stage blocking trigger_kind lag_min session hour "
    "minute weekday adr14 risk risk_adr cost_r mfe_r mae_r minutes_to_stop first_1r first_1.5r first_2r first_3r "
    "net_1r net_1.5r net_2r net_3r r_bias_close minutes_1r minutes_2r skipped plan_state trigger_open trigger_close "
    "bias_open bias_close plan_entry plan_stop fill fill_time"
).split()


def tf_minutes(label: str) -> int | None:
    unit, count = label[-1], int(label[:-1])
    return {"m": count, "h": 60 * count, "D": 1440 * count}.get(unit)


def load_rows(root: Path) -> pd.DataFrame:
    rows = []
    for year in ("2024", "2025", "2026"):
        for path in sorted((root / year).glob("*/*.jsonl.gz")):
            with gzip.open(path, "rt", encoding="utf-8") as handle:
                handle.readline()
                for line in handle:
                    trade = json.loads(line)
                    row = {key: trade.get(key) for key in RAW_KEEP}
                    row["year"] = int(year)
                    for key, value in (trade.get("criteria") or {}).items():
                        row[f"c:{key}"] = value
                    rows.append(row)
    frame = pd.DataFrame(rows)
    frame = frame[frame["skipped"].isna() & frame["risk"].notna()].copy()
    frame = frame[frame["risk"] >= 2 * frame["symbol"].map(TICKS)].copy()
    frame["blocking"] = frame["blocking"].apply(lambda v: tuple(v) if isinstance(v, list) else ())
    for col in ("check", "bias_open", "bias_close", "trigger_close"):
        frame[col] = pd.to_datetime(frame[col], utc=True).dt.tz_convert("America/New_York")
    frame = frame[frame["check"].dt.year == frame["year"]].copy()
    frame["fresh"] = frame["lag_min"] <= 0
    return frame.reset_index(drop=True)


def wall_minutes(stamps) -> np.ndarray:
    """New York wall-clock minutes since 1970-01-01 00:00 (naive)."""
    naive = pd.DatetimeIndex(stamps).tz_localize(None)
    return naive.values.astype("datetime64[m]").astype(np.int64)


class Bars:
    """Bar arrays (1m Databento or 5m TradingView) of one symbol with per-trading-day running extremes."""

    def __init__(self, symbol: str, source: str):
        if source == "tv":
            frame = read_bars_file(TV_DIR / f"{symbol}_5m.csv")
            frame = frame[frame.index >= pd.Timestamp("2023-11-01", tz="America/New_York")]
        else:
            frame = load_minute_bars(symbol, "2023-11-01", "2026-01-20")
        frame = frame.dropna(subset=["open", "high", "low", "close"])
        assert len(frame), f"no bars for {symbol}"
        self.t = wall_minutes(frame.index)
        self.step = int(np.median(np.diff(self.t)))  # bar length in minutes (1 or 5)
        self.o, self.h, self.l, self.c = (frame[k].to_numpy(float) for k in ("open", "high", "low", "close"))
        self.day = (self.t - DAY_START) // 1440
        self.off = (self.t - DAY_START) % 1440
        s = pd.DataFrame({"d": self.day, "h": self.h, "l": self.l})
        self.cum_h = s.groupby("d")["h"].cummax().to_numpy()
        self.cum_l = s.groupby("d")["l"].cummin().to_numpy()
        post = self.off >= OPEN_930
        s2 = pd.DataFrame({"d": self.day, "h": np.where(post, self.h, -np.inf), "l": np.where(post, self.l, np.inf)})
        self.post_h = s2.groupby("d")["h"].cummax().to_numpy()
        self.post_l = s2.groupby("d")["l"].cummin().to_numpy()
        daily = pd.DataFrame({"d": self.day, "o": self.o, "h": self.h, "l": self.l, "c": self.c, "on": ~post})
        g = daily.groupby("d")
        self.daily = pd.DataFrame({"open": g["o"].first(), "high": g["h"].max(), "low": g["l"].min()})
        on = daily[daily["on"]].groupby("d")
        self.daily["on_high"] = on["h"].max()
        self.daily["on_low"] = on["l"].min()
        self.daily["prev_high"] = self.daily["high"].shift(1)
        self.daily["prev_low"] = self.daily["low"].shift(1)
        self.daily["inside_prev"] = (self.daily["high"].shift(1) <= self.daily["high"].shift(2)) & (
            self.daily["low"].shift(1) >= self.daily["low"].shift(2))
        dates = pd.to_datetime(self.daily.index + 1, unit="D")  # trading date = day after the 18:00 open
        self.daily["date"] = dates
        month = dates.to_period("M")
        self.daily["first_of_month"] = ~pd.Series(month, index=self.daily.index).duplicated().to_numpy()
        # 15m bars for swings (open time in wall minutes)
        m15 = (self.t - DAY_START) // 15
        b = pd.DataFrame({"k": m15, "h": self.h, "l": self.l}).groupby("k").agg(h=("h", "max"), l=("l", "min"))
        self.b15 = b

    def last_before(self, moment: int) -> int:
        """Index of the last bar that has CLOSED by ``moment`` (open + step <= moment)."""
        return int(np.searchsorted(self.t, moment - self.step, side="right")) - 1

    def range_max(self, a: int, b: int) -> float:
        return float(self.h[a:b + 1].max()) if b >= a else np.nan

    def range_min(self, a: int, b: int) -> float:
        return float(self.l[a:b + 1].min()) if b >= a else np.nan


def _assert_causal(bars: Bars, k: int, check: int) -> None:
    # the last bar used closed by check
    assert k < 0 or bars.t[k] + bars.step <= check, "lookahead: feature bar closes after check"


def swing_state(own: Bars, other: Bars, check: int, k_own: int, k_oth: int) -> dict:
    """SMT at check from the traded symbol's latest confirmed 15m swings (see module doc)."""
    out = {}
    last_closed = (check - DAY_START) // 15 - 1  # 15m bar index whose close <= check
    b = own.b15
    lo_key = last_closed - 96
    window = b.loc[lo_key:last_closed]
    if len(window) < 6:
        return {"smt_bear": np.nan, "smt_bull": np.nan}
    keys = window.index.to_numpy()
    for side, col, cmp in (("bear", "h", np.greater), ("bull", "l", np.less)):
        vals = window[col].to_numpy()
        found = None
        for j in range(len(vals) - 3, 1, -1):  # bar i needs i+2 closed: j <= len-3
            if keys[j] + 2 > last_closed:
                continue
            if keys[j - 2] != keys[j] - 2 or keys[j + 2] != keys[j] + 2:
                continue
            v = vals[j]
            if cmp(v, vals[j - 1]) and cmp(v, vals[j - 2]) and cmp(v, vals[j + 1]) and cmp(v, vals[j + 2]):
                found = keys[j]
                break
        if found is None:
            out[f"smt_{side}"] = np.nan
            continue
        assert found + 2 <= last_closed and (found + 3) * 15 + DAY_START <= check, "lookahead: swing not confirmed"
        ref_own = b.at[found, col]
        part = other.b15.loc[found - 1:found + 1, col]
        if part.empty:
            out[f"smt_{side}"] = np.nan
            continue
        ref_oth = part.max() if col == "h" else part.min()
        start = (found + 2) * 15 + DAY_START
        a_own = int(np.searchsorted(own.t, start, side="left"))
        a_oth = int(np.searchsorted(other.t, start, side="left"))
        if col == "h":
            took_own = a_own <= k_own and own.range_max(a_own, k_own) > ref_own
            took_oth = a_oth <= k_oth and other.range_max(a_oth, k_oth) > ref_oth
        else:
            took_own = a_own <= k_own and own.range_min(a_own, k_own) < ref_own
            took_oth = a_oth <= k_oth and other.range_min(a_oth, k_oth) < ref_oth
        out[f"smt_{side}"] = float(took_own != took_oth)
        out[f"smt_{side}_own_took"] = float(took_own)
    return out


def path_outcomes(bars: Bars, f: int, sign: float, fill: float, risk: float, cost: float, tick: float) -> dict:
    """Alternative exits walked on minute bars from the fill bar f onward."""
    last = int(np.searchsorted(bars.t, bars.t[f] + HORIZON_MIN, side="left"))
    h, l, c = bars.h[f:last], bars.l[f:last], bars.c[f:last]
    fav = (h - fill) if sign > 0 else (fill - l)
    adv = (fill - l) if sign > 0 else (h - fill)
    stop_i = np.flatnonzero(adv >= risk)
    stop_at = int(stop_i[0]) if len(stop_i) else len(fav)
    out: dict = {}
    h1 = np.flatnonzero(fav[:stop_at] >= risk)
    mtm = sign * (c[-1] - fill) / risk - cost if len(c) else 0.0
    if len(h1):
        i1 = int(h1[0])
        out["reached_1r"] = True
        h2 = np.flatnonzero(fav[i1:] >= 2 * risk)
        i2 = i1 + int(h2[0]) if len(h2) else None
        be = np.flatnonzero(adv[i1 + 1:] >= 0)
        ib = i1 + 1 + int(be[0]) if len(be) else None
        end = min(i2 if i2 is not None else len(fav), stop_at)
        seg = adv[i1 + 1:end]  # adverse excursion after the +1R bar, before 2R / the stop
        low = float(-seg.max() / risk) if len(seg) else 1.0
        out["mae_after_1r"] = -1.0 if stop_at < (i2 if i2 is not None else len(fav)) else min(low, 1.0)
        if i2 is not None and (ib is None or i2 < ib):
            rem = 2.0 + tick / risk
            out["be_after_1r"] = False
        elif ib is not None:
            rem = 0.0
            out["be_after_1r"] = True
        else:
            rem = sign * (c[-1] - fill) / risk
            out["be_after_1r"] = False
        out["net_be2r"] = rem - cost
        out["net_partial"] = 0.5 * (1.0 + tick / risk) + 0.5 * rem - cost
    else:
        out["reached_1r"] = False
        loss = -1.0 - cost if stop_at < len(fav) else mtm
        out["net_be2r"] = out["net_partial"] = loss
    # time exits on the fill's trading day
    day = bars.day[f]
    h2all = np.flatnonzero(fav[:stop_at] >= 2 * risk)
    i2r = int(h2all[0]) if len(h2all) else None
    for label, off in (("t1000", 16 * 60), ("t1100", 17 * 60), ("t1600", 22 * 60)):
        if bars.off[f] >= off:
            out[f"r_{label}"] = np.nan
            if label == "t1100":
                out["r_t1100_2r"] = np.nan
            continue
        e = int(np.searchsorted(bars.t, day * 1440 + DAY_START + off, side="left")) - 1 - f
        if e < 0:
            out[f"r_{label}"] = np.nan
            continue
        e = min(e, len(c) - 1)
        r = -1.0 - cost if stop_at <= e else sign * (c[e] - fill) / risk - cost
        out[f"r_{label}"] = r
        if label == "t1100":
            out["r_t1100_2r"] = (2.0 + tick / risk - cost) if (i2r is not None and i2r <= e) else r
    return out


def enrich_symbol(symbol: str, frame: pd.DataFrame, source: str) -> pd.DataFrame:
    own = Bars(symbol, source)
    partner = PARTNERS[source].get(symbol)
    other = Bars(partner, source) if partner else None
    tick = TICKS[symbol]
    news_days = {pd.Timestamp(d) for v in NEWS.values() for d in v.split()}
    fomc_days = {pd.Timestamp(d) for d in NEWS["fomc"].split()}
    checks = wall_minutes(pd.DatetimeIndex(frame["check"]))
    has_bias = (frame["bias_open"].notna() & frame["bias_close"].notna()).to_numpy()
    bias_open = wall_minutes(pd.DatetimeIndex(frame["bias_open"]))
    bias_close = wall_minutes(pd.DatetimeIndex(frame["bias_close"]))
    records = []
    for pos, row in enumerate(frame.itertuples(index=False)):
        check = int(checks[pos])
        sign = 1.0 if row.direction == "long" else -1.0
        k = own.last_before(check)
        _assert_causal(own, k, check)
        f = int(np.searchsorted(own.t, check, side="left"))  # fill bar: first bar opening at/after check
        if f >= len(own.t):
            records.append({})
            continue
        rec: dict = {}
        dcur = (check - DAY_START) // 1440
        adr = row.adr14
        risk = row.risk
        px = own.c[k]
        same_day = own.day[k] == dcur
        dh = own.cum_h[k] if same_day else np.nan
        dl = own.cum_l[k] if same_day else np.nan
        d = own.daily.loc[dcur] if dcur in own.daily.index else None
        rec["adr_used"] = (dh - dl) / adr if same_day else 0.0
        if d is not None and np.isfinite(d["prev_high"]):
            pdh, pdl = d["prev_high"], d["prev_low"]
            pos_ = (px - pdl) / (pdh - pdl) if pdh > pdl else np.nan
            rec["pd_pos"] = pos_
            rec["pd_pos_dir"] = pos_ if sign > 0 else 1 - pos_
            ahead, behind = (pdh, pdl) if sign > 0 else (pdl, pdh)
            rec["tgt_dist_r"] = sign * (ahead - px) / risk
            rec["tgt_dist_adr"] = sign * (ahead - px) / adr
            rec["behind_dist_r"] = sign * (px - behind) / risk
            taken_h = bool(same_day and dh > pdh)
            taken_l = bool(same_day and dl < pdl)
            rec["pd_target_taken"] = taken_h if sign > 0 else taken_l
            rec["pd_stop_swept"] = taken_l if sign > 0 else taken_h
            rec["inside_prev_day"] = bool(d["inside_prev"])
            rec["first_day_of_month"] = bool(d["first_of_month"])
            date = d["date"]
            rec["news_day"] = (date in news_days) if date.year in (2024, 2025) else np.nan
            rec["fomc_day"] = date in fomc_days
            if same_day:
                dopen = d["open"]
                # the day's open is the first minute's open: known once that minute has opened (<= k)
                rec["day_move_dir"] = sign * (px - dopen) / adr
                rec["opp_run_adr"] = ((dopen - dl) if sign > 0 else (dh - dopen)) / adr
                rec["pct_from_open"] = (px - dopen) / dopen
        off = (check - DAY_START) % 1440
        rec["min_since_930"] = off - OPEN_930
        if off >= OPEN_930 and same_day and d is not None:
            onh, onl = d["on_high"], d["on_low"]
            ph, pl = own.post_h[k], own.post_l[k]
            up, down = bool(ph > onh), bool(pl < onl)
            rec["on_target_taken"] = up if sign > 0 else down
            rec["on_stop_swept"] = down if sign > 0 else up
        setup_tf = row.stack.split(" / ")[1]
        m = tf_minutes(setup_tf)
        if m is not None and m <= 1440:
            rec["setup_min_in"] = off % m
            rec["setup_frac"] = (off % m) / m
        if has_bias[pos] and bias_close[pos] > bias_open[pos]:
            rec["bias_frac"] = (check - bias_open[pos]) / (bias_close[pos] - bias_open[pos])
        if other is not None:
            k2 = other.last_before(check)
            _assert_causal(other, k2, check)
            if k2 >= 0 and other.day[k2] == dcur and dcur in other.daily.index and "pct_from_open" in rec:
                o2 = other.daily.at[dcur, "open"]
                p2 = (other.c[k2] - o2) / o2
                rec["rs_self_stronger"] = float(rec["pct_from_open"] > p2) if sign > 0 else float(rec["pct_from_open"] < p2)
            smt = swing_state(own, other, check, k, k2)
            rec.update(smt)
            if np.isfinite(smt.get("smt_bull", np.nan)) and np.isfinite(smt.get("smt_bear", np.nan)):
                bull, bear = smt["smt_bull"] == 1, smt["smt_bear"] == 1
                rec["smt_with"] = float(bull if sign > 0 else bear)
                rec["smt_against"] = float(bear if sign > 0 else bull)
        # outcomes from the fill on
        assert own.t[f] >= check, "fill minute must open at or after check"
        if abs(own.o[f] + sign * tick - row.fill) > 1e-6:
            rec["fill_mismatch"] = True
        rec.update(path_outcomes(own, f, sign, row.fill, risk, row.cost_r, tick))
        records.append(rec)
    extra = pd.DataFrame(records, index=frame.index)
    return pd.concat([frame, extra], axis=1)


def _job(args: tuple[str, pd.DataFrame, str]) -> pd.DataFrame:
    symbol, frame, source = args
    return enrich_symbol(symbol, frame, source)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=("tv", "databento"), default="tv")
    parser.add_argument("--root", help="default: results/backtest_tv (tv) or results/backtest (databento)")
    parser.add_argument("--out", help="default: <root>/report/trades_enriched.pkl")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--limit", type=int, default=0, help="rows per symbol (smoke test)")
    args = parser.parse_args()
    args.root = args.root or ("results/backtest_tv" if args.source == "tv" else "results/backtest")
    args.out = args.out or f"{args.root}/report/trades_enriched.pkl"
    frame = load_rows(ROOT / args.root)
    print(f"{len(frame)} rows; variants: {frame.groupby(['year', 'variant']).size().to_dict()}", flush=True)
    jobs = []
    for symbol, part in frame.groupby("symbol"):
        part = part.sort_values("check")
        jobs.append((symbol, part.head(args.limit) if args.limit else part, args.source))
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        parts = list(pool.map(_job, jobs))
    out = pd.concat(parts).sort_values(["symbol", "stack", "variant", "check"])
    out["source"] = args.source
    # trigger order within the trading day (per symbol / stack / variant)
    day = (wall_minutes(pd.DatetimeIndex(out["check"])) - DAY_START) // 1440
    out["trading_day"] = day
    out["trade_seq_day"] = out.groupby(["symbol", "stack", "variant", "trading_day"]).cumcount() + 1
    out["taken_seq_day"] = np.where(out["taken"], out[out["taken"]].groupby(
        ["symbol", "stack", "variant", "trading_day"]).cumcount().reindex(out.index).fillna(-1) + 1, np.nan)
    print("fill mismatches:", int(out.get("fill_mismatch", pd.Series(dtype=bool)).fillna(False).sum()))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    out.to_pickle(args.out)
    print(f"wrote {args.out}: {len(out)} rows, {out.shape[1]} columns")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
