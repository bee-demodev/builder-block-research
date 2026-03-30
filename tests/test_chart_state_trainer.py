from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import numpy as np
from config import build_config
from trainer.chart_state_trainer import load_bundle_training_rows, train_chart_state_classifier


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_bundle_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _bundle_row(bundle_id: str, base_path: str, stage: str) -> dict:
    return {
        "bundle_id": bundle_id,
        "path_family": "continuation",
        "continuation_vs_reversal": "continuation",
        "direction": "bullish",
        "fractal_stage": stage,
        "htf_timeframe": "daily_or_4h",
        "itf_timeframe": "1h",
        "ltf_timeframe": "5m",
        "htf_frame_path": f"{base_path}/context.png",
        "itf_frame_path": f"{base_path}/confirmation.png",
        "ltf_frame_path": f"{base_path}/outcome.png",
        "htf_bias": "bullish",
        "poi_type": "reaction_zone",
        "poi_direction": "bullish",
        "poi_source": "manual_review",
        "poi_validity": True,
        "setup_quality": "good_setup",
        "entry_state": "long_ready" if stage == "c4" else "wait",
        "invalidation_state": "intact",
        "session_context": "london",
        "kill_zone_alignment": "aligned",
        "detector_boxes_by_frame": {},
        "cue_summary": f"{bundle_id} summary",
        "review_outcome": "seed_gold",
        "provenance": ["unit"],
        "label_confidence": 0.9,
    }


def test_load_bundle_training_rows_and_train_chart_state(tmp_path: Path) -> None:
    frame_dir = tmp_path / "knowledge" / "ttfm_video_corpus" / "frames" / "demo"
    frame_dir.mkdir(parents=True, exist_ok=True)
    visual_frame = frame_dir / "context_0001.jpg"
    visual_frame.write_bytes(b"img")

    visual_manifest_path = tmp_path / "knowledge" / "ttfm_video_corpus" / "visual_embedding_manifest.json"
    visual_index_path = tmp_path / "knowledge" / "ttfm_video_corpus" / "visual_embedding_index.json"
    screenshot_manifest_path = tmp_path / "data" / "ttfm_screenshot_manifest.json"
    screenshot_embeddings_dir = tmp_path / "data" / "embeddings" / "screenshots"
    screenshot_embeddings_dir.mkdir(parents=True, exist_ok=True)

    _write_json(
        visual_manifest_path,
        {
            "model": "models/gemini-embedding-2-preview",
            "output_dimensionality": 4,
            "item_count": 1,
            "index_path": str(visual_index_path),
        },
    )
    _write_json(
        visual_index_path,
        {
            "model": "models/gemini-embedding-2-preview",
            "output_dimensionality": 4,
            "item_count": 1,
            "items": [
                {
                    "chunk_id": "demo::context",
                    "video_slug": "demo",
                    "title": "Demo",
                    "start": 1.0,
                    "end": 2.0,
                    "text": "bullish continuation long",
                    "vector": [1.0, 0.0, 0.0, 0.0],
                    "frame_path": str(visual_frame.relative_to(tmp_path)),
                    "checkpoint": "context",
                }
            ],
        },
    )

    attachments: list[dict] = []
    bundle_rows: list[dict] = []
    case_specs = [
        ("case_a", "c1"),
        ("case_b", "c2"),
        ("case_c", "c3"),
        ("case_d", "c4"),
    ]
    for index, (case_ref, stage) in enumerate(case_specs):
        screenshots_dir = tmp_path / "artifacts" / "ttfm" / "screenshots" / case_ref
        screenshots_dir.mkdir(parents=True, exist_ok=True)
        for checkpoint, offset in (("context", 0.0), ("confirmation", 1.0), ("outcome", 2.0)):
            image_path = screenshots_dir / f"{checkpoint}.png"
            image_path.write_bytes(b"png")
            np.save(
                screenshot_embeddings_dir / f"{case_ref}__{checkpoint}.npy",
                np.array([0.1 + index, 0.2 + offset, 0.3, 0.4], dtype=np.float32),
            )
            attachments.append(
                {
                    "case_ref": case_ref,
                    "checkpoint": checkpoint,
                    "screenshot_path": str(image_path.relative_to(tmp_path)),
                    "annotation_notes": [f"{case_ref} {checkpoint}"],
                }
            )
        bundle_rows.append(_bundle_row(f"{case_ref}::{stage}", f"artifacts/ttfm/screenshots/{case_ref}", stage))

    _write_json(screenshot_manifest_path, {"attachments": attachments})
    bundle_seed_path = tmp_path / "results" / "phase2_bundle_gold_seed.jsonl"
    _write_bundle_jsonl(bundle_seed_path, bundle_rows)

    config = build_config(root_dir=tmp_path)
    config = replace(
        config,
        active_embedding_dim=4,
        paths=replace(
            config.paths,
            visual_embedding_manifest_path=visual_manifest_path,
            visual_embedding_index_path=visual_index_path,
            screenshot_manifest_path=screenshot_manifest_path,
            screenshot_embedding_dir=screenshot_embeddings_dir,
            phase2_bundle_gold_seed_path=bundle_seed_path,
            chart_state_checkpoint_path=tmp_path / "models" / "chart_state_ttrades_best.pth",
            chart_state_results_tsv_path=tmp_path / "results" / "results_chart_state.tsv",
            phase4_report_path=tmp_path / "results" / "phase4_report.json",
        ),
        phase4=replace(
            config.phase4,
            hidden_dim=16,
            batch_size=2,
            max_epochs=6,
            patience=2,
            validation_ratio=0.25,
            min_train_examples=2,
            min_val_examples=1,
        ),
    )

    rows, skipped = load_bundle_training_rows(config)
    assert len(rows) == 4
    assert skipped["missing_frames"] == 0

    report = train_chart_state_classifier(config)

    assert report["usable_bundle_count"] == 4
    assert Path(report["checkpoint_path"]).exists()
    assert Path(report["results_tsv_path"]).exists()
    assert report["best_val_macro_accuracy"] >= 0.0
