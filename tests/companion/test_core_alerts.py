"""Discord alerts: who gets one, what it says, once per trigger, and never breaking a check."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from companion.core.alerts import SENT_FILE, DiscordAlerts, message, trigger_key, webhook_from_state
from companion.types import PositionPlan, TimeframeStack, Verdict

NY = ZoneInfo("America/New_York")
URL = "https://discord.com/api/webhooks/123/abc"


def verdict(**plan_changes) -> Verdict:
    plan = PositionPlan(
        direction="short",
        state="triggered",
        entry=25410.0,
        stop=25436.0,
        target=25358.0,
        r_multiple=2.0,
        timeframe="5m",
        since=datetime(2026, 11, 12, 9, 40, tzinfo=NY),
        note="Entry is the close of the 5m candle at 09:40 (the turn). Stop: high of the setup swing candle (protected high from the entry CISD).",
        stage_label="actionable",
        age_bars=1,
        risk_adr=0.062,
        cost_r_mini=0.05,
        cost_r_micro=0.11,
    )
    plan = replace(plan, **plan_changes)
    return Verdict(
        style="ttrades",
        symbol="NQ",
        as_of=datetime(2026, 11, 12, 9, 45, tzinfo=NY),
        stack=TimeframeStack("1D / 1h / 5m", "1D", "1h", "5m"),
        decision="short",
        bias="bearish",
        path_family="continuation",
        stage="c4",
        criteria=(),
        entry=plan.entry,
        stop=plan.stop,
        targets=(plan.target,),
        why="Daily Candle 2 swept the high; the 1h closed back down at the fair value gap and the 5m turned.",
        plan=plan,
    )


def collect() -> tuple[list[tuple[str, dict]], DiscordAlerts]:
    sent: list[tuple[str, dict]] = []
    return sent, DiscordAlerts(URL, post=lambda url, payload: sent.append((url, payload)), background=False)


def test_an_actionable_trigger_sends_one_message_with_levels_stop_reason_and_setup():
    sent, alerts = collect()
    assert alerts.consider(verdict()) is True
    assert len(sent) == 1
    url, payload = sent[0]
    assert url == URL
    text = payload["content"]
    assert text.startswith("**NQ SHORT** · 1D / 1h / 5m · continuation · Thu 12 Nov 09:45 New York")
    assert "Entry **25,410.00** · Stop **25,436.00** · Target **25,358.00** (2.0R)" in text
    assert "protected high from the entry CISD" in text  # the stop's protected swing
    assert "Stop 6.2% of ADR · costs 0.05R mini, 0.11R micro" in text
    assert "Why: Daily Candle 2 swept the high" in text
    assert payload["allowed_mentions"] == {"parse": []}  # an alert never pings anyone


def test_the_same_trigger_is_sent_once_and_a_new_trigger_again():
    sent, alerts = collect()
    alerts.consider(verdict())
    alerts.consider(verdict(age_bars=2))  # the next check, same trigger
    assert len(sent) == 1
    alerts.consider(verdict(since=datetime(2026, 11, 12, 10, 5, tzinfo=NY)))
    assert len(sent) == 2


@pytest.mark.parametrize(
    "change",
    [
        {"stage_label": "late"},  # first seen long after it triggered
        {"state": "planned"},
        {"outcome": "target_reached"},
        {"outcome": "stopped"},
    ],
)
def test_no_alert_unless_the_trade_has_just_triggered_and_is_open(change):
    sent, alerts = collect()
    assert alerts.consider(verdict(**change)) is False
    assert sent == []


def test_no_alert_on_watch_or_no_trade_or_without_a_plan():
    sent, alerts = collect()
    assert alerts.consider(replace(verdict(), decision="watch")) is False
    assert alerts.consider(replace(verdict(), decision="no_trade")) is False
    assert alerts.consider(replace(verdict(), plan=None)) is False
    assert alerts.consider(None) is False
    assert sent == []


def test_a_failing_webhook_is_logged_and_never_raises(caplog):
    def refuse(url, payload):
        raise OSError("connection refused")

    alerts = DiscordAlerts(URL, post=refuse, background=False)
    assert alerts.consider(verdict()) is True
    assert "Discord alert failed" in caplog.text


def test_sent_triggers_are_remembered_across_restarts(tmp_path: Path):
    sent: list = []
    post = lambda url, payload: sent.append(payload)  # noqa: E731
    DiscordAlerts(URL, tmp_path, post=post, background=False).consider(verdict())
    assert json.loads((tmp_path / SENT_FILE).read_text(encoding="utf-8")) == [trigger_key(verdict())]
    DiscordAlerts(URL, tmp_path, post=post, background=False).consider(verdict())  # the app restarted
    assert len(sent) == 1


def test_webhook_is_read_from_desktop_json_and_only_a_discord_url_counts(tmp_path: Path):
    assert webhook_from_state(tmp_path) == ""
    assert DiscordAlerts.from_state(tmp_path) is None
    (tmp_path / "desktop.json").write_text(json.dumps({"discord_webhook": "https://example.com/hook"}), encoding="utf-8")
    assert webhook_from_state(tmp_path) == ""
    (tmp_path / "desktop.json").write_text(json.dumps({"history_dir": "x", "discord_webhook": f" {URL} "}), encoding="utf-8")
    assert webhook_from_state(tmp_path) == URL
    assert DiscordAlerts.from_state(tmp_path) is not None


def test_message_stays_under_discords_limit():
    long = verdict(note="x" * 5000)
    assert len(message(long)) <= 2000


def test_a_failed_post_is_tried_again_on_the_next_check_and_given_up_after_three(tmp_path: Path):
    calls: list = []

    def flaky(url, payload):
        calls.append(payload)
        if len(calls) < 2:
            raise OSError("429 too many requests")

    alerts = DiscordAlerts(URL, tmp_path, post=flaky, background=False)
    alerts.consider(verdict())
    assert not (tmp_path / SENT_FILE).exists()  # nothing counts as sent until Discord took it
    alerts.consider(verdict(age_bars=2))  # the next check of the same trigger
    assert len(calls) == 2 and json.loads((tmp_path / SENT_FILE).read_text(encoding="utf-8")) == [trigger_key(verdict())]
    alerts.consider(verdict(age_bars=3))
    assert len(calls) == 2

    def down(url, payload):
        calls.append(payload)
        raise OSError("no network")

    other = DiscordAlerts(URL, post=down, background=False)
    later = verdict(since=datetime(2026, 11, 12, 10, 5, tzinfo=NY))
    for _ in range(5):
        other.consider(later)
    assert len(calls) == 2 + 3


def test_a_thread_that_cannot_start_never_raises_and_frees_the_trigger(monkeypatch):
    sent, alerts = collect()
    alerts._background = True

    class NoThread:
        def __init__(self, *a, **k):
            raise RuntimeError("can't start new thread")

    monkeypatch.setattr("companion.core.alerts.threading.Thread", NoThread)
    assert alerts.consider(verdict()) is False
    alerts._background = False
    assert alerts.consider(verdict()) is True and len(sent) == 1


def test_two_alerts_finishing_together_both_stay_remembered(tmp_path: Path):
    import threading

    gate = threading.Barrier(2)

    def post(url, payload):
        gate.wait(timeout=5)  # both posts land at the same moment

    alerts = DiscordAlerts(URL, tmp_path, post=post, background=True)
    first, second = verdict(), verdict(since=datetime(2026, 11, 12, 10, 5, tzinfo=NY))
    assert alerts.consider(first) and alerts.consider(second)
    for _ in range(200):
        saved = json.loads((tmp_path / SENT_FILE).read_text(encoding="utf-8")) if (tmp_path / SENT_FILE).exists() else []
        if len(saved) == 2:
            break
        threading.Event().wait(0.02)
    assert sorted(saved) == sorted([trigger_key(first), trigger_key(second)])
    assert sorted(DiscordAlerts(URL, tmp_path, post=post)._sent) == sorted(saved)  # after a restart, neither is sent again
