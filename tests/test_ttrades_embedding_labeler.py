from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np

from config import build_config
from data_loader import ChartExample
from labeler.embedding_labeler import (
    AnchorExample,
    bootstrap_anchor_examples,
    label_examples_with_anchors,
)


def _example(example_id: str, vector: list[float], text: str, time_index: int) -> ChartExample:
    return ChartExample(
        example_id=example_id,
        image_path=Path(f"{example_id}.png"),
        embedding=np.array(vector, dtype=np.float32),
        text=text,
        title=example_id,
        source_type="unit_test",
        time_index=time_index,
        metadata={},
    )


def test_bootstrap_anchor_examples_and_abstain_logic() -> None:
    examples = [
        _example("long_anchor", [1.0, 0.0, 0.0, 0.0], "bullish continuation higher", 0),
        _example("short_anchor", [0.0, 1.0, 0.0, 0.0], "bearish continuation lower", 1),
        _example("invalid_anchor", [0.0, 0.0, 1.0, 0.0], "stand aside invalid chop", 2),
        _example("candidate_long", [0.95, 0.05, 0.0, 0.0], "bullish sweep long", 3),
        _example("candidate_short", [0.05, 0.95, 0.0, 0.0], "bearish sweep short", 4),
        _example("candidate_uncertain", [0.34, 0.33, 0.33, 0.0], "mixed chop range", 5),
    ]

    anchors = bootstrap_anchor_examples(examples, per_class=1)
    assert {anchor.class_label for anchor in anchors} == {
        "high_probability_long",
        "high_probability_short",
        "invalid_chop",
    }

    config = build_config()
    phase1 = replace(
        config.phase1,
        knn_k=1,
        prototype_weight=0.5,
        knn_weight=0.5,
        abstain_threshold=0.80,
        confidence_floor=0.75,
        min_margin=0.20,
    )

    results = label_examples_with_anchors(examples, anchors, phase1)
    labels = {row.example_id: row.pseudo_label for row in results.rows}

    assert labels["candidate_long"] == "high_probability_long"
    assert labels["candidate_short"] == "high_probability_short"
    assert labels["candidate_uncertain"] is None
    assert results.review_queue[0]["example_id"] == "candidate_uncertain"


def test_anchor_examples_can_reference_existing_examples_directly() -> None:
    examples = [_example("anchor_ref", [1.0, 0.0, 0.0, 0.0], "bullish continuation", 0)]
    anchors = [
        AnchorExample(
            class_label="high_probability_long",
            image_path=None,
            example_id="anchor_ref",
            note="existing",
            metadata={},
        )
    ]
    config = build_config()
    results = label_examples_with_anchors(examples, anchors, config.phase1)
    assert results.rows[0].pseudo_label == "high_probability_long"

