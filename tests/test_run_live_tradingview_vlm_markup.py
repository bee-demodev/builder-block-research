from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw

from scripts.run_live_tradingview_vlm_markup import (
    parse_markup_text,
    request_payload_for_markup,
    run_vlm_markup,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_image(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (120, 80), (245, 245, 245))
    draw = ImageDraw.Draw(image)
    draw.line((10, 60, 50, 35, 110, 15), fill=(20, 20, 20), width=4)
    image.save(path)


def _packet(tmp_path: Path) -> dict:
    daily = tmp_path / "daily.png"
    h1 = tmp_path / "h1.png"
    m5 = tmp_path / "m5.png"
    for path in (daily, h1, m5):
        _write_image(path)
    return {
        "packet_version": "tv_decision_bundle_v1",
        "symbol": "CME_MINI:NQU2026",
        "decision_ready": True,
        "blocked_reasons": [],
        "chart_paths": {
            "daily": str(daily),
            "h1": str(h1),
            "m5": str(m5),
        },
        "visual_markup_request": {"labels_to_mark": ["sweep"]},
        "bundle_record": {
            "direction": "bullish",
            "htf_bias": "bullish",
            "entry_state": "long_ready",
        },
    }


def _valid_markup() -> dict:
    return {
        "summary": "Daily, H1, and M5 evidence visible.",
        "direction_hint": "bullish",
        "entry_readiness": "ready",
        "labels": [
            {"label": "daily_bias", "timeframe": "daily", "confidence": 0.82, "evidence": "daily bias visible"},
            {"label": "protected_swing", "timeframe": "h1", "confidence": 0.8, "evidence": "protected swing visible"},
            {"label": "poi_or_reaction_zone", "timeframe": "h1", "confidence": 0.78, "evidence": "POI visible"},
            {"label": "sweep", "timeframe": "m5", "confidence": 0.9, "evidence": "sweep visible"},
            {"label": "entry_trigger", "timeframe": "m5", "confidence": 0.86, "evidence": "entry trigger visible"},
        ],
    }


def test_parse_markup_text_accepts_fenced_json() -> None:
    payload = parse_markup_text("```json\n{\"summary\":\"ok\",\"labels\":[]}\n```")

    assert payload == {"summary": "ok", "labels": []}


def test_request_payload_includes_three_images(tmp_path: Path) -> None:
    packet = _packet(tmp_path)
    request = {
        "images": [
            {"timeframe": "daily", "path": packet["chart_paths"]["daily"], "exists": True},
            {"timeframe": "h1", "path": packet["chart_paths"]["h1"], "exists": True},
            {"timeframe": "m5", "path": packet["chart_paths"]["m5"], "exists": True},
        ],
        "output_schema": {"labels": []},
    }

    payload = request_payload_for_markup(request, root_dir=tmp_path, model="test-model")

    user_content = payload["input"][1]["content"]
    assert payload["model"] == "test-model"
    assert sum(1 for item in user_content if item["type"] == "input_image") == 3
    assert all(item["image_url"].startswith("data:image/png;base64,") for item in user_content if item["type"] == "input_image")


def test_run_vlm_markup_missing_key_writes_request_and_status(tmp_path: Path) -> None:
    packet_path = tmp_path / "results" / "packet.json"
    request_path = tmp_path / "results" / "request.json"
    markup_path = tmp_path / "results" / "markup.json"
    raw_path = tmp_path / "results" / "raw.json"
    _write_json(packet_path, _packet(tmp_path))

    result = run_vlm_markup(
        packet_path=packet_path,
        request_path=request_path,
        markup_output_path=markup_path,
        raw_response_path=raw_path,
        root_dir=tmp_path,
        model="test-model",
        timeout_seconds=30,
        api_key="",
    )

    assert result["status"] == "missing_api_key"
    assert request_path.exists()
    assert markup_path.exists()
    assert not raw_path.exists()
    assert "visual_markup" not in json.loads(packet_path.read_text(encoding="utf-8"))


def test_run_vlm_markup_validates_response_and_updates_packet(tmp_path: Path) -> None:
    packet_path = tmp_path / "results" / "packet.json"
    request_path = tmp_path / "results" / "request.json"
    markup_path = tmp_path / "results" / "markup.json"
    raw_path = tmp_path / "results" / "raw.json"
    _write_json(packet_path, _packet(tmp_path))
    seen_payloads: list[dict] = []

    def fake_post(payload: dict, api_key: str, timeout_seconds: int) -> dict:
        seen_payloads.append(payload)
        assert api_key == "test-key"
        assert timeout_seconds == 30
        return {"output_text": json.dumps(_valid_markup())}

    result = run_vlm_markup(
        packet_path=packet_path,
        request_path=request_path,
        markup_output_path=markup_path,
        raw_response_path=raw_path,
        root_dir=tmp_path,
        model="test-model",
        timeout_seconds=30,
        api_key="test-key",
        post_func=fake_post,
    )

    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    markup = json.loads(markup_path.read_text(encoding="utf-8"))
    assert result["status"] == "verified"
    assert result["verified"] is True
    assert markup["verified"] is True
    assert packet["visual_markup"]["status"] == "verified"
    assert raw_path.exists()
    assert seen_payloads
