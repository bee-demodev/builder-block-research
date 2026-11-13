from __future__ import annotations

import json
from pathlib import Path

from scripts.render_live_tradingview_decision_brief import write_brief


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_renders_decision_report_brief(tmp_path: Path) -> None:
    decision_path = tmp_path / "results" / "decision.json"
    pipeline_path = tmp_path / "results" / "pipeline.json"
    output_path = tmp_path / "results" / "brief.md"
    _write_json(
        decision_path,
        {
            "symbol": "CME_MINI:NQU2026",
            "verdict": "take",
            "confidence": 0.81,
            "decision_ready": True,
            "warnings": [],
            "decision_writeup": {
                "headline": "Bullish setup is decision-ready by the current checklist.",
                "direction": "bullish",
                "trigger_needed": "Use the verified M5 entry trigger.",
                "invalidation": "intact",
                "missing_or_unverified": [],
            },
            "checklist": [
                {"field": "daily_bias", "status": "passed", "evidence": "htf_bias=bullish"},
                {"field": "liquidity_draw", "status": "passed", "evidence": "sweep visible"},
            ],
            "retrieval_hits": [
                {
                    "title": "Fractal Model Fundamentals",
                    "source_path": "knowledge/ttfm_video_corpus/chunks.jsonl",
                    "checkpoint": "sweep",
                    "excerpt": "Wait for the sweep and confirmation closure.",
                }
            ],
            "chart_paths": {"daily": "results/live_tradingview/daily.png"},
        },
    )
    _write_json(
        pipeline_path,
        {
            "decision_report_path": "results/decision.json",
            "next_action": "review_trade_decision",
            "warnings": [],
        },
    )

    summary = write_brief(
        root_dir=tmp_path,
        decision_report_path=decision_path,
        pipeline_report_path=pipeline_path,
        output_path=output_path,
    )

    text = output_path.read_text(encoding="utf-8")
    assert summary["used_decision_report"] is True
    assert summary["verdict"] == "take"
    assert "Verdict: take" in text
    assert "Symbol: CME_MINI:NQU2026" in text
    assert "- daily_bias: passed - htf_bias=bullish" in text
    assert "Fractal Model Fundamentals" in text
    assert "review_trade_decision" in text


def test_renders_pipeline_fallback_when_decision_report_missing(tmp_path: Path) -> None:
    decision_path = tmp_path / "results" / "missing_decision.json"
    pipeline_path = tmp_path / "results" / "pipeline.json"
    output_path = tmp_path / "results" / "brief.md"
    _write_json(
        pipeline_path,
        {
            "verdict": "insufficient_evidence",
            "confidence": 0.0,
            "decision_ready": False,
            "next_action": "fix_preflight_blockers",
            "preflight_ready": False,
            "preflight_blocking_checks": ["tradingview_cdp"],
            "preflight_warning_checks": ["openai_api_key", "decision_packet"],
            "packet_path": "results/live_tradingview_decision_packet.json",
        },
    )

    summary = write_brief(
        root_dir=tmp_path,
        decision_report_path=decision_path,
        pipeline_report_path=pipeline_path,
        output_path=output_path,
    )

    text = output_path.read_text(encoding="utf-8")
    assert summary["used_decision_report"] is False
    assert summary["used_pipeline_report"] is True
    assert summary["verdict"] == "insufficient_evidence"
    assert "Blocking checks: tradingview_cdp" in text
    assert "Warning checks: openai_api_key, decision_packet" in text
    assert "No trade decision was produced" in text
