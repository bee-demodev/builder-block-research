from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from config import YOLO_CLASS_NAMES, build_config
from data_loader import embed_chart_image, find_example_by_image, load_chart_corpus

try:
    from trainer.chart_state_trainer import (
        load_chart_state_checkpoint,
        predict_chart_state_probabilities,
    )
except Exception as exc:  # pragma: no cover - environment dependent
    CHART_STATE_IMPORT_ERROR = exc
    load_chart_state_checkpoint = None  # type: ignore[assignment]
    predict_chart_state_probabilities = None  # type: ignore[assignment]
else:
    CHART_STATE_IMPORT_ERROR = None

try:
    from trainer.mlp_trainer import (
        build_checkpoint_context_warnings,
        load_mlp_checkpoint,
        load_mlp_checkpoint_metadata,
        predict_mlp_probabilities,
    )
except Exception as exc:  # pragma: no cover - environment dependent
    MLP_IMPORT_ERROR = exc
    build_checkpoint_context_warnings = None  # type: ignore[assignment]
    load_mlp_checkpoint = None  # type: ignore[assignment]
    load_mlp_checkpoint_metadata = None  # type: ignore[assignment]
    predict_mlp_probabilities = None  # type: ignore[assignment]
else:
    MLP_IMPORT_ERROR = None

try:
    from trainer.yolo_trainer import BEST_WEIGHTS_PATH, load_yolo_detector
except Exception as exc:  # pragma: no cover - environment dependent
    YOLO_IMPORT_ERROR = exc
    BEST_WEIGHTS_PATH = None  # type: ignore[assignment]
    load_yolo_detector = None  # type: ignore[assignment]
else:
    YOLO_IMPORT_ERROR = None


def _annotate_image(image_path: Path, detections: list[dict[str, float]], output_path: Path) -> Path:
    image = cv2.imread(str(image_path))
    if image is None:
        raise RuntimeError(f"Could not read {image_path}")
    height, width = image.shape[:2]
    for detection in detections:
        x_center = detection["x_center"] * width
        y_center = detection["y_center"] * height
        box_width = detection["width"] * width
        box_height = detection["height"] * height
        x1 = int(round(x_center - box_width / 2))
        y1 = int(round(y_center - box_height / 2))
        x2 = int(round(x_center + box_width / 2))
        y2 = int(round(y_center + box_height / 2))
        cv2.rectangle(image, (x1, y1), (x2, y2), (0, 180, 255), 2)
        cv2.putText(
            image,
            detection["class_name"],
            (x1, max(24, y1 - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 180, 255),
            2,
            lineType=cv2.LINE_AA,
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), image)
    return output_path


def select_setup_type(setup_scores: dict[str, float], phase1_config) -> tuple[str, list[str]]:
    if not setup_scores:
        return "model_unavailable", []
    ordered = sorted(setup_scores.items(), key=lambda item: item[1], reverse=True)
    best_label, best_score = ordered[0]
    second_score = ordered[1][1] if len(ordered) > 1 else 0.0
    margin = best_score - second_score
    warnings: list[str] = []
    if best_score < phase1_config.serving_min_confidence:
        warnings.append(
            f"Top setup probability {best_score:.3f} is below serving confidence threshold {phase1_config.serving_min_confidence:.3f}."
        )
        return phase1_config.uncertain_label, warnings
    if margin < phase1_config.serving_min_margin:
        warnings.append(
            f"Top-vs-second setup margin {margin:.3f} is below serving margin threshold {phase1_config.serving_min_margin:.3f}."
        )
        return phase1_config.uncertain_label, warnings
    return best_label, warnings


def select_chart_state_labels(chart_state_scores: dict[str, dict[str, float]]) -> dict[str, str]:
    selected: dict[str, str] = {}
    for head_name, scores in chart_state_scores.items():
        if not scores:
            selected[head_name] = "model_unavailable"
            continue
        selected[head_name] = max(scores.items(), key=lambda item: item[1])[0]
    return selected


def _resolve_chart_embedding(image_path: Path, corpus, config) -> np.ndarray:
    existing_example = find_example_by_image(corpus.examples, image_path)
    if existing_example is not None:
        return existing_example.embedding
    return embed_chart_image(image_path, config)


def _predict_markups_for_image(image_path: Path, config, warnings: list[str]) -> list[dict[str, float]]:
    markups: list[dict[str, float]] = []
    if BEST_WEIGHTS_PATH is None or load_yolo_detector is None:
        warnings.append(f"YOLO runtime unavailable: {YOLO_IMPORT_ERROR}")
        return markups
    yolo_weights_path = config.root_dir / BEST_WEIGHTS_PATH
    if not yolo_weights_path.exists():
        warnings.append(f"Missing YOLO weights: {yolo_weights_path}")
        return markups

    try:
        detector = load_yolo_detector(yolo_weights_path)
        prediction = detector.predict(source=str(image_path), imgsz=config.phase3.imgsz, verbose=False)[0]
    except Exception as exc:
        warnings.append(f"YOLO runtime unavailable: {exc}")
        return markups
    if prediction.boxes is None:
        return markups
    for box in prediction.boxes:
        xywhn = box.xywhn[0].tolist()
        class_id = int(box.cls[0].item())
        markups.append(
            {
                "class_id": class_id,
                "class_name": YOLO_CLASS_NAMES[class_id],
                "confidence": float(box.conf[0].item()) if box.conf is not None else 0.0,
                "x_center": float(xywhn[0]),
                "y_center": float(xywhn[1]),
                "width": float(xywhn[2]),
                "height": float(xywhn[3]),
            }
        )
    return markups


