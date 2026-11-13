"""Building blocks of the TTrades checklist (rules.md section 3).

Everything in the checklist is written once, for the bullish case. A bearish read is
the same code run on the mirrored market: prices are negated and high / low swapped.
``Side`` holds the direction, turns mirrored prices back into real ones and supplies
the direction words for the detail strings, so a trader never sees a mirrored number.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property

import numpy as np
import pandas as pd

from companion.bars import bar_close_times
from companion.structure import find_fair_value_gaps, find_swings
from companion.timeframes import parse_timeframe
from companion.types import Direction


def fmt(price: float) -> str:
    return f"{price:.2f}"


def when(moment: pd.Timestamp) -> str:
    return pd.Timestamp(moment).strftime("%Y-%m-%d %H:%M")


@dataclass(frozen=True)
class Side:
    """The direction a read is made for. Bullish is the identity; bearish mirrors."""

    direction: Direction

    @property
    def sign(self) -> int:
        return 1 if self.direction == "bullish" else -1

    @property
    def bullish(self) -> bool:
        return self.direction == "bullish"

    def px(self, mirrored: float) -> float:
        """Mirrored price -> real price (and back; the map is its own inverse)."""
        return float(self.sign * mirrored) + 0.0

    def p(self, mirrored: float) -> str:
        return fmt(self.px(mirrored))

    def zone(self, top: float, bottom: float) -> tuple[float, float]:
        """Real (top, bottom) of a mirrored zone."""
        a, b = self.px(top), self.px(bottom)
        return max(a, b), min(a, b)

    def zone_text(self, top: float, bottom: float) -> str:
        real_top, real_bottom = self.zone(top, bottom)
        return f"{fmt(real_bottom)}-{fmt(real_top)}"

    # direction words: written for bullish, swapped for bearish
    @property
    def lo(self) -> str:
        return "low" if self.bullish else "high"

    @property
    def hi(self) -> str:
        return "high" if self.bullish else "low"

    @property
    def below(self) -> str:
        return "below" if self.bullish else "above"

    @property
    def above(self) -> str:
        return "above" if self.bullish else "below"

    @property
    def down_close(self) -> str:
        return "down-close" if self.bullish else "up-close"

    @property
    def up_close(self) -> str:
        return "up-close" if self.bullish else "down-close"

    @property
    def trade(self) -> str:
        return "long" if self.bullish else "short"

    @property
    def opposite(self) -> "Side":
        return BEAR if self.bullish else BULL


BULL = Side("bullish")
BEAR = Side("bearish")


@dataclass(frozen=True)
class SwingPoint:
    """A swing low of the mirrored frame. Knowable once bar ``pos + 1`` has closed."""

    pos: int
    price: float


@dataclass(frozen=True)
class Gap:
    """A bullish fair value gap of the mirrored frame. ``pos`` is the middle candle;
    knowable once bar ``pos + 1`` has closed. ``fill_pos`` is the first later bar that
    closed below ``bottom``."""

    pos: int
    top: float
    bottom: float
    fill_pos: int | None


class Bars:
    """One closed bars frame seen from one side, as arrays indexed by position."""

    def __init__(self, frame: pd.DataFrame, timeframe: str, side: Side) -> None:
        self.tf = timeframe
        self.side = side
        self.times: pd.DatetimeIndex = frame.index
        self.closes_at: pd.DatetimeIndex = bar_close_times(frame, timeframe)
        opens, highs, lows, closes = (frame[name].to_numpy(dtype=float) for name in ("open", "high", "low", "close"))
        if side.bullish:
            self.open, self.high, self.low, self.close = opens, highs, lows, closes
        else:
            self.open, self.high, self.low, self.close = -opens, -lows, -highs, -closes
        self.n = len(frame)

    def _mirrored_frame(self) -> pd.DataFrame:
        return pd.DataFrame(
            {"open": self.open, "high": self.high, "low": self.low, "close": self.close}, index=self.times
        )

    def _swings(self) -> tuple[list[SwingPoint], list[SwingPoint]]:
        """(swing lows, swing highs) of the mirrored frame, via ``structure.find_swings``.

        Only the bar and price are taken from the structure events; when each became
        knowable is derived from positions (bar ``pos + 1`` closed), which is exact on
        timeframes whose bars are not all the same length.
        """
        lows: list[SwingPoint] = []
        highs: list[SwingPoint] = []
        if self.n >= 3:
            duration = pd.Timedelta(minutes=parse_timeframe(self.tf).nominal_minutes)
            events = find_swings(self._mirrored_frame(), self.tf, duration)
            positions = self.times.get_indexer([event.time for event in events])
            for event, pos in zip(events, positions.tolist()):
                (lows if event.kind == "low" else highs).append(SwingPoint(pos, event.price))
        return lows, highs

    @cached_property
    def swing_lows(self) -> list[SwingPoint]:
        return self._both_swings[0]

    @cached_property
    def swing_highs(self) -> list[SwingPoint]:
        return self._both_swings[1]

    @cached_property
    def _both_swings(self) -> tuple[list[SwingPoint], list[SwingPoint]]:
        return self._swings()

    @cached_property
    def gaps(self) -> list[Gap]:
        """Bullish fair value gaps of the mirrored frame (rules.md 3.10)."""
        if self.n < 3:
            return []
        duration = pd.Timedelta(minutes=parse_timeframe(self.tf).nominal_minutes)
        events = [
            event
            for event in find_fair_value_gaps(self._mirrored_frame(), self.tf, duration)
            if event.direction == "bullish"
        ]
        positions = self.times.get_indexer([event.time for event in events]).tolist()
        gaps: list[Gap] = []
        for event, pos in zip(events, positions):
            later = np.flatnonzero(self.close[pos + 2 :] < event.bottom)
            fill = int(later[0]) + pos + 2 if len(later) else None
            gaps.append(Gap(pos, event.top, event.bottom, fill))
        return gaps

    def first_at_or_after(self, moment: pd.Timestamp) -> int:
        """Position of the first bar that opens at or after ``moment`` (``n`` if none)."""
        return int(self.times.searchsorted(moment, side="left"))

    def last_closed_by(self, moment: pd.Timestamp) -> int:
        """Position of the last bar whose close time is at or before ``moment`` (-1 if none)."""
        return int(self.closes_at.searchsorted(moment, side="right")) - 1

    def p(self, mirrored: float) -> str:
        return self.side.p(mirrored)

    def at(self, pos: int) -> str:
        return when(self.times[pos])

    def first_break(self, start: int, level: float, break_on: str) -> int | None:
        """First bar at or after ``start`` that breaks a protected low at ``level``."""
        if start >= self.n:
            return None
        probe = self.low if break_on == "wick" else self.close
        hits = np.flatnonzero(probe[start:] < level)
        return int(hits[0]) + start if len(hits) else None


# --- closures (rules.md 3.4 - 3.7) --------------------------------------------


def is_reversal_closure(x: Bars, k: int) -> bool:
    """Bar ``k`` took bar ``k-1``'s low and closed back above it."""
    return k >= 1 and bool(x.low[k] < x.low[k - 1] and x.close[k] > x.low[k - 1])


