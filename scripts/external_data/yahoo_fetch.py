"""Yahoo Finance futures bars via yfinance -> data/external/yahoo/<SYM>_<tf>.csv

    .venv/Scripts/python scripts/external_data/yahoo_fetch.py

Intervals and the windows Yahoo serves: 1m (last ~30 days, 8 days per request), 5m / 15m (60 days),
1h (730 days), 1d (full). Yahoo's =F tickers are the front contract, unadjusted (the series jumps at
Yahoo's roll). Timestamps are bar opens; converted to New York.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "external" / "yahoo"
NY = "America/New_York"
ONLY = sys.argv[1:]
TICKERS = {"NQ": "NQ=F", "ES": "ES=F", "GC": "GC=F", "YM": "YM=F", "RTY": "RTY=F", "CL": "CL=F", "SI": "SI=F", "6E": "6E=F"}


def clean(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = frame.columns.get_level_values(0)
    frame = frame.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]].dropna(subset=["open", "high", "low", "close"])
    index = pd.DatetimeIndex(frame.index)
    index = index.tz_localize("UTC") if index.tz is None else index
    frame.index = index.tz_convert(NY)
    return frame[~frame.index.duplicated(keep="last")].sort_index()


def download(ticker: str, interval: str, **kw) -> pd.DataFrame:
    for attempt in range(3):
        try:
            data = yf.download(ticker, interval=interval, auto_adjust=False, progress=False, prepost=True, threads=False, **kw)
            return clean(data)
        except Exception as error:  # noqa: BLE001
            print(f"  {ticker} {interval} attempt {attempt + 1}: {error}", flush=True)
            time.sleep(3)
    return pd.DataFrame()


def fetch(ticker: str, interval: str) -> pd.DataFrame:
    now = pd.Timestamp.now(tz="UTC")
    if interval == "1m":
        parts = []
        for k in range(4):  # 4 x 7 days, newest first, inside the 30-day window
            end = now - pd.Timedelta(days=7 * k)
            start = end - pd.Timedelta(days=7)
            parts.append(download(ticker, "1m", start=start.to_pydatetime(), end=end.to_pydatetime()))
        parts = [p for p in parts if not p.empty]
        return pd.concat(parts).sort_index().pipe(lambda f: f[~f.index.duplicated(keep="last")]) if parts else pd.DataFrame()
    period = {"5m": "60d", "15m": "60d", "1h": "730d", "1d": "max"}[interval]
    frame = download(ticker, interval, period=period)
    if interval == "1d" and len(frame):
        # Yahoo stamps a daily bar at 00:00 UTC of its trading date; restamp to the session open, 18:00 NY the day before
        dates = frame.index.tz_convert("UTC").tz_localize(None).normalize()
        frame.index = pd.DatetimeIndex(dates - pd.Timedelta(hours=6)).tz_localize(NY, ambiguous="NaT", nonexistent="shift_forward")
    return frame


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    summary = {}
    for sym, ticker in TICKERS.items():
        for interval in ("1m", "5m", "15m", "1h", "1d"):
            if ONLY and interval not in ONLY:
                continue
            frame = fetch(ticker, interval)
            if not frame.empty:  # drop the bar still forming
                minutes = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "1d": 1440}[interval]
                frame = frame[frame.index + pd.Timedelta(minutes=minutes) <= pd.Timestamp.now(tz=NY)]
            if frame.empty:
                print(f"{sym} {interval}: EMPTY", flush=True)
                continue
            body = frame.copy()
            body.insert(0, "timestamp", [t.isoformat() for t in body.index])
            body.to_csv(OUT / f"{sym}_{interval}.csv", index=False)
            summary[f"{sym}_{interval}"] = {"ticker": ticker, "rows": len(frame), "first": frame.index[0].isoformat(), "last": frame.index[-1].isoformat()}
            print(sym, interval, summary[f"{sym}_{interval}"], flush=True)
            time.sleep(1)
    path = OUT / "_fetch_summary.json"
    old = json.loads(path.read_text()) if path.exists() else {}
    path.write_text(json.dumps({**old, **summary}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
