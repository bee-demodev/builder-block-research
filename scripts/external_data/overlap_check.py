"""Cross-check external NQ bars against the Databento minute set (cleaned by companion.bars).

    .venv/Scripts/python scripts/external_data/overlap_check.py --start 2026-01-05 --end 2026-02-14

For each external file: resample Databento to the file's bar size on the companion's grid, then
- timezone/alignment: the bar shift (-3..+3 bars) that minimises mean |close diff|
- price level: median close ratio and difference (continuous vs back-adjusted shows as an offset)
- close diffs at the best shift: mean / median / p95 / max |diff| in points and ticks, share exact
- bar coverage: bars only in one source
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from companion.bars import load_minute_bars, resample  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_backtest import read_bars as read_bars_file  # noqa: E402

TICK = 0.25


def compare(name: str, ext: pd.DataFrame, ref_minutes: pd.DataFrame, tf: str, start, end) -> dict:
    ext = ext[(ext.index >= start) & (ext.index < end)]
    ref = resample(ref_minutes, tf) if tf != "1m" else ref_minutes
    ref = ref[(ref.index >= start) & (ref.index < end)]
    ext, ref = ext.copy(), ref.copy()
    ext.index = pd.DatetimeIndex(ext.index).tz_convert("UTC").as_unit("ns")
    ref.index = pd.DatetimeIndex(ref.index).tz_convert("UTC").as_unit("ns")
    out: dict = {"file": name, "tf": tf, "ext_bars": len(ext), "ref_bars": len(ref)}
    best = None
    for shift in range(-3, 4):
        shifted = ext["close"].shift(shift)  # positional: ext bar i compared with ref bar at index of i-shift
        joined = pd.concat([ref["close"].rename("ref"), shifted.rename("ext")], axis=1, join="inner").dropna()
        if not len(joined):
            continue
        mad = float((joined["ext"] - joined["ref"]).abs().mean())
        if best is None or mad < best[1]:
            best = (shift, mad)
    out["best_shift_bars"] = best[0] if best else None
    joined = pd.concat([ref.add_prefix("ref_"), ext.add_prefix("ext_")], axis=1, join="inner").dropna()
    out["common_bars"] = len(joined)
    out["only_in_ext"] = int(len(ext.index.difference(ref.index)))
    out["only_in_ref"] = int(len(ref.index.difference(ext.index)))
    if len(joined):
        diff = joined["ext_close"] - joined["ref_close"]
        ratio = joined["ext_close"] / joined["ref_close"]
        out.update({
            "median_close_diff": round(float(diff.median()), 3),
            "mean_abs_close_diff": round(float(diff.abs().mean()), 3),
            "p95_abs_close_diff": round(float(diff.abs().quantile(0.95)), 3),
            "max_abs_close_diff": round(float(diff.abs().max()), 3),
            "share_close_exact": round(float((diff.abs() < 1e-9).mean()), 4),
            "share_close_within_1tick": round(float((diff.abs() <= TICK + 1e-9).mean()), 4),
            "median_ratio": round(float(ratio.median()), 6),
            "ratio_iqr": round(float(ratio.quantile(0.75) - ratio.quantile(0.25)), 6),
            "share_high_exact": round(float(((joined["ext_high"] - joined["ref_high"]).abs() < 1e-9).mean()), 4),
            "share_low_exact": round(float(((joined["ext_low"] - joined["ref_low"]).abs() < 1e-9).mean()), 4),
            "volume_ratio_median": round(float((joined["ext_volume"] / joined["ref_volume"].replace(0, np.nan)).median()), 3),
        })
        worst = diff.abs().sort_values(ascending=False).head(3)
        out["worst"] = [{"t": t.isoformat(), "ext": float(joined.loc[t, "ext_close"]), "ref": float(joined.loc[t, "ref_close"])} for t in worst.index]
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2026-01-05")
    ap.add_argument("--end", default="2026-02-14")
    ap.add_argument("--files", nargs="*", default=[
        "data/external/tradingview/NQ_5m.csv:5m",
        "data/external/tradingview/NQ1_15m.csv:15m",
        "data/external/yahoo/NQ_1h.csv:1h",
        "data/external/yahoo/NQ_1d.csv:1D",
    ])
    ap.add_argument("--out", default="data/external/overlap_check_NQ.json")
    args = ap.parse_args()
    start = pd.Timestamp(args.start, tz="America/New_York")
    end = pd.Timestamp(args.end, tz="America/New_York")
    ref = load_minute_bars("NQ", start - pd.Timedelta(days=10), end + pd.Timedelta(days=3))
    results = []
    for item in args.files:
        path, tf = item.rsplit(":", 1)
        if not (ROOT / path).exists():
            print(f"missing {path}")
            continue
        ext = read_bars_file(ROOT / path)
        if tf == "1D":
            # compare daily closes per trading date (Databento daily from minutes, last-trade close)
            res = compare(path, ext, ref, "1D", start, end)
        else:
            res = compare(path, ext, ref, tf, start, end)
        results.append(res)
        print(json.dumps(res))
    Path(ROOT / args.out).write_text(json.dumps({"window": [args.start, args.end], "results": results}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
