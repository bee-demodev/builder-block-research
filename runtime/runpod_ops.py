from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

try:
    from runtime import runpod_jupyter_launcher as launcher
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    import runpod_jupyter_launcher as launcher  # type: ignore[no-redef]


@dataclass(frozen=True)
class RunPodOpsConfig:
    base_url: str | None
    token: str | None
    has_runpod_api_key: bool
    bundle: Path
    run_dir: str
    mode: str
    install: bool
    smoke_epochs: int
    imgsz: int
    download_dir: Path
    pre_gpu_report: Path
    allow_blocked_pre_gpu: bool

    @property
    def can_use_jupyter_api(self) -> bool:
        return bool(self.base_url and self.token)

    @property
    def pre_gpu_ready(self) -> bool:
        return self.allow_blocked_pre_gpu or build_pre_gpu_gate_status(self.pre_gpu_report)["pre_gpu_gate"] == "pass"


def _redact_url(value: str | None) -> str | None:
    if not value:
        return None
    base_url, token = launcher.parse_server(value)
    if token:
        return f"{base_url}?token=<redacted>"
    return base_url


def resolve_config(args: argparse.Namespace, environ: dict[str, str] | None = None) -> RunPodOpsConfig:
    env = environ if environ is not None else os.environ
    raw_base_url = args.base_url or env.get("RUNPOD_JUPYTER_URL")
    token = args.token or env.get("RUNPOD_JUPYTER_TOKEN")
    has_runpod_api_key = bool(env.get("RUNPOD_API_KEY"))
    base_url = None
    if raw_base_url:
        base_url, token_from_url = launcher.parse_server(raw_base_url)
        token = token or token_from_url

    return RunPodOpsConfig(
        base_url=base_url,
        token=token,
        has_runpod_api_key=has_runpod_api_key,
        bundle=args.bundle,
        run_dir=args.run_dir,
        mode=args.mode,
        install=args.install,
        smoke_epochs=args.smoke_epochs,
        imgsz=args.imgsz,
        download_dir=args.download_dir,
        pre_gpu_report=args.pre_gpu_report,
        allow_blocked_pre_gpu=args.allow_blocked_pre_gpu,
    )


def build_pre_gpu_gate_status(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "path": str(path),
            "exists": False,
            "pre_gpu_gate": "missing",
            "blocked_gate_names": ["pre_gpu_readiness_report"],
            "blocking_reasons": ["pre_gpu_readiness_report_missing"],
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "path": str(path),
            "exists": True,
            "pre_gpu_gate": "invalid",
            "blocked_gate_names": ["pre_gpu_readiness_report"],
            "blocking_reasons": [f"pre_gpu_readiness_report_invalid:{type(exc).__name__}"],
        }
    summary = payload.get("summary", {}) if isinstance(payload, dict) else {}
    if not isinstance(summary, dict):
        summary = {}
    return {
        "path": str(path),
        "exists": True,
        "pre_gpu_gate": str(summary.get("pre_gpu_gate") or "missing_summary"),
        "blocked_gate_names": list(summary.get("blocked_gate_names") or []),
        "blocking_reasons": list(summary.get("blocking_reasons") or []),
    }


