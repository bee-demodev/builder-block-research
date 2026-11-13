from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.build_ttrades_state_builder_fixtures import (
    build_state_builder_fixtures,
    write_fixture_file,
)


STATE_MACHINE_PATH = Path(__file__).resolve().parents[1] / "data" / "fractal_state_machine.json"


def _touch_chart(root_dir: Path, path: str) -> None:
    resolved = root_dir / path
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_bytes(b"png-placeholder")


def _base_row(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "bundle_id": "fixture-case::c4",
        "cue_summary": "synthetic reviewed setup fixture",
        "detector_boxes_by_frame": {},
        "direction": "none",
        "entry_state": "wait",
        "fractal_stage": "c1",
        "htf_bias": "neutral",
        "htf_frame_path": "charts/daily.png",
        "htf_timeframe": "1D",
        "invalidation_state": "unknown",
        "itf_frame_path": "charts/h1.png",
        "itf_timeframe": "1h",
        "kill_zone_alignment": "neutral",
        "label_confidence": 0.9,
        "ltf_frame_path": "charts/m5.png",
        "ltf_timeframe": "5m",
        "path_family": "continuation",
        "poi_direction": "neutral",
        "poi_source": "rule_derived",
        "poi_type": "equilibrium_zone",
        "poi_validity": True,
        "review_outcome": "seed_gold",
        "session_context": "unknown",
        "setup_quality": "good_setup",
        "source": "test",
        "source_path": "tests",
        "source_pointer": "case",
    }
    row.update(overrides)
    return row


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_build_state_builder_fixtures_selects_reviewed_rows_and_maps_decisions(tmp_path: Path) -> None:
    for chart_path in ("charts/daily.png", "charts/h1.png", "charts/m5.png"):
        _touch_chart(tmp_path, chart_path)
    bundle_path = tmp_path / "seed.jsonl"
    _write_jsonl(
        bundle_path,
        [
            _base_row(review_outcome="pending"),
            _base_row(path_family="invalid"),
            _base_row(bundle_id="missing-chart", htf_frame_path="charts/missing.png"),
            _base_row(bundle_id="neutral-c1"),
            _base_row(
                bundle_id="bullish-c4",
                direction="bullish",
                entry_state="long_ready",
                fractal_stage="c4",
                htf_bias="bullish",
                invalidation_state="intact",
                kill_zone_alignment="aligned",
                path_family="reversal",
                poi_direction="bullish",
                poi_source="detector",
                poi_type="reaction_zone",
                session_context="new_york",
            ),
        ],
    )

    payload = build_state_builder_fixtures(
        root_dir=tmp_path,
        bundle_seed_path=bundle_path,
        state_machine_path=STATE_MACHINE_PATH,
        limit=2,
    )

    assert payload["summary"]["fixture_gate"] == "pass"
    assert payload["summary"]["fixture_count"] == 2
    assert payload["summary"]["skipped_counts"] == {
        "invalid_state_labels": 1,
        "missing_chart_paths": 1,
        "not_reviewed": 1,
    }
    assert payload["summary"]["expected_decision_counts"] == {
        "insufficient_evidence": 1,
        "valid_long_setup": 1,
    }
    neutral, bullish = payload["fixtures"]
    assert neutral["expected_decision"]["verdict"] == "insufficient_evidence"
    assert neutral["expected_state"]["state_confidence"] == 0.55
    assert {
        "directional_bias_unlabeled",
        "daily_or_htf_bias_unlabeled",
        "daily_h1_m5_alignment_unverified",
        "invalidation_unlabeled",
    }.issubset(set(neutral["expected_state"]["missing_evidence"]))
    assert bullish["expected_state"]["missing_evidence"] == []
    assert bullish["expected_state"]["timeframe_alignment"] == {
        "daily": "bullish",
        "h1": "bullish",
        "m5": "bullish",
        "is_aligned": True,
    }
    assert bullish["expected_decision"] == {
        "verdict": "valid_long_setup",
        "reasons": ["C4 bullish setup is aligned, reviewed, and entry-ready."],
        "blocking_conditions": [],
    }


def test_write_fixture_file_creates_parent_directory(tmp_path: Path) -> None:
    payload = {"summary": {"fixture_count": 0}, "fixtures": []}
    output_path = Path("results") / "fixtures.json"

    write_fixture_file(payload, root_dir=tmp_path, output_path=output_path)

    written_path = tmp_path / output_path
    assert written_path.exists()
    assert json.loads(written_path.read_text(encoding="utf-8")) == payload
