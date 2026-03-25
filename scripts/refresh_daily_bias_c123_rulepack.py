from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import ttfm_video_embeddings as tve


ROOT = Path(__file__).resolve().parent.parent
RULEPACK_PATH = ROOT / "results" / "rulepacks" / "daily_bias_c123_map.json"
QUERY_TRACE_PATH = ROOT / "results" / "rulepacks" / "daily_bias_c123_map_query_hits.json"

QUERY_GROUPS = {
    "daily_bias": {
        "query": "daily bias from daily closures previous day high low continuation reversal",
        "top_k": 4,
    },
    "daily_poi": {
        "query": "daily point of interest equilibrium previous day high low range hourly setup area",
        "top_k": 4,
    },
    "hourly_sequence": {
        "query": "hourly candle 2 candle 3 swing point point of interest closure higher timeframe",
        "top_k": 4,
    },
    "daily_to_hourly_gating": {
        "query": "drop to hourly only after daily bias and daily point of interest are defined candle 2 closure",
        "top_k": 4,
    },
}


def summarize_citation(match: dict) -> dict:
    return {
        "chunk_id": match.get("chunk_id"),
        "video_id": match.get("video_id"),
        "title": match.get("title"),
        "start": match.get("start"),
        "end": match.get("end"),
        "topics": match.get("topics", []),
        "score": match.get("score"),
        "excerpt": str(match.get("text", "")).strip()[:320],
    }


def citation_list(matches: list[dict]) -> list[dict]:
    return [summarize_citation(match) for match in matches]


def dedupe_citations(groups: list[list[dict]]) -> list[dict]:
    ordered: list[dict] = []
    seen: set[str] = set()
    for citations in groups:
        for citation in citations:
            key = str(citation.get("chunk_id"))
            if key not in seen:
                seen.add(key)
                ordered.append(citation)
    return ordered


def run_queries(*, index_path: Path = tve.INDEX_PATH) -> dict[str, list[dict]]:
    api_key = tve.resolve_google_api_key()
    index = tve.load_embedding_index(index_path)

    hits: dict[str, list[dict]] = {}
    for query_group, query_config in QUERY_GROUPS.items():
        hits[query_group] = tve.search_embedding_index(
            index,
            query=str(query_config["query"]),
            api_key=api_key,
            top_k=int(query_config["top_k"]),
        )
    return hits


