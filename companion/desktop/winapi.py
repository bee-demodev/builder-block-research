"""The few Windows calls the desktop app needs, through ctypes (no pywin32).

- ``SingleInstance``: a named mutex. Windows releases it when the process ends, however it
  ends, so a crash can never leave a stale "already running".
- ``find_windows`` / ``bring_to_front``: the running copy's window, by title and class.
- ``work_areas`` / ``placement``: monitors and the window's restored rectangle, for
  remembering where the window was.
- ``message_box``: the plain dialog for anything that stops the app.
- ``webview2_version``: the installed Edge WebView2 Runtime, if any.
"""

from __future__ import annotations

import ctypes
import os
import sys
from ctypes import wintypes
from dataclasses import dataclass

IS_WINDOWS = sys.platform == "win32"
ERROR_ALREADY_EXISTS = 183

MB_OK = 0x0
MB_ICONERROR = 0x10
MB_ICONINFORMATION = 0x40
MB_SETFOREGROUND = 0x10000
MB_TOPMOST = 0x40000

SW_RESTORE = 9
SW_SHOWMINIMIZED = 2
SW_SHOWMAXIMIZED = 3
WPF_RESTORETOMAXIMIZED = 0x2
WM_CLOSE = 0x0010
MONITORINFOF_PRIMARY = 0x1

WEBVIEW2_CLIENTS = (
    "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",  # the Evergreen runtime
    "{2CD8A007-E189-409D-A2C8-9AF4EF3C72AA}",  # Edge beta
    "{0D50BFEC-CD6A-4F9A-964C-C7416E3ACB10}",  # Edge dev
    "{65C35B14-6C1D-4122-AC46-7148CC9D6497}",  # Edge canary
)

Rect = tuple[int, int, int, int]

if IS_WINDOWS:
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _user32 = ctypes.WinDLL("user32", use_last_error=True)

    _kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    _kernel32.CreateMutexW.restype = wintypes.HANDLE
    _kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    _kernel32.CloseHandle.restype = wintypes.BOOL

    _EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    _user32.EnumWindows.argtypes = [_EnumWindowsProc, wintypes.LPARAM]
    _user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    _user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    _user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    _user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    _user32.IsWindowVisible.argtypes = [wintypes.HWND]
    _user32.IsIconic.argtypes = [wintypes.HWND]
    _user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    _user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    _user32.BringWindowToTop.argtypes = [wintypes.HWND]
    _user32.MessageBoxW.argtypes = [wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.UINT]
    _user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]

    _MonitorEnumProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)
    _user32.EnumDisplayMonitors.argtypes = [wintypes.HDC, ctypes.c_void_p, _MonitorEnumProc, wintypes.LPARAM]


class _MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]


class _WINDOWPLACEMENT(ctypes.Structure):
    _fields_ = [
        ("length", wintypes.UINT),
        ("flags", wintypes.UINT),
        ("showCmd", wintypes.UINT),
        ("ptMinPosition", wintypes.POINT),
        ("ptMaxPosition", wintypes.POINT),
        ("rcNormalPosition", wintypes.RECT),
    ]


if IS_WINDOWS:
    _user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(_MONITORINFO)]
    _user32.GetWindowPlacement.argtypes = [wintypes.HWND, ctypes.POINTER(_WINDOWPLACEMENT)]


def _rect(r: wintypes.RECT) -> Rect:
    return (int(r.left), int(r.top), int(r.right), int(r.bottom))


# --- one instance ------------------------------------------------------------------


