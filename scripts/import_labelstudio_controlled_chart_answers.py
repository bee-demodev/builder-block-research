from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import YOLO_CLASS_TO_ID
from labeler.vision_labeler import load_supervision_answers


DEFAULT_LABELSTUDIO_EXPORT = Path("results") / "controlled_charts" / "label_studio" / "tasks.json"
DEFAULT_OUTPUT_ANSWERS = Path("results") / "controlled_charts" / "label_studio" / "imported_answers.json"
DEFAULT_OUTPUT_REPORT = Path("results") / "controlled_charts" / "label_studio" / "import_report.json"
ACTION_TO_OUTCOME = {
    "accept": "accepted",
    "adjust": "adjusted",
    "reject": "rejected",
    "defer": "ambiguous",
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


def task_id(task: dict[str, Any]) -> str:
    data = task.get("data", {}) if isinstance(task.get("data"), dict) else {}
    return str(data.get("image_id") or task.get("id") or "").strip()


def latest_annotation(task: dict[str, Any]) -> dict[str, Any] | None:
    annotations = task.get("annotations", [])
    if not isinstance(annotations, list):
        return None
    usable = [annotation for annotation in annotations if isinstance(annotation, dict)]
    if not usable:
        return None
    return usable[-1]


def extract_review_action(results: list[dict[str, Any]]) -> str | None:
    for result in results:
        if str(result.get("type") or "") != "choices":
            continue
        value = result.get("value", {})
        if not isinstance(value, dict):
            continue
        choices = value.get("choices", [])
        if isinstance(choices, list) and choices:
            return str(choices[0]).strip().lower()
    return None


def extract_notes(results: list[dict[str, Any]]) -> str:
    notes: list[str] = []
    for result in results:
        if str(result.get("type") or "") != "textarea":
            continue
        value = result.get("value", {})
        if not isinstance(value, dict):
            continue
        text = value.get("text", [])
        if isinstance(text, list):
            notes.extend(str(item).strip() for item in text if str(item).strip())
        elif str(text).strip():
            notes.append(str(text).strip())
    return " ".join(notes)


def rectangle_to_detection(result: dict[str, Any]) -> dict[str, Any] | None:
    if str(result.get("type") or "") != "rectanglelabels":
        return None
    value = result.get("value", {})
    if not isinstance(value, dict):
        return None
    labels = value.get("rectanglelabels", [])
    if not isinstance(labels, list) or not labels:
        return None
    class_name = str(labels[0]).strip()
    class_id = YOLO_CLASS_TO_ID.get(class_name)
    if class_id is None:
        return None
    try:
        x = float(value["x"])
        y = float(value["y"])
        width = float(value["width"])
        height = float(value["height"])
    except (KeyError, TypeError, ValueError):
        return None
    return {
        "class_id": class_id,
        "bbox": [
            round((x + (width / 2.0)) / 100.0, 6),
            round((y + (height / 2.0)) / 100.0, 6),
            round(width / 100.0, 6),
            round(height / 100.0, 6),
        ],
    }


def task_to_answer(task: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    example_id = task_id(task)
    data = task.get("data", {}) if isinstance(task.get("data"), dict) else {}
    issues: list[str] = []
    if not example_id:
        example_id = "missing_example_id"
        issues.append("missing_example_id")
    annotation = latest_annotation(task)
    if annotation is None:
        issues.append("missing_annotation")
        return {
            "example_id": example_id,
            "detections": [],
            "review_outcome": "ambiguous",
            "note": "No Label Studio annotation found; leaving deferred.",
            "source": "label_studio_controlled_chart_import",
            "image_path": str(data.get("image") or ""),
            "training_eligible": False,
            "review_action": "defer",
        }, issues
    results = annotation.get("result", [])
    if not isinstance(results, list):
        results = []
    action = extract_review_action(results)
    if action not in ACTION_TO_OUTCOME:
        action = "defer"
        issues.append("missing_or_invalid_review_action")
    detections = [
        detection
        for detection in (rectangle_to_detection(result) for result in results)
        if detection is not None
    ]
    outcome = ACTION_TO_OUTCOME[action]
    if outcome in {"accepted", "adjusted"} and not detections:
        outcome = "ambiguous"
        issues.append("accepted_or_adjusted_without_detections")
    note_parts = [
        f"Label Studio action={action}.",
        extract_notes(results),
    ]
    note = " ".join(part for part in note_parts if part).strip()
    return {
        "example_id": example_id,
        "detections": detections,
        "review_outcome": outcome,
        "note": note,
        "source": "label_studio_controlled_chart_import",
        "image_path": str(data.get("image") or ""),
        "training_eligible": outcome in {"accepted", "adjusted"} and bool(detections),
        "review_action": action,
    }, issues


def import_labelstudio_answers(
    *,
    root_dir: Path,
    labelstudio_export_path: Path,
    output_answers_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    root_dir = root_dir.resolve()
    export_path = resolve(root_dir, labelstudio_export_path)
    raw_payload = read_json(export_path)
    tasks = raw_payload if isinstance(raw_payload, list) else raw_payload.get("tasks", [])
    if not isinstance(tasks, list):
        tasks = []

    answers: list[dict[str, Any]] = []
    issue_counts: Counter[str] = Counter()
    for task in tasks:
        if not isinstance(task, dict):
            issue_counts["non_object_task"] += 1
            continue
        answer, issues = task_to_answer(task)
        answers.append(answer)
        issue_counts.update(issues)

    payload = {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_labelstudio_export": relative_or_absolute(export_path, root_dir),
        "mode": "controlled_chart_labelstudio_import",
        "items": answers,
    }
    temp_output = resolve(root_dir, output_answers_path)
    temp_output.parent.mkdir(parents=True, exist_ok=True)
    temp_output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    validated = load_supervision_answers(temp_output)
    report = {
        "schema_version": "1.0.0",
        "generated_at": payload["generated_at"],
        "source_labelstudio_export": payload["source_labelstudio_export"],
        "output_answers_path": relative_or_absolute(temp_output, root_dir),
        "task_count": len(tasks),
        "answer_item_count": len(answers),
        "validated_trainable_item_count": len(validated),
        "review_outcome_counts": dict(sorted(Counter(item["review_outcome"] for item in answers).items())),
        "issue_counts": dict(sorted(issue_counts.items())),
        "training_gate": "pass" if validated else "blocked_no_reviewed_trainable_items",
    }
    return payload, report


def write_report(report: dict[str, Any], *, root_dir: Path, output_report_path: Path) -> None:
    output_path = resolve(root_dir, output_report_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert Label Studio exports into controlled-chart answer JSON.")
    parser.add_argument("--root-dir", type=Path, default=Path("."))
    parser.add_argument("--labelstudio-export", type=Path, default=DEFAULT_LABELSTUDIO_EXPORT)
    parser.add_argument("--output-answers", type=Path, default=DEFAULT_OUTPUT_ANSWERS)
    parser.add_argument("--output-report", type=Path, default=DEFAULT_OUTPUT_REPORT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root_dir = args.root_dir.resolve()
    _answers, report = import_labelstudio_answers(
        root_dir=root_dir,
        labelstudio_export_path=args.labelstudio_export,
        output_answers_path=args.output_answers,
    )
    write_report(report, root_dir=root_dir, output_report_path=args.output_report)
    print(
        "Imported Label Studio controlled chart answers: "
        f"{relative_or_absolute(resolve(root_dir, args.output_answers), root_dir)} "
        f"validated_trainable={report['validated_trainable_item_count']} "
        f"gate={report['training_gate']}"
    )


if __name__ == "__main__":
    main()
