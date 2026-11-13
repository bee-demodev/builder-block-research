"""The server on a background thread (what the desktop window runs): start, serve, stop as Ctrl+C would."""

from __future__ import annotations

import asyncio
import json
import socket
from pathlib import Path

import aiohttp
import pandas as pd
import pytest

from companion.core.background import ServerThread, bind_port, bind_preferred
from companion.core.server import make_app
from test_core_server import WAIT, live_core
from tradingview_fakes import market_minutes


@pytest.fixture(scope="module")
def minutes() -> pd.DataFrame:
    return market_minutes()


def port_is_free(port: int) -> bool:
    with socket.socket() as probe:
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def test_a_free_port_is_bound_and_a_taken_preferred_port_falls_back() -> None:
    first = bind_port()
    try:
        port = first.getsockname()[1]
        assert first.getsockname()[0] == "127.0.0.1" and port > 0
        assert not port_is_free(port)  # held, so nothing else can take it before the server listens
        second = bind_preferred(preferred=port)  # taken: another free port instead
        try:
            assert second.getsockname()[1] not in (0, port)
        finally:
            second.close()
    finally:
        first.close()
    again = bind_preferred(preferred=port)  # free again: the same port, so the UI's origin stays the same
    try:
        assert again.getsockname()[1] == port
    finally:
        again.close()


def test_started_from_another_thread_it_serves_and_stops_like_ctrl_c(minutes: pd.DataFrame, tmp_path: Path) -> None:
    core, tv = live_core(minutes, tmp_path)
    server = ServerThread(lambda port: make_app(core, port=port))
    url = server.start()
    port = server.port
    assert url == f"http://127.0.0.1:{port}/" and server.running and not port_is_free(port)

    async def client() -> tuple[dict, aiohttp.WSMessage]:
        async with aiohttp.ClientSession() as session, session.ws_connect(f"{url}ws", origin=url.rstrip("/")) as ws:
            async with asyncio.timeout(WAIT):
                hello = json.loads(await ws.receive_str())
            await asyncio.get_running_loop().run_in_executor(None, server.stop)  # the window closed
            async with asyncio.timeout(WAIT):
                while True:
                    last = await ws.receive()
                    if last.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSING):
                        return hello, last

    hello, last = asyncio.run(client())
    assert hello["type"] == "hello"
    assert last.extra == "server shutting down"  # on_shutdown ran: clients were told
    assert not server.running
    assert tv.closed  # the core let go of TradingView
    assert core.controller.state_path.is_file()  # and saved the selections
    assert port_is_free(port)  # nothing left holding the port


def test_a_server_that_cannot_be_built_raises_and_releases_the_port() -> None:
    sock = bind_port()
    port = sock.getsockname()[1]

    def broken(_port: int):
        raise RuntimeError("no core")

    server = ServerThread(broken, sock=sock)
    with pytest.raises(RuntimeError, match="no core"):
        server.start()
    assert port_is_free(port)
    assert server.stop()  # stopping what never ran is harmless
