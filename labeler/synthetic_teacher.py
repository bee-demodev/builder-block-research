from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from config import AppConfig


SCARCE_CLASS_IDS = (0, 1, 4, 6)


def _draw_grid(image: np.ndarray) -> None:
    height, width = image.shape[:2]
    for x in range(60, width - 80, 80):
        cv2.line(image, (x, 40), (x, height - 60), (232, 232, 232), 1)
    for y in range(60, height - 60, 55):
        cv2.line(image, (40, y), (width - 40, y), (238, 238, 238), 1)
    cv2.line(image, (0, height - 44), (width, height - 44), (60, 60, 60), 1)
    for y in range(50, height - 50, 45):
        cv2.line(image, (12, y), (28, y), (90, 90, 90), 1)


def _draw_candles(image: np.ndarray, values: list[tuple[int, int, int, int]]) -> None:
    x = 50
    for open_y, close_y, high_y, low_y in values:
        color = (77, 181, 95) if close_y < open_y else (34, 34, 34)
        cv2.line(image, (x + 8, high_y), (x + 8, low_y), color, 2)
        top = min(open_y, close_y)
        bottom = max(open_y, close_y)
        cv2.rectangle(image, (x, top), (x + 16, bottom), color, thickness=-1)
        x += 24


def _base_chart(width: int = 640, height: int = 360) -> np.ndarray:
    image = np.full((height, width, 3), 255, dtype=np.uint8)
    _draw_grid(image)
    return image


