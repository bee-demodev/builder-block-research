"""Experimental: ask TradingView for a bar *range* (create_series 7th arg "r,from:to") through a
scratch copy of the companion's page feed, installed under its own global (``__extFeed``) in a
background chart tab. Lets 1m history older than the 20k-bar cap be read in windows.

Companion code is not modified: the JS is copied from companion.tradingview.pagefeed and patched
in memory. The feed is destroyed at the end.

    .venv/Scripts/python scripts/external_data/tv_range.py --ticker CME_MINI:NQM2026 --res 1 \
        --start 2026-03-09 --end 2026-03-14 --out x.csv
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from companion.tradingview import cdp, pagefeed  # noqa: E402

GLOBAL = "__extFeed"
CHART = re.compile(r"^https://[a-z.]*tradingview\.com/chart(/|$|\?)", re.I)


def patched_install() -> str:
    js = pagefeed.JS_INSTALL.replace("__companionFeed", GLOBAL)
    js = js.replace("F.open = function (key, symbol, resolution, count) {", "F.open = function (key, symbol, resolution, count, range) {")
    js = js.replace("resolution: resolution, count: count,", "resolution: resolution, count: count, range: range || null,")
    js = js.replace("S.resolution, S.count, null, S.handler)", "S.resolution, S.count, S.range, S.handler)")
    assert js.count("S.range") == 1 and "range || null" in js, "pagefeed changed; patch no longer applies"
    return js


def call(method: str, *args: object) -> str:
    return pagefeed.call(method, *args).replace("__companionFeed", GLOBAL)


class RangeFeed:
    def __init__(self, port: int = 9222, host_id: str | None = None) -> None:
        targets = [t for t in cdp.http_json(port, "/json/list") if t.get("type") == "page" and CHART.search(str(t.get("url", "")))]
        self.session = None
        for target in targets:
            if host_id and not str(target["id"]).startswith(host_id):
                continue
            session = cdp.CdpSession(str(target["webSocketDebuggerUrl"]))
            look = session.evaluate(pagefeed.JS_PEEK, timeout=5) or {}
            if look.get("connected") and not look.get("visible"):
                got = session.evaluate(patched_install(), timeout=10) or {}
                if got.get("ok"):
                    self.session, self.host = session, {"id": target["id"], **look}
                    break
            session.close()
        if self.session is None:
            raise RuntimeError("no background chart tab with a ready connection")
        self.n = 0

    def fetch(self, symbol_string: str, res: str, start: pd.Timestamp, end: pd.Timestamp, count: int = 20000,
              timeout: float = 60.0) -> tuple[list, dict]:
        self.n += 1
        key = f"r{self.n}"
        rng = {"type": "time-range", "from": int(start.timestamp()), "to": int(end.timestamp())}
        state = self.session.evaluate(call("open", key, symbol_string, res, count, rng), timeout=10)
        deadline = time.monotonic() + timeout
        while state.get("state") not in ("ready", "error") and time.monotonic() < deadline:
            time.sleep(0.1)
            state = self.session.evaluate(call("status", key), timeout=10)
        # let updates settle
        time.sleep(0.3)
        data = self.session.evaluate(call("read", key, 10_000_000), timeout=60) or {}
        self.session.evaluate(call("close", key), timeout=5)
        return data.get("rows") or [], {k: data.get(k) for k in ("state", "size", "mode", "error")}

    def close(self) -> None:
        try:
            self.session.evaluate(f"(function(){{var f=window.{GLOBAL}; if(f) f.destroy('closed'); try{{delete window.{GLOBAL}}}catch(e){{}} return true;}})()", timeout=5)
        finally:
            self.session.close()


def to_frame(rows: list) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    frame = pd.DataFrame(rows, columns=["t", "open", "high", "low", "close", "volume"])
    idx = pd.to_datetime(frame["t"], unit="s", utc=True).dt.tz_convert("America/New_York")
    frame.index = pd.DatetimeIndex(idx, name="timestamp")
    return frame.drop(columns="t")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", required=True)
    ap.add_argument("--res", default="1")
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--out")
    ap.add_argument("--count", type=int, default=20000)
    args = ap.parse_args()
    feed = RangeFeed()
    try:
        sym = pagefeed.symbol_string(args.ticker)
        rows, st = feed.fetch(sym, args.res, pd.Timestamp(args.start, tz="America/New_York"), pd.Timestamp(args.end, tz="America/New_York"), count=args.count)
    finally:
        feed.close()
    frame = to_frame(rows)
    print(json.dumps({**st, "rows": len(frame), "first": str(frame.index.min()), "last": str(frame.index.max()), "host": feed.host.get("id", "")[:8]}, default=str))
    if args.out and len(frame):
        frame.to_csv(args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
