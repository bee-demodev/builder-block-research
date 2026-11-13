"""Turn TTrades livestream transcripts + Opus vision/transcript analyses into corpus chunks.

Writes knowledge/ttfm_video_corpus/livestream_chunks.jsonl (same record shape as chunks.jsonl)
and splices it into chunks.jsonl. build_ttfm_video_corpus.build_corpus appends this file every
time it rewrites chunks.jsonl, so livestream content survives any corpus rebuild without the
streams being added to video_manifest.json (which would make the uploads pipeline download them).

Two partitions:
  livestream_qa        raw Whisper transcript, ~1200-char chunks (searchable speech)
  livestream_analysis  one record per Q&A, teaching, warning, trade, live read and per-stream
                       prep, from livestream_analysis/<slug>.json (vision + transcript, Opus)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from build_ttfm_video_corpus import build_chunk_records  # noqa: E402

CORPUS_DIR = ROOT / "knowledge" / "ttfm_video_corpus"
LIVESTREAM_MANIFEST = CORPUS_DIR / "livestream_manifest.json"
ANALYSIS_DIR = CORPUS_DIR / "livestream_analysis"
TRANSCRIPTS_DIR = CORPUS_DIR / "transcripts"
LIVESTREAM_CHUNKS = CORPUS_DIR / "livestream_chunks.jsonl"
CHUNKS = CORPUS_DIR / "chunks.jsonl"
LIVESTREAM_PARTITIONS = {"livestream_qa", "livestream_analysis"}
ANALYSIS_SOURCE = "opus_vision_transcript_analysis"


def _t(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _join(*parts: Any) -> str:
    return " ".join(str(p).strip() for p in parts if p not in (None, "", [], {})).strip()


def analysis_records(row: dict[str, Any], analysis: dict[str, Any]) -> Iterable[dict[str, Any]]:
    base = {
        "video_slug": row["slug"],
        "video_id": row["video_id"],
        "title": f"{row['title']} ({row.get('upload_date')})",
        "source_page": row["url"],
        "corpus_partition": "livestream_analysis",
        "review_categories": [],
        "discovery_source": "youtube_streams_tab",
        "channel_url": row.get("channel_url"),
        "transcript_source": ANALYSIS_SOURCE,
        "stream_date": row.get("upload_date"),
    }

    def rec(kind: str, t: Any, text: str, topics: list[str], **extra: Any) -> dict[str, Any]:
        start = _t(t)
        return {**base, "topics": sorted({x for x in topics if x}), "kind": kind, "start": start, "end": start + 60.0, "text": text, **{k: v for k, v in extra.items() if v}}

    prep = analysis.get("prep") or {}
    htf = "; ".join(
        _join(h.get("symbol"), h.get("timeframe"), h.get("bias"), "-", h.get("reason"), ("DOL: " + h["draw_on_liquidity"]) if h.get("draw_on_liquidity") else "")
        for h in prep.get("htf_read") or []
    )
    levels = "; ".join(_join(k.get("symbol"), k.get("level"), "-", k.get("why")) for k in prep.get("key_levels") or [])
    scenarios = "; ".join(_join("If", s.get("if"), "then", s.get("then")) for s in prep.get("if_then_scenarios") or [])
    smt = "; ".join(_join("/".join(s.get("symbols") or []), s.get("observation")) for s in prep.get("smt") or [])
    yield rec(
        "stream_prep",
        0,
        _join(
            f"Livestream {row.get('upload_date')} summary:", analysis.get("summary"),
            "Day type:", analysis.get("day_type"),
            "Higher-timeframe read:", htf, "Key levels:", levels, "SMT:", smt,
            "Context:", prep.get("news_or_session_context"),
            "Prep order:", " > ".join(prep.get("checklist_order") or []),
            "Scenarios:", scenarios,
        ),
        ["daily_bias", "prep_routine"],
    )
    for qa in analysis.get("qa") or []:
        yield rec("qa", qa.get("t"), _join("Q:", qa.get("question"), "A:", qa.get("answer"), f'"{qa["quote"]}"' if qa.get("quote") else ""), qa.get("concepts") or [])
    for te in analysis.get("teachings") or []:
        yield rec("teaching", te.get("t"), _join(te.get("rule"), f'"{te["quote"]}"' if te.get("quote") else ""), [te.get("concept")], confidence=te.get("confidence"), frame=te.get("frame"))
    for wa in analysis.get("warnings") or []:
        yield rec("warning", wa.get("t"), _join("Mistake:", wa.get("mistake"), "Fix:", wa.get("fix")), ["psychology"])
    for tr in analysis.get("trades") or []:
        yield rec(
            "trade", tr.get("t_entry"),
            _join(tr.get("symbol"), tr.get("direction"), tr.get("model"), "Entry:", tr.get("entry_reason"), "Stop:", tr.get("stop"), "Target:", tr.get("target"), "R:R", tr.get("rr"), "Outcome:", tr.get("outcome")),
            ["trade_review"], frame=tr.get("frame"),
        )
    for lr in analysis.get("live_read") or []:
        yield rec("live_read", lr.get("t"), _join(lr.get("symbol"), lr.get("timeframe"), f"[{lr.get('stage')}]", lr.get("what_he_sees"), "->", lr.get("what_he_does_or_waits_for")), [], frame=lr.get("frame"))
    for vf in analysis.get("visual_only_findings") or []:
        yield rec("visual_finding", vf.get("t"), _join("On chart:", vf.get("finding")), [], frame=vf.get("frame"))


def build() -> dict[str, int]:
    manifest = json.loads(LIVESTREAM_MANIFEST.read_text(encoding="utf-8"))
    records: list[dict[str, Any]] = []
    counts = {"streams": 0, "transcript_chunks": 0, "analysed_streams": 0, "analysis_records": 0}
    for row in manifest["videos"]:
        transcript_path = TRANSCRIPTS_DIR / f"{row['slug']}.json"
        if not transcript_path.exists():
            continue
        counts["streams"] += 1
        video = {**row, "title": f"{row['title']} ({row.get('upload_date')})", "source_page": row["url"]}
        chunks = build_chunk_records(video, json.loads(transcript_path.read_text(encoding="utf-8")))
        for c in chunks:
            c["stream_date"] = row.get("upload_date")
        records += chunks
        counts["transcript_chunks"] += len(chunks)
        analysis_path = ANALYSIS_DIR / f"{row['slug']}.json"
        if analysis_path.exists():
            analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
            recs = list(analysis_records(row, analysis))
            records += recs
            counts["analysed_streams"] += 1
            counts["analysis_records"] += len(recs)
    with LIVESTREAM_CHUNKS.open("w", encoding="utf-8") as handle:
        for r in records:
            handle.write(json.dumps(r, ensure_ascii=False) + "\n")
    splice_into_chunks()
    return counts


def load_livestream_chunks() -> list[dict[str, Any]]:
    if not LIVESTREAM_CHUNKS.exists():
        return []
    return [json.loads(line) for line in LIVESTREAM_CHUNKS.read_text(encoding="utf-8").splitlines() if line.strip()]


def splice_into_chunks() -> None:
    """Replace any livestream rows in chunks.jsonl with the current livestream_chunks.jsonl."""
    kept = []
    if CHUNKS.exists():
        for line in CHUNKS.read_text(encoding="utf-8").splitlines():
            if line.strip() and json.loads(line).get("corpus_partition") not in LIVESTREAM_PARTITIONS:
                kept.append(line)
    extra = [json.dumps(r, ensure_ascii=False) for r in load_livestream_chunks()]
    CHUNKS.write_text("\n".join(kept + extra) + "\n", encoding="utf-8")


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
