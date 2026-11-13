"""Starting TradingView with the live-data link at companion start (``companion.tradingview.launch``).

Every outside effect is a fake: no TradingView is started, closed or looked for."""

from __future__ import annotations

from pathlib import Path

from companion.desktop import settings
from companion.tradingview import launch

EXE = Path("C:/TradingView/TradingView.exe")


class FakeTradingView:
    def __init__(self, *, running: bool, linked: bool, closes: bool = True, opens_port: bool = True, exe: Path | None = EXE) -> None:
        self.is_running = running
        self.linked = linked
        self.closes = closes
        self.opens_port = opens_port
        self.path = exe
        self.calls: list[str] = []
        self.questions: list[str] = []

    def answers(self, port: int) -> bool:
        return self.linked

    def running(self) -> bool:
        return self.is_running

    def exe(self) -> Path | None:
        return self.path

    def launch(self, path: Path, port: int) -> None:
        self.calls.append(f"start {path} --remote-debugging-port={port}")
        self.is_running = True
        self.linked = self.opens_port

    def close(self) -> None:
        self.calls.append("close")
        if self.closes:
            self.is_running = False

    def kill(self) -> None:
        self.calls.append("kill")
        self.is_running = False

    def ensure(self, yes: bool) -> launch.Outcome:
        def confirm(text: str) -> bool:
            self.questions.append(text)
            return yes

        return launch.ensure_link(
            confirm,
            answers=self.answers,
            running=self.running,
            exe=self.exe,
            launch=self.launch,
            close=self.close,
            kill=self.kill,
            sleep=lambda _seconds: None,
            port_wait=0.0,
            exit_wait=0.0,
        )


def test_a_linked_tradingview_is_left_alone() -> None:
    tv = FakeTradingView(running=True, linked=True)
    assert tv.ensure(yes=True).result == launch.LINKED
    assert tv.calls == [] and tv.questions == []


def test_a_closed_tradingview_is_started_with_the_link_without_asking() -> None:
    tv = FakeTradingView(running=False, linked=False)
    outcome = tv.ensure(yes=False)
    assert outcome.result == launch.STARTED
    assert tv.questions == []
    assert tv.calls == [f"start {EXE} --remote-debugging-port=9222"]


def test_an_unlinked_tradingview_is_restarted_only_after_a_yes() -> None:
    tv = FakeTradingView(running=True, linked=False)
    assert tv.ensure(yes=False).result == launch.DECLINED
    assert tv.calls == [] and len(tv.questions) == 1 and "without the live-data link" in tv.questions[0]

    tv = FakeTradingView(running=True, linked=False)
    assert tv.ensure(yes=True).result == launch.RESTARTED
    assert tv.calls == ["close", f"start {EXE} --remote-debugging-port=9222"]


def test_a_tradingview_that_will_not_close_is_ended_before_it_is_started_again() -> None:
    tv = FakeTradingView(running=True, linked=False, closes=False)
    assert tv.ensure(yes=True).result == launch.RESTARTED
    assert tv.calls == ["close", "kill", f"start {EXE} --remote-debugging-port=9222"]


def test_no_install_or_a_port_that_never_opens_is_reported() -> None:
    tv = FakeTradingView(running=False, linked=False, exe=None)
    outcome = tv.ensure(yes=True)
    assert outcome.result == launch.NOT_FOUND and tv.calls == []

    tv = FakeTradingView(running=False, linked=False, opens_port=False)
    outcome = tv.ensure(yes=True)
    assert outcome.result == launch.FAILED and "9222" in outcome.detail


def test_starting_tradingview_is_on_unless_desktop_json_turns_it_off(tmp_path: Path) -> None:
    assert settings.start_tradingview(tmp_path)
    settings.save_settings(tmp_path, start_tradingview=False)
    assert not settings.start_tradingview(tmp_path)
