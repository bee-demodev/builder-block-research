"""Wrapper around companion.tools.backtest for external bar files.

Same as ``python -m companion.tools.backtest run ... --bars-file X`` but with a working CSV reader:
companion.tools.backtest.read_bars_file (lines 347-348) builds the frame from RangeIndex Series with
``index=<DatetimeIndex>``, so pandas aligns by label and every open/high/low/close/volume is NaN.
This wrapper reads the file positionally (``.to_numpy()``) and then calls the harness's own
``scan`` and ``_write`` unchanged.

    .venv/Scripts/python scripts/external_data/run_backtest.py --symbol NQ --stack "1D/1h/5m" \
        --start 2026-03-05 --end 2026-11-14 --bars-file data/external/tradingview/NQ_5m.csv \
        --out results/backtest/external/tradingview/NQ_1D-1h-5m.jsonl.gz
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from companion.tools import backtest as bt  # noqa: E402
from companion.types import BARS_TIMEZONE  # noqa: E402


def read_bars(path: str | Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    text = frame["timestamp"].astype(str)
    if text.str.contains(r"[+-]\d\d:\d\d$|Z$").any():
        stamps = pd.to_datetime(text, utc=True)
    else:
        stamps = pd.to_datetime(text).dt.tz_localize(BARS_TIMEZONE)
    index = pd.DatetimeIndex(stamps).tz_convert(BARS_TIMEZONE)
    index.name = "timestamp"
    bars = pd.DataFrame({col: frame[col].astype(float).to_numpy() for col in ("open", "high", "low", "close")}, index=index)
    bars["volume"] = frame["volume"].astype(float).fillna(0.0).to_numpy() if "volume" in frame else 0.0
    bars = bars.dropna(subset=["open", "high", "low", "close"])
    return bars[~bars.index.duplicated()].sort_index()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--stack", required=True)
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--variant", default="baseline")
    ap.add_argument("--hours", nargs=2, type=int)
    ap.add_argument("--max-days", type=float, default=10.0)
    ap.add_argument("--bars-file", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    parts = [p.strip() for p in args.stack.split("/")]
    bars = read_bars(args.bars_file)
    started = time.time()
    trades, states = bt.scan(args.symbol, parts, args.start, args.end, args.variant,
                             tuple(args.hours) if args.hours else None, args.max_days, minute_bars=bars, progress=True)
    meta = {"symbol": args.symbol, "stack": parts, "start": args.start, "end": args.end, "variant": args.variant,
            "hours": args.hours, "bars_file": args.bars_file, "bars_first": bars.index[0].isoformat(),
            "bars_last": bars.index[-1].isoformat(), "checks": len(states), "trades": len(trades),
            "seconds": round(time.time() - started, 1), "reader": "scripts/external_data/run_backtest.py:read_bars"}
    bt._write(Path(args.out), trades, states, meta)
    errors = sum(1 for s in states if len(s) > 1 and s[1] == "error")
    taken = sum(1 for t in trades if t["taken"])
    print(json.dumps({"out": args.out, "checks": len(states), "errors": errors, "triggers": len(trades), "taken": taken,
                      "seconds": meta["seconds"]}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
