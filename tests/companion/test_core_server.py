"""The local server, for real: aiohttp on a loopback port, the core on its own threads, a fake TradingView."""

from __future__ import annotations

import asyncio
import json
import socket
from pathlib import Path
from typing import Any, Awaitable, Callable

import aiohttp
import pandas as pd
import pytest
from aiohttp.test_utils import TestServer

from companion.app_model import DATA_LIVE, CompanionController
from companion.core.loop import Core
from companion.core.server import is_loopback, make_app
from companion.timeframes import get_stack
from companion.tradingview import TradingViewBarSource
from tradingview_fakes import FakeTradingView, market_minutes, write_symbols

NOW = "2026-03-10 10:47:20"
WAIT = 20.0


@pytest.fixture(scope="module")
def minutes() -> pd.DataFrame:
    return market_minutes()


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def live_core(minutes: pd.DataFrame, tmp_path: Path) -> tuple[Core, FakeTradingView]:
    tv = FakeTradingView(minutes, pd.Timestamp(NOW, tz="America/New_York"))
    source = TradingViewBarSource(tv, symbols_path=write_symbols(tmp_path / "symbols.json"), clock=tv.clock)
    controller = CompanionController(state_path=tmp_path / "state" / "ui_state.json", live_source=source, default_data=DATA_LIVE, clock=tv.clock)
    controller.state.symbol, controller.state.stack, controller.state.style = "NQ", get_stack("1D / 1h / 5m").name, "ttrades"
    return Core(controller, watch_ms=200, tick_ms=50), tv


def serve(minutes: pd.DataFrame, tmp_path: Path, test: Callable[[str, Core, FakeTradingView], Awaitable[None]], **options: Any) -> FakeTradingView:
    """Run ``test(base_url, core, tv)`` against a started server, then shut it down as Ctrl+C would."""
    core, tv = live_core(minutes, tmp_path)
    port = free_port()

    async def run() -> None:
        server = TestServer(make_app(core, port=port, **options), host="127.0.0.1", port=port)
        await server.start_server()
        try:
            await test(f"http://127.0.0.1:{port}", core, tv)
        finally:
            await server.close()

    asyncio.run(run())
    return tv


async def until(socket_: aiohttp.ClientWebSocketResponse, wanted: Callable[[dict[str, Any]], bool]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Read messages until one satisfies ``wanted``; that one, and everything read."""
    seen: list[dict[str, Any]] = []
    async with asyncio.timeout(WAIT):
        while True:
            message = json.loads(await socket_.receive_str())
            seen.append(message)
            if wanted(message):
                return message, seen


def with_view(message: dict[str, Any]) -> bool:
    return message["type"] == "snapshot" and message["view"] is not None


def test_a_client_is_welcomed_then_drives_the_core(minutes: pd.DataFrame, tmp_path: Path) -> None:
    async def test(base: str, core: Core, tv: FakeTradingView) -> None:
        async with aiohttp.ClientSession() as session, session.ws_connect(f"{base}/ws") as ws:
            hello, _ = await until(ws, lambda m: True)
            assert hello["type"] == "hello" and hello["version"] == 1 and hello["state"]["symbol"] == "NQ"
            assert set(hello["options"]) >= {"symbols", "stacks", "timeframes", "styles", "data"}
            first, _ = await until(ws, with_view)  # the core checked by itself on start

            await ws.send_str("not json")
            error, _ = await until(ws, lambda m: m["type"] == "error")
            assert "not JSON" in error["message"]
            await ws.send_str(json.dumps({"type": "step", "direction": 1}))  # well formed, but there is no later bar
            error, _ = await until(ws, lambda m: m["type"] == "error")
            assert "last closed bar" in error["message"]

            await ws.send_json({"type": "check"})
            again, seen = await until(ws, with_view)
            assert again["seq"] > first["seq"] and any(m["type"] == "state" and m["state"]["busy"] for m in seen)

    tv = serve(minutes, tmp_path, test)
    assert tv.closed  # shutting down took the feed out of TradingView's page


def test_every_client_gets_the_latest_snapshot_and_every_update(minutes: pd.DataFrame, tmp_path: Path) -> None:
    async def test(base: str, core: Core, tv: FakeTradingView) -> None:
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(f"{base}/ws") as one:
                await until(one, with_view)
                async with session.ws_connect(f"{base}/ws") as two:
                    _, welcome = await until(two, with_view)
                    assert [m["type"] for m in welcome][:2] == ["hello", "snapshot"]  # the latest one, without a new check
                    await one.send_json({"type": "set", "stack": "4h / 15m / 1m"})
                    for ws in (one, two):
                        update, _ = await until(ws, lambda m: with_view(m) and "4h / 15m / 1m" in m["view"]["headline"])
                        assert update["status"]["state"] in ("live", "stale")

    serve(minutes, tmp_path, test)


def test_only_this_origin_may_open_the_socket(minutes: pd.DataFrame, tmp_path: Path) -> None:
    async def test(base: str, core: Core, tv: FakeTradingView) -> None:
        port = base.rsplit(":", 1)[1]
        async with aiohttp.ClientSession() as session:
            for origin in ("http://evil.example", f"http://evil.example:{port}", "null", f"https://127.0.0.1:{port}"):
                with pytest.raises(aiohttp.WSServerHandshakeError) as refused:
                    await session.ws_connect(f"{base}/ws", origin=origin)
                assert refused.value.status == 403
            for origin in (f"http://127.0.0.1:{port}", f"http://localhost:{port}", "http://localhost:5173"):
                async with session.ws_connect(f"{base}/ws", origin=origin) as ws:
                    assert (await until(ws, lambda m: True))[0]["type"] == "hello"
            # a page that rebinds its own name to this address still sends its own Host
            async with session.get(f"{base}/", headers={"Host": f"evil.example:{port}"}) as response:
                assert response.status == 403

    serve(minutes, tmp_path, test, allow_origins=["http://localhost:5173"])


def test_the_built_ui_is_served_and_nothing_outside_it(minutes: pd.DataFrame, tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    (tmp_path / "secret.txt").write_text("private", encoding="utf-8")

    async def missing(base: str, core: Core, tv: FakeTradingView) -> None:
        async with aiohttp.ClientSession() as session, session.get(f"{base}/") as response:
            assert response.status == 200 and "UI is not built" in await response.text()

    serve(minutes, tmp_path, missing, dist=dist)

    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>companion ui</html>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")

    async def built(base: str, core: Core, tv: FakeTradingView) -> None:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{base}/assets/app.js") as response:
                assert response.status == 200 and await response.text() == "console.log(1)"
            async with session.get(f"{base}/history/NQ") as response:  # the UI's own route: the page itself
                assert "companion ui" in await response.text()
            from yarl import URL

            async with session.get(URL(f"{base}/%2E%2E/secret.txt", encoded=True)) as response:
                assert "private" not in await response.text()

    serve(minutes, tmp_path, built, dist=dist)


def test_the_server_binds_to_loopback_only() -> None:
    assert is_loopback("127.0.0.1") and is_loopback("::1") and is_loopback("localhost")
    assert not is_loopback("0.0.0.0") and not is_loopback("192.168.1.20") and not is_loopback("example.com")
