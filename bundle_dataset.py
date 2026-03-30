from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable

from fractal_state import DEFAULT_STATE_SPEC_PATH, FractalStateMachine, load_state_machine


DEFAULT_BENCHMARK_TARGETS_PATH = Path("data") / "bundle_benchmark_targets.json"
DEFAULT_OUTPUT_PATH = Path("results") / "phase2_bundle_dataset.jsonl"
DEFAULT_GOLD_SEED_OUTPUT_PATH = Path("results") / "phase2_bundle_gold_seed.jsonl"

FRAME_PATH_KEYS = (
    "frame_path",
    "image_path",
    "screenshot_path",
    "chart_path",
    "htf_frame_path",
    "itf_frame_path",
    "ltf_frame_path",
)
TEXT_JOINER = " | "
STAGE_PATTERN = re.compile(r"\bc([1-4])\b", re.IGNORECASE)
IMAGE_PATH_PATTERN = re.compile(
    r"(?i)(?:[A-Za-z]:[\\/]|\.{0,2}[\\/]|tmp[\\/]|results[\\/]|artifacts[\\/])[^\"\n\r]+?\.(?:png|jpe?g|webp)"
)
CASE_CHECKPOINT_TO_STAGE = {
    "context": "c1",
    "sweep": "c1",
    "closure": "c2",
    "confirmation": "c3",
    "outcome": "c4",
}
STAGE_FRAME_PREFS = {
    "c1": ("context", "context", "sweep"),
    "c2": ("context", "sweep", "closure"),
    "c3": ("context", "closure", "confirmation"),
    "c4": ("context", "confirmation", "outcome"),
}


@dataclass
class BundleRecord:
    bundle_id: str
    source: str
    source_path: str
    source_pointer: str
    path_family: str
    continuation_vs_reversal: str
    direction: str
    fractal_stage: str
    htf_timeframe: str
    itf_timeframe: str
    ltf_timeframe: str
    htf_frame_path: str
    itf_frame_path: str
    ltf_frame_path: str
    htf_bias: str
    poi_type: str
    poi_direction: str
    poi_source: str
    poi_validity: bool
    setup_quality: str
    entry_state: str
    invalidation_state: str
    session_context: str
    kill_zone_alignment: str
    detector_boxes_by_frame: dict[str, list[dict[str, Any]]]
    cue_summary: str
    review_outcome: str
    provenance: list[str]
    label_confidence: float


def default_source_paths(root_dir: str | Path | None = None) -> tuple[Path, ...]:
    root = Path(root_dir) if root_dir is not None else Path(".")
    return (
        root / "data" / "trader_annotation_cases.json",
        root / "data" / "topic_model_graph.json",
        root / "data" / "tradingview_pine_validation.json",
        root / "results" / "indicator_specs" / "continuation_entry_model.json",
    )


def _flatten_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    if isinstance(value, dict):
        items: list[str] = []
        for child in value.values():
            items.extend(_flatten_strings(child))
        return items
    if isinstance(value, list):
        items: list[str] = []
        for child in value:
            items.extend(_flatten_strings(child))
        return items
    return []


def _extract_frame_paths(record: dict[str, Any]) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for key, value in record.items():
        key_lower = key.lower()
        if any(token in key_lower for token in FRAME_PATH_KEYS):
            if isinstance(value, str) and value.strip():
                normalized = value.strip()
                if normalized not in seen:
                    seen.add(normalized)
                    found.append(normalized)
            elif isinstance(value, list):
                for item in value:
                    if not isinstance(item, str) or not item.strip():
                        continue
                    normalized = item.strip()
                    if normalized in seen:
                        continue
                    seen.add(normalized)
                    found.append(normalized)
    for text in _flatten_strings(record):
        for match in IMAGE_PATH_PATTERN.finditer(text):
            candidate = match.group(0).strip().rstrip(".,);]")
            if candidate.lower().startswith(("http://", "https://")):
                continue
            if candidate in seen:
                continue
            seen.add(candidate)
            found.append(candidate)
    return found


