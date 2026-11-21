"""Auto-journal TTFM trades into the Obsidian vault: one trade note per trade, one day note per day,
then refresh the index so agents can query them (tt_lookup.py --trades / --day).

  python auto_journal.py --date 2026-11-03                       backtest trades of one day (NQ 1D-1h-5m)
  python auto_journal.py --from 2026-11-02 --to 2026-11-06 --symbol NQ ES --stack 1D-1h-5m 1D-4h-15m
  python auto_journal.py --last 5                                the last 5 trading days that have trades
  python auto_journal.py --live [--date ...]                     the companion's live decision journal
                                                                 (~/.trading_companion/journal.jsonl)
Options: --variant baseline (backtest), --force (rewrite trade notes still in draft; reviewed notes are
never touched), --dry-run.

Sources
  backtest  results/backtest_tv/<year>/<variant>/<SYM>_<stack>.jsonl.gz rows with taken=true: the
            companion's own rules replayed on TradingView bars. R is before slippage.
  live      the app's decision journal: triggers seen live, your took / skipped mark, the outcome.

What is written (paths relative to knowledge/second_brain)
  trades/YYYY/YYYY-MM-DD__<sym>-ttfm-<path>-<side>-HHMM.md   strategy: ttfm; blanks marked ?? for you
  journal/YYYY/YYYY-MM-DD__ttfm.md                          the day: table, totals, teacher rules; the
                                                            '## My notes' section is kept on rewrite
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
try:
    import sqlite3
except ImportError:  # Anaconda's _sqlite3 DLL load fails now and then on this machine ("The handle is invalid"); once more
    import time as _t
    _t.sleep(0.5)
    import sqlite3
import subprocess
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
KB = HERE.parent
BRAIN = KB.parent
REPO = KB.parents[2]
BACKTEST = REPO / "results" / "backtest_tv"
LIVE = Path.home() / ".trading_companion" / "journal.jsonl"
DB = KB / "ttrades-index.sqlite"
WEEKDAY = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
CRITERIA_TEXT = {
    "data_sufficient": "enough bars loaded", "stack_pairing_stated": "the timeframe pairing is one he teaches",
    "cont_opened_against_bias_first": "the candle opened against the bias first (wick formed)",
    "cont_entry_trigger": "an entry trigger printed", "rev_entry_trigger": "an entry trigger printed",
    "cont_objective_open_at_trigger": "the objective was still open at the trigger",
    "cont_entry_early_in_candle": "the entry came early in the candle", "cont_newer_protected_low": "a newer protected swing formed",
    "bias_closure_directional": "the bias candle closed directionally",
    "bias_poi_present": "a higher-timeframe POI was in play",
    "bias_cisd_confirmed": "CISD confirmed the bias",
    "bias_candle_index_ok": "bias candle numbering fits (C2/C3)",
    "bias_swing_intact": "the bias swing held",
    "bias_c2_not_expanded": "candle 2 had not already expanded",
    "cont_objective_open": "the objective was still open",
    "cont_eq_respected": "EQ was respected",
    "cont_poi_tagged": "price tagged the POI",
    "cont_setup_closure": "the setup candle closed (C2 closure)",
    "cont_setup_closure_body_aligned": "the setup closure's body is with the bias",
    "cont_entry_cisd_confirmed": "entry CISD confirmed",
    "cont_entry_cisd_swift": "the entry CISD was swift",
    "cont_entry_window_open": "the entry window was open",
    "cont_protected_swing_intact": "the protected swing held",
    "cont_trigger_clear_of_liquidity": "the trigger was clear of opposing liquidity",
    "cont_trigger_v_shape": "the trigger was V-shaped",
    "cont_not_inside_consolidation": "not inside a consolidation",
    "cont_reward_at_least_2r": "reward at least 2R",
    "rev_key_level_reached": "a key level was reached",
    "rev_expansion_into_level": "price expanded into the level",
    "rev_opposing_run_small": "the opposing run was small",
    "rev_formed_early": "the reversal formed early in the candle",
    "rev_reclaim": "the level was reclaimed",
    "rev_cisd_confirmed": "reversal CISD confirmed",
    "rev_cisd_swift": "the reversal CISD was swift",
    "rev_wick_intact": "the reversal wick held",
    "rev_reward_at_least_2r": "reward at least 2R",
    "session_filter_ok": "inside the session filter",
}
PATH_CONCEPTS = {"reversal": ["reversal", "cisd", "candle-2"], "continuation": ["continuation", "protected-swing", "candle-3"]}  # per-video rule concepts
PATH_PAGES = {"reversal": ["entry-models", "cisd", "candle-closures", "smt-and-psp"],  # the merged concept pages to link
              "continuation": ["entry-models", "swings-and-structure", "candle-closures", "ranges-and-eq"]}


def fmt(x, nd: int = 2) -> str:
    if x is None:
        return "?"
    return f"{x:,.{nd}f}" if abs(x) < 50 else f"{x:,.2f}"


def r(x) -> str:
    return "?" if x is None else f"{x:+.2f}"


# --- sources -----------------------------------------------------------------------------------

def backtest_trades(symbols: list[str], stacks: list[str], variant: str, d_from: date, d_to: date) -> list[dict]:
    out = []
    for year in range(d_from.year, d_to.year + 1):
        for sym in symbols:
            for stack in stacks:
                p = BACKTEST / str(year) / variant / f"{sym}_{stack}.jsonl.gz"
                if not p.exists():
                    continue
                with gzip.open(p, "rt", encoding="utf-8") as f:
                    next(f)  # meta
                    for line in f:
                        t = json.loads(line)
                        if not t.get("taken"):
                            continue
                        when = datetime.fromisoformat(t["fill_time"] or t["check"])
                        if d_from <= when.date() <= d_to:
                            t["_when"], t["_source"], t["_file"] = when, f"backtest {variant}", p.relative_to(REPO).as_posix()
                            out.append(t)
    return out


def live_trades(d_from: date, d_to: date) -> list[dict]:
    if not LIVE.exists():
        return []
    out = []
    for line in LIVE.open(encoding="utf-8"):
        if not line.strip():
            continue
        x = json.loads(line)
        when = datetime.fromisoformat(x.get("since") or x.get("as_of"))
        if not d_from <= when.date() <= d_to:
            continue
        risk = abs((x.get("entry") or 0) - (x.get("stop") or 0)) or None
        out.append({
            "_when": when, "_source": "live", "_file": LIVE.as_posix(), "symbol": x.get("symbol"), "stack": x.get("stack"),
            "direction": x.get("side"), "path": x.get("style") or "", "stage": x.get("stage_label") or "", "decision": x.get("decision"),
            "trigger_kind": "", "bias": "", "session": "", "fill": x.get("entry"), "plan_stop": x.get("stop"), "risk": risk,
            "structural_targets": [x["target"]] if x.get("target") else [], "why": x.get("note") or "", "blocking": x.get("blocked") or [],
            "mark": x.get("mark"), "mark_reason": x.get("reason"), "live_outcome": x.get("outcome"), "result_r": x.get("result_r"),
            "target_r": x.get("r_multiple"), "criteria": {},
        })
    return out


# --- notes -------------------------------------------------------------------------------------

def slug(t: dict) -> str:
    stack = t["stack"].replace(" / ", "-").replace("/", "-").replace(" ", "")
    return f"{t['_when']:%Y-%m-%d}__{t['symbol'].lower()}-ttfm-{stack.lower()}-{t.get('path') or 'plan'}-{t['direction']}-{t['_when']:%H%M}"


def outcome_of(t: dict) -> tuple[str, float | None]:
    if t["_source"] == "live":
        o = t.get("live_outcome") or "open"
        return {"target_reached": "win", "stopped": "loss"}.get(o, "unknown" if o == "open" else o), t.get("result_r")
    res = t.get("net_2r")  # the plan's rule: reward at least 2R
    first = t.get("first_2r")
    return first or "unknown", res  # win | loss | open at the data end / bias close


def teacher_rules(db, concepts: list[str], words: str, k: int = 3) -> list[tuple]:
    """Stated, verified rules from the brain that bear on this trade's path and trigger."""
    if db is None:
        return []
    rows = []
    for c in concepts:
        rows += db.execute("select r.id, r.rule, r.time, r.slug from rules r where r.concept=? and r.conf='stated' and r.quote_check='verified' "
                           "and r.id in (select id from rules_fts where rules_fts match ?) limit 2", (c, " OR ".join(f'"{w}"' for w in words.split() if len(w) > 2) or '"the"')).fetchall()
    seen, out = set(), []
    for row in rows:
        if row[0] not in seen:
            seen.add(row[0])
            out.append(row)
    return out[:k]


