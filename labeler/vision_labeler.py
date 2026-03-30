from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import os
import shutil
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from config import AppConfig, LEGACY_YOLO_CLASS_NAMES, YOLO_CLASS_NAMES, YOLO_CLASS_TO_ID
from data_loader import ChartExample, canonical_time_index, split_examples_by_time


VISION_SYSTEM_PROMPT = """You are an expert chart markup labeler for TTrades-style TradingView screenshots.
Identify only visible chart structures and return a strict JSON array.
Each item must be exactly:
{"class_id": int, "bbox": [x_center, y_center, width, height]}

Rules:
- Use normalized bbox coordinates in the inclusive range 0 to 1.
- Return only classes that are clearly visible on the chart.
- Do not include commentary, markdown, prose, code fences, or keys other than class_id and bbox.
- If no valid markup is visible, return [].

Classes:
0 liquidity_sweep_high
1 liquidity_sweep_low
2 protected_swing
3 bullish_reaction_zone
4 bearish_reaction_zone
"""

SUPERVISION_REVIEW_INSTRUCTIONS = """Codex supervision packet for Phase 2.
Review each queued chart manually or with an in-session image workflow.
For every chart:
- decide whether the image is labelable
- identify visible structures from the approved class list
- produce strict JSON detections using the Phase 2 schema
- note ambiguous charts that should remain in review instead of entering YOLO training
"""
VISION_CACHE_VERSION = 1
SLIDE_TEXT_MARKERS = (
    "diagram",
    "let's get into the pdf",
    "lets get into the pdf",
    "this is an example of",
    "what is a fair value gap",
    "what is a",
    "in this video, we are going to cover",
    "in this video, we are going to talk about",
)
SLIDE_TITLE_MARKERS = (
    "intro",
    "indicator & settings",
    "fundamentals",
)
CHART_TEXT_MARKERS = (
    "here we are in our",
    "let this play out",
    "drop down to the",
    "put my stop",
    "take an entry",
    "new york session",
    "back testing",
    "price reaches into",
    "retest",
    "previous day",
    "previous day's",
    "hourly time frame",
    "5-minute time frame",
    "5minut time frame",
    "protected low",
    "protected swing",
    "sweep out",
)
AUTO_PROMOTION_EXCLUDE_TITLE_MARKERS = (
    "intro",
    "reason ",
    "solution",
    "valid c2 swing",
    "ltf entry",
    "measuring candles",
    "candle 2",
    "candle 3",
)
AUTO_PROMOTION_ALLOWED_CLASS_IDS = {0, 1, 2, 3, 4}
TEACHER_AUTO_LABEL_ALLOWED_CLASS_IDS = {0, 1, 2, 3, 4}
REVIEW_OUTCOMES = {"accepted", "adjusted", "rejected", "no_setup", "ambiguous"}
BEARISH_TEXT_MARKERS = (
    "bearish",
    "continuation lower",
    "trade lower",
    "short",
    "resistance",
    "previous day low",
    "sell",
)
BULLISH_TEXT_MARKERS = (
    "bullish",
    "continuation higher",
    "trade higher",
    "long",
    "support",
    "previous day high",
    "buy",
)
SWING_HIGH_TEXT_MARKERS = (
    "swing high",
    "protected high",
    "higher high",
)
SWING_LOW_TEXT_MARKERS = (
    "swing low",
    "protected low",
    "higher low",
)
CHART_UI_LEFT_EDGE_MIN = 0.05
CHART_UI_BOTTOM_EDGE_MIN = 0.03
CHART_UI_MID_TONE_MIN = 0.04
SLIDE_WHITE_RATIO_MIN = 0.90
SLIDE_BOTTOM_EDGE_MAX = 0.02
SLIDE_RIGHT_EDGE_MAX = 0.025


@dataclass(slots=True)
class Detection:
    class_id: int
    bbox: list[float]


LEGACY_CLASS_NAME_TO_V1_NAME = {
    "liquidity_sweep_high": "liquidity_sweep_high",
    "liquidity_sweep_low": "liquidity_sweep_low",
    "protected_swing": "protected_swing",
    "order_block_bullish": "bullish_reaction_zone",
    "order_block_bearish": "bearish_reaction_zone",
}


def _normalize_label_set(values: list[Any]) -> set[str]:
    return {str(value).strip().lower() for value in values if str(value).strip()}


def _normalize_legacy_detection_class_id(
    class_id: int,
    *,
    class_name: str | None = None,
) -> int | None:
    if 0 <= class_id < len(YOLO_CLASS_NAMES):
        return class_id
    candidate_name = str(class_name or "").strip().lower()
    if not candidate_name and 0 <= class_id < len(LEGACY_YOLO_CLASS_NAMES):
        candidate_name = LEGACY_YOLO_CLASS_NAMES[class_id]
    mapped_name = LEGACY_CLASS_NAME_TO_V1_NAME.get(candidate_name)
    if mapped_name is None:
        return None
    return YOLO_CLASS_TO_ID[mapped_name]


def _guess_reaction_zone_class_id_from_text(text_blob: str) -> int | None:
    directional = _guess_directional_class_id_from_text(text_blob)
    if directional == 3:
        return YOLO_CLASS_TO_ID["bearish_reaction_zone"]
    if directional == 2:
        return YOLO_CLASS_TO_ID["bullish_reaction_zone"]
    return None


def _class_name_from_id(class_id: int) -> str | None:
    if 0 <= class_id < len(YOLO_CLASS_NAMES):
        return YOLO_CLASS_NAMES[class_id]
    return None


def _resolve_image_path(raw_path: str | None, *, root_dir: Path | None = None) -> Path | None:
    cleaned = str(raw_path or "").strip()
    if not cleaned:
        return None
    candidate = Path(cleaned)
    if not candidate.is_absolute():
        candidate = ((root_dir or Path.cwd()) / candidate).resolve()
    return candidate


def _row_text_blob(row: dict[str, Any]) -> str:
    return " ".join(
        [
            str(row.get("title", "")),
            str(row.get("text", "")),
            str(row.get("transcript_window", "")),
            str(row.get("outcome", {}).get("reason", "")),
            " ".join(str(value) for value in row.get("cue_terms", [])),
            " ".join(str(value) for value in row.get("candidate_labels", [])),
            " ".join(str(value) for value in row.get("active_labels", [])),
        ]
    ).lower()


def _infer_v1_candidate_class_names(
    candidate_labels: set[str],
    *,
    text_blob: str,
) -> set[str]:
    mapped: set[str] = set()
    directional_reaction = _guess_reaction_zone_class_id_from_text(text_blob)
    if "liquidity_sweep" in candidate_labels or "liquidity sweep" in candidate_labels:
        if "low" in text_blob or "bullish" in text_blob or "long" in text_blob:
            mapped.add("liquidity_sweep_low")
        elif "high" in text_blob or "bearish" in text_blob or "short" in text_blob:
            mapped.add("liquidity_sweep_high")
    if "protected_swing" in candidate_labels or "protected swing" in candidate_labels:
        mapped.add("protected_swing")
    if any(label in candidate_labels for label in {"order_block", "order block", "fair_value_gap", "fair value gap"}):
        if directional_reaction is not None:
            mapped.add(YOLO_CLASS_NAMES[directional_reaction])
    return mapped


