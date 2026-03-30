from __future__ import annotations

import time
import json
import shutil
import threading
from pathlib import Path
from typing import Any

from config import AppConfig, YOLO_CLASS_NAMES


RESULTS_TSV_PATH = Path("results") / "results_yolo.tsv"
BEST_WEIGHTS_PATH = Path("models") / "yolo26_ttrades_markup_best.pt"
BEST_ONNX_PATH = Path("models") / "yolo26_ttrades_markup_best.onnx"


def _load_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _benchmark_manifest_count(payload: dict[str, Any]) -> int:
    items = payload.get("items")
    if isinstance(items, list):
        return len(items)
    example_ids = payload.get("example_ids")
    if isinstance(example_ids, list):
        return len(example_ids)
    return 0


def _compute_benchmark_report(config: AppConfig, *, weights_path: Path, yolo_factory=None) -> dict[str, Any]:
    benchmark_images_dir = config.paths.yolo_benchmark_images_dir
    benchmark_data_yaml_path = config.paths.yolo_benchmark_data_yaml_path
    if not benchmark_data_yaml_path.exists() or not benchmark_images_dir.exists():
        return {}
    if not any(benchmark_images_dir.iterdir()):
        return {}

    YOLO = yolo_factory or _require_ultralytics()
    benchmark_model = YOLO(str(weights_path))
    benchmark_metrics = benchmark_model.val(
        data=str(benchmark_data_yaml_path),
        imgsz=config.phase3.imgsz,
        batch=1,
        device=_select_device(config),
        split="val",
        plots=False,
        verbose=False,
    )
    box_metrics = getattr(benchmark_metrics, "box", None)
    maps_value = getattr(box_metrics, "maps", None)
    class_maps = [] if maps_value is None else [float(value) for value in list(maps_value)]
    benchmark_report = {
        "mAP50_95": round(float(getattr(box_metrics, "map", 0.0) or 0.0), 6),
        "mAP50": round(float(getattr(box_metrics, "map50", 0.0) or 0.0), 6),
        "classwise_ap50_95": {
            YOLO_CLASS_NAMES[index]: round(float(value), 6)
            for index, value in enumerate(class_maps[: len(YOLO_CLASS_NAMES)])
        },
    }
    benchmark_overlay_dir = config.paths.results_dir / "benchmark_overlays" / "latest"
    reset_yolo_run_directory(benchmark_overlay_dir)
    predictions = benchmark_model.predict(
        source=str(benchmark_images_dir),
        imgsz=config.phase3.imgsz,
        project=str(benchmark_overlay_dir.parent),
        name=benchmark_overlay_dir.name,
        exist_ok=True,
        save=True,
        verbose=False,
    )
    manifest_payload = _load_optional_json(config.paths.benchmark_manifest_path)
    hard_negative_items = [item for item in manifest_payload.get("items", []) if bool(item.get("hard_negative"))]
    if hard_negative_items:
        prediction_lookup: dict[str, Any] = {}
        for prediction in predictions:
            image_path = Path(str(getattr(prediction, "path", "")))
            if not image_path.name:
                continue
            prediction_lookup[image_path.stem] = prediction
        hard_negative_false_positives = 0
        for item in hard_negative_items:
            safe_name = str(item.get("safe_name", "")).strip()
            prediction = prediction_lookup.get(safe_name)
            predicted_count = 0
            if prediction is not None and getattr(prediction, "boxes", None) is not None:
                predicted_count = len(prediction.boxes)
            if predicted_count > 0:
                hard_negative_false_positives += 1
        benchmark_report["hard_negative_count"] = len(hard_negative_items)
        benchmark_report["hard_negative_false_positive_count"] = hard_negative_false_positives
        benchmark_report["hard_negative_false_positive_rate"] = round(
            hard_negative_false_positives / len(hard_negative_items), 6
        )
    benchmark_report["overlay_dir"] = str(benchmark_overlay_dir.resolve())
    return benchmark_report


def _require_ultralytics():
    try:
        from ultralytics import YOLO
    except ImportError as exc:  # pragma: no cover - import guard only
        raise RuntimeError("Ultralytics is required for Phase 3 training.") from exc
    return YOLO


def _select_device(config: AppConfig) -> str | int:
    import torch

    if config.phase3.device != "auto":
        return config.phase3.device
    if torch.cuda.is_available():
        return 0
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def _find_column(frame, candidates: tuple[str, ...]) -> str:
    lowered = {column.lower(): column for column in frame.columns}
    for candidate in candidates:
        if candidate.lower() in lowered:
            return lowered[candidate.lower()]
    for column in frame.columns:
        lowered_name = column.lower()
        if all(token in lowered_name for token in candidates[0].lower().split("/")):
            return column
    raise KeyError(f"Could not find any of {candidates} in {tuple(frame.columns)}")


