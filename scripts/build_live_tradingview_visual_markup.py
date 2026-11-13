from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


DEFAULT_PACKET_PATH = Path("results") / "live_tradingview_decision_packet.json"
DEFAULT_REQUEST_PATH = Path("results") / "live_tradingview_visual_markup_request.json"
VALID_TIMEFRAMES = ("daily", "h1", "m5")
ALLOWED_LABELS = {
    "daily_bias",
    "liquidity_high",
    "liquidity_low",
    "sweep",
    "protected_swing",
    "poi_or_reaction_zone",
    "invalidation",
    "entry_trigger",
    "cisd_confirmation",
    "displacement",
    "current_price",
    "missing_context",
}
M5_ENTRY_LABELS = {"sweep", "entry_trigger", "cisd_confirmation"}
H1_STRUCTURE_LABELS = {"protected_swing", "poi_or_reaction_zone", "invalidation"}
DAILY_CONTEXT_LABELS = {"daily_bias", "liquidity_high", "liquidity_low"}


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


def clamp_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        confidence = 0.5
    return round(max(0.0, min(confidence, 1.0)), 4)


def build_markup_request(packet: dict[str, Any], *, root_dir: Path, packet_path: Path) -> dict[str, Any]:
    chart_paths = packet.get("chart_paths", {}) if isinstance(packet.get("chart_paths"), dict) else {}
    images = []
    for timeframe in VALID_TIMEFRAMES:
        raw_path = str(chart_paths.get(timeframe) or "")
        path = resolve(root_dir, raw_path) if raw_path else Path()
        images.append(
            {
                "timeframe": timeframe,
                "path": relative_or_absolute(path, root_dir) if raw_path else "",
                "exists": bool(raw_path and path.exists()),
            }
        )
    return {
        "mode": "live_tradingview_visual_markup_request",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_packet_path": relative_or_absolute(packet_path, root_dir),
        "packet_version": packet.get("packet_version", ""),
        "symbol": packet.get("symbol", ""),
        "decision_ready": bool(packet.get("decision_ready")),
        "blocked_reasons": packet.get("blocked_reasons", []),
        "images": images,
        "task": {
            "summary": "Inspect the Daily, H1, and M5 TradingView screenshots and return only visible TTrades evidence.",
            "rules": [
                "Use all three screenshots before judging whether an entry is available.",
                "Do not infer hidden candles, off-screen structure, or unstated higher-timeframe context.",
                "Use missing_context when a required level or candle is cropped, unreadable, or blocked.",
                "A take decision later requires verified M5 entry evidence, H1 structure/POI, Daily context, and intact invalidation.",
            ],
        },
        "allowed_labels": sorted(ALLOWED_LABELS),
        "output_schema": {
            "status": "verified | needs_review",
            "summary": "short visible-evidence summary",
            "labels": [
                {
                    "label": "one allowed label",
                    "timeframe": "daily | h1 | m5",
                    "confidence": "0.0-1.0",
                    "evidence": "what is visibly present",
                    "price_hint": "optional visible price/level text",
                }
            ],
            "direction_hint": "bullish | bearish | neutral | unknown",
            "entry_readiness": "ready | wait | no_trade | insufficient_evidence",
            "blocking_issues": ["visible reason this cannot be a take"],
        },
        "existing_packet_request": packet.get("visual_markup_request", {}),
        "existing_bundle_cues": packet.get("bundle_record", {}),
    }


