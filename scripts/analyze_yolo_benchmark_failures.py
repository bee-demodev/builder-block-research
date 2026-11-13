from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from config import YOLO_CLASS_NAMES


@dataclass(frozen=True)
class Box:
    class_id: int
    class_name: str
    xyxy: tuple[float, float, float, float]
    confidence: float | None = None


@dataclass(frozen=True)
class LetterboxMeta:
    ratio: float
    pad_x: float
    pad_y: float
    original_width: int
    original_height: int
    size: int


def load_yolo_labels(label_path: Path, *, image_width: int, image_height: int) -> list[Box]:
    if not label_path.exists():
        return []
    labels: list[Box] = []
    for line in label_path.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split()
        if len(parts) < 5:
            continue
        class_id = int(float(parts[0]))
        x_center, y_center, width, height = [float(value) for value in parts[1:5]]
        x1 = (x_center - width / 2.0) * image_width
        y1 = (y_center - height / 2.0) * image_height
        x2 = (x_center + width / 2.0) * image_width
        y2 = (y_center + height / 2.0) * image_height
        labels.append(
            Box(
                class_id=class_id,
                class_name=YOLO_CLASS_NAMES[class_id] if class_id < len(YOLO_CLASS_NAMES) else str(class_id),
                xyxy=(x1, y1, x2, y2),
            )
        )
    return labels


def letterbox_meta(image_width: int, image_height: int, *, size: int = 1024) -> LetterboxMeta:
    ratio = min(size / image_height, size / image_width)
    resized_width = round(image_width * ratio)
    resized_height = round(image_height * ratio)
    return LetterboxMeta(
        ratio=ratio,
        pad_x=(size - resized_width) / 2.0,
        pad_y=(size - resized_height) / 2.0,
        original_width=image_width,
        original_height=image_height,
        size=size,
    )


def scale_prediction_to_original(
    xyxy: tuple[float, float, float, float],
    meta: LetterboxMeta,
) -> tuple[float, float, float, float]:
    x1, y1, x2, y2 = xyxy
    scaled = (
        (x1 - meta.pad_x) / meta.ratio,
        (y1 - meta.pad_y) / meta.ratio,
        (x2 - meta.pad_x) / meta.ratio,
        (y2 - meta.pad_y) / meta.ratio,
    )
    return (
        max(0.0, min(float(meta.original_width), scaled[0])),
        max(0.0, min(float(meta.original_height), scaled[1])),
        max(0.0, min(float(meta.original_width), scaled[2])),
        max(0.0, min(float(meta.original_height), scaled[3])),
    )


def box_iou(left: Box, right: Box) -> float:
    ax1, ay1, ax2, ay2 = left.xyxy
    bx1, by1, bx2, by2 = right.xyxy
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    inter_width = max(0.0, ix2 - ix1)
    inter_height = max(0.0, iy2 - iy1)
    intersection = inter_width * inter_height
    left_area = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    right_area = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = left_area + right_area - intersection
    return 0.0 if union <= 0.0 else intersection / union


def match_predictions(
    labels: list[Box],
    predictions: list[Box],
    *,
    iou_threshold: float = 0.5,
) -> tuple[list[tuple[int, int, float]], list[int], list[int]]:
    candidates: list[tuple[float, float, int, int]] = []
    for label_index, label in enumerate(labels):
        for prediction_index, prediction in enumerate(predictions):
            if label.class_id != prediction.class_id:
                continue
            iou = box_iou(label, prediction)
            if iou >= iou_threshold:
                candidates.append((iou, prediction.confidence or 0.0, label_index, prediction_index))
    candidates.sort(reverse=True)

    used_labels: set[int] = set()
    used_predictions: set[int] = set()
    matches: list[tuple[int, int, float]] = []
    for iou, _confidence, label_index, prediction_index in candidates:
        if label_index in used_labels or prediction_index in used_predictions:
            continue
        used_labels.add(label_index)
        used_predictions.add(prediction_index)
        matches.append((label_index, prediction_index, iou))

    unmatched_labels = [index for index in range(len(labels)) if index not in used_labels]
    unmatched_predictions = [index for index in range(len(predictions)) if index not in used_predictions]
    return matches, unmatched_labels, unmatched_predictions