def _iter_candidate_records(value: Any, source: str, pointer: str = "$") -> Iterable[tuple[str, dict[str, Any]]]:
    if isinstance(value, dict):
        if value and any(isinstance(child, (str, int, float, bool)) for child in value.values()):
            yield pointer, value
        for key, child in value.items():
            yield from _iter_candidate_records(child, source, f"{pointer}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _iter_candidate_records(child, source, f"{pointer}[{index}]")


def _contains_any(text: str, phrases: Iterable[str]) -> bool:
    return any(phrase in text for phrase in phrases)


def _derive_path_family(text: str, machine: FractalStateMachine) -> tuple[str, float]:
    reversal_hits = sum(
        1
        for phrase in (
            "reversal",
            "reclaim",
            "swept",
            "sweep high",
            "sweep low",
            "return through",
        )
        if phrase in text
    )
    continuation_hits = sum(
        1
        for phrase in (
            "continuation",
            "trend continuation",
            "directional thesis",
            "objective open",
            "follow-through",
        )
        if phrase in text
    )
    if reversal_hits > continuation_hits and machine.supports_path_family("reversal"):
        return "reversal", min(1.0, 0.45 + 0.1 * reversal_hits)
    if machine.supports_path_family("continuation"):
        base = 0.45 + 0.1 * continuation_hits
        return "continuation", min(1.0, base if continuation_hits else 0.35)
    return machine.path_families[0], 0.35


def _derive_stage(text: str, machine: FractalStateMachine) -> tuple[str, float]:
    match = STAGE_PATTERN.search(text)
    if match:
        stage = f"c{match.group(1)}".lower()
        if machine.supports_stage(stage):
            return stage, 0.8

    if _contains_any(text, ("entry-ready", "entry ready", "entry model")):
        return "c4", 0.65
    if _contains_any(text, ("confirmation", "cisd", "closure")):
        return "c3", 0.55
    if _contains_any(text, ("poi", "reaction zone", "equilibrium", "protected swing")):
        return "c2", 0.5
    if _contains_any(text, ("bias", "directional thesis", "objective open", "sweep")):
        return "c1", 0.45
    return "none", 0.4


def _derive_direction(text: str) -> tuple[str, float]:
    bullish_hits = sum(1 for token in ("bullish", "long", "buy") if token in text)
    bearish_hits = sum(1 for token in ("bearish", "short", "sell") if token in text)
    if bullish_hits > bearish_hits:
        return "bullish", min(1.0, 0.45 + 0.1 * bullish_hits)
    if bearish_hits > bullish_hits:
        return "bearish", min(1.0, 0.45 + 0.1 * bearish_hits)
    return "none", 0.35


def _derive_poi(text: str, direction: str, machine: FractalStateMachine) -> tuple[str, str, str, float]:
    if "equilibrium" in text:
        return "equilibrium_zone", "neutral", "rule_derived", 0.7
    if "protected swing" in text:
        poi_direction = direction if direction != "none" else "neutral"
        return "protected_swing_zone", poi_direction, "rule_derived", 0.75
    if _contains_any(text, ("liquidity target", "liquidity sweep", "sweep high", "sweep low")):
        poi_direction = direction if direction != "none" else "neutral"
        return "liquidity_target_zone", poi_direction, "rule_derived", 0.7
    if _contains_any(text, ("reaction zone", "order block", "breaker", "poi")):
        poi_direction = direction if direction != "none" else "neutral"
        return "reaction_zone", poi_direction, "rule_derived", 0.65
    return "none", "neutral", "none", 0.35


def _derive_setup_quality(text: str) -> tuple[str, float]:
    if _contains_any(text, ("no setup", "invalid chop", "no actionable")):
        return "no_setup", 0.85
    if _contains_any(text, ("bad setup", "late", "misaligned", "invalid", "degraded")):
        return "bad_setup", 0.75
    if _contains_any(text, ("good setup", "high probability", "entry-ready", "entry ready")):
        return "good_setup", 0.8
    return "bad_setup", 0.45


def _derive_invalidation_state(text: str) -> tuple[str, float]:
    if _contains_any(text, ("invalidation broken", "broke invalidation", "invalidated")):
        return "broken", 0.8
    if "at risk" in text:
        return "at_risk", 0.65
    if "invalidation" in text:
        return "intact", 0.55
    return "unknown", 0.35


def _derive_session_context(text: str) -> tuple[str, str]:
    if "london" in text:
        return "london", "aligned" if "aligned" in text else "neutral"
    if _contains_any(text, ("new york", "newyork", "ny session")):
        return "new_york", "aligned" if "aligned" in text else "neutral"
    if "off session" in text:
        return "off_session", "misaligned"
    return "unknown", "neutral"


def _derive_entry_state(
    stage: str,
    setup_quality: str,
    direction: str,
    htf_bias: str,
    poi_type: str,
    invalidation_state: str,
    kill_zone_alignment: str,
) -> tuple[str, float]:
    if (
        stage == "c4"
        and setup_quality == "good_setup"
        and direction in {"bullish", "bearish"}
        and htf_bias == direction
        and poi_type != "none"
        and invalidation_state != "broken"
        and kill_zone_alignment != "misaligned"
    ):
        return ("long_ready" if direction == "bullish" else "short_ready"), 0.8
    return "wait", 0.55


def _bundle_review_outcome(confidence: float) -> str:
    if confidence >= 0.75:
        return "derived"
    return "needs_review"


def _build_bundle_id(source: str, pointer: str) -> str:
    pointer_hash = re.sub(r"[^a-zA-Z0-9]+", "-", pointer).strip("-").lower()
    return f"{source}-{pointer_hash}"[:120]


def _infer_path_family_from_case(case_payload: dict[str, Any]) -> str:
    flattened = TEXT_JOINER.join(_flatten_strings(case_payload)).lower()
    trade_models = {
        str(item.get("trade_model", "")).strip().lower()
        for item in case_payload.get("trade_model_links", [])
        if isinstance(item, dict)
    }
    if "reversal_sequence_model" in trade_models or "reversal" in flattened:
        return "reversal"
    return "continuation"


def _infer_directional_context(case_payload: dict[str, Any]) -> tuple[str, str]:
    flattened = TEXT_JOINER.join(_flatten_strings(case_payload)).lower()
    direction, _ = _derive_direction(flattened)
    if direction == "none":
        htf_bias = "neutral"
    else:
        htf_bias = direction
    return direction, htf_bias


def _infer_case_poi(flattened_text: str, direction: str) -> tuple[str, str, str]:
    poi_type, poi_direction, poi_source, _ = _derive_poi(flattened_text, direction, "unused")
    if poi_type == "none":
        if any(token in flattened_text for token in ("order block", "breaker", "point of interest", "poi")):
            return "reaction_zone", poi_direction if poi_direction != "neutral" else "neutral", "rule_derived"
        if "equilibrium" in flattened_text:
            return "equilibrium_zone", "neutral", "rule_derived"
        if "protected swing" in flattened_text:
            return "protected_swing_zone", "neutral", "rule_derived"
    return poi_type, poi_direction, poi_source


def _group_attachments_by_case(payload: dict[str, Any]) -> dict[str, dict[str, dict[str, Any]]]:
    grouped: dict[str, dict[str, dict[str, Any]]] = {}
    for attachment in payload.get("attachments", []):
        if not isinstance(attachment, dict):
            continue
        case_ref = str(attachment.get("case_ref", "")).strip()
        checkpoint = str(attachment.get("checkpoint", "")).strip().lower()
        if not case_ref or not checkpoint:
            continue
        grouped.setdefault(case_ref, {})[checkpoint] = attachment
    return grouped


def _resolve_checkpoint_attachment(
    checkpoint_map: dict[str, dict[str, Any]],
    desired_checkpoint: str,
) -> dict[str, Any] | None:
    if desired_checkpoint in checkpoint_map:
        return checkpoint_map[desired_checkpoint]
    fallbacks = {
        "context": ("sweep", "closure", "confirmation", "outcome"),
        "sweep": ("context", "closure", "confirmation", "outcome"),
        "closure": ("confirmation", "sweep", "outcome", "context"),
        "confirmation": ("closure", "outcome", "sweep", "context"),
        "outcome": ("confirmation", "closure", "sweep", "context"),
    }
    for fallback in fallbacks.get(desired_checkpoint, ()):
        if fallback in checkpoint_map:
            return checkpoint_map[fallback]
    return None


def _attachment_path(attachment: dict[str, Any]) -> str:
    return str(attachment.get("screenshot_path", "")).strip()


def _build_case_bundle_record(
    *,
    case_payload: dict[str, Any],
    checkpoint_map: dict[str, dict[str, Any]],
    stage: str,
    state_machine: FractalStateMachine,
    screenshot_manifest_path: Path,
) -> BundleRecord | None:
    htf_key, itf_key, ltf_key = STAGE_FRAME_PREFS[stage]
    htf_attachment = _resolve_checkpoint_attachment(checkpoint_map, htf_key)
    itf_attachment = _resolve_checkpoint_attachment(checkpoint_map, itf_key)
    ltf_attachment = _resolve_checkpoint_attachment(checkpoint_map, ltf_key)
    if htf_attachment is None or itf_attachment is None or ltf_attachment is None:
        return None

    case_ref = str(case_payload.get("case_ref", "")).strip()
    flattened = TEXT_JOINER.join(_flatten_strings(case_payload)).lower()
    path_family = _infer_path_family_from_case(case_payload)
    if not state_machine.supports_path_family(path_family):
        return None

    direction, htf_bias = _infer_directional_context(case_payload)
    poi_type, poi_direction, poi_source = _infer_case_poi(flattened, direction)
    outcome_decision = str(case_payload.get("outcome", {}).get("decision", "")).strip().lower()
    session_context, kill_zone_alignment = _derive_session_context(flattened)
    setup_quality = "good_setup" if outcome_decision == "trade" else "bad_setup"
    invalidation_state = "intact" if outcome_decision == "trade" and stage in {"c3", "c4"} else ("at_risk" if outcome_decision == "no_trade" else "unknown")
    entry_state, _ = _derive_entry_state(
        stage,
        setup_quality,
        direction,
        htf_bias,
        poi_type,
        invalidation_state,
        kill_zone_alignment,
    )
    if outcome_decision == "no_trade":
        entry_state = "wait"

    checkpoint_for_stage = next(
        (checkpoint for checkpoint, mapped_stage in CASE_CHECKPOINT_TO_STAGE.items() if mapped_stage == stage and checkpoint in checkpoint_map),
        stage,
    )
    cue_summary = " | ".join(
        part
        for part in (
            case_ref,
            stage,
            path_family,
            str(case_payload.get("topic", "")).strip(),
            str(case_payload.get("notes", "")).strip(),
            str(case_payload.get("outcome", {}).get("reason", "")).strip(),
        )
        if part
    )
    return BundleRecord(
        bundle_id=f"{case_ref}::{stage}",
        source="ttfm_screenshot_manifest_seed",
        source_path=str(screenshot_manifest_path.resolve()),
        source_pointer=f"{case_ref}.{checkpoint_for_stage}",
        path_family=path_family,
        continuation_vs_reversal=path_family,
        direction=direction,
        fractal_stage=stage,
        htf_timeframe="daily_or_4h",
        itf_timeframe="1h",
        ltf_timeframe="5m",
        htf_frame_path=_attachment_path(htf_attachment),
        itf_frame_path=_attachment_path(itf_attachment),
        ltf_frame_path=_attachment_path(ltf_attachment),
        htf_bias=htf_bias,
        poi_type=poi_type,
        poi_direction=poi_direction,
        poi_source=poi_source,
        poi_validity=poi_type != "none" and invalidation_state != "broken",
        setup_quality=setup_quality,
        entry_state=entry_state,
        invalidation_state=invalidation_state,
        session_context=session_context,
        kill_zone_alignment=kill_zone_alignment,
        detector_boxes_by_frame={},
        cue_summary=cue_summary,
        review_outcome="seed_gold",
        provenance=[
            "ttfm_screenshot_manifest",
            "trader_annotation_cases",
            "case_heuristic_bundle_seed",
        ],
        label_confidence=0.9 if outcome_decision else 0.75,
    )


def derive_bundle_record(
    record: dict[str, Any],
    source: str,
    source_path: Path,
    pointer: str,
    machine: FractalStateMachine,
) -> BundleRecord | None:
    text = TEXT_JOINER.join(_flatten_strings(record)).lower()
    if not text:
        return None

    path_family, path_conf = _derive_path_family(text, machine)
    stage, stage_conf = _derive_stage(text, machine)
    direction, direction_conf = _derive_direction(text)
    htf_bias = direction if direction in {"bullish", "bearish"} else "neutral"
    poi_type, poi_direction, poi_source, poi_conf = _derive_poi(text, direction, machine)
    setup_quality, setup_conf = _derive_setup_quality(text)
    invalidation_state, invalidation_conf = _derive_invalidation_state(text)
    session_context, kill_zone_alignment = _derive_session_context(text)
    entry_state, entry_conf = _derive_entry_state(
        stage,
        setup_quality,
        direction,
        htf_bias,
        poi_type,
        invalidation_state,
        kill_zone_alignment,
    )

    frame_paths = _extract_frame_paths(record)
    if not frame_paths:
        return None

    htf_frame_path = frame_paths[0]
    itf_frame_path = frame_paths[1] if len(frame_paths) > 1 else htf_frame_path
    ltf_frame_path = frame_paths[2] if len(frame_paths) > 2 else itf_frame_path

    confidence = round(
        (
            path_conf
            + stage_conf
            + direction_conf
            + poi_conf
            + setup_conf
            + invalidation_conf
            + entry_conf
        )
        / 7.0,
        4,
    )
    return BundleRecord(
        bundle_id=_build_bundle_id(source, pointer),
        source=source,
        source_path=str(source_path),
        source_pointer=pointer,
        path_family=path_family,
        continuation_vs_reversal=path_family,
        direction=direction,
        fractal_stage=stage,
        htf_timeframe="daily_or_4h",
        itf_timeframe="1h",
        ltf_timeframe="5m",
        htf_frame_path=htf_frame_path,
        itf_frame_path=itf_frame_path,
        ltf_frame_path=ltf_frame_path,
        htf_bias=htf_bias,
        poi_type=poi_type,
        poi_direction=poi_direction,
        poi_source=poi_source,
        poi_validity=poi_type != "none" and invalidation_state != "broken",
        setup_quality=setup_quality,
        entry_state=entry_state,
        invalidation_state=invalidation_state,
        session_context=session_context,
        kill_zone_alignment=kill_zone_alignment,
        detector_boxes_by_frame={},
        cue_summary=text[:400],
        review_outcome=_bundle_review_outcome(confidence),
        provenance=[source, "rule_derived_bundle_builder"],
        label_confidence=confidence,
    )


def build_bundle_dataset(
    source_paths: Iterable[str | Path] | None = None,
    state_spec_path: str | Path = DEFAULT_STATE_SPEC_PATH,
) -> list[BundleRecord]:
    machine = load_state_machine(state_spec_path)
    effective_sources = tuple(source_paths) if source_paths is not None else default_source_paths()
    bundles: list[BundleRecord] = []
    seen_ids: set[str] = set()
    for raw_source_path in effective_sources:
        source_path = Path(raw_source_path)
        if not source_path.exists():
            continue
        source_name = source_path.stem
        payload = json.loads(source_path.read_text(encoding="utf-8"))
        for pointer, record in _iter_candidate_records(payload, source_name):
            bundle = derive_bundle_record(record, source_name, source_path, pointer, machine)
            if bundle is None or bundle.bundle_id in seen_ids:
                continue
            seen_ids.add(bundle.bundle_id)
            bundles.append(bundle)
    return bundles


def build_bundle_gold_seed(
    screenshot_manifest_path: str | Path,
    trader_annotation_cases_path: str | Path,
    state_spec_path: str | Path = DEFAULT_STATE_SPEC_PATH,
) -> list[BundleRecord]:
    manifest_path = Path(screenshot_manifest_path)
    cases_path = Path(trader_annotation_cases_path)
    if not manifest_path.exists() or not cases_path.exists():
        return []

    state_machine = load_state_machine(state_spec_path)
    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    cases_payload = json.loads(cases_path.read_text(encoding="utf-8"))
    attachments_by_case = _group_attachments_by_case(manifest_payload)
    cases = {
        str(case.get("case_ref", "")).strip(): case
        for case in cases_payload.get("cases", [])
        if isinstance(case, dict) and str(case.get("case_ref", "")).strip()
    }

    bundles: list[BundleRecord] = []
    for case_ref, checkpoint_map in attachments_by_case.items():
        case_payload = cases.get(case_ref)
        if case_payload is None:
            continue
        for stage in ("c1", "c2", "c3", "c4"):
            bundle = _build_case_bundle_record(
                case_payload=case_payload,
                checkpoint_map=checkpoint_map,
                stage=stage,
                state_machine=state_machine,
                screenshot_manifest_path=manifest_path,
            )
            if bundle is not None:
                bundles.append(bundle)
    return bundles


def summarize_bundle_dataset(
    bundles: Iterable[BundleRecord],
    benchmark_targets_path: str | Path = DEFAULT_BENCHMARK_TARGETS_PATH,
) -> dict[str, Any]:
    bundle_list = list(bundles)
    counts = {
        "path_family": {},
        "direction": {},
        "fractal_stage": {},
        "setup_quality": {},
        "review_outcome": {},
    }
    for bundle in bundle_list:
        for field_name, counter in counts.items():
            value = getattr(bundle, field_name)
            counter[value] = counter.get(value, 0) + 1

    benchmark_summary: dict[str, Any] = {
        "target_count": 0,
        "satisfied_target_count": 0,
        "unsatisfied_target_count": 0,
        "coverage_ratio": 0.0,
        "targets": [],
    }
    target_path = Path(benchmark_targets_path)
    if target_path.exists():
        payload = json.loads(target_path.read_text(encoding="utf-8"))
        targets = list(payload.get("targets", []))
        benchmark_rows: list[dict[str, Any]] = []
        satisfied = 0
        for target in targets:
            minimum_examples = int(target.get("minimum_examples", 0) or 0)
            filter_fields = {
                key: value
                for key, value in target.items()
                if key != "minimum_examples"
            }
            observed_count = sum(
                1
                for bundle in bundle_list
                if all(getattr(bundle, key, None) == value for key, value in filter_fields.items())
            )
            meets_minimum = observed_count >= minimum_examples
            if meets_minimum:
                satisfied += 1
            benchmark_rows.append(
                {
                    **target,
                    "observed_count": observed_count,
                    "gap": max(0, minimum_examples - observed_count),
                    "meets_minimum": meets_minimum,
                }
            )
        target_count = len(targets)
        benchmark_summary = {
            "target_count": target_count,
            "satisfied_target_count": satisfied,
            "unsatisfied_target_count": max(0, target_count - satisfied),
            "coverage_ratio": round((satisfied / target_count), 4) if target_count else 0.0,
            "targets": benchmark_rows,
        }

    return {
        "bundle_count": len(bundle_list),
        "counts": counts,
        "benchmark": benchmark_summary,
    }


def write_bundle_dataset(output_path: str | Path, bundles: Iterable[BundleRecord]) -> None:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for bundle in bundles:
            handle.write(json.dumps(asdict(bundle), sort_keys=True))
            handle.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the TTrades bundle dataset artifact.")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Path to the JSONL bundle dataset artifact.",
    )
    parser.add_argument(
        "--gold-seed-output",
        type=Path,
        default=None,
        help="Optional path to write the screenshot-backed gold bundle seed artifact.",
    )
    parser.add_argument(
        "--state-spec",
        type=Path,
        default=DEFAULT_STATE_SPEC_PATH,
        help="Path to the fractal state machine JSON spec.",
    )
    parser.add_argument(
        "--source",
        type=Path,
        action="append",
        default=[],
        help="Optional source artifact path. Can be passed multiple times.",
    )
    args = parser.parse_args()
    sources = args.source or list(default_source_paths())
    bundles = build_bundle_dataset(sources, args.state_spec)
    write_bundle_dataset(args.output, bundles)
    gold_seed_count = 0
    if args.gold_seed_output is not None:
        gold_seed = build_bundle_gold_seed(
            screenshot_manifest_path=Path("data") / "ttfm_screenshot_manifest.json",
            trader_annotation_cases_path=Path("data") / "trader_annotation_cases.json",
            state_spec_path=args.state_spec,
        )
        write_bundle_dataset(args.gold_seed_output, gold_seed)
        gold_seed_count = len(gold_seed)
    print(
        json.dumps(
            {
                "bundle_count": len(bundles),
                "gold_seed_count": gold_seed_count,
                "output_path": str(args.output),
                "state_spec_path": str(args.state_spec),
                "sources": [str(source) for source in sources],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
