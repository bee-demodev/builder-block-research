from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import train_ttfm_video_multimodal_pattern_net as tmvpn
import train_ttfm_visual_pattern_net as tvpn
import ttfm_brain_embeddings as tbe
import ttfm_video_embeddings as tve


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATASET_PATH = ROOT / "results" / "ttfm_video_multimodal_dataset.jsonl"
DEFAULT_MODEL_PATH = (
    ROOT
    / "results"
    / "neural_models"
    / "ttfm_blended_multimodal"
    / "ttfm_blended_multimodal_pattern_net.pt"
)
DEFAULT_OUTPUT = ROOT / "results" / "ttfm_multimodal_review_queue.json"

PROMOTABLE_REVIEW_STATUSES = {
    "approved_for_teacher",
    "teacher_approved",
    "promoted_to_teacher",
}
BLOCKED_CONTRADICTION_STATUSES = {
    "blocked",
    "contradiction_confirmed",
    "needs_reconciliation",
}
CHECKPOINT_WEIGHTS = {
    "confirmation": 18,
    "closure": 15,
    "sweep": 10,
    "outcome": 8,
    "context": 6,
}


def load_jsonl_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return tmvpn.load_multimodal_rows(path)


def normalize_string_list(values: object) -> list[str]:
    if values is None:
        return []
    if isinstance(values, list):
        return [str(value).strip() for value in values if str(value).strip()]
    if isinstance(values, str):
        cleaned = values.strip()
        return [cleaned] if cleaned else []
    return []


def normalize_probability_map(value: object) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, float] = {}
    for label, score in value.items():
        label_name = str(label).strip()
        if not label_name:
            continue
        try:
            normalized[label_name] = float(score)
        except (TypeError, ValueError):
            continue
    return normalized


def normalize_threshold_config(value: object) -> float | dict[str, float]:
    if isinstance(value, dict):
        normalized: dict[str, float] = {}
        for label, threshold in value.items():
            label_name = str(label).strip()
            if not label_name:
                continue
            try:
                normalized[label_name] = float(threshold)
            except (TypeError, ValueError):
                continue
        if normalized:
            return normalized
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.5


def threshold_for_label(
    threshold: float | dict[str, float],
    *,
    label_name: str,
) -> float:
    if isinstance(threshold, dict):
        return float(threshold.get(label_name, 0.5))
    return float(threshold)


def threshold_reference_value(
    threshold: float | dict[str, float],
    *,
    preferred_labels: list[str],
) -> float:
    if not isinstance(threshold, dict):
        return float(threshold)

    values = [
        float(threshold[label_name])
        for label_name in preferred_labels
        if label_name in threshold
    ]
    if not values:
        values = [float(value) for value in threshold.values()]
    if not values:
        return 0.5
    return sum(values) / float(len(values))


def sorted_labels_by_probability(label_probabilities: dict[str, float]) -> list[str]:
    return [
        label
        for label, _score in sorted(
            label_probabilities.items(),
            key=lambda item: (-item[1], item[0]),
        )
    ]


