from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from export_trader_dataset import (
    load_annotation_trade_models,
    load_profile_frameworks,
    load_profile_topics,
    load_profile_trade_models,
)


ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "research.db"
DEFAULT_DATASET_OUTPUT = ROOT / "results" / "model_training_surface.jsonl"
DEFAULT_REPORT_OUTPUT = ROOT / "results" / "model_training_report.json"


def flatten_strings(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        output: list[str] = []
        for item in value.values():
            output.extend(flatten_strings(item))
        return output
    if isinstance(value, list):
        output: list[str] = []
        for item in value:
            output.extend(flatten_strings(item))
        return output
    if isinstance(value, (int, float, bool)):
        return [str(value)]
    return []


def extract_key_paths(value: object, prefix: str = "") -> list[str]:
    if isinstance(value, dict):
        output: list[str] = []
        for key, item in value.items():
            next_prefix = f"{prefix}.{key}" if prefix else str(key)
            output.append(next_prefix)
            output.extend(extract_key_paths(item, next_prefix))
        return output
    if isinstance(value, list):
        output: list[str] = []
        list_prefix = f"{prefix}[]" if prefix else "[]"
        for item in value:
            output.append(list_prefix)
            output.extend(extract_key_paths(item, list_prefix))
        return output
    return []


def normalize_token(value: str) -> str:
    return " ".join(str(value).replace("_", " ").replace("-", " ").split()).lower()


def normalize_outcome_decision(outcome: dict | None) -> str:
    if not outcome:
        return "unknown"
    decision = str(outcome.get("decision", "")).strip().lower()
    if not decision:
        return "trade"
    return decision


def rows_to_dicts(cursor: sqlite3.Cursor) -> list[dict]:
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def load_trader_records(
    connection: sqlite3.Connection,
    profile_slug: str | None = None,
    topic: str | None = None,
) -> list[dict]:
    filters: list[str] = []
    params: list[str] = []
    if profile_slug:
        filters.append("tp.slug = ?")
        params.append(profile_slug)
    if topic:
        filters.append("ta.topic_slug = ?")
        params.append(topic)

    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
    query = f"""
        SELECT
            ta.id,
            tp.id,
            tp.slug,
            tp.display_name,
            tp.profile_type,
            tp.status,
            tp.style_json,
            ta.topic_slug,
            ta.case_ref,
            ta.symbol,
            ta.timeframe,
            ta.chart_context_json,
            ta.annotation_json,
            ta.outcome_json,
            ta.notes,
            s.canonical_url
        FROM trader_annotations ta
        JOIN trader_profiles tp ON tp.id = ta.trader_profile_id
        LEFT JOIN sources s ON s.id = ta.source_id
        {where_clause}
        ORDER BY tp.slug, ta.topic_slug, ta.case_ref
    """

    profile_frameworks = load_profile_frameworks(connection)
    profile_trade_models = load_profile_trade_models(connection)
    profile_topics = load_profile_topics(connection)
    annotation_trade_models = load_annotation_trade_models(connection)

    records: list[dict] = []
    for row in connection.execute(query, params):
        records.append(
            {
                "annotation_id": row[0],
                "profile_id": row[1],
                "profile_slug": row[2],
                "profile_name": row[3],
                "profile_type": row[4],
                "profile_status": row[5],
                "profile_style": json.loads(row[6]) if row[6] else None,
                "profile_frameworks": profile_frameworks.get(row[1], []),
                "profile_trade_models": profile_trade_models.get(row[1], []),
                "profile_topics": profile_topics.get(row[1], []),
                "topic": row[7],
                "case_ref": row[8],
                "symbol": row[9],
                "timeframe": row[10],
                "chart_context": json.loads(row[11]),
                "annotation": json.loads(row[12]),
                "outcome": json.loads(row[13]) if row[13] else None,
                "notes": row[14],
                "source_url": row[15],
                "annotation_trade_models": annotation_trade_models.get(row[0], []),
            }
        )
    return records


def build_training_text(parts: Iterable[str]) -> str:
    cleaned = [part.strip() for part in parts if part and part.strip()]
    return " | ".join(cleaned)


def build_training_example(record: dict, trade_model_link: dict) -> dict:
    profile_trade_model_index = {
        str(item["trade_model"]): item for item in record.get("profile_trade_models", [])
    }
    chart_context = record.get("chart_context") or {}
    annotation = record.get("annotation") or {}
    outcome = record.get("outcome") or {}
    trade_model = str(trade_model_link["trade_model"])
    relation_type = str(trade_model_link["relation_type"])
    outcome_decision = normalize_outcome_decision(outcome)

    annotation_key_paths = sorted(set(extract_key_paths(annotation)))
    annotation_value_tokens = sorted(
        {
            normalize_token(value)
            for value in flatten_strings(annotation)
            if str(value).strip()
        }
    )
    chart_context_tokens = sorted(
        {
            normalize_token(value)
            for value in flatten_strings(chart_context)
            if str(value).strip()
        }
    )
    profile_topic_slugs = sorted(
        {str(item["topic"]) for item in record.get("profile_topics", []) if item.get("topic")}
    )
    profile_framework_slugs = sorted(
        {
            str(item["framework"])
            for item in record.get("profile_frameworks", [])
            if item.get("framework")
        }
    )
    profile_trade_model_roles = sorted(
        {
            f'{item["trade_model"]}:{item["role"]}'
            for item in record.get("profile_trade_models", [])
            if item.get("trade_model") and item.get("role")
        }
    )
    timeframes = [str(value) for value in chart_context.get("timeframe_scope", [])]
    sessions = [str(value) for value in chart_context.get("session_scope", [])]
    setup_variant = str(chart_context.get("setup_variant", ""))
    source_kind = str(chart_context.get("source_kind", ""))

    training_text = build_training_text(
        [
            f"profile {record['profile_slug']}",
            f"topic {record['topic']}",
            f"trade model {trade_model}",
            f"relation {relation_type}",
            f"setup {normalize_token(setup_variant)}",
            f"context {' '.join(chart_context_tokens)}",
            f"annotation {' '.join(annotation_value_tokens)}",
            f"outcome {outcome_decision}",
        ]
    )

    return {
        "example_id": f"{record['case_ref']}::{trade_model}::{relation_type}",
        "profile_slug": record["profile_slug"],
        "profile_name": record["profile_name"],
        "profile_type": record["profile_type"],
        "topic": record["topic"],
        "case_ref": record["case_ref"],
        "source_url": record["source_url"],
        "notes": record["notes"],
        "trade_model": trade_model,
        "relation_type": relation_type,
        "confidence": trade_model_link.get("confidence"),
        "indicator_ready_in_profile": bool(
            profile_trade_model_index.get(trade_model, {}).get("indicator_ready", False)
        ),
        "features": {
            "topic": record["topic"],
            "setup_variant": setup_variant,
            "source_kind": source_kind,
            "timeframe_scope": timeframes,
            "session_scope": sessions,
            "profile_frameworks": profile_framework_slugs,
            "profile_topics": profile_topic_slugs,
            "profile_trade_model_roles": profile_trade_model_roles,
            "annotation_key_paths": annotation_key_paths,
            "annotation_value_tokens": annotation_value_tokens,
            "chart_context_tokens": chart_context_tokens,
        },
        "targets": {
            "trade_model": trade_model,
            "relation_type": relation_type,
            "outcome_decision": outcome_decision,
            "is_no_trade": outcome_decision == "no_trade",
            "has_outcome_label": outcome_decision != "unknown",
            "outcome_reason": outcome.get("reason"),
        },
        "training_text": training_text,
    }


def summarize_multiclass_task(
    labels: Iterable[str],
    *,
    minimum_total_examples: int,
    minimum_examples_per_class: int,
) -> dict:
    counts = Counter(str(label) for label in labels if str(label).strip())
    total_examples = sum(counts.values())
    class_count = len(counts)
    minimum_class_examples = min(counts.values()) if counts else 0
    ready = (
        total_examples >= minimum_total_examples
        and class_count >= 2
        and minimum_class_examples >= minimum_examples_per_class
    )
    blockers: list[str] = []
    if total_examples < minimum_total_examples:
        blockers.append(
            f"Only {total_examples} labeled rows; recommend at least {minimum_total_examples}."
        )
    if class_count < 2:
        blockers.append("Need at least two distinct classes.")
    if counts and minimum_class_examples < minimum_examples_per_class:
        blockers.append(
            f"Smallest class has {minimum_class_examples} rows; recommend at least {minimum_examples_per_class}."
        )

    return {
        "ready": ready,
        "total_examples": total_examples,
        "class_count": class_count,
        "minimum_examples_per_class": minimum_class_examples,
        "recommended_total_examples": minimum_total_examples,
        "recommended_examples_per_class": minimum_examples_per_class,
        "class_counts": dict(sorted(counts.items())),
        "blockers": blockers,
    }


def summarize_binary_one_vs_rest_tasks(
    examples: list[dict],
    *,
    label_key: str,
    minimum_positive_examples: int,
    minimum_negative_examples: int,
) -> list[dict]:
    counts = Counter(str(example[label_key]) for example in examples)
    total = len(examples)
    summaries: list[dict] = []
    for label, positive_examples in sorted(counts.items()):
        negative_examples = total - positive_examples
        ready = (
            positive_examples >= minimum_positive_examples
            and negative_examples >= minimum_negative_examples
        )
        summaries.append(
            {
                label_key: label,
                "positive_examples": positive_examples,
                "negative_examples": negative_examples,
                "recommended_positive_examples": minimum_positive_examples,
                "recommended_negative_examples": minimum_negative_examples,
                "additional_positive_examples_needed": max(
                    0, minimum_positive_examples - positive_examples
                ),
                "additional_negative_examples_needed": max(
                    0, minimum_negative_examples - negative_examples
                ),
                "ready": ready,
            }
        )
    summaries.sort(
        key=lambda item: (
            item["additional_positive_examples_needed"],
            item["additional_negative_examples_needed"],
            item[label_key],
        )
    )
    return summaries


def summarize_training_surface(examples: list[dict]) -> dict:
    trade_model_labels = [example["targets"]["trade_model"] for example in examples]
    relation_type_labels = [example["targets"]["relation_type"] for example in examples]
    outcome_examples = [
        example for example in examples if example["targets"]["has_outcome_label"]
    ]
    outcome_labels = [example["targets"]["outcome_decision"] for example in outcome_examples]

    task_readiness = {
        "trade_model_classification": summarize_multiclass_task(
            trade_model_labels,
            minimum_total_examples=25,
            minimum_examples_per_class=5,
        ),
        "relation_type_classification": summarize_multiclass_task(
            relation_type_labels,
            minimum_total_examples=25,
            minimum_examples_per_class=5,
        ),
        "no_trade_filter": summarize_multiclass_task(
            outcome_labels,
            minimum_total_examples=12,
            minimum_examples_per_class=4,
        ),
    }

    trade_model_binary_tasks = summarize_binary_one_vs_rest_tasks(
        examples,
        label_key="trade_model",
        minimum_positive_examples=5,
        minimum_negative_examples=5,
    )

    recommendations: list[str] = []
    if not task_readiness["trade_model_classification"]["ready"]:
        recommendations.append(
            "Collect more labeled chart cases per trade model before training any multi-class classifier."
        )
    if not task_readiness["no_trade_filter"]["ready"]:
        recommendations.append(
            "Capture explicit `outcome.decision` labels on more cases so the first neural layer can learn stand-aside filters."
        )

    nearest_trade_model_gap = next(
        (task for task in trade_model_binary_tasks if task["additional_positive_examples_needed"] > 0),
        None,
    )
    if nearest_trade_model_gap:
        recommendations.append(
            "The fastest narrow-task path is one-vs-rest scoring for "
            f"{nearest_trade_model_gap['trade_model']} once it gains "
            f"{nearest_trade_model_gap['additional_positive_examples_needed']} more positive examples."
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "example_count": len(examples),
        "unique_case_count": len({example["case_ref"] for example in examples}),
        "unique_trade_model_count": len(set(trade_model_labels)),
        "unique_relation_type_count": len(set(relation_type_labels)),
        "labeled_outcome_count": len(outcome_examples),
        "unknown_outcome_count": len(examples) - len(outcome_examples),
        "trade_model_counts": dict(sorted(Counter(trade_model_labels).items())),
        "relation_type_counts": dict(sorted(Counter(relation_type_labels).items())),
        "outcome_decision_counts": dict(sorted(Counter(outcome_labels).items())),
        "task_readiness": task_readiness,
        "trade_model_binary_tasks": trade_model_binary_tasks,
        "recommendations": recommendations,
    }


def export_training_surface(
    *,
    dataset_output: Path,
    report_output: Path,
    profile_slug: str | None = None,
    topic: str | None = None,
) -> dict:
    with sqlite3.connect(DB_PATH) as connection:
        records = load_trader_records(connection, profile_slug=profile_slug, topic=topic)

    examples: list[dict] = []
    for record in records:
        for trade_model_link in record.get("annotation_trade_models", []):
            examples.append(build_training_example(record, trade_model_link))

    dataset_output.parent.mkdir(parents=True, exist_ok=True)
    with dataset_output.open("w", encoding="utf-8") as handle:
        for example in examples:
            handle.write(json.dumps(example, sort_keys=True) + "\n")

    report = summarize_training_surface(examples)
    report["dataset_output"] = str(dataset_output)
    report_output.parent.mkdir(parents=True, exist_ok=True)
    report_output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export a model-ready training surface from trader annotations and trade-model links."
    )
    parser.add_argument("--dataset-output", default=str(DEFAULT_DATASET_OUTPUT))
    parser.add_argument("--report-output", default=str(DEFAULT_REPORT_OUTPUT))
    parser.add_argument("--profile-slug")
    parser.add_argument("--topic")
    args = parser.parse_args()

    report = export_training_surface(
        dataset_output=Path(args.dataset_output),
        report_output=Path(args.report_output),
        profile_slug=args.profile_slug,
        topic=args.topic,
    )
    print(
        json.dumps(
            {
                "dataset_output": str(Path(args.dataset_output)),
                "report_output": str(Path(args.report_output)),
                "example_count": report["example_count"],
                "labeled_outcome_count": report["labeled_outcome_count"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
