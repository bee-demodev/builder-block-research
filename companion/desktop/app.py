"""The Trading Companion as a desktop app: the core and its UI in one native window.

    python -m companion.desktop [--data live|history] [--history FOLDER] [--ui FOLDER]

What happens:

1. Only one copy runs: a second start finds the running window and brings it to the
   front, then exits (two companions would fight over the same TradingView page).
2. The UI folder and the Edge WebView2 Runtime are checked; what is missing is said in a
   message box, with what to do.
3. The core (``companion.core``) starts in this process on a free loopback port and the
   window opens on that server's own URL (the server only accepts its own origin).
   In live mode a background step makes sure TradingView Desktop runs with the live-data
   link (debug port 9222, which the TradingView MCP uses too): it starts TradingView when
   it is not running, and asks before restarting one that was opened without the link
   (``companion.tradingview.launch``; off with ``"start_tradingview": false`` in desktop.json).
4. Closing the window stops the core as Ctrl+C does for ``python -m companion.core``: the
   selections are saved and the feed is taken out of TradingView's page. The window's
   size and place are remembered.

Everything goes to ``desktop.log`` in the state folder, tracebacks included.
"""

from __future__ import annotations

import argparse
import logging
import logging.handlers
import os
import sys
import threading
import time
from collections.abc import Sequence
from functools import partial
from pathlib import Path
from typing import Any

from companion import paths
from companion.app_model import DATA_LABELS, DATA_LIVE, CompanionController, SessionBarSource, data_coverage, state_dir
from companion.desktop import settings, winapi

TITLE = "Trading Companion"
HOST = "127.0.0.1"
MUTEX_NAME = "Local\\TradingCompanion.Desktop"  # per Windows session; released by Windows when the process ends
WINDOW_CLASS = "WindowsForms10."  # the window library's form class; the older Tk window is "TkTopLevel"
FIND_EXISTING_FOR = 8.0  # seconds a second start waits for the first one's window to appear
BACKGROUND = "#111111"  # behind the page while it loads, so it does not flash white

WEBVIEW2_URL = "https://developer.microsoft.com/microsoft-edge/webview2/"

log = logging.getLogger("companion.desktop")


class Problem(Exception):
    """Something that stops the app, worded for the trader (shown in a message box)."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m companion.desktop", description="The Trading Companion in its own window.")
    parser.add_argument("--data", choices=sorted(DATA_LABELS), help="start in live (TradingView) or history (saved minute bars); remembered")
    parser.add_argument("--history", type=Path, help="folder of the saved <symbol>_minute.csv files (default: history_dir in desktop.json, else the built-in place)")
    parser.add_argument("--ui", type=Path, default=None, help="the built web UI (default companion/web/dist)")
    parser.add_argument("--debug", action="store_true", help="allow the browser's developer tools in the window")
    return parser


# --- logging -----------------------------------------------------------------------


class _LogStream:
    """``sys.stdout`` / ``sys.stderr`` for a process without a console: lines go to the log."""

    def __init__(self, level: int) -> None:
        self.level = level
        self._pending = ""

    def write(self, text: str) -> int:
        self._pending += text
        while "\n" in self._pending:
            line, self._pending = self._pending.split("\n", 1)
            if line.strip():
                logging.getLogger("companion.desktop.output").log(self.level, line.rstrip())
        return len(text)

    def flush(self) -> None:
        pass

    def isatty(self) -> bool:
        return False


def setup_logging(state: Path) -> Path:
    """Log to ``desktop.log`` in the state folder (the temp folder when that cannot be written)."""
    for folder in (Path(state), Path(os.environ.get("TEMP", ".")) / "trading_companion"):
        try:
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / settings.LOG_FILE
            handler = logging.handlers.RotatingFileHandler(path, maxBytes=1_000_000, backupCount=2, encoding="utf-8")
            break
        except OSError:
            continue
    else:  # pragma: no cover - neither folder can be written
        handler, path = logging.StreamHandler(), Path(settings.LOG_FILE)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s [%(threadName)s] %(message)s"))
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    if sys.stdout is None:
        sys.stdout = _LogStream(logging.INFO)  # type: ignore[assignment]
    if sys.stderr is None:
        sys.stderr = _LogStream(logging.WARNING)  # type: ignore[assignment]
    return path


# --- checks ------------------------------------------------------------------------


def check_ui(ui: Path) -> None:
    if (Path(ui) / "index.html").is_file():
        return
    if paths.is_frozen():
        raise Problem(f"The app's screen files are missing:\n{ui}\n\nReinstall Trading Companion (copy the whole \"Trading Companion\" folder again).")
    raise Problem(
        f"The web UI has not been built: {Path(ui) / 'index.html'} does not exist.\n\n"
        "Build it once (in companion/web: npm install, then npm run build), then start Trading Companion again."
    )


def check_webview2() -> str:
    version = winapi.webview2_version()
    if version is None:
        raise Problem(
            "Trading Companion needs the Microsoft Edge WebView2 Runtime, and it is not installed.\n\n"
            f"Install the Evergreen runtime from {WEBVIEW2_URL} , then start Trading Companion again."
        )
    return version


# --- one instance ------------------------------------------------------------------


def bring_existing(wait: float = FIND_EXISTING_FOR) -> bool:
    """Bring the running copy's window to the front; False when it has no window (yet)."""
    deadline = time.monotonic() + wait
    while True:
        windows = winapi.find_windows(TITLE, WINDOW_CLASS, exclude_pid=os.getpid())
        if windows:
            winapi.bring_to_front(windows[0].hwnd)
            log.info("Another copy is running (pid %s): brought its window to the front.", windows[0].pid)
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.2)


