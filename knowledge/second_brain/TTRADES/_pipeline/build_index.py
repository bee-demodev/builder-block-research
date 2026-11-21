"""Build TTRADES/ttrades-index.sqlite from the markdown notes, the transcripts, the education pages,
the playbooks and the journal, and verify every quoted rule against its transcript.

  python _pipeline/build_index.py [--unverified]     (from anywhere)

Tables
  sources, rules (per video, with quote check), concepts, aliases, edges, concept_rules,
  conflicts, decisions, backtests, backtest_rows        same as TCM-CORE
  trades, days                                          the journal (trade notes with strategy: ttfm)
  rules_fts   rules, concept rules, conflicts           (the teacher's method; search this first)
  docs_fts    transcript chunks, education pages, playbooks, journal notes (evidence)
"""
from __future__ import annotations

import gzip
import json
import re
try:
    import sqlite3
except ImportError:  # Anaconda's _sqlite3 DLL load fails now and then on this machine ("The handle is invalid"); once more
    import time as _t
    _t.sleep(0.5)
    import sqlite3
import sys
from pathlib import Path

import yaml

KB = Path(__file__).resolve().parent.parent
BRAIN = KB.parent  # knowledge/second_brain
REPO = KB.parents[2]
CORPUS = REPO / "knowledge" / "ttfm_video_corpus"
PAGES = REPO / "artifacts" / "ttrades" / "pages"
DB = KB / "ttrades-index.sqlite"
TRANSCRIPTS = CORPUS / "transcripts"


def frontmatter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    try:
        return yaml.safe_load(text.split("---", 2)[1]) or {}
    except yaml.YAMLError:
        return {}


def body(text: str) -> str:
    return text.split("---", 2)[2] if text.startswith("---") else text


def cells(line: str) -> list[str]:
    parts = re.split(r"(?<!\\)\|", line.strip())
    return [p.strip().replace("\\|", "|") for p in parts[1:-1]]