def normalize_labels(markup: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    normalized: list[dict[str, Any]] = []
    issues: list[str] = []
    raw_labels = markup.get("labels", [])
    if not isinstance(raw_labels, list):
        return [], ["labels_not_list"]
    for index, item in enumerate(raw_labels):
        if not isinstance(item, dict):
            issues.append(f"label_{index}_not_object")
            continue
        label = str(item.get("label") or item.get("type") or "").strip()
        timeframe = str(item.get("timeframe") or "").strip().lower()
        if label not in ALLOWED_LABELS:
            issues.append(f"label_{index}_unsupported:{label}")
            continue
        if timeframe not in VALID_TIMEFRAMES:
            issues.append(f"label_{index}_bad_timeframe:{timeframe}")
            continue
        normalized.append(
            {
                "label": label,
                "timeframe": timeframe,
                "confidence": clamp_confidence(item.get("confidence")),
                "evidence": str(item.get("evidence") or item.get("notes") or "").strip(),
                "price_hint": str(item.get("price_hint") or item.get("level") or "").strip(),
            }
        )
    return normalized, issues


def markup_coverage(labels: list[dict[str, Any]]) -> dict[str, Any]:
    by_timeframe = {
        timeframe: [item["label"] for item in labels if item.get("timeframe") == timeframe]
        for timeframe in VALID_TIMEFRAMES
    }
    return {
        "by_timeframe": by_timeframe,
        "daily_context": any(label in DAILY_CONTEXT_LABELS for label in by_timeframe["daily"]),
        "h1_structure": any(label in H1_STRUCTURE_LABELS for label in by_timeframe["h1"]),
        "m5_entry_evidence": any(label in M5_ENTRY_LABELS for label in by_timeframe["m5"]),
        "has_missing_context": any(item.get("label") == "missing_context" for item in labels),
    }


def validate_visual_markup(markup: dict[str, Any], packet: dict[str, Any]) -> dict[str, Any]:
    labels, issues = normalize_labels(markup)
    coverage = markup_coverage(labels)
    blocking_issues = [
        str(item).strip()
        for item in markup.get("blocking_issues", [])
        if str(item).strip()
    ] if isinstance(markup.get("blocking_issues"), list) else []
    if not packet.get("decision_ready"):
        blocking_issues.append("capture_not_decision_ready")
    if coverage["has_missing_context"]:
        blocking_issues.append("visual_missing_context")
    if not coverage["daily_context"]:
        blocking_issues.append("daily_context_not_marked")
    if not coverage["h1_structure"]:
        blocking_issues.append("h1_structure_not_marked")
    if not coverage["m5_entry_evidence"]:
        blocking_issues.append("m5_entry_evidence_not_marked")
    verified = not issues and not blocking_issues
    return {
        "status": "verified" if verified else "needs_review",
        "verified": verified,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": str(markup.get("summary") or "").strip(),
        "direction_hint": str(markup.get("direction_hint") or "unknown").strip(),
        "entry_readiness": str(markup.get("entry_readiness") or "insufficient_evidence").strip(),
        "labels": labels,
        "coverage": coverage,
        "validation_issues": issues,
        "blocking_issues": list(dict.fromkeys(blocking_issues)),
        "source": "visual_markup_import",
    }


def attach_visual_markup(packet: dict[str, Any], markup: dict[str, Any]) -> dict[str, Any]:
    updated = dict(packet)
    updated["visual_markup"] = markup
    updated["visual_markup_attached_at"] = datetime.now(timezone.utc).isoformat()
    return updated


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build or import visual markup for a live TradingView decision packet.")
    parser.add_argument("--root-dir", type=Path, default=Path("."))
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    parser.add_argument("--request-output", type=Path, default=DEFAULT_REQUEST_PATH)
    parser.add_argument("--markup", type=Path, default=None, help="Optional VLM/Codex markup JSON to validate and attach.")
    parser.add_argument(
        "--updated-packet",
        type=Path,
        default=None,
        help="Where to write packet with attached visual markup. Defaults to --packet.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root_dir = args.root_dir.resolve()
    packet_path = resolve(root_dir, args.packet)
    request_path = resolve(root_dir, args.request_output)
    packet = load_json(packet_path, {})
    if not isinstance(packet, dict) or not packet:
        raise SystemExit(f"Decision packet not found or invalid: {packet_path}")
    request = build_markup_request(packet, root_dir=root_dir, packet_path=packet_path)
    request_path.parent.mkdir(parents=True, exist_ok=True)
    request_path.write_text(json.dumps(request, indent=2) + "\n", encoding="utf-8")
    result: dict[str, Any] = {
        "request_output": str(request_path),
        "image_count": len(request["images"]),
        "decision_ready": packet.get("decision_ready"),
    }
    if args.markup is not None:
        markup_path = resolve(root_dir, args.markup)
        raw_markup = load_json(markup_path, {})
        if not isinstance(raw_markup, dict) or not raw_markup:
            raise SystemExit(f"Markup JSON not found or invalid: {markup_path}")
        validated = validate_visual_markup(raw_markup, packet)
        updated_packet_path = resolve(root_dir, args.updated_packet or packet_path)
        updated_packet = attach_visual_markup(packet, validated)
        updated_packet_path.parent.mkdir(parents=True, exist_ok=True)
        updated_packet_path.write_text(json.dumps(updated_packet, indent=2) + "\n", encoding="utf-8")
        result.update(
            {
                "markup_status": validated["status"],
                "markup_verified": validated["verified"],
                "updated_packet": str(updated_packet_path),
                "blocking_issues": validated["blocking_issues"],
                "validation_issues": validated["validation_issues"],
            }
        )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