def _make_swing_high_image(seed: int) -> tuple[np.ndarray, list[float]]:
    rng = np.random.default_rng(seed)
    image = _base_chart()
    candles = []
    y = 250
    for _ in range(8):
        delta = int(rng.integers(-18, 18))
        open_y = y
        close_y = max(90, min(280, y + delta))
        high_y = min(open_y, close_y) - int(rng.integers(8, 20))
        low_y = max(open_y, close_y) + int(rng.integers(8, 18))
        candles.append((open_y, close_y, high_y, low_y))
        y = close_y
    peak_x = 50 + 5 * 24 + 8
    peak_y = candles[5][2]
    bbox = [round(peak_x / 640, 4), round(peak_y / 360, 4), 0.05, 0.08]
    _draw_candles(image, candles)
    cv2.rectangle(image, (peak_x - 22, peak_y - 14), (peak_x + 18, peak_y + 16), (120, 220, 220), thickness=-1)
    cv2.putText(image, "SH", (peak_x - 12, peak_y - 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (40, 40, 40), 1, cv2.LINE_AA)
    return image, bbox


def _make_swing_low_image(seed: int) -> tuple[np.ndarray, list[float]]:
    rng = np.random.default_rng(seed)
    image = _base_chart()
    candles = []
    y = 130
    for _ in range(8):
        delta = int(rng.integers(-18, 18))
        open_y = y
        close_y = max(90, min(280, y + delta))
        high_y = min(open_y, close_y) - int(rng.integers(8, 18))
        low_y = max(open_y, close_y) + int(rng.integers(8, 22))
        candles.append((open_y, close_y, high_y, low_y))
        y = close_y
    low_x = 50 + 6 * 24 + 8
    low_y = candles[6][3]
    bbox = [round(low_x / 640, 4), round(low_y / 360, 4), 0.05, 0.09]
    _draw_candles(image, candles)
    cv2.rectangle(image, (low_x - 20, low_y - 18), (low_x + 20, low_y + 12), (120, 220, 220), thickness=-1)
    cv2.putText(image, "SL", (low_x - 12, low_y - 22), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (40, 40, 40), 1, cv2.LINE_AA)
    return image, bbox


def _make_sweep_low_image(seed: int) -> tuple[np.ndarray, list[float]]:
    rng = np.random.default_rng(seed)
    image = _base_chart()
    candles = []
    y = 170
    lows = []
    for index in range(8):
        delta = int(rng.integers(-14, 14))
        open_y = y
        close_y = max(100, min(260, y + delta))
        high_y = min(open_y, close_y) - int(rng.integers(8, 16))
        low_y = max(open_y, close_y) + int(rng.integers(10, 18))
        if index in {2, 3, 4}:
            low_y = 246
        if index == 5:
            low_y = 272
        candles.append((open_y, close_y, high_y, low_y))
        lows.append(low_y)
        y = close_y
    sweep_x = 50 + 5 * 24 + 8
    sweep_y = lows[5]
    bbox = [round(sweep_x / 640, 4), round(sweep_y / 360, 4), 0.05, 0.09]
    _draw_candles(image, candles)
    cv2.rectangle(image, (sweep_x - 18, sweep_y - 20), (sweep_x + 18, sweep_y + 12), (120, 220, 220), thickness=-1)
    cv2.putText(image, "SWL", (sweep_x - 18, sweep_y - 24), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (40, 40, 40), 1, cv2.LINE_AA)
    return image, bbox


def _make_inversion_fvg_image(seed: int) -> tuple[np.ndarray, list[float]]:
    rng = np.random.default_rng(seed)
    image = _base_chart()
    candles = []
    y = 225
    for index in range(8):
        delta = int(rng.integers(-16, 16))
        open_y = y
        close_y = max(100, min(280, y + delta))
        high_y = min(open_y, close_y) - int(rng.integers(8, 18))
        low_y = max(open_y, close_y) + int(rng.integers(8, 18))
        if index == 2:
            high_y = 128
            low_y = 186
        if index == 3:
            high_y = 154
            low_y = 220
        if index == 4:
            high_y = 160
            low_y = 236
        candles.append((open_y, close_y, high_y, low_y))
        y = close_y
    zone_left = 50 + 3 * 24 - 4
    zone_right = 50 + 5 * 24 + 20
    zone_top = 150
    zone_bottom = 188
    bbox = [
        round(((zone_left + zone_right) / 2) / 640, 4),
        round(((zone_top + zone_bottom) / 2) / 360, 4),
        round((zone_right - zone_left) / 640, 4),
        round((zone_bottom - zone_top) / 360, 4),
    ]
    _draw_candles(image, candles)
    cv2.rectangle(image, (zone_left, zone_top), (zone_right, zone_bottom), (120, 220, 220), thickness=-1)
    cv2.putText(image, "IFVG", (zone_left + 8, zone_top - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (40, 40, 40), 1, cv2.LINE_AA)
    return image, bbox


GENERATORS = {
    0: _make_swing_high_image,
    1: _make_swing_low_image,
    4: _make_inversion_fvg_image,
    6: _make_sweep_low_image,
}


def generate_synthetic_sidecar(
    config: AppConfig,
    *,
    class_counts: dict[str, int],
) -> list[dict[str, Any]]:
    target = int(config.phase2.synthetic_sidecar_target_per_class)
    if not config.phase2.synthetic_sidecar_enabled or target <= 0:
        config.paths.phase2_synthetic_sidecar_path.write_text(json.dumps({"items": []}, indent=2), encoding="utf-8")
        return []

    labels_by_id = {
        0: "fractal_swing_high",
        1: "fractal_swing_low",
        4: "inversion_fvg",
        6: "liquidity_sweep_low",
    }
    items: list[dict[str, Any]] = []
    images_dir = config.paths.synthetic_sidecar_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    for class_id in SCARCE_CLASS_IDS:
        label_name = labels_by_id[class_id]
        current_count = int(class_counts.get(label_name, 0) or 0)
        deficit = max(0, target - current_count)
        for index in range(deficit):
            example_id = f"synthetic::{label_name}::{index:02d}"
            image_path = images_dir / f"{example_id.replace(':', '__')}.png"
            image, bbox = GENERATORS[class_id](seed=(class_id * 100) + index)
            cv2.imwrite(str(image_path), image)
            items.append(
                {
                    "example_id": example_id,
                    "image_path": str(image_path.resolve()),
                    "time_index": 10_000_000_000 + (class_id * 1000) + index,
                    "detections": [{"class_id": class_id, "bbox": bbox}],
                    "source": "synthetic_sidecar",
                }
            )

    config.paths.phase2_synthetic_sidecar_path.write_text(json.dumps({"items": items}, indent=2), encoding="utf-8")
    return items