def _guess_directional_class_id_from_text(text_blob: str) -> int | None:
    bearish_score = sum(1 for marker in BEARISH_TEXT_MARKERS if marker in text_blob)
    bullish_score = sum(1 for marker in BULLISH_TEXT_MARKERS if marker in text_blob)
    if bearish_score > bullish_score:
        return YOLO_CLASS_TO_ID["bearish_reaction_zone"]
    if bullish_score > bearish_score:
        return YOLO_CLASS_TO_ID["bullish_reaction_zone"]
    return None


def _guess_swing_class_id_from_text(text_blob: str) -> int | None:
    if any(marker in text_blob for marker in SWING_HIGH_TEXT_MARKERS + SWING_LOW_TEXT_MARKERS):
        return YOLO_CLASS_TO_ID["protected_swing"]
    directional = _guess_directional_class_id_from_text(text_blob)
    if directional in {
        YOLO_CLASS_TO_ID["bullish_reaction_zone"],
        YOLO_CLASS_TO_ID["bearish_reaction_zone"],
    }:
        return YOLO_CLASS_TO_ID["protected_swing"]
    return None


def _compute_chart_image_features(image_path: Path) -> dict[str, float] | None:
    try:
        import cv2
    except ImportError:  # pragma: no cover
        return None

    image = cv2.imread(str(image_path))
    if image is None:
        return None
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 80, 160)
    height, width = gray.shape
    left_band = edges[:, : max(1, int(width * 0.08))]
    right_band = edges[:, width - max(1, int(width * 0.08)) :]
    bottom_band = edges[height - max(1, int(height * 0.14)) :, :]
    return {
        "left_edge_density": float(left_band.mean() / 255.0),
        "right_edge_density": float(right_band.mean() / 255.0),
        "bottom_edge_density": float(bottom_band.mean() / 255.0),
        "mid_tone_ratio": float(((gray > 180) & (gray < 245)).mean()),
        "white_ratio": float((gray > 245).mean()),
    }


def is_teaching_slide_image(image_path: Path) -> bool:
    features = _compute_chart_image_features(image_path)
    if features is None:
        return False
    chart_ui_signals = sum(
        [
            features["left_edge_density"] >= CHART_UI_LEFT_EDGE_MIN,
            features["bottom_edge_density"] >= CHART_UI_BOTTOM_EDGE_MIN,
            features["mid_tone_ratio"] >= CHART_UI_MID_TONE_MIN,
        ]
    )
    slide_signals = sum(
        [
            features["white_ratio"] >= SLIDE_WHITE_RATIO_MIN,
            features["bottom_edge_density"] <= SLIDE_BOTTOM_EDGE_MAX,
            features["right_edge_density"] <= SLIDE_RIGHT_EDGE_MAX,
        ]
    )
    return slide_signals >= 3 and chart_ui_signals <= 1


