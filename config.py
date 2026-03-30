from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field, is_dataclass
from pathlib import Path
from typing import Any


PROJECT_NAME = "ttrades_autoresearch"
SETUP_LABELS = (
    "high_probability_long",
    "high_probability_short",
    "invalid_chop",
)
LEGACY_YOLO_CLASS_NAMES = (
    "fractal_swing_high",
    "fractal_swing_low",
    "order_block_bullish",
    "order_block_bearish",
    "inversion_fvg",
    "liquidity_sweep_high",
    "liquidity_sweep_low",
    "candle_3_closure_zone",
    "protected_swing",
)
YOLO_CLASS_NAMES = (
    "liquidity_sweep_high",
    "liquidity_sweep_low",
    "protected_swing",
    "bullish_reaction_zone",
    "bearish_reaction_zone",
)
YOLO_CLASS_TO_ID = {name: index for index, name in enumerate(YOLO_CLASS_NAMES)}


@dataclass(slots=True)
class PathsConfig:
    root_dir: Path
    knowledge_dir: Path
    data_dir: Path
    scripts_dir: Path
    results_dir: Path
    models_dir: Path
    dataset_dir: Path
    yolo_dir: Path
    yolo_images_train_dir: Path
    yolo_images_val_dir: Path
    yolo_labels_train_dir: Path
    yolo_labels_val_dir: Path
    yolo_data_yaml_path: Path
    yolo_benchmark_dir: Path
    yolo_benchmark_images_dir: Path
    yolo_benchmark_labels_dir: Path
    yolo_benchmark_data_yaml_path: Path
    visual_embedding_manifest_path: Path
    visual_embedding_index_path: Path
    visual_windows_path: Path
    video_manifest_path: Path
    dense_visual_embedding_manifest_path: Path
    dense_visual_embedding_index_path: Path
    dense_visual_windows_path: Path
    dense_visual_windows_report_path: Path
    dense_frame_dir: Path
    frame_dir: Path
    video_dir: Path
    screenshot_manifest_path: Path
    screenshot_root_dir: Path
    screenshot_embedding_dir: Path
    additional_embedding_dirs: list[Path] = field(default_factory=list)
    additional_image_dirs: list[Path] = field(default_factory=list)
    anchors_path: Path = Path()
    phase1_pseudo_labels_path: Path = Path()
    phase1_review_queue_path: Path = Path()
    phase2_representatives_path: Path = Path()
    phase2_review_queue_path: Path = Path()
    phase2_supervision_packet_path: Path = Path()
    phase2_supervision_answers_path: Path = Path()
    phase2_supervision_answers_example_path: Path = Path()
    phase2_dense_supervision_packet_path: Path = Path()
    phase2_dense_supervision_answers_path: Path = Path()
    phase2_dense_supervision_answers_example_path: Path = Path()
    phase2_dense_heuristic_promotions_path: Path = Path()
    phase2_teacher_heuristic_promotions_path: Path = Path()
    phase2_weak_visual_promotions_path: Path = Path()
    phase2_synthetic_sidecar_path: Path = Path()
    synthetic_sidecar_dir: Path = Path()
    phase2_priority_review_queue_path: Path = Path()
    phase2_dataset_stats_path: Path = Path()
    phase2_bundle_dataset_path: Path = Path()
    phase2_bundle_dataset_report_path: Path = Path()
    phase2_bundle_gold_seed_path: Path = Path()
    phase2_bundle_gold_seed_report_path: Path = Path()
    benchmark_manifest_path: Path = Path()
    bundle_benchmark_targets_path: Path = Path()
    fractal_state_spec_path: Path = Path()
    phase2_report_path: Path = Path()
    phase4_report_path: Path = Path()
    workflow_loop_report_path: Path = Path()
    workflow_status_path: Path = Path()
    workflow_history_path: Path = Path()
    suggested_anchors_path: Path = Path()
    corpus_expansion_report_path: Path = Path()
    predict_output_dir: Path = Path()
    chart_state_checkpoint_path: Path = Path()
    chart_state_results_tsv_path: Path = Path()
    yt_channel_url: str = "https://www.youtube.com/@TTrades_edu/videos"
    yt_dlp_bin: str = "yt-dlp"
    ffmpeg_bin: str = "ffmpeg"