# --- the core ----------------------------------------------------------------------


def make_core(history: settings.History, data: str | None) -> Any:
    from companion.core.loop import Core

    controller = CompanionController(
        source=SessionBarSource(history.folder),
        coverage=partial(data_coverage, data_dir=history.folder),
        default_data=DATA_LIVE,
    )
    if data:
        controller.set_data(data)
        controller.save()
    return Core(controller)


async def _note_client(request: Any, response: Any) -> None:
    from aiohttp import web

    if isinstance(response, web.WebSocketResponse):
        log.info("UI connected over the WebSocket (Origin %s).", request.headers.get("Origin"))


def start_core(state: Path, args: argparse.Namespace, ui: Path) -> tuple[Any, Any]:
    """The core and its server on a free loopback port; returns the running ``ServerThread`` and the core."""
    try:
        from companion.core.background import ServerThread, bind_preferred
        from companion.core.server import make_app
    except ImportError as error:
        raise Problem(f"Part of Trading Companion is missing ({error}).\n\nFrom source: pip install -r companion/requirements.txt") from error

    history = settings.find_history(settings.history_folder(state, args.history))
    log.info(history.describe(state))
    try:
        core = make_core(history, args.data)

        def make(port: int) -> Any:
            app = make_app(core, host=HOST, port=port, dist=ui)
            app.on_response_prepare.append(_note_client)
            return app

        server = ServerThread(make, host=HOST, sock=bind_preferred(HOST, settings.last_port(state)))
        url = server.start()
    except Exception as error:
        raise Problem(f"The companion core could not start:\n{type(error).__name__}: {error}") from error
    settings.save_settings(state, last_port=server.port)
    log.info("Core listening on %s (data: %s).", url, core.controller.state.data)
    return server, core


# --- TradingView's live-data link ---------------------------------------------------


def link_tradingview(state: Path, core: Any) -> threading.Thread | None:
    """In live mode, make sure TradingView runs with the debug port, on a background thread
    (the window opens meanwhile). Starts a check once TradingView was (re)started."""
    from companion.core import wire
    from companion.tradingview import launch

    if not settings.start_tradingview(state):
        log.info("Starting TradingView is off (\"start_tradingview\": false in %s).", Path(state) / settings.SETTINGS_FILE)
        return None
    if core.controller.state.data != DATA_LIVE or not launch.available():
        return None

    def work() -> None:
        try:
            outcome = launch.ensure_link(winapi.ask_yes_no)
        except Exception:  # noqa: BLE001 - the window keeps working without it
            log.exception("Starting TradingView with the live-data link failed.")
            return
        log.info("TradingView live-data link: %s%s", outcome.result, f" ({outcome.detail})" if outcome.detail else "")
        if outcome.result in (launch.STARTED, launch.RESTARTED):
            core.submit(wire.Command("check"))
        elif outcome.result in (launch.NOT_FOUND, launch.FAILED):
            winapi.message_box(
                f"Trading Companion could not start TradingView with the live-data link.\n\n{outcome.detail}\n\n"
                f"Start it with {launch.LAUNCHER} instead.",
                error=False,
            )

    thread = threading.Thread(target=work, name="tradingview-link", daemon=True)
    thread.start()
    return thread


# --- the window --------------------------------------------------------------------


