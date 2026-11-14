"""Display-free logic of the companion window.

Everything the window decides lives here so it can be tested without a display:

- what the drop-downs offer (always read from the registries, never listed here)
- turning the selections into a ``TimeframeStack`` and a check request
- stepping the analysis time by one entry-timeframe bar
- running a check and turning any failure into a readable sentence
- which side the trader asked for (Auto / Long / Short) and passing it to the engine
- turning a ``Verdict`` into the rows the window draws: the suggestion and the state of
  its idea, the steps, the trade plan and, behind "Details", the read and the checklist
- the risk / reward tool on the entry chart, and the next step's level on its chart
- the three charts: which candles (never one after the analysis time), which marks on
  which chart, how far to zoom
- remembering the selections between runs, and the display options (text size, direction
  colours, chart overlays, bars shown per chart)
- the live mode: where the bars come from (TradingView or the saved history), when the
  next automatic check is due, whether a verdict is stale, what to say when TradingView
  cannot be read

``companion.app`` holds the Tk widgets and nothing else.
"""

from __future__ import annotations

import json
import math
import os
import threading
import time
import traceback
from dataclasses import asdict, dataclass, field, fields, replace
from pathlib import Path
from typing import Any, Callable, get_args, get_type_hints

import pandas as pd

from companion import bars as _bars
from companion import engine as _engine
from companion import timeframes as _timeframes
from companion.styles import base as _styles
from companion.tradingview import symbols as _tv_symbols
from companion.tradingview.errors import TradingViewError
from companion.types import LookFor, MarkupItem, PositionPlan, TimeframeStack, Verdict

CUSTOM_CHOICE = "Custom…"
WHEN_FORMAT = "%Y-%m-%d %H:%M"
STATE_DIR_ENV = "TRADING_COMPANION_HOME"
STATE_FILE_NAME = "ui_state.json"
ERROR_LOG_NAME = "last_error.log"

# Where the bars come from. The labels are what the Data drop-down shows.
DATA_LIVE = "live"
DATA_HISTORY = "history"
DATA_LABELS: dict[str, str] = {DATA_LIVE: "TradingView (live)", DATA_HISTORY: "Saved history"}
# The side the trader looks for. "" lets the style propose the idea itself.
SIDE_AUTO = ""
SIDE_LABELS: dict[str, str] = {SIDE_AUTO: "Auto", "long": "Long", "short": "Short"}
# Seconds to wait before reading TradingView again: after a failed read, and after a bar
# that was due did not show up (a late tick, a holiday, delayed data). Both back off.
RETRY_SECONDS = (5, 10, 20, 30)
LATE_SECONDS = (2, 3, 5, 10, 15, 30)
STALE_GRACE = pd.Timedelta(seconds=20)  # on top of one entry bar, before a verdict is called stale

# Display options. The keys are what is saved; the labels are what the menus show.
TEXT_SIZES: dict[str, float] = {"normal": 1.0, "large": 1.25, "larger": 1.5}
TEXT_SIZE_LABELS: dict[str, str] = {"normal": "Normal", "large": "Large", "larger": "Larger"}
COLOUR_SCHEMES: dict[str, str] = {"green_red": "Green / red", "blue_orange": "Blue / orange", "mono": "Monochrome"}
OVERLAYS: dict[str, str] = {
    "level_names": "Level names",
    "zones": "Zones",
    "marker_labels": "Marker labels",
    "rr_box": "Risk / reward box",
}
CHART_BARS = 160  # closed candles fetched per chart; the window draws the most recent that fit
MIN_BARS = 10  # the closest a chart zooms in

# Data-quality notes that are about the historical files, not about any style.
MIN_RELIABLE_TIMEFRAME: dict[str, str] = {"GC": "1h"}

Coverage = tuple[pd.Timestamp, pd.Timestamp]  # naive New York wall clock: first moment, last moment


class UserError(Exception):
    """A problem the trader can fix; the message is shown as it is."""


# --- state ------------------------------------------------------------------------


def state_dir() -> Path:
    """Folder for the remembered selections: ``~/.trading_companion`` unless overridden."""
    override = os.environ.get(STATE_DIR_ENV)
    return Path(override) if override else Path.home() / ".trading_companion"


@dataclass
class UiState:
    """What the window remembers between runs. Empty strings mean "use the default"."""

    symbol: str = ""
    stack: str = ""  # a configured stack name, or CUSTOM_CHOICE
    custom_bias: str = ""
    custom_setup: str = ""
    custom_entry: str = ""
    style: str = ""
    when: str = ""  # New York time, WHEN_FORMAT
    hide_advisory: bool = False
    collapse_inactive: bool = True
    show_details: bool = True
    geometry: str = ""
    data: str = ""  # DATA_LIVE or DATA_HISTORY
    auto_refresh: bool = True  # live mode: check again by itself when an entry bar closes
    direction: str = ""  # the side to look for: "" (auto), "long" or "short"
    # display options
    text_size: str = "normal"  # a key of TEXT_SIZES
    colours: str = "green_red"  # a key of COLOUR_SCHEMES
    show_level_names: bool = True
    show_zones: bool = True
    show_marker_labels: bool = True
    show_rr_box: bool = True
    bars_bias: int = 0  # candles shown on the chart of each role; 0 lets the window fit them
    bars_setup: int = 0
    bars_entry: int = 0


_CHOICES: dict[str, dict[str, Any]] = {"text_size": TEXT_SIZES, "colours": COLOUR_SCHEMES}


def _usable(name: str, value: object, default: object) -> bool:
    """Whether a saved value can be taken as it is: the field's own type and, for an option, one it offers."""
    if type(value) is not type(default):  # a bool is not a number of bars
        return False
    if name in _CHOICES:
        return value in _CHOICES[name]
    if name.startswith("bars_"):
        return value == 0 or MIN_BARS <= value <= CHART_BARS + 1  # type: ignore[operator]
    return True


def load_state(path: Path) -> UiState:
    """The saved state; defaults when the file is missing, unreadable or malformed."""
    state = UiState()
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return state
    if not isinstance(data, dict):
        return state
    for item in fields(UiState):
        value = data.get(item.name)
        if _usable(item.name, value, getattr(state, item.name)):
            setattr(state, item.name, value)
    return state


def save_state(state: UiState, path: Path) -> bool:
    """Write the state; ``False`` when the folder cannot be written (never raises)."""
    try:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(state), indent=2), encoding="utf-8")
    except OSError:
        return False
    return True


# --- time -------------------------------------------------------------------------

_GRID_ANCHOR = pd.Timestamp("1970-01-04 18:00")  # a Sunday 18:00: every bar grid starts here
_SESSION_CLOSE = pd.Timedelta(hours=17)
_SESSION_OPEN = pd.Timedelta(hours=18)


def parse_when(text: str) -> pd.Timestamp:
    """A typed date and time as a naive New York minute; ``UserError`` when unreadable."""
    cleaned = " ".join(str(text).split())
    if not cleaned:
        raise UserError("Enter the date and time to analyse, for example 2026-02-18 10:15 (New York time).")
    try:
        moment = pd.Timestamp(cleaned)
    except (ValueError, TypeError, OverflowError):
        moment = pd.NaT
    if moment is pd.NaT:
        raise UserError(f"I could not read “{cleaned}” as a date and time. Use the form 2026-02-18 10:15 (New York time).")
    if moment.tzinfo is not None:
        moment = moment.tz_convert(_bars.BARS_TIMEZONE).tz_localize(None)
    return moment.floor("min")


def format_when(moment: pd.Timestamp) -> str:
    return pd.Timestamp(moment).strftime(WHEN_FORMAT)


def _grid_minutes(timeframe: str) -> int:
    frame = _timeframes.parse_timeframe(timeframe)
    return frame.minutes if frame.minutes is not None else frame.nominal_minutes


def _holds_no_trading(close: pd.Timestamp, minutes: int) -> bool:
    """True when the bar closing at ``close`` lies wholly inside the daily break
    (17:00-18:00) or the weekend (Friday 17:00 - Sunday 18:00). Holidays are not known."""
    opened = close - pd.Timedelta(minutes=minutes)
    day = opened.normalize()
    if opened >= day + _SESSION_CLOSE and close <= day + _SESSION_OPEN:
        return True
    friday = day - pd.Timedelta(days=(opened.weekday() - 4) % 7)
    return opened >= friday + _SESSION_CLOSE and close <= friday + pd.Timedelta(days=2) + _SESSION_OPEN


