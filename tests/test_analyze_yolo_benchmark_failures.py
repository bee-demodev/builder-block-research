from __future__ import annotations

from pathlib import Path

from scripts.analyze_yolo_benchmark_failures import (
    Box,
    box_iou,
    letterbox_meta,
    load_yolo_labels,
    match_predictions,
    scale_prediction_to_original,
    summarize_example,
    write_queue_csv,
)


def test_load_yolo_labels_converts_normalized_xywh_to_pixels(tmp_path: Path) -> None:
    label_path = tmp_path / "sample.txt"
    label_path.write_text("0 0.500000 0.500000 0.250000 0.500000\n", encoding="utf-8")

    labels = load_yolo_labels(label_path, image_width=640, image_height=360)

    assert labels == [
        Box(
            class_id=0,
            class_name="liquidity_sweep_high",
            xyxy=(240.0, 90.0, 400.0, 270.0),
            confidence=None,
        )
    ]


def test_letterbox_prediction_scales_back_to_original_coordinates() -> None:
    meta = letterbox_meta(640, 360, size=1024)

    scaled = scale_prediction_to_original((384.0, 368.0, 640.0, 656.0), meta)

    assert scaled == (240.0, 90.0, 400.0, 270.0)


def test_match_predictions_pairs_same_class_by_iou() -> None:
    labels = [
        Box(0, "liquidity_sweep_high", (10.0, 10.0, 30.0, 30.0)),
        Box(1, "liquidity_sweep_low", (100.0, 100.0, 140.0, 140.0)),
    ]
    predictions = [
        Box(0, "liquidity_sweep_high", (12.0, 12.0, 28.0, 28.0), confidence=0.8),
        Box(1, "liquidity_sweep_low", (200.0, 200.0, 220.0, 220.0), confidence=0.7),
        Box(0, "liquidity_sweep_high", (100.0, 100.0, 140.0, 140.0), confidence=0.6),
    ]

    matches, unmatched_labels, unmatched_predictions = match_predictions(labels, predictions, iou_threshold=0.5)

    assert len(matches) == 1
    assert matches[0][0] == 0
    assert matches[0][1] == 0
    assert box_iou(labels[0], predictions[0]) > 0.5
    assert unmatched_labels == [1]
    assert unmatched_predictions == [1, 2]


def test_summarize_example_prioritizes_weak_class_miss_and_hard_negative() -> None:
    weak_summary = summarize_example(
        manifest_item={
            "example_id": "weak",
            "safe_name": "weak",
            "hard_negative": False,
            "review_outcome": "accepted",
        },
        image_path=Path("weak.jpg"),
        label_path=Path("weak.txt"),
        overlay_path=None,
        labels=[Box(3, "bullish_reaction_zone", (10.0, 10.0, 30.0, 30.0))],
        predictions=[],
        iou_threshold=0.5,
    )
    hard_negative_summary = summarize_example(
        manifest_item={
            "example_id": "negative",
            "safe_name": "negative",
            "hard_negative": True,
            "review_outcome": "no_setup",
        },
        image_path=Path("negative.jpg"),
        label_path=Path("negative.txt"),
        overlay_path=None,
        labels=[],
        predictions=[Box(2, "protected_swing", (10.0, 10.0, 30.0, 30.0), confidence=0.25)],
        iou_threshold=0.5,
    )

    assert weak_summary["reasons"] == ["false_negative", "weak_class_miss"]
    assert weak_summary["priority"] > 100
    assert hard_negative_summary["reasons"] == ["hard_negative_false_positive"]
    assert hard_negative_summary["priority"] > weak_summary["priority"] - 30


def test_write_queue_csv_emits_ranked_review_rows(tmp_path: Path) -> None:
    report = {
        "review_queue": [
            {
                "priority": 100.25,
                "reasons": ["hard_negative_false_positive"],
                "example_id": "negative",
                "safe_name": "negative",
                "hard_negative": True,
                "expected_classes": [],
                "predicted_classes": ["protected_swing"],
                "false_negative_classes": [],
                "false_positive_classes": ["protected_swing"],
                "matched_count": 0,
                "label_count": 0,
                "prediction_count": 1,
                "max_prediction_confidence": 0.25,
                "image_path": "dataset/yolo_benchmark/images/negative.jpg",
                "overlay_path": "results/benchmark_overlays/latest/negative.jpg",
            }
        ]
    }
    output_path = tmp_path / "queue.csv"

    write_queue_csv(report, output_path)

    text = output_path.read_text(encoding="utf-8")
    assert "rank,priority,reasons" in text
    assert "negative" in text
    assert "hard_negative_false_positive" in text
