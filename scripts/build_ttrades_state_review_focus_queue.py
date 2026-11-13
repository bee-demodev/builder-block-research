from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


DEFAULT_PACKET_PATH = Path("results") / "ttrades_state_review_packet_20260622.json"
DEFAULT_VISUAL_SUGGESTIONS_PATH = Path("results") / "ttrades_state_review_visual_suggestions_20260622.json"
DEFAULT_CAPTURE_QUALITY_PATH = Path("results") / "tradingview_capture_quality_report_20260622.json"
DEFAULT_OUTPUT_PATH = Path("results") / "ttrades_state_review_packet.review_first_20260622.json"


@dataclass(slots=True)
class FocusQueueConfig:
    root_dir: Path
    packet_path: Path = DEFAULT_PACKET_PATH
    visual_suggestions_path: Path = DEFAULT_VISUAL_SUGGESTIONS_PATH
    capture_quality_path: Path | None = DEFAULT_CAPTURE_QUALITY_PATH
    output_path: Path = DEFAULT_OUTPUT_PATH


def resolve(root_dir: Path, path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else root_dir / candidate


def relative_or_absolute(path: Path, root_dir: Path) -> str:
    try:
        return str(path.resolve().relative_to(root_dir.resolve()))
    except ValueError:
        return str(path)


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}")
    return payload


def review_order_from_suggestions(suggestions: dict[str, Any]) -> list[str]:
    explicit_order = suggestions.get("next_review_order")
    if isinstance(explicit_order, list) and explicit_order:
        return [str(value) for value in explicit_order if str(value).strip()]
    items = suggestions.get("items", [])
    if not isinstance(items, list):
        return []
    return [
        str(item.get("example_id"))
        for item in items
        if isinstance(item, dict) and item.get("visual_review_status") == "usable_candidate_review_only"
    ]


def suggestion_lookup(suggestions: dict[str, Any]) -> dict[str, dict[str, Any]]:
    items = suggestions.get("items", [])
    if not isinstance(items, list):
        return {}
    return {
        str(item.get("example_id")): item
        for item in items
        if isinstance(item, dict) and str(item.get("example_id", "")).strip()
    }


