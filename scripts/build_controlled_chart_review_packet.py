from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


DEFAULT_INPUT_TASKS = Path("results") / "controlled_charts" / "label_studio" / "tasks_with_predictions.json"
DEFAULT_OUTPUT_DIR = Path("results") / "controlled_charts" / "label_studio" / "review_packet"
DEFAULT_CONTACT_SHEET = "controlled_chart_prediction_contact_sheet.jpg"
DEFAULT_REPORT = "controlled_chart_review_packet.json"
LABEL_COLORS = {
    "liquidity_sweep_high": (220, 60, 60),
    "liquidity_sweep_low": (40, 130, 220),
    "protected_swing": (95, 170, 75),
    "bullish_reaction_zone": (30, 160, 120),
    "bearish_reaction_zone": (190, 120, 40),
}


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


def safe_name(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value)
    return cleaned.strip("_") or "controlled_chart"


def task_image_path(task: dict[str, Any], *, root_dir: Path) -> Path:
    data = task.get("data", {}) if isinstance(task.get("data"), dict) else {}
    path_value = str(data.get("image_abs") or data.get("image") or "")
    return resolve(root_dir, path_value.replace("/", "\\"))


def task_image_id(task: dict[str, Any]) -> str:
    data = task.get("data", {}) if isinstance(task.get("data"), dict) else {}
    return str(data.get("image_id") or task.get("id") or "").strip()


def prediction_results(task: dict[str, Any]) -> list[dict[str, Any]]:
    predictions = task.get("predictions", [])
    if not isinstance(predictions, list):
        return []
    results: list[dict[str, Any]] = []
    for prediction in predictions:
        if not isinstance(prediction, dict):
            continue
        prediction_results = prediction.get("result", [])
        if isinstance(prediction_results, list):
            results.extend(result for result in prediction_results if isinstance(result, dict))
    return results


def rectangle_from_result(result: dict[str, Any], *, image_width: int, image_height: int) -> dict[str, Any] | None:
    if str(result.get("type") or "") != "rectanglelabels":
        return None
    value = result.get("value", {})
    if not isinstance(value, dict):
        return None
    labels = value.get("rectanglelabels", [])
    if not isinstance(labels, list) or not labels:
        return None
    try:
        x = float(value["x"])
        y = float(value["y"])
        width = float(value["width"])
        height = float(value["height"])
    except (KeyError, TypeError, ValueError):
        return None
    x1 = max(0, int(round((x / 100.0) * image_width)))
    y1 = max(0, int(round((y / 100.0) * image_height)))
    x2 = min(image_width - 1, int(round(((x + width) / 100.0) * image_width)))
    y2 = min(image_height - 1, int(round(((y + height) / 100.0) * image_height)))
    if x2 <= x1 or y2 <= y1:
        return None
    return {
        "label": str(labels[0]),
        "score": float(result.get("score") or 0.0),
        "bbox_xyxy": [x1, y1, x2, y2],
    }


def draw_overlay(
    *,
    image_path: Path,
    output_path: Path,
    results: list[dict[str, Any]],
) -> tuple[bool, list[dict[str, Any]]]:
    if not image_path.exists():
        return False, []
    image = Image.open(image_path).convert("RGB")
    width, height = image.size
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    rectangles = [
        rectangle
        for rectangle in (rectangle_from_result(result, image_width=width, image_height=height) for result in results)
        if rectangle is not None
    ]
    line_width = max(2, int(round(min(width, height) / 280)))
    for index, rectangle in enumerate(rectangles, start=1):
        label = rectangle["label"]
        color = LABEL_COLORS.get(label, (180, 80, 220))
        x1, y1, x2, y2 = rectangle["bbox_xyxy"]
        draw.rectangle((x1, y1, x2, y2), outline=color, width=line_width)
        caption = f"{index} {label.replace('_', ' ')}"
        text_y = max(0, y1 - 14)
        text_box = draw.textbbox((x1, text_y), caption, font=font)
        draw.rectangle(text_box, fill=(255, 255, 255))
        draw.text((x1, text_y), caption, fill=color, font=font)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, quality=92)
    return True, rectangles


def fit_image(image: Image.Image, *, max_width: int, max_height: int) -> Image.Image:
    fitted = image.copy()
    fitted.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
    return fitted


