"""The live TradingView bar source, against a fake bridge. No TradingView, no network."""

from __future__ import annotations

import socket
from pathlib import Path

import pandas as pd
import pytest

from companion.bars import HistoricalBarSource, bar_close_times, resample
from companion.styles.ttrades.config import load_config
from companion.styles.ttrades.context import _frame_bars
from companion.timeframes import list_stacks, make_stack, parse_timeframe
from companion.tradingview import TradingViewBarSource, TradingViewError
from companion.tradingview.bridge import CdpBridge, layout_id
from companion.tradingview.errors import LAUNCHER
from companion.tradingview.mapping import resolution_for, rows_to_frame, same_resolution, same_ticker
from companion.tradingview.source import nests
from companion.tradingview.symbols import FeedSettings, list_symbols, settings, ticker_for
from tradingview_fakes import TICKER, FakeTradingView, epoch, market_minutes, stamp_daily, write_symbols

NOW = "2026-03-10 10:47:20"  # a Tuesday, two days after the clocks went forward


@pytest.fixture(scope="module")
def minutes() -> pd.DataFrame:
    return market_minutes()


def make_source(minutes: pd.DataFrame, tmp_path: Path, now: str = NOW, **fake: object) -> tuple[TradingViewBarSource, FakeTradingView]:
    settings_ = {key: fake.pop(key) for key in ("daily_and_above", "daily_stamp_shift_days") if key in fake}
    tv = FakeTradingView(minutes, now, **fake)  # type: ignore[arg-type]
    path = write_symbols(tmp_path / "symbols.json", **settings_)
    return TradingViewBarSource(tv, symbols_path=path, clock=tv.clock), tv


def history(minutes: pd.DataFrame, upto: pd.Timestamp) -> HistoricalBarSource:
    """What the saved-history mode would say with exactly the minutes closed by ``upto``."""
    return HistoricalBarSource(minute_bars={"NQ": minutes[minutes.index + pd.Timedelta(minutes=1) <= upto]})


def rows(frame: pd.DataFrame, stamps: object) -> list[list[float]]:
    return [[int(stamp), *map(float, values)] for stamp, values in zip(stamps, frame.to_numpy())]  # type: ignore[call-overload]


# --- timestamp mapping ------------------------------------------------------------


@pytest.mark.parametrize("label", ["1m", "5m", "15m", "1h", "4h"])
def test_intraday_stamps_are_new_york_opens_across_the_dst_change(minutes: pd.DataFrame, label: str) -> None:
    week = minutes["2026-03-05 18:00":"2026-03-10 17:00"]  # the clocks go forward on Sunday the 8th
    expected = resample(week, label)
    mapped = rows_to_frame(rows(expected, epoch(expected.index)), label)
    pd.testing.assert_frame_equal(mapped, expected)
    assert mapped.index.tz is not None and str(mapped.index.tz) == "America/New_York"
    friday_last, sunday_first = mapped[:"2026-03-07"].index[-1], mapped["2026-03-08":].index[0]
    assert sunday_first == pd.Timestamp("2026-03-08 18:00", tz="America/New_York")  # 22:00 UTC, not 23:00
    assert friday_last < pd.Timestamp("2026-03-06 17:00", tz="America/New_York") and friday_last.utcoffset() == pd.Timedelta(hours=-5)
    assert sunday_first.utcoffset() == pd.Timedelta(hours=-4)


def test_known_utc_seconds_map_to_the_expected_new_york_open() -> None:
    before = int(pd.Timestamp("2026-03-06 14:30", tz="UTC").timestamp())  # 09:30 EST
    after = int(pd.Timestamp("2026-03-09 13:30", tz="UTC").timestamp())  # 09:30 EDT
    for scale in (1, 1000):  # seconds, or milliseconds
        mapped = rows_to_frame([[before * scale, 1, 2, 0.5, 1.5, 10], [after * scale, 2, 3, 1, 2.5, None], None], "5m")
        assert [str(moment) for moment in mapped.index] == ["2026-03-06 09:30:00-05:00", "2026-03-09 09:30:00-04:00"]
        assert mapped["volume"].tolist() == [10.0, 0.0]
    assert rows_to_frame([], "5m").empty


