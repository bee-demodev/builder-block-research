from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageFilter, ImageStat


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.analyze_ttrades_state_review_layout import (
    TIMEFRAMES,
    duplicate_pairs,
    image_info,
    perceptual_pairs,
    relative_or_absolute,
    resolve,
)


DEFAULT_PACKET_PATH = Path("results") / "ttrades_state_review_packet_20260622.json"
DEFAULT_OUTPUT_PATH = Path("results") / "tradingview_capture_quality_report_20260622.json"
ROLE_BY_TIMEFRAME = {"daily": "htf", "h1": "itf", "m5": "ltf"}
EXPECTED_RESOLUTIONS = {
    "daily": {"D", "1D"},
    "h1": {"60", "1H", "60M"},
    "m5": {"5", "5M"},
}
HARD_FLAGS = {
    "missing_timeframe_image",
    "unreadable_timeframe_image",
    "exact_duplicate_timeframe_images",
    "near_duplicate_timeframe_images",
    "low_information_timeframe_image",
    "timeframe_metadata_mismatch",
    "symbol_metadata_mismatch",
}


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def common_capture_dir(root_dir: Path, chart_paths: dict[str, str]) -> Path | None:
    parents: list[Path] = []
    for timeframe in TIMEFRAMES:
        raw_path = chart_paths.get(timeframe)
        if not raw_path:
            continue
        path = resolve(root_dir, raw_path)
        parents.append(path.parent)
    if not parents:
        return None
    first = parents[0]
    return first if all(parent == first for parent in parents) else None


def normalize_resolution(value: Any) -> str:
    cleaned = str(value or "").strip().upper()
    aliases = {
        "1DAY": "1D",
        "DAY": "D",
        "1HOUR": "1H",
        "1HR": "1H",
        "5MIN": "5M",
        "5MINUTE": "5M",
    }
    return aliases.get(cleaned, cleaned)


def image_density_metrics(path: Path, *, crop_box: tuple[float, float, float, float] = (0.08, 0.10, 0.98, 0.96)) -> dict[str, Any]:
    with Image.open(path) as image:
        gray = image.convert("L")
    width, height = gray.size
    left = int(width * crop_box[0])
    top = int(height * crop_box[1])
    right = int(width * crop_box[2])
    bottom = int(height * crop_box[3])
    crop = gray.crop((left, top, right, bottom))
    stat = ImageStat.Stat(crop)
    mean = float(stat.mean[0])
    stddev = float(stat.stddev[0])
    pixels = _pixel_values(crop)
    total = max(len(pixels), 1)
    non_background_ratio = sum(1 for pixel in pixels if abs(pixel - mean) > 18) / total
    edges = crop.filter(ImageFilter.FIND_EDGES)
    edge_pixels = _pixel_values(edges)
    edge_ratio = sum(1 for pixel in edge_pixels if pixel > 24) / max(len(edge_pixels), 1)
    downsampled = crop.resize((128, 128))
    unique_128 = len(set(_pixel_values(downsampled)))
    return {
        "mean_luma": round(mean, 4),
        "stddev_luma": round(stddev, 4),
        "non_background_ratio": round(non_background_ratio, 6),
        "edge_ratio": round(edge_ratio, 6),
        "unique_luma_128": int(unique_128),
    }


def _pixel_values(image: Image.Image) -> list[int]:
    flattened = getattr(image, "get_flattened_data", None)
    if callable(flattened):
        return list(flattened())
    return list(image.getdata())


def low_information(
    metrics: dict[str, Any],
    *,
    min_edge_ratio: float,
    min_non_background_ratio: float,
    min_unique_luma: int,
) -> bool:
    sparse_edges = (
        float(metrics.get("edge_ratio", 0.0)) < min_edge_ratio
        and float(metrics.get("non_background_ratio", 0.0)) < min_non_background_ratio
    )
    sparse_tones = (
        int(metrics.get("unique_luma_128", 0)) < min_unique_luma
        and float(metrics.get("non_background_ratio", 0.0)) < min_non_background_ratio
    )
    return sparse_edges or sparse_tones


