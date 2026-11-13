"""Compile all livestream analyses into themed digests for the cross-stream synthesis pass.

Reads knowledge/ttfm_video_corpus/livestream_analysis/*.json and writes
knowledge/ttfm_video_corpus/livestream_digest/<theme>.md, one compact line per item with its
stream date and timestamp, so a synthesis agent can count how often he says something and cite
it back to a video (https://youtu.be/<id>?t=<seconds>).
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "knowledge" / "ttfm_video_corpus"
ANALYSIS_DIR = CORPUS / "livestream_analysis"
OUT_DIR = CORPUS / "livestream_digest"

THEMES = {
    "prep_and_session": {"prep_routine", "session_timing", "news", "daily_profiles", "session_profile"},
    "bias_and_structure": {"daily_bias", "candle_2", "candle_3", "candle_4", "cisd", "poi", "point_of_interest", "fvg",
                           "fair_value_gap", "protected_swing", "equilibrium", "timeframe_alignment", "wick_logic",
                           "continuation", "reversal", "consolidation", "expansion", "order_block", "breaker"},
    "smt_risk_execution": {"smt", "relative_strength", "risk", "targets", "risk_management", "entry", "stop"},
    "psychology_other": {"psychology", "other"},
}


def theme_for(concepts: list[str]) -> str:
    for theme, keys in THEMES.items():
        if any(c in keys for c in concepts):
            return theme
    return "psychology_other"


def ref(a: dict, t) -> str:
    try:
        sec = int(float(t or 0))
    except (TypeError, ValueError):
        sec = 0
    return f"[{a.get('date')} {a.get('video_id')}@{sec}]"


CURRENT_MODEL_FROM = "2025-01-01"  # streams before this predate the current TTFM model (2022-24: ICT concepts, guests)


def era(a: dict) -> str:
    return "CURRENT" if (a.get("date") or "") >= CURRENT_MODEL_FROM else "OLD"


def write_compact(analyses: list[dict], header: str) -> None:
    """Small views that fit one reader: every teaching as one line, every day as one block."""
    lines = [header, "# All teachings, one line each. Tag: CURRENT = 2025+ (current model), OLD = 2022-24.\n"]
    for a in sorted(analyses, key=lambda x: x.get("date") or "", reverse=True):
        for te in a.get("teachings") or []:
            lines.append(f"- {era(a)} {ref(a, te.get('t'))} ({te.get('concept')}/{te.get('confidence')}) {te.get('rule')}")
    (OUT_DIR / "teachings_compact.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    days = [header, "# Every stream as a day: type, summary, prep order, scenarios, HTF read, warnings.\n"]
    for a in sorted(analyses, key=lambda x: x.get("date") or "", reverse=True):
        prep = a.get("prep") or {}
        days.append(f"\n## {era(a)} {a.get('date')} {a.get('video_id')} — {a.get('title')}")
        days.append(f"day_type: {a.get('day_type')}")
        days.append(f"summary: {a.get('summary')}")
        days.append(f"context: {prep.get('news_or_session_context')}")
        days.append("prep_order: " + " > ".join(prep.get("checklist_order") or []))
        for h in prep.get("htf_read") or []:
            days.append(f"htf: {h.get('symbol')} {h.get('timeframe')} {h.get('bias')} | {h.get('reason')} | DOL {h.get('draw_on_liquidity')}")
        for s in prep.get("smt") or []:
            days.append(f"smt: {'/'.join(s.get('symbols') or [])} {s.get('observation')}")
        for s in prep.get("if_then_scenarios") or []:
            days.append(f"if: {s.get('if')} -> {s.get('then')}")
        for w in a.get("warnings") or []:
            days.append(f"warn: {w.get('mistake')} -> {w.get('fix')}")
    (OUT_DIR / "days_compact.md").write_text("\n".join(days) + "\n", encoding="utf-8")
    write_synthesis_slices(analyses, header)


SLICES = {
    # slice name -> teaching concepts it takes (CURRENT-era streams only)
    "s1_prep_session": {"prep_routine", "session_timing", "news", "daily_profiles", "session_profile"},
    "s2_bias_structure": {"daily_bias", "candle_2", "candle_3", "candle_4", "cisd", "poi", "point_of_interest", "fvg",
                          "fair_value_gap", "protected_swing", "equilibrium", "timeframe_alignment", "wick_logic",
                          "continuation", "reversal", "consolidation", "expansion", "order_block", "breaker"},
    "s3_smt_risk_psych": {"smt", "relative_strength", "risk", "risk_management", "targets", "psychology", "other"},
}


def write_synthesis_slices(analyses: list[dict], header: str) -> None:
    """Inputs for the cross-stream synthesis readers: CURRENT-era only, sized for one reader each."""
    current = sorted((a for a in analyses if era(a) == "CURRENT"), key=lambda x: x.get("date") or "", reverse=True)
    for name, concepts in SLICES.items():
        out = [header, f"# {name}: teachings from {len(current)} current-model streams (2025+)\n"]
        for a in current:
            for te in a.get("teachings") or []:
                c = te.get("concept") or "other"
                if c in concepts or (name == "s3_smt_risk_psych" and not any(c in v for v in SLICES.values())):
                    out.append(f"- {ref(a, te.get('t'))} ({c}/{te.get('confidence')}) {te.get('rule')}")
        if name == "s1_prep_session":
            out.append("\n# Per-day prep (day type, prep order, scenarios)\n")
            for a in current:
                prep = a.get("prep") or {}
                out.append(f"\n## {a.get('date')} {a.get('video_id')}: {a.get('day_type')}")
                out.append(f"context: {prep.get('news_or_session_context')}")
                out.append("prep_order: " + " > ".join(prep.get("checklist_order") or []))
                out += [f"if: {s.get('if')} -> {s.get('then')}" for s in prep.get("if_then_scenarios") or []]
        if name == "s3_smt_risk_psych":
            out.append("\n# Warnings (mistakes he calls out)\n")
            for a in current:
                out += [f"- {ref(a, w.get('t'))} {w.get('mistake')} -> {w.get('fix')}" for w in a.get("warnings") or []]
            out.append("\n# SMT observations in prep\n")
            for a in current:
                out += [f"- {ref(a, s.get('t'))} {'/'.join(s.get('symbols') or [])}: {s.get('observation')}" for s in (a.get("prep") or {}).get("smt") or []]
        (OUT_DIR / f"{name}.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    oq_groups = {"s4_open_questions_a": range(3, 20), "s5_open_questions_b": range(20, 38)}
    for name, qs in oq_groups.items():
        out = [header, f"# {name}: evidence on rules.md section 12 open questions, current-model streams only\n"]
        for q in qs:
            rows = []
            for a in current:
                for e in a.get("open_question_evidence") or []:
                    try:
                        if int(e.get("question")) != q:
                            continue
                    except (TypeError, ValueError):
                        continue
                    rows.append(f"- {ref(a, e.get('t'))} leans: {e.get('leans')} | {e.get('evidence')} | \"{e.get('quote') or ''}\"")
            if rows:
                out.append(f"\n## Q{q} ({len(rows)} items)\n")
                out += rows
        (OUT_DIR / f"{name}.md").write_text("\n".join(out) + "\n", encoding="utf-8")


def main() -> None:
    analyses = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(ANALYSIS_DIR.glob("livestream_*.json"))]
    out: dict[str, list[str]] = defaultdict(list)
    oq: dict[int, list[str]] = defaultdict(list)
    for a in analyses:
        prep = a.get("prep") or {}
        out["prep_and_session"].append(
            f"{ref(a, 0)} DAY: {a.get('day_type')} | SUMMARY: {a.get('summary')} | PREP ORDER: "
            + " > ".join(prep.get("checklist_order") or [])
        )
        for s in prep.get("if_then_scenarios") or []:
            out["prep_and_session"].append(f"{ref(a, s.get('t'))} IF {s.get('if')} THEN {s.get('then')}")
        for h in prep.get("htf_read") or []:
            out["bias_and_structure"].append(
                f"{ref(a, h.get('t'))} HTF {h.get('symbol')} {h.get('timeframe')} {h.get('bias')}: {h.get('reason')} DOL: {h.get('draw_on_liquidity')}"
            )
        for s in prep.get("smt") or []:
            out["smt_risk_execution"].append(f"{ref(a, s.get('t'))} SMT {'/'.join(s.get('symbols') or [])}: {s.get('observation')}")
        for te in a.get("teachings") or []:
            out[theme_for([te.get("concept") or "other"])].append(
                f"{ref(a, te.get('t'))} TEACH ({te.get('concept')}, {te.get('confidence')}): {te.get('rule')}"
            )
        for qa in a.get("qa") or []:
            out[theme_for(qa.get("concepts") or [])].append(f"{ref(a, qa.get('t'))} QA Q: {qa.get('question')} A: {qa.get('answer')}")
        for w in a.get("warnings") or []:
            out["psychology_other"].append(f"{ref(a, w.get('t'))} WARN {w.get('mistake')} -> {w.get('fix')}")
        for tr in a.get("trades") or []:
            out["smt_risk_execution"].append(
                f"{ref(a, tr.get('t_entry'))} TRADE {tr.get('symbol')} {tr.get('direction')} {tr.get('model')}: entry {tr.get('entry_reason')}; stop {tr.get('stop')}; target {tr.get('target')}; rr {tr.get('rr')}; {tr.get('outcome')}"
            )
        for e in a.get("open_question_evidence") or []:
            try:
                q = int(e.get("question"))
            except (TypeError, ValueError):
                continue
            oq[q].append(f"{ref(a, e.get('t'))} leans: {e.get('leans')} | {e.get('evidence')} | \"{e.get('quote') or ''}\"")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    header = f"<!-- generated by scripts/build_livestream_digest.py from {len(analyses)} stream analyses; ref = [date video_id@seconds] -->\n"
    for theme, lines in out.items():
        (OUT_DIR / f"{theme}.md").write_text(header + f"# {theme}\n\n" + "\n".join(f"- {l}" for l in lines) + "\n", encoding="utf-8")
    oq_lines = [header, "# open_question_evidence (rules.md section 12)\n"]
    for q in sorted(oq):
        oq_lines.append(f"\n## Q{q} ({len(oq[q])} streams)\n")
        oq_lines += [f"- {l}" for l in oq[q]]
    (OUT_DIR / "open_questions.md").write_text("\n".join(oq_lines) + "\n", encoding="utf-8")
    write_compact(analyses, header)
    sizes = {p.name: p.stat().st_size for p in OUT_DIR.glob("*.md")}
    print(json.dumps({"analyses": len(analyses), "files": sizes}, indent=2))


if __name__ == "__main__":
    main()
