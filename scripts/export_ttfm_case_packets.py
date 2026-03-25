from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from export_model_training_surface import flatten_strings, load_trader_records


ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "research.db"
DEFAULT_OUTPUT = ROOT / "results" / "ttfm_case_packets.json"
DEFAULT_TAXONOMY_PATH = ROOT / "data" / "ttfm_component_taxonomy.json"
DEFAULT_SCREENSHOT_MANIFEST_PATH = ROOT / "data" / "ttfm_screenshot_manifest.json"
DEFAULT_ANCHOR_LABELS_PATH = ROOT / "data" / "ttfm_anchor_labels.json"

CHECKPOINT_ORDER = (
    ("context", "htf"),
    ("sweep", "etf"),
    ("closure", "ltf"),
    ("confirmation", "ltf"),
    ("outcome", "etf"),
)
CHECKPOINT_TIMEFRAME_KEYS = dict(CHECKPOINT_ORDER)
PROVENANCE_PRECEDENCE = ("anchor_manual", "model_corrected", "rule_derived")


def normalize_token(value: str) -> str:
    return " ".join(str(value).replace("_", " ").replace("-", " ").split()).lower()


def clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def average(values: Iterable[float]) -> float:
    values_list = list(values)
    if not values_list:
        return 0.0
    return sum(values_list) / len(values_list)


