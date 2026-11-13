from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


DEFAULT_PACKET_PATH = Path("results") / "live_tradingview_decision_packet.json"
DEFAULT_OUTPUT_PATH = Path("results") / "live_tradingview_decision_report.json"
ALLOWED_VERDICTS = ("take", "watch", "no_trade", "insufficient_evidence")
ENTRY_STATES = {"long_ready", "short_ready"}
MANUAL_SCREENSHOT_STATE_SOURCE = "manual_screenshot_packet_pending_visual_state"
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "for",
    "from",
    "in",
    "into",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "with",
}
TOKEN_RE = re.compile(r"[a-z0-9_]+")


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def resolve(root_dir: Path, path: str | Path) -> Path:
    raw_path = Path(path)
    return raw_path if raw_path.is_absolute() else (root_dir / raw_path).resolve()


def relative_or_absolute(path: Path, root_dir: Path) -> str:
    try:
        return str(path.resolve().relative_to(root_dir.resolve()))
    except ValueError:
        return str(path.resolve())


def tokenize(value: Any) -> set[str]:
    text = json.dumps(value, sort_keys=True) if isinstance(value, (dict, list)) else str(value or "")
    return {token for token in TOKEN_RE.findall(text.lower()) if len(token) > 2 and token not in STOPWORDS}


def compact_text(value: Any, *, max_chars: int = 420) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= max_chars else text[: max_chars - 3].rstrip() + "..."


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                yield payload


def iter_documents(root_dir: Path, corpus_paths: Iterable[str]) -> Iterable[dict[str, Any]]:
    for raw_path in corpus_paths:
        path = resolve(root_dir, raw_path)
        if not path.exists():
            continue
        if path.is_dir():
            for child in sorted(path.rglob("*")):
                if child.suffix.lower() not in {".md", ".txt", ".jsonl"} or not child.is_file():
                    continue
                if child.suffix.lower() == ".jsonl":
                    for row in iter_jsonl(child):
                        yield normalize_corpus_row(row, child, root_dir)
                else:
                    yield {
                        "source_path": relative_or_absolute(child, root_dir),
                        "title": child.stem,
                        "text": child.read_text(encoding="utf-8", errors="ignore"),
                        "topics": [],
                    }
            continue
        if path.suffix.lower() == ".jsonl":
            for row in iter_jsonl(path):
                yield normalize_corpus_row(row, path, root_dir)
        elif path.suffix.lower() in {".md", ".txt"}:
            yield {
                "source_path": relative_or_absolute(path, root_dir),
                "title": path.stem,
                "text": path.read_text(encoding="utf-8", errors="ignore"),
                "topics": [],
            }


def normalize_corpus_row(row: dict[str, Any], path: Path, root_dir: Path) -> dict[str, Any]:
    text = row.get("embedding_text") or row.get("nearby_transcript_text") or row.get("text") or ""
    return {
        "source_path": relative_or_absolute(path, root_dir),
        "example_id": row.get("example_id") or row.get("window_id") or row.get("chunk_id") or "",
        "title": row.get("title") or row.get("video_slug") or "",
        "video_slug": row.get("video_slug") or "",
        "topics": row.get("topics") or row.get("supporting_topics") or [],
        "checkpoint": row.get("checkpoint") or "",
        "timeframe_role": row.get("timeframe_role") or row.get("timeframe") or "",
        "start": row.get("start"),
        "end": row.get("end"),
        "frame_path": row.get("frame_path") or "",
        "text": text,
    }


def retrieval_terms(packet: dict[str, Any]) -> set[str]:
    terms: set[str] = set()
    retrieval = packet.get("retrieval_context", {}) if isinstance(packet.get("retrieval_context"), dict) else {}
    for query in retrieval.get("queries", []):
        if not isinstance(query, dict):
            continue
        terms.update(tokenize(query.get("query", "")))
        terms.update(tokenize(query.get("filters", {})))
    bundle = packet.get("bundle_record", {}) if isinstance(packet.get("bundle_record"), dict) else {}
    for key in ("htf_bias", "direction", "fractal_stage", "poi_type", "entry_state", "invalidation_state", "cue_summary"):
        terms.update(tokenize(bundle.get(key, "")))
    return terms


