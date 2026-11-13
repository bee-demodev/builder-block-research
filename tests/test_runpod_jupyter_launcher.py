from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
from urllib.parse import unquote

import pytest

from runtime import runpod_jupyter_launcher as launcher


def _remote_path_from_contents_api(path: str) -> str:
    api_path = path.split("?", 1)[0]
    assert api_path.startswith("/api/contents/")
    return unquote(api_path.removeprefix("/api/contents/")).strip("/")


def _write_pre_gpu_report(path: Path, *, gate: str = "pass") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    blocked = [] if gate == "pass" else ["label_studio_review_import"]
    path.write_text(
        json.dumps(
            {
                "summary": {
                    "pre_gpu_gate": gate,
                    "blocked_gate_names": blocked,
                    "blocking_reasons": [f"{name}:blocked" for name in blocked],
                }
            }
        ),
        encoding="utf-8",
    )


def test_parse_server_strips_token_from_url() -> None:
    base_url, token = launcher.parse_server("https://pod-8888.proxy.runpod.net/lab?token=abc123")

    assert base_url == "https://pod-8888.proxy.runpod.net/lab"
    assert token == "abc123"


def test_build_launch_script_runs_smoke_then_full() -> None:
    args = argparse.Namespace(
        install=True,
        smoke_epochs=12,
        imgsz=640,
        mode="both",
        run_dir="ttrades-yolo",
        remote_bundle_name="runpod_yolo_bundle.zip",
    )

    script = launcher.build_launch_script(args)

    assert "RUN_DIR=/workspace/ttrades-yolo" in script
    assert "unzip -q /workspace/runpod_yolo_bundle.zip -d \"$RUN_DIR\"" in script
    assert "python runtime/runpod_phase3_train.py --install --smoke --epochs 12 --imgsz 640" in script
    assert "python runtime/runpod_phase3_train.py 2>&1 | tee results/runpod_full.log" in script
    assert "echo DONE > /workspace/ttrades_yolo_run.done" in script


def test_pre_gpu_gate_status_reads_blocked_report(tmp_path: Path) -> None:
    report = tmp_path / "pre_gpu.json"
    _write_pre_gpu_report(report, gate="blocked")

    status = launcher.build_pre_gpu_gate_status(report)

    assert status["pre_gpu_gate"] == "blocked"
    assert status["blocked_gate_names"] == ["label_studio_review_import"]
    assert status["blocking_reasons"] == ["label_studio_review_import:blocked"]


def test_ensure_pre_gpu_ready_refuses_blocked_launch(tmp_path: Path) -> None:
    report = tmp_path / "pre_gpu.json"
    _write_pre_gpu_report(report, gate="blocked")

    with pytest.raises(SystemExit) as exc:
        launcher.ensure_pre_gpu_ready(report, allow_blocked=False)

    payload = json.loads(str(exc.value))
    assert payload["error"] == "pre_gpu_readiness_blocked"
    assert payload["pre_gpu_readiness"]["pre_gpu_gate"] == "blocked"


def test_main_checks_pre_gpu_before_jupyter_status(tmp_path: Path, monkeypatch) -> None:
    bundle = tmp_path / "bundle.zip"
    bundle.write_bytes(b"zip")
    report = tmp_path / "pre_gpu.json"
    _write_pre_gpu_report(report, gate="blocked")

    def fail_request_json(*_args, **_kwargs):
        raise AssertionError("Jupyter should not be contacted while pre-GPU gate is blocked.")

    monkeypatch.setattr(launcher, "request_json", fail_request_json)
    monkeypatch.setattr(
        "sys.argv",
        [
            "runpod_jupyter_launcher.py",
            "--action",
            "launch",
            "--base-url",
            "https://pod.example/lab",
            "--token",
            "secret",
            "--bundle",
            str(bundle),
            "--pre-gpu-report",
            str(report),
        ],
    )

    with pytest.raises(SystemExit) as exc:
        launcher.main()

    payload = json.loads(str(exc.value))
    assert payload["error"] == "pre_gpu_readiness_blocked"
    assert "secret" not in str(exc.value)


