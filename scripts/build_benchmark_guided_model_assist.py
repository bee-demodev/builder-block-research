from __future__ import annotations

import argparse
import html
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import YOLO_CLASS_NAMES
from scripts.analyze_yolo_benchmark_failures import Box, predict_onnx


DEFAULT_PACKET_PATH = Path("results") / "benchmark_guided_corpus_review_batch_conf025.json"
DEFAULT_OUTPUT_DIR = Path("results") / "benchmark_guided_model_assist_conf025"
DEFAULT_OUTPUT_ANSWERS = Path("results") / "benchmark_guided_corpus_review_answers.model_suggestions_conf025.json"
DEFAULT_MODEL_PATH = Path("models") / "yolo26_ttrades_markup_best.onnx"


@dataclass(slots=True)
class ModelAssistConfig:
    root_dir: Path
    packet_path: Path = DEFAULT_PACKET_PATH
    model_path: Path = DEFAULT_MODEL_PATH
    output_dir: Path = DEFAULT_OUTPUT_DIR
    output_answers_path: Path = DEFAULT_OUTPUT_ANSWERS
    image_size: int = 1024
    confidence_threshold: float = 0.20
    max_predictions_per_image: int = 8


Predictor = Callable[[Path], list[Box]]


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def resolve(root_dir: Path, path: Path | str) -> Path:
    value = Path(path)
    return value if value.is_absolute() else root_dir / value


def relative_or_absolute(path: Path, root_dir: Path) -> str:
    try:
        return str(path.resolve().relative_to(root_dir.resolve()))
    except ValueError:
        return str(path)


def safe_name(value: str, *, suffix: str = ".jpg") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    cleaned = re.sub(r"_+", "_", cleaned)
    return f"{cleaned[:180] or 'item'}{suffix}"


def normalized_candidate_labels(item: dict[str, Any]) -> list[str]:
    labels = []
    for value in item.get("candidate_labels", []) or []:
        label = str(value).strip()
        if label in YOLO_CLASS_NAMES and label not in labels:
            labels.append(label)
    return labels


def xyxy_to_normalized_bbox(box: Box, *, image_width: int, image_height: int) -> list[float] | None:
    x1, y1, x2, y2 = box.xyxy
    if image_width <= 0 or image_height <= 0:
        return None
    x1 = max(0.0, min(float(image_width), float(x1)))
    y1 = max(0.0, min(float(image_height), float(y1)))
    x2 = max(0.0, min(float(image_width), float(x2)))
    y2 = max(0.0, min(float(image_height), float(y2)))
    width = max(0.0, x2 - x1)
    height = max(0.0, y2 - y1)
    if width <= 0.0 or height <= 0.0:
        return None
    return [
        round((x1 + width / 2.0) / image_width, 6),
        round((y1 + height / 2.0) / image_height, 6),
        round(width / image_width, 6),
        round(height / image_height, 6),
    ]


def prediction_to_payload(box: Box, *, image_width: int, image_height: int) -> dict[str, Any] | None:
    bbox = xyxy_to_normalized_bbox(box, image_width=image_width, image_height=image_height)
    if bbox is None:
        return None
    return {
        "class_id": int(box.class_id),
        "class_name": str(box.class_name),
        "bbox": bbox,
        "confidence": round(float(box.confidence or 0.0), 6),
    }


def make_predictor(config: ModelAssistConfig) -> Predictor:
    import onnxruntime as ort

    model_path = resolve(config.root_dir, config.model_path)
    session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])

    def _predict(image_path: Path) -> list[Box]:
        return predict_onnx(
            session,
            image_path,
            image_size=config.image_size,
            confidence_threshold=config.confidence_threshold,
        )

    return _predict


