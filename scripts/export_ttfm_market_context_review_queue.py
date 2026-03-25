from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from export_ttfm_teacher_visual_dataset import DEFAULT_DATASET_OUTPUT as DEFAULT_DATASET_PATH


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "results" / "ttfm_market_context_review_queue.json"


def load_teacher_visual_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped:
            rows.append(json.loads(stripped))
    return rows


def checkpoint_sort_key(item: dict) -> tuple[str, str]:
    return (
        str(item.get("timeframe_role", "")).strip(),
        str(item.get("checkpoint", "")).strip(),
    )


def normalize_string_list(values: object) -> list[str]:
    if values is None:
        return []
    if isinstance(values, list):
        return [str(value).strip() for value in values if str(value).strip()]
    if isinstance(values, str):
        cleaned = values.strip()
        return [cleaned] if cleaned else []
    return []


def classify_source_image_kind(case_rows: list[dict]) -> str:
    notes = " ".join(
        note.lower()
        for row in case_rows
        for note in normalize_string_list(row.get("annotation_notes"))
    )
    if "source article image" in notes:
        return "source_article_image"
    return "unknown"


def determine_recommended_action(alignment_status: str, source_image_kind: str) -> str:
    if alignment_status == "market_context_only" and source_image_kind == "source_article_image":
        return "find_alternate_chart_evidence"
    if alignment_status == "market_context_only":
        return "confirm_anchor_timestamp"
    if alignment_status == "unmapped":
        return "identify_symbol_and_anchor_timestamp"
    return "review_existing_alignment"


def build_override_template(case_ref: str, market_context: dict, *, source_image_kind: str) -> dict:
    notes = ""
    if source_image_kind == "source_article_image":
        notes = (
            "Source is still an article image; attach alternate chart evidence before "
            "setting anchor_timestamp."
        )
    return {
        "case_ref": case_ref,
        "symbol": market_context.get("symbol"),
        "anchor_timestamp": market_context.get("anchor_timestamp"),
        "window_minutes_before": 180,
        "window_minutes_after": 240,
        "mapping_provenance": "case_manual",
        "notes": notes,
    }


def build_market_context_review_queue(rows: list[dict]) -> dict:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        case_ref = str(row.get("case_ref", "")).strip()
        if case_ref:
            grouped[case_ref].append(row)

    items: list[dict] = []
    alignment_status_counts = Counter()
    recommended_action_counts = Counter()
    source_image_kind_counts = Counter()

    for case_ref in sorted(grouped):
        case_rows = sorted(grouped[case_ref], key=checkpoint_sort_key)
        seed = case_rows[0]
        market_context = seed.get("market_context", {})
        alignment_status = str(market_context.get("alignment_status", "unmapped")).strip() or "unmapped"
        source_image_kind = classify_source_image_kind(case_rows)
        recommended_action = determine_recommended_action(alignment_status, source_image_kind)

        checkpoint_samples = [
            {
                "checkpoint": row.get("checkpoint"),
                "timeframe": row.get("timeframe"),
                "timeframe_role": row.get("timeframe_role"),
                "active_labels": row.get("active_labels", []),
                "screenshot_path": row.get("screenshot_path"),
                "annotation_notes": row.get("annotation_notes", []),
            }
            for row in case_rows
        ]

        evidence_refs: list[str] = []
        for row in case_rows:
            for ref in row.get("evidence_refs", []):
                normalized = str(ref).strip()
                if normalized and normalized not in evidence_refs:
                    evidence_refs.append(normalized)

        item = {
            "case_ref": case_ref,
            "topic": seed.get("topic"),
            "trade_models": seed.get("trade_models", []),
            "relation_types": seed.get("relation_types", []),
            "source_url": seed.get("source_url"),
            "alignment_status": alignment_status,
            "mapping_provenance": market_context.get("mapping_provenance"),
            "recommended_action": recommended_action,
            "source_image_kind": source_image_kind,
            "symbol_suggestion": market_context.get("symbol"),
            "source_chart_symbol": market_context.get("source_chart_symbol"),
            "bars_path_suggestion": market_context.get("bars_path"),
            "anchor_timestamp": market_context.get("anchor_timestamp"),
            "market_context_notes": market_context.get("notes"),
            "confidence": market_context.get("confidence"),
            "checkpoint_samples": checkpoint_samples,
            "evidence_refs": evidence_refs,
            "override_template": build_override_template(
                case_ref,
                market_context,
                source_image_kind=source_image_kind,
            ),
        }
        items.append(item)
        alignment_status_counts[alignment_status] += 1
        recommended_action_counts[recommended_action] += 1
        source_image_kind_counts[source_image_kind] += 1

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "case_count": len(items),
            "alignment_status_counts": dict(sorted(alignment_status_counts.items())),
            "recommended_action_counts": dict(sorted(recommended_action_counts.items())),
            "source_image_kind_counts": dict(sorted(source_image_kind_counts.items())),
        },
        "items": items,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export a case-level review queue for filling teacher market-context overrides."
    )
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET_PATH))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    rows = load_teacher_visual_rows(Path(args.dataset))
    queue = build_market_context_review_queue(rows)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(queue, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output_path),
                "case_count": queue["summary"]["case_count"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