def top_predicted_labels(
    label_probabilities: dict[str, float],
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    items = sorted(
        label_probabilities.items(),
        key=lambda item: (-item[1], item[0]),
    )[:limit]
    return [{"label": label, "probability": round(score, 6)} for label, score in items]


def summarize_prediction_alignment(
    row: dict[str, Any],
    *,
    label_probabilities: dict[str, float],
    threshold: float | dict[str, float],
) -> dict[str, Any]:
    weak_labels = sorted(set(normalize_string_list(row.get("active_labels"))))
    predicted_labels = [
        label
        for label in sorted_labels_by_probability(label_probabilities)
        if label_probabilities[label] >= threshold_for_label(threshold, label_name=label)
    ]
    weak_label_set = set(weak_labels)
    predicted_label_set = set(predicted_labels)

    shared_labels = sorted(weak_label_set & predicted_label_set)
    missing_weak_labels = sorted(weak_label_set - predicted_label_set)
    extra_predicted_labels = sorted(predicted_label_set - weak_label_set)
    union = weak_label_set | predicted_label_set
    label_jaccard = (
        float(len(shared_labels)) / float(len(union))
        if union
        else 1.0
    )

    weak_label_support_score = (
        sum(label_probabilities.get(label, 0.0) for label in weak_labels) / float(len(weak_labels))
        if weak_labels
        else 0.0
    )
    predicted_label_support_score = (
        sum(label_probabilities.get(label, 0.0) for label in predicted_labels)
        / float(len(predicted_labels))
        if predicted_labels
        else 0.0
    )
    uncertainty_labels = sorted(
        (
            label
            for label, score in label_probabilities.items()
            if abs(score - threshold_for_label(threshold, label_name=label)) <= 0.1
        ),
        key=lambda label: (
            abs(
                label_probabilities[label]
                - threshold_for_label(threshold, label_name=label)
            ),
            label,
        ),
    )
    reference_threshold = threshold_reference_value(
        threshold,
        preferred_labels=weak_labels,
    )

    return {
        "weak_labels": weak_labels,
        "predicted_labels": predicted_labels,
        "shared_labels": shared_labels,
        "missing_weak_labels": missing_weak_labels,
        "extra_predicted_labels": extra_predicted_labels,
        "label_jaccard": label_jaccard,
        "disagreement_count": len(missing_weak_labels) + len(extra_predicted_labels),
        "weak_label_support_score": weak_label_support_score,
        "predicted_label_support_score": predicted_label_support_score,
        "uncertainty_count": len(uncertainty_labels),
        "uncertainty_labels": uncertainty_labels[:5],
        "top_predicted_labels": top_predicted_labels(label_probabilities),
        "reference_threshold": reference_threshold,
    }


def classify_recommended_action(
    row: dict[str, Any],
    *,
    alignment: dict[str, Any],
    prediction_status: str,
    threshold: float | dict[str, float],
) -> str:
    review_status = str(row.get("review_status", "")).strip() or "unknown"
    contradiction_status = str(row.get("contradiction_status", "")).strip() or "unknown"
    screenshot_path = str(row.get("screenshot_path", "")).strip()

    if not screenshot_path:
        return "skip_missing_frame"
    if contradiction_status in BLOCKED_CONTRADICTION_STATUSES:
        return "resolve_contradiction_before_review"
    if not alignment["weak_labels"]:
        return "collect_more_multimodal_evidence"
    if prediction_status != "scored":
        return "collect_more_multimodal_evidence"
    if alignment["disagreement_count"] > 0:
        return "review_model_disagreement"
    if (
        review_status in PROMOTABLE_REVIEW_STATUSES
        and alignment["label_jaccard"] >= 0.999
        and alignment["weak_label_support_score"] >= max(0.7, alignment["reference_threshold"] + 0.2)
    ):
        return "promote_into_teacher_surface"
    if alignment["weak_label_support_score"] < alignment["reference_threshold"]:
        return "collect_more_multimodal_evidence"
    return "review_for_teacher_promotion"


def compute_priority_score(
    row: dict[str, Any],
    *,
    alignment: dict[str, Any],
    recommended_action: str,
) -> tuple[int, list[str]]:
    checkpoint = str(row.get("checkpoint", "")).strip() or "unknown"
    evidence_refs = normalize_string_list(row.get("evidence_refs"))
    sample_weight = float(
        row.get("sample_weight", row.get("weak_label_confidence", 0.35)) or 0.35
    )

    action_base = {
        "review_model_disagreement": 90,
        "resolve_contradiction_before_review": 75,
        "promote_into_teacher_surface": 50,
        "review_for_teacher_promotion": 45,
        "collect_more_multimodal_evidence": 30,
        "skip_missing_frame": 0,
    }.get(recommended_action, 0)
    checkpoint_bonus = CHECKPOINT_WEIGHTS.get(checkpoint, 4)
    disagreement_bonus = min(int(alignment["disagreement_count"]), 4) * 6
    uncertainty_bonus = min(int(alignment["uncertainty_count"]), 3) * 3
    evidence_bonus = min(len(evidence_refs), 3) * 2
    sample_weight_bonus = int(round(max(0.0, sample_weight) * 10))

    score = (
        action_base
        + checkpoint_bonus
        + disagreement_bonus
        + uncertainty_bonus
        + evidence_bonus
        + sample_weight_bonus
    )
    reasons = [
        f"action:{recommended_action}",
        f"checkpoint:{checkpoint}",
        f"jaccard:{alignment['label_jaccard']:.2f}",
        f"disagreement:{alignment['disagreement_count']}",
        f"weak_support:{alignment['weak_label_support_score']:.2f}",
    ]
    if alignment["uncertainty_count"]:
        reasons.append(f"uncertain_labels:{alignment['uncertainty_count']}")
    return score, reasons


def classify_priority_band(score: int) -> str:
    if score >= 90:
        return "high"
    if score >= 60:
        return "medium"
    return "low"


def build_queue_item(
    row: dict[str, Any],
    *,
    prediction_entry: dict[str, Any] | None,
    threshold: float | dict[str, float],
) -> dict[str, Any]:
    label_probabilities = normalize_probability_map(
        (prediction_entry or {}).get("label_probabilities")
    )
    prediction_status = "scored" if label_probabilities else "unscored"
    alignment = summarize_prediction_alignment(
        row,
        label_probabilities=label_probabilities,
        threshold=threshold,
    )
    recommended_action = classify_recommended_action(
        row,
        alignment=alignment,
        prediction_status=prediction_status,
        threshold=threshold,
    )
    priority_score, priority_reasons = compute_priority_score(
        row,
        alignment=alignment,
        recommended_action=recommended_action,
    )

    transcript_text = str(row.get("transcript_text", "") or "").strip()
    audio_path = str(row.get("audio_path", "") or "").strip()
    screenshot_path = str(row.get("screenshot_path", "") or "").strip()
    return {
        "example_id": str(row.get("example_id", "")).strip(),
        "case_ref": str(row.get("case_ref", "")).strip(),
        "video_slug": str(row.get("video_slug", "")).strip() or None,
        "title": str(row.get("title", "")).strip() or None,
        "checkpoint": str(row.get("checkpoint", "")).strip() or "unknown",
        "corpus_partition": str(row.get("corpus_partition", "seed_curriculum")).strip()
        or "seed_curriculum",
        "review_categories": normalize_string_list(row.get("review_categories")),
        "framework_slug": str(row.get("framework_slug", "ttfm")).strip() or "ttfm",
        "profile_slug": str(row.get("profile_slug", "ttrades_curriculum")).strip()
        or "ttrades_curriculum",
        "brain_type": str(row.get("brain_type", "setup_scorer")).strip() or "setup_scorer",
        "embedding_backend": str(
            (prediction_entry or {}).get("embedding_backend", row.get("embedding_backend", "google_gemini"))
        ).strip()
        or "google_gemini",
        "weak_active_labels": alignment["weak_labels"],
        "predicted_labels": alignment["predicted_labels"],
        "label_probabilities": {
            label: round(float(score), 6)
            for label, score in sorted(label_probabilities.items())
        },
        "top_predicted_labels": alignment["top_predicted_labels"],
        "missing_weak_labels": alignment["missing_weak_labels"],
        "extra_predicted_labels": alignment["extra_predicted_labels"],
        "label_jaccard": round(float(alignment["label_jaccard"]), 6),
        "weak_label_support_score": round(float(alignment["weak_label_support_score"]), 6),
        "predicted_label_support_score": round(
            float(alignment["predicted_label_support_score"]),
            6,
        ),
        "disagreement_count": int(alignment["disagreement_count"]),
        "uncertainty_count": int(alignment["uncertainty_count"]),
        "uncertainty_labels": alignment["uncertainty_labels"],
        "weak_label_confidence": float(row.get("weak_label_confidence", 0.35) or 0.35),
        "sample_weight": float(row.get("sample_weight", 0.35) or 0.35),
        "review_status": str(row.get("review_status", "")).strip() or "unknown",
        "contradiction_status": str(row.get("contradiction_status", "")).strip() or "unknown",
        "has_audio": bool(audio_path),
        "has_text": bool(transcript_text),
        "audio_path": audio_path or None,
        "screenshot_path": screenshot_path or None,
        "evidence_refs": normalize_string_list(row.get("evidence_refs")),
        "prediction_status": prediction_status,
        "prediction_threshold": round(float(alignment["reference_threshold"]), 6),
        "prediction_threshold_mode": "per_label" if isinstance(threshold, dict) else "global",
        "prediction_thresholds": threshold if isinstance(threshold, dict) else None,
        "recommended_action": recommended_action,
        "priority_score": priority_score,
        "priority_band": classify_priority_band(priority_score),
        "priority_reasons": priority_reasons,
    }


def build_multimodal_review_queue(
    rows: list[dict[str, Any]],
    *,
    predictions_by_example_id: dict[str, dict[str, Any]],
    threshold: float | dict[str, float],
) -> dict[str, Any]:
    items = [
        build_queue_item(
            row,
            prediction_entry=predictions_by_example_id.get(str(row.get("example_id", "")).strip()),
            threshold=threshold,
        )
        for row in rows
    ]
    items.sort(
        key=lambda item: (
            -int(item["priority_score"]),
            str(item["checkpoint"]),
            str(item["example_id"]),
        )
    )

    action_counts: Counter[str] = Counter()
    priority_band_counts: Counter[str] = Counter()
    disagreement_count = 0
    disagreement_total = 0
    reviewed_precision_total = 0.0
    reviewed_count = 0
    for item in items:
        action_counts[str(item["recommended_action"])] += 1
        priority_band_counts[str(item["priority_band"])] += 1
        if int(item["disagreement_count"]) > 0:
            disagreement_count += 1
        disagreement_total += int(item["disagreement_count"])
        if str(item.get("review_status", "")) in PROMOTABLE_REVIEW_STATUSES:
            reviewed_precision_total += float(item.get("label_jaccard", 0.0))
            reviewed_count += 1

    review_candidate_count = sum(
        action_counts.get(action, 0)
        for action in (
            "review_model_disagreement",
            "review_for_teacher_promotion",
            "collect_more_multimodal_evidence",
        )
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "row_count": len(items),
            "ready_to_promote_count": action_counts.get("promote_into_teacher_surface", 0),
            "review_candidate_count": review_candidate_count,
            "blocked_contradiction_count": action_counts.get(
                "resolve_contradiction_before_review",
                0,
            ),
            "model_disagreement_count": disagreement_count,
            "mean_disagreement_count": round(
                float(disagreement_total) / float(len(items)) if items else 0.0,
                6,
            ),
            "reviewed_row_count": reviewed_count,
            "reviewed_alignment_precision": round(
                reviewed_precision_total / float(reviewed_count) if reviewed_count else 0.0,
                6,
            ),
            "recommended_action_counts": dict(sorted(action_counts.items())),
            "priority_band_counts": dict(sorted(priority_band_counts.items())),
        },
        "items": items,
    }


