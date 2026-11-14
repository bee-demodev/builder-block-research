"""Score the Phase B pre-registered tests (results/phase_b/PREREGISTERED_PHASE_B.md).

    .venv/Scripts/python -m scripts.phase_b_tests

Reads the runs written by ``scripts.phase_b_runs`` and prints T1-T4 with their verdicts. Also
writes ``results/phase_b/report.md`` and ``results/phase_b/signals.csv.gz`` (one row per taken
signal with the market and limit outcomes).
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd

from companion.tools.backtest import COMMISSION_USD, CONTRACTS, read_bars_file

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "results/phase_b"
GROUPS = ("u21", "2022", "2023", "2024", "2025", "2026")
SYMBOLS = ("NQ", "ES", "GC", "YM", "RTY", "CL", "SI", "6E")
HORIZON = pd.Timedelta(days=10)
KEY = ["symbol", "stack", "trigger_open", "direction"]


def load(group: str, variant: str) -> pd.DataFrame:
    rows = []
    for path in sorted((RUNS / group / variant).glob("*.jsonl.gz")):
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            handle.readline()
            for line in handle:
                trade = json.loads(line)
                if trade.get("skipped") or trade.get("risk") is None:
                    continue
                trade["group"] = group
                rows.append(trade)
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    return frame.drop_duplicates(KEY, keep="first").reset_index(drop=True)


def clustered(values: pd.Series, clusters: pd.Series) -> tuple[float, float, int]:
    """Mean, clustered t and n."""
    x = values.to_numpy(dtype=float)
    n = len(x)
    if n < 2:
        return (float(x.mean()) if n else float("nan")), float("nan"), n
    mean = x.mean()
    sums = pd.Series(x - mean).groupby(clusters.to_numpy()).sum().to_numpy()
    se = np.sqrt((sums**2).sum()) / n
    return float(mean), float(mean / se) if se > 0 else float("nan"), n


def day_cluster(frame: pd.DataFrame) -> pd.Series:
    checks = pd.to_datetime(frame["check"], utc=True).dt.tz_convert("America/New_York")
    trading_day = (checks.dt.tz_localize(None) + pd.Timedelta(hours=6)).dt.normalize()
    return frame["symbol"] + " " + trading_day.astype(str)


class LimitSim:
    """T1: a limit at the plan entry, placed at the first report."""

    def __init__(self, symbol: str) -> None:
        bars = read_bars_file(ROOT / f"data/external/tradingview/{symbol}_5m.csv")
        self.index = bars.index
        self.open, self.high = bars["open"].to_numpy(), bars["high"].to_numpy()
        self.low, self.close = bars["low"].to_numpy(), bars["close"].to_numpy()
        tick, point_value = CONTRACTS[symbol]
        self.tick, self.commission = tick, COMMISSION_USD / point_value

    def run(self, row: pd.Series) -> dict[str, object]:
        sign = 1.0 if row["direction"] == "long" else -1.0
        entry, stop = float(row["plan_entry"]), float(row["plan_stop"])
        check = pd.Timestamp(row["check"])
        plan_risk = sign * (entry - stop)
        none = {"lim_filled": False, "lim_r": 0.0, "lim_why": ""}
        if not plan_risk > 0:
            return {**none, "lim_why": "no risk"}
        first = int(self.index.searchsorted(check, side="left"))
        if first >= len(self.index):
            return {**none, "lim_why": "no data"}
        end_time = check + HORIZON
        cancel_time = min(end_time, pd.Timestamp(row["bias_close"])) if row.get("bias_close") else end_time
        last = int(self.index.searchsorted(end_time, side="left"))
        cancel_at = int(self.index.searchsorted(cancel_time, side="left"))
        plan_target = entry + sign * 2 * plan_risk
        fill_bar = fill = None
        for k in range(first, min(cancel_at, last)):
            o, hi, lo = self.open[k], self.high[k], self.low[k]
            if sign * (o - stop) <= 0:
                return {**none, "lim_why": "opened beyond the stop"}
            if sign * (entry - o) >= 0:  # opens at or through the entry: a marketable limit fills at the open
                fill_bar, fill = k, float(o)
                break
            through = (lo <= entry - self.tick) if sign > 0 else (hi >= entry + self.tick)
            ran = (hi >= plan_target) if sign > 0 else (lo <= plan_target)
            if ran:  # the target traded first (or in the same bar): treat as cancelled
                return {**none, "lim_why": "ran to 2R first"}
            if through:
                fill_bar, fill = k, entry
                break
        if fill_bar is None:
            return {**none, "lim_why": "expired"}
        risk = sign * (fill - stop)
        if not risk > 0:
            return {**none, "lim_why": "no risk"}
        exit_cost = (self.tick + self.commission) / risk
        target = fill + sign * 2 * risk
        for k in range(fill_bar, last):
            hit_stop = (self.low[k] <= stop) if sign > 0 else (self.high[k] >= stop)
            if hit_stop:
                return {"lim_filled": True, "lim_r": -1.0 - exit_cost, "lim_why": "stop", "lim_fill": fill}
            if k > fill_bar and ((self.high[k] >= target) if sign > 0 else (self.low[k] <= target)):
                return {"lim_filled": True, "lim_r": 2.0 - self.commission / risk, "lim_why": "target", "lim_fill": fill}
        close = float(self.close[last - 1]) if last > fill_bar else fill
        return {"lim_filled": True, "lim_r": sign * (close - fill) / risk - exit_cost, "lim_why": "open", "lim_fill": fill}


def table(rows: list[dict[str, object]]) -> str:
    if not rows:
        return "(none)\n"
    heads = list(rows[0])
    out = ["| " + " | ".join(heads) + " |", "|" + "---|" * len(heads)]
    for row in rows:
        out.append("| " + " | ".join(f"{v:+.3f}" if isinstance(v, float) else str(v) for v in row.values()) + " |")
    return "\n".join(out) + "\n"


def main() -> int:
    lines: list[str] = ["# Phase B pre-registered tests: results\n"]
    base = pd.concat([load(g, "baseline") for g in GROUPS], ignore_index=True)
    base = base[base["stack"] != "1M / 1D / 1h"]
    # a baseline file with no quality check ever blocking was run with the checks off (the
    # first run leaked the quality_off patch into later jobs): refuse to score such a mix
    from companion.styles.ttrades import checklist

    quality = {s.key for specs in (checklist.SHARED, checklist.CONTINUATION, checklist.REVERSAL)
               for s in specs if s.role == checklist.QUALITY} | {"objective_at_trigger_ok"}
    blocked = base.groupby(["group", "symbol", "stack"])["blocking"].apply(lambda rows: any(set(r) & quality for r in rows))
    if not blocked.all():
        raise SystemExit(f"baseline files with no quality check blocking: {list(blocked[~blocked].index)}")
    lines.append(f"Checked: all {len(blocked)} baseline files list a quality check as blocking somewhere (the checks were on).\n")
    taken = base[base["taken"]].copy()
    print(f"baseline rows {len(base)}, taken {len(taken)}")

    # ---------------- T1
    sims = {symbol: LimitSim(symbol) for symbol in SYMBOLS if (taken["symbol"] == symbol).any()}
    limit = pd.DataFrame([sims[row["symbol"]].run(row) for _, row in taken.iterrows()], index=taken.index)
    taken = taken.join(limit)
    taken["diff"] = taken["lim_r"] - taken["net_2r"]
    taken["cluster"] = day_cluster(taken)
    mean, t, n = clustered(taken["diff"], taken["cluster"])
    by_year = taken.groupby("group")["diff"].mean().reindex(GROUPS)
    by_symbol = taken.groupby("symbol")["diff"].mean()
    t1_pass = mean > 0 and t >= 2 and (by_year > 0).sum() >= 5 and (by_symbol > 0).sum() >= 6
    lines.append("## T1 limit at the plan entry vs market at the first report (taken signals, R per signal)\n")
    rows = []
    for group, part in taken.groupby("group", sort=False):
        m_mean, m_t, m_n = clustered(part["net_2r"], part["cluster"])
        l_mean, l_t, _ = clustered(part["lim_r"], part["cluster"])
        d_mean, d_t, _ = clustered(part["diff"], part["cluster"])
        filled = part[part["lim_filled"]]
        rows.append({"group": group, "n": m_n, "market": m_mean, "limit": l_mean, "limit - market": d_mean, "t diff": d_t,
                     "fill rate": float(part["lim_filled"].mean()), "R per fill": float(filled["lim_r"].mean()) if len(filled) else float("nan")})
    lines.append(table(rows))
    lines.append(f"\nPooled: limit - market {mean:+.3f} R per signal, clustered t {t:.2f}, n {n}; "
                 f"years > 0: {(by_year > 0).sum()} of {by_year.notna().sum()}; symbols > 0: {(by_symbol > 0).sum()} of {len(by_symbol)}.\n")
    l_mean, l_t, _ = clustered(taken["lim_r"], taken["cluster"])
    m_mean, m_t, _ = clustered(taken["net_2r"], taken["cluster"])
    lines.append(f"Limit itself {l_mean:+.3f} (t {l_t:.2f}); market {m_mean:+.3f} (t {m_t:.2f}). Cancel reasons: "
                 + ", ".join(f"{k} {v}" for k, v in taken.loc[~taken["lim_filled"], "lim_why"].value_counts().items()) + "\n")
    stacks = []
    for stack, part in taken.groupby("stack"):
        stacks.append({"stack": stack, "n": len(part), "market": float(part["net_2r"].mean()), "limit": float(part["lim_r"].mean()),
                       "fill rate": float(part["lim_filled"].mean())})
    lines.append("\nBy stack:\n\n" + table(stacks))
    symbols = [{"symbol": s, "n": int((taken["symbol"] == s).sum()), "limit - market": float(v)} for s, v in by_symbol.items()]
    lines.append("\nBy symbol:\n\n" + table(symbols))
    lines.append(f"\n**T1 {'PASS' if t1_pass else 'FAIL'}**\n")

    # ---------------- T2
    u21 = taken[(taken["group"] == "u21") & taken["stack"].isin(["1D / 1h / 5m", "1D / 4h / 15m"])].copy()
    lines.append("\n## T2 exits on U21 (taken, 1D-bias stacks, market entry)\n")
    t2 = {}
    for name, column in (("bias close", "r_bias_close"), ("3R", "net_3r")):
        part = u21[u21[column].notna()]
        diff = part[column] - part["net_2r"]
        d_mean, d_t, d_n = clustered(diff, part["cluster"])
        per_symbol = diff.groupby(part["symbol"]).mean()
        t2[name] = d_mean > 0 and (per_symbol > 0).sum() >= 5
        lines.append(f"- {name} - 2R: {d_mean:+.3f} R (t {d_t:.2f}, n {d_n}), symbols > 0: {(per_symbol > 0).sum()} of "
                     f"{len(per_symbol)}; 2R {part['net_2r'].mean():+.3f}, {name} {part[column].mean():+.3f}. "
                     f"**{'PASS' if t2[name] else 'FAIL'}**\n")

    # ---------------- T3
    lines.append("\n## T3 quality checks: replay with the checks off\n")
    t3_rows, t3_ok = [], []
    for label, groups, stack_set in (("U21", ["u21"], None), ("2022-2023", ["2022", "2023"], ["1D / 4h / 15m", "1W / 1D / 1h"])):
        on = pd.concat([load(g, "baseline") for g in groups], ignore_index=True)
        off = pd.concat([load(g, "quality_off") for g in groups], ignore_index=True)
        if stack_set is not None:
            on, off = on[on["stack"].isin(stack_set)], off[off["stack"].isin(stack_set)]
        on_taken = on[on["taken"]].set_index(KEY)
        off_taken = off[off["taken"]].set_index(KEY)
        kept = on_taken[on_taken.index.isin(off_taken.index)]
        removed = off_taken[~off_taken.index.isin(on_taken.index)]
        only_on = on_taken[~on_taken.index.isin(off_taken.index)]
        k_mean = float(kept["net_2r"].mean())
        r_mean = float(removed["net_2r"].mean())
        ok = k_mean - r_mean > 0 and r_mean < 0
        t3_ok.append(ok)
        t3_rows.append({"group": label, "kept n": len(kept), "kept": k_mean, "removed n": len(removed), "removed": r_mean,
                        "kept - removed": k_mean - r_mean, "taken only with checks on": len(only_on)})
    lines.append(table(t3_rows))
    t3_pass = all(t3_ok)
    lines.append(f"\n**T3 {'PASS (the checks help)' if t3_pass else 'FAIL'}**\n")

    # ---------------- T4
    h4 = taken[(taken["group"] == "u21") & taken["stack"].isin(["1D / 4h / 15m", "1W / 1D / 1h"])
               & (taken["trigger_kind"] == "cisd") & (taken["risk_adr"] >= 0.10)]
    per_symbol = h4.groupby("symbol")["net_2r"].mean()
    h4_mean, h4_t, h4_n = clustered(h4["net_2r"], h4["cluster"])
    t4_pass = h4_mean > 0 and (per_symbol > 0).sum() >= 5
    lines.append(f"\n## T4 best-measured setup on U21\n\n{h4_mean:+.3f} R (t {h4_t:.2f}, n {h4_n}), symbols > 0: "
                 f"{(per_symbol > 0).sum()} of {len(per_symbol)}. **T4 {'PASS' if t4_pass else 'FAIL'}**\n")

    report = "\n".join(lines)
    (RUNS / "report.md").write_text(report, encoding="utf-8")
    keep = ["group", "symbol", "stack", "check", "direction", "path", "trigger_kind", "risk_adr", "net_2r", "net_3r",
            "r_bias_close", "lim_filled", "lim_r", "lim_why", "session", "lag_min"]
    taken[keep].to_csv(RUNS / "signals.csv.gz", index=False, compression="gzip")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
