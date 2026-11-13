from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


DEFAULT_PACKET_PATH = Path("results") / "live_tradingview_decision_packet.json"
DEFAULT_OUTPUT_PATH = Path("results") / "live_tradingview_decision_preflight.json"
DEFAULT_CLI_PATH = Path("tradingview-mcp") / "src" / "cli" / "index.js"
DEFAULT_CORPUS_PATHS = (
    Path("knowledge") / "ttfm_video_corpus" / "chunks.jsonl",
    Path("knowledge") / "ttfm_video_corpus" / "visual_windows.jsonl",
)
DEFAULT_CDP_PORT = 9222
CommandRunner = Callable[[list[str], Path, int], dict[str, Any]]


def resolve(root_dir: Path, path: str | Path) -> Path:
    raw_path = Path(path)
    return raw_path if raw_path.is_absolute() else (root_dir / raw_path).resolve()


def relative_or_absolute(path: Path, root_dir: Path) -> str:
    try:
        return str(path.resolve().relative_to(root_dir.resolve()))
    except ValueError:
        return str(path.resolve())


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def env_value(env: dict[str, str], *names: str) -> str:
    for name in names:
        if env.get(name):
            return str(env[name])
    return ""


def candidate_paths_from_env(env: dict[str, str]) -> list[tuple[str, Path]]:
    candidates: list[tuple[str, Path]] = []

    def add(source: str, value: str | Path | None) -> None:
        if value:
            candidates.append((source, Path(value)))

    add("TRADINGVIEW_EXE", env_value(env, "TRADINGVIEW_EXE"))
    local_app_data = env_value(env, "LOCALAPPDATA")
    if local_app_data:
        add("LOCALAPPDATA_standard", Path(local_app_data) / "TradingView" / "TradingView.exe")
        add("LOCALAPPDATA_programs", Path(local_app_data) / "Programs" / "TradingView" / "TradingView.exe")
        add(
            "LOCALAPPDATA_programs_desktop",
            Path(local_app_data) / "Programs" / "TradingView Desktop" / "TradingView.exe",
        )
    user_profile = env_value(env, "USERPROFILE", "HOME")
    if user_profile:
        add("USERPROFILE_local", Path(user_profile) / "AppData" / "Local" / "TradingView" / "TradingView.exe")
        add(
            "USERPROFILE_local_programs",
            Path(user_profile) / "AppData" / "Local" / "Programs" / "TradingView" / "TradingView.exe",
        )
    program_files = env_value(env, "PROGRAMFILES", "ProgramFiles")
    if program_files:
        add("PROGRAMFILES", Path(program_files) / "TradingView" / "TradingView.exe")
    program_files_x86 = env_value(env, "PROGRAMFILES(X86)", "ProgramFiles(x86)", "ProgramFilesX86")
    if program_files_x86:
        add("PROGRAMFILES_X86", Path(program_files_x86) / "TradingView" / "TradingView.exe")
    add("linux_opt_lower", Path("/opt/TradingView/tradingview"))
    add("linux_opt_upper", Path("/opt/TradingView/TradingView"))
    if user_profile:
        add("linux_user_local", Path(user_profile) / ".local" / "share" / "TradingView" / "TradingView")
    add("linux_usr_bin", Path("/usr/bin/tradingview"))
    return candidates