def step_moment(moment: pd.Timestamp, timeframe: str, direction: int) -> pd.Timestamp:
    """The next (``direction`` > 0) or previous close of a ``timeframe`` bar.

    Bars sit on the 18:00 New York session grid the engine uses, so a time between two
    closes snaps to the neighbouring close. Closes of bars that hold no trading (the
    daily break, the weekend) are skipped, so one step from Friday 17:00 lands on the
    first bar of Sunday evening.
    """
    minutes = _grid_minutes(timeframe)
    since = int((pd.Timestamp(moment) - _GRID_ANCHOR).total_seconds() // 60)
    forward = direction > 0
    slot = since // minutes + 1 if forward else -(-since // minutes) - 1
    for _ in range(20_000):
        candidate = _GRID_ANCHOR + pd.Timedelta(minutes=slot * minutes)
        if not _holds_no_trading(candidate, minutes):
            return candidate
        slot += 1 if forward else -1
    return candidate


# --- data -------------------------------------------------------------------------


def data_coverage(symbol: str, data_dir: Path | None = None) -> Coverage | None:
    """First and last moment the historical file of ``symbol`` covers, or ``None``.
    ``data_dir``: the folder of the minute files (default ``companion.bars.DATA_DIR``)."""
    path = Path(data_dir if data_dir is not None else _bars.DATA_DIR) / f"{symbol.lower()}_minute.csv"
    try:
        with path.open("rb") as handle:
            handle.readline()
            first = handle.readline()
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - 4096))
            tail = [line for line in handle.read().splitlines() if line.strip()]
        if not first.strip() or not tail:
            return None
        start, last = (
            _timeframes.to_new_york(line.split(b",", 1)[0].decode("ascii")).tz_localize(None)
            for line in (first, tail[-1])
        )
    except (OSError, ValueError, IndexError):
        return None
    return start, last + pd.Timedelta(minutes=1)


class SessionBarSource:
    """One ``BarSource`` for the whole session of the window.

    It opens the minute file on a window around the moments asked for, with room on
    both sides, so walking a session candle by candle does not reload anything. Bars
    come from ``HistoricalBarSource.get_bars``, which returns only bars closed at
    ``as_of``; the extra room ahead is never handed out early.
    """

    AHEAD = pd.Timedelta(days=7)
    BEHIND = pd.Timedelta(days=21)
    _MARGIN = 1.6  # calendar time per bar of nominal length (weekends, holidays, gaps)

    def __init__(self, data_dir: Path | None = None) -> None:
        self._data_dir = data_dir
        self._loaded: dict[str, tuple[pd.Timestamp, pd.Timestamp, _bars.HistoricalBarSource]] = {}
        self._lock = threading.Lock()
        self.load_seconds = 0.0  # wall clock spent opening minute files, all reads together (``CheckOutcome.load_ms``)

    description = _bars.HistoricalBarSource.description

    def has_symbol(self, symbol: str) -> bool:
        return symbol.upper() in self._loaded

    def get_bars(self, symbol: str, timeframe: str, as_of: _bars.TimeLike, lookback: int) -> pd.DataFrame:
        moment = _timeframes.to_new_york(as_of)
        nominal = pd.Timedelta(minutes=_timeframes.parse_timeframe(timeframe).nominal_minutes)
        start = moment - nominal * (lookback + 2) * self._MARGIN - pd.Timedelta(days=10)
        key = symbol.upper()
        with self._lock:
            current = self._loaded.get(key)
            if current is None or current[0] > start or current[1] < moment:
                begin, end = start - self.BEHIND, moment + self.AHEAD
                if current is not None:
                    begin, end = min(begin, current[0]), max(end, current[1])
                opened = time.perf_counter()
                try:
                    current = (begin, end, _bars.HistoricalBarSource(self._data_dir, start=begin, end=end))
                    current[2].minute_bars(key)  # load now, inside the lock
                finally:
                    self.load_seconds += time.perf_counter() - opened
                self._loaded[key] = current
        return current[2].get_bars(symbol, timeframe, as_of, lookback)


# --- a check ----------------------------------------------------------------------


@dataclass(frozen=True)
class CheckRequest:
    symbol: str
    when: pd.Timestamp  # naive New York minute
    stack: TimeframeStack
    style: str
    live: bool = False  # read TradingView rather than the saved history
    follow: bool = False  # live only: analyse "now" (the last closed entry bar), whatever ``when`` says
    direction: str = ""  # "" (the style proposes the idea), "long" or "short"
    # live only: an entry bar TradingView has already followed with a newer one counts as closed
    # before the settle time (``TradingViewBarSource.refresh``). The headless core asks for it;
    # ``close_on_next_bar: false`` in companion/config/symbols.json turns it off.
    close_on_next_bar: bool = False


@dataclass(frozen=True)
class CheckOutcome:
    request: CheckRequest
    verdict: Verdict | None = None
    error: str = ""
    charts: tuple["ChartView", ...] = ()
    chart_problem: str = ""  # why there are no charts, when the verdict itself is fine
    # live mode only
    data_time: pd.Timestamp | None = None  # close of the last closed entry bar TradingView had (naive New York)
    problem: str = ""  # the kind of live-feed problem, "" when there was none
    offer_history: bool = False  # the feed itself is missing: offer the saved history
    retry: bool = False  # worth reading again without the trader doing anything
    # where the time went (wall clock): reading TradingView's entry bars; the engine and the
    # charts; and, within the engine's run but not counted in ``compute_ms``, loading bars the
    # source did not hold yet (saved history: opening the minute file; live: the first read of
    # another timeframe from TradingView). Sources report it through a ``load_seconds`` counter.
    fetch_ms: int = 0
    compute_ms: int = 0
    load_ms: int = 0
    revised: int = 0  # live: bars already held that TradingView sent again with other values

    @property
    def ok(self) -> bool:
        return self.verdict is not None


@dataclass(frozen=True)
class LiveStatus:
    """The live state the window shows beside the controls."""

    state: str  # history | connecting | live | stale | paused | past | offline
    text: str
    stale: bool = False  # the verdict on screen must not be read as current


# --- what the window draws --------------------------------------------------------

_MARKS = {True: ("pass", "PASS"), False: ("fail", "FAIL"), None: ("na", "N/A")}
_TONES = {"long": "long", "short": "short", "watch": "watch", "no_trade": "no_trade"}
# What the trader is told to do. ``Verdict.decision`` keeps its own values.
DECISION_WORDS = {"long": "TRADE LONG", "short": "TRADE SHORT", "watch": "WATCH", "no_trade": "DON'T TRADE"}
READ_WORDS = {"confirmed": "Confirmed", "waiting": "Waiting", "failed": "Failed", "not_applicable": "Not read"}
ROLE_ORDER = ("bias", "setup", "entry")


@dataclass(frozen=True)
class LevelView:
    name: str  # "Entry", "Stop", "Target 1"
    price: str
    note: str = ""  # "risk 2.20", "3.32R"


@dataclass(frozen=True)
class RowView:
    key: str
    status: str  # "pass" | "fail" | "na"
    mark: str  # the word shown beside the colour: PASS / FAIL / N/A
    label: str
    detail: str
    tags: str  # "gate · 1D"
    advisory: bool


@dataclass(frozen=True)
class GroupView:
    name: str  # the group as the style names it
    title: str
    path: str  # the path family the group belongs to, "" when shared
    active: bool  # False when it belongs to the path that is not in play
    collapsed: bool
    rows: tuple[RowView, ...]
    passed: int
    failed: int
    not_evaluated: int

    @property
    def tally(self) -> str:
        parts = [f"{self.passed} of {len(self.rows)} passed"]
        if self.failed:
            parts.append(f"{self.failed} failed")
        if self.not_evaluated:
            parts.append(f"{self.not_evaluated} not evaluated")
        return ", ".join(parts)


@dataclass(frozen=True)
class ReadRow:
    """One line of the top-down read as the window shows it."""

    role: str
    timeframe: str
    status: str  # confirmed / waiting / failed / not_applicable
    word: str  # the status in a word, shown beside its mark
    headline: str
    reason: str


@dataclass(frozen=True)
class Candle:
    time: pd.Timestamp  # open time, New York
    open: float
    high: float
    low: float
    close: float
    forming: bool = False  # still open at the analysis time: built from closed lower-timeframe bars
    label: str = ""  # how the candle is named to the trader ("09:55", "Feb 17")


@dataclass(frozen=True)
class ChartMark:
    """A ``MarkupItem`` placed on one chart. ``start`` / ``end`` are candle positions."""

    kind: str  # level | zone | marker
    role: str  # reference | poi | protected | confirm | waiting | entry | stop | target
    label: str  # the short label drawn on the chart
    title: str  # the style's full label
    price: float | None = None
    top: float | None = None
    bottom: float | None = None
    start: int | None = None  # None: began before the candles shown (a marker: not on this chart)
    end: int | None = None  # None: runs to the right edge