def section(text: str, heading: str) -> str:
    m = re.search(rf"^## {re.escape(heading)}\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    return m.group(1) if m else ""


def tables(text: str, heading: str | None = None):
    """Yield (header_cells, row_cells) for each markdown table row, optionally under one H2."""
    if heading:
        text = section(text, heading)
    header = None
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            header = None
            continue
        c = cells(line)
        if header is None:
            header = c
        elif all(re.fullmatch(r":?-+:?", x) for x in c if x):
            continue
        else:
            yield header, c


def secs(stamp: str) -> int:
    p = [int(x) for x in stamp.split(":")]
    return p[0] * 3600 + p[1] * 60 + p[2] if len(p) == 3 else p[0] * 60 + p[1]


def stamps(text: str) -> list[int]:
    return [secs(s) for s in re.findall(r"\b\d{1,2}:\d{2}(?::\d{2})?\b", text)]


def mmss(t: float) -> str:
    t = int(t)
    return f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}" if t >= 3600 else f"{t // 60:02d}:{t % 60:02d}"


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", str(s).lower())).strip()


def load_segments(slug: str) -> list[dict] | None:
    p = TRANSCRIPTS / f"{slug}.json"
    if not p.exists():
        return None
    data = json.loads(p.read_text(encoding="utf-8"))
    rows = data["segments"] if isinstance(data, dict) else data
    out = []
    for r in rows:
        start = float(r.get("start", 0))
        end = float(r["end"]) if "end" in r else start + float(r.get("duration", 0))
        out.append({"start": start, "end": end, "text": r.get("text", "")})
    return out


def check_quote(quote: str, times: list[int], segs: list[dict], before: int = 90) -> str:
    """verified: every fragment of the quote is in the transcript near a cited time.
    elsewhere: in the transcript but not near the time. close: most 4-grams match nearby.
    unverified: not found. no_quote: nothing to check."""
    q = re.sub(r"\[[^\]]*\]", " ", quote)  # analyst fixes like "sis D [CISD]"
    q = re.sub(r"\([^)]*\)", " ", q)
    frags = [norm(f) for f in re.split(r"\.\.\.|…|\"\s*[/;,]\s*\"|\" / \"", q)]
    frags = [f for f in frags if len(f.split()) >= 3]
    if not frags:
        return "no_quote"
    whole = norm(" ".join(s["text"] for s in segs))
    near = whole
    if times:
        lo, hi = min(times) - before, max(times) + 150
        near = norm(" ".join(s["text"] for s in segs if s["end"] >= lo and s["start"] <= hi))
    if all(f in near for f in frags):
        return "verified"
    if all(f in whole for f in frags):
        return "elsewhere"
    words = " ".join(frags).split()
    grams = [" ".join(words[i:i + 4]) for i in range(max(1, len(words) - 3))]
    if sum(g in near for g in grams) / len(grams) >= 0.6:
        return "close"
    return "unverified"


SCHEMA = """
create table sources(slug primary key, title, recorded, format, partition, youtube_id, duration_min, concepts, path);
create table rules(id primary key, slug, n, rule, concept, conf, time, t_seconds, quote, quote_check);
create table concepts(id primary key, title, confidence, chain_step, timeframe_role, path);
create table aliases(alias, concept_id);
create table edges(src, rel, dst);
create table concept_rules(id primary key, concept_id, n, rule, conf, citations);
create table conflicts(id primary key, concept_id, question, side_a, side_b, kind, status, decision_id);
create table decisions(id primary key, date, question, choice, reason, settles, code);
create table backtests(id primary key, title, model, concepts, run_date, d_from, d_to, symbols, switches, tests, plans, total_r, data, path);
create table backtest_rows(run_id, symbol, setup, grade, plans, tp1, tp2, stopped, avg_r, total_r);
create table trades(id primary key, date, time, symbol, stack, source, path_kind, stage, trigger_kind, direction, bias, session,
                    weekday, entry, stop, risk, target_r, result_r, r_1, r_2, r_3, r_bias_close, mfe_r, mae_r, outcome,
                    status, verdict, mistakes, criteria_failed, why, note_path);
create table days(date primary key, symbols, trades, wins, losses, net_r, status, note_path);
create virtual table rules_fts using fts5(id unindexed, kind unindexed, concept, text);
create virtual table docs_fts using fts5(id unindexed, kind unindexed, title, text);
"""


def index_sources(db) -> None:
    for p in sorted((KB / "sources").glob("*.md")):
        text = p.read_text(encoding="utf-8")
        fm = frontmatter(text)
        slug = fm.get("slug") or p.stem
        db.execute("insert or replace into sources values(?,?,?,?,?,?,?,?,?)", (
            slug, fm.get("title"), str(fm.get("recorded")), fm.get("format"), fm.get("partition"), fm.get("youtube_id"),
            fm.get("duration_min"), json.dumps(fm.get("concepts") or []), p.relative_to(KB).as_posix()))
        segs = load_segments(slug)
        for header, row in tables(text, "Key rules"):
            if len(row) < 6 or not header[0].startswith("#"):
                continue
            n, rule, concept, conf, time, quote = row[:6]
            ts = stamps(time)
            # livestream times are frame times; a frame is taken after the speech it shows (up to 4 min)
            check = check_quote(quote, ts, segs, 330 if fm.get("partition") == "livestream" else 90) if segs else "no_transcript"
            rid = f"{slug}#{n}"
            db.execute("insert or replace into rules values(?,?,?,?,?,?,?,?,?,?)", (rid, slug, n, rule, concept, conf, time, ts[0] if ts else None, quote, check))
            db.execute("insert into rules_fts values(?,?,?,?)", (rid, "rule", concept, f"{rule} {quote}"))


def index_concepts(db) -> None:
    for p in sorted((KB / "concepts").glob("*.md")):
        text = p.read_text(encoding="utf-8")
        fm = frontmatter(text)
        cid = fm.get("id") or p.stem
        db.execute("insert or replace into concepts values(?,?,?,?,?,?)", (cid, fm.get("title", cid), fm.get("confidence"), json.dumps(fm.get("chain_step") or []), json.dumps(fm.get("timeframe_role") or []), p.relative_to(KB).as_posix()))
        for a in {cid, cid.replace("-", " "), fm.get("title", cid), *(fm.get("aliases") or []), *(fm.get("covers") or [])}:
            db.execute("insert into aliases values(?,?)", (norm(str(a)), cid))
        for rel in ("requires", "feeds", "confirms", "invalidates"):
            for dst in fm.get(rel) or []:
                db.execute("insert into edges values(?,?,?)", (cid, rel, dst))
        for header, row in tables(text, "Rules"):
            if len(row) < 4 or not re.fullmatch(r"\d+", row[0]):
                continue
            rid = f"{cid}#{row[0]}"
            db.execute("insert or replace into concept_rules values(?,?,?,?,?,?)", (rid, cid, row[0], row[1], row[2], row[3]))
            db.execute("insert into rules_fts values(?,?,?,?)", (rid, "concept_rule", cid, row[1]))


def index_glossary(db) -> None:
    p = KB / "glossary.md"
    if not p.exists():
        return
    gl = p.read_text(encoding="utf-8")
    for header, row in tables(gl):
        if len(row) >= 4 and header[0].lower().startswith("term"):
            for cid in re.findall(r"\[\[(?:concepts/)?([a-z0-9-]+)\]\]", row[3]):
                if db.execute("select 1 from concepts where id=?", (cid,)).fetchone():
                    for a in [row[0], *re.split(r"[,;]", row[1])]:
                        a = norm(re.sub(r"\([^)]*\)", "", a))
                        if a:
                            db.execute("insert into aliases values(?,?)", (a, cid))
    for header, row in tables(gl, "Mishearings"):
        if len(row) >= 2:
            target = norm(re.sub(r"\([^)]*\)", "", row[1]))
            hit = db.execute("select concept_id from aliases where alias=? limit 1", (target,)).fetchone()
            for w in target.split():
                hit = hit or db.execute("select concept_id from aliases where alias=? limit 1", (w,)).fetchone()
            if hit:
                for a in re.split(r"[,;/]", row[0]):
                    a = norm(re.sub(r"\([^)]*\)", "", a))
                    if a:
                        db.execute("insert into aliases values(?,?)", (a, hit[0]))


def index_conflicts_and_decisions(db) -> None:
    decided = {}
    p = KB / "decisions.md"
    if p.exists():
        for header, row in tables(p.read_text(encoding="utf-8")):
            if len(row) >= 7 and re.fullmatch(r"TD-\d+", row[0]):
                db.execute("insert or replace into decisions values(?,?,?,?,?,?,?)", tuple(row[:7]))
                for c in re.findall(r"[A-Z0-9]+-\d+", row[5]):
                    decided[c] = row[0]
    p = KB / "conflicts.md"
    if p.exists():
        ctext = p.read_text(encoding="utf-8")
        for m in re.finditer(r"^## \[\[(?:concepts/)?([a-z0-9-]+)\]\]\s*$(.*?)(?=^## |\Z)", ctext, re.M | re.S):
            for header, row in tables(m.group(2)):
                if len(row) >= 6 and re.fullmatch(r"[A-Z0-9]+-\d+", row[0]):
                    db.execute("insert or replace into conflicts values(?,?,?,?,?,?,?,?)", (row[0], m.group(1), row[1], row[2], row[3], row[4], row[5], decided.get(row[0])))
                    db.execute("insert into rules_fts values(?,?,?,?)", (row[0], "conflict", m.group(1), f"{row[1]} {row[2]} {row[3]}"))


def index_backtests(db) -> None:
    for p in sorted((KB / "backtests").glob("*.md")):
        text = p.read_text(encoding="utf-8")
        fm = frontmatter(text)
        if fm.get("type") != "backtest-run":
            continue
        db.execute("insert or replace into backtests values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            fm["id"], fm["title"], fm.get("model"), json.dumps(fm.get("concepts") or []), str(fm.get("run_date")), str(fm.get("from")), str(fm.get("to")),
            json.dumps(fm.get("symbols") or []), json.dumps(fm.get("switches") or {}), json.dumps(fm.get("tests") or []), fm.get("plans"), fm.get("total_r"), fm.get("data"), p.relative_to(KB).as_posix()))
        for header, row in tables(text, "Per setup"):
            if len(row) >= 9:
                db.execute("insert into backtest_rows values(?,?,?,?,?,?,?,?,?,?)", (fm["id"], *row[:9]))


