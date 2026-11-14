"""Build job lists for run_jobs.py. Phase 1: OOS NQ/ES/GC on TV 5m, 1m stacks on TV/Yahoo 1m, Yahoo 1h."""
import json, sys
from pathlib import Path
END = "2026-11-14"
def slug(stack): return stack.replace("/", "-")
def job(src, sym, stack, start, tf, hours=None):
    j = {"symbol": sym, "stack": stack, "start": start, "end": END, "bars_file": f"data/external/{src}/{sym}_{tf}.csv",
         "out": f"results/backtest/external/{src}/{sym}_{slug(stack)}.jsonl.gz"}
    if hours: j["hours"] = hours
    return j
phase = sys.argv[1]
jobs = []
if phase == "1":
    # cheap first: 1h entries, 15m, 1m short windows; 5m-entry OOS last (NQ 1D/1h/5m already running)
    for s in ["NQ","ES","GC","YM","RTY","CL","SI","6E"]:
        jobs.append(job("yahoo", s, "1W/1D/1h", "2024-12-15", "1h"))
        jobs.append(job("yahoo", s, "1M/1D/1h", "2026-06-01", "1h"))
    for s in ["NQ","ES","GC"]:
        for st in ["1W/1D/1h", "1M/1D/1h", "1W/4h/15m", "1D/4h/15m"]:
            jobs.append(job("tradingview", s, st, "2026-03-05", "5m"))
    for s in ["NQ","ES","GC"]:
        for st in ["1h/5m/1m", "1h/15m/1m"]:
            jobs.append(job("tradingview", s, st, "2026-11-01", "1m", [1, 16]))
    for s in ["NQ","ES","GC","YM","RTY","CL","SI","6E"]:
        for st in ["1h/5m/1m", "1h/15m/1m"]:
            jobs.append(job("yahoo", s, st, "2026-10-25", "1m", [1, 16]))
    for s in ["ES","GC"]:
        jobs.append(job("tradingview", s, "1D/1h/5m", "2026-03-05", "5m"))
if phase == "2":
    # deep runs on the 5 extra symbols, TV 5m stitched (file from 2021-01-03); starts leave the bias warm-up
    for s in ["YM", "RTY", "CL", "SI", "6E"]:
        jobs.append(job("tradingview", s, "1W/1D/1h", "2021-06-21", "5m"))
        jobs.append(job("tradingview", s, "1M/1D/1h", "2023-01-01", "5m"))
    for s in ["YM", "RTY", "CL", "SI", "6E"]:
        jobs.append(job("tradingview", s, "1W/4h/15m", "2021-06-21", "5m"))
        jobs.append(job("tradingview", s, "1D/4h/15m", "2021-04-19", "5m"))
    for s in ["YM", "RTY", "CL", "SI", "6E"]:
        jobs.append(job("tradingview", s, "1D/1h/5m", "2024-01-01", "5m"))
Path(f"scripts/external_data/jobs_phase{phase}.json").write_text(json.dumps(jobs, indent=1))
print(len(jobs))