def discover_tradingview_executable(
    *,
    root_dir: Path,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    source_env = env if env is not None else os.environ
    seen: set[str] = set()
    candidates: list[dict[str, Any]] = []
    selected: Path | None = None
    for source, raw_path in candidate_paths_from_env(source_env):
        path = resolve(root_dir, raw_path)
        key = str(path).lower()
        if key in seen:
            continue
        seen.add(key)
        exists = path.exists()
        is_file = path.is_file()
        item = {
            "source": source,
            "path": relative_or_absolute(path, root_dir),
            "exists": exists,
            "is_file": is_file,
        }
        candidates.append(item)
        if selected is None and is_file:
            selected = path
    return {
        "name": "tradingview_executable_discovery",
        "ok": selected is not None,
        "status": "found" if selected else "not_found",
        "selected_path": relative_or_absolute(selected, root_dir) if selected else "",
        "selected_path_absolute": str(selected.resolve()) if selected else "",
        "candidate_count": len(candidates),
        "candidates": candidates,
    }


def default_command_runner(command: list[str], cwd: Path, timeout_seconds: int) -> dict[str, Any]:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError as exc:
        return {"ok": False, "returncode": None, "stdout": "", "stderr": str(exc)}
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "returncode": None,
            "stdout": exc.stdout or "",
            "stderr": f"timeout after {timeout_seconds}s",
        }
    stdout = result.stdout.strip()
    stderr = result.stderr.strip()
    parsed: Any = None
    if stdout:
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError:
            parsed = None
    ok = result.returncode == 0 and (not isinstance(parsed, dict) or parsed.get("success") is not False)
    return {
        "ok": ok,
        "returncode": result.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "json": parsed,
    }


def check_tradingview_cdp(
    *,
    root_dir: Path,
    cli_path: Path,
    timeout_seconds: int,
    command_runner: CommandRunner,
) -> dict[str, Any]:
    resolved_cli = resolve(root_dir, cli_path)
    if not resolved_cli.exists():
        return {
            "name": "tradingview_cdp",
            "ok": False,
            "status": "missing_cli",
            "path": relative_or_absolute(resolved_cli, root_dir),
            "message": "TradingView MCP CLI is missing.",
        }
    command = ["node", str(resolved_cli), "status"]
    result = command_runner(command, root_dir, timeout_seconds)
    message = ""
    payload = result.get("json")
    if isinstance(payload, dict):
        message = str(payload.get("error") or payload.get("message") or "")
    if not message:
        message = str(result.get("stderr") or result.get("stdout") or "")
    launch_command = ["node", str(resolved_cli), "launch", "--port", str(DEFAULT_CDP_PORT), "--no-kill"]
    return {
        "name": "tradingview_cdp",
        "ok": bool(result.get("ok")),
        "status": "reachable" if result.get("ok") else "unreachable",
        "command": " ".join(command),
        "message": message,
        "remediation": {
            "launch_command": " ".join(launch_command),
            "manual_command": f"TradingView.exe --remote-debugging-port={DEFAULT_CDP_PORT}",
            "custom_exe_command": (
                "python scripts\\check_live_tradingview_decision_preflight.py "
                "--launch-tradingview --tradingview-exe C:\\path\\to\\TradingView.exe"
            ),
            "note": "Use launch only when you want this workflow to start TradingView Desktop with CDP enabled.",
        },
    }


def launch_tradingview_exe(
    *,
    root_dir: Path,
    exe_path: Path,
    timeout_seconds: int,
    command_runner: CommandRunner,
    port: int = DEFAULT_CDP_PORT,
) -> dict[str, Any]:
    resolved_exe = resolve(root_dir, exe_path)
    if not resolved_exe.exists():
        return {
            "name": "tradingview_launch",
            "ok": False,
            "status": "missing_executable",
            "path": relative_or_absolute(resolved_exe, root_dir),
            "cdp_port": port,
            "kill_existing": False,
            "message": "TradingView executable path does not exist.",
        }
    script = (
        "$ErrorActionPreference = 'Stop'; "
        "$process = Start-Process -LiteralPath $args[0] -ArgumentList $args[1] -PassThru; "
        "[pscustomobject]@{ success = $true; pid = $process.Id; path = $args[0]; cdp_port = "
        + str(port)
        + " } | ConvertTo-Json -Compress"
    )
    command = [
        "powershell",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        script,
        str(resolved_exe),
        f"--remote-debugging-port={port}",
    ]
    result = command_runner(command, root_dir, timeout_seconds)
    message = ""
    payload = result.get("json")
    if isinstance(payload, dict):
        message = str(payload.get("error") or payload.get("warning") or payload.get("message") or "")
    if not message:
        message = str(result.get("stderr") or result.get("stdout") or "")
    return {
        "name": "tradingview_launch",
        "ok": bool(result.get("ok")),
        "status": "launched_direct_exe" if result.get("ok") else "launch_failed",
        "command": " ".join(command),
        "path": relative_or_absolute(resolved_exe, root_dir),
        "cdp_port": port,
        "kill_existing": False,
        "message": message,
    }


