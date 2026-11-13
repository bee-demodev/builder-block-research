from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw

from scripts.build_controlled_chart_review_packet import build_review_packet, write_report


def _write_chart(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (260, 180), "white")
    draw = ImageDraw.Draw(image)
    draw.line((40, 40, 40, 130), fill=(0, 170, 160), width=3)
    draw.rectangle((36, 80, 44, 100), fill=(0, 170, 160))
    draw.line((180, 28, 180, 120), fill=(240, 40, 40), width=3)
    draw.rectangle((176, 62, 184, 90), fill=(240, 40, 40))
    image.save(path)


def _prediction(label: str, *, x: float, y: float, width: float, height: float) -> dict:
    return {
        "from_name": "detections",
        "to_name": "image",
        "type": "rectanglelabels",
        "score": 0.24,
        "value": {
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "rectanglelabels": [label],
        },
    }


def _task(image_path: Path, *, image_id: str = "case-1") -> dict:
    return {
        "id": image_id,
        "data": {
            "image": str(image_path),
            "image_abs": str(image_path),
            "image_id": image_id,
            "symbol": "ES",
            "contract": "ES_continuous",
            "timeframe": "5m",
        },
        "predictions": [
            {
                "model_version": "opencv_visual_hints_v1",
                "score": 0.24,
                "result": [
                    _prediction("liquidity_sweep_high", x=66.0, y=10.0, width=8.0, height=20.0),
                    _prediction("liquidity_sweep_low", x=12.0, y=62.0, width=8.0, height=20.0),
                ],
            }
        ],
    }


def test_build_review_packet_writes_overlays_contact_sheet_and_report(tmp_path: Path) -> None:
    image_path = tmp_path / "charts" / "case.png"
    _write_chart(image_path)
    tasks_path = tmp_path / "tasks_with_predictions.json"
    tasks_path.write_text(json.dumps([_task(image_path)]), encoding="utf-8")
    output_dir = tmp_path / "review_packet"

    report = build_review_packet(root_dir=tmp_path, input_tasks_path=tasks_path, output_dir=output_dir)
    write_report(report, root_dir=tmp_path, output_dir=output_dir)

    assert report["summary"]["task_count"] == 1
    assert report["summary"]["overlay_count"] == 1
    assert report["summary"]["prediction_count"] == 2
    assert report["summary"]["prediction_label_counts"] == {
        "liquidity_sweep_high": 1,
        "liquidity_sweep_low": 1,
    }
    assert report["review_policy"]["training_eligible"] is False
    overlay_path = tmp_path / report["items"][0]["overlay_path"]
    contact_sheet_path = tmp_path / report["contact_sheet_path"]
    report_path = output_dir / "controlled_chart_review_packet.json"
    assert overlay_path.exists()
    assert contact_sheet_path.exists()
    assert report_path.exists()
    assert json.loads(report_path.read_text(encoding="utf-8"))["summary"]["prediction_count"] == 2


def test_build_review_packet_reports_missing_images(tmp_path: Path) -> None:
    tasks_path = tmp_path / "tasks_with_predictions.json"
    tasks_path.write_text(json.dumps([_task(tmp_path / "missing.png", image_id="missing-case")]), encoding="utf-8")

    report = build_review_packet(root_dir=tmp_path, input_tasks_path=tasks_path, output_dir=tmp_path / "review_packet")

    assert report["summary"]["task_count"] == 1
    assert report["summary"]["overlay_count"] == 0
    assert report["summary"]["missing_image_count"] == 1
    assert report["summary"]["missing_images"] == ["missing-case"]
    assert report["items"][0]["overlay_path"] == ""
