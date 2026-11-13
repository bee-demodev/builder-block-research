from __future__ import annotations

import json
from pathlib import Path

from scripts.build_ttrades_state_review_dashboard import build_dashboard, image_src


def test_state_review_dashboard_renders_three_timeframes_and_answer_template(tmp_path: Path) -> None:
    for name in ("daily", "h1", "m5"):
        image = tmp_path / "artifacts" / "case-a" / f"{name}.png"
        image.parent.mkdir(parents=True, exist_ok=True)
        image.write_bytes(b"png")
    output_path = tmp_path / "results" / "dashboard.html"
    packet = {
        "selection_summary": {
            "corpus_evidence_item_count": 1,
            "missing_evidence_counts": {"directional_bias_unlabeled": 1},
        },
        "items": [
            {
                "example_id": "case-a::c4",
                "source": "unit",
                "priority_score": 99.0,
                "selection_reasons": ["missing_direction"],
                "chart_paths": {
                    "daily": "artifacts/case-a/daily.png",
                    "h1": "artifacts/case-a/h1.png",
                    "m5": "artifacts/case-a/m5.png",
                },
                "candidate_state": {
                    "path_family": "continuation",
                    "direction": "none",
                    "fractal_stage": "c4",
                    "htf_bias": "neutral",
                    "timeframe_alignment": {"daily": "none", "h1": "none", "m5": "none", "is_aligned": False},
                    "poi": {"type": "none", "direction": "neutral", "source": "none", "validity": False},
                    "setup_quality": "no_setup",
                    "entry_state": "wait",
                    "invalidation": {"state": "unknown", "reason": "unit"},
                    "state_confidence": 0.5,
                    "missing_evidence": ["directional_bias_unlabeled"],
                },
                "candidate_decision": {"verdict": "insufficient_evidence", "blocking_conditions": ["directional_bias_unlabeled"]},
                "review_fields_required": ["direction"],
                "corpus_evidence": [
                    {
                        "chunk_id": "demo:1-2",
                        "title": "Demo Evidence",
                        "source_path": "https://example.test/demo",
                        "score": 2.0,
                        "claim": "Daily bias must be confirmed before dropping to lower timeframes.",
                    }
                ],
                "review_outcome": "needs_review",
                "training_eligible": False,
            }
        ],
    }
    answers = {
        "items": [
            {
                "example_id": "case-a::c4",
                "review_outcome": "needs_review",
                "training_eligible": False,
                "reviewer_notes": [],
            }
        ]
    }

    html = build_dashboard(packet, answers, root_dir=tmp_path, output_path=output_path)

    assert "TTrades State Review Dashboard" in html
    assert "case-a::c4" in html
    assert "Daily / HTF" in html
    assert "1h" in html
    assert "5m" in html
    assert "Demo Evidence" in html
    assert "directional_bias_unlabeled" in html
    assert "trainable: false" in html


def test_image_src_makes_result_relative_paths(tmp_path: Path) -> None:
    output_path = tmp_path / "results" / "dashboard.html"
    image = tmp_path / "artifacts" / "case-a" / "daily.png"
    image.parent.mkdir(parents=True, exist_ok=True)
    image.write_bytes(b"png")

    assert image_src("artifacts/case-a/daily.png", root_dir=tmp_path, output_path=output_path) == "../artifacts/case-a/daily.png"
