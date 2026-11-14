"""Engine runs for the Phase B pre-registered tests (results/phase_b/PREREGISTERED_PHASE_B.md).

    .venv/Scripts/python -m scripts.phase_b_runs --workers 22

U21: 2021-08-01 to 2022-01-01, 8 symbols, 1D/1h/5m, 1D/4h/15m, 1W/1D/1h, variants baseline and quality_off.
2022 and 2023: baseline and quality_off on 1D/4h/15m and 1W/1D/1h.
2024 to 2026-11-14: baseline on 1D/1h/5m, 1D/4h/15m, 1W/4h/15m, 1W/1D/1h.
All on the current engine (the older results/backtest_tv* runs predate Phase A).

``quality_off`` makes every quality check advisory (backtest only, by patching the checklist in the
worker process), so every entry-ready trigger is taken: the replay of what the checks hold back.
"""

from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SYMBOLS = ("NQ", "ES", "GC", "YM", "RTY", "CL", "SI", "6E")
U21_STACKS = (("1D", "1h", "5m"), ("1D", "4h", "15m"), ("1W", "1D", "1h"))
HOLDOUT_STACKS = (("1D", "4h", "15m"), ("1W", "1D", "1h"))
RECENT_STACKS = (("1D", "1h", "5m"), ("1D", "4h", "15m"), ("1W", "4h", "15m"), ("1W", "1D", "1h"))


def quality_off() -> None:
    """Every quality check advisory, in this process only."""
    from companion.styles.ttrades import checklist

    original = checklist.Checklist.role

    def role(self: checklist.Checklist, key: str) -> str:
        found = original(self, key)
        return checklist.ADVISORY if found == checklist.QUALITY else found

    checklist.Checklist.role = role  # type: ignore[method-assign]


def run(job: dict[str, Any]) -> dict[str, Any]:
    from companion.tools import backtest

    out = Path(job["out"])
    if out.exists():
        return {**job, "status": "exists"}
    started = time.time()
    from companion.styles.ttrades import checklist

    if job["variant"] == "quality_off":
        quality_off()
    elif checklist.Checklist.role.__name__ != "role" or checklist.Checklist.role.__qualname__ != "Checklist.role":
        return {**job, "status": "error: quality_off patch present in a baseline job"}
        backtest.VARIANTS["quality_off"] = {"objective_at_trigger_role": "advisory"}
    try:
        bars = backtest.read_bars_file(job["bars_file"])
        trades, states = backtest.scan(job["symbol"], job["stack"], job["start"], job["end"], job["variant"], minute_bars=bars)
    except Exception as error:  # noqa: BLE001
        return {**job, "status": f"error: {type(error).__name__}: {error}"}
    meta = {**job, "checks": len(states), "trades": len(trades), "seconds": round(time.time() - started, 1)}
    backtest._write(out, trades, states, meta)
    return {**job, "status": "ok", "trades": len(trades), "seconds": meta["seconds"]}


def jobs() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []

    def add(symbol: str, stack: tuple[str, str, str], start: str, end: str, variant: str, folder: str) -> None:
        slug = "-".join(stack)
        out.append({
            "symbol": symbol, "stack": list(stack), "start": start, "end": end, "variant": variant,
            "bars_file": str(ROOT / f"data/external/tradingview/{symbol}_5m.csv"),
            "out": str(ROOT / f"results/phase_b/{folder}/{variant}/{symbol}_{slug}.jsonl.gz"),
        })

    for variant in ("baseline", "quality_off"):
        for stack in U21_STACKS:
            for symbol in SYMBOLS:
                add(symbol, stack, "2021-08-01", "2022-01-01", variant, "u21")
    for year in (2022, 2023):
        for variant in ("baseline", "quality_off"):
            for stack in HOLDOUT_STACKS:
                for symbol in SYMBOLS:
                    add(symbol, stack, f"{year}-01-01", f"{year + 1}-01-01", variant, str(year))
    for year in (2024, 2025, 2026):
        end = "2026-11-14" if year == 2026 else f"{year + 1}-01-01"
        for stack in RECENT_STACKS:
            for symbol in SYMBOLS:
                add(symbol, stack, f"{year}-01-01", end, "baseline", str(year))
    out.sort(key=lambda job: {"5m": 0, "15m": 1}.get(job["stack"][2], 2))  # longest first
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=20)
    args = parser.parse_args()
    todo = jobs()
    print(f"{len(todo)} jobs on {args.workers} workers", flush=True)
    # one job per process: the quality_off patch must never outlive its job (it leaked into
    # later baseline jobs of the same worker on the first run; those outputs were moved aside)
    with ProcessPoolExecutor(max_workers=args.workers, max_tasks_per_child=1) as pool:
        for future in as_completed([pool.submit(run, job) for job in todo]):
            result = future.result()
            print(json.dumps({k: result.get(k) for k in ("symbol", "stack", "variant", "start", "status", "trades", "seconds")}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