def capture_metadata(root_dir: Path, chart_paths: dict[str, str]) -> tuple[Path | None, dict[str, Any] | None]:
    capture_dir = common_capture_dir(root_dir, chart_paths)
    if capture_dir is None:
        return None, None
    capture_path = capture_dir / "capture.json"
    payload = load_json(capture_path, None)
    return capture_path, payload if isinstance(payload, dict) else None


def metadata_flags(
    metadata: dict[str, Any] | None,
    *,
    expected_symbol: str | None = None,
) -> tuple[list[str], dict[str, Any]]:
    if metadata is None:
        return ["missing_capture_metadata"], {}
    frames = metadata.get("frames", {}) if isinstance(metadata.get("frames"), dict) else {}
    frame_summary: dict[str, Any] = {}
    flags: list[str] = []
    original_symbol = str((metadata.get("original_state") or {}).get("symbol") or "").strip()
    expected = expected_symbol or original_symbol
    for timeframe, role in ROLE_BY_TIMEFRAME.items():
        frame = frames.get(role, {}) if isinstance(frames.get(role), dict) else {}
        resolved = normalize_resolution(frame.get("resolved_resolution") or (frame.get("state") or {}).get("resolution"))
        symbol = str(frame.get("symbol") or (frame.get("state") or {}).get("symbol") or "").strip()
        frame_summary[timeframe] = {
            "role": role,
            "requested_timeframe": str(frame.get("requested_timeframe") or ""),
            "resolved_resolution": resolved,
            "symbol": symbol,
        }
        if resolved and resolved not in EXPECTED_RESOLUTIONS[timeframe]:
            flags.append("timeframe_metadata_mismatch")
        if expected and symbol and symbol != expected:
            flags.append("symbol_metadata_mismatch")
    return list(dict.fromkeys(flags)), {
        "capture_symbol": original_symbol,
        "expected_symbol": expected or "",
        "frames": frame_summary,
    }


def dimension_flags(images: dict[str, dict[str, Any]]) -> list[str]:
    sizes = {
        (info.get("width"), info.get("height"))
        for info in images.values()
        if info.get("exists") and info.get("width") and info.get("height")
    }
    return ["inconsistent_image_dimensions"] if len(sizes) > 1 else []


def analyze_item(
    root_dir: Path,
    item: dict[str, Any],
    *,
    max_hamming: int,
    min_edge_ratio: float,
    min_non_background_ratio: float,
    min_unique_luma: int,
) -> dict[str, Any]:
    chart_paths = item.get("chart_paths", {}) if isinstance(item.get("chart_paths"), dict) else {}
    images = {
        timeframe: image_info(root_dir, str(chart_paths.get(timeframe, "")))
        for timeframe in TIMEFRAMES
    }
    for timeframe, info in images.items():
        if not info.get("exists"):
            continue
        try:
            metrics = image_density_metrics(resolve(root_dir, str(chart_paths.get(timeframe, ""))))
            info["density"] = metrics
            info["low_information"] = low_information(
                metrics,
                min_edge_ratio=min_edge_ratio,
                min_non_background_ratio=min_non_background_ratio,
                min_unique_luma=min_unique_luma,
            )
        except Exception as exc:
            info["density"] = None
            info["low_information"] = True
            info["error"] = f"density_error:{type(exc).__name__}"

    exact = duplicate_pairs({timeframe: info.get("sha256") for timeframe, info in images.items()})
    perceptual = perceptual_pairs(
        {timeframe: info.get("visual_hash") for timeframe, info in images.items()},
        max_hamming=max_hamming,
    )
    capture_path, metadata = capture_metadata(root_dir, {key: str(value) for key, value in chart_paths.items()})
    meta_flags, meta_summary = metadata_flags(metadata)

    flags: list[str] = []
    missing = [timeframe for timeframe, info in images.items() if not info.get("exists")]
    unreadable = [timeframe for timeframe, info in images.items() if info.get("error") and info.get("error") != "missing_image"]
    low_info = [timeframe for timeframe, info in images.items() if info.get("low_information")]
    if missing:
        flags.append("missing_timeframe_image")
    if unreadable:
        flags.append("unreadable_timeframe_image")
    if exact:
        flags.append("exact_duplicate_timeframe_images")
    elif perceptual:
        flags.append("near_duplicate_timeframe_images")
    if low_info:
        flags.append("low_information_timeframe_image")
    flags.extend(meta_flags)
    flags.extend(dimension_flags(images))
    flags = list(dict.fromkeys(flags))
    hard_flags = [flag for flag in flags if flag in HARD_FLAGS]
    action = "recapture_before_review" if hard_flags else "review_with_caution" if flags else "review_state_labels"
    return {
        "example_id": str(item.get("example_id", "")),
        "source": str(item.get("source", "")),
        "priority_score": float(item.get("priority_score") or 0.0),
        "recommended_action": action,
        "quality_flags": flags,
        "hard_flags": hard_flags,
        "low_information_timeframes": low_info,
        "capture_metadata_path": relative_or_absolute(capture_path, root_dir) if capture_path else "",
        "capture_metadata": meta_summary,
        "images": images,
        "exact_duplicate_pairs": exact,
        "near_duplicate_pairs": perceptual,
    }


