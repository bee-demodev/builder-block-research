from __future__ import annotations

import argparse
import json
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


from labeler.tradingview_weak_labeler import (
    DECISION_ALLOWED_VERDICTS,
    DECISION_MIN_CHART_HEIGHT,
    DECISION_MIN_CHART_WIDTH,
    DECISION_PACKET_VERSION,
    DECISION_PREFERRED_VIEWPORT,
)


DEFAULT_OUTPUT_PATH = Path("results") / "live_tradingview_decision_packet.json"
TIMEFRAMES = ("daily", "h1", "m5")


def resolve(root_dir: Path, path: str | Path) -> Path:
    raw_path = Path(path)
    return raw_path if raw_path.is_absolute() else (root_dir / raw_path).resolve()


def relative_or_absolute(path: Path, root_dir: Path) -> str:
    try:
        return str(path.resolve().relative_to(root_dir.resolve()))
    except ValueError:
        return str(path.resolve())


def png_dimensions(data: bytes) -> tuple[int, int] | None:
    if len(data) < 24 or not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return None
    if data[12:16] != b"IHDR":
        return None
    width, height = struct.unpack(">II", data[16:24])
    return int(width), int(height)


def jpeg_dimensions(data: bytes) -> tuple[int, int] | None:
    if len(data) < 4 or not data.startswith(b"\xff\xd8"):
        return None
    index = 2
    while index + 9 < len(data):
        if data[index] != 0xFF:
            index += 1
            continue
        marker = data[index + 1]
        index += 2
        if marker in {0xD8, 0xD9, 0x01} or 0xD0 <= marker <= 0xD7:
            continue
        if index + 2 > len(data):
            return None
        segment_length = int.from_bytes(data[index : index + 2], "big")
        if segment_length < 2 or index + segment_length > len(data):
            return None
        if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
            if segment_length < 7:
                return None
            height = int.from_bytes(data[index + 3 : index + 5], "big")
            width = int.from_bytes(data[index + 5 : index + 7], "big")
            return int(width), int(height)
        index += segment_length
    return None


def image_dimensions(path: Path) -> tuple[int, int] | None:
    if not path.exists() or not path.is_file():
        return None
    data = path.read_bytes()[:8192]
    return png_dimensions(data) or jpeg_dimensions(data)


def inspect_image(*, root_dir: Path, timeframe: str, path: Path) -> dict[str, Any]:
    exists = path.exists() and path.is_file()
    dimensions = image_dimensions(path) if exists else None
    width = dimensions[0] if dimensions else 0
    height = dimensions[1] if dimensions else 0
    issues: list[str] = []
    if not exists:
        issues.append("missing_image")
    elif dimensions is None:
        issues.append("unsupported_or_unreadable_image")
    else:
        if width < DECISION_MIN_CHART_WIDTH:
            issues.append("width_too_small")
        if height < DECISION_MIN_CHART_HEIGHT:
            issues.append("height_too_small")
    return {
        "timeframe": timeframe,
        "path": relative_or_absolute(path, root_dir),
        "exists": exists,
        "width": width,
        "height": height,
        "minimum_width": DECISION_MIN_CHART_WIDTH,
        "minimum_height": DECISION_MIN_CHART_HEIGHT,
        "decision_usable": exists and dimensions is not None and not issues,
        "issues": issues,
    }


def duplicate_image_issues(image_paths: dict[str, Path]) -> dict[str, list[str]]:
    issues = {timeframe: [] for timeframe in image_paths}
    seen_resolved_paths: dict[str, str] = {}
    seen_bytes: dict[bytes, str] = {}
    for timeframe, path in image_paths.items():
        resolved = str(path.resolve())
        if resolved in seen_resolved_paths:
            first_timeframe = seen_resolved_paths[resolved]
            issues[timeframe].append(f"duplicate_image_path:{first_timeframe}")
            issues[first_timeframe].append(f"duplicate_image_path:{timeframe}")
        else:
            seen_resolved_paths[resolved] = timeframe

        if not path.exists() or not path.is_file():
            continue
        data = path.read_bytes()
        if data in seen_bytes:
            first_timeframe = seen_bytes[data]
            issues[timeframe].append(f"duplicate_image_content:{first_timeframe}")
            issues[first_timeframe].append(f"duplicate_image_content:{timeframe}")
        else:
            seen_bytes[data] = timeframe
    return {timeframe: list(dict.fromkeys(values)) for timeframe, values in issues.items()}


