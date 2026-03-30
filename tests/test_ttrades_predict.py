from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np

import predict
from config import build_config


def test_select_setup_type_returns_uncertain_for_flat_scores(tmp_path: Path) -> None:
    config = build_config(root_dir=tmp_path)
    scores = {
        "high_probability_long": 0.326,
        "high_probability_short": 0.324,
        "invalid_chop": 0.349,
    }

    setup_type, warnings = predict.select_setup_type(scores, config.phase1)

    assert setup_type == "uncertain"
    assert any("below serving confidence threshold" in warning or "below serving margin threshold" in warning for warning in warnings)


def test_select_setup_type_keeps_confident_prediction(tmp_path: Path) -> None:
    config = build_config(root_dir=tmp_path)
    config = replace(
        config,
        phase1=replace(
            config.phase1,
            serving_min_confidence=0.55,
            serving_min_margin=0.15,
        ),
    )
    scores = {
        "high_probability_long": 0.82,
        "high_probability_short": 0.10,
        "invalid_chop": 0.08,
    }

    setup_type, warnings = predict.select_setup_type(scores, config.phase1)

    assert setup_type == "high_probability_long"
    assert warnings == []


def test_select_chart_state_labels_picks_highest_probability() -> None:
    labels = predict.select_chart_state_labels(
        {
            "path_family": {"continuation": 0.2, "reversal": 0.8},
            "fractal_stage": {"c1": 0.1, "c2": 0.2, "c3": 0.7},
        }
    )

    assert labels == {
        "path_family": "reversal",
        "fractal_stage": "c3",
    }


def test_predict_bundle_returns_chart_state_and_detector_markups(monkeypatch, tmp_path: Path) -> None:
    config = build_config(root_dir=tmp_path)
    htf = tmp_path / "htf.png"
    itf = tmp_path / "itf.png"
    ltf = tmp_path / "ltf.png"
    for path in (htf, itf, ltf):
        path.write_bytes(b"img")
    config.paths.chart_state_checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    config.paths.chart_state_checkpoint_path.write_text("stub", encoding="utf-8")

    monkeypatch.setattr(predict, "build_config", lambda: config)
    monkeypatch.setattr(
        predict,
        "load_chart_corpus",
        lambda _config: type("Corpus", (), {"examples": []})(),
    )
    embedding_map = {
        str(htf.resolve()): np.array([1.0, 0.0, 0.0], dtype=np.float32),
        str(itf.resolve()): np.array([0.0, 1.0, 0.0], dtype=np.float32),
        str(ltf.resolve()): np.array([0.0, 0.0, 1.0], dtype=np.float32),
    }
    monkeypatch.setattr(predict, "find_example_by_image", lambda _examples, _image_path: None)
    monkeypatch.setattr(
        predict,
        "embed_chart_image",
        lambda image_path, _config: embedding_map[str(image_path.resolve())],
    )
    monkeypatch.setattr(
        predict,
        "load_chart_state_checkpoint",
        lambda _path: ("model", {"path_family": ["continuation", "reversal"], "fractal_stage": ["c1", "c2"]}, None),
    )
    monkeypatch.setattr(
        predict,
        "predict_chart_state_probabilities",
        lambda _model, features, *, label_spaces, device: {
            "path_family": {"continuation": 0.8, "reversal": 0.2},
            "fractal_stage": {"c1": 0.25, "c2": 0.75},
        },
    )
    monkeypatch.setattr(
        predict,
        "_predict_markups_for_image",
        lambda image_path, _config, warnings: [
            {
                "class_id": 2,
                "class_name": "protected_swing",
                "confidence": 0.91,
                "x_center": 0.5,
                "y_center": 0.5,
                "width": 0.2,
                "height": 0.1,
            }
        ],
    )
    monkeypatch.setattr(
        predict,
        "_annotate_image",
        lambda image_path, detections, output_path: output_path,
    )

    result = predict.predict_bundle(htf, itf, ltf)

    assert result["chart_state"] == {
        "path_family": "continuation",
        "fractal_stage": "c2",
    }
    assert set(result["detector_markups_by_frame"].keys()) == {"htf", "itf", "ltf"}
    assert result["warnings"] == []
