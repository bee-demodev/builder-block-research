"""The real bridge against a fake TradingView Desktop: pages, the debug port's target list, the page feed.

No TradingView and no network. ``FakeDesktop`` stands in for the debug port; each
``FakePage`` answers the handful of expressions the bridge may evaluate and fails the test
on any other, which is how "it never touches a chart" is held.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from companion.tradingview import TradingViewBarSource, TradingViewError, cdp, pagefeed
from companion.tradingview.bridge import CdpBridge, layout_id, series_key
from companion.tradingview.mapping import rows_to_frame
from companion.tradingview.source import BarsPayload
from companion.tradingview.symbols import FeedSettings
from tradingview_fakes import TICKER, write_symbols

_CALL = re.compile(r"return f\.(\w+)\((.*)\); \}\)\(\)$", re.DOTALL)
START = 1_794_000_000  # a bar time, UTC seconds


def five_minute_rows(count: int, last: int = START) -> list[list[float]]:
    return [[last - 300 * (count - 1 - i), 100.0 + i, 101.0 + i, 99.0 + i, 100.5 + i, 10.0] for i in range(count)]


class FakePage:
    """One TradingView page: what it shows, and the feed object once it is installed."""

    def __init__(self, target_id: str, url: str, *, symbol: str = "CME_MINI:NQZ2026", resolution: str = "5", visible: bool = False, connected: bool = True) -> None:
        self.id, self.url, self.symbol, self.resolution, self.visible, self.connected = target_id, url, symbol, resolution, visible, connected
        self.feed: dict[str, dict[str, Any]] | None = None  # key -> series
        self.dead = ""
        self.history: dict[str, list[list[float]]] = {}  # resolution -> every bar TradingView has
        self.errors: dict[str, dict[str, str]] = {}  # ticker -> the error its series ends in
        self.mode = "streaming"
        self.polls_until_ready = 2
        self.evaluated: list[str] = []
        self.opened: list[str] = []
        self.closed: list[str] = []
        self.more_requests: list[tuple[str, int]] = []
        self.clock = 0

    @property
    def target(self) -> dict[str, Any]:
        return {"id": self.id, "type": "page", "url": self.url, "title": "chart", "webSocketDebuggerUrl": f"ws://fake/{self.id}"}

    # --- what the bridge may evaluate ---

    def evaluate(self, expression: str) -> Any:
        self.evaluated.append(expression)
        if expression == pagefeed.JS_PEEK:
            return {"visible": self.visible, "connected": self.connected, "symbol": self.symbol, "resolution": self.resolution,
                    "feed": self.feed is not None and not self.dead}  # fmt: skip
        if expression == pagefeed.JS_INSTALL:
            if not self.connected:
                return {"ok": False, "error": "not_connected"}
            reused = self.feed is not None and not self.dead
            if not reused:
                self.feed, self.dead = {}, ""
            return {"ok": True, "reused": reused}
        if expression == pagefeed.JS_REMOVE:
            had, self.feed = self.feed is not None, None
            return had
        match = _CALL.search(expression)
        assert match and expression.startswith("(function () { var f = window.__companionFeed;"), f"the bridge evaluated something else: {expression[:160]}"
        if self.feed is None or self.dead:
            return {"ok": False, "dead": True, "why": self.dead or "missing"}
        return getattr(self, "_" + match.group(1))(*json.loads(f"[{match.group(2)}]"))

    def _status(self, key: str) -> dict[str, Any]:
        self.clock += 1
        assert self.feed is not None
        out: dict[str, Any] = {"ok": True, "dead": False, "connected": self.connected, "now": 1, "server_time": 1}
        series = self.feed.get(key)
        if series is None:
            return {**out, "state": "none"}
        series["used"] = self.clock
        if series["state"] in ("resolving", "loading"):
            series["polls"] += 1
            if series["polls"] >= self.polls_until_ready:
                error = self.errors.get(series["ticker"])
                series["state"], series["error"] = ("error", error) if error else ("ready", None)
        rows = series["rows"] if series["state"] == "ready" else []
        return {**out, "state": series["state"], "error": series.get("error"), "size": len(rows), "first": rows[0][0] if rows else None,
                "last": rows[-1][0] if rows else None, "mode": self.mode, "busy": False, "more": False, "dry": series["dry"],
                "info": {"pro_name": series["ticker"], "delay": 0, "update_mode": self.mode}, "last_close": series.get("last_close")}  # fmt: skip

    def _open(self, key: str, symbol: str, resolution: str, count: int) -> dict[str, Any]:
        assert self.feed is not None
        if key not in self.feed or self.feed[key]["state"] == "error":
            body = json.loads(symbol[1:])
            assert symbol.startswith("=") and body["symbol"] and "settlement-as-close" in body
            everything = self.history.get(resolution, five_minute_rows(4000))
            self.feed[key] = {"ticker": body["symbol"], "resolution": resolution, "state": "resolving", "polls": 0, "dry": 0,
                              "all": everything, "rows": everything[-count:], "used": 0, "symbol": body}  # fmt: skip
            self.opened.append(key)
        return self._status(key)

    def _more(self, key: str, bars: int) -> dict[str, Any]:
        assert self.feed is not None
        series = self.feed[key]
        self.more_requests.append((key, bars))
        have = len(series["rows"])
        series["rows"] = series["all"][-(have + bars) :]
        series["dry"] = series["dry"] + 1 if len(series["rows"]) == have else 0
        return {"asked": True}

    def _read(self, key: str, count: int) -> dict[str, Any]:
        out = self._status(key)
        assert self.feed is not None
        if key in self.feed:
            out["rows"] = self.feed[key]["rows"][-count:] if out["state"] == "ready" else []
        return out

    def _close(self, key: str) -> dict[str, Any]:
        assert self.feed is not None
        self.feed.pop(key, None)
        self.closed.append(key)
        return {"keys": list(self.feed)}

    def _list(self) -> list[dict[str, Any]]:
        assert self.feed is not None
        return [{"key": key, "state": s["state"], "size": len(s["rows"]), "used": s["used"]} for key, s in self.feed.items()]


class FakeSession:
    def __init__(self, page: FakePage, desktop: "FakeDesktop") -> None:
        self.page, self.desktop, self.is_open = page, desktop, True

    def evaluate(self, expression: str, timeout: float | None = None) -> Any:
        if not self.is_open or self.page not in self.desktop.pages:
            raise cdp.CdpError("the debug socket closed")
        return self.page.evaluate(expression)

    def call(self, method: str, params: dict[str, Any] | None = None, timeout: float | None = None) -> dict[str, Any]:
        raise AssertionError(f"the bridge sent a raw debug command: {method}")  # no input events, no navigation, no targets

    def close(self) -> None:
        self.is_open = False


class FakeDesktop:
    """The debug port: the target list and a socket per page."""

    def __init__(self, *pages: FakePage, extra: tuple[dict[str, Any], ...] = ()) -> None:
        self.pages = list(pages)
        self.extra = list(extra)  # targets that are not chart pages
        self.port_open = True
        self.sockets: list[str] = []

    def list_targets(self) -> list[dict[str, Any]]:
        if not self.port_open:
            raise cdp.CdpError("GET /json/list: connection refused")
        return [*self.extra, *(page.target for page in self.pages)]

    def open_session(self, target: dict[str, Any]) -> FakeSession:
        page = next((page for page in self.pages if page.id == target["id"]), None)
        assert page is not None, f"the bridge opened a socket to a page that is not a chart: {target.get('url')}"
        self.sockets.append(page.id)
        return FakeSession(page, self)

    def bridge(self, running: bool = True, **settings: Any) -> CdpBridge:
        bridge = CdpBridge(FeedSettings(**settings), is_running=lambda: running, list_targets=self.list_targets, open_session=self.open_session)
        bridge.POLL = 0.0
        return bridge


OTHERS = (
    {"id": "S1", "type": "page", "url": "https://www.tradingview.com/scripts/", "title": "scripts"},
    {"id": "S2", "type": "page", "url": "https://www.tradingview.com/u/SomeTrader/", "title": "profile"},
    {"id": "N1", "type": "page", "url": "file:///C:/Program%20Files/WindowsApps/TradingView.Desktop/resources/app.asar/app/new-tab/index.html", "title": "New tab"},
    {"id": "W1", "type": "page", "url": "file:///C:/Program%20Files/WindowsApps/TradingView.Desktop/resources/app.asar/app/window/index.html", "title": "shell"},
    {"id": "K1", "type": "worker", "url": "", "title": ""},
)


def desktop() -> tuple[FakeDesktop, FakePage, FakePage, FakePage]:
    visible = FakePage("VIS", "https://www.tradingview.com/chart/YKdpKoM0/", visible=True)
    hidden = FakePage("HID", "https://www.tradingview.com/chart/gGIo8QCZ/", symbol="BATS:NVDA", resolution="1W")
    third = FakePage("THR", "https://www.tradingview.com/chart/2ekC72yQ/", symbol="COMEX:GC1!")
    return FakeDesktop(visible, hidden, third, extra=OTHERS), visible, hidden, third


# --- where the feed lives ---------------------------------------------------------


def test_the_feed_goes_into_a_background_chart_tab_and_nothing_else_is_touched() -> None:
    tv, visible, hidden, third = desktop()
    bridge = tv.bridge()
    payload = bridge.fetch_bars(TICKER, "5", 50)
    assert len(payload.rows) == 50 and payload.rows[-1][0] == START and payload.ticker == TICKER and not payload.exhausted
    assert bridge.host_id == "HID" and bridge.report["host"]["layout"] == "gGIo8QCZ" and bridge.report["host"]["visible"] is False
    # the tab on screen was asked what it shows, once, and nothing more; the search stopped at the first background tab
    assert visible.evaluated == [pagefeed.JS_PEEK] and third.evaluated == []
    assert visible.feed is None and third.feed is None
    # only chart pages get a socket: not the scripts page, the profile, the new-tab page or the shell
    assert tv.sockets == ["VIS", "HID"]
    # what the host shows is what it showed
    assert (hidden.symbol, hidden.resolution) == ("BATS:NVDA", "1W")


def test_the_tab_on_screen_is_used_only_when_it_is_the_only_one() -> None:
    only = FakePage("VIS", "https://www.tradingview.com/chart/YKdpKoM0/", visible=True)
    bridge = FakeDesktop(only, extra=OTHERS).bridge()
    assert len(bridge.fetch_bars(TICKER, "5", 10).rows) == 10 and bridge.host_id == "VIS"
    assert (only.symbol, only.resolution) == ("CME_MINI:NQZ2026", "5")


def test_a_restarted_companion_finds_its_feed_again() -> None:
    tv, visible, hidden, third = desktop()
    tv.bridge().fetch_bars(TICKER, "5", 10)
    second = tv.bridge()  # the first one was never closed: its series are still in the page
    second.fetch_bars(TICKER, "5", 10)
    assert second.host_id == "HID" and second.report["host"]["reused_feed"] is True
    assert hidden.opened == [series_key(TICKER, "5")]  # not opened twice


def test_page_scripts_change_no_chart() -> None:
    """Every script the bridge can send: none calls a chart setter, input event, navigation or trading call."""
    scripts = [pagefeed.JS_PEEK, pagefeed.JS_INSTALL, pagefeed.JS_REMOVE, pagefeed.call("read", "k", 5)]
    banned = ("setSymbol", "setResolution", "setLayout", "loadChart", "saveChart", "createStudy", "removeStudy", "createAlert", "alert(",
              "executeAction", "placeOrder", "trading", "location.", "window.open", "dispatchEvent", ".click(", "localStorage", "modifySeries",
              "setTimezone", "switchTimezone", "createMultipointShape", "createShape", "removeEntity")  # fmt: skip
    for script in scripts:
        assert not [word for word in banned if word in script]
    install = pagefeed.JS_INSTALL
    assert install.count("link.createSeries(") == 1  # one series per data session, ever
    assert install.index("case 'symbol_resolved'") < install.index("link.createSeries(") < install.index("case 'symbol_error'")  # and only once the symbol resolved
    assert pagefeed.symbol_string("CME_MINI:NQ1!") == '={"adjustment":"splits","session":"extended","settlement-as-close":false,"symbol":"CME_MINI:NQ1!"}'
    assert json.loads(pagefeed.symbol_string("X:Y", settlement_as_close=True, session="")[1:]) == {"adjustment": "splits", "settlement-as-close": True, "symbol": "X:Y"}
    assert layout_id("https://www.tradingview.com/chart/YKdpKoM0/") == "YKdpKoM0" and layout_id("https://www.tradingview.com/chart/") == ""


# --- reading ----------------------------------------------------------------------


def test_older_bars_are_asked_for_until_there_are_enough() -> None:
    tv, _, hidden, _ = desktop()
    bridge = tv.bridge()
    payload = bridge.fetch_bars(TICKER, "5", 1200)
    assert len(payload.rows) == 1200 and not payload.exhausted
    assert hidden.more_requests == [(series_key(TICKER, "5"), 920)]  # 300 came with the series
    assert bridge.report["series"]["deepen"]["requests"] == 1
    hidden.more_requests.clear()
    assert len(bridge.fetch_bars(TICKER, "5", 8).rows) == 8 and hidden.more_requests == []  # a refresh asks for nothing


def test_running_out_of_history_is_reported_not_waited_for() -> None:
    tv, _, hidden, _ = desktop()
    hidden.history["1M"] = five_minute_rows(330)
    payload = tv.bridge().fetch_bars(TICKER, "1M", 600)
    assert len(payload.rows) == 330 and payload.exhausted
    assert len(hidden.more_requests) == 3  # one that brought the rest, two that brought nothing


@pytest.mark.parametrize(
    ("error", "kind"),
    [
        ({"kind": "symbol", "text": "invalid symbol"}, "symbol_not_found"),
        ({"kind": "symbol", "text": "permission denied symbol CME_MINI:NQ1!"}, "no_permission"),
        ({"kind": "series", "text": "study_not_auth:BarSetRange@tv-basicstudies"}, "no_permission"),
        ({"kind": "series", "text": "unsupported resolution"}, "unexpected_bars"),
        ({"kind": "series", "text": "something else"}, "loading"),
        ({"kind": "critical", "text": "exceed limit of series in the session"}, "protocol"),
    ],
)
def test_tradingviews_refusals_are_told_apart(error: dict[str, str], kind: str) -> None:
    tv, _, hidden, _ = desktop()
    hidden.errors[TICKER] = error
    bridge = tv.bridge()
    with pytest.raises(TradingViewError) as caught:
        bridge.fetch_bars(TICKER, "5", 10)
    assert caught.value.kind == kind and error["text"] in caught.value.technical
    assert hidden.closed == [series_key(TICKER, "5")] and hidden.feed == {}  # the failed series is not left open
    hidden.errors.clear()
    assert len(bridge.fetch_bars(TICKER, "5", 10).rows) == 10  # and a corrected symbol works on the next try


def test_a_series_with_no_bars_reads_as_missing_market_data() -> None:
    tv, _, hidden, _ = desktop()
    hidden.history["5"] = []
    with pytest.raises(TradingViewError) as caught:
        tv.bridge().fetch_bars(TICKER, "5", 10)
    assert caught.value.kind == "no_permission" and TICKER in str(caught.value)


@pytest.mark.parametrize(("mode", "note"), [("streaming", ()), ("delayed_streaming_900", ("DELAYED data (15 min behind)",)), ("endofday", ("not streaming (endofday)",))])
def test_delayed_data_is_said(mode: str, note: tuple[str, ...]) -> None:
    tv, _, hidden, _ = desktop()
    hidden.mode = mode
    assert tv.bridge().fetch_bars(TICKER, "5", 10).notes == note


def test_only_so_many_series_stay_open_and_the_entry_one_is_never_the_one_closed() -> None:
    tv, _, hidden, _ = desktop()
    bridge = tv.bridge(max_series=3)
    bridge.fetch_bars(TICKER, "5", 10)
    bridge.park(TICKER, "5")
    for resolution in ("60", "1D", "240", "15"):
        bridge.fetch_bars(TICKER, resolution, 10)
    assert hidden.feed is not None and len(hidden.feed) == 3 and series_key(TICKER, "5") in hidden.feed
    assert hidden.closed == [series_key(TICKER, "60"), series_key(TICKER, "1D")]  # the least recently read went first
    assert all(hidden.opened.count(key) == 1 for key in hidden.opened)


# --- losing the host --------------------------------------------------------------


def test_closing_the_host_tab_moves_the_feed_to_another_tab() -> None:
    tv, visible, hidden, third = desktop()
    bridge = tv.bridge()
    bridge.fetch_bars(TICKER, "5", 10)
    tv.pages.remove(hidden)  # the trader closed that tab
    assert len(bridge.fetch_bars(TICKER, "5", 10).rows) == 10
    assert bridge.host_id == "THR" and visible.feed is None  # the other background tab, still not the one on screen


def test_a_dropped_data_connection_is_reinstalled_quietly() -> None:
    tv, _, hidden, _ = desktop()
    bridge = tv.bridge()
    bridge.fetch_bars(TICKER, "5", 10)
    hidden.dead = "disconnected"  # TradingView reconnected the page: the feed's sessions are gone
    assert len(bridge.fetch_bars(TICKER, "5", 10).rows) == 10
    assert bridge.report["reinstalled"] == 1 and hidden.opened == [series_key(TICKER, "5")] * 2


def test_a_reloaded_host_page_gets_the_feed_again() -> None:
    tv, _, hidden, _ = desktop()
    bridge = tv.bridge()
    bridge.fetch_bars(TICKER, "5", 10)
    hidden.feed = None  # the page was reloaded: the global is gone
    assert len(bridge.fetch_bars(TICKER, "5", 10).rows) == 10 and hidden.feed


def test_no_chart_tab_says_what_to_do() -> None:
    bridge = FakeDesktop(extra=OTHERS).bridge()
    with pytest.raises(TradingViewError) as caught:
        bridge.fetch_bars(TICKER, "5", 10)
    message = str(caught.value)
    assert caught.value.kind == "no_chart_tab" and caught.value.is_connection and caught.value.retry
    assert "Open any chart in TradingView" in message and "without changing it" in message
    assert "socket" not in message and "9222" not in message and 1 <= message.count(". ") + 1 <= 2


def test_charts_that_are_still_connecting_read_as_loading() -> None:
    page = FakePage("ONE", "https://www.tradingview.com/chart/abc/", connected=False)
    with pytest.raises(TradingViewError) as caught:
        FakeDesktop(page).bridge().fetch_bars(TICKER, "5", 10)
    assert caught.value.kind == "loading" and caught.value.retry and page.feed is None


@pytest.mark.parametrize(("running", "kind"), [(True, "no_debug_port"), (False, "not_running")])
def test_a_closed_port_is_told_from_a_missing_tradingview(running: bool, kind: str) -> None:
    tv, _, _, _ = desktop()
    bridge = tv.bridge(running=running)
    bridge.fetch_bars(TICKER, "5", 10)
    tv.port_open = False
    with pytest.raises(TradingViewError) as caught:
        bridge.fetch_bars(TICKER, "5", 10)
    assert caught.value.kind == kind


def test_closing_the_bridge_takes_the_feed_out_of_the_page() -> None:
    tv, _, hidden, _ = desktop()
    bridge = tv.bridge()
    bridge.fetch_bars(TICKER, "5", 10)
    bridge.close()
    assert hidden.feed is None and hidden.evaluated[-1] == pagefeed.JS_REMOVE
    bridge.close()  # twice is fine


# --- through the source -----------------------------------------------------------


def test_the_source_reads_through_the_real_bridge(tmp_path: Path) -> None:
    tv, _, hidden, _ = desktop()
    last_open = pd.Timestamp("2026-03-10 10:40", tz="America/New_York")
    hidden.history["5"] = five_minute_rows(4000, last=int(last_open.timestamp()))
    clock = last_open + pd.Timedelta(minutes=7, seconds=20)  # 10:47:20: the 10:45 bar is forming, 10:40 closed at 10:45
    hidden.history["5"].append([int(last_open.timestamp()) + 300, 1.0, 2.0, 0.5, 1.5, 3.0])
    source = TradingViewBarSource(tv.bridge(), symbols_path=write_symbols(tmp_path / "symbols.json"), clock=lambda: clock)
    update = source.refresh("NQ", "5m")
    assert update.last_open == last_open and update.ticker == TICKER
    bars = source.get_bars("NQ", "5m", clock, 600)
    assert len(bars) == 600 and bars.index[-1] == last_open  # the forming 10:45 bar is not in it
    assert source.description == "TradingView live — CME_MINI:NQ1! — last bar closed 10:45"


class _Daily:
    """A bridge whose newest daily bar TradingView says is still open (a holiday session runs into the next day)."""

    def __init__(self, rows: list[list[float]], until: float | None) -> None:
        self.rows, self.until = rows, until

    def fetch_bars(self, ticker: str, resolution: str, count: int) -> BarsPayload:
        return BarsPayload(rows=self.rows[-count:], ticker=ticker, forming_until=self.until)

    def park(self, ticker: str, resolution: str) -> None: ...

    def close(self) -> None: ...


def test_a_daily_bar_tradingview_still_holds_open_is_not_called_closed(tmp_path: Path) -> None:
    # Sunday 18 Jan 2026 18:00 opens the Martin Luther King Day session; TradingView's bar runs to Tuesday 17:00
    opens = [pd.Timestamp(day, tz="America/New_York") for day in ("2026-01-14 18:00", "2026-01-15 18:00", "2026-01-18 18:00")]
    rows = [[int(stamp.timestamp()), 100.0, 110.0, 90.0, 105.0, 1.0] for stamp in opens]
    monday_evening = pd.Timestamp("2026-01-19 19:00", tz="America/New_York")  # the calendar says Monday's bar closed an hour ago
    tuesday_close = pd.Timestamp("2026-01-20 18:00", tz="America/New_York").timestamp()
    path = write_symbols(tmp_path / "symbols.json")
    held = TradingViewBarSource(_Daily(rows, tuesday_close), symbols_path=path, clock=lambda: monday_evening).get_bars("NQ", "1D", monday_evening, 5)
    assert list(held.index) == opens[:2]
    naive = TradingViewBarSource(_Daily(rows, None), symbols_path=path, clock=lambda: monday_evening).get_bars("NQ", "1D", monday_evening, 5)
    assert list(naive.index) == opens  # without TradingView's word the calendar decides, as before
    later = pd.Timestamp("2026-01-20 18:00:10", tz="America/New_York")
    done = TradingViewBarSource(_Daily(rows, tuesday_close), symbols_path=path, clock=lambda: later).get_bars("NQ", "1D", later, 5)
    assert list(done.index) == opens


# --- weekly and monthly bars that start with a holiday session (seen on NQ) ---------


def _stamped(*opens: str) -> list[list[float]]:
    return [[int(pd.Timestamp(stamp, tz="America/New_York").timestamp()), 10.0 + i, 20.0 + i, 5.0 + i, 15.0 + i, 1.0] for i, stamp in enumerate(opens)]


def test_a_week_that_tradingview_opens_on_the_holiday_thursday_is_the_following_week() -> None:
    # real NQ1! weekly stamps around 4 July 2025: the bar for 7-11 July opens Thursday 3 July 18:00
    weekly = rows_to_frame(_stamped("2025-06-22 18:00", "2025-06-29 18:00", "2025-07-03 18:00", "2025-07-13 18:00"), "1W")
    assert [stamp.strftime("%Y-%m-%d %H:%M") for stamp in weekly.index] == ["2025-06-22 18:00", "2025-06-29 18:00", "2025-07-06 18:00", "2025-07-13 18:00"]
    assert weekly["open"].tolist() == [10.0, 11.0, 12.0, 13.0]  # TradingView's bars, untouched
    # a week whose first session opens Monday evening (Monday shut) stays in its own week
    late = rows_to_frame(_stamped("2024-03-24 18:00", "2024-04-01 18:00", "2024-04-07 18:00"), "1W")
    assert late.index[1] == pd.Timestamp("2024-03-31 18:00", tz="America/New_York")


def test_a_month_that_tradingview_opens_on_the_last_evening_of_the_month_before_is_the_next_month() -> None:
    # real NQ1! monthly stamps: June 2021 opens Sunday 30 May 18:00 (Memorial Day session)
    monthly = rows_to_frame(_stamped("2021-03-31 18:00", "2021-05-02 18:00", "2021-05-30 18:00", "2021-06-30 18:00", "2021-08-01 18:00"), "1M")
    assert [stamp.strftime("%Y-%m") for stamp in (monthly.index + pd.Timedelta(days=4))] == ["2021-04", "2021-05", "2021-06", "2021-07", "2021-08"]
    assert monthly["open"].tolist() == [10.0, 11.0, 12.0, 13.0, 14.0] and monthly.index.is_monotonic_increasing