def draw_model_overlay(image_path: Path, predictions: list[dict[str, Any]], output_path: Path) -> bool:
    try:
        import cv2
    except ImportError:  # pragma: no cover
        return False
    image = cv2.imread(str(image_path))
    if image is None:
        return False
    height, width = image.shape[:2]
    for index, prediction in enumerate(predictions, start=1):
        cx, cy, bw, bh = [float(value) for value in prediction["bbox"]]
        x1 = max(0, int((cx - bw / 2.0) * width))
        y1 = max(0, int((cy - bh / 2.0) * height))
        x2 = min(width - 1, int((cx + bw / 2.0) * width))
        y2 = min(height - 1, int((cy + bh / 2.0) * height))
        matched = bool(prediction.get("candidate_matched"))
        color = (80, 220, 120) if matched else (90, 120, 245)
        cv2.rectangle(image, (x1, y1), (x2, y2), color, thickness=2)
        label = f"M{index} {str(prediction['class_name']).replace('_', ' ')[:14]} {float(prediction['confidence']):.2f}"
        cv2.putText(image, label, (x1, max(16, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return bool(cv2.imwrite(str(output_path), image))


def image_src(path: Path, *, html_path: Path, root_dir: Path) -> str:
    try:
        return Path(*path.resolve().relative_to(html_path.parent.resolve()).parts).as_posix()
    except ValueError:
        try:
            return Path("..", "..", *path.resolve().relative_to(root_dir.resolve()).parts).as_posix()
        except ValueError:
            return path.as_uri()


def build_dashboard(rows: list[dict[str, Any]], report: dict[str, Any], *, root_dir: Path, output_dir: Path) -> str:
    cards: list[str] = []
    html_path = output_dir / "index.html"
    sorted_rows = sorted(
        rows,
        key=lambda row: (
            -int(row.get("model_candidate_matched_count", 0)),
            -int(row.get("model_prediction_count", 0)),
            int(row.get("review_rank", 9999) or 9999),
        ),
    )
    for row in sorted_rows:
        raw_overlay_path = str(row.get("model_overlay_path") or "").strip()
        overlay_path = Path(raw_overlay_path) if raw_overlay_path else None
        source_path = resolve(root_dir, str(row.get("image_path", "")))
        media_path = overlay_path if overlay_path is not None and overlay_path.exists() else source_path
        labels = "".join(f"<span>{html.escape(str(label))}</span>" for label in row.get("candidate_labels", []))
        predictions_json = json.dumps(row.get("model_assist", {}), indent=2)
        cards.append(
            f"""
            <article class="card {'has-match' if row.get('model_candidate_matched_count') else 'no-match'}">
              <div class="media"><img src="{html.escape(image_src(media_path, html_path=html_path, root_dir=root_dir))}" alt="{html.escape(str(row.get('example_id', '')))}" loading="lazy" /></div>
              <div class="body">
                <div class="rank">#{html.escape(str(row.get('review_rank', '')))} | matched {html.escape(str(row.get('model_candidate_matched_count', 0)))} | predictions {html.escape(str(row.get('model_prediction_count', 0)))}</div>
                <h2>{html.escape(str(row.get('example_id', '')))}</h2>
                <p>{html.escape(str(row.get('recommended_action', '')))} | guided score {html.escape(str(row.get('score', '')))}</p>
                <p class="chips">{labels}</p>
                <details open><summary>Model Assist</summary><pre>{html.escape(predictions_json)}</pre></details>
              </div>
            </article>
            """
        )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Benchmark-Guided Model Assist</title>
<style>
:root {{ color-scheme: dark; font-family: Inter, system-ui, sans-serif; background: #101416; color: #eef3f1; }}
body {{ margin: 0; background: #101416; }}
header {{ position: sticky; top: 0; z-index: 2; padding: 14px 18px; background: #172023; border-bottom: 1px solid #314043; }}
h1 {{ margin: 0 0 4px; font-size: 20px; }}
header p {{ margin: 0; color: #b8c8c5; font-size: 13px; }}
main {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(560px, 1fr)); gap: 12px; padding: 12px; }}
.card {{ display: grid; grid-template-columns: minmax(260px, 45%) 1fr; min-height: 360px; border: 1px solid #2e3d40; background: #151d20; border-radius: 8px; overflow: hidden; }}
.card.has-match {{ border-color: #65894a; }}
.media {{ background: #080b0c; display: flex; align-items: center; justify-content: center; }}
img {{ width: 100%; height: 100%; object-fit: contain; display: block; }}
.body {{ padding: 12px; min-width: 0; }}
.rank, p {{ color: #b8c8c5; font-size: 12px; }}
h2 {{ font-size: 14px; line-height: 1.25; overflow-wrap: anywhere; }}
.chips span {{ display: inline-block; margin: 0 5px 5px 0; padding: 3px 7px; border: 1px solid #4f696d; border-radius: 999px; color: #d8fffb; background: #213235; }}
pre {{ white-space: pre-wrap; overflow-wrap: anywhere; background: #0d1214; border: 1px solid #263235; border-radius: 6px; padding: 8px; font-size: 12px; }}
summary {{ cursor: pointer; font-size: 12px; font-weight: 650; }}
@media (max-width: 720px) {{ main {{ grid-template-columns: 1fr; }} .card {{ grid-template-columns: 1fr; }} .media {{ min-height: 260px; }} }}
</style>
</head>
<body>
<header>
<h1>Benchmark-Guided Model Assist</h1>
<p>{report["item_count"]} rows | candidate matches {report["rows_with_candidate_matches"]} | any predictions {report["rows_with_any_predictions"]} | review-only, not labels</p>
</header>
<main>
{''.join(cards)}
</main>
</body>
</html>
"""


def build_model_assist(
    config: ModelAssistConfig,
    *,
    predictor: Predictor | None = None,
    draw_overlays: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    root_dir = config.root_dir.resolve()
    packet_path = resolve(root_dir, config.packet_path)
    model_path = resolve(root_dir, config.model_path)
    output_dir = resolve(root_dir, config.output_dir)
    overlay_dir = output_dir / "overlays"
    packet = load_json(packet_path, {})
    items = [item for item in packet.get("items", []) if isinstance(item, dict)]
    predictor = predictor or make_predictor(config)

    rows: list[dict[str, Any]] = []
    answer_items: list[dict[str, Any]] = []
    any_prediction_count = 0
    candidate_match_count = 0
    hard_negative_prediction_count = 0
    matched_class_counts: Counter[str] = Counter()
    unexpected_class_counts: Counter[str] = Counter()
    prediction_errors: Counter[str] = Counter()

    for item in items:
        example_id = str(item.get("example_id", "")).strip()
        image_path = resolve(root_dir, str(item.get("image_path", "")))
        candidate_labels = normalized_candidate_labels(item)
        predictions: list[Box] = []
        if not image_path.exists():
            prediction_errors["missing_image"] += 1
        else:
            try:
                predictions = predictor(image_path)[: config.max_predictions_per_image]
            except Exception:
                prediction_errors["predict_failed"] += 1
                predictions = []

        image_width = 0
        image_height = 0
        if image_path.exists():
            try:
                import cv2

                image = cv2.imread(str(image_path))
                if image is not None:
                    image_height, image_width = image.shape[:2]
            except ImportError:  # pragma: no cover
                image_width = image_height = 0

        prediction_payloads: list[dict[str, Any]] = []
        for box in predictions:
            payload = prediction_to_payload(box, image_width=image_width, image_height=image_height)
            if payload is None:
                continue
            payload["candidate_matched"] = not candidate_labels or payload["class_name"] in candidate_labels
            prediction_payloads.append(payload)

        matched_predictions = [payload for payload in prediction_payloads if payload["candidate_matched"]]
        unexpected_predictions = [payload for payload in prediction_payloads if not payload["candidate_matched"]]
        if prediction_payloads:
            any_prediction_count += 1
            if item.get("recommended_action") == "hard_negative_review" or not candidate_labels:
                hard_negative_prediction_count += 1
        if matched_predictions:
            candidate_match_count += 1
        for prediction in matched_predictions:
            matched_class_counts[str(prediction["class_name"])] += 1
        for prediction in unexpected_predictions:
            unexpected_class_counts[str(prediction["class_name"])] += 1

        overlay_path: Path | None = None
        if draw_overlays and prediction_payloads and image_path.exists():
            overlay_path = overlay_dir / safe_name(f"{item.get('review_rank', 0):04d}__{example_id}")
            if not draw_model_overlay(image_path, prediction_payloads, overlay_path):
                overlay_path = None

        model_assist = {
            "source": "onnx_detector_review_hint",
            "model_path": relative_or_absolute(model_path, root_dir),
            "confidence_threshold": config.confidence_threshold,
            "image_size": config.image_size,
            "prediction_count": len(prediction_payloads),
            "candidate_matched_count": len(matched_predictions),
            "candidate_matched_predictions": matched_predictions,
            "unexpected_predictions": unexpected_predictions,
            "all_predictions": prediction_payloads,
            "overlay_path": relative_or_absolute(overlay_path, root_dir) if overlay_path is not None else None,
            "warning": "Review hint only. Do not promote model predictions without visual confirmation.",
        }
        row = {
            **item,
            "model_prediction_count": len(prediction_payloads),
            "model_candidate_matched_count": len(matched_predictions),
            "model_overlay_path": str(overlay_path) if overlay_path is not None else None,
            "model_assist": model_assist,
        }
        rows.append(row)
        answer_items.append(
            {
                "example_id": example_id,
                "detections": [],
                "review_outcome": "ambiguous",
                "note": (
                    "Benchmark-guided corpus review with ONNX model assist. "
                    f"model_predictions={len(prediction_payloads)} candidate_matches={len(matched_predictions)}. "
                    "Detections intentionally left empty until visual confirmation."
                ),
                "source": "benchmark_guided_model_assist",
                "image_path": str(item.get("image_path", "")),
                "candidate_labels": candidate_labels,
                "recommended_action": str(item.get("recommended_action", "")),
                "score": item.get("score"),
                "model_assist": model_assist,
            }
        )

    generated_at = datetime.now(timezone.utc).isoformat()
    report = {
        "generated_at": generated_at,
        "mode": "benchmark_guided_model_assist",
        "source_packet": relative_or_absolute(packet_path, root_dir),
        "model_path": relative_or_absolute(model_path, root_dir),
        "output_answer_seed": relative_or_absolute(resolve(root_dir, config.output_answers_path), root_dir),
        "output_dir": relative_or_absolute(output_dir, root_dir),
        "item_count": len(rows),
        "rows_with_any_predictions": any_prediction_count,
        "rows_with_candidate_matches": candidate_match_count,
        "hard_negative_rows_with_predictions": hard_negative_prediction_count,
        "matched_class_counts": dict(matched_class_counts),
        "unexpected_class_counts": dict(unexpected_class_counts),
        "prediction_errors": dict(prediction_errors),
        "promotion_note": "Model predictions are review hints only. Training detections remain empty until manually confirmed.",
    }
    answers = {
        "generated_at": generated_at,
        "mode": "benchmark_guided_model_assist_answers_seed",
        "source_packet": report["source_packet"],
        "instructions": [
            "Use model_assist as visual review hints only.",
            "Do not train from rows left as ambiguous.",
            "Copy or correct boxes into detections only after manual visual confirmation.",
            "For true hard negatives, set review_outcome to no_setup and leave detections empty.",
        ],
        "items": answer_items,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "model_assist_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (output_dir / "model_assist_rows.json").write_text(json.dumps({"summary": report, "items": rows}, indent=2) + "\n", encoding="utf-8")
    (output_dir / "index.html").write_text(build_dashboard(rows, report, root_dir=root_dir, output_dir=output_dir), encoding="utf-8")
    resolve(root_dir, config.output_answers_path).write_text(json.dumps(answers, indent=2) + "\n", encoding="utf-8")
    return report, answers


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build review-only ONNX model hints for a benchmark-guided corpus batch.")
    parser.add_argument("--root-dir", type=Path, default=Path.cwd())
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--output-answers", type=Path, default=DEFAULT_OUTPUT_ANSWERS)
    parser.add_argument("--imgsz", type=int, default=1024)
    parser.add_argument("--confidence", type=float, default=0.20)
    parser.add_argument("--max-predictions-per-image", type=int, default=8)
    return parser


def main(argv: list[str] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    args = build_arg_parser().parse_args(argv)
    config = ModelAssistConfig(
        root_dir=args.root_dir,
        packet_path=args.packet,
        model_path=args.model,
        output_dir=args.output_dir,
        output_answers_path=args.output_answers,
        image_size=args.imgsz,
        confidence_threshold=args.confidence,
        max_predictions_per_image=args.max_predictions_per_image,
    )
    report, answers = build_model_assist(config)
    print(
        json.dumps(
            {
                "output_dir": report["output_dir"],
                "output_answers": report["output_answer_seed"],
                "item_count": report["item_count"],
                "rows_with_any_predictions": report["rows_with_any_predictions"],
                "rows_with_candidate_matches": report["rows_with_candidate_matches"],
                "hard_negative_rows_with_predictions": report["hard_negative_rows_with_predictions"],
                "matched_class_counts": report["matched_class_counts"],
                "unexpected_class_counts": report["unexpected_class_counts"],
                "answer_items": len(answers.get("items", [])),
            },
            indent=2,
        )
    )
    return report, answers


if __name__ == "__main__":
    main()
