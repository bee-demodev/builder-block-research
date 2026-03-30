from __future__ import annotations

import contextlib
import hashlib
import json
import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from config import AppConfig, SETUP_LABELS, config_to_dict
from data_loader import ChartExample, split_examples_by_time
from labeler.embedding_labeler import PseudoLabelResult

try:
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset
except ImportError as exc:  # pragma: no cover - import guard only
    torch = None
    nn = None
    TORCH_IMPORT_ERROR = exc
else:
    TORCH_IMPORT_ERROR = None


RESULTS_TSV_PATH = Path("results") / "results_mlp.tsv"
CHECKPOINT_PATH = Path("models") / "mlp_ttrades_best.pth"


@dataclass(slots=True)
class EpochMetrics:
    train_loss: float
    val_loss: float
    val_f1_macro: float
    accuracy: float
    precision: float
    recall: float
    confusion: np.ndarray
    predictions: list[dict[str, Any]]
    true_label_names: list[str]
    predicted_label_names: list[str]


class SmallMLP(nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int, dropout: float) -> None:
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim // 2, len(SETUP_LABELS)),
        )

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        return self.network(features)


def _confusion_matrix(y_true: np.ndarray, y_pred: np.ndarray, class_count: int) -> np.ndarray:
    matrix = np.zeros((class_count, class_count), dtype=np.int64)
    for true_value, predicted_value in zip(y_true.astype(int), y_pred.astype(int)):
        matrix[true_value, predicted_value] += 1
    return matrix


def _macro_metrics(matrix: np.ndarray) -> tuple[float, float, float]:
    precisions: list[float] = []
    recalls: list[float] = []
    f1s: list[float] = []
    for index in range(matrix.shape[0]):
        tp = float(matrix[index, index])
        fp = float(matrix[:, index].sum() - tp)
        fn = float(matrix[index, :].sum() - tp)
        precision = 0.0 if tp + fp == 0.0 else tp / (tp + fp)
        recall = 0.0 if tp + fn == 0.0 else tp / (tp + fn)
        f1 = 0.0 if precision + recall == 0.0 else 2 * precision * recall / (precision + recall)
        precisions.append(precision)
        recalls.append(recall)
        f1s.append(f1)
    return float(np.mean(precisions)), float(np.mean(recalls)), float(np.mean(f1s))


def _require_torch() -> None:
    if TORCH_IMPORT_ERROR is not None:
        raise RuntimeError("PyTorch is required for Phase 1 training.") from TORCH_IMPORT_ERROR


def _select_device() -> torch.device:
    _require_torch()
    if torch.cuda.is_available():
        return torch.device("cuda")
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def _can_use_torch_compile(device: torch.device) -> bool:
    if device.type != "cuda":
        return False
    if not hasattr(torch, "compile"):
        return False
    return importlib.util.find_spec("triton") is not None


def _compute_class_weights(labels: np.ndarray, config: AppConfig) -> torch.Tensor:
    if config.phase1.class_weights:
        weights = [float(config.phase1.class_weights.get(label, 1.0)) for label in SETUP_LABELS]
        return torch.tensor(weights, dtype=torch.float32)
    counts = np.bincount(labels, minlength=len(SETUP_LABELS))
    weights = np.array([0.0 if count == 0 else len(labels) / (len(SETUP_LABELS) * count) for count in counts], dtype=np.float32)
    return torch.tensor(weights, dtype=torch.float32)


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def build_training_artifact_fingerprints(config: AppConfig) -> dict[str, Any]:
    fingerprints: dict[str, Any] = {}
    tracked_paths = {
        "visual_embedding_index": config.paths.visual_embedding_index_path,
        "anchor_manifest": config.paths.anchors_path,
        "pseudo_labels": config.paths.phase1_pseudo_labels_path,
    }
    for key, path in tracked_paths.items():
        fingerprints[f"{key}_path"] = str(path.resolve())
        fingerprints[f"{key}_exists"] = path.exists()
        fingerprints[f"{key}_sha256"] = _sha256_file(path) if path.exists() else None
    return fingerprints


