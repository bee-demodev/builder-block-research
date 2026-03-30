from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from data_loader import ChartExample
from labeler.synthetic_teacher import generate_synthetic_sidecar
from labeler.vision_labeler import (
    VISION_SYSTEM_PROMPT,
    build_dense_supervision_packet_from_rows,
    build_priority_review_queue,
    build_supervision_packet,
    detections_to_yolo_lines,
    export_yolo_dataset,
    load_supervision_answers,
    parse_detection_payload,
    select_accept_packet_autolabels,
    select_heuristic_dense_autolabels,
    select_scarce_accept_packet_autolabels,
    select_setup_quality_autolabels,
    select_teacher_screenshot_autolabels,
    select_weak_visual_autolabels,
    validate_detections,
)
from config import build_config


def test_parse_and_validate_detection_payload() -> None:
    payload = """
    [
      {"class_id": 0, "bbox": [0.5, 0.4, 0.2, 0.1]},
      {"class_id": 4, "bbox": [0.3, 0.6, 0.15, 0.2]}
    ]
    """
    detections = parse_detection_payload(payload)
    issues = validate_detections(detections)
    lines = detections_to_yolo_lines(detections)

    assert issues == []
    assert lines == [
        "0 0.500000 0.400000 0.200000 0.100000",
        "4 0.300000 0.600000 0.150000 0.200000",
    ]


def test_validate_detection_payload_rejects_invalid_boxes() -> None:
    payload = '[{"class_id": 9, "bbox": [1.2, 0.5, -0.1, 0.3]}]'
    detections = parse_detection_payload(payload)
    issues = validate_detections(detections)

    assert any("class_id" in issue for issue in issues)
    assert any("bbox" in issue for issue in issues)
    assert "strict JSON array" in VISION_SYSTEM_PROMPT


def test_parse_detection_payload_rejects_non_array_json() -> None:
    with pytest.raises(ValueError):
        parse_detection_payload('{"class_id": 0}')


def test_build_supervision_packet_includes_context_fields(tmp_path) -> None:
    image_path = tmp_path / "demo.png"
    image_path.write_bytes(b"img")
    example = ChartExample(
        example_id="demo::1",
        image_path=image_path,
        embedding=None,
        text="bullish continuation setup",
        title="Demo Title",
        source_type="visual_embedding_index",
        time_index=7,
        metadata={
            "checkpoint": "confirmation",
            "video_slug": "demo_video",
            "candidate_labels": ["protected_swing"],
            "cue_terms": ["entry", "sweep"],
        },
    )

    packet = build_supervision_packet([example], cluster_assignments={"demo::1": 3})

    assert packet["mode"] == "supervision_only"
    assert packet["item_count"] == 1
    assert packet["items"][0]["cluster_id"] == 3
    assert packet["items"][0]["checkpoint"] == "confirmation"
    assert packet["items"][0]["candidate_labels"] == ["protected_swing"]