@dataclass(frozen=True)
class RiskRewardTool:
    """The position plan as a long / short position tool on the entry chart.

    The risk zone lies between entry and stop, the reward zone between entry and target.
    Both begin at candle ``start`` (the trigger candle, or the last candle when the plan is
    only planned) and run to the right edge; nothing is drawn left of ``start``.
    """

    direction: str  # long | short
    planned: bool  # nothing has triggered: drawn dashed and labelled "planned"
    entry: float
    stop: float
    target: float
    start: int  # candle position the zones begin at
    r_multiple: float
    outcome: str = "open"  # open | target_reached | stopped
    outcome_at: int | None = None  # candle position that reached the target or the stop, when it is on the chart
    entry_note: str = ""  # the next step's words, when the level it waits on is this entry
    box: bool = True  # the risk and reward zones are drawn (the three lines always are)
    named: bool = True  # the lines carry their full names; False leaves the bare Entry / Stop / Target

    @property
    def risk_zone(self) -> tuple[float, float]:
        """(top, bottom) of the risk zone."""
        return max(self.entry, self.stop), min(self.entry, self.stop)

    @property
    def reward_zone(self) -> tuple[float, float]:
        """(top, bottom) of the reward zone."""
        return max(self.entry, self.target), min(self.entry, self.target)

    @property
    def risk_points(self) -> float:
        return abs(self.entry - self.stop)

    @property
    def reward_points(self) -> float:
        return abs(self.target - self.entry)


@dataclass(frozen=True)
class ChartView:
    role: str
    timeframe: str
    candles: tuple[Candle, ...]
    marks: tuple[ChartMark, ...]
    status: str = ""  # the read's status for this role, "" when the style gave none
    word: str = ""
    headline: str = ""
    as_of: str = ""  # the analysis time, for the "as of" line
    minutes: int = 0  # nominal length of one candle, for round time labels
    tool: RiskRewardTool | None = None  # the entry chart only


@dataclass(frozen=True)
class StepRow:
    """One step of the plan as the window shows it."""

    number: int
    status: str  # done | next | later | blocked
    word: str  # the status in a word, shown beside its mark
    timeframe: str
    label: str
    detail: str  # next: the exact condition with its price; done: what was seen; blocked: why
    price: float | None = None  # the level of the condition, when it is one price
    level_label: str = ""  # the condition's words without the price, as the chart names its line


@dataclass(frozen=True)
class PlanView:
    """Entry, stop and target as the window shows them."""

    direction: str  # long | short
    state: str  # planned | triggered
    outcome: str  # open | target_reached | stopped
    title: str  # "PLANNED LONG", "LONG"
    levels: tuple[LevelView, ...]  # Entry, Stop, Target
    note: str
    # the same levels as numbers, and where the idea stands, for a client that draws its own
    entry: float | None = None
    stop: float | None = None
    target: float | None = None
    r_multiple: float | None = None
    timeframe: str = ""  # the entry timeframe the levels belong to
    since: pd.Timestamp | None = None  # triggered: open of the trigger bar; planned: open of the last closed entry bar
    outcome_at: pd.Timestamp | None = None  # open of the entry bar that reached the target or the stop
    last: float | None = None  # last closed entry-timeframe close
    r_now: float | None = None  # triggered: how far ``last`` is from the entry, in multiples of the risk


@dataclass(frozen=True)
class VerdictView:
    decision: str  # the raw decision, e.g. "no_trade"
    decision_word: str  # "DON'T TRADE"
    tone: str  # colour family: long / short / watch / no_trade / neutral
    headline: str  # symbol, time, stack, style
    bias: str
    path: str
    stage: str
    levels: tuple[LevelView, ...]
    has_levels: bool
    invalidation: str
    summary: str
    groups: tuple[GroupView, ...]
    hidden_advisory: int = 0
    notes: tuple[str, ...] = field(default_factory=tuple)
    read: tuple[ReadRow, ...] = ()  # highest timeframe first
    why: str = ""
    waiting_for: str = ""
    direction: str = ""  # "long" / "short" when the path in play has a side, for the charts' colours
    charts: tuple[ChartView, ...] = ()
    chart_problem: str = ""
    source_note: str = ""
    last: LevelView | None = None  # close of the last closed entry-timeframe bar, and how far it is from the entry
    # the side asked for, the suggestion with the state of its idea, the steps and the plan
    requested: str = ""  # "" (auto) | long | short
    idea: str = ""  # the side of the idea described, "" when there is none
    suggestion: str = ""  # the decision as the window words it: "TRADE LONG", "WATCH · SHORT", "LONG · TARGET REACHED"
    suggestion_tone: str = "neutral"
    idea_state: str = ""  # one line on where the idea stands: planned / triggered / open / finished
    idea_alert: bool = False  # the state qualifies the suggestion (finished, stopped, or the entry is far behind price)
    auto_note: str = ""  # a forced side the style itself reads differently
    steps: tuple[StepRow, ...] = ()
    plan: PlanView | None = None
    look_for: LookFor | None = None  # what to look for while the setup is ahead (display only)


def path_families() -> tuple[str, ...]:
    """The path names a verdict can carry, read from the ``Verdict`` contract."""
    try:
        names = get_args(get_type_hints(Verdict)["path_family"])
    except Exception:  # an unusual annotation must not break the window
        names = ()
    return tuple(name for name in names if isinstance(name, str) and name != "none")


def group_path(group: str, families: tuple[str, ...] | None = None) -> str:
    """The path family a checklist group belongs to (its first word), or ``""``."""
    words = group.strip().lower().split()
    known = path_families() if families is None else families
    return words[0] if words and words[0] in known else ""


def _price(value: float) -> str:
    return f"{value:,.2f}"


def level_rows(verdict: Verdict) -> tuple[LevelView, ...]:
    if verdict.entry is None or verdict.stop is None:
        return ()
    risk = abs(verdict.entry - verdict.stop)
    rows = [LevelView("Entry", _price(verdict.entry)), LevelView("Stop", _price(verdict.stop), f"risk {_price(risk)}")]
    for number, target in enumerate(verdict.targets, start=1):
        multiple = f"{abs(target - verdict.entry) / risk:.2f}R" if risk > 0 else "R n/a"
        rows.append(LevelView(f"Target {number}", _price(target), multiple))
    return tuple(rows)


def _minutes(label: str) -> int:
    try:
        return _timeframes.parse_timeframe(label).nominal_minutes
    except ValueError:
        return -1


def read_rows(verdict: Verdict) -> tuple[ReadRow, ...]:
    """The style's top-down read, highest timeframe first whatever order it came in."""
    rows = [
        ReadRow(step.role, step.timeframe, step.status, READ_WORDS.get(step.status, step.status.title()), step.headline, step.reason)
        for step in verdict.read
    ]
    rows.sort(key=lambda row: -_minutes(row.timeframe))  # stable: equal or unknown labels keep the style's order
    return tuple(rows)


# --- charts -----------------------------------------------------------------------

_CHART_ROLES = {"reference", "poi", "protected", "confirm", "waiting", "entry", "stop", "target"}
_ALWAYS_IN_VIEW = {"entry", "stop", "target", "confirm", "waiting", "protected", "poi", "next"}
STEP_WORDS = {"done": "Done", "next": "Next", "later": "Later", "blocked": "Blocked"}
LATE_SHARE = 0.5  # an open idea whose last close is at least this far on the way to its target is called late


def _forming_candle(closed: pd.DataFrame, timeframe: str, entry: pd.DataFrame, as_of: pd.Timestamp) -> Candle | None:
    """The candle of ``timeframe`` still open at ``as_of``, built only from the closed
    entry-timeframe bars that open at or after the close of its last closed candle."""
    if not len(closed) or not len(entry):
        return None
    last_close = _bars.bar_close_times(closed.iloc[-1:], timeframe)[0]
    inside = entry[entry.index >= last_close]
    if not len(inside):
        return None
    opened = last_close
    for _ in range(1000):  # move past candles that hold no bars at all (weekend, holiday)
        following = _timeframes.bar_close_time(opened, timeframe)
        if following > inside.index[0]:
            break
        opened = following
    return Candle(
        time=opened,
        open=float(inside["open"].iloc[0]),
        high=float(inside["high"].max()),
        low=float(inside["low"].min()),
        close=float(inside["close"].iloc[-1]),
        forming=True,
        label=_timeframes.candle_label(opened, timeframe, as_of),
    )


def _place(item: MarkupItem, opens: pd.DatetimeIndex) -> ChartMark | None:
    role = (item.role or "reference").strip().lower()
    if role not in _CHART_ROLES:
        return None

    def locate(moment: object) -> int | None:
        if moment is None or not len(opens):
            return None
        position = int(opens.searchsorted(_timeframes.to_new_york(moment), side="right")) - 1  # type: ignore[arg-type]
        return position if position >= 0 else None

    start, end = locate(item.start), locate(item.end)
    if item.kind == "marker" and (start is None or item.price is None):
        return None  # the candle it points at is older than the candles shown
    if item.end is not None and end is None:
        return None  # it ended before the candles shown
    if item.kind == "zone" and (item.top is None or item.bottom is None):
        return None
    if item.kind == "level" and item.price is None:
        return None
    return ChartMark(item.kind, role, item.short or item.label, item.label, item.price, item.top, item.bottom, start, end)