@pytest.mark.parametrize("stamp", ["session_open", "utc_midnight", "exchange_midnight"])
@pytest.mark.parametrize("label", ["1D", "1W", "1M"])
def test_daily_and_above_land_on_the_companion_open_however_tradingview_stamps_them(minutes: pd.DataFrame, label: str, stamp: str) -> None:
    expected = resample(minutes, label)  # the companion's own daily / weekly / monthly bars
    mapped = rows_to_frame(rows(expected, stamp_daily(expected.index, stamp)), label)
    pd.testing.assert_frame_equal(mapped, expected)


def test_daily_opens_keep_the_18_00_wall_clock_through_the_dst_week(minutes: pd.DataFrame) -> None:
    expected = resample(minutes["2026-03-04 18:00":"2026-03-11 17:00"], "1D")
    mapped = rows_to_frame(rows(expected, stamp_daily(expected.index, "utc_midnight")), "1D")
    assert [moment.strftime("%a %m-%d %H:%M %z") for moment in mapped.index] == [
        "Wed 03-04 18:00 -0500", "Thu 03-05 18:00 -0500", "Sun 03-08 18:00 -0400", "Mon 03-09 18:00 -0400", "Tue 03-10 18:00 -0400",
    ]  # fmt: skip
    closes = bar_close_times(mapped, "1D")
    assert closes[1] == pd.Timestamp("2026-03-06 18:00", tz="America/New_York")


def test_a_daily_bar_stamped_outside_its_trading_day_is_refused_and_can_be_corrected(minutes: pd.DataFrame) -> None:
    expected = resample(minutes["2026-03-01 18:00":"2026-03-13 17:00"], "1D")
    early = rows(expected, stamp_daily(expected.index, "day_early"))
    with pytest.raises(TradingViewError) as caught:
        rows_to_frame(early, "1D")
    assert caught.value.kind == "unexpected_bars" and "daily_stamp_shift_days" in str(caught.value)
    pd.testing.assert_frame_equal(rows_to_frame(early, "1D", shift_days=1), expected)


def test_4h_bars_off_the_session_grid_are_refused_then_built_from_1h(minutes: pd.DataFrame, tmp_path: Path) -> None:
    source, tv = make_source(minutes, tmp_path, utc_anchored_4h=True)
    with pytest.raises(TradingViewError) as caught:
        rows_to_frame(tv.fetch_bars(TICKER, "240", 50).rows, "4h")
    assert caught.value.kind == "unexpected_bars" and "4h" in str(caught.value)

    bars = source.get_bars("NQ", "4h", tv.now, 40)
    pd.testing.assert_frame_equal(bars, history(minutes, tv.now).get_bars("NQ", "4h", tv.now, 40))
    assert {hour for hour in bars.index.hour} <= {18, 22, 2, 6, 10, 14}
    assert (TICKER, "60") in {(call[0], call[1]) for call in tv.calls}


def test_helpers_compare_tickers_and_resolutions() -> None:
    assert same_ticker("CME_MINI:NQ1!", "cme_mini:nq1!") and same_ticker("NQZ2026", "CME_MINI:NQZ2026")
    assert not same_ticker("CME_MINI:NQ1!", "CME_MINI:ES1!") and not same_ticker("NQ1!", "")
    assert same_resolution("D", "1D") and same_resolution("60", "60") and not same_resolution("1", "1D")
    assert [resolution_for(label) for label in ("1m", "1h", "4h", "1D", "1W", "1M")] == ["1", "60", "240", "1D", "1W", "1M"]
    assert layout_id("https://www.tradingview.com/chart/AbC123xy/?symbol=NQ") == "AbC123xy" and layout_id("https://www.tradingview.com/chart/") == ""


# --- closed bars only -------------------------------------------------------------