def load_mlp_checkpoint_metadata(checkpoint_path: Path) -> dict[str, Any]:
    _require_torch()
    checkpoint = torch.load(checkpoint_path, map_location="cpu")
    return dict(checkpoint.get("training_artifacts", {}))


def build_checkpoint_context_warnings(metadata: dict[str, Any], config: AppConfig) -> list[str]:
    warnings: list[str] = []
    tracked_paths = {
        "visual_embedding_index": config.paths.visual_embedding_index_path,
        "anchor_manifest": config.paths.anchors_path,
        "pseudo_labels": config.paths.phase1_pseudo_labels_path,
    }
    readable_names = {
        "visual_embedding_index": "Visual embedding index",
        "anchor_manifest": "Anchor manifest",
        "pseudo_labels": "Pseudo-label snapshot",
    }
    for key, current_path in tracked_paths.items():
        current_exists = current_path.exists()
        expected_exists = bool(metadata.get(f"{key}_exists"))
        expected_hash = metadata.get(f"{key}_sha256")
        if expected_exists and not current_exists:
            warnings.append(f"{readable_names[key]} is missing at serving time: {current_path}")
            continue
        if current_exists and expected_hash:
            current_hash = _sha256_file(current_path)
            if current_hash != expected_hash:
                warnings.append(
                    f"{readable_names[key]} fingerprint mismatch between checkpoint and current workspace."
                )
    return warnings


def _prepare_labeled_examples(examples: list[ChartExample], pseudo_labels: PseudoLabelResult) -> list[dict[str, Any]]:
    lookup = {row.example_id: row for row in pseudo_labels.rows if row.pseudo_label}
    labeled: list[dict[str, Any]] = []
    label_to_index = {label: index for index, label in enumerate(SETUP_LABELS)}
    for example in sorted(examples, key=lambda item: item.time_index):
        row = lookup.get(example.example_id)
        if row is None:
            continue
        labeled.append(
            {
                "example_id": example.example_id,
                "embedding": example.embedding.astype(np.float32),
                "label_index": label_to_index[row.pseudo_label],
                "label_name": row.pseudo_label,
                "time_index": example.time_index,
                "image_path": str(example.image_path),
            }
        )
    if len(labeled) < 2:
        raise RuntimeError("Need at least two confidently labeled examples to train the MLP.")
    return labeled


def _tensorize(rows: list[dict[str, Any]]) -> tuple[torch.Tensor, torch.Tensor]:
    features = np.vstack([row["embedding"] for row in rows]).astype(np.float32)
    labels = np.asarray([row["label_index"] for row in rows], dtype=np.int64)
    return torch.tensor(features), torch.tensor(labels)


def _evaluate_model(
    model: SmallMLP,
    features: torch.Tensor,
    labels: torch.Tensor,
    rows: list[dict[str, Any]],
    *,
    criterion: nn.Module,
    device: torch.device,
) -> EpochMetrics:
    model.eval()
    with torch.no_grad():
        logits = model(features.to(device))
        loss = criterion(logits, labels.to(device)).item()
        probabilities = torch.softmax(logits, dim=-1).cpu().numpy()
        predictions = np.argmax(probabilities, axis=1)
    y_true = labels.cpu().numpy()
    matrix = _confusion_matrix(y_true, predictions, len(SETUP_LABELS))
    precision, recall, f1_macro = _macro_metrics(matrix)
    accuracy = float(np.mean((y_true == predictions).astype(np.float32)))
    example_predictions = []
    for row, predicted_index, probability_row in zip(rows[:5], predictions[:5], probabilities[:5]):
        example_predictions.append(
            {
                "example_id": row["example_id"],
                "true_label": SETUP_LABELS[row["label_index"]],
                "predicted_label": SETUP_LABELS[int(predicted_index)],
                "confidence": round(float(np.max(probability_row)), 6),
                "image_path": row["image_path"],
            }
        )
    return EpochMetrics(
        train_loss=0.0,
        val_loss=float(loss),
        val_f1_macro=f1_macro,
        accuracy=accuracy,
        precision=precision,
        recall=recall,
        confusion=matrix,
        predictions=example_predictions,
        true_label_names=[SETUP_LABELS[int(index)] for index in y_true.tolist()],
        predicted_label_names=[SETUP_LABELS[int(index)] for index in predictions.tolist()],
    )


