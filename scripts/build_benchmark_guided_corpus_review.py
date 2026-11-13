from __future__ import annotations

import argparse
import glob
import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import YOLO_CLASS_NAMES


DEFAULT_BENCHMARK_FAILURE_BATCH = Path("results") / "benchmark_failure_review_batch_conf025.json"
DEFAULT_CORPUS_PREP_PACKET = Path("results") / "ttfm_corpus_prep_packet.json"
DEFAULT_BENCHMARK_MANIFEST = Path("results") / "benchmark_manifest.json"
DEFAULT_OUTPUT_BATCH = Path("results") / "benchmark_guided_corpus_review_batch_conf025.json"
DEFAULT_OUTPUT_ANSWERS = Path("results") / "benchmark_guided_corpus_review_answers.seed_conf025.json"
DEFAULT_LIMIT = 96
DEFAULT_HARD_NEGATIVE_LIMIT = 16
DEFAULT_EXISTING_ANSWER_PATTERNS = (
    "results/phase2_supervision_answers.json",
    "results/phase2_dense_supervision_answers.json",
    "results/phase2_dense_heuristic_promotions.json",
    "results/phase2_teacher_heuristic_promotions.json",
    "results/phase2_weak_visual_promotions.json",
    "results/ttfm_corpus_priority_review_answers.visual_checked*.json",
)


@dataclass(slots=True)
class BenchmarkGuidedCorpusConfig:
    root_dir: Path
    benchmark_failure_batch_path: Path = DEFAULT_BENCHMARK_FAILURE_BATCH
    corpus_prep_packet_path: Path = DEFAULT_CORPUS_PREP_PACKET
    benchmark_manifest_path: Path = DEFAULT_BENCHMARK_MANIFEST
    output_batch_path: Path = DEFAULT_OUTPUT_BATCH
    output_answers_path: Path = DEFAULT_OUTPUT_ANSWERS
    limit: int = DEFAULT_LIMIT
    hard_negative_limit: int = DEFAULT_HARD_NEGATIVE_LIMIT
    existing_answer_patterns: tuple[str, ...] = field(default_factory=lambda: DEFAULT_EXISTING_ANSWER_PATTERNS)


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_path(root_dir: Path, path: Path | str) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else root_dir / candidate


def relative_or_absolute(path: Path, root_dir: Path) -> str:
    try:
        return str(path.resolve().relative_to(root_dir.resolve()))
    except ValueError:
        return str(path)


