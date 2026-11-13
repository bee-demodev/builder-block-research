from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fractal_state import DEFAULT_STATE_SPEC_PATH, FractalStateMachine, load_state_machine


DEFAULT_BUNDLE_SEED_PATHS = (
    Path("results") / "phase2_bundle_gold_seed.jsonl",
    Path("results") / "live_tradingview_bundle_seed.jsonl",
)
DEFAULT_BUNDLE_REPORT_PATH = Path("results") / "phase2_bundle_gold_seed_report.json"
DEFAULT_CORPUS_CHUNKS_PATH = Path("knowledge") / "ttfm_video_corpus" / "chunks.jsonl"
DEFAULT_OUTPUT_PACKET_PATH = Path("results") / "ttrades_state_review_packet_20260622.json"
DEFAULT_OUTPUT_ANSWERS_PATH = Path("results") / "ttrades_state_review_answers.seed_20260622.json"
TOKEN_PATTERN = re.compile(r"[a-z0-9_]+")
STOPWORDS = {
    "and",
    "are",
    "for",
    "from",
    "have",
    "the",
    "this",
    "that",
    "with",
}


@dataclass(slots=True)
class StateReviewConfig:
    root_dir: Path
    bundle_seed_paths: tuple[Path, ...] = field(default_factory=lambda: DEFAULT_BUNDLE_SEED_PATHS)
    bundle_report_path: Path = DEFAULT_BUNDLE_REPORT_PATH
    corpus_chunks_path: Path = DEFAULT_CORPUS_CHUNKS_PATH
    state_machine_path: Path = DEFAULT_STATE_SPEC_PATH
    output_packet_path: Path = DEFAULT_OUTPUT_PACKET_PATH
    output_answers_path: Path = DEFAULT_OUTPUT_ANSWERS_PATH
    limit: int = 80


def resolve_path(root_dir: Path, path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else root_dir / candidate


def relative_or_absolute(path: Path, root_dir: Path) -> str:
    try:
        return str(path.resolve().relative_to(root_dir.resolve()))
    except ValueError:
        return str(path)


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        cleaned = line.strip()
        if cleaned:
            payload = json.loads(cleaned)
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in TOKEN_PATTERN.findall(text.lower())
        if len(token) >= 3 and token not in STOPWORDS
    }


def _load_corpus_chunks(root_dir: Path, path: Path) -> list[dict[str, Any]]:
    chunks = read_jsonl(resolve_path(root_dir, path))
    normalized: list[dict[str, Any]] = []
    for chunk in chunks:
        text = str(chunk.get("text") or "")
        topics = [str(topic) for topic in chunk.get("topics", []) if isinstance(topic, str)]
        token_set = _tokens(" ".join([str(chunk.get("title") or ""), " ".join(topics), text]))
        if token_set:
            normalized.append({**chunk, "_tokens": token_set})
    return normalized


def _corpus_query_text(row: dict[str, Any], state: dict[str, Any]) -> str:
    parts = [
        str(row.get("bundle_id") or ""),
        str(row.get("cue_summary") or ""),
        state["path_family"],
        state["direction"],
        state["fractal_stage"],
        state["htf_bias"],
        state["poi"]["type"],
        state["setup_quality"],
        state["entry_state"],
        " ".join(state["missing_evidence"]),
    ]
    return " ".join(part for part in parts if part)


def _corpus_evidence(
    row: dict[str, Any],
    state: dict[str, Any],
    corpus_chunks: list[dict[str, Any]],
    *,
    limit: int = 3,
) -> list[dict[str, Any]]:
    query_tokens = _tokens(_corpus_query_text(row, state))
    if not query_tokens:
        return []
    scored: list[tuple[float, dict[str, Any]]] = []
    for chunk in corpus_chunks:
        chunk_tokens = chunk.get("_tokens", set())
        overlap = query_tokens.intersection(chunk_tokens)
        if not overlap:
            continue
        topics = {str(topic) for topic in chunk.get("topics", []) if isinstance(topic, str)}
        topic_bonus = 0.5 * len(topics.intersection(query_tokens))
        scored.append((float(len(overlap)) + topic_bonus, chunk))
    scored.sort(key=lambda item: (-item[0], str(item[1].get("chunk_id") or "")))
    evidence: list[dict[str, Any]] = []
    for score, chunk in scored[:limit]:
        text = " ".join(str(chunk.get("text") or "").split())
        video_slug = str(chunk.get("video_slug") or "")
        chunk_id = str(chunk.get("chunk_id") or f"{video_slug}:{chunk.get('start', '')}-{chunk.get('end', '')}")
        evidence.append(
            {
                "chunk_id": chunk_id,
                "title": str(chunk.get("title") or ""),
                "source_path": str(chunk.get("source_page") or ""),
                "video_slug": video_slug,
                "topics": [str(topic) for topic in chunk.get("topics", []) if isinstance(topic, str)],
                "score": round(score, 4),
                "claim": text[:280],
            }
        )
    return evidence


