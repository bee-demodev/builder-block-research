"""What the desktop app keeps in the state folder, and the decisions that need no screen.

Files in the state folder (``~/.trading_companion``, or ``TRADING_COMPANION_HOME``):

- ``window.json``: the window's last size and position (``x``, ``y``, ``width``, ``height``,
  ``maximized``), in the window library's logical pixels;
- ``desktop.json``: settings the trader may edit by hand:
  ``history_dir``: the folder of the saved ``<symbol>_minute.csv`` files (default: the
  repo's ``data/databento/bars`` from source, ``<folder of the exe>/history`` packaged);
  ``start_tradingview`` (default true): in live mode, start TradingView Desktop with the
  live-data link when the app starts, and offer to restart one opened without it;
  ``last_port`` is written by the app (the UI keeps the same origin between runs when
  that port is still free);
- ``desktop.log``: what the app did, and the traceback of anything that went wrong.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence

from companion import paths
from companion.bars import SUPPORTED_SYMBOLS

WINDOW_FILE = "window.json"
SETTINGS_FILE = "desktop.json"
LOG_FILE = "desktop.log"

DEFAULT_SIZE = (1440, 960)
MIN_SIZE = (900, 600)

Rect = tuple[int, int, int, int]  # left, top, right, bottom


# --- window geometry ---------------------------------------------------------------


@dataclass(frozen=True)
class Geometry:
    x: int | None  # None: let the window library centre it
    y: int | None
    width: int
    height: int
    maximized: bool = False


def load_geometry(state: Path) -> Geometry | None:
    """The saved geometry, or ``None`` when there is none or it cannot be read."""
    try:
        data = json.loads((Path(state) / WINDOW_FILE).read_text(encoding="utf-8"))
        x, y = data.get("x"), data.get("y")
        return Geometry(
            None if x is None else int(x),
            None if y is None else int(y),
            int(data["width"]),
            int(data["height"]),
            bool(data.get("maximized", False)),
        )
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None


def save_geometry(state: Path, geometry: Geometry) -> bool:
    try:
        Path(state).mkdir(parents=True, exist_ok=True)
        (Path(state) / WINDOW_FILE).write_text(json.dumps(asdict(geometry), indent=2), encoding="utf-8")
    except OSError:
        return False
    return True


def _overlap(a: Rect, b: Rect) -> int:
    width = min(a[2], b[2]) - max(a[0], b[0])
    height = min(a[3], b[3]) - max(a[1], b[1])
    return max(0, width) * max(0, height)


def initial_geometry(saved: Geometry | None, work_areas: Sequence[Rect]) -> Geometry:
    """Where the window opens. ``work_areas``: each monitor's usable area, the primary first.

    First run: ``DEFAULT_SIZE``, shrunk to fit the primary monitor and centred on it.
    Later runs: the saved size and place, moved onto the monitor it overlaps most (the
    primary when it overlaps none, e.g. a monitor that has been unplugged) and shrunk and
    shifted until it lies wholly inside that monitor's usable area."""
    if not work_areas:
        return saved if saved is not None else Geometry(None, None, *DEFAULT_SIZE)
    primary = work_areas[0]
    if saved is None or saved.x is None or saved.y is None:
        area = primary
        width, height = DEFAULT_SIZE
        maximized = bool(saved and saved.maximized)
        x = y = None
    else:
        window: Rect = (saved.x, saved.y, saved.x + saved.width, saved.y + saved.height)
        area = max(work_areas, key=lambda candidate: _overlap(window, candidate))
        if _overlap(window, area) == 0:
            area = primary
        width, height, x, y, maximized = saved.width, saved.height, saved.x, saved.y, saved.maximized
    area_width, area_height = area[2] - area[0], area[3] - area[1]
    width = max(min(width, area_width), min(MIN_SIZE[0], area_width))
    height = max(min(height, area_height), min(MIN_SIZE[1], area_height))
    if x is None or y is None:
        x, y = area[0] + (area_width - width) // 2, area[1] + (area_height - height) // 2
    x = min(max(x, area[0]), area[2] - width)
    y = min(max(y, area[1]), area[3] - height)
    return Geometry(int(x), int(y), int(width), int(height), maximized)


# --- desktop.json ------------------------------------------------------------------


def load_settings(state: Path) -> dict[str, Any]:
    try:
        data = json.loads((Path(state) / SETTINGS_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_settings(state: Path, **changes: Any) -> bool:
    """Merge ``changes`` into ``desktop.json`` (keeping what the trader wrote there)."""
    data = load_settings(state)
    data.update(changes)
    try:
        Path(state).mkdir(parents=True, exist_ok=True)
        (Path(state) / SETTINGS_FILE).write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        return False
    return True


def start_tradingview(state: Path) -> bool:
    return load_settings(state).get("start_tradingview", True) is not False


def last_port(state: Path) -> int | None:
    value = load_settings(state).get("last_port")
    return value if isinstance(value, int) and 1024 <= value <= 65535 else None


# --- the saved history -------------------------------------------------------------


@dataclass(frozen=True)
class History:
    folder: Path
    symbols: tuple[str, ...]  # the symbols with a minute file there

    @property
    def available(self) -> bool:
        return bool(self.symbols)

    def describe(self, state: Path) -> str:
        if self.available:
            return f"Saved history: {self.folder} ({', '.join(self.symbols)})."
        what = "has no <symbol>_minute.csv files" if self.folder.is_dir() else "does not exist"
        return (
            f"Saved history is unavailable: {self.folder} {what}. Live mode works without it. "
            f"To use saved history, put nq_minute.csv / es_minute.csv / gc_minute.csv in that folder, "
            f"or set \"history_dir\" in {Path(state) / SETTINGS_FILE}."
        )


def history_folder(state: Path, override: Path | None = None) -> Path:
    """The folder asked for on the command line, else ``history_dir`` in ``desktop.json``, else the default."""
    if override is not None:
        return Path(override)
    configured = load_settings(state).get("history_dir")
    if isinstance(configured, str) and configured.strip():
        return Path(configured.strip()).expanduser()
    return paths.default_history_dir()


def find_history(folder: Path) -> History:
    folder = Path(folder)
    found = tuple(symbol for symbol in SUPPORTED_SYMBOLS if (folder / f"{symbol.lower()}_minute.csv").is_file())
    return History(folder, found)
