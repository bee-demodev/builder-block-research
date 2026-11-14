"""Discord alerts: one message when a live check turns into an actionable trade.

The webhook comes from ``discord_webhook`` in ``desktop.json`` in the state folder (the
trader pastes it there; it never goes in the repo). Without one, nothing is sent.

A message goes out only for a live check that follows the latest bars, whose decision is
long or short and whose plan has just triggered ("actionable": at most a few entry bars
old and price still near the entry). Each trigger is sent once, also across restarts:
the keys Discord accepted are kept in ``discord_sent.json``. A failed post is tried again
on the next check while the trigger is still actionable (at most ``MAX_ATTEMPTS`` times).
Sending and saving run on their own thread and never fail or slow a check; a failure is
only logged. The core only asks on fresh data (``CompanionController.is_stale``).
"""

from __future__ import annotations

import json
import logging
import os
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

from companion.types import Verdict

log = logging.getLogger("companion.alerts")

SETTINGS_FILE = "desktop.json"
SENT_FILE = "discord_sent.json"
KEEP = 200  # trigger keys remembered
MAX_ATTEMPTS = 3  # failed posts of one trigger before it is given up
TIMEOUT_S = 8.0

Post = Callable[[str, dict[str, Any]], None]


def post_json(url: str, payload: dict[str, Any]) -> None:
    """POST ``payload`` to a Discord webhook. Raises on a network error or a refusal."""
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "User-Agent": "TradingCompanion (alerts, 1.0)"},
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:  # noqa: S310 (the trader's own webhook)
        response.read()


