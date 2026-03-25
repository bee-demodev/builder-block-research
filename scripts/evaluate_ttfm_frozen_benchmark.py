from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import train_ttfm_video_multimodal_pattern_net as tmvpn
import train_ttfm_visual_pattern_net as tvpn
import ttfm_brain_embeddings as tbe
import ttfm_video_embeddings as tve


DEFAULT_TEACHER_DATASET_PATH = ROOT / "results" / "ttfm_teacher_augmented_visual_dataset.jsonl"
DEFAULT_WEAK_DATASET_PATH = ROOT / "results" / "ttfm_video_multimodal_dataset.jsonl"
DEFAULT_REVIEW_QUEUE_PATH = ROOT / "results" / "ttfm_multimodal_review_queue.json"
DEFAULT_BENCHMARK_OUTPUT = ROOT / "results" / "ttfm_frozen_benchmark_pack.jsonl"
DEFAULT_REPORT_OUTPUT = ROOT / "results" / "ttfm_frozen_benchmark_report.json"
PROMOTABLE_REVIEW_STATUSES = {
    "approved_for_teacher",
    "teacher_approved",
    "promoted_to_teacher",
}


def load_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return dict(default or {})
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return tmvpn.load_multimodal_rows(path)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row) for row in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )


def normalize_string_list(values: object) -> list[str]:
    if values is None:
        return []
    if isinstance(values, list):
        return [str(value).strip() for value in values if str(value).strip()]
    if isinstance(values, str):
        cleaned = values.strip()
        return [cleaned] if cleaned else []
    return []


def benchmark_row_is_valid(row: dict[str, Any]) -> bool:
    example_id = str(row.get("example_id", "")).strip()
    if not example_id:
        return False
    if not normalize_string_list(row.get("active_labels")):
        return False
    return bool(str(row.get("screenshot_path", "")).strip())


def reviewed_disagreement_example_ids(review_queue: dict[str, Any]) -> list[str]:
    example_ids: list[str] = []
    for item in review_queue.get("items", []):
        example_id = str(item.get("example_id", "")).strip()
        if not example_id:
            continue
        review_status = str(item.get("review_status", "")).strip()
        disagreement_count = int(item.get("disagreement_count", 0) or 0)
        if review_status not in PROMOTABLE_REVIEW_STATUSES:
            continue
        if disagreement_count <= 0:
            continue
        example_ids.append(example_id)
    return example_ids