def build_rulepack(hits: dict[str, list[dict]]) -> dict:
    daily_bias_citations = citation_list(hits.get("daily_bias", []))
    daily_poi_citations = citation_list(hits.get("daily_poi", []))
    hourly_citations = citation_list(hits.get("hourly_sequence", []))
    gating_citations = citation_list(hits.get("daily_to_hourly_gating", []))

    source_notes = ["Video corpus is the primary authority for this MVP."]
    if (
        not daily_bias_citations
        or not daily_poi_citations
        or not hourly_citations
        or not gating_citations
    ):
        source_notes.append(
            "At least one retrieval group returned sparse evidence; docs may be needed in a later refresh."
        )
    else:
        source_notes.append("No docs were required for clarification in this refresh.")

    sources = dedupe_citations(
        [daily_bias_citations, daily_poi_citations, hourly_citations, gating_citations]
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "trade_model": {
            "slug": "daily_bias_c123_map",
            "name": "Daily Bias C1/C2/C3 Map",
        },
        "timeframe_path": {
            "bias": "D",
            "structure": "60",
            "execution": "5",
        },
        "source_priority": {
            "primary": "videos",
            "secondary": "docs",
            "policy": "Use TTrades videos first. Use docs only to clarify missing details or unresolved mismatches.",
            "notes": source_notes,
        },
        "query_groups": list(hits.keys()),
        "daily_bias_rules": {
            "qualification": [
                "Establish a one-sided daily bias from daily closures before dropping to the hourly chart.",
                "A daily close through the previous day structure supports continuation; failure to close through supports reversal bias.",
                "If there is no clear daily bias, do not continue to the hourly execution read.",
            ],
            "citations": daily_bias_citations,
        },
        "daily_poi_rules": {
            "qualification": [
                "Project the previous day range and equilibrium onto the hourly chart and treat the aligned half of that range as the daily POI.",
                "For bullish daily bias, use the lower half of the previous day range as the retracement zone.",
                "For bearish daily bias, use the upper half of the previous day range as the retracement zone.",
            ],
            "bullish_poi_definition": "Bullish daily POI is bounded by the previous day low and previous day equilibrium.",
            "bearish_poi_definition": "Bearish daily POI is bounded by the previous day equilibrium and previous day high.",
            "citations": daily_poi_citations,
        },
        "hourly_sequence_rules": {
            "activation_start": "Activate hourly structure only after the daily bias is present and the hourly Candle 2 forms inside the daily POI.",
            "activation_end": "End the active hourly sequence when the daily POI loses relevance or the hourly map is invalidated.",
            "c1_definition": "Hourly Candle 1 is the bar immediately before the swing-point bar.",
            "c2_definition": "Hourly Candle 2 is the swing bar that prints at or inside the daily POI and closes in the direction of the daily bias.",
            "c3_definition": "Hourly Candle 3 is the next hourly bar after Candle 2 and represents the expected immediate follow-through.",
            "entry_guidance": "When Candle 2 is confirmed inside the daily POI, the phase-1 entry guide is the open of hourly Candle 3 in the direction of the daily bias.",
            "waiting_guidance": "If Candle 2 has not formed yet, show only one small cue that tells the trader which Candle 2 direction to wait for inside the daily POI.",
            "citations": hourly_citations,
        },
        "lower_timeframe_refinement_rules": {
            "activation_start": "Drop to the five-minute chart only after the hourly C1/C2/C3 sequence aligns with the daily bias and the hourly Candle 3 is active.",
            "c1_definition": "Five-minute Candle 1 is the bar immediately before the five-minute swing bar inside the active hourly Candle 3 window.",
            "c2_definition": "Five-minute Candle 2 is the five-minute swing bar that confirms continuation in the direction of the active hourly sequence.",
            "c3_definition": "Five-minute Candle 3 is the immediate follow-through bar after the five-minute Candle 2 confirmation.",
            "entry_guidance": "Phase-1 execution refines the hourly idea with five-minute continuation confirmation before treating the move as actionable.",
            "citations": hourly_citations,
        },
        "gating_rules": {
            "daily_to_hourly": "Do not look for hourly structure until the daily bias is defined.",
            "hourly_poi_filter": "Only print hourly C1/C2/C3 if Candle 2 forms inside the active daily POI band.",
            "hourly_to_five_minute": "Only evaluate five-minute continuation after the hourly sequence is active and still aligned with the daily bias.",
            "invalidation": "Reset the active hourly sequence when price closes back through the opposite side of the daily POI or when the daily bias is no longer actionable.",
            "citations": gating_citations,
        },
        "docs_support": {
            "used": False,
            "citations": [],
            "notes": ["This refresh relied on the video corpus only."],
        },
        "sources": sources,
    }


def refresh_rulepack(
    *,
    rulepack_path: Path = RULEPACK_PATH,
    query_trace_path: Path = QUERY_TRACE_PATH,
    index_path: Path = tve.INDEX_PATH,
) -> dict:
    hits = run_queries(index_path=index_path)
    rulepack = build_rulepack(hits)

    rulepack_path.parent.mkdir(parents=True, exist_ok=True)
    query_trace_path.parent.mkdir(parents=True, exist_ok=True)
    rulepack_path.write_text(json.dumps(rulepack, indent=2), encoding="utf-8")
    query_trace_path.write_text(json.dumps(hits, indent=2), encoding="utf-8")

    return {
        "ok": True,
        "slug": rulepack["trade_model"]["slug"],
        "rulepack_path": tve.path_for_manifest(rulepack_path),
        "query_trace_path": tve.path_for_manifest(query_trace_path),
        "query_groups": rulepack["query_groups"],
        "citation_count": len(rulepack["sources"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Refresh the daily bias C1/C2/C3 rulepack from the TTFM video embedding index."
    )
    parser.add_argument("--rulepack-path", type=Path, default=RULEPACK_PATH)
    parser.add_argument("--query-trace-path", type=Path, default=QUERY_TRACE_PATH)
    parser.add_argument("--index-path", type=Path, default=tve.INDEX_PATH)
    args = parser.parse_args()

    print(
        json.dumps(
            refresh_rulepack(
                rulepack_path=args.rulepack_path,
                query_trace_path=args.query_trace_path,
                index_path=args.index_path,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
