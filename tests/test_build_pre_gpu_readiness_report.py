from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.build_pre_gpu_readiness_report import (
    DEFAULT_AUTO_PSEUDO_LABEL_REPORT,
    DEFAULT_AUTO_STATE_FIXTURES,
    DEFAULT_LABELSTUDIO_IMPORT_REPORT,
    DEFAULT_LABELSTUDIO_MANIFEST,
    DEFAULT_LINEAGE_MANIFEST,
    DEFAULT_RAW_MANIFEST,
    DEFAULT_RUNPOD_PLAN,
    DEFAULT_STATE_FIXTURES,
    build_pre_gpu_readiness_report,
    write_report,
)


def _write_json(root_dir: Path, relative_path: Path, payload: dict[str, Any]) -> None:
    path = root_dir / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_common_pass_inputs(root_dir: Path) -> None:
    _write_json(
        root_dir,
        DEFAULT_RAW_MANIFEST,
        {
            "required_symbols": ["NQ", "ES", "GC"],
            "summary": {
                "raw_data_gate": "pass",
                "missing_or_partial_required_symbols": [],
            },
        },
    )
    _write_json(
        root_dir,
        DEFAULT_LINEAGE_MANIFEST,
        {
            "summary": {
                "lineage_gate": "pass",
                "image_count": 9,
                "blocked_or_partial_symbols": [],
            },
        },
    )
    _write_json(
        root_dir,
        DEFAULT_LABELSTUDIO_MANIFEST,
        {
            "review_policy": {"allowed_actions": ["accept", "adjust", "reject", "defer"]},
            "task_count": 9,
            "missing_image_count": 0,
        },
    )
    _write_json(
        root_dir,
        DEFAULT_RUNPOD_PLAN,
        {
            "status": "ready_to_launch_when_jupyter_credentials_are_available",
            "next_experiment": {
                "name": "imgsz1280_scale_recall_probe",
                "command": "python runtime/runpod_jupyter_launcher.py --action launch --imgsz 1280",
            },
            "success_gate": {"minimum_benchmark_mAP50_95": 0.1},
        },
    )


def test_pre_gpu_readiness_report_blocks_scaffold_without_reviewed_truth(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.delenv("RUNPOD_JUPYTER_URL", raising=False)
    monkeypatch.delenv("RUNPOD_JUPYTER_TOKEN", raising=False)
    _write_common_pass_inputs(tmp_path)
    _write_json(
        tmp_path,
        DEFAULT_LABELSTUDIO_IMPORT_REPORT,
        {
            "training_gate": "blocked_no_reviewed_trainable_items",
            "validated_trainable_item_count": 0,
            "review_outcome_counts": {"ambiguous": 9},
            "issue_counts": {"missing_annotation": 9},
        },
    )
    _write_json(
        tmp_path,
        DEFAULT_STATE_FIXTURES,
        {
            "summary": {
                "fixture_gate": "pass",
                "fixture_count": 20,
                "expected_decision_counts": {"insufficient_evidence": 20},
                "missing_evidence_counts": {"directional_bias_unlabeled": 20},
            },
        },
    )

    report = build_pre_gpu_readiness_report(root_dir=tmp_path)

    assert report["summary"]["pre_gpu_gate"] == "blocked"
    assert report["summary"]["blocked_gate_names"] == [
        "label_studio_review_import",
        "state_builder_fixtures",
        "runpod_launch_environment",
    ]
    assert "label_studio_review_import:label_studio_training_gate_not_pass" in report["summary"]["blocking_reasons"]
    assert "state_builder_fixtures:state_fixture_decision_coverage_below_minimum" in report["summary"]["blocking_reasons"]
    assert "runpod_launch_environment:runpod_jupyter_credentials_missing" in report["summary"]["blocking_reasons"]


def test_pre_gpu_readiness_report_passes_when_review_state_and_launch_gates_pass(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("RUNPOD_JUPYTER_URL", "https://example.invalid")
    monkeypatch.setenv("RUNPOD_JUPYTER_TOKEN", "token")
    _write_common_pass_inputs(tmp_path)
    _write_json(
        tmp_path,
        DEFAULT_LABELSTUDIO_IMPORT_REPORT,
        {
            "training_gate": "pass",
            "validated_trainable_item_count": 3,
            "review_outcome_counts": {"accepted": 2, "adjusted": 1},
            "issue_counts": {},
        },
    )
    _write_json(
        tmp_path,
        DEFAULT_STATE_FIXTURES,
        {
            "summary": {
                "fixture_gate": "pass",
                "fixture_count": 20,
                "expected_decision_counts": {
                    "insufficient_evidence": 16,
                    "watch_only": 2,
                    "valid_long_setup": 1,
                    "no_trade": 1,
                },
                "missing_evidence_counts": {},
            },
        },
    )

    report = build_pre_gpu_readiness_report(root_dir=tmp_path)

    assert report["summary"]["pre_gpu_gate"] == "pass"
    assert report["summary"]["blocked_gate_names"] == []
    assert report["summary"]["status_counts"] == {"pass": 7}


def test_pre_gpu_readiness_report_passes_with_auto_pseudo_labels_and_auto_state(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("RUNPOD_JUPYTER_URL", "https://example.invalid")
    monkeypatch.setenv("RUNPOD_JUPYTER_TOKEN", "token")
    _write_common_pass_inputs(tmp_path)
    _write_json(
        tmp_path,
        DEFAULT_LABELSTUDIO_IMPORT_REPORT,
        {
            "training_gate": "blocked_no_reviewed_trainable_items",
            "validated_trainable_item_count": 0,
            "review_outcome_counts": {"ambiguous": 9},
            "issue_counts": {"missing_annotation": 9},
        },
    )
    _write_json(
        tmp_path,
        DEFAULT_AUTO_PSEUDO_LABEL_REPORT,
        {
            "auto_training_gate": "pass",
            "validated_trainable_item_count": 4,
            "class_counts": {"liquidity_sweep_high": 2, "liquidity_sweep_low": 2},
            "status_counts": {"auto_promoted_high_confidence": 4},
        },
    )
    _write_json(
        tmp_path,
        DEFAULT_STATE_FIXTURES,
        {
            "summary": {
                "fixture_gate": "pass",
                "fixture_count": 20,
                "expected_decision_counts": {"insufficient_evidence": 20},
                "missing_evidence_counts": {"directional_bias_unlabeled": 20},
            },
        },
    )
    _write_json(
        tmp_path,
        DEFAULT_AUTO_STATE_FIXTURES,
        {
            "summary": {
                "fixture_gate": "pass",
                "fixture_count": 1,
                "expected_decision_counts": {"watch_only": 1},
                "missing_evidence_counts": {},
            },
        },
    )

    report = build_pre_gpu_readiness_report(root_dir=tmp_path)
    gates = {item["name"]: item for item in report["gates"]}

    assert report["summary"]["pre_gpu_gate"] == "pass"
    assert report["summary"]["blocked_gate_names"] == []
    assert gates["label_studio_review_import"]["evidence"]["selected_label_source"] == "auto_pseudo_labels"
    assert gates["state_builder_fixtures"]["evidence"]["selected_state_source"] == "auto_state_fixtures"


def test_write_report_creates_output_file(tmp_path: Path) -> None:
    payload = {"summary": {"pre_gpu_gate": "blocked"}, "gates": []}

    write_report(payload, root_dir=tmp_path, output_path=Path("results") / "pre_gpu.json")

    written = tmp_path / "results" / "pre_gpu.json"
    assert json.loads(written.read_text(encoding="utf-8")) == payload
