from __future__ import annotations

import json
from pathlib import Path

import torch

from config import build_config
from trainer.mlp_trainer import build_checkpoint_context_warnings, build_training_artifact_fingerprints, load_mlp_checkpoint_metadata


def test_checkpoint_metadata_warns_on_anchor_drift(tmp_path: Path) -> None:
    config = build_config(root_dir=tmp_path)
    config.paths.visual_embedding_index_path.parent.mkdir(parents=True, exist_ok=True)
    config.paths.anchors_path.parent.mkdir(parents=True, exist_ok=True)
    config.paths.phase1_pseudo_labels_path.parent.mkdir(parents=True, exist_ok=True)

    config.paths.visual_embedding_index_path.write_text(json.dumps({"items": []}), encoding="utf-8")
    config.paths.anchors_path.write_text(json.dumps({"anchors": [{"id": 1}]}), encoding="utf-8")
    config.paths.phase1_pseudo_labels_path.write_text('{"example_id":"a"}\n', encoding="utf-8")

    fingerprints = build_training_artifact_fingerprints(config)
    checkpoint_path = tmp_path / "mlp_test_checkpoint.pth"
    torch.save(
        {
            "state_dict": {},
            "label_to_index": {},
            "input_dim": 768,
            "hidden_dim": 128,
            "dropout": 0.1,
            "training_artifacts": fingerprints,
        },
        checkpoint_path,
    )

    config.paths.anchors_path.write_text(json.dumps({"anchors": [{"id": 2}]}), encoding="utf-8")

    metadata = load_mlp_checkpoint_metadata(checkpoint_path)
    warnings = build_checkpoint_context_warnings(metadata, config)

    assert any("Anchor manifest fingerprint mismatch" in warning for warning in warnings)
