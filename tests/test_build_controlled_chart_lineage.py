from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image

from scripts.build_controlled_chart_lineage import (
    build_controlled_chart_lineage,
    write_manifest,
)


def _write_minute_csv(path: Path, *, rows: int = 720) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    start = datetime(2026, 6, 1, 9, 30, tzinfo=timezone(timedelta(hours=-4)))
    lines = ["timestamp,open,high,low,close,volume,session"]
    for index in range(rows):
        timestamp = start + timedelta(minutes=index)
        base = 100.0 + (index * 0.1)
        session = "new_york" if 0 <= index % 360 < 300 else "other"
        lines.append(
            ",".join(
                [
                    timestamp.isoformat(),
                    f"{base:.2f}",
                    f"{base + 1.0:.2f}",
                    f"{base - 1.0:.2f}",
                    f"{base + 0.25:.2f}",
                    str(100 + index),
                    session,
                ]
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_controlled_chart_lineage_renders_review_only_images(tmp_path: Path) -> None:
    csv_path = tmp_path / "data" / "databento" / "bars" / "nq_minute.csv"
    _write_minute_csv(csv_path)

    manifest = build_controlled_chart_lineage(
        root_dir=tmp_path,
        data_dir=tmp_path / "data" / "databento",
        output_dir=tmp_path / "results" / "controlled_charts",
        symbols=("NQ",),
        tail_rows=720,
        width=640,
        height=360,
        dpi=100,
    )

    assert manifest["review_policy"] == {
        "candidate_only": True,
        "training_eligible_default": False,
        "allowed_actions": ["accept", "adjust", "reject", "defer"],
        "promotion_requires_visual_review": True,
    }
    assert manifest["summary"]["lineage_gate"] == "pass"
    assert manifest["summary"]["image_count"] == 3
    item = manifest["items"][0]
    assert item["symbol"] == "NQ"
    assert item["status"] == "captured"
    assert item["tail_rows_loaded"] == 720
    assert {image["timeframe"] for image in item["images"]} == {"1D", "1h", "5m"}

    for image in item["images"]:
        assert image["symbol"] == "NQ"
        assert image["contract"] == "NQ_continuous_1m"
        assert image["status"] == "captured"
        assert image["source_timeframe"] == "1m"
        assert image["visible_range"]["bar_count"] > 0
        assert image["raw_timestamp_range"]["row_count"] > 0
        assert image["session"]["dominant"] in {"new_york", "other"}
        assert image["review"]["status"] == "defer"
        assert image["review"]["training_eligible"] is False
        output_image = tmp_path / image["image_path"]
        assert output_image.exists()
        with Image.open(output_image) as rendered:
            assert rendered.size == (640, 360)


def test_controlled_chart_lineage_writes_manifest_and_blocks_missing_csv(tmp_path: Path) -> None:
    output_dir = tmp_path / "results" / "controlled_charts"

    manifest = build_controlled_chart_lineage(
        root_dir=tmp_path,
        data_dir=tmp_path / "data" / "databento",
        output_dir=output_dir,
        symbols=("ES",),
        tail_rows=10,
        width=320,
        height=180,
        dpi=100,
    )
    manifest_path = write_manifest(manifest, root_dir=tmp_path, output_dir=output_dir)
    written = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest_path.exists()
    assert written["summary"]["lineage_gate"] == "blocked"
    assert written["summary"]["blocked_or_partial_symbols"] == ["ES"]
    assert written["items"][0]["status"] == "blocked"
    assert written["items"][0]["blocking_reasons"] == ["normalized_1m_csv_missing"]
