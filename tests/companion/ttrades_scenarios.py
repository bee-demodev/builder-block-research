"""Synthetic markets for the TTrades style tests.

A scenario is a sparse one-minute frame: every candle the test cares about is ONE
minute row, placed at the candle's open minute and carrying the candle's whole OHLC.
Resampling then reproduces the candle exactly on its own timeframe, and a higher
timeframe candle is the aggregate of the rows inside it. So a scenario reads as a list
of bias candles, with the last two spelled out in setup and entry candles.

Prices are written for the bullish story. ``mirror=True`` reflects every price around
``PIVOT`` (and swaps high / low), which gives the bearish mirror of the same story.

Time runs on a plain clock with no weekends: the resampler only looks at the clock.
The start date keeps every scenario clear of daylight-saving changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from companion.bars import HistoricalBarSource
from companion.timeframes import parse_timeframe
from companion.types import BARS_TIMEZONE, TimeframeStack

SYMBOL = "NQ"
PIVOT = 200.0
START = pd.Timestamp("2024-04-01 18:00", tz=BARS_TIMEZONE)

Row = tuple[float, float, float, float]  # open, high, low, close

FILLER: Row = (100, 110, 90, 100)  # a doji with tied highs and lows: no swings, no gaps


def _duration(label: str) -> pd.Timedelta:
    timeframe = parse_timeframe(label)
    if timeframe.kind not in ("minute", "hour", "day"):
        raise ValueError("scenario stacks use intraday or daily timeframes")
    return pd.Timedelta(minutes=timeframe.nominal_minutes)


class ScenarioBuilder:
    """Lays candles on the clock for one stack and hands back a ``BarSource``."""

    def __init__(self, stack: TimeframeStack, mirror: bool = False) -> None:
        self.stack = stack
        self.mirror = mirror
        self._bias, self._setup, self._entry = (_duration(label) for label in (stack.bias, stack.setup, stack.entry))
        self._rows: dict[pd.Timestamp, Row] = {}
        self._count = 0  # bias candles laid so far; the next one opens at bias_open(self._count)

    def bias_open(self, index: int | None = None) -> pd.Timestamp:
        return START + self._bias * (self._count if index is None else index)

    def at(self, setup_slot: int = 0, entry_slot: int = 0) -> pd.Timestamp:
        """Clock time of an entry slot inside a setup slot of the bias candle being built."""
        return self.bias_open() + self._setup * setup_slot + self._entry * entry_slot

    def _put(self, moment: pd.Timestamp, row: Row) -> None:
        if moment in self._rows:
            raise ValueError(f"two candles at {moment}")
        open_, high, low, close = (float(value) for value in row)
        if not low <= min(open_, close) <= max(open_, close) <= high:
            raise ValueError(f"not a candle: {row}")
        self._rows[moment] = (PIVOT - open_, PIVOT - low, PIVOT - high, PIVOT - close) if self.mirror else (open_, high, low, close)

    def bias(self, *rows: Row) -> "ScenarioBuilder":
        """Whole bias candles, one row each."""
        for row in rows:
            self._put(self.bias_open(), row)
            self._count += 1
        return self

    def setup(self, slot: int, row: Row) -> "ScenarioBuilder":
        """One whole setup candle inside the bias candle being built."""
        self._put(self.at(slot), row)
        return self

    def entries(self, setup_slot: int, rows: list[Row], first: int = 0) -> "ScenarioBuilder":
        """Consecutive entry candles inside one setup candle of the bias candle being built."""
        for offset, row in enumerate(rows):
            self._put(self.at(setup_slot, first + offset), row)
        return self

    def next_bias(self) -> "ScenarioBuilder":
        """Finish the detailed bias candle and move to the next one."""
        self._count += 1
        return self

    def frame(self, until: pd.Timestamp | None = None) -> pd.DataFrame:
        """The minute frame; with ``until``, only the rows whose minute has closed by then."""
        index = pd.DatetimeIndex(sorted(self._rows), name="timestamp")
        bars = pd.DataFrame([self._rows[moment] for moment in index], columns=["open", "high", "low", "close"], index=index)
        bars["volume"] = 1.0
        if until is not None:
            bars = bars[bars.index + pd.Timedelta(minutes=1) <= until]
        return bars

    def source(self, until: pd.Timestamp | None = None) -> HistoricalBarSource:
        return HistoricalBarSource(minute_bars={SYMBOL: self.frame(until)})


@dataclass
class Scenario:
    builder: ScenarioBuilder
    stack: TimeframeStack
    times: dict[str, pd.Timestamp] = field(default_factory=dict)  # named moments to evaluate at

    def source(self, until: pd.Timestamp | None = None) -> HistoricalBarSource:
        return self.builder.source(until)

    def price(self, bullish_price: float) -> float:
        """A price of the bullish story as it appears in this scenario."""
        return PIVOT - bullish_price if self.builder.mirror else bullish_price


# Where the action sits in the forming bias candle, per stack: the setup slot of the
# swing candle. Chosen so the trigger closes inside the New York kill zone.
_SWING_SLOT = {"1D": 14, "4h": 10}  # 1D opens 18:00 -> 08:00; 4h opens 06:00 -> 08:30
_HISTORY = {"1D": 72, "4h": 99}  # bias candles before the forming one (4h: 99 % 6 == 3 -> opens 06:00)


def continuation_scenario(
    stack: TimeframeStack,
    *,
    mirror: bool = False,
    first_target: float = 105.0,
    previous_setup_bar: Row = (96.8, 97.8, 96.5, 97.0),
    inside_bias_bar: bool = False,
    with_aftermath: bool = False,
    swing_rows: list[Row] | None = None,
    trigger_rows: list[Row] | None = None,
) -> Scenario:
    """A bullish continuation that reaches entry-ready (rules.md section 6, case A).

    Bias: ``B[-1]`` takes the swing low 84 and closes back above the prior low 88 (a
    Candle 2 closure with a large wick: O 96 H ``first_target`` L 80 C 97); the setup
    timeframe confirms with a close above 96, leaving the bias order block 82-96.
    Respect level = wick midpoint 88; equilibrium = (first_target + 80) / 2.

    Forming candle: opens 97.5, drifts, then the swing setup bar dips to 91 into the bias
    order block and closes 97.5 (a setup Candle 2 closure). Inside it the entry
    timeframe closes above 97.0 two bars after the low (entry CISD). In the next setup
    bar price pulls back to 95.5 and closes above 97.5 at 97.7: the continuation order
    block. Two triggers follow: the entry CISD (entry 97.5 at the close of the setup
    closure, stop 91) and the order block (entry 97.7, stop 95.5). Structural levels:
    ``first_target`` and 115 (an old bias swing high).

    Named times: ``before_setup`` (swing bar still forming), ``setup_closed``,
    ``trigger`` (close of the trigger bar), ``window_closed``.

    ``swing_rows`` replace the entry rows inside the setup swing candle (the dip to the low
    and the entry CISD). ``trigger_rows`` replace the entry rows of
    the setup candle after the swing (pullback and order-block trigger); ``trigger`` is then
    the close of their last row and ``after_trigger`` the close of the row after it.
    """
    build = ScenarioBuilder(stack, mirror)
    swing_slot = _SWING_SLOT[stack.bias]
    history = _HISTORY[stack.bias]
    build.bias(*[FILLER] * (history - 11))
    build.bias((100, 115, 90, 100))  # swing high 115: the second target
    build.bias(*[FILLER] * 7)
    build.bias((100, 108, 84, 98))  # swing low 84: the bias point of interest
    build.bias((95, 106, 88, 96))
    if inside_bias_bar:
        build.bias((96, 104, 90, 95.5))  # inside bar, closes inside the prior body: no read
    else:
        # B[-1], in setup candles: three down-close bars into 80, then the close above 96
        build.setup(0, (96, first_target, 95, 95.5))
        build.setup(1, (95.5, 96, 90, 91))
        build.setup(2, (91, 92, 80, 82))
        build.setup(3, (82, 97, 81, 89))
        build.setup(4, (89, 98, 88, 97))
        build.next_bias()
    assert build._count == history
    # B[0], the forming candle
    build.setup(0, (97.5, 97.9, 96.9, 97.0))
    build.setup(swing_slot - 1, previous_setup_bar)
    build.entries(
        swing_slot,
        swing_rows
        or [
            (97.0, 97.2, 95.0, 95.2),
            (95.2, 95.5, 93.0, 93.2),
            (93.2, 93.5, 91.0, 91.5),  # the setup swing low
            (91.5, 94.0, 91.2, 93.8),
            (93.8, 97.6, 93.5, 97.4),  # entry CISD: closes above 97.0
            (97.4, 98.0, 97.0, 97.5),
        ],
    )
    rows = trigger_rows or [
        (97.5, 97.8, 96.5, 96.6),
        (96.6, 96.8, 95.5, 95.8),  # pullback low: the new protected low
        (95.8, 97.9, 95.7, 97.7),  # trigger: closes above 97.5
    ]
    build.entries(swing_slot + 1, rows)
    times = {
        "before_setup": build.at(swing_slot, 3),
        "setup_closed": build.at(swing_slot + 1),
        "trigger": build.at(swing_slot + 1, len(rows)),
        "after_trigger": build.at(swing_slot + 1, len(rows) + 1),
        "window_closed": build.at(swing_slot + 2) + pd.Timedelta(minutes=1),
    }
    if with_aftermath:
        # what happens later must not change what was knowable at "trigger"
        build.entries(swing_slot + 1, [(97.7, 97.8, 79.0, 79.5), (79.5, 120.0, 79.0, 119.0)], first=3)
        build.setup(swing_slot + 2, (119, 121, 70, 71))
        build.next_bias()
        build.bias((71, 130, 60, 125), FILLER)
    return Scenario(build, stack, times)


def reversal_scenario(
    stack: TimeframeStack,
    *,
    mirror: bool = False,
    wick_low: float = 54.0,
    previous_low: float = 55.0,
    run_into_level: bool = True,
) -> Scenario:
    """A bullish reversal that reaches entry-ready (rules.md section 7), daily bias.

    The key level is the low of ``B[-1]`` (O 70 H 71 L ``previous_low`` C 58); the
    history holds no bias-timeframe swing low or bullish gap. The forming candle opens
    58 and sells off in down-close setup candles (the expansion into the level; with
    ``run_into_level=False`` the setup candle before the low closes up instead), makes its low ``wick_low`` early with a small wick, the
    setup bar closes back above the level and the entry timeframe closes above 57.0 at
    57.4 (the CISD: entry 57.4, stop ``wick_low``). It then pulls back to 56.2 and
    closes above 57.5 at 57.8 (the continuation order block: entry 57.8, stop 56.2).
    Structural levels: equilibrium 63, previous high 71.

    ``wick_low`` 54 trades through the level 55; 55.05 only comes near it.
    ``previous_low`` 50 leaves the low 54 with no key level nearby.

    Named times: ``level_taken`` (low made, nothing closed back yet), ``trigger``.
    """
    build = ScenarioBuilder(stack, mirror)
    swing_slot = _SWING_SLOT[stack.bias]
    history = _HISTORY[stack.bias]
    build.bias(*[FILLER] * (history - 3))
    build.bias((100, 101, 80, 85), (85, 86, 68, 70), (70, 71, previous_low, 58))
    build.setup(0, (58.0, 58.5, 56.5, 57.0))
    if run_into_level:
        # a down-close setup candle (58.0 -> 57.0) whose last entry candle closes up, so the
        # entry-timeframe series into the low is the three candles of the swing slot only
        last = int(build._setup / build._entry) - 1
        build.entries(swing_slot - 1, [(58.0, 58.2, 56.8, 56.9)])
        build.entries(swing_slot - 1, [(56.9, 57.1, 56.85, 57.0)], first=last)
    else:
        build.setup(swing_slot - 1, (56.8, 57.3, 56.5, 57.0))
    build.entries(
        swing_slot,
        [
            (57.0, 57.2, 56.0, 56.1),
            (56.1, 56.3, 55.2, 55.3),
            (55.3, 55.4, wick_low, wick_low + 0.2),  # the wick low, at the key level
            (wick_low + 0.2, 56.0, wick_low + 0.1, 55.9),
            (55.9, 57.6, 55.8, 57.4),  # CISD: closes above 57.0
            (57.4, 57.8, 57.2, 57.5),
        ],
    )
    build.entries(
        swing_slot + 1,
        [
            (57.5, 57.6, 56.8, 56.9),
            (56.9, 57.0, 56.2, 56.4),  # pullback low
            (56.4, 57.9, 56.3, 57.8),  # trigger
        ],
    )
    times = {"level_taken": build.at(swing_slot, 3), "trigger": build.at(swing_slot + 1, 3)}
    return Scenario(build, stack, times)
