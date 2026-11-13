from __future__ import annotations

import json
from pathlib import Path

from scripts.analyze_yolo_benchmark_failures import Box
from scripts.build_benchmark_guided_model_assist import (
    ModelAssistConfig,
    build_model_assist,
    xyxy_to_normalized_bbox,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_image(path: Path, *, width: int = 200, height: int = 100) -> None:
    import cv2
    import numpy as np

    path.parent.mkdir(parents=True, exist_ok=True)
    image = np.zeros((height, width, 3), dtype=np.uint8)
    assert cv2.imwrite(str(path), image)


def test_xyxy_to_normalized_bbox_clips_to_image_bounds() -> None:
    box = Box(3, "bullish_reaction_zone", (-10.0, 10.0, 110.0, 70.0), confidence=0.8)

    assert xyxy_to_normalized_bbox(box, image_width=100, image_height=100) == [
        0.5,
        0.4,
        1.0,
        0.6,
    ]


def test_model_assist_keeps_predictions_as_ambiguous_review_hints(tmp_path: Path) -> None:
    image_path = tmp_path / "images" / "case.jpg"
    _write_image(image_path)
    packet_path = tmp_path / "results" / "guided_packet.json"
    model_path = tmp_path / "model.onnx"
    model_path.write_bytes(b"fake-model")
    _write_json(
        packet_path,
        {
            "items": [
                {
                    "example_id": "case",
                    "review_rank": 1,
                    "image_path": str(image_path),
                    "candidate_labels": ["bullish_reaction_zone"],
                    "recommended_action": "review",
                    "score": 22.5,
                }
            ]
        },
    )

    def fake_predictor(_path: Path) -> list[Box]:
        return [
            Box(3, "bullish_reaction_zone", (20.0, 20.0, 80.0, 60.0), confidence=0.77),
            Box(2, "protected_swing", (100.0, 20.0, 140.0, 60.0), confidence=0.66),
        ]

    report, answers = build_model_assist(
        ModelAssistConfig(
            root_dir=tmp_path,
            packet_path=packet_path,
            model_path=model_path,
            output_dir=tmp_path / "results" / "assist",
            output_answers_path=tmp_path / "results" / "answers.json",
        ),
        predictor=fake_predictor,
        draw_overlays=False,
    )

    item = answers["items"][0]
    assist = item["model_assist"]
    assert report["rows_with_any_predictions"] == 1
    assert report["rows_with_candidate_matches"] == 1
    assert report["matched_class_counts"] == {"bullish_reaction_zone": 1}
    assert report["unexpected_class_counts"] == {"protected_swing": 1}
    assert item["detections"] == []
    assert item["review_outcome"] == "ambiguous"
    assert assist["candidate_matched_predictions"][0]["class_name"] == "bullish_reaction_zone"
    assert assist["unexpected_predictions"][0]["class_name"] == "protected_swing"
    assert assist["warning"].startswith("Review hint only")