def index_docs(db) -> None:
    n = 0
    # Transcript evidence straight from the transcripts (fresh after a re-transcription), in ~60 s windows.
    titles = {}
    for sp in (KB / "sources").glob("*.md"):
        titles[sp.stem] = str(frontmatter(sp.read_text(encoding="utf-8")).get("title") or sp.stem)
    for tp in sorted(TRANSCRIPTS.glob("*.json")):
        segs = load_segments(tp.stem) or []
        win, t0 = [], None
        for sgm in segs + [None]:
            if sgm is not None and (t0 is None or sgm["start"] - t0 < 60):
                t0 = sgm["start"] if t0 is None else t0
                win.append(sgm["text"])
                continue
            if win:
                db.execute("insert into docs_fts values(?,?,?,?)", (f"{tp.stem}@{mmss(t0)}", "transcript", titles.get(tp.stem, tp.stem), " ".join(win)))
                n += 1
            if sgm is not None:
                win, t0 = [sgm["text"]], sgm["start"]
    for p in sorted(PAGES.glob("*.md")):
        db.execute("insert into docs_fts values(?,?,?,?)", (f"page:{p.stem}", "page", p.stem.replace("_", " "), body(p.read_text(encoding="utf-8"))))
    for p in sorted((BRAIN / "wiki" / "playbooks").glob("*.md")):
        t = p.read_text(encoding="utf-8")
        db.execute("insert into docs_fts values(?,?,?,?)", (f"playbook:{p.stem}", "playbook", frontmatter(t).get("title", p.stem), body(t)))
    return n