def show_window(url: str, state: Path, debug: bool = False) -> None:
    """Open the window on ``url`` and return when it has been closed."""
    try:
        import webview
    except ImportError as error:
        raise Problem(f"The window library is missing ({error}).\n\nFrom source: pip install -r companion/requirements.txt") from error

    winapi.make_dpi_aware()
    areas = winapi.work_areas()
    geometry = settings.initial_geometry(settings.load_geometry(state), areas)
    primary = areas[0] if areas else (0, 0, *settings.MIN_SIZE)
    min_size = (min(settings.MIN_SIZE[0], primary[2] - primary[0]), min(settings.MIN_SIZE[1], primary[3] - primary[1]))
    log.info("Opening the window at %s (work areas %s, scale %.2f).", geometry, areas, winapi.scale())
    window = webview.create_window(
        TITLE,
        url,
        width=geometry.width,
        height=geometry.height,
        x=geometry.x,
        y=geometry.y,
        maximized=geometry.maximized,
        min_size=min_size,
        background_color=BACKGROUND,
    )
    own: dict[str, int] = {}
    failures: list[str] = []

    def own_hwnd() -> int | None:
        if "hwnd" not in own:
            windows = winapi.find_windows(TITLE, WINDOW_CLASS, pid=os.getpid())
            if windows:
                own["hwnd"] = windows[0].hwnd
        return own.get("hwnd")

    def on_shown() -> None:
        hwnd = own_hwnd()
        if hwnd:
            winapi.bring_to_front(hwnd)
        log.info("Window shown (hwnd %s).", hwnd)

    def on_closing() -> None:
        hwnd = own_hwnd()
        placed = winapi.placement(hwnd) if hwnd else None
        if placed is not None:
            (left, top, right, bottom), maximized = placed
            saved = settings.Geometry(left, top, right - left, bottom - top, maximized)
            settings.save_geometry(state, saved)
            log.info("Window closing; remembered %s.", saved)
        else:
            log.info("Window closing.")

    def started() -> None:
        renderer = getattr(sys.modules.get("webview.platforms.winforms"), "renderer", None)
        log.info("Window library started (renderer %s).", renderer)
        if renderer is not None and renderer != "edgechromium":
            failures.append(
                "Trading Companion could not use the Microsoft Edge WebView2 Runtime "
                f"(the window library chose {renderer}).\n\nInstall or repair the runtime from {WEBVIEW2_URL} , then start again."
            )
            window.destroy()

    window.events.shown += on_shown
    window.events.closing += on_closing
    icon = paths.resource("desktop", "icon.ico")
    storage = Path(state) / "webview"
    webview.start(
        started,
        gui="edgechromium",
        debug=debug,
        private_mode=False,  # keep the UI's own small settings (its theme) between runs
        storage_path=str(storage),
        icon=str(icon) if icon.is_file() else None,
    )
    log.info("Window closed.")
    if failures:
        raise Problem(failures[0])


# --- main --------------------------------------------------------------------------


def run(args: argparse.Namespace, state: Path) -> int:
    instance = winapi.SingleInstance(MUTEX_NAME)
    if not instance.first:
        if not bring_existing():
            winapi.message_box("Trading Companion is already running (it may still be starting).", error=False)
            log.info("Another copy is running; its window was not found.")
        instance.release()
        return 0
    try:
        ui = Path(args.ui) if args.ui is not None else paths.default_ui_dir()
        check_ui(ui)
        log.info("WebView2 runtime %s; UI %s.", check_webview2(), ui)
        server, core = start_core(state, args, ui)
        link_tradingview(state, core)
        try:
            show_window(server.url, state, debug=args.debug)
        finally:
            stopped = server.stop()
            log.info("Core stopped; port %s released." if stopped else "Core did not stop in time (port %s).", server.port)
    finally:
        instance.release()
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    state = state_dir()
    log_path = setup_logging(state)
    log.info("Trading Companion desktop starting (pid %s, %s, state %s).", os.getpid(), "packaged" if paths.is_frozen() else "from source", state)
    try:
        return run(args, state)
    except Problem as problem:
        log.error("%s", problem, exc_info=problem.__cause__ is not None)
        winapi.message_box(f"{problem}\n\nDetails are in {log_path}")
        return 1
    except Exception as error:  # noqa: BLE001 - never a silent exit
        log.exception("Trading Companion stopped on an unexpected error.")
        winapi.message_box(f"Trading Companion stopped on an unexpected error:\n{type(error).__name__}: {error}\n\nDetails are in {log_path}")
        return 1