def build_plan(config: RunPodOpsConfig) -> dict[str, Any]:
    missing: list[str] = []
    if not config.base_url:
        missing.append("RUNPOD_JUPYTER_URL")
    if not config.token:
        missing.append("RUNPOD_JUPYTER_TOKEN")
    if not config.bundle.exists():
        missing.append(str(config.bundle))
    pre_gpu = build_pre_gpu_gate_status(config.pre_gpu_report)
    if not config.allow_blocked_pre_gpu and pre_gpu["pre_gpu_gate"] != "pass":
        missing.append("pre_gpu_readiness_gate_pass")

    if config.can_use_jupyter_api and config.bundle.exists() and config.pre_gpu_ready:
        preferred_path = "jupyter_api"
        next_action = "launch"
    elif config.base_url and not config.token:
        preferred_path = "jupyter_api_waiting_for_token"
        next_action = "set_token"
    elif not config.pre_gpu_ready:
        preferred_path = "pre_gpu_readiness_blocked"
        next_action = "review_pre_gpu_gate"
    else:
        preferred_path = "ssh_or_jupyter_credentials_needed"
        next_action = "configure_access"

    return {
        "preferred_path": preferred_path,
        "next_action": next_action,
        "can_launch": config.can_use_jupyter_api and config.bundle.exists() and config.pre_gpu_ready,
        "missing": missing,
        "pre_gpu_readiness": {
            **pre_gpu,
            "allow_blocked_pre_gpu": config.allow_blocked_pre_gpu,
        },
        "access": {
            "base_url": _redact_url(config.base_url),
            "has_token": bool(config.token),
        },
        "native_runpod_mcp": {
            "has_runpod_api_key": config.has_runpod_api_key,
            "role": "infrastructure_management",
            "does_not_replace": "pod_jupyter_or_ssh_training_execution",
            "install_command": "codex mcp add runpod --env RUNPOD_API_KEY=$env:RUNPOD_API_KEY -- npx -y @runpod/mcp-server@latest",
        },
        "bundle": {
            "path": str(config.bundle),
            "exists": config.bundle.exists(),
            "bytes": config.bundle.stat().st_size if config.bundle.exists() else 0,
        },
        "commands": {
            "launch": "python runtime/runpod_ops.py --action launch --install --mode both",
            "status": "python runtime/runpod_ops.py --action status --tail-chars 8000",
            "download": "python runtime/runpod_ops.py --action download --download-dir results/runpod_jupyter_download",
            "pod_status": "python runtime/runpod_ops.py --action pod-status --pod-id <pod_id>",
            "ssh_preflight": "python runtime/runpod_ops.py --action ssh-preflight --pod-id <pod_id>",
            "start_pod": "python runtime/runpod_ops.py --action start-pod --pod-id <pod_id> --confirm-start",
            "stop_pod": "python runtime/runpod_ops.py --action stop-pod --pod-id <pod_id> --confirm-stop",
        },
    }


def fetch_pods(api_key: str, *, rest_api_url: str = "https://rest.runpod.io/v1") -> list[dict[str, Any]]:
    request = Request(
        f"{rest_api_url.rstrip('/')}/pods",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    with urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if isinstance(payload, list):
        return [pod for pod in payload if isinstance(pod, dict)]
    if isinstance(payload, dict) and "id" in payload:
        return [payload]
    if isinstance(payload, dict):
        for value in payload.values():
            if isinstance(value, list):
                return [pod for pod in value if isinstance(pod, dict)]
    return []


SENSITIVE_RESPONSE_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "env",
    "environment",
    "jupyter_password",
    "password",
    "public_key",
    "secret",
    "secrets",
    "token",
}