def retrieve_context(packet: dict[str, Any], *, root_dir: Path, max_hits: int = 6) -> list[dict[str, Any]]:
    retrieval = packet.get("retrieval_context", {}) if isinstance(packet.get("retrieval_context"), dict) else {}
    corpus_paths = retrieval.get("corpus", []) if isinstance(retrieval.get("corpus"), list) else []
    query_terms = retrieval_terms(packet)
    hits: list[dict[str, Any]] = []
    if not query_terms:
        return hits
    for document in iter_documents(root_dir, corpus_paths):
        doc_terms = tokenize(
            {
                "title": document.get("title", ""),
                "topics": document.get("topics", []),
                "checkpoint": document.get("checkpoint", ""),
                "timeframe_role": document.get("timeframe_role", ""),
                "text": document.get("text", ""),
            }
        )
        matched_terms = sorted(query_terms & doc_terms)
        if not matched_terms:
            continue
        score = len(matched_terms)
        if any(term in matched_terms for term in ("daily", "bias", "timeframe", "alignment")):
            score += 2
        if any(term in matched_terms for term in ("sweep", "liquidity", "protected", "poi", "interest")):
            score += 2
        if any(term in matched_terms for term in ("entry", "closure", "cisd", "invalidation")):
            score += 2
        hits.append(
            {
                "score": score,
                "matched_terms": matched_terms[:18],
                "source_path": document.get("source_path", ""),
                "example_id": document.get("example_id", ""),
                "title": document.get("title", ""),
                "video_slug": document.get("video_slug", ""),
                "topics": document.get("topics", []),
                "checkpoint": document.get("checkpoint", ""),
                "timeframe_role": document.get("timeframe_role", ""),
                "start": document.get("start"),
                "end": document.get("end"),
                "frame_path": document.get("frame_path", ""),
                "excerpt": compact_text(document.get("text", "")),
            }
        )
    hits.sort(key=lambda item: (-int(item["score"]), item["source_path"], item.get("example_id", "")))
    return hits[:max_hits]


def visual_markup_verified(packet: dict[str, Any]) -> bool:
    markup = packet.get("visual_markup") or packet.get("visual_markup_result") or {}
    return isinstance(markup, dict) and bool(markup.get("verified") or markup.get("status") == "verified")


def visual_markup(packet: dict[str, Any]) -> dict[str, Any]:
    markup = packet.get("visual_markup") or packet.get("visual_markup_result") or {}
    return markup if isinstance(markup, dict) else {}


def visual_labels(packet: dict[str, Any]) -> list[dict[str, Any]]:
    labels = visual_markup(packet).get("labels", [])
    return [item for item in labels if isinstance(item, dict)] if isinstance(labels, list) else []


def has_visual_label(packet: dict[str, Any], *labels: str) -> bool:
    wanted = set(labels)
    for item in visual_labels(packet):
        label = str(item.get("label") or item.get("type") or "").strip()
        if label in wanted:
            return True
    return False


def is_manual_screenshot_placeholder(bundle: dict[str, Any]) -> bool:
    return str(bundle.get("source") or "") == MANUAL_SCREENSHOT_STATE_SOURCE


def visual_label_confidence(labels: list[dict[str, Any]]) -> float:
    values: list[float] = []
    for label in labels:
        try:
            values.append(float(label.get("confidence", 0.65)))
        except (TypeError, ValueError):
            values.append(0.65)
    if not values:
        return 0.45
    return round(max(0.35, min(sum(values) / len(values), 0.92)), 4)


