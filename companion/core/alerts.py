"""Discord alerts: one message when a live check turns into an actionable trade.

The webhook comes from ``discord_webhook`` in ``desktop.json`` in the state folder (the
trader pastes it there; it never goes in the repo). Without one, nothing is sent.

A message goes out only for a live check that follows the latest bars, whose decision is
long or short and whose plan has just triggered ("actionable": at most a few entry bars
old and price still near the entry). Each trigger is sent once, also across restarts:
the keys already sent are kept in ``discord_sent.json``. Sending runs on its own thread
and never fails or slows a check; a failure is only logged.
"""

from __future__ import annotations

import json
import logging
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
    ok = url.startswith(("https://discord.com/api/webhooks/", "https://discordapp.com/api/webhooks/"))
    if url and not ok:
        log.warning("discord_webhook in %s is not a Discord webhook URL; alerts are off.", Path(state) / SETTINGS_FILE)
    return url if ok else ""


def trigger_key(verdict: Verdict) -> str | None:
    """The trigger an alert is about, or None when this verdict is not a fresh, actionable trade."""
    plan = verdict.plan
    if verdict.decision not in ("long", "short") or plan is None:
        return None
    if plan.state != "triggered" or plan.outcome != "open" or plan.stage_label != "actionable":
        return None
    since = plan.since.isoformat() if plan.since is not None else ""
    stack = verdict.stack
    return f"{verdict.symbol}|{stack.bias}/{stack.setup}/{stack.entry}|{verdict.style}|{plan.direction}|{since}"


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
        lines.append(" · ".join(extras).capitalize())
    if verdict.why:
        lines.append(f"Why: {verdict.why}")
    return "\n".join(lines)[:1900]  # Discord caps a message at 2000 characters


class DiscordAlerts:
    """Sends one Discord message per actionable trigger. ``consider`` is cheap and never raises."""

    def __init__(self, webhook: str, state: Path | None = None, post: Post | None = None, background: bool = True) -> None:
        self.webhook = webhook
        self.state = Path(state) if state is not None else None
        self._post = post or post_json
        self._background = background
        self._lock = threading.Lock()
        self._sent: list[str] = self._load()

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
        try:
            key = trigger_key(verdict)
            if key is None:
                return False
            with self._lock:
                if key in self._sent:
                    return False
                self._sent = [*self._sent, key][-KEEP:]
                self._save()
            payload = {"content": message(verdict), "username": "Trading Companion", "allowed_mentions": {"parse": []}}
        except Exception:  # an alert must never break a check
            log.exception("Could not prepare a Discord alert.")
            return False
        if self._background:
            threading.Thread(target=self._send, args=(payload, key), name="discord-alert", daemon=True).start()
        else:
            self._send(payload, key)
        return True

    def _send(self, payload: dict[str, Any], key: str) -> None:
        try:
            self._post(self.webhook, payload)
            log.info("Discord alert sent: %s", key)
        except (urllib.error.URLError, OSError, ValueError) as problem:
            log.warning("Discord alert failed (%s): %s", key, problem)
        except Exception:
            log.exception("Discord alert failed: %s", key)

    def _load(self) -> list[str]:
        if self.state is None:
            return []
        try:
            data = json.loads((self.state / SENT_FILE).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        return [str(k) for k in data][-KEEP:] if isinstance(data, list) else []

    def _save(self) -> None:
        if self.state is None:
            return
        try:
            self.state.mkdir(parents=True, exist_ok=True)
            (self.state / SENT_FILE).write_text(json.dumps(self._sent), encoding="utf-8")
        except OSError:
            pass
