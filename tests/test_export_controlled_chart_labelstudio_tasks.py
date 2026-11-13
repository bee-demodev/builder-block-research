from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from scripts.export_controlled_chart_labelstudio_tasks import (
    export_labelstudio_tasks,
    write_outputs,
)


def _write_image(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (64, 40), (245, 245, 245)).save(path)


def _lineage_manifest(image_path: str) -> dict:
    return {
        "schema_version": "1.0.0",
        "items": [
            {
                "symbol": "NQ",
                "contract": "NQ_continuous_1m",
                "status": "captured",
                "images": [
                    {
                        "image_id": "controlled_NQ_m5_demo",
                        "symbol": "NQ",
                        "contract": "NQ_continuous_1m",
                        "timeframe": "5m",
                        "source_timeframe": "1m",
                        "status": "captured",
                        "image_path": image_path,
                        "source_csv_path": "data/databento/bars/nq_minute.csv",
                        "source_raw_path": "data/databento/raw/nq_minute.parquet",
                        "visible_range": {
                            "start": "2026-06-01T09:30:00-04:00",
                            "end": "2026-06-01T10:30:00-04:00",
                            "bar_count": 12,
                        },
                        "raw_timestamp_range": {
                            "start": "2026-06-01T09:26:00-04:00",
                            "end": "2026-06-01T10:30:00-04:00",
                            "row_count": 65,
                        },
                        "session": {
                            "dominant": "new_york",
                            "values": ["new_york"],
                            "counts": {"new_york": 65},
                        },
                        "quality_filter": {
                            "method": "median_ohlc_ratio",
                            "removed_ratio": 0.0,
                        },
                    }
                ],
            }
        ],
    }


def test_export_labelstudio_tasks_preserves_lineage_and_review_actions(tmp_path: Path) -> None:
    image_path = tmp_path / "results" / "controlled_charts" / "images" / "nq.png"
    _write_image(image_path)
    manifest_path = tmp_path / "results" / "controlled_charts" / "controlled_chart_lineage_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(_lineage_manifest(str(image_path.relative_to(tmp_path)))),
        encoding="utf-8",
    )

    export_manifest, tasks, label_config = export_labelstudio_tasks(
        root_dir=tmp_path,
        input_manifest_path=manifest_path,
        output_dir=tmp_path / "results" / "controlled_charts" / "label_studio",
    )
    write_outputs(
        export_manifest,
        tasks,
        label_config,
        root_dir=tmp_path,
        output_dir=tmp_path / "results" / "controlled_charts" / "label_studio",
    )

    assert export_manifest["task_count"] == 1
    assert export_manifest["missing_image_count"] == 0
    assert export_manifest["review_policy"]["allowed_actions"] == ["accept", "adjust", "reject", "defer"]
    task = tasks[0]
    assert task["id"] == "controlled_NQ_m5_demo"
    assert task["data"]["symbol"] == "NQ"
    assert task["data"]["timeframe"] == "5m"
    assert task["data"]["raw_row_count"] == 65
    assert task["meta"]["training_eligible"] is False
    assert "<Choice value=\"accept\"/>" in label_config
    assert "<RectangleLabels name=\"detections\"" in label_config
    assert (tmp_path / "results" / "controlled_charts" / "label_studio" / "tasks.json").exists()
    assert (tmp_path / "results" / "controlled_charts" / "label_studio" / "label_config.xml").exists()


def test_export_labelstudio_tasks_reports_missing_images(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(_lineage_manifest("results/controlled_charts/images/missing.png")),
        encoding="utf-8",
    )

    export_manifest, tasks, _label_config = export_labelstudio_tasks(
        root_dir=tmp_path,
        input_manifest_path=manifest_path,
        output_dir=tmp_path / "label_studio",
    )

    assert tasks == []
    assert export_manifest["task_count"] == 0
    assert export_manifest["missing_image_count"] == 1
    assert export_manifest["missing_images"] == ["controlled_NQ_m5_demo"]