def derive_ttrades_state(packet: dict[str, Any]) -> dict[str, Any]:
    bundle = packet.get("bundle_record", {}) if isinstance(packet.get("bundle_record"), dict) else {}
    result = {
        "applied": False,
        "source": str(bundle.get("source") or "bundle_record"),
        "reasons": [],
        "blocking_issues": [],
        "state": dict(bundle),
    }
    if not is_manual_screenshot_placeholder(bundle):
        result["reasons"].append("bundle_record_not_manual_screenshot_placeholder")
        return result
    if not visual_markup_verified(packet):
        result["reasons"].append("visual_markup_not_verified")
        return result

    markup = visual_markup(packet)
    labels = visual_labels(packet)
    label_names = {str(item.get("label") or item.get("type") or "").strip() for item in labels}
    direction_hint = str(markup.get("direction_hint") or "unknown").strip().lower()
    entry_readiness = str(markup.get("entry_readiness") or "insufficient_evidence").strip().lower()
    blocking_issues = [
        str(item).strip()
        for item in markup.get("blocking_issues", [])
        if str(item).strip()
    ] if isinstance(markup.get("blocking_issues"), list) else []
    coverage = markup.get("coverage", {}) if isinstance(markup.get("coverage"), dict) else {}
    daily_context = bool(coverage.get("daily_context")) or bool(label_names & {"daily_bias", "liquidity_high", "liquidity_low"})
    h1_structure = bool(coverage.get("h1_structure")) or bool(label_names & {"protected_swing", "poi_or_reaction_zone", "invalidation"})
    m5_entry = bool(coverage.get("m5_entry_evidence")) or bool(label_names & {"sweep", "entry_trigger", "cisd_confirmation"})
    has_missing_context = bool(coverage.get("has_missing_context")) or "missing_context" in label_names
    derived = dict(bundle)
    derived.update(
        {
            "source": "visual_markup_derived_state",
            "visual_state_source": "verified_visual_markup",
            "visual_state_blocking_issues": blocking_issues,
            "visual_state_coverage": {
                "daily_context": daily_context,
                "h1_structure": h1_structure,
                "m5_entry_evidence": m5_entry,
                "has_missing_context": has_missing_context,
            },
            "label_confidence": visual_label_confidence(labels),
        }
    )

    if direction_hint in {"bullish", "bearish"}:
        derived["direction"] = direction_hint
        derived["htf_bias"] = direction_hint if daily_context else "unknown"
    elif direction_hint == "neutral" or entry_readiness == "no_trade":
        derived["direction"] = "none"
        derived["htf_bias"] = "neutral"
    else:
        derived["direction"] = "none"
        derived["htf_bias"] = "unknown"

    if "poi_or_reaction_zone" in label_names:
        derived["poi_type"] = "visual_markup_reaction_zone"
    elif "protected_swing" in label_names:
        derived["poi_type"] = "visual_markup_protected_swing"
    else:
        derived["poi_type"] = "none"
    derived["poi_validity"] = h1_structure and derived["poi_type"] != "none"
    derived["invalidation_state"] = "intact" if "invalidation" in label_names and not blocking_issues else "unknown"
    if entry_readiness == "ready" and direction_hint == "bullish":
        derived["entry_state"] = "long_ready"
    elif entry_readiness == "ready" and direction_hint == "bearish":
        derived["entry_state"] = "short_ready"
    else:
        derived["entry_state"] = "wait"

    all_required_visible = (
        derived["direction"] in {"bullish", "bearish"}
        and derived["htf_bias"] == derived["direction"]
        and derived["poi_validity"]
        and derived["entry_state"] in ENTRY_STATES
        and derived["invalidation_state"] == "intact"
        and m5_entry
        and not has_missing_context
        and not blocking_issues
    )
    if entry_readiness == "no_trade" or direction_hint == "neutral":
        derived["setup_quality"] = "no_setup"
    elif all_required_visible:
        derived["setup_quality"] = "good_setup"
    else:
        derived["setup_quality"] = "unknown"

    result.update(
        {
            "applied": True,
            "source": "visual_markup_derived_state",
            "reasons": [],
            "blocking_issues": blocking_issues + (["visual_missing_context"] if has_missing_context else []),
            "state": derived,
        }
    )
    return result


def effective_bundle(packet: dict[str, Any]) -> dict[str, Any]:
    derived = derive_ttrades_state(packet)
    return dict(derived["state"]) if derived.get("applied") else dict(derived["state"])