class SingleInstance:
    """Hold the named mutex ``name`` for as long as this object (or the process) lives.

    ``first`` is False when another holder exists. A holder that crashed or was killed
    holds nothing: Windows closes its handles, and the next start is first again."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._handle = None
        self.first = True
        if not IS_WINDOWS:
            return
        handle = _kernel32.CreateMutexW(None, False, name)
        error = ctypes.get_last_error()
        if not handle:
            raise ctypes.WinError(error)
        self._handle = handle
        self.first = error != ERROR_ALREADY_EXISTS

    def release(self) -> None:
        if self._handle:
            _kernel32.CloseHandle(self._handle)
            self._handle = None

    def __enter__(self) -> "SingleInstance":
        return self

    def __exit__(self, *_: object) -> None:
        self.release()


# --- windows -----------------------------------------------------------------------


@dataclass(frozen=True)
class Window:
    hwnd: int
    title: str
    class_name: str
    pid: int
    visible: bool


def list_windows() -> list[Window]:
    """Every top-level window."""
    if not IS_WINDOWS:
        return []
    found: list[Window] = []

    def visit(hwnd: int, _lparam: int) -> bool:
        length = _user32.GetWindowTextLengthW(hwnd)
        title = ctypes.create_unicode_buffer(length + 1)
        _user32.GetWindowTextW(hwnd, title, length + 1)
        klass = ctypes.create_unicode_buffer(256)
        _user32.GetClassNameW(hwnd, klass, 256)
        pid = wintypes.DWORD()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        found.append(Window(int(hwnd or 0), title.value, klass.value, int(pid.value), bool(_user32.IsWindowVisible(hwnd))))
        return True

    _user32.EnumWindows(_EnumWindowsProc(visit), 0)
    return found


def find_windows(title: str, class_prefix: str = "", pid: int | None = None, exclude_pid: int | None = None) -> list[Window]:
    """Visible top-level windows titled exactly ``title`` (and of a class starting with ``class_prefix``)."""
    return [
        window
        for window in list_windows()
        if window.visible
        and window.title == title
        and window.class_name.startswith(class_prefix)
        and (pid is None or window.pid == pid)
        and (exclude_pid is None or window.pid != exclude_pid)
    ]


def bring_to_front(hwnd: int) -> bool:
    if not IS_WINDOWS:
        return False
    if _user32.IsIconic(hwnd):
        _user32.ShowWindow(hwnd, SW_RESTORE)
    _user32.BringWindowToTop(hwnd)
    return bool(_user32.SetForegroundWindow(hwnd))


def post_close(hwnd: int) -> bool:
    """Ask a window to close, as its close button does."""
    return bool(IS_WINDOWS and _user32.PostMessageW(hwnd, WM_CLOSE, 0, 0))


# --- monitors and placement --------------------------------------------------------


def make_dpi_aware() -> None:
    """Report real pixels to this process (the window library does the same when it starts)."""
    if IS_WINDOWS:
        try:
            _user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


def scale() -> float:
    """Logical-to-physical pixels for this (system-DPI-aware) process: 1.0 at 96 dpi."""
    if not IS_WINDOWS:
        return 1.0
    try:
        return max(0.5, _user32.GetDpiForSystem() / 96)
    except (AttributeError, OSError):
        return 1.0


def monitors() -> list[tuple[Rect, Rect, bool]]:
    """(monitor, work area, primary) per monitor, in physical pixels, the primary first."""
    if not IS_WINDOWS:
        return []
    found: list[tuple[Rect, Rect, bool]] = []

    def visit(handle: int, _hdc: int, _rect_: object, _lparam: int) -> bool:
        info = _MONITORINFO()
        info.cbSize = ctypes.sizeof(_MONITORINFO)
        if _user32.GetMonitorInfoW(handle, ctypes.byref(info)):
            found.append((_rect(info.rcMonitor), _rect(info.rcWork), bool(info.dwFlags & MONITORINFOF_PRIMARY)))
        return True

    _user32.EnumDisplayMonitors(None, None, _MonitorEnumProc(visit), 0)
    return sorted(found, key=lambda item: not item[2])


def work_areas(factor: float | None = None) -> list[Rect]:
    """Each monitor's usable area (without the taskbar) in logical pixels, the primary first."""
    factor = scale() if factor is None else factor
    return [tuple(int(round(v / factor)) for v in work) for _monitor, work, _primary in monitors()]  # type: ignore[misc]


def placement(hwnd: int, factor: float | None = None) -> tuple[Rect, bool] | None:
    """The window's restored rectangle (screen coordinates, logical pixels) and whether it is maximized.

    ``GetWindowPlacement`` gives the restored rectangle even while the window is maximized
    or minimized, in workspace coordinates: those are offset from screen coordinates by
    the primary monitor's taskbar when it sits on the left or the top."""
    if not IS_WINDOWS:
        return None
    info = _WINDOWPLACEMENT()
    info.length = ctypes.sizeof(_WINDOWPLACEMENT)
    if not _user32.GetWindowPlacement(hwnd, ctypes.byref(info)):
        return None
    left, top, right, bottom = _rect(info.rcNormalPosition)
    primary = next((item for item in monitors() if item[2]), None)
    if primary is not None:
        dx, dy = primary[1][0] - primary[0][0], primary[1][1] - primary[0][1]
        left, top, right, bottom = left + dx, top + dy, right + dx, bottom + dy
    factor = scale() if factor is None else factor
    rect = tuple(int(round(v / factor)) for v in (left, top, right, bottom))
    maximized = info.showCmd == SW_SHOWMAXIMIZED or (info.showCmd == SW_SHOWMINIMIZED and bool(info.flags & WPF_RESTORETOMAXIMIZED))
    return rect, maximized  # type: ignore[return-value]


# --- dialogs and the runtime -------------------------------------------------------


def message_box(text: str, title: str = "Trading Companion", error: bool = True) -> None:
    """A plain blocking dialog. Off Windows (tests) it goes to stderr."""
    if not IS_WINDOWS:
        print(f"{title}: {text}", file=sys.stderr)
        return
    style = (MB_ICONERROR if error else MB_ICONINFORMATION) | MB_OK | MB_SETFOREGROUND | MB_TOPMOST
    _user32.MessageBoxW(None, text, title, style)


def webview2_version() -> str | None:
    """The installed Edge WebView2 Runtime's version, or ``None`` when there is none (or it is too old to use)."""
    if not IS_WINDOWS:
        return None
    import winreg

    places = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\EdgeUpdate\Clients"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\EdgeUpdate\Clients"),
    ]
    for client in WEBVIEW2_CLIENTS:
        for hive, base in places:
            try:
                with winreg.OpenKey(hive, rf"{base}\{client}") as key:
                    version, _kind = winreg.QueryValueEx(key, "pv")
            except OSError:
                continue
            version = str(version)
            try:
                if tuple(int(part) for part in version.split(".")[:3]) >= (86, 0, 622):
                    return version
            except ValueError:
                continue
    return None


def this_pid() -> int:
    return os.getpid()
