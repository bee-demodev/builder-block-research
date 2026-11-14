"""The decision journal: every trigger the trader saw live, what they did, and how it ended.

It is the only way to measure whether the trader's discretion adds an edge the rules lack:
the engine's own triggers are the baseline, the trader's taken and skipped ones are held
against it, stack by stack.

- **Logged**: a live check that follows the latest bars, whose decision is long, short or
  watch and whose plan has triggered (a watch is a trigger held back by quality checks or
  one that has played out). One record per trigger (``alerts.plan_key``: symbol, stack,
  style, side, trigger bar), with what was shown the first time it was seen.
- **Marked**: the trader says "took" or "skipped", with a reason from ``wire.JOURNAL_REASONS``
  and an optional note. Marking again overwrites.
- **Outcome**: filled from later live checks of the same trigger (whatever their decision):
  the target reached is ``+r_multiple``, stopped is ``-1`` R. Every open record of the
  symbol and stack is also resolved from the entry chart's closed bars with its own frozen
  levels (the plan's rule: the first bar after the trigger bar through the stop or the
  target; one that does both is stopped), so a trigger stays counted when the app moves on
  to another idea. One older than the bars on screen stays open; no outcome is invented.
  R is the plan's, before costs.
- **Honest averages**: a call made after the trade had already ended (``late``), or on a
  trigger first seen already played out, is kept but left out of the took / skipped
  averages; the all-triggers baseline counts every closed trigger.

Records live in ``journal.jsonl`` in the state folder, one JSON object per line and per
trigger, rewritten whole (temp file, then replace) when one changes, by a writer thread
when the core runs it (``background``), so a slow disk never delays a check. The journal
never changes a decision, the checklist or a setting, and ``observe`` never raises: a write
that fails is logged and the check goes on.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from companion.core import wire
from companion.core.alerts import plan_key
from companion.types import Verdict

log = logging.getLogger("companion.journal")

JOURNAL_FILE = "journal.jsonl"
LOGGED_DECISIONS = ("long", "short", "watch")
MIN_N = 20  # closed trades below which an average R means nothing yet

Record = dict[str, Any]


class JournalError(ValueError):
    """A mark that cannot be applied; the text goes back to the client."""


def blocked_reasons(verdict: Verdict) -> list[str]:
    """Why a triggered plan is held back (watch only): its path's failing quality checks, and played out."""
    plan = verdict.plan
    if verdict.decision != "watch" or plan is None:
        return []
    family = verdict.path_family if verdict.path_family != "none" else ""
    keys = [
        c.key
        for c in verdict.criteria
        if c.role.strip().lower() == "quality" and c.passed is not True and (not family or not c.group or c.group.startswith(family))
    ]
    if plan.outcome != "open":
        keys.append("played_out")
    return list(dict.fromkeys(keys))


def _result_r(outcome: str, r_multiple: float | None) -> float | None:
    if outcome == "target_reached":
        return None if r_multiple is None else round(float(r_multiple), 4)
    if outcome == "stopped":
        return -1.0
    return None


def _hindsight(record: Record) -> bool:
    """The call on this trigger could not have been made before it ended."""
    return bool(record.get("late")) or bool(record.get("seen_closed"))


def _naive(value: Any) -> pd.Timestamp | None:
    """A time as naive New York, for comparing record times with chart bars."""
    if value is None or value == "":
        return None
    try:
        stamp = pd.Timestamp(value)
    except (TypeError, ValueError):
        return None
    if stamp.tzinfo is not None:
        stamp = stamp.tz_convert("America/New_York").tz_localize(None)
    return stamp


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and abs(number) != float("inf") else None