def test_list_remote_files_recurses_directory_models(monkeypatch) -> None:
    models = {
        "workspace/ttrades-yolo/results/benchmark_overlays/latest": {
            "type": "directory",
            "content": [
                {
                    "type": "file",
                    "path": "workspace/ttrades-yolo/results/benchmark_overlays/latest/root.jpg",
                },
                {
                    "type": "directory",
                    "path": "workspace/ttrades-yolo/results/benchmark_overlays/latest/nested",
                },
            ],
        },
        "workspace/ttrades-yolo/results/benchmark_overlays/latest/nested": {
            "type": "directory",
            "content": [
                {
                    "type": "file",
                    "path": "workspace/ttrades-yolo/results/benchmark_overlays/latest/nested/child.jpg",
                }
            ],
        },
    }

    def fake_try_request_json(_method: str, _base_url: str, path: str, _token: str, _payload=None):
        return models.get(_remote_path_from_contents_api(path))

    monkeypatch.setattr(launcher, "try_request_json", fake_try_request_json)

    files = launcher.list_remote_files(
        "https://pod.example",
        "token",
        "workspace/ttrades-yolo/results/benchmark_overlays/latest",
    )

    assert files == [
        "workspace/ttrades-yolo/results/benchmark_overlays/latest/root.jpg",
        "workspace/ttrades-yolo/results/benchmark_overlays/latest/nested/child.jpg",
    ]


def test_download_artifacts_pulls_core_files_and_overlay_tree(tmp_path: Path, monkeypatch) -> None:
    phase3_report = json.dumps({"best_val_mAP50_95": 0.25})
    overlay_bytes = b"jpg-bytes"
    models = {
        "workspace/ttrades-yolo/results/phase3_report.json": {
            "type": "file",
            "format": "text",
            "content": phase3_report,
        },
        "workspace/ttrades-yolo/models/yolo26_ttrades_markup_best.onnx": {
            "type": "file",
            "format": "base64",
            "content": base64.b64encode(b"onnx-bytes").decode("ascii"),
        },
        "workspace/ttrades-yolo/results/benchmark_overlays/latest": {
            "type": "directory",
            "content": [
                {
                    "type": "directory",
                    "path": "workspace/ttrades-yolo/results/benchmark_overlays/latest/hard_negatives",
                }
            ],
        },
        "workspace/ttrades-yolo/results/benchmark_overlays/latest/hard_negatives": {
            "type": "directory",
            "content": [
                {
                    "type": "file",
                    "path": "workspace/ttrades-yolo/results/benchmark_overlays/latest/hard_negatives/example.jpg",
                }
            ],
        },
        "workspace/ttrades-yolo/results/benchmark_overlays/latest/hard_negatives/example.jpg": {
            "type": "file",
            "format": "base64",
            "content": base64.b64encode(overlay_bytes).decode("ascii"),
        },
    }

    def fake_try_request_json(_method: str, _base_url: str, path: str, _token: str, _payload=None):
        return models.get(_remote_path_from_contents_api(path))

    monkeypatch.setattr(launcher, "try_request_json", fake_try_request_json)

    launcher.download_artifacts("https://pod.example", "token", "ttrades-yolo", tmp_path)

    assert (tmp_path / "phase3_report.json").read_text(encoding="utf-8") == phase3_report
    assert (tmp_path / "yolo26_ttrades_markup_best.onnx").read_bytes() == b"onnx-bytes"
    overlay_path = tmp_path / "results" / "benchmark_overlays" / "latest" / "hard_negatives" / "example.jpg"
    assert overlay_path.read_bytes() == overlay_bytes

    manifest = json.loads((tmp_path / "download_manifest.json").read_text(encoding="utf-8"))
    downloaded = {row["remote_path"]: row for row in manifest if row["status"] == "downloaded"}
    assert "workspace/ttrades-yolo/results/phase3_report.json" in downloaded
    assert "workspace/ttrades-yolo/results/benchmark_overlays/latest/hard_negatives/example.jpg" in downloaded
