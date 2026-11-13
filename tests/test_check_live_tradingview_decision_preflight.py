from __future__ import annotations

import json
from pathlib import Path

from scripts.check_live_tradingview_decision_preflight import build_preflight_report


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_corpus(tmp_path: Path) -> None:
    corpus_dir = tmp_path / "knowledge" / "ttfm_video_corpus"
    corpus_dir.mkdir(parents=True, exist_ok=True)
    (corpus_dir / "chunks.jsonl").write_text('{"text":"daily bias"}\n', encoding="utf-8")
    (corpus_dir / "visual_windows.jsonl").write_text('{"text":"sweep"}\n', encoding="utf-8")


def _runner(ok: bool):
    def command_runner(command: list[str], cwd: Path, timeout_seconds: int) -> dict:
        return {
            "ok": ok,
            "returncode": 0 if ok else 1,
            "stdout": '{"success":true}' if ok else '{"success":false,"error":"fetch failed"}',
            "stderr": "",
            "json": {"success": ok} if ok else {"success": False, "error": "fetch failed"},
        }

    return command_runner


def test_preflight_ready_when_required_live_checks_pass(tmp_path: Path) -> None:
    _write_corpus(tmp_path)
    cli = tmp_path / "tradingview-mcp" / "src" / "cli" / "index.js"
    cli.parent.mkdir(parents=True, exist_ok=True)
    cli.write_text("stub", encoding="utf-8")

    report = build_preflight_report(
        root_dir=tmp_path,
        cli_path=cli,
        command_runner=_runner(True),
        env={},
    )

    assert report["ready"] is True
    assert report["blocking_checks"] == []
    assert [check["name"] for check in report["warning_checks"]] == ["openai_api_key", "decision_packet"]
    assert report["next_action"] == "run_live_pipeline"


def test_preflight_blocks_when_cdp_unreachable(tmp_path: Path) -> None:
    _write_corpus(tmp_path)
    cli = tmp_path / "tradingview-mcp" / "src" / "cli" / "index.js"
    cli.parent.mkdir(parents=True, exist_ok=True)
    cli.write_text("stub", encoding="utf-8")

    report = build_preflight_report(
        root_dir=tmp_path,
        cli_path=cli,
        command_runner=_runner(False),
        env={"OPENAI_API_KEY": "present"},
    )

    assert report["ready"] is False
    assert [check["name"] for check in report["blocking_checks"]] == ["tradingview_cdp"]
    assert report["blocking_checks"][0]["status"] == "unreachable"
    assert "launch --port 9222 --no-kill" in report["blocking_checks"][0]["remediation"]["launch_command"]


def test_preflight_can_require_openai_key_and_packet(tmp_path: Path) -> None:
    _write_corpus(tmp_path)
    packet = tmp_path / "results" / "live_tradingview_decision_packet.json"
    _write_json(packet, {"decision_ready": False, "symbol": "CME_MINI:NQU2026", "blocked_reasons": ["small"]})
    cli = tmp_path / "tradingview-mcp" / "src" / "cli" / "index.js"
    cli.parent.mkdir(parents=True, exist_ok=True)
    cli.write_text("stub", encoding="utf-8")

    report = build_preflight_report(
        root_dir=tmp_path,
        packet_path=packet,
        cli_path=cli,
        require_openai_key=True,
        require_packet=True,
        command_runner=_runner(True),
        env={},
    )

    assert report["ready"] is False
    assert [check["name"] for check in report["blocking_checks"]] == ["openai_api_key", "decision_packet"]


def test_preflight_accepts_ready_packet_when_required(tmp_path: Path) -> None:
    _write_corpus(tmp_path)
    packet = tmp_path / "results" / "live_tradingview_decision_packet.json"
    _write_json(packet, {"decision_ready": True, "symbol": "CME_MINI:NQU2026", "blocked_reasons": []})
    cli = tmp_path / "tradingview-mcp" / "src" / "cli" / "index.js"
    cli.parent.mkdir(parents=True, exist_ok=True)
    cli.write_text("stub", encoding="utf-8")

    report = build_preflight_report(
        root_dir=tmp_path,
        packet_path=packet,
        cli_path=cli,
        require_openai_key=True,
        require_packet=True,
        command_runner=_runner(True),
        env={"OPENAI_API_KEY": "present"},
    )

    assert report["ready"] is True
    assert report["blocking_checks"] == []
    assert report["warning_checks"] == []