def _propose_overlay_detections_for_image(
    image_path: Path,
    *,
    class_id: int | None,
    min_area_ratio: float = 0.0015,
    max_area_ratio: float = 0.18,
    max_suggestions: int = 3,
) -> list[dict[str, Any]]:
    if class_id is None or not image_path.exists():
        return []
    try:
        import cv2
    except ImportError:  # pragma: no cover
        return []

    image = cv2.imread(str(image_path))
    if image is None:
        return []
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    height, width = image.shape[:2]
    image_area = float(height * width)
    masks = [
        cv2.inRange(hsv, (15, 20, 120), (40, 255, 255)),
        cv2.inRange(hsv, (75, 15, 120), (110, 255, 255)),
    ]
    kernel = np.ones((3, 3), dtype=np.uint8)
    suggestions: list[dict[str, Any]] = []
    for mask in masks:
        cleaned = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, kernel)
        contours, _hierarchy = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area_ratio = (w * h) / image_area
            if area_ratio < min_area_ratio or area_ratio > max_area_ratio:
                continue
            if w < 8 or h < 6:
                continue
            suggestions.append(
                {
                    "class_id": class_id,
                    "bbox": [
                        round((x + (w / 2.0)) / width, 4),
                        round((y + (h / 2.0)) / height, 4),
                        round(w / width, 4),
                        round(h / height, 4),
                    ],
                }
            )
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[int, int, int, int]] = set()
    for suggestion in sorted(suggestions, key=lambda item: item["bbox"][2] * item["bbox"][3], reverse=True):
        key = tuple(int(value * 1000) for value in suggestion["bbox"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(suggestion)
        if len(deduped) >= max_suggestions:
            break
    return deduped


def _propose_overlay_detections_for_teacher_image(
    image_path: Path,
    *,
    class_id: int | None,
) -> list[dict[str, Any]]:
    suggestions = _propose_overlay_detections_for_image(
        image_path,
        class_id=class_id,
        min_area_ratio=0.002,
        max_area_ratio=0.20,
        max_suggestions=3,
    )
    if suggestions:
        return suggestions

    try:
        import cv2
    except ImportError:  # pragma: no cover
        return []

    image = cv2.imread(str(image_path))
    if image is None:
        return []
    height, width = image.shape[:2]
    crop_specs = [
        (0.18, 0.98, 0.08, 0.92),
        (0.28, 0.98, 0.10, 0.90),
    ]
    all_suggestions: list[dict[str, Any]] = []
    for top_ratio, bottom_ratio, left_ratio, right_ratio in crop_specs:
        y0 = int(height * top_ratio)
        y1 = int(height * bottom_ratio)
        x0 = int(width * left_ratio)
        x1 = int(width * right_ratio)
        if y1 <= y0 or x1 <= x0:
            continue
        crop = image[y0:y1, x0:x1]
        temp_path = image_path.parent / f"__codex_crop_{image_path.stem}.png"
        cv2.imwrite(str(temp_path), crop)
        try:
            crop_suggestions = _propose_overlay_detections_for_image(
                temp_path,
                class_id=class_id,
                min_area_ratio=0.002,
                max_area_ratio=0.30,
                max_suggestions=3,
            )
        finally:
            if temp_path.exists():
                temp_path.unlink()
        for suggestion in crop_suggestions:
            cx, cy, w_ratio, h_ratio = suggestion["bbox"]
            abs_bbox = [
                round((x0 + (cx * (x1 - x0))) / width, 4),
                round((y0 + (cy * (y1 - y0))) / height, 4),
                round((w_ratio * (x1 - x0)) / width, 4),
                round((h_ratio * (y1 - y0)) / height, 4),
            ]
            all_suggestions.append({"class_id": suggestion["class_id"], "bbox": abs_bbox})
    deduped = []
    seen: set[tuple[int, int, int, int]] = set()
    for suggestion in sorted(all_suggestions, key=lambda item: item["bbox"][2] * item["bbox"][3], reverse=True):
        key = tuple(int(value * 1000) for value in suggestion["bbox"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(suggestion)
        if len(deduped) >= 3:
            break
    return deduped


def _select_dominant_suggestion(suggestions: list[dict[str, Any]], *, min_dominance_ratio: float = 1.4) -> dict[str, Any] | None:
    if not suggestions:
        return None
    if len(suggestions) == 1:
        return suggestions[0]
    sorted_suggestions = sorted(
        suggestions,
        key=lambda item: float(item["bbox"][2]) * float(item["bbox"][3]),
        reverse=True,
    )
    largest = float(sorted_suggestions[0]["bbox"][2]) * float(sorted_suggestions[0]["bbox"][3])
    second = float(sorted_suggestions[1]["bbox"][2]) * float(sorted_suggestions[1]["bbox"][3])
    if second == 0.0 or largest >= second * min_dominance_ratio:
        return sorted_suggestions[0]
    return None


def has_openai_api_key() -> bool:
    return bool(
        os.getenv("OPENAI_API_KEY")
        or os.getenv("OPENAI_APIKEY")
        or os.getenv("OPENAI_KEY")
    )


def parse_detection_payload(payload: str) -> list[Detection]:
    parsed = json.loads(payload)
    if not isinstance(parsed, list):
        raise ValueError("Vision response must be a strict JSON array.")
    detections: list[Detection] = []
    for row in parsed:
        if not isinstance(row, dict):
            raise ValueError("Each detection must be a JSON object.")
        detections.append(
            Detection(
                class_id=int(row["class_id"]),
                bbox=[float(value) for value in row["bbox"]],
            )
        )
    return detections


def validate_detections(
    detections: list[Detection],
    *,
    suspicious_class_limit: int = 10,
    suspicious_box_limit: int = 30,
) -> list[str]:
    issues: list[str] = []
    if len(detections) > suspicious_box_limit:
        issues.append(f"bbox count exceeds suspicious limit: {len(detections)} > {suspicious_box_limit}")
    class_counts: dict[int, int] = {}
    for index, detection in enumerate(detections):
        if detection.class_id < 0 or detection.class_id >= len(YOLO_CLASS_NAMES):
            issues.append(f"detection[{index}] has invalid class_id={detection.class_id}")
        if len(detection.bbox) != 4:
            issues.append(f"detection[{index}] bbox must contain 4 values")
            continue
        x_center, y_center, width, height = detection.bbox
        if not (0.0 <= x_center <= 1.0 and 0.0 <= y_center <= 1.0):
            issues.append(f"detection[{index}] bbox center must stay within [0,1]")
        if not (0.0 < width <= 1.0 and 0.0 < height <= 1.0):
            issues.append(f"detection[{index}] bbox width/height must stay within (0,1]")
        class_counts[detection.class_id] = class_counts.get(detection.class_id, 0) + 1
    for class_id, count in class_counts.items():
        if count > suspicious_class_limit:
            issues.append(f"class_id {class_id} exceeds suspicious repetition limit with {count} boxes")
    return issues


def detections_to_yolo_lines(detections: list[Detection]) -> list[str]:
    return [
        f"{detection.class_id} "
        f"{detection.bbox[0]:.6f} {detection.bbox[1]:.6f} "
        f"{detection.bbox[2]:.6f} {detection.bbox[3]:.6f}"
        for detection in detections
    ]


def _extract_response_text(payload: dict[str, Any]) -> str:
    output_text = str(payload.get("output_text", "")).strip()
    if output_text:
        return output_text
    text_chunks: list[str] = []
    for output_item in payload.get("output", []):
        for content in output_item.get("content", []):
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                text_chunks.append(str(content["text"]))
    return "\n".join(text_chunks).strip()


def _encode_image_to_data_url(image_path: Path) -> str:
    mime_type = mimetypes.guess_type(image_path.name)[0] or "image/png"
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def _cache_metadata(image_path: Path, config: AppConfig) -> dict[str, Any]:
    return {
        "vision_model": config.phase2.vision_model,
        "prompt_sha256": _sha256_text(VISION_SYSTEM_PROMPT),
        "image_sha256": _sha256_file(image_path),
        "validator_version": VISION_CACHE_VERSION,
    }


def _load_cached_detections(cache_path: Path, image_path: Path, config: AppConfig) -> list[Detection] | None:
    if not cache_path.exists():
        return None
    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return parse_detection_payload(json.dumps(payload))
    if not isinstance(payload, dict):
        return None
    metadata = dict(payload.get("metadata", {}))
    if metadata != _cache_metadata(image_path, config):
        return None
    detections = payload.get("detections", [])
    return parse_detection_payload(json.dumps(detections))


def label_chart_image_with_openai(image_path: Path, config: AppConfig) -> list[Detection]:
    api_key = (
        os.getenv("OPENAI_API_KEY")
        or os.getenv("OPENAI_APIKEY")
        or os.getenv("OPENAI_KEY")
    )
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for Phase 2 vision labeling.")

    request_payload = {
        "model": config.phase2.vision_model,
        "input": [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": VISION_SYSTEM_PROMPT}],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": "Label this chart. Return only the strict JSON array.",
                    },
                    {
                        "type": "input_image",
                        "image_url": _encode_image_to_data_url(image_path),
                        "detail": "high",
                    },
                ],
            },
        ],
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(request_payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=config.phase2.request_timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:  # pragma: no cover - depends on live API
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Vision labeling failed with status {exc.code}: {details}") from exc
    except urllib.error.URLError as exc:  # pragma: no cover - depends on live API
        raise RuntimeError(f"Vision labeling failed: {exc.reason}") from exc

    return parse_detection_payload(_extract_response_text(payload))


def label_representative_examples(
    examples: list[ChartExample],
    config: AppConfig,
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    review_queue: list[dict[str, Any]] = []
    cache_dir = config.paths.results_dir / "vision_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    for example in examples:
        cache_path = cache_dir / f"{example.example_id.replace(':', '__')}.json"
        cached = _load_cached_detections(cache_path, example.image_path, config)
        if cached is not None:
            detections = cached
        else:
            last_error: str | None = None
            detections = None
            for _attempt in range(config.phase2.max_retries):
                try:
                    detections = label_chart_image_with_openai(example.image_path, config)
                    cache_path.write_text(
                        json.dumps(
                            {
                                "metadata": _cache_metadata(example.image_path, config),
                                "detections": [
                                    {"class_id": detection.class_id, "bbox": detection.bbox}
                                    for detection in detections
                                ],
                            },
                            indent=2,
                        ),
                        encoding="utf-8",
                    )
                    break
                except Exception as exc:  # pragma: no cover - depends on live API
                    last_error = str(exc)
            if detections is None:
                review_queue.append(
                    {
                        "example_id": example.example_id,
                        "image_path": str(example.image_path),
                        "reason": "vision_request_failed",
                        "error": last_error,
                    }
                )
                continue

        issues = validate_detections(
            detections,
            suspicious_class_limit=config.phase2.suspicious_class_limit,
            suspicious_box_limit=config.phase2.suspicious_box_limit,
        )
        record = {
            "example_id": example.example_id,
            "image_path": str(example.image_path),
            "time_index": example.time_index,
            "detections": [{"class_id": det.class_id, "bbox": det.bbox} for det in detections],
            "issues": issues,
        }
        if issues:
            review_queue.append({**record, "reason": "validation_failed"})
        else:
            records.append(record)

    return {"records": records, "review_queue": review_queue}


def build_supervision_review_queue(examples: list[ChartExample]) -> list[dict[str, Any]]:
    return build_supervision_packet(examples)["items"]


def build_supervision_packet(
    examples: list[ChartExample],
    *,
    cluster_assignments: dict[str, int] | None = None,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for example in examples:
        metadata = dict(getattr(example, "metadata", {}) or {})
        transcript_excerpt = str(metadata.get("text", "") or example.text).strip()
        candidate_label_set = _normalize_label_set(metadata.get("candidate_labels", []))
        cue_terms = list(metadata.get("cue_terms", []))
        text_blob = _row_text_blob(metadata | {"text": transcript_excerpt})
        candidate_class_names = sorted(
            _infer_v1_candidate_class_names(candidate_label_set, text_blob=text_blob)
        )
        candidate_detections: list[dict[str, Any]] = []
        image_path = _resolve_image_path(str(example.image_path))
        if image_path is not None:
            if "protected_swing" in candidate_class_names:
                candidate_detections.extend(
                    _propose_overlay_detections_for_image(
                        image_path,
                        class_id=YOLO_CLASS_TO_ID["protected_swing"],
                    )
                )
        items.append(
            {
                "example_id": example.example_id,
                "image_path": str(example.image_path),
                "time_index": example.time_index,
                "cluster_id": None if cluster_assignments is None else cluster_assignments.get(example.example_id),
                "title": str(metadata.get("title", "") or example.title),
                "source_type": str(metadata.get("source_type", "") or example.source_type),
                "checkpoint": metadata.get("checkpoint"),
                "video_slug": metadata.get("video_slug"),
                "video_id": metadata.get("video_id"),
                "topics": list(metadata.get("topics", [])),
                "candidate_labels": candidate_class_names,
                "cue_terms": cue_terms,
                "source_url": metadata.get("source_url"),
                "frame_path": metadata.get("frame_path"),
                "frame_paths": [str(example.image_path)],
                "timestamp_seconds": float(metadata.get("start", 0.0) or 0.0),
                "cue_summary": ", ".join(cue_terms[:5]) or transcript_excerpt[:160],
                "transcript_excerpt": transcript_excerpt[:400],
                "candidate_detections": candidate_detections,
                "recommended_action": "accept" if candidate_detections else "adjust",
                "reason": "codex_supervision_required",
                "notes": "OPENAI_API_KEY is not configured, so live GPT-5.4 vision labeling was skipped.",
            }
        )
    return {
        "mode": "supervision_only",
        "instructions": SUPERVISION_REVIEW_INSTRUCTIONS,
        "response_schema": {
            "items": [
                {
                    "example_id": "string",
                    "detections": [{"class_id": "int", "bbox": [0.5, 0.5, 0.25, 0.15]}],
                    "review_outcome": "accepted",
                    "note": "optional string",
                }
            ]
        },
        "class_names": {index: name for index, name in enumerate(YOLO_CLASS_NAMES)},
        "item_count": len(items),
        "items": items,
    }


def build_dense_supervision_packet_from_rows(
    rows: list[dict[str, Any]],
    *,
    limit: int = 300,
    per_video_cap: int = 4,
    video_order_lookup: dict[str, int] | None = None,
    review_frame_radius: int = 2,
    min_spacing_seconds: float = 0.0,
) -> dict[str, Any]:
    lookup = video_order_lookup or {}

    def is_chart_like_row(row: dict[str, Any]) -> bool:
        title = str(row.get("title", "")).strip().lower()
        text = str(row.get("text", "")).strip().lower()
        transcript_source = str(row.get("transcript_source", "")).strip().lower()
        topics = {str(topic).strip().lower() for topic in row.get("topics", [])}
        chart_signals = any(marker in text for marker in CHART_TEXT_MARKERS)
        slide_signals = any(marker in text for marker in SLIDE_TEXT_MARKERS) or any(
            marker in title for marker in SLIDE_TITLE_MARKERS
        )
        metadata_only_instruction = transcript_source == "synthetic_from_video_metadata" and "educational_channel" in topics

        if metadata_only_instruction and not chart_signals:
            return False
        if slide_signals and not chart_signals:
            return False
        image_path = _resolve_image_path(row.get("frame_path"))
        if image_path is not None and image_path.exists() and is_teaching_slide_image(image_path):
            return False
        return True

    def infer_candidate_class_names(row: dict[str, Any]) -> list[str]:
        candidate_labels = _normalize_label_set(row.get("candidate_labels", []))
        cue_terms = _normalize_label_set(row.get("cue_terms", []))
        combined = candidate_labels | cue_terms
        return sorted(_infer_v1_candidate_class_names(combined, text_blob=_row_text_blob(row)))

    def propose_overlay_detections(row: dict[str, Any], inferred_class_names: list[str]) -> list[dict[str, Any]]:
        image_path = _resolve_image_path(row.get("frame_path"))
        if image_path is None:
            return []
        suggestions: list[dict[str, Any]] = []
        seen: set[tuple[int, int, int, int, int]] = set()
        for class_name in inferred_class_names:
            class_id = YOLO_CLASS_TO_ID[class_name]
            for suggestion in _propose_overlay_detections_for_image(image_path, class_id=class_id):
                key = (class_id, *[int(value * 1000) for value in suggestion["bbox"]])
                if key in seen:
                    continue
                seen.add(key)
                suggestions.append(suggestion)
        return suggestions

    filtered = [
        row
        for row in rows
        if str(row.get("frame_status", "")).strip() == "extracted"
        and str(row.get("frame_path", "")).strip()
        and is_chart_like_row(row)
    ]
    filtered.sort(
        key=lambda row: (
            int(row.get("cue_score", 0) or 0),
            len(row.get("candidate_labels", [])),
            len(row.get("cue_terms", [])),
        ),
        reverse=True,
    )
    filtered_by_video: dict[str, list[dict[str, Any]]] = {}
    for row in filtered:
        video_slug = str(row.get("video_slug", "")).strip()
        filtered_by_video.setdefault(video_slug, []).append(row)
    for video_slug in filtered_by_video:
        filtered_by_video[video_slug].sort(key=lambda item: float(item.get("start", 0.0) or 0.0))
    selected: list[dict[str, Any]] = []
    per_video_counts: dict[str, int] = {}
    last_selected_start: dict[str, float] = {}
    for row in filtered:
        video_slug = str(row.get("video_slug", "")).strip()
        if video_slug and per_video_counts.get(video_slug, 0) >= per_video_cap:
            continue
        start_seconds = float(row.get("start", 0.0) or 0.0)
        if video_slug and abs(start_seconds - last_selected_start.get(video_slug, float("-inf"))) < min_spacing_seconds:
            continue
        selected.append(row)
        if video_slug:
            per_video_counts[video_slug] = per_video_counts.get(video_slug, 0) + 1
            last_selected_start[video_slug] = start_seconds
        if len(selected) >= limit:
            break

    packet_items = []
    for row in selected:
        inferred_class_names = infer_candidate_class_names(row)
        candidate_detections = propose_overlay_detections(row, inferred_class_names)
        same_video_rows = filtered_by_video.get(str(row.get("video_slug", "")).strip(), [])
        row_index = next((index for index, item in enumerate(same_video_rows) if str(item.get("example_id", "")) == str(row.get("example_id", ""))), 0)
        start_index = max(0, row_index - review_frame_radius)
        end_index = min(len(same_video_rows), row_index + review_frame_radius + 1)
        frame_paths = [
            str(neighbor.get("frame_path", ""))
            for neighbor in same_video_rows[start_index:end_index]
            if str(neighbor.get("frame_path", "")).strip()
        ]
        cue_terms = list(row.get("cue_terms", []))
        transcript_excerpt = str(row.get("text", ""))[:400]
        packet_items.append(
            {
                "example_id": str(row.get("example_id", "")),
                "image_path": str(row.get("frame_path", "")),
                "time_index": canonical_time_index(
                    video_slug=str(row.get("video_slug", "")).strip(),
                    start_seconds=float(row.get("start", 0.0) or 0.0),
                    video_order_lookup=lookup,
                    fallback_index=len(packet_items),
                ),
                "cluster_id": None,
                "title": str(row.get("title", "")),
                "source_type": str(row.get("source_type", "")),
                "checkpoint": str(row.get("checkpoint", "")),
                "video_slug": str(row.get("video_slug", "")),
                "video_id": str(row.get("video_id", "")),
                "topics": list(row.get("topics", [])),
                "candidate_labels": inferred_class_names,
                "cue_terms": cue_terms,
                "source_url": row.get("source_url"),
                "frame_path": row.get("frame_path"),
                "frame_paths": frame_paths,
                "timestamp_seconds": float(row.get("start", 0.0) or 0.0),
                "cue_summary": ", ".join(cue_terms[:5]) or transcript_excerpt[:160],
                "transcript_excerpt": transcript_excerpt,
                "candidate_detections": candidate_detections,
                "recommended_action": "accept" if candidate_detections else "adjust",
                "reason": "dense_codex_supervision_required",
                "notes": "Teaching-moment review packet mined from the TTrades YouTube corpus. Review nearby frames and correct candidate detections rather than authoring labels from scratch.",
            }
        )
    return {
        "mode": "dense_supervision_only",
        "instructions": SUPERVISION_REVIEW_INSTRUCTIONS,
        "response_schema": {
            "items": [
                {
                    "example_id": "string",
                    "detections": [{"class_id": "int", "bbox": [0.5, 0.5, 0.25, 0.15]}],
                    "review_outcome": "accepted",
                    "note": "optional string",
                }
            ]
        },
        "class_names": {index: name for index, name in enumerate(YOLO_CLASS_NAMES)},
        "item_count": len(packet_items),
        "items": packet_items,
    }


def select_heuristic_dense_autolabels(
    packet: dict[str, Any],
    *,
    existing_answer_ids: set[str],
    max_new_items: int,
    min_bbox_area: float,
    max_bbox_area: float,
) -> list[dict[str, Any]]:
    candidates: list[tuple[tuple[int, int], dict[str, Any]]] = []
    for item in packet.get("items", []):
        example_id = str(item.get("example_id", "")).strip()
        if not example_id or example_id in existing_answer_ids:
            continue
        title = str(item.get("title", "")).lower()
        if any(marker in title for marker in AUTO_PROMOTION_EXCLUDE_TITLE_MARKERS):
            continue
        suggestions = list(item.get("candidate_detections", []) or item.get("heuristic_suggestions", []))
        suggestion = _select_dominant_suggestion(suggestions)
        if suggestion is None:
            continue
        class_id = int(suggestion.get("class_id", -1))
        if class_id not in AUTO_PROMOTION_ALLOWED_CLASS_IDS:
            continue
        bbox = [float(value) for value in suggestion.get("bbox", [])]
        if len(bbox) != 4:
            continue
        area = bbox[2] * bbox[3]
        if area < min_bbox_area or area > max_bbox_area:
            continue
        candidate_labels = _infer_v1_candidate_class_names(
            {str(label).strip().lower() for label in item.get("candidate_labels", [])},
            text_blob=" ".join(
                [
                    str(item.get("title", "")),
                    str(item.get("cue_summary", "")),
                    str(item.get("transcript_excerpt", "")),
                    " ".join(str(value) for value in item.get("cue_terms", [])),
                ]
            ).lower(),
        ) | {str(label).strip().lower() for label in item.get("candidate_labels", []) if str(label).strip().lower() in YOLO_CLASS_TO_ID}
        class_name = YOLO_CLASS_NAMES[class_id]
        if class_name.endswith("reaction_zone") and class_name not in candidate_labels:
            continue
        if class_name == "protected_swing" and "protected_swing" not in candidate_labels:
            continue
        score = (
            len(candidate_labels),
            len(item.get("cue_terms", [])),
        )
        candidates.append(
            (
                score,
                {
                    "example_id": example_id,
                    "detections": [{"class_id": class_id, "bbox": bbox}],
                    "review_outcome": "accepted",
                    "source": "heuristic_auto_label",
                },
            )
        )

    candidates.sort(key=lambda entry: entry[0], reverse=True)
    return [row for _score, row in candidates[:max_new_items]]


def select_teacher_screenshot_autolabels(
    dataset_path: Path,
    *,
    root_dir: Path,
    existing_answer_ids: set[str],
    max_new_items: int,
) -> list[dict[str, Any]]:
    if not dataset_path.exists():
        return []

    try:
        import cv2
    except ImportError:  # pragma: no cover
        return []

    def infer_class_id(row: dict[str, Any]) -> int | None:
        labels = _normalize_label_set(row.get("active_labels", []))
        text_blob = _row_text_blob(row)
        checkpoint = str(row.get("checkpoint", "")).strip().lower()
        if "order_block" in labels or "fair_value_gap" in labels:
            return _guess_reaction_zone_class_id_from_text(text_blob)
        if "liquidity_sweep" in labels:
            if "low" in text_blob or "bullish" in text_blob or "long" in text_blob:
                return YOLO_CLASS_TO_ID["liquidity_sweep_low"]
            if "high" in text_blob or "bearish" in text_blob or "short" in text_blob:
                return YOLO_CLASS_TO_ID["liquidity_sweep_high"]
        if "protected_swing" in labels:
            return _guess_swing_class_id_from_text(text_blob) or YOLO_CLASS_TO_ID["protected_swing"]
        return None

    candidates: list[tuple[tuple[int, int], dict[str, Any]]] = []
    for line in dataset_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        example_id = str(row.get("example_id", "")).strip()
        if not example_id or example_id in existing_answer_ids:
            continue
        class_id = infer_class_id(row)
        if class_id not in TEACHER_AUTO_LABEL_ALLOWED_CLASS_IDS:
            continue
        screenshot_path = _resolve_image_path(row.get("screenshot_path"), root_dir=root_dir)
        if not screenshot_path.exists():
            continue
        suggestions = _propose_overlay_detections_for_teacher_image(
            screenshot_path,
            class_id=class_id,
        )
        suggestion = _select_dominant_suggestion(suggestions)
        if suggestion is None:
            continue
        score = (
            len(row.get("active_labels", [])),
            len(row.get("supporting_topics", [])),
        )
        candidates.append(
            (
                score,
                {
                    "example_id": example_id,
                    "detections": [suggestion],
                    "review_outcome": "accepted",
                    "source": "teacher_screenshot_auto_label",
                },
            )
        )

    candidates.sort(key=lambda entry: entry[0], reverse=True)
    return [row for _score, row in candidates[:max_new_items]]


def select_weak_visual_autolabels(
    dataset_path: Path,
    *,
    root_dir: Path,
    existing_answer_ids: set[str],
    max_new_items: int,
) -> list[dict[str, Any]]:
    if not dataset_path.exists():
        return []

    candidates: list[tuple[tuple[int, int], dict[str, Any]]] = []
    for line in dataset_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        example_id = str(row.get("example_id", "")).strip()
        if not example_id or example_id in existing_answer_ids:
            continue
        if str(row.get("review_status", "")).strip() != "ready_for_weak_training":
            continue
        if not bool(row.get("eligible_for_training", False)):
            continue
        image_path = _resolve_image_path(row.get("screenshot_path") or row.get("frame_path"), root_dir=root_dir)
        if image_path is None or not image_path.exists() or is_teaching_slide_image(image_path):
            continue

        labels = _normalize_label_set(row.get("active_labels", []))
        checkpoint = str(row.get("checkpoint", "")).strip().lower()
        text_blob = _row_text_blob(row)
        class_id = None
        if "order_block" in labels or "fair_value_gap" in labels:
            class_id = _guess_reaction_zone_class_id_from_text(text_blob)
        elif "protected_swing" in labels:
            class_id = _guess_swing_class_id_from_text(text_blob) or YOLO_CLASS_TO_ID["protected_swing"]
        elif "liquidity_sweep" in labels:
            if "low" in text_blob or "bullish" in text_blob:
                class_id = YOLO_CLASS_TO_ID["liquidity_sweep_low"]
            elif "high" in text_blob or "bearish" in text_blob:
                class_id = YOLO_CLASS_TO_ID["liquidity_sweep_high"]
        if class_id is None:
            continue

        suggestions = _propose_overlay_detections_for_image(
            image_path,
            class_id=class_id,
            min_area_ratio=0.002,
            max_area_ratio=0.20,
            max_suggestions=3,
        )
        suggestion = _select_dominant_suggestion(suggestions)
        if suggestion is None:
            continue
        score = (len(labels), len(row.get("cue_terms", [])))
        candidates.append(
            (
                score,
                {
                    "example_id": example_id,
                    "detections": [suggestion],
                    "review_outcome": "accepted",
                    "source": "weak_visual_auto_label",
                },
            )
        )
    candidates.sort(key=lambda entry: entry[0], reverse=True)
    return [row for _score, row in candidates[:max_new_items]]


def select_setup_quality_autolabels(
    packet: dict[str, Any],
    *,
    existing_answer_ids: set[str],
    max_new_items: int,
    positive_confidence_floor: float,
    negative_confidence_floor: float,
) -> list[dict[str, Any]]:
    candidates: list[tuple[tuple[float, int], dict[str, Any]]] = []
    for item in packet.get("items", []):
        example_id = str(item.get("example_id", "")).strip()
        if not example_id or example_id in existing_answer_ids:
            continue
        recommended_action = str(item.get("recommended_action", "")).strip().lower()
        setup_type = str(item.get("setup_type", "")).strip().lower()
        setup_confidence = float(item.get("setup_confidence", 0.0) or 0.0)
        candidate_detections = list(item.get("candidate_detections", []) or item.get("heuristic_suggestions", []))
        if (
            recommended_action == "accept"
            and setup_type in {"high_probability_long", "high_probability_short"}
            and setup_confidence >= positive_confidence_floor
            and candidate_detections
        ):
            candidates.append(
                (
                    (setup_confidence, len(candidate_detections)),
                    {
                        "example_id": example_id,
                        "detections": candidate_detections,
                        "review_outcome": "accepted",
                        "note": f"Auto-accepted from setup-quality scorer ({setup_type}, confidence={setup_confidence:.3f}).",
                        "source": "setup_quality_auto_label",
                    },
                )
            )
        elif (
            recommended_action == "no_setup"
            and setup_type == "invalid_chop"
            and setup_confidence >= negative_confidence_floor
        ):
            candidates.append(
                (
                    (setup_confidence, 0),
                    {
                        "example_id": example_id,
                        "detections": [],
                        "review_outcome": "no_setup",
                        "note": f"Auto-promoted to no_setup from setup-quality scorer (confidence={setup_confidence:.3f}).",
                        "source": "setup_quality_auto_label",
                    },
                )
            )

    candidates.sort(key=lambda entry: entry[0], reverse=True)
    return [row for _score, row in candidates[:max_new_items]]


def select_accept_packet_autolabels(
    packet: dict[str, Any],
    *,
    existing_answer_ids: set[str],
    max_new_items: int,
    confidence_floor: float,
) -> list[dict[str, Any]]:
    candidates: list[tuple[tuple[float, int], dict[str, Any]]] = []
    for item in packet.get("items", []):
        example_id = str(item.get("example_id", "")).strip()
        if not example_id or example_id in existing_answer_ids:
            continue
        if str(item.get("recommended_action", "")).strip().lower() != "accept":
            continue
        detections = list(item.get("candidate_detections", []) or item.get("heuristic_suggestions", []))
        if not detections:
            continue
        normalized = []
        max_confidence = 0.0
        for detection in detections:
            bbox = [float(value) for value in detection.get("bbox", [])]
            if len(bbox) != 4:
                continue
            confidence = float(detection.get("confidence", 1.0) or 1.0)
            max_confidence = max(max_confidence, confidence)
            normalized.append(
                {
                    "class_id": int(detection["class_id"]),
                    "bbox": bbox,
                }
            )
        if not normalized:
            continue
        if max_confidence < confidence_floor:
            continue
        candidates.append(
            (
                (max_confidence, len(normalized)),
                {
                    "example_id": example_id,
                    "detections": normalized,
                    "review_outcome": "accepted",
                    "note": f"Auto-promoted from packet recommended_action=accept (max_confidence={max_confidence:.3f}).",
                    "source": "accept_packet_auto_label",
                },
            )
        )

    candidates.sort(key=lambda entry: entry[0], reverse=True)
    return [row for _score, row in candidates[:max_new_items]]


def select_scarce_accept_packet_autolabels(
    packet: dict[str, Any],
    *,
    existing_answer_ids: set[str],
    max_new_items: int,
    confidence_floor: float,
    scarce_class_names: tuple[str, ...],
) -> list[dict[str, Any]]:
    scarce_names = {str(name).strip() for name in scarce_class_names}
    candidates: list[tuple[tuple[float, int], dict[str, Any]]] = []
    for item in packet.get("items", []):
        example_id = str(item.get("example_id", "")).strip()
        if not example_id or example_id in existing_answer_ids:
            continue
        if str(item.get("recommended_action", "")).strip().lower() != "adjust":
            continue
        candidate_labels = {str(label).strip() for label in item.get("candidate_labels", [])}
        if not (candidate_labels & scarce_names):
            continue
        detections = list(item.get("candidate_detections", []) or item.get("heuristic_suggestions", []))
        if not detections:
            continue
        normalized = []
        max_confidence = 0.0
        contains_scarce_class = False
        for detection in detections:
            bbox = [float(value) for value in detection.get("bbox", [])]
            if len(bbox) != 4:
                continue
            class_id = int(detection["class_id"])
            class_name = _class_name_from_id(class_id)
            if class_name not in scarce_names:
                continue
            contains_scarce_class = True
            confidence = float(detection.get("confidence", 1.0) or 1.0)
            max_confidence = max(max_confidence, confidence)
            normalized.append({"class_id": class_id, "bbox": bbox})
        if not contains_scarce_class or not normalized:
            continue
        if max_confidence < confidence_floor:
            continue
        candidates.append(
            (
                (max_confidence, len(normalized)),
                {
                    "example_id": example_id,
                    "detections": normalized,
                    "review_outcome": "accepted",
                    "note": f"Auto-promoted for scarce class coverage (max_confidence={max_confidence:.3f}).",
                    "source": "scarce_accept_packet_auto_label",
                },
            )
        )

    candidates.sort(key=lambda entry: entry[0], reverse=True)
    return [row for _score, row in candidates[:max_new_items]]


def build_priority_review_queue(
    packet: dict[str, Any],
    *,
    existing_answer_ids: set[str],
    class_counts: dict[str, int],
    limit: int = 100,
) -> list[dict[str, Any]]:
    scarce_scores = {name: max(0, 10 - int(class_counts.get(name, 0) or 0)) for name in YOLO_CLASS_NAMES}
    ranked: list[tuple[tuple[int, int, int], dict[str, Any]]] = []
    for item in packet.get("items", []):
        example_id = str(item.get("example_id", "")).strip()
        if not example_id or example_id in existing_answer_ids:
            continue
        candidate_labels = _normalize_label_set(item.get("candidate_labels", []))
        mapped_classes = set(candidate_labels)
        scarcity_score = sum(scarce_scores.get(name, 0) for name in mapped_classes)
        heuristic_count = len(item.get("candidate_detections", []) or item.get("heuristic_suggestions", []))
        metadata_score = len(item.get("cue_terms", [])) + len(item.get("candidate_labels", []))
        ranked.append(
            (
                (scarcity_score, heuristic_count, metadata_score),
                {
                    "example_id": example_id,
                    "image_path": item.get("image_path"),
                    "title": item.get("title"),
                    "candidate_labels": item.get("candidate_labels", []),
                    "cue_terms": item.get("cue_terms", []),
                    "candidate_detections": item.get("candidate_detections", []) or item.get("heuristic_suggestions", []),
                    "recommended_action": item.get("recommended_action", "adjust"),
                    "scarcity_score": scarcity_score,
                    "suggested_classes": sorted(mapped_classes),
                },
            )
        )
    ranked.sort(key=lambda entry: entry[0], reverse=True)
    return [row for _score, row in ranked[:limit]]


def _normalize_answer_detections(raw_detections: list[dict[str, Any]]) -> list[Detection]:
    normalized: list[Detection] = []
    for detection in raw_detections:
        normalized_class_id = _normalize_legacy_detection_class_id(
            int(detection.get("class_id", -1)),
            class_name=detection.get("class_name"),
        )
        if normalized_class_id is None:
            continue
        bbox = [float(value) for value in detection.get("bbox", [])]
        if len(bbox) != 4:
            continue
        normalized.append(Detection(class_id=normalized_class_id, bbox=bbox))
    return normalized


def load_supervision_answers(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload if isinstance(payload, list) else payload.get("items", [])
    validated: list[dict[str, Any]] = []
    for row in rows:
        example_id = str(row.get("example_id", "")).strip()
        if not example_id:
            raise ValueError("Each supervision answer must include example_id.")
        raw_detections = list(row.get("detections", []))
        default_outcome = "no_setup" if not raw_detections else "accepted"
        review_outcome = str(row.get("review_outcome", default_outcome)).strip().lower()
        if review_outcome not in REVIEW_OUTCOMES:
            raise ValueError(f"Supervision answer for {example_id} has invalid review_outcome={review_outcome}")
        detections = _normalize_answer_detections(raw_detections)
        issues = validate_detections(detections)
        if review_outcome in {"accepted", "adjusted"} and not detections:
            if not raw_detections:
                review_outcome = "no_setup"
            else:
                continue
        if issues and review_outcome in {"accepted", "adjusted"}:
            raise ValueError(f"Supervision answer for {example_id} failed validation: {issues}")
        if review_outcome in {"rejected", "ambiguous"}:
            continue
        validated.append(
            {
                "example_id": example_id,
                "detections": [{"class_id": det.class_id, "bbox": det.bbox} for det in detections],
                "review_outcome": review_outcome,
                "note": str(row.get("note", "")).strip(),
            }
        )
    return validated


def _clear_directory_files(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for child in directory.iterdir():
        if child.is_file():
            child.unlink()


def _select_benchmark_rows(labeled_examples: list[dict[str, Any]], config: AppConfig) -> list[dict[str, Any]]:
    target = max(0, int(config.phase2.benchmark_target_count))
    positive_target_per_class = max(0, int(config.phase2.benchmark_positive_target_per_class))
    hard_negative_target = max(0, int(config.phase2.benchmark_hard_negative_target_count))
    version = str(config.phase2.benchmark_version).strip()
    if target == 0:
        config.paths.benchmark_manifest_path.write_text(
            json.dumps({"benchmark_version": version, "items": []}, indent=2),
            encoding="utf-8",
        )
        return []

    eligible_rows = [row for row in labeled_examples if str(row.get("source", "")).strip() != "synthetic_sidecar"]
    if not eligible_rows:
        config.paths.benchmark_manifest_path.write_text(
            json.dumps({"benchmark_version": version, "items": []}, indent=2),
            encoding="utf-8",
        )
        return []

    existing_items: list[dict[str, Any]] = []
    if config.paths.benchmark_manifest_path.exists():
        existing_payload = json.loads(config.paths.benchmark_manifest_path.read_text(encoding="utf-8"))
        if str(existing_payload.get("benchmark_version", "")).strip() == version:
            existing_items = list(existing_payload.get("items", []))

    row_lookup = {str(row["example_id"]): row for row in eligible_rows}
    selected_rows: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    manifest_items: list[dict[str, Any]] = []

    for item in existing_items:
        example_id = str(item.get("example_id", "")).strip()
        row = row_lookup.get(example_id)
        if row is None:
            continue
        selected_rows.append(row)
        selected_ids.add(example_id)
        manifest_items.append(item)

    positives_by_class: dict[str, list[dict[str, Any]]] = {class_name: [] for class_name in YOLO_CLASS_NAMES}
    hard_negatives: list[dict[str, Any]] = []
    for row in sorted(eligible_rows, key=lambda item: str(item["example_id"])):
        if str(row["example_id"]) in selected_ids:
            continue
        if str(row.get("review_outcome", "")).strip() == "no_setup":
            hard_negatives.append(row)
            continue
        row_classes = {
            _class_name_from_id(int(detection["class_id"]))
            for detection in row.get("detections", [])
        }
        for class_name in sorted(name for name in row_classes if name is not None):
            positives_by_class[class_name].append(row)

    for class_name in YOLO_CLASS_NAMES:
        current_count = sum(1 for item in manifest_items if class_name in item.get("class_names", []))
        for row in positives_by_class[class_name]:
            if current_count >= positive_target_per_class or len(manifest_items) >= target:
                break
            example_id = str(row["example_id"])
            if example_id in selected_ids:
                continue
            class_names = sorted({
                _class_name_from_id(int(detection["class_id"]))
                for detection in row.get("detections", [])
                if _class_name_from_id(int(detection["class_id"])) is not None
            })
            selected_rows.append(row)
            selected_ids.add(example_id)
            manifest_items.append(
                {
                    "example_id": example_id,
                    "safe_name": example_id.replace(":", "__").replace("/", "_"),
                    "benchmark_version": version,
                    "review_outcome": str(row.get("review_outcome", "accepted")).strip() or "accepted",
                    "hard_negative": False,
                    "class_names": class_names,
                }
            )
            current_count += 1

    current_hard_negative_count = sum(1 for item in manifest_items if item.get("hard_negative"))
    for row in hard_negatives:
        if current_hard_negative_count >= hard_negative_target or len(manifest_items) >= target:
            break
        example_id = str(row["example_id"])
        if example_id in selected_ids:
            continue
        selected_rows.append(row)
        selected_ids.add(example_id)
        manifest_items.append(
            {
                "example_id": example_id,
                "safe_name": example_id.replace(":", "__").replace("/", "_"),
                "benchmark_version": version,
                "review_outcome": "no_setup",
                "hard_negative": True,
                "class_names": [],
            }
        )
        current_hard_negative_count += 1

    config.paths.benchmark_manifest_path.write_text(
        json.dumps(
            {
                "benchmark_version": version,
                "target_count": target,
                "positive_target_per_class": positive_target_per_class,
                "hard_negative_target_count": hard_negative_target,
                "items": manifest_items,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return selected_rows


def _write_single_split_dataset(
    rows: list[dict[str, Any]],
    *,
    image_dir: Path,
    label_dir: Path,
) -> list[dict[str, Any]]:
    exported: list[dict[str, Any]] = []
    for row in rows:
        safe_name = row["example_id"].replace(":", "__").replace("/", "_")
        source_image = Path(row["image_path"])
        target_image = image_dir / f"{safe_name}{source_image.suffix}"
        target_label = label_dir / f"{safe_name}.txt"
        shutil.copy2(source_image, target_image)
        detections = [Detection(class_id=int(item["class_id"]), bbox=[float(value) for value in item["bbox"]]) for item in row["detections"]]
        target_label.write_text("\n".join(detections_to_yolo_lines(detections)), encoding="utf-8")
        exported.append(
            {
                "example_id": row["example_id"],
                "safe_name": safe_name,
                "image_path": str(target_image),
                "label_path": str(target_label),
                "box_count": len(detections),
                "review_outcome": str(row.get("review_outcome", "accepted")).strip() or "accepted",
            }
        )
    return exported


def export_yolo_dataset(labeled_examples: list[dict[str, Any]], config: AppConfig) -> dict[str, Any]:
    for directory in (
        config.paths.yolo_images_train_dir,
        config.paths.yolo_images_val_dir,
        config.paths.yolo_labels_train_dir,
        config.paths.yolo_labels_val_dir,
        config.paths.yolo_benchmark_images_dir,
        config.paths.yolo_benchmark_labels_dir,
    ):
        _clear_directory_files(directory)

    normalized_examples = []
    for row in labeled_examples:
        review_outcome = str(row.get("review_outcome", "accepted")).strip().lower() or "accepted"
        if review_outcome not in REVIEW_OUTCOMES:
            review_outcome = "accepted"
        if review_outcome in {"rejected", "ambiguous"}:
            continue
        normalized_detections = _normalize_answer_detections(list(row.get("detections", [])))
        if review_outcome in {"accepted", "adjusted"} and not normalized_detections:
            continue
        normalized_examples.append(
            {
                **row,
                "review_outcome": review_outcome,
                "hard_negative": review_outcome == "no_setup",
                "detections": [{"class_id": det.class_id, "bbox": det.bbox} for det in normalized_detections],
            }
        )

    sorted_examples = sorted(normalized_examples, key=lambda item: item["time_index"])
    benchmark_rows = _select_benchmark_rows(sorted_examples, config)
    benchmark_ids = {str(row["example_id"]) for row in benchmark_rows}
    trainable_examples = [row for row in sorted_examples if str(row["example_id"]) not in benchmark_ids]
    train_rows, val_rows = split_examples_by_time(
        [
            ChartExample(
                example_id=row["example_id"],
                image_path=Path(row["image_path"]),
                embedding=np.zeros(config.active_embedding_dim, dtype=np.float32),
                text="",
                title=row["example_id"],
                source_type="phase2_dataset",
                time_index=row["time_index"],
                metadata={"detections": row["detections"]},
            )
            for row in trainable_examples
        ],
        validation_ratio=config.phase2.validation_ratio,
    )
    split_lookup = {row.example_id: "train" for row in train_rows}
    split_lookup.update({row.example_id: "val" for row in val_rows})

    class_counts = {index: 0 for index in range(len(YOLO_CLASS_NAMES))}
    exported_examples: list[dict[str, Any]] = []
    for row in trainable_examples:
        split = split_lookup[row["example_id"]]
        image_target_dir = config.paths.yolo_images_train_dir if split == "train" else config.paths.yolo_images_val_dir
        label_target_dir = config.paths.yolo_labels_train_dir if split == "train" else config.paths.yolo_labels_val_dir
        safe_name = row["example_id"].replace(":", "__").replace("/", "_")
        source_image = Path(row["image_path"])
        target_image = image_target_dir / f"{safe_name}{source_image.suffix}"
        target_label = label_target_dir / f"{safe_name}.txt"
        shutil.copy2(source_image, target_image)
        detections = [Detection(class_id=int(item["class_id"]), bbox=[float(value) for value in item["bbox"]]) for item in row["detections"]]
        target_label.write_text("\n".join(detections_to_yolo_lines(detections)), encoding="utf-8")
        for detection in detections:
            class_counts[detection.class_id] += 1
        exported_examples.append(
            {
                "example_id": row["example_id"],
                "split": split,
                "image_path": str(target_image),
                "label_path": str(target_label),
                "box_count": len(detections),
                "review_outcome": row["review_outcome"],
            }
        )

    benchmark_examples = _write_single_split_dataset(
        benchmark_rows,
        image_dir=config.paths.yolo_benchmark_images_dir,
        label_dir=config.paths.yolo_benchmark_labels_dir,
    )

    config.paths.yolo_data_yaml_path.write_text(
        "\n".join(
            [
                f"path: {config.paths.yolo_dir}",
                "train: images/train",
                "val: images/val",
                "names:",
                *[f"  {index}: {name}" for index, name in enumerate(YOLO_CLASS_NAMES)],
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    config.paths.yolo_benchmark_data_yaml_path.write_text(
        "\n".join(
            [
                f"path: {config.paths.yolo_benchmark_dir}",
                "train: images",
                "val: images",
                "names:",
                *[f"  {index}: {name}" for index, name in enumerate(YOLO_CLASS_NAMES)],
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    stats = {
        "dataset_dir": str(config.paths.yolo_dir),
        "train_count": sum(1 for row in exported_examples if row["split"] == "train"),
        "val_count": sum(1 for row in exported_examples if row["split"] == "val"),
        "benchmark_count": len(benchmark_examples),
        "benchmark_hard_negative_count": sum(1 for row in benchmark_examples if row.get("review_outcome") == "no_setup"),
        "class_counts": {YOLO_CLASS_NAMES[index]: count for index, count in class_counts.items() if count},
        "examples": exported_examples[:10],
        "benchmark_examples": benchmark_examples[:10],
        "benchmark_manifest_path": str(config.paths.benchmark_manifest_path),
    }
    config.paths.phase2_dataset_stats_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    return stats