NUM = lambda v: float(v) if isinstance(v, (int, float)) else (float(v) if isinstance(v, str) and re.fullmatch(r"-?\d+(\.\d+)?", v.strip()) else None)


def index_journal(db) -> None:
    """Trade notes (strategy: ttfm) and TTFM day notes. The markdown is the record: a reviewed
    note's human fields (outcome, verdict, mistakes) flow into the index on the next build."""
    for p in sorted((BRAIN / "trades").glob("*/*.md")):
        text = p.read_text(encoding="utf-8")
        fm = frontmatter(text)
        if fm.get("strategy") != "ttfm":
            continue
        mistakes = " ".join(l.strip("- ").strip() for l in section(text, "Mistakes").splitlines() if l.strip().startswith("-") and "??" not in l)
        db.execute("insert or replace into trades values(" + ",".join("?" * 31) + ")", (
            p.stem, str(fm.get("date")), fm.get("time"), fm.get("symbol"), fm.get("stack"), fm.get("source"), fm.get("path"), fm.get("stage"),
            fm.get("trigger_kind"), fm.get("direction"), fm.get("bias"), fm.get("session"), fm.get("weekday"), NUM(fm.get("entry")), NUM(fm.get("stop")),
            NUM(fm.get("risk")), NUM(fm.get("target_r")), NUM(fm.get("result_r")), NUM(fm.get("r_1")), NUM(fm.get("r_2")), NUM(fm.get("r_3")),
            NUM(fm.get("r_bias_close")), NUM(fm.get("mfe_r")), NUM(fm.get("mae_r")), fm.get("outcome"), fm.get("status"), fm.get("verdict"),
            mistakes, json.dumps(fm.get("criteria_failed") or []), section(text, "Thesis").strip()[:600], p.relative_to(BRAIN).as_posix()))
        db.execute("insert into docs_fts values(?,?,?,?)", (f"trade:{p.stem}", "trade", fm.get("title", p.stem), body(text)))
    for p in sorted((BRAIN / "journal").glob("*/*__ttfm.md")):
        text = p.read_text(encoding="utf-8")
        fm = frontmatter(text)
        db.execute("insert or replace into days values(?,?,?,?,?,?,?,?)", (str(fm.get("date")), json.dumps(fm.get("symbols") or []), fm.get("trades"), fm.get("wins"), fm.get("losses"), NUM(fm.get("net_r")), fm.get("status"), p.relative_to(BRAIN).as_posix()))
        db.execute("insert into docs_fts values(?,?,?,?)", (f"day:{p.stem}", "day", fm.get("title", p.stem), body(text)))


def main() -> None:
    tmp = DB.with_suffix(".tmp.sqlite")
    if tmp.exists():
        tmp.unlink()
    db = sqlite3.connect(tmp)
    db.executescript(SCHEMA)
    index_sources(db)
    index_concepts(db)
    index_glossary(db)
    index_conflicts_and_decisions(db)
    index_backtests(db)
    chunks = index_docs(db)
    index_journal(db)
    db.commit()
    q = lambda s: db.execute(s).fetchall()
    print("sources", q("select count(*) from sources")[0][0], "| rules", q("select count(*) from rules")[0][0],
          "| concepts", q("select count(*) from concepts")[0][0], "| concept rules", q("select count(*) from concept_rules")[0][0],
          "| conflicts", q("select count(*) from conflicts")[0][0], "| decisions", q("select count(*) from decisions")[0][0],
          "| backtests", q("select count(*) from backtests")[0][0], "| trades", q("select count(*) from trades")[0][0],
          "| days", q("select count(*) from days")[0][0], "| transcript chunks", chunks)
    print("quote check:", dict(q("select quote_check, count(*) from rules group by 1")))
    (KB / "rules.jsonl").write_text(
        "\n".join(json.dumps(dict(zip(("id", "slug", "n", "rule", "concept", "conf", "time", "t_seconds", "quote", "quote_check"), r)), ensure_ascii=False) for r in q("select * from rules")) + "\n",
        encoding="utf-8")
    if "--unverified" in sys.argv:
        for r in q("select id, time, quote from rules where quote_check='unverified'"):
            print(r)
    db.close()
    tmp.replace(DB)


if __name__ == "__main__":
    main()
