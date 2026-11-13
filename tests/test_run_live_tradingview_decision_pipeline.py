from __future__ import annotations

import json
import struct
from pathlib import Path

from config import build_config
from scripts.build_manual_tradingview_decision_packet import build_manual_packet
from scripts.run_live_tradingview_decision_pipeline import run_live_decision_pipeline


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


def _packet(tmp_path: Path) -> dict:
    _write_corpus(tmp_path)
    return {
        "packet_version": "tv_decision_bundle_v1",
        "symbol": "CME_MINI:NQU2026",
        "decision_ready": True,
        "blocked_reasons": [],
        "chart_paths": {
            "daily": str(tmp_path / "daily.png"),
            "h1": str(tmp_path / "h1.png"),
            "m5": str(tmp_path / "m5.png"),
        },
        "retrieval_context": {
            "corpus": [
                "knowledge/ttfm_video_corpus/chunks.jsonl",
                "knowledge/ttfm_video_corpus/visual_windows.jsonl",
            ],
            "queries": [
                {
                    "name": "timeframe_alignment",
                    "query": "TTrades daily h1 m5 bias timeframe alignment point of interest",
                    "filters": {"concepts": ["daily_bias", "poi"]},
                },
                {
                    "name": "entry_and_invalidation",
                    "query": "TTrades sweep entry confirmation invalidation protected swing",
                    "filters": {"concepts": ["liquidity_sweep", "entry_trigger"]},
                },
            ],
        },
        "bundle_record": {
            "direction": "bullish",
            "htf_bias": "bullish",
            "fractal_stage": "c4",
            "poi_type": "protected_swing_zone",
            "poi_validity": True,
            "entry_state": "long_ready",
            "invalidation_state": "intact",
            "setup_quality": "good_setup",
            "path_family": "continuation",
            "label_confidence": 0.82,
        },
    }