def is_continuation_closure(x: Bars, k: int) -> bool:
    return k >= 1 and bool(x.close[k] > x.high[k - 1])


def is_inside_bar(x: Bars, k: int) -> bool:
    return k >= 1 and bool(x.high[k] <= x.high[k - 1] and x.low[k] >= x.low[k - 1])


def candle3_edge(x: Bars, k: int, edge: str) -> float:
    """The body edge of Candle 2 (bar ``k``) a Candle 3 closure must close beyond."""
    return float(max(x.open[k], x.close[k]) if edge == "far" else x.open[k])


def completes_candle3_closure(x: Bars, k: int, edge: str) -> bool:
    """Bar ``k`` holds bar ``k-1``'s low and closes above its body (rules.md 3.6)."""
    return k >= 1 and bool(x.low[k] >= x.low[k - 1] and x.close[k] > candle3_edge(x, k - 1, edge))


# --- change in state of delivery (rules.md 3.11, 3.12, 3.15) --------------------


@dataclass(frozen=True)
class CisdRead:
    """A bullish change in state of delivery anchored at one low, confirmed or not."""

    anchor: int  # bar holding the low
    anchor_low: float
    series: tuple[int, int] | None  # first / last bar of the down-close run, inclusive
    level: float  # highest open of the series: the price to close above
    ob_bottom: float  # lowest close of the series: the order block's other edge
    confirm: int | None  # bar that closed above ``level``
    lower_low: int | None  # bar that traded below the anchor before any confirmation

    @property
    def confirmed(self) -> bool:
        return self.confirm is not None

    @property
    def bars_to_confirm(self) -> int | None:
        return None if self.confirm is None else self.confirm - self.anchor

    @property
    def mean_threshold(self) -> float:
        return (self.level + self.ob_bottom) / 2.0


