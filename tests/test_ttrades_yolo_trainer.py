from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import numpy as np

from config import build_config
from trainer.yolo_trainer import (
    _compute_benchmark_report,
    _select_device,
    copy_if_different,
    extract_yolo_epoch_payloads,
    reset_yolo_run_directory,
    resolve_yolo_base_model,
    write_phase3_report_from_existing_run,
)


class _FakeYOLO:
    def __init__(self, name: str) -> None:
        if name == "missing.pt":
            raise RuntimeError("missing")
        self.name = name
        self.ckpt_path = f"resolved::{name}"


class _FakeBenchmarkBox:
    def __init__(self) -> None:
        self.map = 0.12
        self.map50 = 0.34
        self.maps = np.array([0.1, 0.2, 0.3], dtype=np.float32)


class _FakeBenchmarkMetrics:
    def __init__(self) -> None:
        self.box = _FakeBenchmarkBox()


class _FakeBenchmarkYOLO(_FakeYOLO):
    def val(self, **_kwargs):
        return _FakeBenchmarkMetrics()

    def predict(self, **_kwargs):
        return None


class _FakeBoxes:
    def __init__(self, classes: list[int], confidences: list[float], xyxy: list[list[float]]) -> None:
        self.cls = np.array(classes, dtype=np.float32)
        self.conf = np.array(confidences, dtype=np.float32)
        self.xyxy = np.array(xyxy, dtype=np.float32)

    def __len__(self) -> int:
        return len(self.cls)


class _FakePrediction:
    def __init__(self, path: Path, boxes: _FakeBoxes) -> None:
        self.path = str(path)
        self.boxes = boxes


class _FakeBenchmarkYOLOWithPredictions(_FakeBenchmarkYOLO):
    def predict(self, **kwargs):
        source = Path(kwargs["source"])
        project = Path(kwargs["project"])
        name = kwargs["name"]
        overlay_dir = project / name
        overlay_dir.mkdir(parents=True, exist_ok=True)
        for image_path in source.glob("*.jpg"):
            (overlay_dir / image_path.name).write_bytes(b"overlay")
        return [
            _FakePrediction(
                source / "hard_negative.jpg",
                _FakeBoxes([0], [0.42], [[1.0, 2.0, 30.0, 40.0]]),
            ),
            _FakePrediction(
                source / "positive.jpg",
                _FakeBoxes([], [], []),
            ),
        ]


def test_resolve_yolo_base_model_uses_requested_model(tmp_path: Path) -> None:
    config = build_config(root_dir=tmp_path)

    model, resolved_name, warnings = resolve_yolo_base_model(
        config,
        yolo_factory=_FakeYOLO,
    )

    assert resolved_name == config.phase3.model_name
    assert getattr(model, "name") == config.phase3.model_name
    assert warnings == []


def test_resolve_yolo_base_model_falls_back_when_requested_model_fails(tmp_path: Path) -> None:
    config = build_config(root_dir=tmp_path)
    config = replace(
        config,
        phase3=replace(
            config.phase3,
            model_name="missing.pt",
            fallback_model_names=("yolo11n.pt",),
        ),
    )

    model, resolved_name, warnings = resolve_yolo_base_model(
        config,
        yolo_factory=_FakeYOLO,
    )

    assert resolved_name == "yolo11n.pt"
    assert getattr(model, "name") == "yolo11n.pt"
    assert any("missing.pt" in warning for warning in warnings)


def test_copy_if_different_skips_same_file(tmp_path: Path) -> None:
    target = tmp_path / "same.onnx"
    target.write_text("x", encoding="utf-8")

    copy_if_different(target, target)

    assert target.read_text(encoding="utf-8") == "x"


def test_extract_yolo_epoch_payloads_reads_new_rows(tmp_path: Path) -> None:
    results_csv = tmp_path / "results.csv"
    results_csv.write_text(
        "epoch,train/box_loss,train/cls_loss,metrics/mAP50-95(B),metrics/mAP50(B),metrics/precision(B),metrics/recall(B)\n"
        "0,1.0,2.0,0.1,0.2,0.3,0.4\n"
        "1,0.9,1.8,0.2,0.3,0.4,0.5\n",
        encoding="utf-8",
    )

    payloads = extract_yolo_epoch_payloads(results_csv, start_after_epoch=1)

    assert payloads == [
        {
            "epoch": 2,
            "phase3/box_loss": 0.9,
            "phase3/cls_loss": 1.8,
            "phase3/val_mAP50_95": 0.2,
            "phase3/val_mAP50": 0.3,
            "phase3/precision": 0.4,
            "phase3/recall": 0.5,
        }
    ]


def test_reset_yolo_run_directory_clears_stale_files(tmp_path: Path) -> None:
    save_dir = tmp_path / "ttrades_yolo"
    save_dir.mkdir(parents=True, exist_ok=True)
    stale = save_dir / "results.csv"
    stale.write_text("old", encoding="utf-8")

    reset_yolo_run_directory(save_dir)

    assert save_dir.exists()
    assert not stale.exists()


