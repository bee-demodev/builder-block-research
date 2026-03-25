from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import torch

from export_model_training_surface import build_training_text, flatten_strings, normalize_token
from train_narrow_pattern_net import TextMLP, select_device, tokenize_text, vectorize_text


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODEL_DIR = ROOT / "results" / "neural_models"


def sorted_normalized_tokens(value: object) -> list[str]:
    return sorted(
        {
            normalize_token(item)
            for item in flatten_strings(value)
            if str(item).strip()
        }
    )


def build_inference_text(state: dict[str, Any]) -> str:
    chart_context = state.get("chart_context") or {}
    annotation = state.get("annotation") or {}
    setup_variant = str(
        state.get("setup_variant")
        or chart_context.get("setup_variant")
        or chart_context.get("pattern_variant")
        or ""
    )
    profile_slug = str(state.get("profile_slug", "")).strip()
    topic = str(state.get("topic", "")).strip()
    trade_model = str(
        state.get("trade_model")
        or state.get("task_name")
        or state.get("model_task")
        or ""
    ).strip()
    relation_type = str(state.get("relation_type", "")).strip()

    chart_context_tokens = sorted_normalized_tokens(chart_context)
    annotation_tokens = sorted_normalized_tokens(annotation)

    parts = [
        f"profile {profile_slug}" if profile_slug else "",
        f"topic {topic}" if topic else "",
        f"trade model {trade_model}" if trade_model else "",
        f"relation {relation_type}" if relation_type else "",
        f"setup {normalize_token(setup_variant)}" if setup_variant else "",
        f"context {' '.join(chart_context_tokens)}" if chart_context_tokens else "",
        f"annotation {' '.join(annotation_tokens)}" if annotation_tokens else "",
    ]
    return build_training_text(parts)


def default_model_path(task_name: str) -> Path:
    return DEFAULT_MODEL_DIR / f"{task_name}.pt"


def load_model_bundle(
    model_path: Path,
    *,
    device_preference: str = "auto",
) -> dict[str, Any]:
    device = select_device(device_preference)
    artifact = torch.load(model_path, map_location=device, weights_only=False)
    vocabulary = dict(artifact["vocabulary"])
    hidden_dim = int(artifact["hidden_dim"])
    model = TextMLP(input_dim=len(vocabulary), hidden_dim=hidden_dim)
    model.load_state_dict(artifact["state_dict"])
    model.to(device)
    model.eval()
    return {
        "task_name": artifact["task_name"],
        "positive_label": artifact["positive_label"],
        "negative_label": artifact["negative_label"],
        "vocabulary": vocabulary,
        "model": model,
        "device": device,
    }


def build_signal_payload(
    *,
    state: dict[str, Any],
    task_name: str,
    probability: float,
    threshold: float,
) -> dict[str, Any] | None:
    candidate_signal = state.get("candidate_signal")
    if not isinstance(candidate_signal, dict):
        return None
    if probability < threshold:
        return None

    signal = dict(candidate_signal)
    signal["model_task"] = task_name
    signal["model_score"] = round(float(probability), 6)
    signal["threshold"] = threshold
    thesis = str(signal.get("thesis", "")).strip()
    if thesis:
        signal["thesis"] = f"{thesis} | {task_name}={probability:.4f}"
    else:
        signal["thesis"] = f"{task_name}={probability:.4f}"
    return signal


def score_pattern_state(
    state: dict[str, Any],
    *,
    model_path: Path,
    device_preference: str = "auto",
    threshold: float = 0.5,
) -> dict[str, Any]:
    bundle = load_model_bundle(model_path, device_preference=device_preference)
    inference_text = build_inference_text(state)
    vocabulary = bundle["vocabulary"]
    tokens = tokenize_text(inference_text)
    feature_vector = vectorize_text(inference_text, vocabulary)
    matched_vocabulary_token_count = sum(1 for token in tokens if token in vocabulary)

    features = torch.tensor(
        [feature_vector],
        dtype=torch.float32,
        device=bundle["device"],
    )
    with torch.no_grad():
        probability = float(torch.sigmoid(bundle["model"](features)).item())
    prediction = probability >= threshold
    signal = build_signal_payload(
        state=state,
        task_name=bundle["task_name"],
        probability=probability,
        threshold=threshold,
    )

    return {
        "task_name": bundle["task_name"],
        "device": bundle["device"],
        "probability": probability,
        "prediction": prediction,
        "threshold": threshold,
        "input_text": inference_text,
        "input_token_count": len(tokens),
        "matched_vocabulary_token_count": matched_vocabulary_token_count,
        "vocabulary_size": len(vocabulary),
        "positive_label": bundle["positive_label"],
        "negative_label": bundle["negative_label"],
        "signal": signal,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Score a structured chart-state payload against a trained narrow pattern model "
            "and optionally emit a runtime-compatible signal candidate."
        )
    )
    parser.add_argument("--state-json", required=True)
    parser.add_argument("--task-name")
    parser.add_argument("--model-path")
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda", "mps"])
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--output", default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    state = json.loads(Path(args.state_json).read_text(encoding="utf-8"))
    model_path = Path(args.model_path) if args.model_path else default_model_path(str(args.task_name))
    scored = score_pattern_state(
        state,
        model_path=model_path,
        device_preference=args.device,
        threshold=args.threshold,
    )

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(scored, indent=2), encoding="utf-8")

    print(json.dumps(scored, indent=2))


if __name__ == "__main__":
    main()
