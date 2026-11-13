from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw

from config import build_config
from labeler.tradingview_weak_labeler import capture_live_tradingview_bundle


def _write_chart(path: Path, pattern: str, *, size: tuple[int, int] = (128, 128)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    width, height = size
    image = Image.new("RGB", size, (246, 246, 246))
    draw = ImageDraw.Draw(image)
    line_width = max(4, min(width, height) // 80)
    if pattern == "up":
        draw.line(
            (
                int(width * 0.08),
                int(height * 0.86),
                int(width * 0.40),
                int(height * 0.55),
                int(width * 0.92),
                int(height * 0.14),
            ),
            fill=(20, 20, 20),
            width=line_width,
        )
        draw.rectangle(
            (
                int(width * 0.22),
                int(height * 0.48),
                int(width * 0.55),
                int(height * 0.72),
            ),
            outline=(25, 25, 25),
            width=line_width,
        )
    elif pattern == "down":
        draw.line(
            (
                int(width * 0.08),
                int(height * 0.14),
                int(width * 0.40),
                int(height * 0.55),
                int(width * 0.92),
                int(height * 0.86),
            ),
            fill=(20, 20, 20),
            width=line_width,
        )
        draw.rectangle(
            (
                int(width * 0.45),
                int(height * 0.34),
                int(width * 0.78),
                int(height * 0.60),
            ),
            outline=(25, 25, 25),
            width=line_width,
        )
    elif pattern == "box":
        draw.rectangle(
            (
                int(width * 0.16),
                int(height * 0.16),
                int(width * 0.84),
                int(height * 0.84),
            ),
            outline=(20, 20, 20),
            width=line_width,
        )
        draw.line(
            (
                int(width * 0.16),
                int(height * 0.84),
                int(width * 0.84),
                int(height * 0.16),
            ),
            fill=(20, 20, 20),
            width=line_width,
        )
    else:
        raise ValueError(pattern)
    image.save(path)


def _fake_runner(source_files: dict[str, Path]):
    state_by_resolution = {
        "D": {"success": True, "symbol": "CME_MINI:ESM2026", "resolution": "1D"},
        "60": {"success": True, "symbol": "CME_MINI:ESM2026", "resolution": "60"},
        "5": {"success": True, "symbol": "CME_MINI:ESM2026", "resolution": "5"},
    }
    active_resolution = {"value": "60"}
    pane_state = {"layout": "4", "active_index": 2}
    window_bounds = {"left": 100, "top": 50, "width": 1440, "height": 900, "windowState": "normal"}

    def fake_cli_runner(args: list[str]) -> dict:
        command = tuple(args)
        if command == ("state",):
            return dict(state_by_resolution[active_resolution["value"]])
        if command[:1] == ("timeframe",):
            token = command[1]
            active_resolution["value"] = {"D": "D", "60": "60", "5": "5"}.get(token, token)
            return {"success": True}
        if command == ("quote",):
            return {"success": True, "last": 6629.5, "time": 1782165600}
        if command[:1] == ("range",):
            return {"success": True, "requested": {"from": command[2], "to": command[4]}}
        if command[:2] == ("ui", "eval"):
            return {"success": True, "result": {"reset": True}}
        if command[:2] == ("ui", "window"):
            if len(command) == 2:
                return {"success": True, "window_id": 1, "bounds": dict(window_bounds)}
            before = dict(window_bounds)
            option_values = {command[index]: command[index + 1] for index in range(2, len(command), 2)}
            for flag, key in (("--left", "left"), ("--top", "top"), ("--width", "width"), ("--height", "height")):
                if flag in option_values:
                    window_bounds[key] = int(option_values[flag])
            if "--state" in option_values:
                window_bounds["windowState"] = str(option_values["--state"])
            return {
                "success": True,
                "window_id": 1,
                "before": before,
                "after": dict(window_bounds),
                "requested": option_values,
            }
        if command == ("pane", "list"):
            return {
                "success": True,
                "layout": pane_state["layout"],
                "layout_name": "2x2 grid" if pane_state["layout"] == "4" else "1 chart",
                "chart_count": 4 if pane_state["layout"] == "4" else 1,
                "active_index": pane_state["active_index"],
                "panes": [],
            }
        if command[:2] == ("pane", "layout"):
            pane_state["layout"] = command[2]
            pane_state["active_index"] = 0
            return {"success": True, "layout": command[2]}
        if command[:2] == ("pane", "focus"):
            pane_state["active_index"] = int(command[2])
            return {"success": True, "focused_index": int(command[2])}
        if command[:3] == ("data", "labels", "-f"):
            return {
                "success": True,
                "studies": [
                    {
                        "name": "Multi Timeframe Fractal Map [Herman]",
                        "labels": [
                            {"text": "2", "price": 6629.0},
                            {"text": "M5 CISD+✓", "price": 6629.75},
                        ],
                    }
                ],
            }
        if command[:3] == ("data", "lines", "-f"):
            return {
                "success": True,
                "studies": [
                    {
                        "name": "Multi Timeframe Fractal Map [Herman]",
                        "horizontal_levels": [6628.5, 6637.5],
                    }
                ],
            }
        if command[:3] == ("data", "tables", "-f"):
            return {"success": True, "studies": []}
        if command[:1] == ("symbol",):
            return {"success": True}
        if command[:1] == ("screenshot",):
            output_name = command[-1]
            if output_name.endswith("_htf"):
                return {"success": True, "file_path": str(source_files["bundle_htf"])}
            if output_name.endswith("_itf"):
                return {"success": True, "file_path": str(source_files["bundle_itf"])}
            if output_name.endswith("_ltf"):
                return {"success": True, "file_path": str(source_files["bundle_ltf"])}
            raise AssertionError(f"Unexpected screenshot output name: {output_name}")
        raise AssertionError(f"Unexpected CLI command: {args}")

    return fake_cli_runner


def _retry_fake_runner(first_source_files: dict[str, Path], second_source_files: dict[str, Path]):
    screenshot_calls = {"count": 0}
    runner = _fake_runner(first_source_files)
    second_runner = _fake_runner(second_source_files)

    def fake_cli_runner(args: list[str]) -> dict:
        if tuple(args[:1]) == ("screenshot",):
            screenshot_calls["count"] += 1
            if screenshot_calls["count"] <= 3:
                return runner(args)
            return second_runner(args)
        return second_runner(args)

    return fake_cli_runner


def test_capture_live_tradingview_bundle_persists_quality_passed_bundle_seed(monkeypatch, tmp_path: Path) -> None:
    screenshot_source_dir = tmp_path / "tradingview-mcp" / "screenshots"
    screenshot_source_dir.mkdir(parents=True, exist_ok=True)
    source_files = {
        "bundle_htf": screenshot_source_dir / "bundle_htf.png",
        "bundle_itf": screenshot_source_dir / "bundle_itf.png",
        "bundle_ltf": screenshot_source_dir / "bundle_ltf.png",
    }
    _write_chart(source_files["bundle_htf"], "up")
    _write_chart(source_files["bundle_itf"], "down")
    _write_chart(source_files["bundle_ltf"], "box")

    monkeypatch.setattr("labeler.tradingview_weak_labeler.time.sleep", lambda _seconds: None)
    config = build_config(root_dir=tmp_path)

    report = capture_live_tradingview_bundle(config, cli_runner=_fake_runner(source_files))

    bundle_seed_text = config.paths.live_tradingview_bundle_seed_path.read_text(encoding="utf-8")
    assert "CME_MINI:ESM2026" in bundle_seed_text
    assert "\"htf_timeframe\": \"D\"" in bundle_seed_text
    assert "\"ltf_timeframe\": \"5\"" in bundle_seed_text
    assert "\"fractal_stage\": \"c2\"" in bundle_seed_text
    assert "\"direction\": \"bullish\"" in bundle_seed_text
    assert Path(report["raw_capture_path"]).exists()
    raw_capture = json.loads(Path(report["raw_capture_path"]).read_text(encoding="utf-8"))
    assert raw_capture["original_pane_state"]["layout"] == "4"
    assert raw_capture["original_pane_state"]["active_index"] == 2
    assert raw_capture["original_window_bounds"]["bounds"]["width"] == 1440
    assert raw_capture["original_window_bounds"]["bounds"]["height"] == 900
    assert Path(report["capture_dir"]).exists()
    assert report["capture_quality_passed"] is True
    assert report["bundle_seed_appended"] is True
    assert report["capture_quality_attempt_count"] == 1
    assert report["capture_quality"]["recommended_action"] == "review_state_labels"
    assert Path(report["decision_packet_path"]).exists()
    assert report["decision_ready"] is False
    assert "decision_chart_resolution_too_small" in report["decision_support_flags"]


def test_capture_live_tradingview_bundle_writes_decision_ready_packet_for_large_stack(monkeypatch, tmp_path: Path) -> None:
    screenshot_source_dir = tmp_path / "tradingview-mcp" / "screenshots"
    screenshot_source_dir.mkdir(parents=True, exist_ok=True)
    source_files = {
        "bundle_htf": screenshot_source_dir / "bundle_htf.png",
        "bundle_itf": screenshot_source_dir / "bundle_itf.png",
        "bundle_ltf": screenshot_source_dir / "bundle_ltf.png",
    }
    _write_chart(source_files["bundle_htf"], "up", size=(1400, 800))
    _write_chart(source_files["bundle_itf"], "down", size=(1400, 800))
    _write_chart(source_files["bundle_ltf"], "box", size=(1400, 800))

    monkeypatch.setattr("labeler.tradingview_weak_labeler.time.sleep", lambda _seconds: None)
    config = build_config(root_dir=tmp_path)

    report = capture_live_tradingview_bundle(config, cli_runner=_fake_runner(source_files))
    packet = json.loads(config.paths.live_tradingview_decision_packet_path.read_text(encoding="utf-8"))

    assert report["capture_quality_passed"] is True
    assert report["decision_ready"] is True
    assert packet["decision_ready"] is True
    assert packet["packet_version"] == "tv_decision_bundle_v1"
    assert packet["symbol"] == "CME_MINI:ESM2026"
    assert packet["timeframe_order"] == ["daily", "h1", "m5"]
    assert set(packet["chart_paths"]) == {"daily", "h1", "m5"}
    assert packet["capture_contract"]["minimum_chart_image"] == {"width": 1200, "height": 650}
    assert packet["decision_gate"]["allowed_verdicts"] == [
        "take",
        "watch",
        "no_trade",
        "insufficient_evidence",
    ]
    assert packet["ttrades_checklist"][0]["field"] == "daily_bias"
    assert set(packet["visual_markup_request"]["labels_to_mark"]) >= {
        "daily_bias",
        "cisd_confirmation",
        "displacement",
        "current_price",
        "missing_context",
    }
    assert [query["name"] for query in packet["retrieval_context"]["queries"]] == [
        "timeframe_alignment",
        "liquidity_and_poi",
        "entry_and_invalidation",
        "current_capture_cues",
    ]


def test_capture_live_tradingview_bundle_sets_visible_range_before_screenshots(monkeypatch, tmp_path: Path) -> None:
    screenshot_source_dir = tmp_path / "tradingview-mcp" / "screenshots"
    screenshot_source_dir.mkdir(parents=True, exist_ok=True)
    source_files = {
        "bundle_htf": screenshot_source_dir / "bundle_htf.png",
        "bundle_itf": screenshot_source_dir / "bundle_itf.png",
        "bundle_ltf": screenshot_source_dir / "bundle_ltf.png",
    }
    _write_chart(source_files["bundle_htf"], "up")
    _write_chart(source_files["bundle_itf"], "down")
    _write_chart(source_files["bundle_ltf"], "box")
    commands: list[list[str]] = []
    base_runner = _fake_runner(source_files)

    def recording_runner(args: list[str]) -> dict:
        commands.append(args)
        return base_runner(args)

    monkeypatch.setattr("labeler.tradingview_weak_labeler.time.sleep", lambda _seconds: None)
    config = build_config(root_dir=tmp_path)

    report = capture_live_tradingview_bundle(config, cli_runner=recording_runner)

    assert report["capture_quality_passed"] is True
    window_commands = [command for command in commands if command[:2] == ["ui", "window"]]
    layout_commands = [command for command in commands if command[:2] == ["pane", "layout"]]
    focus_commands = [command for command in commands if command[:2] == ["pane", "focus"]]
    range_commands = [command for command in commands if command[:1] == ["range"]]
    reset_commands = [command for command in commands if command[:2] == ["ui", "eval"]]
    assert window_commands[0] == ["ui", "window"]
    assert window_commands[1] == [
        "ui",
        "window",
        "--width",
        "1920",
        "--height",
        "1080",
        "--left",
        "0",
        "--top",
        "0",
        "--state",
        "normal",
    ]
    assert layout_commands[0] == ["pane", "layout", "s"]
    assert focus_commands[0] == ["pane", "focus", "0"]
    assert len(range_commands) == 3
    assert len(reset_commands) == 3
    assert range_commands[0][1] == "--from"
    assert range_commands[0][3] == "--to"
    screenshot_commands = [command for command in commands if command[:1] == ["screenshot"]]
    assert commands.index(window_commands[1]) < commands.index(screenshot_commands[0])
    assert commands.index(layout_commands[0]) < commands.index(screenshot_commands[0])
    assert commands.index(focus_commands[0]) < commands.index(screenshot_commands[0])
    assert commands.index(range_commands[0]) < commands.index(screenshot_commands[0])
    assert commands.index(reset_commands[0]) < commands.index(screenshot_commands[0])


def test_capture_live_tradingview_bundle_blocks_bad_capture_seed_append(monkeypatch, tmp_path: Path) -> None:
    screenshot_source_dir = tmp_path / "tradingview-mcp" / "screenshots"
    screenshot_source_dir.mkdir(parents=True, exist_ok=True)
    duplicate = screenshot_source_dir / "duplicate.png"
    _write_chart(duplicate, "up")
    source_files = {
        "bundle_htf": duplicate,
        "bundle_itf": duplicate,
        "bundle_ltf": duplicate,
    }
    monkeypatch.setattr("labeler.tradingview_weak_labeler.time.sleep", lambda _seconds: None)
    config = build_config(root_dir=tmp_path)

    report = capture_live_tradingview_bundle(config, cli_runner=_fake_runner(source_files))

    assert report["capture_quality_passed"] is False
    assert report["bundle_seed_appended"] is False
    assert report["capture_quality_attempt_count"] == 2
    assert "exact_duplicate_timeframe_images" in report["capture_quality"]["quality_flags"]
    assert report["decision_ready"] is False
    assert not config.paths.live_tradingview_bundle_seed_path.exists()
    assert json.loads(config.paths.live_tradingview_decision_packet_path.read_text(encoding="utf-8"))["decision_ready"] is False
    assert Path(report["raw_capture_path"]).exists()


def test_capture_live_tradingview_bundle_retries_until_quality_passes(monkeypatch, tmp_path: Path) -> None:
    screenshot_source_dir = tmp_path / "tradingview-mcp" / "screenshots"
    screenshot_source_dir.mkdir(parents=True, exist_ok=True)
    duplicate = screenshot_source_dir / "duplicate.png"
    _write_chart(duplicate, "up")
    first_source_files = {
        "bundle_htf": duplicate,
        "bundle_itf": duplicate,
        "bundle_ltf": duplicate,
    }
    second_source_files = {
        "bundle_htf": screenshot_source_dir / "bundle_htf_retry.png",
        "bundle_itf": screenshot_source_dir / "bundle_itf_retry.png",
        "bundle_ltf": screenshot_source_dir / "bundle_ltf_retry.png",
    }
    _write_chart(second_source_files["bundle_htf"], "up")
    _write_chart(second_source_files["bundle_itf"], "down")
    _write_chart(second_source_files["bundle_ltf"], "box")
    monkeypatch.setattr("labeler.tradingview_weak_labeler.time.sleep", lambda _seconds: None)
    config = build_config(root_dir=tmp_path)

    report = capture_live_tradingview_bundle(
        config,
        cli_runner=_retry_fake_runner(first_source_files, second_source_files),
    )

    assert report["capture_quality_passed"] is True
    assert report["bundle_seed_appended"] is True
    assert report["capture_quality_attempt_count"] == 2
    assert report["capture_quality_attempts"][0]["capture_quality_passed"] is False
    assert report["capture_quality_attempts"][1]["capture_quality_passed"] is True
    assert config.paths.live_tradingview_bundle_seed_path.exists()
    assert "attempt_2" in config.paths.live_tradingview_bundle_seed_path.read_text(encoding="utf-8")
