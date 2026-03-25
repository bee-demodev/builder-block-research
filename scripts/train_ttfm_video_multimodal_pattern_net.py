from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


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

import train_ttfm_visual_pattern_net as tvpn
import ttfm_brain_embeddings as tbe
import ttfm_video_embeddings as tve


DEFAULT_DATASET_PATH = ROOT / "results" / "ttfm_video_multimodal_dataset.jsonl"
DEFAULT_OUTPUT_DIR = ROOT / "results" / "neural_models" / "ttfm_video_multimodal"
DEFAULT_MODEL_NAME = "ttfm_video_multimodal_pattern_net"
DEFAULT_BRAIN_TYPE = "setup_scorer"


class MultimodalPatternNet(nn.Module):
    def __init__(
        self,
        *,
        output_dim: int,
        embedding_dim: int,
        modality_feature_dim: int = 3,
        branch_hidden_dim: int = 256,
        fusion_hidden_dim: int = 256,
    ) -> None:
        super().__init__()
        self.visual_projection = nn.Sequential(
            nn.Linear(embedding_dim, branch_hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.1),
        )
        self.transcript_projection = nn.Sequential(
            nn.Linear(embedding_dim, branch_hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.1),
        )
        self.audio_projection = nn.Sequential(
            nn.Linear(embedding_dim, branch_hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.1),
        )
        self.fusion = nn.Sequential(
            nn.Linear(branch_hidden_dim * 3 + modality_feature_dim, fusion_hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.15),
            nn.Linear(fusion_hidden_dim, fusion_hidden_dim // 2),
            nn.ReLU(),
        )
        self.classifier = nn.Linear(fusion_hidden_dim // 2, output_dim)
        self.calibration_head = nn.Sequential(
            nn.Linear(fusion_hidden_dim // 2, 64),
            nn.ReLU(),
            nn.Linear(64, 1),
        )

    def forward(
        self,
        visual_embeddings: torch.Tensor,
        transcript_embeddings: torch.Tensor,
        audio_embeddings: torch.Tensor,
        modality_features: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        visual_features = self.visual_projection(visual_embeddings)
        transcript_features = self.transcript_projection(transcript_embeddings)
        audio_features = self.audio_projection(audio_embeddings)
        fused = self.fusion(
            torch.cat(
                [visual_features, transcript_features, audio_features, modality_features],
                dim=1,
            )
        )
        return self.classifier(fused), self.calibration_head(fused)


def require_torch() -> None:
    if TORCH_IMPORT_ERROR is not None:
        raise RuntimeError("PyTorch is required for multimodal training.") from TORCH_IMPORT_ERROR


def load_multimodal_rows(dataset_path: Path) -> list[dict[str, Any]]:
    return tvpn.load_teacher_visual_rows(dataset_path)


def build_examples(
    rows: list[dict[str, Any]],
    *,
    label_to_index: dict[str, int],
    output_dimensionality: int = tve.DEFAULT_OUTPUT_DIMENSIONALITY,
    text_embedding_model: str = tve.DEFAULT_MODEL,
    visual_embedding_model: str = tve.DEFAULT_MULTIMODAL_MODEL,
    audio_understanding_model: str = tbe.DEFAULT_AUDIO_UNDERSTANDING_MODEL,
    visual_index_path: Path = tbe.DEFAULT_VISUAL_INDEX_PATH,
    audio_semantic_cache_path: Path = tbe.DEFAULT_AUDIO_SEMANTIC_CACHE_PATH,
    text_embedding_cache_path: Path = tbe.DEFAULT_TEXT_EMBEDDING_CACHE_PATH,
    text_embedder: tbe.TextEmbedder | None = None,
    visual_embedder: tbe.VisualEmbedder | None = None,
    audio_summarizer: tbe.AudioSummarizer | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    visual_index_lookup = tbe.load_embedding_lookup(visual_index_path)
    return tbe.build_examples_from_google_embeddings(
        rows,
        label_to_index=label_to_index,
        output_dimensionality=output_dimensionality,
        text_embedding_model=text_embedding_model,
        visual_embedding_model=visual_embedding_model,
        audio_understanding_model=audio_understanding_model,
        audio_semantic_cache_path=audio_semantic_cache_path,
        text_embedding_cache_path=text_embedding_cache_path,
        visual_index_lookup=visual_index_lookup,
        text_embedder=text_embedder,
        visual_embedder=visual_embedder,
        audio_summarizer=audio_summarizer,
    )


def build_tensors(
    examples: list[dict[str, Any]],
    *,
    device: str,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    require_torch()
    visual_embeddings = torch.tensor(
        [example["visual_embedding"] for example in examples],
        dtype=torch.float32,
        device=device,
    )
    transcript_embeddings = torch.tensor(
        [example["transcript_embedding"] for example in examples],
        dtype=torch.float32,
        device=device,
    )
    audio_embeddings = torch.tensor(
        [example["audio_semantic_embedding"] for example in examples],
        dtype=torch.float32,
        device=device,
    )
    modality_features = torch.tensor(
        [
            [
                1.0 if example.get("has_visual") else 0.0,
                1.0 if example.get("has_transcript") else 0.0,
                1.0 if example.get("has_audio_semantic") else 0.0,
            ]
            for example in examples
        ],
        dtype=torch.float32,
        device=device,
    )
    labels = torch.tensor(
        [example["target"] for example in examples],
        dtype=torch.float32,
        device=device,
    )
    weights = torch.tensor(
        [float(example.get("sample_weight", 1.0)) for example in examples],
        dtype=torch.float32,
        device=device,
    )
    return (
        visual_embeddings,
        transcript_embeddings,
        audio_embeddings,
        modality_features,
        labels,
        weights,
    )


def iter_minibatches(
    visual_embeddings: torch.Tensor,
    transcript_embeddings: torch.Tensor,
    audio_embeddings: torch.Tensor,
    modality_features: torch.Tensor,
    labels: torch.Tensor,
    sample_weights: torch.Tensor,
    *,
    batch_size: int,
) -> list[tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]]:
    batches: list[
        tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]
    ] = []
    for start in range(0, len(visual_embeddings), batch_size):
        end = start + batch_size
        batches.append(
            (
                visual_embeddings[start:end],
                transcript_embeddings[start:end],
                audio_embeddings[start:end],
                modality_features[start:end],
                labels[start:end],
                sample_weights[start:end],
            )
        )
    return batches


def reduce_weighted_scalar_loss(loss_vector: torch.Tensor, weights: torch.Tensor) -> torch.Tensor:
    total_weight = weights.sum()
    if float(total_weight.item()) <= 0.0:
        return loss_vector.mean()
    return torch.sum(loss_vector * weights) / total_weight


def calibration_targets(labels: torch.Tensor) -> torch.Tensor:
    return labels.mean(dim=1, keepdim=True)


def average_setup_confidence(calibration_logits: torch.Tensor) -> float:
    return float(torch.sigmoid(calibration_logits).mean().item())


def train_multimodal_classifier(
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
    embedding_dim: int = tve.DEFAULT_OUTPUT_DIMENSIONALITY,
    seed: int = 42,
    brain_type: str = DEFAULT_BRAIN_TYPE,
    framework_slug: str = "ttfm",
    profile_slug: str = "ttrades_curriculum",
    embedding_backend: str = "google_gemini",
) -> dict[str, Any]:
    require_torch()
    if not examples:
        raise ValueError("No multimodal examples were provided for training.")
    if not label_to_index:
        raise ValueError("Label space is empty; lower the min_positive_examples threshold.")

    device = tvpn.select_device(device_preference)
    random.seed(seed)
    torch.manual_seed(seed)
    if device == "cuda":
        torch.cuda.manual_seed_all(seed)

    train_examples, validation_examples = tvpn.split_examples(
        examples,
        validation_ratio=validation_ratio,
        seed=seed,
    )
    if not train_examples:
        raise ValueError("Training split is empty. Increase the dataset or reduce validation_ratio.")

    (
        train_visual_embeddings,
        train_transcript_embeddings,
        train_audio_embeddings,
        train_modality_features,
        train_labels,
        train_weights,
    ) = build_tensors(train_examples, device=device)
    if validation_examples:
        (
            validation_visual_embeddings,
            validation_transcript_embeddings,
            validation_audio_embeddings,
            validation_modality_features,
            validation_labels,
            validation_weights,
        ) = build_tensors(validation_examples, device=device)
    else:
        validation_visual_embeddings = None
        validation_transcript_embeddings = None
        validation_audio_embeddings = None
        validation_modality_features = None
        validation_labels = None
        validation_weights = None

    model = MultimodalPatternNet(
        output_dim=len(label_to_index),
        embedding_dim=embedding_dim,
    ).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    pos_weight = tvpn.compute_pos_weight(train_labels)
    label_criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight, reduction="none")
    calibration_criterion = nn.MSELoss(reduction="none")

    best_state = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}
    best_validation_loss = float("inf")
    best_validation_f1 = -1.0
    best_validation_recall = -1.0
    best_prediction_threshold = 0.5
    best_prediction_threshold_mode = "per_label"
    best_prediction_thresholds = [0.5] * len(label_to_index)
    best_epoch = 0
    training_history: list[dict[str, float | int | str]] = []

    for epoch in range(1, epochs + 1):
        model.train()
        batch_losses: list[float] = []
        batch_setup_confidences: list[float] = []
        for (
            batch_visual_embeddings,
            batch_transcript_embeddings,
            batch_audio_embeddings,
            batch_modality_features,
            batch_labels,
            batch_weights,
        ) in iter_minibatches(
            train_visual_embeddings,
            train_transcript_embeddings,
            train_audio_embeddings,
            train_modality_features,
            train_labels,
            train_weights,
            batch_size=batch_size,
        ):
            optimizer.zero_grad()
            label_logits, calibration_logits = model(
                batch_visual_embeddings,
                batch_transcript_embeddings,
                batch_audio_embeddings,
                batch_modality_features,
            )
            label_loss = tvpn.reduce_weighted_multilabel_loss(
                label_criterion(label_logits, batch_labels),
                batch_weights,
            )
            calibration_loss = reduce_weighted_scalar_loss(
                calibration_criterion(
                    torch.sigmoid(calibration_logits),
                    calibration_targets(batch_labels),
                ).squeeze(1),
                batch_weights,
            )
            loss = label_loss + (0.1 * calibration_loss)
            loss.backward()
            optimizer.step()
            batch_losses.append(float(loss.item()))
            batch_setup_confidences.append(average_setup_confidence(calibration_logits))

        model.eval()
        with torch.no_grad():
            if validation_visual_embeddings is None:
                selection_logits, selection_calibration_logits = model(
                    train_visual_embeddings,
                    train_transcript_embeddings,
                    train_audio_embeddings,
                    train_modality_features,
                )
                validation_loss_value = sum(batch_losses) / max(1, len(batch_losses))
                selection_labels = train_labels
                selection_weights = train_weights
                selection_setup_confidence = average_setup_confidence(selection_calibration_logits)
            else:
                selection_logits, selection_calibration_logits = model(
                    validation_visual_embeddings,
                    validation_transcript_embeddings,
                    validation_audio_embeddings,
                    validation_modality_features,
                )
                validation_loss_value = float(
                    tvpn.reduce_weighted_multilabel_loss(
                        label_criterion(selection_logits, validation_labels),
                        validation_weights,
                    ).item()
                )
                selection_labels = validation_labels
                selection_weights = validation_weights
                selection_setup_confidence = average_setup_confidence(selection_calibration_logits)

            epoch_thresholds, selection_metrics = tvpn.select_per_label_prediction_thresholds(
                selection_logits,
                selection_labels,
            )
            epoch_threshold = sum(epoch_thresholds) / max(1, len(epoch_thresholds))

        average_train_loss = sum(batch_losses) / max(1, len(batch_losses))
        training_history.append(
            {
                "epoch": epoch,
                "train_loss": average_train_loss,
                "validation_loss": validation_loss_value,
                "validation_micro_f1": selection_metrics["micro_f1"],
                "validation_micro_recall": selection_metrics["micro_recall"],
                "prediction_threshold": epoch_threshold,
                "prediction_threshold_mode": "per_label",
                "average_setup_confidence": selection_setup_confidence,
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
            best_prediction_thresholds = list(epoch_thresholds)
            best_epoch = epoch
            best_state = {
                key: value.detach().cpu().clone() for key, value in model.state_dict().items()
            }

    model.load_state_dict(best_state)
    model.to(device)
    model.eval()

    with torch.no_grad():
        final_train_logits, final_train_calibration_logits = model(
            train_visual_embeddings,
            train_transcript_embeddings,
            train_audio_embeddings,
            train_modality_features,
        )
        final_train_loss = float(
            tvpn.reduce_weighted_multilabel_loss(
                label_criterion(final_train_logits, train_labels),
                train_weights,
            ).item()
        )
        train_metrics = tvpn.compute_multilabel_metrics(
            logits=final_train_logits,
            labels=train_labels,
            loss_value=final_train_loss,
            threshold=best_prediction_thresholds,
        )
        train_metrics["average_setup_confidence"] = average_setup_confidence(
            final_train_calibration_logits
        )
        if validation_visual_embeddings is None:
            validation_metrics: dict[str, Any] = {}
        else:
            final_validation_logits, final_validation_calibration_logits = model(
                validation_visual_embeddings,
                validation_transcript_embeddings,
                validation_audio_embeddings,
                validation_modality_features,
            )
            final_validation_loss = float(
                tvpn.reduce_weighted_multilabel_loss(
                    label_criterion(final_validation_logits, validation_labels),
                    validation_weights,
                ).item()
            )
            validation_metrics = tvpn.compute_multilabel_metrics(
                logits=final_validation_logits,
                labels=validation_labels,
                loss_value=final_validation_loss,
                threshold=best_prediction_thresholds,
            )
            validation_metrics["average_setup_confidence"] = average_setup_confidence(
                final_validation_calibration_logits
            )

    output_dir.mkdir(parents=True, exist_ok=True)
    model_path = output_dir / f"{model_name}.pt"
    report_path = output_dir / f"{model_name}_report.json"
    prediction_thresholds_by_label = {
        label_name: float(best_prediction_thresholds[index])
        for label_name, index in label_to_index.items()
    }

    example_metadata = examples[0] if examples else {}
    artifact = {
        "model_name": model_name,
        "model_type": "GoogleEmbeddingFusionPatternNet",
        "brain_type": brain_type,
        "framework_slug": framework_slug,
        "profile_slug": profile_slug,
        "embedding_backend": embedding_backend,
        "visual_embedding_model": str(
            example_metadata.get("visual_embedding_model", tve.DEFAULT_MULTIMODAL_MODEL)
        ),
        "text_embedding_model": str(example_metadata.get("text_embedding_model", tve.DEFAULT_MODEL)),
        "audio_semantic_mode": str(
            example_metadata.get(
                "audio_semantic_mode_config",
                tbe.DEFAULT_AUDIO_UNDERSTANDING_MODEL,
            )
        ),
        "embedding_dim": embedding_dim,
        "label_to_index": label_to_index,
        "prediction_threshold": best_prediction_threshold,
        "prediction_threshold_mode": best_prediction_threshold_mode,
        "prediction_thresholds": prediction_thresholds_by_label,
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
        "brain_type": brain_type,
        "framework_slug": artifact["framework_slug"],
        "profile_slug": artifact["profile_slug"],
        "embedding_backend": artifact["embedding_backend"],
        "visual_embedding_model": artifact["visual_embedding_model"],
        "text_embedding_model": artifact["text_embedding_model"],
        "audio_semantic_mode": artifact["audio_semantic_mode"],
        "embedding_dim": embedding_dim,
        "example_count": len(examples),
        "train_example_count": len(train_examples),
        "validation_example_count": len(validation_examples),
        "label_space_size": len(label_to_index),
        "label_space": list(label_to_index.keys()),
        "label_counts": dict(sorted(label_counts.items())),
        "audio_enabled_example_count": sum(1 for example in examples if example.get("has_audio")),
        "audio_semantic_example_count": sum(
            1 for example in examples if example.get("has_audio_semantic")
        ),
        "text_enabled_example_count": sum(
            1 for example in examples if example.get("has_transcript")
        ),
        "train_pos_weight": {
            label_name: float(pos_weight[index].item())
            for label_name, index in label_to_index.items()
        },
        "best_epoch": best_epoch,
        "best_validation_loss": best_validation_loss,
        "best_validation_f1": best_validation_f1,
        "best_prediction_threshold": best_prediction_threshold,
        "best_prediction_threshold_mode": best_prediction_threshold_mode,
        "best_prediction_thresholds": prediction_thresholds_by_label,
        "epochs": epochs,
        "learning_rate": learning_rate,
        "batch_size": batch_size,
        "train_metrics": train_metrics,
        "validation_metrics": validation_metrics,
        "training_history": training_history,
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Train a Google-embedding-first TTFM multimodal pattern model from screenshots, "
            "transcript context, and audio semantic summaries."
        )
    )
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET_PATH))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--model-name", default=DEFAULT_MODEL_NAME)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--validation-ratio", type=float, default=0.2)
    parser.add_argument("--epochs", type=int, default=16)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--embedding-dim", type=int, default=tve.DEFAULT_OUTPUT_DIMENSIONALITY)
    parser.add_argument("--text-embedding-model", default=tve.DEFAULT_MODEL)
    parser.add_argument("--visual-embedding-model", default=tve.DEFAULT_MULTIMODAL_MODEL)
    parser.add_argument("--visual-index", default=str(tbe.DEFAULT_VISUAL_INDEX_PATH))
    parser.add_argument("--audio-understanding-model", default=tbe.DEFAULT_AUDIO_UNDERSTANDING_MODEL)
    parser.add_argument("--audio-semantic-cache", default=str(tbe.DEFAULT_AUDIO_SEMANTIC_CACHE_PATH))
    parser.add_argument("--text-embedding-cache", default=str(tbe.DEFAULT_TEXT_EMBEDDING_CACHE_PATH))
    parser.add_argument("--framework-slug", default="ttfm")
    parser.add_argument("--profile-slug", default="ttrades_curriculum")
    parser.add_argument("--brain-type", default=DEFAULT_BRAIN_TYPE)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--min-positive-examples", type=int, default=2)
    args = parser.parse_args()

    rows = load_multimodal_rows(Path(args.dataset))
    selected_labels, label_counts, skipped_labels = tvpn.select_label_space(
        rows,
        min_positive_examples=args.min_positive_examples,
    )
    label_to_index = {label: index for index, label in enumerate(selected_labels)}
    examples, skipped_examples, embedding_prep_report = build_examples(
        rows,
        label_to_index=label_to_index,
        output_dimensionality=args.embedding_dim,
        text_embedding_model=args.text_embedding_model,
        visual_embedding_model=args.visual_embedding_model,
        audio_understanding_model=args.audio_understanding_model,
        visual_index_path=Path(args.visual_index),
        audio_semantic_cache_path=Path(args.audio_semantic_cache),
        text_embedding_cache_path=Path(args.text_embedding_cache),
    )
    report = train_multimodal_classifier(
        examples,
        label_to_index=label_to_index,
        output_dir=Path(args.output_dir),
        model_name=args.model_name,
        device_preference=args.device,
        validation_ratio=args.validation_ratio,
        epochs=args.epochs,
        learning_rate=args.learning_rate,
        batch_size=args.batch_size,
        embedding_dim=args.embedding_dim,
        seed=args.seed,
        brain_type=args.brain_type,
        framework_slug=args.framework_slug,
        profile_slug=args.profile_slug,
    )

    report["dataset_path"] = str(Path(args.dataset).resolve())
    report["min_positive_examples"] = args.min_positive_examples
    report["raw_row_count"] = len(rows)
    report["selected_label_counts"] = {label: label_counts[label] for label in selected_labels}
    report["skipped_labels"] = skipped_labels
    report["skipped_examples"] = skipped_examples
    report["embedding_prep"] = embedding_prep_report

    report_path = Path(report["model_path"]).with_name(f"{args.model_name}_report.json")
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "model_path": report["model_path"],
                "report_path": str(report_path),
                "validation_micro_f1": report["validation_metrics"].get("micro_f1"),
                "prediction_threshold": report["best_prediction_threshold"],
                "example_count": report["example_count"],
                "embedding_backend": report["embedding_backend"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