def _enum_default(machine: FractalStateMachine, enum_name: str, value: Any, fallback: str) -> str:
    candidate = str(value or "").strip()
    if candidate in machine.enums[enum_name]:
        return candidate
    return fallback


def _direction_alignment(direction: str) -> dict[str, Any]:
    value = direction if direction in {"bullish", "bearish"} else "none"
    return {
        "daily": value,
        "h1": value,
        "m5": value,
        "is_aligned": value != "none",
    }


def _candidate_missing_evidence(row: dict[str, Any], state: dict[str, Any]) -> list[str]:
    missing: list[str] = ["manual_visual_review_required"]
    if state["direction"] == "none":
        missing.append("directional_bias_unlabeled")
    if state["htf_bias"] == "neutral":
        missing.append("daily_or_htf_bias_unlabeled")
    if not state["timeframe_alignment"]["is_aligned"]:
        missing.append("daily_h1_m5_alignment_unverified")
    if state["poi"]["type"] == "none":
        missing.append("point_of_interest_unlabeled")
    if state["entry_state"] == "wait" and state["fractal_stage"] == "c4" and state["setup_quality"] == "good_setup":
        missing.append("c4_entry_readiness_unverified")
    if state["invalidation"]["state"] == "unknown":
        missing.append("invalidation_unlabeled")
    if not row.get("detector_boxes_by_frame"):
        missing.append("no_yolo_detections_attached")
    if str(row.get("review_outcome", "")).strip().lower() in {"needs_review", "derived", ""}:
        missing.append("source_candidate_not_gold")
    return list(dict.fromkeys(missing))


def _candidate_decision(state: dict[str, Any]) -> dict[str, Any]:
    missing = list(state["missing_evidence"])
    blocking_conditions = list(missing)
    if missing:
        return {
            "verdict": "insufficient_evidence",
            "reasons": ["Candidate state still needs visual confirmation before it can train or trade."],
            "blocking_conditions": blocking_conditions,
        }
    if state["entry_state"] == "long_ready":
        return {
            "verdict": "valid_long_setup",
            "reasons": ["Candidate state is C4, bullish, aligned, and has intact invalidation."],
            "blocking_conditions": [],
        }
    if state["entry_state"] == "short_ready":
        return {
            "verdict": "valid_short_setup",
            "reasons": ["Candidate state is C4, bearish, aligned, and has intact invalidation."],
            "blocking_conditions": [],
        }
    return {
        "verdict": "watch_only",
        "reasons": ["Candidate state is not entry-ready."],
        "blocking_conditions": ["entry_state_is_wait"],
    }


def _review_fields_from_missing(missing: list[str]) -> list[str]:
    field_map = {
        "directional_bias_unlabeled": "direction",
        "daily_or_htf_bias_unlabeled": "htf_bias",
        "daily_h1_m5_alignment_unverified": "timeframe_alignment",
        "point_of_interest_unlabeled": "poi",
        "c4_entry_readiness_unverified": "entry_state",
        "invalidation_unlabeled": "invalidation",
        "no_yolo_detections_attached": "detections",
        "source_candidate_not_gold": "review_outcome",
        "manual_visual_review_required": "visual_confirmation",
    }
    return list(dict.fromkeys(field_map.get(item, item) for item in missing))


def _candidate_state_from_bundle(row: dict[str, Any], machine: FractalStateMachine) -> dict[str, Any]:
    direction = _enum_default(machine, "direction", row.get("direction"), "none")
    htf_bias = _enum_default(machine, "htf_bias", row.get("htf_bias"), "neutral")
    state = {
        "path_family": _enum_default(machine, "path_family", row.get("path_family"), "continuation"),
        "direction": direction,
        "fractal_stage": _enum_default(machine, "fractal_stage", row.get("fractal_stage"), "none"),
        "htf_bias": htf_bias,
        "timeframe_alignment": _direction_alignment(direction if htf_bias == direction else "none"),
        "poi": {
            "type": _enum_default(machine, "poi_type", row.get("poi_type"), "none"),
            "direction": _enum_default(machine, "poi_direction", row.get("poi_direction"), "neutral"),
            "source": _enum_default(machine, "poi_source", row.get("poi_source"), "none"),
            "validity": bool(row.get("poi_validity", False)),
            "anchor_timeframe": "1h" if str(row.get("poi_type", "")) != "none" else None,
        },
        "setup_quality": _enum_default(machine, "setup_quality", row.get("setup_quality"), "no_setup"),
        "entry_state": _enum_default(machine, "entry_state", row.get("entry_state"), "wait"),
        "invalidation": {
            "state": _enum_default(machine, "invalidation_state", row.get("invalidation_state"), "unknown"),
            "reason": "Candidate inherited from bundle seed; confirm visually before promotion.",
        },
        "session_context": _enum_default(machine, "session_context", row.get("session_context"), "unknown"),
        "kill_zone_alignment": _enum_default(machine, "kill_zone_alignment", row.get("kill_zone_alignment"), "neutral"),
        "state_confidence": max(0.0, min(1.0, float(row.get("label_confidence") or 0.0))),
        "missing_evidence": [],
    }
    state["missing_evidence"] = _candidate_missing_evidence(row, state)
    if state["missing_evidence"]:
        state["state_confidence"] = round(min(state["state_confidence"], 0.55), 4)
    return state


