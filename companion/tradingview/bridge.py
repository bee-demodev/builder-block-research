"""The real bridge: TradingView Desktop over its debug port (Chrome DevTools Protocol).

How it gets bars
----------------
Not from a chart, and not from a tab of its own: TradingView Desktop 3.5 refuses every
way of opening a tab over the debug port (``Target.createTarget``, ``/json/new``, Ctrl+T).
Instead the bridge picks one of the chart tabs that is already open (the first background
one; the tab on screen only when it is the only chart tab), and installs ``companion.tradingview.pagefeed`` in that page: a small
object that opens data series of its own on the page's existing market-data connection.
One private series per (ticker, resolution), each streaming like a chart would, none of
them attached to a chart.

What it touches
---------------
In the host page: one global object and its private data sessions. Nothing else. No
chart's symbol, resolution, layout, studies, drawings, alerts or settings are changed;
no tab is opened, closed, navigated or brought to the front; nothing is clicked or typed.
The other tabs are only asked what they show (for the diagnostic). No orders, no alerts.

If the host tab is closed, reloaded or loses its connection, the bridge installs the
feed in another chart tab by itself. If no chart tab is open at all it raises
``no_chart_tab``: the trader opens any chart and the feed resumes.

Limits respected
----------------
- one series per data session (a second one is a critical error on TradingView's side);
- at most ``max_series`` private series at a time (the least recently read one is closed
  first; the entry timeframe the window rests on is never the one closed).
"""

from __future__ import annotations

import re
import threading
import time
from typing import Any, Callable

from companion.tradingview import cdp, pagefeed
from companion.tradingview.errors import TradingViewError
from companion.tradingview.source import BarsPayload
from companion.tradingview.symbols import FeedSettings

CHART_PATTERN = r"^https://[a-z.]*tradingview\.com/chart(/|$|\?)"
_LAYOUT = re.compile(r"/chart/([A-Za-z0-9]+)/")
MORE_STEP = 5000  # older bars asked for in one request
PRELOAD = 300  # what a chart asks for when it opens a series


def layout_id(url: str) -> str:
    """The saved-layout id in a chart address (``/chart/AbCd1234/``), ``""`` when it has none."""
    match = _LAYOUT.search(url or "")
    return match.group(1) if match else ""


def series_key(ticker: str, resolution: str) -> str:
    return f"{ticker}|{resolution}"


class _FeedLost(Exception):
    """The feed object in the host page is gone (page reloaded, connection dropped)."""


