"""Shared contracts for the trading companion.

Every module in ``companion`` builds on these types. Changing a field here is a
cross-module change: update the producers, the consumers and their tests together.

Bars convention (used everywhere a "bars frame" is mentioned)
-------------------------------------------------------------
A ``pandas.DataFrame`` with:

- index: tz-aware ``DatetimeIndex`` named ``timestamp`` in ``America/New_York``,
  holding the bar OPEN time, strictly increasing and unique
- columns: ``open``, ``high``, ``low``, ``close``, ``volume`` (floats)

A bar is "closed" at ``as_of`` when ``open_time + timeframe duration <= as_of``.
Nothing in the decision path may read a bar that is not closed at ``as_of``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

BARS_COLUMNS: tuple[str, ...] = ("open", "high", "low", "close", "volume")
BARS_TIMEZONE = "America/New_York"

Direction = Literal["bullish", "bearish"]
Decision = Literal["long", "short", "watch", "no_trade"]
ReadStatus = Literal["confirmed", "waiting", "failed", "not_applicable"]
TradeSide = Literal["long", "short"]
StepStatus = Literal["done", "next", "later", "blocked"]
PlanState = Literal["planned", "triggered"]
PlanOutcome = Literal["open", "target_reached", "stopped"]
StageLabel = Literal["", "forming", "actionable", "late", "played_out"]


@dataclass(frozen=True)
class TimeframeStack:
    """One selectable top-down stack. Values are timeframe labels such as
    ``1m 5m 15m 30m 1h 4h 1D 1W 1M``. Roles run from highest to lowest timeframe."""

    name: str  # shown in the drop-down, e.g. "1D / 1h / 5m"
    bias: str  # timeframe that sets directional bias
    setup: str  # timeframe where the point of interest and candle sequence form
    entry: str  # timeframe that confirms and times the entry


# --- structure events -------------------------------------------------------
# ``time`` fields are bar open times taken from the bars frame the event was found on.
# ``confirmed_at`` is the earliest moment the event is knowable without lookahead.
# ``FairValueGap.filled_at`` and ``ProtectedSwing.broken_at`` are bar CLOSE times: the
# close of the bar that filled / broke it, which is when that becomes knowable.


@dataclass(frozen=True)
class Swing:
    kind: Literal["high", "low"]
    time: datetime
    price: float
    confirmed_at: datetime
    timeframe: str


@dataclass(frozen=True)
class Sweep:
    """Price traded beyond a prior swing and closed back inside it."""

    side: Literal["high", "low"]  # which side's liquidity was taken
    time: datetime  # bar that swept
    swept_price: float  # the swing level that was taken
    extreme: float  # furthest price reached beyond the level
    swept_swing_time: datetime
    confirmed_at: datetime
    timeframe: str


@dataclass(frozen=True)
class FairValueGap:
    direction: Direction
    time: datetime  # middle candle of the three
    top: float
    bottom: float
    confirmed_at: datetime
    timeframe: str
    # CLOSE time of the first bar that closed through the far side, if any
    filled_at: datetime | None = None


@dataclass(frozen=True)
class Cisd:
    """Change in state of delivery."""

    direction: Direction  # direction delivery changed TO
    time: datetime  # bar whose close confirmed it
    level: float  # the open price that was closed through
    confirmed_at: datetime
    timeframe: str


@dataclass(frozen=True)
class ProtectedSwing:
    kind: Literal["high", "low"]
    time: datetime
    price: float
    confirmed_at: datetime
    timeframe: str
    broken_at: datetime | None = None  # CLOSE time of the bar that broke it, if any


# --- verdict ----------------------------------------------------------------


@dataclass(frozen=True)
class CriterionResult:
    key: str  # stable id, e.g. "htf_bias_directional"
    label: str  # plain-language name shown to the trader
    passed: bool | None  # None = could not be evaluated (missing data)
    detail: str  # what was observed, with prices/times
    timeframe: str | None = None
    # Where the criterion sits in its style's checklist, so a renderer can group and
    # mark criteria without knowing the style. Both are free text chosen by the style.
    group: str = ""  # e.g. "continuation c2"
    role: str = ""  # e.g. "gate", "step", "quality", "advisory"


@dataclass(frozen=True)
class MarkupItem:
    """Something to draw on the chart."""

    kind: Literal["level", "zone", "marker"]
    label: str
    timeframe: str
    price: float | None = None  # level / marker
    top: float | None = None  # zone
    bottom: float | None = None  # zone
    start: datetime | None = None
    end: datetime | None = None
    # How a chart should treat the item, so a renderer needs no knowledge of the style.
    # ``role`` is one of: "reference" (a level the read is measured against), "poi" (the
    # point of interest), "protected" (the swing that must hold), "confirm" (the candle or
    # level that confirmed), "waiting" (a level that still has to be closed through),
    # "entry", "stop", "target", "info" (context a chart may leave out). Empty means
    # "reference". ``short`` is a label of a few words for the chart.
    role: str = ""
    short: str = ""
    # True for a level the whole chain is read against (the previous bias candle's high
    # and low, the respect level, the protected swing, the trigger): it is drawn on every
    # chart of the stack, not only on its own timeframe's, so the three charts agree.
    shared: bool = False


@dataclass(frozen=True)
class ReadStep:
    """One line of the top-down read: what one role's timeframe says, in the trader's words.

    A style fills one step per role it reads, highest timeframe first, for the path that
    is in play only. Nothing here is specific to a style.
    """

    role: str  # "bias" | "setup" | "entry"
    timeframe: str  # the stack's label for that role, e.g. "1D"
    status: ReadStatus  # confirmed / waiting / failed / not_applicable
    headline: str  # a few words, e.g. "Bullish · Candle 3 forming"
    reason: str  # one sentence with the key prices; "" when there is nothing to say


@dataclass(frozen=True)
class PlanStep:
    """One thing that has to happen for the idea, in order from the highest timeframe to the entry.

    ``status``: "done" (it happened), "next" (the one thing awaited now), "later" (comes
    after the next one), "blocked" (it cannot go on as it stands: the idea is dead here, or
    a check stands in the way). At most one step is "next"; none is when the idea is
    complete or dead. Nothing here is specific to a style.
    """

    role: str  # the line of the top-down read it belongs to: "bias" | "setup" | "entry"
    timeframe: str  # the timeframe to watch for it, e.g. "5m"
    status: StepStatus
    label: str  # a few plain words, e.g. "5m turns up"
    detail: str = ""  # done: what was seen; blocked: why; next: the exact condition, with its price
    price: float | None = None  # the level of the condition, when it is one price
    level_label: str = ""  # the condition's words without the price, for the chart: "5m close above"


@dataclass(frozen=True)
class PositionPlan:
    """Entry, stop and target of the idea, and where it stands.

    ``state`` "planned": nothing has triggered. ``entry`` is the level the trigger has to
    clear, ``stop`` the current structural extreme; both move if price makes a new extreme
    first. ``state`` "triggered": the rules' own entry, stop and target, and ``outcome``
    says what price has done since (a bar that reaches both the stop and the target counts
    as stopped).
    """

    direction: TradeSide
    state: PlanState
    entry: float
    stop: float
    target: float
    r_multiple: float  # reward / risk
    timeframe: str  # the entry timeframe the levels belong to
    since: datetime | None = None  # triggered: open of the trigger bar; planned: open of the last closed entry bar
    outcome: PlanOutcome = "open"
    outcome_at: datetime | None = None  # open of the entry bar that reached the target or the stop
    last: float | None = None  # last closed entry-timeframe close
    r_now: float | None = None  # triggered: how far ``last`` is from the entry, in multiples of the risk
    note: str = ""  # one sentence the trader should read with the levels
    # Where the idea stands, for the trader (rules.md open question 33):
    # "forming" (planned), "actionable" (triggered, young and near its entry), "late"
    # (triggered, but too old or too far from the entry), "played_out" (target or stop traded).
    stage_label: StageLabel = ""
    age_bars: int | None = None  # triggered: closed entry bars after the trigger bar
    # The stop's size against the 14-day average daily range, and what one contract costs
    # (one tick of slippage plus commission) as a share of the risk. None when unknown.
    risk_adr: float | None = None
    cost_r_mini: float | None = None
    cost_r_micro: float | None = None


@dataclass(frozen=True)
class Verdict:
    style: str  # e.g. "ttrades"
    symbol: str
    as_of: datetime
    stack: TimeframeStack
    decision: Decision
    bias: Literal["bullish", "bearish", "neutral"]
    path_family: Literal["continuation", "reversal", "none"]
    stage: Literal["none", "c1", "c2", "c3", "c4"]
    criteria: tuple[CriterionResult, ...]
    entry: float | None = None
    stop: float | None = None
    targets: tuple[float, ...] = ()
    invalidation: str = ""
    summary: str = ""
    markup: tuple[MarkupItem, ...] = field(default_factory=tuple)
    # The top-down read (added after the fields above; all optional so older
    # constructors keep working). ``read`` runs from the highest timeframe to the lowest.
    read: tuple[ReadStep, ...] = field(default_factory=tuple)
    why: str = ""  # one sentence: why this decision
    waiting_for: str = ""  # on a watch: what has to happen next, in plain words
    # The side the trader asked for ("" = the style chose), the side of the idea described
    # ("" = none), and, when the two would differ, one line saying what the style itself reads.
    requested: str = ""  # "" | "long" | "short"
    idea: str = ""  # "" | "long" | "short"
    auto_note: str = ""
    # What has to happen, in order, and the trade it leads to. ``plan`` is None when the
    # rules cannot compute its levels yet; the steps then say what must come first.
    steps: tuple[PlanStep, ...] = field(default_factory=tuple)
    plan: PositionPlan | None = None
