"""What the headless core asks of the live feed: the cheap peek, and closing a bar on TradingView's next one.

No TradingView: ``FakeTradingView`` behind the source, ``FakePage`` behind the real bridge.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from companion.bars import HistoricalBarSource
from companion.tradingview import TradingViewBarSource, cdp
from test_tradingview_bridge import OTHERS, FakeDesktop, FakePage, five_minute_rows
from tradingview_fakes import TICKER, FakeTradingView, market_minutes, write_symbols

NY = "America/New_York"


@pytest.fixture(scope="module")
def minutes() -> pd.DataFrame:
    return market_minutes()


def ny(clock: str) -> pd.Timestamp:
    return pd.Timestamp(f"2026-03-10 {clock}", tz=NY)


def make_source(minutes: pd.DataFrame, tmp_path: Path, now: str) -> tuple[TradingViewBarSource, FakeTradingView]:
    tv = FakeTradingView(minutes, ny(now))
    return TradingViewBarSource(tv, symbols_path=write_symbols(tmp_path / "symbols.json"), clock=tv.clock), tv


def history(minutes: pd.DataFrame, upto: pd.Timestamp) -> HistoricalBarSource:
    return HistoricalBarSource(minute_bars={"NQ": minutes[minutes.index + pd.Timedelta(minutes=1) <= upto]})


# --- closing a bar on the next one --------------------------------------------------


def test_a_bar_tradingview_has_followed_is_closed_before_the_settle_time_when_asked(minutes: pd.DataFrame, tmp_path: Path) -> None:
    source, tv = make_source(minutes, tmp_path, "10:44:30")
    source.refresh("NQ", "5m")
    source.get_bars("NQ", "15m", tv.now, 20)  # the setup timeframe is loaded, as after a first check
    tv.now = ny("10:45:00.5")  # the 10:45 bar has opened; the settle time has not passed

    assert source.refresh("NQ", "5m").last_close == ny("10:40")  # the window's way: wait for the settle time
    update = source.refresh("NQ", "5m", close_on_next_bar=True)
    assert update.last_close == ny("10:45") and update.new_bars == 1

    # the 15m bar closing at 10:45 is built from the closed 5m bars and equals the saved-history mode
    reference = history(minutes, ny("10:45"))
    for label in ("5m", "15m", "1h"):
        pd.testing.assert_frame_equal(source.get_bars("NQ", label, ny("10:45"), 20), reference.get_bars("NQ", label, ny("10:45"), 20))
    assert source.get_bars("NQ", "5m", tv.now, 1).index[-1] == ny("10:40")  # the forming 10:45 bar is never kept


def test_a_bar_sent_again_with_other_prices_is_counted_as_revised(minutes: pd.DataFrame, tmp_path: Path) -> None:
    market = minutes.copy()
    source, tv = make_source(market, tmp_path, "10:45:00.5")
    source.refresh("NQ", "5m", close_on_next_bar=True)
    assert source.refresh("NQ", "5m", close_on_next_bar=True).revised == 0

    market.loc[ny("10:44"), "close"] += 0.25  # a late print TradingView folds into the bar it already sent
    tv.now = ny("10:45:01")
    update = source.refresh("NQ", "5m", close_on_next_bar=True)
    assert update.revised == 1
    assert source.get_bars("NQ", "5m", tv.now, 1)["close"].iloc[-1] == market.loc[ny("10:44"), "close"]  # the new value wins


# --- the source's peek --------------------------------------------------------------


def test_peek_reads_the_forming_bar_without_touching_the_store(minutes: pd.DataFrame, tmp_path: Path) -> None:
    source, tv = make_source(minutes, tmp_path, "10:47:20")
    seen = source.peek("NQ", "5m")
    assert seen is not None and list(seen.bars.index) == [ny("10:40"), ny("10:45")]
    assert seen.followed_close == ny("10:45")
    assert seen.newest["close"] == tv.visible()["close"].iloc[-1]
    assert tv.calls == [] and source.coverage("NQ", "5m") is None  # nothing was read into the store

    tv.peek_fails = True
    assert source.peek("NQ", "5m") is None
    assert source.peek("CL", "5m") is None  # a symbol with no ticker: no answer, no exception


def test_peek_without_a_link_or_without_bridge_support_is_none(minutes: pd.DataFrame, tmp_path: Path) -> None:
    unlinked = TradingViewBarSource(symbols_path=write_symbols(tmp_path / "symbols.json"))
    assert unlinked.peek("NQ", "5m") is None  # never connects by itself

    class OldBridge:
        def fetch_bars(self, ticker: str, resolution: str, count: int) -> Any: ...
        def park(self, ticker: str, resolution: str) -> None: ...
        def close(self) -> None: ...

    assert TradingViewBarSource(OldBridge(), symbols_path=tmp_path / "symbols.json").peek("NQ", "5m") is None


# --- the page script's peek ---------------------------------------------------------

_PAGE_STUB = r"""
var sessions = {}, handlers = {};
var link = {
  connected: function () { return true; }, serverTime: function () { return 1794000000; },
  createSession: function (sid, s) { sessions[sid] = s; }, removeSession: function () {},
  chartCreateSession: function () {}, chartDeleteSession: function () {},
  resolveSymbol: function (sid, symId, symbol, h) { handlers[sid] = h; },
  createSeries: function () {}, requestMoreData: function () {}
};
globalThis.window = {TradingViewApi: {_activeChartWidgetWV: {value: function () {
  return {_chartWidget: {model: function () { return {model: function () { return {chartApi: function () { return {_chartApi: link}; }}; }}; }}};
}}}};
"""


@pytest.mark.skipif(__import__("shutil").which("node") is None, reason="node is not installed")
def test_the_page_feed_peek_returns_the_newest_two_bars_of_a_series() -> None:
    import json
    import subprocess

    from companion.tradingview import pagefeed

    key = f"{TICKER}|5"
    script = _PAGE_STUB + f"""