def _shared_marks(
    markup: tuple[MarkupItem, ...], timeframe: str, opens: pd.DatetimeIndex, own: list[ChartMark]
) -> list[ChartMark]:
    """The shared levels of the other timeframes, for this chart: the levels the whole chain
    is read against, so the bias, setup and entry charts show the same lines under the same
    names. A level this chart already draws at that price is not drawn twice."""
    taken = [mark.price for mark in own if mark.kind == "level" and mark.price is not None]
    out: list[ChartMark] = []
    for item in markup:
        if not item.shared or item.timeframe == timeframe or item.kind != "level" or item.price is None:
            continue
        if any(abs(item.price - price) <= 1e-9 * max(1.0, abs(price)) for price in taken):
            continue
        # its start (a moment) lands on this chart's candle that holds it, or on the left edge
        mark = _place(item, opens)
        if mark is not None:
            out.append(mark)
            taken.append(item.price)
    return out


def build_charts(
    source: _bars.BarSource,
    symbol: str,
    stack: TimeframeStack,
    as_of: object,
    markup: tuple[MarkupItem, ...] = (),
    bars: int = CHART_BARS,
) -> tuple[ChartView, ...]:
    """One chart per role, highest timeframe first, as of ``as_of``.

    Candles are the closed bars ``source`` hands out for ``as_of`` (the same call the
    styles use, so never a bar that closes later). The bias and setup charts end with
    their still-forming candle, built from closed entry-timeframe bars only. Each
    markup item goes to the chart of its own timeframe.
    """
    moment = _timeframes.to_new_york(as_of)  # type: ignore[arg-type]
    ratio = _minutes(stack.bias) / max(1, _minutes(stack.entry))
    entry = source.get_bars(symbol, stack.entry, moment, int(min(6000, max(bars, math.ceil(ratio) + 10))))
    charts = []
    for role in ROLE_ORDER:
        timeframe = getattr(stack, role)
        frame = entry.iloc[-bars:] if role == "entry" else source.get_bars(symbol, timeframe, moment, bars)
        candles = [
            Candle(when, float(row.open), float(row.high), float(row.low), float(row.close), False, _timeframes.candle_label(when, timeframe, moment))
            for when, row in zip(frame.index, frame.itertuples())
        ]
        if role != "entry":
            forming = _forming_candle(frame, timeframe, entry, moment)
            if forming is not None:
                candles.append(forming)
        opens = pd.DatetimeIndex([candle.time for candle in candles])
        marks = [mark for mark in (_place(item, opens) for item in markup if item.timeframe == timeframe) if mark is not None]
        marks += _shared_marks(markup, timeframe, opens, marks)
        charts.append(
            ChartView(role, timeframe, tuple(candles), tuple(marks), as_of=moment.strftime("%H:%M"), minutes=max(0, _minutes(timeframe)))
        )
    return tuple(charts)


def chart_window(chart: ChartView, fit: int, most: int | None = None) -> int:
    """Position of the first candle to draw: the last ``fit`` candles, reaching further
    back (up to ``most``) when a mark starts earlier, so what the read relied on is on screen."""
    total = len(chart.candles)
    fit = max(1, fit)
    most = max(fit, most if most is not None else fit * 2)
    starts = [mark.start for mark in chart.marks if mark.start is not None]
    if chart.tool is not None:
        starts.append(chart.tool.start)  # the trigger candle stays on screen
    needed = total - min(starts) + 3 if starts else 0
    return total - min(total, max(fit, min(needed, most)))


def _mark_prices(mark: ChartMark) -> list[float]:
    return [value for value in (mark.price, mark.top, mark.bottom) if value is not None]


def chart_price_range(chart: ChartView, first: int = 0, reach: float = 2.5) -> tuple[float, float]:
    """Low and high of the price axis: the candles drawn plus the marks.

    Entry, stop, target, what confirmed or protects the trade and the near edge of the
    point of interest are always inside. A reference level, or the far edge of a zone,
    is left off the scale (the chart says so at its edge) when including it would
    squeeze the candles below ``1 / reach`` of the height.
    """
    candles = chart.candles[first:]
    tool = [chart.tool.entry, chart.tool.stop, chart.tool.target] if chart.tool is not None else []
    if not candles:
        prices = [price for mark in chart.marks for price in _mark_prices(mark)] + tool
        return (min(prices), max(prices)) if prices else (0.0, 1.0)
    low, high = min(candle.low for candle in candles), max(candle.high for candle in candles)
    low, high = min([low, *tool]), max([high, *tool])  # the whole position tool is always on the scale
    base = max(high - low, 1e-9)
    visible = [mark for mark in chart.marks if mark.end is None or mark.end >= first]
    middle = (low + high) / 2
    optional: list[float] = []  # reference levels, and the far edge of a zone
    for mark in visible:
        prices = sorted(_mark_prices(mark), key=lambda price: abs(price - middle))
        if mark.role in _ALWAYS_IN_VIEW:
            low, high = min(low, prices[0]), max(high, prices[0])
            optional.extend(prices[1:])
        else:
            optional.extend(prices)
    limit = max(high - low, base * reach)
    for price in sorted(optional, key=lambda price: abs(price - middle)):
        if max(high, price) - min(low, price) <= limit:
            low, high = min(low, price), max(high, price)
    pad = (high - low) * 0.06 or 1.0
    return low - pad, high + pad


def nice_ticks(low: float, high: float, count: int = 6) -> list[float]:
    """Round price levels for an axis running ``low`` .. ``high``."""
    span = high - low
    if not span > 0 or count < 1:
        return []
    raw = span / count
    power = 10 ** math.floor(math.log10(raw))
    step = next(power * factor for factor in (1, 2, 2.5, 5, 10) if power * factor >= raw)
    first = math.ceil(low / step) * step
    return [round(first + index * step, 10) for index in range(int((high - first) / step) + 1)]


def last_price(verdict: Verdict, charts: tuple[ChartView, ...]) -> LevelView | None:
    """The last closed entry-timeframe close. With a plan on the table the note says how
    far price already is from the entry, in multiples of the risk: the entry is the
    trigger candle's close, which can be some candles back."""
    closed = [candle for chart in charts if chart.role == "entry" for candle in chart.candles if not candle.forming]
    if not closed:
        return None
    last = closed[-1].close
    note = ""
    if verdict.entry is not None and verdict.stop is not None and verdict.entry != verdict.stop:
        moved = (last - verdict.entry) / (verdict.entry - verdict.stop)
        note = "at the entry" if abs(moved) < 0.005 else f"{moved:+.2f}R from entry"
    return LevelView("Last", _price(last), note)


def _clock(moment: object, as_of: object) -> str:
    """A bar's open as the trader reads it: the time, with the date when it is another day."""
    opened, now = _timeframes.to_new_york(moment), _timeframes.to_new_york(as_of)  # type: ignore[arg-type]
    return opened.strftime("%H:%M") if opened.date() == now.date() else f"{opened.strftime('%b')} {opened.day} {opened.strftime('%H:%M')}"


def idea_state(verdict: Verdict) -> tuple[str, str, str, bool]:
    """``(suggestion, tone, state line, alert)``: the decision as the window words it.

    The decision itself is the style's and is not changed here. What changes is how it is
    said once its idea has moved on (rules.md open question 33): an idea whose target or
    stop has already traded is not offered as "TRADE LONG", and one whose last close is at
    least ``LATE_SHARE`` of the way to the target is called late.
    """
    decision, plan = verdict.decision, verdict.plan
    side = (plan.direction if plan is not None else verdict.idea).upper()
    word = DECISION_WORDS.get(decision, decision.replace("_", " ").upper())
    tone = _TONES.get(decision, "neutral")
    if decision == "no_trade":
        if verdict.requested:
            return f"NO {verdict.requested.upper()} SETUP", tone, f"The rules give no route to a {verdict.requested} right now.", False
        return word, tone, "", False
    if plan is None:
        if decision == "watch" and side:
            return f"{word} · {side}", tone, f"{side.capitalize()} idea, nothing to enter yet: no entry level until the steps get further.", False
        return word, tone, "", False
    if plan.state == "planned":
        return f"{word} · {side}", tone, f"Planned {side.lower()}, not triggered: the levels are a projection and move with a new extreme.", False
    since = _clock(plan.since, verdict.as_of) if plan.since is not None else "earlier"
    moved = f"{plan.r_now:+.2f}R" if plan.r_now is not None else "?"
    if plan.outcome in ("target_reached", "stopped"):
        at = _clock(plan.outcome_at, verdict.as_of) if plan.outcome_at is not None else "since"
        what = f"the {plan.r_multiple:.2f}R target {_price(plan.target)}" if plan.outcome == "target_reached" else f"the stop {_price(plan.stop)}"
        name = "TARGET REACHED" if plan.outcome == "target_reached" else "STOPPED"
        return f"{side} · {name}", "no_trade", f"Finished: {what} traded at {at}. Triggered {since}; this is not an entry now.", True
    if decision not in ("long", "short"):
        return f"{word} · {side}", tone, f"{side.capitalize()} triggered {since} and is open ({moved} from entry), but it is no longer an entry: see the blocked step.", True
    progress = (plan.last - plan.entry) / (plan.target - plan.entry) if plan.last is not None and plan.target != plan.entry else 0.0
    if progress >= LATE_SHARE:
        behind = abs(plan.last - plan.entry) if plan.last is not None else 0.0
        return (
            f"{side} · LATE", tone,
            f"Triggered {since}, still open, but late: the last close is {moved} from the entry ({_price(behind)} past it, "
            f"{progress:.0%} of the way to the target).",
            True,
        )  # fmt: skip
    return word, tone, f"Triggered {since} · open · last close {moved} from the entry.", False


