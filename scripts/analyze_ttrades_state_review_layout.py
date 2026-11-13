from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


DEFAULT_PACKET_PATH = Path("results") / "ttrades_state_review_packet_20260622.json"
DEFAULT_OUTPUT_PATH = Path("results") / "ttrades_state_review_layout_report_20260622.json"
TIMEFRAMES = ("daily", "h1", "m5")


def resolve(root_dir: Path, path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else root_dir / candidate


def relative_or_absolute(path: Path, root_dir: Path) -> str:
    try:
        return str(path.resolve().relative_to(root_dir.resolve()))
    except ValueError:
        return str(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def average_hash(path: Path, *, size: int = 16) -> str:
    with Image.open(path) as image:
        gray = image.convert("L").resize((size, size))
        pixels = list(gray.tobytes())
    average = sum(pixels) / len(pixels)
    bits = "".join("1" if pixel >= average else "0" for pixel in pixels)
    return hex(int(bits, 2))[2:].zfill((size * size) // 4)


def hamming_hex(left: str, right: str) -> int:
    width = max(len(left), len(right)) * 4
    return (int(left or "0", 16) ^ int(right or "0", 16)).bit_count() if width else 0


def image_info(root_dir: Path, raw_path: str) -> dict[str, Any]:
    path = resolve(root_dir, raw_path)
    if not raw_path or not path.exists():
        return {
            "path": raw_path,
            "exists": False,
            "width": None,
            "height": None,
            "sha256": None,
            "visual_hash": None,
            "error": "missing_image",
        }
    try:
        with Image.open(path) as image:
            width, height = image.size
        return {
            "path": relative_or_absolute(path, root_dir),
            "exists": True,
            "width": int(width),
            "height": int(height),
            "sha256": sha256_file(path),
            "visual_hash": average_hash(path),
            "error": None,
        }
    except Exception as exc:
        return {
            "path": relative_or_absolute(path, root_dir),
            "exists": False,
            "width": None,
            "height": None,
            "sha256": None,
            "visual_hash": None,
            "error": f"image_read_error:{type(exc).__name__}",
        }


def duplicate_pairs(values: dict[str, str | None]) -> list[list[str]]:
    pairs: list[list[str]] = []
    frames = list(values)
    for index, left in enumerate(frames):
        for right in frames[index + 1 :]:
            if values[left] and values[left] == values[right]:
                pairs.append([left, right])
    return pairs


def perceptual_pairs(values: dict[str, str | None], *, max_hamming: int) -> list[dict[str, Any]]:
    pairs: list[dict[str, Any]] = []
    frames = list(values)
    for index, left in enumerate(frames):
        for right in frames[index + 1 :]:
            left_hash = values[left]
            right_hash = values[right]
            if not left_hash or not right_hash:
                continue
            distance = hamming_hex(left_hash, right_hash)
            if distance <= max_hamming:
                pairs.append({"pair": [left, right], "hamming": distance})
    return pairs


def analyze_item(root_dir: Path, item: dict[str, Any], *, max_hamming: int) -> dict[str, Any]:
    chart_paths = item.get("chart_paths", {}) if isinstance(item.get("chart_paths"), dict) else {}
    images = {
        timeframe: image_info(root_dir, str(chart_paths.get(timeframe, "")))
        for timeframe in TIMEFRAMES
    }
    missing = [timeframe for timeframe, info in images.items() if not info["exists"]]
    exact = duplicate_pairs({timeframe: info["sha256"] for timeframe, info in images.items()})
    perceptual = perceptual_pairs(
        {timeframe: info["visual_hash"] for timeframe, info in images.items()},
        max_hamming=max_hamming,
    )
    layout_flags: list[str] = []
    if missing:
        layout_flags.append("missing_timeframe_image")
    if exact:
        layout_flags.append("exact_duplicate_timeframe_images")
    elif perceptual:
        layout_flags.append("near_duplicate_timeframe_images")

    if missing or exact or perceptual:
        action = "skip_invalid_layout"
    else:
        action = "review_state_labels"
    return {
        "example_id": str(item.get("example_id", "")),
        "priority_score": float(item.get("priority_score") or 0.0),
        "source": str(item.get("source", "")),
        "layout_flags": layout_flags,
        "recommended_review_action": action,
        "images": images,
        "exact_duplicate_pairs": exact,
        "near_duplicate_pairs": perceptual,
        "candidate_missing_evidence": list(
            (item.get("candidate_state", {}) if isinstance(item.get("candidate_state"), dict) else {}).get("missing_evidence", [])
        ),
    }


def analyze_packet(
    packet: dict[str, Any],
    *,
    root_dir: Path,
    packet_path: Path,
    max_hamming: int = 8,
) -> dict[str, Any]:
    items = [
        analyze_item(root_dir, item, max_hamming=max_hamming)
        for item in packet.get("items", [])
        if isinstance(item, dict)
    ]
    counts = Counter(item["recommended_review_action"] for item in items)
    flag_counts = Counter(flag for item in items for flag in item["layout_flags"])
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_packet_path": relative_or_absolute(packet_path, root_dir),
        "candidate_count": len(items),
        "max_hamming": max_hamming,
        "action_counts": dict(sorted(counts.items())),
        "layout_flag_counts": dict(sorted(flag_counts.items())),
        "items": sorted(
            items,
            key=lambda item: (
                item["recommended_review_action"] != "skip_invalid_layout",
                -item["priority_score"],
                item["example_id"],
            ),
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze TTrades state-review candidates for invalid chart layout.")
    parser.add_argument("--root-dir", type=Path, default=Path("."))
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--max-hamming", type=int, default=8)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root_dir = args.root_dir.resolve()
    packet_path = resolve(root_dir, args.packet)
    output_path = resolve(root_dir, args.output)
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    report = analyze_packet(
        packet,
        root_dir=root_dir,
        packet_path=packet_path,
        max_hamming=args.max_hamming,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output_path": str(output_path),
                "candidate_count": report["candidate_count"],
                "action_counts": report["action_counts"],
                "layout_flag_counts": report["layout_flag_counts"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
