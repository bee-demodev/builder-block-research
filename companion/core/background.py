"""The local server on a thread of its own, for a host that owns the main thread (a window).

``python -m companion.core`` runs the server with ``web.run_app`` on the main thread, and
Ctrl+C stops it. A desktop window needs the main thread for itself, so here the same
aiohttp application runs on its own event loop in a background thread:

    server = ServerThread(lambda port: make_app(core, port=port))
    url = server.start()   # returns once the server answers; raises if it could not start
    ...
    server.stop()          # what Ctrl+C does: clients are closed, the core stops (saves the
                           # selections, lets go of TradingView), the port is released

The port is bound before the application is built (``0`` asks the system for a free one),
so the app's own-origin check knows the real port and no other program can take the port
between choosing it and listening on it.
"""

from __future__ import annotations

import asyncio
import socket
import threading
from typing import Callable

from aiohttp import web

from companion.core.server import DEFAULT_HOST

SHUTDOWN_TIMEOUT = 5.0  # seconds open requests get to finish once the server stops


def bind_port(host: str = DEFAULT_HOST, port: int = 0) -> socket.socket:
    """A listening-ready TCP socket bound to ``host:port`` (``0``: a free port the system picks).

    Windows: ``SO_EXCLUSIVEADDRUSE`` so no other program can bind the same port while it is held."""
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    sock = socket.socket(family, socket.SOCK_STREAM)
    try:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        sock.bind((host.strip("[]"), port))
    except OSError:
        sock.close()
        raise
    return sock


def bind_preferred(host: str = DEFAULT_HOST, preferred: int | None = None) -> socket.socket:
    """``preferred`` when it is free (so the UI keeps the same origin between runs), otherwise any free port."""
    if preferred:
        try:
            return bind_port(host, preferred)
        except OSError:
            pass
    return bind_port(host, 0)


class ServerThread:
    """Serve ``make(port)`` on ``sock`` (default: a free loopback port) from a background thread."""

    def __init__(
        self,
        make: Callable[[int], web.Application],
        *,
        host: str = DEFAULT_HOST,
        sock: socket.socket | None = None,
        shutdown_timeout: float = SHUTDOWN_TIMEOUT,
    ) -> None:
        self.host = host
        self._make = make
        self._sock = sock
        self._shutdown_timeout = shutdown_timeout
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop_requested: asyncio.Event | None = None
        self._ready = threading.Event()
        self._error: BaseException | None = None
        self.port: int | None = None
        self.app: web.Application | None = None

    @property
    def url(self) -> str:
        host = f"[{self.host}]" if ":" in self.host else self.host
        return f"http://{host}:{self.port}/"

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, timeout: float = 15.0) -> str:
        """Build the app, start serving and return its URL once it listens. Raises what stopped it."""
        if self._thread is not None:
            raise RuntimeError("ServerThread.start was already called")
        sock = self._sock if self._sock is not None else bind_port(self.host, 0)
        self._sock = sock
        self.port = sock.getsockname()[1]
        try:
            self.app = self._make(self.port)
        except BaseException:
            sock.close()
            raise
        self._thread = threading.Thread(target=self._run, name="companion-server", daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout):
            self.stop()
            raise TimeoutError(f"The companion server did not start within {timeout:g} s.")
        if self._error is not None:
            self._thread.join(timeout)
            raise self._error
        return self.url

    def stop(self, timeout: float = 15.0) -> bool:
        """Stop serving the way Ctrl+C does (``on_shutdown`` runs: clients closed, core stopped).
        Returns ``True`` when the server thread has finished."""
        thread, loop, stop = self._thread, self._loop, self._stop_requested
        if thread is None:
            if self._sock is not None:
                self._sock.close()
            return True
        if loop is not None and stop is not None and not loop.is_closed():
            try:
                loop.call_soon_threadsafe(stop.set)
            except RuntimeError:  # the loop has already closed
                pass
        thread.join(timeout)
        return not thread.is_alive()

    # --- the server thread ---

    def _run(self) -> None:
        try:
            asyncio.run(self._serve())
        except BaseException as error:  # noqa: BLE001 - handed to start(); the thread must not die silently
            if self._error is None:
                self._error = error
        finally:
            self._ready.set()
            if self._sock is not None:
                self._sock.close()

    async def _serve(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._stop_requested = asyncio.Event()
        assert self.app is not None and self._sock is not None
        runner = web.AppRunner(self.app, handle_signals=False, access_log=None, shutdown_timeout=self._shutdown_timeout)
        await runner.setup()
        try:
            site = web.SockSite(runner, self._sock)
            await site.start()
            self._ready.set()
            await self._stop_requested.wait()
        finally:
            await runner.cleanup()
