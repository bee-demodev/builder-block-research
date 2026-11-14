"""Aggregate companion backtest trade files into edge tables.

    .venv/Scripts/python scripts/analyze_backtest.py --root results/backtest --out results/backtest/report

Reads every ``*.jsonl.gz`` written by ``companion.tools.backtest`` under ``--root`` and
writes ``trades.csv.gz`` (one row per trigger), ``summary.md`` and a CSV per table.

Metric conventions (all in R, net of costs, one contract, no compounding):
- ``exp_2r``: mean of ``net_2r`` (fixed 2R target vs the structural stop; open trades marked
  to market at the horizon). ``exp_1r`` likewise. ``exp_body``: mean ``r_bias_close``.
- ``win_2r``: share of resolved trades that hit 2R before the stop.
- ``pf_2r``: gross won / gross lost on ``net_2r``. ``maxdd_2r``: worst peak-to-trough of the
  cumulative ``net_2r`` in time order.
- A row with fewer than ``--min-n`` trades is dropped from the tables.
"""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd

KEEP = (
    "symbol stack variant check decision taken direction bias path stage blocking trigger_kind lag_min session hour "
    "weekday adr14 risk risk_adr cost_r mfe_r mae_r minutes_to_stop first_1r first_2r first_3r net_1r net_1.5r net_2r "
    "net_3r r_bias_close minutes_2r skipped plan_state"
).split()


def load(root: Path) -> pd.DataFrame:
    rows = []
    for path in sorted(root.rglob("*.jsonl.gz")):
        rel = path.relative_to(root).parts
        dataset = "databento" if rel[0].isdigit() else rel[0] if rel[0] != "external" else f"external/{rel[1]}"
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            meta = json.loads(handle.readline()).get("meta", {})
            for line in handle:
                trade = json.loads(line)
                row = {key: trade.get(key) for key in KEEP}
                row["dataset"] = dataset
                row["year"] = int(str(trade["check"])[:4])
                for key, value in (trade.get("criteria") or {}).items():
                    row[f"c:{key}"] = value
                rows.append(row)
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame["check"] = pd.to_datetime(frame["check"], utc=True).dt.tz_convert("America/New_York")
    frame = frame[frame["skipped"].isna() & frame["risk"].notna()].copy()
    # A stop closer than two ticks cannot be traded (and its R outcomes explode): drop it.
    ticks = frame["symbol"].map({"NQ": 0.25, "ES": 0.25, "YM": 1.0, "RTY": 0.1, "GC": 0.1, "SI": 0.005, "CL": 0.01,
                                 "6E": 0.00005}).fillna(0.0)
    frame["tiny_stop"] = frame["risk"] < 2 * ticks
    frame = frame[~frame["tiny_stop"]].copy()
    frame["fresh"] = frame["lag_min"] <= 0
    frame["blocking"] = frame["blocking"].apply(lambda value: tuple(value) if isinstance(value, list) else ())
    return frame


def max_drawdown(values: pd.Series) -> float:
    curve = values.cumsum()
    return float((curve - curve.cummax()).min()) if len(curve) else 0.0


def stats(group: pd.DataFrame) -> pd.Series:
    resolved = group[group["first_2r"] != "open"]
    won = group.loc[group["net_2r"] > 0, "net_2r"].sum()
    lost = -group.loc[group["net_2r"] < 0, "net_2r"].sum()
    ordered = group.sort_values("check")
    return pd.Series({
        "n": len(group),
        "win_1r": (group["first_1r"] == "win").sum() / max(1, (group["first_1r"] != "open").sum()),
        "win_2r": (resolved["first_2r"] == "win").mean() if len(resolved) else np.nan,
        "exp_1r": group["net_1r"].mean(),
        "exp_2r": group["net_2r"].mean(),
        "exp_3r": group["net_3r"].mean(),
        "exp_body": group["r_bias_close"].mean(),
        "pf_2r": won / lost if lost > 0 else np.inf,
        "sum_2r": group["net_2r"].sum(),
        "maxdd_2r": max_drawdown(ordered["net_2r"]),
        "med_mfe": group["mfe_r"].median(),
        "med_risk_adr": group["risk_adr"].median(),
    })


def table(frame: pd.DataFrame, by: list[str], min_n: int) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    out = frame.groupby(by, dropna=False).apply(stats, include_groups=False)
    out = out[out["n"] >= min_n]
    return out.round(3)