def test_write_phase3_report_from_existing_run_includes_benchmark_and_source_counts(tmp_path: Path) -> None:
    config = build_config(root_dir=tmp_path)
    run_dir = config.paths.results_dir / "ultralytics_runs" / "ttrades_yolo"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "results.csv").write_text(
        "epoch,train/box_loss,train/cls_loss,metrics/mAP50-95(B),metrics/mAP50(B),metrics/precision(B),metrics/recall(B)\n"
        "0,1.0,2.0,0.1,0.2,0.3,0.4\n",
        encoding="utf-8",
    )
    config.paths.phase2_dataset_stats_path.write_text('{"train_count":41,"val_count":10}', encoding="utf-8")
    config.paths.benchmark_manifest_path.write_text('{"items":[{"example_id":"a"},{"example_id":"b"}]}', encoding="utf-8")
    config.paths.workflow_status_path.write_text(
        '{"metrics":{"focused_reviewed_count":11,"dense_reviewed_count":24,"heuristic_auto_label_count":5,"dense_remaining_count":444}}',
        encoding="utf-8",
    )

    report = write_phase3_report_from_existing_run(config, resolved_model_name="yolo26n.pt", preflight_warnings=[])

    assert report["benchmark_count"] == 2
    assert report["train_count_at_run"] == 41
    assert report["source_composition"]["heuristic_auto_label_count"] == 5


def test_compute_benchmark_report_accepts_numpy_maps(tmp_path: Path) -> None:
    config = build_config(root_dir=tmp_path)
    config = replace(config, phase3=replace(config.phase3, device="0"))
    config.paths.yolo_benchmark_images_dir.mkdir(parents=True, exist_ok=True)
    (config.paths.yolo_benchmark_images_dir / "a.jpg").write_bytes(b"a")
    config.paths.yolo_benchmark_data_yaml_path.write_text("path: benchmark\ntrain: images\nval: images\nnames:\n  0: liquidity_sweep_high\n", encoding="utf-8")
    weights = tmp_path / "weights.pt"
    weights.write_text("x", encoding="utf-8")

    import trainer.yolo_trainer as yolo_trainer

    original_select_device = yolo_trainer._select_device
    yolo_trainer._select_device = lambda _config: "0"
    try:
        report = _compute_benchmark_report(config, weights_path=weights, yolo_factory=_FakeBenchmarkYOLO)
    finally:
        yolo_trainer._select_device = original_select_device

    assert report["mAP50_95"] == 0.12
    assert report["mAP50"] == 0.34
    assert "liquidity_sweep_high" in report["classwise_ap50_95"]


def test_compute_benchmark_report_writes_per_image_prediction_manifest(tmp_path: Path) -> None:
    config = build_config(root_dir=tmp_path)
    config = replace(config, phase3=replace(config.phase3, device="0"))
    config.paths.yolo_benchmark_images_dir.mkdir(parents=True, exist_ok=True)
    config.paths.yolo_benchmark_labels_dir.mkdir(parents=True, exist_ok=True)
    (config.paths.yolo_benchmark_images_dir / "hard_negative.jpg").write_bytes(b"a")
    (config.paths.yolo_benchmark_images_dir / "positive.jpg").write_bytes(b"b")
    (config.paths.yolo_benchmark_labels_dir / "hard_negative.txt").write_text("", encoding="utf-8")
    (config.paths.yolo_benchmark_labels_dir / "positive.txt").write_text(
        "3 0.500000 0.500000 0.250000 0.250000\n",
        encoding="utf-8",
    )
    config.paths.yolo_benchmark_data_yaml_path.write_text(
        "path: benchmark\ntrain: images\nval: images\nnames:\n  0: liquidity_sweep_high\n  3: bullish_reaction_zone\n",
        encoding="utf-8",
    )
    config.paths.benchmark_manifest_path.write_text(
        json.dumps(
            {
                "target_count": 2,
                "items": [
                    {
                        "example_id": "hard-negative",
                        "safe_name": "hard_negative",
                        "hard_negative": True,
                        "review_outcome": "no_setup",
                        "class_names": [],
                    },
                    {
                        "example_id": "positive",
                        "safe_name": "positive",
                        "hard_negative": False,
                        "review_outcome": "accepted",
                        "class_names": ["bullish_reaction_zone"],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    weights = tmp_path / "weights.pt"
    weights.write_text("x", encoding="utf-8")

    import trainer.yolo_trainer as yolo_trainer

    original_select_device = yolo_trainer._select_device
    yolo_trainer._select_device = lambda _config: "0"
    try:
        report = _compute_benchmark_report(config, weights_path=weights, yolo_factory=_FakeBenchmarkYOLOWithPredictions)
    finally:
        yolo_trainer._select_device = original_select_device

    prediction_report_path = Path(report["per_image_report_path"])
    prediction_report = json.loads(prediction_report_path.read_text(encoding="utf-8"))
    hard_negative = next(item for item in prediction_report["items"] if item["safe_name"] == "hard_negative")
    positive = next(item for item in prediction_report["items"] if item["safe_name"] == "positive")

    assert report["hard_negative_false_positive_count"] == 1
    assert report["per_image_review_queue_count"] == 2
    assert prediction_report["summary"]["hard_negative_false_positive_rate"] == 1.0
    assert hard_negative["review_bucket"] == "hard_negative_fp"
    assert hard_negative["predicted_boxes"][0]["class_name"] == "liquidity_sweep_high"
    assert positive["review_bucket"] == "single_label_miss"
    assert positive["missing_class_names"] == ["bullish_reaction_zone"]
