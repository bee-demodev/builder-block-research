"""The WebSocket wire contract, version 1: every message the core sends or accepts.

Everything that decides what goes over the socket lives here, so the contract has one
home. JSON text frames, snake_case field names.

Server to client
----------------
- ``hello``: ``{"type": "hello", "version": 1, "options": Options, "state": State}``. Sent on
  connect, and again to everyone when the options change (switching between live and
  saved history changes the symbol list).
- ``state``: ``{"type": "state", "state": State}``. After every command and whenever
  ``busy`` flips.
- ``snapshot``: ``{"type": "snapshot", "seq", "view": VerdictView | null, "error",
  "offer_history", "status": Status, "timing": Timing | null}``. After every check.
  ``seq`` rises with every check this process runs, so a client can drop a snapshot
  older than one it already shows. It is not persisted: it starts again at 1 when the
  core restarts. A client must therefore reset its baseline on every ``hello`` (a new
  connection, or a restarted core) and accept the next snapshot whatever its ``seq``;
  the web UI does this in its reducer.
- ``status``: ``{"type": "status", "status": Status}``. When it changes (about once a
  second while live: its text counts down).
- ``tick``: ``{"type": "tick", "timeframe", "candle": Candle, "last"}``. The forming entry
  candle, for display only: it never reaches the engine.
- ``error``: ``{"type": "error", "message"}``. To the one client whose message could not
  be used.

Client to server
----------------
- ``set``: any of ``symbol``, ``stack``, ``style``, ``data``, ``when``, ``side``, plus
  ``custom_bias``, ``custom_setup``, ``custom_entry`` for the "Custom…" stack; every value
  a string of at most ``MAX_TEXT`` characters. A value that cannot be used is left as it
  was and named in one ``error`` reply; the others still apply.

  ``side`` is the bias selector: ``""`` (Auto: the style proposes the idea), ``"long"`` or
  ``"short"`` (only that side). A label (``"Auto"``, ``"Long"``, ``"Short"``, any case) is
  taken too; anything else is refused. As in the window, a new side reads the same moment
  again at once when the core is live or a verdict is on screen; there is no need to send
  ``check`` after it.
- ``check``, ``latest``, ``use_history``: no fields.
- ``step``: ``{"direction": -1 | 1}``.
- ``pause``: ``{"paused": true | false}``.
- ``journal``: ``{"key", "mark", "reason"?, "note"?}``, the trader's call on a trigger in the
  decision journal (``companion.core.journal``). ``key`` is ``Journal.trigger.key`` from the
  view; ``mark`` is ``"took"``, ``"skipped"`` or ``""`` (clear it); ``reason`` ``""`` or one of
  ``JOURNAL_REASONS`` (late, no_confluence, news, risk_too_big, other); ``note`` free text
  of at most ``MAX_TEXT`` characters. Marking again overwrites. The answer is a new
  ``snapshot`` whose view carries the updated journal; an unknown key gets an ``error``.

Shapes
------
Every key below is always present; ``| null`` marks the ones that can be null.

``Options``: ``symbols``, ``stacks``, ``timeframes``, ``styles``: ``[str]``; ``data``:
``["live", "history"]`` (the values of ``State.data``); ``data_labels``: ``{value: label}``;
``custom_stack``: the stack name that means "Custom…"; ``sides``: ``["", "long", "short"]``
(the values of ``State.side``); ``side_labels``: ``{"": "Auto", "long": "Long", "short": "Short"}``.

``State``: ``symbol``, ``stack``, ``style``, ``data``, ``when`` (``"YYYY-MM-DD HH:MM"`` New
York; ``""`` while live and nothing has been read yet), ``custom_bias``, ``custom_setup``,
``custom_entry``, ``side``: str; ``follow`` (live: analysing "now"), ``auto_refresh``,
``busy`` (a check is running), ``live``: bool.

``Status``: ``state`` (history | connecting | live | stale | paused | past | offline),
``text``, ``stale`` (the verdict on screen must not be read as current): bool.

``Timing``: ``bar_closed_at`` (live: the close of the bar analysed) | null,
``detected_at`` (when the core decided to check), ``fetch_ms`` (reading TradingView's
entry bars; 0 on saved history), ``load_ms`` (loading bars the source did not hold yet,
during the engine's run: opening the minute file on saved history, the first read of
another timeframe from TradingView live; 0 once they are held), ``compute_ms`` (the rules
and the charts, without ``load_ms``), ``lag_ms`` (live "now": from the bar's close to the
snapshot) | null. ``load_ms`` was added within version 1: a client that ignores it reads
``compute_ms`` as before, now without the loading.

``VerdictView``: what the window draws for one check.

- ``decision`` (long | short | watch | no_trade, the style's own), ``decision_word``
  ("TRADE LONG", "DON'T TRADE"), ``tone`` (long | short | watch | no_trade | neutral),
  ``headline`` (symbol · time · stack · style), ``bias``, ``path``, ``stage`` (upper case,
  "—" for none), ``levels``: ``[Level]`` (the verdict's entry, stop and every target),
  ``has_levels``, ``invalidation``, ``summary``, ``why``, ``waiting_for``, ``groups``:
  ``[Group]``, ``hidden_advisory``: int, ``notes``: ``[str]``, ``read``: ``[ReadRow]``
  (highest timeframe first), ``direction`` ("" | long | short: the side for the charts'
  colours, set only when the decision is a trade), ``charts``: ``[Chart]`` (bias, setup,
  entry), ``chart_problem``, ``source_note``, ``last``: ``Level`` | null (the last closed
  entry close, its note how far it is from the entry: "+0.19R from entry").
- The suggestion as the window shows it in its banner: ``requested`` ("" | long | short:
  the side asked for), ``idea`` ("" | long | short: the side of the idea described),
  ``suggestion`` ("TRADE SHORT", "WATCH · SHORT", "SHORT · TARGET REACHED", "LONG · LATE",
  "NO LONG SETUP"), ``suggestion_tone`` (as ``tone``; a finished idea is "no_trade"),
  ``idea_state`` (one line on where the idea stands; "" when there is none), ``idea_alert``
  (that line qualifies the suggestion: the window prefixes "⚠  " and colours it as a
  warning), ``auto_note`` (with a forced side: how the style reads it by itself; "" otherwise).
- ``steps``: ``[Step]``, what has to happen, highest timeframe first.
- ``plan``: ``Plan`` | null, the trade plan.
- ``look_for``: ``LookFor`` | null, what to look for while the setup is still ahead
  (display only; null when there is nothing to show, and absent from an older core).
- ``journal``: ``Journal`` | null, the decision journal for this view's stack. Only in a
  live snapshot (absent on saved history and from an older core); display only, it never
  changes the decision.

``Journal``: ``stack`` (the stack's name), ``note`` (its backtest note from stacks.json, ""
when none), ``trigger``: ``JournalTrigger`` | null (the trigger on screen, when the journal
has logged it), ``reasons``: ``[{"key", "label"}]`` (the skip reasons the client offers),
``stats``: ``{"taken", "skipped", "all": {"n": int, "avg_r": float | null}, "open": int,
"min_n": int}``: closed outcomes on this stack, the trader's taken and skipped triggers and
every logged trigger (the engine's baseline), average R before costs; ``open`` counts the
logged triggers still open; an ``n`` under ``min_n`` is too small to mean anything.
``JournalTrigger``: ``key``, ``side`` (long | short), ``since`` (open of the trigger bar) | null,
``mark`` ("" | took | skipped), ``reason`` ("" or a reason key), ``note``, ``outcome`` (open |
target_reached | stopped), ``result_r`` (+r_multiple at the target, -1 stopped) | null.

``Level``: ``name``, ``price`` (formatted "24,722.50"), ``note``.
``Group``: ``name``, ``title``, ``path``, ``active``, ``collapsed``, ``rows``: ``[Row]``,
``passed``, ``failed``, ``not_evaluated``, ``tally`` ("3 of 5 passed, 1 failed").
``Row``: ``key``, ``status`` (pass | fail | na), ``mark``, ``label``, ``detail``, ``tags``
("gate · 1D"), ``advisory``.
``ReadRow``: ``role`` (bias | setup | entry), ``timeframe``, ``status`` (confirmed | waiting |
failed | not_applicable), ``word``, ``headline``, ``reason``.

``Step``: ``number`` (1, 2, ...), ``status`` (done | next | later | blocked; at most one is
next), ``word`` ("Done", "Next", "Later", "Blocked"), ``timeframe``, ``label``, ``detail``
(next: the exact condition with its price; done: what was seen; blocked: why; may be ""),
``price``: float | null (the level of the condition when it is one price), ``level_label``
(the condition's words without the price, as the chart names its line: "1h close below").

``Plan``: ``direction`` (long | short), ``state`` (planned | triggered), ``outcome`` (open |
target_reached | stopped), ``title`` ("PLANNED SHORT", "SHORT"), ``levels``: ``[Level]``
(Entry, Stop, Target, worded as the window prints them), ``note``; and the same as
numbers: ``entry``, ``stop``, ``target``, ``r_multiple``: float, ``timeframe`` (the entry
timeframe), ``since`` (triggered: open of the trigger bar; planned: open of the last
closed entry bar) | null, ``outcome_at`` (open of the bar that reached the target or the
stop) | null, ``last`` (last closed entry close) | null, ``r_now`` (triggered: ``last``
from the entry in multiples of the risk) | null; ``stage_label`` (forming | actionable |
late | played_out | ""), ``age_bars`` (triggered: closed entry bars after the trigger) |
null, ``risk_adr`` (the stop as a share of the 14-day average daily range) | null,
``cost_r_mini`` / ``cost_r_micro`` (one contract's round-turn cost as a share of the risk)
| null, ``cost_note`` (those in words, "" when unknown).

``LookFor``: ``direction`` (long | short), ``timeframe`` (the timeframe to watch for the
setup, "1h"), ``entry_timeframe`` ("5m"), ``steps``: ``[{"label", "status"}]`` (status as a
``Step``'s), ``options``: ``[{"key": "A" | "B", "name", "top", "bottom", "condition"}]`` (A,
the nearest point of interest, first; B the next one beyond it, ``condition`` saying when it
comes into play; real prices), ``entry``, ``stop``, ``target`` (words: "5m close below the
run", "above the 1h C2 high", "2R, then PDL"; no price that depends on a candle not yet
formed), ``target_price``: float | null (the structural level ``target`` names),
``entry_during``: bool (the entry forms while the setup's C2 forms; false: after it).

``Chart``: ``role`` (bias | setup | entry), ``timeframe``, ``candles``: ``[Candle]`` (never
one after the analysis time), ``marks``: ``[Mark]``, ``status`` (the read's status for this
role, "" when none), ``word``, ``headline``, ``as_of``, ``minutes`` (nominal candle length),
``tool``: ``Tool`` | null (the entry chart only, when there is a plan).

``Candle``: ``time``, ``t``, ``open``, ``high``, ``low``, ``close``, ``forming``, ``label``.

``Mark``: ``kind`` (level | zone | marker), ``role`` (reference | poi | protected | confirm |
waiting | entry | stop | target | next | session; ``session`` marks are the intraday
reference levels, a layer a client shows only when asked), ``label`` (short, drawn on the chart), ``title``
(full), ``price``, ``top``, ``bottom``: float | null, ``start``, ``end``: candle position |
null (start null: began before the candles shown; end null: runs to the right edge). The
next step's level is a ``level`` mark with role ``next`` and label "Next: <level_label>"
on the chart of its timeframe, unless that price is the tool's entry (see ``entry_note``).
On the entry chart, plain level marks on the tool's three prices are left out: the tool
draws them.

``Tool``, the plan as a position tool on the entry chart: ``direction``, ``planned`` (bool:
nothing has triggered), ``entry``, ``stop``, ``target``, ``r_multiple``: float, ``start``
(candle position both zones begin at: the trigger candle, or the last candle when planned;
nothing is drawn left of it; they run to the right edge), ``outcome``, ``outcome_at``
(candle position that reached the target or the stop) | null, ``entry_note`` ("" or the
next step's words when the level it waits on is this entry: "Next: 5m close below"),
``box``, ``named`` (always true from the core: the risk / reward box and the level names
are per-device display options a client applies itself). Worked out for the client as the
window works them out:

- ``risk_zone``, ``reward_zone``: ``{"top", "bottom"}``, between entry and stop / target;
  ``risk_points``, ``reward_points``: their heights.
- ``lines``: ``[{"role": entry | stop | target, "price", "names": [str], "names_worded": [str]}]``.
  ``names`` run from the fullest to the bare role word ("Stop  −29.25", "Stop"): the
  window takes the fullest that fits, and only the last one ("Entry", "Stop", "Target")
  when level names are turned off. ``names_worded`` are the names when that line's zone
  has no room for its caption ("Stop · risk  −29.25"): the stop's for the risk zone, the
  target's for the reward zone. A line whose outcome happened ends " · HIT".
- ``captions``: ``{"reward": "PLANNED  REWARD  2.00R", "risk": "PLANNED  RISK  1R"}``, the
  words drawn inside the zones ("PLANNED  " only while planned).

The window draws the tool dashed (zones hatched, entry line dashed) while ``planned`` or
while the status is stale, and the entry line in the "next" style when ``entry_note`` is
set; a diamond marks ``outcome_at`` on the target or stop price.

Times
-----
``time`` fields are ISO-8601 with the New York offset. A candle also carries ``t``: its
New York wall-clock open time written as if it were UTC, in epoch seconds, because chart
libraries draw UTC and this makes their axis read New York time.

Version
-------
Every field added since the first release of version 1 (``side``, ``sides``,
``side_labels``, ``load_ms``, the plan, the steps, the tool, ``look_for``, ``journal`` and the
``journal`` command) is an addition, so
``version`` stays 1. The one narrowing: ``compute_ms`` no longer includes loading bars
(now ``load_ms``); a version 1 client only displays it, and it now says what its name
says. Unknown keys must be ignored by a client.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, fields, is_dataclass, replace
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from companion import timeframes as _timeframes
from companion.app_model import (
    CUSTOM_CHOICE,
    DATA_LABELS,
    SIDE_LABELS,
    Candle,
    CompanionController,
    GroupView,
    LiveStatus,
    RiskRewardTool,
    VerdictView,
    tool_captions,
    tool_lines,
)
from companion.types import BARS_TIMEZONE

VERSION = 1
SET_FIELDS = ("symbol", "stack", "style", "data", "when", "side")
CUSTOM_FIELDS = ("custom_bias", "custom_setup", "custom_entry")  # the "Custom…" stack's three timeframes
COMMANDS = ("set", "check", "step", "latest", "pause", "use_history", "journal")
MAX_TEXT = 200  # longest string value a command may carry
JOURNAL_MARKS = ("took", "skipped", "")  # "" clears the trader's call
JOURNAL_REASONS = {"late": "Late", "no_confluence": "No confluence", "news": "News", "risk_too_big": "Risk too big", "other": "Other"}

_EPOCH = pd.Timestamp("1970-01-01")


# --- times ------------------------------------------------------------------------


def new_york(moment: object) -> pd.Timestamp:
    """A moment as a New York timestamp; a naive one is taken as New York wall clock."""
    stamp = pd.Timestamp(moment)  # type: ignore[arg-type]
    if stamp.tzinfo is None:
        return stamp.tz_localize(BARS_TIMEZONE, ambiguous=True, nonexistent="shift_forward")
    return stamp.tz_convert(BARS_TIMEZONE)


def iso(moment: object | None) -> str | None:
    """ISO-8601 with the New York offset, ``None`` for no moment."""
    if moment is None or moment is pd.NaT:
        return None
    return new_york(moment).isoformat()


def wall_epoch(moment: object) -> int:
    """New York wall-clock time written as if it were UTC, in epoch seconds."""
    wall = new_york(moment).tz_localize(None)
    return int((wall - _EPOCH) // pd.Timedelta(seconds=1))


# --- values -----------------------------------------------------------------------


def candle(item: Candle) -> dict[str, Any]:
    return {
        "time": iso(item.time),
        "t": wall_epoch(item.time),
        "open": _number(item.open),
        "high": _number(item.high),
        "low": _number(item.low),
        "close": _number(item.close),
        "forming": bool(item.forming),
        "label": item.label,
    }


def _number(value: Any) -> float | int | None:
    if isinstance(value, (bool, np.bool_)):
        raise TypeError("a flag is not a number")
    if isinstance(value, (int, np.integer)):
        return int(value)
    number = float(value)
    return number if math.isfinite(number) else None  # JSON has no NaN or infinity


def plain(value: Any) -> Any:
    """A view object as JSON values: dataclasses field for field, tuples as arrays."""
    if isinstance(value, Candle):
        return candle(value)
    if is_dataclass(value) and not isinstance(value, type):
        out = {item.name: plain(getattr(value, item.name)) for item in fields(value)}
        if isinstance(value, GroupView):
            out["tally"] = value.tally
        if isinstance(value, RiskRewardTool):
            out.update(_tool_extras(value))
        return out
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, float, np.integer, np.floating)):
        return _number(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return iso(value)
    if isinstance(value, (tuple, list)):
        return [plain(item) for item in value]
    if isinstance(value, dict):
        return {str(key): plain(item) for key, item in value.items()}
    raise TypeError(f"no wire form for {type(value).__name__}")


def _tool_extras(tool: RiskRewardTool) -> dict[str, Any]:
    """What the window works out from a risk / reward tool to draw it, so a client need not."""
    full = replace(tool, named=True)  # the client applies its own "level names" preference
    plain_lines = tool_lines(full)
    worded = {role: names for role, _price, names in tool_lines(full, risk_word=True, reward_word=True)}
    reward, risk = tool_captions(tool)
    top_bottom = lambda zone: {"top": _number(zone[0]), "bottom": _number(zone[1])}  # noqa: E731
    return {
        "risk_zone": top_bottom(tool.risk_zone),
        "reward_zone": top_bottom(tool.reward_zone),
        "risk_points": _number(tool.risk_points),
        "reward_points": _number(tool.reward_points),
        "lines": [
            {"role": role, "price": _number(price), "names": list(names), "names_worded": list(worded[role])}
            for role, price, names in plain_lines
        ],
        "captions": {"reward": reward, "risk": risk},
    }


def view(item: VerdictView | None) -> dict[str, Any] | None:
    return None if item is None else plain(item)


def status(item: LiveStatus) -> dict[str, Any]:
    return {"state": item.state, "text": item.text, "stale": bool(item.stale)}


def options(controller: CompanionController) -> dict[str, Any]:
    """What the drop-downs offer, asked fresh from the controller (and so from the registries)."""
    return {
        "symbols": controller.symbols(),
        "stacks": controller.stack_choices(),
        "stack_notes": controller.stack_notes(),  # what the backtest found, by stack name
        "timeframes": controller.timeframe_choices(),
        "styles": controller.style_choices(),
        "data": list(DATA_LABELS),  # the values ``state.data`` and ``set.data`` use
        "data_labels": dict(DATA_LABELS),  # how the Tk window names them
        "custom_stack": CUSTOM_CHOICE,
        "sides": list(SIDE_LABELS),  # the values ``state.side`` and ``set.side`` use: "" is Auto
        "side_labels": dict(SIDE_LABELS),
    }


def state(controller: CompanionController, busy: bool) -> dict[str, Any]:
    current = controller.state
    when = current.when
    if controller.is_live and controller.live_time is None:
        when = ""  # nothing read from TradingView yet: no bar time to show
    return {
        "symbol": current.symbol,
        "stack": current.stack,
        "style": current.style,
        "data": current.data,
        "when": when,
        "follow": bool(controller.follow),
        "auto_refresh": bool(current.auto_refresh),
        "busy": bool(busy),
        "live": bool(controller.is_live),
        "custom_bias": current.custom_bias,
        "custom_setup": current.custom_setup,
        "custom_entry": current.custom_entry,
        "side": current.direction,
    }


def timing(
    *, bar_closed_at: object | None, detected_at: object, fetch_ms: int, compute_ms: int, lag_ms: int | None, load_ms: int = 0
) -> dict[str, Any]:
    return {
        "bar_closed_at": iso(bar_closed_at),
        "detected_at": iso(detected_at),
        "fetch_ms": int(fetch_ms),
        "compute_ms": int(compute_ms),
        "lag_ms": None if lag_ms is None else int(lag_ms),
        "load_ms": int(load_ms),
    }


# --- messages ---------------------------------------------------------------------


def hello(options_: dict[str, Any], state_: dict[str, Any]) -> dict[str, Any]:
    return {"type": "hello", "version": VERSION, "options": options_, "state": state_}


def state_message(state_: dict[str, Any]) -> dict[str, Any]:
    return {"type": "state", "state": state_}


def snapshot(
    seq: int,
    view_: VerdictView | None,
    error_: str,
    offer_history: bool,
    status_: LiveStatus,
    timing_: dict[str, Any] | None,
    journal: dict[str, Any] | None = None,
) -> dict[str, Any]:
    shown = view(view_)
    if shown is not None and journal is not None:
        shown["journal"] = plain(journal)  # live only: a saved-history snapshot keeps the shape it always had
    return {
        "type": "snapshot",
        "seq": int(seq),
        "view": shown,
        "error": error_ or "",
        "offer_history": bool(offer_history),
        "status": status(status_),
        "timing": timing_,
    }


def status_message(status_: LiveStatus) -> dict[str, Any]:
    return {"type": "status", "status": status(status_)}


def tick(timeframe: str, candle_: Candle, last: float) -> dict[str, Any]:
    return {"type": "tick", "timeframe": timeframe, "candle": candle(candle_), "last": _number(last)}


def error(message: str) -> dict[str, Any]:
    return {"type": "error", "message": str(message)}


def dumps(message: dict[str, Any]) -> str:
    """One text frame. Refuses NaN and infinity, which browsers cannot parse."""
    return json.dumps(message, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


# --- commands ---------------------------------------------------------------------


class WireError(ValueError):
    """A client message that cannot be used; the text goes back in an ``error`` message."""


@dataclass(frozen=True)
class Command:
    type: str
    values: dict[str, str] = field(default_factory=dict)  # set: the fields to change
    direction: int = 0  # step
    paused: bool = False  # pause
    # journal: values holds "key", "mark", "reason", "note"


def parse_command(text: str | bytes) -> Command:
    """A client frame -> a ``Command``; ``WireError`` with a plain reason when it is not one."""
    if isinstance(text, bytes):
        try:
            text = text.decode("utf-8")
        except UnicodeDecodeError:
            raise WireError("Messages must be UTF-8 JSON text.") from None
    try:
        message = json.loads(text)
    except (ValueError, RecursionError):
        raise WireError("That message is not JSON.") from None
    if not isinstance(message, dict):
        raise WireError("A message must be a JSON object with a \"type\".")
    kind = message.get("type")
    if kind not in COMMANDS:
        raise WireError(f"Unknown message type {json.dumps(kind)[:60]}; expected one of: {', '.join(COMMANDS)}.")
    extra = sorted(set(message) - {"type"} - _ALLOWED.get(kind, set()))
    if extra:
        raise WireError(f"A {kind} message does not take: {', '.join(extra)}.")
    if kind == "set":
        values: dict[str, str] = {}
        for key in (*SET_FIELDS, *CUSTOM_FIELDS):
            if key in message:
                value = message[key]
                if not isinstance(value, str) or len(value) > MAX_TEXT:
                    raise WireError(f"set: {key} must be a string of at most {MAX_TEXT} characters.")
                values[key] = value
        if not values:
            raise WireError(f"set needs at least one of: {', '.join(SET_FIELDS)}.")
        return Command("set", values)
    if kind == "step":
        direction = message.get("direction")
        if isinstance(direction, bool) or direction not in (-1, 1):
            raise WireError("step needs \"direction\": -1 or 1.")
        return Command("step", direction=int(direction))
    if kind == "pause":
        paused = message.get("paused")
        if not isinstance(paused, bool):
            raise WireError("pause needs \"paused\": true or false.")
        return Command("pause", paused=paused)
    if kind == "journal":
        return Command("journal", _journal_values(message))
    return Command(kind)


def _journal_values(message: dict[str, Any]) -> dict[str, str]:
    values: dict[str, str] = {}
    for key in ("key", "mark", "reason", "note"):
        value = message.get(key, "")
        if not isinstance(value, str) or len(value) > MAX_TEXT:
            raise WireError(f"journal: {key} must be a string of at most {MAX_TEXT} characters.")
        values[key] = value
    if not values["key"]:
        raise WireError("journal needs \"key\": the trigger's key from the view.")
    if "mark" not in message or values["mark"] not in JOURNAL_MARKS:
        raise WireError(f"journal needs \"mark\": {', '.join(json.dumps(mark) for mark in JOURNAL_MARKS)}.")
    if values["reason"] and values["reason"] not in JOURNAL_REASONS:
        raise WireError(f"journal: reason must be \"\" or one of: {', '.join(JOURNAL_REASONS)}.")
    return values


_ALLOWED: dict[str, set[str]] = {
    "set": {*SET_FIELDS, *CUSTOM_FIELDS},
    "step": {"direction"},
    "pause": {"paused"},
    "journal": {"key", "mark", "reason", "note"},
}


def candle_from_bar(opened: pd.Timestamp, bar: Any, timeframe: str, close_time: pd.Timestamp, now: pd.Timestamp) -> Candle:
    """A bar of a frame as a ``Candle``; ``forming`` while its close lies after ``now``."""
    return Candle(
        time=new_york(opened),
        open=float(bar["open"]),
        high=float(bar["high"]),
        low=float(bar["low"]),
        close=float(bar["close"]),
        forming=bool(new_york(close_time) > new_york(now)),
        label=_timeframes.candle_label(opened, timeframe, new_york(now)),
    )