def _manual_packet(tmp_path: Path) -> dict:
    _write_corpus(tmp_path)
    screen_dir = tmp_path / "screens"
    daily = screen_dir / "daily.png"
    h1 = screen_dir / "h1.png"
    m5 = screen_dir / "m5.png"
    _write_png_header(daily, width=1920, height=1080)
    _write_png_header(h1, width=1920, height=1080)
    _write_png_header(m5, width=1920, height=1080)
    return build_manual_packet(
        root_dir=tmp_path,
        symbol="CME_MINI:NQU2026",
        daily_path=daily,
        h1_path=h1,
        m5_path=m5,
        source_note="pipeline manual screenshot integration",
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


def test_pipeline_existing_packet_creates_markup_request_and_watch_report(tmp_path: Path) -> None:
    config = build_config(root_dir=tmp_path)
    packet_path = tmp_path / "results" / "packet.json"
    request_path = tmp_path / "results" / "markup_request.json"
    decision_path = tmp_path / "results" / "decision.json"
    pipeline_path = tmp_path / "results" / "pipeline.json"
    _write_json(packet_path, _packet(tmp_path))

    report = run_live_decision_pipeline(
        config=config,
        packet_path=packet_path,
        markup_request_path=request_path,
        decision_report_path=decision_path,
        pipeline_report_path=pipeline_path,
        skip_capture=True,
    )

    request = json.loads(request_path.read_text(encoding="utf-8"))
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    persisted = json.loads(pipeline_path.read_text(encoding="utf-8"))
    assert report["verdict"] == "watch"
    assert report["next_action"] == "send_markup_request_to_codex_vlm"
    assert request["mode"] == "live_tradingview_visual_markup_request"
    assert decision["warnings"] == ["visual_markup_not_verified"]
    assert persisted["decision_report_path"] == "results\\decision.json"


def test_pipeline_imports_markup_updates_packet_and_writes_take_report(tmp_path: Path) -> None:
    config = build_config(root_dir=tmp_path)
    packet_path = tmp_path / "results" / "packet.json"
    request_path = tmp_path / "results" / "markup_request.json"
    decision_path = tmp_path / "results" / "decision.json"
    pipeline_path = tmp_path / "results" / "pipeline.json"
    brief_path = tmp_path / "results" / "brief.md"
    journal_path = tmp_path / "results" / "journal.jsonl"
    markup_path = tmp_path / "results" / "markup.json"
    _write_json(packet_path, _packet(tmp_path))
    _write_json(markup_path, _verified_markup())

    report = run_live_decision_pipeline(
        config=config,
        packet_path=packet_path,
        markup_request_path=request_path,
        decision_report_path=decision_path,
        pipeline_report_path=pipeline_path,
        brief_path=brief_path,
        journal_path=journal_path,
        markup_path=markup_path,
        skip_capture=True,
        render_brief=True,
        append_journal=True,
        journal_notes=["paper decision pending trader outcome"],
        journal_follow_up_labels=["track_outcome"],
    )

    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    persisted = json.loads(pipeline_path.read_text(encoding="utf-8"))
    journal_event = json.loads(journal_path.read_text(encoding="utf-8").splitlines()[0])
    assert report["verdict"] == "take"
    assert report["next_action"] == "review_trade_decision"
    assert report["markup_verified"] is True
    assert report["brief_rendered"] is True
    assert report["journal_appended"] is True
    assert packet["visual_markup"]["status"] == "verified"
    assert decision["verdict"] == "take"
    assert decision["warnings"] == []
    assert "Verdict: take" in brief_path.read_text(encoding="utf-8")
    assert persisted["brief_path"] == "results\\brief.md"
    assert journal_event["event_type"] == "decision_pending_outcome"
    assert journal_event["journal"]["status"] == "pending_outcome"
    assert journal_event["journal"]["notes"] == ["paper decision pending trader outcome"]
    assert journal_event["journal"]["follow_up_labels"] == ["track_outcome"]


def test_pipeline_manual_screenshot_packet_derives_state_from_verified_markup(tmp_path: Path) -> None:
    config = build_config(root_dir=tmp_path)
    packet_path = tmp_path / "results" / "packet.json"
    request_path = tmp_path / "results" / "markup_request.json"
    decision_path = tmp_path / "results" / "decision.json"
    pipeline_path = tmp_path / "results" / "pipeline.json"
    brief_path = tmp_path / "results" / "brief.md"
    journal_path = tmp_path / "results" / "journal.jsonl"
    markup_path = tmp_path / "results" / "markup.json"
    _write_json(packet_path, _manual_packet(tmp_path))
    _write_json(markup_path, _verified_markup())

    report = run_live_decision_pipeline(
        config=config,
        packet_path=packet_path,
        markup_request_path=request_path,
        decision_report_path=decision_path,
        pipeline_report_path=pipeline_path,
        brief_path=brief_path,
        journal_path=journal_path,
        markup_path=markup_path,
        skip_capture=True,
        render_brief=True,
        append_journal=True,
        journal_notes=["manual three-timeframe screenshot decision"],
        journal_follow_up_labels=["track_outcome"],
    )

    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    request = json.loads(request_path.read_text(encoding="utf-8"))
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    journal_event = json.loads(journal_path.read_text(encoding="utf-8").splitlines()[0])
    assert report["verdict"] == "take"
    assert report["markup_verified"] is True
    assert packet["mode"] == "manual_tradingview_screenshot_decision_support"
    assert packet["visual_markup"]["coverage"]["daily_context"] is True
    assert packet["visual_markup"]["coverage"]["h1_structure"] is True
    assert packet["visual_markup"]["coverage"]["m5_entry_evidence"] is True
    assert [image["timeframe"] for image in request["images"]] == ["daily", "h1", "m5"]
    assert all(image["exists"] for image in request["images"])
    assert decision["derived_ttrades_state"]["applied"] is True
    assert decision["derived_ttrades_state"]["state"]["source"] == "visual_markup_derived_state"
    assert decision["decision_writeup"]["direction"] == "bullish"
    assert "Verdict: take" in brief_path.read_text(encoding="utf-8")
    assert journal_event["event_type"] == "decision_pending_outcome"
    assert journal_event["journal"]["notes"] == ["manual three-timeframe screenshot decision"]


def test_pipeline_can_call_vlm_adapter_before_decision(tmp_path: Path) -> None:
    config = build_config(root_dir=tmp_path)
    packet_path = tmp_path / "results" / "packet.json"
    request_path = tmp_path / "results" / "markup_request.json"
    decision_path = tmp_path / "results" / "decision.json"
    pipeline_path = tmp_path / "results" / "pipeline.json"
    vlm_markup_path = tmp_path / "results" / "vlm_markup.json"
    vlm_raw_path = tmp_path / "results" / "vlm_raw.json"
    _write_json(packet_path, _packet(tmp_path))
    calls: list[dict] = []

    def fake_vlm(**kwargs) -> dict:
        calls.append(kwargs)
        packet = json.loads(Path(kwargs["packet_path"]).read_text(encoding="utf-8"))
        packet["visual_markup"] = {
            "status": "verified",
            "verified": True,
            "labels": [
                {"label": "daily_bias", "timeframe": "daily", "confidence": 0.86, "evidence": "daily bias visible"},
                {"label": "protected_swing", "timeframe": "h1", "confidence": 0.82, "evidence": "protected low visible"},
                {"label": "poi_or_reaction_zone", "timeframe": "h1", "confidence": 0.8, "evidence": "reaction zone visible"},
                {"label": "sweep", "timeframe": "m5", "confidence": 0.9, "evidence": "sweep visible"},
                {"label": "entry_trigger", "timeframe": "m5", "confidence": 0.88, "evidence": "confirmation visible"},
            ],
            "blocking_issues": [],
            "validation_issues": [],
        }
        _write_json(Path(kwargs["request_path"]), {"mode": "request"})
        _write_json(Path(kwargs["markup_output_path"]), packet["visual_markup"])
        _write_json(Path(kwargs["raw_response_path"]), {"output_text": "{}"})
        _write_json(Path(kwargs["packet_path"]), packet)
        return {"status": "verified", "verified": True}

    report = run_live_decision_pipeline(
        config=config,
        packet_path=packet_path,
        markup_request_path=request_path,
        decision_report_path=decision_path,
        pipeline_report_path=pipeline_path,
        call_vlm=True,
        vlm_markup_output_path=vlm_markup_path,
        vlm_raw_response_path=vlm_raw_path,
        vlm_model="test-model",
        vlm_timeout_seconds=15,
        skip_capture=True,
        vlm_func=fake_vlm,
    )

    assert calls
    assert calls[0]["model"] == "test-model"
    assert calls[0]["timeout_seconds"] == 15
    assert report["vlm_called"] is True
    assert report["vlm_status"] == "verified"
    assert report["verdict"] == "take"
    assert json.loads(decision_path.read_text(encoding="utf-8"))["verdict"] == "take"


def test_pipeline_preflight_blocks_before_capture(tmp_path: Path) -> None:
    config = build_config(root_dir=tmp_path)
    packet_path = tmp_path / "results" / "packet.json"
    request_path = tmp_path / "results" / "markup_request.json"
    decision_path = tmp_path / "results" / "decision.json"
    pipeline_path = tmp_path / "results" / "pipeline.json"
    preflight_path = tmp_path / "results" / "preflight.json"
    brief_path = tmp_path / "results" / "brief.md"
    journal_path = tmp_path / "results" / "journal.jsonl"
    preflight_calls: list[dict] = []

    def fake_preflight(**kwargs) -> dict:
        preflight_calls.append(kwargs)
        return {
            "mode": "live_tradingview_decision_preflight",
            "ready": False,
            "blocking_checks": [{"name": "tradingview_cdp", "status": "unreachable"}],
            "warning_checks": [{"name": "openai_api_key", "status": "missing"}],
        }

    def fail_capture(*args, **kwargs) -> dict:
        raise AssertionError("capture must not run when preflight blocks")

    report = run_live_decision_pipeline(
        config=config,
        packet_path=packet_path,
        markup_request_path=request_path,
        decision_report_path=decision_path,
        pipeline_report_path=pipeline_path,
        preflight_report_path=preflight_path,
        brief_path=brief_path,
        journal_path=journal_path,
        preflight=True,
        preflight_timeout_seconds=3,
        render_brief=True,
        append_journal=True,
        journal_notes=["blocked before capture"],
        journal_follow_up_labels=["fix_tradingview_cdp"],
        call_vlm=True,
        capture_func=fail_capture,
        preflight_func=fake_preflight,
    )

    persisted = json.loads(pipeline_path.read_text(encoding="utf-8"))
    preflight_report = json.loads(preflight_path.read_text(encoding="utf-8"))
    journal_event = json.loads(journal_path.read_text(encoding="utf-8").splitlines()[0])
    assert preflight_calls
    assert preflight_calls[0]["timeout_seconds"] == 3
    assert preflight_calls[0]["require_packet"] is False
    assert preflight_calls[0]["require_openai_key"] is True
    assert report["capture_executed"] is False
    assert report["next_action"] == "fix_preflight_blockers"
    assert report["preflight_blocking_checks"] == ["tradingview_cdp"]
    assert report["warnings"] == ["preflight_blocked"]
    assert report["verdict"] == "insufficient_evidence"
    assert persisted == report
    assert report["brief_rendered"] is True
    assert report["brief_path"] == "results\\brief.md"
    assert report["journal_appended"] is True
    assert journal_event["event_type"] == "blocked_or_no_decision"
    assert journal_event["journal"]["classification"] == "not_applicable"
    assert journal_event["journal"]["notes"] == ["blocked before capture"]
    assert journal_event["journal"]["follow_up_labels"] == ["fix_tradingview_cdp"]
    assert "Blocking checks: tradingview_cdp" in brief_path.read_text(encoding="utf-8")
    assert preflight_report["ready"] is False
    assert not request_path.exists()
    assert not decision_path.exists()
