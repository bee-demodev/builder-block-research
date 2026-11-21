"""Fast lookups over the TTrades brain. One command, one answer, every line cited.

  python tt_lookup.py --map                     the whole method (read first)
  python tt_lookup.py cisd                      concept card: place in the method, definition, conflicts, decisions
  python tt_lookup.py "candle 2" --rules        plus the merged, cited rules (--grep WORD to filter)
  python tt_lookup.py --search "wick into a key level"   teacher's rules first, then transcript / page evidence
  python tt_lookup.py --quote <slug> 12:34      the transcript around a cited time (ground truth)
  python tt_lookup.py --rule <slug>#3           one per-video rule with its quote check
  python tt_lookup.py --conflict CISD-2         one conflict in full
  python tt_lookup.py --sources [concept]       source notes, newest first (optionally for one concept)
  python tt_lookup.py --trades session=asia path=reversal [outcome=loss] [symbol=NQ] [from=2026-01-01] [to=...]
                                                journal trades that match, with win rate and R
  python tt_lookup.py --day 2026-11-03          one journal day: its trades and note path
  python tt_lookup.py --backtest <id> [SYMBOL]  one registered backtest run
  python tt_lookup.py --evidence [WORD]         the evidence ledger: each tested rule / switch, its walk-forward
                                                R per week (train / validate / test) and verdict

Rebuilds the index when any note is newer than it.
"""
from __future__ import annotations

import io
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
from pathlib import Path

KB = Path(__file__).resolve().parent.parent
BRAIN = KB.parent
DB = KB / "ttrades-index.sqlite"
TRANSCRIPTS = KB.parents[2] / "knowledge" / "ttfm_video_corpus" / "transcripts"


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", s.lower())).strip()


def ensure_index() -> None:
    notes = [*KB.glob("*.md"), *(KB / "concepts").glob("*.md"), *(KB / "sources").glob("*.md"), *(KB / "backtests").glob("*.md"),
             *(BRAIN / "trades").glob("*/*.md"), *(BRAIN / "journal").glob("*/*__ttfm.md")]
    if not DB.exists() or (notes and max(p.stat().st_mtime for p in notes) > DB.stat().st_mtime):
        subprocess.run([sys.executable, str(KB / "_pipeline" / "build_index.py")], check=True, stdout=subprocess.DEVNULL)


