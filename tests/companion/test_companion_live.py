"""The window's live mode, tested on the controller alone: no display, no TradingView."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from companion.app_model import (
    DATA_HISTORY,
    DATA_LABELS,
    DATA_LIVE,
    LATE_SECONDS,
    RETRY_SECONDS,
    CheckOutcome,
    CompanionController,
    UiState,
    UserError,
    load_state,
)
from companion.bars import HISTORICAL_SOURCE_NOTE
from companion.timeframes import get_stack
from companion.tradingview import TradingViewBarSource, TradingViewError
from tradingview_fakes import FakeTradingView, market_minutes, write_symbols

DAILY = get_stack("1D / 1h / 5m")
NOW = "2026-03-10 10:47:20"  # Tuesday; the last closed 5m bar closed at 10:45


@pytest.fixture(scope="module")
def minutes() -> pd.DataFrame:
    return market_minutes()


def live_controller(minutes: pd.DataFrame, tmp_path: Path, now: str = NOW, **kwargs: object) -> tuple[CompanionController, FakeTradingView]:
    tv = FakeTradingView(minutes, now)
    source = TradingViewBarSource(tv, symbols_path=write_symbols(tmp_path / "symbols.json"), clock=tv.clock)
    controller = CompanionController(
        state_path=tmp_path / "state" / "ui_state.json", live_source=source, default_data=DATA_LIVE, clock=tv.clock, **kwargs  # type: ignore[arg-type]
    )
    controller.state.symbol, controller.state.stack, controller.state.style = "NQ", DAILY.name, "ttrades"
    return controller, tv


def check(controller: CompanionController) -> CheckOutcome:
    outcome = controller.run_check(controller.build_request())
    controller.accept(outcome)
    return outcome


def at(clock: str) -> pd.Timestamp:
    return pd.Timestamp(f"2026-03-10 {clock}")


# --- the Data choice --------------------------------------------------------------


def test_data_choice_defaults_to_saved_history_and_is_remembered(tmp_path: Path) -> None:
    path = tmp_path / "ui_state.json"
    controller = CompanionController(state_path=path, coverage=lambda symbol: None)
    assert controller.data_choices() == ["TradingView (live)", "Saved history"]
    assert (controller.state.data, controller.is_live, controller.data_label()) == (DATA_HISTORY, False, "Saved history")
    assert controller.source_note() == HISTORICAL_SOURCE_NOTE

    controller.set_data("TradingView (live)")  # the drop-down's label
    controller.state.auto_refresh = False
    assert controller.is_live and controller.save()
    assert (load_state(path).data, load_state(path).auto_refresh) == (DATA_LIVE, False)
    again = CompanionController(state_path=path, coverage=lambda symbol: None)
    assert again.is_live and again.data_label() == DATA_LABELS[DATA_LIVE] and not again.state.auto_refresh

    assert CompanionController(state_path=tmp_path / "new.json", default_data=DATA_LIVE).is_live  # what the real window starts with
    assert UiState().auto_refresh is True


def test_live_symbols_come_from_the_symbol_list(minutes: pd.DataFrame, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    controller, _tv = live_controller(minutes, tmp_path)
    monkeypatch.setattr("companion.tradingview.symbols.SYMBOLS_PATH", write_symbols(tmp_path / "mine.json", {"NQ": "CME_MINI:NQZ2026", "CL": "NYMEX:CL1!"}))
    assert controller.symbols() == ["NQ", "CL"]
    controller.set_data(DATA_HISTORY)
    assert controller.symbols() == ["NQ", "ES", "GC"]


# --- a live check -----------------------------------------------------------------


def test_live_check_analyses_the_last_closed_entry_bar(minutes: pd.DataFrame, tmp_path: Path) -> None:
    controller, tv = live_controller(minutes, tmp_path)
    assert controller.live_status(None).state == "connecting" and controller.will_load(controller.build_request())
    request = controller.build_request()
    assert request.live and request.follow

    outcome = controller.run_check(request)
    assert controller.live_time is None  # run_check changes nothing: it runs off the UI thread
    controller.accept(outcome)
    assert outcome.ok and outcome.data_time == at("10:45") and outcome.request.when == at("10:45")
    assert pd.Timestamp(outcome.verdict.as_of).strftime("%H:%M") == "10:45"
    assert controller.state.when == "2026-03-10 10:45" and controller.live_time == at("10:45")

    view = controller.present(outcome)
    assert view.source_note == "TradingView live — CME_MINI:NQ1! — last bar closed 10:45"
    assert [chart.timeframe for chart in view.charts] == ["1D", "1h", "5m"]
    newest = [candle for candle in view.charts[2].candles if not candle.forming][-1]
    assert newest.time == pd.Timestamp("2026-03-10 10:40", tz="America/New_York")  # nothing after the last closed bar
    assert view.notes == ()  # the saved-history data notes do not apply


def test_auto_refresh_is_due_when_the_next_entry_bar_has_closed(minutes: pd.DataFrame, tmp_path: Path) -> None:
    controller, tv = live_controller(minutes, tmp_path)
    assert not controller.should_refresh()  # nothing asked yet: the window starts the first check itself
    first = check(controller)
    assert controller.due == at("10:50:03.5")  # the 10:50 close plus the settle time
    status = controller.live_status(first)
    assert status.state == "live" and not status.stale
    assert status.text == "LIVE  ·  last bar closed 10:45  ·  next check 10:50:03 (in 2:44)"

    tv.advance(minutes=2)
    assert not controller.should_refresh()
    tv.now = pd.Timestamp("2026-03-10 10:50:04", tz="America/New_York")
    assert controller.should_refresh()
    calls = len(tv.calls)
    second = check(controller)
    assert second.data_time == at("10:50") and controller.due == at("10:55:03.5") and not controller.should_refresh()
    assert len(tv.calls) == calls + 1 and tv.calls[-1][1] == "5"  # one small read of the entry timeframe
    assert controller.state.when == "2026-03-10 10:50"


def test_a_bar_that_is_late_is_looked_for_again_soon_then_less_often(minutes: pd.DataFrame, tmp_path: Path) -> None:
    controller, tv = live_controller(minutes, tmp_path)
    check(controller)
    tv.minutes = minutes[minutes.index < pd.Timestamp("2026-03-10 10:45", tz="America/New_York")]  # TradingView stops sending bars
    waits = []
    for _ in range(len(LATE_SECONDS) + 2):
        tv.now = pd.Timestamp(controller.due, tz="America/New_York") + pd.Timedelta(seconds=1)
        if tv.now < pd.Timestamp("2026-03-10 10:50:04", tz="America/New_York"):
            tv.now = pd.Timestamp("2026-03-10 10:50:04", tz="America/New_York")
        outcome = check(controller)
        assert outcome.ok and outcome.data_time == at("10:45")
        waits.append((controller.due - controller.now()).total_seconds())
    assert waits == [3.0, 5.0, 10.0, 15.0, 30.0, 30.0, 30.0, 30.0][: len(waits)]


def test_the_weekend_does_not_poll(minutes: pd.DataFrame, tmp_path: Path) -> None:
    controller, tv = live_controller(minutes, tmp_path, now="2026-03-14 11:00:00")  # a Saturday
    outcome = check(controller)
    assert outcome.data_time == pd.Timestamp("2026-03-13 17:00")
    assert controller.due == pd.Timestamp("2026-03-15 18:05:03.5")  # the first 5m close of Sunday evening
    status = controller.live_status(outcome)
    assert status.state == "stale" and status.stale and "market closed" in status.text and "Fri 17:00" in status.text


# --- pause, stale, looking back ---------------------------------------------------


def test_pause_stops_the_automatic_check_but_not_a_manual_one(minutes: pd.DataFrame, tmp_path: Path) -> None:
    controller, tv = live_controller(minutes, tmp_path)
    first = check(controller)
    controller.set_auto_refresh(False)
    tv.now = pd.Timestamp("2026-03-10 10:56:00", tz="America/New_York")
    assert not controller.should_refresh()
    status = controller.live_status(first)
    assert status.state == "paused" and status.stale and status.text.startswith("PAUSED  ·  last bar closed 10:45")

    manual = check(controller)  # Check still works
    assert manual.data_time == at("10:55") and not controller.should_refresh()
    assert not controller.live_status(manual).stale

    controller.set_auto_refresh(True)
    assert controller.should_refresh()  # resuming catches up at once


def test_a_verdict_older_than_one_entry_bar_is_marked_stale(minutes: pd.DataFrame, tmp_path: Path) -> None:
    controller, tv = live_controller(minutes, tmp_path)
    outcome = check(controller)
    for clock, stale in (("10:49:59", False), ("10:50:20", False), ("10:50:25", True), ("11:30:00", True)):
        assert controller.is_stale(outcome, at(clock)) is stale, clock
    status = controller.live_status(outcome, at("10:58:00"))
    assert status.state == "stale" and status.stale and "last bar closed 10:45, 13 min ago (no newer bar from TradingView)" in status.text
    assert not controller.is_stale(None) and not controller.is_stale(CheckOutcome(outcome.request, error="x"))


def test_stepping_back_through_the_live_history_is_marked_not_now(minutes: pd.DataFrame, tmp_path: Path) -> None:
    controller, tv = live_controller(minutes, tmp_path)
    with pytest.raises(UserError, match="Press Check first"):
        controller.step(-1)
    check(controller)
    with pytest.raises(UserError, match="last closed bar"):
        controller.step(1)

    assert controller.step(-1) == "2026-03-10 10:40" and not controller.follow
    assert controller.step(-1) == "2026-03-10 10:35"
    request = controller.build_request()
    assert request.live and not request.follow and request.when == at("10:35")
    calls = len(tv.calls)
    tv.now = pd.Timestamp("2026-03-10 10:52:00", tz="America/New_York")
    earlier = check(controller)
    assert len(tv.calls) == calls  # looking back reads nothing new from TradingView
    assert earlier.ok and pd.Timestamp(earlier.verdict.as_of).strftime("%H:%M") == "10:35" and earlier.request.when == at("10:35")
    closed = [candle for chart in earlier.charts for candle in chart.candles if not candle.forming and chart.role == "entry"]
    assert closed[-1].time == pd.Timestamp("2026-03-10 10:30", tz="America/New_York")  # no bar after the one looked at
    status = controller.live_status(earlier)
    assert status.state == "past" and status.text.startswith("NOT NOW  ·  looking back at 10:35")
    assert not controller.should_refresh() and not controller.is_stale(earlier)  # it waits while you look back

    assert controller.step(1) == "2026-03-10 10:40" and not controller.follow
    assert controller.step(1) == "2026-03-10 10:45" and controller.follow  # back on the last bar: live again
    controller.step(-1)
    assert controller.jump_to_latest() == "2026-03-10 10:45" and controller.follow
    assert check(controller).data_time == at("10:50")

    for _ in range(5000):  # the loaded history has a start
        try:
            controller.step(-1)
        except UserError as error:
            assert "start of the bars loaded from TradingView" in str(error)
            break
    else:
        pytest.fail("stepping back never reached the start of the loaded bars")


# --- when TradingView cannot be read ----------------------------------------------


@pytest.mark.parametrize("kind", ["not_running", "no_debug_port"])
def test_a_missing_connection_says_what_to_do_offers_history_and_retries_quietly(minutes: pd.DataFrame, tmp_path: Path, kind: str) -> None:
    controller, tv = live_controller(minutes, tmp_path)
    tv.error = TradingViewError(kind)
    waits = []
    for _ in range(6):
        outcome = check(controller)
        assert not outcome.ok and outcome.problem == kind and outcome.offer_history and outcome.retry
        assert outcome.error == str(tv.error) and "Start-TradingView-Live.cmd" in outcome.error
        waits.append((controller.due - controller.now()).total_seconds())
        tv.advance(seconds=waits[-1] + 1)
        assert controller.should_refresh()
    assert waits == [*RETRY_SECONDS, RETRY_SECONDS[-1], RETRY_SECONDS[-1]]
    status = controller.live_status(None)
    assert status.state == "offline" and status.stale and status.text.startswith("NOT CONNECTED  ·  trying again in")

    tv.error = None  # TradingView comes up: the next automatic check just works
    recovered = check(controller)
    assert recovered.ok and controller.live_status(recovered).state in ("live", "stale")
    assert controller.due is not None


def test_falling_back_to_saved_history(minutes: pd.DataFrame, tmp_path: Path) -> None:
    saved = object()
    controller, tv = live_controller(minutes, tmp_path, source=saved, coverage=lambda symbol: None)
    tv.error = TradingViewError("not_running")
    assert check(controller).offer_history
    controller.set_data(DATA_HISTORY)
    assert not controller.is_live and controller.source is saved and controller.due is None
    assert not controller.should_refresh() and controller.live_status(None).state == "history"
    request = controller.build_request()
    assert not request.live and not request.follow


def test_a_wrong_symbol_is_explained_and_not_retried(minutes: pd.DataFrame, tmp_path: Path) -> None:
    controller, tv = live_controller(minutes, tmp_path)
    tv.error = TradingViewError("symbol_not_found", "CME_MINI:NQ1!")
    outcome = check(controller)
    assert outcome.problem == "symbol_not_found" and not outcome.offer_history and not outcome.retry
    assert "symbols.json" in outcome.error and controller.due is None and not controller.should_refresh()

    tv.error = TradingViewError("loading")
    loading = check(controller)
    assert loading.retry and not loading.offer_history and controller.due is not None


def test_a_failed_refresh_leaves_the_earlier_verdict_stale_not_current(minutes: pd.DataFrame, tmp_path: Path) -> None:
    controller, tv = live_controller(minutes, tmp_path)
    good = check(controller)
    tv.now = pd.Timestamp("2026-03-10 10:50:05", tz="America/New_York")
    tv.error = TradingViewError("protocol")
    failed = check(controller)
    assert not failed.ok and failed.retry
    status = controller.live_status(good)  # the window keeps drawing ``good``
    assert status.state == "offline" and status.stale
    assert controller.live_time == at("10:45")  # still the old bar


def test_an_unexpected_bridge_fault_becomes_a_sentence(minutes: pd.DataFrame, tmp_path: Path) -> None:
    controller, tv = live_controller(minutes, tmp_path)
    tv.error = RuntimeError("socket exploded")
    outcome = controller.run_check(controller.build_request())
    assert not outcome.ok and outcome.error.startswith("Something went wrong while checking NQ (RuntimeError: socket exploded).")
    controller.accept(outcome)
    assert controller.due is None  # an unknown fault is not hammered


def test_changing_the_selection_starts_again_from_now(minutes: pd.DataFrame, tmp_path: Path) -> None:
    controller, tv = live_controller(minutes, tmp_path)
    check(controller)
    controller.step(-1)
    controller.state.stack = "1h / 5m / 1m"
    controller.selection_changed()
    assert controller.follow and controller.live_time is None
    outcome = check(controller)
    assert outcome.ok and outcome.data_time == at("10:47") and controller.due == at("10:48:03.5")
    controller.shutdown()
    assert tv.closed