@pytest.mark.parametrize("stack", list_stacks(), ids=lambda stack: stack.name)
def test_bars_equal_the_saved_history_mode_and_never_include_a_forming_bar(minutes: pd.DataFrame, tmp_path: Path, stack) -> None:  # type: ignore[no-untyped-def]
    source, tv = make_source(minutes, tmp_path, daily_stamp="utc_midnight")
    reference = history(minutes, tv.now)
    for label in (stack.bias, stack.setup, stack.entry):
        live = source.get_bars("NQ", label, tv.now, 60)
        pd.testing.assert_frame_equal(live, reference.get_bars("NQ", label, tv.now, 60))
        assert bar_close_times(live, label)[-1] <= tv.now - pd.Timedelta(seconds=3)
        newest_native = tv.native(label).index[-1]
        assert newest_native > live.index[-1]  # TradingView had a forming bar; it was dropped


def test_a_bar_counts_as_closed_only_after_the_settle_time(minutes: pd.DataFrame, tmp_path: Path) -> None:
    source, tv = make_source(minutes, tmp_path, now="2026-03-10 10:45:01")
    assert source.refresh("NQ", "5m").last_close == pd.Timestamp("2026-03-10 10:40", tz="America/New_York")
    tv.advance(seconds=3)  # 10:45:04: three seconds after the close
    update = source.refresh("NQ", "5m")
    assert (update.last_open.strftime("%H:%M"), update.last_close.strftime("%H:%M"), update.new_bars) == ("10:40", "10:45", 1)


def test_a_clock_finer_than_the_bar_index_is_accepted(minutes: pd.DataFrame, tmp_path: Path) -> None:
    source, tv = make_source(minutes, tmp_path)
    tv.now = tv.now + pd.Timedelta(nanoseconds=123_456_789)
    assert source.refresh("NQ", "5m").last_close.strftime("%H:%M") == "10:45"
    assert len(source.get_bars("NQ", "1h", tv.now, 5)) == 5 and len(source.get_bars("NQ", "1D", tv.now, 5)) == 5


def test_an_earlier_as_of_returns_nothing_that_closed_later(minutes: pd.DataFrame, tmp_path: Path) -> None:
    source, tv = make_source(minutes, tmp_path)
    source.refresh("NQ", "5m")
    earlier = pd.Timestamp("2026-03-10 09:32", tz="America/New_York")
    reference = history(minutes, earlier)
    for label in ("1D", "1h", "5m"):
        bars = source.get_bars("NQ", label, earlier, 30)
        assert bar_close_times(bars, label)[-1] <= earlier
        pd.testing.assert_frame_equal(bars, reference.get_bars("NQ", label, earlier, 30))
    assert source.get_bars("NQ", "5m", "2026-03-10 09:32", 1).index[-1].strftime("%H:%M") == "09:25"  # naive = New York
    with pytest.raises(ValueError):
        source.get_bars("NQ", "5m", earlier, -1)


# --- depth ------------------------------------------------------------------------


def test_history_is_deepened_when_the_lookback_exceeds_what_is_loaded(minutes: pd.DataFrame, tmp_path: Path) -> None:
    source, tv = make_source(minutes, tmp_path)
    assert len(source.get_bars("NQ", "5m", tv.now, 100)) == 100 and tv.deepened == []
    bars = source.get_bars("NQ", "5m", tv.now, 874)  # what the style asks of the 5m frame on 1D / 1h / 5m
    assert len(bars) == 874 and tv.deepened and tv.deepened[-1][0] == "5" and tv.deepened[-1][1] >= 875
    pd.testing.assert_frame_equal(bars, history(minutes, tv.now).get_bars("NQ", "5m", tv.now, 874))

    asked = len(tv.calls)
    assert len(source.get_bars("NQ", "5m", tv.now, 800)) == 800 and len(tv.calls) == asked  # already held
    back = tv.now - pd.Timedelta(days=2)
    assert len(source.get_bars("NQ", "5m", back, 874)) == 874 and len(tv.calls) == asked + 1  # stepping back needs older bars


