from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import torch

from score_pattern_state import load_model_bundle
from train_narrow_pattern_net import (
    compute_binary_metrics,
    load_surface_examples,
    prepare_task_examples,
    vectorize_text,
)


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATASET_PATH = ROOT / "results" / "reinforced_model_training_surface.jsonl"
DEFAULT_ITERATION_RETRAINING_REPORT_PATH = ROOT / "results" / "iteration_retraining_report.json"
DEFAULT_CHAMPION_MODEL_DIR = ROOT / "results" / "neural_models"
DEFAULT_CHALLENGER_MODEL_DIR = ROOT / "results" / "neural_models" / "iteration_retrained"
DEFAULT_OUTPUT = ROOT / "results" / "iteration_challenger_report.json"
METRIC_KEYS = ("accuracy", "precision", "recall", "f1")


def load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def is_reinforcement_example(example: dict[str, Any]) -> bool:
    return str(example.get("example_id", "")).startswith("iteration::")


def score_model_on_examples(
    examples: list[dict[str, Any]],
    model_path: Path,
    *,
    device_preference: str = "auto",
    threshold: float = 0.5,
) -> dict[str, Any]:
    bundle = load_model_bundle(model_path, device_preference=device_preference)
    vocabulary = bundle["vocabulary"]
    features = torch.tensor(
        [vectorize_text(str(example["text"]), vocabulary) for example in examples],
        dtype=torch.float32,
        device=bundle["device"],
    )
    labels = torch.tensor(
        [float(example["label"]) for example in examples],
        dtype=torch.float32,
        device=bundle["device"],
    )

    with torch.no_grad():
        logits = bundle["model"](features)
        metrics = compute_binary_metrics(logits=logits, labels=labels, loss_value=None)
        probabilities = torch.sigmoid(logits).detach().cpu().tolist()

    return {
        "task_name": bundle["task_name"],
        "device": bundle["device"],
        "model_path": str(model_path),
        "example_count": len(examples),
        "threshold": threshold,
        "average_probability": (
            sum(float(value) for value in probabilities) / len(probabilities)
            if probabilities
            else 0.0
        ),
        "metrics": metrics,
    }


def build_metric_delta(
    champion_metrics: dict[str, Any],
    challenger_metrics: dict[str, Any],
) -> dict[str, float]:
    return {
        key: round(float(challenger_metrics.get(key, 0.0)) - float(champion_metrics.get(key, 0.0)), 6)
        for key in METRIC_KEYS
    }


def choose_winner(
    champion_metrics: dict[str, Any],
    challenger_metrics: dict[str, Any],
) -> str:
    challenger_f1 = float(challenger_metrics.get("f1", 0.0))
    champion_f1 = float(champion_metrics.get("f1", 0.0))
    if challenger_f1 > champion_f1:
        return "challenger"
    if champion_f1 > challenger_f1:
        return "champion"

    challenger_accuracy = float(challenger_metrics.get("accuracy", 0.0))
    champion_accuracy = float(champion_metrics.get("accuracy", 0.0))
    if challenger_accuracy > champion_accuracy:
        return "challenger"
    if champion_accuracy > challenger_accuracy:
        return "champion"
    return "tie"


def build_comparison_block(
    *,
    champion_result: dict[str, Any],
    challenger_result: dict[str, Any],
) -> dict[str, Any]:
    champion_metrics = champion_result.get("metrics", {})
    challenger_metrics = challenger_result.get("metrics", {})
    winner = choose_winner(champion_metrics, challenger_metrics)
    return {
        "winner": winner,
        "champion": champion_result,
        "challenger": challenger_result,
        "metric_delta": build_metric_delta(champion_metrics, challenger_metrics),
    }


def build_recommendation(*, status: str, winner: str | None) -> str:
    if status == "missing_challenger_model":
        return "inspect_retraining_output"
    if status == "missing_champion_model":
        return "initialize_champion_review"
    if status == "untrainable_dataset":
        return "collect_more_examples"
    if winner == "challenger":
        return "promote_after_review"
    if winner == "champion":
        return "keep_champion"
    return "collect_more_examples"