def trade_note(t: dict, db) -> tuple[str, dict]:
    when = t["_when"]
    outcome, res = outcome_of(t)
    risk = t.get("risk")
    entry = t.get("fill") if t.get("fill") is not None else t.get("plan_entry")
    # the checklist of the path the engine took: a reversal is not judged by the continuation criteria
    other = {"reversal": "cont_", "continuation": "rev_"}.get(t.get("path") or "", "#")
    crit = {k: v for k, v in (t.get("criteria") or {}).items() if not k.startswith(other)}
    failed = [k for k, v in crit.items() if v is False]
    passed = [k for k, v in crit.items() if v is True]
    tgt = (t.get("structural_targets") or [None])[0]
    concepts = PATH_CONCEPTS.get(t.get("path") or "", [])
    meta = {
        "title": f"Trade Review - {t['symbol']} TTFM {t.get('path') or ''} {t['direction']} {when:%H:%M}",
        "date": f"{when:%Y-%m-%d}", "time": f"{when:%H:%M}", "type": "trade", "strategy": "ttfm",
        "model": f"TTFM {t['stack']}", "stack": t["stack"], "symbol": t["symbol"], "source": t["_source"],
        "session": t.get("session") or "unknown", "weekday": WEEKDAY[when.weekday()], "direction": t["direction"],
        "path": t.get("path") or "", "stage": t.get("stage") or "", "trigger_kind": t.get("trigger_kind") or "",
        "bias": t.get("bias") or "", "entry": entry, "stop": t.get("plan_stop"), "risk": risk,
        "target_r": t.get("target_r") or 2.0, "result_r": None if res is None else round(res, 3),
        "r_1": None if t.get("net_1r") is None else round(t["net_1r"], 3), "r_2": None if t.get("net_2r") is None else round(t["net_2r"], 3),
        "r_3": None if t.get("net_3r") is None else round(t["net_3r"], 3),
        "r_bias_close": None if t.get("r_bias_close") is None else round(t["r_bias_close"], 3),
        "mfe_r": None if t.get("mfe_r") is None else round(t["mfe_r"], 3), "mae_r": None if t.get("mae_r") is None else round(t["mae_r"], 3),
        "outcome": outcome, "criteria_failed": failed, "status": "draft", "confidence": "unknown",
        "verdict": "??", "source_count": 1, "journal": f"[[{when:%Y-%m-%d}__ttfm]]",
    }
    if t["_source"] == "live":
        meta["mark"] = t.get("mark") or ""
    fm = "---\n" + "\n".join(f"{k}: {json.dumps(v, ensure_ascii=False) if isinstance(v, (list, str)) and (isinstance(v, list) or re.search(r'[:#\[\]{}]|^$', v)) else ('null' if v is None else v)}" for k, v in meta.items()) + "\n---\n"
    src_note = ("The companion's own rules replayed on TradingView bars (`" + t["_file"] + "`). Fill at the trigger candle's close; "
                "R includes the backtest's cost model but no slippage; when one candle spans stop and target the stop wins.") if t["_source"] != "live" \
        else f"From the companion's live decision journal (`{t['_file']}`). Your mark: **{t.get('mark') or 'not marked'}** {t.get('mark_reason') or ''}."
    lines = [fm, f"# {t['symbol']} TTFM {t.get('path') or ''} {t['direction']} {when:%a %d %b %H:%M}", "",
             "> [!info] Journaled automatically, not a live fill" if t["_source"] != "live" else "> [!info] Journaled automatically from the live app",
             f"> {src_note} Fill the blanks marked `??` and set `status: reviewed`.", "",
             "## Quick log", "",
             f"- **Model:** TTFM {t['stack']}, {t.get('path') or '?'} at {t.get('stage') or '?'}, trigger {t.get('trigger_kind') or '?'}; bias {t.get('bias') or '?'}; {meta['session']} session, {meta['weekday']}",
             f"- **Entry:** {fmt(entry)} at {when:%H:%M} ({t['direction']})",
             f"- **Stop:** {fmt(t.get('plan_stop'))} (risk {fmt(risk)} points" + (f", {t['risk_adr']:.0%} of ADR14)" if t.get("risk_adr") else ")"),
             f"- **Target:** 2R" + (f"; structural target {fmt(tgt)}" if tgt else ""),
             f"- **Result:** {r(res)} R ({outcome}); ladder 1R {r(t.get('net_1r'))}, 2R {r(t.get('net_2r'))}, 3R {r(t.get('net_3r'))}, held to the bias close {r(t.get('r_bias_close'))}",
             f"- **Excursion:** best {r(t.get('mfe_r'))} R, worst {r(-(t.get('mae_r') or 0) if t.get('mae_r') is not None else None)} R" + (f"; stopped after {t['minutes_to_stop']:.0f} min" if t.get("minutes_to_stop") else ""),
             "", "## Thesis", "", (t.get("why") or "??"), "",
             "## Checklist (the engine's criteria)", ""]
    lines += [f"- [x] {CRITERIA_TEXT.get(k, k)}" for k in passed] + [f"- [ ] {CRITERIA_TEXT.get(k, k)} (`{k}`)" for k in failed]
    if not crit:
        lines.append("- no criteria recorded")
    lines += ["", "## What actually happened", "", "??", "", "## Mistakes", "", "- ??", "", "## What still looks valid", "", "- ??", "",
              "## Verdict", "", "Verdict: ?? (valid_model_trade | rule_gap | engine_error | discretion_better). Would you have taken it: ??", "",
              "## Teacher's rules that bear on it", ""]
    rules = teacher_rules(db, concepts, " ".join([t.get("path") or "", t.get("trigger_kind") or "", t.get("stage") or "", t.get("session") or ""]))
    lines += [f"- {rule} ([[TTRADES/sources/{s}|{s}]] {tm})" for _, rule, tm, s in rules] or ["- (build the index to link rules)"]
    lines += ["", "## Linked", "", f"- [[{when:%Y-%m-%d}__ttfm]]"] + [f"- [[TTRADES/concepts/{c}|{c}]]" for c in PATH_PAGES.get(t.get("path") or "", [])]
    return "\n".join(lines) + "\n", meta