var installed = {pagefeed.JS_INSTALL.strip()};
var F = window.__companionFeed;
var before = {pagefeed.call("peek", key)};
F.open({json.dumps(key)}, "=x", "5", 300);
var sid = Object.keys(sessions)[0];
sessions[sid].onMessage({{method: 'connected'}});
var h = handlers[sid];
h({{method: 'symbol_resolved', params: ['sds_sym_1', {{name: 'NQ1!'}}]}});
// bars arrive out of order, as history and live updates can
h({{method: 'data_update', params: {{plots: [{{value: [300, 1, 2, 0, 1.5, 9]}}, {{value: [900, 3, 4, 2, 3.5, 9]}}, {{value: [600, 2, 3, 1, 2.5, 9]}}]}}}});
h({{method: 'series_completed', params: ['', 'streaming']}});
var first = {pagefeed.call("peek", key)};
h({{method: 'data_update', params: {{plots: [{{value: [900, 3, 4.5, 2, 4.25, 12]}}]}}}});
var updated = {pagefeed.call("peek", key)};
console.log(JSON.stringify({{installed: installed, before: before, first: first, updated: updated}}));
"""
    done = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
    assert done.returncode == 0, done.stderr
    out = json.loads(done.stdout)
    assert out["installed"]["ok"] is True and out["before"]["state"] == "none"
    assert out["first"]["state"] == "ready" and out["first"]["rows"] == [[600, 2, 3, 1, 2.5, 9], [900, 3, 4, 2, 3.5, 9]]
    assert out["updated"]["rows"][-1] == [900, 3, 4.5, 2, 4.25, 12]  # the forming bar's live update


# --- the bridge's peek --------------------------------------------------------------


class PeekPage(FakePage):
    """A page whose feed also answers ``peek`` as ``pagefeed`` does: the newest two rows of an open series."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.peek_raises = False

    def _peek(self, key: str) -> dict[str, Any]:
        if self.peek_raises:
            raise cdp.CdpError("page script failed: TypeError")
        assert self.feed is not None
        series = self.feed.get(key)
        if series is None:
            return {"ok": True, "dead": False, "state": "none"}
        return {"ok": True, "dead": False, "state": series["state"], "rows": series["rows"][-2:] if series["state"] == "ready" else []}


def peek_desktop() -> tuple[FakeDesktop, PeekPage]:
    page = PeekPage("HID", "https://www.tradingview.com/chart/gGIo8QCZ/")
    return FakeDesktop(page, extra=OTHERS), page


def test_the_bridge_peeks_only_at_a_series_that_is_already_open() -> None:
    desktop, page = peek_desktop()
    bridge = desktop.bridge()
    assert bridge.peek(TICKER, "5") is None and desktop.sockets == []  # no link yet: it does not connect
    bridge.fetch_bars(TICKER, "5", 50)
    answer = bridge.peek(TICKER, "5")
    assert answer is not None and answer["rows"] == five_minute_rows(4000)[-2:]
    assert bridge.peek(TICKER, "15") is None  # a series nobody opened is not opened by a peek
    assert page.opened == [f"{TICKER}|5"]


def test_the_bridge_peek_never_waits_for_a_read_and_survives_a_failing_page() -> None:
    desktop, page = peek_desktop()
    bridge = desktop.bridge()
    bridge.fetch_bars(TICKER, "5", 50)

    held, release = threading.Event(), threading.Event()

    def long_read() -> None:
        with bridge._lock:  # noqa: SLF001 - a check holding the link
            held.set()
            release.wait(5)

    reader = threading.Thread(target=long_read)
    reader.start()
    held.wait(5)
    try:
        assert bridge.peek(TICKER, "5") is None
    finally:
        release.set()
        reader.join()

    page.peek_raises = True
    assert bridge.peek(TICKER, "5") is None
    page.peek_raises = False
    assert bridge.peek(TICKER, "5") is not None  # the link was kept

    page.dead = "reloaded"
    assert bridge.peek(TICKER, "5") is None
