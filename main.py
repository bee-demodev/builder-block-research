from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path

from config import AppConfig, YOLO_CLASS_NAMES, build_config, config_to_dict, ensure_runtime_dirs
from bundle_dataset import (
    build_bundle_dataset,
    build_bundle_gold_seed,
    summarize_bundle_dataset,
    write_bundle_dataset,
)
from data_loader import (
    build_dense_visual_corpus,
    canonical_time_index,
    dense_visual_corpus_is_fresh,
    ensure_corpus_size,
    load_chart_corpus,
    load_dense_window_lookup,
    load_video_order_lookup,
)
from labeler.embedding_labeler import (
    bootstrap_anchor_examples,
    label_examples_with_anchors,
    load_anchor_examples,
    save_anchor_examples,
    save_pseudo_label_outputs,
    select_representative_examples,
)
from labeler.synthetic_teacher import generate_synthetic_sidecar
from labeler.vision_labeler import (
    build_dense_supervision_packet_from_rows,
    build_priority_review_queue,
    build_supervision_packet,
    export_yolo_dataset,
    has_openai_api_key,
    label_representative_examples,
    load_supervision_answers,
    select_accept_packet_autolabels,
    select_heuristic_dense_autolabels,
    select_scarce_accept_packet_autolabels,
    select_setup_quality_autolabels,
    select_teacher_screenshot_autolabels,
    select_weak_visual_autolabels,
)
from workflow import write_workflow_reports


class _NullRun:
    def log(self, *_args, **_kwargs) -> None:
        return None

    def finish(self) -> None:
        return None


def _resolve_existing_path(preferred: Path, fallback: Path) -> Path:
    return preferred if preferred.exists() else fallback