def day_note(day: date, rows: list[tuple[str, dict]], old: str | None) -> str:
    closed = [m for _, m in rows if m["result_r"] is not None]
    wins = sum(1 for m in closed if m["result_r"] > 0)
    net = sum(m["result_r"] for m in closed)
    keep = "\n- ??\n"
    if old and "## My notes" in old:
        keep = old.split("## My notes", 1)[1]
    status = "reviewed" if old and re.search(r"^status: reviewed", old, re.M) else "draft"
    syms = sorted({m["symbol"] for _, m in rows})
    head = ["---", f"title: {day:%Y-%m-%d} TTFM journal", f"date: {day:%Y-%m-%d}", "type: journal", "strategy: ttfm",
            f"symbols: {json.dumps(syms)}", f"trades: {len(rows)}", f"wins: {wins}", f"losses: {len(closed) - wins}",
            f"net_r: {net:.3f}", f"status: {status}", f"source_count: {len(rows)}", "---", "",
            f"# {day:%A %d %B %Y}: TTFM", "",
            f"> [!summary] {len(rows)} trade{'s' if len(rows) != 1 else ''} on {', '.join(syms)}: {wins} won, {len(closed) - wins} lost, {net:+.2f} R (2R plan, backtest R before slippage).", "",
            "## Trades", "", "| Time | Symbol | Stack | Path / stage | Side | Session | R | Outcome | Note |", "|---|---|---|---|---|---|---|---|---|"]
    for name, m in sorted(rows, key=lambda x: x[1]["time"]):
        head.append(f"| {m['time']} | {m['symbol']} | {m['stack']} | {m['path']} / {m['stage']} | {m['direction']} | {m['session']} | {r(m['result_r'])} | {m['outcome']} | [[{name}]] |")
    fails = defaultdict(int)
    for _, m in rows:
        for k in m["criteria_failed"]:
            fails[k] += 1
    head += ["", "## Patterns today", ""]
    by_path = defaultdict(list)
    for _, m in rows:
        if m["result_r"] is not None:
            by_path[(m["path"], m["session"])].append(m["result_r"])
    head += [f"- {p or '?'} in {s}: {len(v)} trades, {sum(1 for x in v if x > 0)} won, {sum(v):+.2f} R" for (p, s), v in sorted(by_path.items())]
    if fails:
        head.append("- Criteria the engine let through as failed: " + ", ".join(f"{CRITERIA_TEXT.get(k, k)} ({n})" for k, n in sorted(fails.items(), key=lambda x: -x[1])))
    head += ["", "## Review prompts", "", "- Which of these would you have taken, and which skipped? Mark each note's verdict.",
             "- Did the daily bias read hold all day? ??", "- Candidate promotions (rule changes to test, never applied directly): ??", "",
             "## My notes" + keep.rstrip("\n") + "\n"]
    return "\n".join(head)


