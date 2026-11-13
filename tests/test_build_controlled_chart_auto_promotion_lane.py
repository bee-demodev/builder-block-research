from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image

from scripts.build_controlled_chart_auto_promotion_lane import (
    build_auto_promotion_lane,
    write_report,
)


def _write_chart(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (320, 180), "white").save(path)


def _write_csv(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    start = datetime(2026, 1, 1, 9, 0, tzinfo=timezone(timedelta(hours=-5)))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["timestamp", "open", "high", "low", "close", "volume", "session"])
        writer.writeheader()
        for index in range(120):
            timestamp = start + timedelta(minutes=index)
            high = 101.0
            low = 99.0
            close = 100.0
            if index == 60:
                high = 106.0
                close = 100.0
            writer.writerow(
                {
                    "timestamp": timestamp.isoformat(),
                    "open": 100.0,
                    "high": high,
                    "low": low,
                    "close": close,
                    "volume": 100,
                    "session": "new_york",
                }
            )


def _lineage(root_dir: Path, csv_path: Path) -> dict:
    image_specs = [
        ("controlled_ES_daily", "1D", "daily.png"),
        ("controlled_ES_h1", "1h", "h1.png"),
        ("controlled_ES_m5", "5m", "m5.png"),
    ]
    images = []
    for image_id, timeframe, name in image_specs:
        image_path = root_dir / "charts" / name
        _write_chart(image_path)
        images.append(
            {
                "image_id": image_id,
                "symbol": "ES",
                "contract": "ES_test",
                "timeframe": timeframe,
                "status": "captured",
                "image_path": str(image_path.relative_to(root_dir)),
                "source_csv_path": str(csv_path.relative_to(root_dir)),
                "visible_range": {
                    "start": "2026-01-01T09:00:00-05:00",
                    "end": "2026-01-01T10:59:00-05:00",
                    "bar_count": 24,
                },
                "quality_filter": {
                    "min_price": 90.0,
                    "max_price": 110.0,
                    "removed_ratio": 0.0,
                },
                "session": {"dominant": "new_york"},
            }
        )
    return {
        "schema_version": "1.0.0",
        "summary": {"lineage_gate": "pass", "image_count": 3},
        "items": [{"symbol": "ES", "status": "captured", "images": images}],
    }


def test_build_auto_promotion_lane_emits_pseudo_labels_and_state_fixtures(tmp_path: Path) -> None:
    csv_path = tmp_path / "data" / "es_minute.csv"
    _write_csv(csv_path)
    lineage_path = tmp_path / "results" / "controlled_charts" / "lineage.json"
    lineage_path.parent.mkdir(parents=True, exist_ok=True)
    lineage_path.write_text(json.dumps(_lineage(tmp_path, csv_path)), encoding="utf-8")

    _answers, report, state_fixtures = build_auto_promotion_lane(
        root_dir=tmp_path,
        lineage_manifest_path=lineage_path,
        output_answers_path=tmp_path / "results" / "controlled_charts" / "auto_pseudo_labels.json",
        output_state_fixtures_path=tmp_path / "results" / "fixtures.auto.json",
    )
    write_report(report, root_dir=tmp_path, output_report_path=tmp_path / "results" / "controlled_charts" / "auto_report.json")

    assert report["auto_training_gate"] == "pass"
    assert report["validated_trainable_item_count"] >= 1
    assert report["class_counts"]["liquidity_sweep_high"] >= 1
    assert state_fixtures["summary"]["fixture_gate"] == "pass"
    assert state_fixtures["summary"]["expected_decision_counts"] == {"watch_only": 1}
    assert (tmp_path / "results" / "controlled_charts" / "auto_report.json").exists()