def blocking_effect(frame: pd.DataFrame, min_n: int) -> pd.DataFrame:
    """For each quality check: the trades it held back when it was the ONLY failing check,
    against the trades that passed everything. A good filter holds back trades worse than the
    taken ones."""
    rows = []
    taken = frame[frame["taken"]]
    for key in sorted({k for keys in frame["blocking"] for k in keys}):
        alone = frame[frame["blocking"].apply(lambda keys, k=key: keys == (k,))]
        anywhere = frame[frame["blocking"].apply(lambda keys, k=key: k in keys)]
        for label, part in (("only", alone), ("any", anywhere)):
            if len(part) >= min_n:
                rows.append({"check": key, "scope": label, **stats(part).to_dict()})
    rows.append({"check": "(taken: all checks pass)", "scope": "", **stats(taken).to_dict()})
    return pd.DataFrame(rows).round(3)


def markdown(data: pd.DataFrame) -> str:
    flat = data.reset_index() if not isinstance(data.index, pd.RangeIndex) else data
    cells = [[str(c) for c in flat.columns]] + [[f"{v:.3f}" if isinstance(v, float) else str(v) for v in row]
                                               for row in flat.itertuples(index=False)]
    lines = ["| " + " | ".join(cells[0]) + " |", "|" + "---|" * len(cells[0])]
    lines += ["| " + " | ".join(row) + " |" for row in cells[1:]]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="results/backtest")
    parser.add_argument("--out", default="results/backtest/report")
    parser.add_argument("--min-n", type=int, default=20)
    args = parser.parse_args()
    root, out = Path(args.root), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    frame = load(root)
    frame.drop(columns=[c for c in frame.columns if c.startswith("c:")]).to_csv(out / "trades.csv.gz", index=False)
    frame.to_pickle(out / "trades_full.pkl")
    base = frame[(frame["variant"] == "baseline") & (frame["dataset"] == "databento")]
    sections: list[tuple[str, pd.DataFrame]] = [
        ("Taken trades by stack, symbol and year", table(base[base["taken"]], ["stack", "symbol", "year"], args.min_n)),
        ("Taken vs shadow by stack (both years, all symbols)", table(base, ["stack", "taken"], args.min_n)),
        ("Taken trades by stack and path", table(base[base["taken"]], ["stack", "path"], args.min_n)),
        ("All triggers by path, trigger kind and taken", table(base, ["path", "trigger_kind", "taken"], args.min_n)),
        ("All triggers by session", table(base, ["session"], args.min_n)),
        ("Intraday stacks: all triggers by session and path", table(base[base["stack"].isin(
            ["1D / 1h / 5m", "4h / 15m / 1m", "1h / 5m / 1m", "1D / 30m / 3m", "1h / 15m / 1m", "1D / 4h / 15m", "1W / 4h / 15m"])],
            ["session", "path"], args.min_n)),
        ("All triggers by hour (New York)", table(base, ["hour"], args.min_n)),
        ("All triggers by weekday (0=Mon)", table(base, ["weekday"], args.min_n)),
        ("Fresh (reported on the trigger bar) vs late", table(base, ["fresh", "taken"], args.min_n)),
        ("Variants (2025)", table(frame[(frame["year"] == 2025) & (frame["dataset"] == "databento")], ["variant", "taken"], args.min_n)),
        ("Variants by stack (2025, taken)", table(frame[(frame["year"] == 2025) & frame["taken"] & (frame["dataset"] == "databento")],
                                                   ["stack", "variant"], args.min_n)),
        ("External data (TradingView / Yahoo)", table(frame[frame["dataset"] != "databento"], ["dataset", "symbol", "stack", "taken"], 10)),
    ]
    base = base.assign(risk_bucket=pd.qcut(base["risk_adr"], 5, duplicates="drop"))
    sections.append(("All triggers by stop size (risk / 14-day ADR quintile)", table(base, ["risk_bucket"], args.min_n)))
    sections.append(("Quality checks: what they hold back vs what is taken", blocking_effect(base, args.min_n)))
    lines = ["# Companion backtest summary", "", f"{len(frame)} triggers loaded; baseline Databento: {len(base)} "
             f"({int(base['taken'].sum())} taken, {int((~base['taken']).sum())} shadow).", "",
             "R net of costs; exp_2r = mean R with a fixed 2R target; exp_body = mean R held to the bias candle close.", ""]
    for index, (title, data) in enumerate(sections):
        if data is None or data.empty:
            continue
        data.to_csv(out / f"t{index:02d}.csv")
        lines += [f"## {title}", "", markdown(data), ""]
    (out / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out / 'summary.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