def section(text: str, heading: str) -> str:
    m = re.search(rf"^## {re.escape(heading)}\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    return m.group(1).strip() if m else ""


def resolve(db, phrase: str) -> list[str]:
    n = norm(phrase)
    hit = [r[0] for r in db.execute("select distinct concept_id from aliases where alias=?", (n,))]
    if hit:
        return hit
    return [r[0] for r in db.execute("select concept_id, count(*) c from aliases where alias like ? group by 1 order by c desc", (f"%{n}%",))][:3]


def fts(db, table: str, phrase: str, limit: int, kind: str | None = None):
    words = [f'"{w}"' for w in norm(phrase).split() if len(w) > 1]
    if not words:
        return []
    where = f" and kind='{kind}'" if kind else ""
    sql = f"select * from {table} where {table} match ?{where} order by bm25({table}) limit {limit}"
    return db.execute(sql, (" AND ".join(words),)).fetchall() or db.execute(sql, (" OR ".join(words),)).fetchall()


def evidence_for(db, cid: str, conflict_ids: set[str]) -> list[tuple]:
    """Ledger rows filed under the concept, or naming one of its conflict / rule ids."""
    out = []
    for row in db.execute("select * from evidence"):
        named = set(re.findall(r"[A-Z0-9]+-\d+", row[0]))
        if row[1] == cid or named & conflict_ids:
            out.append(row)
    return out


def evidence_line(row: tuple) -> str:
    rules, concept, switch, variant, stacks, cap, train, validate, test, verdict, run = row
    return (f"- {rules} [{concept}] {switch} (variant {variant}; {stacks}; {cap}): R/week train {train} | "
            f"validate {validate} | test {test} -> {verdict} [{run}]")


def card(db, cid: str, rules: bool, grep: str | None) -> None:
    title, conf, steps, roles, path = db.execute("select title, confidence, chain_step, timeframe_role, path from concepts where id=?", (cid,)).fetchone()
    text = (KB / path).read_text(encoding="utf-8")
    edges = lambda rel: ", ".join(r[0] for r in db.execute("select dst from edges where src=? and rel=?", (cid, rel))) or "-"
    print(f"# {title}  [{cid}]  (definition consistency: {conf})\nPage: {(KB / path).as_posix()}")
    print(f"\n## Place in the method (see --map)\n- chain step: {', '.join(json.loads(steps)) or '-'} | timeframe role: {', '.join(json.loads(roles)) or '-'}")
    print(f"- requires (upstream): {edges('requires')}\n- feeds (downstream): {edges('feeds')}")
    print("\n## Definition (teacher)\n" + section(text, "Definition"))
    changed = section(text, "How it changed over time")
    if changed:
        print("\n## How it changed over time\n" + changed)
    print("\n## Open conflicts and gaps (ASK Vik before coding anything that depends on an undecided one)")
    rows = db.execute("select id, question, kind, status, decision_id from conflicts where concept_id=?", (cid,)).fetchall()
    for i, q, kind, status, dec in rows:
        print(f"- {i} [{kind}; {'DECIDED ' + dec if dec else 'UNDECIDED, ' + str(status)}] {q[:230]}{'...' if len(q) > 230 else ''}")
    if not rows:
        print("- none recorded")
    print("\n## Vik's decisions (not the teacher's words)")
    ids = {r[0] for r in rows}
    mine = [d for d in db.execute("select id, date, question, choice, settles, code from decisions") if ids & set(re.findall(r"[A-Z0-9]+-\d+", d[4])) or cid.replace("-", " ") in norm(" ".join(map(str, d[2:])))]
    for d in mine:
        print(f"- {d[0]} ({d[1]}): {d[2]} -> {d[3]} | settles: {d[4]} | code: {d[5]}")
    if not mine:
        print("- none recorded for this concept")
    print("\n## Backtest evidence (evidence.md; the engine's own runs, never a reason to override the teacher unasked)")
    found = evidence_for(db, cid, ids)
    for row in found:
        print(evidence_line(row))
    if not found:
        print("- no switch for this concept has been backtested yet")
    t = db.execute("select count(*), sum(result_r), sum(result_r>0) from trades where path_kind=? or trigger_kind=?", (cid, cid)).fetchone()
    if t[0]:
        print(f"\n## Journal evidence\n- {t[0]} journaled trades on this path / trigger, {t[2]} won, {t[1]:+.1f} R. Detail: --trades path={cid}")
    n_rules = db.execute("select count(*) from concept_rules where concept_id=?", (cid,)).fetchone()[0]
    print(f"\n## Rules: {n_rules} merged, cited rules on the page. Add --rules to print them (--grep WORD to filter).")
    if rules:
        for n, rule, c, cites in db.execute("select n, rule, conf, citations from concept_rules where concept_id=?", (cid,)):
            if not grep or grep.lower() in (rule + cites).lower():
                print(f"- [{n}] ({c}) {rule}  << {cites}")
    print("\n## Read next\n- Worked examples: the page's 'Examples' section\n- Verbatim: python tt_lookup.py --quote <slug> mm:ss")


def secs(stamp: str) -> int:
    p = [int(x) for x in stamp.split(":")]
    return p[0] * 3600 + p[1] * 60 + p[2] if len(p) == 3 else p[0] * 60 + p[1]


def quote(slug: str, stamp: str) -> None:
    p = TRANSCRIPTS / f"{slug}.json"
    if not p.exists():
        print(f"no transcript for {slug}")
        return
    t = secs(stamp)
    rows = json.loads(p.read_text(encoding="utf-8"))
    rows = rows["segments"] if isinstance(rows, dict) else rows
    for r in rows:
        if t - 60 <= float(r["start"]) <= t + 90:
            s = int(float(r["start"]))
            print(f"[{s // 60:02d}:{s % 60:02d}] {r['text']}")


def trades(db, args: list[str]) -> None:
    cols = {"symbol", "stack", "session", "direction", "bias", "stage", "trigger_kind", "outcome", "status", "verdict", "source", "weekday"}
    where, vals = [], []
    for a in args:
        if "=" not in a:
            continue
        k, v = a.split("=", 1)
        if k == "path":
            where.append("path_kind=?")
        elif k == "from":
            where.append("date>=?")
        elif k == "to":
            where.append("date<=?")
        elif k in cols:
            where.append(f"{k}=?")
        else:
            print(f"unknown filter {k}; use path, from, to or {', '.join(sorted(cols))}")
            return
        vals.append(v)
    sql = "select date, time, symbol, stack, path_kind, stage, direction, session, result_r, outcome, status, note_path from trades"
    rows = db.execute(sql + (" where " + " and ".join(where) if where else "") + " order by date, time", vals).fetchall()
    for r in rows[-40:]:
        print(f"- {r[0]} {r[1]} {r[2]} {r[3]} {r[4]}/{r[5]} {r[6]} {r[7]}: {'' if r[8] is None else f'{r[8]:+.2f} R'} {r[9]} [{r[10]}] {r[11]}")
    closed = [r for r in rows if r[8] is not None]
    if closed:
        wins = sum(1 for r in closed if r[8] > 0)
        print(f"\n{len(rows)} trades ({len(rows) - 40} older not shown)" if len(rows) > 40 else f"\n{len(rows)} trades")
        print(f"closed {len(closed)}: win rate {wins / len(closed):.0%}, total {sum(r[8] for r in closed):+.2f} R, avg {sum(r[8] for r in closed) / len(closed):+.3f} R (backtest R, before slippage)")
    elif not rows:
        print("no journaled trades match")


def main() -> None:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return
    if args[0] == "--map":
        p = KB / "method-map.md"
        print(p.read_text(encoding="utf-8") if p.exists() else "method-map.md not written yet")
        return
    ensure_index()
    db = sqlite3.connect(DB)
    cmd = args[0]
    if cmd == "--search":
        phrase = " ".join(args[1:])
        rows = fts(db, "rules_fts", phrase, 12)
        print("## Teacher's rules")
        for rid, kind, concept, text in rows:
            print(f"- {rid} [{kind}; {concept}] {text[:260]}")
        if not rows:
            print("- none")
        print("\n## Evidence (transcripts, pages, playbooks, journal)")
        ev = fts(db, "docs_fts", phrase, 8)
        for rid, kind, title, text in ev:
            print(f"- {rid} [{kind}] {title[:70]}: {re.sub(r'\\s+', ' ', text)[:220]}")
        if not rows and not ev:
            print("NOT FOUND. Ask Vik; do not guess.")
        return
    if cmd == "--quote":
        quote(args[1], args[2])
        return
    if cmd == "--rule":
        r = db.execute("select * from rules where id=?", (args[1],)).fetchone()
        print("\n".join(f"{k}: {v}" for k, v in zip(("id", "source", "n", "rule", "concept", "confidence", "time", "seconds", "quote", "quote check"), r)) if r else "no such rule")
        return
    if cmd == "--conflict":
        r = db.execute("select * from conflicts where id=?", (args[1],)).fetchone()
        print("\n".join(f"{k}: {v}" for k, v in zip(("id", "concept", "question", "side A", "side B", "kind", "status", "decision"), r)) if r else "no such conflict")
        return
    if cmd == "--sources":
        c = args[1] if len(args) > 1 else None
        for slug, title, rec, fmt, concepts, path in db.execute("select slug, title, recorded, format, concepts, path from sources order by recorded desc"):
            if not c or c in json.loads(concepts or "[]"):
                print(f"- {rec} [{fmt}] {title} -> {path}")
        return
    if cmd == "--trades":
        trades(db, args[1:])
        return
    if cmd == "--day":
        d = db.execute("select * from days where date=?", (args[1],)).fetchone()
        print(f"day note: {BRAIN.as_posix()}/{d[7]} | {d[2]} trades, {d[3]} won, {d[4]} lost, {d[5]:+.2f} R [{d[6]}]" if d else "no TTFM day note for that date")
        trades(db, [f"from={args[1]}", f"to={args[1]}"])
        return
    if cmd == "--evidence":
        word = " ".join(args[1:]).lower()
        rows = [r for r in db.execute("select * from evidence") if not word or word in " ".join(map(str, r)).lower()]
        for row in rows:
            print(evidence_line(row))
        print(f"\n{len(rows)} ledger row(s). Ledger: {(KB / 'evidence.md').as_posix()}" if rows else "no ledger rows match")
        return
    if cmd == "--backtest":
        r = db.execute("select title, d_from, d_to, switches, tests, data, path from backtests where id=?", (args[1] if len(args) > 1 else "",)).fetchone()
        if not r:
            print("no such run. Runs:", ", ".join(x[0] for x in db.execute("select id from backtests")) or "none registered")
            return
        print(f"{r[0]}\n{r[1]} to {r[2]} | switches {r[3]} | bears on {r[4]}\nnote: {(KB / r[6]).as_posix()}\ndata: {r[5]}")
        q = "select symbol, setup, grade, plans, tp1, tp2, stopped, avg_r, total_r from backtest_rows where run_id=?"
        sym = args[2] if len(args) > 2 else None
        for row in db.execute(q + (" and symbol=?" if sym else ""), (args[1], sym) if sym else (args[1],)):
            print("  " + " | ".join(map(str, row)))
        return
    grep = args[args.index("--grep") + 1] if "--grep" in args else None
    phrase = " ".join(a for a in args if not a.startswith("--") and a != grep)
    ids = resolve(db, phrase)
    if not ids:
        print(f"NOT FOUND: no concept or alias matches '{phrase}'. Try --search, or ask Vik. Do not guess.")
        return
    if len(ids) > 1:
        print(f"'{phrase}' matches several pages: {', '.join(ids)}. Showing the first.\n")
    card(db, ids[0], "--rules" in args, grep)


if __name__ == "__main__":
    main()
