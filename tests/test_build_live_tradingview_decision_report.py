from __future__ import annotations

import json
from pathlib import Path

from scripts.build_live_tradingview_decision_report import build_decision_report


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _packet(tmp_path: Path, *, decision_ready: bool = True, bundle: dict | None = None, visual_markup: dict | None = None) -> dict:
    corpus_path = tmp_path / "knowledge" / "ttfm_video_corpus" / "chunks.jsonl"
    visual_path = tmp_path / "knowledge" / "ttfm_video_corpus" / "visual_windows.jsonl"
    _write_jsonl(
        corpus_path,
        [
            {
                "example_id": "fractal_model_fundamentals:0001",
                "video_slug": "fractal_model_fundamentals",
                "title": "TTrades Playbook | Fractal Model Fundamentals",
                "topics": ["daily_bias", "poi", "fractal_model"],
                "text": "Daily bias aligns the hourly and five minute model. Use a point of interest and protected swing.",
            }
        ],
    )
    _write_jsonl(
        visual_path,
        [
            {
                "example_id": "youtube_fractal_model_fundamentals_visual_v1::sweep",
                "title": "TTrades Playbook | Fractal Model Fundamentals",
                "checkpoint": "sweep",
                "timeframe_role": "ltf",
                "topics": ["liquidity_sweep", "cisd", "entry_trigger"],
                "frame_path": "knowledge/ttfm_video_corpus/frames/fractal/sweep.jpg",
                "text": "Wait for the sweep and then the continuation entry after confirmation closure.",
            }
        ],
    )
    payload = {
        "packet_version": "tv_decision_bundle_v1",
        "symbol": "CME_MINI:ESM2026",
        "decision_ready": decision_ready,
        "blocked_reasons": [] if decision_ready else ["decision_chart_resolution_too_small"],
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
                    "query": "TTrades sweep entry confirmation CISD invalidation protected swing",
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
            **(bundle or {}),
        },
    }
    if visual_markup is not None:
        payload["visual_markup"] = visual_markup
    return payload


def _manual_placeholder_bundle() -> dict:
    return {
        "direction": "none",
        "htf_bias": "unknown",
        "fractal_stage": "unknown",
        "poi_type": "none",
        "poi_validity": False,
        "entry_state": "wait",
        "invalidation_state": "unknown",
        "setup_quality": "unknown",
        "path_family": "unknown",
        "label_confidence": 0.35,
        "source": "manual_screenshot_packet_pending_visual_state",
    }


def _manual_take_markup(direction: str = "bullish") -> dict:
    return {
        "status": "verified",
        "verified": True,
        "direction_hint": direction,
        "entry_readiness": "ready",
        "labels": [
            {"label": "daily_bias", "timeframe": "daily", "confidence": 0.8},
            {"label": "liquidity_high", "timeframe": "daily", "confidence": 0.72},
            {"label": "protected_swing", "timeframe": "h1", "confidence": 0.83},
            {"label": "poi_or_reaction_zone", "timeframe": "h1", "confidence": 0.82},
            {"label": "invalidation", "timeframe": "h1", "confidence": 0.78},
            {"label": "sweep", "timeframe": "m5", "confidence": 0.86},
            {"label": "entry_trigger", "timeframe": "m5", "confidence": 0.84},
        ],
    }


def test_report_blocks_non_decision_ready_packet(tmp_path: Path) -> None:
    packet = _packet(tmp_path, decision_ready=False)

    report = build_decision_report(packet, root_dir=tmp_path, packet_path=tmp_path / "packet.json")

    assert report["verdict"] == "insufficient_evidence"
    assert report["confidence"] <= 0.2
    assert "capture_not_decision_ready" in report["warnings"]
    assert report["decision_writeup"]["trigger_needed"].startswith("Recapture")


def test_report_watches_when_visual_markup_is_missing(tmp_path: Path) -> None:
    packet = _packet(tmp_path)

    report = build_decision_report(packet, root_dir=tmp_path, packet_path=tmp_path / "packet.json")

    assert report["verdict"] == "watch"
    assert report["confidence"] <= 0.45
    assert "visual_markup_not_verified" in report["warnings"]
    assert "m5_entry_readiness" in report["reasons"]
    assert report["retrieval_hits"]
    assert report["decision_writeup"]["trigger_needed"].startswith("Wait for verified M5")