def _load_optional_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _count_labeled_class_counts(rows: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        for detection in row.get("detections", []):
            class_id = int(detection["class_id"])
            class_name = YOLO_CLASS_NAMES[class_id] if 0 <= class_id < len(YOLO_CLASS_NAMES) else None
            if class_name is None:
                continue
            counts[class_name] = counts.get(class_name, 0) + 1
    return counts


def _dedupe_labeled_rows(rows: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    for row in rows:
        example_id = str(row.get("example_id", "")).strip()
        if not example_id:
            continue
        if example_id not in merged:
            merged[example_id] = {
                **row,
                "detections": list(row.get("detections", [])),
            }
            continue
        existing = merged[example_id]
        seen: set[tuple[int, int, int, int, int]] = {
            (
                int(detection["class_id"]),
                *[int(float(value) * 1000) for value in detection["bbox"]],
            )
            for detection in existing.get("detections", [])
        }
        for detection in row.get("detections", []):
            key = (
                int(detection["class_id"]),
                *[int(float(value) * 1000) for value in detection["bbox"]],
            )
            if key in seen:
                continue
            seen.add(key)
            existing.setdefault("detections", []).append(
                {
                    "class_id": int(detection["class_id"]),
                    "bbox": [float(value) for value in detection["bbox"]],
                }
            )
        existing_outcome = str(existing.get("review_outcome", "accepted")).strip().lower()
        new_outcome = str(row.get("review_outcome", "accepted")).strip().lower()
        if existing_outcome == "no_setup" and new_outcome in {"accepted", "adjusted"}:
            existing["review_outcome"] = new_outcome
        if row.get("note"):
            existing["note"] = str(row.get("note", "")).strip()
    return list(merged.values())


def _load_setup_quality_runtime(config: AppConfig):
    if not config.phase2.setup_quality_enabled:
        return None
    checkpoint_path = config.root_dir / "models" / "mlp_ttrades_best.pth"
    if not checkpoint_path.exists():
        return None
    try:
        from trainer.mlp_trainer import (
            build_checkpoint_context_warnings,
            load_mlp_checkpoint,
            load_mlp_checkpoint_metadata,
            predict_mlp_probabilities,
        )
    except Exception:
        return None
    try:
        model, _label_to_index, device = load_mlp_checkpoint(checkpoint_path)
        metadata = load_mlp_checkpoint_metadata(checkpoint_path)
    except Exception:
        return None
    return {
        "model": model,
        "device": device,
        "metadata": metadata,
        "predict": predict_mlp_probabilities,
        "warnings": build_checkpoint_context_warnings(metadata, config),
    }


def _load_detector_runtime(config: AppConfig):
    if not config.phase2.detector_proposal_enabled:
        return None
    weights_path = config.root_dir / "models" / "yolo26_ttrades_markup_best.pt"
    if not weights_path.exists():
        return None
    try:
        from trainer.yolo_trainer import load_yolo_detector
    except Exception:
        return None
    try:
        detector = load_yolo_detector(weights_path)
    except Exception:
        return None
    return detector


def _classify_setup_quality(setup_scores: dict[str, float], phase1_config) -> tuple[str, float, float]:
    ordered = sorted(setup_scores.items(), key=lambda item: item[1], reverse=True)
    if not ordered:
        return "model_unavailable", 0.0, 0.0
    best_label, best_score = ordered[0]
    second_score = ordered[1][1] if len(ordered) > 1 else 0.0
    return best_label, float(best_score), float(best_score - second_score)


def _enrich_packet_with_setup_quality(packet: dict, example_lookup: dict[str, Any], config: AppConfig) -> dict:
    runtime = _load_setup_quality_runtime(config)
    if runtime is None:
        return packet

    for item in packet.get("items", []):
        example = example_lookup.get(str(item.get("example_id", "")).strip())
        if example is None:
            continue
        setup_scores = runtime["predict"](runtime["model"], example.embedding.astype("float32"), device=runtime["device"])
        setup_type, setup_confidence, setup_margin = _classify_setup_quality(setup_scores, config.phase1)
        item["setup_scores"] = {label: round(float(score), 6) for label, score in setup_scores.items()}
        item["setup_type"] = setup_type
        item["setup_confidence"] = round(setup_confidence, 6)
        item["setup_margin"] = round(setup_margin, 6)
        if runtime["warnings"]:
            item["setup_model_warnings"] = list(runtime["warnings"])

        if setup_type == "invalid_chop" and setup_confidence >= config.phase2.setup_quality_negative_confidence_floor:
            item["recommended_action"] = "no_setup"
        elif (
            setup_type in {"high_probability_long", "high_probability_short"}
            and item.get("candidate_detections")
            and setup_confidence >= config.phase2.setup_quality_positive_confidence_floor
        ):
            item["recommended_action"] = "accept"

    return packet


def _merge_candidate_detections(existing: list[dict], incoming: list[dict]) -> list[dict]:
    merged: list[dict] = []
    seen: set[tuple[int, int, int, int, int]] = set()
    for suggestion in [*existing, *incoming]:
        bbox = [float(value) for value in suggestion.get("bbox", [])]
        if len(bbox) != 4:
            continue
        class_id = int(suggestion.get("class_id", -1))
        key = (class_id, *[int(value * 1000) for value in bbox])
        if key in seen:
            continue
        seen.add(key)
        normalized = {"class_id": class_id, "bbox": bbox}
        if "confidence" in suggestion:
            normalized["confidence"] = float(suggestion["confidence"])
        merged.append(normalized)
    return merged


def _write_phase2_bundle_artifacts(config: AppConfig) -> dict[str, object]:
    source_paths = (
        config.root_dir / "data" / "trader_annotation_cases.json",
        config.root_dir / "data" / "topic_model_graph.json",
        config.root_dir / "data" / "tradingview_pine_validation.json",
        config.root_dir / "results" / "indicator_specs" / "continuation_entry_model.json",
    )
    state_spec_path = _resolve_existing_path(config.paths.fractal_state_spec_path, Path("data") / "fractal_state_machine.json")
    benchmark_targets_path = _resolve_existing_path(
        config.paths.bundle_benchmark_targets_path,
        Path("data") / "bundle_benchmark_targets.json",
    )
    bundles = build_bundle_dataset(
        source_paths=source_paths,
        state_spec_path=state_spec_path,
    )
    write_bundle_dataset(config.paths.phase2_bundle_dataset_path, bundles)
    summary = summarize_bundle_dataset(bundles, benchmark_targets_path=benchmark_targets_path)
    bundle_report = {
        **summary,
        "output_path": str(config.paths.phase2_bundle_dataset_path.resolve()),
        "report_path": str(config.paths.phase2_bundle_dataset_report_path.resolve()),
        "state_spec_path": str(Path(state_spec_path).resolve()),
        "benchmark_targets_path": str(Path(benchmark_targets_path).resolve()),
        "source_paths": [str(path.resolve()) for path in source_paths if path.exists()],
    }
    config.paths.phase2_bundle_dataset_report_path.write_text(
        json.dumps(bundle_report, indent=2),
        encoding="utf-8",
    )
    gold_seed = build_bundle_gold_seed(
        screenshot_manifest_path=config.paths.screenshot_manifest_path,
        trader_annotation_cases_path=config.root_dir / "data" / "trader_annotation_cases.json",
        state_spec_path=state_spec_path,
    )
    write_bundle_dataset(config.paths.phase2_bundle_gold_seed_path, gold_seed)
    gold_seed_summary = summarize_bundle_dataset(gold_seed, benchmark_targets_path=benchmark_targets_path)
    gold_seed_report = {
        **gold_seed_summary,
        "output_path": str(config.paths.phase2_bundle_gold_seed_path.resolve()),
        "report_path": str(config.paths.phase2_bundle_gold_seed_report_path.resolve()),
        "state_spec_path": str(Path(state_spec_path).resolve()),
        "benchmark_targets_path": str(Path(benchmark_targets_path).resolve()),
        "screenshot_manifest_path": str(config.paths.screenshot_manifest_path.resolve()),
    }
    config.paths.phase2_bundle_gold_seed_report_path.write_text(
        json.dumps(gold_seed_report, indent=2),
        encoding="utf-8",
    )
    benchmark = dict(bundle_report.get("benchmark", {}))
    gold_seed_benchmark = dict(gold_seed_report.get("benchmark", {}))
    return {
        "bundle_count": int(bundle_report.get("bundle_count", 0) or 0),
        "bundle_dataset_path": str(config.paths.phase2_bundle_dataset_path.resolve()),
        "bundle_dataset_report_path": str(config.paths.phase2_bundle_dataset_report_path.resolve()),
        "benchmark_target_count": int(benchmark.get("target_count", 0) or 0),
        "benchmark_satisfied_target_count": int(benchmark.get("satisfied_target_count", 0) or 0),
        "benchmark_coverage_ratio": float(benchmark.get("coverage_ratio", 0.0) or 0.0),
        "bundle_gold_seed_count": int(gold_seed_report.get("bundle_count", 0) or 0),
        "bundle_gold_seed_path": str(config.paths.phase2_bundle_gold_seed_path.resolve()),
        "bundle_gold_seed_report_path": str(config.paths.phase2_bundle_gold_seed_report_path.resolve()),
        "bundle_gold_seed_benchmark_satisfied_target_count": int(gold_seed_benchmark.get("satisfied_target_count", 0) or 0),
        "bundle_gold_seed_benchmark_coverage_ratio": float(gold_seed_benchmark.get("coverage_ratio", 0.0) or 0.0),
    }


def _enrich_packet_with_detector_proposals(packet: dict, config: AppConfig) -> dict:
    detector = _load_detector_runtime(config)
    if detector is None:
        return packet

    items = list(packet.get("items", []))
    image_paths = [str(item.get("image_path", "")).strip() for item in items]
    usable_indexes = [index for index, path in enumerate(image_paths) if path]
    if not usable_indexes:
        return packet

    try:
        predictions = detector.predict(
            source=[image_paths[index] for index in usable_indexes],
            imgsz=config.phase3.imgsz,
            verbose=False,
        )
    except Exception:
        return packet

    for item_index, prediction in zip(usable_indexes, predictions):
        item = items[item_index]
        predicted_detections: list[dict[str, float]] = []
        allowed_class_names = {str(label).strip() for label in item.get("candidate_labels", [])}
        if prediction.boxes is not None:
            for box in prediction.boxes:
                confidence = float(box.conf[0].item()) if box.conf is not None else 0.0
                if confidence < config.phase2.detector_proposal_confidence_floor:
                    continue
                class_id = int(box.cls[0].item())
                class_name = YOLO_CLASS_NAMES[class_id] if 0 <= class_id < len(YOLO_CLASS_NAMES) else None
                if allowed_class_names and class_name not in allowed_class_names:
                    continue
                xywhn = box.xywhn[0].tolist()
                predicted_detections.append(
                    {
                        "class_id": class_id,
                        "bbox": [float(xywhn[0]), float(xywhn[1]), float(xywhn[2]), float(xywhn[3])],
                        "confidence": round(confidence, 6),
                    }
                )
                if len(predicted_detections) >= config.phase2.detector_proposal_max_detections_per_image:
                    break
        if predicted_detections:
            merged = _merge_candidate_detections(list(item.get("candidate_detections", [])), predicted_detections)
            item["candidate_detections"] = merged
            if item.get("recommended_action") == "adjust":
                item["recommended_action"] = "accept"

    return packet


def _init_wandb(config: AppConfig, *, job_type: str, run_suffix: str):
    if config.wandb.mode == "disabled":
        return _NullRun()
    try:
        import wandb
    except ImportError:
        return _NullRun()

    return wandb.init(
        project=config.wandb.project,
        entity=config.wandb.entity,
        mode=config.wandb.mode,
        job_type=job_type,
        name=f"{config.wandb.run_name_prefix}-{run_suffix}",
        tags=config.wandb.tags + [job_type],
        config=config_to_dict(config),
        reinit=True,
    )


def run_phase_1(config: AppConfig, anchors_path: Path | None = None) -> dict:
    from trainer.mlp_trainer import train_mlp_classifier

    corpus = load_chart_corpus(config)
    effective_anchors_path = anchors_path or config.paths.anchors_path
    if effective_anchors_path.exists():
        anchors = load_anchor_examples(effective_anchors_path)
    else:
        anchors = bootstrap_anchor_examples(corpus.examples, per_class=config.phase1.anchor_examples_per_class)
        save_anchor_examples(config.paths.suggested_anchors_path, anchors)
        if effective_anchors_path == config.paths.anchors_path:
            save_anchor_examples(effective_anchors_path, anchors)

    pseudo_labels = label_examples_with_anchors(corpus.examples, anchors, config.phase1, config=config)
    save_pseudo_label_outputs(
        pseudo_labels,
        pseudo_labels_path=config.paths.phase1_pseudo_labels_path,
        review_queue_path=config.paths.phase1_review_queue_path,
    )

    run = _init_wandb(config, job_type="phase1", run_suffix="mlp")
    try:
        train_report = train_mlp_classifier(corpus.examples, pseudo_labels, config, run=run)
    finally:
        run.finish()
    write_workflow_reports(config, completed_phase="phase1", phase_report=train_report)
    return train_report


def run_phase_2(config: AppConfig) -> dict:
    representative_budget = config.phase2.representative_budget_min
    if has_openai_api_key():
        corpus = ensure_corpus_size(config, minimum_examples=representative_budget)
    else:
        corpus = load_chart_corpus(config)
    selection = select_representative_examples(
        corpus.examples,
        cluster_method=config.phase2.cluster_method,
        min_clusters=config.phase2.min_clusters,
        max_clusters=config.phase2.max_clusters,
        representative_budget=min(config.phase2.representative_budget_max, len(corpus.examples)),
        random_samples_per_cluster=config.phase2.random_samples_per_cluster,
        seed=config.phase2.sample_seed,
    )
    config.paths.phase2_representatives_path.write_text(
        json.dumps(
            {
                "method": selection["method"],
                "cluster_count": selection["cluster_count"],
                "selected_examples": [
                    {
                        "example_id": example.example_id,
                        "image_path": str(example.image_path),
                        "time_index": example.time_index,
                    }
                    for example in selection["examples"]
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    run = _init_wandb(config, job_type="phase2", run_suffix="dataset")
    try:
        dense_packet = None
        video_order_lookup = load_video_order_lookup(config)
        if config.paths.dense_visual_windows_path.exists():
            dense_rows = [
                json.loads(line)
                for line in config.paths.dense_visual_windows_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            dense_packet = build_dense_supervision_packet_from_rows(
                dense_rows,
                limit=config.phase2.dense_supervision_packet_limit,
                per_video_cap=config.phase2.dense_supervision_per_video_cap,
                video_order_lookup=video_order_lookup,
                review_frame_radius=config.phase2.dense_review_frame_radius,
                min_spacing_seconds=config.phase2.dense_teaching_moment_min_spacing_seconds,
            )
            dense_packet = _enrich_packet_with_detector_proposals(dense_packet, config)
            dense_packet = _enrich_packet_with_setup_quality(
                dense_packet,
                {example.example_id: example for example in corpus.examples},
                config,
            )
            config.paths.phase2_dense_supervision_packet_path.write_text(
                json.dumps(dense_packet, indent=2),
                encoding="utf-8",
            )
            config.paths.phase2_dense_supervision_answers_example_path.write_text(
                json.dumps(
                    {
                        "items": [
                            {
                                "example_id": item["example_id"],
                                "detections": [],
                                "review_outcome": "accepted",
                                "note": "",
                            }
                            for item in dense_packet["items"]
                        ]
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

        manual_answers = []
        if config.paths.phase2_supervision_answers_path.exists():
            manual_answers.extend(load_supervision_answers(config.paths.phase2_supervision_answers_path))
        if config.paths.phase2_dense_supervision_answers_path.exists():
            manual_answers.extend(load_supervision_answers(config.paths.phase2_dense_supervision_answers_path))
        dense_promotion_answers = load_supervision_answers(config.paths.phase2_dense_heuristic_promotions_path) if config.paths.phase2_dense_heuristic_promotions_path.exists() else []
        teacher_promotion_answers = load_supervision_answers(config.paths.phase2_teacher_heuristic_promotions_path) if config.paths.phase2_teacher_heuristic_promotions_path.exists() else []
        weak_visual_promotion_answers = load_supervision_answers(config.paths.phase2_weak_visual_promotions_path) if config.paths.phase2_weak_visual_promotions_path.exists() else []
        precomputed_answers = [
            *manual_answers,
            *dense_promotion_answers,
            *teacher_promotion_answers,
            *weak_visual_promotion_answers,
        ]
        existing_answer_ids = {str(item.get("example_id", "")).strip() for item in precomputed_answers}
        heuristic_auto_answers = []
        if config.phase2.heuristic_auto_label_enabled and dense_packet is not None:
            heuristic_auto_answers = select_heuristic_dense_autolabels(
                dense_packet,
                existing_answer_ids=existing_answer_ids,
                max_new_items=config.phase2.heuristic_auto_label_max_new_per_run,
                min_bbox_area=config.phase2.heuristic_auto_label_min_bbox_area,
                max_bbox_area=config.phase2.heuristic_auto_label_max_bbox_area,
            )
            dense_promotion_answers.extend(heuristic_auto_answers)
            config.paths.phase2_dense_heuristic_promotions_path.write_text(
                json.dumps({"items": dense_promotion_answers}, indent=2),
                encoding="utf-8",
            )
            precomputed_answers.extend(heuristic_auto_answers)
            existing_answer_ids = {str(item.get("example_id", "")).strip() for item in precomputed_answers}
        setup_quality_auto_answers = []
        if dense_packet is not None and config.phase2.setup_quality_enabled:
            setup_quality_auto_answers = select_setup_quality_autolabels(
                dense_packet,
                existing_answer_ids=existing_answer_ids,
                max_new_items=config.phase2.setup_quality_auto_label_max_new_per_run,
                positive_confidence_floor=config.phase2.setup_quality_positive_confidence_floor,
                negative_confidence_floor=config.phase2.setup_quality_negative_confidence_floor,
            )
            dense_promotion_answers.extend(setup_quality_auto_answers)
            config.paths.phase2_dense_heuristic_promotions_path.write_text(
                json.dumps({"items": dense_promotion_answers}, indent=2),
                encoding="utf-8",
            )
            precomputed_answers.extend(setup_quality_auto_answers)
            existing_answer_ids = {str(item.get("example_id", "")).strip() for item in precomputed_answers}
        accept_packet_auto_answers = []
        if dense_packet is not None and config.phase2.accept_packet_auto_label_enabled:
            accept_packet_auto_answers = select_accept_packet_autolabels(
                dense_packet,
                existing_answer_ids=existing_answer_ids,
                max_new_items=config.phase2.accept_packet_auto_label_max_new_per_run,
                confidence_floor=config.phase2.accept_packet_auto_label_confidence_floor,
            )
            dense_promotion_answers.extend(accept_packet_auto_answers)
            config.paths.phase2_dense_heuristic_promotions_path.write_text(
                json.dumps({"items": dense_promotion_answers}, indent=2),
                encoding="utf-8",
            )
            precomputed_answers.extend(accept_packet_auto_answers)
            existing_answer_ids = {str(item.get("example_id", "")).strip() for item in precomputed_answers}
        scarce_accept_packet_auto_answers = []
        if dense_packet is not None and config.phase2.scarce_accept_packet_auto_label_enabled:
            scarce_accept_packet_auto_answers = select_scarce_accept_packet_autolabels(
                dense_packet,
                existing_answer_ids=existing_answer_ids,
                max_new_items=config.phase2.scarce_accept_packet_auto_label_max_new_per_run,
                confidence_floor=config.phase2.scarce_accept_packet_auto_label_confidence_floor,
                scarce_class_names=config.phase2.scarce_class_names,
            )
            dense_promotion_answers.extend(scarce_accept_packet_auto_answers)
            config.paths.phase2_dense_heuristic_promotions_path.write_text(
                json.dumps({"items": dense_promotion_answers}, indent=2),
                encoding="utf-8",
            )
            precomputed_answers.extend(scarce_accept_packet_auto_answers)
        teacher_auto_answers = select_teacher_screenshot_autolabels(
            config.root_dir / "results" / "ttfm_teacher_augmented_visual_dataset.jsonl",
            root_dir=config.root_dir,
            existing_answer_ids={str(item.get("example_id", "")).strip() for item in precomputed_answers},
            max_new_items=config.phase2.teacher_screenshot_auto_label_max_new_per_run,
        )
        teacher_promotion_answers.extend(teacher_auto_answers)
        config.paths.phase2_teacher_heuristic_promotions_path.write_text(
            json.dumps({"items": teacher_promotion_answers}, indent=2),
            encoding="utf-8",
        )
        precomputed_answers.extend(teacher_auto_answers)
        weak_visual_auto_answers = select_weak_visual_autolabels(
            config.root_dir / "results" / "ttfm_video_weak_visual_dataset.jsonl",
            root_dir=config.root_dir,
            existing_answer_ids={str(item.get("example_id", "")).strip() for item in precomputed_answers},
            max_new_items=config.phase2.weak_visual_auto_label_max_new_per_run,
        )
        weak_visual_promotion_answers.extend(weak_visual_auto_answers)
        config.paths.phase2_weak_visual_promotions_path.write_text(
            json.dumps({"items": weak_visual_promotion_answers}, indent=2),
            encoding="utf-8",
        )
        precomputed_answers.extend(weak_visual_auto_answers)

        if precomputed_answers:
            row_lookup = {example.example_id: example for example in corpus.examples}
            dense_window_lookup = load_dense_window_lookup(config.paths.dense_visual_windows_path)
            labeled_rows = []
            for answer in precomputed_answers:
                example = row_lookup.get(answer["example_id"])
                if example is not None:
                    labeled_rows.append(
                        {
                            "example_id": example.example_id,
                            "image_path": str(example.image_path),
                            "time_index": example.time_index,
                            "detections": answer["detections"],
                            "review_outcome": answer.get("review_outcome", "accepted"),
                            "note": answer.get("note", ""),
                            "issues": [],
                        }
                    )
                    continue
                dense_row = dense_window_lookup.get(answer["example_id"])
                if dense_row is None:
                    continue
                labeled_rows.append(
                        {
                            "example_id": str(dense_row.get("example_id", "")),
                            "image_path": str(dense_row.get("frame_path", "")),
                            "time_index": canonical_time_index(
                                video_slug=str(dense_row.get("video_slug", "")).strip(),
                            start_seconds=float(dense_row.get("start", 0.0) or 0.0),
                            video_order_lookup=video_order_lookup,
                            fallback_index=int(dense_row.get("__lookup_order", 0) or 0),
                            ),
                            "detections": answer["detections"],
                            "review_outcome": answer.get("review_outcome", "accepted"),
                            "note": answer.get("note", ""),
                            "issues": [],
                        }
                    )
            reviewed_window_count = len(labeled_rows)
            positive_reviewed_count = sum(1 for row in labeled_rows if row.get("review_outcome") in {"accepted", "adjusted"} and row.get("detections"))
            hard_negative_reviewed_count = sum(1 for row in labeled_rows if row.get("review_outcome") == "no_setup")
            synthetic_sidecar_rows = generate_synthetic_sidecar(
                config,
                class_counts=_count_labeled_class_counts(labeled_rows),
            ) if labeled_rows else []
            if synthetic_sidecar_rows:
                labeled_rows.extend(synthetic_sidecar_rows)
            labeled_rows = _dedupe_labeled_rows(labeled_rows)
            dataset_stats = export_yolo_dataset(labeled_rows, config)
            priority_review_queue = build_priority_review_queue(
                dense_packet or {"items": []},
                existing_answer_ids={str(item.get("example_id", "")).strip() for item in precomputed_answers},
                class_counts=dataset_stats.get("class_counts", {}),
            )
            config.paths.phase2_priority_review_queue_path.write_text(
                json.dumps({"items": priority_review_queue}, indent=2),
                encoding="utf-8",
            )
            bundle_artifacts = _write_phase2_bundle_artifacts(config)
            report = {
                "mode": "supervision_answers",
                "selection": {
                    "method": selection["method"],
                    "cluster_count": selection["cluster_count"],
                    "selected_count": selection["selected_count"],
                },
                "dataset_stats": dataset_stats,
                "supervision_answers_path": str(config.paths.phase2_supervision_answers_path.resolve()) if config.paths.phase2_supervision_answers_path.exists() else None,
                "dense_supervision_answers_path": str(config.paths.phase2_dense_supervision_answers_path.resolve()) if config.paths.phase2_dense_supervision_answers_path.exists() else None,
                "dense_heuristic_promotions_path": str(config.paths.phase2_dense_heuristic_promotions_path.resolve()) if config.paths.phase2_dense_heuristic_promotions_path.exists() else None,
                "teacher_heuristic_promotions_path": str(config.paths.phase2_teacher_heuristic_promotions_path.resolve()) if config.paths.phase2_teacher_heuristic_promotions_path.exists() else None,
                "weak_visual_promotions_path": str(config.paths.phase2_weak_visual_promotions_path.resolve()) if config.paths.phase2_weak_visual_promotions_path.exists() else None,
                "synthetic_sidecar_path": str(config.paths.phase2_synthetic_sidecar_path.resolve()) if config.paths.phase2_synthetic_sidecar_path.exists() else None,
                "priority_review_queue_path": str(config.paths.phase2_priority_review_queue_path.resolve()),
                "used_answer_count": reviewed_window_count,
                "reviewed_window_count": reviewed_window_count,
                "positive_reviewed_count": positive_reviewed_count,
                "hard_negative_reviewed_count": hard_negative_reviewed_count,
                "heuristic_auto_label_count": len(heuristic_auto_answers) + len(setup_quality_auto_answers) + len(accept_packet_auto_answers) + len(scarce_accept_packet_auto_answers),
                "setup_quality_auto_label_count": len(setup_quality_auto_answers),
                "accept_packet_auto_label_count": len(accept_packet_auto_answers),
                "scarce_accept_packet_auto_label_count": len(scarce_accept_packet_auto_answers),
                "teacher_auto_label_count": len(teacher_auto_answers),
                "weak_visual_auto_label_count": len(weak_visual_auto_answers),
                "synthetic_sidecar_count": len(synthetic_sidecar_rows),
                "priority_review_count": len(priority_review_queue),
                "bundle_artifacts": bundle_artifacts,
            }
            run.log(
                {
                    "phase2/selected_count": selection["selected_count"],
                    "phase2/cluster_count": selection["cluster_count"],
                    "phase2/review_queue_count": 0,
                    "phase2/train_images": dataset_stats["train_count"],
                    "phase2/val_images": dataset_stats["val_count"],
                    "phase2/supervision_answers_used": reviewed_window_count,
                    "phase2/positive_reviewed_count": positive_reviewed_count,
                    "phase2/hard_negative_reviewed_count": hard_negative_reviewed_count,
                    "phase2/heuristic_auto_label_count": len(heuristic_auto_answers) + len(setup_quality_auto_answers) + len(accept_packet_auto_answers) + len(scarce_accept_packet_auto_answers),
                    "phase2/setup_quality_auto_label_count": len(setup_quality_auto_answers),
                    "phase2/accept_packet_auto_label_count": len(accept_packet_auto_answers),
                    "phase2/scarce_accept_packet_auto_label_count": len(scarce_accept_packet_auto_answers),
                    "phase2/teacher_auto_label_count": len(teacher_auto_answers),
                    "phase2/weak_visual_auto_label_count": len(weak_visual_auto_answers),
                    "phase2/synthetic_sidecar_count": len(synthetic_sidecar_rows),
                    "phase2/bundle_count": bundle_artifacts["bundle_count"],
                    "phase2/bundle_benchmark_coverage_ratio": bundle_artifacts["benchmark_coverage_ratio"],
                }
            )
            config.paths.phase2_report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
            write_workflow_reports(config, completed_phase="phase2", phase_report=report)
            return report

        if not has_openai_api_key():
            supervision_packet = build_supervision_packet(
                selection["examples"],
                cluster_assignments=selection.get("cluster_assignments"),
            )
            supervision_packet = _enrich_packet_with_detector_proposals(supervision_packet, config)
            supervision_packet = _enrich_packet_with_setup_quality(
                supervision_packet,
                {example.example_id: example for example in corpus.examples},
                config,
            )
            review_queue = supervision_packet["items"]
            config.paths.phase2_review_queue_path.write_text(
                json.dumps(
                    {
                        "mode": "supervision_only",
                        "items": review_queue,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            config.paths.phase2_supervision_packet_path.write_text(
                json.dumps(supervision_packet, indent=2),
                encoding="utf-8",
            )
            config.paths.phase2_supervision_answers_example_path.write_text(
                json.dumps(
                    {
                        "items": [
                            {
                                "example_id": item["example_id"],
                                "detections": [],
                                "review_outcome": "accepted",
                                "note": "",
                            }
                            for item in review_queue
                        ]
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            run.log(
                {
                    "phase2/selected_count": selection["selected_count"],
                    "phase2/cluster_count": selection["cluster_count"],
                    "phase2/review_queue_count": len(review_queue),
                    "phase2/supervision_only": 1,
                }
            )
            bundle_artifacts = _write_phase2_bundle_artifacts(config)
            report = {
                "mode": "supervision_only",
                "selection": {
                    "method": selection["method"],
                    "cluster_count": selection["cluster_count"],
                    "selected_count": selection["selected_count"],
                },
                "review_queue_count": len(review_queue),
                "review_queue_path": str(config.paths.phase2_review_queue_path.resolve()),
                "supervision_packet_path": str(config.paths.phase2_supervision_packet_path.resolve()),
                "supervision_answers_example_path": str(config.paths.phase2_supervision_answers_example_path.resolve()),
                "dense_supervision_packet_path": str(config.paths.phase2_dense_supervision_packet_path.resolve()) if config.paths.dense_visual_windows_path.exists() else None,
                "dense_supervision_answers_example_path": str(config.paths.phase2_dense_supervision_answers_example_path.resolve()) if config.paths.dense_visual_windows_path.exists() else None,
                "bundle_artifacts": bundle_artifacts,
                "message": "OPENAI_API_KEY is not configured. Representative charts were queued for Codex supervision instead of live GPT-5.4 vision labeling.",
            }
            config.paths.phase2_report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
            write_workflow_reports(config, completed_phase="phase2", phase_report=report)
            return report

        labeling = label_representative_examples(selection["examples"], config)
        config.paths.phase2_review_queue_path.write_text(
            json.dumps({"items": labeling["review_queue"]}, indent=2),
            encoding="utf-8",
        )
        dataset_stats = export_yolo_dataset(labeling["records"], config)
        run.log(
            {
                "phase2/selected_count": selection["selected_count"],
                "phase2/cluster_count": selection["cluster_count"],
                "phase2/review_queue_count": len(labeling["review_queue"]),
                "phase2/train_images": dataset_stats["train_count"],
                "phase2/val_images": dataset_stats["val_count"],
            }
        )
    finally:
        run.finish()

    bundle_artifacts = _write_phase2_bundle_artifacts(config)
    report = {
        "mode": "live_labeling",
        "selection": {
            "method": selection["method"],
            "cluster_count": selection["cluster_count"],
            "selected_count": selection["selected_count"],
        },
        "dataset_stats": dataset_stats,
        "review_queue_count": len(labeling["review_queue"]),
        "bundle_artifacts": bundle_artifacts,
    }
    config.paths.phase2_report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_workflow_reports(config, completed_phase="phase2", phase_report=report)
    return report


def run_phase_3(config: AppConfig) -> dict:
    from trainer.yolo_trainer import train_yolo_detector

    run = _init_wandb(config, job_type="phase3", run_suffix="yolo")
    try:
        report = train_yolo_detector(config, run=run)
    finally:
        run.finish()
    write_workflow_reports(config, completed_phase="phase3", phase_report=report)
    return report


def run_phase_4(config: AppConfig) -> dict:
    from trainer.chart_state_trainer import train_chart_state_classifier

    run = _init_wandb(config, job_type="phase4", run_suffix="chart-state")
    try:
        report = train_chart_state_classifier(config, run=run)
    finally:
        run.finish()
    write_workflow_reports(config, completed_phase="phase4", phase_report=report)
    return report


def run_autonomous_workflow_loop(config: AppConfig) -> dict:
    if config.phase2.dense_chunk_pass_enabled and not dense_visual_corpus_is_fresh(config):
        build_dense_visual_corpus(config)

    cycle_reports: list[dict] = []
    last_dataset = _load_optional_json(config.paths.phase2_dataset_stats_path)
    last_train = int(last_dataset.get("train_count", 0) or 0)
    last_val = int(last_dataset.get("val_count", 0) or 0)
    phase3_report: dict | None = None
    stopped_reason = "no_progress"

    for cycle_index in range(1, config.phase2.autonomous_max_cycles + 1):
        phase2_report = run_phase_2(config)
        status = _load_optional_json(config.paths.workflow_status_path)
        metrics = dict(status.get("metrics", {}))
        assessment = dict(status.get("assessment", {}))
        current_train = int(metrics.get("yolo_train_count", 0) or 0)
        current_val = int(metrics.get("yolo_val_count", 0) or 0)
        heuristic_count = int(metrics.get("heuristic_auto_label_count", 0) or 0)
        grew = current_train > last_train or current_val > last_val
        cycle_reports.append(
            {
                "cycle": cycle_index,
                "phase2_report": phase2_report,
                "train_count": current_train,
                "val_count": current_val,
                "heuristic_auto_label_count": heuristic_count,
                "next_action": assessment.get("next_action"),
                "grew_dataset": grew,
            }
        )

        if current_train >= config.phase2.autonomous_train_target and current_val >= config.phase2.autonomous_val_target:
            phase3_report = run_phase_3(config)
            stopped_reason = "retrained_after_target_reached"
            break

        if not grew:
            stopped_reason = "phase2_growth_stalled"
            break

        last_train = current_train
        last_val = current_val

    final_status = _load_optional_json(config.paths.workflow_status_path)
    report = {
        "mode": "workflow_loop",
        "cycle_count": len(cycle_reports),
        "stopped_reason": stopped_reason,
        "cycles": cycle_reports,
        "phase3_report": phase3_report,
        "final_status": final_status,
    }
    config.paths.workflow_loop_report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "TTrades AutoResearch root operator. "
            "Run Phase 1 for pseudo-labeling + MLP, Phase 2 for YOLO dataset prep, "
            "Phase 3 for YOLO training, or Phase 4 for chart-state bundle training."
        )
    )
    parser.add_argument("--phase", required=True, choices=("1", "2", "3", "4", "loop"))
    parser.add_argument("--anchors", type=Path, default=None)
    parser.add_argument("--wandb-mode", choices=("online", "offline", "disabled"), default=None)
    parser.add_argument("--allow-expand", action="store_true", help="Allow Phase 2 to expand the YouTube corpus when coverage is too small.")
    return parser


def main(argv: list[str] | None = None) -> dict | None:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    config = build_config()
    if args.wandb_mode:
        config = replace(config, wandb=replace(config.wandb, mode=args.wandb_mode))
    if args.allow_expand:
        config = replace(config, phase2=replace(config.phase2, auto_expand_if_needed=True))
    ensure_runtime_dirs(config)

    if args.phase == "1":
        return run_phase_1(config, anchors_path=args.anchors)
    if args.phase == "2":
        return run_phase_2(config)
    if args.phase == "3":
        return run_phase_3(config)
    if args.phase == "4":
        return run_phase_4(config)
    if args.phase == "loop":
        return run_autonomous_workflow_loop(config)
    return None


if __name__ == "__main__":
    report = main()
    if report is not None:
        print(json.dumps(report, indent=2))
