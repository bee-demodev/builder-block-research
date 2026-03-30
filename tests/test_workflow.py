from __future__ import annotations

import json
from pathlib import Path

from config import build_config
from workflow import build_workflow_snapshot, write_workflow_reports


def test_build_workflow_snapshot_recommends_more_dense_labels(tmp_path: Path) -> None:
    config = build_config(root_dir=tmp_path)
    config.paths.results_dir.mkdir(parents=True, exist_ok=True)
    (config.paths.results_dir / "phase1_report.json").write_text(json.dumps({"best_val_F1_macro": 0.25}), encoding="utf-8")
    config.paths.phase2_dataset_stats_path.write_text(
        json.dumps({"train_count": 20, "val_count": 5}),
        encoding="utf-8",
    )
    config.paths.phase2_supervision_answers_path.write_text(
        json.dumps({"items": [{"example_id": "focused_a"}]}),
        encoding="utf-8",
    )
    (config.paths.results_dir / "phase3_report.json").write_text(json.dumps({"best_val_mAP50_95": 0.08}), encoding="utf-8")
    config.paths.phase2_dense_supervision_packet_path.write_text(
        json.dumps({"items": [{"example_id": "a"}, {"example_id": "b"}]}),
        encoding="utf-8",
    )
    config.paths.phase2_dense_supervision_answers_path.write_text(
        json.dumps({"items": [{"example_id": "a"}]}),
        encoding="utf-8",
    )
    config.paths.phase2_bundle_dataset_report_path.write_text(
        json.dumps(
            {
                "bundle_count": 7,
                "benchmark": {
                    "target_count": 18,
                    "satisfied_target_count": 5,
                    "unsatisfied_target_count": 13,
                    "coverage_ratio": 0.2778,
                },
            }
        ),
        encoding="utf-8",
    )
    config.paths.phase2_bundle_gold_seed_report_path.write_text(
        json.dumps(
            {
                "bundle_count": 11,
                "benchmark": {
                    "target_count": 18,
                    "satisfied_target_count": 2,
                    "unsatisfied_target_count": 16,
                    "coverage_ratio": 0.1111,
                },
            }
        ),
        encoding="utf-8",
    )
    config.paths.phase4_report_path.write_text(
        json.dumps({"best_val_macro_accuracy": 0.42}),
        encoding="utf-8",
    )

    snapshot = build_workflow_snapshot(config, completed_phase="phase3", phase_report={"ok": True})

    assert snapshot["metrics"]["dense_remaining_count"] == 1
    assert snapshot["metrics"]["focused_reviewed_count"] == 1
    assert snapshot["metrics"]["reviewed_answer_count"] == 2
    assert snapshot["metrics"]["bundle_record_count"] == 7
    assert snapshot["metrics"]["bundle_benchmark_satisfied_target_count"] == 5
    assert snapshot["metrics"]["bundle_gold_seed_count"] == 11
    assert snapshot["metrics"]["phase4_best_val_macro_accuracy"] == 0.42
    assert snapshot["assessment"]["next_action"] == "label_more_dense_examples"


def test_write_workflow_reports_persists_status_and_history(tmp_path: Path) -> None:
    config = build_config(root_dir=tmp_path)
    snapshot = write_workflow_reports(config, completed_phase="phase2", phase_report={"ok": True})

    assert config.paths.workflow_status_path.exists()
    assert config.paths.workflow_history_path.exists()
    assert json.loads(config.paths.workflow_status_path.read_text(encoding="utf-8"))["completed_phase"] == "phase2"
    assert json.loads(config.paths.workflow_history_path.read_text(encoding="utf-8").splitlines()[-1])["completed_phase"] == "phase2"
    assert snapshot["completed_phase"] == "phase2"