def summarize_example(
    *,
    manifest_item: dict[str, Any],
    image_path: Path,
    label_path: Path,
    overlay_path: Path | None,
    labels: list[Box],
    predictions: list[Box],
    iou_threshold: float,
) -> dict[str, Any]:
    matches, unmatched_labels, unmatched_predictions = match_predictions(
        labels,
        predictions,
        iou_threshold=iou_threshold,
    )
    false_negative_classes = [labels[index].class_name for index in unmatched_labels]
    false_positive_classes = [predictions[index].class_name for index in unmatched_predictions]
    expected_classes = [label.class_name for label in labels]
    predicted_classes = [prediction.class_name for prediction in predictions]
    hard_negative = bool(manifest_item.get("hard_negative"))
    reasons: list[str] = []
    if hard_negative and predictions:
        reasons.append("hard_negative_false_positive")
    if false_negative_classes:
        reasons.append("false_negative")
    if false_positive_classes and not hard_negative:
        reasons.append("false_positive")
    weak_classes = {"liquidity_sweep_high", "bullish_reaction_zone"}
    if any(class_name in weak_classes for class_name in false_negative_classes):
        reasons.append("weak_class_miss")

    priority = 0.0
    if "hard_negative_false_positive" in reasons:
        priority += 100.0
    if "weak_class_miss" in reasons:
        priority += 70.0
    if "false_negative" in reasons:
        priority += 50.0 + len(false_negative_classes)
    if "false_positive" in reasons:
        priority += 25.0 + len(false_positive_classes)
    max_confidence = max((prediction.confidence or 0.0 for prediction in predictions), default=0.0)
    priority += max_confidence

    return {
        "example_id": manifest_item.get("example_id"),
        "safe_name": manifest_item.get("safe_name") or image_path.stem,
        "hard_negative": hard_negative,
        "review_outcome": manifest_item.get("review_outcome"),
        "image_path": str(image_path),
        "label_path": str(label_path),
        "overlay_path": str(overlay_path) if overlay_path is not None and overlay_path.exists() else None,
        "expected_classes": expected_classes,
        "predicted_classes": predicted_classes,
        "matched_count": len(matches),
        "label_count": len(labels),
        "prediction_count": len(predictions),
        "false_negative_classes": false_negative_classes,
        "false_positive_classes": false_positive_classes,
        "max_prediction_confidence": round(max_confidence, 6),
        "priority": round(priority, 6),
        "reasons": reasons,
        "matches": [
            {
                "label_index": label_index,
                "prediction_index": prediction_index,
                "iou": round(iou, 6),
                "class_name": labels[label_index].class_name,
                "confidence": predictions[prediction_index].confidence,
            }
            for label_index, prediction_index, iou in matches
        ],
    }


def _build_letterboxed_input(image_path: Path, *, size: int):
    import cv2
    import numpy as np

    image = cv2.imread(str(image_path))
    if image is None:
        raise RuntimeError(f"Could not read image: {image_path}")
    original_height, original_width = image.shape[:2]
    meta = letterbox_meta(original_width, original_height, size=size)
    resized = cv2.resize(
        image,
        (round(original_width * meta.ratio), round(original_height * meta.ratio)),
        interpolation=cv2.INTER_LINEAR,
    )
    top = int(round(meta.pad_y - 0.1))
    bottom = int(round(meta.pad_y + 0.1))
    left = int(round(meta.pad_x - 0.1))
    right = int(round(meta.pad_x + 0.1))
    padded = cv2.copyMakeBorder(
        resized,
        top,
        bottom,
        left,
        right,
        cv2.BORDER_CONSTANT,
        value=(114, 114, 114),
    )
    rgb = padded[:, :, ::-1]
    tensor = rgb.transpose(2, 0, 1).astype("float32") / 255.0
    return np.expand_dims(tensor, axis=0), meta


def predict_onnx(
    session: Any,
    image_path: Path,
    *,
    image_size: int,
    confidence_threshold: float,
) -> list[Box]:
    input_tensor, meta = _build_letterboxed_input(image_path, size=image_size)
    input_name = session.get_inputs()[0].name
    output = session.run(None, {input_name: input_tensor})[0][0]
    predictions: list[Box] = []
    for row in output:
        confidence = float(row[4])
        if confidence < confidence_threshold:
            continue
        class_id = int(row[5])
        if class_id < 0 or class_id >= len(YOLO_CLASS_NAMES):
            continue
        xyxy = scale_prediction_to_original(
            (float(row[0]), float(row[1]), float(row[2]), float(row[3])),
            meta,
        )
        predictions.append(
            Box(
                class_id=class_id,
                class_name=YOLO_CLASS_NAMES[class_id],
                xyxy=xyxy,
                confidence=round(confidence, 6),
            )
        )
    predictions.sort(key=lambda box: box.confidence or 0.0, reverse=True)
    return predictions


def load_manifest_items(manifest_path: Path) -> list[dict[str, Any]]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    items = payload.get("items", [])
    return [item for item in items if isinstance(item, dict)]