def decision_rag_queries(symbol: str) -> list[dict[str, Any]]:
    return [
        {
            "name": "timeframe_alignment",
            "query": f"TTrades {symbol} daily h1 m5 bias timeframe alignment point of interest",
            "filters": {"concepts": ["daily_bias", "timeframe_alignment", "poi"]},
        },
        {
            "name": "entry_and_invalidation",
            "query": f"TTrades {symbol} sweep entry confirmation invalidation protected swing",
            "filters": {"concepts": ["liquidity_sweep", "entry_trigger", "invalidation"]},
        },
        {
            "name": "no_trade_filters",
            "query": "TTrades no trade after expansion higher timeframe objective continuation failure missing confirmation",
            "filters": {"concepts": ["no_trade", "continuation_failure", "missing_confirmation"]},
        },
    ]


def build_manual_packet(
    *,
    root_dir: Path,
    symbol: str,
    daily_path: Path,
    h1_path: Path,
    m5_path: Path,
    source_note: str = "",
) -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).isoformat()
    chart_paths = {
        "daily": relative_or_absolute(daily_path, root_dir),
        "h1": relative_or_absolute(h1_path, root_dir),
        "m5": relative_or_absolute(m5_path, root_dir),
    }
    image_reports = {
        "daily": inspect_image(root_dir=root_dir, timeframe="daily", path=daily_path),
        "h1": inspect_image(root_dir=root_dir, timeframe="h1", path=h1_path),
        "m5": inspect_image(root_dir=root_dir, timeframe="m5", path=m5_path),
    }
    duplicate_issues = duplicate_image_issues(
        {
            "daily": daily_path,
            "h1": h1_path,
            "m5": m5_path,
        }
    )
    for timeframe, issues in duplicate_issues.items():
        if issues:
            image_reports[timeframe]["issues"].extend(issues)
            image_reports[timeframe]["issues"] = list(dict.fromkeys(image_reports[timeframe]["issues"]))
            image_reports[timeframe]["decision_usable"] = False
    blocked_reasons = [
        f"{timeframe}:{issue}"
        for timeframe, report in image_reports.items()
        for issue in report["issues"]
    ]
    decision_ready = not blocked_reasons
    return {
        "mode": "manual_tradingview_screenshot_decision_support",
        "packet_version": DECISION_PACKET_VERSION,
        "generated_at": generated_at,
        "captured_at": generated_at,
        "symbol": symbol,
        "decision_ready": decision_ready,
        "blocked_reasons": blocked_reasons,
        "source_capture_path": "",
        "source_note": source_note,
        "chart_paths": chart_paths,
        "timeframe_order": list(TIMEFRAMES),
        "capture_contract": {
            "source": "manual_tradingview_screenshots",
            "required_timeframes": list(TIMEFRAMES),
            "minimum_chart_pixels": {
                "width": DECISION_MIN_CHART_WIDTH,
                "height": DECISION_MIN_CHART_HEIGHT,
            },
            "preferred_viewport": DECISION_PREFERRED_VIEWPORT,
            "rules": [
                "Screenshots must show a single readable chart pane per timeframe.",
                "Daily, H1, and M5 screenshots must be from the same symbol and current analysis moment.",
                "Do not reuse old or cropped screenshots for live decisions.",
            ],
        },
        "capture_quality": {
            "capture_quality_passed": decision_ready,
            "recommended_action": "continue_to_visual_markup" if decision_ready else "recapture_manual_screenshots",
            "quality_flags": blocked_reasons,
            "hard_flags": blocked_reasons,
            "decision_support_flags": blocked_reasons,
            "resolution_failures": {
                timeframe: report
                for timeframe, report in image_reports.items()
                if report["issues"]
            },
            "capture_metadata_path": "",
            "capture_metadata": {
                "source": "manual_tradingview_screenshots",
                "symbol": symbol,
                "source_note": source_note,
            },
            "images": image_reports,
        },
        "visual_markup_request": {
            "instructions": [
                "Inspect all three timeframe screenshots before choosing visible markup.",
                "Mark only visible evidence; do not infer hidden candles or missing higher-timeframe context.",
                "Use missing_context when any required screenshot is unreadable, stale, cropped, or ambiguous.",
            ],
            "labels_to_mark": [
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
            ],
        },
        "retrieval_context": {
            "corpus": [
                "knowledge/ttfm_video_corpus/chunks.jsonl",
                "knowledge/ttfm_video_corpus/visual_windows.jsonl",
                "knowledge/second_brain",
                "results/daily_research_history.jsonl",
            ],
            "queries": decision_rag_queries(symbol),
        },
        "ttrades_checklist": [
            {"field": "daily_bias", "required_for_take": True, "status": "unfilled"},
            {"field": "h1_structure_and_poi", "required_for_take": True, "status": "unfilled"},
            {"field": "m5_entry_readiness", "required_for_take": True, "status": "unfilled"},
            {"field": "liquidity_draw", "required_for_take": True, "status": "unfilled"},
            {"field": "invalidation", "required_for_take": True, "status": "unfilled"},
            {"field": "retrieval_support", "required_for_take": True, "status": "unfilled"},
        ],
        "decision_gate": {
            "allowed_verdicts": list(DECISION_ALLOWED_VERDICTS),
            "take_requires": [
                "verified visual markup",
                "derived state from Daily/H1/M5 visible evidence",
                "retrieval examples that support rather than contradict the setup",
            ],
            "insufficient_evidence_when": [
                "any required timeframe is missing, too small, duplicated, unreadable, stale, or cropped",
                "symbol or timeframe metadata cannot be trusted from the screenshots",
            ],
        },
        "journal_stub": {
            "status": "pending_decision_review",
            "expected_later_fields": [
                "visual_markup",
                "derived_ttrades_state",
                "verdict",
                "outcome",
                "valid_loss_or_error_classification",
            ],
        },
        "bundle_record": {
            "direction": "none",
            "htf_bias": "unknown",
            "fractal_stage": "unknown",
            "poi_type": "none",
            "poi_validity": False,
            "entry_state": "wait",
            "invalidation_state": "unknown",
            "setup_quality": "unknown",
            "path_family": "unknown",
            "label_confidence": 0.35,
            "source": "manual_screenshot_packet_pending_visual_state",
        },
        "capture_attempt_summary": [
            {
                "attempt": 1,
                "capture_dir": "",
                "capture_quality_passed": decision_ready,
                "recommended_action": "continue_to_visual_markup" if decision_ready else "recapture_manual_screenshots",
                "quality_flags": blocked_reasons,
            }
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a decision packet from manual TradingView Daily/H1/M5 screenshots.")
    parser.add_argument("--root-dir", type=Path, default=Path("."))
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--daily", type=Path, required=True)
    parser.add_argument("--h1", type=Path, required=True)
    parser.add_argument("--m5", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--source-note", default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root_dir = args.root_dir.resolve()
    output_path = resolve(root_dir, args.output)
    packet = build_manual_packet(
        root_dir=root_dir,
        symbol=args.symbol,
        daily_path=resolve(root_dir, args.daily),
        h1_path=resolve(root_dir, args.h1),
        m5_path=resolve(root_dir, args.m5),
        source_note=args.source_note,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output_path": str(output_path),
                "decision_ready": packet["decision_ready"],
                "blocked_reasons": packet["blocked_reasons"],
                "recommended_action": packet["capture_quality"]["recommended_action"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