def plan_view(plan: PositionPlan | None) -> PlanView | None:
    if plan is None:
        return None
    risk, reward = abs(plan.entry - plan.stop), abs(plan.target - plan.entry)
    levels = (
        LevelView("Entry", _price(plan.entry), "trigger level" if plan.state == "planned" else ""),
        LevelView("Stop", _price(plan.stop), f"risk {_price(risk)}"),
        LevelView("Target", _price(plan.target), f"{plan.r_multiple:.2f}R  ·  {_price(reward)}"),
    )
    title = f"PLANNED {plan.direction.upper()}" if plan.state == "planned" else plan.direction.upper()
    return PlanView(
        plan.direction, plan.state, plan.outcome, title, levels, plan.note,
        entry=plan.entry, stop=plan.stop, target=plan.target, r_multiple=plan.r_multiple, timeframe=plan.timeframe,
        since=_new_york_or_none(plan.since), outcome_at=_new_york_or_none(plan.outcome_at), last=plan.last, r_now=plan.r_now,
    )  # fmt: skip


def _new_york_or_none(moment: object) -> pd.Timestamp | None:
    return None if moment is None else _timeframes.to_new_york(moment)  # type: ignore[arg-type]


def tool_lines(tool: RiskRewardTool, risk_word: bool = False, reward_word: bool = False) -> list[tuple[str, float, tuple[str, ...]]]:
    """(role, price, names) of the tool's three lines; the names run from the fullest to the bare role word.

    The names carry what a colour alone would not, and the words "risk" and "reward"
    when their zone has no room for its caption. The role word itself is never cut.
    """
    if not tool.named:
        return [("entry", tool.entry, ("Entry",)), ("stop", tool.stop, ("Stop",)), ("target", tool.target, ("Target",))]
    if tool.entry_note:  # the next step waits on this very price: its words, then what the line is
        entry: tuple[str, ...] = (f"{tool.entry_note} = entry", "Next = entry", "Entry")
    elif tool.planned:
        entry = (f"Planned {tool.direction} entry", "Planned entry", "Entry")
    else:
        entry = (f"{tool.direction.capitalize()} entry", "Entry")
    stop_hit = "  · HIT" if tool.outcome == "stopped" else ""
    target_hit = "  · HIT" if tool.outcome == "target_reached" else ""
    stop_word = "Stop · risk" if risk_word else "Stop"
    target_word = "Target · reward" if reward_word else "Target"
    stop = (f"{stop_word}  −{_price(tool.risk_points)}{stop_hit}", f"{stop_word}{stop_hit}", f"Stop{stop_hit}", "Stop")
    target = (
        f"{target_word} {tool.r_multiple:.2f}R  +{_price(tool.reward_points)}{target_hit}",
        f"{target_word} {tool.r_multiple:.2f}R{target_hit}",
        f"{target_word}{target_hit}",
        f"Target{target_hit}",
        "Target",
    )
    return [("entry", tool.entry, entry), ("stop", tool.stop, tuple(dict.fromkeys(stop))), ("target", tool.target, tuple(dict.fromkeys(target)))]


def tool_captions(tool: RiskRewardTool) -> tuple[str, str]:
    """(reward, risk): the words drawn inside the two zones of the tool."""
    lead = "PLANNED  " if tool.planned else ""
    return f"{lead}REWARD  {tool.r_multiple:.2f}R", f"{lead}RISK  1R"


def risk_reward_tool(plan: PositionPlan | None, chart: ChartView) -> RiskRewardTool | None:
    """The plan placed on the entry chart's candles, or ``None`` when there is nothing to place."""
    if plan is None or not chart.candles:
        return None
    opens = pd.DatetimeIndex([candle.time for candle in chart.candles])
    last = len(chart.candles) - 1

    def locate(moment: object) -> int | None:
        if moment is None:
            return None
        position = int(opens.searchsorted(_timeframes.to_new_york(moment), side="right")) - 1  # type: ignore[arg-type]
        return position if position >= 0 else None

    planned = plan.state == "planned"
    found = locate(plan.since)
    start = last if planned else (found if found is not None else 0)  # a trigger older than the candles shown: from the first one
    return RiskRewardTool(
        direction=plan.direction,
        planned=planned,
        entry=plan.entry,
        stop=plan.stop,
        target=plan.target,
        start=min(max(start, 0), last),
        r_multiple=plan.r_multiple,
        outcome=plan.outcome,
        outcome_at=locate(plan.outcome_at),
    )


def _with_plan(verdict: Verdict, charts: tuple[ChartView, ...]) -> tuple[ChartView, ...]:
    """The next step's level on the chart of its timeframe, and the position tool on the entry chart."""
    upcoming = next((step for step in verdict.steps if step.status == "next" and step.price is not None), None)
    placed = []
    for chart in charts:
        marks = list(chart.marks)
        tool = risk_reward_tool(verdict.plan, chart) if chart.role == "entry" else None
        if tool is not None:
            # the tool carries entry, stop and target: a plain line on one of its prices would only repeat it
            carried = (tool.entry, tool.stop, tool.target)
            marks = [
                mark for mark in marks
                if not (
                    mark.kind == "level"
                    and (mark.role in ("entry", "stop", "target") or (mark.price is not None and any(abs(mark.price - price) < 1e-9 for price in carried)))
                )
            ]  # fmt: skip
        if upcoming is not None and upcoming.price is not None and upcoming.timeframe == chart.timeframe:
            price = upcoming.price
            words = f"Next: {upcoming.level_label or upcoming.label}"
            # one line per price: the next step's level replaces whatever plain line sat on it
            marks = [mark for mark in marks if not (mark.kind == "level" and mark.price is not None and abs(mark.price - price) < 1e-9)]
            if tool is not None and abs(tool.entry - price) < 1e-9:
                tool = replace(tool, entry_note=words)  # the level it waits on is the plan's entry: the tool's line says both
            else:
                marks.append(ChartMark("level", "next", words, upcoming.detail, price=price))
        placed.append(replace(chart, marks=tuple(marks), tool=tool))
    return tuple(placed)


def step_rows(verdict: Verdict) -> tuple[StepRow, ...]:
    return tuple(
        StepRow(
            number, step.status, STEP_WORDS.get(step.status, step.status.title()), step.timeframe, step.label, step.detail,
            price=step.price, level_label=step.level_label,
        )  # fmt: skip
        for number, step in enumerate(verdict.steps, start=1)
    )


