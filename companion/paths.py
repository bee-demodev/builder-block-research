"""Where the companion's own files are, run from source or from the packaged app.

From source the package is ``<repo>/companion`` and the saved minute history is the
repo's ``data/databento/bars``. In the packaged app (PyInstaller, one folder) the package
and its data files are unpacked under ``sys._MEIPASS`` (``<app>/_internal``) with the same
layout, ``companion/config/stacks.json`` and so on, and the history is looked for in a
``history`` folder next to ``Trading Companion.exe`` (the desktop app can point it
elsewhere; see ``companion.desktop.settings``).

Every module that opens one of these files asks here, so both cases live in one place.
"""

from __future__ import annotations

import sys
from pathlib import Path

HISTORY_FOLDER = "history"  # packaged app: <folder of the exe>/history/<symbol>_minute.csv

# Files the companion opens by path at run time, relative to the package. The build
# copies exactly these into the packaged app and fails when one is missing.
RUNTIME_DATA_FILES: tuple[tuple[str, ...], ...] = (
    ("config", "stacks.json"),  # companion.timeframes: the timeframe stacks
    ("config", "symbols.json"),  # companion.tradingview.symbols: live symbols and the debug port
    ("styles", "ttrades", "config.json"),  # companion.styles.ttrades.config: the style's numbers
    ("config", "evidence.json"),  # companion.evidence: the backtest record shown on a plan
)
# Shipped alongside for the trader to read; nothing opens it at run time.
REFERENCE_FILES: tuple[tuple[str, ...], ...] = (("styles", "ttrades", "rules.md"),)


def is_frozen() -> bool:
    """True inside the packaged app."""
    return bool(getattr(sys, "frozen", False))


def package_dir() -> Path:
    """The ``companion`` package folder: the repo's, or the one unpacked in the packaged app."""
    if is_frozen():
        bundle = getattr(sys, "_MEIPASS", None)
        return (Path(bundle) if bundle else Path(sys.executable).resolve().parent) / "companion"
    return Path(__file__).resolve().parent


def resource(*parts: str) -> Path:
    """A file shipped with the package, e.g. ``resource("config", "stacks.json")``."""
    return package_dir().joinpath(*parts)


def app_dir() -> Path:
    """The folder of ``Trading Companion.exe`` when packaged; the repo root from source."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def default_history_dir() -> Path:
    """Where the saved ``<symbol>_minute.csv`` files are unless something says otherwise."""
    if is_frozen():
        return app_dir() / HISTORY_FOLDER
    return app_dir() / "data" / "databento" / "bars"


def default_ui_dir() -> Path:
    """The built web UI served at ``/``."""
    return resource("web", "dist")