def test_every_configured_stack_gets_the_history_the_style_asks_for(minutes: pd.DataFrame, tmp_path: Path) -> None:
    cfg = load_config()
    reference = history(minutes, pd.Timestamp(NOW, tz="America/New_York"))
    deepest = 0
    for stack in list_stacks():
        source, tv = make_source(minutes, tmp_path)
        wanted = {
            stack.bias: cfg.bias_bars_needed(stack.bias) + 2,
            stack.setup: _frame_bars(cfg, stack.bias, stack.setup, cfg.setup_cover_bias_bars),
            stack.entry: _frame_bars(cfg, stack.bias, stack.entry, cfg.entry_cover_bias_bars),
        }
        deepest = max(deepest, *wanted.values())
        for label, lookback in wanted.items():
            bars = source.get_bars("NQ", label, tv.now, lookback)
            available = len(reference.get_bars("NQ", label, tv.now, 100_000))
            assert len(bars) == min(lookback, available), (stack.name, label)
            assert max(count for _ticker, resolution, count in tv.calls if resolution == resolution_for(label)) > min(lookback, available)
    assert deepest > 2000  # far deeper than the 500-bar cap of the MCP reader


def test_a_short_history_is_returned_as_it_is_without_asking_again_and_again(minutes: pd.DataFrame, tmp_path: Path) -> None:
    source, tv = make_source(minutes, tmp_path, history_limit=120)
    assert len(source.get_bars("NQ", "1h", tv.now, 500)) == 119  # 120 bars, less the forming one
    asked = len(tv.calls)
    assert len(source.get_bars("NQ", "1h", tv.now, 500)) == 119 and len(tv.calls) == asked


# --- refresh ----------------------------------------------------------------------


def assert_same_as_a_full_reload(source: TradingViewBarSource, tv: FakeTradingView, tmp_path: Path, labels: tuple[str, ...], depth: int = 60) -> None:
    fresh = TradingViewBarSource(FakeTradingView(tv.minutes, tv.now, daily_stamp=tv.daily_stamp), symbols_path=tmp_path / "symbols.json", clock=tv.clock)
    for label in labels:
        pd.testing.assert_frame_equal(source.get_bars("NQ", label, tv.now, depth), fresh.get_bars("NQ", label, tv.now, depth), obj=f"{label} at {tv.now}")


def test_refresh_appends_new_bars_and_keeps_higher_timeframes_equal_to_a_full_reload(minutes: pd.DataFrame, tmp_path: Path) -> None:
    source, tv = make_source(minutes, tmp_path, now="2026-03-10 15:52:10")
    first = source.refresh("NQ", "5m")
    for label in ("1D", "1h", "5m"):
        source.get_bars("NQ", label, tv.now, 100)
    assert first.last_close.strftime("%H:%M") == "15:50" and tv.parks[-1] == (TICKER, "5")

    switches = tv.switches
    for _ in range(12):  # an hour of 5m closes, inside the trading day
        tv.advance(minutes=5)
        calls = len(tv.calls)
        update = source.refresh("NQ", "5m")
        assert update.new_bars == 1 and update.last_close == tv.now.floor("5min")
        assert tv.calls[calls:] == [(TICKER, "5", tv.calls[-1][2])] and tv.calls[-1][2] <= 8  # one small read, nothing else
        assert_same_as_a_full_reload(source, tv, tmp_path, ("1D", "1h", "5m"))
    assert tv.switches == switches  # the chart never left the entry timeframe
    assert source.get_bars("NQ", "1h", tv.now, 1).index[-1].strftime("%H:%M") == "15:00"
    assert source.origin("NQ", "1h")["derived"] == 1  # the 15:00 hour was built from 5m bars, not read again

    tv.now = pd.Timestamp("2026-03-10 18:00:10", tz="America/New_York")  # the trading day has closed
    source.refresh("NQ", "5m")
    assert source.get_bars("NQ", "1D", tv.now, 1).index[-1] == pd.Timestamp("2026-03-09 18:00", tz="America/New_York")
    assert (TICKER, "1D") in {(c[0], c[1]) for c in tv.calls[-3:]} and tv.parks[-1] == (TICKER, "5")  # read natively, then parked back
    assert_same_as_a_full_reload(source, tv, tmp_path, ("1D", "1h", "5m"))

    tv.now = pd.Timestamp("2026-03-16 09:31:30", tz="America/New_York")  # six days later, across a weekend
    update = source.refresh("NQ", "5m")
    assert update.new_bars > 800 and update.last_close.strftime("%a %H:%M") == "Mon 09:30"
    assert_same_as_a_full_reload(source, tv, tmp_path, ("1D", "1h", "5m"))