def class_counts(boxes: Iterable[Box]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for box in boxes:
        counts[box.class_name] = counts.get(box.class_name, 0) + 1
    return dict(sorted(counts.items()))


def build_failure_report(
    *,
    model_path: Path,
    benchmark_images_dir: Path,
    benchmark_labels_dir: Path,
    manifest_path: Path,
    overlay_dir: Path | None,
    image_size: int,
    confidence_threshold: float,
    iou_threshold: float,
) -> dict[str, Any]:
    import cv2
    import onnxruntime as ort

    session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
    items = load_manifest_items(manifest_path)
    examples: list[dict[str, Any]] = []
    aggregate_expected: dict[str, int] = {}
    aggregate_false_negatives: dict[str, int] = {}
    aggregate_false_positives: dict[str, int] = {}
    hard_negative_count = 0
    hard_negative_false_positive_count = 0

    for item in items:
        safe_name = str(item.get("safe_name") or "").strip()
        if not safe_name:
            continue
        image_path = benchmark_images_dir / f"{safe_name}.jpg"
        label_path = benchmark_labels_dir / f"{safe_name}.txt"
        overlay_path = overlay_dir / f"{safe_name}.jpg" if overlay_dir is not None else None
        image = cv2.imread(str(image_path))
        if image is None:
            continue
        image_height, image_width = image.shape[:2]
        labels = load_yolo_labels(label_path, image_width=image_width, image_height=image_height)
        predictions = predict_onnx(
            session,
            image_path,
            image_size=image_size,
            confidence_threshold=confidence_threshold,
        )
        summary = summarize_example(
            manifest_item=item,
            image_path=image_path,
            label_path=label_path,
            overlay_path=overlay_path,
            labels=labels,
            predictions=predictions,
            iou_threshold=iou_threshold,
        )
        examples.append(summary)
        for class_name, count in class_counts(labels).items():
            aggregate_expected[class_name] = aggregate_expected.get(class_name, 0) + count
        for class_name in summary["false_negative_classes"]:
            aggregate_false_negatives[class_name] = aggregate_false_negatives.get(class_name, 0) + 1
        for class_name in summary["false_positive_classes"]:
            aggregate_false_positives[class_name] = aggregate_false_positives.get(class_name, 0) + 1
        if summary["hard_negative"]:
            hard_negative_count += 1
            if summary["prediction_count"] > 0:
                hard_negative_false_positive_count += 1

    review_queue = sorted(
        [example for example in examples if example["priority"] > 0],
        key=lambda example: (example["priority"], example["max_prediction_confidence"]),
        reverse=True,
    )
    return {
        "model_path": str(model_path),
        "benchmark_images_dir": str(benchmark_images_dir),
        "manifest_path": str(manifest_path),
        "image_size": image_size,
        "confidence_threshold": confidence_threshold,
        "iou_threshold": iou_threshold,
        "example_count": len(examples),
        "review_queue_count": len(review_queue),
        "expected_by_class": dict(sorted(aggregate_expected.items())),
        "false_negatives_by_class": dict(sorted(aggregate_false_negatives.items())),
        "false_positives_by_class": dict(sorted(aggregate_false_positives.items())),
        "hard_negative_count": hard_negative_count,
        "hard_negative_false_positive_count": hard_negative_false_positive_count,
        "hard_negative_false_positive_rate": (
            0.0 if hard_negative_count == 0 else round(hard_negative_false_positive_count / hard_negative_count, 6)
        ),
        "review_queue": review_queue,
        "examples": examples,
    }


def write_queue_csv(report: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "rank",
        "priority",
        "reasons",
        "example_id",
        "safe_name",
        "hard_negative",
        "expected_classes",
        "predicted_classes",
        "false_negative_classes",
        "false_positive_classes",
        "matched_count",
        "label_count",
        "prediction_count",
        "max_prediction_confidence",
        "image_path",
        "overlay_path",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for rank, example in enumerate(report["review_queue"], start=1):
            writer.writerow(
                {
                    "rank": rank,
                    "priority": example["priority"],
                    "reasons": ",".join(example["reasons"]),
                    "example_id": example["example_id"],
                    "safe_name": example["safe_name"],
                    "hard_negative": example["hard_negative"],
                    "expected_classes": ",".join(example["expected_classes"]),
                    "predicted_classes": ",".join(example["predicted_classes"]),
                    "false_negative_classes": ",".join(example["false_negative_classes"]),
                    "false_positive_classes": ",".join(example["false_positive_classes"]),
                    "matched_count": example["matched_count"],
                    "label_count": example["label_count"],
                    "prediction_count": example["prediction_count"],
                    "max_prediction_confidence": example["max_prediction_confidence"],
                    "image_path": example["image_path"],
                    "overlay_path": example["overlay_path"],
                }
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a per-image benchmark failure queue from a YOLO ONNX model.")
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--benchmark-images-dir", type=Path, default=Path("dataset/yolo_benchmark/images"))
    parser.add_argument("--benchmark-labels-dir", type=Path, default=Path("dataset/yolo_benchmark/labels"))
    parser.add_argument("--manifest", type=Path, default=Path("results/benchmark_manifest.json"))
    parser.add_argument("--overlay-dir", type=Path)
    parser.add_argument("--image-size", type=int, default=1024)
    parser.add_argument("--confidence-threshold", type=float, default=0.001)
    parser.add_argument("--iou-threshold", type=float, default=0.5)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_failure_report(
        model_path=args.model,
        benchmark_images_dir=args.benchmark_images_dir,
        benchmark_labels_dir=args.benchmark_labels_dir,
        manifest_path=args.manifest,
        overlay_dir=args.overlay_dir,
        image_size=args.image_size,
        confidence_threshold=args.confidence_threshold,
        iou_threshold=args.iou_threshold,
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    write_queue_csv(report, args.output_csv)
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "example_count",
                    "review_queue_count",
                    "false_negatives_by_class",
                    "false_positives_by_class",
                    "hard_negative_false_positive_count",
                    "hard_negative_false_positive_rate",
                )
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