def present(
    verdict: Verdict,
    *,
    hide_advisory: bool = False,
    collapse_inactive: bool = True,
    collapsed: dict[str, bool] | None = None,
    notes: tuple[str, ...] = (),
    charts: tuple[ChartView, ...] = (),
    chart_problem: str = "",
    source_note: str = "",
) -> VerdictView:
    """Turn a verdict into what the window draws.

    Rows keep the style's order and are grouped by ``CriterionResult.group``. A group
    whose name starts with a path family other than the verdict's is "not active" and
    starts collapsed when ``collapse_inactive`` is set. ``collapsed`` holds the groups
    the trader opened or closed by hand and wins over that default.
    """
    families = path_families()
    live_path = verdict.path_family if verdict.path_family in families else ""
    grouped: dict[str, list[RowView]] = {}
    hidden = 0
    for criterion in verdict.criteria:
        advisory = criterion.role.strip().lower() == "advisory"
        if advisory and hide_advisory:
            hidden += 1
            continue
        status, mark = _MARKS[criterion.passed]
        tags = " · ".join(tag for tag in (criterion.role, criterion.timeframe) if tag)
        grouped.setdefault(criterion.group or "checklist", []).append(
            RowView(criterion.key, status, mark, criterion.label, criterion.detail, tags, advisory)
        )
    groups = []
    for name, rows in grouped.items():
        path = group_path(name, families)
        active = not (path and live_path and path != live_path)
        folded = (collapsed or {}).get(name, collapse_inactive and not active)
        groups.append(
            GroupView(
                name=name,
                title=name.upper(),
                path=path,
                active=active,
                collapsed=folded,
                rows=tuple(rows),
                passed=sum(row.status == "pass" for row in rows),
                failed=sum(row.status == "fail" for row in rows),
                not_evaluated=sum(row.status == "na" for row in rows),
            )
        )
    levels = level_rows(verdict)
    read = read_rows(verdict)
    by_role = {row.role: row for row in read}
    headed = tuple(
        replace(chart, status=by_role[chart.role].status, word=by_role[chart.role].word, headline=by_role[chart.role].headline)
        if chart.role in by_role
        else chart
        for chart in charts
    )
    headed = _with_plan(verdict, headed)
    suggestion, suggestion_tone, state, alert = idea_state(verdict)
    return VerdictView(
        requested=verdict.requested,
        idea=verdict.idea,
        suggestion=suggestion,
        suggestion_tone=suggestion_tone,
        idea_state=state,
        idea_alert=alert,
        auto_note=verdict.auto_note,
        steps=step_rows(verdict),
        plan=plan_view(verdict.plan),
        look_for=verdict.look_for,
        last=last_price(verdict, charts),
        decision=verdict.decision,
        decision_word=DECISION_WORDS.get(verdict.decision, verdict.decision.replace("_", " ").upper()),
        tone=_TONES.get(verdict.decision, "neutral"),
        headline=f"{verdict.symbol}  ·  {format_when(pd.Timestamp(verdict.as_of))} New York  ·  {verdict.stack.name}  ·  {verdict.style}",
        bias=verdict.bias.upper(),
        path="—" if verdict.path_family == "none" else verdict.path_family.upper(),
        stage="—" if verdict.stage == "none" else verdict.stage.upper(),
        levels=levels,
        has_levels=bool(levels),
        invalidation=verdict.invalidation,
        summary=verdict.summary,
        groups=tuple(groups),
        hidden_advisory=hidden,
        notes=tuple(notes),
        read=read,
        why=verdict.why,
        waiting_for=verdict.waiting_for,
        direction=verdict.decision if verdict.decision in ("long", "short") else "",
        charts=headed,
        chart_problem=chart_problem,
        source_note=source_note,
    )


# --- controller -------------------------------------------------------------------


def _ms_since(start: float, end: float | None = None) -> int:
    return int(round(((time.perf_counter() if end is None else end) - start) * 1000))