@dataclass(slots=True)
class WandBConfig:
    project: str = PROJECT_NAME
    entity: str | None = None
    mode: str = field(default_factory=lambda: os.getenv("WANDB_MODE", "online"))
    run_name_prefix: str = PROJECT_NAME
    tags: list[str] = field(default_factory=lambda: ["ttrades", "autoresearch"])


@dataclass(slots=True)
class Phase1Config:
    knn_k: int = 5
    prototype_weight: float = 0.55
    knn_weight: float = 0.45
    abstain_threshold: float = 0.62
    confidence_floor: float = 0.68
    min_margin: float = 0.08
    anchor_examples_per_class: int = 3
    hidden_dim: int = 256
    dropout: float = 0.15
    learning_rate: float = 3e-4
    weight_decay: float = 1e-4
    batch_size: int = 64
    max_epochs: int = 120
    patience: int = 15
    validation_ratio: float = 0.20
    class_weights: dict[str, float] = field(default_factory=dict)
    serving_min_confidence: float = 0.55
    serving_min_margin: float = 0.10
    uncertain_label: str = "uncertain"


@dataclass(slots=True)
class Phase2Config:
    cluster_method: str = "hdbscan"
    min_clusters: int = 80
    max_clusters: int = 120
    representative_budget_min: int = 800
    representative_budget_max: int = 1500
    random_samples_per_cluster: int = 10
    auto_expand_if_needed: bool = False
    max_expansion_rounds: int = 1
    validation_ratio: float = 0.20
    vision_model: str = "gpt-5.4-pro"
    max_retries: int = 3
    request_timeout_seconds: int = 180
    suspicious_class_limit: int = 10
    suspicious_box_limit: int = 30
    review_confidence_floor: float = 0.75
    sample_seed: int = 42
    dense_chunk_pass_enabled: bool = True
    dense_max_chunks_per_video: int | None = 18
    dense_supervision_packet_limit: int = 180
    dense_supervision_per_video_cap: int = 12
    dense_teaching_moment_min_spacing_seconds: float = 8.0
    dense_review_frame_radius: int = 3
    heuristic_auto_label_enabled: bool = True
    heuristic_auto_label_max_new_per_run: int = 64
    heuristic_auto_label_min_bbox_area: float = 0.0025
    heuristic_auto_label_max_bbox_area: float = 0.08
    setup_quality_enabled: bool = True
    setup_quality_positive_confidence_floor: float = 0.68
    setup_quality_negative_confidence_floor: float = 0.74
    setup_quality_auto_label_max_new_per_run: int = 80
    detector_proposal_enabled: bool = True
    detector_proposal_confidence_floor: float = 0.30
    detector_proposal_max_detections_per_image: int = 3
    accept_packet_auto_label_enabled: bool = True
    accept_packet_auto_label_confidence_floor: float = 0.35
    accept_packet_auto_label_max_new_per_run: int = 64
    scarce_accept_packet_auto_label_enabled: bool = True
    scarce_accept_packet_auto_label_confidence_floor: float = 0.20
    scarce_accept_packet_auto_label_max_new_per_run: int = 48
    scarce_class_names: tuple[str, ...] = ("liquidity_sweep_high", "bearish_reaction_zone")
    materialize_screenshot_embeddings: bool = False
    teacher_screenshot_auto_label_max_new_per_run: int = 48
    weak_visual_auto_label_max_new_per_run: int = 64
    synthetic_sidecar_enabled: bool = False
    synthetic_sidecar_target_per_class: int = 10
    benchmark_target_count: int = 75
    benchmark_positive_target_per_class: int = 10
    benchmark_hard_negative_target_count: int = 25
    benchmark_version: str = "v1_fractal_core"
    autonomous_max_cycles: int = 6
    autonomous_train_target: int = 50
    autonomous_val_target: int = 15


@dataclass(slots=True)
class Phase3Config:
    model_name: str = "yolo26n.pt"
    fallback_model_names: tuple[str, ...] = ("yolo11n.pt", "yolov8n.pt")
    imgsz: int = 1024
    batch: int = -1
    epochs: int = 150
    patience: int = 40
    amp: bool = True
    device: str = "0"
    export_onnx: bool = True
    example_log_interval: int = 10