def load_model_artifact(model_path: Path) -> dict[str, Any]:
    tmvpn.require_torch()
    try:
        return tmvpn.torch.load(model_path, map_location="cpu", weights_only=False)
    except TypeError:
        return tmvpn.torch.load(model_path, map_location="cpu")


def score_multimodal_rows(
    rows: list[dict[str, Any]],
    *,
    model_path: Path,
    device_preference: str = "auto",
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    tmvpn.require_torch()
    artifact = load_model_artifact(model_path)
    label_to_index = {
        str(label): int(index) for label, index in dict(artifact.get("label_to_index", {})).items()
    }
    if not label_to_index:
        raise ValueError(f"Model artifact at {model_path} did not include label_to_index.")

    examples, skipped_examples, embedding_prep_report = tmvpn.build_examples(
        rows,
        label_to_index=label_to_index,
        output_dimensionality=int(artifact.get("embedding_dim", 768) or 768),
        text_embedding_model=str(artifact.get("text_embedding_model", tve.DEFAULT_MODEL)),
        visual_embedding_model=str(
            artifact.get("visual_embedding_model", tve.DEFAULT_MULTIMODAL_MODEL)
        ),
        audio_understanding_model=str(
            artifact.get("audio_semantic_mode", tbe.DEFAULT_AUDIO_UNDERSTANDING_MODEL)
        ),
    )
    if not examples:
        return {}, {
            "prediction_threshold": normalize_threshold_config(
                artifact.get("prediction_thresholds", artifact.get("prediction_threshold", 0.5))
            ),
            "skipped_examples": skipped_examples,
            "embedding_prep": embedding_prep_report,
        }

    device = tvpn.select_device(device_preference)
    model = tmvpn.MultimodalPatternNet(
        output_dim=len(label_to_index),
        embedding_dim=int(artifact.get("embedding_dim", 768) or 768),
    )
    model.load_state_dict(dict(artifact["state_dict"]))
    model.to(device)
    model.eval()

    visual_embeddings, transcript_embeddings, audio_embeddings, modalities, _labels, _weights = tmvpn.build_tensors(
        examples,
        device=device,
    )

    with tmvpn.torch.no_grad():
        logits, calibration_logits = model(
            visual_embeddings,
            transcript_embeddings,
            audio_embeddings,
            modalities,
        )
        probabilities = tmvpn.torch.sigmoid(logits).detach().cpu()
        setup_confidences = tmvpn.torch.sigmoid(calibration_logits).detach().cpu()

    sorted_labels = sorted(label_to_index.items(), key=lambda item: item[1])
    predictions_by_example_id: dict[str, dict[str, Any]] = {}
    for example, row_scores, setup_confidence in zip(examples, probabilities, setup_confidences):
        label_probabilities = {
            label_name: float(row_scores[index].item())
            for label_name, index in sorted_labels
        }
        predictions_by_example_id[str(example.get("example_id", ""))] = {
            "label_probabilities": label_probabilities,
            "setup_confidence": float(setup_confidence.item()),
            "embedding_backend": str(artifact.get("embedding_backend", "google_gemini")),
        }

    return predictions_by_example_id, {
        "prediction_threshold": normalize_threshold_config(
            artifact.get("prediction_thresholds", artifact.get("prediction_threshold", 0.5))
        ),
        "skipped_examples": skipped_examples,
        "embedding_prep": embedding_prep_report,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Score weak multimodal TTFM video rows with the blended multimodal model and "
            "export a ranked review queue for label-quality improvement."
        )
    )
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET_PATH))
    parser.add_argument("--model-path", default=str(DEFAULT_MODEL_PATH))
    parser.add_argument("--device", default="auto")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    rows = load_jsonl_rows(Path(args.dataset))
    predictions_by_example_id, score_report = score_multimodal_rows(
        rows,
        model_path=Path(args.model_path),
        device_preference=args.device,
    )
    queue = build_multimodal_review_queue(
        rows,
        predictions_by_example_id=predictions_by_example_id,
        threshold=score_report.get("prediction_threshold", 0.5),
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(queue, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "output": str(output_path),
                "row_count": queue["summary"]["row_count"],
                "model_disagreement_count": queue["summary"]["model_disagreement_count"],
                "ready_to_promote_count": queue["summary"]["ready_to_promote_count"],
                "review_candidate_count": queue["summary"]["review_candidate_count"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
