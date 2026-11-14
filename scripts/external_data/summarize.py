"""Summarise results/backtest/external/**.jsonl.gz: per source x symbol x stack, taken vs shadow.

win% = wins / (wins + losses) for "first to m R vs stop" (open trades excluded from the ratio, counted separately).
Rows with "skipped" (fill beyond stop) are excluded. Groups with < --min trades are dropped from the table.
"""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load(path: Path) -> tuple[dict, list[dict]]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        meta = json.loads(handle.readline())["meta"]
        trades = [json.loads(line) for line in handle if line.strip()]
    return meta, trades


def stats(rows: list[dict]) -> dict:
    rows = [r for r in rows if "first_1r" in r and not r.get("skipped")]
    out = {"n": len(rows)}
    for m in ("1", "2"):
        w = sum(r[f"first_{m}r"] == "win" for r in rows)
        l = sum(r[f"first_{m}r"] == "loss" for r in rows)
        out[f"win{m}"] = round(100 * w / (w + l), 1) if w + l else None
        out[f"open{m}"] = sum(r[f"first_{m}r"] == "open" for r in rows)
    vals = [r["net_2r"] for r in rows if r.get("net_2r") is not None]
    out["mean_net2r"] = round(sum(vals) / len(vals), 3) if vals else None
    vals = [r["net_1r"] for r in rows if r.get("net_1r") is not None]
    out["mean_net1r"] = round(sum(vals) / len(vals), 3) if vals else None
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="results/backtest/external")
    ap.add_argument("--min", type=int, default=10)
    ap.add_argument("--json-out", default="results/backtest/external/summary.json")
    args = ap.parse_args()
    table = []
    for path in sorted((ROOT / args.root).rglob("*.jsonl.gz")):
        meta, trades = load(path)
        taken = [t for t in trades if t.get("taken")]
        shadow = [t for t in trades if not t.get("taken")]
        row = {"source": path.parent.name, "symbol": meta["symbol"], "stack": "/".join(meta["stack"]), "start": meta["start"],
               "end": meta["end"], "checks": meta.get("checks"), "triggers": len(trades), "taken": stats(taken), "shadow": stats(shadow)}
        table.append(row)
    (ROOT / args.json_out).write_text(json.dumps(table, indent=1))
    head = f"{'source':11} {'sym':4} {'stack':10} {'period':23} {'trig':>5} | {'TAKEN n':>7} {'w1%':>5} {'w2%':>5} {'net2R':>6} | {'SHADOW n':>8} {'w1%':>5} {'w2%':>5} {'net2R':>6}"
    print(head)
    print("-" * len(head))
    for r in table:
        if r["triggers"] < args.min:
            continue
        def cell(s):
            if s["n"] < args.min:
                return f"{s['n']:>7} {'-':>5} {'-':>5} {'-':>6}"
            return f"{s['n']:>7} {s['win1'] or 0:>5} {s['win2'] or 0:>5} {s['mean_net2r']:>6}"
        print(f"{r['source']:11} {r['symbol']:4} {r['stack']:10} {r['start']}..{r['end']} {r['triggers']:>5} | {cell(r['taken'])} | {cell(r['shadow']):>8}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