def test_daily_bars_can_be_derived_instead_of_read_again(minutes: pd.DataFrame, tmp_path: Path) -> None:
    source, tv = make_source(minutes, tmp_path, now="2026-03-10 16:58:10", daily_and_above="derived")
    source.refresh("NQ", "5m")
    source.get_bars("NQ", "1D", tv.now, 30)
    asked = [call for call in tv.calls if call[1] == "1D"]
    tv.now = pd.Timestamp("2026-03-10 18:05:10", tz="America/New_York")
    source.refresh("NQ", "5m")
    assert [call for call in tv.calls if call[1] == "1D"] == asked and source.origin("NQ", "1D")["derived"] == 1
    assert_same_as_a_full_reload(source, tv, tmp_path, ("1D", "5m"), depth=30)


@pytest.mark.parametrize("stack", [make_stack("1W", "4h", "15m"), make_stack("4h", "15m", "1m"), make_stack("30m", "5m", "3m")], ids=lambda s: s.name)
def test_refresh_is_consistent_on_other_stacks(minutes: pd.DataFrame, tmp_path: Path, stack) -> None:  # type: ignore[no-untyped-def]
    source, tv = make_source(minutes, tmp_path, now="2026-03-13 13:40:30")  # a Friday: the week closes during the test
    labels = (stack.bias, stack.setup, stack.entry)
    source.refresh("NQ", stack.entry)
    for label in labels:
        source.get_bars("NQ", label, tv.now, 40)
    for jump in ("2026-03-13 14:01:10", "2026-03-13 16:59:40", "2026-03-13 17:00:10", "2026-03-15 18:20:10", "2026-03-16 02:03:10"):
        tv.now = pd.Timestamp(jump, tz="America/New_York")
        source.refresh("NQ", stack.entry)
        assert_same_as_a_full_reload(source, tv, tmp_path, labels, depth=40)
    assert nests(parse_timeframe("5m"), parse_timeframe("1h")) and not nests(parse_timeframe("3m"), parse_timeframe("5m"))
    assert nests(parse_timeframe("1D"), parse_timeframe("1M")) and not nests(parse_timeframe("1W"), parse_timeframe("1M"))


def test_description_names_the_ticker_and_the_last_bar(minutes: pd.DataFrame, tmp_path: Path) -> None:
    source, tv = make_source(minutes, tmp_path)
    assert source.description == "TradingView live — not connected yet" and not source.has_symbol("NQ")
    source.refresh("NQ", "5m")
    assert source.description == "TradingView live — CME_MINI:NQ1! — last bar closed 10:45"
    assert source.has_symbol("NQ") and source.last_closed("NQ", "5m") == pd.Timestamp("2026-03-10 10:45", tz="America/New_York")
    assert source.coverage("NQ", "1h") is None


# --- symbols ----------------------------------------------------------------------


def test_the_shipped_symbol_list_maps_the_three_futures() -> None:
    assert list_symbols() == ["NQ", "ES", "GC"]
    assert [ticker_for(symbol) for symbol in ("NQ", "es", "GC")] == ["CME_MINI:NQ1!", "CME_MINI:ES1!", "COMEX:GC1!"]
    assert settings() == FeedSettings(port=9222, settle_seconds=3.0, daily_stamp_shift_days=0, daily_and_above="native")


def test_a_dated_contract_or_a_new_symbol_is_a_json_edit(minutes: pd.DataFrame, tmp_path: Path) -> None:
    path = write_symbols(tmp_path / "symbols.json", {"NQ": {"ticker": "CME_MINI:NQZ2026"}, "CL": "NYMEX:CL1!"}, port=9333, settle_seconds="soon")
    assert list_symbols(path) == ["NQ", "CL"] and ticker_for("CL", path) == "NYMEX:CL1!"
    assert settings(path).port == 9333 and settings(path).settle_seconds == 3.0  # a wrong type falls back to the default
    tv = FakeTradingView(minutes, NOW, tickers=("CME_MINI:NQZ2026",))
    source = TradingViewBarSource(tv, symbols_path=path, clock=tv.clock)
    assert source.refresh("NQ", "5m").ticker == "CME_MINI:NQZ2026" and tv.calls[0][0] == "CME_MINI:NQZ2026"