class Journal:
    """The trigger records, held in memory and kept in ``path``. ``observe`` is cheap and never raises."""

    def __init__(self, path: Path | None = None, background: bool = False) -> None:
        self.path = Path(path) if path is not None else None
        self._lock = threading.Lock()
        self._records: dict[str, Record] = self._load()
        self._background = background
        self._changed = threading.Condition(self._lock)
        self._version = 0  # bumps with every change
        self._written = 0  # the version last written (or given up on)
        self._writer: threading.Thread | None = None

    @classmethod
    def from_state(cls, state: Path) -> Journal:
        return cls(Path(state) / JOURNAL_FILE, background=True)

    # --- reading ---

    def records(self) -> list[Record]:
        with self._lock:
            return [dict(record) for record in self._records.values()]

    def get(self, key: str | None) -> Record | None:
        if not key:
            return None
        with self._lock:
            record = self._records.get(key)
            return dict(record) if record is not None else None

    def record_for(self, verdict: Verdict | None) -> Record | None:
        """The journal's record of the trigger ``verdict`` shows, when it has one."""
        if verdict is None:
            return None
        try:
            return self.get(plan_key(verdict))
        except Exception:  # noqa: BLE001 - the journal must never break a check
            log.exception("Could not look up a journal record.")
            return None

    def stats(self, stack: str, symbol: str | None = None, style: str | None = None) -> dict[str, Any]:
        """Closed outcomes on ``stack`` (and ``symbol`` / ``style`` when given, so NQ and ES are
        never pooled): taken, skipped and every logged trigger (the engine's baseline)."""
        with self._lock:
            mine = [
                record
                for record in self._records.values()
                if record.get("stack") == stack
                and (symbol is None or record.get("symbol") == symbol)
                and (style is None or record.get("style") == style)
            ]
        closed = [record for record in mine if _number(record.get("result_r")) is not None]

        def tally(rows: list[Record]) -> dict[str, Any]:
            values = [_number(row.get("result_r")) or 0.0 for row in rows]
            return {"n": len(values), "avg_r": round(sum(values) / len(values), 4) if values else None}

        called = [r for r in closed if not _hindsight(r)]
        return {
            "taken": tally([r for r in called if r.get("mark") == "took"]),
            "skipped": tally([r for r in called if r.get("mark") == "skipped"]),
            "all": tally(closed),
            "open": len(mine) - len(closed),
            "min_n": MIN_N,
            "late": sum(1 for r in closed if r.get("mark") in ("took", "skipped") and _hindsight(r)),
        }

    # --- writing ---

    def observe(
        self, verdict: Verdict | None, *, follow: bool, now: object | None = None, bars: Iterable[Any] = ()
    ) -> Record | None:
        """Log a new trigger, or fill the outcome of a logged one, from a finished check.

        ``bars``: the entry chart's candles (``time``, ``high``, ``low``, ``forming``); the
        closed ones resolve every open record of this symbol and stack with its own levels.
        Only a live check that follows the latest bars counts (``follow``): looking back at
        history never logs nor fills. Returns the trigger's record, or None. Never raises."""
        if verdict is None or not follow:
            return None
        try:
            record = self._observe(verdict, now)
            self._resolve(verdict, bars, now)
            return self.get(record["key"]) if record is not None else None
        except Exception:  # noqa: BLE001 - the journal must never break a check
            log.exception("Could not update the decision journal.")
            return None

    def _resolve(self, verdict: Verdict, bars: Iterable[Any], now: object | None) -> None:
        """Close open records of ``verdict``'s symbol and stack from closed entry bars (the plan's own rule)."""
        closed = [(_naive(bar.time), float(bar.high), float(bar.low)) for bar in bars if not getattr(bar, "forming", False)]
        closed = [bar for bar in closed if bar[0] is not None]
        if not closed:
            return
        first = closed[0][0]
        with self._lock:
            changed = False
            for record in self._records.values():
                if record.get("outcome", "open") != "open":
                    continue
                if record.get("symbol") != verdict.symbol or record.get("stack") != verdict.stack.name:
                    continue
                since, stop, target = _naive(record.get("since")), _number(record.get("stop")), _number(record.get("target"))
                if since is None or stop is None or target is None or since < first:
                    continue  # its bars are no longer on screen: leave it open rather than guess
                long = record.get("side") == "long"
                for time, high, low in closed:
                    if time <= since:
                        continue
                    hit_stop = low < stop if long else high > stop
                    hit_target = high >= target if long else low <= target
                    if hit_stop or hit_target:
                        outcome = "stopped" if hit_stop else "target_reached"  # a bar that does both is stopped
                        record["outcome"] = outcome
                        record["outcome_at"] = wire.iso(time)
                        record["result_r"] = _result_r(outcome, _number(record.get("r_multiple")))
                        record["closed_at"] = wire.iso(now) if now is not None else None
                        changed = True
                        break
            if changed:
                self._save()

    def _observe(self, verdict: Verdict, now: object | None) -> Record | None:
        key = plan_key(verdict)
        plan = verdict.plan
        if key is None or plan is None:
            return None
        with self._lock:
            record = self._records.get(key)
            if record is None:
                if verdict.decision not in LOGGED_DECISIONS:
                    return None
                record = self._new(key, verdict, now)
                record["seen_closed"] = plan.outcome != "open"  # first seen already played out: no call in time
                self._records[key] = record
                changed = True
            else:
                changed = False
            if record.get("outcome", "open") == "open" and plan.outcome in ("target_reached", "stopped"):
                record["outcome"] = plan.outcome
                record["outcome_at"] = wire.iso(plan.outcome_at)
                record["result_r"] = _result_r(plan.outcome, plan.r_multiple)
                record["closed_at"] = wire.iso(now) if now is not None else None
                changed = True
            if changed:
                self._save()
            return dict(record)

    def _new(self, key: str, verdict: Verdict, now: object | None) -> Record:
        plan = verdict.plan
        assert plan is not None
        return {
            "key": key,
            "symbol": verdict.symbol,
            "stack": verdict.stack.name,
            "style": verdict.style,
            "side": plan.direction,
            "since": wire.iso(plan.since),
            "as_of": wire.iso(verdict.as_of),
            "logged_at": wire.iso(now) if now is not None else None,
            # what was shown the first time the trigger was seen
            "decision": verdict.decision,
            "stage_label": plan.stage_label,
            "entry": _number(plan.entry),
            "stop": _number(plan.stop),
            "target": _number(plan.target),
            "r_multiple": _number(plan.r_multiple),
            "blocked": blocked_reasons(verdict),
            # the trader's call
            "mark": "",
            "reason": "",
            "note": "",
            "marked_at": None,
            # how it ended
            "outcome": "open",
            "outcome_at": None,
            "result_r": None,
            "closed_at": None,
        }

    def mark(self, key: str, mark: str, reason: str = "", note: str = "", now: object | None = None) -> Record:
        """The trader's call on a logged trigger: "took", "skipped", or "" to clear it. Overwrites."""
        if mark not in wire.JOURNAL_MARKS:
            raise JournalError(f"mark must be one of: {', '.join(json.dumps(m) for m in wire.JOURNAL_MARKS)}.")
        if reason and reason not in wire.JOURNAL_REASONS:
            raise JournalError(f"reason must be one of: {', '.join(wire.JOURNAL_REASONS)}.")
        with self._lock:
            record = self._records.get(key)
            if record is None:
                raise JournalError("That trigger is not in the journal.")
            if record.get("outcome", "open") != "open":
                raise JournalError("That trade has already ended; a call now would be hindsight, so it is not recorded.")
            cleared = mark == ""
            # a call made once the trade has ended is hindsight: kept, but out of the averages
            record["late"] = not cleared and record.get("outcome", "open") != "open"
            record["mark"] = mark
            record["reason"] = "" if cleared else reason
            record["note"] = "" if cleared else note.strip()
            record["marked_at"] = None if cleared or now is None else wire.iso(now)
            self._save()
            return dict(record)

    # --- the file ---

    def _load(self) -> dict[str, Record]:
        if self.path is None:
            return {}
        try:
            text = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return {}
        except OSError:
            log.exception("Could not read the decision journal %s.", self.path)
            return {}
        records: dict[str, Record] = {}
        for number, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except ValueError:
                log.warning("Skipped line %d of %s: not JSON.", number, self.path)
                continue
            if isinstance(record, dict) and isinstance(record.get("key"), str):
                records[record["key"]] = record  # a later line for the same trigger wins
        return records

    def _save(self) -> None:
        """Rewrite the file (called with the lock held): now, or on the writer thread when ``background``."""
        if self.path is None:
            return
        self._version += 1
        if not self._background:
            self._write(list(self._records.values()))
            self._written = self._version
            return
        try:
            if self._writer is None or not self._writer.is_alive():
                self._writer = threading.Thread(target=self._write_loop, name="journal-writer", daemon=True)
                self._writer.start()
        except RuntimeError:  # no thread to be had: write here rather than lose it
            self._write(list(self._records.values()))
            self._written = self._version
            return
        self._changed.notify_all()

    def _write_loop(self) -> None:
        while True:
            with self._lock:
                while self._written >= self._version:
                    self._changed.wait()
                version, records = self._version, [dict(record) for record in self._records.values()]
            self._write(records)
            with self._lock:
                self._written = max(self._written, version)
                self._changed.notify_all()

    def flush(self, timeout: float = 5.0) -> bool:
        """Wait until every change is on disk (tests, and the core when it stops). True when it is."""
        with self._lock:
            return self._changed.wait_for(lambda: self._written >= self._version, timeout)

    def _write(self, records: list[Record]) -> None:
        """Rewrite the file from ``records``. A failure is logged, never raised."""
        if self.path is None:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            spare = self.path.with_name(self.path.name + ".tmp")
            lines = (json.dumps(record, ensure_ascii=False, separators=(",", ":")) for record in records)
            spare.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")
            os.replace(spare, self.path)
        except (OSError, TypeError, ValueError):
            log.exception("Could not write the decision journal %s.", self.path)

    # --- for the client ---

    def view(self, verdict: Verdict | None, stack_note: str = "") -> dict[str, Any] | None:
        """``Journal`` on the wire: the stack's stats and note, and the trigger on screen when it is logged."""
        if verdict is None:
            return None
        try:
            stack = verdict.stack.name
            record = self.record_for(verdict)
            return {
                "stack": stack,
                "note": stack_note,
                "trigger": _trigger(record) if record is not None else None,
                "reasons": [{"key": key, "label": label} for key, label in wire.JOURNAL_REASONS.items()],
                "stats": self.stats(stack, verdict.symbol, verdict.style),
            }
        except Exception:  # noqa: BLE001 - the journal must never break a check
            log.exception("Could not show the decision journal.")
            return None


def _trigger(record: Record) -> dict[str, Any]:
    outcome = record.get("outcome")
    return {
        "key": str(record.get("key", "")),
        "side": record.get("side") if record.get("side") in ("long", "short") else "long",
        "since": record.get("since"),
        "mark": record.get("mark") if record.get("mark") in wire.JOURNAL_MARKS else "",
        "reason": record.get("reason") if record.get("reason") in wire.JOURNAL_REASONS else "",
        "note": str(record.get("note") or ""),
        "outcome": outcome if outcome in ("open", "target_reached", "stopped") else "open",
        "result_r": _number(record.get("result_r")),
    }
