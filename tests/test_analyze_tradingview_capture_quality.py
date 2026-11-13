from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw

from scripts.analyze_tradingview_capture_quality import analyze_packet


def _chart_image(path: Path, *, pattern: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (96, 96), (246, 246, 246))
    draw = ImageDraw.Draw(image)
    if pattern == "up":
        draw.line((8, 80, 40, 45, 88, 16), fill=(20, 20, 20), width=5)
        draw.rectangle((20, 40, 50, 65), outline=(30, 30, 30), width=3)
    elif pattern == "down":
        draw.line((8, 16, 40, 45, 88, 80), fill=(20, 20, 20), width=5)
        draw.rectangle((52, 35, 82, 62), outline=(30, 30, 30), width=3)
    elif pattern == "box":
        draw.rectangle((16, 16, 80, 80), outline=(20, 20, 20), width=5)
        draw.line((16, 80, 80, 16), fill=(20, 20, 20), width=4)
    elif pattern == "blank-line":
        draw.line((48, 0, 48, 95), fill=(40, 40, 40), width=1)
    else:
        raise ValueError(pattern)
    image.save(path)
    return str(path.relative_to(path.parents[2]))


def _capture_metadata(
    capture_dir: Path,
    *,
    symbol: str = "CME_MINI:NQM2026",
    bad_daily_resolution: bool = False,
    bad_h1_symbol: bool = False,
) -> None:
    payload = {
        "original_state": {"symbol": symbol},
        "frames": {
            "htf": {
                "requested_timeframe": "D",
                "resolved_resolution": "240" if bad_daily_resolution else "1D",
                "symbol": symbol,
            },
            "itf": {
                "requested_timeframe": "60",
                "resolved_resolution": "60",
                "symbol": "CME_MINI:ESM2026" if bad_h1_symbol else symbol,
            },
            "ltf": {
                "requested_timeframe": "5",
                "resolved_resolution": "5",
                "symbol": symbol,
            },
        },
    }
    (capture_dir / "capture.json").write_text(json.dumps(payload), encoding="utf-8")


def _packet_item(tmp_path: Path, name: str, patterns: tuple[str, str, str]) -> dict:
    capture_dir = tmp_path / "captures" / name
    return {
        "example_id": name,
        "priority_score": 1.0,
        "chart_paths": {
            "daily": _chart_image(capture_dir / "htf.png", pattern=patterns[0]),
            "h1": _chart_image(capture_dir / "itf.png", pattern=patterns[1]),
            "m5": _chart_image(capture_dir / "ltf.png", pattern=patterns[2]),
        },
    }


def _analyze(tmp_path: Path, items: list[dict]) -> dict:
    return analyze_packet(
        {"items": items},
        root_dir=tmp_path,
        packet_path=tmp_path / "packet.json",
        max_hamming=0,
        min_edge_ratio=0.018,
        min_non_background_ratio=0.012,
        min_unique_luma=90,
    )


def test_capture_quality_allows_distinct_metadata_clean_stack(tmp_path: Path) -> None:
    item = _packet_item(tmp_path, "usable", ("up", "down", "box"))
    _capture_metadata(tmp_path / "captures" / "usable")

    report = _analyze(tmp_path, [item])

    assert report["action_counts"] == {"review_state_labels": 1}
    assert report["quality_flag_counts"] == {}
    assert report["items"][0]["quality_flags"] == []


def test_capture_quality_flags_low_information_and_bad_timeframe(tmp_path: Path) -> None:
    item = _packet_item(tmp_path, "bad-m5", ("up", "down", "blank-line"))
    _capture_metadata(tmp_path / "captures" / "bad-m5", bad_daily_resolution=True)

    report = _analyze(tmp_path, [item])
    result = report["items"][0]

    assert result["recommended_action"] == "recapture_before_review"
    assert "low_information_timeframe_image" in result["quality_flags"]
    assert result["low_information_timeframes"] == ["m5"]
    assert "timeframe_metadata_mismatch" in result["quality_flags"]


def test_capture_quality_flags_symbol_mismatch(tmp_path: Path) -> None:
    item = _packet_item(tmp_path, "symbol-mismatch", ("up", "down", "box"))
    _capture_metadata(tmp_path / "captures" / "symbol-mismatch", bad_h1_symbol=True)

    report = _analyze(tmp_path, [item])
    result = report["items"][0]

    assert result["recommended_action"] == "recapture_before_review"
    assert result["quality_flags"] == ["symbol_metadata_mismatch"]
    assert result["capture_metadata"]["frames"]["h1"]["symbol"] == "CME_MINI:ESM2026"


def test_capture_quality_flags_duplicate_timeframe_images(tmp_path: Path) -> None:
    item = _packet_item(tmp_path, "duplicate", ("up", "down", "box"))
    item["chart_paths"]["h1"] = item["chart_paths"]["daily"]
    _capture_metadata(tmp_path / "captures" / "duplicate")

    report = _analyze(tmp_path, [item])
    result = report["items"][0]

    assert result["recommended_action"] == "recapture_before_review"
    assert "exact_duplicate_timeframe_images" in result["quality_flags"]
    assert result["exact_duplicate_pairs"] == [["daily", "h1"]]