def copy_if_different(source: Path, destination: Path) -> None:
    if source.resolve() == destination.resolve():
        return
    shutil.copy2(source, destination)


def reset_yolo_run_directory(save_dir: Path) -> None:
    if save_dir.exists():
        shutil.rmtree(save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)


def resolve_yolo_base_model(config: AppConfig, *, yolo_factory=None):
    YOLO = yolo_factory or _require_ultralytics()
    warnings: list[str] = []
    candidates = [config.phase3.model_name, *config.phase3.fallback_model_names]
    seen: set[str] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        try:
            model = YOLO(candidate)
        except Exception as exc:
            warnings.append(f"Failed to load base model {candidate}: {exc}")
            continue
        return model, candidate, warnings
    raise RuntimeError("Could not resolve any usable YOLO base model from configured candidates.")


def extract_yolo_epoch_payloads(results_csv: Path, *, start_after_epoch: int = 0) -> list[dict[str, float]]:
    import pandas as pd

    if not results_csv.exists():
        return []
    frame = pd.read_csv(results_csv)
    if frame.empty:
        return []
    epoch_column = _find_column(frame, ("epoch",))
    box_loss_column = _find_column(frame, ("train/box_loss", "box_loss"))
    cls_loss_column = _find_column(frame, ("train/cls_loss", "cls_loss"))
    map50_95_column = _find_column(frame, ("metrics/mAP50-95(B)", "metrics/mAP50-95"))
    map50_column = _find_column(frame, ("metrics/mAP50(B)", "metrics/mAP50"))
    precision_column = _find_column(frame, ("metrics/precision(B)", "metrics/precision"))
    recall_column = _find_column(frame, ("metrics/recall(B)", "metrics/recall"))

    payloads: list[dict[str, float]] = []
    for _, row in frame.iterrows():
        epoch = int(row[epoch_column]) + 1
        if epoch <= start_after_epoch:
            continue
        payloads.append(
            {
                "epoch": epoch,
                "phase3/box_loss": float(row[box_loss_column]),
                "phase3/cls_loss": float(row[cls_loss_column]),
                "phase3/val_mAP50_95": float(row[map50_95_column]),
                "phase3/val_mAP50": float(row[map50_column]),
                "phase3/precision": float(row[precision_column]),
                "phase3/recall": float(row[recall_column]),
            }
        )
    return payloads


def _start_wandb_csv_monitor(results_csv: Path, run: Any):
    state = {"last_epoch": 0}
    stop_event = threading.Event()

    def worker() -> None:
        while not stop_event.is_set():
            try:
                payloads = extract_yolo_epoch_payloads(results_csv, start_after_epoch=state["last_epoch"])
                for payload in payloads:
                    run.log(payload)
                    state["last_epoch"] = int(payload["epoch"])
            except Exception:
                pass
            time.sleep(1.0)

    thread = threading.Thread(target=worker, name="wandb-yolo-csv-monitor", daemon=True)
    thread.start()
    return stop_event, thread, state


