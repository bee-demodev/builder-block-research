from __future__ import annotations

import contextlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from config import AppConfig, config_to_dict
from data_loader import load_chart_corpus
from fractal_state import load_state_machine

try:
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset
except Exception as exc:  # pragma: no cover - import guard only
    torch = None
    nn = None
    TORCH_IMPORT_ERROR = exc
else:
    TORCH_IMPORT_ERROR = None


HEAD_FIELDS = (
    "path_family",
    "fractal_stage",
    "setup_quality",
    "entry_state",
    "htf_bias",
    "poi_type",
    "poi_direction",
)


@dataclass(slots=True)
class BundleTrainingRow:
    bundle_id: str
    case_key: str
    features: np.ndarray
    labels: dict[str, int]
    raw_labels: dict[str, str]


@dataclass(slots=True)
class PrototypeChartStateModel:
    label_spaces: dict[str, list[str]]
    centroids: dict[str, dict[str, np.ndarray]]


class MultiHeadChartStateMLP(nn.Module if nn is not None else object):
    def __init__(self, input_dim: int, hidden_dim: int, dropout: float, head_sizes: dict[str, int]) -> None:
        super().__init__()
        bottleneck = max(hidden_dim // 2, 16)
        self.backbone = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, bottleneck),
            nn.GELU(),
            nn.Dropout(dropout),
        )
        self.heads = nn.ModuleDict(
            {
                head_name: nn.Linear(bottleneck, head_size)
                for head_name, head_size in head_sizes.items()
            }
        )

    def forward(self, features: torch.Tensor) -> dict[str, torch.Tensor]:
        shared = self.backbone(features)
        return {
            head_name: head(shared)
            for head_name, head in self.heads.items()
        }


def _require_torch() -> None:
    if TORCH_IMPORT_ERROR is not None:
        raise RuntimeError("PyTorch is required for chart-state training.") from TORCH_IMPORT_ERROR


