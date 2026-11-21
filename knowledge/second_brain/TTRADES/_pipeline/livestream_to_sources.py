"""Turn the analysed livestream JSON (ttfm_video_corpus/livestream_analysis/<slug>.json, written by
Opus agents that read each stream's frames and transcript) into TTRADES source notes, same shape as
the video notes, so the index and lookup treat them alike.

  python livestream_to_sources.py           writes sources/<slug>.md for every analysed stream
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
KB = HERE.parent
CORPUS = KB.parents[2] / "knowledge" / "ttfm_video_corpus"

CONCEPT_MAP = {
    "point_of_interest": "poi", "fair_value_gap": "fvg", "inverse_fair_value_gap": "ifvg",
    "session_timing": "time-of-day", "risk_management": "risk", "daily_profiles": "daily-profile",
    "weekly_profiles": "weekly-profile", "top_down_alignment": "top-down-alignment",
    "timeframe_alignment": "timeframe-pairing", "liquidity_sweep": "liquidity-sweep",
    "ttfm_indicator": "ttfm-indicator", "smt_divergence": "smt", "candle2": "candle-2", "candle3": "candle-3",
}
CONF = {"stated_rule": "stated", "demonstrated": "demonstrated", "implied": "implied"}


def cid(c: str | None) -> str:
    c = (c or "").strip().lower()
    return CONCEPT_MAP.get(c, c.replace("_", "-").replace(" ", "-")) or "general"


def mmss(t) -> str:
    try:
        t = int(float(t))
    except (TypeError, ValueError):
        return "?"
    return f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}" if t >= 3600 else f"{t // 60:02d}:{t % 60:02d}"


def cell(s) -> str:
    return str(s if s is not None else "").replace("|", "\\|").replace("\n", " ").strip()


def note(d: dict) -> str:
    slug = d["slug"]
    teach = d.get("teachings") or []
    concepts: dict[str, int] = {}
    for t in teach:
        for c in str(t.get("concept") or "").split(","):
            concepts[cid(c)] = concepts.get(cid(c), 0) + 1
    tfs = sorted({h.get("timeframe") for h in (d.get("prep") or {}).get("htf_read", []) if h.get("timeframe")} |
                 {r.get("timeframe") for r in d.get("live_read") or [] if r.get("timeframe")})
    q = d.get("quality") or {}
    fm = [
        "---",
        f'title: "{d.get("title", slug).replace(chr(34), chr(39))} ({d.get("date")})"',
        "type: ttrades-source",
        f"slug: {slug}",
        "source: youtube-livestream",
        f"youtube_id: {d.get('video_id')}",
        f"youtube_url: https://www.youtube.com/watch?v={d.get('video_id')}",
        "partition: livestream",
        f"recorded: {d.get('date')}",
        "format: live-session",
        "speakers: [ttrades]",
        f"instruments: {json.dumps(d.get('instruments') or [])}",
        f"timeframes: {json.dumps(tfs)}",
        f"concepts: {json.dumps([c for c, _ in sorted(concepts.items(), key=lambda x: -x[1])][:12])}",
        f'transcript: "[[../../ttfm_video_corpus/transcripts/{slug}.txt]]"',
        f'frames: "../../ttfm_video_corpus/livestream_frames/{slug}/"',
        f"day_type: \"{cell(d.get('day_type'))}\"",
        f"analysis: ../../ttfm_video_corpus/livestream_analysis/{slug}.json",
        "confidence: " + ("medium" if q.get("frames_useful") else "low"),
        "---",
        "",
        f"# {d.get('title')} ({d.get('date')})",
        "",
        "> [!info] Converted from the livestream analysis JSON (an Opus agent read the stream's frames and transcript).",
        "",
        "## TL;DR",
        d.get("summary") or "",
        "",
        "## Key rules",
        "| # | Rule (one sentence, operational) | Concept | Conf. | Time | Quote |",
        "|---|---|---|---|---|---|",
    ]
    for i, t in enumerate(teach, 1):
        fm.append(f"| {i} | {cell(t.get('rule'))} | {cid(t.get('concept'))} | {CONF.get(t.get('confidence'), 'stated')} | {mmss(t.get('t'))} | \"{cell(t.get('quote'))}\" |")
    prep = d.get("prep") or {}
    fm += ["", "## The day read (prep)"]
    for h in prep.get("htf_read") or []:
        fm.append(f"- **{h.get('symbol')} {h.get('timeframe')}: {h.get('bias')}** ({mmss(h.get('t'))}): {h.get('reason')} Draw: {h.get('draw_on_liquidity')}.")
    for k in prep.get("key_levels") or []:
        fm.append(f"- Level {k.get('symbol')}: {k.get('level')}: {k.get('why')} ({mmss(k.get('t'))})")
    for s in prep.get("smt") or []:
        fm.append(f"- SMT {'/'.join(s.get('symbols') or [])}: {s.get('observation')} ({mmss(s.get('t'))})")
    if prep.get("news_or_session_context"):
        fm.append(f"- Context: {prep['news_or_session_context']}")
    if prep.get("checklist_order"):
        fm.append("- Checklist order: " + " → ".join(map(str, prep["checklist_order"])))
    for s in prep.get("if_then_scenarios") or []:
        fm.append(f"- If {s.get('if')} → {s.get('then')} ({mmss(s.get('t'))})")
    fm += ["", "## Live read", "| Time | NY | Symbol | TF | Stage | What he sees | What he does / waits for |", "|---|---|---|---|---|---|---|"]
    for r in d.get("live_read") or []:
        fm.append(f"| {mmss(r.get('t'))} | {cell(r.get('when_ny'))} | {cell(r.get('symbol'))} | {cell(r.get('timeframe'))} | {cell(r.get('stage'))} | {cell(r.get('what_he_sees'))} | {cell(r.get('what_he_does_or_waits_for'))} |")
    fm += ["", "## Trades"]
    for t in d.get("trades") or []:
        fm.append(f"- **{t.get('symbol')} {t.get('direction')}** ({mmss(t.get('t_entry'))}): {t.get('model')}. Entry: {t.get('entry_reason')} Stop: {t.get('stop')}. Target: {t.get('target')}. R:R {t.get('rr')}. Outcome: {t.get('outcome')}.")
    if not d.get("trades"):
        fm.append("- none taken")
    fm += ["", "## Q&A"]
    for a in d.get("qa") or []:
        fm.append(f"- **Q ({mmss(a.get('t'))}):** {a.get('question')} **A:** {a.get('answer')}")
    fm += ["", "## Mistakes and warnings"]
    for w in d.get("warnings") or []:
        fm.append(f"- {w.get('mistake')} Fix: {w.get('fix')} ({mmss(w.get('t'))})")
    fm += ["", "## Conflicts and open questions"]
    for v in d.get("visual_only_findings") or []:
        fm.append(f"- Visual only ({mmss(v.get('t'))}): {v.get('finding')}")
    for o in d.get("open_question_evidence") or []:
        fm.append(f"- Open question {o.get('question')} ({mmss(o.get('t'))}): {o.get('evidence')} Leans: {o.get('leans')}")
    if q.get("transcript_issues"):
        fm += ["", "## Glossary additions", f"- {q['transcript_issues']}"]
    return "\n".join(fm) + "\n"


def main() -> None:
    out = KB / "sources"
    out.mkdir(exist_ok=True)
    n = 0
    for p in sorted((CORPUS / "livestream_analysis").glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        (out / f"{d['slug']}.md").write_text(note(d), encoding="utf-8")
        n += 1
    print(n, "livestream notes written")


if __name__ == "__main__":
    main()
