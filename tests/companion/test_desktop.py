"""The desktop app's parts that need no screen: resources from source and packaged, the history
folder, window geometry, the one-instance guard and the messages shown when it cannot start."""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest

from companion import paths
from companion.core import wire
from companion.desktop import app as desktop
from companion.desktop import settings, winapi
from companion.desktop.settings import Geometry

windows_only = pytest.mark.skipif(sys.platform != "win32", reason="Windows named mutex")

PRIMARY = (0, 0, 1920, 1040)  # 1080p with the taskbar at the bottom
SECOND = (1920, 0, 4480, 1400)


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    state = tmp_path / "home"
    monkeypatch.setenv("TRADING_COMPANION_HOME", str(state))
    return state


@pytest.fixture
def frozen(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Pretend to be the packaged app in ``tmp_path/app``."""
    app = tmp_path / "app"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(app / "_internal"), raising=False)
    monkeypatch.setattr(sys, "executable", str(app / "Trading Companion.exe"))
    return app


# --- where files are -------------------------------------------------------------


def test_from_source_resources_are_the_repo_files_and_every_loader_uses_them() -> None:
    from companion import bars, evidence, timeframes
    from companion.core import server
    from companion.styles.ttrades import config as ttrades_config
    from companion.tradingview import symbols

    repo = Path(__file__).resolve().parents[2]
    assert not paths.is_frozen()
    assert paths.package_dir() == repo / "companion" and paths.app_dir() == repo
    for parts in paths.RUNTIME_DATA_FILES + paths.REFERENCE_FILES:
        assert paths.resource(*parts).is_file(), parts  # the build copies exactly these
    loaded = {timeframes.STACKS_PATH, symbols.SYMBOLS_PATH, ttrades_config.CONFIG_PATH, evidence.EVIDENCE_PATH}
    assert loaded == {paths.resource(*parts) for parts in paths.RUNTIME_DATA_FILES}
    assert bars.DATA_DIR == repo / "data" / "databento" / "bars"
    assert server.DIST == repo / "companion" / "web" / "dist"


def test_packaged_resources_are_unpacked_beside_the_exe_and_history_is_next_to_it(frozen: Path) -> None:
    assert paths.is_frozen()
    assert paths.package_dir() == frozen / "_internal" / "companion"
    assert paths.resource("config", "stacks.json") == frozen / "_internal" / "companion" / "config" / "stacks.json"
    assert paths.default_ui_dir() == frozen / "_internal" / "companion" / "web" / "dist"
    assert paths.app_dir() == frozen
    assert paths.default_history_dir() == frozen / "history"


# --- the saved history -------------------------------------------------------------


def test_the_history_folder_comes_from_the_command_line_then_desktop_json_then_the_default(home: Path, frozen: Path, tmp_path: Path) -> None:
    assert settings.history_folder(home) == frozen / "history"
    settings.save_settings(home, history_dir=str(tmp_path / "bars"), last_port=50123)
    assert settings.history_folder(home) == tmp_path / "bars"
    assert settings.history_folder(home, tmp_path / "given") == tmp_path / "given"
    assert settings.last_port(home) == 50123
    settings.save_settings(home, last_port="nonsense")
    assert settings.last_port(home) is None and settings.history_folder(home) == tmp_path / "bars"  # the trader's line is kept


def test_an_absent_history_folder_is_said_plainly_and_a_present_one_lists_its_symbols(home: Path, tmp_path: Path) -> None:
    missing = settings.find_history(tmp_path / "history")
    assert not missing.available
    assert "does not exist" in missing.describe(home) and "Live mode works without it" in missing.describe(home)
    folder = tmp_path / "history"
    folder.mkdir()
    assert "has no <symbol>_minute.csv files" in settings.find_history(folder).describe(home)
    (folder / "nq_minute.csv").write_text("timestamp,open,high,low,close,volume\n", encoding="utf-8")
    found = settings.find_history(folder)
    assert found.available and found.symbols == ("NQ",) and "(NQ)" in found.describe(home)


def test_without_history_the_core_still_starts_and_a_history_check_says_what_is_missing(home: Path, tmp_path: Path) -> None:
    core = desktop.make_core(settings.find_history(tmp_path / "history"), "history")
    snapshots: list[dict] = []
    core.add_listener(lambda message: snapshots.append(message) if message["type"] == "snapshot" else None)
    core.begin()
    core.submit(wire.parse_command('{"type": "check"}'))
    core.step()
    assert core.controller.coverage("NQ") is None
    assert "No historical data found for NQ" in snapshots[-1]["error"]
    assert str(tmp_path / "history") in snapshots[-1]["error"]
    core.stop()
    assert (home / "ui_state.json").is_file()


# --- the window's place ------------------------------------------------------------


def test_the_first_window_is_the_default_size_centred_and_shrunk_to_a_small_screen() -> None:
    assert settings.initial_geometry(None, [PRIMARY, SECOND]) == Geometry(240, 40, 1440, 960)
    small = (0, 0, 1366, 728)
    assert settings.initial_geometry(None, [small]) == Geometry(0, 0, 1366, 728)
    assert settings.initial_geometry(None, []) == Geometry(None, None, 1440, 960)


def test_a_saved_window_comes_back_where_it_was_on_its_own_monitor() -> None:
    saved = Geometry(2100, 120, 1600, 1000, maximized=True)
    assert settings.initial_geometry(saved, [PRIMARY, SECOND]) == saved
    assert settings.initial_geometry(Geometry(100, 50, 1200, 800), [PRIMARY, SECOND]) == Geometry(100, 50, 1200, 800)


def test_a_window_off_every_screen_or_too_big_is_brought_back_inside_one() -> None:
    unplugged = Geometry(5000, 200, 1600, 1000)  # was on a monitor that is gone
    assert settings.initial_geometry(unplugged, [PRIMARY]) == Geometry(320, 40, 1600, 1000)
    straddling = Geometry(1800, -300, 3000, 2000)  # mostly on the second monitor, taller than it
    assert settings.initial_geometry(straddling, [PRIMARY, SECOND]) == Geometry(1920, 0, 2560, 1400)
    tiny = Geometry(10, 10, 100, 80)
    assert settings.initial_geometry(tiny, [PRIMARY]) == Geometry(10, 10, *settings.MIN_SIZE)


def test_the_geometry_is_saved_and_a_damaged_file_means_the_default(tmp_path: Path) -> None:
    assert settings.load_geometry(tmp_path) is None
    assert settings.save_geometry(tmp_path, Geometry(10, 20, 1300, 900, True))
    assert settings.load_geometry(tmp_path) == Geometry(10, 20, 1300, 900, True)
    (tmp_path / settings.WINDOW_FILE).write_text("{not json", encoding="utf-8")
    assert settings.load_geometry(tmp_path) is None
    (tmp_path / settings.WINDOW_FILE).write_text('{"x": 1}', encoding="utf-8")
    assert settings.load_geometry(tmp_path) is None


# --- one instance ------------------------------------------------------------------


@windows_only
def test_a_second_holder_of_the_mutex_is_not_first_and_a_released_one_frees_it() -> None:
    name = f"Local\\TradingCompanion.Test.{uuid.uuid4().hex}"
    first = winapi.SingleInstance(name)
    second = winapi.SingleInstance(name)
    assert first.first and not second.first
    first.release()
    second.release()
    with winapi.SingleInstance(name) as third:
        assert third.first


@windows_only
def test_a_crashed_holder_leaves_nothing_stale() -> None:
    name = f"Local\\TradingCompanion.Test.{uuid.uuid4().hex}"
    holder = subprocess.Popen(
        [sys.executable, "-c", f"from companion.desktop.winapi import SingleInstance; import os, time; m = SingleInstance({name!r}); print(m.first, os.getpid(), flush=True); time.sleep(60)"],
        stdout=subprocess.PIPE,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )
    try:
        assert holder.stdout is not None
        first, pid = holder.stdout.readline().split()
        assert first == "True"
        with winapi.SingleInstance(name) as meanwhile:
            assert not meanwhile.first
        # TerminateProcess on the interpreter itself (a venv's python.exe may be a launcher with
        # the interpreter as its child): no clean-up runs, as in a crash
        os.kill(int(pid), signal.SIGTERM)
        holder.wait(10)
        deadline = time.monotonic() + 10
        while str(pid) in subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True).stdout:
            assert time.monotonic() < deadline, "the holder did not end"
            time.sleep(0.1)
        with winapi.SingleInstance(name) as after:
            assert after.first
    finally:
        holder.kill()


# --- what the trader sees when it cannot start -------------------------------------


@pytest.fixture
def boxes(home: Path, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    shown: list[str] = []
    monkeypatch.setattr(winapi, "message_box", lambda text, title="Trading Companion", error=True: shown.append(text))
    monkeypatch.setattr(desktop, "MUTEX_NAME", f"Local\\TradingCompanion.Test.{uuid.uuid4().hex}")
    monkeypatch.setattr(winapi, "webview2_version", lambda: "157.0.0.0")
    before = list(logging.getLogger().handlers)
    yield shown
    for handler in logging.getLogger().handlers[len(before):]:
        handler.close()
        logging.getLogger().removeHandler(handler)


def test_a_missing_ui_is_a_message_saying_how_to_build_it(boxes: list[str], home: Path, tmp_path: Path) -> None:
    assert desktop.main(["--ui", str(tmp_path / "nothing")]) == 1
    assert len(boxes) == 1 and "has not been built" in boxes[0] and "npm run build" in boxes[0]
    assert str(home / settings.LOG_FILE) in boxes[0]
    assert "has not been built" in (home / settings.LOG_FILE).read_text(encoding="utf-8")


def test_a_missing_webview2_runtime_is_a_message_saying_where_to_get_it(boxes: list[str], home: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / "ui").mkdir()
    (tmp_path / "ui" / "index.html").write_text("<!doctype html>", encoding="utf-8")
    monkeypatch.setattr(winapi, "webview2_version", lambda: None)
    assert desktop.main(["--ui", str(tmp_path / "ui")]) == 1
    assert "WebView2 Runtime" in boxes[0] and desktop.WEBVIEW2_URL in boxes[0]


def test_a_core_that_fails_to_start_is_a_message_and_a_traceback_in_the_log(boxes: list[str], home: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / "ui").mkdir()
    (tmp_path / "ui" / "index.html").write_text("<!doctype html>", encoding="utf-8")

    def broken(*_args: object) -> None:
        raise ValueError("symbols.json is damaged")

    monkeypatch.setattr(desktop, "make_core", broken)
    assert desktop.main(["--ui", str(tmp_path / "ui")]) == 1
    assert "The companion core could not start" in boxes[0] and "symbols.json is damaged" in boxes[0]
    logged = (home / settings.LOG_FILE).read_text(encoding="utf-8")
    assert "Traceback (most recent call last)" in logged and "ValueError: symbols.json is damaged" in logged
