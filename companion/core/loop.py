"""``Core``: the companion's live loop without a window.

What the Tk window does with timers, done by one owning thread:

- one ``CompanionController``, touched only by the core thread (it is not thread-safe);
- one worker that runs ``CompanionController.run_check``, the only call that is safe off
  the owning thread (its docstring says so); the result comes back to the core thread,
  which hands it to ``accept`` and turns it into a ``snapshot`` message;
- a tick (every ``tick_ms``) that sends the live status line when it changes and starts
  the scheduled check when ``should_refresh`` says one is due;
- a watcher (live and following "now" only): every ``watch_ms`` one cheap read of the
  entry series' newest two bars (``TradingViewBarSource.peek``) on a thread of its own.
  It sends a ``tick`` with the forming candle when that changed, and starts a check as
  soon as TradingView has opened the bar after one the core has not analysed yet. When
  it cannot read, nothing changes: the scheduler above keeps running regardless, so the
  watcher can only make a check earlier, never prevent or replace one. Ticks never reach
  the engine and never change a verdict.

Commands come in through ``submit`` (any thread); messages go out through listeners,
called on the core thread with dicts built by ``companion.core.wire``.

Every live check also appends one line to ``timings.jsonl`` in the companion's state
folder: when the bar closed, when the core noticed, how long it waited for the worker,
the read, loading bars it did not hold, the engine, and the total lag.

A live check that follows "now" and turns into an actionable long or short also posts one
Discord message, when ``discord_webhook`` is set in ``desktop.json`` (``companion.core.alerts``).

Every live check that follows "now" and shows a triggered plan (long, short or watch) is
logged once per trigger in the decision journal, ``journal.jsonl`` in the state folder
(``companion.core.journal``); later checks of the same trigger fill its outcome, and the
``journal`` command records the trader's call on it. A live snapshot's view carries the
journal for its stack. The journal never changes a verdict and never fails a check.
"""

from __future__ import annotations

import json
import logging
import queue
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from companion.app_model import (
    CUSTOM_CHOICE,
    DATA_HISTORY,
    DATA_LABELS,
    SIDE_LABELS,
    CheckOutcome,
    CheckRequest,
    CompanionController,
    LiveStatus,
    UserError,
    format_when,
    parse_when,
)
from companion.bars import bar_close_times
from companion.core import wire
from companion.core.alerts import DiscordAlerts
from companion.core.journal import Journal, JournalError

log = logging.getLogger("companion.core")

TIMINGS_NAME = "timings.jsonl"
ERROR_LOG_NAME = "core_error.log"
WATCH_MS = 500
TICK_MS = 250
WATCH_BACKOFF_AFTER = 3  # failed peeks in a row before the watcher slows down
WATCH_BACKOFF_MS = 5000

Message = dict[str, Any]
Listener = Callable[[Message], None]
Reply = Callable[[Message], None]
Runner = Callable[[Callable[[], None]], Any]  # runs a job somewhere (a worker thread; inline in tests)


def inline(job: Callable[[], None]) -> None:
    """A runner that runs the job at once, on the caller's thread (tests drive the loop with ``step``)."""
    job()


@dataclass(frozen=True)
class _Job:
    seq: int
    request: CheckRequest
    trigger: str  # command | start | schedule | watch
    detected_at: pd.Timestamp  # naive New York: when the core decided to check


def _no_reply(_message: Message) -> None:
    pass