def test_symbol_problems_are_explained(minutes: pd.DataFrame, tmp_path: Path) -> None:
    path = write_symbols(tmp_path / "symbols.json", {"NQ": {"ticker": TICKER}, "ZZ": {"ticker": "NOPE:ZZ1!"}, "BAD": {"name": "no ticker"}})
    tv = FakeTradingView(minutes, NOW)
    source = TradingViewBarSource(tv, symbols_path=path, clock=tv.clock)
    with pytest.raises(TradingViewError) as unknown:
        source.get_bars("CL", "5m", tv.now, 10)
    assert unknown.value.kind == "unknown_symbol" and "CL has no TradingView ticker" in str(unknown.value) and "symbols.json" in str(unknown.value)
    assert tv.calls == []  # nothing was asked of TradingView
    with pytest.raises(TradingViewError) as missing:
        source.refresh("ZZ", "5m")
    assert missing.value.kind == "symbol_not_found" and "NOPE:ZZ1!" in str(missing.value) and "symbols.json" in str(missing.value)
    with pytest.raises(TradingViewError, match="needs a 'ticker'"):
        ticker_for("BAD", path)
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    with pytest.raises(TradingViewError, match="not valid JSON"):
        list_symbols(broken)
    with pytest.raises(TradingViewError, match="is missing"):
        ticker_for("NQ", tmp_path / "absent.json")
    assert settings(broken) == FeedSettings()


# --- connection failures ----------------------------------------------------------


@pytest.mark.parametrize(
    ("kind", "detail", "says", "connection"),
    [
        ("not_running", "", ("TradingView Desktop is not running", LAUNCHER), True),
        ("no_debug_port", "", ("started without the live-data link", "answer Yes when it offers to restart TradingView", LAUNCHER), True),
        ("loading", "", ("still loading the chart", "try again"), False),
        ("symbol_not_found", "CME_MINI:NQX1!", ("does not know the symbol CME_MINI:NQX1!", "symbols.json"), False),
        ("no_permission", "COMEX:GC1!", ("not sending market data for COMEX:GC1!", "subscription"), False),
        ("no_chart_tab", "", ("no chart tab is open", "Open any chart in TradingView", "without changing it"), True),
        ("protocol", "", ("link to TradingView dropped", "reconnect"), True),
    ],
)
def test_each_failure_has_a_plain_message(minutes: pd.DataFrame, tmp_path: Path, kind: str, detail: str, says: tuple[str, ...], connection: bool) -> None:
    source, tv = make_source(minutes, tmp_path)
    tv.error = TradingViewError(kind, detail, technical="socket said no")
    with pytest.raises(TradingViewError) as caught:
        source.refresh("NQ", "5m")
    message = str(caught.value)
    assert caught.value.kind == kind and caught.value.is_connection == connection
    assert all(part in message for part in says)
    assert "socket" not in message and "CDP" not in message and "9222" not in message  # plain words only
    assert 1 <= message.count(". ") + 1 <= 2  # one or two sentences

    tv.error = None  # and it recovers on the next try
    assert source.refresh("NQ", "5m").new_bars > 0


def test_no_bars_at_all_reads_as_missing_market_data(minutes: pd.DataFrame, tmp_path: Path) -> None:
    source, tv = make_source(minutes, tmp_path, now="2026-01-04 17:00:00")  # before the first minute of the fake market
    with pytest.raises(TradingViewError) as caught:
        source.refresh("NQ", "5m")
    assert caught.value.kind == "no_permission" and TICKER in str(caught.value)


@pytest.mark.parametrize(("running", "kind"), [(True, "no_debug_port"), (False, "not_running")])
def test_the_real_bridge_tells_a_closed_port_from_a_missing_tradingview(tmp_path: Path, running: bool, kind: str) -> None:
    with socket.socket() as probe:  # a port nothing listens on
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    bridge = CdpBridge(FeedSettings(port=port), is_running=lambda: running)
    with pytest.raises(TradingViewError) as caught:
        bridge.fetch_bars(TICKER, "5", 10)
    assert caught.value.kind == kind
    assert bridge.host_id == ""  # nothing was installed anywhere
