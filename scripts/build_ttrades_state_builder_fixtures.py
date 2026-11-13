from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fractal_state import DEFAULT_STATE_SPEC_PATH, FractalStateMachine, load_state_machine


DEFAULT_BUNDLE_SEED_PATH = Path("results") / "phase2_bundle_gold_seed.jsonl"
DEFAULT_OUTPUT_PATH = Path("results") / "ttrades_state_builder_fixtures.json"
REVIEWED_OUTCOMES = {"seed_gold", "accepted", "adjusted"}
STATE_FIELDS = (
    "path_family",
    "fractal_stage",
    "direction",
    "htf_bias",
    "poi_type",
    "poi_direction",
    "poi_source",
    "setup_quality",
    "entry_state",
    "invalidation_state",
    "session_context",
    "kill_zone_alignment",
)


def resolve(root_dir: Path, path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else root_dir / candidate


def relative_or_absolute(path: Path, root_dir: Path) -> str:
    try:
        return str(path.resolve().relative_to(root_dir.resolve()))
    except ValueError:
        return str(path)


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


def enum_value(machine: FractalStateMachine, enum_name: str, value: Any) -> str | None:
    candidate = str(value or "").strip()
    return candidate if candidate in machine.enums[enum_name] else None


def validated_labels(machine: FractalStateMachine, row: dict[str, Any]) -> dict[str, str] | None:
    labels: dict[str, str] = {}
    for field in STATE_FIELDS:
        value = enum_value(machine, field, row.get(field))
        if value is None:
            return None
        labels[field] = value
    return labels


def alignment_from_labels(labels: dict[str, str]) -> dict[str, Any]:
    direction = labels["direction"]
    htf_bias = labels["htf_bias"]
    aligned_direction = direction if direction in {"bullish", "bearish"} and htf_bias == direction else "none"
    return {
        "daily": aligned_direction,
        "h1": aligned_direction,
        "m5": aligned_direction,
        "is_aligned": aligned_direction != "none",
    }


def missing_evidence(labels: dict[str, str], row: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    alignment = alignment_from_labels(labels)
    if labels["direction"] == "none":
        missing.append("directional_bias_unlabeled")
    if labels["htf_bias"] == "neutral":
        missing.append("daily_or_htf_bias_unlabeled")
    if not alignment["is_aligned"]:
        missing.append("daily_h1_m5_alignment_unverified")
    if labels["poi_type"] == "none":
        missing.append("point_of_interest_unlabeled")
    if labels["invalidation_state"] == "unknown":
        missing.append("invalidation_unlabeled")
    if (
        labels["fractal_stage"] == "c4"
        and labels["setup_quality"] == "good_setup"
        and labels["entry_state"] == "wait"
    ):
        missing.append("c4_entry_readiness_unverified")
    if str(row.get("review_outcome", "")).strip().lower() not in REVIEWED_OUTCOMES:
        missing.append("source_not_reviewed")
    return list(dict.fromkeys(missing))


def expected_state(labels: dict[str, str], row: dict[str, Any]) -> dict[str, Any]:
    missing = missing_evidence(labels, row)
    confidence = max(0.0, min(1.0, float(row.get("label_confidence") or 0.0)))
    if missing:
        confidence = min(confidence, 0.55)
    return {
        "path_family": labels["path_family"],
        "direction": labels["direction"],
        "fractal_stage": labels["fractal_stage"],
        "htf_bias": labels["htf_bias"],
        "timeframe_alignment": alignment_from_labels(labels),
        "poi": {
            "type": labels["poi_type"],
            "direction": labels["poi_direction"],
            "source": labels["poi_source"],
            "validity": bool(row.get("poi_validity", False)),
            "anchor_timeframe": "1h" if labels["poi_type"] != "none" else None,
        },
        "setup_quality": labels["setup_quality"],
        "entry_state": labels["entry_state"],
        "invalidation": {
            "state": labels["invalidation_state"],
            "reason": "Reviewed fixture label from bundle seed.",
        },
        "session_context": labels["session_context"],
        "kill_zone_alignment": labels["kill_zone_alignment"],
        "state_confidence": round(confidence, 4),
        "missing_evidence": missing,
    }


def expected_decision(state: dict[str, Any]) -> dict[str, Any]:
    missing = list(state["missing_evidence"])
    if missing:
        return {
            "verdict": "insufficient_evidence",
            "reasons": ["Reviewed setup fixture still has missing state evidence."],
            "blocking_conditions": missing,
        }
    if state["setup_quality"] == "no_setup":
        return {
            "verdict": "no_trade",
            "reasons": ["Reviewed fixture is labeled as no setup."],
            "blocking_conditions": [],
        }
    if state["invalidation"]["state"] == "broken":
        return {
            "verdict": "no_trade",
            "reasons": ["Reviewed fixture has a broken invalidation state."],
            "blocking_conditions": ["invalidation_broken"],
        }

    entry_blocks = entry_rule_blocks(state)
    if state["entry_state"] == "long_ready":
        if entry_blocks:
            return {
                "verdict": "watch_only",
                "reasons": ["Long-ready label conflicts with deterministic entry constraints."],
                "blocking_conditions": entry_blocks,
            }
        return {
            "verdict": "valid_long_setup",
            "reasons": ["C4 bullish setup is aligned, reviewed, and entry-ready."],
            "blocking_conditions": [],
        }
    if state["entry_state"] == "short_ready":
        if entry_blocks:
            return {
                "verdict": "watch_only",
                "reasons": ["Short-ready label conflicts with deterministic entry constraints."],
                "blocking_conditions": entry_blocks,
            }
        return {
            "verdict": "valid_short_setup",
            "reasons": ["C4 bearish setup is aligned, reviewed, and entry-ready."],
            "blocking_conditions": [],
        }
    return {
        "verdict": "watch_only",
        "reasons": ["Reviewed fixture is not entry-ready."],
        "blocking_conditions": list(dict.fromkeys(["entry_state_is_wait", *entry_blocks])),
    }


def entry_rule_blocks(state: dict[str, Any]) -> list[str]:
    blocks: list[str] = []
    entry_state = state["entry_state"]
    expected_direction = {"long_ready": "bullish", "short_ready": "bearish"}.get(entry_state)
    if state["fractal_stage"] != "c4":
        blocks.append("fractal_stage_not_c4")
    if state["setup_quality"] != "good_setup":
        blocks.append("setup_quality_not_good_setup")
    if not state["timeframe_alignment"]["is_aligned"]:
        blocks.append("timeframes_not_aligned")
    if state["poi"]["type"] == "none" or not state["poi"]["validity"]:
        blocks.append("poi_not_valid")
    if state["invalidation"]["state"] != "intact":
        blocks.append("invalidation_not_intact")
    if state["kill_zone_alignment"] == "misaligned":
        blocks.append("kill_zone_misaligned")
    if expected_direction is not None:
        if state["direction"] != expected_direction:
            blocks.append(f"{entry_state}_direction_mismatch")
        if state["htf_bias"] != expected_direction:
            blocks.append(f"{entry_state}_htf_bias_mismatch")
    return blocks


def chart_paths_exist(root_dir: Path, row: dict[str, Any]) -> bool:
    return all(
        resolve(root_dir, str(row.get(field) or "")).exists()
        for field in ("htf_frame_path", "itf_frame_path", "ltf_frame_path")
    )


def fixture_from_row(
    *,
    root_dir: Path,
    row: dict[str, Any],
    labels: dict[str, str],
    index: int,
) -> dict[str, Any]:
    state = expected_state(labels, row)
    return {
        "fixture_id": f"state_fixture_{index:04d}",
        "bundle_id": str(row.get("bundle_id") or ""),
        "review_outcome": str(row.get("review_outcome") or ""),
        "source": str(row.get("source") or ""),
        "source_path": str(row.get("source_path") or ""),
        "source_pointer": str(row.get("source_pointer") or ""),
        "inputs": {
            "chart_paths": {
                "daily": str(row.get("htf_frame_path") or ""),
                "h1": str(row.get("itf_frame_path") or ""),
                "m5": str(row.get("ltf_frame_path") or ""),
            },
            "timeframes": {
                "daily": str(row.get("htf_timeframe") or ""),
                "h1": str(row.get("itf_timeframe") or ""),
                "m5": str(row.get("ltf_timeframe") or ""),
            },
            "detector_boxes_by_frame": row.get("detector_boxes_by_frame") or {},
            "cue_summary": str(row.get("cue_summary") or ""),
        },
        "expected_state": state,
        "expected_decision": expected_decision(state),
    }


def build_state_builder_fixtures(
    *,
    root_dir: Path,
    bundle_seed_path: Path,
    state_machine_path: Path = DEFAULT_STATE_SPEC_PATH,
    limit: int = 20,
) -> dict[str, Any]:
    root_dir = root_dir.resolve()
    seed_path = resolve(root_dir, bundle_seed_path)
    machine = load_state_machine(resolve(root_dir, state_machine_path))
    rows = read_jsonl(seed_path)
    fixtures: list[dict[str, Any]] = []
    skipped: Counter[str] = Counter()
    for row in rows:
        if len(fixtures) >= limit:
            break
        outcome = str(row.get("review_outcome", "")).strip().lower()
        if outcome not in REVIEWED_OUTCOMES:
            skipped["not_reviewed"] += 1
            continue
        labels = validated_labels(machine, row)
        if labels is None:
            skipped["invalid_state_labels"] += 1
            continue
        if not chart_paths_exist(root_dir, row):
            skipped["missing_chart_paths"] += 1
            continue
        fixtures.append(fixture_from_row(root_dir=root_dir, row=row, labels=labels, index=len(fixtures) + 1))

    missing_counts = Counter(
        missing
        for fixture in fixtures
        for missing in fixture["expected_state"]["missing_evidence"]
    )
    verdict_counts = Counter(fixture["expected_decision"]["verdict"] for fixture in fixtures)
    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "Deterministic state-builder fixtures from reviewed TTrades setup bundle rows.",
        "source_bundle_seed_path": relative_or_absolute(seed_path, root_dir),
        "state_machine_path": relative_or_absolute(resolve(root_dir, state_machine_path), root_dir),
        "state_machine_version": machine.version,
        "reviewed_outcomes": sorted(REVIEWED_OUTCOMES),
        "summary": {
            "requested_fixture_count": limit,
            "fixture_count": len(fixtures),
            "fixture_gate": "pass" if len(fixtures) >= limit else "blocked",
            "skipped_counts": dict(sorted(skipped.items())),
            "expected_decision_counts": dict(sorted(verdict_counts.items())),
            "missing_evidence_counts": dict(sorted(missing_counts.items())),
        },
        "fixtures": fixtures,
    }


def write_fixture_file(payload: dict[str, Any], *, root_dir: Path, output_path: Path) -> None:
    resolved = resolve(root_dir, output_path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build deterministic TTrades state-builder fixtures.")
    parser.add_argument("--root-dir", type=Path, default=Path("."))
    parser.add_argument("--bundle-seed", type=Path, default=DEFAULT_BUNDLE_SEED_PATH)
    parser.add_argument("--state-machine", type=Path, default=DEFAULT_STATE_SPEC_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--limit", type=int, default=20)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root_dir = args.root_dir.resolve()
    payload = build_state_builder_fixtures(
        root_dir=root_dir,
        bundle_seed_path=args.bundle_seed,
        state_machine_path=args.state_machine,
        limit=args.limit,
    )
    write_fixture_file(payload, root_dir=root_dir, output_path=args.output)
    print(
        "Built TTrades state-builder fixtures: "
        f"{relative_or_absolute(resolve(root_dir, args.output), root_dir)} "
        f"gate={payload['summary']['fixture_gate']} "
        f"fixtures={payload['summary']['fixture_count']}"
    )


if __name__ == "__main__":
    main()