class Core:
    """The live loop around one controller. ``start``/``stop`` run it on its own thread;
    a caller that drives it itself (tests) calls ``begin`` once and then ``step``."""

    def __init__(
        self,
        controller: CompanionController,
        *,
        watch_ms: int = WATCH_MS,
        tick_ms: int = TICK_MS,
        listener: Listener | None = None,
        run_check: Runner | None = None,
        run_watch: Runner | None = None,
        timings_path: Path | None = None,
        alerts: DiscordAlerts | None | bool = True,
        journal: Journal | None | bool = True,
    ) -> None:
        self.controller = controller
        self.watch_ms = max(50, int(watch_ms))
        self.tick_ms = max(20, int(tick_ms))
        self.timings_path = Path(timings_path) if timings_path is not None else controller.state_path.parent / TIMINGS_NAME
        self._listeners: list[Listener] = [listener] if listener is not None else []
        # Discord alerts for entries that trigger: True reads the webhook from desktop.json, False is off.
        state = controller.state_path.parent
        self.alerts = DiscordAlerts.from_state(state) if alerts is True else (alerts or None)
        # the decision journal: True keeps it in journal.jsonl in the state folder, False is off
        self.journal = Journal.from_state(state) if journal is True else (journal or None)
        self._inbox: queue.Queue[tuple[Any, ...]] = queue.Queue()
        self._run_check = run_check
        self._run_watch = run_watch
        self._pools: list[ThreadPoolExecutor] = []
        self._thread: threading.Thread | None = None
        self._stopping = threading.Event()
        self.latest: dict[str, Message] = {}  # the last message of each type (hello, state, snapshot, status, tick)

        # owned by the core thread
        self._seq = 0  # bumps with every check asked for; a result whose number is old is dropped
        self._busy = False
        self._pending: _Job | None = None  # asked while a check ran: the newest one wins
        self._good: CheckOutcome | None = None  # the last live "now" verdict, kept on screen (stale) when a refresh fails
        self._shown: CheckOutcome | None = None  # the outcome whose verdict is on screen
        self._snapshots = 0
        self._last_snapshot: tuple[Any, str, bool, Message | None] | None = None  # view, error, offer_history, timing
        self._options: Message | None = None
        self._state: Message | None = None
        self._status: Message | None = None
        self._peeking = False
        self._next_peek: pd.Timestamp | None = None
        self._watch_target: tuple[str, str] | None = None
        self._watch_failures = 0
        self._last_tick: tuple[Any, ...] | None = None
        self._triggered_for: pd.Timestamp | None = None  # the bar close the watcher already started a check for

    # --- outside: any thread ---

    def add_listener(self, listener: Listener) -> None:
        self._listeners.append(listener)

    def submit(self, command: wire.Command, reply: Reply | None = None) -> None:
        """Queue a command for the core thread. ``reply`` gets an ``error`` message when it cannot be done."""
        self._inbox.put(("command", command, reply or _no_reply))

    def start(self) -> None:
        if self._thread is not None:
            return
        if self._run_check is None:
            pool = ThreadPoolExecutor(1, thread_name_prefix="companion-check")
            self._pools.append(pool)
            self._run_check = pool.submit
        if self._run_watch is None:
            pool = ThreadPoolExecutor(1, thread_name_prefix="companion-watch")
            self._pools.append(pool)
            self._run_watch = pool.submit
        self._thread = threading.Thread(target=self._run, name="companion-core", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        """Stop the loop, remember the selections and let go of TradingView."""
        self._stopping.set()
        self._inbox.put(("wake",))
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout)
        for pool in self._pools:
            pool.shutdown(wait=False, cancel_futures=True)
        self.controller.save()
        if self.journal is not None and not self.journal.flush(2.0):  # the last call on disk before the app goes
            log.warning("The decision journal's last changes may not be on disk.")
        self.controller.shutdown()

    # --- the loop ---

    def _run(self) -> None:
        self._guard(self.begin)
        while not self._stopping.is_set():
            try:
                item = self._inbox.get(timeout=self.tick_ms / 1000)
            except queue.Empty:
                item = None
            if item is not None:
                self._guard(self._handle, item)
            self._drain()
            if not self._stopping.is_set():
                self._guard(self._tick)

    def begin(self) -> None:
        """First messages, and the first live check (the window does the same when it opens)."""
        controller = self.controller
        if self._run_check is None:
            self._run_check = inline
        if self._run_watch is None:
            self._run_watch = inline
        self._fit_when()
        self._emit_hello(force=True)
        self._emit_state(force=True)
        self._snapshot(None, "", False, controller.live_status(None), None)
        if controller.is_live:
            self._check(auto=True, trigger="start")

    def step(self) -> None:
        """Handle everything queued, run one tick, and handle what that queued. For callers that drive the loop."""
        self._drain()
        self._guard(self._tick)
        self._drain()

    def _drain(self) -> None:
        while True:
            try:
                item = self._inbox.get_nowait()
            except queue.Empty:
                return
            self._guard(self._handle, item)

    def _guard(self, action: Callable[..., None], *args: Any) -> None:
        """The loop must outlive any fault: it is logged to the state folder and the loop goes on."""
        try:
            action(*args)
        except Exception:  # noqa: BLE001
            try:
                path = self.controller.state_path.parent / ERROR_LOG_NAME
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(traceback.format_exc(), encoding="utf-8")
            except OSError:
                pass

    def _handle(self, item: tuple[Any, ...]) -> None:
        kind = item[0]
        if kind == "command":
            self._command(item[1], item[2])
        elif kind == "result":
            self._result(item[1], item[2], item[3])
        elif kind == "peek":
            self._peeked(item[1], item[2])

    # --- commands ---

    def _command(self, command: wire.Command, reply: Reply) -> None:
        before = self._state
        try:
            handler = getattr(self, f"_do_{command.type}", None)
            if handler is None:
                reply(wire.error(f"Unknown command {command.type}."))
                return
            handler(command, reply)
        except UserError as problem:
            reply(wire.error(str(problem)))
        finally:
            self._emit_hello()
            self._emit_state(force=self._state is before)  # every command is answered with the state, once

    def _do_set(self, command: wire.Command, reply: Reply) -> None:
        controller, current = self.controller, self.controller.state
        values = dict(command.values)
        problems: list[str] = []
        data_changed = selection_changed = symbol_changed = side_changed = False

        if "data" in values:
            choice = values.pop("data").strip()
            mode = next((key for key, label in DATA_LABELS.items() if choice in (key, label)), None)
            if mode is None:
                problems.append(f"Data must be one of: {', '.join(DATA_LABELS)}.")
            elif mode != current.data:
                controller.set_data(mode)
                data_changed = True
        if "symbol" in values:
            wanted = values.pop("symbol").strip().upper()
            offered = controller.symbols()
            if wanted not in offered:
                problems.append(f"{wanted or 'That'} is not a symbol here; pick one of: {', '.join(offered)}.")
            elif wanted != current.symbol:
                current.symbol, symbol_changed = wanted, True
        for name in wire.CUSTOM_FIELDS:
            if name in values:
                frame = values.pop(name).strip()
                if frame not in controller.timeframe_choices():
                    problems.append(f"{frame or 'That'} is not a timeframe; pick one of: {', '.join(controller.timeframe_choices())}.")
                elif frame != getattr(current, name):
                    setattr(current, name, frame)
                    selection_changed = selection_changed or controller.is_custom or values.get("stack") == CUSTOM_CHOICE
        if "stack" in values:
            stack = values.pop("stack").strip()
            if stack not in controller.stack_choices():
                problems.append(f"“{stack}” is not a stack; pick one of: {', '.join(controller.stack_choices())}.")
            elif stack != current.stack:
                current.stack, selection_changed = stack, True
        if "style" in values:
            style = values.pop("style").strip()
            if style not in controller.style_choices():
                problems.append(f"“{style}” is not a style; pick one of: {', '.join(controller.style_choices())}.")
            elif style != current.style:
                current.style, selection_changed = style, True
        if "side" in values:
            wanted = values.pop("side").strip().lower()
            side = next((value for value, label in SIDE_LABELS.items() if wanted in (value, label.lower())), None)
            if side is None:
                choices = ", ".join(f"{json.dumps(value)} ({label})" for value, label in SIDE_LABELS.items())
                problems.append(f"Side must be one of: {choices}.")
            elif side != current.direction:
                controller.set_direction(side)
                side_changed = True
        if "when" in values:
            text = values.pop("when")
            if controller.is_live:
                problems.append("In live mode the time is TradingView's last closed bar: use step or latest to move it.")
            else:
                try:
                    current.when = format_when(parse_when(text))
                except UserError as problem:
                    problems.append(str(problem))

        if side_changed:
            self._good = None  # a kept live verdict was for the other side
        if data_changed:
            self._data_changed()
        elif controller.is_live and (selection_changed or symbol_changed):
            self._restart_live()
        else:
            if symbol_changed:
                self._fit_when()
            if side_changed and (controller.is_live or self._shown is not None):
                self._check(auto=False, trigger="command")  # the same moment again, for the side now asked (as the window does)
        controller.save()
        if problems:
            reply(wire.error(" ".join(problems)))

    def _do_check(self, command: wire.Command, reply: Reply) -> None:
        self._check(auto=False, trigger="command")

    def _do_step(self, command: wire.Command, reply: Reply) -> None:
        self.controller.step(command.direction)  # UserError: the reason goes back to the client
        self._check(auto=False, trigger="command")

    def _do_latest(self, command: wire.Command, reply: Reply) -> None:
        self.controller.jump_to_latest()
        self._check(auto=False, trigger="command")

    def _do_pause(self, command: wire.Command, reply: Reply) -> None:
        controller = self.controller
        controller.set_auto_refresh(not command.paused)
        controller.save()
        self._emit_status(controller.live_status(self._shown))

    def _do_journal(self, command: wire.Command, reply: Reply) -> None:
        """The trader's call on a logged trigger. The view on screen is sent again with it."""
        if self.journal is None:
            raise UserError("The decision journal is off.")
        values = command.values
        try:
            self.journal.mark(values.get("key", ""), values.get("mark", ""), values.get("reason", ""), values.get("note", ""), self.controller.now())
        except JournalError as problem:
            raise UserError(str(problem)) from None
        last = self._last_snapshot
        if last is not None and last[0] is not None:
            view, trouble, offer_history, timing = last
            self._snapshot(view, trouble, offer_history, self.controller.live_status(self._shown), timing)

    def _do_use_history(self, command: wire.Command, reply: Reply) -> None:
        if self.controller.state.data != DATA_HISTORY:
            self.controller.set_data(DATA_HISTORY)
            self._data_changed()
            self.controller.save()

    def _fit_when(self) -> None:
        """Saved history: a time the symbol's data does not cover moves to its last moment (as the window does
        when the symbol changes). Coming from live, the time is "now", which the saved files never reach."""
        controller = self.controller
        if controller.is_live:
            return
        covered = controller.coverage(controller.state.symbol)
        try:
            if covered is not None and not covered[0] <= parse_when(controller.state.when) <= covered[1]:
                controller.jump_to_latest()
        except UserError:
            pass

    def _data_changed(self) -> None:
        """Live <-> saved history: forget what was shown; a check still running belongs to the other mode."""
        controller = self.controller
        self._good = self._shown = None
        self._pending = None
        self._seq += 1
        self._reset_watch()
        self._fit_when()
        controller.save()
        self._snapshot(None, "", False, controller.live_status(None), None)
        if controller.is_live:
            self._check(auto=False, trigger="command")

    def _restart_live(self) -> None:
        """Live: another symbol, stack or style is read straight away, from "now"."""
        self.controller.selection_changed()
        self._good = None
        self._reset_watch()
        self._check(auto=False, trigger="command")

    # --- checks ---

    def _check(self, *, auto: bool, trigger: str) -> bool:
        """Ask for the check the selections describe. ``auto`` (the core by itself) never queues behind a running one."""
        if auto and self._busy:
            return False
        controller = self.controller
        try:
            request = controller.build_request()
        except UserError as problem:
            controller.due = None  # nothing to retry until the selection changes
            self._shown = None
            self._snapshot(None, str(problem), False, controller.live_status(None), None)
            return False
        if request.live:
            request = replace(request, close_on_next_bar=True)  # the feed's own setting can still turn it off
        if not auto:
            controller.save()
        self._seq += 1
        job = _Job(self._seq, request, trigger, controller.now())
        if self._busy:
            self._pending = job
        else:
            self._launch(job)
        return True

    def _launch(self, job: _Job) -> None:
        self._busy = True
        controller, inbox = self.controller, self._inbox

        def work() -> None:
            started = controller.now()
            try:
                outcome = controller.run_check(job.request)
            except Exception as error:  # run_check never raises; this is the last line of defence
                outcome = CheckOutcome(job.request, error=f"Something went wrong while checking ({type(error).__name__}).")
            inbox.put(("result", job, outcome, started))

        assert self._run_check is not None
        self._run_check(work)
        self._emit_state()

    def _result(self, job: _Job, outcome: CheckOutcome, started: pd.Timestamp) -> None:
        self._busy = False
        if self._pending is not None:
            following, self._pending = self._pending, None
            self._launch(following)  # the newer request wins; this result is not shown
            return
        controller = self.controller
        if job.seq != self._seq or outcome.request.live != controller.is_live:
            self._emit_state()
            return  # asked before the data source or the selection changed
        controller.accept(outcome)
        ready = controller.now()
        follow = outcome.request.live and outcome.request.follow
        if self.journal is not None and follow and outcome.verdict is not None:
            entry = next((chart for chart in outcome.charts if chart.role == "entry"), None)
            self.journal.observe(  # never raises; before the snapshot, which shows it
                outcome.verdict, follow=True, now=ready, bars=entry.candles if entry is not None else ()
            )
        lag = _ms(ready - outcome.data_time) if follow and outcome.data_time is not None else None
        timing = wire.timing(
            bar_closed_at=outcome.data_time,
            detected_at=job.detected_at,
            fetch_ms=outcome.fetch_ms,
            compute_ms=outcome.compute_ms,
            lag_ms=lag,
            load_ms=outcome.load_ms,
        )
        self._render(outcome, timing)
        self._emit_state()
        if self.alerts is not None and follow and outcome.verdict is not None and not controller.is_stale(outcome, ready):
            self.alerts.consider(outcome.verdict)  # never raises; sends on its own thread. Stale bars never alert
        if outcome.request.live:
            self._record(job, outcome, started, ready, lag)

    def _render(self, outcome: CheckOutcome, timing: Message) -> None:
        """What the window draws for a finished check, as a snapshot (``CompanionApp._render_outcome``)."""
        controller = self.controller
        trouble = ""
        if outcome.verdict is None:
            good = self._good
            same = good is not None and (good.request.symbol, good.request.stack, good.request.style, good.request.direction) == (
                outcome.request.symbol, outcome.request.stack, outcome.request.style, outcome.request.direction,
            )  # fmt: skip
            if not (outcome.problem and outcome.retry and same and controller.is_live):
                self._shown = None
                self._snapshot(None, outcome.error, outcome.offer_history, controller.live_status(None), timing)
                return
            trouble, shown = outcome.error, good  # a live refresh failed: the last verdict stays, marked stale
        else:
            shown = outcome
            if outcome.request.live and outcome.request.follow:
                self._good = outcome
        assert shown is not None
        self._shown = shown
        view = controller.present(shown)
        self._snapshot(view, trouble, bool(trouble) and outcome.offer_history, controller.live_status(shown), timing)

    def _record(self, job: _Job, outcome: CheckOutcome, started: pd.Timestamp, ready: pd.Timestamp, lag: int | None) -> None:
        """One line per live check in ``timings.jsonl``. Never fails the loop."""
        closed = outcome.data_time
        line = {
            "at": wire.iso(ready),
            "trigger": job.trigger,
            "symbol": outcome.request.symbol,
            "entry": outcome.request.stack.entry,
            "follow": outcome.request.follow,
            "bar_closed_at": wire.iso(closed),
            "detected_at": wire.iso(job.detected_at),
            "detect_ms": _ms(job.detected_at - closed) if closed is not None and outcome.request.follow else None,
            "queue_ms": _ms(started - job.detected_at),
            "fetch_ms": outcome.fetch_ms,
            "compute_ms": outcome.compute_ms,
            "load_ms": outcome.load_ms,
            "lag_ms": lag,
            "ok": outcome.ok,
            "problem": outcome.problem,
            "revised": outcome.revised,
        }
        try:
            self.timings_path.parent.mkdir(parents=True, exist_ok=True)
            with self.timings_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(line, separators=(",", ":")) + "\n")
        except OSError:
            pass

    # --- the tick ---

    def _tick(self) -> None:
        controller = self.controller
        now = controller.now()
        if not controller.is_live:
            self._emit_status(controller.live_status(None, now))
            return
        self._emit_status(controller.live_status(self._shown, now))
        if controller.should_refresh(now) and not self._busy:
            self._check(auto=True, trigger="schedule")
        self._watch(now)

    # --- the watcher ---

    def _reset_watch(self) -> None:
        self._watch_target = None
        self._next_peek = None
        self._last_tick = None
        self._triggered_for = None
        self._watch_failures = 0

    def _watch(self, now: pd.Timestamp) -> None:
        controller = self.controller
        if not controller.follow or self._peeking or self._busy:
            return  # while a check runs it holds the link and is reading the same bars anyway
        if self._next_peek is not None and now < self._next_peek:
            return
        try:
            entry = controller.resolve_stack().entry
        except UserError:
            return
        target = (controller.state.symbol, entry)
        if target != self._watch_target:
            self._reset_watch()
            self._watch_target = target
        wait = self.watch_ms if self._watch_failures < WATCH_BACKOFF_AFTER else max(self.watch_ms, WATCH_BACKOFF_MS)
        self._next_peek = now + pd.Timedelta(milliseconds=wait)
        source, inbox = controller.live_source(), self._inbox

        def look() -> None:
            try:
                seen = source.peek(*target)
            except Exception:  # a source without peek, or one that failed: the scheduler carries on
                seen = None
            inbox.put(("peek", target, seen))

        self._peeking = True
        assert self._run_watch is not None
        self._run_watch(look)

    def _peeked(self, target: tuple[str, str], seen: Any) -> None:
        self._peeking = False
        controller = self.controller
        if target != self._watch_target or not (controller.is_live and controller.follow):
            return  # the selection moved on while the peek ran
        if seen is None:
            self._watch_failures += 1
            return
        self._watch_failures = 0
        now = controller.now()
        bars = seen.bars
        opened, newest = bars.index[-1], bars.iloc[-1]
        closes = bar_close_times(bars.iloc[-1:], seen.timeframe)[0]
        candle = wire.candle_from_bar(opened, newest, seen.timeframe, closes, now)
        key = (candle.time, candle.open, candle.high, candle.low, candle.close, candle.forming)
        if key != self._last_tick:
            self._last_tick = key
            self._emit(wire.tick(seen.timeframe, candle, candle.close))
        self._maybe_check_closed(seen.followed_close)

    def _maybe_check_closed(self, followed: pd.Timestamp | None) -> None:
        """TradingView has opened the bar after ``followed``: check now rather than at close plus settle."""
        controller = self.controller
        if followed is None or controller.live_time is None or not controller.state.auto_refresh or self._busy:
            return
        closed = wire.new_york(followed).tz_localize(None)
        if closed <= controller.live_time or closed == self._triggered_for:
            return
        try:
            allowed = bool(controller.live_source().settings().close_on_next_bar)
        except Exception:
            allowed = False
        if allowed and self._check(auto=True, trigger="watch"):
            self._triggered_for = closed  # once per bar: if that check does not bring it, the scheduler's ladder does

    # --- messages ---

    def _journal_view(self, view: Any) -> Message | None:
        """The journal for the verdict on screen: live only (saved history keeps its snapshot as it was)."""
        shown = self._shown
        if view is None or self.journal is None or shown is None or shown.verdict is None or not self.controller.is_live:
            return None
        try:
            note = _journal_note(self.controller, shown.verdict.stack.name)
        except Exception:  # noqa: BLE001 - a note must never break a snapshot
            note = ""
        return self.journal.view(shown.verdict, note)

    def _emit(self, message: Message) -> None:
        self.latest[message["type"]] = message
        for listener in list(self._listeners):
            try:
                listener(message)
            except Exception:  # noqa: BLE001 - one broken listener must not stop the loop
                pass

    def _emit_hello(self, force: bool = False) -> None:
        options = wire.options(self.controller)
        if force or options != self._options:
            self._options = options
            self._emit(wire.hello(options, wire.state(self.controller, self._busy)))

    def _emit_state(self, force: bool = False) -> None:
        message = wire.state_message(wire.state(self.controller, self._busy))
        if force or message != self._state:
            self._state = message
            self._emit(message)

    def _emit_status(self, status: LiveStatus, force: bool = False) -> None:
        message = wire.status_message(status)
        if force or message != self._status:
            self._status = message
            self._emit(message)

    def _snapshot(self, view: Any, error: str, offer_history: bool, status: LiveStatus, timing: Message | None) -> None:
        self._snapshots += 1
        self._last_snapshot = (view, error, offer_history, timing)
        self._emit(wire.snapshot(self._snapshots, view, error, offer_history, status, timing, self._journal_view(view)))
        self._emit_status(status, force=True)  # so a client that only follows status messages agrees with the snapshot


def _journal_note(controller: CompanionController, stack: str) -> str:
    return controller.stack_notes().get(stack, "")


def _ms(delta: pd.Timedelta) -> int:
    return int(round(pd.Timedelta(delta).total_seconds() * 1000))
