from __future__ import annotations

import argparse
import html
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import YOLO_CLASS_NAMES, YOLO_CLASS_TO_ID
from labeler.vision_labeler import _propose_overlay_detections_for_image


DEFAULT_PRIORITY_BATCH_PATH = Path("results") / "ttfm_corpus_priority_review_batch.json"
DEFAULT_MODEL_SUGGESTIONS_PATH = Path("results") / "ttfm_corpus_priority_review_answers.model_suggestions.json"
DEFAULT_OUTPUT_DIR = Path("results") / "priority_review_heuristic_assist_20260622T171500Z"
DEFAULT_OUTPUT_ANSWER_PATH = Path("results") / "ttfm_corpus_priority_review_answers.heuristic_suggestions.json"


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def resolve(root_dir: Path, path: Path) -> Path:
    return path if path.is_absolute() else root_dir / path


def safe_name(value: str, *, suffix: str = ".jpg") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    cleaned = re.sub(r"_+", "_", cleaned)
    return f"{cleaned[:180] or 'item'}{suffix}"


def bbox_key(bbox: list[float]) -> tuple[int, int, int, int]:
    return tuple(int(round(float(value) * 10000)) for value in bbox)


def normalize_bbox(raw_bbox: Any) -> list[float] | None:
    if not isinstance(raw_bbox, list) or len(raw_bbox) != 4:
        return None
    bbox = [round(float(value), 6) for value in raw_bbox]
    if any(value < 0.0 or value > 1.0 for value in bbox):
        return None
    if bbox[2] <= 0.0 or bbox[3] <= 0.0:
        return None
    return bbox


def build_heuristic_suggestions(item: dict[str, Any], *, root_dir: Path) -> list[dict[str, Any]]:
    image_path = resolve(root_dir, Path(str(item.get("image_path", ""))))
    if not image_path.exists():
        return []

    grouped: dict[tuple[int, int, int, int], dict[str, Any]] = {}
    for class_name in item.get("candidate_labels", []) or []:
        class_name = str(class_name)
        class_id = YOLO_CLASS_TO_ID.get(class_name)
        if class_id is None:
            continue
        suggestions = _propose_overlay_detections_for_image(
            image_path,
            class_id=class_id,
            min_area_ratio=0.0015,
            max_area_ratio=0.20,
            max_suggestions=3,
        )
        for suggestion in suggestions:
            bbox = normalize_bbox(suggestion.get("bbox"))
            if bbox is None:
                continue
            key = bbox_key(bbox)
            row = grouped.setdefault(
                key,
                {
                    "bbox": bbox,
                    "candidate_class_ids": [],
                    "candidate_class_names": [],
                    "area": round(bbox[2] * bbox[3], 6),
                    "source": "opencv_overlay_color_hint",
                    "review_only": True,
                },
            )
            if class_id not in row["candidate_class_ids"]:
                row["candidate_class_ids"].append(class_id)
            if class_name not in row["candidate_class_names"]:
                row["candidate_class_names"].append(class_name)

    rows = list(grouped.values())
    for row in rows:
        ordered = sorted(
            zip(row["candidate_class_ids"], row["candidate_class_names"]),
            key=lambda pair: pair[0],
        )
        row["candidate_class_ids"] = [class_id for class_id, _name in ordered]
        row["candidate_class_names"] = [name for _class_id, name in ordered]
    rows.sort(key=lambda row: (float(row["area"]), len(row["candidate_class_names"])), reverse=True)
    return rows[:8]


