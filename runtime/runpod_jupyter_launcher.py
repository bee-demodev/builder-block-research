from __future__ import annotations

import argparse
import base64
import json
import os
import ssl
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import parse_qs, quote, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen


def parse_server(value: str) -> tuple[str, str | None]:
    parsed = urlparse(value)
    query = parse_qs(parsed.query)
    token = query.get("token", [None])[0]
    clean = parsed._replace(query="", fragment="")
    return urlunparse(clean).rstrip("/"), token


def request_json(method: str, base_url: str, path: str, token: str, payload: dict[str, Any] | None = None) -> Any:
    url = f"{base_url}{path}"
    query = urlencode({"token": token})
    sep = "&" if "?" in url else "?"
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = Request(f"{url}{sep}{query}", data=data, headers=headers, method=method)
    with urlopen(req, timeout=30, context=ssl.create_default_context()) as response:
        body = response.read().decode("utf-8")
        return json.loads(body) if body else {}


def try_request_json(method: str, base_url: str, path: str, token: str, payload: dict[str, Any] | None = None) -> Any | None:
    try:
        return request_json(method, base_url, path, token, payload)
    except HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def contents_path(remote_path: str, *, content: bool = True) -> str:
    cleaned = remote_path.strip("/")
    path = f"/api/contents/{quote(cleaned)}"
    if content:
        path += "?content=1"
    return path


def put_file(base_url: str, token: str, local_path: Path, remote_path: str) -> None:
    payload = {
        "type": "file",
        "format": "base64",
        "content": base64.b64encode(local_path.read_bytes()).decode("ascii"),
    }
    request_json("PUT", base_url, f"/api/contents/{remote_path.strip('/')}", token, payload)


def put_text(base_url: str, token: str, text: str, remote_path: str) -> None:
    payload = {"type": "file", "format": "text", "content": text}
    request_json("PUT", base_url, f"/api/contents/{remote_path.strip('/')}", token, payload)


def get_remote_file(base_url: str, token: str, remote_path: str) -> tuple[bytes, str] | None:
    model = try_request_json("GET", base_url, contents_path(remote_path), token)
    if model is None or model.get("type") != "file":
        return None
    content = model.get("content") or ""
    file_format = model.get("format") or "text"
    if file_format == "base64":
        return base64.b64decode(content), file_format
    return str(content).encode("utf-8"), file_format


def list_remote_files(base_url: str, token: str, remote_path: str) -> list[str]:
    model = try_request_json("GET", base_url, contents_path(remote_path), token)
    if model is None:
        return []
    model_type = model.get("type")
    if model_type == "file":
        return [str(model.get("path") or remote_path).strip("/")]
    if model_type != "directory":
        return []

    files: list[str] = []
    for child in model.get("content") or []:
        child_path = str(child.get("path") or f"{remote_path.strip('/')}/{child.get('name', '')}").strip("/")
        if child.get("type") == "file":
            files.append(child_path)
        elif child.get("type") == "directory":
            files.extend(list_remote_files(base_url, token, child_path))
    return files


def get_remote_text(base_url: str, token: str, remote_path: str, *, tail_chars: int | None = None) -> str | None:
    remote = get_remote_file(base_url, token, remote_path)
    if remote is None:
        return None
    text = remote[0].decode("utf-8", errors="replace")
    if tail_chars is not None and len(text) > tail_chars:
        return text[-tail_chars:]
    return text


def websocket_url(base_url: str, token: str, terminal_name: str) -> str:
    parsed = urlparse(base_url)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    query = urlencode({"token": token})
    return urlunparse((scheme, parsed.netloc, f"/terminals/websocket/{terminal_name}", "", query, ""))


def start_terminal_command(base_url: str, token: str, command: str) -> str:
    try:
        import websocket  # type: ignore[import-not-found]
    except ImportError as exc:
        raise SystemExit(
            "Starting a Jupyter terminal requires websocket-client. "
            "Install it locally with: python -m pip install websocket-client"
        ) from exc

    terminal = request_json("POST", base_url, "/api/terminals", token, {})
    name = terminal["name"]
    ws = websocket.create_connection(websocket_url(base_url, token, name), timeout=20)
    try:
        ws.send(json.dumps(["stdin", command + "\n"]))
    finally:
        ws.close()
    return name