def _selection_score(row: dict[str, Any], state: dict[str, Any]) -> tuple[float, list[str]]:
    score = 10.0
    reasons: list[str] = []
    if state["direction"] == "none":
        score += 30.0
        reasons.append("missing_direction")
    if state["htf_bias"] == "neutral":
        score += 25.0
        reasons.append("missing_htf_bias")
    if state["fractal_stage"] == "c4":
        score += 20.0
        reasons.append("c4_candidate")
    if state["setup_quality"] in {"good_setup", "bad_setup"}:
        score += 10.0
        reasons.append(f"setup_quality:{state['setup_quality']}")
    if str(row.get("review_outcome", "")).strip().lower() == "needs_review":
        score += 15.0
        reasons.append("source_needs_review")
    if state["poi"]["type"] == "none":
        score += 10.0
        reasons.append("missing_poi")
    if not row.get("detector_boxes_by_frame"):
        score += 5.0
        reasons.append("needs_yolo_detections")
    return round(score, 4), reasons or ["state_review_seed"]


def _timeframe_scope(row: dict[str, Any]) -> list[str]:
    scopes = ["daily", "h1", "m5", "multi_timeframe"]
    if str(row.get("source", "")).startswith("ttfm_screenshot_manifest"):
        scopes.append("fractal")
    return scopes


def _chart_paths(row: dict[str, Any]) -> dict[str, str]:
    return {
        "daily": str(row.get("htf_frame_path") or ""),
        "h1": str(row.get("itf_frame_path") or ""),
        "m5": str(row.get("ltf_frame_path") or ""),
    }


def _target_gap_summary(bundle_report: dict[str, Any]) -> dict[str, Any]:
    benchmark = bundle_report.get("benchmark", {}) if isinstance(bundle_report, dict) else {}
    targets = benchmark.get("targets", []) if isinstance(benchmark, dict) else []
    gap_targets = [
        target
        for target in targets
        if isinstance(target, dict) and not bool(target.get("meets_minimum", False))
    ]
    return {
        "target_count": int(benchmark.get("target_count") or len(targets) or 0),
        "satisfied_target_count": int(benchmark.get("satisfied_target_count") or 0),
        "unsatisfied_target_count": int(benchmark.get("unsatisfied_target_count") or len(gap_targets) or 0),
        "coverage_ratio": float(benchmark.get("coverage_ratio") or 0.0),
        "largest_gaps": sorted(
            gap_targets,
            key=lambda item: int(item.get("gap") or 0),
            reverse=True,
        )[:12],
    }


def _answer_template(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "example_id": item["example_id"],
        "review_outcome": "needs_review",
        "training_eligible": False,
        "state_labels": item["candidate_state"],
        "decision_label": {
            "verdict": "insufficient_evidence",
            "reasons": ["Seed answer is review-only until visually checked."],
            "blocking_conditions": item["candidate_state"]["missing_evidence"],
        },
        "reviewer_notes": [],
        "promotion_requirements": [
            "confirm_daily_h1_m5_direction",
            "confirm_fractal_stage_c1_c2_c3_c4",
            "confirm_poi_and_invalidation",
            "confirm_corpus_evidence_matches_chart",
            "confirm_decision_verdict_or_no_trade_reason",
        ],
    }


