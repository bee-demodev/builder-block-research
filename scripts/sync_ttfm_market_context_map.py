from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE_PATH = ROOT / "results" / "ttfm_market_context_override_templates.json"
DEFAULT_TARGET_PATH = ROOT / "data" / "ttfm_market_context_map.json"
DEFAULT_NOTES = [
    "Populate case_overrides as teacher screenshots are matched to replayable market bars.",
    "Use anchor_timestamp only when the screenshot or source explicitly identifies the chart time.",
    "Until then, the teacher-visual dataset may rely on lower-confidence trade-model proxy mappings from TradingView validation.",
]


def load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_override(item: dict[str, Any]) -> dict[str, Any] | None:
    case_ref = str(item.get("case_ref", "")).strip()
    if not case_ref:
        return None

    normalized = {
        "case_ref": case_ref,
        "symbol": str(item.get("symbol", "")).strip().upper() or None,
        "anchor_timestamp": str(item.get("anchor_timestamp", "")).strip() or None,
        "window_minutes_before": item.get("window_minutes_before", 180),
        "window_minutes_after": item.get("window_minutes_after", 240),
        "mapping_provenance": str(item.get("mapping_provenance", "case_manual")).strip() or "case_manual",
        "notes": str(item.get("notes", "")).strip() or None,
    }

    if not normalized["symbol"] and not normalized["anchor_timestamp"] and not normalized["notes"]:
        return None
    return normalized


def merge_market_context_map(
    existing_map: dict[str, Any],
    source_overrides: list[dict[str, Any]],
) -> dict[str, Any]:
    merged_lookup: dict[str, dict[str, Any]] = {}
    for item in existing_map.get("case_overrides", []):
        normalized = normalize_override(item)
        if normalized:
            merged_lookup[normalized["case_ref"]] = normalized

    for item in source_overrides:
        normalized = normalize_override(item)
        if not normalized:
            continue
        existing = merged_lookup.get(normalized["case_ref"], {})
        merged_lookup[normalized["case_ref"]] = {
            "case_ref": normalized["case_ref"],
            "symbol": normalized["symbol"] or existing.get("symbol"),
            "anchor_timestamp": normalized["anchor_timestamp"] or existing.get("anchor_timestamp"),
            "window_minutes_before": normalized["window_minutes_before"]
            if normalized.get("window_minutes_before") is not None
            else existing.get("window_minutes_before", 180),
            "window_minutes_after": normalized["window_minutes_after"]
            if normalized.get("window_minutes_after") is not None
            else existing.get("window_minutes_after", 240),
            "mapping_provenance": normalized["mapping_provenance"] or existing.get("mapping_provenance", "case_manual"),
            "notes": normalized["notes"] or existing.get("notes"),
        }

    return {
        "notes": list(existing_map.get("notes") or DEFAULT_NOTES),
        "case_overrides": [
            merged_lookup[case_ref]
            for case_ref in sorted(merged_lookup)
        ],
    }


def write_market_context_map(payload: dict[str, Any], target_path: Path) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Merge reviewed TTFM market-context overrides into the canonical market context map."
    )
    parser.add_argument("--source", default=str(DEFAULT_SOURCE_PATH))
    parser.add_argument("--target", default=str(DEFAULT_TARGET_PATH))
    args = parser.parse_args()

    source_payload = load_json(Path(args.source), {"case_overrides": []})
    existing_map = load_json(Path(args.target), {"notes": DEFAULT_NOTES, "case_overrides": []})
    merged = merge_market_context_map(existing_map, source_payload.get("case_overrides", []))
    target_path = Path(args.target)
    write_market_context_map(merged, target_path)
    print(
        json.dumps(
            {
                "target": str(target_path),
                "case_override_count": len(merged.get("case_overrides", [])),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
