from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.build_ttrades_state_review_focus_queue import (
    FocusQueueConfig,
    build_focus_queue,
    write_focus_queue,
)


def _packet() -> dict:
    return {
        "items": [
            {
                "example_id": "case-a::c4",
                "selection_reasons": ["priority_state_gap"],
                "candidate_state": {
                    "missing_evidence": [
                        "manual_visual_review_required",
                        "directional_bias_unlabeled",
                    ]
                },
                "corpus_evidence": [{"chunk_id": "demo:1"}],
                "training_eligible": True,
            },
            {
                "example_id": "case-b::c2",
                "selection_reasons": [],
                "candidate_state": {"missing_evidence": ["manual_visual_review_required"]},
                "corpus_evidence": [{"chunk_id": "demo:2"}, {"chunk_id": "demo:3"}],
                "training_eligible": True,
            },
            {
                "example_id": "case-c::none",
                "candidate_state": {"missing_evidence": []},
                "corpus_evidence": [],
                "training_eligible": True,
            },
        ]
    }


def _visual_suggestions() -> dict:
    return {
        "next_review_order": ["case-a::c4", "case-b::c2"],
        "items": [
            {
                "example_id": "case-a::c4",
                "visual_review_status": "usable_candidate_review_only",
                "recommended_next_action": "Review first.",
                "promotion_blockers": ["Confirm alignment."],
            },
            {
                "example_id": "case-b::c2",
                "visual_review_status": "usable_candidate_review_only",
                "recommended_next_action": "Review second.",
                "promotion_blockers": ["Confirm C2 state."],
            },
            {
                "example_id": "case-c::none",
                "visual_review_status": "skip_capture_quality",
            },
        ],
    }


def test_focus_queue_filters_review_order_and_forces_non_trainable(tmp_path: Path) -> None:
    focused = build_focus_queue(
        _packet(),
        _visual_suggestions(),
        packet_path=tmp_path / "packet.json",
        visual_suggestions_path=tmp_path / "visual.json",
        root_dir=tmp_path,
    )

    assert [item["example_id"] for item in focused["items"]] == ["case-a::c4", "case-b::c2"]
    assert focused["selection_summary"] == {
        "candidate_count": 2,
        "source_candidate_count": 3,
        "visual_review_first_count": 2,
        "capture_quality_reviewable_count": 0,
        "training_eligible_count": 0,
        "excluded_for_capture_quality_count": 0,
        "missing_evidence_counts": {
            "directional_bias_unlabeled": 1,
            "manual_visual_review_required": 2,
        },
        "corpus_evidence_item_count": 2,
        "corpus_evidence_total_rows": 3,
    }
    assert all(item["training_eligible"] is False for item in focused["items"])
    assert focused["items"][0]["visual_suggestion_ref"]["training_eligible"] is False
    assert "codex_visual_review_first" in focused["items"][0]["selection_reasons"]
    assert focused["items"][0]["visual_suggestion_ref"]["promotion_blockers"] == ["Confirm alignment."]
    assert focused["excluded_for_capture_quality"] == []


def test_focus_queue_excludes_capture_quality_failures(tmp_path: Path) -> None:
    focused = build_focus_queue(
        _packet(),
        _visual_suggestions(),
        packet_path=tmp_path / "packet.json",
        visual_suggestions_path=tmp_path / "visual.json",
        capture_quality_path=tmp_path / "capture_quality.json",
        capture_quality={
            "items": [
                {
                    "example_id": "case-a::c4",
                    "recommended_action": "review_state_labels",
                    "quality_flags": [],
                },
                {
                    "example_id": "case-b::c2",
                    "recommended_action": "recapture_before_review",
                    "quality_flags": ["low_information_timeframe_image"],
                },
            ]
        },
        root_dir=tmp_path,
    )

    assert [item["example_id"] for item in focused["items"]] == ["case-a::c4"]
    assert focused["items"][0]["capture_quality_ref"] == {
        "source": "capture_quality.json",
        "recommended_action": "review_state_labels",
        "quality_flags": [],
    }
    assert focused["selection_summary"]["excluded_for_capture_quality_count"] == 1
    assert focused["selection_summary"]["capture_quality_reviewable_count"] == 0
    assert focused["excluded_for_capture_quality"] == [
        {
            "example_id": "case-b::c2",
            "recommended_action": "recapture_before_review",
            "quality_flags": ["low_information_timeframe_image"],
        }
    ]