def build_contact_sheet(
    *,
    items: list[dict[str, Any]],
    root_dir: Path,
    output_path: Path,
    columns: int = 3,
    cell_width: int = 480,
    cell_height: int = 350,
) -> None:
    rows = max(1, math.ceil(len(items) / columns))
    sheet = Image.new("RGB", (columns * cell_width, rows * cell_height), "white")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for index, item in enumerate(items):
        row = index // columns
        col = index % columns
        x0 = col * cell_width
        y0 = row * cell_height
        overlay_path = resolve(root_dir, item["overlay_path"])
        if overlay_path.exists():
            image = fit_image(Image.open(overlay_path).convert("RGB"), max_width=cell_width - 24, max_height=cell_height - 68)
            sheet.paste(image, (x0 + 12, y0 + 54))
        title = f"{item['symbol']} {item['timeframe']} | hints {item['prediction_count']}"
        subtitle = item["image_id"][:58]
        draw.rectangle((x0, y0, x0 + cell_width - 1, y0 + cell_height - 1), outline=(210, 210, 210), width=1)
        draw.text((x0 + 12, y0 + 10), title, fill=(20, 20, 20), font=font)
        draw.text((x0 + 12, y0 + 28), subtitle, fill=(70, 70, 70), font=font)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path, quality=92)


def build_review_packet(
    *,
    root_dir: Path,
    input_tasks_path: Path = DEFAULT_INPUT_TASKS,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    root_dir = root_dir.resolve()
    input_path = resolve(root_dir, input_tasks_path)
    resolved_output_dir = resolve(root_dir, output_dir)
    overlay_dir = resolved_output_dir / "overlays"
    raw_payload = read_json(input_path)
    tasks = raw_payload if isinstance(raw_payload, list) else raw_payload.get("tasks", [])
    if not isinstance(tasks, list):
        tasks = []

    items: list[dict[str, Any]] = []
    label_counts: Counter[str] = Counter()
    missing_images: list[str] = []
    for index, task in enumerate(tasks, start=1):
        if not isinstance(task, dict):
            continue
        image_id = task_image_id(task) or f"controlled_chart_{index:04d}"
        data = task.get("data", {}) if isinstance(task.get("data"), dict) else {}
        image_path = task_image_path(task, root_dir=root_dir)
        results = prediction_results(task)
        overlay_path = overlay_dir / f"{index:03d}_{safe_name(image_id)}.jpg"
        ok, rectangles = draw_overlay(image_path=image_path, output_path=overlay_path, results=results)
        if not ok:
            missing_images.append(image_id)
            overlay_value = ""
        else:
            overlay_value = relative_or_absolute(overlay_path, root_dir)
        labels = [rectangle["label"] for rectangle in rectangles]
        label_counts.update(labels)
        items.append(
            {
                "rank": index,
                "image_id": image_id,
                "symbol": str(data.get("symbol") or ""),
                "contract": str(data.get("contract") or ""),
                "timeframe": str(data.get("timeframe") or ""),
                "image_path": relative_or_absolute(image_path, root_dir),
                "overlay_path": overlay_value,
                "prediction_count": len(rectangles),
                "prediction_labels": labels,
                "rectangles": rectangles,
                "review_action_required": "accept_adjust_reject_or_defer",
                "training_eligible": False,
            }
        )

    contact_sheet_path = resolved_output_dir / DEFAULT_CONTACT_SHEET
    build_contact_sheet(
        items=[item for item in items if item.get("overlay_path")],
        root_dir=root_dir,
        output_path=contact_sheet_path,
    )
    report = {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_tasks_path": relative_or_absolute(input_path, root_dir),
        "output_dir": relative_or_absolute(resolved_output_dir, root_dir),
        "contact_sheet_path": relative_or_absolute(contact_sheet_path, root_dir),
        "overlay_dir": relative_or_absolute(overlay_dir, root_dir),
        "review_policy": {
            "source": "label_studio_predictions",
            "review_only": True,
            "training_eligible": False,
            "promotion_requires_labelstudio_accept_or_adjust": True,
        },
        "summary": {
            "task_count": len(tasks),
            "overlay_count": sum(1 for item in items if item.get("overlay_path")),
            "prediction_count": sum(item["prediction_count"] for item in items),
            "prediction_label_counts": dict(sorted(label_counts.items())),
            "missing_image_count": len(missing_images),
            "missing_images": missing_images,
        },
        "items": items,
    }
    return report


def write_report(report: dict[str, Any], *, root_dir: Path, output_dir: Path) -> None:
    resolved_output_dir = resolve(root_dir, output_dir)
    resolved_output_dir.mkdir(parents=True, exist_ok=True)
    (resolved_output_dir / DEFAULT_REPORT).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a controlled-chart visual review packet from Label Studio predictions.")
    parser.add_argument("--root-dir", type=Path, default=Path("."))
    parser.add_argument("--input-tasks", type=Path, default=DEFAULT_INPUT_TASKS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root_dir = args.root_dir.resolve()
    report = build_review_packet(
        root_dir=root_dir,
        input_tasks_path=args.input_tasks,
        output_dir=args.output_dir,
    )
    write_report(report, root_dir=root_dir, output_dir=args.output_dir)
    print(
        "Built controlled-chart review packet: "
        f"{report['contact_sheet_path']} "
        f"overlays={report['summary']['overlay_count']} "
        f"predictions={report['summary']['prediction_count']}"
    )


if __name__ == "__main__":
    main()
