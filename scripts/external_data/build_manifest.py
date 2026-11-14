"""Write data/external/manifest.json describing every bar file under data/external/."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_backtest import read_bars  # noqa: E402
from tv_stitch import gaps  # noqa: E402

EXT = ROOT / "data" / "external"
MIN = {"1m": 1, "3m": 3, "5m": 5, "15m": 15, "1h": 60, "1d": 1440}
YAHOO = {"NQ": "NQ=F", "ES": "ES=F", "GC": "GC=F", "YM": "YM=F", "RTY": "RTY=F", "CL": "CL=F", "SI": "SI=F", "6E": "6E=F"}


def describe(path: Path) -> dict:
    source = path.parent.name
    stem = path.stem
    symbol, tf = stem.rsplit("_", 1)
    bars = read_bars(path)
    entry: dict = {"file": str(path.relative_to(ROOT)).replace("\\", "/"), "source": source, "symbol": symbol, "timeframe": tf,
                   "rows": len(bars), "first_bar": bars.index[0].isoformat(), "last_bar": bars.index[-1].isoformat(),
                   "timestamp": "bar open, America/New_York"}
    if tf == "1d":
        d = bars.index[1:] - bars.index[:-1]
        big = [(bars.index[i].isoformat(), round(d[i] / pd.Timedelta(days=1), 1)) for i in (d > pd.Timedelta(days=4)).nonzero()[0]]
        entry["gaps"] = {"over_4_days": len(big), "largest": sorted(big, key=lambda x: -x[1])[:5]}
    else:
        holes = gaps(bars.index, MIN[tf])
        holiday_like = [g for g in holes if g["hours"] <= 6 or 48 <= g["hours"] <= 80]  # early closes, long weekends, DST weekends
        other = [g for g in holes if g not in holiday_like]
        entry["gaps"] = {"over_2h_in_trading_week": len(holes), "holiday_or_early_close_like": len(holiday_like),
                         "other": len(other), "other_largest": sorted(other, key=lambda g: -g["hours"])[:8]}
    stitch = path.with_suffix(".stitch.json")
    fetch = path.with_suffix(".fetch.json")
    if source == "tradingview" and stitch.exists():
        info = json.loads(stitch.read_text())
        entry.update({
            "ticker": f"dated contracts {info['contracts_used'][0]} .. {info['contracts_used'][-1]} ({len(info['contracts_used'])} used)",
            "series": "continuous, UNADJUSTED (no back-adjustment), stitched from dated contracts; roll = next session after "
                      "another contract out-trades the lead on session volume (same idea as the Databento lead-volume roll)",
            "rolls": [f"{r['session']} -> {r['to'].split(':')[-1]}" for r in info["rolls"] if r["session"] >= entry["first_bar"][:10]],
            "per_contract_files": "data/external/tradingview/contracts/<CODE>_5m.csv (each capped at ~20k bars by TradingView)",
        })
    elif source == "tradingview" and fetch.exists():
        info = json.loads(fetch.read_text())
        dated = not info["ticker"].endswith("1!")
        entry.update({
            "ticker": info["ticker"],
            "series": ("single dated contract (the current lead), unadjusted" if dated else
                       "TradingView continuous 1! (switches at TradingView's roll), unadjusted"),
            "depth_limit": "TradingView serves ~20k bars per series at any intraday resolution; this is all of it",
        })
    elif source == "yahoo":
        entry.update({
            "ticker": YAHOO.get(symbol, symbol),
            "series": "Yahoo continuous front month (=F), unadjusted; jumps at Yahoo's roll",
            "depth_limit": {"1m": "last ~30 days (8 days per request)", "5m": "60 days", "15m": "60 days", "1h": "730 days",
                            "1d": "full history"}[tf],
        })
        if tf == "1d":
            entry["note"] = ("daily close is the settlement (~16:00 ET for equity index), not the 17:00 last trade; "
                             "restamped from Yahoo's 00:00 UTC date to 18:00 NY the evening before")
        if tf == "1h":
            entry["note"] = "hour bars on the clock hour; matches the companion grid (18:00 session open)"
    return entry


def main() -> int:
    files = sorted(p for p in EXT.glob("*/*.csv") if p.parent.name in ("tradingview", "yahoo"))
    entries = [describe(p) for p in files]
    for e in entries:
        print(e["file"], e["rows"], e["first_bar"], e["last_bar"], e["gaps"])
    manifest = {
        "built": pd.Timestamp.now(tz="America/New_York").isoformat(),
        "columns": "timestamp,open,high,low,close,volume (timestamp = bar open, ISO 8601 with New York offset)",
        "overlap_check": "data/external/overlap_check_NQ.json",
        "contracts_dir": "data/external/tradingview/contracts/ (raw per-contract 5m bars used for stitching)",
        "files": entries,
    }
    (EXT / "manifest.json").write_text(json.dumps(manifest, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
