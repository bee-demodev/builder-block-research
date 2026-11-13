from __future__ import annotations

from pathlib import Path

from scripts.build_tradingview_recapture_plan import build_recapture_plan


def _live_item(example_id: str, *, symbol: str, flags: list[str], priority: float = 0.0) -> dict:
    return {
        "example_id": example_id,
        "source": "tradingview_mcp_live",
        "priority_score": priority,
        "recommended_action": "recapture_before_review",
        "quality_flags": flags,
        "capture_metadata_path": f"results/live_tradingview/{example_id}/capture.json",
        "capture_metadata": {
            "expected_symbol": symbol,
            "capture_symbol": symbol,
            "frames": {
                "daily": {"resolved_resolution": "240", "symbol": symbol},
                "h1": {"resolved_resolution": "60", "symbol": symbol},
                "m5": {"resolved_resolution": "5", "symbol": symbol},
            },
        },
        "images": {
            "daily": {"path": "daily.png", "low_information": False},
            "h1": {"path": "h1.png", "low_information": False},
            "m5": {"path": "m5.png", "low_information": "low_information_timeframe_image" in flags},
        },
    }


def test_recapture_plan_prioritizes_live_failures_and_groups_by_symbol(tmp_path: Path) -> None:
    capture_quality = {
        "candidate_count": 4,
        "items": [
            _live_item(
                "nq-low-info",
                symbol="CME_MINI:NQM2026",
                flags=["low_information_timeframe_image"],
                priority=10.0,
            ),
            _live_item(
                "es-duplicate",
                symbol="CME_MINI:ESM2026",
                flags=["near_duplicate_timeframe_images", "timeframe_metadata_mismatch"],
                priority=15.0,
            ),
            {
                "example_id": "tutorial-case",
                "source": "ttfm_screenshot_manifest_seed",
                "priority_score": 99.0,
                "recommended_action": "recapture_before_review",
                "quality_flags": ["missing_capture_metadata", "inconsistent_image_dimensions"],
            },
            {
                "example_id": "clean-case",
                "source": "tradingview_mcp_live",
                "recommended_action": "review_state_labels",
                "quality_flags": [],
                "capture_metadata": {"expected_symbol": "CME_MINI:ESM2026"},
            },
        ],
    }

    plan = build_recapture_plan(
        capture_quality,
        capture_quality_path=tmp_path / "capture_quality.json",
        root_dir=tmp_path,
    )

    assert plan["summary"]["failed_capture_count"] == 3
    assert plan["summary"]["recapture_target_count"] == 2
    assert plan["summary"]["non_live_failed_count"] == 1
    assert plan["summary"]["passing_review_state_count"] == 1
    assert [target["example_id"] for target in plan["recapture_targets"]] == ["es-duplicate", "nq-low-info"]
    assert plan["recapture_targets"][0]["requested_stack"] == {"daily": "D", "h1": "60", "m5": "5"}
    assert plan["recapture_targets"][1]["symbol"] == "CME_MINI:NQM2026"
    assert plan["summary"]["recapture_target_by_symbol"]["CME_MINI:ESM2026"]["target_count"] == 1
    assert plan["non_live_rebuild_or_exclude"][0]["example_id"] == "tutorial-case"
    assert "Do not recapture in TradingView" in plan["non_live_rebuild_or_exclude"][0]["recommended_action"]


def test_recapture_plan_uses_live_path_when_source_is_missing(tmp_path: Path) -> None:
    capture_quality = {
        "items": [
            {
                "example_id": "path-live",
                "source": "",
                "recommended_action": "recapture_before_review",
                "quality_flags": ["exact_duplicate_timeframe_images"],
                "capture_metadata_path": "results/live_tradingview/path-live/capture.json",
                "capture_metadata": {"expected_symbol": "CME_MINI:ESM2026", "frames": {}},
                "images": {},
            }
        ]
    }

    plan = build_recapture_plan(
        capture_quality,
        capture_quality_path=tmp_path / "capture_quality.json",
        root_dir=tmp_path,
    )

    assert plan["summary"]["recapture_target_count"] == 1
    assert plan["recapture_targets"][0]["example_id"] == "path-live"
    assert plan["non_live_rebuild_or_exclude"] == []