def build_task_report(
    *,
    task_name: str,
    examples: list[dict[str, Any]],
    champion_model_dir: Path,
    challenger_model_dir: Path,
    score_fn: Callable[..., dict[str, Any]] = score_model_on_examples,
    device_preference: str = "auto",
    threshold: float = 0.5,
) -> dict[str, Any]:
    champion_model_path = champion_model_dir / f"{task_name}.pt"
    challenger_model_path = challenger_model_dir / f"{task_name}.pt"
    champion_training_report = load_json(
        champion_model_dir / f"{task_name}_report.json",
        {},
    )
    challenger_training_report = load_json(
        challenger_model_dir / f"{task_name}_report.json",
        {},
    )

    try:
        prepared_task = prepare_task_examples(examples, task_name=task_name)
    except ValueError as exc:
        return {
            "task_name": task_name,
            "status": "untrainable_dataset",
            "winner": None,
            "recommendation": build_recommendation(status="untrainable_dataset", winner=None),
            "shared_example_count": 0,
            "reinforcement_example_count": 0,
            "positive_label": None,
            "negative_label": None,
            "error": str(exc),
            "champion_model_path": str(champion_model_path),
            "challenger_model_path": str(challenger_model_path),
            "champion_training_report": champion_training_report,
            "challenger_training_report": challenger_training_report,
        }

    full_examples = list(prepared_task["examples"])
    reinforcement_examples = [
        example for example in full_examples if is_reinforcement_example(example)
    ]

    report = {
        "task_name": task_name,
        "status": "pending",
        "winner": None,
        "recommendation": None,
        "shared_example_count": len(full_examples),
        "reinforcement_example_count": len(reinforcement_examples),
        "positive_label": prepared_task.get("positive_label"),
        "negative_label": prepared_task.get("negative_label"),
        "skipped_example_count": len(prepared_task.get("skipped_example_ids", [])),
        "champion_model_path": str(champion_model_path),
        "challenger_model_path": str(challenger_model_path),
        "champion_training_report": champion_training_report,
        "challenger_training_report": challenger_training_report,
    }

    if not challenger_model_path.exists():
        report["status"] = "missing_challenger_model"
        report["recommendation"] = build_recommendation(
            status=report["status"],
            winner=None,
        )
        return report

    if not champion_model_path.exists():
        report["status"] = "missing_champion_model"
        report["recommendation"] = build_recommendation(
            status=report["status"],
            winner=None,
        )
        return report

    champion_full = score_fn(
        full_examples,
        champion_model_path,
        device_preference=device_preference,
        threshold=threshold,
    )
    challenger_full = score_fn(
        full_examples,
        challenger_model_path,
        device_preference=device_preference,
        threshold=threshold,
    )
    full_surface = build_comparison_block(
        champion_result=champion_full,
        challenger_result=challenger_full,
    )

    reinforcement_only = None
    if reinforcement_examples:
        champion_reinforcement = score_fn(
            reinforcement_examples,
            champion_model_path,
            device_preference=device_preference,
            threshold=threshold,
        )
        challenger_reinforcement = score_fn(
            reinforcement_examples,
            challenger_model_path,
            device_preference=device_preference,
            threshold=threshold,
        )
        reinforcement_only = build_comparison_block(
            champion_result=champion_reinforcement,
            challenger_result=challenger_reinforcement,
        )

    winner = full_surface["winner"]
    report.update(
        {
            "status": "compared",
            "winner": winner,
            "recommendation": build_recommendation(status="compared", winner=winner),
            "full_surface": full_surface,
            "reinforcement_only": reinforcement_only,
        }
    )
    return report