def write_phase3_report_from_existing_run(
    config: AppConfig,
    *,
    resolved_model_name: str | None = None,
    preflight_warnings: list[str] | None = None,
    include_benchmark: bool = True,
) -> dict[str, Any]:
    import pandas as pd

    save_dir = config.paths.results_dir / "ultralytics_runs" / "ttrades_yolo"
    results_csv = save_dir / "results.csv"
    target_weights = config.root_dir / BEST_WEIGHTS_PATH
    target_onnx = config.root_dir / BEST_ONNX_PATH
    if not results_csv.exists():
        raise RuntimeError(f"Missing YOLO results CSV: {results_csv}")
    frame = pd.read_csv(results_csv)
    map50_95_column = _find_column(frame, ("metrics/mAP50-95(B)", "metrics/mAP50-95"))
    best_map = float(frame[map50_95_column].max()) if len(frame.index) else 0.0
    benchmark_manifest = _load_optional_json(config.paths.benchmark_manifest_path)
    phase2_stats = _load_optional_json(config.paths.phase2_dataset_stats_path)
    workflow_status = _load_optional_json(config.paths.workflow_status_path)
    benchmark_report = {}
    target_weights = config.root_dir / BEST_WEIGHTS_PATH
    if include_benchmark and target_weights.exists():
        benchmark_report = _compute_benchmark_report(config, weights_path=target_weights)
    report = {
        "save_dir": str(save_dir.resolve()),
        "base_model_requested": config.phase3.model_name,
        "base_model_resolved": resolved_model_name or config.phase3.model_name,
        "preflight_warnings": preflight_warnings or [],
        "best_weights_path": str(target_weights.resolve()) if target_weights.exists() else None,
        "best_onnx_path": str(target_onnx.resolve()) if target_onnx.exists() else None,
        "results_tsv_path": str((config.root_dir / RESULTS_TSV_PATH).resolve()),
        "class_names": list(YOLO_CLASS_NAMES),
        "best_val_mAP50_95": round(best_map, 6),
        "train_count_at_run": int(phase2_stats.get("train_count", 0) or 0),
        "val_count_at_run": int(phase2_stats.get("val_count", 0) or 0),
        "benchmark_count": _benchmark_manifest_count(benchmark_manifest),
        "benchmark_report": benchmark_report,
        "source_composition": {
            "focused_reviewed_count": int(workflow_status.get("metrics", {}).get("focused_reviewed_count", 0) or 0),
            "dense_reviewed_count": int(workflow_status.get("metrics", {}).get("dense_reviewed_count", 0) or 0),
            "heuristic_auto_label_count": int(workflow_status.get("metrics", {}).get("heuristic_auto_label_count", 0) or 0),
            "teacher_auto_label_count": int(workflow_status.get("metrics", {}).get("teacher_auto_label_count", 0) or 0),
            "weak_visual_auto_label_count": int(workflow_status.get("metrics", {}).get("weak_visual_auto_label_count", 0) or 0),
            "dense_remaining_count": int(workflow_status.get("metrics", {}).get("dense_remaining_count", 0) or 0),
        },
    }
    (config.paths.results_dir / "phase3_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def train_yolo_detector(config: AppConfig, *, run: Any) -> dict[str, Any]:
    YOLO = _require_ultralytics()
    import pandas as pd

    results_tsv_path = config.root_dir / RESULTS_TSV_PATH
    results_tsv_path.write_text("epoch\tbox_loss\tcls_loss\tval_mAP50_95\tbest_mAP50_95\tnotes\n", encoding="utf-8")
    save_dir = config.paths.results_dir / "ultralytics_runs" / "ttrades_yolo"
    reset_yolo_run_directory(save_dir)
    results_csv = save_dir / "results.csv"

    model, resolved_model_name, preflight_warnings = resolve_yolo_base_model(config, yolo_factory=YOLO)
    if preflight_warnings:
        run.log({"phase3/preflight_warning_count": len(preflight_warnings)})
    enable_live_wandb = callable(getattr(run, "log", None)) and run.__class__.__name__ != "_NullRun"
    stop_event = None
    monitor_thread = None
    monitor_state = {"last_epoch": 0}
    if enable_live_wandb:
        stop_event, monitor_thread, monitor_state = _start_wandb_csv_monitor(results_csv, run)
    results = model.train(
        data=str(config.paths.yolo_data_yaml_path),
        imgsz=config.phase3.imgsz,
        batch=config.phase3.batch,
        epochs=config.phase3.epochs,
        patience=config.phase3.patience,
        amp=config.phase3.amp,
        project=str(config.paths.results_dir / "ultralytics_runs"),
        name="ttrades_yolo",
        exist_ok=True,
        device=_select_device(config),
        save=True,
        verbose=True,
    )
    if stop_event is not None:
        stop_event.set()
    if monitor_thread is not None:
        monitor_thread.join(timeout=5)
    if enable_live_wandb:
        for payload in extract_yolo_epoch_payloads(results_csv, start_after_epoch=monitor_state["last_epoch"]):
            run.log(payload)
            monitor_state["last_epoch"] = int(payload["epoch"])

    save_dir = Path(getattr(results, "save_dir", getattr(model.trainer, "save_dir", save_dir)))
    results_csv = save_dir / "results.csv"
    best_weights = save_dir / "weights" / "best.pt"
    if not results_csv.exists():
        raise RuntimeError(f"YOLO training did not produce {results_csv}.")
    if not best_weights.exists():
        raise RuntimeError(f"YOLO training did not produce {best_weights}.")

    frame = pd.read_csv(results_csv)
    epoch_column = _find_column(frame, ("epoch",))
    box_loss_column = _find_column(frame, ("train/box_loss", "box_loss"))
    cls_loss_column = _find_column(frame, ("train/cls_loss", "cls_loss"))
    map50_95_column = _find_column(frame, ("metrics/mAP50-95(B)", "metrics/mAP50-95"))
    map50_column = _find_column(frame, ("metrics/mAP50(B)", "metrics/mAP50"))
    precision_column = _find_column(frame, ("metrics/precision(B)", "metrics/precision"))
    recall_column = _find_column(frame, ("metrics/recall(B)", "metrics/recall"))

    best_map = float("-inf")
    for _, row in frame.iterrows():
        epoch = int(row[epoch_column]) + 1
        current_map = float(row[map50_95_column])
        note = ""
        if current_map > best_map:
            best_map = current_map
            note = "best"
        with results_tsv_path.open("a", encoding="utf-8") as handle:
            handle.write(
                f"{epoch}\t{float(row[box_loss_column]):.6f}\t{float(row[cls_loss_column]):.6f}\t"
                f"{current_map:.6f}\t{best_map:.6f}\t{note}\n"
            )
        if not enable_live_wandb:
            run.log(
                {
                    "epoch": epoch,
                    "phase3/box_loss": float(row[box_loss_column]),
                    "phase3/cls_loss": float(row[cls_loss_column]),
                    "phase3/val_mAP50_95": current_map,
                    "phase3/val_mAP50": float(row[map50_column]),
                    "phase3/precision": float(row[precision_column]),
                    "phase3/recall": float(row[recall_column]),
                }
            )

    target_weights = config.root_dir / BEST_WEIGHTS_PATH
    target_weights.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(best_weights, target_weights)

    benchmark_report = {}
    preview_images = []
    preview_candidates = sorted(save_dir.glob("val_batch*_pred.jpg")) + sorted(save_dir.glob("train_batch*.jpg"))
    try:
        import wandb

        for image_path in preview_candidates[:10]:
            preview_images.append(wandb.Image(str(image_path), caption=image_path.name))
        if preview_images:
            run.log({"phase3/example_images": preview_images})
    except Exception:  # pragma: no cover - wandb image logging is optional
        pass

    onnx_path = None
    if config.phase3.export_onnx:
        exporter = YOLO(str(target_weights))
        export_result = exporter.export(format="onnx", imgsz=config.phase3.imgsz)
        onnx_path = Path(str(export_result))
        copy_if_different(onnx_path, config.root_dir / BEST_ONNX_PATH)

    if config.paths.yolo_benchmark_data_yaml_path.exists() and any(config.paths.yolo_benchmark_images_dir.iterdir()):
        benchmark_report = _compute_benchmark_report(config, weights_path=target_weights, yolo_factory=YOLO)
        run.log(
            {
                "phase3/benchmark_mAP50_95": benchmark_report["mAP50_95"],
                "phase3/benchmark_mAP50": benchmark_report["mAP50"],
            }
        )

    benchmark_manifest = _load_optional_json(config.paths.benchmark_manifest_path)
    phase2_stats = _load_optional_json(config.paths.phase2_dataset_stats_path)
    workflow_status = _load_optional_json(config.paths.workflow_status_path)
    report = {
        "save_dir": str(save_dir.resolve()),
        "base_model_requested": config.phase3.model_name,
        "base_model_resolved": resolved_model_name,
        "preflight_warnings": preflight_warnings,
        "best_weights_path": str(target_weights.resolve()),
        "best_onnx_path": str((config.root_dir / BEST_ONNX_PATH).resolve()) if onnx_path else None,
        "results_tsv_path": str(results_tsv_path.resolve()),
        "class_names": list(YOLO_CLASS_NAMES),
        "best_val_mAP50_95": round(best_map, 6),
        "train_count_at_run": int(phase2_stats.get("train_count", 0) or 0),
        "val_count_at_run": int(phase2_stats.get("val_count", 0) or 0),
        "benchmark_count": _benchmark_manifest_count(benchmark_manifest),
        "benchmark_report": benchmark_report,
        "source_composition": {
            "focused_reviewed_count": int(workflow_status.get("metrics", {}).get("focused_reviewed_count", 0) or 0),
            "dense_reviewed_count": int(workflow_status.get("metrics", {}).get("dense_reviewed_count", 0) or 0),
            "heuristic_auto_label_count": int(workflow_status.get("metrics", {}).get("heuristic_auto_label_count", 0) or 0),
            "teacher_auto_label_count": int(workflow_status.get("metrics", {}).get("teacher_auto_label_count", 0) or 0),
            "weak_visual_auto_label_count": int(workflow_status.get("metrics", {}).get("weak_visual_auto_label_count", 0) or 0),
            "dense_remaining_count": int(workflow_status.get("metrics", {}).get("dense_remaining_count", 0) or 0),
        },
    }
    (config.paths.results_dir / "phase3_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def load_yolo_detector(weights_path: Path):
    YOLO = _require_ultralytics()
    return YOLO(str(weights_path))
