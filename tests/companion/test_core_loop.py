"""The headless core's live loop, driven by hand: fake clock, fake TradingView, checks run inline.

``Core.step`` handles what is queued and runs one tick, so each test moves the fake clock
and steps, then looks at the messages the core sent.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from companion.app_model import DATA_LIVE, CompanionController
from companion.core.loop import Core, inline
from companion.core.wire import Command
from companion.timeframes import get_stack
from companion.tradingview import TradingViewBarSource, TradingViewError
from tradingview_fakes import FakeTradingView, market_minutes, write_symbols

DAILY = get_stack("1D / 1h / 5m")
NOW = "2026-03-10 10:47:20"  # Tuesday; the last closed 5m bar closed at 10:45
NY = "America/New_York"


@pytest.fixture(scope="module")
def minutes() -> pd.DataFrame:
    return market_minutes()


class Harness:
    """A live core over the fake market, and every message it sent."""

    def __init__(self, minutes: pd.DataFrame, tmp_path: Path, now: str = NOW, **settings: object) -> None:
        self.tv = FakeTradingView(minutes, now)
        source = TradingViewBarSource(self.tv, symbols_path=write_symbols(tmp_path / "symbols.json", **settings), clock=self.tv.clock)
        self.controller = CompanionController(
            state_path=tmp_path / "state" / "ui_state.json", live_source=source, default_data=DATA_LIVE, clock=self.tv.clock
        )
        self.controller.state.symbol, self.controller.state.stack, self.controller.state.style = "NQ", DAILY.name, "ttrades"
        self.messages: list[dict[str, Any]] = []
        self.replies: list[dict[str, Any]] = []
        self.core = Core(self.controller, run_check=inline, run_watch=inline, listener=self.messages.append, watch_ms=500)
        self.core.begin()
        self.core.step()  # the first check's result

    def at(self, clock: str) -> None:
        """Move the clock to ``clock`` on 2026-03-10 (New York) and step once."""
        self.tv.now = pd.Timestamp(f"2026-03-10 {clock}", tz=NY)
        self.core.step()

    def walk(self, start: str, end: str, every: str = "500ms") -> None:
        """Step the clock from ``start`` to ``end`` like the real loop would."""
        for moment in pd.date_range(f"2026-03-10 {start}", f"2026-03-10 {end}", freq=every, tz=NY):
            self.tv.now = moment
            self.core.step()

    def send(self, kind: str, **values: Any) -> None:
        self.core.submit(Command(kind, **values), self.replies.append)
        self.core.step()

    def of(self, kind: str) -> list[dict[str, Any]]:
        return [message for message in self.messages if message["type"] == kind]

    def verdicts(self) -> list[dict[str, Any]]:
        return [message for message in self.of("snapshot") if message["view"] is not None]

    def timings(self) -> list[dict[str, Any]]:
        path = self.core.timings_path
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []

    def clear(self) -> None:
        self.messages.clear()


def entry_reads(tv: FakeTradingView) -> int:
    """How many times the entry series was read (one per live check once everything is loaded)."""
    return sum(1 for call in tv.calls if call[1] == "5")


# --- the first check ----------------------------------------------------------------


def test_starting_live_checks_at_once_and_says_hello_first(minutes: pd.DataFrame, tmp_path: Path) -> None:
    h = Harness(minutes, tmp_path)
    kinds = [message["type"] for message in h.messages]
    assert kinds[:2] == ["hello", "state"]
    assert h.of("hello")[0]["options"]["stacks"][0] == DAILY.name and h.of("hello")[0]["state"]["live"] is True
    snapshot = h.verdicts()[-1]
    assert snapshot["view"]["headline"].startswith("NQ  ·  2026-03-10 10:45 New York")
    assert snapshot["timing"]["bar_closed_at"] == "2026-03-10T10:45:00-04:00"
    assert h.controller.live_time == pd.Timestamp("2026-03-10 10:45") and h.controller.due == pd.Timestamp("2026-03-10 10:50:03.5")
    assert [state["state"]["busy"] for state in h.of("state")][-2:] == [True, False]


# --- the watcher --------------------------------------------------------------------


def test_a_new_closed_bar_is_checked_once_as_soon_as_tradingview_opens_the_next(minutes: pd.DataFrame, tmp_path: Path) -> None:
    h = Harness(minutes, tmp_path)
    before = entry_reads(h.tv)
    h.walk("10:47:20.5", "10:49:59.5")
    assert entry_reads(h.tv) == before and len(h.verdicts()) == 1  # ticks only while the bar forms

    h.at("10:50:00.4")  # TradingView has opened the 10:50 bar: the 10:45 bar is final, well before 10:50:03.5
    assert entry_reads(h.tv) == before + 1
    latest = h.verdicts()[-1]
    assert latest["timing"]["bar_closed_at"] == "2026-03-10T10:50:00-04:00"
    assert latest["timing"]["lag_ms"] == 400 and latest["timing"]["detected_at"] == "2026-03-10T10:50:00.400000-04:00"
    assert h.controller.live_time == pd.Timestamp("2026-03-10 10:50")
    newest = [candle for candle in latest["view"]["charts"][2]["candles"] if not candle["forming"]][-1]
    assert newest["label"] == "10:45"  # the bar that just closed, and nothing after it

    h.walk("10:50:00.9", "10:54:59.9")  # through the old due time and the rest of the bar
    assert entry_reads(h.tv) == before + 1 and len(h.verdicts()) == 2  # exactly one check for that bar
    assert [line["trigger"] for line in h.timings()] == ["start", "watch"]


def test_ticks_carry_the_forming_entry_candle_and_never_start_a_check(minutes: pd.DataFrame, tmp_path: Path) -> None:
    h = Harness(minutes, tmp_path)
    h.clear()
    h.walk("10:47:21", "10:49:51", every="30s")
    ticks = h.of("tick")
    assert len(ticks) == 2 and not h.of("snapshot")  # the fake market changes once a minute: 10:48 and 10:49 opened
    candle = ticks[-1]["candle"]
    assert ticks[-1]["timeframe"] == "5m" and candle["forming"] is True and candle["label"] == "10:45"
    assert candle["time"] == "2026-03-10T10:45:00-04:00" and candle["t"] == int(pd.Timestamp("2026-03-10 10:45", tz="UTC").timestamp())
    seen = h.tv.visible()
    assert ticks[-1]["last"] == seen["close"].iloc[-1] and candle["high"] == seen.loc["2026-03-10 10:45":, "high"].max()

    h.at("10:49:51.6")  # nothing changed since the last look: no tick
    assert len(h.of("tick")) == 2


def test_a_watcher_that_cannot_read_leaves_the_scheduler_in_charge(minutes: pd.DataFrame, tmp_path: Path) -> None:
    h = Harness(minutes, tmp_path)
    h.tv.peek_fails = True
    h.clear()
    h.walk("10:49:59", "10:50:03")
    assert not h.verdicts() and not h.of("tick")
    h.at("10:50:03.6")  # the scheduled time: the 10:50 close plus the settle time
    assert len(h.verdicts()) == 1 and h.controller.live_time == pd.Timestamp("2026-03-10 10:50")
    assert h.timings()[-1]["trigger"] == "schedule" and h.timings()[-1]["lag_ms"] == 3600

    peeks = h.tv.peeks
    h.walk("10:50:04", "10:50:24")  # failing again and again: it backs off to one look every 5 s
    assert h.tv.peeks - peeks <= 5


def test_a_watcher_without_peek_support_changes_nothing(minutes: pd.DataFrame, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    h = Harness(minutes, tmp_path)
    monkeypatch.delattr(FakeTradingView, "peek")  # an older bridge
    h.walk("10:49:59", "10:50:04")
    assert len(h.verdicts()) == 2 and h.timings()[-1]["trigger"] == "schedule"


def test_with_close_on_next_bar_off_the_bar_waits_for_the_settle_time(minutes: pd.DataFrame, tmp_path: Path) -> None:
    h = Harness(minutes, tmp_path, close_on_next_bar=False)
    h.walk("10:50:00", "10:50:03")
    assert len(h.verdicts()) == 1 and h.of("tick")  # still ticks
    h.at("10:50:03.5")
    assert len(h.verdicts()) == 2 and h.timings()[-1]["trigger"] == "schedule"


def test_pause_stops_every_automatic_check_and_resume_catches_up(minutes: pd.DataFrame, tmp_path: Path) -> None:
    h = Harness(minutes, tmp_path)
    h.send("pause", paused=True)
    assert h.of("status")[-1]["status"]["state"] == "paused" and h.of("state")[-1]["state"]["auto_refresh"] is False
    reads = entry_reads(h.tv)
    h.walk("10:49:58", "10:56:00", every="1s")  # past two closes and both due times
    assert entry_reads(h.tv) == reads and len(h.verdicts()) == 1

    h.send("pause", paused=False)
    assert entry_reads(h.tv) == reads + 1 and h.controller.live_time == pd.Timestamp("2026-03-10 10:55")


def test_a_failed_refresh_keeps_the_last_verdict_marked_stale(minutes: pd.DataFrame, tmp_path: Path) -> None:
    h = Harness(minutes, tmp_path)
    good = h.verdicts()[-1]["view"]
    h.tv.error = TradingViewError("protocol")
    h.walk("10:49:59.5", "10:50:04")
    latest = h.of("snapshot")[-1]
    assert latest["view"] == good and "link to TradingView dropped" in latest["error"]
    assert latest["status"]["stale"] is True and latest["status"]["state"] == "offline" and latest["offer_history"] is True
    assert h.timings()[-1]["problem"] == "protocol" and h.timings()[-1]["ok"] is False


# --- commands -----------------------------------------------------------------------


def test_step_back_and_latest_move_between_bars(minutes: pd.DataFrame, tmp_path: Path) -> None:
    h = Harness(minutes, tmp_path)
    h.send("step", direction=-1)
    assert h.of("state")[-1]["state"]["follow"] is False and h.of("status")[-1]["status"]["state"] == "past"
    assert "10:40 New York" in h.verdicts()[-1]["view"]["headline"]
    h.clear()
    h.walk("10:49:59.5", "10:50:04")  # looking back: no watcher, no scheduled check
    assert not h.of("tick") and not h.verdicts()

    h.send("latest")
    assert h.of("state")[-1]["state"]["follow"] is True and "10:50 New York" in h.verdicts()[-1]["view"]["headline"]
    h.send("step", direction=1)
    assert "last closed bar" in h.replies[-1]["message"] and h.replies[-1]["type"] == "error"


def test_set_validates_and_reports_what_it_could_not_use(minutes: pd.DataFrame, tmp_path: Path) -> None:
    h = Harness(minutes, tmp_path)
    h.clear()
    h.send("set", values={"symbol": "ZZ", "style": "nope", "when": "2026-03-10 09:00"})
    message = h.replies[-1]["message"]
    assert "ZZ is not a symbol" in message and "“nope” is not a style" in message and "live mode the time is TradingView" in message
    assert not h.verdicts() and h.of("state")  # nothing changed, nothing checked, but the state is confirmed

    h.send("set", values={"stack": "4h / 15m / 1m"})  # live: a new stack is read at once
    assert h.controller.state.stack == "4h / 15m / 1m" and "4h / 15m / 1m" in h.verdicts()[-1]["view"]["headline"]


def test_a_side_is_picked_by_value_or_label_and_the_same_bar_is_read_again_for_it(minutes: pd.DataFrame, tmp_path: Path) -> None:
    h = Harness(minutes, tmp_path)
    hello = h.of("hello")[0]
    assert hello["options"]["sides"] == ["", "long", "short"] and hello["state"]["side"] == ""
    first = h.verdicts()[-1]["view"]
    h.clear()
    h.send("set", values={"side": "Short"})
    assert h.of("state")[-1]["state"]["side"] == "short" and h.controller.state.direction == "short"
    view = h.verdicts()[-1]["view"]
    assert view["requested"] == "short" and view["headline"] == first["headline"]  # the same bar, for the side now asked

    h.clear()
    h.send("set", values={"side": "sideways"})
    assert h.replies[-1]["type"] == "error" and "Side must be one of" in h.replies[-1]["message"]
    assert h.of("state")[-1]["state"]["side"] == "short" and not h.verdicts()  # nothing changed, nothing checked

    h.send("set", values={"side": "auto"})
    assert h.of("state")[-1]["state"]["side"] == "" and h.verdicts()[-1]["view"]["requested"] == ""


def test_a_failed_read_after_a_side_change_does_not_show_the_other_sides_verdict(minutes: pd.DataFrame, tmp_path: Path) -> None:
    h = Harness(minutes, tmp_path)
    h.tv.error = TradingViewError("protocol")
    h.clear()
    h.send("set", values={"side": "long"})
    latest = h.of("snapshot")[-1]
    assert latest["view"] is None and latest["error"]


def test_switching_to_history_drops_the_live_check_in_flight(minutes: pd.DataFrame, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("companion.tradingview.symbols.SYMBOLS_PATH", write_symbols(tmp_path / "mine.json", {"NQ": "CME_MINI:NQ1!"}))
    h = Harness(minutes, tmp_path)
    queued: list[Any] = []
    h.core._run_check = queued.append  # hold the next check's job instead of running it  # noqa: SLF001
    h.send("check")
    assert len(queued) == 1 and h.of("state")[-1]["state"]["busy"] is True
    h.clear()
    h.send("use_history")
    hello = h.of("hello")[-1]  # the symbol list changed with the data source: everyone gets the new options
    assert hello["options"]["symbols"] == ["NQ", "ES", "GC"] and h.of("state")[-1]["state"]["live"] is False
    assert h.of("snapshot")[-1]["view"] is None  # what was on screen belonged to the other mode
    queued.pop()()  # the live check finishes after the switch
    h.core.step()
    assert not h.verdicts() and h.of("state")[-1]["state"]["busy"] is False


def test_entering_saved_history_moves_a_live_now_to_the_end_of_the_data(tmp_path: Path) -> None:
    covered = (pd.Timestamp("2026-01-05 18:00"), pd.Timestamp("2026-03-04 19:00"))
    controller = CompanionController(state_path=tmp_path / "ui_state.json", coverage=lambda symbol: covered, default_data=DATA_LIVE)
    assert controller.state.when > "2026-03-04 19:00"  # live: "now", which the saved files never reach
    messages: list[dict[str, Any]] = []
    core = Core(controller, run_check=lambda job: None, run_watch=inline, listener=messages.append)
    core.begin()
    core.submit(Command("use_history"))
    core.step()
    assert controller.state.when == "2026-03-04 19:00" and messages[-1]["state"]["when"] == "2026-03-04 19:00"

    controller.state.when = "2026-06-01 10:00"  # a saved time the data does not cover, found at start
    Core(controller, run_check=lambda job: None, run_watch=inline).begin()
    assert controller.state.when == "2026-03-04 19:00"
