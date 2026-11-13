from __future__ import annotations

import json
from pathlib import Path

from scripts.append_live_tradingview_decision_journal import (
    append_event,
    build_journal_event,
    load_json,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_blocked_pipeline_appends_no_decision_event(tmp_path: Path) -> None:
    pipeline_path = tmp_path / "results" / "pipeline.json"
    decision_path = tmp_path / "results" / "missing_decision.json"
    journal_path = tmp_path / "results" / "journal.jsonl"
    _write_json(
        pipeline_path,
        {
            "verdict": "insufficient_evidence",
            "confidence": 0.0,
            "decision_ready": False,
            "warnings": ["preflight_blocked"],
            "next_action": "fix_preflight_blockers",
            "preflight_executed": True,
            "preflight_ready": False,
            "preflight_blocking_checks": ["tradingview_cdp"],
            "preflight_warning_checks": ["openai_api_key", "decision_packet"],
            "packet_path": "results/live_tradingview_decision_packet.json",
        },
    )

    event = build_journal_event(
        root_dir=tmp_path,
        decision_report_path=decision_path,
        pipeline_report_path=pipeline_path,
        decision_report=load_json(decision_path),
        pipeline_report=load_json(pipeline_path),
    )
    append_event(journal_path, event)

    persisted = _read_jsonl(journal_path)[0]
    assert persisted["event_type"] == "blocked_or_no_decision"
    assert persisted["decision"]["verdict"] == "insufficient_evidence"
    assert persisted["decision"]["next_action"] == "fix_preflight_blockers"
    assert persisted["preflight"]["blocking_checks"] == ["tradingview_cdp"]
    assert persisted["journal"]["status"] == "not_applicable"
    assert persisted["journal"]["outcome"] == "not_applicable"
    assert persisted["journal"]["classification"] == "not_applicable"


def test_take_decision_appends_pending_outcome_event(tmp_path: Path) -> None:
    decision_path = tmp_path / "results" / "decision.json"
    pipeline_path = tmp_path / "results" / "pipeline.json"
    _write_json(
        decision_path,
        {
            "source_packet_path": "results/live_tradingview_decision_packet.json",
            "symbol": "CME_MINI:NQU2026",
            "verdict": "take",
            "confidence": 0.84,
            "decision_ready": True,
            "warnings": [],
            "reasons": [],
            "decision_writeup": {
                "missing_or_unverified": [],
            },
            "retrieval_hits": [
                {
                    "source_path": "knowledge/ttfm_video_corpus/chunks.jsonl",
                    "example_id": "fractal_model_fundamentals:0001",
                    "title": "Fractal Model Fundamentals",
                    "checkpoint": "sweep",
                    "score": 11,
                    "matched_terms": ["sweep", "entry"],
                }
            ],
            "chart_paths": {"m5": "results/live_tradingview/m5.png"},
        },
    )
    _write_json(
        pipeline_path,
        {
            "decision_report_path": "results/live_tradingview_decision_report.json",
            "next_action": "review_trade_decision",
            "preflight_executed": True,
            "preflight_ready": True,
        },
    )

    event = build_journal_event(
        root_dir=tmp_path,
        decision_report_path=decision_path,
        pipeline_report_path=pipeline_path,
        decision_report=load_json(decision_path),
        pipeline_report=load_json(pipeline_path),
        notes=["pending outcome after trader review"],
        follow_up_labels=["track_outcome"],
    )

    assert event["event_type"] == "decision_pending_outcome"
    assert event["decision"]["symbol"] == "CME_MINI:NQU2026"
    assert event["decision"]["verdict"] == "take"
    assert event["journal"]["status"] == "pending_outcome"
    assert event["journal"]["outcome"] == "unknown"
    assert event["journal"]["classification"] == "not_reviewed"
    assert event["journal"]["notes"] == ["pending outcome after trader review"]
    assert event["journal"]["follow_up_labels"] == ["track_outcome"]
    assert event["retrieval_evidence"][0]["matched_terms"] == ["sweep", "entry"]


def test_explicit_loss_classification_logs_outcome(tmp_path: Path) -> None:
    decision_path = tmp_path / "results" / "decision.json"
    pipeline_path = tmp_path / "results" / "pipeline.json"
    _write_json(
        decision_path,
        {
            "symbol": "CME_MINI:ESU2026",
            "verdict": "take",
            "confidence": 0.77,
            "decision_ready": True,
            "warnings": [],
        },
    )
    _write_json(pipeline_path, {"next_action": "review_trade_decision"})

    event = build_journal_event(
        root_dir=tmp_path,
        decision_report_path=decision_path,
        pipeline_report_path=pipeline_path,
        decision_report=load_json(decision_path),
        pipeline_report=load_json(pipeline_path),
        outcome="loss",
        classification="valid_loss_part_of_odds",
        notes=["setup was valid; stop hit inside expected distribution"],
        follow_up_labels=["odds_loss_case"],
    )

    assert event["event_type"] == "outcome_logged"
    assert event["journal"]["status"] == "outcome_logged"
    assert event["journal"]["outcome"] == "loss"
    assert event["journal"]["classification"] == "valid_loss_part_of_odds"
    assert event["journal"]["follow_up_labels"] == ["odds_loss_case"]
