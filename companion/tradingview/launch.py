"""Start TradingView Desktop with the live-data link (the debug port) for the companion.

The companion and the TradingView MCP both read TradingView through the same Chrome debug
port (9222). TradingView only opens it when started with ``--remote-debugging-port``, so a
TradingView opened from its normal icon cannot be read. ``ensure_link`` fixes that at
companion start:

- the port answers: nothing to do;
- TradingView is not running: start it with the link, no question asked;
- TradingView is open without the link: ask (``confirm``); on yes, close it the way its
  close button does, wait for it to exit, and start it again with the link. On no, leave it.

Every wait is bounded. Nothing here runs off Windows.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from companion.tradingview.cdp import port_answers, tradingview_is_running
from companion.tradingview.errors import LAUNCHER

log = logging.getLogger("companion.tradingview.launch")

PORT = 9222
IMAGE = "TradingView.exe"
NO_WINDOW = 0x08000000  # CREATE_NO_WINDOW: helper commands never flash a console
PORT_WAIT = 45.0  # seconds for a freshly started TradingView to open the port
EXIT_WAIT = 20.0  # seconds for TradingView to close after it was asked to

LINKED = "linked"  # the port already answered
STARTED = "started"  # TradingView was not running; started with the link
RESTARTED = "restarted"  # was open without the link; closed and started again
DECLINED = "declined"  # open without the link; the trader said no
NOT_FOUND = "not_found"  # no TradingView Desktop install found
FAILED = "failed"  # started, but the port never answered (or it would not close)


@dataclass(frozen=True)
class Outcome:
    result: str
    detail: str = ""


def find_exe() -> Path | None:
    """TradingView.exe: the usual installs, then the Microsoft Store one (same order as the .cmd launcher)."""
    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "TradingView" / IMAGE,
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "TradingView" / IMAGE,
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "TradingView" / IMAGE,
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return _store_exe()


def _store_exe() -> Path | None:
    script = (
        "$p = Get-AppxPackage -Name 'TradingView.Desktop*' -ErrorAction SilentlyContinue | "
        "Sort-Object Version -Descending | Select-Object -First 1; "
        "if ($p) { Join-Path $p.InstallLocation 'TradingView.exe' }"
    )
    try:
        done = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=20, creationflags=NO_WINDOW,
        )  # fmt: skip
    except (OSError, subprocess.SubprocessError) as error:
        log.info("Looking up the Store TradingView failed: %s", error)
        return None
    found = done.stdout.strip().splitlines()
    return Path(found[-1]) if found and Path(found[-1]).is_file() else None


def start(exe: Path, port: int = PORT) -> None:
    """Start TradingView detached through the shell (as a double-click does): it is not our child and outlives us."""
    os.startfile(str(exe), arguments=f"--remote-debugging-port={port}")  # type: ignore[attr-defined]


def close_politely() -> None:
    """Ask every TradingView window to close (no /F: TradingView saves and exits as from its close button)."""
    subprocess.run(["taskkill", "/IM", IMAGE], capture_output=True, timeout=15, creationflags=NO_WINDOW)


def force_close() -> None:
    subprocess.run(["taskkill", "/IM", IMAGE, "/T", "/F"], capture_output=True, timeout=15, creationflags=NO_WINDOW)


def _wait(condition: Callable[[], bool], seconds: float, sleep: Callable[[float], None], step: float = 1.0) -> bool:
    deadline = time.monotonic() + seconds
    while True:
        if condition():
            return True
        if time.monotonic() >= deadline:
            return False
        sleep(step)


ASK = (
    "TradingView is open, but it was started without the live-data link, so the companion "
    "(and the TradingView MCP) cannot read it.\n\n"
    "Restart TradingView now with the link? It closes and reopens by itself in about 20 seconds; "
    "your saved layouts come back.\n\n"
    "No leaves TradingView as it is."
)


def ensure_link(
    confirm: Callable[[str], bool],
    *,
    port: int = PORT,
    answers: Callable[[int], bool] = port_answers,
    running: Callable[[], bool] = tradingview_is_running,
    exe: Callable[[], Path | None] = find_exe,
    launch: Callable[[Path, int], None] = start,
    close: Callable[[], None] = close_politely,
    kill: Callable[[], None] = force_close,
    sleep: Callable[[float], None] = time.sleep,
    port_wait: float = PORT_WAIT,
    exit_wait: float = EXIT_WAIT,
) -> Outcome:
    """Make sure TradingView is running with the debug port open. See the module docstring."""
    if answers(port):
        return Outcome(LINKED)
    restart = running()
    if restart and not confirm(ASK):
        return Outcome(DECLINED)
    path = exe()
    if path is None:
        return Outcome(NOT_FOUND, "TradingView Desktop was not found (looked in %LOCALAPPDATA%, Program Files and the Store apps).")
    if restart:
        close()
        if not _wait(lambda: not running(), exit_wait, sleep):
            log.info("TradingView did not close within %.0f s; ending it.", exit_wait)
            kill()
            if not _wait(lambda: not running(), 10.0, sleep):
                return Outcome(FAILED, "TradingView would not close.")
    launch(path, port)
    if not _wait(lambda: answers(port), port_wait, sleep):
        return Outcome(FAILED, f"TradingView was started from {path}, but port {port} did not answer within {port_wait:.0f} s.")
    return Outcome(RESTARTED if restart else STARTED, str(path))


def available() -> bool:
    return sys.platform == "win32"