def iter_payload_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict) and isinstance(payload.get("items"), list):
        return [item for item in payload["items"] if isinstance(item, dict)]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def normalized_class_names(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    names = []
    for value in values:
        label = str(value).strip()
        if label in YOLO_CLASS_NAMES:
            names.append(label)
    return names


def reviewed_answer_item(item: dict[str, Any]) -> bool:
    outcome = str(item.get("review_outcome", "")).strip().lower()
    detections = item.get("detections", [])
    return bool(detections) or outcome in {"accepted", "adjusted", "rejected", "no_setup"}


def expand_existing_answer_paths(root_dir: Path, patterns: tuple[str, ...]) -> list[Path]:
    paths: list[Path] = []
    seen: set[Path] = set()
    for pattern in patterns:
        candidate = Path(pattern)
        search_pattern = str(candidate if candidate.is_absolute() else root_dir / candidate)
        for raw_path in glob.glob(search_pattern):
            path = Path(raw_path).resolve()
            if path not in seen:
                seen.add(path)
                paths.append(path)
    return sorted(paths)


def load_reviewed_ids(root_dir: Path, patterns: tuple[str, ...]) -> tuple[set[str], list[str]]:
    reviewed_ids: set[str] = set()
    source_paths: list[str] = []
    for path in expand_existing_answer_paths(root_dir, patterns):
        payload = load_json(path, {})
        used = False
        for item in iter_payload_items(payload):
            example_id = str(item.get("example_id", "")).strip()
            if example_id and reviewed_answer_item(item):
                reviewed_ids.add(example_id)
                used = True
        if used:
            source_paths.append(relative_or_absolute(path, root_dir))
    return reviewed_ids, source_paths


def load_benchmark_ids(benchmark_manifest: dict[str, Any], benchmark_failure_batch: dict[str, Any]) -> set[str]:
    benchmark_ids: set[str] = set()
    for item in iter_payload_items(benchmark_manifest):
        example_id = str(item.get("example_id", "")).strip()
        if example_id:
            benchmark_ids.add(example_id)
    for item in iter_payload_items(benchmark_failure_batch):
        example_id = str(item.get("example_id", "")).strip()
        if example_id:
            benchmark_ids.add(example_id)
    return benchmark_ids


def benchmark_demand_summary(benchmark_failure_batch: dict[str, Any]) -> dict[str, Any]:
    false_negative_counts: Counter[str] = Counter()
    false_positive_counts: Counter[str] = Counter()
    action_counts: Counter[str] = Counter()
    candidate_label_counts: Counter[str] = Counter()
    hard_negative_false_positive_count = 0

    for item in iter_payload_items(benchmark_failure_batch):
        context = item.get("benchmark_context", {}) if isinstance(item.get("benchmark_context"), dict) else {}
        action = str(item.get("recommended_action", "")).strip()
        if action:
            action_counts[action] += 1
        if bool(item.get("hard_negative")) or action == "review_hard_negative_false_positive":
            hard_negative_false_positive_count += 1
        for class_name in normalized_class_names(context.get("false_negative_classes", [])):
            false_negative_counts[class_name] += 1
        for class_name in normalized_class_names(context.get("false_positive_classes", [])):
            false_positive_counts[class_name] += 1
        for class_name in normalized_class_names(item.get("candidate_labels", [])):
            candidate_label_counts[class_name] += 1

    class_weights = {
        class_name: round(false_negative_counts[class_name] * 5.0 + false_positive_counts[class_name] * 1.25, 4)
        for class_name in YOLO_CLASS_NAMES
        if false_negative_counts[class_name] or false_positive_counts[class_name]
    }
    return {
        "false_negative_counts": dict(false_negative_counts),
        "false_positive_counts": dict(false_positive_counts),
        "recommended_action_counts": dict(action_counts),
        "candidate_label_counts": dict(candidate_label_counts),
        "hard_negative_false_positive_count": hard_negative_false_positive_count,
        "class_weights": class_weights,
    }


def path_exists_for_item(item: dict[str, Any], root_dir: Path) -> bool:
    raw_path = str(item.get("image_path") or item.get("relative_image_path") or "").strip()
    if not raw_path:
        return False
    return resolve_path(root_dir, raw_path).exists()


def score_corpus_item(item: dict[str, Any], demand: dict[str, Any]) -> dict[str, Any]:
    candidate_labels = normalized_class_names(item.get("candidate_labels", []))
    base_score = float(item.get("score") or 0.0)
    class_weights = {
        str(class_name): float(weight)
        for class_name, weight in (demand.get("class_weights", {}) if isinstance(demand, dict) else {}).items()
    }
    false_negative_counts = Counter(demand.get("false_negative_counts", {}))
    false_positive_counts = Counter(demand.get("false_positive_counts", {}))
    matched_classes = [class_name for class_name in candidate_labels if class_weights.get(class_name, 0.0) > 0.0]
    demand_score = sum(class_weights.get(class_name, 0.0) for class_name in set(candidate_labels))
    action = str(item.get("recommended_action", "")).strip()
    action_component = {
        "accept_or_adjust": 12.0,
        "review": 7.0,
        "hard_negative_review": 0.0,
    }.get(action, 4.0)
    hard_negative_pressure = float(demand.get("hard_negative_false_positive_count") or 0.0)
    if not candidate_labels or action == "hard_negative_review":
        guided_score = base_score * 0.1 + hard_negative_pressure * 10.0
        selection_reasons = ["hard_negative_balance"]
        if hard_negative_pressure:
            selection_reasons.append("benchmark_false_positive_pressure")
    else:
        guided_score = demand_score + base_score * 0.15 + action_component
        selection_reasons = [f"benchmark_demand:{class_name}" for class_name in matched_classes]
        if not selection_reasons:
            selection_reasons = ["corpus_score_fallback"]

    guided = dict(item)
    guided["corpus_score"] = round(base_score, 4)
    guided["score"] = round(guided_score, 4)
    guided["benchmark_guided_score"] = round(guided_score, 4)
    guided["benchmark_demand_classes"] = matched_classes
    guided["benchmark_demand_counts"] = {
        class_name: {
            "false_negative": int(false_negative_counts[class_name]),
            "false_positive": int(false_positive_counts[class_name]),
            "weight": round(class_weights.get(class_name, 0.0), 4),
        }
        for class_name in matched_classes
    }
    guided["selection_reasons"] = sorted(set(list(item.get("selection_reasons", []) or []) + selection_reasons))
    return guided


def summarize_selected(items: list[dict[str, Any]]) -> dict[str, Any]:
    action_counts: Counter[str] = Counter()
    class_counts: Counter[str] = Counter()
    demand_class_counts: Counter[str] = Counter()
    for item in items:
        action_counts[str(item.get("recommended_action", ""))] += 1
        for class_name in normalized_class_names(item.get("candidate_labels", [])):
            class_counts[class_name] += 1
        for class_name in normalized_class_names(item.get("benchmark_demand_classes", [])):
            demand_class_counts[class_name] += 1
    return {
        "recommended_action_counts": dict(action_counts),
        "candidate_label_counts": dict(class_counts),
        "benchmark_demand_class_counts": dict(demand_class_counts),
    }


def build_answer_seed(packet: dict[str, Any]) -> dict[str, Any]:
    answer_items: list[dict[str, Any]] = []
    for item in packet.get("items", []):
        candidate_labels = normalized_class_names(item.get("candidate_labels", []))
        demand_classes = normalized_class_names(item.get("benchmark_demand_classes", []))
        note_bits = [
            "Benchmark-guided corpus review only; do not promote without manual review.",
            f"recommended_action={item.get('recommended_action', '')}",
        ]
        if candidate_labels:
            note_bits.append(f"candidate_labels={','.join(candidate_labels)}")
        if demand_classes:
            note_bits.append(f"demand_classes={','.join(demand_classes)}")
        answer_items.append(
            {
                "example_id": str(item.get("example_id", "")).strip(),
                "detections": [],
                "review_outcome": "ambiguous",
                "note": " ".join(bit for bit in note_bits if bit.strip()),
                "source": "benchmark_guided_corpus_review",
                "image_path": str(item.get("image_path", "")),
                "candidate_labels": candidate_labels,
                "recommended_action": str(item.get("recommended_action", "")),
                "score": item.get("score"),
            }
        )
    return {
        "generated_at": packet.get("generated_at"),
        "mode": "benchmark_guided_corpus_review_answers_seed",
        "source_packet_mode": packet.get("mode"),
        "instructions": (
            "Rows left as ambiguous are ignored by Phase 2 loaders. Promote only manually reviewed "
            "detections or explicit no_setup hard negatives into normal supervision answer files."
        ),
        "items": answer_items,
    }


def build_guided_packet(config: BenchmarkGuidedCorpusConfig) -> tuple[dict[str, Any], dict[str, Any]]:
    root_dir = config.root_dir.resolve()
    benchmark_failure_path = resolve_path(root_dir, config.benchmark_failure_batch_path)
    corpus_packet_path = resolve_path(root_dir, config.corpus_prep_packet_path)
    benchmark_manifest_path = resolve_path(root_dir, config.benchmark_manifest_path)
    benchmark_failure_batch = load_json(benchmark_failure_path, {})
    corpus_packet = load_json(corpus_packet_path, {})
    benchmark_manifest = load_json(benchmark_manifest_path, {})

    benchmark_ids = load_benchmark_ids(benchmark_manifest, benchmark_failure_batch)
    reviewed_ids, reviewed_answer_sources = load_reviewed_ids(root_dir, config.existing_answer_patterns)
    demand = benchmark_demand_summary(benchmark_failure_batch)

    exclusions: Counter[str] = Counter()
    positive_items: list[dict[str, Any]] = []
    hard_negative_items: list[dict[str, Any]] = []
    for item in iter_payload_items(corpus_packet):
        example_id = str(item.get("example_id", "")).strip()
        if not example_id:
            exclusions["missing_example_id"] += 1
            continue
        if example_id in benchmark_ids:
            exclusions["held_out_benchmark_example"] += 1
            continue
        if example_id in reviewed_ids:
            exclusions["already_reviewed"] += 1
            continue
        if not path_exists_for_item(item, root_dir):
            exclusions["missing_image_path"] += 1
            continue
        guided = score_corpus_item(item, demand)
        if not normalized_class_names(guided.get("candidate_labels", [])) or guided.get("recommended_action") == "hard_negative_review":
            hard_negative_items.append(guided)
        else:
            positive_items.append(guided)

    positive_items.sort(key=lambda item: (float(item["benchmark_guided_score"]), str(item["example_id"])), reverse=True)
    hard_negative_items.sort(key=lambda item: (float(item["benchmark_guided_score"]), str(item["example_id"])), reverse=True)
    selected_items = positive_items[: config.limit] + hard_negative_items[: config.hard_negative_limit]
    selected_items.sort(key=lambda item: (float(item["benchmark_guided_score"]), str(item["example_id"])), reverse=True)
    for rank, item in enumerate(selected_items, start=1):
        item["review_rank"] = rank

    generated_at = datetime.now(timezone.utc).isoformat()
    packet = {
        "generated_at": generated_at,
        "mode": "benchmark_guided_corpus_review",
        "instructions": (
            "Use benchmark failures only as aggregate class demand. Candidate labels on each item "
            "come from the corpus prep packet, not held-out benchmark truth."
        ),
        "source_paths": {
            "benchmark_failure_batch": relative_or_absolute(benchmark_failure_path, root_dir),
            "corpus_prep_packet": relative_or_absolute(corpus_packet_path, root_dir),
            "benchmark_manifest": relative_or_absolute(benchmark_manifest_path, root_dir),
            "reviewed_answer_sources": reviewed_answer_sources,
        },
        "limits": {
            "positive_limit": config.limit,
            "hard_negative_limit": config.hard_negative_limit,
        },
        "input_counts": {
            "corpus_items": len(iter_payload_items(corpus_packet)),
            "held_out_benchmark_ids": len(benchmark_ids),
            "reviewed_ids": len(reviewed_ids),
            "eligible_positive_count": len(positive_items),
            "eligible_hard_negative_count": len(hard_negative_items),
        },
        "exclusion_counts": dict(exclusions),
        "benchmark_demand_summary": demand,
        "item_count": len(selected_items),
        "selected_positive_count": sum(1 for item in selected_items if normalized_class_names(item.get("candidate_labels", []))),
        "selected_hard_negative_count": sum(1 for item in selected_items if not normalized_class_names(item.get("candidate_labels", []))),
        "selected_summary": summarize_selected(selected_items),
        "items": selected_items,
    }
    return packet, build_answer_seed(packet)


def write_outputs(packet: dict[str, Any], answers: dict[str, Any], config: BenchmarkGuidedCorpusConfig) -> None:
    root_dir = config.root_dir.resolve()
    output_batch = resolve_path(root_dir, config.output_batch_path)
    output_answers = resolve_path(root_dir, config.output_answers_path)
    output_batch.parent.mkdir(parents=True, exist_ok=True)
    output_answers.parent.mkdir(parents=True, exist_ok=True)
    output_batch.write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")
    output_answers.write_text(json.dumps(answers, indent=2) + "\n", encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a benchmark-guided fresh corpus review packet.")
    parser.add_argument("--root-dir", type=Path, default=Path.cwd())
    parser.add_argument("--benchmark-failure-batch", type=Path, default=DEFAULT_BENCHMARK_FAILURE_BATCH)
    parser.add_argument("--corpus-prep-packet", type=Path, default=DEFAULT_CORPUS_PREP_PACKET)
    parser.add_argument("--benchmark-manifest", type=Path, default=DEFAULT_BENCHMARK_MANIFEST)
    parser.add_argument("--output-batch", type=Path, default=DEFAULT_OUTPUT_BATCH)
    parser.add_argument("--output-answers", type=Path, default=DEFAULT_OUTPUT_ANSWERS)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--hard-negative-limit", type=int, default=DEFAULT_HARD_NEGATIVE_LIMIT)
    parser.add_argument(
        "--existing-answer-pattern",
        action="append",
        dest="existing_answer_patterns",
        help="Glob/path for answer files whose non-ambiguous items should be excluded. Repeatable.",
    )
    return parser


def main(argv: list[str] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    args = build_arg_parser().parse_args(argv)
    config = BenchmarkGuidedCorpusConfig(
        root_dir=args.root_dir,
        benchmark_failure_batch_path=args.benchmark_failure_batch,
        corpus_prep_packet_path=args.corpus_prep_packet,
        benchmark_manifest_path=args.benchmark_manifest,
        output_batch_path=args.output_batch,
        output_answers_path=args.output_answers,
        limit=args.limit,
        hard_negative_limit=args.hard_negative_limit,
        existing_answer_patterns=tuple(args.existing_answer_patterns or DEFAULT_EXISTING_ANSWER_PATTERNS),
    )
    packet, answers = build_guided_packet(config)
    write_outputs(packet, answers, config)
    print(
        json.dumps(
            {
                "output_batch": str(resolve_path(config.root_dir.resolve(), config.output_batch_path).resolve()),
                "output_answers": str(resolve_path(config.root_dir.resolve(), config.output_answers_path).resolve()),
                "item_count": packet["item_count"],
                "selected_positive_count": packet["selected_positive_count"],
                "selected_hard_negative_count": packet["selected_hard_negative_count"],
                "exclusion_counts": packet["exclusion_counts"],
                "selected_summary": packet["selected_summary"],
            },
            indent=2,
        )
    )
    return packet, answers


if __name__ == "__main__":
    main()
