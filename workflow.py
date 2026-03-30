from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import AppConfig


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return _read_json(path)


def _count_audio_clips(root: Path) -> int:
    audio_dir = root / "knowledge" / "ttfm_video_corpus" / "audio_clips"
    if not audio_dir.exists():
        return 0
    return sum(1 for _ in audio_dir.rglob("*.wav"))


def _count_audio_semantic_entries(root: Path) -> int:
    cache_path = root / "knowledge" / "ttfm_video_corpus" / "audio_semantic_cache.json"
    if not cache_path.exists():
        return 0
    payload = _read_json(cache_path)
    return len(payload.get("entries", {}))


def _remaining_dense_reviews(config: AppConfig) -> int:
    packet = _load_optional_json(config.paths.phase2_dense_supervision_packet_path)
    answers = _load_optional_json(config.paths.phase2_dense_supervision_answers_path)
    packet_items = list(packet.get("items", []))
    answered = {str(item.get("example_id", "")).strip() for item in answers.get("items", [])}
    return sum(1 for item in packet_items if str(item.get("example_id", "")).strip() not in answered)


def _count_reviewed_windows(path: Path) -> tuple[int, int, int]:
    payload = _load_optional_json(path)
    items = list(payload.get("items", []))
    total = 0
    positives = 0
    negatives = 0
    for item in items:
        outcome = str(item.get("review_outcome", "accepted")).strip().lower() or "accepted"
        if outcome in {"rejected", "ambiguous"}:
            continue
        total += 1
        if outcome == "no_setup":
            negatives += 1
        else:
            positives += 1
    return total, positives, negatives


