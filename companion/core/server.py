"""The local server: a WebSocket at ``/ws`` for the UI, and the built UI at ``/``.

Bound to the loopback interface only. A browser page from any other origin must not be
able to drive the companion, so a WebSocket upgrade is refused unless its ``Origin`` is
this server's own (``http://127.0.0.1:<port>`` or ``http://localhost:<port>``) or absent
(a script, not a browser). Requests whose ``Host`` is not one of those names are refused
too, which stops a DNS-rebinding page from posing as this origin. ``--allow-origin`` adds
an origin (a UI dev server, for example).

Every client gets ``hello``, the latest ``snapshot`` and ``status`` when it connects, then
everything the core sends. Messages are queued per client on the event loop, so a slow
client never holds up the core or the others; one that falls too far behind is dropped.
"""

from __future__ import annotations

import asyncio
import ipaddress
from pathlib import Path
from typing import Any, Iterable

from aiohttp import WSMsgType, web

from companion import paths as _paths
from companion.core import wire
from companion.core.loop import Core

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DIST = _paths.default_ui_dir()
CLIENT_QUEUE = 2000  # messages waiting for one client before it is dropped
MAX_MESSAGE = 64 * 1024

NOT_BUILT = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Trading Companion</title></head>
<body style="font-family: system-ui, sans-serif; background: #111; color: #ddd; padding: 2rem">
<h1>Trading Companion</h1>
<p>The companion core is running, but the UI is not built: <code>companion/web/dist</code> does not exist.</p>
<p>The WebSocket is at <code>/ws</code>.</p>
</body></html>
"""

_CORE = web.AppKey("core", Core)
_HUB = web.AppKey("hub", object)


def is_loopback(host: str) -> bool:
    if host.strip().lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host.strip("[]")).is_loopback
    except ValueError:
        return False


def own_hosts(host: str, port: int) -> set[str]:
    """The ``Host`` header values this server answers to."""
    names = {host, "127.0.0.1", "localhost"}
    if ":" in host and not host.startswith("["):
        names.add(f"[{host}]")
    return {f"{name}:{port}" for name in names}


def own_origins(host: str, port: int, extra: Iterable[str] = ()) -> set[str]:
    return {f"http://{name}" for name in own_hosts(host, port)} | {origin.rstrip("/") for origin in extra}


class Hub:
    """The connected clients, on the event loop. The core calls ``publish`` from its own thread."""

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop
        self.clients: dict[web.WebSocketResponse, asyncio.Queue[str | None]] = {}
        self.latest: dict[str, dict[str, Any]] = {}  # as delivered, so a newcomer is never behind or ahead of the others

    def publish(self, message: dict[str, Any]) -> None:
        """Thread-safe: hand one core message to every client."""
        self.loop.call_soon_threadsafe(self._broadcast, message)

    def reply_to(self, socket: web.WebSocketResponse) -> Any:
        def reply(message: dict[str, Any]) -> None:
            self.loop.call_soon_threadsafe(self._send, socket, message)

        return reply

    def _broadcast(self, message: dict[str, Any]) -> None:
        kind = message.get("type")
        if kind in ("hello", "state", "snapshot", "status"):
            self.latest[str(kind)] = message
        if kind == "hello":
            self.latest["state"] = wire.state_message(message["state"])
        text = wire.dumps(message)
        for socket in list(self.clients):
            self._put(socket, text)

    def _send(self, socket: web.WebSocketResponse, message: dict[str, Any]) -> None:
        if socket in self.clients:
            self._put(socket, wire.dumps(message))

    def _put(self, socket: web.WebSocketResponse, text: str | None) -> None:
        outbox = self.clients.get(socket)
        if outbox is None:
            return
        try:
            outbox.put_nowait(text)
        except asyncio.QueueFull:
            self.clients.pop(socket, None)
            asyncio.ensure_future(socket.close(message=b"too slow"))

    def join(self, socket: web.WebSocketResponse) -> asyncio.Queue[str | None]:
        """Register a client and queue its welcome: hello (with the current state), snapshot, status."""
        outbox: asyncio.Queue[str | None] = asyncio.Queue(CLIENT_QUEUE)
        self.clients[socket] = outbox
        hello = self.latest.get("hello")
        if hello is not None:
            state = self.latest.get("state", {}).get("state", hello["state"])
            outbox.put_nowait(wire.dumps({**hello, "state": state}))
        for kind in ("snapshot", "status"):
            if kind in self.latest:
                outbox.put_nowait(wire.dumps(self.latest[kind]))
        return outbox

    def leave(self, socket: web.WebSocketResponse) -> None:
        outbox = self.clients.pop(socket, None)
        if outbox is not None:
            try:
                outbox.put_nowait(None)
            except asyncio.QueueFull:
                pass


def make_app(core: Core, *, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, dist: Path = DIST, allow_origins: Iterable[str] = ()) -> web.Application:
    """The aiohttp application around a core. The core is started and stopped with the app."""
    hosts = own_hosts(host, port)
    origins = own_origins(host, port, allow_origins)

    @web.middleware
    async def only_this_host(request: web.Request, handler: Any) -> web.StreamResponse:
        if request.headers.get("Host", "") not in hosts:
            return web.Response(status=403, text="This server answers on the loopback address only.")
        return await handler(request)

    app = web.Application(middlewares=[only_this_host])
    app[_CORE] = core

    async def socket_handler(request: web.Request) -> web.StreamResponse:
        origin = request.headers.get("Origin")
        if origin is not None and origin.rstrip("/") not in origins:
            return web.Response(status=403, text="WebSocket refused: this origin may not drive the companion.")
        hub: Hub = app[_HUB]  # type: ignore[assignment]
        socket = web.WebSocketResponse(heartbeat=20, max_msg_size=MAX_MESSAGE)
        await socket.prepare(request)
        outbox = hub.join(socket)
        reply = hub.reply_to(socket)

        async def writer() -> None:
            while True:
                text = await outbox.get()
                if text is None or socket.closed:
                    return
                try:
                    await socket.send_str(text)
                except (ConnectionError, RuntimeError):
                    return

        sending = asyncio.ensure_future(writer())
        try:
            async for frame in socket:
                if frame.type in (WSMsgType.TEXT, WSMsgType.BINARY):
                    try:
                        command = wire.parse_command(frame.data)
                    except wire.WireError as problem:
                        reply(wire.error(str(problem)))
                        continue
                    core.submit(command, reply)
                elif frame.type == WSMsgType.ERROR:
                    break
        finally:
            hub.leave(socket)
            sending.cancel()
        return socket

    async def page_handler(request: web.Request) -> web.StreamResponse:
        if not dist.is_dir():
            return web.Response(text=NOT_BUILT, content_type="text/html")
        root = dist.resolve()
        wanted = (root / request.match_info.get("tail", "")).resolve()
        if wanted != root and root not in wanted.parents:
            raise web.HTTPNotFound()
        if wanted.is_file():
            return web.FileResponse(wanted)
        index = root / "index.html"
        if index.is_file():
            return web.FileResponse(index)  # a single-page app: its own router reads the path
        raise web.HTTPNotFound()

    async def on_startup(app_: web.Application) -> None:
        hub = Hub(asyncio.get_running_loop())
        app_[_HUB] = hub
        core.add_listener(hub.publish)
        core.start()

    async def on_shutdown(app_: web.Application) -> None:
        hub: Hub = app_[_HUB]  # type: ignore[assignment]
        for socket in list(hub.clients):
            await socket.close(message=b"server shutting down")
        await asyncio.get_running_loop().run_in_executor(None, core.stop)

    app.router.add_get("/ws", socket_handler)
    app.router.add_get("/{tail:.*}", page_handler)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    return app