def analyze_packet(
    packet: dict[str, Any],
    *,
    root_dir: Path,
    packet_path: Path,
    max_hamming: int = 8,
    min_edge_ratio: float = 0.018,
    min_non_background_ratio: float = 0.012,
    min_unique_luma: int = 90,
) -> dict[str, Any]:
    items = [
        analyze_item(
            root_dir,
            item,
            max_hamming=max_hamming,
            min_edge_ratio=min_edge_ratio,
            min_non_background_ratio=min_non_background_ratio,
            min_unique_luma=min_unique_luma,
        )
        for item in packet.get("items", [])
        if isinstance(item, dict)
    ]
    action_counts = Counter(item["recommended_action"] for item in items)
    flag_counts = Counter(flag for item in items for flag in item["quality_flags"])
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_packet_path": relative_or_absolute(packet_path, root_dir),
        "candidate_count": len(items),
        "thresholds": {
            "max_hamming": max_hamming,
            "min_edge_ratio": min_edge_ratio,
            "min_non_background_ratio": min_non_background_ratio,
            "min_unique_luma": min_unique_luma,
        },
        "action_counts": dict(sorted(action_counts.items())),
        "quality_flag_counts": dict(sorted(flag_counts.items())),
        "items": sorted(
            items,
            key=lambda item: (
                item["recommended_action"] == "review_state_labels",
                item["recommended_action"] == "review_with_caution",
                -item["priority_score"],
                item["example_id"],
            ),
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze TradingView Daily/1h/5m capture quality before state review.")
    parser.add_argument("--root-dir", type=Path, default=Path("."))
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--max-hamming", type=int, default=8)
    parser.add_argument("--min-edge-ratio", type=float, default=0.018)
    parser.add_argument("--min-non-background-ratio", type=float, default=0.012)
    parser.add_argument("--min-unique-luma", type=int, default=90)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root_dir = args.root_dir.resolve()
    packet_path = resolve(root_dir, args.packet)
    output_path = resolve(root_dir, args.output)
    packet = load_json(packet_path, {})
    report = analyze_packet(
        packet,
        root_dir=root_dir,
        packet_path=packet_path,
        max_hamming=args.max_hamming,
        min_edge_ratio=args.min_edge_ratio,
        min_non_background_ratio=args.min_non_background_ratio,
        min_unique_luma=args.min_unique_luma,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output_path": str(output_path),
                "candidate_count": report["candidate_count"],
                "action_counts": report["action_counts"],
                "quality_flag_counts": report["quality_flag_counts"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