def test_report_allows_take_only_after_verified_visual_markup(tmp_path: Path) -> None:
    packet = _packet(
        tmp_path,
        visual_markup={
            "verified": True,
            "labels": [
                {"label": "sweep", "timeframe": "m5"},
                {"label": "protected_swing", "timeframe": "h1"},
                {"label": "poi_or_reaction_zone", "timeframe": "h1"},
            ],
        },
    )

    report = build_decision_report(packet, root_dir=tmp_path, packet_path=tmp_path / "packet.json")

    assert report["verdict"] == "take"
    assert report["confidence"] >= 0.7
    assert report["warnings"] == []
    assert report["decision_writeup"]["direction"] == "bullish"
    assert all(item["status"] == "passed" for item in report["checklist"] if item["required_for_take"])


def test_report_rejects_no_setup_even_when_capture_is_ready(tmp_path: Path) -> None:
    packet = _packet(
        tmp_path,
        bundle={
            "direction": "none",
            "htf_bias": "neutral",
            "entry_state": "wait",
            "setup_quality": "no_setup",
        },
        visual_markup={"verified": True, "labels": [{"label": "missing_context"}]},
    )

    report = build_decision_report(packet, root_dir=tmp_path, packet_path=tmp_path / "packet.json")

    assert report["verdict"] == "no_trade"
    assert "setup_quality=no_setup" in report["reasons"]
    assert report["decision_writeup"]["headline"] == "No trade by the current TTrades gate."


def test_report_derives_take_from_manual_screenshot_visual_markup(tmp_path: Path) -> None:
    packet = _packet(
        tmp_path,
        bundle=_manual_placeholder_bundle(),
        visual_markup=_manual_take_markup("bullish"),
    )

    report = build_decision_report(packet, root_dir=tmp_path, packet_path=tmp_path / "packet.json")

    assert report["verdict"] == "take"
    assert report["warnings"] == []
    assert report["derived_ttrades_state"]["applied"] is True
    state = report["derived_ttrades_state"]["state"]
    assert state["source"] == "visual_markup_derived_state"
    assert state["direction"] == "bullish"
    assert state["htf_bias"] == "bullish"
    assert state["entry_state"] == "long_ready"
    assert state["poi_validity"] is True
    assert state["invalidation_state"] == "intact"
    assert report["decision_writeup"]["direction"] == "bullish"
    assert all(item["status"] == "passed" for item in report["checklist"] if item["required_for_take"])


def test_report_derives_watch_when_manual_markup_lacks_m5_entry(tmp_path: Path) -> None:
    markup = {
        "status": "verified",
        "verified": True,
        "direction_hint": "bearish",
        "entry_readiness": "wait",
        "labels": [
            {"label": "daily_bias", "timeframe": "daily"},
            {"label": "liquidity_low", "timeframe": "daily"},
            {"label": "protected_swing", "timeframe": "h1"},
            {"label": "poi_or_reaction_zone", "timeframe": "h1"},
            {"label": "invalidation", "timeframe": "h1"},
        ],
    }
    packet = _packet(
        tmp_path,
        bundle=_manual_placeholder_bundle(),
        visual_markup=markup,
    )

    report = build_decision_report(packet, root_dir=tmp_path, packet_path=tmp_path / "packet.json")

    assert report["verdict"] == "watch"
    assert "m5_entry_readiness" in report["reasons"]
    state = report["derived_ttrades_state"]["state"]
    assert state["direction"] == "bearish"
    assert state["entry_state"] == "wait"
    assert report["decision_writeup"]["trigger_needed"].startswith("Wait for verified M5")


def test_report_blocks_manual_markup_with_missing_context(tmp_path: Path) -> None:
    markup = _manual_take_markup("bullish")
    markup["labels"] = list(markup["labels"]) + [{"label": "missing_context", "timeframe": "h1"}]
    packet = _packet(
        tmp_path,
        bundle=_manual_placeholder_bundle(),
        visual_markup=markup,
    )

    report = build_decision_report(packet, root_dir=tmp_path, packet_path=tmp_path / "packet.json")

    assert report["verdict"] == "insufficient_evidence"
    assert "visual_missing_context" in report["reasons"]
    assert report["derived_ttrades_state"]["applied"] is True
    assert "visual_missing_context" in report["derived_ttrades_state"]["blocking_issues"]


def test_report_keeps_manual_packet_without_visual_markup_insufficient(tmp_path: Path) -> None:
    packet = _packet(tmp_path, bundle=_manual_placeholder_bundle())

    report = build_decision_report(packet, root_dir=tmp_path, packet_path=tmp_path / "packet.json")

    assert report["verdict"] == "insufficient_evidence"
    assert report["reasons"] == ["visual_markup_not_verified"]
    assert "visual_markup_not_verified" in report["warnings"]
    assert report["derived_ttrades_state"]["applied"] is False
