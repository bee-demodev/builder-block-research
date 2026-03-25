from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import torch
    from torch import nn
except ImportError as exc:  # pragma: no cover - exercised only in non-ML environments
    torch = None
    nn = None
    TORCH_IMPORT_ERROR = exc
else:
    TORCH_IMPORT_ERROR = None


DEFAULT_DATASET_PATH = ROOT / "results" / "ttfm_teacher_visual_dataset.jsonl"
DEFAULT_OUTPUT_DIR = ROOT / "results" / "neural_models" / "ttfm_visual"
DEFAULT_MODEL_NAME = "ttfm_visual_pattern_net"
DEFAULT_THRESHOLD_CANDIDATES = (0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.55)


class SmallVisualCNN(nn.Module):
    def __init__(self, output_dim: int) -> None:
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(3, 16, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(kernel_size=2),
            nn.Conv2d(16, 32, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(kernel_size=2),
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool2d((1, 1)),
        )
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(64, 64),
            nn.ReLU(),
            nn.Linear(64, output_dim),
        )

    def forward(self, images: torch.Tensor) -> torch.Tensor:
        features = self.features(images)
        return self.classifier(features)


def require_torch() -> None:
    if TORCH_IMPORT_ERROR is not None:
        raise RuntimeError("PyTorch is required for neural training.") from TORCH_IMPORT_ERROR