def anchored_cisd(x: Bars, anchor: int, doji_in_series: bool) -> CisdRead:
    """rules.md 3.11 for the low at bar ``anchor`` (bullish; the mirrored frame gives bearish).

    Series: the unbroken run of down-close bars ending at the anchor, or at the bar
    before it when the anchor itself closed up. Level: the highest open in the run, or
    the anchor's body top when there is no run. Confirmation: the first later bar that
    closes above the level. A bar that trades below the anchor first ends the read
    unconfirmed (the caller re-anchors on the new low).
    """
    opens, closes, lows = x.open, x.close, x.low

    def member(i: int) -> bool:
        return bool(closes[i] < opens[i] or (doji_in_series and closes[i] == opens[i]))

    end = anchor if member(anchor) else anchor - 1
    series: tuple[int, int] | None = None
    if end >= 0 and member(end):
        start = end
        while start - 1 >= 0 and member(start - 1):
            start -= 1
        while start <= end and closes[start] == opens[start]:  # a doji never starts a series
            start += 1
        if start <= end:
            series = (start, end)
    if series is not None:
        level = float(opens[series[0] : series[1] + 1].max())
        bottom = float(closes[series[0] : series[1] + 1].min())
    else:
        level = float(max(opens[anchor], closes[anchor]))
        bottom = float(min(opens[anchor], closes[anchor]))
    anchor_low = float(lows[anchor])
    confirm: int | None = None
    lower: int | None = None
    closes_after = np.flatnonzero(closes[anchor + 1 :] > level)
    lows_after = np.flatnonzero(lows[anchor + 1 :] < anchor_low)
    first_close = int(closes_after[0]) if len(closes_after) else None
    first_low = int(lows_after[0]) if len(lows_after) else None
    if first_close is not None and (first_low is None or first_close <= first_low):
        confirm = anchor + 1 + first_close
    elif first_low is not None:
        lower = anchor + 1 + first_low
    return CisdRead(anchor, anchor_low, series, level, bottom, confirm, lower)


def cisd_text(x: Bars, read: CisdRead) -> str:
    """Plain-language description of a read, in real prices."""
    side = x.side
    if read.series is None:
        made_by = f"no {side.down_close} series, so the level is the body of the {x.at(read.anchor)} bar"
    else:
        count = read.series[1] - read.series[0] + 1
        made_by = f"series of {count} {side.down_close} {x.tf} bar(s) from {x.at(read.series[0])}"
    text = f"{side.lo} {x.p(read.anchor_low)} at {x.at(read.anchor)}; level {x.p(read.level)} ({made_by})"
    if read.confirm is not None:
        return (
            f"{text}; {x.tf} bar {x.at(read.confirm)} closed {side.above} it at {x.p(x.close[read.confirm])}, "
            f"{read.bars_to_confirm} bar(s) after the {side.lo}"
        )
    if read.lower_low is not None:
        return (
            f"{text}; before any close {side.above} it, {x.at(read.lower_low)} traded {side.below} "
            f"the {side.lo} to {x.p(x.low[read.lower_low])}"
        )
    last = x.n - 1
    return f"{text}; no {x.tf} close {side.above} it yet (last close {x.p(x.close[last])} at {x.at(last)})"