def test_load_supervision_answers_validates_schema(tmp_path) -> None:
    answers_path = tmp_path / "answers.json"
    answers_path.write_text(
        """
        {
          "items": [
            {
              "example_id": "demo::1",
              "detections": [
                {"class_id": 0, "bbox": [0.5, 0.4, 0.2, 0.1]}
              ]
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    answers = load_supervision_answers(answers_path)

    assert answers == [
        {
            "example_id": "demo::1",
            "detections": [{"class_id": 0, "bbox": [0.5, 0.4, 0.2, 0.1]}],
            "review_outcome": "accepted",
            "note": "",
        }
    ]


def test_build_dense_supervision_packet_from_rows_limits_per_video() -> None:
    rows = []
    for index in range(6):
        rows.append(
            {
                "example_id": f"video_a::{index}",
                "frame_path": f"frames/video_a/{index}.jpg",
                "frame_status": "extracted",
                "title": "Video A",
                "source_type": "youtube_dense_window",
                "checkpoint": "dense",
                "video_slug": "video_a",
                "video_id": "a",
                "topics": ["bias"],
                "candidate_labels": ["liquidity_sweep"],
                "cue_terms": ["sweep"],
                "source_url": "https://youtu.be/a",
                "text": "sweep text",
                "cue_score": 10 - index,
                "start": float(index),
            }
        )
    packet = build_dense_supervision_packet_from_rows(rows, limit=5, per_video_cap=2)

    assert packet["mode"] == "dense_supervision_only"
    assert packet["item_count"] == 2
    assert all(item["video_slug"] == "video_a" for item in packet["items"])


def test_build_dense_supervision_packet_filters_slide_like_rows() -> None:
    rows = [
        {
            "example_id": "slide::1",
            "frame_path": "frames/slide/1.jpg",
            "frame_status": "extracted",
            "title": "Simple Day Trading Strategy -Intro",
            "source_type": "youtube_dense_window",
            "checkpoint": "dense",
            "video_slug": "slide_video",
            "video_id": "slide",
            "topics": ["educational_channel"],
            "candidate_labels": ["order_block"],
            "cue_terms": ["order block", "entry"],
            "source_url": "https://youtu.be/slide",
            "text": "Simple Day Trading Strategy -Intro. educational_channel. Entry confirmation around order block.",
            "cue_score": 50,
            "start": 1.0,
            "transcript_source": "synthetic_from_video_metadata",
        },
        {
            "example_id": "chart::1",
            "frame_path": "frames/chart/1.jpg",
            "frame_status": "extracted",
            "title": "Trade Continuations Using Order Blocks",
            "source_type": "youtube_dense_window",
            "checkpoint": "dense",
            "video_slug": "chart_video",
            "video_id": "chart",
            "topics": ["order_block"],
            "candidate_labels": ["order_block"],
            "cue_terms": ["entry", "retest"],
            "source_url": "https://youtu.be/chart",
            "text": "Here we are in our first example. Let this play out, then take an entry on the retest and put my stop below the protected low.",
            "cue_score": 30,
            "start": 2.0,
            "transcript_source": "cached_json",
        },
    ]

    packet = build_dense_supervision_packet_from_rows(rows, limit=10, per_video_cap=4)

    assert packet["item_count"] == 1
    assert packet["items"][0]["example_id"] == "chart::1"


def test_build_dense_supervision_packet_adds_heuristic_suggestions_for_highlighted_zone(tmp_path: Path) -> None:
    image_path = tmp_path / "chart.png"
    image = np.full((120, 180, 3), 255, dtype=np.uint8)
    cv2.rectangle(image, (60, 40), (120, 78), (90, 220, 220), thickness=-1)
    cv2.imwrite(str(image_path), image)

    rows = [
        {
            "example_id": "chart::highlight",
            "frame_path": str(image_path),
            "frame_status": "extracted",
            "title": "Trade Continuations Using Order Blocks",
            "source_type": "youtube_dense_window",
            "checkpoint": "dense",
            "video_slug": "chart_video",
            "video_id": "chart",
            "topics": ["order_block"],
            "candidate_labels": ["order_block"],
            "cue_terms": ["order block", "bullish"],
            "source_url": "https://youtu.be/chart",
            "text": "Here we take an order block long after a bullish continuation.",
            "cue_score": 20,
            "start": 2.0,
            "transcript_source": "cached_json",
        },
    ]

    packet = build_dense_supervision_packet_from_rows(rows, limit=10, per_video_cap=4)

    assert packet["item_count"] == 1
    suggestions = packet["items"][0]["candidate_detections"]
    assert suggestions
    assert suggestions[0]["class_id"] == 4


def test_build_dense_supervision_packet_filters_slide_like_image_even_with_chart_text(tmp_path: Path) -> None:
    slide_path = tmp_path / "slide.png"
    slide = np.full((360, 640, 3), 255, dtype=np.uint8)
    cv2.rectangle(slide, (230, 90), (280, 250), (20, 20, 20), thickness=-1)
    cv2.rectangle(slide, (360, 110), (410, 270), (20, 20, 20), thickness=-1)
    cv2.imwrite(str(slide_path), slide)

    chart_path = tmp_path / "chart.png"
    chart = np.full((360, 640, 3), 255, dtype=np.uint8)
    for x in range(60, 520, 40):
        cv2.line(chart, (x, 80), (x, 300), (225, 225, 225), 1)
    for y in range(90, 300, 35):
        cv2.line(chart, (50, y), (520, y), (225, 225, 225), 1)
    for y in range(80, 320, 30):
        cv2.line(chart, (20, y), (35, y), (80, 80, 80), 1)
    cv2.line(chart, (0, 325), (639, 325), (50, 50, 50), 1)
    for x in range(80, 520, 70):
        cv2.rectangle(chart, (x, 140), (x + 12, 210), (20, 20, 20), thickness=-1)
        cv2.line(chart, (x + 6, 120), (x + 6, 235), (20, 20, 20), 1)
    cv2.imwrite(str(chart_path), chart)

    rows = [
        {
            "example_id": "slide::chartish",
            "frame_path": str(slide_path),
            "frame_status": "extracted",
            "title": "Trade Continuations Using Order Blocks",
            "source_type": "youtube_dense_window",
            "checkpoint": "dense",
            "video_slug": "slide_video",
            "video_id": "slide",
            "topics": ["order_block"],
            "candidate_labels": ["order_block"],
            "cue_terms": ["order block", "entry", "retest"],
            "source_url": "https://youtu.be/slide",
            "text": "Here we are in our first example. Let this play out and take an entry on the retest.",
            "cue_score": 40,
            "start": 1.0,
            "transcript_source": "cached_json",
        },
        {
            "example_id": "chart::real",
            "frame_path": str(chart_path),
            "frame_status": "extracted",
            "title": "Trade Continuations Using Order Blocks",
            "source_type": "youtube_dense_window",
            "checkpoint": "dense",
            "video_slug": "chart_video",
            "video_id": "chart",
            "topics": ["order_block"],
            "candidate_labels": ["order_block"],
            "cue_terms": ["order block", "entry", "retest"],
            "source_url": "https://youtu.be/chart",
            "text": "Here we are in our first example. Let this play out and take an entry on the retest.",
            "cue_score": 30,
            "start": 2.0,
            "transcript_source": "cached_json",
        },
    ]

    packet = build_dense_supervision_packet_from_rows(rows, limit=10, per_video_cap=4)

    assert packet["item_count"] == 1
    assert packet["items"][0]["example_id"] == "chart::real"


def test_select_heuristic_dense_autolabels_promotes_only_strict_candidates() -> None:
    packet = {
        "items": [
            {
                "example_id": "good::1",
                "title": "Trade Continuations Using Order Blocks",
                "candidate_labels": ["bullish_reaction_zone"],
                "cue_terms": ["order block", "entry", "continuation"],
                "candidate_detections": [{"class_id": 3, "bbox": [0.5, 0.5, 0.1, 0.08]}],
            },
            {
                "example_id": "bad::multi",
                "title": "Trade Continuations Using Order Blocks",
                "candidate_labels": ["bullish_reaction_zone"],
                "cue_terms": ["order block"],
                "candidate_detections": [
                    {"class_id": 3, "bbox": [0.5, 0.5, 0.1, 0.08]},
                    {"class_id": 3, "bbox": [0.6, 0.5, 0.1, 0.08]},
                ],
            },
            {
                "example_id": "bad::slide",
                "title": "Reason 2 - Solution",
                "candidate_labels": ["bullish_reaction_zone"],
                "cue_terms": ["order block"],
                "candidate_detections": [{"class_id": 3, "bbox": [0.5, 0.5, 0.1, 0.08]}],
            },
        ]
    }

    promoted = select_heuristic_dense_autolabels(
        packet,
        existing_answer_ids=set(),
        max_new_items=10,
        min_bbox_area=0.0025,
        max_bbox_area=0.08,
    )

    assert promoted == [
        {
            "example_id": "good::1",
            "detections": [{"class_id": 3, "bbox": [0.5, 0.5, 0.1, 0.08]}],
            "review_outcome": "accepted",
            "source": "heuristic_auto_label",
        }
    ]


def test_select_weak_visual_autolabels_promotes_chart_like_order_block(tmp_path: Path) -> None:
    image_path = tmp_path / "chart.png"
    image = np.full((180, 320, 3), 255, dtype=np.uint8)
    for y in range(20, 170, 30):
        cv2.line(image, (8, y), (24, y), (80, 80, 80), 1)
    cv2.line(image, (0, 170), (319, 170), (50, 50, 50), 1)
    cv2.rectangle(image, (150, 80), (210, 120), (90, 220, 220), thickness=-1)
    cv2.imwrite(str(image_path), image)

    dataset_path = tmp_path / "weak.jsonl"
    dataset_path.write_text(
        json.dumps(
            {
                "example_id": "weak::1",
                "active_labels": ["order_block"],
                "checkpoint": "confirmation",
                "review_status": "ready_for_weak_training",
                "eligible_for_training": True,
                "cue_terms": ["order block", "entry"],
                "transcript_window": "bullish continuation order block retest long",
                "screenshot_path": str(image_path),
            }
        )
        + "\n",
        encoding="utf-8",
    )

    promoted = select_weak_visual_autolabels(
        dataset_path,
        root_dir=tmp_path,
        existing_answer_ids=set(),
        max_new_items=10,
    )

    assert len(promoted) == 1
    assert promoted[0]["example_id"] == "weak::1"
    assert promoted[0]["source"] == "weak_visual_auto_label"
    assert promoted[0]["detections"][0]["class_id"] == 4
    bbox = promoted[0]["detections"][0]["bbox"]
    assert pytest.approx(bbox[0], rel=0.01) == 0.5641
    assert pytest.approx(bbox[1], rel=0.01) == 0.5583
    assert pytest.approx(bbox[2], rel=0.02) == 0.19
    assert pytest.approx(bbox[3], rel=0.02) == 0.226


def test_select_teacher_screenshot_autolabels_uses_chart_crop_fallback(tmp_path: Path) -> None:
    image_path = tmp_path / "teacher.png"
    image = np.full((360, 640, 3), 255, dtype=np.uint8)
    cv2.rectangle(image, (40, 20), (600, 120), (220, 120, 60), thickness=-1)
    cv2.rectangle(image, (250, 180), (340, 310), (90, 220, 220), thickness=-1)
    cv2.imwrite(str(image_path), image)

    dataset_path = tmp_path / "teacher.jsonl"
    dataset_path.write_text(
        json.dumps(
            {
                "example_id": "teacher::1",
                "active_labels": ["protected_swing"],
                "checkpoint": "confirmation",
                "supporting_topics": ["continuation"],
                "screenshot_path": str(image_path),
            }
        )
        + "\n",
        encoding="utf-8",
    )

    promoted = select_teacher_screenshot_autolabels(
        dataset_path,
        root_dir=tmp_path,
        existing_answer_ids=set(),
        max_new_items=10,
    )

    assert len(promoted) == 1
    assert promoted[0]["example_id"] == "teacher::1"
    assert promoted[0]["source"] == "teacher_screenshot_auto_label"
    assert promoted[0]["detections"][0]["class_id"] == 2


def test_select_weak_visual_autolabels_maps_protected_swing_to_fractal_low(tmp_path: Path) -> None:
    image_path = tmp_path / "chart.png"
    image = np.full((180, 320, 3), 255, dtype=np.uint8)
    for y in range(20, 170, 30):
        cv2.line(image, (8, y), (24, y), (80, 80, 80), 1)
    cv2.line(image, (0, 170), (319, 170), (50, 50, 50), 1)
    cv2.rectangle(image, (140, 70), (210, 125), (90, 220, 220), thickness=-1)
    cv2.imwrite(str(image_path), image)

    dataset_path = tmp_path / "weak_protected.jsonl"
    dataset_path.write_text(
        json.dumps(
            {
                "example_id": "weak::protected",
                "active_labels": ["protected_swing"],
                "checkpoint": "confirmation",
                "review_status": "ready_for_weak_training",
                "eligible_for_training": True,
                "cue_terms": ["protected swing", "entry"],
                "transcript_window": "bullish continuation with a new protected low before expansion higher",
                "screenshot_path": str(image_path),
            }
        )
        + "\n",
        encoding="utf-8",
    )

    promoted = select_weak_visual_autolabels(
        dataset_path,
        root_dir=tmp_path,
        existing_answer_ids=set(),
        max_new_items=10,
    )

    assert len(promoted) == 1
    assert promoted[0]["detections"][0]["class_id"] == 2


def test_export_yolo_dataset_replaces_previous_snapshot(tmp_path) -> None:
    from dataclasses import replace
    config = build_config(root_dir=tmp_path)
    config = replace(config, phase2=replace(config.phase2, benchmark_target_count=1))
    image_a = tmp_path / "a.jpg"
    image_a.write_bytes(b"a")
    image_b = tmp_path / "b.jpg"
    image_b.write_bytes(b"b")

    config.paths.yolo_images_train_dir.mkdir(parents=True, exist_ok=True)
    stale_image = config.paths.yolo_images_train_dir / "stale.jpg"
    stale_image.write_bytes(b"stale")
    config.paths.yolo_labels_train_dir.mkdir(parents=True, exist_ok=True)
    stale_label = config.paths.yolo_labels_train_dir / "stale.txt"
    stale_label.write_text("0 0.5 0.5 0.2 0.2", encoding="utf-8")

    stats = export_yolo_dataset(
        [
            {
                "example_id": "demo::1",
                "image_path": str(image_a),
                "time_index": 1,
                "detections": [{"class_id": 0, "bbox": [0.5, 0.5, 0.2, 0.2]}],
                "issues": [],
            },
            {
                "example_id": "demo::2",
                "image_path": str(image_b),
                "time_index": 2,
                "detections": [{"class_id": 2, "bbox": [0.4, 0.4, 0.2, 0.2]}],
                "issues": [],
            },
        ],
        config,
    )

    assert not stale_image.exists()
    assert not stale_label.exists()
    assert stats["train_count"] == 1
    assert stats["benchmark_count"] == 1
    assert config.paths.yolo_benchmark_data_yaml_path.exists()
    assert config.paths.benchmark_manifest_path.exists()


def test_export_yolo_dataset_excludes_synthetic_rows_from_benchmark(tmp_path) -> None:
    from dataclasses import replace
    config = build_config(root_dir=tmp_path)
    config = replace(config, phase2=replace(config.phase2, benchmark_target_count=1))
    image_a = tmp_path / "a.jpg"
    image_a.write_bytes(b"a")
    image_b = tmp_path / "b.jpg"
    image_b.write_bytes(b"b")

    stats = export_yolo_dataset(
        [
            {
                "example_id": "real::1",
                "image_path": str(image_a),
                "time_index": 1,
                "detections": [{"class_id": 0, "bbox": [0.5, 0.5, 0.2, 0.2]}],
                "issues": [],
            },
            {
                "example_id": "synthetic::1",
                "image_path": str(image_b),
                "time_index": 2,
                "detections": [{"class_id": 1, "bbox": [0.4, 0.4, 0.2, 0.2]}],
                "issues": [],
                "source": "synthetic_sidecar",
            },
        ],
        config,
    )

    assert stats["benchmark_count"] == 1
    assert stats["train_count"] == 1


def test_generate_synthetic_sidecar_targets_all_scarce_classes(tmp_path: Path) -> None:
    from dataclasses import replace

    config = build_config(root_dir=tmp_path)
    config = replace(config, phase2=replace(config.phase2, synthetic_sidecar_enabled=True, synthetic_sidecar_target_per_class=10))

    rows = generate_synthetic_sidecar(
        config,
        class_counts={
            "fractal_swing_high": 6,
            "fractal_swing_low": 7,
            "inversion_fvg": 6,
            "liquidity_sweep_low": 8,
        },
    )

    assert len(rows) == 13
    assert len(rows) == 13
    assert config.paths.phase2_synthetic_sidecar_path.exists()


def test_build_priority_review_queue_prioritizes_scarce_classes() -> None:
    packet = {
        "items": [
            {
                "example_id": "dense::1",
                "image_path": "a.jpg",
                "title": "A",
                "candidate_labels": ["order_block"],
                "cue_terms": ["order block"],
                "candidate_detections": [],
            },
            {
                "example_id": "dense::2",
                "image_path": "b.jpg",
                "title": "B",
                "candidate_labels": ["protected_swing", "liquidity_sweep_high"],
                "cue_terms": ["protected swing", "sweep"],
                "candidate_detections": [{"class_id": 2, "bbox": [0.5, 0.5, 0.1, 0.1]}],
            },
        ]
    }

    queue = build_priority_review_queue(
        packet,
        existing_answer_ids=set(),
        class_counts={"bullish_reaction_zone": 25, "bearish_reaction_zone": 21, "protected_swing": 2, "liquidity_sweep_high": 1},
        limit=10,
    )

    assert queue[0]["example_id"] == "dense::2"
    assert "protected_swing" in queue[0]["suggested_classes"]


def test_select_setup_quality_autolabels_promotes_positive_and_negative_cases() -> None:
    packet = {
        "items": [
            {
                "example_id": "good::1",
                "recommended_action": "accept",
                "setup_type": "high_probability_long",
                "setup_confidence": 0.91,
                "candidate_detections": [{"class_id": 3, "bbox": [0.5, 0.5, 0.2, 0.1]}],
            },
            {
                "example_id": "bad::1",
                "recommended_action": "no_setup",
                "setup_type": "invalid_chop",
                "setup_confidence": 0.88,
                "candidate_detections": [],
            },
            {
                "example_id": "weak::1",
                "recommended_action": "accept",
                "setup_type": "high_probability_short",
                "setup_confidence": 0.55,
                "candidate_detections": [{"class_id": 4, "bbox": [0.4, 0.4, 0.2, 0.1]}],
            },
        ]
    }

    promoted = select_setup_quality_autolabels(
        packet,
        existing_answer_ids=set(),
        max_new_items=10,
        positive_confidence_floor=0.72,
        negative_confidence_floor=0.78,
    )

    assert promoted == [
        {
            "example_id": "good::1",
            "detections": [{"class_id": 3, "bbox": [0.5, 0.5, 0.2, 0.1]}],
            "review_outcome": "accepted",
            "note": "Auto-accepted from setup-quality scorer (high_probability_long, confidence=0.910).",
            "source": "setup_quality_auto_label",
        },
        {
            "example_id": "bad::1",
            "detections": [],
            "review_outcome": "no_setup",
            "note": "Auto-promoted to no_setup from setup-quality scorer (confidence=0.880).",
            "source": "setup_quality_auto_label",
        },
    ]


def test_select_accept_packet_autolabels_promotes_accept_items() -> None:
    packet = {
        "items": [
            {
                "example_id": "accept::1",
                "recommended_action": "accept",
                "candidate_detections": [
                    {"class_id": 4, "bbox": [0.4, 0.4, 0.2, 0.1], "confidence": 0.61},
                    {"class_id": 1, "bbox": [0.5, 0.6, 0.1, 0.1], "confidence": 0.47},
                ],
            },
            {
                "example_id": "skip::1",
                "recommended_action": "adjust",
                "candidate_detections": [{"class_id": 2, "bbox": [0.5, 0.5, 0.2, 0.1], "confidence": 0.91}],
            },
        ]
    }

    promoted = select_accept_packet_autolabels(
        packet,
        existing_answer_ids=set(),
        max_new_items=10,
        confidence_floor=0.35,
    )

    assert promoted == [
        {
            "example_id": "accept::1",
            "detections": [
                {"class_id": 4, "bbox": [0.4, 0.4, 0.2, 0.1]},
                {"class_id": 1, "bbox": [0.5, 0.6, 0.1, 0.1]},
            ],
            "review_outcome": "accepted",
            "note": "Auto-promoted from packet recommended_action=accept (max_confidence=0.610).",
            "source": "accept_packet_auto_label",
        }
    ]


def test_select_scarce_accept_packet_autolabels_promotes_adjust_items_for_scarce_classes() -> None:
    packet = {
        "items": [
            {
                "example_id": "scarce::1",
                "recommended_action": "adjust",
                "candidate_labels": ["bearish_reaction_zone"],
                "candidate_detections": [{"class_id": 4, "bbox": [0.4, 0.4, 0.2, 0.1], "confidence": 0.24}],
            },
            {
                "example_id": "common::1",
                "recommended_action": "adjust",
                "candidate_labels": ["protected_swing"],
                "candidate_detections": [{"class_id": 2, "bbox": [0.5, 0.5, 0.2, 0.1], "confidence": 0.91}],
            },
        ]
    }

    promoted = select_scarce_accept_packet_autolabels(
        packet,
        existing_answer_ids=set(),
        max_new_items=10,
        confidence_floor=0.20,
        scarce_class_names=("liquidity_sweep_high", "bearish_reaction_zone"),
    )

    assert promoted == [
        {
            "example_id": "scarce::1",
            "detections": [{"class_id": 4, "bbox": [0.4, 0.4, 0.2, 0.1]}],
            "review_outcome": "accepted",
            "note": "Auto-promoted for scarce class coverage (max_confidence=0.240).",
            "source": "scarce_accept_packet_auto_label",
        }
    ]
