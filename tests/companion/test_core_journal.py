"""The decision journal: one record per trigger, the trader's call, outcomes, stats, and the wire."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from companion import engine
from companion.app_model import DATA_LIVE, CompanionController
from companion.core import wire
from companion.core.alerts import plan_key
from companion.core.journal import JOURNAL_FILE, MIN_N, Journal, JournalError, blocked_reasons
from companion.core.loop import Core, inline
from companion.timeframes import get_stack
from companion.tradingview import TradingViewBarSource
from companion.types import CriterionResult, PositionPlan, TimeframeStack, Verdict
from tradingview_fakes import FakeTradingView, market_minutes, write_symbols

NY = ZoneInfo("America/New_York")
STACK = TimeframeStack("1D / 1h / 5m", "1D", "1h", "5m")
NOW = pd.Timestamp("2026-11-12 09:46")


def verdict(decision: str = "short", stack: TimeframeStack = STACK, minute: int = 40, **plan_changes: Any) -> Verdict:
    plan = PositionPlan(
        direction="short",
        state="triggered",
        entry=25410.0,
        stop=25436.0,
        target=25358.0,
        r_multiple=2.0,
        timeframe="5m",
        since=datetime(2026, 11, 12, 9, minute, tzinfo=NY),
        stage_label="actionable",
        age_bars=1,
    )
    plan = replace(plan, **plan_changes)
    return Verdict(
        style="ttrades",
        symbol="NQ",
        as_of=datetime(2026, 11, 12, 9, 45, tzinfo=NY),
        stack=stack,
        decision=decision,  # type: ignore[arg-type]
        bias="bearish",
        path_family="continuation",
        stage="c4",
        criteria=(),
        plan=plan,
    )


def lines(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


# --- what is logged -------------------------------------------------------------------


def test_each_trigger_is_logged_once_with_what_was_shown(tmp_path: Path) -> None:
    journal = Journal(tmp_path / JOURNAL_FILE)
    record = journal.observe(verdict(), follow=True, now=NOW)
    journal.observe(verdict(age_bars=2, stage_label="late"), follow=True, now=NOW + pd.Timedelta(minutes=5))  # the next check
    assert record is not None and record["key"] == plan_key(verdict())
    saved = lines(tmp_path / JOURNAL_FILE)
    assert len(saved) == 1
    first = saved[0]
    assert (first["symbol"], first["stack"], first["style"], first["side"]) == ("NQ", "1D / 1h / 5m", "ttrades", "short")
    assert first["since"] == "2026-11-12T09:40:00-05:00" and first["as_of"] == "2026-11-12T09:45:00-05:00"
    assert (first["decision"], first["stage_label"]) == ("short", "actionable")  # the first sight, not the later one
    assert (first["entry"], first["stop"], first["target"], first["r_multiple"]) == (25410.0, 25436.0, 25358.0, 2.0)
    assert (first["mark"], first["outcome"], first["result_r"], first["blocked"]) == ("", "open", None, [])

    journal.observe(verdict(minute=55), follow=True, now=NOW)  # another trigger bar: another record
    assert len(lines(tmp_path / JOURNAL_FILE)) == 2


def test_a_watch_held_back_by_quality_checks_is_logged_with_why() -> None:
    criteria = (
        CriterionResult("cont_reward_at_least_2r", "Reward at least 2R", False, "", group="continuation c4", role="quality"),
        CriterionResult("rev_reward_at_least_2r", "Reward at least 2R", False, "", group="reversal c4", role="quality"),
        CriterionResult("cont_fvg", "FVG", True, "", group="continuation c3", role="quality"),
        CriterionResult("bias", "Bias", False, "", group="continuation c1", role="gate"),
    )
    held = replace(verdict("watch"), criteria=criteria)
    assert blocked_reasons(held) == ["cont_reward_at_least_2r"]  # the path in play, quality checks that failed
    record = Journal().observe(held, follow=True)
    assert record is not None and record["decision"] == "watch" and record["blocked"] == ["cont_reward_at_least_2r"]
    played = verdict("watch", outcome="stopped", stage_label="played_out")
    assert blocked_reasons(played) == ["played_out"]


@pytest.mark.parametrize(
    "seen",
    [
        verdict("no_trade"),
        verdict(state="planned"),
        replace(verdict(), plan=None),
        None,
    ],
    ids=["no-trade", "planned", "no-plan", "no-verdict"],
)
def test_nothing_is_logged_without_a_triggered_plan_on_a_trade_or_watch(seen: Verdict | None, tmp_path: Path) -> None:
    journal = Journal(tmp_path / JOURNAL_FILE)
    assert journal.observe(seen, follow=True) is None
    assert journal.records() == [] and not (tmp_path / JOURNAL_FILE).exists()


def test_looking_back_at_history_neither_logs_nor_fills(tmp_path: Path) -> None:
    journal = Journal(tmp_path / JOURNAL_FILE)
    assert journal.observe(verdict(), follow=False) is None
    assert journal.records() == []
    journal.observe(verdict(), follow=True)
    journal.observe(verdict(outcome="stopped"), follow=False)
    assert journal.records()[0]["outcome"] == "open"


# --- outcomes -------------------------------------------------------------------------


def test_outcomes_are_filled_from_later_checks_of_the_same_trigger() -> None:
    journal = Journal()
    journal.observe(verdict(), follow=True)
    journal.observe(verdict(minute=55), follow=True)
    journal.observe(verdict(minute=30), follow=True)
    assert all(r["outcome"] == "open" for r in journal.records())
    # the target reached: whatever the later decision, the plan's R
    journal.observe(verdict("watch", outcome="target_reached", r_multiple=2.5, stage_label="played_out"), follow=True)
    # stopped: -1R, even on a no_trade verdict (which never starts a record)
    journal.observe(verdict("no_trade", minute=55, outcome="stopped"), follow=True)
    by_since = {r["since"][11:16]: r for r in journal.records()}
    assert (by_since["09:40"]["outcome"], by_since["09:40"]["result_r"]) == ("target_reached", 2.5)
    assert (by_since["09:55"]["outcome"], by_since["09:55"]["result_r"]) == ("stopped", -1.0)
    assert (by_since["09:30"]["outcome"], by_since["09:30"]["result_r"]) == ("open", None)  # never seen again: stays open
    journal.observe(verdict(outcome="stopped"), follow=True)  # a closed outcome is not rewritten
    assert {r["since"][11:16]: r["result_r"] for r in journal.records()}["09:40"] == 2.5


def test_a_trigger_first_seen_after_it_played_out_is_logged_closed() -> None:
    record = Journal().observe(verdict("watch", outcome="stopped", stage_label="played_out"), follow=True)
    assert record is not None and (record["outcome"], record["result_r"], record["blocked"]) == ("stopped", -1.0, ["played_out"])


# --- the trader's call ----------------------------------------------------------------


def test_took_and_skipped_are_kept_and_changing_ones_mind_overwrites(tmp_path: Path) -> None:
    journal = Journal(tmp_path / JOURNAL_FILE)
    key = journal.observe(verdict(), follow=True)["key"]  # type: ignore[index]
    journal.mark(key, "skipped", "late", " chased it ", now=NOW)
    record = lines(tmp_path / JOURNAL_FILE)[0]
    assert (record["mark"], record["reason"], record["note"], record["marked_at"]) == ("skipped", "late", "chased it", "2026-11-12T09:46:00-05:00")
    journal.mark(key, "took", now=NOW)
    record = lines(tmp_path / JOURNAL_FILE)[0]
    assert (record["mark"], record["reason"], record["note"]) == ("took", "", "")
    journal.mark(key, "", "news")  # cleared
    assert (journal.get(key)["mark"], journal.get(key)["reason"]) == ("", "")  # type: ignore[index]
    assert len(lines(tmp_path / JOURNAL_FILE)) == 1


@pytest.mark.parametrize(
    ("key", "mark", "reason", "says"),
    [("nope", "took", "", "not in the journal"), (None, "maybe", "", "mark must be"), (None, "skipped", "bored", "reason must be")],
)
def test_a_mark_that_cannot_apply_is_refused(key: str | None, mark: str, reason: str, says: str) -> None:
    journal = Journal()
    known = journal.observe(verdict(), follow=True)["key"]  # type: ignore[index]
    with pytest.raises(JournalError, match=says):
        journal.mark(key or known, mark, reason)


# --- stats ------------------------------------------------------------------------------


def test_stats_count_closed_outcomes_per_stack_taken_skipped_and_all() -> None:
    journal = Journal()
    other = TimeframeStack("1D / 4h / 15m", "1D", "4h", "15m")
    plays = [(30, "took", "target_reached"), (35, "took", "stopped"), (40, "skipped", "target_reached"), (45, "", "stopped"), (50, "took", "open")]
    for minute, mark, outcome in plays:
        record = journal.observe(verdict(minute=minute), follow=True)
        if mark:
            journal.mark(record["key"], mark)  # type: ignore[index]
        if outcome != "open":
            journal.observe(verdict(minute=minute, outcome=outcome), follow=True)
    journal.observe(verdict(stack=other, outcome="target_reached"), follow=True)  # another stack: not counted here

    stats = journal.stats("1D / 1h / 5m")
    assert stats["taken"] == {"n": 2, "avg_r": 0.5}  # +2 and -1; the open one does not count
    assert stats["skipped"] == {"n": 1, "avg_r": 2.0}
    assert stats["all"] == {"n": 4, "avg_r": 0.5}  # +2 -1 +2 -1, the engine's baseline
    assert (stats["open"], stats["min_n"]) == (1, MIN_N)
    assert journal.stats("1D / 4h / 15m")["all"] == {"n": 1, "avg_r": 2.0}
    assert journal.stats("1W / 4h / 15m")["taken"] == {"n": 0, "avg_r": None}


# --- the file ---------------------------------------------------------------------------


def test_the_journal_is_read_back_after_a_restart_and_bad_lines_are_skipped(tmp_path: Path) -> None:
    first = Journal(tmp_path / JOURNAL_FILE)
    key = first.observe(verdict(), follow=True)["key"]  # type: ignore[index]
    first.mark(key, "took")
    with (tmp_path / JOURNAL_FILE).open("a", encoding="utf-8") as handle:
        handle.write("{not json\n\n")
    again = Journal(tmp_path / JOURNAL_FILE)
    assert again.get(key)["mark"] == "took"  # type: ignore[index]
    again.observe(verdict(), follow=True)  # the same trigger after a restart: still one record
    assert len(again.records()) == 1


def test_a_journal_that_cannot_be_written_never_breaks_a_check(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")
    journal = Journal(blocker / JOURNAL_FILE)  # its folder is a file
    record = journal.observe(verdict(), follow=True)
    assert record is not None and record["outcome"] == "open"  # kept in memory, the write failure logged
    assert "Could not write the decision journal" in caplog.text


def test_the_view_carries_the_stack_note_the_trigger_and_the_stats() -> None:
    journal = Journal()
    journal.observe(verdict(), follow=True)
    shown = journal.view(verdict(age_bars=3), "Backtest 2024-26: flat after costs.")
    assert shown is not None
    assert shown["stack"] == "1D / 1h / 5m" and shown["note"] == "Backtest 2024-26: flat after costs."
    assert shown["trigger"] == {
        "key": plan_key(verdict()), "side": "short", "since": "2026-11-12T09:40:00-05:00", "mark": "", "reason": "",
        "note": "", "outcome": "open", "result_r": None,
    }  # fmt: skip
    assert [r["key"] for r in shown["reasons"]] == list(wire.JOURNAL_REASONS)
    assert shown["stats"]["open"] == 1
    assert journal.view(verdict(minute=10))["trigger"] is None  # type: ignore[index]  # a trigger it never logged
    assert journal.view(None) is None


# --- the wire ---------------------------------------------------------------------------


def test_journal_commands_are_read_as_the_contract_writes_them() -> None:
    sent = {"type": "journal", "key": "NQ|1D/1h/5m|ttrades|short|x", "mark": "skipped", "reason": "no_confluence", "note": "thin"}
    assert wire.parse_command(json.dumps(sent)) == wire.Command("journal", {k: v for k, v in sent.items() if k != "type"})
    bare = wire.parse_command('{"type": "journal", "key": "k", "mark": "took"}')
    assert bare.values == {"key": "k", "mark": "took", "reason": "", "note": ""}
    assert wire.parse_command('{"type": "journal", "key": "k", "mark": ""}').values["mark"] == ""


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ('{"type": "journal", "mark": "took"}', "key"),
        ('{"type": "journal", "key": "k"}', "mark"),
        ('{"type": "journal", "key": "k", "mark": "maybe"}', "mark"),
        ('{"type": "journal", "key": "k", "mark": "skipped", "reason": "bored"}', "reason"),
        ('{"type": "journal", "key": "k", "mark": "took", "note": 5}', "note"),
        ('{"type": "journal", "key": "k", "mark": "took", "score": 1}', "does not take: score"),
        (json.dumps({"type": "journal", "key": "k", "mark": "took", "note": "x" * 201}), "at most 200"),
    ],
)
def test_journal_commands_that_cannot_be_used_are_refused(text: str, reason: str) -> None:
    with pytest.raises(wire.WireError) as caught:
        wire.parse_command(text)
    assert reason in str(caught.value)


def test_a_snapshot_carries_the_journal_only_when_given() -> None:
    from companion.app_model import LiveStatus, VerdictView

    view = VerdictView(
        decision="short", decision_word="TRADE SHORT", tone="short", headline="", bias="", path="", stage="", levels=(),
        has_levels=False, invalidation="", summary="", groups=(),
    )  # fmt: skip
    status = LiveStatus("live", "LIVE")
    assert "journal" not in wire.snapshot(1, view, "", False, status, None)["view"]  # saved history keeps its shape
    journal = Journal()
    journal.observe(verdict(), follow=True)
    message = json.loads(wire.dumps(wire.snapshot(2, view, "", False, status, None, journal.view(verdict(), "note"))))
    assert message["view"]["journal"]["trigger"]["key"] == plan_key(verdict())
    assert message["view"]["journal"]["stats"]["all"] == {"n": 0, "avg_r": None}
    assert wire.snapshot(3, None, "x", False, status, None, {"stack": "s"})["view"] is None


# --- the live loop ----------------------------------------------------------------------


class Market:
    """A live core over the fake market whose verdicts carry a triggered short on the 10:40 bar."""

    def __init__(self, tmp_path: Path, outcome: str = "open") -> None:
        self.outcome = outcome
        self.tv = FakeTradingView(market_minutes(), "2026-03-10 10:47:20")
        source = TradingViewBarSource(self.tv, symbols_path=write_symbols(tmp_path / "symbols.json"), clock=self.tv.clock)
        self.controller = CompanionController(
            state_path=tmp_path / "state" / "ui_state.json", live_source=source, default_data=DATA_LIVE, clock=self.tv.clock,
            analyze_fn=self.analyze,
        )  # fmt: skip
        self.controller.state.symbol, self.controller.state.stack, self.controller.state.style = "NQ", "1D / 1h / 5m", "ttrades"
        self.messages: list[dict[str, Any]] = []
        self.replies: list[dict[str, Any]] = []
        self.core = Core(self.controller, run_check=inline, run_watch=inline, listener=self.messages.append, alerts=False)
        self.core.begin()
        self.core.step()

    def analyze(self, *args: Any, **kwargs: Any) -> Verdict:
        real = engine.analyze(*args, **kwargs)
        plan = PositionPlan(
            "short", "triggered", 25000.0, 25020.0, 24960.0, 2.0, "5m",
            since=datetime(2026, 3, 10, 10, 40, tzinfo=NY), outcome=self.outcome,  # type: ignore[arg-type]
        )  # fmt: skip
        return replace(real, decision="short", plan=plan)

    def send(self, kind: str, **values: Any) -> None:
        self.core.submit(wire.Command(kind, values), self.replies.append)
        self.core.step()

    def last_view(self) -> dict[str, Any]:
        return [m for m in self.messages if m["type"] == "snapshot" and m["view"] is not None][-1]["view"]


def test_a_live_check_logs_its_trigger_and_the_trader_marks_it(tmp_path: Path) -> None:
    market = Market(tmp_path)
    journal = market.core.journal
    assert journal is not None and journal.path == tmp_path / "state" / JOURNAL_FILE
    assert len(journal.records()) == 1
    shown = market.last_view()["journal"]
    assert shown["stack"] == "1D / 1h / 5m" and shown["note"].startswith("Backtest 2024-26")  # the stack's evidence line
    key = shown["trigger"]["key"]
    assert shown["trigger"]["mark"] == ""

    before = len(market.messages)
    market.send("journal", key=key, mark="skipped", reason="news", note="CPI at 10")
    assert market.replies == []
    answered = market.last_view()["journal"]["trigger"]
    assert len(market.messages) > before and (answered["mark"], answered["reason"], answered["note"]) == ("skipped", "news", "CPI at 10")
    assert journal.flush()  # the core writes on its own thread
    assert lines(tmp_path / "state" / JOURNAL_FILE)[0]["mark"] == "skipped"

    market.send("journal", key="not a trigger", mark="took")
    assert market.replies[-1]["type"] == "error" and "not in the journal" in market.replies[-1]["message"]


def test_the_loop_fills_the_outcome_and_never_logs_when_looking_back(tmp_path: Path) -> None:
    market = Market(tmp_path)
    journal = market.core.journal
    assert journal is not None
    market.outcome = "stopped"
    market.send("step", direction=-1)  # looking back: no outcome filled from it
    assert journal.records()[0]["outcome"] == "open"
    market.send("latest")  # following now again
    assert (journal.records()[0]["outcome"], journal.records()[0]["result_r"]) == ("stopped", -1.0)
    assert market.last_view()["journal"]["stats"]["all"] == {"n": 1, "avg_r": -1.0}


def test_a_live_check_without_journal_is_unchanged(tmp_path: Path) -> None:
    market = Market(tmp_path)
    market.core.journal = None
    market.send("check")
    assert "journal" not in market.last_view()
    market.send("journal", key="k", mark="took")
    assert "off" in market.replies[-1]["message"]


# --- council fixes: outcomes from the bars, hindsight calls, the writer thread ----------


class Bar:
    def __init__(self, hhmm: str, high: float, low: float, forming: bool = False) -> None:
        self.time = pd.Timestamp(f"2026-11-12 {hhmm}")  # naive New York, like the chart's candles
        self.high, self.low, self.forming = high, low, forming


def test_an_open_trigger_is_resolved_from_the_bars_even_when_the_app_shows_another_idea(tmp_path: Path) -> None:
    journal = Journal(tmp_path / JOURNAL_FILE)
    journal.observe(verdict(), follow=True, now=NOW)  # the 09:40 short: stop 25,436, target 25,358
    other = verdict(decision="long", minute=55, direction="long", entry=25400.0, stop=25380.0, target=25440.0)
    bars = [Bar("09:40", 25420, 25405), Bar("09:45", 25440, 25410), Bar("09:50", 25445, 25430)]
    journal.observe(other, follow=True, now=NOW, bars=bars)  # the screen moved on; the short was stopped at 09:45
    short = [r for r in journal.records() if r["side"] == "short"][0]
    assert (short["outcome"], short["result_r"]) == ("stopped", -1.0)
    assert short["outcome_at"].startswith("2026-11-12T09:45")


def test_a_bar_through_both_levels_is_stopped_and_the_trigger_bar_and_forming_bars_never_count(tmp_path: Path) -> None:
    journal = Journal(tmp_path / JOURNAL_FILE)
    journal.observe(verdict(), follow=True, now=NOW)
    key = journal.records()[0]["key"]
    journal.observe(verdict(), follow=True, now=NOW, bars=[Bar("09:40", 25500, 25300), Bar("09:45", 25420, 25300, forming=True)])
    assert journal.get(key)["outcome"] == "open"  # the trigger bar itself and a forming bar decide nothing
    journal.observe(verdict(), follow=True, now=NOW, bars=[Bar("09:40", 25420, 25405), Bar("09:45", 25440, 25350)])
    assert (journal.get(key)["outcome"], journal.get(key)["result_r"]) == ("stopped", -1.0)


def test_a_trigger_older_than_the_bars_on_screen_stays_open(tmp_path: Path) -> None:
    journal = Journal(tmp_path / JOURNAL_FILE)
    journal.observe(verdict(), follow=True, now=NOW)
    key = journal.records()[0]["key"]
    journal.observe(verdict(minute=55), follow=True, now=NOW, bars=[Bar("10:00", 25300, 25200)])
    assert journal.get(key)["outcome"] == "open"


def test_calls_made_after_the_trade_ended_stay_out_of_the_averages(tmp_path: Path) -> None:
    journal = Journal(tmp_path / JOURNAL_FILE)
    journal.observe(verdict(), follow=True, now=NOW)
    key = journal.records()[0]["key"]
    journal.observe(verdict(outcome="target_reached"), follow=True, now=NOW)
    journal.mark(key, "took", now=NOW)  # marked a winner after the fact
    stats = journal.stats(STACK.name)
    assert stats["taken"]["n"] == 0 and stats["all"]["n"] == 1 and stats["late"] == 1
    journal.observe(verdict(minute=55, decision="watch", outcome="stopped", stage_label="played_out"), follow=True, now=NOW)
    seen_late = [r for r in journal.records() if r["key"] != key][0]
    journal.mark(seen_late["key"], "skipped", now=NOW)  # first seen already played out: a call cannot be in time
    stats = journal.stats(STACK.name)
    assert stats["skipped"]["n"] == 0 and stats["all"]["n"] == 2 and stats["late"] == 2


def test_the_core_journal_writes_on_its_own_thread_and_flush_waits_for_it(tmp_path: Path) -> None:
    journal = Journal.from_state(tmp_path)
    journal.observe(verdict(), follow=True, now=NOW)
    assert journal.flush()
    assert len(lines(tmp_path / JOURNAL_FILE)) == 1