# --- points of interest (rules.md 3.14) -----------------------------------------


@dataclass(frozen=True)
class Zone:
    top: float
    bottom: float

    @property
    def mid(self) -> float:
        return (self.top + self.bottom) / 2.0


@dataclass(frozen=True)
class PoiHit:
    kind: str  # "swing" | "fvg" | "order_block"
    top: float
    bottom: float
    source_pos: int  # position of the swing / gap in the frame; -1 for an order block
    text: str  # plain-language description in real prices
    gap: Gap | None = None


def poi_reached(
    x: Bars,
    low: float,
    before: int,
    *,
    min_swing_pos: int,
    fvg_min_size: float,
    min_fvg_top: float | None = None,
    close: float | None = None,
    order_block: Zone | None = None,
    order_block_name: str = "order block",
) -> PoiHit | None:
    """Did a bar with this ``low`` reach a bullish point of interest (rules.md 3.14)?

    ``before`` is the position of the bar being tested (bars ``0..before-1`` are its
    history); pass ``x.n`` for a candle that is not a row of the frame, such as the
    forming bias candle.

    (a) it took a swing low that was confirmed before the bar opened, sits at or after
        ``min_swing_pos`` and had not been traded through since;
    (b) it traded into a bullish fair value gap that was confirmed before the bar opened
        and not yet filled (optionally with its top above ``min_fvg_top``);
    (c) it traded into ``order_block`` and closed at or above its mean threshold.
    """
    side = x.side
    for swing in reversed(x.swing_lows):
        if swing.pos + 1 >= before or swing.pos < min_swing_pos or not low < swing.price:
            continue
        between = x.low[swing.pos + 1 : before]
        if len(between) and float(between.min()) < swing.price:
            continue
        text = f"took the untaken {x.tf} swing {side.lo} {x.p(swing.price)} from {x.at(swing.pos)}"
        return PoiHit("swing", swing.price, swing.price, swing.pos, text)
    for gap in reversed(x.gaps):
        if gap.pos + 1 >= before or (gap.fill_pos is not None and gap.fill_pos < before):
            continue
        if gap.top - gap.bottom < fvg_min_size or low > gap.top:
            continue
        if min_fvg_top is not None and not gap.top > min_fvg_top:
            continue
        text = (
            f"traded into the unfilled {side.direction} {x.tf} fair value gap "
            f"{side.zone_text(gap.top, gap.bottom)} formed at {x.at(gap.pos)}"
        )
        return PoiHit("fvg", gap.top, gap.bottom, gap.pos, text, gap)
    if order_block is not None and close is not None and low <= order_block.top and close >= order_block.mid:
        text = (
            f"traded into the {order_block_name} {side.zone_text(order_block.top, order_block.bottom)} and closed "
            f"at {x.p(close)}, at or {side.above} its mean threshold {x.p(order_block.mid)}"
        )
        return PoiHit("order_block", order_block.top, order_block.bottom, -1, text)
    return None


# --- wick size (rules.md 3.8) ---------------------------------------------------


@dataclass(frozen=True)
class WickRead:
    size: str  # "small" | "large" | "unclassified"
    run: float  # opposing run, in price units
    early: bool | None  # None when the candle's duration is unknown
    text: str


def closed_wick_is_large(x: Bars, k: int, frac: float) -> tuple[bool, float, float]:
    """(large?, wick, range) of closed bar ``k`` for a bullish Candle 2 (rules.md 3.8)."""
    wick = float(min(x.open[k], x.close[k]) - x.low[k])
    span = float(x.high[k] - x.low[k])
    return (span > 0 and wick >= frac * span), wick, span