def load_component_taxonomy(path: Path = DEFAULT_TAXONOMY_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_optional_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def load_screenshot_manifest(path: Path = DEFAULT_SCREENSHOT_MANIFEST_PATH) -> dict:
    return load_optional_json(path, {"attachments": []})


def load_anchor_label_manifest(path: Path = DEFAULT_ANCHOR_LABELS_PATH) -> dict:
    return load_optional_json(path, {"labels": []})


def load_records_from_db(
    connection: sqlite3.Connection,
    *,
    profile_slug: str | None = None,
    topic: str | None = None,
) -> list[dict]:
    return load_trader_records(connection, profile_slug=profile_slug, topic=topic)


def build_record_blob(record: dict) -> str:
    text_parts = [
        record.get("topic"),
        record.get("case_ref"),
        record.get("notes"),
        record.get("timeframe"),
        *(item.get("trade_model") for item in record.get("annotation_trade_models", [])),
        *(item.get("relation_type") for item in record.get("annotation_trade_models", [])),
        *flatten_strings(record.get("chart_context")),
        *flatten_strings(record.get("annotation")),
        *flatten_strings(record.get("outcome")),
    ]
    return " ".join(normalize_token(part) for part in text_parts if part).strip()


def infer_timeframe_stack(chart_context: dict | None, fallback_timeframe: str | None) -> dict:
    chart_context = chart_context or {}
    scope = [str(value).strip() for value in chart_context.get("timeframe_scope", []) if str(value).strip()]
    fallback = str(fallback_timeframe).strip() if fallback_timeframe else ""

    if len(scope) >= 3:
        htf, etf, ltf = scope[0], scope[1], scope[2]
    elif len(scope) == 2:
        htf, ltf = scope[0], scope[1]
        etf = fallback or ltf
    elif len(scope) == 1:
        htf = scope[0]
        etf = fallback or scope[0]
        ltf = fallback or scope[0]
    else:
        htf = "higher"
        etf = fallback or "execution"
        ltf = fallback or "lower"

    ordered = [value for value in [htf, etf, ltf] if value]
    unique_labels = []
    for value in ordered:
        if value not in unique_labels:
            unique_labels.append(value)

    return {
        "htf": htf,
        "etf": etf,
        "ltf": ltf,
        "labels": unique_labels,
        "is_multi_timeframe": len(unique_labels) > 1,
    }


def infer_component_labels(record: dict, taxonomy: dict) -> list[dict]:
    record_blob = build_record_blob(record)
    matched_components: list[dict] = []
    for component in taxonomy.get("components", []):
        markers = [normalize_token(marker) for marker in component.get("markers", [])]
        if any(marker in record_blob for marker in markers):
            matched_components.append(component)
    return matched_components


def index_components_by_label(taxonomy: dict) -> dict[str, dict]:
    return {
        str(component["label"]): component
        for component in taxonomy.get("components", [])
        if str(component.get("label", "")).strip()
    }


def normalize_labels(labels: Iterable[str]) -> list[str]:
    return sorted({str(label).strip() for label in labels if str(label).strip()})


def normalize_string_list(values: object) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        cleaned = values.strip()
        return [cleaned] if cleaned else []
    if isinstance(values, list):
        output: list[str] = []
        for value in values:
            output.extend(normalize_string_list(value))
        return output
    return []


def index_screenshot_manifest(manifest: dict | None) -> dict[tuple[str, str], dict]:
    manifest = manifest or {"attachments": []}
    indexed: dict[tuple[str, str], dict] = {}
    for attachment in manifest.get("attachments", []):
        case_ref = str(attachment.get("case_ref", "")).strip()
        checkpoint = str(attachment.get("checkpoint", "")).strip()
        if not case_ref or not checkpoint:
            continue
        indexed[(case_ref, checkpoint)] = attachment
    return indexed


def index_anchor_label_manifest(manifest: dict | None) -> dict[tuple[str, str], dict[str, list[str]]]:
    manifest = manifest or {"labels": []}
    indexed: dict[tuple[str, str], dict[str, list[str]]] = {}
    for item in manifest.get("labels", []):
        case_ref = str(item.get("case_ref", "")).strip()
        checkpoint = str(item.get("checkpoint", "")).strip()
        provenance = str(item.get("provenance", "")).strip()
        if not case_ref or not checkpoint or provenance not in PROVENANCE_PRECEDENCE:
            continue
        indexed.setdefault((case_ref, checkpoint), {})[provenance] = normalize_labels(item.get("labels", []))
    return indexed


def select_active_labels(labels_by_provenance: dict[str, list[str]]) -> tuple[list[str], str]:
    for provenance in PROVENANCE_PRECEDENCE:
        labels = normalize_labels(labels_by_provenance.get(provenance, []))
        if labels:
            return labels, provenance
    return [], "unlabeled"


def build_checkpoint_evidence_refs(
    *,
    active_labels: list[str],
    components_by_label: dict[str, dict],
    draft_spec_keys: list[str],
    packet_topic: str | None,
    manifest_refs: list[str],
) -> list[str]:
    refs = list(manifest_refs)
    if packet_topic:
        refs.append(f"topic:{packet_topic}")
    for label in active_labels:
        component = components_by_label.get(label, {})
        for topic in component.get("supporting_topics", []):
            refs.append(f"topic:{topic}")
    for spec_key in draft_spec_keys:
        refs.append(f"draft_spec:{spec_key}")
    return normalize_string_list(refs)


def build_checkpoints(
    record: dict,
    timeframe_stack: dict,
    components: list[dict],
    taxonomy: dict,
    *,
    screenshot_manifest: dict | None = None,
    anchor_label_manifest: dict | None = None,
) -> list[dict]:
    component_by_checkpoint: dict[str, list[str]] = {}
    for component in components:
        for checkpoint in component.get("checkpoints", []):
            component_by_checkpoint.setdefault(str(checkpoint), []).append(component["label"])

    screenshot_lookup = index_screenshot_manifest(screenshot_manifest)
    anchor_lookup = index_anchor_label_manifest(anchor_label_manifest)
    components_by_label = index_components_by_label(taxonomy)
    draft_spec_keys = build_draft_spec_keys(record)
    case_ref = str(record.get("case_ref", "")).strip()
    packet_topic = str(record.get("topic", "")).strip()

    checkpoints: list[dict] = []
    for checkpoint_name, timeframe_key in CHECKPOINT_ORDER:
        rule_derived_labels = normalize_labels(component_by_checkpoint.get(checkpoint_name, []))
        labels_by_provenance: dict[str, list[str]] = {}
        if rule_derived_labels:
            labels_by_provenance["rule_derived"] = rule_derived_labels
        for provenance, labels in anchor_lookup.get((case_ref, checkpoint_name), {}).items():
            if labels:
                labels_by_provenance[provenance] = normalize_labels(labels)

        active_labels, active_label_provenance = select_active_labels(labels_by_provenance)
        attachment = screenshot_lookup.get((case_ref, checkpoint_name), {})
        screenshot_path = str(attachment.get("screenshot_path", "")).strip() or None
        evidence_refs = build_checkpoint_evidence_refs(
            active_labels=active_labels,
            components_by_label=components_by_label,
            draft_spec_keys=draft_spec_keys,
            packet_topic=packet_topic,
            manifest_refs=normalize_string_list(attachment.get("evidence_refs")),
        )
        checkpoints.append(
            {
                "checkpoint": checkpoint_name,
                "timeframe": timeframe_stack[timeframe_key],
                "timeframe_role": timeframe_key,
                "expected_component_labels": active_labels,
                "active_label_provenance": active_label_provenance,
                "labels_by_provenance": labels_by_provenance,
                "screenshot_required": True,
                "screenshot_status": "attached" if screenshot_path else "missing",
                "screenshot_path": screenshot_path,
                "annotation_notes": normalize_string_list(attachment.get("annotation_notes")),
                "zone_geometry": attachment.get("zone_geometry"),
                "evidence_refs": evidence_refs,
            }
        )
    return checkpoints


def infer_label_provenance(record: dict) -> str:
    return "rule_derived"


def build_draft_spec_keys(record: dict) -> list[str]:
    profile_slug = str(record.get("profile_slug", "")).strip()
    spec_keys: list[str] = []
    for link in record.get("annotation_trade_models", []):
        trade_model = str(link.get("trade_model", "")).strip()
        if trade_model and trade_model != "phases_of_price_framework":
            spec_keys.append(f"{profile_slug}__{trade_model}")
    return sorted(set(spec_keys))


def build_case_packet(
    record: dict,
    taxonomy: dict | None = None,
    *,
    screenshot_manifest: dict | None = None,
    anchor_label_manifest: dict | None = None,
) -> dict:
    taxonomy = taxonomy or load_component_taxonomy()
    components = infer_component_labels(record, taxonomy)
    timeframe_stack = infer_timeframe_stack(record.get("chart_context"), record.get("timeframe"))
    checkpoints = build_checkpoints(
        record,
        timeframe_stack,
        components,
        taxonomy,
        screenshot_manifest=screenshot_manifest,
        anchor_label_manifest=anchor_label_manifest,
    )
    trade_models = sorted(
        {
            str(link.get("trade_model", "")).strip()
            for link in record.get("annotation_trade_models", [])
            if str(link.get("trade_model", "")).strip()
        }
    )
    relation_types = sorted(
        {
            str(link.get("relation_type", "")).strip()
            for link in record.get("annotation_trade_models", [])
            if str(link.get("relation_type", "")).strip()
        }
    )
    components_by_label = index_components_by_label(taxonomy)
    component_labels = normalize_labels(
        label
        for checkpoint in checkpoints
        for label in checkpoint.get("expected_component_labels", [])
    )
    supporting_topics = sorted(
        {
            topic
            for label in component_labels
            for topic in components_by_label.get(label, {}).get("supporting_topics", [])
            if str(topic).strip()
        }
    )

    return {
        "framework_slug": str(taxonomy.get("framework_slug", "ttfm")),
        "framework_name": str(taxonomy.get("framework_name", "TTrades Fractal Model")),
        "profile_slug": record.get("profile_slug"),
        "profile_name": record.get("profile_name"),
        "case_ref": record.get("case_ref"),
        "topic": record.get("topic"),
        "source_url": record.get("source_url"),
        "notes": record.get("notes"),
        "timeframe_stack": timeframe_stack,
        "trade_models": trade_models,
        "relation_types": relation_types,
        "component_labels": component_labels,
        "supporting_topics": supporting_topics,
        "label_provenance": infer_label_provenance(record),
        "draft_spec_keys": build_draft_spec_keys(record),
        "outcome": record.get("outcome"),
        "checkpoints": checkpoints,
    }


def summarize_case_packets(case_packets: list[dict]) -> dict:
    component_counts: Counter[str] = Counter()
    provenance_counts: Counter[str] = Counter()
    active_label_provenance_counts: Counter[str] = Counter()
    missing_screenshot_count = 0
    missing_anchor_label_count = 0
    missing_evidence_ref_count = 0
    missing_annotation_notes_count = 0
    checkpoint_count = 0
    multi_timeframe_count = 0

    for packet in case_packets:
        component_counts.update(packet.get("component_labels", []))
        provenance_counts.update([packet.get("label_provenance", "unknown")])
        packet_checkpoints = packet.get("checkpoints", [])
        checkpoint_count += len(packet_checkpoints)
        missing_screenshot_count += sum(1 for checkpoint in packet_checkpoints if not checkpoint.get("screenshot_path"))
        missing_anchor_label_count += sum(
            1
            for checkpoint in packet_checkpoints
            if not checkpoint.get("labels_by_provenance", {}).get("anchor_manual")
        )
        missing_evidence_ref_count += sum(
            1 for checkpoint in packet_checkpoints if not checkpoint.get("evidence_refs")
        )
        missing_annotation_notes_count += sum(
            1 for checkpoint in packet_checkpoints if not checkpoint.get("annotation_notes")
        )
        active_label_provenance_counts.update(
            checkpoint.get("active_label_provenance", "unlabeled")
            for checkpoint in packet_checkpoints
        )
        if packet.get("timeframe_stack", {}).get("is_multi_timeframe"):
            multi_timeframe_count += 1

    case_count = len(case_packets)
    screenshot_coverage = clamp(1.0 - (missing_screenshot_count / checkpoint_count)) if checkpoint_count else 0.0
    anchor_coverage = clamp(1.0 - (missing_anchor_label_count / checkpoint_count)) if checkpoint_count else 0.0
    return {
        "framework_slug": "ttfm",
        "case_count": case_count,
        "checkpoint_count": checkpoint_count,
        "missing_screenshot_count": missing_screenshot_count,
        "missing_anchor_label_count": missing_anchor_label_count,
        "missing_evidence_ref_count": missing_evidence_ref_count,
        "missing_annotation_notes_count": missing_annotation_notes_count,
        "screenshot_coverage": round(screenshot_coverage, 4),
        "anchor_coverage": round(anchor_coverage, 4),
        "multi_timeframe_case_ratio": round(
            clamp(multi_timeframe_count / case_count) if case_count else 0.0,
            4,
        ),
        "component_counts": dict(sorted(component_counts.items())),
        "label_provenance_counts": dict(sorted(provenance_counts.items())),
        "active_label_provenance_counts": dict(sorted(active_label_provenance_counts.items())),
        "remaining_missing_evidence_counts": {
            "screenshot": missing_screenshot_count,
            "anchor_labels": missing_anchor_label_count,
            "evidence_refs": missing_evidence_ref_count,
            "annotation_notes": missing_annotation_notes_count,
        },
    }


def build_case_packet_report(
    records: list[dict],
    taxonomy: dict | None = None,
    *,
    screenshot_manifest: dict | None = None,
    anchor_label_manifest: dict | None = None,
) -> dict:
    taxonomy = taxonomy or load_component_taxonomy()
    screenshot_manifest = screenshot_manifest if screenshot_manifest is not None else load_screenshot_manifest()
    anchor_label_manifest = (
        anchor_label_manifest if anchor_label_manifest is not None else load_anchor_label_manifest()
    )
    case_packets = [
        build_case_packet(
            record,
            taxonomy,
            screenshot_manifest=screenshot_manifest,
            anchor_label_manifest=anchor_label_manifest,
        )
        for record in records
    ]
    summary = summarize_case_packets(case_packets)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "framework_slug": taxonomy.get("framework_slug", "ttfm"),
        "framework_name": taxonomy.get("framework_name", "TTrades Fractal Model"),
        "summary": summary,
        "case_packets": case_packets,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export timeframe-aware TTFM multimodal case packets from historical annotation records."
    )
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--profile-slug")
    parser.add_argument("--topic")
    parser.add_argument("--screenshot-manifest", default=str(DEFAULT_SCREENSHOT_MANIFEST_PATH))
    parser.add_argument("--anchor-labels", default=str(DEFAULT_ANCHOR_LABELS_PATH))
    args = parser.parse_args()

    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row
        records = load_records_from_db(
            connection,
            profile_slug=args.profile_slug,
            topic=args.topic,
        )

    report = build_case_packet_report(
        records,
        screenshot_manifest=load_screenshot_manifest(Path(args.screenshot_manifest)),
        anchor_label_manifest=load_anchor_label_manifest(Path(args.anchor_labels)),
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output_path),
                "case_count": report["summary"]["case_count"],
                "checkpoint_count": report["summary"]["checkpoint_count"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
