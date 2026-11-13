from __future__ import annotations

import argparse
import copy
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


DEFAULT_INPUT_TASKS = Path("results") / "controlled_charts" / "label_studio" / "tasks.json"
DEFAULT_OUTPUT_TASKS = Path("results") / "controlled_charts" / "label_studio" / "tasks_with_predictions.json"
DEFAULT_OUTPUT_REPORT = Path("results") / "controlled_charts" / "label_studio" / "prediction_report.json"
MODEL_VERSION = "opencv_visual_hints_v1"


def resolve(root_dir: Path, path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else root_dir / candidate


def relative_or_absolute(path: Path, root_dir: Path) -> str:
    try:
        return str(path.resolve().relative_to(root_dir.resolve()))
    except ValueError:
        return str(path)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def rectangle_result(
    *,
    label: str,
    image_width: int,
    image_height: int,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    score: float,
) -> dict[str, Any]:
    x1 = clamp(x1, 0, image_width - 1)
    y1 = clamp(y1, 0, image_height - 1)
    x2 = clamp(x2, x1 + 1, image_width)
    y2 = clamp(y2, y1 + 1, image_height)
    return {
        "from_name": "detections",
        "to_name": "image",
        "type": "rectanglelabels",
        "score": round(score, 4),
        "value": {
            "x": round((x1 / image_width) * 100.0, 4),
            "y": round((y1 / image_height) * 100.0, 4),
            "width": round(((x2 - x1) / image_width) * 100.0, 4),
            "height": round(((y2 - y1) / image_height) * 100.0, 4),
            "rectanglelabels": [label],
        },
        "meta": {
            "source": MODEL_VERSION,
            "review_only": True,
            "hint": "extreme_colored_price_pixels",
        },
    }


def image_path_from_task(task: dict[str, Any], *, root_dir: Path) -> Path:
    data = task.get("data", {}) if isinstance(task.get("data"), dict) else {}
    path_value = str(data.get("image_abs") or data.get("image") or "")
    return resolve(root_dir, path_value.replace("/", "\\"))


def detect_extreme_price_hints(image_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    image = cv2.imread(str(image_path))
    if image is None:
        return [], {"status": "missing_or_unreadable_image", "image_path": str(image_path)}
    height, width = image.shape[:2]
    top = int(height * 0.05)
    bottom = int(height * 0.62)
    left = int(width * 0.06)
    right = int(width * 0.94)
    roi = image[top:bottom, left:right]
    if roi.size == 0:
        return [], {"status": "empty_roi", "image_path": str(image_path), "width": width, "height": height}

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]
    # Candles are saturated red/teal in the generated charts. Gridlines/text are low saturation;
    # the lower volume panel is excluded by the fixed price-region crop above.
    mask = (saturation > 55) & (value > 35) & (value < 255)
    ys, xs = np.where(mask)
    if len(xs) < 25:
        return [], {
            "status": "not_enough_colored_price_pixels",
            "image_path": str(image_path),
            "colored_pixel_count": int(len(xs)),
            "width": width,
            "height": height,
        }

    xs = xs + left
    ys = ys + top
    min_y = int(np.min(ys))
    max_y = int(np.max(ys))
    price_range = max(1, bottom - top)
    extreme_band = max(3, int(price_range * 0.035))
    box_width = max(18, int(width * 0.022))
    box_height = max(22, int(price_range * 0.09))

    high_candidates = xs[ys <= min_y + extreme_band]
    low_candidates = xs[ys >= max_y - extreme_band]
    hints: list[dict[str, Any]] = []
    if len(high_candidates):
        high_x = float(np.median(high_candidates))
        hints.append(
            rectangle_result(
                label="liquidity_sweep_high",
                image_width=width,
                image_height=height,
                x1=high_x - (box_width / 2),
                y1=min_y - 4,
                x2=high_x + (box_width / 2),
                y2=min_y + box_height,
                score=0.24,
            )
        )
    if len(low_candidates):
        low_x = float(np.median(low_candidates))
        hints.append(
            rectangle_result(
                label="liquidity_sweep_low",
                image_width=width,
                image_height=height,
                x1=low_x - (box_width / 2),
                y1=max_y - box_height,
                x2=low_x + (box_width / 2),
                y2=max_y + 4,
                score=0.24,
            )
        )
    return hints, {
        "status": "hinted" if hints else "no_hints",
        "image_path": str(image_path),
        "width": width,
        "height": height,
        "colored_pixel_count": int(len(xs)),
        "price_roi": {"left": left, "top": top, "right": right, "bottom": bottom},
        "extreme_y": {"high": min_y, "low": max_y},
        "hint_count": len(hints),
    }


def build_labelstudio_preannotations(
    *,
    root_dir: Path,
    input_tasks_path: Path = DEFAULT_INPUT_TASKS,
    output_tasks_path: Path = DEFAULT_OUTPUT_TASKS,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    root_dir = root_dir.resolve()
    input_path = resolve(root_dir, input_tasks_path)
    raw_payload = read_json(input_path)
    tasks = raw_payload if isinstance(raw_payload, list) else raw_payload.get("tasks", [])
    if not isinstance(tasks, list):
        tasks = []

    output_tasks: list[dict[str, Any]] = []
    task_reports: list[dict[str, Any]] = []
    label_counts: Counter[str] = Counter()
    missing_images: list[str] = []
    for raw_task in tasks:
        if not isinstance(raw_task, dict):
            continue
        task = copy.deepcopy(raw_task)
        image_path = image_path_from_task(task, root_dir=root_dir)
        hints, hint_report = detect_extreme_price_hints(image_path)
        image_id = str((task.get("data") or {}).get("image_id") or task.get("id") or "")
        if hint_report["status"] == "missing_or_unreadable_image":
            missing_images.append(image_id or str(image_path))
        if hints:
            task["predictions"] = [
                {
                    "model_version": MODEL_VERSION,
                    "score": round(sum(float(hint.get("score") or 0.0) for hint in hints) / len(hints), 4),
                    "result": hints,
                }
            ]
            task.setdefault("meta", {})
            if isinstance(task["meta"], dict):
                task["meta"]["preannotation_policy"] = {
                    "source": MODEL_VERSION,
                    "review_only": True,
                    "training_eligible": False,
                    "requires_accept_or_adjust_annotation": True,
                }
            label_counts.update(
                str(result["value"]["rectanglelabels"][0])
                for result in hints
                if result.get("value", {}).get("rectanglelabels")
            )
        task_reports.append({"image_id": image_id, **hint_report})
        output_tasks.append(task)

    report = {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_tasks_path": relative_or_absolute(input_path, root_dir),
        "output_tasks_path": relative_or_absolute(resolve(root_dir, output_tasks_path), root_dir),
        "model_version": MODEL_VERSION,
        "review_policy": {
            "prediction_source": "opencv_visual_hints",
            "review_only": True,
            "training_eligible": False,
            "promotion_requires_labelstudio_annotation": True,
            "importer_ignores_predictions": True,
        },
        "task_count": len(output_tasks),
        "tasks_with_predictions": sum(1 for task in output_tasks if task.get("predictions")),
        "prediction_count": sum(
            len(prediction.get("result", []))
            for task in output_tasks
            for prediction in task.get("predictions", [])
            if isinstance(prediction, dict)
        ),
        "prediction_label_counts": dict(sorted(label_counts.items())),
        "missing_image_count": len(missing_images),
        "missing_images": missing_images,
        "task_reports": task_reports,
    }
    return output_tasks, report


def write_outputs(
    tasks: list[dict[str, Any]],
    report: dict[str, Any],
    *,
    root_dir: Path,
    output_tasks_path: Path,
    output_report_path: Path,
) -> None:
    tasks_path = resolve(root_dir, output_tasks_path)
    report_path = resolve(root_dir, output_report_path)
    tasks_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    tasks_path.write_text(json.dumps(tasks, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build review-only Label Studio preannotations for controlled charts.")
    parser.add_argument("--root-dir", type=Path, default=Path("."))
    parser.add_argument("--input-tasks", type=Path, default=DEFAULT_INPUT_TASKS)
    parser.add_argument("--output-tasks", type=Path, default=DEFAULT_OUTPUT_TASKS)
    parser.add_argument("--output-report", type=Path, default=DEFAULT_OUTPUT_REPORT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root_dir = args.root_dir.resolve()
    tasks, report = build_labelstudio_preannotations(
        root_dir=root_dir,
        input_tasks_path=args.input_tasks,
        output_tasks_path=args.output_tasks,
    )
    write_outputs(
        tasks,
        report,
        root_dir=root_dir,
        output_tasks_path=args.output_tasks,
        output_report_path=args.output_report,
    )
    print(
        "Built controlled-chart Label Studio preannotations: "
        f"{relative_or_absolute(resolve(root_dir, args.output_tasks), root_dir)} "
        f"tasks_with_predictions={report['tasks_with_predictions']} "
        f"predictions={report['prediction_count']}"
    )


if __name__ == "__main__":
    main()
