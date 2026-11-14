"""Pull deep history from TradingView Desktop through the companion's CdpBridge (private series,
no chart is switched) and write data/external/tradingview/<SYM>_<tf>.csv.

    .venv/Scripts/python scripts/external_data/tv_fetch.py --ticker CME_MINI:NQ1! --symbol NQ --res 1 --count 300000

Uses CdpBridge as-is; only instance attributes (deepen time budget) are raised. The feed object
is removed from the host page at the end (bridge.close()).
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

from companion.tradingview.bridge import CdpBridge  # noqa: E402
from companion.tradingview.symbols import FeedSettings  # noqa: E402

TF_LABEL = {"1": "1m", "3": "3m", "5": "5m", "15": "15m", "60": "1h", "1D": "1D"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", required=True)
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--res", required=True)
    ap.add_argument("--count", type=int, default=300000)
    ap.add_argument("--deepen-seconds", type=float, default=900)
    ap.add_argument("--out-dir", default=str(ROOT / "data" / "external" / "tradingview"))
    ap.add_argument("--probe", action="store_true", help="print span only, write nothing")
    args = ap.parse_args()

    bridge = CdpBridge(FeedSettings(max_series=2))
    bridge.DEEPEN_SECONDS = args.deepen_seconds
    bridge.MORE_SECONDS = 30.0
    started = time.time()
    try:
        payload = bridge.fetch_bars(args.ticker, args.res, args.count)
    finally:
        report = dict(bridge.report)
        try:
            bridge.release(args.ticker, args.res)
        finally:
            bridge.close()
    rows = payload.rows
    frame = pd.DataFrame(list(rows), columns=["t", "open", "high", "low", "close", "volume"][: len(rows[0])])
    if frame["t"].max() > 1e11:
        frame["t"] = frame["t"] / 1000.0
    idx = pd.to_datetime(frame["t"], unit="s", utc=True).dt.tz_convert("America/New_York")
    frame.index = pd.DatetimeIndex(idx)
    frame = frame[~frame.index.duplicated(keep="last")].sort_index()
    # drop the forming bar
    if payload.forming_until is not None and len(frame):
        frame = frame.iloc[:-1]
    info = {
        "ticker": payload.ticker, "requested": args.ticker, "res": args.res, "rows": len(frame),
        "first": frame.index[0].isoformat() if len(frame) else None,
        "last": frame.index[-1].isoformat() if len(frame) else None,
        "exhausted": payload.exhausted, "notes": list(payload.notes), "seconds": round(time.time() - started, 1),
        "deepen": (report.get("series") or {}).get("deepen"), "host": report.get("host"),
    }
    print(json.dumps(info, default=str))
    if args.probe:
        return 0
    out = Path(args.out_dir) / f"{args.symbol}_{TF_LABEL.get(args.res, args.res)}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    body = frame[["open", "high", "low", "close", "volume"]].copy()
    body.insert(0, "timestamp", [t.isoformat() for t in body.index])
    body.to_csv(out, index=False)
    (out.with_suffix(".fetch.json")).write_text(json.dumps(info, default=str, indent=1))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