def load_teacher_visual_rows(dataset_path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with dataset_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            cleaned = line.strip()
            if cleaned:
                rows.append(json.loads(cleaned))
    return rows


def select_label_space(
    rows: list[dict[str, Any]],
    *,
    min_positive_examples: int,
) -> tuple[list[str], dict[str, int], list[str]]:
    label_counts: Counter[str] = Counter()
    for row in rows:
        label_counts.update(str(label).strip() for label in row.get("active_labels", []) if str(label).strip())

    selected_labels = sorted(
        label for label, count in label_counts.items() if count >= min_positive_examples
    )
    skipped_labels = sorted(
        label for label, count in label_counts.items() if count < min_positive_examples
    )
    return selected_labels, dict(sorted(label_counts.items())), skipped_labels


def resolve_image_path(path_value: str) -> Path:
    candidate = Path(path_value)
    if candidate.is_absolute():
        return candidate
    return ROOT / candidate


def normalize_sample_weight(value: object, *, default: float = 1.0) -> float:
    try:
        weight = float(value)
    except (TypeError, ValueError):
        return default
    if weight <= 0.0:
        return default
    return weight


def build_examples(
    rows: list[dict[str, Any]],
    *,
    label_to_index: dict[str, int],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    examples: list[dict[str, Any]] = []
    skipped_examples: list[dict[str, Any]] = []
    output_dim = len(label_to_index)

    for row in rows:
        path_value = str(row.get("screenshot_path", "")).strip()
        image_path = resolve_image_path(path_value)
        if not path_value or not image_path.exists():
            skipped_examples.append(
                {
                    "example_id": str(row.get("example_id", "")).strip() or "unknown",
                    "reason": "missing_image",
                    "screenshot_path": path_value or None,
                }
            )
            continue

        target = [0.0] * output_dim
        for label in row.get("active_labels", []):
            normalized = str(label).strip()
            index = label_to_index.get(normalized)
            if index is not None:
                target[index] = 1.0

        examples.append(
            {
                "example_id": str(row.get("example_id", "")).strip(),
                "case_ref": str(row.get("case_ref", "")).strip(),
                "checkpoint": str(row.get("checkpoint", "")).strip(),
                "image_path": str(image_path),
                "target": target,
                "active_labels": row.get("active_labels", []),
                "market_context": row.get("market_context", {}),
                "sample_weight": normalize_sample_weight(row.get("sample_weight", 1.0)),
            }
        )

    return examples, skipped_examples


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


def split_examples(
    examples: list[dict[str, Any]],
    *,
    validation_ratio: float,
    seed: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not 0.0 <= validation_ratio < 1.0:
        raise ValueError("validation_ratio must be in the range [0.0, 1.0).")
    shuffled = list(examples)
    rng = random.Random(seed)
    rng.shuffle(shuffled)
    if len(shuffled) <= 1 or validation_ratio == 0.0:
        return shuffled, []
    validation_count = max(1, int(round(len(shuffled) * validation_ratio)))
    validation_count = min(validation_count, len(shuffled) - 1)
    train_examples = shuffled[validation_count:]
    validation_examples = shuffled[:validation_count]
    return ensure_train_label_coverage(train_examples, validation_examples)


def ensure_train_label_coverage(
    train_examples: list[dict[str, Any]],
    validation_examples: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not train_examples or not validation_examples:
        return train_examples, validation_examples

    train_pool = list(train_examples)
    validation_pool = list(validation_examples)
    output_dim = len(train_pool[0]["target"])
    train_positive_counts = [0] * output_dim
    for example in train_pool:
        for index, value in enumerate(example["target"]):
            if value == 1.0:
                train_positive_counts[index] += 1

    moved_example = True
    while moved_example and len(validation_pool) > 1:
        moved_example = False
        for label_index, positive_count in enumerate(train_positive_counts):
            if positive_count > 0:
                continue

            candidate_index = next(
                (
                    index
                    for index, example in enumerate(validation_pool)
                    if example["target"][label_index] == 1.0
                ),
                None,
            )
            if candidate_index is None:
                continue

            example = validation_pool.pop(candidate_index)
            train_pool.append(example)
            for index, value in enumerate(example["target"]):
                if value == 1.0:
                    train_positive_counts[index] += 1
            moved_example = True
            break

    return train_pool, validation_pool


def image_to_tensor(image_path: Path, *, image_size: int) -> torch.Tensor:
    require_torch()
    image = Image.open(image_path).convert("RGB").resize((image_size, image_size))
    pixels = torch.tensor(bytearray(image.tobytes()), dtype=torch.float32)
    return pixels.view(image_size, image_size, 3).permute(2, 0, 1) / 255.0


def build_tensors(
    examples: list[dict[str, Any]],
    *,
    image_size: int,
    device: str,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    require_torch()
    image_tensors = [
        image_to_tensor(Path(example["image_path"]), image_size=image_size) for example in examples
    ]
    label_tensors = [example["target"] for example in examples]
    sample_weights = [float(example.get("sample_weight", 1.0)) for example in examples]
    images = torch.stack(image_tensors).to(device=device)
    labels = torch.tensor(label_tensors, dtype=torch.float32, device=device)
    weights = torch.tensor(sample_weights, dtype=torch.float32, device=device)
    return images, labels, weights


def iter_minibatches(
    images: torch.Tensor,
    labels: torch.Tensor,
    sample_weights: torch.Tensor,
    *,
    batch_size: int,
) -> list[tuple[torch.Tensor, torch.Tensor, torch.Tensor]]:
    batches: list[tuple[torch.Tensor, torch.Tensor, torch.Tensor]] = []
    for start in range(0, len(images), batch_size):
        end = start + batch_size
        batches.append((images[start:end], labels[start:end], sample_weights[start:end]))
    return batches


def threshold_to_tensor(
    threshold: float | list[float] | tuple[float, ...] | torch.Tensor,
    *,
    label_count: int,
    device: torch.device | str,
    dtype: torch.dtype,
) -> tuple[torch.Tensor, bool]:
    require_torch()
    if isinstance(threshold, (int, float)):
        scalar = float(threshold)
        return torch.full((label_count,), scalar, dtype=dtype, device=device), True

    if isinstance(threshold, torch.Tensor):
        tensor = threshold.to(device=device, dtype=dtype).flatten()
    else:
        tensor = torch.tensor(list(threshold), dtype=dtype, device=device).flatten()

    if tensor.numel() == 1:
        scalar = float(tensor.item())
        return torch.full((label_count,), scalar, dtype=dtype, device=device), True
    if tensor.numel() != label_count:
        raise ValueError(
            f"Expected {label_count} threshold values, but received {int(tensor.numel())}."
        )
    return tensor, False


def compute_multilabel_metrics(
    *,
    logits: torch.Tensor,
    labels: torch.Tensor,
    loss_value: float | None,
    threshold: float | list[float] | tuple[float, ...] | torch.Tensor = 0.5,
) -> dict[str, Any]:
    require_torch()
    probabilities = torch.sigmoid(logits)
    threshold_tensor, is_scalar_threshold = threshold_to_tensor(
        threshold,
        label_count=int(probabilities.shape[1]),
        device=probabilities.device,
        dtype=probabilities.dtype,
    )
    predictions = (probabilities >= threshold_tensor.view(1, -1)).to(dtype=torch.int64)
    truth = labels.to(dtype=torch.int64)

    true_positive = int(((predictions == 1) & (truth == 1)).sum().item())
    true_negative = int(((predictions == 0) & (truth == 0)).sum().item())
    false_positive = int(((predictions == 1) & (truth == 0)).sum().item())
    false_negative = int(((predictions == 0) & (truth == 1)).sum().item())
    total = max(1, int(truth.numel()))
    precision_denominator = true_positive + false_positive
    recall_denominator = true_positive + false_negative
    precision = true_positive / precision_denominator if precision_denominator else 0.0
    recall = true_positive / recall_denominator if recall_denominator else 0.0
    f1_denominator = precision + recall
    f1 = 2 * precision * recall / f1_denominator if f1_denominator else 0.0
    exact_match = float((predictions == truth).all(dim=1).float().mean().item())

    metrics = {
        "micro_accuracy": (true_positive + true_negative) / total,
        "micro_precision": precision,
        "micro_recall": recall,
        "micro_f1": f1,
        "exact_match_ratio": exact_match,
        "positive_predictions": int(predictions.sum().item()),
        "positive_labels": int(truth.sum().item()),
        "confusion": {
            "true_positive": true_positive,
            "true_negative": true_negative,
            "false_positive": false_positive,
            "false_negative": false_negative,
        },
        "threshold": float(threshold_tensor.mean().item()),
    }
    if not is_scalar_threshold:
        metrics["thresholds"] = [float(value) for value in threshold_tensor.detach().cpu().tolist()]
    if loss_value is not None:
        metrics["loss"] = loss_value
    return metrics


def compute_pos_weight(labels: torch.Tensor) -> torch.Tensor:
    require_torch()
    positive_counts = labels.sum(dim=0)
    negative_counts = labels.shape[0] - positive_counts
    safe_positive_counts = torch.where(
        positive_counts > 0,
        positive_counts,
        torch.ones_like(positive_counts),
    )
    pos_weight = negative_counts / safe_positive_counts
    return torch.clamp(pos_weight, min=1.0)


def reduce_weighted_multilabel_loss(
    per_label_loss: torch.Tensor,
    example_weights: torch.Tensor,
) -> torch.Tensor:
    require_torch()
    if per_label_loss.ndim == 0:
        raise ValueError("per_label_loss must include a batch dimension.")

    if per_label_loss.ndim == 1:
        per_example_loss = per_label_loss
    else:
        per_example_loss = per_label_loss.mean(dim=tuple(range(1, per_label_loss.ndim)))

    normalized_weights = example_weights.reshape(-1).to(
        device=per_example_loss.device,
        dtype=per_example_loss.dtype,
    )
    if normalized_weights.shape[0] != per_example_loss.shape[0]:
        raise ValueError("example_weights must align with the batch dimension of per_label_loss.")

    weight_sum = normalized_weights.sum()
    if float(weight_sum.item()) <= 0.0:
        return per_example_loss.mean()
    return (per_example_loss * normalized_weights).sum() / weight_sum


def compute_binary_classification_metrics(
    *,
    probabilities: torch.Tensor,
    labels: torch.Tensor,
    threshold: float,
) -> dict[str, Any]:
    require_torch()
    predictions = (probabilities >= float(threshold)).to(dtype=torch.int64)
    truth = labels.to(dtype=torch.int64)

    true_positive = int(((predictions == 1) & (truth == 1)).sum().item())
    false_positive = int(((predictions == 1) & (truth == 0)).sum().item())
    false_negative = int(((predictions == 0) & (truth == 1)).sum().item())
    precision_denominator = true_positive + false_positive
    recall_denominator = true_positive + false_negative
    precision = true_positive / precision_denominator if precision_denominator else 0.0
    recall = true_positive / recall_denominator if recall_denominator else 0.0
    f1_denominator = precision + recall
    f1 = 2 * precision * recall / f1_denominator if f1_denominator else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "positive_predictions": int(predictions.sum().item()),
        "positive_labels": int(truth.sum().item()),
    }


def select_per_label_prediction_thresholds(
    logits: torch.Tensor,
    labels: torch.Tensor,
    *,
    candidate_thresholds: list[float] | tuple[float, ...] = DEFAULT_THRESHOLD_CANDIDATES,
) -> tuple[list[float], dict[str, Any]]:
    require_torch()
    probabilities = torch.sigmoid(logits)
    thresholds: list[float] = []

    for label_index in range(int(labels.shape[1])):
        best_threshold = 0.5
        best_metrics = compute_binary_classification_metrics(
            probabilities=probabilities[:, label_index],
            labels=labels[:, label_index],
            threshold=best_threshold,
        )
        best_gap = abs(best_metrics["positive_predictions"] - best_metrics["positive_labels"])

        for threshold in candidate_thresholds:
            metrics = compute_binary_classification_metrics(
                probabilities=probabilities[:, label_index],
                labels=labels[:, label_index],
                threshold=float(threshold),
            )
            gap = abs(metrics["positive_predictions"] - metrics["positive_labels"])
            if (
                metrics["f1"] > best_metrics["f1"]
                or (
                    metrics["f1"] == best_metrics["f1"]
                    and metrics["recall"] > best_metrics["recall"]
                )
                or (
                    metrics["f1"] == best_metrics["f1"]
                    and metrics["recall"] == best_metrics["recall"]
                    and metrics["precision"] > best_metrics["precision"]
                )
                or (
                    metrics["f1"] == best_metrics["f1"]
                    and metrics["recall"] == best_metrics["recall"]
                    and metrics["precision"] == best_metrics["precision"]
                    and gap < best_gap
                )
                or (
                    metrics["f1"] == best_metrics["f1"]
                    and metrics["recall"] == best_metrics["recall"]
                    and metrics["precision"] == best_metrics["precision"]
                    and gap == best_gap
                    and abs(float(threshold) - 0.5) < abs(best_threshold - 0.5)
                )
            ):
                best_threshold = float(threshold)
                best_metrics = metrics
                best_gap = gap

        thresholds.append(best_threshold)

    metrics = compute_multilabel_metrics(
        logits=logits,
        labels=labels,
        loss_value=None,
        threshold=thresholds,
    )
    return thresholds, metrics


def select_prediction_threshold(
    logits: torch.Tensor,
    labels: torch.Tensor,
    *,
    candidate_thresholds: list[float] | tuple[float, ...] = DEFAULT_THRESHOLD_CANDIDATES,
) -> tuple[float, dict[str, Any]]:
    best_threshold = 0.5
    best_metrics = compute_multilabel_metrics(
        logits=logits,
        labels=labels,
        loss_value=None,
        threshold=best_threshold,
    )

    for threshold in candidate_thresholds:
        metrics = compute_multilabel_metrics(
            logits=logits,
            labels=labels,
            loss_value=None,
            threshold=threshold,
        )
        if (
            metrics["micro_f1"] > best_metrics["micro_f1"]
            or (
                metrics["micro_f1"] == best_metrics["micro_f1"]
                and metrics["micro_recall"] > best_metrics["micro_recall"]
            )
            or (
                metrics["micro_f1"] == best_metrics["micro_f1"]
                and metrics["micro_recall"] == best_metrics["micro_recall"]
                and abs(threshold - 0.5) < abs(best_threshold - 0.5)
            )
        ):
            best_threshold = threshold
            best_metrics = metrics

    return best_threshold, best_metrics


def train_visual_classifier(
    examples: list[dict[str, Any]],
    *,
    label_to_index: dict[str, int],
    output_dir: Path,
    model_name: str = DEFAULT_MODEL_NAME,
    device_preference: str = "auto",
    validation_ratio: float = 0.2,
    epochs: int = 16,
    learning_rate: float = 1e-3,
    batch_size: int = 8,
    image_size: int = 128,
    seed: int = 42,
) -> dict[str, Any]:
    require_torch()
    if not examples:
        raise ValueError("No examples were provided for training.")
    if not label_to_index:
        raise ValueError("Label space is empty; lower the min_positive_examples threshold.")

    device = select_device(device_preference)
    random.seed(seed)
    torch.manual_seed(seed)
    if device == "cuda":
        torch.cuda.manual_seed_all(seed)

    train_examples, validation_examples = split_examples(
        examples,
        validation_ratio=validation_ratio,
        seed=seed,
    )
    if not train_examples:
        raise ValueError("Training split is empty. Increase the dataset or reduce validation_ratio.")

    train_images, train_labels, train_weights = build_tensors(
        train_examples,
        image_size=image_size,
        device=device,
    )
    if validation_examples:
        validation_images, validation_labels, validation_weights = build_tensors(
            validation_examples,
            image_size=image_size,
            device=device,
        )
    else:
        validation_images = validation_labels = validation_weights = None

    model = SmallVisualCNN(output_dim=len(label_to_index)).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    pos_weight = compute_pos_weight(train_labels)
    criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight, reduction="none")

    best_state = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}
    best_validation_loss = float("inf")
    best_validation_f1 = -1.0
    best_validation_recall = -1.0
    best_prediction_threshold = 0.5
    best_epoch = 0
    training_history: list[dict[str, float | int]] = []

    for epoch in range(1, epochs + 1):
        model.train()
        batch_losses: list[float] = []
        for batch_images, batch_labels, batch_weights in iter_minibatches(
            train_images,
            train_labels,
            train_weights,
            batch_size=batch_size,
        ):
            optimizer.zero_grad()
            logits = model(batch_images)
            loss = reduce_weighted_multilabel_loss(
                criterion(logits, batch_labels),
                batch_weights,
            )
            loss.backward()
            optimizer.step()
            batch_losses.append(float(loss.item()))

        model.eval()
        with torch.no_grad():
            if validation_images is None:
                selection_logits = model(train_images)
                validation_loss_value = sum(batch_losses) / max(1, len(batch_losses))
                epoch_threshold, selection_metrics = select_prediction_threshold(
                    selection_logits,
                    train_labels,
                )
            else:
                validation_logits = model(validation_images)
                validation_loss_value = float(
                    reduce_weighted_multilabel_loss(
                        criterion(validation_logits, validation_labels),
                        validation_weights,
                    ).item()
                )
                epoch_threshold, selection_metrics = select_prediction_threshold(
                    validation_logits,
                    validation_labels,
                )

        average_train_loss = sum(batch_losses) / max(1, len(batch_losses))
        training_history.append(
            {
                "epoch": epoch,
                "train_loss": average_train_loss,
                "validation_loss": validation_loss_value,
                "validation_micro_f1": selection_metrics["micro_f1"],
                "validation_micro_recall": selection_metrics["micro_recall"],
                "prediction_threshold": epoch_threshold,
            }
        )

        if (
            selection_metrics["micro_f1"] > best_validation_f1
            or (
                selection_metrics["micro_f1"] == best_validation_f1
                and selection_metrics["micro_recall"] > best_validation_recall
            )
            or (
                selection_metrics["micro_f1"] == best_validation_f1
                and selection_metrics["micro_recall"] == best_validation_recall
                and validation_loss_value < best_validation_loss
            )
        ):
            best_validation_loss = validation_loss_value
            best_validation_f1 = selection_metrics["micro_f1"]
            best_validation_recall = selection_metrics["micro_recall"]
            best_prediction_threshold = epoch_threshold
            best_epoch = epoch
            best_state = {
                key: value.detach().cpu().clone() for key, value in model.state_dict().items()
            }

    model.load_state_dict(best_state)
    model.to(device)
    model.eval()

    with torch.no_grad():
        final_train_logits = model(train_images)
        final_train_loss = float(
            reduce_weighted_multilabel_loss(
                criterion(final_train_logits, train_labels),
                train_weights,
            ).item()
        )
        train_metrics = compute_multilabel_metrics(
            logits=final_train_logits,
            labels=train_labels,
            loss_value=final_train_loss,
            threshold=best_prediction_threshold,
        )
        if validation_images is None:
            validation_metrics = {}
        else:
            final_validation_logits = model(validation_images)
            final_validation_loss = float(
                reduce_weighted_multilabel_loss(
                    criterion(final_validation_logits, validation_labels),
                    validation_weights,
                ).item()
            )
            validation_metrics = compute_multilabel_metrics(
                logits=final_validation_logits,
                labels=validation_labels,
                loss_value=final_validation_loss,
                threshold=best_prediction_threshold,
            )

    output_dir.mkdir(parents=True, exist_ok=True)
    model_path = output_dir / f"{model_name}.pt"
    report_path = output_dir / f"{model_name}_report.json"

    artifact = {
        "model_name": model_name,
        "model_type": "SmallVisualCNN",
        "label_to_index": label_to_index,
        "image_size": image_size,
        "prediction_threshold": best_prediction_threshold,
        "state_dict": {key: value.cpu() for key, value in best_state.items()},
    }
    torch.save(artifact, model_path)

    label_counts = Counter()
    for example in examples:
        for label_name, index in label_to_index.items():
            if example["target"][index] == 1.0:
                label_counts[label_name] += 1

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model_name": model_name,
        "model_path": str(model_path),
        "device": device,
        "cuda_visible_to_torch": bool(torch.cuda.is_available()),
        "cuda_version": getattr(torch.version, "cuda", None),
        "example_count": len(examples),
        "train_example_count": len(train_examples),
        "validation_example_count": len(validation_examples),
        "label_space_size": len(label_to_index),
        "label_space": list(label_to_index.keys()),
        "label_counts": dict(sorted(label_counts.items())),
        "train_pos_weight": {
            label_name: float(pos_weight[index].item())
            for label_name, index in label_to_index.items()
        },
        "best_epoch": best_epoch,
        "best_validation_loss": best_validation_loss,
        "best_validation_f1": best_validation_f1,
        "best_prediction_threshold": best_prediction_threshold,
        "epochs": epochs,
        "learning_rate": learning_rate,
        "batch_size": batch_size,
        "image_size": image_size,
        "train_metrics": train_metrics,
        "validation_metrics": validation_metrics,
        "training_history": training_history,
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train a screenshot-based TTFM visual component model."
    )
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET_PATH))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--model-name", default=DEFAULT_MODEL_NAME)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--validation-ratio", type=float, default=0.2)
    parser.add_argument("--epochs", type=int, default=16)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--image-size", type=int, default=128)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--min-positive-examples", type=int, default=2)
    args = parser.parse_args()

    rows = load_teacher_visual_rows(Path(args.dataset))
    selected_labels, label_counts, skipped_labels = select_label_space(
        rows,
        min_positive_examples=args.min_positive_examples,
    )
    label_to_index = {label: index for index, label in enumerate(selected_labels)}
    examples, skipped_examples = build_examples(rows, label_to_index=label_to_index)
    report = train_visual_classifier(
        examples,
        label_to_index=label_to_index,
        output_dir=Path(args.output_dir),
        model_name=args.model_name,
        device_preference=args.device,
        validation_ratio=args.validation_ratio,
        epochs=args.epochs,
        learning_rate=args.learning_rate,
        batch_size=args.batch_size,
        image_size=args.image_size,
        seed=args.seed,
    )

    report["dataset_path"] = str(Path(args.dataset).resolve())
    report["min_positive_examples"] = args.min_positive_examples
    report["raw_row_count"] = len(rows)
    report["selected_label_counts"] = {label: label_counts[label] for label in selected_labels}
    report["skipped_labels"] = skipped_labels
    report["skipped_examples"] = skipped_examples

    report_path = Path(report["model_path"]).with_name(f"{args.model_name}_report.json")
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "model_path": report["model_path"],
                "report_path": str(report_path),
                "device": report["device"],
                "example_count": report["example_count"],
                "label_space_size": report["label_space_size"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
