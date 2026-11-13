from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from scripts.analyze_ttrades_state_review_layout import analyze_packet, image_info


def _image(path: Path, *, color: tuple[int, int, int], size: tuple[int, int] = (64, 64)) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path)
    return str(path)


def _pattern_image(path: Path, *, pattern: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (64, 64), (245, 245, 245))
    draw = ImageDraw.Draw(image)
    if pattern == "up":
        draw.line((8, 52, 30, 28, 56, 8), fill=(10, 10, 10), width=4)
    elif pattern == "down":
        draw.line((8, 8, 30, 28, 56, 52), fill=(10, 10, 10), width=4)
    else:
        draw.rectangle((18, 18, 46, 46), outline=(10, 10, 10), width=4)
    image.save(path)
    return str(path)


def test_layout_report_flags_exact_duplicate_timeframes(tmp_path: Path) -> None:
    daily = _image(tmp_path / "charts" / "daily.png", color=(255, 255, 255))
    h1 = daily
    m5 = _image(tmp_path / "charts" / "m5.png", color=(0, 0, 0))
    packet = {
        "items": [
            {
                "example_id": "duplicate-case",
                "priority_score": 10,
                "chart_paths": {"daily": daily, "h1": h1, "m5": m5},
                "candidate_state": {"missing_evidence": ["directional_bias_unlabeled"]},
            }
        ]
    }

    report = analyze_packet(packet, root_dir=tmp_path, packet_path=tmp_path / "packet.json")

    assert report["action_counts"] == {"skip_invalid_layout": 1}
    assert report["layout_flag_counts"] == {"exact_duplicate_timeframe_images": 1}
    assert report["items"][0]["exact_duplicate_pairs"] == [["daily", "h1"]]


def test_layout_report_flags_resized_near_duplicate_timeframes(tmp_path: Path) -> None:
    daily = _image(tmp_path / "charts" / "daily.png", color=(64, 128, 192), size=(80, 80))
    h1 = _image(tmp_path / "charts" / "h1.png", color=(64, 128, 192), size=(40, 40))
    m5 = _image(tmp_path / "charts" / "m5.png", color=(220, 220, 220), size=(80, 80))
    packet = {
        "items": [
            {
                "example_id": "near-duplicate-case",
                "priority_score": 10,
                "chart_paths": {"daily": daily, "h1": h1, "m5": m5},
                "candidate_state": {"missing_evidence": []},
            }
        ]
    }

    report = analyze_packet(packet, root_dir=tmp_path, packet_path=tmp_path / "packet.json", max_hamming=8)

    assert report["action_counts"] == {"skip_invalid_layout": 1}
    assert report["layout_flag_counts"] == {"near_duplicate_timeframe_images": 1}
    assert report["items"][0]["near_duplicate_pairs"][0]["pair"] == ["daily", "h1"]


def test_layout_report_allows_distinct_existing_images(tmp_path: Path) -> None:
    packet = {
        "items": [
            {
                "example_id": "usable-case",
                "priority_score": 10,
                "chart_paths": {
                    "daily": _pattern_image(tmp_path / "charts" / "daily.png", pattern="up"),
                    "h1": _pattern_image(tmp_path / "charts" / "h1.png", pattern="down"),
                    "m5": _pattern_image(tmp_path / "charts" / "m5.png", pattern="box"),
                },
                "candidate_state": {"missing_evidence": []},
            }
        ]
    }

    report = analyze_packet(packet, root_dir=tmp_path, packet_path=tmp_path / "packet.json", max_hamming=0)

    assert report["action_counts"] == {"review_state_labels": 1}
    assert report["layout_flag_counts"] == {}


def test_image_info_reports_missing_image(tmp_path: Path) -> None:
    info = image_info(tmp_path, "missing.png")

    assert info["exists"] is False
    assert info["error"] == "missing_image"