def draw_overlay(image_path: Path, suggestions: list[dict[str, Any]], output_path: Path) -> bool:
    try:
        import cv2
    except ImportError:  # pragma: no cover
        return False

    image = cv2.imread(str(image_path))
    if image is None:
        return False
    height, width = image.shape[:2]
    palette = [
        (66, 211, 245),
        (80, 220, 120),
        (245, 190, 66),
        (180, 120, 245),
        (245, 92, 92),
        (230, 230, 90),
    ]
    for index, suggestion in enumerate(suggestions, start=1):
        cx, cy, bw, bh = [float(value) for value in suggestion["bbox"]]
        x1 = max(0, int((cx - bw / 2.0) * width))
        y1 = max(0, int((cy - bh / 2.0) * height))
        x2 = min(width - 1, int((cx + bw / 2.0) * width))
        y2 = min(height - 1, int((cy + bh / 2.0) * height))
        color = palette[(index - 1) % len(palette)]
        cv2.rectangle(image, (x1, y1), (x2, y2), color, thickness=2)
        label = f"H{index}: " + ",".join(str(name).replace("_", " ")[:10] for name in suggestion["candidate_class_names"][:2])
        text_y = max(16, y1 - 6)
        cv2.putText(image, label, (x1, text_y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return bool(cv2.imwrite(str(output_path), image))


def image_src(path: Path, *, root_dir: Path, html_path: Path) -> str:
    try:
        return Path(*path.resolve().relative_to(html_path.parent.resolve()).parts).as_posix()
    except ValueError:
        try:
            rel = path.resolve().relative_to(root_dir.resolve())
            return Path("..", "..", *rel.parts).as_posix()
        except ValueError:
            return path.as_uri()


def build_dashboard(
    rows: list[dict[str, Any]],
    *,
    root_dir: Path,
    output_dir: Path,
    report: dict[str, Any],
) -> str:
    cards: list[str] = []
    html_path = output_dir / "index.html"
    for row in sorted(rows, key=lambda item: (-(item.get("heuristic_suggestion_count", 0) or 0), item.get("review_rank") or 9999)):
        overlay_path = Path(str(row.get("heuristic_overlay_path") or ""))
        source_path = resolve(root_dir, Path(str(row.get("image_path", ""))))
        media_path = overlay_path if overlay_path.exists() else source_path
        suggestions_json = json.dumps(row.get("heuristic_suggestions", []), indent=2)
        model_json = json.dumps(row.get("model_candidate_matched_predictions", []), indent=2)
        labels = "".join(f"<span>{html.escape(str(label))}</span>" for label in row.get("candidate_labels", []))
        cards.append(
            f"""
            <article class="card {'has-hints' if row.get('heuristic_suggestion_count') else 'no-hints'}">
              <div class="media"><img src="{html.escape(image_src(media_path, root_dir=root_dir, html_path=html_path))}" alt="{html.escape(str(row.get('example_id', '')))}" loading="lazy" /></div>
              <div class="body">
                <div class="rank">#{html.escape(str(row.get('review_rank', '')))} | heuristic {html.escape(str(row.get('heuristic_suggestion_count', 0)))} | model matched {html.escape(str(row.get('model_candidate_matched_count', 0)))}</div>
                <h2>{html.escape(str(row.get('example_id', '')))}</h2>
                <p>{html.escape(str(row.get('recommended_action', '')))} | priority {html.escape(str(row.get('review_priority_reason', '')))}</p>
                <p class="chips">{labels}</p>
                <details open><summary>Heuristic Suggestions</summary><pre>{html.escape(suggestions_json)}</pre></details>
                <details><summary>Model Candidate-Matched Suggestions</summary><pre>{html.escape(model_json)}</pre></details>
              </div>
            </article>
            """
        )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>TTFM Priority Heuristic Assist</title>
<style>
:root {{ color-scheme: dark; font-family: Inter, system-ui, sans-serif; background: #101416; color: #eef3f1; }}
body {{ margin: 0; background: #101416; }}
header {{ position: sticky; top: 0; z-index: 2; padding: 14px 18px; background: #172023; border-bottom: 1px solid #314043; }}
h1 {{ margin: 0 0 4px; font-size: 20px; }}
header p {{ margin: 0; color: #b8c8c5; font-size: 13px; }}
main {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(560px, 1fr)); gap: 12px; padding: 12px; }}
.card {{ display: grid; grid-template-columns: minmax(260px, 45%) 1fr; min-height: 360px; border: 1px solid #2e3d40; background: #151d20; border-radius: 8px; overflow: hidden; }}
.card.has-hints {{ border-color: #65894a; }}
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
<h1>TTFM Priority Heuristic Assist</h1>
<p>{report["item_count"]} images | heuristic hints on {report["rows_with_heuristic_suggestions"]} rows | model candidate matches on {report["rows_with_model_candidate_matches"]} rows | suggestions are not labels</p>
</header>
<main>
{''.join(cards)}
</main>
</body>
</html>
"""


def build_outputs(
    *,
    root_dir: Path,
    priority_batch_path: Path,
    model_suggestions_path: Path,
    output_dir: Path,
    output_answer_path: Path,
) -> dict[str, Any]:
    priority_batch = load_json(priority_batch_path, {})
    model_seed = load_json(model_suggestions_path, {})
    model_by_id = {
        str(item.get("example_id", "")).strip(): item
        for item in model_seed.get("items", [])
        if str(item.get("example_id", "")).strip()
    }

    overlay_dir = output_dir / "overlays"
    rows: list[dict[str, Any]] = []
    answer_items: list[dict[str, Any]] = []
    class_candidate_counts: Counter[str] = Counter()
    rows_with_hints = 0
    hard_negative_rows_with_hints = 0
    model_candidate_match_rows = 0

    for item in priority_batch.get("items", []):
        example_id = str(item.get("example_id", "")).strip()
        image_path = resolve(root_dir, Path(str(item.get("image_path", ""))))
        suggestions = build_heuristic_suggestions(item, root_dir=root_dir)
        overlay_path: Path | None = None
        if suggestions:
            rows_with_hints += 1
            if item.get("recommended_action") == "hard_negative_review":
                hard_negative_rows_with_hints += 1
            for suggestion in suggestions:
                for class_name in suggestion.get("candidate_class_names", []):
                    class_candidate_counts[str(class_name)] += 1
            overlay_path = overlay_dir / safe_name(f"{item.get('review_rank', 0):04d}__{example_id}")
            draw_overlay(image_path, suggestions, overlay_path)

        model_item = model_by_id.get(example_id, {})
        model_assist = model_item.get("model_assist", {}) if isinstance(model_item, dict) else {}
        model_matches = list(model_assist.get("candidate_matched_predictions", []) or [])
        if model_matches:
            model_candidate_match_rows += 1

        row = {
            **item,
            "heuristic_suggestion_count": len(suggestions),
            "heuristic_suggestions": suggestions,
            "heuristic_overlay_path": str(overlay_path) if overlay_path is not None and overlay_path.exists() else None,
            "model_candidate_matched_count": len(model_matches),
            "model_candidate_matched_predictions": model_matches,
        }
        rows.append(row)

        answer_item = dict(model_item) if model_item else {
            "example_id": example_id,
            "detections": [],
            "review_outcome": "ambiguous",
            "note": "Priority review row. Keep ambiguous until manually reviewed.",
            "candidate_labels": item.get("candidate_labels", []),
            "recommended_action": item.get("recommended_action"),
            "score": item.get("score"),
        }
        answer_item["detections"] = []
        answer_item["review_outcome"] = "ambiguous"
        answer_item["heuristic_assist"] = {
            "source": "opencv_overlay_color_hint",
            "suggestion_count": len(suggestions),
            "suggestions": suggestions,
            "overlay_path": str(overlay_path.relative_to(root_dir)).replace("\\", "/") if overlay_path is not None and overlay_path.exists() else None,
            "warning": "Review suggestions only. Copy or correct boxes into detections only after manual visual confirmation.",
        }
        answer_item["note"] = (
            f"{answer_item.get('note', '')} Heuristic assist suggestions={len(suggestions)}. "
            "Detections intentionally left empty."
        ).strip()
        answer_items.append(answer_item)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "priority_review_heuristic_assist",
        "source_priority_batch": str(priority_batch_path.relative_to(root_dir)),
        "source_model_suggestions": str(model_suggestions_path.relative_to(root_dir)) if model_suggestions_path.exists() else None,
        "output_answer_seed": str(output_answer_path.relative_to(root_dir)),
        "output_dir": str(output_dir.relative_to(root_dir)),
        "item_count": len(rows),
        "rows_with_heuristic_suggestions": rows_with_hints,
        "rows_without_heuristic_suggestions": len(rows) - rows_with_hints,
        "hard_negative_rows_with_heuristic_suggestions": hard_negative_rows_with_hints,
        "rows_with_model_candidate_matches": model_candidate_match_rows,
        "heuristic_candidate_class_counts": dict(class_candidate_counts),
        "promotion_note": "Heuristic boxes are review hints only. Training detections remain empty until manually confirmed.",
        "next_gate": {
            "minimum_train_images_for_confidence": 150,
            "minimum_val_images_for_confidence": 40,
            "hard_negative_target": 25,
            "priority_classes": ["liquidity_sweep_high", "bearish_reaction_zone", "bullish_reaction_zone"],
        },
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    answer_payload = {
        "generated_at": report["generated_at"],
        "mode": "priority_review_answer_seed_with_model_and_heuristic_suggestions",
        "source_priority_batch": str(priority_batch_path.relative_to(root_dir)),
        "source_model_suggestions": str(model_suggestions_path.relative_to(root_dir)) if model_suggestions_path.exists() else None,
        "instructions": [
            "Use model_assist and heuristic_assist only as visual hints.",
            "Do not train from rows left as ambiguous.",
            "Copy or correct boxes into detections only after manual visual confirmation.",
            "For true hard negatives, set review_outcome to no_setup and leave detections empty.",
        ],
        "items": answer_items,
    }
    output_answer_path.write_text(json.dumps(answer_payload, indent=2), encoding="utf-8")
    (output_dir / "heuristic_suggestions.json").write_text(json.dumps({"summary": report, "items": rows}, indent=2), encoding="utf-8")
    (output_dir / "heuristic_assist_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (output_dir / "index.html").write_text(build_dashboard(rows, root_dir=root_dir, output_dir=output_dir, report=report), encoding="utf-8")
    return report


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build deterministic review-only OpenCV box hints for the priority TTFM corpus batch.")
    parser.add_argument("--root-dir", type=Path, default=Path.cwd())
    parser.add_argument("--priority-batch", type=Path, default=DEFAULT_PRIORITY_BATCH_PATH)
    parser.add_argument("--model-suggestions", type=Path, default=DEFAULT_MODEL_SUGGESTIONS_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--output-answer", type=Path, default=DEFAULT_OUTPUT_ANSWER_PATH)
    return parser


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = build_arg_parser().parse_args(argv)
    root_dir = args.root_dir.resolve()
    report = build_outputs(
        root_dir=root_dir,
        priority_batch_path=resolve(root_dir, args.priority_batch),
        model_suggestions_path=resolve(root_dir, args.model_suggestions),
        output_dir=resolve(root_dir, args.output_dir),
        output_answer_path=resolve(root_dir, args.output_answer),
    )
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    main()