def print_remote_status(base_url: str, token: str, run_dir: str, *, tail_chars: int) -> None:
    status = request_json("GET", base_url, "/api/status", token)
    print(f"Jupyter status ok: {status.get('started') or 'reachable'}")
    for remote_path in [
        "workspace/ttrades_yolo_run.pid",
        "workspace/ttrades_yolo_run.done",
        "workspace/ttrades_yolo_run.log",
        f"workspace/{run_dir}/results/runpod_smoke.log",
        f"workspace/{run_dir}/results/runpod_full.log",
        f"workspace/{run_dir}/results/phase3_report.json",
    ]:
        text = get_remote_text(base_url, token, remote_path, tail_chars=tail_chars)
        if text is None:
            print(f"missing: /{remote_path}")
            continue
        print(f"\n--- /{remote_path} ---")
        print(text.rstrip())


def download_artifacts(
    base_url: str,
    token: str,
    run_dir: str,
    output_dir: Path,
    *,
    include_overlays: bool = True,
    overlay_dir: str = "results/benchmark_overlays/latest",
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    remote_paths = [
        "workspace/ttrades_yolo_run.pid",
        "workspace/ttrades_yolo_run.done",
        "workspace/ttrades_yolo_run.log",
        f"workspace/{run_dir}/results/runpod_smoke.log",
        f"workspace/{run_dir}/results/runpod_full.log",
        f"workspace/{run_dir}/results/phase3_report.json",
        f"workspace/{run_dir}/results/results_yolo.tsv",
        f"workspace/{run_dir}/models/yolo26_ttrades_markup_best.pt",
        f"workspace/{run_dir}/models/yolo26_ttrades_markup_best.onnx",
    ]
    overlay_prefix = f"workspace/{run_dir}/{overlay_dir.strip('/')}"
    if include_overlays:
        remote_paths.extend(list_remote_files(base_url, token, overlay_prefix))

    manifest: list[dict[str, Any]] = []
    for remote_path in remote_paths:
        remote = get_remote_file(base_url, token, remote_path)
        if remote is None:
            manifest.append({"remote_path": remote_path, "status": "missing"})
            print(f"missing: /{remote_path}")
            continue
        data, file_format = remote
        if remote_path.startswith(overlay_prefix):
            local_path = output_dir / Path(remote_path).relative_to(f"workspace/{run_dir}")
        else:
            local_path = output_dir / Path(remote_path).name
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(data)
        manifest.append(
            {
                "remote_path": remote_path,
                "local_path": str(local_path),
                "status": "downloaded",
                "bytes": len(data),
                "format": file_format,
            }
        )
        print(f"downloaded: /{remote_path} -> {local_path}")
    (output_dir / "download_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def build_launch_script(args: argparse.Namespace) -> str:
    install_flag = " --install" if args.install else ""
    smoke_line = (
        f"python runtime/runpod_phase3_train.py{install_flag} --smoke "
        f"--epochs {args.smoke_epochs} --imgsz {args.imgsz} 2>&1 | tee results/runpod_smoke.log"
    )
    full_line = "python runtime/runpod_phase3_train.py 2>&1 | tee results/runpod_full.log"
    run_lines = []
    if args.mode in {"smoke", "both"}:
        run_lines.append(smoke_line)
    if args.mode in {"full", "both"}:
        run_lines.append(full_line)

    return "\n".join(
        [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            f"RUN_DIR=/workspace/{args.run_dir}",
            "cd /workspace",
            "rm -rf \"$RUN_DIR\"",
            "mkdir -p \"$RUN_DIR\"",
            f"unzip -q /workspace/{args.remote_bundle_name} -d \"$RUN_DIR\"",
            "cd \"$RUN_DIR\"",
            "nvidia-smi",
            *run_lines,
            "echo DONE > /workspace/ttrades_yolo_run.done",
        ]
    ) + "\n"


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


def ensure_pre_gpu_ready(path: Path, *, allow_blocked: bool) -> None:
    status = build_pre_gpu_gate_status(path)
    if allow_blocked or status["pre_gpu_gate"] == "pass":
        return
    raise SystemExit(
        json.dumps(
            {
                "error": "pre_gpu_readiness_blocked",
                "pre_gpu_readiness": status,
                "message": "Refusing to launch RunPod training before the pre-GPU readiness gate passes.",
            },
            indent=2,
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Upload and launch the TTrades YOLO bundle on a RunPod Jupyter server.")
    parser.add_argument("--action", choices=["launch", "status", "download"], default="launch")
    parser.add_argument("--base-url", default=os.environ.get("RUNPOD_JUPYTER_URL"), help="Jupyter base URL, optionally with ?token=...")
    parser.add_argument("--token", default=os.environ.get("RUNPOD_JUPYTER_TOKEN"), help="Jupyter token. Prefer env var; never commit it.")
    parser.add_argument("--bundle", type=Path, default=Path("runtime/runpod_yolo_bundle.zip"))
    parser.add_argument("--remote-bundle-name", default="runpod_yolo_bundle.zip")
    parser.add_argument("--run-dir", default="ttrades-yolo")
    parser.add_argument("--mode", choices=["smoke", "full", "both"], default="both")
    parser.add_argument("--install", action="store_true", help="Install runtime deps during the smoke command.")
    parser.add_argument("--smoke-epochs", type=int, default=12)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--no-start", action="store_true", help="Upload files only; do not open a Jupyter terminal.")
    parser.add_argument("--tail-chars", type=int, default=6000, help="Characters to print from each remote log during --action status.")
    parser.add_argument("--download-dir", type=Path, default=Path("results/runpod_jupyter_download"), help="Local output dir for --action download.")
    parser.add_argument("--pre-gpu-report", type=Path, default=Path("results/pre_gpu_readiness_report.json"))
    parser.add_argument(
        "--allow-blocked-pre-gpu",
        action="store_true",
        help="Explicitly bypass the pre-GPU readiness gate for launch. Do not use for normal paid training.",
    )
    parser.add_argument("--skip-overlays", action="store_true", help="Do not recursively download benchmark overlay images.")
    parser.add_argument("--overlay-dir", default="results/benchmark_overlays/latest", help="Remote overlay directory under the run dir.")
    args = parser.parse_args()

    if not args.base_url:
        raise SystemExit("Set RUNPOD_JUPYTER_URL or pass --base-url.")
    base_url, token_from_url = parse_server(args.base_url)
    token = args.token or token_from_url
    if not token:
        raise SystemExit("Set RUNPOD_JUPYTER_TOKEN, pass --token, or include ?token=... in --base-url.")
    if args.action == "launch" and not args.bundle.exists():
        raise SystemExit(f"Bundle not found: {args.bundle}")
    if args.action == "launch":
        ensure_pre_gpu_ready(args.pre_gpu_report, allow_blocked=args.allow_blocked_pre_gpu)

    try:
        status = request_json("GET", base_url, "/api/status", token)
    except HTTPError as exc:
        raise SystemExit(f"Jupyter status check failed: HTTP {exc.code}") from exc

    if args.action == "status":
        print_remote_status(base_url, token, args.run_dir, tail_chars=args.tail_chars)
        return 0

    if args.action == "download":
        print(f"Jupyter status ok: {status.get('started') or 'reachable'}")
        download_artifacts(
            base_url,
            token,
            args.run_dir,
            args.download_dir,
            include_overlays=not args.skip_overlays,
            overlay_dir=args.overlay_dir,
        )
        print(f"Download manifest: {args.download_dir / 'download_manifest.json'}")
        return 0

    remote_bundle = f"workspace/{args.remote_bundle_name}"
    remote_script = "workspace/run_ttrades_yolo.sh"
    launch_script = build_launch_script(args)
    put_file(base_url, token, args.bundle, remote_bundle)
    put_text(base_url, token, launch_script, remote_script)

    print(f"Jupyter status ok: {status.get('started') or 'reachable'}")
    print(f"Uploaded bundle to /{remote_bundle}")
    print(f"Uploaded launcher to /{remote_script}")
    print("Token was read only from process arguments/environment and was not written to disk.")

    if args.no_start:
        print("Start command to run in the pod terminal:")
        print("bash /workspace/run_ttrades_yolo.sh")
        return 0

    terminal_name = start_terminal_command(
        base_url,
        token,
        "nohup bash /workspace/run_ttrades_yolo.sh > /workspace/ttrades_yolo_run.log 2>&1 & echo $! > /workspace/ttrades_yolo_run.pid",
    )
    print(f"Started training in Jupyter terminal: {terminal_name}")
    print("Poll /workspace/ttrades_yolo_run.log and /workspace/ttrades_yolo_run.done for progress.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