def webhook_from_state(state: Path) -> str:
    """``discord_webhook`` from ``desktop.json``, or "" when there is none or it is not a Discord webhook."""
    try:
        data = json.loads((Path(state) / SETTINGS_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    url = data.get("discord_webhook", "") if isinstance(data, dict) else ""
    if not isinstance(url, str):
        return ""
    url = url.strip()
    hosts = ("discord.com", "discordapp.com", "ptb.discord.com", "canary.discord.com")
    ok = url.startswith(tuple(f"https://{host}/api/webhooks/" for host in hosts))
    if url and not ok:
        log.warning("discord_webhook in %s is not a Discord webhook URL; alerts are off.", Path(state) / SETTINGS_FILE)
    return url if ok else ""


def plan_key(verdict: Verdict) -> str | None:
    """Which trigger a verdict's plan is (symbol, stack, style, side, trigger bar), or None when nothing has triggered.

    The same trigger keeps its key from check to check, whatever the decision or the stage
    says about it, so the alerts and the decision journal can each act on it once."""
    plan = verdict.plan
    if plan is None or plan.state != "triggered":
        return None
    since = plan.since.isoformat() if plan.since is not None else ""
    stack = verdict.stack
    return f"{verdict.symbol}|{stack.bias}/{stack.setup}/{stack.entry}|{verdict.style}|{plan.direction}|{since}"


def trigger_key(verdict: Verdict) -> str | None:
    """The trigger an alert is about, or None when this verdict is not a fresh, actionable trade."""
    plan = verdict.plan
    if verdict.decision not in ("long", "short") or plan is None:
        return None
    if plan.state != "triggered" or plan.outcome != "open" or plan.stage_label != "actionable":
        return None
    return plan_key(verdict)


def _price(value: float) -> str:
    return f"{value:,.2f}"


def message(verdict: Verdict) -> str:
    """The Discord message for an actionable trade: side, levels, why and when."""
    plan = verdict.plan
    assert plan is not None
    stack = verdict.stack
    side = plan.direction.upper()
    when = verdict.as_of.strftime("%a %d %b %H:%M") + " New York"
    lines = [
        f"**{verdict.symbol} {side}** · {stack.bias} / {stack.setup} / {stack.entry} · {verdict.path_family} · {when}",
        f"Entry **{_price(plan.entry)}** · Stop **{_price(plan.stop)}** · Target **{_price(plan.target)}** ({plan.r_multiple:.1f}R)",
    ]
    if plan.note:
        lines.append(plan.note)
    extras = []
    if plan.risk_adr is not None:
        extras.append(f"stop {plan.risk_adr * 100:.1f}% of ADR")
    if plan.cost_r_mini is not None:
        extras.append(f"costs {plan.cost_r_mini:.2f}R mini" + (f", {plan.cost_r_micro:.2f}R micro" if plan.cost_r_micro is not None else ""))
    if extras:
        joined = " · ".join(extras)
        lines.append(joined[:1].upper() + joined[1:])  # not str.capitalize, which lowercases "ADR" and "R"
    if verdict.why:
        lines.append(f"Why: {verdict.why}")
    return "\n".join(lines)[:1900]  # Discord caps a message at 2000 characters


class DiscordAlerts:
    """Sends one Discord message per actionable trigger. ``consider`` is cheap and never raises.

    A trigger counts as sent only once Discord took the message: a failed post (no network,
    a refusal, a rate limit) frees it again, so the next check of the same still-actionable
    trigger tries again, up to ``MAX_ATTEMPTS`` times. The sent list is saved by the sending
    thread, never on the check thread."""

    def __init__(self, webhook: str, state: Path | None = None, post: Post | None = None, background: bool = True) -> None:
        self.webhook = webhook
        self.state = Path(state) if state is not None else None
        self._post = post or post_json
        self._background = background
        self._lock = threading.Lock()
        self._save_lock = threading.Lock()  # one save at a time, each writing the newest list
        self._sent: list[str] = self._load()
        self._busy: set[str] = set()  # posting now
        self._tries: dict[str, int] = {}  # failed posts per trigger

    @classmethod
    def from_state(cls, state: Path) -> DiscordAlerts | None:
        url = webhook_from_state(state)
        if not url:
            return None
        log.info("Discord alerts are on (entries that trigger).")
        return cls(url, state)

    def consider(self, verdict: Verdict | None) -> bool:
        """Send an alert if ``verdict`` is a new actionable trade. True when one was sent (or queued)."""
        if verdict is None:
            return False
        key: str | None = None
        try:
            key = trigger_key(verdict)
            if key is None:
                return False
            with self._lock:
                if key in self._sent or key in self._busy or self._tries.get(key, 0) >= MAX_ATTEMPTS:
                    return False
                self._busy.add(key)
            payload = {"content": message(verdict), "username": "Trading Companion", "allowed_mentions": {"parse": []}}
            if self._background:
                threading.Thread(target=self._send, args=(payload, key), name="discord-alert", daemon=True).start()
            else:
                self._send(payload, key)
            return True
        except Exception:  # an alert must never break a check
            log.exception("Could not prepare a Discord alert.")
            if key is not None:
                with self._lock:
                    self._busy.discard(key)
            return False

    def _send(self, payload: dict[str, Any], key: str) -> None:
        delivered = False
        try:
            self._post(self.webhook, payload)
            delivered = True
            log.info("Discord alert sent: %s", key)
        except (urllib.error.URLError, OSError, ValueError) as problem:
            log.warning("Discord alert failed (%s): %s", key, problem)
        except Exception:
            log.exception("Discord alert failed: %s", key)
        with self._lock:
            self._busy.discard(key)
            if not delivered:
                self._tries[key] = self._tries.get(key, 0) + 1
                return
            self._sent = [*self._sent, key][-KEEP:]
        with self._save_lock:  # read the list inside the save lock, so a later save never writes an older one
            with self._lock:
                sent = list(self._sent)
            self._save(sent)

    def _load(self) -> list[str]:
        if self.state is None:
            return []
        try:
            data = json.loads((self.state / SENT_FILE).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        return [str(k) for k in data][-KEEP:] if isinstance(data, list) else []

    def _save(self, sent: list[str]) -> None:
        if self.state is None:
            return
        try:
            self.state.mkdir(parents=True, exist_ok=True)
            spare = self.state / (SENT_FILE + ".tmp")
            spare.write_text(json.dumps(sent), encoding="utf-8")
            os.replace(spare, self.state / SENT_FILE)  # whole or not at all
        except OSError:
            log.warning("Could not save %s.", self.state / SENT_FILE)