def test_focus_queue_writes_output(tmp_path: Path) -> None:
    packet_path = tmp_path / "packet.json"
    visual_path = tmp_path / "visual.json"
    output_path = tmp_path / "results" / "focused.json"
    packet_path.write_text(json.dumps(_packet()), encoding="utf-8")
    visual_path.write_text(json.dumps(_visual_suggestions()), encoding="utf-8")

    focused = write_focus_queue(
        FocusQueueConfig(
            root_dir=tmp_path,
            packet_path=packet_path,
            visual_suggestions_path=visual_path,
            output_path=output_path,
        ),
        json.loads(packet_path.read_text(encoding="utf-8")),
        json.loads(visual_path.read_text(encoding="utf-8")),
    )

    written = json.loads(output_path.read_text(encoding="utf-8"))
    assert written["items"] == focused["items"]
    assert written["selection_summary"]["training_eligible_count"] == 0
    assert written["selection_summary"]["excluded_for_capture_quality_count"] == 0


def test_focus_queue_includes_quality_passed_live_capture_without_visual_suggestion(tmp_path: Path) -> None:
    packet = _packet()
    packet["items"].append(
        {
            "example_id": "fresh-live::c2",
            "source": "tradingview_mcp_live",
            "selection_reasons": ["priority_state_gap"],
            "candidate_state": {"missing_evidence": ["manual_visual_review_required"]},
            "corpus_evidence": [{"chunk_id": "demo:4"}],
            "training_eligible": True,
        }
    )

    focused = build_focus_queue(
        packet,
        _visual_suggestions(),
        packet_path=tmp_path / "packet.json",
        visual_suggestions_path=tmp_path / "visual.json",
        capture_quality_path=tmp_path / "capture_quality.json",
        capture_quality={
            "items": [
                {
                    "example_id": "fresh-live::c2",
                    "recommended_action": "review_state_labels",
                    "quality_flags": [],
                    "priority_score": 85.0,
                }
            ]
        },
        root_dir=tmp_path,
    )

    assert [item["example_id"] for item in focused["items"]] == ["case-a::c4", "case-b::c2", "fresh-live::c2"]
    fresh = focused["items"][2]
    assert fresh["training_eligible"] is False
    assert "capture_quality_reviewable" in fresh["selection_reasons"]
    assert "fresh_live_capture_quality_passed" in fresh["selection_reasons"]
    assert fresh["visual_suggestion_ref"] == {
        "source": "",
        "visual_review_status": "capture_quality_passed_no_visual_suggestion",
        "training_eligible": False,
        "recommended_next_action": "Fresh capture quality passed; review manually before promotion.",
        "promotion_blockers": [],
    }
    assert focused["selection_summary"]["candidate_count"] == 3
    assert focused["selection_summary"]["visual_review_first_count"] == 2
    assert focused["selection_summary"]["capture_quality_reviewable_count"] == 1


def test_focus_queue_raises_for_missing_review_id(tmp_path: Path) -> None:
    suggestions = _visual_suggestions()
    suggestions["next_review_order"] = ["missing-case"]

    with pytest.raises(ValueError, match="missing-case"):
        build_focus_queue(
            _packet(),
            suggestions,
            packet_path=tmp_path / "packet.json",
            visual_suggestions_path=tmp_path / "visual.json",
            root_dir=tmp_path,
        )
