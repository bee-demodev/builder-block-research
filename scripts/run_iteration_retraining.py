from __future__ import annotations

import argparse
import json
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from export_model_training_surface import summarize_training_surface
from phase_one_focus import (
    PHASE_ONE_BOOTSTRAP_POSITIVE_MINIMUMS,
    build_phase_one_focus,
)
from train_narrow_pattern_net import (
    DEFAULT_DATASET_PATH,
    load_surface_examples,
    prepare_task_examples,
    train_task_classifier,
)


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REINFORCED_DATASET_PATH = ROOT / "results" / "reinforced_model_training_surface.jsonl"
DEFAULT_OUTPUT_DIR = ROOT / "results" / "neural_models" / "iteration_retrained"
DEFAULT_REPORT_OUTPUT = ROOT / "results" / "iteration_retraining_report.json"


def build_source_holdout_task_summaries(
    trained_task_reports: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for report in trained_task_reports:
        evaluation = report.get("source_holdout_evaluation") or {}
        positive_metrics = evaluation.get("positive_group_macro_metrics") or {}
        negative_metrics = evaluation.get("negative_only_group_macro_metrics") or {}
        micro_metrics = evaluation.get("micro_metrics") or {}
        summaries.append(
            {
                "task_name": str(report["task_name"]),
                "group_field": evaluation.get("group_field"),
                "group_count": evaluation.get("group_count"),
                "evaluated_group_count": evaluation.get("evaluated_group_count"),
                "skipped_group_count": evaluation.get("skipped_group_count"),
                "evaluated_positive_group_count": evaluation.get(
                    "evaluated_positive_group_count"
                ),
                "evaluated_negative_only_group_count": evaluation.get(
                    "evaluated_negative_only_group_count"
                ),
                "micro_f1": micro_metrics.get("f1"),
                "micro_recall": micro_metrics.get("recall"),
                "positive_group_macro_f1": positive_metrics.get("f1"),
                "positive_group_macro_recall": positive_metrics.get("recall"),
                "negative_only_group_mean_specificity": negative_metrics.get("specificity"),
                "negative_only_group_mean_false_positive_rate": negative_metrics.get(
                    "false_positive_rate"
                ),
            }
        )
    return summaries


def remove_path_if_exists(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
    elif path.exists():
        path.unlink()


def build_phase_one_bootstrap_tasks(training_surface: dict[str, Any]) -> list[dict[str, Any]]:
    bootstrap_tasks: list[dict[str, Any]] = []
    for task in training_surface.get("trade_model_binary_tasks", []):
        if not isinstance(task, dict):
            continue
        trade_model = str(task.get("trade_model", "")).strip()
        bootstrap_positive_examples = PHASE_ONE_BOOTSTRAP_POSITIVE_MINIMUMS.get(trade_model)
        if not bootstrap_positive_examples or task.get("ready"):
            continue
        positive_examples = int(task.get("positive_examples", 0) or 0)
        negative_examples = int(task.get("negative_examples", 0) or 0)
        recommended_negative_examples = int(
            task.get("recommended_negative_examples", 0) or 0
        )
        if (
            positive_examples >= bootstrap_positive_examples
            and negative_examples >= recommended_negative_examples
        ):
            bootstrap_tasks.append(
                {
                    **task,
                    "bootstrap_positive_examples_required": bootstrap_positive_examples,
                }
            )
    return bootstrap_tasks


def build_retraining_plan(examples: list[dict[str, Any]]) -> dict[str, Any]:
    training_surface = summarize_training_surface(examples)
    task_names = [
        str(task["trade_model"])
        for task in training_surface.get("trade_model_binary_tasks", [])
        if task.get("ready")
    ]
    phase_one_bootstrap_tasks = build_phase_one_bootstrap_tasks(training_surface)
    task_names.extend(
        str(task["trade_model"])
        for task in phase_one_bootstrap_tasks
    )

    outcome_counts = training_surface.get("outcome_decision_counts", {})
    trade_count = int(outcome_counts.get("trade", 0))
    no_trade_count = int(outcome_counts.get("no_trade", 0))
    trade_vs_no_trade_trainable = trade_count >= 2 and no_trade_count >= 2
    if trade_vs_no_trade_trainable:
        task_names.append("trade_vs_no_trade")

    deduped_task_names = list(dict.fromkeys(task_names))
    return {
        "task_names": deduped_task_names,
        "training_surface": training_surface,
        "trade_vs_no_trade_trainable": trade_vs_no_trade_trainable,
        "trade_vs_no_trade_counts": {
            "trade": trade_count,
            "no_trade": no_trade_count,
        },
        "phase_one_bootstrap_tasks": phase_one_bootstrap_tasks,
        "phase_one_focus": build_phase_one_focus(training_surface),
    }


def run_iteration_retraining_on_examples(
    *,
    examples: list[dict[str, Any]],
    output_dir: Path,
    train_fn: Callable[..., dict[str, Any]] = train_task_classifier,
    device_preference: str = "auto",
    validation_ratio: float = 0.25,
    validation_grouping: str = "source_group",
    epochs: int = 40,
    learning_rate: float = 0.02,
    hidden_dim: int = 32,
    seed: int = 42,
) -> dict[str, Any]:
    plan = build_retraining_plan(examples)
    trained_task_reports: list[dict[str, Any]] = []

    output_dir.mkdir(parents=True, exist_ok=True)
    for task_name in plan["task_names"]:
        prepared_task = prepare_task_examples(examples, task_name=task_name)
        trained_task_reports.append(
            train_fn(
                prepared_task,
                output_dir=output_dir,
                device_preference=device_preference,
                validation_ratio=validation_ratio,
                validation_grouping=validation_grouping,
                epochs=epochs,
                learning_rate=learning_rate,
                hidden_dim=hidden_dim,
                seed=seed,
            )
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "output_dir": str(output_dir),
        "dataset_example_count": len(examples),
        "trained_task_count": len(trained_task_reports),
        "trained_task_names": [report["task_name"] for report in trained_task_reports],
        "trained_tasks": trained_task_reports,
        "source_holdout_task_summaries": build_source_holdout_task_summaries(
            trained_task_reports
        ),
        "training_surface": plan["training_surface"],
        "trade_vs_no_trade_trainable": plan["trade_vs_no_trade_trainable"],
        "trade_vs_no_trade_counts": plan["trade_vs_no_trade_counts"],
        "validation_grouping_requested": validation_grouping,
        "phase_one_bootstrap_tasks": plan["phase_one_bootstrap_tasks"],
        "phase_one_focus": plan["phase_one_focus"],
    }


def export_iteration_retraining(
    *,
    dataset_path: Path,
    output_dir: Path,
    report_output: Path,
    device_preference: str = "auto",
    validation_ratio: float = 0.25,
    validation_grouping: str = "source_group",
    epochs: int = 40,
    learning_rate: float = 0.02,
    hidden_dim: int = 32,
    seed: int = 42,
) -> dict[str, Any]:
    examples = load_surface_examples(dataset_path)
    report = run_iteration_retraining_on_examples(
        examples=examples,
        output_dir=output_dir,
        device_preference=device_preference,
        validation_ratio=validation_ratio,
        validation_grouping=validation_grouping,
        epochs=epochs,
        learning_rate=learning_rate,
        hidden_dim=hidden_dim,
        seed=seed,
    )
    persisted_report = {
        **report,
        "dataset_path": str(dataset_path),
        "report_output": str(report_output),
    }
    report_output.parent.mkdir(parents=True, exist_ok=True)
    report_output.write_text(json.dumps(persisted_report, indent=2) + "\n", encoding="utf-8")
    return persisted_report


def export_iteration_retraining_with_retries(
    *,
    dataset_path: Path,
    output_dir: Path,
    report_output: Path,
    device_preference: str = "auto",
    validation_ratio: float = 0.25,
    validation_grouping: str = "source_group",
    epochs: int = 40,
    learning_rate: float = 0.02,
    hidden_dim: int = 32,
    seed: int = 42,
    max_attempts: int = 2,
    retry_delay_seconds: float = 0.0,
) -> dict[str, Any]:
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    attempt_history: list[dict[str, Any]] = []
    last_error: Exception | None = None

    for attempt_number in range(1, max_attempts + 1):
        attempt_started_at = datetime.now(timezone.utc).isoformat()
        try:
            report = export_iteration_retraining(
                dataset_path=dataset_path,
                output_dir=output_dir,
                report_output=report_output,
                device_preference=device_preference,
                validation_ratio=validation_ratio,
                validation_grouping=validation_grouping,
                epochs=epochs,
                learning_rate=learning_rate,
                hidden_dim=hidden_dim,
                seed=seed,
            )
        except Exception as exc:  # pragma: no cover - exercised through retry tests
            attempt_finished_at = datetime.now(timezone.utc).isoformat()
            last_error = exc
            attempt_history.append(
                {
                    "attempt_number": attempt_number,
                    "status": "failed",
                    "started_at": attempt_started_at,
                    "finished_at": attempt_finished_at,
                    "output_dir": str(output_dir),
                    "report_output": str(report_output),
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                }
            )
            if attempt_number < max_attempts:
                remove_path_if_exists(output_dir)
                remove_path_if_exists(report_output)
                if retry_delay_seconds > 0:
                    time.sleep(retry_delay_seconds)
            continue

        attempt_finished_at = datetime.now(timezone.utc).isoformat()
        attempt_history.append(
            {
                "attempt_number": attempt_number,
                "status": "succeeded",
                "started_at": attempt_started_at,
                "finished_at": attempt_finished_at,
                "output_dir": str(output_dir),
                "report_output": str(report_output),
            }
        )
        retry_summary = {
            "max_attempts": max_attempts,
            "attempt_count": len(attempt_history),
            "succeeded": True,
            "failed_attempt_count": sum(
                1 for attempt in attempt_history if attempt["status"] == "failed"
            ),
            "attempts": attempt_history,
        }
        final_report = {**report, "retry_summary": retry_summary}
        report_output.parent.mkdir(parents=True, exist_ok=True)
        report_output.write_text(json.dumps(final_report, indent=2) + "\n", encoding="utf-8")
        return final_report

    retry_summary = {
        "max_attempts": max_attempts,
        "attempt_count": len(attempt_history),
        "succeeded": False,
        "failed_attempt_count": len(attempt_history),
        "attempts": attempt_history,
        "last_error_type": type(last_error).__name__ if last_error else None,
        "last_error_message": str(last_error) if last_error else None,
    }
    failure_report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset_path": str(dataset_path),
        "output_dir": str(output_dir),
        "report_output": str(report_output),
        "retry_summary": retry_summary,
    }
    report_output.parent.mkdir(parents=True, exist_ok=True)
    report_output.write_text(json.dumps(failure_report, indent=2) + "\n", encoding="utf-8")
    if last_error is None:
        raise RuntimeError("Iteration retraining failed without capturing an exception")
    raise last_error


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Retrain ready narrow TTrades classifiers on the reinforced training surface "
            "without overwriting the current champion models."
        )
    )
    parser.add_argument("--dataset-path", default=str(DEFAULT_REINFORCED_DATASET_PATH))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--report-output", default=str(DEFAULT_REPORT_OUTPUT))
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda", "mps"])
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--learning-rate", type=float, default=0.02)
    parser.add_argument("--hidden-dim", type=int, default=32)
    parser.add_argument("--validation-ratio", type=float, default=0.25)
    parser.add_argument("--max-attempts", type=int, default=2)
    parser.add_argument("--retry-delay-seconds", type=float, default=0.0)
    parser.add_argument(
        "--validation-grouping",
        default="source_group",
        choices=["split_group", "source_group"],
    )
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    report = export_iteration_retraining_with_retries(
        dataset_path=Path(args.dataset_path),
        output_dir=Path(args.output_dir),
        report_output=Path(args.report_output),
        device_preference=args.device,
        validation_ratio=args.validation_ratio,
        validation_grouping=args.validation_grouping,
        epochs=args.epochs,
        learning_rate=args.learning_rate,
        hidden_dim=args.hidden_dim,
        seed=args.seed,
        max_attempts=args.max_attempts,
        retry_delay_seconds=args.retry_delay_seconds,
    )
    print(
        json.dumps(
            {
                "dataset_path": report["dataset_path"],
                "output_dir": report["output_dir"],
                "trained_task_count": report["trained_task_count"],
                "trained_task_names": report["trained_task_names"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