def checklist_status(packet: dict[str, Any], retrieval_hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    bundle = effective_bundle(packet)
    direction = str(bundle.get("direction") or "none")
    htf_bias = str(bundle.get("htf_bias") or "unknown")
    entry_state = str(bundle.get("entry_state") or "wait")
    invalidation_state = str(bundle.get("invalidation_state") or "unknown")
    poi_valid = bool(bundle.get("poi_validity"))
    poi_type = str(bundle.get("poi_type") or "none")
    visual_verified = visual_markup_verified(packet)
    return [
        {
            "field": "daily_bias",
            "status": "passed" if htf_bias in {"bullish", "bearish"} else "missing",
            "evidence": f"htf_bias={htf_bias}",
            "required_for_take": True,
        },
        {
            "field": "h1_structure_and_poi",
            "status": "passed" if poi_valid and poi_type != "none" else "missing",
            "evidence": f"poi_type={poi_type}; poi_validity={poi_valid}",
            "required_for_take": True,
        },
        {
            "field": "m5_entry_readiness",
            "status": "passed" if entry_state in ENTRY_STATES and visual_verified else "needs_visual_markup",
            "evidence": f"entry_state={entry_state}; visual_markup_verified={visual_verified}",
            "required_for_take": True,
        },
        {
            "field": "liquidity_draw",
            "status": "passed" if visual_verified and has_visual_label(packet, "sweep", "liquidity_high", "liquidity_low") else "needs_visual_markup",
            "evidence": "requires verified visual markup of liquidity/sweep from the screenshots",
            "required_for_take": True,
        },
        {
            "field": "invalidation",
            "status": "passed" if invalidation_state == "intact" else "missing",
            "evidence": f"invalidation_state={invalidation_state}",
            "required_for_take": True,
        },
        {
            "field": "retrieval_support",
            "status": "passed" if retrieval_hits else "missing",
            "evidence": f"retrieval_hit_count={len(retrieval_hits)}",
            "required_for_take": True,
        },
        {
            "field": "direction_alignment",
            "status": "passed" if direction in {"bullish", "bearish"} and direction == htf_bias else "missing",
            "evidence": f"direction={direction}; htf_bias={htf_bias}",
            "required_for_take": True,
        },
    ]


def decide_verdict(packet: dict[str, Any], checklist: list[dict[str, Any]], retrieval_hits: list[dict[str, Any]]) -> tuple[str, list[str]]:
    raw_bundle = packet.get("bundle_record", {}) if isinstance(packet.get("bundle_record"), dict) else {}
    derived = derive_ttrades_state(packet)
    bundle = dict(derived["state"])
    if not packet.get("decision_ready"):
        return "insufficient_evidence", list(packet.get("blocked_reasons") or ["capture_not_decision_ready"])
    if is_manual_screenshot_placeholder(raw_bundle) and not derived.get("applied"):
        return "insufficient_evidence", list(derived.get("reasons") or ["visual_state_not_derived"])
    setup_quality = str(bundle.get("setup_quality") or "unknown")
    direction = str(bundle.get("direction") or "none")
    if derived.get("applied") and derived.get("blocking_issues"):
        return "insufficient_evidence", list(derived.get("blocking_issues") or ["visual_state_blocked"])
    if is_manual_screenshot_placeholder(raw_bundle) and direction == "none" and setup_quality == "unknown":
        return "insufficient_evidence", ["direction_not_derived_from_visual_markup"]
    if setup_quality in {"no_setup", "bad_setup"} or direction == "none":
        return "no_trade", [f"setup_quality={setup_quality}", f"direction={direction}"]
    required_failures = [
        item["field"]
        for item in checklist
        if item.get("required_for_take") and item.get("status") != "passed"
    ]
    if not required_failures:
        return "take", []
    if "m5_entry_readiness" in required_failures or "liquidity_draw" in required_failures:
        return "watch", required_failures
    if retrieval_hits and setup_quality == "good_setup":
        return "watch", required_failures
    return "insufficient_evidence", required_failures


def confidence_score(packet: dict[str, Any], verdict: str, checklist: list[dict[str, Any]]) -> float:
    bundle = effective_bundle(packet)
    try:
        base = float(bundle.get("label_confidence") or 0.35)
    except (TypeError, ValueError):
        base = 0.35
    passed = sum(1 for item in checklist if item.get("status") == "passed")
    total = max(len(checklist), 1)
    score = (base * 0.55) + ((passed / total) * 0.45)
    if not packet.get("decision_ready"):
        score = min(score, 0.2)
    if not visual_markup_verified(packet):
        score = min(score, 0.45)
    if verdict == "take":
        score = max(score, 0.7)
    return round(score, 4)


def writeup(packet: dict[str, Any], verdict: str, checklist: list[dict[str, Any]], reasons: list[str]) -> dict[str, Any]:
    bundle = effective_bundle(packet)
    direction = str(bundle.get("direction") or "none")
    invalidation = str(bundle.get("invalidation_state") or "unknown")
    entry_state = str(bundle.get("entry_state") or "wait")
    if verdict == "take":
        headline = f"{direction.title()} setup is decision-ready by the current checklist."
        trigger = "Use the verified M5 entry trigger from visual markup."
    elif verdict == "watch":
        headline = "Setup context is present, but the current screenshots do not prove an entry now."
        trigger = "Wait for verified M5 sweep/reaction/confirmation before considering entry."
    elif verdict == "no_trade":
        headline = "No trade by the current TTrades gate."
        trigger = "Reassess only after structure, direction, or invalidation changes."
    else:
        headline = "Insufficient evidence for a trade decision."
        trigger = "Recapture the required Daily/H1/M5 stack or complete verified visual markup."
    missing = [item["field"] for item in checklist if item.get("required_for_take") and item.get("status") != "passed"]
    return {
        "headline": headline,
        "direction": direction,
        "trigger_needed": trigger,
        "invalidation": invalidation,
        "entry_state": entry_state,
        "missing_or_unverified": missing or reasons,
    }


def build_decision_report(
    packet: dict[str, Any],
    *,
    root_dir: Path,
    packet_path: Path,
    max_hits: int = 6,
) -> dict[str, Any]:
    retrieval_hits = retrieve_context(packet, root_dir=root_dir, max_hits=max_hits)
    checklist = checklist_status(packet, retrieval_hits)
    verdict, reasons = decide_verdict(packet, checklist, retrieval_hits)
    derived_state = derive_ttrades_state(packet)
    if verdict not in ALLOWED_VERDICTS:
        verdict = "insufficient_evidence"
    warnings: list[str] = []
    if not visual_markup_verified(packet):
        warnings.append("visual_markup_not_verified")
    if not packet.get("decision_ready"):
        warnings.append("capture_not_decision_ready")
    return {
        "mode": "live_tradingview_decision_report",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_packet_path": relative_or_absolute(packet_path, root_dir),
        "packet_version": packet.get("packet_version", ""),
        "symbol": packet.get("symbol", ""),
        "decision_ready": bool(packet.get("decision_ready")),
        "verdict": verdict,
        "confidence": confidence_score(packet, verdict, checklist),
        "reasons": reasons,
        "warnings": warnings,
        "derived_ttrades_state": derived_state,
        "decision_writeup": writeup(packet, verdict, checklist, reasons),
        "checklist": checklist,
        "retrieval_hits": retrieval_hits,
        "chart_paths": packet.get("chart_paths", {}),
        "journal_stub": {
            "status": "pending_trader_review",
            "verdict": verdict,
            "requires_outcome_later": verdict in {"take", "watch"},
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a TTrades decision-support report from a live TradingView packet.")
    parser.add_argument("--root-dir", type=Path, default=Path("."))
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--max-hits", type=int, default=6)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root_dir = args.root_dir.resolve()
    packet_path = resolve(root_dir, args.packet)
    output_path = resolve(root_dir, args.output)
    packet = load_json(packet_path, {})
    if not isinstance(packet, dict) or not packet:
        raise SystemExit(f"Decision packet not found or invalid: {packet_path}")
    report = build_decision_report(
        packet,
        root_dir=root_dir,
        packet_path=packet_path,
        max_hits=args.max_hits,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output_path": str(output_path),
                "verdict": report["verdict"],
                "confidence": report["confidence"],
                "decision_ready": report["decision_ready"],
                "retrieval_hit_count": len(report["retrieval_hits"]),
                "warnings": report["warnings"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
