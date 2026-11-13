from __future__ import annotations

import json
import struct
from pathlib import Path

from config import build_config
from scripts.run_manual_tradingview_decision_pipeline import run_manual_decision_pipeline


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


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


def _write_corpus(tmp_path: Path) -> None:
    _write_jsonl(
        tmp_path / "knowledge" / "ttfm_video_corpus" / "chunks.jsonl",
        [
            {
                "example_id": "fractal_model_fundamentals:0001",
                "title": "TTrades Playbook | Fractal Model Fundamentals",
                "topics": ["daily_bias", "poi", "fractal_model"],
                "text": "Daily bias aligns the hourly and five minute model. Protected swing and point of interest matter.",
            }
        ],
    )
    _write_jsonl(
        tmp_path / "knowledge" / "ttfm_video_corpus" / "visual_windows.jsonl",
        [
            {
                "example_id": "youtube_fractal_model_fundamentals_visual_v1::sweep",
                "title": "TTrades Playbook | Fractal Model Fundamentals",
                "topics": ["liquidity_sweep", "entry_trigger"],
                "checkpoint": "sweep",
                "text": "Wait for the sweep and continuation entry after confirmation closure.",
            }
        ],
    )


def _verified_markup() -> dict:
    return {
        "summary": "All required timeframe evidence is visible.",
        "direction_hint": "bullish",
        "entry_readiness": "ready",
        "labels": [
            {"label": "daily_bias", "timeframe": "daily", "confidence": 0.86, "evidence": "daily bias visible"},
            {"label": "protected_swing", "timeframe": "h1", "confidence": 0.82, "evidence": "protected low visible"},
            {"label": "poi_or_reaction_zone", "timeframe": "h1", "confidence": 0.8, "evidence": "reaction zone visible"},
            {"label": "invalidation", "timeframe": "h1", "confidence": 0.81, "evidence": "invalidation level visible"},
            {"label": "sweep", "timeframe": "m5", "confidence": 0.9, "evidence": "sweep visible"},
            {"label": "entry_trigger", "timeframe": "m5", "confidence": 0.88, "evidence": "confirmation visible"},
        ],
    }


def _screens(tmp_path: Path, *, width: int = 1920, height: int = 1080) -> tuple[Path, Path, Path]:
    daily = tmp_path / "screens" / "daily.png"
    h1 = tmp_path / "screens" / "h1.png"
    m5 = tmp_path / "screens" / "m5.png"
    for path in (daily, h1, m5):
        _write_png_header(path, width=width, height=height)
    return daily, h1, m5


def test_manual_decision_pipeline_blocks_bad_screenshots_before_pipeline(tmp_path: Path) -> None:
    config = build_config(root_dir=tmp_path)
    daily, h1, m5 = _screens(tmp_path)
    h1.write_bytes(daily.read_bytes())
    packet_path = tmp_path / "results" / "packet.json"
    run_report_path = tmp_path / "results" / "manual_run.json"

    def fail_pipeline(**_kwargs) -> dict:
        raise AssertionError("pipeline must not run for blocked screenshots")

    report = run_manual_decision_pipeline(
        config=config,
        symbol="CME_MINI:NQU2026",
        daily_path=daily,
        h1_path=h1,
        m5_path=m5,
        packet_path=packet_path,
        markup_request_path=tmp_path / "results" / "request.json",
        decision_report_path=tmp_path / "results" / "decision.json",
        pipeline_report_path=tmp_path / "results" / "pipeline.json",
        run_report_path=run_report_path,
        pipeline_func=fail_pipeline,
    )

    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    persisted = json.loads(run_report_path.read_text(encoding="utf-8"))
    assert report["decision_ready"] is False
    assert report["pipeline_executed"] is False
    assert report["next_action"] == "recapture_manual_screenshots"
    assert "daily:duplicate_image_content:h1" in report["blocked_reasons"]
    assert packet["decision_ready"] is False
    assert persisted == report


def test_manual_decision_pipeline_runs_packet_markup_brief_and_journal(tmp_path: Path) -> None:
    config = build_config(root_dir=tmp_path)
    _write_corpus(tmp_path)
    daily, h1, m5 = _screens(tmp_path)
    packet_path = tmp_path / "results" / "packet.json"
    request_path = tmp_path / "results" / "request.json"
    decision_path = tmp_path / "results" / "decision.json"
    pipeline_path = tmp_path / "results" / "pipeline.json"
    run_report_path = tmp_path / "results" / "manual_run.json"
    markup_path = tmp_path / "results" / "markup.json"
    brief_path = tmp_path / "results" / "brief.md"
    journal_path = tmp_path / "results" / "journal.jsonl"
    _write_json(markup_path, _verified_markup())

    report = run_manual_decision_pipeline(
        config=config,
        symbol="CME_MINI:NQU2026",
        daily_path=daily,
        h1_path=h1,
        m5_path=m5,
        packet_path=packet_path,
        markup_request_path=request_path,
        decision_report_path=decision_path,
        pipeline_report_path=pipeline_path,
        run_report_path=run_report_path,
        markup_path=markup_path,
        render_brief=True,
        brief_path=brief_path,
        append_journal=True,
        journal_path=journal_path,
        journal_notes=["manual wrapper smoke"],
        journal_follow_up_labels=["track_outcome"],
    )

    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    request = json.loads(request_path.read_text(encoding="utf-8"))
    journal_event = json.loads(journal_path.read_text(encoding="utf-8").splitlines()[0])
    assert report["decision_ready"] is True
    assert report["pipeline_executed"] is True
    assert report["verdict"] == "take"
    assert report["markup_verified"] is True
    assert report["brief_path"] == "results\\brief.md"
    assert packet["mode"] == "manual_tradingview_screenshot_decision_support"
    assert decision["derived_ttrades_state"]["applied"] is True
    assert [image["timeframe"] for image in request["images"]] == ["daily", "h1", "m5"]
    assert "Verdict: take" in brief_path.read_text(encoding="utf-8")
    assert journal_event["journal"]["notes"] == ["manual wrapper smoke"]