# --- main --------------------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date")
    ap.add_argument("--from", dest="d_from")
    ap.add_argument("--to", dest="d_to")
    ap.add_argument("--last", type=int)
    ap.add_argument("--symbol", nargs="+", default=["NQ"])
    ap.add_argument("--stack", nargs="+", default=["1D-1h-5m"])
    ap.add_argument("--variant", default="baseline")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    today = date.today()
    if a.date:
        d_from = d_to = date.fromisoformat(a.date)
    else:
        d_from = date.fromisoformat(a.d_from) if a.d_from else date(today.year, 1, 1)
        d_to = date.fromisoformat(a.d_to) if a.d_to else today
    trades = live_trades(d_from, d_to) if a.live else backtest_trades(a.symbol, a.stack, a.variant, d_from, d_to)
    if a.last:
        days = sorted({t["_when"].date() for t in trades})[-a.last:]
        trades = [t for t in trades if t["_when"].date() in days]
    if not trades:
        print(f"no trades from {d_from} to {d_to} ({'live journal ' + LIVE.as_posix() if a.live else ', '.join(a.symbol) + ' ' + ', '.join(a.stack)})")
        return
    db = sqlite3.connect(DB) if DB.exists() else None
    per_day: dict[date, list[tuple[str, dict]]] = defaultdict(list)
    wrote = skipped = 0
    for t in sorted(trades, key=lambda t: t["_when"]):
        name = slug(t)
        text, meta = trade_note(t, db)
        p = BRAIN / "trades" / f"{t['_when']:%Y}" / f"{name}.md"
        per_day[t["_when"].date()].append((name, meta))
        if p.exists():
            old = p.read_text(encoding="utf-8")
            if re.search(r"^status: reviewed", old, re.M) or not a.force:
                skipped += 1
                continue
        if not a.dry_run:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
        wrote += 1
    for day, rows in sorted(per_day.items()):
        p = BRAIN / "journal" / f"{day:%Y}" / f"{day:%Y-%m-%d}__ttfm.md"
        old = p.read_text(encoding="utf-8") if p.exists() else None
        if not a.dry_run:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(day_note(day, rows, old), encoding="utf-8")
        print(f"{p.relative_to(BRAIN).as_posix()}: {len(rows)} trades")
    if db is not None:
        db.close()
    print(f"{wrote} trade notes written, {skipped} kept (existing; --force rewrites drafts, reviewed notes are never touched)")
    if not a.dry_run:
        subprocess.run([sys.executable, str(HERE / "build_index.py")], check=True, stdout=subprocess.DEVNULL)
        print("index refreshed: python tt_lookup.py --day <date> | --trades path=reversal session=asia")


if __name__ == "__main__":
    main()
