from __future__ import annotations

import argparse
import json
import random
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import torch
    from torch import nn
except ImportError as exc:  # pragma: no cover - exercised only in non-ML environments
    torch = None
    nn = None
    TORCH_IMPORT_ERROR = exc
else:
    TORCH_IMPORT_ERROR = None


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATASET_PATH = ROOT / "results" / "model_training_surface.jsonl"
DEFAULT_OUTPUT_DIR = ROOT / "results" / "neural_models"
TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
DEFAULT_VALIDATION_GROUPING = "source_group"
VALIDATION_GROUPING_CHOICES = ("split_group", "source_group")
DEFAULT_THRESHOLD_CANDIDATES = (
    0.2,
    0.25,
    0.3,
    0.35,
    0.4,
    0.45,
    0.5,
    0.55,
    0.6,
)


class TextMLP(nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int) -> None:
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1),
        )

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        return self.network(features).squeeze(-1)


def require_torch() -> None:
    if TORCH_IMPORT_ERROR is not None:
        raise RuntimeError("PyTorch is required for neural training.") from TORCH_IMPORT_ERROR


def load_surface_examples(dataset_path: Path) -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []
    with dataset_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            cleaned = line.strip()
            if cleaned:
                examples.append(json.loads(cleaned))
    return examples


def prepare_task_examples(
    raw_examples: list[dict[str, Any]],
    *,
    task_name: str,
) -> dict[str, Any]:
    prepared_examples: list[dict[str, Any]] = []
    skipped_example_ids: list[str] = []

    if task_name == "trade_vs_no_trade":
        positive_label = "trade"
        negative_label = "no_trade"
        for example in raw_examples:
            targets = example.get("targets", {})
            example_id = str(example["example_id"])
            if not targets.get("has_outcome_label"):
                skipped_example_ids.append(example_id)
                continue
            label = 1 if str(targets.get("outcome_decision")) == positive_label else 0
            prepared_examples.append(
                {
                    "example_id": example_id,
                    "text": str(example["training_text"]),
                    "label": label,
                    "case_ref": str(example.get("case_ref") or example_id),
                    "split_group": str(
                        example.get("split_group")
                        or example.get("case_ref")
                        or example_id
                    ),
                    "source_group": str(
                        example.get("source_group")
                        or example.get("split_group")
                        or example.get("source_url")
                        or example.get("case_ref")
                        or example_id
                    ),
                }
            )
    else:
        positive_label = task_name
        negative_label = "other_trade_models"
        for example in raw_examples:
            targets = example.get("targets", {})
            example_id = str(example["example_id"])
            if targets.get("outcome_segment_only"):
                skipped_example_ids.append(example_id)
                continue
            prepared_examples.append(
                {
                    "example_id": example_id,
                    "text": str(example["training_text"]),
                    "label": 1 if str(targets.get("trade_model")) == task_name else 0,
                    "case_ref": str(example.get("case_ref") or example_id),
                    "split_group": str(
                        example.get("split_group")
                        or example.get("case_ref")
                        or example_id
                    ),
                    "source_group": str(
                        example.get("source_group")
                        or example.get("split_group")
                        or example.get("source_url")
                        or example.get("case_ref")
                        or example_id
                    ),
                }
            )

    label_counts = Counter(item["label"] for item in prepared_examples)
    if label_counts.get(1, 0) == 0 or label_counts.get(0, 0) == 0:
        raise ValueError(
            f"Task {task_name!r} does not have both positive and negative examples."
        )

    return {
        "task_name": task_name,
        "positive_label": positive_label,
        "negative_label": negative_label,
        "examples": prepared_examples,
        "skipped_example_ids": skipped_example_ids,
    }


def select_device(device_preference: str) -> str:
    require_torch()
    normalized = device_preference.lower()
    if normalized == "auto":
        if torch.cuda.is_available():
            return "cuda"
        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            return "mps"
        return "cpu"

    if normalized == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested, but PyTorch does not see an available CUDA device.")
    if normalized == "mps" and not (
        getattr(torch.backends, "mps", None) and torch.backends.mps.is_available()
    ):
        raise RuntimeError("MPS was requested, but it is not available in this environment.")
    if normalized not in {"cpu", "cuda", "mps"}:
        raise ValueError(f"Unsupported device preference: {device_preference}")
    return normalized