def build_frozen_benchmark_rows(
    *,
    teacher_rows: list[dict[str, Any]],
    weak_rows: list[dict[str, Any]],
    review_queue: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_example_ids: set[str] = set()
    weak_lookup = {
        str(row.get("example_id", "")).strip(): row
        for row in weak_rows
        if str(row.get("example_id", "")).strip()
    }

    for teacher_row in teacher_rows:
        if not benchmark_row_is_valid(teacher_row):
            continue
        example_id = str(teacher_row.get("example_id", "")).strip()
        if example_id in seen_example_ids:
            continue
        seen_example_ids.add(example_id)
        row = dict(teacher_row)
        row["benchmark_source"] = "teacher"
        rows.append(row)

    for example_id in reviewed_disagreement_example_ids(review_queue):
        if example_id in seen_example_ids:
            continue
        weak_row = weak_lookup.get(example_id)
        if weak_row is None or not benchmark_row_is_valid(weak_row):
            continue
        seen_example_ids.add(example_id)
        row = dict(weak_row)
        row["benchmark_source"] = "reviewed_disagreement"
        rows.append(row)

    return rows


def summarize_benchmark_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    source_counts: Counter[str] = Counter()
    for row in rows:
        source_counts[str(row.get("benchmark_source", "unknown")).strip() or "unknown"] += 1
    return {
        "row_count": len(rows),
        "benchmark_source_counts": dict(sorted(source_counts.items())),
    }


def ensure_frozen_benchmark_pack(
    *,
    benchmark_output: Path,
    teacher_rows: list[dict[str, Any]],
    weak_rows: list[dict[str, Any]],
    review_queue: dict[str, Any],
    force_rebuild: bool = False,
) -> dict[str, Any]:
    if benchmark_output.exists() and not force_rebuild:
        existing_rows = load_jsonl(benchmark_output)
        return {
            "status": "cache_hit",
            "benchmark_output": str(benchmark_output),
            **summarize_benchmark_rows(existing_rows),
        }

    rows = build_frozen_benchmark_rows(
        teacher_rows=teacher_rows,
        weak_rows=weak_rows,
        review_queue=review_queue,
    )
    write_jsonl(benchmark_output, rows)
    return {
        "status": "ran",
        "benchmark_output": str(benchmark_output),
        **summarize_benchmark_rows(rows),
    }


def prediction_thresholds_for_artifact(artifact: dict[str, Any], label_to_index: dict[str, int]) -> list[float]:
    thresholds_by_label = artifact.get("prediction_thresholds")
    if isinstance(thresholds_by_label, dict) and thresholds_by_label:
        ordered = sorted(label_to_index.items(), key=lambda item: item[1])
        return [float(thresholds_by_label.get(label_name, 0.5)) for label_name, _index in ordered]
    return [float(artifact.get("prediction_threshold", 0.5) or 0.5)] * len(label_to_index)


def compare_benchmark_metrics(
    *,
    champion: dict[str, Any] | None,
    challenger: dict[str, Any] | None,
) -> dict[str, Any]:
    metric_keys = (
        "micro_f1",
        "precision",
        "recall",
        "exact_match_ratio",
        "disagreement_count",
    )
    champion = dict(champion or {})
    challenger = dict(challenger or {})
    delta: dict[str, float | int | None] = {}
    for key in metric_keys:
        champion_value = champion.get(key)
        challenger_value = challenger.get(key)
        if champion_value is None or challenger_value is None:
            delta[key] = None
            continue
        if key == "disagreement_count":
            delta[key] = int(challenger_value) - int(champion_value)
        else:
            delta[key] = float(challenger_value) - float(champion_value)

    winner = "unknown"
    if challenger and not champion:
        winner = "challenger"
    elif champion and challenger:
        champion_f1 = float(champion.get("micro_f1", 0.0) or 0.0)
        challenger_f1 = float(challenger.get("micro_f1", 0.0) or 0.0)
        if challenger_f1 > champion_f1:
            winner = "challenger"
        elif challenger_f1 < champion_f1:
            winner = "champion"
        else:
            champion_disagreements = int(champion.get("disagreement_count", 0) or 0)
            challenger_disagreements = int(challenger.get("disagreement_count", 0) or 0)
            if challenger_disagreements < champion_disagreements:
                winner = "challenger"
            elif challenger_disagreements > champion_disagreements:
                winner = "champion"
            else:
                winner = "tie"
    return {
        "winner": winner,
        "champion": champion,
        "challenger": challenger,
        "delta": delta,
    }


def evaluate_model_against_benchmark(
    *,
    model_path: Path,
    benchmark_rows: list[dict[str, Any]],
    device_preference: str = "auto",
) -> dict[str, Any]:
    tmvpn.require_torch()
    if not model_path.exists():
        return {"status": "skipped", "reason": "missing_model", "model_path": str(model_path)}
    if not benchmark_rows:
        return {"status": "skipped", "reason": "empty_benchmark", "model_path": str(model_path)}

    artifact = tmvpn.torch.load(model_path, map_location="cpu")
    label_to_index = {
        str(label_name): int(index)
        for label_name, index in dict(artifact.get("label_to_index", {})).items()
    }
    if not label_to_index:
        return {"status": "skipped", "reason": "empty_label_space", "model_path": str(model_path)}

    examples, skipped_examples, embedding_prep = tmvpn.build_examples(
        benchmark_rows,
        label_to_index=label_to_index,
        output_dimensionality=int(artifact.get("embedding_dim", tve.DEFAULT_OUTPUT_DIMENSIONALITY)),
        text_embedding_model=str(artifact.get("text_embedding_model", tve.DEFAULT_MODEL)),
        visual_embedding_model=str(artifact.get("visual_embedding_model", tve.DEFAULT_MULTIMODAL_MODEL)),
        audio_understanding_model=str(
            artifact.get("audio_semantic_mode", tbe.DEFAULT_AUDIO_UNDERSTANDING_MODEL)
        ),
    )
    if not examples:
        return {
            "status": "skipped",
            "reason": "no_scored_examples",
            "model_path": str(model_path),
            "skipped_example_count": len(skipped_examples),
            "embedding_prep": embedding_prep,
        }

    device = tvpn.select_device(device_preference)
    model = tmvpn.MultimodalPatternNet(
        output_dim=len(label_to_index),
        embedding_dim=int(artifact.get("embedding_dim", tve.DEFAULT_OUTPUT_DIMENSIONALITY)),
    ).to(device)
    model.load_state_dict(artifact["state_dict"])
    model.eval()

    (
        visual_embeddings,
        transcript_embeddings,
        audio_embeddings,
        modality_features,
        labels,
        _weights,
    ) = tmvpn.build_tensors(examples, device=device)

    with tmvpn.torch.no_grad():
        logits, _calibration_logits = model(
            visual_embeddings,
            transcript_embeddings,
            audio_embeddings,
            modality_features,
        )

    thresholds = prediction_thresholds_for_artifact(artifact, label_to_index)
    metrics = tvpn.compute_multilabel_metrics(
        logits=logits,
        labels=labels,
        loss_value=None,
        threshold=thresholds,
    )
    threshold_tensor, _is_scalar = tvpn.threshold_to_tensor(
        thresholds,
        label_count=int(logits.shape[1]),
        device=logits.device,
        dtype=logits.dtype,
    )
    probabilities = tmvpn.torch.sigmoid(logits)
    predictions = (probabilities >= threshold_tensor.view(1, -1)).to(dtype=tmvpn.torch.int64)
    truth = labels.to(dtype=tmvpn.torch.int64)
    disagreement_count = int((predictions != truth).any(dim=1).sum().item())

    return {
        "status": "ran",
        "model_path": str(model_path),
        "benchmark_row_count": len(benchmark_rows),
        "scored_example_count": len(examples),
        "skipped_example_count": len(skipped_examples),
        "micro_f1": float(metrics.get("micro_f1", 0.0) or 0.0),
        "precision": float(metrics.get("micro_precision", 0.0) or 0.0),
        "recall": float(metrics.get("micro_recall", 0.0) or 0.0),
        "exact_match_ratio": float(metrics.get("exact_match_ratio", 0.0) or 0.0),
        "disagreement_count": disagreement_count,
        "prediction_threshold_mode": str(artifact.get("prediction_threshold_mode", "global")),
        "embedding_prep": embedding_prep,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build or reuse a frozen TTFM benchmark pack and optionally score a multimodal model against it."
        )
    )
    parser.add_argument("--teacher-dataset", type=Path, default=DEFAULT_TEACHER_DATASET_PATH)
    parser.add_argument("--weak-dataset", type=Path, default=DEFAULT_WEAK_DATASET_PATH)
    parser.add_argument("--review-queue", type=Path, default=DEFAULT_REVIEW_QUEUE_PATH)
    parser.add_argument("--benchmark-output", type=Path, default=DEFAULT_BENCHMARK_OUTPUT)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT_OUTPUT)
    parser.add_argument("--model-path", type=Path, default=None)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--force-rebuild", action="store_true")
    args = parser.parse_args()

    teacher_rows = load_jsonl(args.teacher_dataset)
    weak_rows = load_jsonl(args.weak_dataset)
    review_queue = load_json(args.review_queue, {"items": []})

    benchmark_report = ensure_frozen_benchmark_pack(
        benchmark_output=args.benchmark_output,
        teacher_rows=teacher_rows,
        weak_rows=weak_rows,
        review_queue=review_queue,
        force_rebuild=args.force_rebuild,
    )
    benchmark_rows = load_jsonl(args.benchmark_output)
    evaluation = (
        evaluate_model_against_benchmark(
            model_path=args.model_path,
            benchmark_rows=benchmark_rows,
            device_preference=args.device,
        )
        if args.model_path
        else {"status": "skipped", "reason": "no_model_requested"}
    )
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "benchmark": benchmark_report,
        "evaluation": evaluation,
    }
    write_json(args.report_output, report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