@dataclass(slots=True)
class Phase4Config:
    hidden_dim: int = 256
    dropout: float = 0.15
    learning_rate: float = 3e-4
    weight_decay: float = 1e-4
    batch_size: int = 16
    max_epochs: int = 120
    patience: int = 20
    validation_ratio: float = 0.25
    min_train_examples: int = 8
    min_val_examples: int = 2


@dataclass(slots=True)
class AppConfig:
    project_name: str
    root_dir: Path
    seed: int
    active_embedding_dim: int
    mixed_precision: bool
    use_torch_compile: bool
    paths: PathsConfig
    wandb: WandBConfig
    phase1: Phase1Config
    phase2: Phase2Config
    phase3: Phase3Config
    phase4: Phase4Config


def _default_paths(root_dir: Path) -> PathsConfig:
    knowledge_dir = root_dir / "knowledge"
    data_dir = root_dir / "data"
    results_dir = root_dir / "results"
    models_dir = root_dir / "models"
    dataset_dir = root_dir / "dataset"
    yolo_dir = dataset_dir / "yolo"
    yolo_benchmark_dir = dataset_dir / "yolo_benchmark"
    return PathsConfig(
        root_dir=root_dir,
        knowledge_dir=knowledge_dir,
        data_dir=data_dir,
        scripts_dir=root_dir / "scripts",
        results_dir=results_dir,
        models_dir=models_dir,
        dataset_dir=dataset_dir,
        yolo_dir=yolo_dir,
        yolo_images_train_dir=yolo_dir / "images" / "train",
        yolo_images_val_dir=yolo_dir / "images" / "val",
        yolo_labels_train_dir=yolo_dir / "labels" / "train",
        yolo_labels_val_dir=yolo_dir / "labels" / "val",
        yolo_data_yaml_path=yolo_dir / "data.yaml",
        yolo_benchmark_dir=yolo_benchmark_dir,
        yolo_benchmark_images_dir=yolo_benchmark_dir / "images",
        yolo_benchmark_labels_dir=yolo_benchmark_dir / "labels",
        yolo_benchmark_data_yaml_path=yolo_benchmark_dir / "data.yaml",
        visual_embedding_manifest_path=knowledge_dir / "ttfm_video_corpus" / "visual_embedding_manifest.json",
        visual_embedding_index_path=knowledge_dir / "ttfm_video_corpus" / "visual_embedding_index.json",
        visual_windows_path=knowledge_dir / "ttfm_video_corpus" / "visual_windows.jsonl",
        video_manifest_path=knowledge_dir / "ttfm_video_corpus" / "video_manifest.json",
        dense_visual_embedding_manifest_path=knowledge_dir / "ttfm_video_corpus" / "dense_visual_embedding_manifest.json",
        dense_visual_embedding_index_path=knowledge_dir / "ttfm_video_corpus" / "dense_visual_embedding_index.json",
        dense_visual_windows_path=knowledge_dir / "ttfm_video_corpus" / "dense_visual_windows.jsonl",
        dense_visual_windows_report_path=knowledge_dir / "ttfm_video_corpus" / "dense_visual_windows_report.json",
        dense_frame_dir=knowledge_dir / "ttfm_video_corpus" / "dense_frames",
        frame_dir=knowledge_dir / "ttfm_video_corpus" / "frames",
        video_dir=knowledge_dir / "ttfm_video_corpus" / "videos",
        screenshot_manifest_path=data_dir / "ttfm_screenshot_manifest.json",
        screenshot_root_dir=root_dir / "artifacts" / "ttfm" / "screenshots",
        screenshot_embedding_dir=data_dir / "embeddings" / "screenshots",
        anchors_path=data_dir / "ttrades_anchor_examples.json",
        phase1_pseudo_labels_path=results_dir / "phase1_pseudo_labels.jsonl",
        phase1_review_queue_path=results_dir / "phase1_review_queue.json",
        phase2_representatives_path=results_dir / "phase2_representatives.json",
        phase2_review_queue_path=results_dir / "phase2_review_queue.json",
        phase2_supervision_packet_path=results_dir / "phase2_supervision_packet.json",
        phase2_supervision_answers_path=results_dir / "phase2_supervision_answers.json",
        phase2_supervision_answers_example_path=results_dir / "phase2_supervision_answers.example.json",
        phase2_dense_supervision_packet_path=results_dir / "phase2_dense_supervision_packet.json",
        phase2_dense_supervision_answers_path=results_dir / "phase2_dense_supervision_answers.json",
        phase2_dense_supervision_answers_example_path=results_dir / "phase2_dense_supervision_answers.example.json",
        phase2_dense_heuristic_promotions_path=results_dir / "phase2_dense_heuristic_promotions.json",
        phase2_teacher_heuristic_promotions_path=results_dir / "phase2_teacher_heuristic_promotions.json",
        phase2_weak_visual_promotions_path=results_dir / "phase2_weak_visual_promotions.json",
        phase2_synthetic_sidecar_path=results_dir / "phase2_synthetic_sidecar.json",
        synthetic_sidecar_dir=results_dir / "synthetic_sidecar",
        phase2_priority_review_queue_path=results_dir / "phase2_priority_review_queue.json",
        phase2_dataset_stats_path=results_dir / "phase2_dataset_stats.json",
        phase2_bundle_dataset_path=results_dir / "phase2_bundle_dataset.jsonl",
        phase2_bundle_dataset_report_path=results_dir / "phase2_bundle_dataset_report.json",
        phase2_bundle_gold_seed_path=results_dir / "phase2_bundle_gold_seed.jsonl",
        phase2_bundle_gold_seed_report_path=results_dir / "phase2_bundle_gold_seed_report.json",
        benchmark_manifest_path=results_dir / "benchmark_manifest.json",
        bundle_benchmark_targets_path=data_dir / "bundle_benchmark_targets.json",
        fractal_state_spec_path=data_dir / "fractal_state_machine.json",
        phase2_report_path=results_dir / "phase2_report.json",
        phase4_report_path=results_dir / "phase4_report.json",
        workflow_loop_report_path=results_dir / "workflow_loop_report.json",
        workflow_status_path=results_dir / "workflow_status.json",
        workflow_history_path=results_dir / "workflow_history.jsonl",
        suggested_anchors_path=results_dir / "suggested_anchor_examples.json",
        corpus_expansion_report_path=results_dir / "corpus_expansion_report.json",
        predict_output_dir=results_dir / "predictions",
        chart_state_checkpoint_path=models_dir / "chart_state_ttrades_best.pth",
        chart_state_results_tsv_path=results_dir / "results_chart_state.tsv",
    )


