from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from export_ttfm_case_packets import DEFAULT_OUTPUT as DEFAULT_CASE_PACKET_PATH


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BARS_MANIFEST_PATH = ROOT / "data" / "databento" / "manifest.json"
DEFAULT_MARKET_MAP_PATH = ROOT / "data" / "ttfm_market_context_map.json"
DEFAULT_VALIDATION_PATH = ROOT / "data" / "tradingview_pine_validation.json"
DEFAULT_DATASET_OUTPUT = ROOT / "results" / "ttfm_teacher_visual_dataset.jsonl"
DEFAULT_REPORT_OUTPUT = ROOT / "results" / "ttfm_teacher_visual_dataset_report.json"


def load_optional_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def load_case_packet_report(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def index_bars_manifest(manifest: dict) -> dict[str, dict]:
    indexed: dict[str, dict] = {}
    for item in manifest.get("files", []):
        symbol = str(item.get("symbol", "")).strip().upper()
        if not symbol:
            continue
        indexed[symbol] = {
            "symbol": symbol,
            "timeframe": str(item.get("timeframe", "")).strip() or None,
            "bars_path": str(item.get("normalized_csv_path", "")).strip() or None,
            "first_timestamp": str(item.get("first_timestamp", "")).strip() or None,
            "last_timestamp": str(item.get("last_timestamp", "")).strip() or None,
            "row_count": int(item.get("row_count", 0) or 0),
        }
    return indexed


def parse_recorded_at(value: str) -> datetime:
    normalized = str(value).strip().replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def resolve_symbol_from_chart_symbol(chart_symbol: str, known_symbols: list[str]) -> str | None:
    if not chart_symbol:
        return None
    candidate = str(chart_symbol).strip().upper()
    if ":" in candidate:
        candidate = candidate.split(":", 1)[1]
    candidate = re.sub(r"[^A-Z0-9]", "", candidate)
    for symbol in sorted(known_symbols, key=len, reverse=True):
        if candidate.startswith(symbol):
            return symbol
    return None


def derive_proxy_confidence(validation: dict) -> float:
    qa_status = str(validation.get("qa_status", "")).strip().lower()
    if qa_status == "pass":
        return 0.7
    if qa_status == "fail":
        return 0.45
    return 0.35


def build_trade_model_defaults_from_validation(
    validation_manifest: dict,
    bars_lookup: dict[str, dict],
) -> dict[str, dict]:
    known_symbols = sorted(bars_lookup)
    latest_by_spec: dict[str, tuple[datetime, dict]] = {}
    for validation in validation_manifest.get("validations", []):
        spec_key = str(validation.get("spec_key", "")).strip()
        chart_symbol = str(validation.get("chart_symbol", "")).strip()
        if not spec_key or not chart_symbol:
            continue
        resolved_symbol = resolve_symbol_from_chart_symbol(chart_symbol, known_symbols)
        if not resolved_symbol:
            continue
        recorded_at = parse_recorded_at(str(validation.get("recorded_at", "")).strip())
        latest_by_spec[spec_key] = (recorded_at, validation)

    defaults: dict[str, dict] = {}
    for spec_key, (_, validation) in latest_by_spec.items():
        resolved_symbol = resolve_symbol_from_chart_symbol(
            str(validation.get("chart_symbol", "")).strip(),
            known_symbols,
        )
        if not resolved_symbol:
            continue
        bar_info = bars_lookup[resolved_symbol]
        defaults[spec_key] = {
            "symbol": resolved_symbol,
            "timeframe": bar_info.get("timeframe"),
            "bars_path": bar_info.get("bars_path"),
            "first_timestamp": bar_info.get("first_timestamp"),
            "last_timestamp": bar_info.get("last_timestamp"),
            "row_count": bar_info.get("row_count"),
            "alignment_status": "market_context_only",
            "mapping_provenance": "tradingview_validation_proxy",
            "source_chart_symbol": str(validation.get("chart_symbol", "")).strip(),
            "source_spec_key": spec_key,
            "confidence": derive_proxy_confidence(validation),
            "anchor_timestamp": None,
            "window_minutes_before": None,
            "window_minutes_after": None,
            "notes": (
                "Mapped from live TradingView validation for the matching trade model; "
                "requires teacher-case timestamp confirmation before full alignment."
            ),
        }
    return defaults


def index_case_overrides(market_map: dict) -> dict[str, dict]:
    indexed: dict[str, dict] = {}
    for item in market_map.get("case_overrides", []):
        case_ref = str(item.get("case_ref", "")).strip()
        if not case_ref:
            continue
        indexed[case_ref] = item
    return indexed


def build_market_context(
    *,
    bar_info: dict | None,
    alignment_status: str,
    mapping_provenance: str,
    symbol: str | None,
    source_chart_symbol: str | None = None,
    source_spec_key: str | None = None,
    anchor_timestamp: str | None = None,
    window_minutes_before: int | None = None,
    window_minutes_after: int | None = None,
    confidence: float | None = None,
    notes: str | None = None,
) -> dict:
    return {
        "alignment_status": alignment_status,
        "mapping_provenance": mapping_provenance,
        "symbol": symbol,
        "bars_path": bar_info.get("bars_path") if bar_info else None,
        "bars_timeframe": bar_info.get("timeframe") if bar_info else None,
        "bars_first_timestamp": bar_info.get("first_timestamp") if bar_info else None,
        "bars_last_timestamp": bar_info.get("last_timestamp") if bar_info else None,
        "bars_row_count": bar_info.get("row_count") if bar_info else None,
        "anchor_timestamp": anchor_timestamp,
        "window_minutes_before": window_minutes_before,
        "window_minutes_after": window_minutes_after,
        "source_chart_symbol": source_chart_symbol,
        "source_spec_key": source_spec_key,
        "confidence": confidence,
        "notes": notes,
    }


def resolve_market_context(
    packet: dict,
    *,
    bars_lookup: dict[str, dict],
    case_override_lookup: dict[str, dict],
    trade_model_defaults: dict[str, dict],
) -> dict:
    case_ref = str(packet.get("case_ref", "")).strip()
    override = case_override_lookup.get(case_ref)
    if override:
        symbol = str(override.get("symbol", "")).strip().upper() or None
        bar_info = bars_lookup.get(symbol) if symbol else None
        if bar_info:
            anchor_timestamp = str(override.get("anchor_timestamp", "")).strip() or None
            return build_market_context(
                bar_info=bar_info,
                alignment_status="fully_aligned" if anchor_timestamp else "market_context_only",
                mapping_provenance=str(override.get("mapping_provenance", "case_manual")).strip()
                or "case_manual",
                symbol=symbol,
                anchor_timestamp=anchor_timestamp,
                window_minutes_before=(
                    int(override["window_minutes_before"])
                    if override.get("window_minutes_before") is not None
                    else None
                ),
                window_minutes_after=(
                    int(override["window_minutes_after"])
                    if override.get("window_minutes_after") is not None
                    else None
                ),
                confidence=float(override.get("confidence", 1.0)),
                notes=str(override.get("notes", "")).strip() or None,
            )

    for trade_model in packet.get("trade_models", []):
        default = trade_model_defaults.get(str(trade_model).strip())
        if not default:
            continue
        bar_info = bars_lookup.get(str(default.get("symbol", "")).strip().upper())
        return build_market_context(
            bar_info=bar_info,
            alignment_status=str(default.get("alignment_status", "market_context_only")),
            mapping_provenance=str(default.get("mapping_provenance", "tradingview_validation_proxy")),
            symbol=str(default.get("symbol", "")).strip() or None,
            source_chart_symbol=str(default.get("source_chart_symbol", "")).strip() or None,
            source_spec_key=str(default.get("source_spec_key", "")).strip() or None,
            confidence=float(default.get("confidence", 0.35)),
            notes=str(default.get("notes", "")).strip() or None,
        )

    return build_market_context(
        bar_info=None,
        alignment_status="unmapped",
        mapping_provenance="unmapped",
        symbol=None,
        notes=(
            "No case-level market override or trade-model proxy mapping is currently available. "
            "Add a case override with symbol and anchor timestamp to fully align this teacher example."
        ),
    )


def build_teacher_visual_dataset_rows(
    case_packet_report: dict,
    *,
    bars_manifest: dict,
    validation_manifest: dict,
    market_map: dict,
) -> list[dict]:
    bars_lookup = index_bars_manifest(bars_manifest)
    trade_model_defaults = build_trade_model_defaults_from_validation(validation_manifest, bars_lookup)
    case_override_lookup = index_case_overrides(market_map)

    rows: list[dict] = []
    for packet in case_packet_report.get("case_packets", []):
        market_context = resolve_market_context(
            packet,
            bars_lookup=bars_lookup,
            case_override_lookup=case_override_lookup,
            trade_model_defaults=trade_model_defaults,
        )
        for checkpoint in packet.get("checkpoints", []):
            screenshot_path = checkpoint.get("screenshot_path")
            if not screenshot_path:
                continue
            rows.append(
                {
                    "example_id": f"{packet['case_ref']}::{checkpoint['checkpoint']}",
                    "case_ref": packet["case_ref"],
                    "topic": packet.get("topic"),
                    "trade_models": packet.get("trade_models", []),
                    "relation_types": packet.get("relation_types", []),
                    "checkpoint": checkpoint["checkpoint"],
                    "timeframe": checkpoint.get("timeframe"),
                    "timeframe_role": checkpoint.get("timeframe_role"),
                    "timeframe_stack": packet.get("timeframe_stack", {}),
                    "active_labels": checkpoint.get("expected_component_labels", []),
                    "active_label_provenance": checkpoint.get("active_label_provenance"),
                    "labels_by_provenance": checkpoint.get("labels_by_provenance", {}),
                    "supporting_topics": packet.get("supporting_topics", []),
                    "draft_spec_keys": packet.get("draft_spec_keys", []),
                    "outcome": packet.get("outcome"),
                    "annotation_notes": checkpoint.get("annotation_notes", []),
                    "evidence_refs": checkpoint.get("evidence_refs", []),
                    "zone_geometry": checkpoint.get("zone_geometry"),
                    "source_url": packet.get("source_url"),
                    "screenshot_path": screenshot_path,
                    "market_context": market_context,
                }
            )
    return rows


def summarize_teacher_visual_dataset(rows: list[dict], case_packet_report: dict) -> dict:
    checkpoint_count = int(case_packet_report.get("summary", {}).get("checkpoint_count", 0))
    skipped_missing_screenshot_count = max(0, checkpoint_count - len(rows))
    alignment_status_counts = Counter()
    mapping_provenance_counts = Counter()
    mapped_case_refs: set[str] = set()
    fully_aligned_case_refs: set[str] = set()
    proxy_case_refs: set[str] = set()

    for row in rows:
        market_context = row.get("market_context", {})
        alignment_status = str(market_context.get("alignment_status", "unmapped"))
        mapping_provenance = str(market_context.get("mapping_provenance", "unmapped"))
        case_ref = str(row.get("case_ref", "")).strip()
        alignment_status_counts[alignment_status] += 1
        mapping_provenance_counts[mapping_provenance] += 1
        if alignment_status != "unmapped" and case_ref:
            mapped_case_refs.add(case_ref)
        if alignment_status == "fully_aligned" and case_ref:
            fully_aligned_case_refs.add(case_ref)
        if mapping_provenance == "tradingview_validation_proxy" and case_ref:
            proxy_case_refs.add(case_ref)

    return {
        "row_count": len(rows),
        "checkpoint_count": checkpoint_count,
        "skipped_missing_screenshot_count": skipped_missing_screenshot_count,
        "alignment_status_counts": dict(sorted(alignment_status_counts.items())),
        "mapping_provenance_counts": dict(sorted(mapping_provenance_counts.items())),
        "mapped_case_count": len(mapped_case_refs),
        "fully_aligned_case_count": len(fully_aligned_case_refs),
        "trade_model_proxy_case_count": len(proxy_case_refs),
    }


def build_teacher_visual_dataset_report(
    case_packet_report: dict,
    *,
    bars_manifest: dict,
    validation_manifest: dict,
    market_map: dict,
) -> tuple[list[dict], dict]:
    rows = build_teacher_visual_dataset_rows(
        case_packet_report,
        bars_manifest=bars_manifest,
        validation_manifest=validation_manifest,
        market_map=market_map,
    )
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": summarize_teacher_visual_dataset(rows, case_packet_report),
    }
    return rows, report


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Export screenshot-backed TTFM teacher rows with explicit market-context alignment status."
        )
    )
    parser.add_argument("--case-packets", default=str(DEFAULT_CASE_PACKET_PATH))
    parser.add_argument("--bars-manifest", default=str(DEFAULT_BARS_MANIFEST_PATH))
    parser.add_argument("--validation-manifest", default=str(DEFAULT_VALIDATION_PATH))
    parser.add_argument("--market-map", default=str(DEFAULT_MARKET_MAP_PATH))
    parser.add_argument("--output", default=str(DEFAULT_DATASET_OUTPUT))
    parser.add_argument("--report-output", default=str(DEFAULT_REPORT_OUTPUT))
    args = parser.parse_args()

    case_packet_report = load_case_packet_report(Path(args.case_packets))
    bars_manifest = load_optional_json(Path(args.bars_manifest), {"files": []})
    validation_manifest = load_optional_json(Path(args.validation_manifest), {"validations": []})
    market_map = load_optional_json(Path(args.market_map), {"case_overrides": []})

    rows, report = build_teacher_visual_dataset_report(
        case_packet_report,
        bars_manifest=bars_manifest,
        validation_manifest=validation_manifest,
        market_map=market_map,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "\n".join(json.dumps(row) for row in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )

    report_path = Path(args.report_output)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "dataset_output": str(output_path),
                "report_output": str(report_path),
                "row_count": report["summary"]["row_count"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
