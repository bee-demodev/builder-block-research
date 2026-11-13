from __future__ import annotations

import json
from pathlib import Path

from scripts.build_live_tradingview_decision_report import build_decision_report
from scripts.build_live_tradingview_visual_markup import (
    attach_visual_markup,
    build_markup_request,
    validate_visual_markup,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _packet(tmp_path: Path, *, decision_ready: bool = True) -> dict:
    corpus_path = tmp_path / "knowledge" / "ttfm_video_corpus" / "chunks.jsonl"
    visual_path = tmp_path / "knowledge" / "ttfm_video_corpus" / "visual_windows.jsonl"
    _write_jsonl(
        corpus_path,
        [
            {
                "example_id": "fractal_model_fundamentals:0001",
                "title": "TTrades Playbook | Fractal Model Fundamentals",
                "topics": ["daily_bias", "poi", "fractal_model"],
                "text": "Daily bias aligns the hourly and five minute model with a protected swing and point of interest.",
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
                "text": "Wait for the sweep and then the continuation entry after confirmation closure.",
            }
        ],
    )
    return {
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
        },
    }


def test_markup_request_contains_all_timeframe_images_and_schema(tmp_path: Path) -> None:
    packet = _packet(tmp_path)
    for path in packet["chart_paths"].values():
        Path(path).write_text("stub", encoding="utf-8")

    request = build_markup_request(packet, root_dir=tmp_path, packet_path=tmp_path / "packet.json")

    assert request["mode"] == "live_tradingview_visual_markup_request"
    assert request["symbol"] == "CME_MINI:ESM2026"
    assert [image["timeframe"] for image in request["images"]] == ["daily", "h1", "m5"]
    assert all(image["exists"] for image in request["images"])
    assert "sweep" in request["allowed_labels"]
    assert "missing_context" in request["allowed_labels"]
    assert request["output_schema"]["labels"][0]["timeframe"] == "daily | h1 | m5"


def test_validate_markup_rejects_bad_label_and_bad_timeframe(tmp_path: Path) -> None:
    packet = _packet(tmp_path)
    markup = {
        "summary": "Bad markup",
        "labels": [
            {"label": "made_up", "timeframe": "m5", "confidence": 0.9},
            {"label": "sweep", "timeframe": "weekly", "confidence": 0.9},
        ],
    }

    result = validate_visual_markup(markup, packet)

    assert result["verified"] is False
    assert result["status"] == "needs_review"
    assert "label_0_unsupported:made_up" in result["validation_issues"]
    assert "label_1_bad_timeframe:weekly" in result["validation_issues"]
    assert "daily_context_not_marked" in result["blocking_issues"]
    assert result["labels"] == []


def test_validate_markup_requires_daily_h1_and_m5_visible_evidence(tmp_path: Path) -> None:
    packet = _packet(tmp_path)
    markup = {
        "summary": "M5 shows a sweep but HTF context is not marked.",
        "labels": [
            {"label": "sweep", "timeframe": "m5", "confidence": 0.92, "evidence": "visible run below prior low"},
        ],
    }

    result = validate_visual_markup(markup, packet)

    assert result["verified"] is False
    assert result["coverage"]["m5_entry_evidence"] is True
    assert "daily_context_not_marked" in result["blocking_issues"]
    assert "h1_structure_not_marked" in result["blocking_issues"]


def test_valid_markup_can_be_attached_and_unlocks_take_report(tmp_path: Path) -> None:
    packet = _packet(tmp_path)
    markup = {
        "summary": "Daily bias, H1 structure, and M5 sweep/entry are all visible.",
        "direction_hint": "bullish",
        "entry_readiness": "ready",
        "labels": [
            {"label": "daily_bias", "timeframe": "daily", "confidence": 0.86, "evidence": "daily context is aligned bullish"},
            {"label": "protected_swing", "timeframe": "h1", "confidence": 0.82, "evidence": "protected low is visible"},
            {"label": "poi_or_reaction_zone", "timeframe": "h1", "confidence": 0.8, "evidence": "reaction zone is visible"},
            {"label": "sweep", "timeframe": "m5", "confidence": 0.91, "evidence": "sweep is visible"},
            {"label": "entry_trigger", "timeframe": "m5", "confidence": 0.88, "evidence": "confirmation close is visible"},
        ],
    }

    visual_markup = validate_visual_markup(markup, packet)
    updated_packet = attach_visual_markup(packet, visual_markup)
    report = build_decision_report(updated_packet, root_dir=tmp_path, packet_path=tmp_path / "packet.json")

    assert visual_markup["verified"] is True
    assert updated_packet["visual_markup"]["status"] == "verified"
    assert report["verdict"] == "take"
    assert report["warnings"] == []


def test_missing_context_label_blocks_verification(tmp_path: Path) -> None:
    packet = _packet(tmp_path)
    markup = {
        "summary": "Daily context is blocked.",
        "labels": [
            {"label": "daily_bias", "timeframe": "daily", "confidence": 0.7},
            {"label": "protected_swing", "timeframe": "h1", "confidence": 0.7},
            {"label": "sweep", "timeframe": "m5", "confidence": 0.7},
            {"label": "missing_context", "timeframe": "daily", "confidence": 0.95},
        ],
    }

    result = validate_visual_markup(markup, packet)

    assert result["verified"] is False
    assert "visual_missing_context" in result["blocking_issues"]