def launch_tradingview_cdp(
    *,
    root_dir: Path,
    cli_path: Path,
    timeout_seconds: int,
    command_runner: CommandRunner,
    port: int = DEFAULT_CDP_PORT,
    kill_existing: bool = False,
    exe_path: Path | None = None,
) -> dict[str, Any]:
    if exe_path is not None:
        return launch_tradingview_exe(
            root_dir=root_dir,
            exe_path=exe_path,
            timeout_seconds=timeout_seconds,
            command_runner=command_runner,
            port=port,
        )
    resolved_cli = resolve(root_dir, cli_path)
    if not resolved_cli.exists():
        return {
            "name": "tradingview_launch",
            "ok": False,
            "status": "missing_cli",
            "path": relative_or_absolute(resolved_cli, root_dir),
            "message": "TradingView MCP CLI is missing.",
        }
    command = ["node", str(resolved_cli), "launch", "--port", str(port)]
    if not kill_existing:
        command.append("--no-kill")
    result = command_runner(command, root_dir, timeout_seconds)
    message = ""
    payload = result.get("json")
    if isinstance(payload, dict):
        message = str(payload.get("error") or payload.get("warning") or payload.get("message") or "")
    if not message:
        message = str(result.get("stderr") or result.get("stdout") or "")
    return {
        "name": "tradingview_launch",
        "ok": bool(result.get("ok")),
        "status": "launched_or_already_running" if result.get("ok") else "launch_failed",
        "command": " ".join(command),
        "cdp_port": port,
        "kill_existing": kill_existing,
        "message": message,
    }


def check_openai_key(env: dict[str, str] | None = None) -> dict[str, Any]:
    source = env if env is not None else os.environ
    present_names = [
        name
        for name in ("OPENAI_API_KEY", "OPENAI_APIKEY", "OPENAI_KEY")
        if source.get(name)
    ]
    return {
        "name": "openai_api_key",
        "ok": bool(present_names),
        "status": "present" if present_names else "missing",
        "present_env_names": present_names,
        "message": "OpenAI API key is available." if present_names else "Set OPENAI_API_KEY to enable --call-vlm.",
    }


def check_decision_packet(*, root_dir: Path, packet_path: Path) -> dict[str, Any]:
    resolved_packet = resolve(root_dir, packet_path)
    payload = load_json(resolved_packet)
    if payload is None:
        return {
            "name": "decision_packet",
            "ok": False,
            "status": "missing_or_invalid",
            "path": relative_or_absolute(resolved_packet, root_dir),
            "message": "Run the capture pipeline to create a live TradingView decision packet.",
        }
    return {
        "name": "decision_packet",
        "ok": bool(payload.get("decision_ready")),
        "status": "decision_ready" if payload.get("decision_ready") else "not_decision_ready",
        "path": relative_or_absolute(resolved_packet, root_dir),
        "symbol": payload.get("symbol", ""),
        "blocked_reasons": payload.get("blocked_reasons", []),
        "message": "Decision packet is ready." if payload.get("decision_ready") else "Decision packet exists but is not decision-ready.",
    }


def check_corpus(*, root_dir: Path, corpus_paths: tuple[Path, ...] = DEFAULT_CORPUS_PATHS) -> dict[str, Any]:
    items = []
    for raw_path in corpus_paths:
        path = resolve(root_dir, raw_path)
        items.append(
            {
                "path": relative_or_absolute(path, root_dir),
                "exists": path.exists(),
                "size_bytes": path.stat().st_size if path.exists() else 0,
            }
        )
    ok = all(item["exists"] and item["size_bytes"] > 0 for item in items)
    return {
        "name": "ttrades_corpus",
        "ok": ok,
        "status": "present" if ok else "missing_or_empty",
        "items": items,
        "message": "TTrades retrieval corpus is present." if ok else "Required retrieval corpus files are missing or empty.",
    }


