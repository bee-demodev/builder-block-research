from __future__ import annotations

import json
import struct
from pathlib import Path

from scripts.build_manual_tradingview_decision_packet import build_manual_packet, image_dimensions


def _write_png_header(path: Path, *, width: int, height: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + struct.pack(">I", 13)
        + b"IHDR"
        + struct.pack(">II", width, height)
        + b"\x08\x02\x00\x00\x00"
        + b"\x00\x00\x00\x00"
        + path.name.encode("utf-8")
    )


def test_image_dimensions_reads_png_header(tmp_path: Path) -> None:
    image = tmp_path / "daily.png"
    _write_png_header(image, width=1920, height=1080)

    assert image_dimensions(image) == (1920, 1080)


def test_manual_packet_is_decision_ready_for_three_large_screenshots(tmp_path: Path) -> None:
    daily = tmp_path / "screens" / "daily.png"
    h1 = tmp_path / "screens" / "h1.png"
    m5 = tmp_path / "screens" / "m5.png"
    for path in (daily, h1, m5):
        _write_png_header(path, width=1920, height=1080)

    packet = build_manual_packet(
        root_dir=tmp_path,
        symbol="CME_MINI:NQU2026",
        daily_path=daily,
        h1_path=h1,
        m5_path=m5,
        source_note="manual screenshot smoke",
    )

    assert packet["mode"] == "manual_tradingview_screenshot_decision_support"
    assert packet["decision_ready"] is True
    assert packet["blocked_reasons"] == []
    assert packet["chart_paths"] == {
        "daily": "screens\\daily.png",
        "h1": "screens\\h1.png",
        "m5": "screens\\m5.png",
    }
    assert packet["capture_quality"]["recommended_action"] == "continue_to_visual_markup"
    assert packet["capture_quality"]["images"]["m5"]["decision_usable"] is True
    assert packet["retrieval_context"]["queries"][0]["name"] == "timeframe_alignment"
    assert packet["bundle_record"]["source"] == "manual_screenshot_packet_pending_visual_state"


def test_manual_packet_blocks_small_or_missing_screenshots(tmp_path: Path) -> None:
    daily = tmp_path / "screens" / "daily.png"
    h1 = tmp_path / "screens" / "h1.png"
    m5 = tmp_path / "screens" / "m5.png"
    _write_png_header(daily, width=1920, height=1080)
    _write_png_header(h1, width=900, height=600)

    packet = build_manual_packet(
        root_dir=tmp_path,
        symbol="CME_MINI:ESU2026",
        daily_path=daily,
        h1_path=h1,
        m5_path=m5,
    )

    assert packet["decision_ready"] is False
    assert "h1:width_too_small" in packet["blocked_reasons"]
    assert "h1:height_too_small" in packet["blocked_reasons"]
    assert "m5:missing_image" in packet["blocked_reasons"]
    assert packet["capture_quality"]["recommended_action"] == "recapture_manual_screenshots"
    assert packet["capture_quality"]["resolution_failures"]["h1"]["issues"] == [
        "width_too_small",
        "height_too_small",
    ]
    assert packet["capture_quality"]["resolution_failures"]["m5"]["issues"] == ["missing_image"]


def test_manual_packet_blocks_duplicate_screenshot_content(tmp_path: Path) -> None:
    daily = tmp_path / "screens" / "daily.png"
    h1 = tmp_path / "screens" / "h1.png"
    m5 = tmp_path / "screens" / "m5.png"
    for path in (daily, h1, m5):
        _write_png_header(path, width=1920, height=1080)
    h1.write_bytes(daily.read_bytes())

    packet = build_manual_packet(
        root_dir=tmp_path,
        symbol="CME_MINI:NQU2026",
        daily_path=daily,
        h1_path=h1,
        m5_path=m5,
    )

    assert packet["decision_ready"] is False
    assert "daily:duplicate_image_content:h1" in packet["blocked_reasons"]
    assert "h1:duplicate_image_content:daily" in packet["blocked_reasons"]
    assert packet["capture_quality"]["images"]["daily"]["decision_usable"] is False
    assert packet["capture_quality"]["images"]["m5"]["decision_usable"] is True


def test_manual_packet_serializes_to_pipeline_packet_shape(tmp_path: Path) -> None:
    daily = tmp_path / "daily.png"
    h1 = tmp_path / "h1.png"
    m5 = tmp_path / "m5.png"
    for path in (daily, h1, m5):
        _write_png_header(path, width=1600, height=900)

    packet = build_manual_packet(
        root_dir=tmp_path,
        symbol="COMEX:GCQ2026",
        daily_path=daily,
        h1_path=h1,
        m5_path=m5,
    )
    serialized = json.loads(json.dumps(packet))

    assert serialized["packet_version"] == "tv_decision_bundle_v1"
    assert serialized["timeframe_order"] == ["daily", "h1", "m5"]
    assert set(serialized["visual_markup_request"]["labels_to_mark"]) >= {
        "daily_bias",
        "protected_swing",
        "entry_trigger",
        "missing_context",
    }
    assert "take" in serialized["decision_gate"]["allowed_verdicts"]
