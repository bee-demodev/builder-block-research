from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


DEFAULT_CAPTURE_QUALITY_PATH = Path("results") / "tradingview_capture_quality_report_20260622.json"
DEFAULT_OUTPUT_PATH = Path("results") / "tradingview_recapture_plan_20260622.json"
FLAG_WEIGHTS = {
    "low_information_timeframe_image": 120,
    "exact_duplicate_timeframe_images": 110,
    "symbol_metadata_mismatch": 100,
    "near_duplicate_timeframe_images": 90,
    "timeframe_metadata_mismatch": 80,
    "missing_timeframe_image": 75,
    "unreadable_timeframe_image": 75,
    "missing_capture_metadata": 40,
    "inconsistent_image_dimensions": 20,
}


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


def capture_symbol(item: dict[str, Any]) -> str:
    metadata = item.get("capture_metadata", {}) if isinstance(item.get("capture_metadata"), dict) else {}
    for key in ("expected_symbol", "capture_symbol"):
        value = str(metadata.get(key) or "").strip()
        if value:
            return value
    return "unknown"


def is_live_tradingview_failure(item: dict[str, Any]) -> bool:
    if item.get("source") == "tradingview_mcp_live":
        return True
    capture_path = str(item.get("capture_metadata_path") or "").replace("\\", "/")
    return "results/live_tradingview/" in capture_path


def severity_score(item: dict[str, Any]) -> float:
    flags = [str(flag) for flag in item.get("quality_flags", [])]
    flag_score = sum(FLAG_WEIGHTS.get(flag, 10) for flag in flags)
    priority = float(item.get("priority_score") or 0.0)
    return round(flag_score + priority, 4)


def recapture_reason(flags: list[str]) -> str:
    if "low_information_timeframe_image" in flags:
        return "Recapture because at least one timeframe image is too blank or sparse for state review."
    if "exact_duplicate_timeframe_images" in flags:
        return "Recapture because at least two timeframe screenshots are exact duplicates."
    if "near_duplicate_timeframe_images" in flags:
        return "Recapture because timeframe screenshots are visually near-duplicate."
    if "timeframe_metadata_mismatch" in flags:
        return "Recapture because the saved metadata does not confirm Daily / 1h / 5m."
    if "symbol_metadata_mismatch" in flags:
        return "Recapture because symbol metadata is inconsistent across frames."
    return "Recapture before review because the capture-quality gate failed."


def recapture_target(item: dict[str, Any], *, root_dir: Path) -> dict[str, Any]:
    flags = [str(flag) for flag in item.get("quality_flags", [])]
    metadata = item.get("capture_metadata", {}) if isinstance(item.get("capture_metadata"), dict) else {}
    images = item.get("images", {}) if isinstance(item.get("images"), dict) else {}
    capture_path = Path(str(item.get("capture_metadata_path") or ""))
    capture_dir = capture_path.parent if str(capture_path) else Path()
    return {
        "example_id": str(item.get("example_id") or ""),
        "symbol": capture_symbol(item),
        "severity_score": severity_score(item),
        "quality_flags": flags,
        "reason": recapture_reason(flags),
        "capture_metadata_path": str(item.get("capture_metadata_path") or ""),
        "capture_dir": str(capture_dir) if str(capture_dir) else "",
        "requested_stack": {
            "daily": "D",
            "h1": "60",
            "m5": "5",
        },
        "prior_frame_metadata": metadata.get("frames", {}),
        "prior_images": {
            timeframe: {
                "path": str((info or {}).get("path") or ""),
                "low_information": bool((info or {}).get("low_information", False)),
            }
            for timeframe, info in images.items()
            if isinstance(info, dict)
        },
        "post_recapture_gate": "Run scripts/analyze_tradingview_capture_quality.py and require review_state_labels before seed append.",
    }


def non_live_failure(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "example_id": str(item.get("example_id") or ""),
        "source": str(item.get("source") or ""),
        "severity_score": severity_score(item),
        "quality_flags": [str(flag) for flag in item.get("quality_flags", [])],
        "recommended_action": (
            "Do not recapture in TradingView. Rebuild as a proper multi-timeframe case, "
            "attach capture metadata, or exclude from state training."
        ),
    }


def symbol_summary(targets: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for target in targets:
        grouped[str(target["symbol"])].append(target)
    summary: dict[str, Any] = {}
    for symbol, rows in sorted(grouped.items()):
        flags = Counter(flag for row in rows for flag in row.get("quality_flags", []))
        summary[symbol] = {
            "target_count": len(rows),
            "top_flags": dict(flags.most_common()),
            "top_example_ids": [row["example_id"] for row in sorted(rows, key=lambda row: (-row["severity_score"], row["example_id"]))[:5]],
        }
    return summary


def build_recapture_plan(capture_quality: dict[str, Any], *, capture_quality_path: Path, root_dir: Path) -> dict[str, Any]:
    failed = [
        item
        for item in capture_quality.get("items", [])
        if isinstance(item, dict) and item.get("recommended_action") == "recapture_before_review"
    ]
    passing = [
        item
        for item in capture_quality.get("items", [])
        if isinstance(item, dict) and item.get("recommended_action") == "review_state_labels"
    ]
    targets = [
        recapture_target(item, root_dir=root_dir)
        for item in failed
        if is_live_tradingview_failure(item)
    ]
    targets.sort(key=lambda row: (-float(row["severity_score"]), row["symbol"], row["example_id"]))
    non_live = [
        non_live_failure(item)
        for item in failed
        if not is_live_tradingview_failure(item)
    ]
    non_live.sort(key=lambda row: (-float(row["severity_score"]), row["example_id"]))
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_capture_quality_report": relative_or_absolute(capture_quality_path, root_dir),
        "policy": {
            "purpose": "Prioritize TradingView recaptures before state review or RunPod training.",
            "training_gate": "Do not train from failed captures. Recaptured rows must pass capture quality and still require visual promotion.",
            "required_stack": {"daily": "D", "h1": "60", "m5": "5"},
        },
        "summary": {
            "source_candidate_count": int(capture_quality.get("candidate_count") or len(capture_quality.get("items", []))),
            "failed_capture_count": len(failed),
            "recapture_target_count": len(targets),
            "non_live_failed_count": len(non_live),
            "passing_review_state_count": len(passing),
            "recapture_target_by_symbol": symbol_summary(targets),
        },
        "recapture_targets": targets,
        "non_live_rebuild_or_exclude": non_live,
        "passing_review_state_candidates": [
            {
                "example_id": str(item.get("example_id") or ""),
                "symbol": capture_symbol(item),
                "quality_flags": [str(flag) for flag in item.get("quality_flags", [])],
            }
            for item in passing
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a prioritized TradingView recapture plan from capture-quality results.")
    parser.add_argument("--root-dir", type=Path, default=Path("."))
    parser.add_argument("--capture-quality", type=Path, default=DEFAULT_CAPTURE_QUALITY_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root_dir = args.root_dir.resolve()
    capture_quality_path = resolve(root_dir, args.capture_quality)
    output_path = resolve(root_dir, args.output)
    plan = build_recapture_plan(
        load_json(capture_quality_path),
        capture_quality_path=capture_quality_path,
        root_dir=root_dir,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output_path": str(output_path),
                "failed_capture_count": plan["summary"]["failed_capture_count"],
                "recapture_target_count": plan["summary"]["recapture_target_count"],
                "non_live_failed_count": plan["summary"]["non_live_failed_count"],
                "passing_review_state_count": plan["summary"]["passing_review_state_count"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