def capture_quality_lookup(capture_quality: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not capture_quality:
        return {}
    items = capture_quality.get("items", [])
    if not isinstance(items, list):
        return {}
    return {
        str(item.get("example_id")): item
        for item in items
        if isinstance(item, dict) and str(item.get("example_id", "")).strip()
    }


def capture_quality_review_ids(
    quality_by_id: dict[str, dict[str, Any]],
    source_items: dict[str, dict[str, Any]],
    suggestions_by_id: dict[str, dict[str, Any]],
    existing_review_ids: list[str],
) -> list[str]:
    existing = set(existing_review_ids)
    candidates: list[tuple[float, str]] = []
    for example_id, quality in quality_by_id.items():
        if example_id in existing or example_id not in source_items:
            continue
        if quality.get("recommended_action") != "review_state_labels":
            continue
        suggestion = suggestions_by_id.get(example_id, {})
        visual_status = str(suggestion.get("visual_review_status") or "")
        if visual_status.startswith("skip"):
            continue
        candidates.append((float(quality.get("priority_score") or 0.0), example_id))
    return [example_id for _priority, example_id in sorted(candidates, key=lambda item: (-item[0], item[1]))]


def missing_evidence_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for item in items:
        state = item.get("candidate_state", {}) if isinstance(item.get("candidate_state"), dict) else {}
        for value in state.get("missing_evidence", []):
            counts[str(value)] += 1
    return dict(sorted(counts.items()))


def build_focus_queue(
    packet: dict[str, Any],
    visual_suggestions: dict[str, Any],
    *,
    packet_path: Path,
    visual_suggestions_path: Path,
    root_dir: Path,
    capture_quality: dict[str, Any] | None = None,
    capture_quality_path: Path | None = None,
) -> dict[str, Any]:
    source_items = {
        str(item.get("example_id")): item
        for item in packet.get("items", [])
        if isinstance(item, dict) and str(item.get("example_id", "")).strip()
    }
    suggestions_by_id = suggestion_lookup(visual_suggestions)
    quality_by_id = capture_quality_lookup(capture_quality)
    review_ids = review_order_from_suggestions(visual_suggestions)
    quality_review_ids = capture_quality_review_ids(quality_by_id, source_items, suggestions_by_id, review_ids)
    review_ids = [*review_ids, *quality_review_ids]
    missing_ids = [example_id for example_id in review_ids if example_id not in source_items]
    if missing_ids:
        raise ValueError(f"Review ids missing from source packet: {', '.join(missing_ids)}")

    items: list[dict[str, Any]] = []
    excluded_for_capture_quality: list[dict[str, Any]] = []
    for example_id in review_ids:
        quality = quality_by_id.get(example_id)
        if quality and quality.get("recommended_action") != "review_state_labels":
            excluded_for_capture_quality.append(
                {
                    "example_id": example_id,
                    "recommended_action": str(quality.get("recommended_action") or ""),
                    "quality_flags": [str(flag) for flag in quality.get("quality_flags", [])],
                }
            )
            continue
        source_item = dict(source_items[example_id])
        suggestion = suggestions_by_id.get(example_id, {})
        has_visual_suggestion = bool(suggestion)
        visual_status = str(
            suggestion.get("visual_review_status")
            or ("capture_quality_passed_no_visual_suggestion" if example_id in quality_review_ids else "visual_review_first")
        )
        added_reasons = [
            *[str(value) for value in source_item.get("selection_reasons", [])],
            "layout_hash_reviewable",
        ]
        if example_id in quality_review_ids:
            added_reasons.extend(["capture_quality_reviewable", "fresh_live_capture_quality_passed"])
        else:
            added_reasons.append("codex_visual_review_first")
        added_reasons.append(visual_status)
        source_item["selection_reasons"] = list(
            dict.fromkeys(added_reasons)
        )
        source_item["visual_suggestion_ref"] = {
            "source": relative_or_absolute(visual_suggestions_path, root_dir) if has_visual_suggestion else "",
            "visual_review_status": visual_status,
            "training_eligible": False,
            "recommended_next_action": str(
                suggestion.get("recommended_next_action")
                or ("Fresh capture quality passed; review manually before promotion." if example_id in quality_review_ids else "")
            ),
            "promotion_blockers": [
                str(value)
                for value in suggestion.get("promotion_blockers", [])
                if str(value).strip()
            ],
        }
        if quality:
            source_item["capture_quality_ref"] = {
                "source": relative_or_absolute(capture_quality_path, root_dir) if capture_quality_path else "",
                "recommended_action": str(quality.get("recommended_action") or ""),
                "quality_flags": [str(flag) for flag in quality.get("quality_flags", [])],
            }
        source_item["training_eligible"] = False
        items.append(source_item)

    focused = {
        "mode": "ttrades_state_review_first_queue",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_packet": relative_or_absolute(packet_path, root_dir),
        "source_visual_suggestions": relative_or_absolute(visual_suggestions_path, root_dir),
        "source_capture_quality": relative_or_absolute(capture_quality_path, root_dir) if capture_quality_path and capture_quality else "",
        "review_rule": (
            "Focused human review queue only. Rows remain non-trainable until manually "
            "promoted in the canonical answer file."
        ),
        "selection_summary": {
            "candidate_count": len(items),
            "source_candidate_count": len(source_items),
            "visual_review_first_count": len(items) - len(quality_review_ids),
            "capture_quality_reviewable_count": len(quality_review_ids),
            "training_eligible_count": 0,
            "excluded_for_capture_quality_count": len(excluded_for_capture_quality),
            "missing_evidence_counts": missing_evidence_counts(items),
            "corpus_evidence_item_count": sum(1 for item in items if item.get("corpus_evidence")),
            "corpus_evidence_total_rows": sum(len(item.get("corpus_evidence", [])) for item in items),
        },
        "excluded_for_capture_quality": excluded_for_capture_quality,
        "items": items,
    }
    return focused


def write_focus_queue(
    config: FocusQueueConfig,
    packet: dict[str, Any],
    visual_suggestions: dict[str, Any],
    capture_quality: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root_dir = config.root_dir.resolve()
    packet_path = resolve(root_dir, config.packet_path)
    visual_suggestions_path = resolve(root_dir, config.visual_suggestions_path)
    capture_quality_path = resolve(root_dir, config.capture_quality_path) if config.capture_quality_path else None
    output_path = resolve(root_dir, config.output_path)
    focused = build_focus_queue(
        packet,
        visual_suggestions,
        packet_path=packet_path,
        visual_suggestions_path=visual_suggestions_path,
        capture_quality=capture_quality,
        capture_quality_path=capture_quality_path,
        root_dir=root_dir,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(focused, indent=2) + "\n", encoding="utf-8")
    return focused


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a focused TTrades state-review queue from visual suggestions.")
    parser.add_argument("--root-dir", type=Path, default=Path("."))
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    parser.add_argument("--visual-suggestions", type=Path, default=DEFAULT_VISUAL_SUGGESTIONS_PATH)
    parser.add_argument("--capture-quality", type=Path, default=DEFAULT_CAPTURE_QUALITY_PATH)
    parser.add_argument("--no-capture-quality-filter", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root_dir = args.root_dir.resolve()
    packet_path = resolve(root_dir, args.packet)
    visual_suggestions_path = resolve(root_dir, args.visual_suggestions)
    capture_quality_path = None if args.no_capture_quality_filter else resolve(root_dir, args.capture_quality)
    capture_quality = None if capture_quality_path is None or not capture_quality_path.exists() else load_json(capture_quality_path)
    focused = write_focus_queue(
        FocusQueueConfig(
            root_dir=root_dir,
            packet_path=args.packet,
            visual_suggestions_path=args.visual_suggestions,
            capture_quality_path=None if args.no_capture_quality_filter else args.capture_quality,
            output_path=args.output,
        ),
        load_json(packet_path),
        load_json(visual_suggestions_path),
        capture_quality,
    )
    print(
        json.dumps(
            {
                "output_path": str(resolve(root_dir, args.output)),
                "candidate_count": focused["selection_summary"]["candidate_count"],
                "training_eligible_count": focused["selection_summary"]["training_eligible_count"],
                "excluded_for_capture_quality_count": focused["selection_summary"]["excluded_for_capture_quality_count"],
                "corpus_evidence_item_count": focused["selection_summary"]["corpus_evidence_item_count"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