class CdpBridge:
    """``Bridge`` over the debug port. One instance per window; safe to call from any one thread at a time."""

    READY_SECONDS = 20.0
    DEEPEN_SECONDS = 60.0
    MORE_SECONDS = 12.0
    POLL = 0.05

    def __init__(
        self,
        settings: FeedSettings | None = None,
        *,
        chart_pattern: str = CHART_PATTERN,
        is_running: Callable[[], bool] | None = None,
        list_targets: Callable[[], Any] | None = None,
        open_session: Callable[[dict[str, Any]], Any] | None = None,
    ) -> None:
        self.settings = settings if settings is not None else FeedSettings()
        self.port = self.settings.port
        self._pattern = re.compile(chart_pattern, re.IGNORECASE)
        self._is_running = is_running if is_running is not None else cdp.tradingview_is_running
        self._list_targets = list_targets if list_targets is not None else (lambda: cdp.http_json(self.port, "/json/list"))
        self._open_session = open_session if open_session is not None else self._open_socket
        self._session: Any = None
        self._host_id = ""
        self._pinned = ""
        self._lock = threading.RLock()
        self.report: dict[str, Any] = {}  # what happened, for the diagnostic command

    # --- targets ---

    def _open_socket(self, target: dict[str, Any]) -> cdp.CdpSession:
        address = target.get("webSocketDebuggerUrl") or f"ws://{cdp.HOST}:{self.port}/devtools/page/{target['id']}"
        return cdp.CdpSession(str(address))

    def _targets(self) -> list[dict[str, Any]]:
        try:
            listed = self._list_targets()
        except cdp.CdpError as error:
            self._drop()
            kind = "no_debug_port" if self._is_running() else "not_running"
            raise TradingViewError(kind, technical=str(error)) from None
        if not isinstance(listed, list):
            return []
        return [t for t in listed if isinstance(t, dict) and t.get("type") == "page" and self._pattern.search(str(t.get("url", "")))]

    def _drop(self) -> None:
        if self._session is not None:
            try:
                self._session.close()
            except Exception:  # noqa: BLE001 - closing a dead socket
                pass
        self._session = None

    def peek_tabs(self) -> list[dict[str, Any]]:
        """Symbol, resolution, visibility and layout of every open chart tab. Reads only."""
        seen = []
        for target in self._targets():
            entry: dict[str, Any] = {"id": str(target.get("id")), "layout": layout_id(str(target.get("url", "")))}
            try:
                if str(target.get("id")) == self._host_id and self._session is not None:
                    entry.update(self._session.evaluate(pagefeed.JS_PEEK, timeout=5) or {})
                else:
                    session = self._open_session(target)
                    try:
                        entry.update(session.evaluate(pagefeed.JS_PEEK, timeout=5) or {})
                    finally:
                        session.close()
            except cdp.CdpError as error:
                entry["error"] = str(error)
            seen.append(entry)
        return seen

    def chart_bars(self, target_id: str, count: int = 300) -> dict[str, Any]:
        """The bars one of the open charts holds itself (the diagnostic compares them with the feed's). Reads only."""
        target = next((t for t in self._targets() if str(t.get("id")) == target_id), None)
        if target is None:
            return {}
        session = self._open_session(target)
        try:
            return session.evaluate(pagefeed.JS_CHART_BARS % int(count), timeout=20) or {}
        finally:
            session.close()

    # --- the host page ---

    @property
    def host_id(self) -> str:
        return self._host_id

    def _connect(self) -> Any:
        """A debug socket to a chart page with the feed installed in it."""
        targets = self._targets()
        ids = {str(t.get("id")) for t in targets}
        if self._session is not None and getattr(self._session, "is_open", True) and self._host_id in ids:
            return self._session
        self._drop()
        self._host_id = ""
        if not targets:
            raise TradingViewError("no_chart_tab", technical="the debug port lists no tradingview.com/chart page")

        # Which page hosts the feed: the first background chart tab with a working data
        # connection, in the port's order, and the search stops there, so as few of the
        # trader's tabs as possible are even looked at. (A restarted companion lands on the
        # same tab and finds its series still there.) A tab on screen is used only when no
        # background tab will do.
        problems: list[str] = []
        on_screen: list[tuple[dict[str, Any], Any, dict[str, Any]]] = []
        chosen = None

        def install(target: dict[str, Any], session: Any, look: dict[str, Any]) -> bool:
            nonlocal chosen
            try:
                installed = session.evaluate(pagefeed.JS_INSTALL, timeout=10) or {}
            except cdp.CdpError as error:
                installed = {"ok": False, "error": str(error)}
            if installed.get("ok"):
                chosen = (target, session, look, installed)
                return True
            problems.append(f"{target.get('id')}: install {installed.get('error')}")
            return False

        for target in targets:
            try:
                session = self._open_session(target)
            except cdp.CdpError as error:
                problems.append(f"{target.get('id')}: {error}")
                continue
            try:
                look = session.evaluate(pagefeed.JS_PEEK, timeout=5) or {}
            except cdp.CdpError as error:
                look = {"error": str(error)}
            if not look.get("connected"):
                problems.append(f"{target.get('id')}: {look.get('error') or 'data connection not ready'}")
                session.close()
            elif look.get("visible"):
                on_screen.append((target, session, look))
            elif install(target, session, look):
                break
            else:
                session.close()
        for target, session, look in on_screen:
            if chosen is not None or not install(target, session, look):
                session.close()
        if chosen is None:
            raise TradingViewError("loading", technical="no chart page with a ready data connection: " + "; ".join(problems))
        target, session, look, installed = chosen
        self._session, self._host_id = session, str(target.get("id"))
        self.report["host"] = {
            "id": self._host_id,
            "layout": layout_id(str(target.get("url", ""))),
            "symbol": look.get("symbol"),
            "resolution": look.get("resolution"),
            "visible": bool(look.get("visible")),
            "reused_feed": bool(installed.get("reused")),
        }
        return session

    def _call(self, session: Any, method: str, *args: object, timeout: float = 10) -> dict[str, Any]:
        answer = session.evaluate(pagefeed.call(method, *args), timeout=timeout)
        if not isinstance(answer, dict):
            return {"value": answer}
        if answer.get("dead") or answer.get("error") == "dead":
            raise _FeedLost(str(answer.get("why") or "gone"))
        return answer

    # --- Bridge ---

    def fetch_bars(self, ticker: str, resolution: str, count: int) -> BarsPayload:
        with self._lock:
            last = ""
            for attempt in (1, 2, 3):
                try:
                    return self._fetch(self._connect(), ticker, resolution, count)
                except _FeedLost as lost:
                    # the page reloaded or its connection dropped: install afresh (another tab if need be)
                    last = f"feed lost: {lost}"
                    self.report["reinstalled"] = self.report.get("reinstalled", 0) + 1
                    self._drop()
                except cdp.CdpError as error:
                    last = str(error)
                    self._drop()
                self.report.setdefault("retries", []).append(f"{time.strftime('%H:%M:%S')} {ticker} {resolution}: {last}")
                del self.report["retries"][:-20]
                if attempt < 3:
                    time.sleep(0.3 * attempt)
            self._targets()  # raises not_running / no_debug_port when the port is gone
            raise TradingViewError("protocol", technical=last)

    def park(self, ticker: str, resolution: str) -> None:
        """Nothing is switched any more; this only marks the series that must not be closed to make room."""
        self._pinned = series_key(ticker, resolution)

    def close(self) -> None:
        """Take the feed out of the host page and drop the socket. Best effort."""
        if not self._lock.acquire(timeout=2.0):
            return
        try:
            if self._session is not None:
                try:
                    self._session.evaluate(pagefeed.JS_REMOVE, timeout=3)
                except cdp.CdpError:
                    pass
            self._drop()
            self._host_id = ""
        finally:
            self._lock.release()

    def release(self, ticker: str, resolution: str) -> None:
        """Close one private series (the diagnostic uses it)."""
        with self._lock:
            if self._session is not None:
                try:
                    self._session.evaluate(pagefeed.call("close", series_key(ticker, resolution)), timeout=5)
                except cdp.CdpError:
                    self._drop()

    PEEK_SECONDS = 1.0

    def peek(self, ticker: str, resolution: str) -> dict[str, Any] | None:
        """The newest two bars of an open private series, forming one last: one small ``Runtime.evaluate``.

        For a watcher that asks about twice a second, so it never waits and never connects:
        ``None`` while a read holds the link, before the feed is installed, when the series
        is not open, or when the page does not answer within ``PEEK_SECONDS``. A failed peek
        leaves the link to the next read, which reconnects when it has to.
        """
        if not self._lock.acquire(blocking=False):
            return None
        try:
            if self._session is None or not getattr(self._session, "is_open", True):
                return None
            try:
                answer = self._session.evaluate(pagefeed.call("peek", series_key(ticker, resolution)), timeout=self.PEEK_SECONDS)
            except cdp.CdpError:
                return None
        finally:
            self._lock.release()
        if not isinstance(answer, dict) or answer.get("dead") or answer.get("state") != "ready" or not answer.get("rows"):
            return None
        return answer

    def status(self, ticker: str, resolution: str) -> dict[str, Any]:
        """The private series as the page sees it (size, last update, server clock). Opens nothing."""
        with self._lock:
            try:
                return self._call(self._connect(), "status", series_key(ticker, resolution))
            except (_FeedLost, cdp.CdpError) as error:
                return {"state": "none", "error": str(error)}

    # --- reading ---

    def _make_room(self, session: Any, key: str) -> None:
        listed = session.evaluate(pagefeed.call("list"), timeout=5)
        if not isinstance(listed, list):
            if isinstance(listed, dict) and listed.get("dead"):
                raise _FeedLost(str(listed.get("why") or "gone"))
            return
        if any(entry.get("key") == key for entry in listed):
            return
        limit = max(2, int(self.settings.max_series))
        spare = sorted((entry for entry in listed if entry.get("key") != self._pinned), key=lambda entry: entry.get("used") or 0)
        while len(listed) >= limit and spare:
            victim = spare.pop(0)
            session.evaluate(pagefeed.call("close", victim["key"]), timeout=5)
            listed = [entry for entry in listed if entry.get("key") != victim["key"]]
            self.report["closed_for_room"] = self.report.get("closed_for_room", 0) + 1

    def _fetch(self, session: Any, ticker: str, resolution: str, count: int) -> BarsPayload:
        started = time.monotonic()
        key = series_key(ticker, resolution)
        count = max(1, int(count))
        self._make_room(session, key)
        symbol = pagefeed.symbol_string(ticker, settlement_as_close=self.settings.settlement_as_close, session=self.settings.session)
        state = self._call(session, "open", key, symbol, resolution, PRELOAD)  # what a chart asks for; older bars come on request
        fresh = state.get("state") != "ready"
        deadline = started + self.READY_SECONDS
        while state.get("state") not in ("ready", "error"):
            if time.monotonic() > deadline:
                self._close_quietly(session, key)
                raise TradingViewError("loading", f"{ticker} at {resolution}", technical=f"series still {state.get('state')} after {self.READY_SECONDS:.0f} s")
            time.sleep(self.POLL)
            state = self._call(session, "status", key)
        if state.get("state") == "error":
            self._close_quietly(session, key)
            raise self._classify(state.get("error") or {}, ticker, resolution)
        if state.get("connected") is False:
            raise _FeedLost("the page's data connection is down")
        if fresh:
            self.report["load_seconds"] = round(time.monotonic() - started, 2)

        deepened = None
        if int(state.get("size") or 0) < count:
            state, deepened = self._deepen(session, key, state, count)
        data = self._call(session, "read", key, count, timeout=60)
        rows = data.get("rows") or []
        size = int(data.get("size") or 0)
        if not rows:
            self._close_quietly(session, key)
            raise TradingViewError("no_permission", ticker, technical=f"the {resolution} series completed with no bars (mode {data.get('mode')})")
        info = data.get("info") or {}
        mode = str(data.get("mode") or "")
        notes: tuple[str, ...] = ()
        if "delayed" in mode or "delayed" in str(info.get("update_mode", "")).lower():
            digits = re.search(r"(\d+)\s*$", mode)
            seconds = int(digits.group(1)) if digits else int(info.get("delay") or 0)
            notes = (f"DELAYED data ({seconds // 60} min behind)" if seconds >= 60 else "DELAYED data",)
        elif mode and mode not in ("streaming", "pulsed"):
            notes = (f"not streaming ({mode.replace('_', ' ')})",)
        self.report["series"] = {
            "key": key, "size": size, "mode": mode, "deepen": deepened, "server_time": data.get("server_time"),
            "page_time": data.get("now"), "updated": data.get("updated"), "last_close": data.get("last_close"), "info": info,
        }  # fmt: skip
        closes = data.get("last_close")
        return BarsPayload(
            rows=rows,
            exhausted=size < count,
            ticker=str(info.get("pro_name") or ticker),
            notes=notes,
            forming_until=float(closes) + 1.0 if isinstance(closes, (int, float)) and rows[-1][0] < closes else None,
        )

    def _close_quietly(self, session: Any, key: str) -> None:
        try:
            session.evaluate(pagefeed.call("close", key), timeout=5)
        except cdp.CdpError:
            pass

    def _deepen(self, session: Any, key: str, state: dict[str, Any], count: int) -> tuple[dict[str, Any], dict[str, Any]]:
        """Ask for older bars until ``count`` are held or TradingView has no more."""
        deadline = time.monotonic() + self.DEEPEN_SECONDS
        requests = 0
        while int(state.get("size") or 0) < count and int(state.get("dry") or 0) < 2 and time.monotonic() < deadline:
            need = min(MORE_STEP, count - int(state.get("size") or 0) + 20)
            asked = self._call(session, "more", key, need)
            requests += 1 if asked.get("asked") else 0
            round_end = time.monotonic() + self.MORE_SECONDS
            while True:
                time.sleep(self.POLL)
                state = self._call(session, "status", key)
                if state.get("state") != "ready":
                    raise self._classify(state.get("error") or {}, key.split("|")[0], key.split("|")[-1])
                if not state.get("more") and not state.get("busy"):
                    break
                if time.monotonic() > round_end:
                    return state, {"requests": requests, "size": state.get("size"), "wanted": count, "timed_out": True}
        return state, {"requests": requests, "size": state.get("size"), "wanted": count, "dry": state.get("dry")}

    @staticmethod
    def _classify(error: dict[str, Any], ticker: str, resolution: str) -> TradingViewError:
        """TradingView's own words for a failed series -> the companion's kind."""
        kind, text = str(error.get("kind", "")), str(error.get("text", ""))
        technical = f"{kind}: {text}"
        low = text.lower()
        if kind == "symbol":
            if "invalid" in low or "not found" in low or "unknown" in low:
                return TradingViewError("symbol_not_found", ticker, technical=technical)
            return TradingViewError("no_permission", ticker, technical=technical)  # permission denied and its variants
        if kind == "series":
            if "unsupported" in low or "resolution" in low or "custom_resolution" in low or "interval" in low:
                return TradingViewError("unexpected_bars", f"TradingView will not serve {ticker} at resolution {resolution}", technical=technical)
            if "auth" in low or "permission" in low or "denied" in low:
                return TradingViewError("no_permission", ticker, technical=technical)
            return TradingViewError("loading", f"{ticker} at {resolution}", technical=technical)
        return TradingViewError("protocol", technical=technical)
