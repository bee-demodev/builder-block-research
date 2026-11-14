"""Run backtest jobs (scripts/external_data/run_backtest.py) from a JSON list, N at a time.

    .venv/Scripts/python scripts/external_data/run_jobs.py jobs.json --workers 3

Each job: {"symbol", "stack", "start", "end", "bars_file", "out", "hours"?}. Jobs whose output exists are skipped.
Per-job stdout/stderr: scripts/external_data/logs/<out stem>.log
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PY = str(ROOT / ".venv" / "Scripts" / "python.exe")
LOGS = ROOT / "scripts" / "external_data" / "logs"


def run(job: dict) -> dict:
    out = ROOT / job["out"]
    if out.exists():
        return {**job, "status": "exists"}
    cmd = [PY, str(ROOT / "scripts" / "external_data" / "run_backtest.py"), "--symbol", job["symbol"], "--stack", job["stack"],
           "--start", job["start"], "--end", job["end"], "--bars-file", job["bars_file"], "--out", job["out"]]
    if job.get("hours"):
        cmd += ["--hours", *map(str, job["hours"])]
    LOGS.mkdir(parents=True, exist_ok=True)
    log = LOGS / (Path(job["out"]).name.replace(".jsonl.gz", "") + f"__{Path(job['out']).parent.name}.log")
    started = time.time()
    with open(log, "w", encoding="utf-8") as handle:
        code = subprocess.call(cmd, cwd=ROOT, stdout=handle, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
    return {**job, "status": "ok" if code == 0 else f"exit {code}", "seconds": round(time.time() - started)}


def main() -> int:
    jobs = json.loads(Path(sys.argv[1]).read_text())
    workers = int(sys.argv[sys.argv.index("--workers") + 1]) if "--workers" in sys.argv else 3
    print(f"{len(jobs)} jobs, {workers} workers", flush=True)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(run, job) for job in jobs]
        for future in as_completed(futures):
            r = future.result()
            print(json.dumps({k: r.get(k) for k in ("symbol", "stack", "out", "status", "seconds")}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