def build_preflight_report(
    *,
    root_dir: Path,
    packet_path: Path = DEFAULT_PACKET_PATH,
    cli_path: Path = DEFAULT_CLI_PATH,
    timeout_seconds: int = 8,
    require_packet: bool = False,
    require_openai_key: bool = False,
    attempt_launch: bool = False,
    launch_port: int = DEFAULT_CDP_PORT,
    launch_kill_existing: bool = False,
    tradingview_exe_path: Path | None = None,
    command_runner: CommandRunner = default_command_runner,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    source_env = env if env is not None else os.environ
    executable_discovery = discover_tradingview_executable(root_dir=root_dir, env=source_env)
    launch_exe_path = tradingview_exe_path
    if launch_exe_path is None and executable_discovery.get("selected_path_absolute"):
        launch_exe_path = Path(str(executable_discovery["selected_path_absolute"]))
    launch_attempt = (
        launch_tradingview_cdp(
            root_dir=root_dir,
            cli_path=cli_path,
            timeout_seconds=timeout_seconds,
            command_runner=command_runner,
            port=launch_port,
            kill_existing=launch_kill_existing,
            exe_path=launch_exe_path,
        )
        if attempt_launch
        else None
    )
    checks = [
        check_tradingview_cdp(
            root_dir=root_dir,
            cli_path=cli_path,
            timeout_seconds=timeout_seconds,
            command_runner=command_runner,
        ),
        check_openai_key(env),
        check_decision_packet(root_dir=root_dir, packet_path=packet_path),
        check_corpus(root_dir=root_dir),
    ]
    required = {"tradingview_cdp", "ttrades_corpus"}
    if require_packet:
        required.add("decision_packet")
    if require_openai_key:
        required.add("openai_api_key")
    blocking = [check for check in checks if check["name"] in required and not check["ok"]]
    warnings = [check for check in checks if check["name"] not in required and not check["ok"]]
    return {
        "mode": "live_tradingview_decision_preflight",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ready": not blocking,
        "required_checks": sorted(required),
        "blocking_checks": blocking,
        "warning_checks": warnings,
        "tradingview_executable_discovery": executable_discovery,
        "launch_attempt": launch_attempt,
        "checks": checks,
        "next_action": "run_live_pipeline" if not blocking else "fix_blocking_checks",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check prerequisites for the live TradingView TTrades decision pipeline.")
    parser.add_argument("--root-dir", type=Path, default=Path("."))
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    parser.add_argument("--cli", type=Path, default=DEFAULT_CLI_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--timeout-seconds", type=int, default=8)
    parser.add_argument("--require-packet", action="store_true")
    parser.add_argument("--require-openai-key", action="store_true")
    parser.add_argument("--launch-tradingview", action="store_true", help="Attempt to launch TradingView Desktop with CDP before checking status.")
    parser.add_argument("--launch-port", type=int, default=DEFAULT_CDP_PORT)
    parser.add_argument("--launch-kill-existing", action="store_true", help="Allow the MCP launcher to kill existing TradingView instances first.")
    parser.add_argument("--tradingview-exe", type=Path, default=None, help="Explicit TradingView.exe path for nonstandard installs.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root_dir = args.root_dir.resolve()
    output_path = resolve(root_dir, args.output)
    tradingview_exe = args.tradingview_exe
    if tradingview_exe is None and os.environ.get("TRADINGVIEW_EXE"):
        tradingview_exe = Path(os.environ["TRADINGVIEW_EXE"])
    report = build_preflight_report(
        root_dir=root_dir,
        packet_path=args.packet,
        cli_path=args.cli,
        timeout_seconds=args.timeout_seconds,
        require_packet=args.require_packet,
        require_openai_key=args.require_openai_key,
        attempt_launch=args.launch_tradingview,
        launch_port=args.launch_port,
        launch_kill_existing=args.launch_kill_existing,
        tradingview_exe_path=tradingview_exe,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output_path": str(output_path),
                "ready": report["ready"],
                "blocking_checks": [check["name"] for check in report["blocking_checks"]],
                "warning_checks": [check["name"] for check in report["warning_checks"]],
                "next_action": report["next_action"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