def build_state_review_packet(config: StateReviewConfig) -> tuple[dict[str, Any], dict[str, Any]]:
    root_dir = config.root_dir.resolve()
    machine = load_state_machine(resolve_path(root_dir, config.state_machine_path))
    bundle_report = read_json(resolve_path(root_dir, config.bundle_report_path), {})
    corpus_chunks = _load_corpus_chunks(root_dir, config.corpus_chunks_path)

    items: list[dict[str, Any]] = []
    source_paths: list[str] = []
    seen_ids: set[str] = set()
    for raw_path in config.bundle_seed_paths:
        seed_path = resolve_path(root_dir, raw_path)
        rows = read_jsonl(seed_path)
        if rows:
            source_paths.append(relative_or_absolute(seed_path, root_dir))
        for row in rows:
            example_id = str(row.get("bundle_id") or "").strip()
            if not example_id or example_id in seen_ids:
                continue
            seen_ids.add(example_id)
            state = _candidate_state_from_bundle(row, machine)
            priority_score, selection_reasons = _selection_score(row, state)
            corpus_evidence = _corpus_evidence(row, state, corpus_chunks)
            item = {
                "example_id": example_id,
                "source": str(row.get("source") or ""),
                "source_path": str(row.get("source_path") or relative_or_absolute(seed_path, root_dir)),
                "source_pointer": str(row.get("source_pointer") or ""),
                "priority_score": priority_score,
                "selection_reasons": selection_reasons,
                "timeframe_scope": _timeframe_scope(row),
                "chart_paths": _chart_paths(row),
                "corpus_evidence": corpus_evidence,
                "candidate_state": state,
                "candidate_decision": _candidate_decision(state),
                "review_fields_required": _review_fields_from_missing(state["missing_evidence"]),
                "review_outcome": "needs_review",
                "training_eligible": False,
            }
            items.append(item)
    corpus_path = resolve_path(root_dir, config.corpus_chunks_path)
    if corpus_chunks and corpus_path.exists():
        source_paths.append(relative_or_absolute(corpus_path, root_dir))
    source_paths = list(dict.fromkeys(source_paths))

    items = sorted(
        items,
        key=lambda item: (-float(item["priority_score"]), str(item["example_id"])),
    )[: max(0, config.limit)]
    missing_counts = Counter(
        missing
        for item in items
        for missing in item["candidate_state"]["missing_evidence"]
    )
    packet = {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_paths": source_paths,
        "state_machine_version": machine.version,
        "review_policy": {
            "candidate_only": True,
            "training_eligible_default": False,
            "promotion_requires_visual_review": True,
        },
        "target_gap_summary": _target_gap_summary(bundle_report),
        "selection_summary": {
            "candidate_count": len(items),
            "corpus_evidence_item_count": sum(1 for item in items if item["corpus_evidence"]),
            "missing_evidence_counts": dict(sorted(missing_counts.items())),
        },
        "items": items,
    }
    answers = {
        "schema_version": "1.0.0",
        "generated_at": packet["generated_at"],
        "source_packet_path": relative_or_absolute(resolve_path(root_dir, config.output_packet_path), root_dir),
        "review_policy": packet["review_policy"],
        "items": [_answer_template(item) for item in items],
    }
    return packet, answers


def write_outputs(config: StateReviewConfig, packet: dict[str, Any], answers: dict[str, Any]) -> None:
    packet_path = resolve_path(config.root_dir, config.output_packet_path)
    answers_path = resolve_path(config.root_dir, config.output_answers_path)
    packet_path.parent.mkdir(parents=True, exist_ok=True)
    answers_path.parent.mkdir(parents=True, exist_ok=True)
    packet_path.write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")
    answers_path.write_text(json.dumps(answers, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root-dir", type=Path, default=Path("."))
    parser.add_argument("--bundle-seed", type=Path, action="append", dest="bundle_seeds")
    parser.add_argument("--bundle-report", type=Path, default=DEFAULT_BUNDLE_REPORT_PATH)
    parser.add_argument("--corpus-chunks", type=Path, default=DEFAULT_CORPUS_CHUNKS_PATH)
    parser.add_argument("--state-machine", type=Path, default=DEFAULT_STATE_SPEC_PATH)
    parser.add_argument("--output-packet", type=Path, default=DEFAULT_OUTPUT_PACKET_PATH)
    parser.add_argument("--output-answers", type=Path, default=DEFAULT_OUTPUT_ANSWERS_PATH)
    parser.add_argument("--limit", type=int, default=80)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = StateReviewConfig(
        root_dir=args.root_dir,
        bundle_seed_paths=tuple(args.bundle_seeds or DEFAULT_BUNDLE_SEED_PATHS),
        bundle_report_path=args.bundle_report,
        corpus_chunks_path=args.corpus_chunks,
        state_machine_path=args.state_machine,
        output_packet_path=args.output_packet,
        output_answers_path=args.output_answers,
        limit=args.limit,
    )
    packet, answers = build_state_review_packet(config)
    write_outputs(config, packet, answers)
    print(
        json.dumps(
            {
                "packet_path": str(resolve_path(config.root_dir, config.output_packet_path)),
                "answers_path": str(resolve_path(config.root_dir, config.output_answers_path)),
                "candidate_count": len(packet["items"]),
                "missing_evidence_counts": packet["selection_summary"]["missing_evidence_counts"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