def test_preflight_can_attempt_launch_before_status(tmp_path: Path) -> None:
    _write_corpus(tmp_path)
    cli = tmp_path / "tradingview-mcp" / "src" / "cli" / "index.js"
    cli.parent.mkdir(parents=True, exist_ok=True)
    cli.write_text("stub", encoding="utf-8")
    calls: list[list[str]] = []

    def command_runner(command: list[str], cwd: Path, timeout_seconds: int) -> dict:
        calls.append(command)
        if "launch" in command:
            return {
                "ok": True,
                "returncode": 0,
                "stdout": '{"success":true,"cdp_port":9222}',
                "stderr": "",
                "json": {"success": True, "cdp_port": 9222},
            }
        return {
            "ok": True,
            "returncode": 0,
            "stdout": '{"success":true}',
            "stderr": "",
            "json": {"success": True},
        }

    report = build_preflight_report(
        root_dir=tmp_path,
        cli_path=cli,
        attempt_launch=True,
        command_runner=command_runner,
        env={"OPENAI_API_KEY": "present"},
    )

    assert report["ready"] is True
    assert calls[0][-4:] == ["launch", "--port", "9222", "--no-kill"]
    assert calls[1][-1] == "status"
    assert report["launch_attempt"]["ok"] is True
    assert report["launch_attempt"]["kill_existing"] is False
    assert report["blocking_checks"] == []
    assert report["tradingview_executable_discovery"]["status"] == "not_found"


def test_preflight_launch_can_allow_killing_existing_instances(tmp_path: Path) -> None:
    _write_corpus(tmp_path)
    cli = tmp_path / "tradingview-mcp" / "src" / "cli" / "index.js"
    cli.parent.mkdir(parents=True, exist_ok=True)
    cli.write_text("stub", encoding="utf-8")
    calls: list[list[str]] = []

    def command_runner(command: list[str], cwd: Path, timeout_seconds: int) -> dict:
        calls.append(command)
        return {
            "ok": True,
            "returncode": 0,
            "stdout": '{"success":true}',
            "stderr": "",
            "json": {"success": True},
        }

    report = build_preflight_report(
        root_dir=tmp_path,
        cli_path=cli,
        attempt_launch=True,
        launch_kill_existing=True,
        command_runner=command_runner,
        env={"OPENAI_API_KEY": "present"},
    )

    assert "--no-kill" not in calls[0]
    assert report["launch_attempt"]["kill_existing"] is True


def test_preflight_can_launch_explicit_tradingview_exe_before_status(tmp_path: Path) -> None:
    _write_corpus(tmp_path)
    cli = tmp_path / "tradingview-mcp" / "src" / "cli" / "index.js"
    cli.parent.mkdir(parents=True, exist_ok=True)
    cli.write_text("stub", encoding="utf-8")
    exe = tmp_path / "custom" / "TradingView.exe"
    exe.parent.mkdir(parents=True, exist_ok=True)
    exe.write_text("stub", encoding="utf-8")
    calls: list[list[str]] = []

    def command_runner(command: list[str], cwd: Path, timeout_seconds: int) -> dict:
        calls.append(command)
        if command[0] == "powershell":
            return {
                "ok": True,
                "returncode": 0,
                "stdout": '{"success":true,"pid":123,"cdp_port":9222}',
                "stderr": "",
                "json": {"success": True, "pid": 123, "cdp_port": 9222},
            }
        return {
            "ok": True,
            "returncode": 0,
            "stdout": '{"success":true}',
            "stderr": "",
            "json": {"success": True},
        }

    report = build_preflight_report(
        root_dir=tmp_path,
        cli_path=cli,
        attempt_launch=True,
        tradingview_exe_path=exe,
        command_runner=command_runner,
        env={"OPENAI_API_KEY": "present"},
    )

    assert calls[0][0] == "powershell"
    assert str(exe) in calls[0]
    assert "--remote-debugging-port=9222" in calls[0]
    assert calls[1][-1] == "status"
    assert report["launch_attempt"]["status"] == "launched_direct_exe"
    assert report["launch_attempt"]["path"] == "custom\\TradingView.exe"
    assert report["launch_attempt"]["kill_existing"] is False
    assert report["ready"] is True


