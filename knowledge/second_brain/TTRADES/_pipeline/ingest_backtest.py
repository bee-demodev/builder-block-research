"""Register a TTFM backtest run (results/backtest_tv/<year>/<variant>/) as one summary note.

  python ingest_backtest.py results/backtest_tv/2026/baseline --id tv-2026-baseline --what "the app's default rules" [--tests TD-001 CISD-2]

Writes TTRADES/backtests/<id>.md (type: backtest-run) with a per-setup table (symbol, stack + path,
session, trades, 1R / 2R wins, stopped, avg / total R at the 2R plan). The raw files stay where they
are. Backtests are evidence (the engine's own rules, no slippage), never a reason to change a rule
without asking Vik.
"""
from __future__ import annotations

import argparse
import gzip
import json
from collections import defaultdict
from datetime import date
from pathlib import Path

KB = Path(__file__).resolve().parent.parent
REPO = KB.parents[2]


def data_path(folder: Path) -> str:
    """The run folder as written in the note: repo-relative, or from ``results/`` on when the runs
    live in another checkout (never an absolute local path: the repo is public)."""
    try:
        return folder.resolve().relative_to(REPO).as_posix()
    except ValueError:
        parts = folder.resolve().parts
        return "/".join(parts[parts.index("results"):]) if "results" in parts else folder.name


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", nargs="+", help="one or more <year>/<variant> folders (e.g. one per year of a grid)")
    ap.add_argument("--id", required=True)
    ap.add_argument("--what", default="")
    ap.add_argument("--tests", nargs="*", default=[])
    a = ap.parse_args()
    folders = [(REPO / f) if not Path(f).is_absolute() else Path(f) for f in a.folder]
    groups: dict[tuple, list[dict]] = defaultdict(list)
    metas, d_from, d_to = [], None, None
    for p in sorted(p for folder in folders for p in folder.glob("*.jsonl.gz")):
        with gzip.open(p, "rt", encoding="utf-8") as f:
            meta = json.loads(next(f))["meta"]
            metas.append(meta)
            for line in f:
                t = json.loads(line)
                if not t.get("taken"):
                    continue
                day = (t.get("fill_time") or t["check"])[:10]
                d_from, d_to = min(d_from or day, day), max(d_to or day, day)
                groups[(t["symbol"], f"{'-'.join(meta['stack'])} {t.get('path')}", t.get("session") or "?")].append(t)
    if not groups:
        print("no taken trades in", ", ".join(map(str, folders)))
        return
    rows, total, plans = [], 0.0, 0
    for (sym, setup, sess), ts in sorted(groups.items()):
        rs = [t["net_2r"] for t in ts if t.get("net_2r") is not None]
        tot = sum(rs)
        total += tot
        plans += len(ts)
        rows.append(f"| {sym} | {setup} | {sess} | {len(ts)} | {sum(t.get('first_1r') == 'win' for t in ts)} | {sum(t.get('first_2r') == 'win' for t in ts)} | "
                    f"{sum(t.get('first_2r') == 'loss' for t in ts)} | {tot / len(rs) if rs else 0:+.3f} | {tot:+.2f} |")
    symbols = sorted({m["symbol"] for m in metas})
    stacks = sorted({"-".join(m["stack"]) for m in metas})
    out = KB / "backtests" / f"{a.id}.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join([
        "---", f"id: {a.id}", f'title: "TTFM backtest {a.id}: {a.what}"', "type: backtest-run", "model: TTFM",
        f"concepts: [reversal, continuation, cisd, candle-2, protected-swing]", f"run_date: {date.today()}", f"from: {d_from}", f"to: {d_to}",
        f"symbols: {json.dumps(symbols)}", f"switches: {json.dumps({'variant': metas[0].get('variant'), 'stacks': stacks})}",
        f"tests: {json.dumps(a.tests)}", f"plans: {plans}", f"total_r: {total:.2f}", f"data: {json.dumps([data_path(f) for f in folders])}", "---", "",
        f"# TTFM backtest {a.id}", "", a.what, "",
        f"{plans} taken trades, {total:+.2f} R at the 2R plan over {d_from} to {d_to}. The companion's own rules on TradingView bars; "
        "cost model included, no slippage. Evidence, not a validated rule.", "",
        "## Per setup", "", "| Symbol | Stack + path | Session | Trades | 1R wins | 2R wins | Stopped | Avg R | Total R |", "|---|---|---|---|---|---|---|---|---|",
        *rows, ""]), encoding="utf-8")
    print(out.as_posix(), plans, "trades", f"{total:+.2f} R")


if __name__ == "__main__":
    main()