def _load_history_entries(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            entries.append(payload)
    return entries


def _latest_phase_snapshot(history: list[dict[str, Any]], phase_name: str) -> dict[str, Any] | None:
    for entry in reversed(history):
        if str(entry.get("completed_phase", "")).strip() == phase_name:
            return entry
    return None


def build_workflow_snapshot(config: AppConfig, *, completed_phase: str | None = None, phase_report: dict[str, Any] | None = None) -> dict[str, Any]:
    history_entries = _load_history_entries(config.paths.workflow_history_path)
    phase1_report = _load_optional_json(config.paths.results_dir / "phase1_report.json")
    phase2_report = _load_optional_json(config.paths.phase2_report_path)
    phase2_dataset_stats = _load_optional_json(config.paths.phase2_dataset_stats_path)
    phase2_bundle_report = _load_optional_json(config.paths.phase2_bundle_dataset_report_path)
    phase2_bundle_gold_seed_report = _load_optional_json(config.paths.phase2_bundle_gold_seed_report_path)
    phase3_report = _load_optional_json(config.paths.results_dir / "phase3_report.json")
    phase4_report = _load_optional_json(config.paths.phase4_report_path)
    dense_manifest = _load_optional_json(config.paths.dense_visual_embedding_manifest_path)

    train_count = int(phase2_dataset_stats.get("train_count", 0) or 0)
    val_count = int(phase2_dataset_stats.get("val_count", 0) or 0)
    class_counts = dict(phase2_dataset_stats.get("class_counts", {}))
    focused_answers, focused_positive_answers, focused_negative_answers = _count_reviewed_windows(config.paths.phase2_supervision_answers_path)
    dense_answers, dense_positive_answers, dense_negative_answers = _count_reviewed_windows(config.paths.phase2_dense_supervision_answers_path)
    heuristic_promotions = len(_load_optional_json(config.paths.phase2_dense_heuristic_promotions_path).get("items", []))
    teacher_promotions = len(_load_optional_json(config.paths.phase2_teacher_heuristic_promotions_path).get("items", []))
    weak_visual_promotions = len(_load_optional_json(config.paths.phase2_weak_visual_promotions_path).get("items", []))
    total_reviewed_answers = (
        focused_answers
        + dense_answers
        + heuristic_promotions
        + teacher_promotions
        + weak_visual_promotions
    )
    total_positive_reviews = focused_positive_answers + dense_positive_answers + heuristic_promotions + teacher_promotions + weak_visual_promotions
    total_negative_reviews = focused_negative_answers + dense_negative_answers
    dense_remaining = _remaining_dense_reviews(config)
    dense_embeddings = int(dense_manifest.get("item_count", 0) or 0)
    phase1_f1 = float(phase1_report.get("best_val_F1_macro", 0.0) or 0.0)
    phase3_map = float(phase3_report.get("best_val_mAP50_95", 0.0) or 0.0)
    benchmark_map = float(phase3_report.get("benchmark_report", {}).get("mAP50_95", 0.0) or 0.0)
    hard_negative_fp_rate = float(phase3_report.get("benchmark_report", {}).get("hard_negative_false_positive_rate", 1.0) or 1.0)
    bundle_count = int(phase2_bundle_report.get("bundle_count", 0) or 0)
    bundle_benchmark = dict(phase2_bundle_report.get("benchmark", {}))
    bundle_target_count = int(bundle_benchmark.get("target_count", 0) or 0)
    bundle_satisfied_target_count = int(bundle_benchmark.get("satisfied_target_count", 0) or 0)
    bundle_unsatisfied_target_count = int(bundle_benchmark.get("unsatisfied_target_count", 0) or 0)
    bundle_coverage_ratio = float(bundle_benchmark.get("coverage_ratio", 0.0) or 0.0)
    bundle_gold_seed_count = int(phase2_bundle_gold_seed_report.get("bundle_count", 0) or 0)
    bundle_gold_seed_benchmark = dict(phase2_bundle_gold_seed_report.get("benchmark", {}))
    bundle_gold_seed_coverage_ratio = float(bundle_gold_seed_benchmark.get("coverage_ratio", 0.0) or 0.0)
    phase4_macro_accuracy = float(phase4_report.get("best_val_macro_accuracy", 0.0) or 0.0)
    recommended_dense_label_batch_size = 40
    recommended_positive_review_batch_size = 25
    minimum_train_images_for_confidence = 150
    minimum_val_images_for_confidence = 40
    scarce_class_threshold = 8
    scarce_classes = [
        class_name
        for class_name in ("liquidity_sweep_high", "liquidity_sweep_low", "protected_swing", "bullish_reaction_zone", "bearish_reaction_zone")
        if int(class_counts.get(class_name, 0) or 0) < scarce_class_threshold
    ]

    last_phase3_snapshot = _latest_phase_snapshot(history_entries, "phase3")
    last_phase3_metrics = dict((last_phase3_snapshot or {}).get("metrics", {}))
    reviewed_since_last_phase3 = max(
        0,
        total_reviewed_answers - int(last_phase3_metrics.get("reviewed_answer_count", 0) or 0),
    )
    positive_reviewed_since_last_phase3 = max(
        0,
        total_positive_reviews - int(last_phase3_metrics.get("positive_reviewed_count", 0) or 0),
    )
    yolo_train_since_last_phase3 = max(
        0,
        train_count - int(last_phase3_metrics.get("yolo_train_count", 0) or 0),
    )

    if benchmark_map >= 0.25 and hard_negative_fp_rate <= 0.10 and train_count >= minimum_train_images_for_confidence and val_count >= minimum_val_images_for_confidence:
        next_action = "ready_for_live_replay"
        rationale = "Detector has met the V1 benchmark and hard-negative gates needed for screenshot-based live replay testing."
    elif train_count < minimum_train_images_for_confidence or val_count < minimum_val_images_for_confidence:
        next_action = "label_more_dense_examples"
        rationale = (
            "YOLO dataset is still too small to trust detector quality; keep labeling dense TTrades examples "
            "until the train and validation splits are materially larger."
        )
    elif scarce_classes:
        next_action = "class_balance_insufficient"
        rationale = (
            "Dataset size is now adequate enough for another run, but key classes are still underrepresented: "
            + ", ".join(scarce_classes)
            + ". Prioritize the ranked review queue for those classes before retraining."
        )
    elif reviewed_since_last_phase3 >= recommended_dense_label_batch_size or positive_reviewed_since_last_phase3 >= recommended_positive_review_batch_size:
        next_action = "rerun_phase3"
        rationale = "Enough new reviewed labels have accumulated since the last YOLO run to justify another retrain."
    elif benchmark_map < 0.10 or hard_negative_fp_rate > 0.25:
        next_action = "refresh_phase2_then_retrain"
        rationale = "Benchmark quality is still weak; prioritize more reviewed labels, especially hard negatives, and retrain."
    elif benchmark_map < 0.25:
        next_action = "expand_class_balance"
        rationale = "Detector is learning some signal, but needs more class-balanced examples and better hard-negative control."
    elif dense_remaining > 0:
        next_action = "continue_dense_review"
        rationale = "There is still unused dense supervision capacity available in the current packet."
    else:
        next_action = "build_next_dense_packet"
        rationale = "Current dense packet is exhausted; generate a new review batch."

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "completed_phase": completed_phase,
        "phase_report": phase_report or {},
        "phase1": phase1_report,
        "phase2": phase2_report,
        "phase2_dataset": phase2_dataset_stats,
        "phase2_bundle": phase2_bundle_report,
        "phase2_bundle_gold_seed": phase2_bundle_gold_seed_report,
        "phase3": phase3_report,
        "phase4": phase4_report,
        "corpus": {
            "dense_embedding_count": dense_embeddings,
            "audio_clip_count": _count_audio_clips(config.root_dir),
            "audio_semantic_entry_count": _count_audio_semantic_entries(config.root_dir),
        },
        "metrics": {
            "phase1_best_val_F1_macro": phase1_f1,
            "phase3_best_val_mAP50_95": phase3_map,
            "yolo_train_count": train_count,
            "yolo_val_count": val_count,
            "focused_reviewed_count": focused_answers,
            "dense_reviewed_count": dense_answers,
            "heuristic_auto_label_count": heuristic_promotions,
            "teacher_auto_label_count": teacher_promotions,
            "weak_visual_auto_label_count": weak_visual_promotions,
            "reviewed_answer_count": total_reviewed_answers,
            "positive_reviewed_count": total_positive_reviews,
            "negative_reviewed_count": total_negative_reviews,
            "dense_remaining_count": dense_remaining,
            "reviewed_since_last_phase3": reviewed_since_last_phase3,
            "positive_reviewed_since_last_phase3": positive_reviewed_since_last_phase3,
            "yolo_train_since_last_phase3": yolo_train_since_last_phase3,
            "recommended_dense_label_batch_size": recommended_dense_label_batch_size,
            "recommended_positive_review_batch_size": recommended_positive_review_batch_size,
            "scarce_classes": scarce_classes,
            "benchmark_mAP50_95": benchmark_map,
            "hard_negative_false_positive_rate": hard_negative_fp_rate,
            "bundle_record_count": bundle_count,
            "bundle_benchmark_target_count": bundle_target_count,
            "bundle_benchmark_satisfied_target_count": bundle_satisfied_target_count,
            "bundle_benchmark_unsatisfied_target_count": bundle_unsatisfied_target_count,
            "bundle_benchmark_coverage_ratio": bundle_coverage_ratio,
            "bundle_gold_seed_count": bundle_gold_seed_count,
            "bundle_gold_seed_benchmark_coverage_ratio": bundle_gold_seed_coverage_ratio,
            "phase4_best_val_macro_accuracy": phase4_macro_accuracy,
        },
        "assessment": {
            "next_action": next_action,
            "rationale": rationale,
            "minimum_train_images_for_confidence": minimum_train_images_for_confidence,
            "minimum_val_images_for_confidence": minimum_val_images_for_confidence,
            "live_readiness_benchmark_map_threshold": 0.25,
            "live_readiness_hard_negative_fp_threshold": 0.10,
        },
    }


def write_workflow_reports(config: AppConfig, *, completed_phase: str | None = None, phase_report: dict[str, Any] | None = None) -> dict[str, Any]:
    snapshot = build_workflow_snapshot(config, completed_phase=completed_phase, phase_report=phase_report)
    config.paths.workflow_status_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    config.paths.workflow_history_path.parent.mkdir(parents=True, exist_ok=True)
    with config.paths.workflow_history_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(snapshot) + "\n")
    return snapshot