def summarize_task_reports(task_reports: list[dict[str, Any]]) -> dict[str, Any]:
    compared_reports = [report for report in task_reports if report.get("status") == "compared"]
    challenger_wins = [report for report in compared_reports if report.get("winner") == "challenger"]
    champion_wins = [report for report in compared_reports if report.get("winner") == "champion"]
    ties = [report for report in compared_reports if report.get("winner") == "tie"]

    return {
        "trained_task_count": len(task_reports),
        "compared_task_count": len(compared_reports),
        "challenger_win_count": len(challenger_wins),
        "champion_win_count": len(champion_wins),
        "tie_task_count": len(ties),
        "missing_champion_count": sum(
            1 for report in task_reports if report.get("status") == "missing_champion_model"
        ),
        "missing_challenger_count": sum(
            1 for report in task_reports if report.get("status") == "missing_challenger_model"
        ),
        "untrainable_task_count": sum(
            1 for report in task_reports if report.get("status") == "untrainable_dataset"
        ),
        "promotion_candidate_count": sum(
            1 for report in task_reports if report.get("recommendation") == "promote_after_review"
        ),
        "promotion_candidate_tasks": [
            report["task_name"]
            for report in task_reports
            if report.get("recommendation") == "promote_after_review"
        ],
    }


def build_iteration_challenger_report(
    *,
    examples: list[dict[str, Any]],
    iteration_retraining_report: dict[str, Any],
    champion_model_dir: Path,
    challenger_model_dir: Path,
    score_fn: Callable[..., dict[str, Any]] = score_model_on_examples,
    device_preference: str = "auto",
    threshold: float = 0.5,
) -> dict[str, Any]:
    task_reports = [
        build_task_report(
            task_name=str(task_name),
            examples=examples,
            champion_model_dir=champion_model_dir,
            challenger_model_dir=challenger_model_dir,
            score_fn=score_fn,
            device_preference=device_preference,
            threshold=threshold,
        )
        for task_name in iteration_retraining_report.get("trained_task_names", [])
    ]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "protocol": {
            "dataset_scope": "current_reinforced_training_surface",
            "note": (
                "This benchmark scores both champion and challenger models on the same "
                "reinforced surface. It is useful for loop comparison, but it is not a "
                "held-out generalization estimate."
            ),
            "threshold": threshold,
        },
        "summary": summarize_task_reports(task_reports),
        "task_reports": task_reports,
    }


def export_iteration_challenger_report(
    *,
    dataset_path: Path,
    iteration_retraining_report_path: Path,
    champion_model_dir: Path,
    challenger_model_dir: Path,
    output_path: Path,
    device_preference: str = "auto",
    threshold: float = 0.5,
) -> dict[str, Any]:
    report = build_iteration_challenger_report(
        examples=load_surface_examples(dataset_path),
        iteration_retraining_report=load_json(iteration_retraining_report_path, {}),
        champion_model_dir=champion_model_dir,
        challenger_model_dir=challenger_model_dir,
        device_preference=device_preference,
        threshold=threshold,
    )
    persisted_report = {
        **report,
        "dataset_path": str(dataset_path),
        "iteration_retraining_report_path": str(iteration_retraining_report_path),
        "champion_model_dir": str(champion_model_dir),
        "challenger_model_dir": str(challenger_model_dir),
        "output_path": str(output_path),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(persisted_report, indent=2) + "\n", encoding="utf-8")
    return persisted_report


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Compare the latest retrained narrow classifiers against the current champion "
            "models on the reinforced TTrades surface."
        )
    )
    parser.add_argument("--dataset-path", default=str(DEFAULT_DATASET_PATH))
    parser.add_argument(
        "--iteration-retraining-report",
        default=str(DEFAULT_ITERATION_RETRAINING_REPORT_PATH),
    )
    parser.add_argument("--champion-model-dir", default=str(DEFAULT_CHAMPION_MODEL_DIR))
    parser.add_argument("--challenger-model-dir", default=str(DEFAULT_CHALLENGER_MODEL_DIR))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda", "mps"])
    parser.add_argument("--threshold", type=float, default=0.5)
    args = parser.parse_args()

    report = export_iteration_challenger_report(
        dataset_path=Path(args.dataset_path),
        iteration_retraining_report_path=Path(args.iteration_retraining_report),
        champion_model_dir=Path(args.champion_model_dir),
        challenger_model_dir=Path(args.challenger_model_dir),
        output_path=Path(args.output),
        device_preference=args.device,
        threshold=args.threshold,
    )
    print(
        json.dumps(
            {
                "output_path": report["output_path"],
                "compared_task_count": report["summary"]["compared_task_count"],
                "challenger_win_count": report["summary"]["challenger_win_count"],
                "promotion_candidate_tasks": report["summary"]["promotion_candidate_tasks"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