def predict_chart(image_path: Path) -> dict[str, object]:
    config = build_config()
    corpus = load_chart_corpus(config)
    warnings: list[str] = []
    embedding = _resolve_chart_embedding(image_path, corpus, config)

    mlp_checkpoint_path = config.root_dir / "models" / "mlp_ttrades_best.pth"
    if mlp_checkpoint_path.exists() and load_mlp_checkpoint is not None:
        try:
            mlp_model, _label_to_index, device = load_mlp_checkpoint(mlp_checkpoint_path)
            checkpoint_metadata = load_mlp_checkpoint_metadata(mlp_checkpoint_path)
            warnings.extend(build_checkpoint_context_warnings(checkpoint_metadata, config))
            setup_scores = predict_mlp_probabilities(mlp_model, embedding.astype(np.float32), device=device)
            setup_type, setup_warnings = select_setup_type(setup_scores, config.phase1)
            warnings.extend(setup_warnings)
        except Exception as exc:
            setup_scores = {}
            setup_type = "model_unavailable"
            warnings.append(f"MLP runtime unavailable: {exc}")
    else:
        setup_scores = {}
        setup_type = "model_unavailable"
        if not mlp_checkpoint_path.exists():
            warnings.append(f"Missing MLP checkpoint: {mlp_checkpoint_path}")
        else:
            warnings.append(f"MLP runtime unavailable: {MLP_IMPORT_ERROR}")

    markups = _predict_markups_for_image(image_path, config, warnings)

    annotated_path = _annotate_image(
        image_path,
        markups,
        config.paths.predict_output_dir / f"{image_path.stem}_annotated{image_path.suffix}",
    )
    return {
        "image_path": str(image_path.resolve()),
        "setup_type": setup_type,
        "setup_scores": setup_scores,
        "markups": markups,
        "annotated_image_path": str(annotated_path.resolve()),
        "warnings": warnings,
    }


def predict_bundle(htf_image_path: Path, itf_image_path: Path, ltf_image_path: Path) -> dict[str, object]:
    config = build_config()
    corpus = load_chart_corpus(config)
    warnings: list[str] = []
    frame_paths = {
        "htf": htf_image_path.resolve(),
        "itf": itf_image_path.resolve(),
        "ltf": ltf_image_path.resolve(),
    }
    embeddings = {
        frame_name: _resolve_chart_embedding(frame_path, corpus, config).astype(np.float32)
        for frame_name, frame_path in frame_paths.items()
    }
    bundle_features = np.concatenate(
        [embeddings["htf"], embeddings["itf"], embeddings["ltf"]],
        axis=0,
    )

    chart_state_checkpoint_path = config.paths.chart_state_checkpoint_path
    if chart_state_checkpoint_path.exists() and load_chart_state_checkpoint is not None and predict_chart_state_probabilities is not None:
        try:
            chart_state_model, label_spaces, chart_state_device = load_chart_state_checkpoint(chart_state_checkpoint_path)
            chart_state_scores = predict_chart_state_probabilities(
                chart_state_model,
                bundle_features,
                label_spaces=label_spaces,
                device=chart_state_device,
            )
            chart_state = select_chart_state_labels(chart_state_scores)
        except Exception as exc:
            chart_state_scores = {}
            chart_state = {}
            warnings.append(f"Chart-state runtime unavailable: {exc}")
    else:
        chart_state_scores = {}
        chart_state = {}
        if not chart_state_checkpoint_path.exists():
            warnings.append(f"Missing chart-state checkpoint: {chart_state_checkpoint_path}")
        else:
            warnings.append(f"Chart-state runtime unavailable: {CHART_STATE_IMPORT_ERROR}")

    detector_markups_by_frame: dict[str, list[dict[str, float]]] = {}
    annotated_paths: dict[str, str] = {}
    for frame_name, frame_path in frame_paths.items():
        markups = _predict_markups_for_image(frame_path, config, warnings)
        detector_markups_by_frame[frame_name] = markups
        annotated_path = _annotate_image(
            frame_path,
            markups,
            config.paths.predict_output_dir / f"{frame_path.stem}_{frame_name}_annotated{frame_path.suffix}",
        )
        annotated_paths[frame_name] = str(annotated_path.resolve())

    return {
        "bundle_paths": {frame_name: str(path) for frame_name, path in frame_paths.items()},
        "chart_state": chart_state,
        "chart_state_scores": chart_state_scores,
        "detector_markups_by_frame": detector_markups_by_frame,
        "annotated_image_paths": annotated_paths,
        "warnings": warnings,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run joint MLP + YOLO prediction for a single chart image.")
    parser.add_argument("--image", type=Path, default=None)
    parser.add_argument("--bundle-htf", type=Path, default=None)
    parser.add_argument("--bundle-itf", type=Path, default=None)
    parser.add_argument("--bundle-ltf", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> dict[str, object]:
    args = build_arg_parser().parse_args(argv)
    bundle_args = [args.bundle_htf, args.bundle_itf, args.bundle_ltf]
    if all(bundle_args):
        result = predict_bundle(
            args.bundle_htf.resolve(),
            args.bundle_itf.resolve(),
            args.bundle_ltf.resolve(),
        )
    elif args.image is not None:
        result = predict_chart(args.image.resolve())
    else:
        raise SystemExit("Provide --image for single-chart prediction or --bundle-htf/--bundle-itf/--bundle-ltf for bundle prediction.")
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    main()