def _cosine_similarity(left: np.ndarray, right: np.ndarray) -> float:
    left_norm = float(np.linalg.norm(left))
    right_norm = float(np.linalg.norm(right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return float(np.dot(left, right) / (left_norm * right_norm))


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
    return True


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        cleaned = line.strip()
        if cleaned:
            rows.append(json.loads(cleaned))
    return rows


def _resolve_frame_path(root_dir: Path, raw_path: str) -> Path:
    candidate = Path(str(raw_path).strip())
    if candidate.is_absolute():
        return candidate.resolve()
    return (root_dir / candidate).resolve()


def _bundle_case_key(bundle_id: str) -> str:
    return bundle_id.split("::", 1)[0].strip() or bundle_id


def _load_label_spaces() -> dict[str, list[str]]:
    machine = load_state_machine()
    return {
        head_name: list(machine.enums[head_name])
        for head_name in HEAD_FIELDS
    }


def load_bundle_training_rows(config: AppConfig, bundle_seed_path: Path | None = None) -> tuple[list[BundleTrainingRow], dict[str, int]]:
    seed_path = bundle_seed_path or config.paths.phase2_bundle_gold_seed_path
    corpus = load_chart_corpus(config)
    embedding_lookup = {
        str(example.image_path.resolve()): example.embedding.astype(np.float32)
        for example in corpus.examples
    }
    label_spaces = _load_label_spaces()
    label_to_index = {
        head_name: {label: index for index, label in enumerate(labels)}
        for head_name, labels in label_spaces.items()
    }

    rows: list[BundleTrainingRow] = []
    skipped = {
        "missing_frames": 0,
        "invalid_labels": 0,
    }
    for payload in _read_jsonl(seed_path):
        try:
            frame_paths = [
                _resolve_frame_path(config.root_dir, str(payload["htf_frame_path"])),
                _resolve_frame_path(config.root_dir, str(payload["itf_frame_path"])),
                _resolve_frame_path(config.root_dir, str(payload["ltf_frame_path"])),
            ]
        except Exception:
            skipped["missing_frames"] += 1
            continue
        embeddings: list[np.ndarray] = []
        for frame_path in frame_paths:
            embedding = embedding_lookup.get(str(frame_path.resolve()))
            if embedding is None:
                embeddings = []
                break
            embeddings.append(embedding)
        if len(embeddings) != 3:
            skipped["missing_frames"] += 1
            continue

        raw_labels = {
            head_name: str(payload.get(head_name, "")).strip()
            for head_name in HEAD_FIELDS
        }
        if any(raw_labels[head_name] not in label_to_index[head_name] for head_name in HEAD_FIELDS):
            skipped["invalid_labels"] += 1
            continue

        rows.append(
            BundleTrainingRow(
                bundle_id=str(payload.get("bundle_id", "")).strip(),
                case_key=_bundle_case_key(str(payload.get("bundle_id", "")).strip()),
                features=np.concatenate(embeddings, axis=0).astype(np.float32),
                labels={
                    head_name: label_to_index[head_name][raw_labels[head_name]]
                    for head_name in HEAD_FIELDS
                },
                raw_labels=raw_labels,
            )
        )
    return rows, skipped


def _split_bundle_rows(rows: list[BundleTrainingRow], validation_ratio: float) -> tuple[list[BundleTrainingRow], list[BundleTrainingRow]]:
    case_keys = sorted({_bundle_case_key(row.bundle_id) for row in rows})
    if len(case_keys) <= 1 or validation_ratio <= 0.0:
        return rows, []
    validation_case_count = max(1, int(round(len(case_keys) * validation_ratio)))
    validation_case_count = min(validation_case_count, len(case_keys) - 1)
    validation_keys = set(case_keys[-validation_case_count:])
    train_rows = [row for row in rows if row.case_key not in validation_keys]
    val_rows = [row for row in rows if row.case_key in validation_keys]
    return train_rows, val_rows


def _evaluate_prototype_model(
    model: PrototypeChartStateModel,
    rows: list[BundleTrainingRow],
) -> dict[str, float]:
    head_accuracies: dict[str, float] = {}
    for head_name in HEAD_FIELDS:
        correct = 0
        total = 0
        for row in rows:
            centroids = model.centroids[head_name]
            scored = sorted(
                (
                    (_cosine_similarity(row.features, centroid), label)
                    for label, centroid in centroids.items()
                ),
                reverse=True,
            )
            if not scored:
                continue
            predicted_label = scored[0][1]
            if predicted_label == row.raw_labels[head_name]:
                correct += 1
            total += 1
        head_accuracies[head_name] = float(correct / total) if total else 0.0
    head_accuracies["macro_accuracy"] = float(np.mean(list(head_accuracies.values()))) if head_accuracies else 0.0
    return head_accuracies


def _train_prototype_chart_state_classifier(
    config: AppConfig,
    *,
    bundle_seed_path: Path | None = None,
) -> dict[str, Any]:
    label_spaces = _load_label_spaces()
    rows, skipped = load_bundle_training_rows(config, bundle_seed_path=bundle_seed_path)
    if len(rows) < (config.phase4.min_train_examples + config.phase4.min_val_examples):
        raise RuntimeError(
            f"Not enough bundle seed rows to train chart-state model. "
            f"Found {len(rows)} usable rows after skips {skipped}."
        )

    train_rows, val_rows = _split_bundle_rows(rows, config.phase4.validation_ratio)
    if len(train_rows) < config.phase4.min_train_examples or len(val_rows) < config.phase4.min_val_examples:
        raise RuntimeError(
            f"Chart-state split too small. train={len(train_rows)} val={len(val_rows)}."
        )

    centroids: dict[str, dict[str, np.ndarray]] = {}
    for head_name in HEAD_FIELDS:
        head_centroids: dict[str, np.ndarray] = {}
        for label_name in label_spaces[head_name]:
            label_rows = [row.features for row in train_rows if row.raw_labels[head_name] == label_name]
            if not label_rows:
                continue
            head_centroids[label_name] = np.mean(np.vstack(label_rows), axis=0).astype(np.float32)
        centroids[head_name] = head_centroids

    model = PrototypeChartStateModel(label_spaces=label_spaces, centroids=centroids)
    metrics = _evaluate_prototype_model(model, val_rows)
    checkpoint_payload = {
        "model_type": "prototype",
        "label_spaces": label_spaces,
        "centroids": {
            head_name: {
                label_name: centroid.tolist()
                for label_name, centroid in head_centroids.items()
            }
            for head_name, head_centroids in centroids.items()
        },
        "bundle_seed_path": str((bundle_seed_path or config.paths.phase2_bundle_gold_seed_path).resolve()),
        "config": config_to_dict(config),
    }
    config.paths.chart_state_checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    config.paths.chart_state_checkpoint_path.write_text(json.dumps(checkpoint_payload, indent=2), encoding="utf-8")
    config.paths.chart_state_results_tsv_path.write_text(
        "mode\tmacro_accuracy\nprototype\t{:.6f}\n".format(metrics["macro_accuracy"]),
        encoding="utf-8",
    )
    report = {
        "training_mode": "prototype_fallback",
        "best_epoch": 0,
        "best_val_macro_accuracy": round(metrics["macro_accuracy"], 6),
        "best_val_head_accuracy": {
            head_name: round(float(metric), 6)
            for head_name, metric in metrics.items()
        },
        "train_bundle_count": len(train_rows),
        "val_bundle_count": len(val_rows),
        "usable_bundle_count": len(rows),
        "skipped_rows": skipped,
        "bundle_seed_path": str((bundle_seed_path or config.paths.phase2_bundle_gold_seed_path).resolve()),
        "checkpoint_path": str(config.paths.chart_state_checkpoint_path.resolve()),
        "results_tsv_path": str(config.paths.chart_state_results_tsv_path.resolve()),
        "warnings": [f"PyTorch runtime unavailable, used prototype fallback: {TORCH_IMPORT_ERROR}"],
    }
    config.paths.phase4_report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def _tensorize(rows: list[BundleTrainingRow], label_spaces: dict[str, list[str]]) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
    features = np.vstack([row.features for row in rows]).astype(np.float32)
    labels = {
        head_name: torch.tensor([row.labels[head_name] for row in rows], dtype=torch.long)
        for head_name in label_spaces
    }
    return torch.tensor(features), labels


def _evaluate_model(
    model: MultiHeadChartStateMLP,
    features: torch.Tensor,
    labels: dict[str, torch.Tensor],
    *,
    device: torch.device,
) -> tuple[float, dict[str, float]]:
    model.eval()
    total_loss = 0.0
    head_accuracies: dict[str, float] = {}
    with torch.no_grad():
        logits = model(features.to(device))
        for head_name in HEAD_FIELDS:
            head_logits = logits[head_name]
            head_labels = labels[head_name].to(device)
            total_loss += float(nn.CrossEntropyLoss()(head_logits, head_labels).item())
            predictions = head_logits.argmax(dim=-1)
            accuracy = float((predictions == head_labels).float().mean().item())
            head_accuracies[head_name] = accuracy
    macro_accuracy = float(np.mean(list(head_accuracies.values()))) if head_accuracies else 0.0
    head_accuracies["macro_accuracy"] = macro_accuracy
    return total_loss / max(1, len(HEAD_FIELDS)), head_accuracies


def train_chart_state_classifier(
    config: AppConfig,
    *,
    bundle_seed_path: Path | None = None,
    run: Any | None = None,
) -> dict[str, Any]:
    if TORCH_IMPORT_ERROR is not None:
        return _train_prototype_chart_state_classifier(
            config,
            bundle_seed_path=bundle_seed_path,
        )
    _require_torch()
    label_spaces = _load_label_spaces()
    rows, skipped = load_bundle_training_rows(config, bundle_seed_path=bundle_seed_path)
    if len(rows) < (config.phase4.min_train_examples + config.phase4.min_val_examples):
        raise RuntimeError(
            f"Not enough bundle seed rows to train chart-state model. "
            f"Found {len(rows)} usable rows after skips {skipped}."
        )

    train_rows, val_rows = _split_bundle_rows(rows, config.phase4.validation_ratio)
    if len(train_rows) < config.phase4.min_train_examples or len(val_rows) < config.phase4.min_val_examples:
        raise RuntimeError(
            f"Chart-state split too small. train={len(train_rows)} val={len(val_rows)}."
        )

    train_features, train_labels = _tensorize(train_rows, label_spaces)
    val_features, val_labels = _tensorize(val_rows, label_spaces)

    device = _select_device()
    model = MultiHeadChartStateMLP(
        input_dim=train_features.shape[1],
        hidden_dim=config.phase4.hidden_dim,
        dropout=config.phase4.dropout,
        head_sizes={head_name: len(labels) for head_name, labels in label_spaces.items()},
    ).to(device)
    if config.use_torch_compile and _can_use_torch_compile(device):
        try:
            model = torch.compile(model)  # type: ignore[assignment]
        except Exception:
            pass

    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=config.phase4.learning_rate,
        weight_decay=config.phase4.weight_decay,
    )
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda" and config.mixed_precision)
    train_dataset = TensorDataset(
        train_features,
        *[train_labels[head_name] for head_name in HEAD_FIELDS],
    )
    train_loader = DataLoader(
        train_dataset,
        batch_size=min(config.phase4.batch_size, len(train_rows)),
        shuffle=True,
    )

    results_tsv_path = config.paths.chart_state_results_tsv_path
    results_tsv_path.write_text(
        "epoch\ttrain_loss\tval_loss\tmacro_accuracy\tbest_macro_accuracy\n",
        encoding="utf-8",
    )
    best_macro_accuracy = float("-inf")
    best_epoch = 0
    best_state: dict[str, Any] | None = None
    best_head_metrics: dict[str, float] = {}
    patience_counter = 0

    for epoch in range(1, config.phase4.max_epochs + 1):
        model.train()
        batch_losses: list[float] = []
        for batch in train_loader:
            batch_features = batch[0].to(device)
            batch_targets = {
                head_name: batch[index + 1].to(device)
                for index, head_name in enumerate(HEAD_FIELDS)
            }
            optimizer.zero_grad(set_to_none=True)
            autocast_context = (
                torch.autocast(device_type="cuda", dtype=torch.float16)
                if device.type == "cuda" and config.mixed_precision
                else contextlib.nullcontext()
            )
            with autocast_context:
                logits = model(batch_features)
                loss = sum(
                    nn.CrossEntropyLoss()(logits[head_name], batch_targets[head_name])
                    for head_name in HEAD_FIELDS
                ) / len(HEAD_FIELDS)
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            batch_losses.append(float(loss.item()))

        val_loss, val_head_metrics = _evaluate_model(
            model,
            val_features,
            val_labels,
            device=device,
        )
        train_loss = float(np.mean(batch_losses)) if batch_losses else 0.0
        macro_accuracy = val_head_metrics["macro_accuracy"]

        if run is not None:
            run.log(
                {
                    "epoch": epoch,
                    "phase4/train_loss": train_loss,
                    "phase4/val_loss": val_loss,
                    "phase4/macro_accuracy": macro_accuracy,
                    **{
                        f"phase4/{head_name}_accuracy": accuracy
                        for head_name, accuracy in val_head_metrics.items()
                    },
                }
            )

        note = ""
        if macro_accuracy > best_macro_accuracy:
            best_macro_accuracy = macro_accuracy
            best_epoch = epoch
            patience_counter = 0
            best_head_metrics = dict(val_head_metrics)
            note = "best"
            best_state = {
                "state_dict": model.state_dict(),
                "input_dim": int(train_features.shape[1]),
                "hidden_dim": config.phase4.hidden_dim,
                "dropout": config.phase4.dropout,
                "label_spaces": label_spaces,
                "config": config_to_dict(config),
                "bundle_seed_path": str((bundle_seed_path or config.paths.phase2_bundle_gold_seed_path).resolve()),
            }
            config.paths.chart_state_checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
            torch.save(best_state, config.paths.chart_state_checkpoint_path)
        else:
            patience_counter += 1
            note = f"patience={patience_counter}"

        with results_tsv_path.open("a", encoding="utf-8") as handle:
            handle.write(
                f"{epoch}\t{train_loss:.6f}\t{val_loss:.6f}\t{macro_accuracy:.6f}\t{max(best_macro_accuracy, macro_accuracy):.6f}\t{note}\n"
            )

        if patience_counter >= config.phase4.patience:
            break

    if best_state is None:
        raise RuntimeError("Chart-state training did not produce a checkpoint.")

    report = {
        "best_epoch": best_epoch,
        "best_val_macro_accuracy": round(best_macro_accuracy, 6),
        "best_val_head_accuracy": {
            head_name: round(float(metric), 6)
            for head_name, metric in best_head_metrics.items()
        },
        "train_bundle_count": len(train_rows),
        "val_bundle_count": len(val_rows),
        "usable_bundle_count": len(rows),
        "skipped_rows": skipped,
        "bundle_seed_path": str((bundle_seed_path or config.paths.phase2_bundle_gold_seed_path).resolve()),
        "checkpoint_path": str(config.paths.chart_state_checkpoint_path.resolve()),
        "results_tsv_path": str(results_tsv_path.resolve()),
    }
    config.paths.phase4_report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def load_chart_state_checkpoint(checkpoint_path: Path, *, device: str | None = None) -> tuple[Any, dict[str, list[str]], Any]:
    checkpoint_path = Path(checkpoint_path)
    checkpoint_text = checkpoint_path.read_text(encoding="utf-8")
    if checkpoint_text.lstrip().startswith("{"):
        payload = json.loads(checkpoint_text)
        if payload.get("model_type") == "prototype":
            label_spaces = {str(key): list(value) for key, value in payload["label_spaces"].items()}
            model = PrototypeChartStateModel(
                label_spaces=label_spaces,
                centroids={
                    head_name: {
                        label_name: np.asarray(vector, dtype=np.float32)
                        for label_name, vector in head_centroids.items()
                    }
                    for head_name, head_centroids in payload["centroids"].items()
                },
            )
            return model, label_spaces, None
    _require_torch()
    runtime_device = torch.device(device or _select_device())
    checkpoint = torch.load(checkpoint_path, map_location=runtime_device)
    label_spaces = {str(key): list(value) for key, value in checkpoint["label_spaces"].items()}
    model = MultiHeadChartStateMLP(
        input_dim=int(checkpoint["input_dim"]),
        hidden_dim=int(checkpoint["hidden_dim"]),
        dropout=float(checkpoint["dropout"]),
        head_sizes={head_name: len(labels) for head_name, labels in label_spaces.items()},
    )
    model.load_state_dict(checkpoint["state_dict"])
    model.to(runtime_device)
    model.eval()
    return model, label_spaces, runtime_device


def predict_chart_state_probabilities(
    model: Any,
    features: np.ndarray,
    *,
    label_spaces: dict[str, list[str]],
    device: Any,
) -> dict[str, dict[str, float]]:
    if isinstance(model, PrototypeChartStateModel):
        predictions: dict[str, dict[str, float]] = {}
        for head_name, centroids in model.centroids.items():
            scored = [
                (_cosine_similarity(features, centroid), label_name)
                for label_name, centroid in centroids.items()
            ]
            if not scored:
                predictions[head_name] = {
                    label_name: 0.0
                    for label_name in label_spaces[head_name]
                }
                continue
            scores = np.asarray([score for score, _label_name in scored], dtype=np.float32)
            scores = np.exp(scores - np.max(scores))
            probabilities = scores / max(float(scores.sum()), 1e-6)
            predictions[head_name] = {
                label_name: 0.0
                for label_name in label_spaces[head_name]
            }
            for probability, (_score, label_name) in zip(probabilities.tolist(), scored):
                predictions[head_name][label_name] = float(probability)
        return predictions
    _require_torch()
    with torch.no_grad():
        logits = model(torch.tensor(features, dtype=torch.float32).unsqueeze(0).to(device))
    predictions: dict[str, dict[str, float]] = {}
    for head_name, head_logits in logits.items():
        probs = torch.softmax(head_logits, dim=-1).cpu().numpy()[0]
        predictions[head_name] = {
            label_spaces[head_name][index]: float(probability)
            for index, probability in enumerate(probs)
        }
    return predictions
