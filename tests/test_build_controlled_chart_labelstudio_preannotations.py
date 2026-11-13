from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw

from scripts.build_controlled_chart_labelstudio_preannotations import (
    build_labelstudio_preannotations,
    write_outputs,
)
from scripts.import_labelstudio_controlled_chart_answers import import_labelstudio_answers


def _write_synthetic_chart(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (240, 160), "white")
    draw = ImageDraw.Draw(image)
    for x in range(20, 220, 40):
        draw.line((x, 10 + (x % 60), x, 80 + (x % 35)), fill=(0, 170, 160), width=2)
        draw.rectangle((x - 3, 45 + (x % 20), x + 3, 62 + (x % 20)), fill=(0, 170, 160))
    draw.line((48, 12, 48, 92), fill=(255, 0, 0), width=2)
    draw.line((184, 34, 184, 108), fill=(0, 170, 160), width=2)
    image.save(path)


def _write_chart_with_volume_trap(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (240, 180), "white")
    draw = ImageDraw.Draw(image)
    draw.line((44, 24, 44, 84), fill=(255, 0, 0), width=2)
    draw.line((150, 62, 150, 108), fill=(0, 170, 160), width=2)
    draw.rectangle((147, 80, 153, 98), fill=(0, 170, 160))
    for x in range(20, 220, 16):
        draw.rectangle((x, 135, x + 8, 178), fill=(0, 170, 160))
    image.save(path)


def _task(image_path: Path, *, image_id: str = "synthetic-chart") -> dict:
    return {
        "id": image_id,
        "data": {
            "image": str(image_path),
            "image_abs": str(image_path),
            "image_id": image_id,
            "symbol": "NQ",
            "timeframe": "5m",
        },
        "meta": {"training_eligible": False},
    }


def test_build_labelstudio_preannotations_adds_review_only_predictions(tmp_path: Path) -> None:
    image_path = tmp_path / "charts" / "synthetic.png"
    _write_synthetic_chart(image_path)
    tasks_path = tmp_path / "tasks.json"
    tasks_path.write_text(json.dumps([_task(image_path)]), encoding="utf-8")

    tasks, report = build_labelstudio_preannotations(
        root_dir=tmp_path,
        input_tasks_path=tasks_path,
        output_tasks_path=tmp_path / "tasks_with_predictions.json",
    )

    assert report["task_count"] == 1
    assert report["tasks_with_predictions"] == 1
    assert report["prediction_count"] == 2
    assert report["review_policy"] == {
        "prediction_source": "opencv_visual_hints",
        "review_only": True,
        "training_eligible": False,
        "promotion_requires_labelstudio_annotation": True,
        "importer_ignores_predictions": True,
    }
    assert "annotations" not in tasks[0]
    prediction = tasks[0]["predictions"][0]
    labels = [result["value"]["rectanglelabels"][0] for result in prediction["result"]]
    assert labels == ["liquidity_sweep_high", "liquidity_sweep_low"]
    assert tasks[0]["meta"]["preannotation_policy"]["training_eligible"] is False


def test_predictions_do_not_make_labelstudio_import_trainable(tmp_path: Path) -> None:
    image_path = tmp_path / "charts" / "synthetic.png"
    _write_synthetic_chart(image_path)
    tasks_path = tmp_path / "tasks.json"
    output_tasks_path = tmp_path / "tasks_with_predictions.json"
    report_path = tmp_path / "prediction_report.json"
    tasks_path.write_text(json.dumps([_task(image_path)]), encoding="utf-8")
    tasks, report = build_labelstudio_preannotations(
        root_dir=tmp_path,
        input_tasks_path=tasks_path,
        output_tasks_path=output_tasks_path,
    )
    write_outputs(
        tasks,
        report,
        root_dir=tmp_path,
        output_tasks_path=output_tasks_path,
        output_report_path=report_path,
    )

    _answers, import_report = import_labelstudio_answers(
        root_dir=tmp_path,
        labelstudio_export_path=output_tasks_path,
        output_answers_path=tmp_path / "imported_answers.json",
    )

    assert import_report["training_gate"] == "blocked_no_reviewed_trainable_items"
    assert import_report["validated_trainable_item_count"] == 0
    assert import_report["review_outcome_counts"] == {"ambiguous": 1}
    assert import_report["issue_counts"] == {"missing_annotation": 1}


def test_preannotations_exclude_volume_panel_from_low_hint(tmp_path: Path) -> None:
    image_path = tmp_path / "charts" / "volume_trap.png"
    _write_chart_with_volume_trap(image_path)
    tasks_path = tmp_path / "tasks.json"
    tasks_path.write_text(json.dumps([_task(image_path)]), encoding="utf-8")

    tasks, _report = build_labelstudio_preannotations(
        root_dir=tmp_path,
        input_tasks_path=tasks_path,
        output_tasks_path=tmp_path / "tasks_with_predictions.json",
    )

    low_result = next(
        result
        for result in tasks[0]["predictions"][0]["result"]
        if result["value"]["rectanglelabels"] == ["liquidity_sweep_low"]
    )
    low_bottom = low_result["value"]["y"] + low_result["value"]["height"]
    assert low_bottom < 70.0


def test_build_labelstudio_preannotations_reports_missing_images(tmp_path: Path) -> None:
    tasks_path = tmp_path / "tasks.json"
    tasks_path.write_text(json.dumps([_task(tmp_path / "missing.png")]), encoding="utf-8")

    tasks, report = build_labelstudio_preannotations(
        root_dir=tmp_path,
        input_tasks_path=tasks_path,
        output_tasks_path=tmp_path / "tasks_with_predictions.json",
    )

    assert len(tasks) == 1
    assert "predictions" not in tasks[0]
    assert report["tasks_with_predictions"] == 0
    assert report["missing_image_count"] == 1
    assert report["missing_images"] == ["synthetic-chart"]