def tokenize_text(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(text.lower().replace("_", " ").replace("-", " "))


def build_feature_tokens(text: str) -> list[str]:
    tokens = tokenize_text(text)
    if len(tokens) < 2:
        return tokens
    bigrams = [f"{left}__{right}" for left, right in zip(tokens, tokens[1:])]
    return tokens + bigrams


def build_vocabulary(examples: list[dict[str, Any]]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for example in examples:
        counter.update(build_feature_tokens(example["text"]))
    return {token: index for index, token in enumerate(sorted(counter))}


def vectorize_text(text: str, vocabulary: dict[str, int]) -> list[float]:
    vector = [0.0] * len(vocabulary)
    tokens = build_feature_tokens(text)
    if not tokens or not vocabulary:
        return vector
    for token in tokens:
        index = vocabulary.get(token)
        if index is not None:
            vector[index] += 1.0
    scale = float(len(tokens))
    return [value / scale for value in vector]


def resolve_group_key(example: dict[str, Any], group_field: str) -> str:
    value = example.get(group_field)
    if value:
        return str(value)
    return str(example.get("split_group") or example.get("case_ref") or example["example_id"])


def count_unique_groups_by_label(
    examples: list[dict[str, Any]],
    *,
    group_field: str,
) -> dict[int, int]:
    counts: dict[int, set[str]] = {0: set(), 1: set()}
    for example in examples:
        counts[int(example["label"])].add(resolve_group_key(example, group_field))
    return {label: len(groups) for label, groups in counts.items()}


def select_validation_grouping(
    examples: list[dict[str, Any]],
    *,
    requested_grouping: str,
) -> tuple[str, str | None]:
    if requested_grouping not in VALIDATION_GROUPING_CHOICES:
        raise ValueError(f"Unsupported validation grouping: {requested_grouping}")

    requested_counts = count_unique_groups_by_label(examples, group_field=requested_grouping)
    if min(requested_counts.values()) >= 2:
        return requested_grouping, None

    if requested_grouping != "split_group":
        fallback_grouping = "split_group"
        fallback_counts = count_unique_groups_by_label(examples, group_field=fallback_grouping)
        if min(fallback_counts.values()) >= 2:
            return (
                fallback_grouping,
                (
                    f"Fell back from {requested_grouping} to {fallback_grouping} because "
                    f"{requested_grouping} only had {requested_counts[0]} negative-label groups "
                    f"and {requested_counts[1]} positive-label groups."
                ),
            )

    return (
        requested_grouping,
        (
            f"Using {requested_grouping} even though it only has "
            f"{requested_counts[0]} negative-label groups and {requested_counts[1]} "
            "positive-label groups."
        ),
    )


def exact_group_holdout_split(
    examples: list[dict[str, Any]],
    *,
    held_out_group: str,
    group_field: str = "source_group",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    train_examples: list[dict[str, Any]] = []
    validation_examples: list[dict[str, Any]] = []

    for example in examples:
        example_group = resolve_group_key(example, group_field)
        if example_group == held_out_group:
            validation_examples.append(example)
        else:
            train_examples.append(example)

    return train_examples, validation_examples


def stratified_split(
    examples: list[dict[str, Any]],
    *,
    validation_ratio: float,
    seed: int,
    group_field: str = "split_group",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not 0.0 <= validation_ratio < 1.0:
        raise ValueError("validation_ratio must be in the range [0.0, 1.0).")

    grouped = {
        0: [example for example in examples if example["label"] == 0],
        1: [example for example in examples if example["label"] == 1],
    }
    rng = random.Random(seed)
    train_examples: list[dict[str, Any]] = []
    validation_examples: list[dict[str, Any]] = []

    for label_group in grouped.values():
        grouped_examples: dict[str, list[dict[str, Any]]] = {}
        for example in label_group:
            split_group = resolve_group_key(example, group_field)
            grouped_examples.setdefault(split_group, []).append(example)

        shuffled_groups = list(grouped_examples.values())
        rng.shuffle(shuffled_groups)
        group_count = len(shuffled_groups)
        if group_count <= 1 or validation_ratio == 0.0:
            validation_group_count = 0
        else:
            validation_group_count = max(1, int(round(group_count * validation_ratio)))
            validation_group_count = min(validation_group_count, group_count - 1)

        validation_groups = shuffled_groups[:validation_group_count]
        train_groups = shuffled_groups[validation_group_count:]
        for group in validation_groups:
            validation_examples.extend(group)
        for group in train_groups:
            train_examples.extend(group)

    rng.shuffle(train_examples)
    rng.shuffle(validation_examples)
    return train_examples, validation_examples


def build_feature_tensors(
    examples: list[dict[str, Any]],
    vocabulary: dict[str, int],
    *,
    device: str,
) -> tuple[torch.Tensor, torch.Tensor]:
    require_torch()
    feature_rows = [vectorize_text(example["text"], vocabulary) for example in examples]
    label_rows = [float(example["label"]) for example in examples]
    features = torch.tensor(feature_rows, dtype=torch.float32, device=device)
    labels = torch.tensor(label_rows, dtype=torch.float32, device=device)
    return features, labels


def compute_binary_metrics(
    *,
    logits: torch.Tensor,
    labels: torch.Tensor,
    loss_value: float | None,
    threshold: float = 0.5,
) -> dict[str, Any]:
    require_torch()
    probabilities = torch.sigmoid(logits)
    predictions = (probabilities >= threshold).to(dtype=torch.int64)
    truth = labels.to(dtype=torch.int64)

    true_positive = int(((predictions == 1) & (truth == 1)).sum().item())
    true_negative = int(((predictions == 0) & (truth == 0)).sum().item())
    false_positive = int(((predictions == 1) & (truth == 0)).sum().item())
    false_negative = int(((predictions == 0) & (truth == 1)).sum().item())
    return compute_binary_metrics_from_confusion(
        true_positive=true_positive,
        true_negative=true_negative,
        false_positive=false_positive,
        false_negative=false_negative,
        loss_value=loss_value,
        threshold=threshold,
    )


def compute_binary_metrics_from_confusion(
    *,
    true_positive: int,
    true_negative: int,
    false_positive: int,
    false_negative: int,
    loss_value: float | None,
    threshold: float | None = None,
) -> dict[str, Any]:
    total = max(1, true_positive + true_negative + false_positive + false_negative)
    precision_denominator = true_positive + false_positive
    recall_denominator = true_positive + false_negative
    precision = true_positive / precision_denominator if precision_denominator else 0.0
    recall = true_positive / recall_denominator if recall_denominator else 0.0
    f1_denominator = precision + recall
    f1 = 2 * precision * recall / f1_denominator if f1_denominator else 0.0

    metrics = {
        "accuracy": (true_positive + true_negative) / total,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "positive_predictions": true_positive + false_positive,
        "positive_labels": true_positive + false_negative,
        "confusion": {
            "true_positive": true_positive,
            "true_negative": true_negative,
            "false_positive": false_positive,
            "false_negative": false_negative,
        },
    }
    if threshold is not None:
        metrics["threshold"] = threshold
    if loss_value is not None:
        metrics["loss"] = loss_value
    return metrics


def average_metric_values(metric_values: list[float]) -> float | None:
    if not metric_values:
        return None
    return sum(metric_values) / len(metric_values)


def summarize_macro_metrics(metric_rows: list[dict[str, Any]]) -> dict[str, float | None]:
    if not metric_rows:
        return {}
    return {
        "accuracy": average_metric_values([float(row.get("accuracy", 0.0)) for row in metric_rows]),
        "precision": average_metric_values(
            [float(row.get("precision", 0.0)) for row in metric_rows]
        ),
        "recall": average_metric_values([float(row.get("recall", 0.0)) for row in metric_rows]),
        "f1": average_metric_values([float(row.get("f1", 0.0)) for row in metric_rows]),
    }


def summarize_negative_only_group_metrics(evaluated_groups: list[dict[str, Any]]) -> dict[str, float | None]:
    if not evaluated_groups:
        return {}

    specificities: list[float] = []
    false_positive_rates: list[float] = []
    accuracies: list[float] = []
    positive_prediction_rates: list[float] = []

    for group in evaluated_groups:
        metrics = group["metrics"]
        confusion = metrics["confusion"]
        true_negative = int(confusion["true_negative"])
        false_positive = int(confusion["false_positive"])
        denominator = true_negative + false_positive
        if denominator <= 0:
            specificity = 0.0
            false_positive_rate = 0.0
        else:
            specificity = true_negative / denominator
            false_positive_rate = false_positive / denominator
        specificities.append(specificity)
        false_positive_rates.append(false_positive_rate)
        accuracies.append(float(metrics.get("accuracy", 0.0)))
        positive_prediction_rates.append(
            float(metrics.get("positive_predictions", 0)) / max(1, int(group["validation_count"]))
        )

    return {
        "accuracy": average_metric_values(accuracies),
        "specificity": average_metric_values(specificities),
        "false_positive_rate": average_metric_values(false_positive_rates),
        "positive_prediction_rate": average_metric_values(positive_prediction_rates),
    }


def compute_positive_class_weight(labels: torch.Tensor) -> torch.Tensor:
    require_torch()
    positive_count = float(labels.sum().item())
    negative_count = float(labels.shape[0] - positive_count)
    if positive_count <= 0.0:
        return torch.tensor(1.0, dtype=torch.float32, device=labels.device)
    return torch.tensor(
        max(1.0, negative_count / positive_count),
        dtype=torch.float32,
        device=labels.device,
    )


def select_prediction_threshold(
    logits: torch.Tensor,
    labels: torch.Tensor,
    *,
    candidate_thresholds: tuple[float, ...] = DEFAULT_THRESHOLD_CANDIDATES,
) -> tuple[float, dict[str, Any]]:
    best_threshold = 0.5
    best_metrics = compute_binary_metrics(
        logits=logits,
        labels=labels,
        loss_value=None,
        threshold=best_threshold,
    )

    for threshold in candidate_thresholds:
        metrics = compute_binary_metrics(
            logits=logits,
            labels=labels,
            loss_value=None,
            threshold=threshold,
        )
        if (
            metrics["f1"] > best_metrics["f1"]
            or (
                metrics["f1"] == best_metrics["f1"]
                and metrics["recall"] > best_metrics["recall"]
            )
            or (
                metrics["f1"] == best_metrics["f1"]
                and metrics["recall"] == best_metrics["recall"]
                and abs(threshold - 0.5) < abs(best_threshold - 0.5)
            )
        ):
            best_threshold = threshold
            best_metrics = metrics

    return best_threshold, best_metrics


def fit_text_classifier_on_split(
    *,
    task_name: str,
    positive_label: str,
    negative_label: str,
    train_examples: list[dict[str, Any]],
    validation_examples: list[dict[str, Any]],
    device: str,
    epochs: int,
    learning_rate: float,
    hidden_dim: int,
    seed: int,
) -> dict[str, Any]:
    require_torch()
    if not train_examples:
        raise ValueError("Training split is empty. Increase the dataset or reduce validation_ratio.")

    random.seed(seed)
    torch.manual_seed(seed)

    vocabulary = build_vocabulary(train_examples)
    if not vocabulary:
        raise ValueError("The training vocabulary is empty.")

    train_features, train_labels = build_feature_tensors(train_examples, vocabulary, device=device)
    if validation_examples:
        validation_features, validation_labels = build_feature_tensors(
            validation_examples,
            vocabulary,
            device=device,
        )
    else:
        validation_features = validation_labels = None

    model = TextMLP(input_dim=len(vocabulary), hidden_dim=hidden_dim).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    positive_class_weight = compute_positive_class_weight(train_labels)
    criterion = nn.BCEWithLogitsLoss(pos_weight=positive_class_weight)

    best_state = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}
    best_validation_loss = float("inf")
    best_epoch = 0

    for epoch in range(1, epochs + 1):
        model.train()
        optimizer.zero_grad()
        train_logits = model(train_features)
        train_loss = criterion(train_logits, train_labels)
        train_loss.backward()
        optimizer.step()

        model.eval()
        with torch.no_grad():
            if validation_features is None:
                validation_loss_value = float(train_loss.item())
            else:
                validation_logits = model(validation_features)
                validation_loss_value = float(
                    criterion(validation_logits, validation_labels).item()
                )
        if validation_loss_value < best_validation_loss:
            best_validation_loss = validation_loss_value
            best_epoch = epoch
            best_state = {
                key: value.detach().cpu().clone() for key, value in model.state_dict().items()
            }

    model.load_state_dict(best_state)
    model.to(device)
    model.eval()

    with torch.no_grad():
        final_train_logits = model(train_features)
        final_train_loss = float(criterion(final_train_logits, train_labels).item())

        if validation_features is None:
            validation_metrics = {}
            best_prediction_threshold = 0.5
        else:
            final_validation_logits = model(validation_features)
            final_validation_loss = float(
                criterion(final_validation_logits, validation_labels).item()
            )
            best_prediction_threshold, validation_metrics = select_prediction_threshold(
                final_validation_logits,
                validation_labels,
            )
            validation_metrics = compute_binary_metrics(
                logits=final_validation_logits,
                labels=validation_labels,
                loss_value=final_validation_loss,
                threshold=best_prediction_threshold,
            )
        train_metrics = compute_binary_metrics(
            logits=final_train_logits,
            labels=train_labels,
            loss_value=final_train_loss,
            threshold=best_prediction_threshold,
        )

    return {
        "task_name": task_name,
        "positive_label": positive_label,
        "negative_label": negative_label,
        "device": device,
        "vocabulary": vocabulary,
        "hidden_dim": hidden_dim,
        "state_dict": {key: value.cpu() for key, value in best_state.items()},
        "train_positive_class_weight": float(positive_class_weight.item()),
        "best_prediction_threshold": best_prediction_threshold,
        "best_epoch": best_epoch,
        "train_metrics": train_metrics,
        "validation_metrics": validation_metrics,
    }


def evaluate_source_holdout_report(
    prepared_task: dict[str, Any],
    *,
    device_preference: str = "auto",
    group_field: str = "source_group",
    epochs: int = 40,
    learning_rate: float = 0.02,
    hidden_dim: int = 32,
    seed: int = 42,
) -> dict[str, Any]:
    require_torch()
    examples = list(prepared_task.get("examples", []))
    if not examples:
        raise ValueError("No examples were provided for source holdout evaluation.")

    device = select_device(device_preference)
    groups = sorted({resolve_group_key(example, group_field) for example in examples})
    evaluated_groups: list[dict[str, Any]] = []
    skipped_groups: list[dict[str, Any]] = []

    for group_index, held_out_group in enumerate(groups):
        train_examples, validation_examples = exact_group_holdout_split(
            examples,
            held_out_group=held_out_group,
            group_field=group_field,
        )
        train_label_counts = Counter(example["label"] for example in train_examples)
        validation_label_counts = Counter(example["label"] for example in validation_examples)
        fold_report = {
            "held_out_group": held_out_group,
            "train_count": len(train_examples),
            "validation_count": len(validation_examples),
            "train_positive_count": int(train_label_counts.get(1, 0)),
            "train_negative_count": int(train_label_counts.get(0, 0)),
            "validation_positive_count": int(validation_label_counts.get(1, 0)),
            "validation_negative_count": int(validation_label_counts.get(0, 0)),
        }

        if not train_examples:
            skipped_groups.append(
                {
                    **fold_report,
                    "reason": "training_split_empty",
                }
            )
            continue
        if train_label_counts.get(1, 0) == 0:
            skipped_groups.append(
                {
                    **fold_report,
                    "reason": "training_split_missing_positive_examples",
                }
            )
            continue
        if train_label_counts.get(0, 0) == 0:
            skipped_groups.append(
                {
                    **fold_report,
                    "reason": "training_split_missing_negative_examples",
                }
            )
            continue

        fit_result = fit_text_classifier_on_split(
            task_name=str(prepared_task["task_name"]),
            positive_label=str(prepared_task["positive_label"]),
            negative_label=str(prepared_task["negative_label"]),
            train_examples=train_examples,
            validation_examples=validation_examples,
            device=device,
            epochs=epochs,
            learning_rate=learning_rate,
            hidden_dim=hidden_dim,
            seed=seed + group_index,
        )
        evaluated_groups.append(
            {
                **fold_report,
                "contains_positive_label": fold_report["validation_positive_count"] > 0,
                "best_prediction_threshold": fit_result["best_prediction_threshold"],
                "metrics": fit_result["validation_metrics"],
            }
        )

    positive_groups = [
        group for group in evaluated_groups if bool(group["contains_positive_label"])
    ]
    negative_only_groups = [
        group for group in evaluated_groups if not bool(group["contains_positive_label"])
    ]
    micro_confusion = Counter()
    for group in evaluated_groups:
        confusion = group["metrics"]["confusion"]
        micro_confusion["true_positive"] += int(confusion["true_positive"])
        micro_confusion["true_negative"] += int(confusion["true_negative"])
        micro_confusion["false_positive"] += int(confusion["false_positive"])
        micro_confusion["false_negative"] += int(confusion["false_negative"])

    return {
        "group_field": group_field,
        "group_count": len(groups),
        "groups": groups,
        "evaluated_group_count": len(evaluated_groups),
        "skipped_group_count": len(skipped_groups),
        "evaluated_positive_group_count": len(positive_groups),
        "evaluated_negative_only_group_count": len(negative_only_groups),
        "macro_metrics": summarize_macro_metrics(
            [group["metrics"] for group in evaluated_groups]
        ),
        "micro_metrics": compute_binary_metrics_from_confusion(
            true_positive=int(micro_confusion["true_positive"]),
            true_negative=int(micro_confusion["true_negative"]),
            false_positive=int(micro_confusion["false_positive"]),
            false_negative=int(micro_confusion["false_negative"]),
            loss_value=None,
            threshold=None,
        )
        if evaluated_groups
        else {},
        "positive_group_macro_metrics": summarize_macro_metrics(
            [group["metrics"] for group in positive_groups]
        ),
        "negative_only_group_macro_metrics": summarize_negative_only_group_metrics(
            negative_only_groups
        ),
        "evaluated_groups": evaluated_groups,
        "skipped_groups": skipped_groups,
    }


def train_task_classifier(
    prepared_task: dict[str, Any],
    *,
    output_dir: Path,
    device_preference: str = "auto",
    validation_ratio: float = 0.25,
    validation_grouping: str = DEFAULT_VALIDATION_GROUPING,
    epochs: int = 40,
    learning_rate: float = 0.02,
    hidden_dim: int = 32,
    seed: int = 42,
) -> dict[str, Any]:
    require_torch()
    if not prepared_task.get("examples"):
        raise ValueError("No examples were provided for training.")

    device = select_device(device_preference)
    task_name = str(prepared_task["task_name"])
    examples = list(prepared_task["examples"])
    validation_grouping_used, validation_grouping_fallback_reason = select_validation_grouping(
        examples,
        requested_grouping=validation_grouping,
    )
    validation_group_counts = count_unique_groups_by_label(
        examples,
        group_field=validation_grouping_used,
    )
    train_examples, validation_examples = stratified_split(
        examples,
        validation_ratio=validation_ratio,
        seed=seed,
        group_field=validation_grouping_used,
    )
    fit_result = fit_text_classifier_on_split(
        task_name=task_name,
        positive_label=str(prepared_task["positive_label"]),
        negative_label=str(prepared_task["negative_label"]),
        train_examples=train_examples,
        validation_examples=validation_examples,
        device=device,
        epochs=epochs,
        learning_rate=learning_rate,
        hidden_dim=hidden_dim,
        seed=seed,
    )
    source_holdout_evaluation = evaluate_source_holdout_report(
        prepared_task,
        device_preference=device,
        group_field="source_group",
        epochs=epochs,
        learning_rate=learning_rate,
        hidden_dim=hidden_dim,
        seed=seed,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    model_path = output_dir / f"{task_name}.pt"
    report_path = output_dir / f"{task_name}_report.json"

    artifact = {
        "task_name": task_name,
        "positive_label": prepared_task["positive_label"],
        "negative_label": prepared_task["negative_label"],
        "vocabulary": fit_result["vocabulary"],
        "hidden_dim": hidden_dim,
        "state_dict": fit_result["state_dict"],
    }
    torch.save(artifact, model_path)

    labels = [example["label"] for example in examples]
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "task_name": task_name,
        "positive_label": prepared_task["positive_label"],
        "negative_label": prepared_task["negative_label"],
        "device": device,
        "torch_version": torch.__version__,
        "cuda_visible_to_torch": bool(torch.cuda.is_available()),
        "cuda_version": torch.version.cuda,
        "example_count": len(examples),
        "positive_count": int(sum(labels)),
        "negative_count": len(examples) - int(sum(labels)),
        "skipped_example_count": len(prepared_task.get("skipped_example_ids", [])),
        "train_count": len(train_examples),
        "validation_count": len(validation_examples),
        "vocabulary_size": len(fit_result["vocabulary"]),
        "train_positive_class_weight": fit_result["train_positive_class_weight"],
        "best_prediction_threshold": fit_result["best_prediction_threshold"],
        "validation_grouping_requested": validation_grouping,
        "validation_grouping_used": validation_grouping_used,
        "validation_group_counts": {
            "negative_label_groups": validation_group_counts[0],
            "positive_label_groups": validation_group_counts[1],
        },
        "validation_grouping_fallback_reason": validation_grouping_fallback_reason,
        "hyperparameters": {
            "epochs": epochs,
            "learning_rate": learning_rate,
            "hidden_dim": hidden_dim,
            "validation_ratio": validation_ratio,
            "validation_grouping": validation_grouping_used,
            "seed": seed,
        },
        "best_epoch": fit_result["best_epoch"],
        "metrics": {
            "train": fit_result["train_metrics"],
            "validation": fit_result["validation_metrics"],
        },
        "source_holdout_evaluation": source_holdout_evaluation,
        "model_path": str(model_path),
        "report_path": str(report_path),
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Train a narrow binary neural classifier against the exported trading "
            "training surface. This is intended for offline experiments only."
        )
    )
    parser.add_argument("--dataset-path", default=str(DEFAULT_DATASET_PATH))
    parser.add_argument("--task-name", required=True)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda", "mps"])
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--learning-rate", type=float, default=0.02)
    parser.add_argument("--hidden-dim", type=int, default=32)
    parser.add_argument("--validation-ratio", type=float, default=0.25)
    parser.add_argument(
        "--validation-grouping",
        default=DEFAULT_VALIDATION_GROUPING,
        choices=VALIDATION_GROUPING_CHOICES,
    )
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    dataset_path = Path(args.dataset_path)
    examples = load_surface_examples(dataset_path)
    prepared = prepare_task_examples(examples, task_name=args.task_name)
    report = train_task_classifier(
        prepared,
        output_dir=Path(args.output_dir),
        device_preference=args.device,
        validation_ratio=args.validation_ratio,
        validation_grouping=args.validation_grouping,
        epochs=args.epochs,
        learning_rate=args.learning_rate,
        hidden_dim=args.hidden_dim,
        seed=args.seed,
    )
    print(
        json.dumps(
            {
                "task_name": report["task_name"],
                "device": report["device"],
                "example_count": report["example_count"],
                "validation_accuracy": report["metrics"]["validation"].get("accuracy"),
                "report_path": report["report_path"],
                "model_path": report["model_path"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