def train_mlp_classifier(
    examples: list[ChartExample],
    pseudo_labels: PseudoLabelResult,
    config: AppConfig,
    *,
    run: Any,
) -> dict[str, Any]:
    _require_torch()
    if hasattr(torch, "set_float32_matmul_precision"):
        torch.set_float32_matmul_precision("high")

    labeled_rows = _prepare_labeled_examples(examples, pseudo_labels)
    train_rows, val_rows = split_examples_by_time(
        [
            ChartExample(
                example_id=row["example_id"],
                image_path=Path(row["image_path"]),
                embedding=row["embedding"],
                text="",
                title=row["example_id"],
                source_type="phase1_train",
                time_index=row["time_index"],
                metadata={"label_index": row["label_index"]},
            )
            for row in labeled_rows
        ],
        validation_ratio=config.phase1.validation_ratio,
    )
    train_lookup = {row.example_id for row in train_rows}
    val_lookup = {row.example_id for row in val_rows}
    train_dataset_rows = [row for row in labeled_rows if row["example_id"] in train_lookup]
    val_dataset_rows = [row for row in labeled_rows if row["example_id"] in val_lookup]
    if not val_dataset_rows:
        raise RuntimeError("Validation split is empty; reduce the validation ratio or collect more labels.")

    train_features, train_labels = _tensorize(train_dataset_rows)
    val_features, val_labels = _tensorize(val_dataset_rows)
    device = _select_device()
    model = SmallMLP(config.active_embedding_dim, config.phase1.hidden_dim, config.phase1.dropout).to(device)
    if config.use_torch_compile and _can_use_torch_compile(device):
        try:
            model = torch.compile(model)  # type: ignore[assignment]
        except Exception:  # pragma: no cover - compile fallback is environment specific
            pass

    criterion = nn.CrossEntropyLoss(weight=_compute_class_weights(train_labels.numpy(), config).to(device))
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=config.phase1.learning_rate,
        weight_decay=config.phase1.weight_decay,
    )
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda" and config.mixed_precision)
    train_loader = DataLoader(
        TensorDataset(train_features, train_labels),
        batch_size=min(config.phase1.batch_size, len(train_dataset_rows)),
        shuffle=True,
    )

    results_tsv_path = config.root_dir / RESULTS_TSV_PATH
    results_tsv_path.write_text("epoch\ttrain_loss\tval_F1\tbest_F1\tnotes\n", encoding="utf-8")
    best_f1 = float("-inf")
    best_epoch = 0
    best_state: dict[str, Any] | None = None
    patience_counter = 0

    for epoch in range(1, config.phase1.max_epochs + 1):
        model.train()
        batch_losses: list[float] = []
        for batch_features, batch_labels in train_loader:
            batch_features = batch_features.to(device)
            batch_labels = batch_labels.to(device)
            optimizer.zero_grad(set_to_none=True)
            autocast_context = (
                torch.autocast(device_type="cuda", dtype=torch.float16)
                if device.type == "cuda" and config.mixed_precision
                else contextlib.nullcontext()
            )
            with autocast_context:
                logits = model(batch_features)
                loss = criterion(logits, batch_labels)
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            batch_losses.append(float(loss.item()))

        metrics = _evaluate_model(
            model,
            val_features,
            val_labels,
            val_dataset_rows,
            criterion=criterion,
            device=device,
        )
        metrics.train_loss = float(np.mean(batch_losses)) if batch_losses else 0.0

        note = ""
        if metrics.val_f1_macro > best_f1:
            best_f1 = metrics.val_f1_macro
            best_epoch = epoch
            patience_counter = 0
            note = "best"
            best_state = {
                "state_dict": model.state_dict(),
                "label_to_index": {label: index for index, label in enumerate(SETUP_LABELS)},
                "input_dim": config.active_embedding_dim,
                "hidden_dim": config.phase1.hidden_dim,
                "dropout": config.phase1.dropout,
                "config": config_to_dict(config),
                "training_artifacts": build_training_artifact_fingerprints(config),
            }
            checkpoint_path = config.root_dir / CHECKPOINT_PATH
            checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
            torch.save(best_state, checkpoint_path)
        else:
            patience_counter += 1
            note = f"patience={patience_counter}"

        run.log(
            {
                "epoch": epoch,
                "phase1/train_loss": metrics.train_loss,
                "phase1/val_loss": metrics.val_loss,
                "phase1/val_F1_macro": metrics.val_f1_macro,
                "phase1/accuracy": metrics.accuracy,
                "phase1/precision": metrics.precision,
                "phase1/recall": metrics.recall,
            }
        )
        try:
            import wandb

            run.log(
                {
                    "phase1/confusion_matrix": wandb.plot.confusion_matrix(
                        probs=None,
                        y_true=metrics.true_label_names,
                        preds=metrics.predicted_label_names,
                        class_names=list(SETUP_LABELS),
                    ),
                    "phase1/example_predictions": wandb.Table(
                        columns=["example_id", "true_label", "predicted_label", "confidence", "image_path"],
                        data=[
                            [
                                prediction["example_id"],
                                prediction["true_label"],
                                prediction["predicted_label"],
                                prediction["confidence"],
                                prediction["image_path"],
                            ]
                            for prediction in metrics.predictions
                        ],
                    ),
                }
            )
        except Exception:  # pragma: no cover - wandb plot helpers are optional
            pass

        with results_tsv_path.open("a", encoding="utf-8") as handle:
            handle.write(
                f"{epoch}\t{metrics.train_loss:.6f}\t{metrics.val_f1_macro:.6f}\t{best_f1:.6f}\t{note}\n"
            )

        if patience_counter >= config.phase1.patience:
            break

    if best_state is None:
        raise RuntimeError("Phase 1 training did not produce a best checkpoint.")

    report = {
        "best_epoch": best_epoch,
        "best_val_F1_macro": round(best_f1, 6),
        "train_example_count": len(train_dataset_rows),
        "val_example_count": len(val_dataset_rows),
        "checkpoint_path": str((config.root_dir / CHECKPOINT_PATH).resolve()),
        "results_tsv_path": str(results_tsv_path.resolve()),
    }
    (config.paths.results_dir / "phase1_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def load_mlp_checkpoint(checkpoint_path: Path, *, device: str | None = None) -> tuple[SmallMLP, dict[str, int], torch.device]:
    _require_torch()
    runtime_device = torch.device(device or _select_device())
    checkpoint = torch.load(checkpoint_path, map_location=runtime_device)
    model = SmallMLP(
        int(checkpoint["input_dim"]),
        int(checkpoint["hidden_dim"]),
        float(checkpoint["dropout"]),
    )
    model.load_state_dict(checkpoint["state_dict"])
    model.to(runtime_device)
    model.eval()
    return model, dict(checkpoint["label_to_index"]), runtime_device


def predict_mlp_probabilities(model: SmallMLP, embedding: np.ndarray, *, device: torch.device) -> dict[str, float]:
    _require_torch()
    with torch.no_grad():
        logits = model(torch.tensor(embedding, dtype=torch.float32).unsqueeze(0).to(device))
        probabilities = torch.softmax(logits, dim=-1).cpu().numpy()[0]
    return {label: float(probabilities[index]) for index, label in enumerate(SETUP_LABELS)}