def test_preflight_auto_uses_discovered_tradingview_exe(tmp_path: Path) -> None:
    _write_corpus(tmp_path)
    cli = tmp_path / "tradingview-mcp" / "src" / "cli" / "index.js"
    cli.parent.mkdir(parents=True, exist_ok=True)
    cli.write_text("stub", encoding="utf-8")
    local_app_data = tmp_path / "local_app_data"
    exe = local_app_data / "Programs" / "TradingView" / "TradingView.exe"
    exe.parent.mkdir(parents=True, exist_ok=True)
    exe.write_text("stub", encoding="utf-8")
    calls: list[list[str]] = []

    def command_runner(command: list[str], cwd: Path, timeout_seconds: int) -> dict:
        calls.append(command)
        if command[0] == "powershell":
            return {
                "ok": True,
                "returncode": 0,
                "stdout": '{"success":true,"pid":123,"cdp_port":9222}',
                "stderr": "",
                "json": {"success": True, "pid": 123, "cdp_port": 9222},
            }
        return {
            "ok": True,
            "returncode": 0,
            "stdout": '{"success":true}',
            "stderr": "",
            "json": {"success": True},
        }

    report = build_preflight_report(
        root_dir=tmp_path,
        cli_path=cli,
        attempt_launch=True,
        command_runner=command_runner,
        env={"LOCALAPPDATA": str(local_app_data), "OPENAI_API_KEY": "present"},
    )

    assert calls[0][0] == "powershell"
    assert str(exe) in calls[0]
    assert report["tradingview_executable_discovery"]["status"] == "found"
    assert report["tradingview_executable_discovery"]["selected_path"] == "local_app_data\\Programs\\TradingView\\TradingView.exe"
    assert report["launch_attempt"]["status"] == "launched_direct_exe"
    assert report["ready"] is True


def test_preflight_reports_missing_explicit_tradingview_exe(tmp_path: Path) -> None:
    _write_corpus(tmp_path)
    cli = tmp_path / "tradingview-mcp" / "src" / "cli" / "index.js"
    cli.parent.mkdir(parents=True, exist_ok=True)
    cli.write_text("stub", encoding="utf-8")
    missing_exe = tmp_path / "missing" / "TradingView.exe"
    calls: list[list[str]] = []

    def command_runner(command: list[str], cwd: Path, timeout_seconds: int) -> dict:
        calls.append(command)
        return {
            "ok": False,
            "returncode": 1,
            "stdout": '{"success":false,"error":"fetch failed"}',
            "stderr": "",
            "json": {"success": False, "error": "fetch failed"},
        }

    report = build_preflight_report(
        root_dir=tmp_path,
        cli_path=cli,
        attempt_launch=True,
        tradingview_exe_path=missing_exe,
        command_runner=command_runner,
        env={"OPENAI_API_KEY": "present"},
    )

    assert calls and calls[0][-1] == "status"
    assert all(call[0] != "powershell" for call in calls)
    assert report["launch_attempt"]["status"] == "missing_executable"
    assert report["launch_attempt"]["path"] == "missing\\TradingView.exe"
    assert report["ready"] is False


def test_preflight_reports_executable_discovery_candidates(tmp_path: Path) -> None:
    _write_corpus(tmp_path)
    cli = tmp_path / "tradingview-mcp" / "src" / "cli" / "index.js"
    cli.parent.mkdir(parents=True, exist_ok=True)
    cli.write_text("stub", encoding="utf-8")
    local_app_data = tmp_path / "local_app_data"

    report = build_preflight_report(
        root_dir=tmp_path,
        cli_path=cli,
        command_runner=_runner(False),
        env={"LOCALAPPDATA": str(local_app_data), "OPENAI_API_KEY": "present"},
    )

    discovery = report["tradingview_executable_discovery"]
    assert discovery["status"] == "not_found"
    assert discovery["selected_path"] == ""
    assert any(
        item["path"] == "local_app_data\\Programs\\TradingView\\TradingView.exe" and item["exists"] is False
        for item in discovery["candidates"]
    )
