from __future__ import annotations

import json
from pathlib import Path

from fractal_state import load_state_machine
from scripts.build_ttrades_state_review_packet import (
    StateReviewConfig,
    build_state_review_packet,
    write_outputs,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _bundle_row(bundle_id: str, *, direction: str = "none", stage: str = "c4") -> dict:
    return {
        "bundle_id": bundle_id,
        "source": "unit",
        "source_path": "unit.json",
        "source_pointer": bundle_id,
        "path_family": "continuation",
        "direction": direction,
        "fractal_stage": stage,
        "htf_bias": direction if direction in {"bullish", "bearish"} else "neutral",
        "htf_frame_path": f"artifacts/{bundle_id}/daily.png",
        "itf_frame_path": f"artifacts/{bundle_id}/h1.png",
        "ltf_frame_path": f"artifacts/{bundle_id}/m5.png",
        "poi_type": "reaction_zone" if direction != "none" else "none",
        "poi_direction": direction if direction != "none" else "neutral",
        "poi_source": "rule_derived" if direction != "none" else "none",
        "poi_validity": direction != "none",
        "setup_quality": "good_setup",
        "entry_state": "long_ready" if direction == "bullish" and stage == "c4" else "wait",
        "invalidation_state": "intact" if direction != "none" else "unknown",
        "session_context": "new_york",
        "kill_zone_alignment": "aligned",
        "detector_boxes_by_frame": {},
        "review_outcome": "seed_gold",
        "label_confidence": 0.9,
    }


def test_state_review_schema_enums_match_state_machine() -> None:
    schema = json.loads(Path("data/ttrades_state_review.schema.json").read_text(encoding="utf-8"))
    machine = load_state_machine()

    defs = schema["$defs"]
    for enum_name in (
        "path_family",
        "fractal_stage",
        "direction",
        "htf_bias",
        "poi_type",
        "poi_direction",
        "poi_source",
        "setup_quality",
        "entry_state",
        "invalidation_state",
        "session_context",
        "kill_zone_alignment",
    ):
        assert defs[enum_name]["enum"] == list(machine.enums[enum_name])


def test_state_review_packet_is_candidate_only_and_prioritizes_missing_direction(tmp_path: Path) -> None:
    bundle_seed = tmp_path / "results" / "phase2_bundle_gold_seed.jsonl"
    bundle_report = tmp_path / "results" / "phase2_bundle_gold_seed_report.json"
    corpus_chunks = tmp_path / "knowledge" / "ttfm_video_corpus" / "chunks.jsonl"
    _write_jsonl(
        bundle_seed,
        [
            _bundle_row("needs-direction", direction="none", stage="c4"),
            _bundle_row("directional-candidate", direction="bullish", stage="c4"),
        ],
    )
    _write_json(
        bundle_report,
        {
            "benchmark": {
                "target_count": 2,
                "satisfied_target_count": 0,
                "unsatisfied_target_count": 2,
                "coverage_ratio": 0.0,
                "targets": [
                    {
                        "path_family": "continuation",
                        "direction": "bullish",
                        "fractal_stage": "c4",
                        "minimum_examples": 10,
                        "observed_count": 0,
                        "gap": 10,
                        "meets_minimum": False,
                    }
                ],
            }
        },
    )
    _write_jsonl(
        corpus_chunks,
        [
            {
                "chunk_id": "fractal_model_fundamentals:0000",
                "video_slug": "fractal_model_fundamentals",
                "title": "Fractal Model Fundamentals",
                "source_page": "https://example.test/fractal",
                "topics": ["fractal_stage", "daily_bias", "poi"],
                "text": "Daily bias, candle 2 swing point, candle 3 confirmation, and candle 4 continuation.",
            }
        ],
    )

    packet, answers = build_state_review_packet(
        StateReviewConfig(
            root_dir=tmp_path,
            bundle_seed_paths=(bundle_seed,),
            bundle_report_path=bundle_report,
            corpus_chunks_path=corpus_chunks,
            state_machine_path=Path.cwd() / "data" / "fractal_state_machine.json",
            output_packet_path=tmp_path / "packet.json",
            output_answers_path=tmp_path / "answers.json",
        )
    )

    assert [item["example_id"] for item in packet["items"]] == ["needs-direction", "directional-candidate"]
    assert packet["review_policy"]["candidate_only"] is True
    assert packet["selection_summary"]["corpus_evidence_item_count"] == 2
    assert packet["items"][0]["training_eligible"] is False
    assert packet["items"][0]["corpus_evidence"][0]["chunk_id"] == "fractal_model_fundamentals:0000"
    assert packet["items"][0]["review_outcome"] == "needs_review"
    assert "directional_bias_unlabeled" in packet["items"][0]["candidate_state"]["missing_evidence"]
    assert packet["items"][0]["candidate_decision"]["verdict"] == "insufficient_evidence"
    assert answers["items"][0]["training_eligible"] is False
    assert answers["items"][0]["review_outcome"] == "needs_review"
    assert answers["items"][0]["decision_label"]["verdict"] == "insufficient_evidence"


def test_state_review_packet_writes_outputs(tmp_path: Path) -> None:
    bundle_seed = tmp_path / "seed.jsonl"
    packet_path = tmp_path / "results" / "packet.json"
    answers_path = tmp_path / "results" / "answers.json"
    _write_jsonl(bundle_seed, [_bundle_row("case-a", direction="bearish", stage="c3")])

    config = StateReviewConfig(
        root_dir=tmp_path,
        bundle_seed_paths=(bundle_seed,),
        corpus_chunks_path=tmp_path / "missing_chunks.jsonl",
        state_machine_path=Path.cwd() / "data" / "fractal_state_machine.json",
        output_packet_path=packet_path,
        output_answers_path=answers_path,
    )
    packet, answers = build_state_review_packet(config)
    write_outputs(config, packet, answers)

    assert packet_path.exists()
    assert answers_path.exists()
    written_packet = json.loads(packet_path.read_text(encoding="utf-8"))
    assert written_packet["items"][0]["chart_paths"] == {
        "daily": "artifacts/case-a/daily.png",
        "h1": "artifacts/case-a/h1.png",
        "m5": "artifacts/case-a/m5.png",
    }
