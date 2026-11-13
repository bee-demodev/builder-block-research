import argparse
import json
from pathlib import Path

from runtime import runpod_ops


def _args(**overrides):
    values = {
        "base_url": None,
        "token": None,
        "bundle": Path("runtime/runpod_yolo_bundle.zip"),
        "run_dir": "ttrades-yolo",
        "mode": "both",
        "install": True,
        "smoke_epochs": 12,
        "imgsz": 640,
        "download_dir": Path("results/runpod_jupyter_download"),
        "pre_gpu_report": Path("results/pre_gpu_readiness_report.json"),
        "allow_blocked_pre_gpu": False,
        "tail_chars": 8000,
        "skip_overlays": False,
        "pod_id": None,
        "pod_name": None,
        "confirm_start": False,
        "confirm_stop": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


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


def test_resolve_config_extracts_token_from_url_without_persisting_it() -> None:
    args = _args(base_url="https://pod-8888.proxy.runpod.net/lab?token=secret")

    config = runpod_ops.resolve_config(args, environ={"RUNPOD_API_KEY": "api-secret"})

    assert config.base_url == "https://pod-8888.proxy.runpod.net/lab"
    assert config.token == "secret"
    assert config.has_runpod_api_key is True


def test_build_plan_reports_missing_credentials_and_bundle_status(tmp_path: Path) -> None:
    pre_gpu_report = tmp_path / "pre_gpu.json"
    _write_pre_gpu_report(pre_gpu_report)
    args = _args(bundle=tmp_path / "missing.zip", pre_gpu_report=pre_gpu_report)
    config = runpod_ops.resolve_config(args, environ={})

    plan = runpod_ops.build_plan(config)

    assert plan["can_launch"] is False
    assert plan["preferred_path"] == "ssh_or_jupyter_credentials_needed"
    assert "RUNPOD_JUPYTER_URL" in plan["missing"]
    assert "RUNPOD_JUPYTER_TOKEN" in plan["missing"]
    assert str(tmp_path / "missing.zip") in plan["missing"]
    assert plan["native_runpod_mcp"]["has_runpod_api_key"] is False
    assert plan["native_runpod_mcp"]["role"] == "infrastructure_management"
    assert plan["native_runpod_mcp"]["does_not_replace"] == "pod_jupyter_or_ssh_training_execution"


def test_build_plan_redacts_token_from_access_url(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle.zip"
    bundle.write_bytes(b"zip")
    pre_gpu_report = tmp_path / "pre_gpu.json"
    _write_pre_gpu_report(pre_gpu_report)
    args = _args(base_url="https://pod.example/lab?token=secret", bundle=bundle, pre_gpu_report=pre_gpu_report)
    config = runpod_ops.resolve_config(args, environ={})

    plan = runpod_ops.build_plan(config)

    assert plan["can_launch"] is True
    assert plan["preferred_path"] == "jupyter_api"
    assert plan["access"] == {
        "base_url": "https://pod.example/lab",
        "has_token": True,
    }
    assert json.dumps(plan).find("secret") == -1


def test_build_plan_blocks_launch_when_pre_gpu_gate_is_blocked(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle.zip"
    bundle.write_bytes(b"zip")
    pre_gpu_report = tmp_path / "pre_gpu.json"
    _write_pre_gpu_report(pre_gpu_report, gate="blocked")
    args = _args(base_url="https://pod.example/lab?token=secret", bundle=bundle, pre_gpu_report=pre_gpu_report)
    config = runpod_ops.resolve_config(args, environ={})

    plan = runpod_ops.build_plan(config)

    assert plan["can_launch"] is False
    assert plan["preferred_path"] == "pre_gpu_readiness_blocked"
    assert "pre_gpu_readiness_gate_pass" in plan["missing"]
    assert plan["pre_gpu_readiness"]["pre_gpu_gate"] == "blocked"
    assert plan["pre_gpu_readiness"]["blocked_gate_names"] == ["label_studio_review_import"]
    assert json.dumps(plan).find("secret") == -1


def test_build_plan_allows_explicit_pre_gpu_bypass(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle.zip"
    bundle.write_bytes(b"zip")
    pre_gpu_report = tmp_path / "pre_gpu.json"
    _write_pre_gpu_report(pre_gpu_report, gate="blocked")
    args = _args(
        base_url="https://pod.example/lab?token=secret",
        bundle=bundle,
        pre_gpu_report=pre_gpu_report,
        allow_blocked_pre_gpu=True,
    )
    config = runpod_ops.resolve_config(args, environ={})

    plan = runpod_ops.build_plan(config)

    assert plan["can_launch"] is True
    assert plan["preferred_path"] == "jupyter_api"
    assert plan["pre_gpu_readiness"]["allow_blocked_pre_gpu"] is True


def test_build_plan_reports_native_mcp_key_presence_without_secret(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle.zip"
    bundle.write_bytes(b"zip")
    pre_gpu_report = tmp_path / "pre_gpu.json"
    _write_pre_gpu_report(pre_gpu_report)
    args = _args(bundle=bundle, pre_gpu_report=pre_gpu_report)
    config = runpod_ops.resolve_config(args, environ={"RUNPOD_API_KEY": "api-secret"})

    plan = runpod_ops.build_plan(config)

    assert plan["native_runpod_mcp"]["has_runpod_api_key"] is True
    assert "@runpod/mcp-server" in plan["native_runpod_mcp"]["install_command"]
    assert json.dumps(plan).find("api-secret") == -1


def test_delegate_command_uses_launcher_without_token_arguments() -> None:
    args = _args()

    command = runpod_ops.build_delegate_command("launch", args)

    assert command[1].endswith("runpod_jupyter_launcher.py")
    assert "--action" in command
    assert "launch" in command
    assert "--install" in command
    assert "--pre-gpu-report" in command
    assert str(args.pre_gpu_report) in command
    assert "--token" not in command
    assert "--base-url" not in command


def test_delegate_command_forwards_explicit_pre_gpu_bypass() -> None:
    args = _args(allow_blocked_pre_gpu=True)

    command = runpod_ops.build_delegate_command("launch", args)

    assert "--allow-blocked-pre-gpu" in command


def test_run_delegate_refuses_launch_when_pre_gpu_gate_is_blocked(tmp_path: Path, capsys) -> None:
    bundle = tmp_path / "bundle.zip"
    bundle.write_bytes(b"zip")
    pre_gpu_report = tmp_path / "pre_gpu.json"
    _write_pre_gpu_report(pre_gpu_report, gate="blocked")
    args = _args(base_url="https://pod.example/lab?token=secret", bundle=bundle, pre_gpu_report=pre_gpu_report)
    config = runpod_ops.resolve_config(args, environ={})

    exit_code = runpod_ops.run_delegate("launch", args, config)
    err = capsys.readouterr().err

    assert exit_code == 2
    assert "pre_gpu_readiness_blocked" in err
    assert "secret" not in err


def test_sanitize_pod_status_reports_safe_shutdown_rule_without_env() -> None:
    pod = {
        "id": "pod-1",
        "name": "trainer",
        "desiredStatus": "RUNNING",
        "imageName": "runpod/pytorch",
        "gpuCount": 1,
        "costPerHr": 0.44,
        "publicIp": "127.0.0.1",
        "ports": ["8888/http", "22/tcp"],
        "portMappings": {"22": 22040},
        "volumeMountPath": "/workspace",
        "volumeInGb": 50,
        "containerDiskInGb": 30,
        "env": {
            "JUPYTER_PASSWORD": "secret",
        },
    }

    status = runpod_ops.sanitize_pod_status(pod)

    assert status["storage"]["volume_mount_path"] == "/workspace"
    assert status["storage"]["volume_in_gb"] == 50
    assert status["storage"]["has_network_volume"] is False
    assert status["storage"]["shutdown_action"] == "stop_pod_not_terminate"
    serialized = json.dumps(status)
    assert "secret" not in serialized
    assert "JUPYTER_PASSWORD" not in serialized


def test_sanitize_runpod_response_redacts_nested_runtime_secrets() -> None:
    payload = {
        "id": "pod-1",
        "env": {
            "JUPYTER_PASSWORD": "secret-password",
            "PUBLIC_KEY": "ssh-ed25519 AAAATEST",
        },
        "nested": {
            "apiToken": "secret-token",
            "safe": "visible",
        },
    }

    sanitized = runpod_ops.sanitize_runpod_response(payload)
    serialized = json.dumps(sanitized)

    assert sanitized["id"] == "pod-1"
    assert sanitized["env"] == "<redacted>"
    assert sanitized["nested"]["safe"] == "visible"
    assert "secret-password" not in serialized
    assert "secret-token" not in serialized
    assert "AAAATEST" not in serialized


def test_build_ssh_preflight_reports_commands_without_key_contents(tmp_path: Path, monkeypatch) -> None:
    ssh_dir = tmp_path / ".ssh"
    ssh_dir.mkdir()
    public_key = ssh_dir / "id_ed25519.pub"
    public_key.write_text("ssh-ed25519 AAAATEST user@example.com\n", encoding="utf-8")
    monkeypatch.setattr(runpod_ops.shutil, "which", lambda _name: None)
    pod = {
        "id": "pod-1",
        "name": "trainer",
        "desiredStatus": "RUNNING",
        "publicIp": "203.0.113.10",
        "portMappings": {"22": 22040},
        "volumeMountPath": "/workspace",
    }

    preflight = runpod_ops.build_ssh_preflight(pod, home_dir=tmp_path)

    assert preflight["can_attempt_full_ssh"] is True
    assert preflight["local"]["runpodctl_installed"] is False
    assert preflight["local"]["public_keys"][0]["key_type"] == "ssh-ed25519"
    assert preflight["local"]["preferred_private_key_path"].endswith("id_ed25519")
    assert preflight["commands"]["ssh"].startswith("ssh root@203.0.113.10 -p 22040")
    serialized = json.dumps(preflight)
    assert "AAAATEST" not in serialized


def test_build_ssh_preflight_reports_missing_inputs(tmp_path: Path) -> None:
    pod = {
        "id": "pod-1",
        "name": "trainer",
        "desiredStatus": "RUNNING",
        "portMappings": {},
    }

    preflight = runpod_ops.build_ssh_preflight(pod, home_dir=tmp_path)

    assert preflight["can_attempt_full_ssh"] is False
    assert preflight["commands"]["ssh"] is None
    assert set(preflight["missing"]) == {"public_ip", "ssh_port_22_mapping", "local_public_key"}


def test_select_pod_prefers_single_running_pod_when_no_selector() -> None:
    pods = [
        {"id": "old", "name": "old", "desiredStatus": "EXITED"},
        {"id": "run", "name": "trainer", "desiredStatus": "RUNNING"},
    ]

    assert runpod_ops.select_pod(pods, pod_id=None, pod_name=None)["id"] == "run"
    assert runpod_ops.select_pod(pods, pod_id="old", pod_name=None)["name"] == "old"
    assert runpod_ops.select_pod(pods, pod_id=None, pod_name="trainer")["id"] == "run"


def test_stop_selected_pod_requires_selector_and_confirmation(monkeypatch, capsys) -> None:
    monkeypatch.setenv("RUNPOD_API_KEY", "api-secret")

    missing_selector_code = runpod_ops.stop_selected_pod(_args(confirm_stop=True))
    missing_selector_err = capsys.readouterr().err
    assert missing_selector_code == 2
    assert "missing_pod_selector" in missing_selector_err

    missing_confirmation_code = runpod_ops.stop_selected_pod(_args(pod_id="pod-1"))
    missing_confirmation_err = capsys.readouterr().err
    assert missing_confirmation_code == 2
    assert "missing_confirm_stop" in missing_confirmation_err


def test_start_selected_pod_requires_selector_and_confirmation(monkeypatch, capsys) -> None:
    monkeypatch.setenv("RUNPOD_API_KEY", "api-secret")

    missing_selector_code = runpod_ops.start_selected_pod(_args(confirm_start=True))
    missing_selector_err = capsys.readouterr().err
    assert missing_selector_code == 2
    assert "missing_pod_selector" in missing_selector_err

    missing_confirmation_code = runpod_ops.start_selected_pod(_args(pod_id="pod-1"))
    missing_confirmation_err = capsys.readouterr().err
    assert missing_confirmation_code == 2
    assert "missing_confirm_start" in missing_confirmation_err


def test_start_selected_pod_calls_safe_start_endpoint(monkeypatch, capsys) -> None:
    monkeypatch.setenv("RUNPOD_API_KEY", "api-secret")
    calls = []

    def fake_fetch_pods(api_key: str):
        calls.append(("fetch", api_key))
        return [
            {
                "id": "pod-1",
                "name": "trainer",
                "desiredStatus": "EXITED",
                "volumeMountPath": "/workspace",
                "volumeInGb": 50,
                "containerDiskInGb": 30,
            }
        ]

    def fake_start_pod(api_key: str, pod_id: str):
        calls.append(("start", api_key, pod_id))
        return {"pod_id": pod_id, "http_status": 200, "response": {}}

    monkeypatch.setattr(runpod_ops, "fetch_pods", fake_fetch_pods)
    monkeypatch.setattr(runpod_ops, "start_pod", fake_start_pod)

    exit_code = runpod_ops.start_selected_pod(_args(pod_id="pod-1", confirm_start=True))
    output = capsys.readouterr().out

    assert exit_code == 0
    assert calls == [("fetch", "api-secret"), ("start", "api-secret", "pod-1")]
    assert "start_pod" in output
    assert "api-secret" not in output


def test_stop_selected_pod_calls_safe_stop_endpoint(monkeypatch, capsys) -> None:
    monkeypatch.setenv("RUNPOD_API_KEY", "api-secret")
    calls = []

    def fake_fetch_pods(api_key: str):
        calls.append(("fetch", api_key))
        return [
            {
                "id": "pod-1",
                "name": "trainer",
                "desiredStatus": "RUNNING",
                "volumeMountPath": "/workspace",
                "volumeInGb": 50,
                "containerDiskInGb": 30,
            }
        ]

    def fake_stop_pod(api_key: str, pod_id: str):
        calls.append(("stop", api_key, pod_id))
        return {"pod_id": pod_id, "http_status": 200, "response": {}}

    monkeypatch.setattr(runpod_ops, "fetch_pods", fake_fetch_pods)
    monkeypatch.setattr(runpod_ops, "stop_pod", fake_stop_pod)

    exit_code = runpod_ops.stop_selected_pod(_args(pod_id="pod-1", confirm_stop=True))
    output = capsys.readouterr().out

    assert exit_code == 0
    assert calls == [("fetch", "api-secret"), ("stop", "api-secret", "pod-1")]
    assert "stop_pod" in output
    assert "do not terminate" in output.lower()
    assert "api-secret" not in output


def test_stop_pod_builds_rest_stop_request(monkeypatch) -> None:
    captured = {}

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc, _tb):
            return None

        def read(self):
            return b"{}"

    def fake_urlopen(request, timeout):
        captured["full_url"] = request.full_url
        captured["method"] = request.get_method()
        captured["authorization"] = request.headers.get("Authorization")
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(runpod_ops, "urlopen", fake_urlopen)

    result = runpod_ops.stop_pod("api-secret", "pod-1", rest_api_url="https://rest.example/v1")

    assert result["http_status"] == 200
    assert captured == {
        "full_url": "https://rest.example/v1/pods/pod-1/stop",
        "method": "POST",
        "authorization": "Bearer api-secret",
        "timeout": 30,
    }


def test_start_pod_builds_rest_start_request(monkeypatch) -> None:
    captured = {}

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc, _tb):
            return None

        def read(self):
            return b"{}"

    def fake_urlopen(request, timeout):
        captured["full_url"] = request.full_url
        captured["method"] = request.get_method()
        captured["authorization"] = request.headers.get("Authorization")
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(runpod_ops, "urlopen", fake_urlopen)

    result = runpod_ops.start_pod("api-secret", "pod-1", rest_api_url="https://rest.example/v1")

    assert result["http_status"] == 200
    assert captured == {
        "full_url": "https://rest.example/v1/pods/pod-1/start",
        "method": "POST",
        "authorization": "Bearer api-secret",
        "timeout": 30,
    }
