from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CASE_PACKET_REPORT_PATH = ROOT / "results" / "ttfm_case_packets.json"
DEFAULT_EPISODES_PATH = ROOT / "data" / "trading_iteration_episodes.json"
DEFAULT_OUTPUT = ROOT / "results" / "trading_iteration_grading_report.json"


def load_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_labels(values: object) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        cleaned = values.strip()
        return [cleaned] if cleaned else []
    if isinstance(values, list):
        return sorted({str(value).strip() for value in values if str(value).strip()})
    return []


def normalize_string(value: object) -> str:
    return str(value or "").strip()


def average(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def grade_from_score(score: float) -> str:
    if score >= 0.85:
        return "A"
    if score >= 0.8:
        return "A-"
    if score >= 0.75:
        return "B+"
    if score >= 0.7:
        return "B"
    if score >= 0.6:
        return "B-"
    if score >= 0.55:
        return "C+"
    if score >= 0.5:
        return "C"
    if score >= 0.4:
        return "D"
    return "F"


def f1_like_score(expected: list[str], predicted: list[str]) -> float:
    expected_set = set(expected)
    predicted_set = set(predicted)
    if not expected_set and not predicted_set:
        return 1.0
    if not expected_set or not predicted_set:
        return 0.0
    overlap = len(expected_set & predicted_set)
    return (2.0 * overlap) / (len(expected_set) + len(predicted_set))


def build_case_packet_lookup(case_packet_report: dict) -> dict[str, dict]:
    return {
        normalize_string(packet.get("case_ref")): packet
        for packet in case_packet_report.get("case_packets", [])
        if normalize_string(packet.get("case_ref"))
    }


def build_checkpoint_prediction_lookup(episode: dict) -> dict[str, list[str]]:
    raw_predictions = episode.get("checkpoint_predictions")
    if not isinstance(raw_predictions, list):
        raw_predictions = episode.get("checkpoints")
    if not isinstance(raw_predictions, list):
        return {}

    output: dict[str, list[str]] = {}
    for item in raw_predictions:
        if not isinstance(item, dict):
            continue
        checkpoint = normalize_string(item.get("checkpoint"))
        if not checkpoint:
            continue
        labels = normalize_labels(
            item.get("component_labels")
            if "component_labels" in item
            else item.get("predicted_component_labels")
        )
        output[checkpoint] = labels
    return output


def grade_episode(episode: dict, case_packet: dict | None) -> dict[str, Any]:
    episode_id = normalize_string(episode.get("episode_id")) or normalize_string(episode.get("case_ref"))
    case_ref = normalize_string(episode.get("case_ref"))

    if case_packet is None:
        return {
            "episode_id": episode_id,
            "case_ref": case_ref,
            "status": "unknown_case_ref",
            "understanding_score": 0.0,
            "grade": grade_from_score(0.0),
            "trade_model_correct": False,
            "relation_type_correct": False,
            "checkpoint_component_score": 0.0,
            "checkpoint_results": [],
        }

    expected_trade_models = normalize_labels(case_packet.get("trade_models"))
    expected_relation_types = normalize_labels(case_packet.get("relation_types"))
    predicted_trade_model = normalize_string(
        episode.get("trade_model") or episode.get("predicted_trade_model")
    )
    predicted_relation_type = normalize_string(
        episode.get("relation_type") or episode.get("predicted_relation_type")
    )
    trade_model_correct = predicted_trade_model in expected_trade_models if predicted_trade_model else False
    relation_type_correct = predicted_relation_type in expected_relation_types if predicted_relation_type else False

    prediction_lookup = build_checkpoint_prediction_lookup(episode)
    checkpoint_scores: list[float] = []
    checkpoint_results: list[dict[str, Any]] = []
    for checkpoint in case_packet.get("checkpoints", []):
        checkpoint_name = normalize_string(checkpoint.get("checkpoint"))
        expected_labels = normalize_labels(checkpoint.get("expected_component_labels"))
        predicted_labels = prediction_lookup.get(checkpoint_name, [])
        score = round(f1_like_score(expected_labels, predicted_labels), 4)
        checkpoint_scores.append(score)
        checkpoint_results.append(
            {
                "checkpoint": checkpoint_name,
                "expected_component_labels": expected_labels,
                "predicted_component_labels": predicted_labels,
                "score": score,
            }
        )

    checkpoint_component_score = round(average(checkpoint_scores), 4)
    understanding_score = round(
        (0.25 if trade_model_correct else 0.0)
        + (0.15 if relation_type_correct else 0.0)
        + (0.60 * checkpoint_component_score),
        4,
    )
    return {
        "episode_id": episode_id,
        "case_ref": case_ref,
        "status": "graded",
        "expected_trade_models": expected_trade_models,
        "predicted_trade_model": predicted_trade_model,
        "trade_model_correct": trade_model_correct,
        "expected_relation_types": expected_relation_types,
        "predicted_relation_type": predicted_relation_type,
        "relation_type_correct": relation_type_correct,
        "checkpoint_component_score": checkpoint_component_score,
        "checkpoint_results": checkpoint_results,
        "understanding_score": understanding_score,
        "grade": grade_from_score(understanding_score),
    }


def build_iteration_grading_report(
    *,
    case_packet_report: dict,
    episodes_payload: dict,
) -> dict[str, Any]:
    case_lookup = build_case_packet_lookup(case_packet_report)
    episodes = list(episodes_payload.get("episodes", []))
    graded_episodes = [
        grade_episode(episode, case_lookup.get(normalize_string(episode.get("case_ref"))))
        for episode in episodes
    ]

    scored = [item for item in graded_episodes if item.get("status") == "graded"]
    understanding_scores = [float(item.get("understanding_score", 0.0)) for item in scored]
    checkpoint_scores = [float(item.get("checkpoint_component_score", 0.0)) for item in scored]
    trade_model_hits = [1.0 if item.get("trade_model_correct") else 0.0 for item in scored]
    relation_type_hits = [1.0 if item.get("relation_type_correct") else 0.0 for item in scored]
    unique_cases = {
        normalize_string(item.get("case_ref"))
        for item in scored
        if normalize_string(item.get("case_ref"))
    }
    total_cases = int(case_packet_report.get("summary", {}).get("case_count", len(case_lookup)))

    average_understanding_score = round(average(understanding_scores), 4)
    summary = {
        "episode_count": len(episodes),
        "graded_episode_count": len(scored),
        "unknown_case_count": sum(
            1 for item in graded_episodes if item.get("status") == "unknown_case_ref"
        ),
        "case_coverage": round((len(unique_cases) / total_cases), 4) if total_cases else 0.0,
        "average_understanding_score": average_understanding_score,
        "trade_model_accuracy": round(average(trade_model_hits), 4),
        "relation_type_accuracy": round(average(relation_type_hits), 4),
        "checkpoint_component_score": round(average(checkpoint_scores), 4),
        "latest_understanding_score": round(
            float(scored[-1].get("understanding_score", 0.0)) if scored else 0.0,
            4,
        ),
        "grade": grade_from_score(average_understanding_score),
    }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "framework_slug": case_packet_report.get("framework_slug", "ttfm"),
        "summary": summary,
        "episodes": graded_episodes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Grade TTrades iteration episodes against the current case-packet expectations."
    )
    parser.add_argument("--case-packets", default=str(DEFAULT_CASE_PACKET_REPORT_PATH))
    parser.add_argument("--episodes", default=str(DEFAULT_EPISODES_PATH))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    report = build_iteration_grading_report(
        case_packet_report=load_json(Path(args.case_packets), {"summary": {}, "case_packets": []}),
        episodes_payload=load_json(Path(args.episodes), {"episodes": []}),
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output_path),
                "episode_count": report["summary"]["episode_count"],
                "graded_episode_count": report["summary"]["graded_episode_count"],
                "average_understanding_score": report["summary"]["average_understanding_score"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
