from __future__ import annotations

import csv
from pathlib import Path

from scripts.build_benchmark_failure_review_packet import (
    BenchmarkFailureConfig,
    build_review_packet,
)


def _write_queue(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = [
        "rank",
        "priority",
        "reasons",
        "example_id",
        "safe_name",
        "hard_negative",
        "expected_classes",
        "predicted_classes",
        "false_negative_classes",
        "false_positive_classes",
        "matched_count",
        "label_count",
        "prediction_count",
        "max_prediction_confidence",
        "image_path",
        "overlay_path",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_build_review_packet_keeps_benchmark_truth_out_of_candidate_labels(tmp_path: Path) -> None:
    image_path = tmp_path / "dataset" / "yolo_benchmark" / "images" / "case.jpg"
    overlay_path = tmp_path / "results" / "overlays" / "case.jpg"
    image_path.parent.mkdir(parents=True, exist_ok=True)
    overlay_path.parent.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(b"image")
    overlay_path.write_bytes(b"overlay")
    queue_path = tmp_path / "results" / "queue.csv"
    _write_queue(
        queue_path,
        [
            {
                "rank": "1",
                "priority": "149.5",
                "reasons": "false_negative,false_positive,weak_class_miss",
                "example_id": "case-id",
                "safe_name": "case",
                "hard_negative": "False",
                "expected_classes": "bullish_reaction_zone,liquidity_sweep_low",
                "predicted_classes": "protected_swing",
                "false_negative_classes": "bullish_reaction_zone,liquidity_sweep_low",
                "false_positive_classes": "protected_swing",
                "matched_count": "0",
                "label_count": "2",
                "prediction_count": "1",
                "max_prediction_confidence": "0.42",
                "image_path": str(image_path),
                "overlay_path": str(overlay_path),
            }
        ],
    )

    packet, answer_seed = build_review_packet(
        BenchmarkFailureConfig(
            root_dir=tmp_path,
            queue_path=queue_path,
            output_batch_path=tmp_path / "batch.json",
            output_answers_path=tmp_path / "answers.json",
            run_id="run-test",
        )
    )

    item = packet["items"][0]
    answer_item = answer_seed["items"][0]
    assert packet["item_count"] == 1
    assert item["candidate_labels"] == ["protected_swing"]
    assert item["benchmark_context"]["expected_classes"] == [
        "bullish_reaction_zone",
        "liquidity_sweep_low",
    ]
    assert item["recommended_action"] == "review_weak_class_miss"
    assert answer_item["detections"] == []
    assert answer_item["review_outcome"] == "ambiguous"
    assert answer_item["candidate_labels"] == ["protected_swing"]


def test_build_review_packet_excludes_missing_assets_and_counts_reason(tmp_path: Path) -> None:
    image_path = tmp_path / "image.jpg"
    image_path.write_bytes(b"image")
    queue_path = tmp_path / "queue.csv"
    _write_queue(
        queue_path,
        [
            {
                "rank": "1",
                "priority": "100.0",
                "reasons": "hard_negative_false_positive",
                "example_id": "missing-overlay",
                "safe_name": "missing-overlay",
                "hard_negative": "True",
                "expected_classes": "",
                "predicted_classes": "liquidity_sweep_high",
                "false_negative_classes": "",
                "false_positive_classes": "liquidity_sweep_high",
                "matched_count": "0",
                "label_count": "0",
                "prediction_count": "1",
                "max_prediction_confidence": "0.33",
                "image_path": str(image_path),
                "overlay_path": str(tmp_path / "missing.jpg"),
            }
        ],
    )

    packet, answer_seed = build_review_packet(
        BenchmarkFailureConfig(
            root_dir=tmp_path,
            queue_path=queue_path,
            output_batch_path=tmp_path / "batch.json",
            output_answers_path=tmp_path / "answers.json",
            run_id="run-test",
        )
    )

    assert packet["item_count"] == 0
    assert packet["input_row_count"] == 1
    assert packet["exclusion_counts"] == {"missing_overlay_path": 1}
    assert answer_seed["items"] == []