def build_config(*, root_dir: Path | None = None) -> AppConfig:
    resolved_root = Path(root_dir or Path(__file__).resolve().parent).resolve()
    config = AppConfig(
        project_name=PROJECT_NAME,
        root_dir=resolved_root,
        seed=42,
        active_embedding_dim=768,
        mixed_precision=True,
        use_torch_compile=True,
        paths=_default_paths(resolved_root),
        wandb=WandBConfig(),
        phase1=Phase1Config(),
        phase2=Phase2Config(),
        phase3=Phase3Config(),
        phase4=Phase4Config(),
    )
    ensure_runtime_dirs(config)
    return config


def ensure_runtime_dirs(config: AppConfig) -> None:
    for directory in (
        config.paths.results_dir,
        config.paths.models_dir,
        config.paths.yolo_dir,
        config.paths.yolo_images_train_dir,
        config.paths.yolo_images_val_dir,
        config.paths.yolo_labels_train_dir,
        config.paths.yolo_labels_val_dir,
        config.paths.yolo_benchmark_dir,
        config.paths.yolo_benchmark_images_dir,
        config.paths.yolo_benchmark_labels_dir,
        config.paths.predict_output_dir,
        config.paths.dense_frame_dir,
        config.paths.screenshot_embedding_dir,
        config.paths.synthetic_sidecar_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)


def _serialize(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return {key: _serialize(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _serialize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize(item) for item in value]
    return value


def config_to_dict(config: AppConfig) -> dict[str, Any]:
    return _serialize(config)
