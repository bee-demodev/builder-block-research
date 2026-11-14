"""Fetch dated futures contracts from TradingView (CdpBridge private series, ~20k-bar cap per
series) and stitch them into one unadjusted, volume-rolled series, like the Databento set.

    .venv/Scripts/python scripts/external_data/tv_stitch.py --symbol NQ --res 5 --from-year 2021

Raw contracts: data/external/tradingview/contracts/<CODE>_<tf>.csv (cached; refetched with --refresh)
Stitched:      data/external/tradingview/<SYM>_<tf>.csv  (+ <SYM>_<tf>.stitch.json: rolls, coverage)

Roll rule: session date = trading day (18:00 NY opens the next date). The lead moves to the
next contract (by expiry) from the session AFTER the first session in which the next contract
traded more volume than the lead (causal). If the lead has no bars in a session and a later
contract does, the lead moves at once (expired / missing data).
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
from companion.tradingview.errors import TradingViewError  # noqa: E402
from companion.tradingview.symbols import FeedSettings  # noqa: E402

CODES = "FGHJKMNQUVXZ"
SPEC = {  # root ticker, active months
    "NQ": ("CME_MINI:NQ", "HMUZ"),
    "ES": ("CME_MINI:ES", "HMUZ"),
    "YM": ("CBOT_MINI:YM", "HMUZ"),
    "RTY": ("CME_MINI:RTY", "HMUZ"),
    "6E": ("CME:6E", "HMUZ"),
    "GC": ("COMEX:GC", "GJMQVZ"),
    "SI": ("COMEX:SI", "HKNUZ"),
    "CL": ("NYMEX:CL", CODES),
}
TF = {"1": "1m", "3": "3m", "5": "5m", "15": "15m", "60": "1h"}
OUT = ROOT / "data" / "external" / "tradingview"
NY = "America/New_York"


def contracts(symbol: str, from_year: int, to_year: int) -> list[tuple[str, int, int]]:
    root, months = SPEC[symbol]
    out = []
    for year in range(from_year, to_year + 1):
        for code in months:
            out.append((f"{root}{code}{year}", year, CODES.index(code) + 1))
    return out


def rows_to_frame(rows) -> pd.DataFrame:
    frame = pd.DataFrame(list(rows), columns=["t", "open", "high", "low", "close", "volume"])
    if len(frame) and frame["t"].max() > 1e11:
        frame["t"] = frame["t"] / 1000.0
    frame.index = pd.DatetimeIndex(pd.to_datetime(frame["t"], unit="s", utc=True).dt.tz_convert(NY), name="timestamp")
    frame = frame.drop(columns="t")
    return frame[~frame.index.duplicated(keep="last")].sort_index()


def fetch_contract(bridge: CdpBridge, ticker: str, res: str, path: Path, refresh: bool) -> pd.DataFrame | None:
    if path.exists() and not refresh:
        frame = pd.read_csv(path, index_col=0)
        frame.index = pd.DatetimeIndex(pd.to_datetime(frame.index, utc=True)).tz_convert(NY)
        return frame
    try:
        payload = bridge.fetch_bars(ticker, res, 400_000)
    except TradingViewError as error:
        print(f"  {ticker}: {error.kind} {getattr(error, 'technical', '')}", flush=True)
        return None
    finally:
        try:
            bridge.release(ticker, res)
        except Exception:  # noqa: BLE001
            pass
    frame = rows_to_frame(payload.rows)
    if payload.forming_until is not None and len(frame):
        frame = frame.iloc[:-1]  # forming bar of a live contract
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path)
    print(f"  {ticker}: {len(frame)} bars {frame.index[0]} -> {frame.index[-1]}", flush=True)
    time.sleep(0.5)
    return frame


def session_date(index: pd.DatetimeIndex) -> pd.Index:
    return (index.tz_localize(None) + pd.Timedelta(hours=6)).normalize()


def stitch(frames: list[tuple[str, pd.DataFrame]]) -> tuple[pd.DataFrame, list[dict]]:
    vols = {}
    for name, frame in frames:
        vols[name] = frame["volume"].groupby(session_date(frame.index)).sum()
    table = pd.DataFrame(vols).fillna(0.0)  # columns already in expiry order
    names = list(table.columns)
    # Start where the first contract of the list has bars: before that only far back months
    # (thin, gappy) trade in the fetched set.
    begin = frames[0][1].index[0]
    begin_date = session_date(pd.DatetimeIndex([begin]))[0]
    table = table[table.index >= begin_date]
    dates = table.index.sort_values()
    lead = int(table.loc[dates[0]].to_numpy().argmax())
    switch_to: int | None = None
    choice: dict[pd.Timestamp, str] = {}
    rolls: list[dict] = []
    for date in dates:
        if switch_to is not None:
            lead = switch_to
            rolls.append({"session": str(date.date()), "to": names[lead], "why": "volume"})
        switch_to = None
        row = table.loc[date].to_numpy()
        # lead missing today but a later contract trades: move at once to the busiest later one
        if row[lead] <= 0 and lead + 1 < len(names) and row[lead + 1:].sum() > 0:
            lead = lead + 1 + int(row[lead + 1:].argmax())
            rolls.append({"session": str(date.date()), "to": names[lead], "why": "lead had no bars"})
        choice[date] = names[lead]
        if lead + 1 < len(names):
            later = lead + 1 + int(row[lead + 1:].argmax())
            if row[later] > row[lead]:  # another contract out-traded the lead: it leads from the next session
                switch_to = later
    parts = []
    by_name = dict(frames)
    for name in names:
        days = [d for d, n in choice.items() if n == name]
        if not days:
            continue
        frame = by_name[name]
        part = frame[session_date(frame.index).isin(days)].copy()
        part["contract"] = name.split(":")[-1]
        parts.append(part)
    out = pd.concat(parts).sort_index()
    out = out[~out.index.duplicated(keep="first")]
    return out, rolls


def gaps(index: pd.DatetimeIndex, bar_minutes: int) -> list[dict]:
    """Holes inside the trading week longer than 2 h (weekend close Fri 17:00 -> Sun 18:00 excluded)."""
    found = []
    deltas = index[1:] - index[:-1]
    for i in (deltas > pd.Timedelta(hours=2)).nonzero()[0]:
        a, b = index[i], index[i + 1]
        a_close = a + pd.Timedelta(minutes=bar_minutes)
        weekend = a_close.dayofweek == 4 and b.dayofweek == 6 and (b - a_close) <= pd.Timedelta(hours=49, minutes=30)
        if weekend:
            continue
        found.append({"from": a_close.isoformat(), "to": b.isoformat(), "hours": round((b - a_close) / pd.Timedelta(hours=1), 1)})
    return found


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--res", default="5")
    ap.add_argument("--from-year", type=int, default=2021)
    ap.add_argument("--to-year", type=int, default=2027)
    ap.add_argument("--start", help="drop stitched bars before this date (contracts expiring early in from-year start in the year before)")
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()
    tf = TF[args.res]
    today = pd.Timestamp.now(tz=NY)
    bridge = CdpBridge(FeedSettings(max_series=2))
    bridge.DEEPEN_SECONDS = 300.0
    bridge.MORE_SECONDS = 30.0
    frames: list[tuple[str, pd.DataFrame]] = []
    failed: list[str] = []
    try:
        for ticker, year, month in contracts(args.symbol, args.from_year, args.to_year):
            # skip contracts too far out to trade yet (more than ~15 months away)
            if pd.Timestamp(year=year, month=month, day=1, tz=NY) > today + pd.Timedelta(days=200):
                continue
            path = OUT / "contracts" / f"{ticker.split(':')[-1]}_{tf}.csv"
            frame = fetch_contract(bridge, ticker, args.res, path, args.refresh)
            if frame is None or not len(frame):
                failed.append(ticker)
                continue
            frames.append((ticker, frame))
    finally:
        bridge.close()
    series, rolls = stitch(frames)
    if args.start:
        series = series[series.index >= pd.Timestamp(args.start, tz=NY)]
    body = series[["open", "high", "low", "close", "volume"]].copy()
    body.insert(0, "timestamp", [t.isoformat() for t in body.index])
    out = OUT / f"{args.symbol}_{tf}.csv"
    body.to_csv(out, index=False)
    holes = gaps(series.index, int(args.res))
    info = {
        "symbol": args.symbol, "tf": tf, "rows": len(series), "first": series.index[0].isoformat(), "last": series.index[-1].isoformat(),
        "contracts_used": series["contract"].unique().tolist(), "failed": failed, "rolls": rolls,
        "gaps_over_2h": len(holes), "largest_gaps": sorted(holes, key=lambda g: -g["hours"])[:10],
        "contract_spans": {n.split(":")[-1]: [f.index[0].isoformat(), f.index[-1].isoformat(), len(f)] for n, f in frames},
    }
    out.with_suffix(".stitch.json").write_text(json.dumps(info, indent=1))
    print(json.dumps({k: info[k] for k in ("symbol", "tf", "rows", "first", "last", "failed", "gaps_over_2h")}))
    print("largest gaps:", json.dumps(info["largest_gaps"][:5]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
