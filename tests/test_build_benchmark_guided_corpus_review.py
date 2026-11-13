from __future__ import annotations

import json
from pathlib import Path

from scripts.build_benchmark_guided_corpus_review import (
    BenchmarkGuidedCorpusConfig,
    build_guided_packet,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _image(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"image")
    return str(path)


def test_guided_packet_excludes_benchmark_and_reviewed_ids_without_truth_leakage(tmp_path: Path) -> None:
    benchmark_failure_path = tmp_path / "results" / "benchmark_failure.json"
    benchmark_manifest_path = tmp_path / "results" / "benchmark_manifest.json"
    corpus_packet_path = tmp_path / "results" / "corpus_packet.json"
    reviewed_answers_path = tmp_path / "results" / "reviewed_answers.json"

    _write_json(
        benchmark_failure_path,
        {
            "items": [
                {
                    "example_id": "held-out-from-failure",
                    "candidate_labels": ["liquidity_sweep_high"],
                    "recommended_action": "review_weak_class_miss",
                    "benchmark_context": {
                        "expected_classes": ["bullish_reaction_zone"],
                        "false_negative_classes": ["bullish_reaction_zone", "bullish_reaction_zone"],
                        "false_positive_classes": ["liquidity_sweep_high"],
                    },
                }
            ]
        },
    )
    _write_json(benchmark_manifest_path, {"items": [{"example_id": "held-out-from-manifest"}]})
    _write_json(
        reviewed_answers_path,
        {
            "items": [
                {
                    "example_id": "already-reviewed",
                    "review_outcome": "adjusted",
                    "detections": [{"class_id": 4, "bbox": [0.1, 0.1, 0.2, 0.2]}],
                },
                {
                    "example_id": "ambiguous-only",
                    "review_outcome": "ambiguous",
                    "detections": [],
                },
            ]
        },
    )
    _write_json(
        corpus_packet_path,
        {
            "items": [
                {
                    "example_id": "held-out-from-failure",
                    "image_path": _image(tmp_path / "images" / "held-out-failure.jpg"),
                    "score": 100,
                    "recommended_action": "accept_or_adjust",
                    "candidate_labels": ["bullish_reaction_zone"],
                },
                {
                    "example_id": "held-out-from-manifest",
                    "image_path": _image(tmp_path / "images" / "held-out-manifest.jpg"),
                    "score": 100,
                    "recommended_action": "accept_or_adjust",
                    "candidate_labels": ["bullish_reaction_zone"],
                },
                {
                    "example_id": "already-reviewed",
                    "image_path": _image(tmp_path / "images" / "reviewed.jpg"),
                    "score": 100,
                    "recommended_action": "accept_or_adjust",
                    "candidate_labels": ["bullish_reaction_zone"],
                },
                {
                    "example_id": "fresh-corpus",
                    "image_path": _image(tmp_path / "images" / "fresh.jpg"),
                    "score": 20,
                    "recommended_action": "review",
                    "candidate_labels": ["protected_swing"],
                },
                {
                    "example_id": "ambiguous-only",
                    "image_path": _image(tmp_path / "images" / "ambiguous.jpg"),
                    "score": 18,
                    "recommended_action": "review",
                    "candidate_labels": ["protected_swing"],
                },
            ]
        },
    )

    packet, answers = build_guided_packet(
        BenchmarkGuidedCorpusConfig(
            root_dir=tmp_path,
            benchmark_failure_batch_path=benchmark_failure_path,
            corpus_prep_packet_path=corpus_packet_path,
            benchmark_manifest_path=benchmark_manifest_path,
            existing_answer_patterns=("results/reviewed_answers.json",),
            limit=10,
            hard_negative_limit=0,
        )
    )

    selected_ids = {item["example_id"] for item in packet["items"]}
    assert selected_ids == {"fresh-corpus", "ambiguous-only"}
    assert packet["exclusion_counts"] == {
        "held_out_benchmark_example": 2,
        "already_reviewed": 1,
    }
    assert packet["benchmark_demand_summary"]["false_negative_counts"] == {"bullish_reaction_zone": 2}
    for item in packet["items"]:
        assert item["candidate_labels"] == ["protected_swing"]
        assert "benchmark_context" not in item
        assert "expected_classes" not in item
    for item in answers["items"]:
        assert item["detections"] == []
        assert item["review_outcome"] == "ambiguous"
        assert item["candidate_labels"] == ["protected_swing"]


def test_guided_packet_uses_benchmark_demand_to_rank_fresh_corpus_items(tmp_path: Path) -> None:
    benchmark_failure_path = tmp_path / "benchmark_failure.json"
    benchmark_manifest_path = tmp_path / "benchmark_manifest.json"
    corpus_packet_path = tmp_path / "corpus_packet.json"
    _write_json(
        benchmark_failure_path,
        {
            "items": [
                {
                    "example_id": "bench-a",
                    "candidate_labels": [],
                    "recommended_action": "review_weak_class_miss",
                    "benchmark_context": {
                        "false_negative_classes": [
                            "bullish_reaction_zone",
                            "bullish_reaction_zone",
                            "bullish_reaction_zone",
                        ],
                        "false_positive_classes": [],
                    },
                }
            ]
        },
    )
    _write_json(benchmark_manifest_path, {"items": []})
    _write_json(
        corpus_packet_path,
        {
            "items": [
                {
                    "example_id": "high-demand-lower-corpus-score",
                    "image_path": _image(tmp_path / "images" / "high-demand.jpg"),
                    "score": 20,
                    "recommended_action": "review",
                    "candidate_labels": ["bullish_reaction_zone"],
                },
                {
                    "example_id": "no-demand-higher-corpus-score",
                    "image_path": _image(tmp_path / "images" / "no-demand.jpg"),
                    "score": 80,
                    "recommended_action": "review",
                    "candidate_labels": ["protected_swing"],
                },
            ]
        },
    )

    packet, _answers = build_guided_packet(
        BenchmarkGuidedCorpusConfig(
            root_dir=tmp_path,
            benchmark_failure_batch_path=benchmark_failure_path,
            corpus_prep_packet_path=corpus_packet_path,
            benchmark_manifest_path=benchmark_manifest_path,
            existing_answer_patterns=(),
            limit=2,
            hard_negative_limit=0,
        )
    )

    assert [item["example_id"] for item in packet["items"]] == [
        "high-demand-lower-corpus-score",
        "no-demand-higher-corpus-score",
    ]
    assert packet["items"][0]["benchmark_demand_classes"] == ["bullish_reaction_zone"]
    assert packet["items"][0]["benchmark_demand_counts"]["bullish_reaction_zone"]["false_negative"] == 3


def test_guided_packet_reserves_hard_negative_reviews_from_false_positive_pressure(tmp_path: Path) -> None:
    benchmark_failure_path = tmp_path / "benchmark_failure.json"
    benchmark_manifest_path = tmp_path / "benchmark_manifest.json"
    corpus_packet_path = tmp_path / "corpus_packet.json"
    _write_json(
        benchmark_failure_path,
        {
            "items": [
                {
                    "example_id": "bench-hard-negative",
                    "hard_negative": True,
                    "candidate_labels": ["liquidity_sweep_high"],
                    "recommended_action": "review_hard_negative_false_positive",
                    "benchmark_context": {
                        "false_negative_classes": [],
                        "false_positive_classes": ["liquidity_sweep_high"],
                    },
                }
            ]
        },
    )
    _write_json(benchmark_manifest_path, {"items": []})
    _write_json(
        corpus_packet_path,
        {
            "items": [
                {
                    "example_id": "fresh-hard-negative",
                    "image_path": _image(tmp_path / "images" / "hard-negative.jpg"),
                    "score": 39,
                    "recommended_action": "hard_negative_review",
                    "candidate_labels": [],
                }
            ]
        },
    )

    packet, answers = build_guided_packet(
        BenchmarkGuidedCorpusConfig(
            root_dir=tmp_path,
            benchmark_failure_batch_path=benchmark_failure_path,
            corpus_prep_packet_path=corpus_packet_path,
            benchmark_manifest_path=benchmark_manifest_path,
            existing_answer_patterns=(),
            limit=0,
            hard_negative_limit=1,
        )
    )

    assert packet["selected_hard_negative_count"] == 1
    assert packet["items"][0]["example_id"] == "fresh-hard-negative"
    assert "benchmark_false_positive_pressure" in packet["items"][0]["selection_reasons"]
    assert answers["items"][0]["detections"] == []
    assert answers["items"][0]["review_outcome"] == "ambiguous"