def sanitize_runpod_response(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, child in value.items():
            normalized = str(key).replace("-", "_").lower()
            if normalized in SENSITIVE_RESPONSE_KEYS or "password" in normalized or "token" in normalized:
                sanitized[str(key)] = "<redacted>"
            else:
                sanitized[str(key)] = sanitize_runpod_response(child)
        return sanitized
    if isinstance(value, list):
        return [sanitize_runpod_response(item) for item in value]
    return value


def stop_pod(api_key: str, pod_id: str, *, rest_api_url: str = "https://rest.runpod.io/v1") -> dict[str, Any]:
    request = Request(
        f"{rest_api_url.rstrip('/')}/pods/{pod_id}/stop",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    with urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8")
        payload = json.loads(body) if body.strip() else {}
    return {
        "pod_id": pod_id,
        "http_status": getattr(response, "status", None),
        "response": sanitize_runpod_response(payload),
    }


def start_pod(api_key: str, pod_id: str, *, rest_api_url: str = "https://rest.runpod.io/v1") -> dict[str, Any]:
    request = Request(
        f"{rest_api_url.rstrip('/')}/pods/{pod_id}/start",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    with urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8")
        payload = json.loads(body) if body.strip() else {}
    return {
        "pod_id": pod_id,
        "http_status": getattr(response, "status", None),
        "response": sanitize_runpod_response(payload),
    }


def select_pod(pods: list[dict[str, Any]], *, pod_id: str | None, pod_name: str | None) -> dict[str, Any] | None:
    if pod_id:
        return next((pod for pod in pods if str(pod.get("id", "")) == pod_id), None)
    if pod_name:
        return next((pod for pod in pods if str(pod.get("name", "")) == pod_name), None)
    if len(pods) == 1:
        return pods[0]
    running = [pod for pod in pods if str(pod.get("desiredStatus", "")).upper() == "RUNNING"]
    return running[0] if len(running) == 1 else None


def sanitize_pod_status(pod: dict[str, Any]) -> dict[str, Any]:
    volume_mount_path = str(pod.get("volumeMountPath") or "")
    has_network_volume = bool(
        pod.get("networkVolumeId")
        or pod.get("networkVolume")
        or pod.get("networkVolumeInfo")
    )
    return {
        "id": pod.get("id"),
        "name": pod.get("name"),
        "desired_status": pod.get("desiredStatus"),
        "image_name": pod.get("imageName"),
        "gpu_count": pod.get("gpuCount"),
        "cost_per_hr": pod.get("costPerHr"),
        "public_ip": pod.get("publicIp"),
        "ports": pod.get("ports", []),
        "port_mappings": pod.get("portMappings", {}),
        "storage": {
            "volume_mount_path": volume_mount_path,
            "volume_in_gb": pod.get("volumeInGb"),
            "container_disk_in_gb": pod.get("containerDiskInGb"),
            "has_network_volume": has_network_volume,
            "safe_resume_rule": (
                "Files under /workspace survive pod stops/restarts on volume disk, "
                "but are deleted if the pod is terminated unless a network volume or external backup is used."
            ),
            "shutdown_action": "stop_pod_not_terminate",
        },
    }


def local_ssh_public_keys(home_dir: Path | None = None) -> list[dict[str, Any]]:
    home = home_dir or Path.home()
    ssh_dir = home / ".ssh"
    summaries: list[dict[str, Any]] = []
    for key_name in ("id_ed25519.pub", "id_rsa.pub"):
        key_path = ssh_dir / key_name
        if not key_path.exists():
            summaries.append(
                {
                    "path": str(key_path),
                    "exists": False,
                    "key_type": None,
                    "chars": 0,
                }
            )
            continue
        text = key_path.read_text(encoding="utf-8", errors="replace").strip()
        key_type = text.split(" ", 1)[0] if text else None
        summaries.append(
            {
                "path": str(key_path),
                "exists": True,
                "key_type": key_type,
                "chars": len(text),
            }
        )
    return summaries


def build_ssh_preflight(pod: dict[str, Any], *, home_dir: Path | None = None) -> dict[str, Any]:
    status = sanitize_pod_status(pod)
    public_ip = str(status.get("public_ip") or "")
    port_mappings = status.get("port_mappings") or {}
    ssh_port = port_mappings.get("22") or port_mappings.get(22)
    key_summaries = local_ssh_public_keys(home_dir=home_dir)
    preferred_key = next((key for key in key_summaries if key["exists"] and key["key_type"] == "ssh-ed25519"), None)
    if preferred_key is None:
        preferred_key = next((key for key in key_summaries if key["exists"]), None)
    private_key_path = None
    if preferred_key:
        private_key_path = str(Path(str(preferred_key["path"])).with_suffix(""))
    can_attempt_full_ssh = bool(public_ip and ssh_port and private_key_path)
    return {
        "pod": {
            "id": status.get("id"),
            "name": status.get("name"),
            "desired_status": status.get("desired_status"),
            "public_ip": public_ip or None,
            "ssh_port": ssh_port,
        },
        "local": {
            "runpodctl_installed": shutil.which("runpodctl") is not None,
            "public_keys": key_summaries,
            "preferred_private_key_path": private_key_path,
        },
        "can_attempt_full_ssh": can_attempt_full_ssh,
        "commands": {
            "ssh": (
                f"ssh root@{public_ip} -p {ssh_port} -i {private_key_path}"
                if can_attempt_full_ssh
                else None
            ),
            "scp_bundle": (
                f"scp -P {ssh_port} -i {private_key_path} runtime/runpod_yolo_bundle.zip root@{public_ip}:/workspace/"
                if can_attempt_full_ssh
                else None
            ),
        },
        "missing": [
            name
            for name, missing in (
                ("public_ip", not public_ip),
                ("ssh_port_22_mapping", not ssh_port),
                ("local_public_key", private_key_path is None),
            )
            if missing
        ],
    }


def build_delegate_command(action: str, args: argparse.Namespace) -> list[str]:
    command = [
        sys.executable,
        str(Path(__file__).with_name("runpod_jupyter_launcher.py")),
        "--action",
        action,
        "--bundle",
        str(args.bundle),
        "--run-dir",
        args.run_dir,
        "--mode",
        args.mode,
        "--smoke-epochs",
        str(args.smoke_epochs),
        "--imgsz",
        str(args.imgsz),
        "--download-dir",
        str(args.download_dir),
        "--pre-gpu-report",
        str(args.pre_gpu_report),
        "--tail-chars",
        str(args.tail_chars),
    ]
    if args.install:
        command.append("--install")
    if args.allow_blocked_pre_gpu:
        command.append("--allow-blocked-pre-gpu")
    if args.skip_overlays:
        command.append("--skip-overlays")
    return command


def run_delegate(action: str, args: argparse.Namespace, config: RunPodOpsConfig) -> int:
    if not config.can_use_jupyter_api:
        print(json.dumps(build_plan(config), indent=2), file=sys.stderr)
        return 2
    if action == "launch" and not config.bundle.exists():
        print(json.dumps(build_plan(config), indent=2), file=sys.stderr)
        return 2
    if action == "launch" and not config.pre_gpu_ready:
        print(json.dumps(build_plan(config), indent=2), file=sys.stderr)
        return 2

    child_env = os.environ.copy()
    child_env["RUNPOD_JUPYTER_URL"] = config.base_url or ""
    child_env["RUNPOD_JUPYTER_TOKEN"] = config.token or ""
    completed = subprocess.run(build_delegate_command(action, args), env=child_env, check=False)
    return int(completed.returncode)


def print_pod_status(args: argparse.Namespace) -> int:
    api_key = os.environ.get("RUNPOD_API_KEY")
    if not api_key:
        print(
            json.dumps(
                {
                    "error": "missing_RUNPOD_API_KEY",
                    "message": "Set RUNPOD_API_KEY in the current process only.",
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2
    pods = fetch_pods(api_key)
    pod = select_pod(pods, pod_id=args.pod_id, pod_name=args.pod_name)
    if pod is None:
        print(
            json.dumps(
                {
                    "error": "pod_not_selected",
                    "available_pods": [
                        {
                            "id": pod.get("id"),
                            "name": pod.get("name"),
                            "desired_status": pod.get("desiredStatus"),
                        }
                        for pod in pods
                    ],
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(sanitize_pod_status(pod), indent=2))
    return 0


def print_ssh_preflight(args: argparse.Namespace) -> int:
    api_key = os.environ.get("RUNPOD_API_KEY")
    if not api_key:
        print(
            json.dumps(
                {
                    "error": "missing_RUNPOD_API_KEY",
                    "message": "Set RUNPOD_API_KEY in the current process only.",
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2
    pods = fetch_pods(api_key)
    pod = select_pod(pods, pod_id=args.pod_id, pod_name=args.pod_name)
    if pod is None:
        print(
            json.dumps(
                {
                    "error": "pod_not_selected",
                    "available_pods": [
                        {
                            "id": pod.get("id"),
                            "name": pod.get("name"),
                            "desired_status": pod.get("desiredStatus"),
                        }
                        for pod in pods
                    ],
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(build_ssh_preflight(pod), indent=2))
    return 0


def stop_selected_pod(args: argparse.Namespace) -> int:
    api_key = os.environ.get("RUNPOD_API_KEY")
    if not api_key:
        print(
            json.dumps(
                {
                    "error": "missing_RUNPOD_API_KEY",
                    "message": "Set RUNPOD_API_KEY in the current process only.",
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2
    if not args.pod_id and not args.pod_name:
        print(
            json.dumps(
                {
                    "error": "missing_pod_selector",
                    "message": "Pass --pod-id or --pod-name. Refusing to stop an implicit pod.",
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2
    if not args.confirm_stop:
        print(
            json.dumps(
                {
                    "error": "missing_confirm_stop",
                    "message": "Stopping interrupts the pod. Re-run with --confirm-stop to stop, not terminate, the selected pod.",
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2

    pods = fetch_pods(api_key)
    pod = select_pod(pods, pod_id=args.pod_id, pod_name=args.pod_name)
    if pod is None:
        print(
            json.dumps(
                {
                    "error": "pod_not_found",
                    "pod_id": args.pod_id,
                    "pod_name": args.pod_name,
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2

    pod_id = str(pod.get("id") or "").strip()
    if not pod_id:
        print(json.dumps({"error": "pod_missing_id"}, indent=2), file=sys.stderr)
        return 2

    try:
        stop_result = stop_pod(api_key, pod_id)
    except HTTPError as exc:
        print(
            json.dumps(
                {
                    "error": "stop_pod_failed",
                    "pod_id": pod_id,
                    "http_status": exc.code,
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1

    print(
        json.dumps(
            {
                "action": "stop_pod",
                "result": stop_result,
                "selected_pod": sanitize_pod_status(pod),
                "resume_note": "Stopped pods preserve /workspace volume disk, but do not terminate/delete this pod unless /workspace is backed up.",
            },
            indent=2,
        )
    )
    return 0


def start_selected_pod(args: argparse.Namespace) -> int:
    api_key = os.environ.get("RUNPOD_API_KEY")
    if not api_key:
        print(
            json.dumps(
                {
                    "error": "missing_RUNPOD_API_KEY",
                    "message": "Set RUNPOD_API_KEY in the current process only.",
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2
    if not args.pod_id and not args.pod_name:
        print(
            json.dumps(
                {
                    "error": "missing_pod_selector",
                    "message": "Pass --pod-id or --pod-name. Refusing to start an implicit pod.",
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2
    if not args.confirm_start:
        print(
            json.dumps(
                {
                    "error": "missing_confirm_start",
                    "message": "Starting can incur RunPod compute cost. Re-run with --confirm-start to start the selected pod.",
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2

    pods = fetch_pods(api_key)
    pod = select_pod(pods, pod_id=args.pod_id, pod_name=args.pod_name)
    if pod is None:
        print(
            json.dumps(
                {
                    "error": "pod_not_found",
                    "pod_id": args.pod_id,
                    "pod_name": args.pod_name,
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2

    pod_id = str(pod.get("id") or "").strip()
    if not pod_id:
        print(json.dumps({"error": "pod_missing_id"}, indent=2), file=sys.stderr)
        return 2

    try:
        start_result = start_pod(api_key, pod_id)
    except HTTPError as exc:
        print(
            json.dumps(
                {
                    "error": "start_pod_failed",
                    "pod_id": pod_id,
                    "http_status": exc.code,
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1

    print(
        json.dumps(
            {
                "action": "start_pod",
                "result": start_result,
                "selected_pod": sanitize_pod_status(pod),
                "resume_note": "After the pod reaches RUNNING, verify Jupyter/SSH access and keep training outputs under /workspace.",
            },
            indent=2,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="MCP-friendly local controller for the TTrades RunPod YOLO training loop."
    )
    parser.add_argument("--action", choices=["plan", "pod-status", "ssh-preflight", "start-pod", "stop-pod", "launch", "status", "download"], default="plan")
    parser.add_argument("--base-url", default=None, help="Jupyter base URL, optionally with ?token=...")
    parser.add_argument("--token", default=None, help="Jupyter token. Prefer env var; never commit it.")
    parser.add_argument("--bundle", type=Path, default=Path("runtime/runpod_yolo_bundle.zip"))
    parser.add_argument("--run-dir", default="ttrades-yolo")
    parser.add_argument("--mode", choices=["smoke", "full", "both"], default="both")
    parser.add_argument("--install", action="store_true")
    parser.add_argument("--smoke-epochs", type=int, default=12)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--download-dir", type=Path, default=Path("results/runpod_jupyter_download"))
    parser.add_argument("--pre-gpu-report", type=Path, default=Path("results/pre_gpu_readiness_report.json"))
    parser.add_argument(
        "--allow-blocked-pre-gpu",
        action="store_true",
        help="Explicitly bypass the pre-GPU readiness gate for launch. Do not use for normal paid training.",
    )
    parser.add_argument("--tail-chars", type=int, default=6000)
    parser.add_argument("--skip-overlays", action="store_true")
    parser.add_argument("--pod-id", default=None)
    parser.add_argument("--pod-name", default=None)
    parser.add_argument("--confirm-start", action="store_true", help="Required for --action start-pod.")
    parser.add_argument("--confirm-stop", action="store_true", help="Required for --action stop-pod.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = resolve_config(args)

    if args.action == "plan":
        print(json.dumps(build_plan(config), indent=2))
        return 0
    if args.action == "pod-status":
        return print_pod_status(args)
    if args.action == "ssh-preflight":
        return print_ssh_preflight(args)
    if args.action == "start-pod":
        return start_selected_pod(args)
    if args.action == "stop-pod":
        return stop_selected_pod(args)
    return run_delegate(args.action, args, config)


if __name__ == "__main__":
    raise SystemExit(main())
