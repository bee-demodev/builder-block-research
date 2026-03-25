from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from export_ttfm_case_packets import (
    CHECKPOINT_TIMEFRAME_KEYS,
    DEFAULT_OUTPUT as DEFAULT_CASE_PACKET_PATH,
    DEFAULT_TAXONOMY_PATH,
    index_components_by_label,
    load_component_taxonomy,
    normalize_labels,
)


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "results" / "ttfm_disagreement_report.json"


def clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def safe_divide(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def load_case_packet_report(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_predictions(path: Path) -> list[dict]:
    if not path.exists():
        return []
    predictions: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        cleaned = line.strip()
        if cleaned:
            predictions.append(json.loads(cleaned))
    return predictions


def build_prediction_lookup(predictions: list[dict]) -> dict[tuple[str, str], dict]:
    lookup: dict[tuple[str, str], dict] = {}
    for prediction in predictions:
        case_ref = str(prediction.get("case_ref", "")).strip()
        checkpoint = str(prediction.get("checkpoint", "")).strip()
        if not case_ref or not checkpoint:
            continue
        lookup[(case_ref, checkpoint)] = prediction
    return lookup


def collect_mistake_clusters(cluster_examples: dict[str, set[str]]) -> list[dict]:
    clusters = []
    for cluster_id, examples in sorted(
        cluster_examples.items(),
        key=lambda item: (-len(item[1]), item[0]),
    ):
        clusters.append(
            {
                "cluster_id": cluster_id,
                "count": len(examples),
                "examples": sorted(examples),
            }
        )
    return clusters


def compute_per_label_metrics(label_stats: dict[str, dict[str, int]]) -> dict[str, dict]:
    metrics: dict[str, dict] = {}
    for label, stats in sorted(label_stats.items()):
        tp = int(stats["tp"])
        fp = int(stats["fp"])
        fn = int(stats["fn"])
        precision = safe_divide(tp, tp + fp)
        recall = safe_divide(tp, tp + fn)
        f1 = safe_divide(2 * precision * recall, precision + recall) if precision and recall else 0.0
        metrics[label] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        }
    return metrics


def build_disagreement_report(
    case_packet_report: dict,
    predictions: list[dict],
    taxonomy: dict | None = None,
) -> dict:
    taxonomy = taxonomy or load_component_taxonomy(DEFAULT_TAXONOMY_PATH)
    components_by_label = index_components_by_label(taxonomy)
    prediction_lookup = build_prediction_lookup(predictions)

    label_stats: dict[str, dict[str, int]] = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    cluster_examples: dict[str, set[str]] = defaultdict(set)
    checkpoint_results: list[dict] = []

    evaluated_checkpoint_count = 0
    anchor_checkpoint_count = 0
    anchor_case_regressions = 0
    total_predicted_labels = 0
    sequence_violation_count = 0
    timeframe_violation_count = 0
    rule_mismatch_count = 0

    for packet in case_packet_report.get("case_packets", []):
        packet_topics = {str(packet.get("topic", "")).strip(), *packet.get("supporting_topics", [])}
        for checkpoint in packet.get("checkpoints", []):
            if checkpoint.get("screenshot_status") != "attached":
                continue

            evaluated_checkpoint_count += 1
            key = (str(packet.get("case_ref", "")).strip(), str(checkpoint.get("checkpoint", "")).strip())
            prediction = prediction_lookup.get(key, {})
            predicted_labels = set(normalize_labels(prediction.get("predicted_labels", [])))
            expected_labels = set(normalize_labels(checkpoint.get("expected_component_labels", [])))
            missing_labels = sorted(expected_labels - predicted_labels)
            unexpected_labels = sorted(predicted_labels - expected_labels)
            has_anchor_labels = bool(checkpoint.get("labels_by_provenance", {}).get("anchor_manual"))
            if has_anchor_labels:
                anchor_checkpoint_count += 1
                if missing_labels or unexpected_labels:
                    anchor_case_regressions += 1

            total_predicted_labels += len(predicted_labels)

            for label in sorted(expected_labels & predicted_labels):
                label_stats[label]["tp"] += 1
            for label in missing_labels:
                label_stats[label]["fn"] += 1
                cluster_examples[f"missing:{label}"].add(f"{key[0]}::{key[1]}")
            for label in unexpected_labels:
                label_stats[label]["fp"] += 1
                cluster_examples[f"unexpected:{label}"].add(f"{key[0]}::{key[1]}")

            checkpoint_sequence_ok = True
            checkpoint_timeframe_ok = True
            checkpoint_rule_mismatches: list[str] = []

            for label in predicted_labels:
                component = components_by_label.get(label, {})
                allowed_checkpoints = set(component.get("checkpoints", []))
                allowed_timeframe_roles = {
                    CHECKPOINT_TIMEFRAME_KEYS[name]
                    for name in allowed_checkpoints
                    if name in CHECKPOINT_TIMEFRAME_KEYS
                }

                if allowed_checkpoints and checkpoint["checkpoint"] not in allowed_checkpoints:
                    sequence_violation_count += 1
                    checkpoint_sequence_ok = False
                    cluster_examples[f"invalid_checkpoint:{label}:{checkpoint['checkpoint']}"].add(
                        f"{key[0]}::{key[1]}"
                    )
                if allowed_timeframe_roles and checkpoint.get("timeframe_role") not in allowed_timeframe_roles:
                    timeframe_violation_count += 1
                    checkpoint_timeframe_ok = False
                    cluster_examples[f"timeframe_drift:{label}:{checkpoint.get('timeframe_role')}"].add(
                        f"{key[0]}::{key[1]}"
                    )

                supporting_topics = {
                    str(topic).strip()
                    for topic in component.get("supporting_topics", [])
                    if str(topic).strip()
                }
                if supporting_topics and not (packet_topics & supporting_topics):
                    rule_mismatch_count += 1
                    checkpoint_rule_mismatches.append(label)
                    cluster_examples[f"rule_mismatch:{label}"].add(f"{key[0]}::{key[1]}")

            checkpoint_results.append(
                {
                    "case_ref": key[0],
                    "checkpoint": key[1],
                    "expected_labels": sorted(expected_labels),
                    "predicted_labels": sorted(predicted_labels),
                    "missing_labels": missing_labels,
                    "unexpected_labels": unexpected_labels,
                    "has_anchor_labels": has_anchor_labels,
                    "sequence_consistent": checkpoint_sequence_ok,
                    "timeframe_consistent": checkpoint_timeframe_ok,
                    "rule_mismatches": checkpoint_rule_mismatches,
                }
            )

    per_label_metrics = compute_per_label_metrics(label_stats)
    macro_f1 = safe_divide(
        sum(metric["f1"] for metric in per_label_metrics.values()),
        len(per_label_metrics),
    )
    total_tp = sum(metric["tp"] for metric in per_label_metrics.values())
    total_fp = sum(metric["fp"] for metric in per_label_metrics.values())
    total_fn = sum(metric["fn"] for metric in per_label_metrics.values())
    micro_precision = safe_divide(total_tp, total_tp + total_fp)
    micro_recall = safe_divide(total_tp, total_tp + total_fn)
    micro_f1 = safe_divide(
        2 * micro_precision * micro_recall,
        micro_precision + micro_recall,
    ) if micro_precision and micro_recall else 0.0
    sequence_consistency = 1.0 - safe_divide(sequence_violation_count, total_predicted_labels)
    timeframe_consistency = 1.0 - safe_divide(timeframe_violation_count, total_predicted_labels)
    rule_mismatch_rate = safe_divide(rule_mismatch_count, total_predicted_labels)
    anchor_label_agreement = 1.0 - safe_divide(anchor_case_regressions, anchor_checkpoint_count)
    mistake_clusters = collect_mistake_clusters(cluster_examples)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "evaluated_checkpoint_count": evaluated_checkpoint_count,
            "anchor_checkpoint_count": anchor_checkpoint_count,
            "anchor_case_regressions": anchor_case_regressions,
            "anchor_label_agreement": round(clamp(anchor_label_agreement), 4),
            "macro_f1": round(clamp(macro_f1), 4),
            "micro_f1": round(clamp(micro_f1), 4),
            "timeframe_consistency": round(clamp(timeframe_consistency), 4),
            "sequence_consistency": round(clamp(sequence_consistency), 4),
            "rule_mismatch_count": rule_mismatch_count,
            "rule_mismatch_rate": round(clamp(rule_mismatch_rate), 4),
            "rule_mismatch_delta": 0.0,
            "mistake_cluster_count": len(mistake_clusters),
        },
        "per_label_metrics": per_label_metrics,
        "checkpoint_results": checkpoint_results,
        "mistake_clusters": mistake_clusters,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare TTFM component predictions against screenshot-backed case packets."
    )
    parser.add_argument("--case-packets", default=str(DEFAULT_CASE_PACKET_PATH))
    parser.add_argument("--predictions")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    case_packet_report = load_case_packet_report(Path(args.case_packets))
    predictions = load_predictions(Path(args.predictions)) if args.predictions else []
    report = build_disagreement_report(case_packet_report, predictions)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output_path),
                "evaluated_checkpoint_count": report["summary"]["evaluated_checkpoint_count"],
                "macro_f1": report["summary"]["macro_f1"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