def _load_seconds(source: Any) -> float:
    """The source's running total of time spent loading bars; 0 for a source that does not keep one."""
    try:
        return float(getattr(source, "load_seconds", 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _timed(analyse: Callable[[], CheckOutcome], source: Any) -> tuple[CheckOutcome, int, int]:
    """``(outcome, compute_ms, load_ms)``: the loading the source reports is taken out of the compute time."""
    started, loaded = time.perf_counter(), _load_seconds(source)
    outcome = analyse()
    total = _ms_since(started)
    load = min(total, max(0, int(round((_load_seconds(source) - loaded) * 1000))))
    return outcome, total - load, load


class CompanionController:
    """Selections in, verdict rows out. Holds the one bar source of the session."""

    def __init__(
        self,
        source: _bars.BarSource | None = None,
        state_path: Path | None = None,
        coverage: Callable[[str], Coverage | None] | None = None,
        analyze_fn: Callable[..., Verdict] | None = None,
        live_source: Any = None,
        default_data: str = DATA_HISTORY,
        clock: Callable[[], pd.Timestamp] | None = None,
    ) -> None:
        self._history_source: Any = source if source is not None else SessionBarSource()
        self._live_source: Any = live_source  # made on first use: importing it must not need TradingView
        self._default_data = default_data if default_data in DATA_LABELS else DATA_HISTORY
        self._clock = clock
        self.follow = True  # live mode: analysing "now" rather than an earlier bar of the loaded history
        self.live_time: pd.Timestamp | None = None  # close of the last closed entry bar seen (naive New York)
        self.due: pd.Timestamp | None = None  # when the next automatic check should run
        self._failures = 0
        self._late = 0
        self._last_problem = ""
        self.state_path = Path(state_path) if state_path is not None else state_dir() / STATE_FILE_NAME
        self._coverage_fn = coverage if coverage is not None else data_coverage
        self._coverage_cache: dict[str, Coverage | None] = {}
        self._analyze_fn = analyze_fn
        self.state = load_state(self.state_path)
        self.normalise()

    # --- where the bars come from ---

    @property
    def is_live(self) -> bool:
        return self.state.data == DATA_LIVE

    @property
    def source(self) -> Any:
        """The one bar source of the current data mode."""
        return self.live_source() if self.is_live else self._history_source

    def live_source(self) -> Any:
        if self._live_source is None:
            from companion.tradingview.source import TradingViewBarSource

            self._live_source = TradingViewBarSource()
        return self._live_source

    def data_choices(self) -> list[str]:
        return list(DATA_LABELS.values())

    def data_label(self) -> str:
        return DATA_LABELS.get(self.state.data, DATA_LABELS[DATA_HISTORY])

    def set_data(self, choice: str) -> None:
        """Switch between live and saved history; ``choice`` is a mode or its drop-down label."""
        mode = next((key for key, label in DATA_LABELS.items() if choice in (key, label)), None)
        if mode is None or mode == self.state.data:
            return
        self.state.data = mode
        self.follow = True
        self.live_time = None
        self.due = None
        self._failures = self._late = 0
        self._last_problem = ""
        self.normalise()

    # --- the side to look for ---

    def side_choices(self) -> list[tuple[str, str]]:
        """``(value, label)`` of the bias selector, in the order shown."""
        return list(SIDE_LABELS.items())

    def set_direction(self, choice: str) -> None:
        """Auto, Long or Short; ``choice`` is a value or its label. Anything else is Auto."""
        wanted = str(choice).strip().lower()
        self.state.direction = next(
            (value for value, label in SIDE_LABELS.items() if wanted in (value, label.lower()) and value), SIDE_AUTO
        )

    def selection_changed(self) -> None:
        """Live: another symbol, stack or style was picked, so start again from "now"."""
        self.follow = True
        self.live_time = None
        self.due = None
        self._failures = self._late = 0
        self._last_problem = ""

    def shutdown(self) -> None:
        """Let go of the link to TradingView (the feed's data series are closed; nothing is left in its page)."""
        close = getattr(self._live_source, "close", None)
        if callable(close):
            try:
                close()
            except Exception:
                pass

    def now(self) -> pd.Timestamp:
        """The clock as naive New York time."""
        moment = pd.Timestamp(self._clock()) if self._clock is not None else pd.Timestamp.now(tz=_bars.BARS_TIMEZONE)
        moment = moment.tz_convert(_bars.BARS_TIMEZONE).tz_localize(None) if moment.tzinfo is not None else moment
        return moment.floor("ms")

    # --- what the drop-downs offer (always asked fresh from the registries) ---

    def symbols(self) -> list[str]:
        if self.is_live:
            try:
                return _tv_symbols.list_symbols()  # live: whatever companion/config/symbols.json maps
            except TradingViewError:
                pass
        return list(_bars.SUPPORTED_SYMBOLS)

    def stack_names(self) -> list[str]:
        return [stack.name for stack in _timeframes.list_stacks()]

    def stack_choices(self) -> list[str]:
        return [*self.stack_names(), CUSTOM_CHOICE]

    def default_stack_name(self) -> str:
        return _timeframes.default_stack().name

    def timeframe_choices(self) -> list[str]:
        return list(_timeframes.available_timeframes())

    def style_choices(self) -> list[str]:
        return list(_styles.list_styles())

    # --- selections ---

    def normalise(self) -> None:
        """Replace anything the registries no longer offer with the default."""
        state = self.state
        if state.data not in DATA_LABELS:
            state.data = self._default_data
        if state.direction not in SIDE_LABELS:
            state.direction = SIDE_AUTO
        symbols, styles, frames = self.symbols(), self.style_choices(), self.timeframe_choices()
        if state.symbol not in symbols:
            state.symbol = symbols[0] if symbols else ""
        if state.stack not in self.stack_choices():
            state.stack = self.default_stack_name()
        if state.style not in styles:
            state.style = styles[0] if styles else ""
        default = _timeframes.default_stack()
        for name, fallback in (("custom_bias", default.bias), ("custom_setup", default.setup), ("custom_entry", default.entry)):
            if getattr(state, name) not in frames:
                setattr(state, name, fallback if fallback in frames else (frames[0] if frames else ""))
        try:
            state.when = format_when(parse_when(state.when))
        except UserError:
            state.when = format_when(self.default_when(state.symbol))

    @property
    def is_custom(self) -> bool:
        return self.state.stack == CUSTOM_CHOICE

    def resolve_stack(self) -> TimeframeStack:
        """The selected stack; ``UserError`` in plain words when it cannot be used."""
        state = self.state
        if state.stack != CUSTOM_CHOICE:
            for stack in _timeframes.list_stacks():
                if stack.name == state.stack:
                    return stack
            raise UserError(f"The stack “{state.stack}” is no longer configured. Pick another one.")
        picked = (state.custom_bias, state.custom_setup, state.custom_entry)
        if not all(picked):
            raise UserError("A custom stack needs all three timeframes: bias, setup and entry.")
        try:
            return _timeframes.make_stack(*picked)
        except ValueError as error:
            if "highest to lowest" in str(error):
                raise UserError(
                    f"{' / '.join(picked)} is not a usable stack. The three timeframes must step down in size: "
                    "bias the largest, setup in the middle, entry the smallest (for example 4h / 15m / 1m)."
                ) from None
            raise UserError(str(error)) from None

    def stack_problem(self) -> str:
        """The validation message for the current selection, ``""`` when it is fine."""
        try:
            self.resolve_stack()
        except UserError as error:
            return str(error)
        return ""

    # --- time ---

    def coverage(self, symbol: str) -> Coverage | None:
        if self.is_live:
            return None  # the saved file's span says nothing about the live feed
        key = symbol.upper()
        if key not in self._coverage_cache:
            try:
                self._coverage_cache[key] = self._coverage_fn(key)
            except Exception:
                self._coverage_cache[key] = None
        return self._coverage_cache[key]

    def default_when(self, symbol: str) -> pd.Timestamp:
        """The last moment the data covers; the current New York minute when unknown."""
        covered = self.coverage(symbol) if symbol else None
        if covered is not None:
            return covered[1]
        return pd.Timestamp.now(tz=_bars.BARS_TIMEZONE).tz_localize(None).floor("min")

    def jump_to_latest(self) -> str:
        if self.is_live:
            self.follow = True
            self.state.when = format_when(self.live_time if self.live_time is not None else self.now().floor("min"))
            return self.state.when
        self.state.when = format_when(self.default_when(self.state.symbol))
        return self.state.when

    def _step_live(self, direction: int) -> str:
        """Step through the bars TradingView has loaded. Stepping forward onto the last bar is "now" again."""
        stack = self.resolve_stack()
        if self.live_time is None:
            raise UserError("Nothing is loaded from TradingView yet. Press Check first.")
        current = self.live_time if self.follow else min(parse_when(self.state.when), self.live_time)
        moved = step_moment(current, stack.entry, direction)
        if moved >= self.live_time:
            if self.follow and direction > 0:
                raise UserError("That is the last closed bar. The next one appears by itself when it closes.")
            self.follow = True
            moved = self.live_time
        else:
            covered = None
            try:
                covered = self.live_source().coverage(self.state.symbol, stack.entry)
            except TradingViewError:
                pass
            if covered is not None and moved < covered[0].tz_localize(None):
                raise UserError(f"That is the start of the bars loaded from TradingView ({format_when(covered[0].tz_localize(None))} New York).")
            self.follow = False
        self.state.when = format_when(moved)
        return self.state.when

    def step(self, direction: int) -> str:
        """Move the analysis time one entry-timeframe bar; returns the new time text.

        Raises ``UserError`` when the stack or the time is not usable, or when the step
        would leave the data.
        """
        if self.is_live:
            return self._step_live(direction)
        stack = self.resolve_stack()
        current = parse_when(self.state.when)
        moved = step_moment(current, stack.entry, direction)
        covered = self.coverage(self.state.symbol)
        if covered is not None:
            if moved > covered[1]:
                if current >= covered[1]:
                    raise UserError(f"That is the end of the {self.state.symbol} data ({format_when(covered[1])} New York).")
                moved = covered[1]
            elif moved < covered[0]:
                raise UserError(f"That is the start of the {self.state.symbol} data ({format_when(covered[0])} New York).")
        self.state.when = format_when(moved)
        return self.state.when

    # --- checking ---

    def build_request(self) -> CheckRequest:
        """The check the current selections describe; ``UserError`` when they are not usable."""
        state = self.state
        if state.symbol not in self.symbols():
            raise UserError("Pick a symbol first.")
        if state.style not in self.style_choices():
            raise UserError("Pick a style first.")
        stack = self.resolve_stack()
        if self.is_live:
            if self.follow or self.live_time is None:  # "now": the time is filled in from TradingView's last closed bar
                when = self.live_time if self.live_time is not None else self.now().floor("min")
                return CheckRequest(state.symbol, when, stack, state.style, live=True, follow=True, direction=state.direction)
            return CheckRequest(
                state.symbol, min(parse_when(state.when), self.live_time), stack, state.style, live=True, direction=state.direction
            )
        when = parse_when(state.when)
        covered = self.coverage(state.symbol)
        if covered is not None:
            if when > covered[1]:
                raise UserError(
                    f"The {state.symbol} data ends at {format_when(covered[1])} New York. "
                    "Pick that time or an earlier one (Latest jumps there)."
                )
            if when < covered[0]:
                raise UserError(f"The {state.symbol} data starts at {format_when(covered[0])} New York. Pick a later time.")
        return CheckRequest(state.symbol, when, stack, state.style, direction=state.direction)

    def will_load(self, request: CheckRequest) -> bool:
        """True when this check has to read the symbol's history first (slow)."""
        has_symbol = getattr(self.source, "has_symbol", None)
        return callable(has_symbol) and not has_symbol(request.symbol)

    def notes_for(self, request: CheckRequest) -> tuple[str, ...]:
        floor = MIN_RELIABLE_TIMEFRAME.get(request.symbol.upper())
        if not floor or request.live:  # the note is about the saved files
            return ()
        limit = _timeframes.parse_timeframe(floor).nominal_minutes
        small = [
            label
            for label in (request.stack.bias, request.stack.setup, request.stack.entry)
            if _timeframes.parse_timeframe(label).nominal_minutes < limit
        ]
        if not small:
            return ()
        return (f"{request.symbol} history is only reliable at {floor} and above; this stack reads {', '.join(small)}. Treat the result with care.",)

    def run_check(self, request: CheckRequest) -> CheckOutcome:
        """Run the engine. Never raises: a failure comes back as a sentence.

        Safe to call off the UI thread: it changes nothing on the controller. Hand the
        result to ``accept`` on the UI thread.
        """
        started = time.perf_counter()
        if not request.live:
            history = self._history_source
            outcome, compute, load = _timed(lambda: self._analyse(request, history), history)
            return replace(outcome, compute_ms=compute, load_ms=load)
        try:
            source = self.live_source()
            held = source.last_closed(request.symbol, request.stack.entry)
            revised = 0
            if request.follow or held is None:
                early = request.close_on_next_bar and bool(getattr(source.settings(), "close_on_next_bar", False))
                update = source.refresh(request.symbol, request.stack.entry, close_on_next_bar=True) if early else source.refresh(request.symbol, request.stack.entry)
                held, revised = update.last_close, int(getattr(update, "revised", 0))
            fetched = time.perf_counter()
            data_time = pd.Timestamp(held).tz_localize(None)
            when = data_time if request.follow else min(request.when, data_time)
            request = replace(request, when=when)
            asked = request
            outcome, compute, load = _timed(lambda: self._analyse(asked, source), source)
            return replace(
                outcome, data_time=data_time, fetch_ms=_ms_since(started, fetched), compute_ms=compute, load_ms=load, revised=revised
            )
        except TradingViewError as error:
            return CheckOutcome(
                request, error=str(error), problem=error.kind, offer_history=error.is_connection, retry=error.retry, fetch_ms=_ms_since(started)
            )
        except Exception as error:  # the bridge is new code talking to someone else's program
            return self._unexpected(request, error)

    def _analyse(self, request: CheckRequest, source: Any) -> CheckOutcome:
        analyze = self._analyze_fn if self._analyze_fn is not None else _engine.analyze
        try:
            chosen = {"direction": request.direction} if request.direction else {}  # Auto: the call every style has always had
            verdict = analyze(request.symbol, format_when(request.when), request.stack, request.style, source, **chosen)
        except TradingViewError:
            raise  # run_check words it
        except (KeyError, ValueError) as error:
            message = str(error.args[0]) if error.args else str(error)
            if " " not in message.strip():  # a bare key or value: a fault inside a style, not a sentence
                return self._unexpected(request, error)
            return CheckOutcome(request, error=f"The check could not run: {message}")
        except FileNotFoundError as error:
            missing = error.filename or "the data file"
            return CheckOutcome(request, error=f"No historical data found for {request.symbol} (looked for {missing}).")
        except Exception as error:  # the window must survive anything a style throws
            return self._unexpected(request, error)
        try:
            charts = build_charts(source, request.symbol, request.stack, format_when(request.when), verdict.markup)
        except Exception as error:  # a chart must never cost the trader the verdict
            self._log_error()
            return CheckOutcome(request, verdict=verdict, chart_problem=f"The charts could not be drawn ({type(error).__name__}).")
        return CheckOutcome(request, verdict=verdict, charts=charts)

    def source_note(self) -> str:
        """Where the bars come from, as the bar source itself describes it."""
        return _bars.describe_source(self.source)

    # --- live mode: scheduling, staleness, what to say ---

    def _entry_minutes(self, request: CheckRequest | None = None) -> int:
        try:
            stack = request.stack if request is not None else self.resolve_stack()
        except UserError:
            return 5
        return _timeframes.parse_timeframe(stack.entry).nominal_minutes

    def _settle(self) -> pd.Timedelta:
        try:
            seconds = float(self.live_source().settings().settle_seconds)
        except Exception:
            seconds = 3.0
        return pd.Timedelta(seconds=seconds + 0.5)

    def accept(self, outcome: CheckOutcome, now: pd.Timestamp | None = None) -> None:
        """Take in a finished check (on the UI thread): remember the data time and plan the next one."""
        if not outcome.request.live:
            return
        moment = pd.Timestamp(now) if now is not None else self.now()
        self._last_problem = outcome.problem
        if outcome.problem:
            self._failures += 1
            wait = RETRY_SECONDS[min(self._failures, len(RETRY_SECONDS)) - 1]
            self.due = moment + pd.Timedelta(seconds=wait) if outcome.retry else None
            return
        self._failures = 0
        if outcome.data_time is None:
            self.due = None
            return
        fresh = self.live_time is None or outcome.data_time > self.live_time
        self.live_time = outcome.data_time
        if outcome.request.follow:
            self.state.when = format_when(outcome.data_time)
        closes = step_moment(outcome.data_time, outcome.request.stack.entry, 1) + self._settle()
        if closes > moment:
            self._late = 0
            self.due = closes
        else:  # the next bar should have closed already and TradingView has not shown it
            self._late = 0 if fresh else self._late + 1
            self.due = moment + pd.Timedelta(seconds=LATE_SECONDS[min(self._late, len(LATE_SECONDS) - 1)])

    def should_refresh(self, now: pd.Timestamp | None = None) -> bool:
        """Whether an automatic check is due: live, following "now", not paused, and the time has come."""
        if not self.is_live or not self.state.auto_refresh or not self.follow or self.due is None:
            return False
        return (pd.Timestamp(now) if now is not None else self.now()) >= self.due

    def set_auto_refresh(self, enabled: bool, now: pd.Timestamp | None = None) -> None:
        self.state.auto_refresh = bool(enabled)
        if enabled and self.is_live and self.follow:
            self.due = pd.Timestamp(now) if now is not None else self.now()  # catch up straight away

    def is_stale(self, outcome: CheckOutcome | None, now: pd.Timestamp | None = None) -> bool:
        """A live "now" verdict whose data is more than one entry bar old must not look current."""
        if outcome is None or not outcome.request.live or not outcome.request.follow or outcome.data_time is None:
            return False
        moment = pd.Timestamp(now) if now is not None else self.now()
        allowed = pd.Timedelta(minutes=self._entry_minutes(outcome.request)) + self._settle() + STALE_GRACE
        return moment - outcome.data_time > allowed

    def live_status(self, outcome: CheckOutcome | None, now: pd.Timestamp | None = None) -> LiveStatus:
        """One line for the window: live, stale, paused, not-now, or not connected, and when the next check is due."""
        if not self.is_live:
            return LiveStatus("history", "")
        moment = pd.Timestamp(now) if now is not None else self.now()

        def countdown() -> str:
            if self.due is None or not self.state.auto_refresh or not self.follow:
                return ""
            seconds = max(0, int(math.ceil((self.due - moment).total_seconds())))
            return f"{seconds // 60}:{seconds % 60:02d}" if seconds >= 60 else f"{seconds} s"

        def bar(closed: pd.Timestamp) -> str:
            return closed.strftime("%H:%M") if closed.date() == moment.date() else closed.strftime("%a %H:%M")

        wait = countdown()
        if self._last_problem:
            again = f"trying again in {wait}" if wait else ("press Check to try again" if self.state.auto_refresh else "paused · press Check to try again")
            return LiveStatus("offline", f"NOT CONNECTED  ·  {again}", stale=True)
        if self.live_time is None:
            return LiveStatus("connecting", "CONNECTING to TradingView…")
        last = f"last bar closed {bar(self.live_time)}"
        if not self.follow:
            return LiveStatus("past", f"NOT NOW  ·  looking back at {self.state.when[-5:]}  ·  {last}  ·  Latest returns to live")
        stale = self.is_stale(outcome, moment)
        if not self.state.auto_refresh:
            return LiveStatus("paused", f"PAUSED  ·  {last}  ·  press Check to refresh, or Resume", stale=stale)
        if stale:
            age = int((moment - self.live_time).total_seconds() // 60)
            closed = _holds_no_trading(moment.floor("min"), 1)
            why = "market closed" if closed else "no newer bar from TradingView"
            return LiveStatus("stale", f"STALE  ·  {last}, {age} min ago ({why})  ·  next look in {wait or '…'}", stale=True)
        return LiveStatus("live", f"LIVE  ·  {last}  ·  next check {self.due.strftime('%H:%M:%S') if self.due is not None else '…'} (in {wait or '…'})")

    def _unexpected(self, request: CheckRequest, error: Exception) -> CheckOutcome:
        """A fault in the rules or the data, not something the trader typed. Call while handling ``error``."""
        logged = self._log_error()
        text = str(error).strip()
        reason = f"{type(error).__name__}: {text.splitlines()[0]}" if text else type(error).__name__
        where = f" Details were saved to {logged}" if logged else ""
        return CheckOutcome(request, error=f"Something went wrong while checking {request.symbol} ({reason}).{where}")

    def _log_error(self) -> Path | None:
        path = self.state_path.parent / ERROR_LOG_NAME
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(traceback.format_exc(), encoding="utf-8")
        except OSError:
            return None
        return path

    def present(self, outcome: CheckOutcome, collapsed: dict[str, bool] | None = None) -> VerdictView:
        if outcome.verdict is None:
            raise ValueError("this check has no verdict to present")
        return present(
            outcome.verdict,
            hide_advisory=self.state.hide_advisory,
            collapse_inactive=self.state.collapse_inactive,
            collapsed=collapsed,
            notes=self.notes_for(outcome.request),
            charts=outcome.charts,
            chart_problem=outcome.chart_problem,
            source_note=self.source_note(),
        )

    # --- display options ---

    def text_scale(self) -> float:
        return TEXT_SIZES.get(self.state.text_size, 1.0)

    def set_text_size(self, choice: str) -> None:
        """A key of ``TEXT_SIZES`` or its label; anything else is Normal."""
        wanted = str(choice).strip().lower()
        self.state.text_size = next((key for key, label in TEXT_SIZE_LABELS.items() if wanted in (key, label.lower())), "normal")

    def step_text_size(self, direction: int) -> str:
        """One size up or down (Ctrl+= / Ctrl+-), stopping at the ends; returns the new key."""
        keys = list(TEXT_SIZES)
        position = keys.index(self.state.text_size) if self.state.text_size in keys else 0
        self.state.text_size = keys[min(max(position + (1 if direction > 0 else -1), 0), len(keys) - 1)]
        return self.state.text_size

    def set_colours(self, choice: str) -> None:
        """A key of ``COLOUR_SCHEMES`` or its label; anything else is green / red."""
        wanted = str(choice).strip().lower()
        self.state.colours = next((key for key, label in COLOUR_SCHEMES.items() if wanted in (key, label.lower())), "green_red")

    def overlays(self) -> dict[str, bool]:
        """Which chart overlays are on, by the keys of ``OVERLAYS``."""
        return {name: bool(getattr(self.state, f"show_{name}")) for name in OVERLAYS}

    def set_overlay(self, name: str, shown: bool) -> None:
        if name in OVERLAYS:
            setattr(self.state, f"show_{name}", bool(shown))

    def chart_bars(self, role: str) -> int:
        """Candles the trader asked to see on the chart of ``role``; 0 when the window fits them itself."""
        return int(getattr(self.state, f"bars_{role}", 0)) if role in ROLE_ORDER else 0

    def set_chart_bars(self, role: str, bars: int) -> None:
        if role in ROLE_ORDER:
            setattr(self.state, f"bars_{role}", 0 if bars <= 0 else int(min(max(bars, MIN_BARS), CHART_BARS + 1)))

    def reset_zoom(self, role: str | None = None) -> None:
        for name in ROLE_ORDER if role is None else (role,):
            self.set_chart_bars(name, 0)

    def reset_display(self) -> None:
        """Text size, direction colours, overlays and zoom back to what a new install shows."""
        fresh = UiState()
        for name in ("text_size", "colours", *(f"show_{key}" for key in OVERLAYS), *(f"bars_{role}" for role in ROLE_ORDER)):
            setattr(self.state, name, getattr(fresh, name))

    # --- persistence ---

    def save(self) -> bool:
        return save_state(self.state, self.state_path)
