"""Market-structure calculator: turns one bars frame into structure events.

Every ``find_*`` function is pure. It takes a bars frame (see ``companion.types``
for the convention), the ``timeframe`` label to stamp on the events, and the bar
duration as a ``pandas.Timedelta``, and returns a list of the matching event
dataclass sorted by ``time`` (ties by ``confirmed_at``).

No lookahead
------------
Every bar in the frame is treated as closed. ``confirmed_at`` is the CLOSE time
(open time + ``bar_duration``) of the last bar needed to establish the event.
``FairValueGap.filled_at`` and ``ProtectedSwing.broken_at`` are likewise the close
time of the bar that filled / broke it, because that is when it becomes knowable.
The guarantee, proven by the truncation test in ``tests/companion``:

    find_x(bars truncated to those closed at T) == known_as_of(find_x(all bars), T)

Rows are treated as consecutive candles even when timestamps are missing between
them (session gaps); only ``confirmed_at`` arithmetic uses the clock.

Definitions come from the TTrades transcripts under
``knowledge/ttfm_video_corpus/transcripts/``; each docstring names its source.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any, Literal, TypeVar

import numpy as np
import pandas as pd

from companion.types import Cisd, Direction, FairValueGap, ProtectedSwing, Sweep, Swing

_PRICE_COLUMNS: tuple[str, ...] = ("open", "high", "low", "close")

Event = TypeVar("Event", Swing, Sweep, FairValueGap, Cisd, ProtectedSwing)


# --- small helpers the checklist needs ---------------------------------------


@dataclass(frozen=True)
class CandleMeasurements:
    """Wick and body measurements of one bar, in price units."""

    range: float  # high - low (wick to wick)
    body: float  # abs(close - open)
    upper_wick: float  # high - body_top
    lower_wick: float  # body_bottom - low
    body_top: float  # max(open, close)
    body_bottom: float  # min(open, close)
    direction: Direction | None  # None for a doji (close == open)


def equilibrium(high: float, low: float) -> float:
    """The 50% level of a range.

    Source ``equilibrium_for_expansions.txt``: "I'm always going to measure the
    candles from wick high to wick low and then mark out the equilibrium that way.
    I'm not going to use the bodies like I do for the change in the state of
    delivery or order blocks." Pass a candle's (or a day's) high and low for its
    EQ. For the 0.5 of a wick (``master_candlestick_wicks_the_key_to_catching_
    reversals.txt``: "marking out 0.5 of this wick from the body to the low or the
    body to the high") pass ``body_top, high`` or ``low, body_bottom`` from
    :func:`measure_candle`.
    """
    return (float(high) + float(low)) / 2.0


def candle_direction(bar: Mapping[str, Any] | pd.Series) -> Direction | None:
    """``"bullish"`` for an up-close candle (close > open), ``"bearish"`` for a
    down-close candle (close < open), ``None`` for a doji.

    The transcripts speak of "up close" / "down close" candles throughout
    (``protected_swings_understanding_trend_and_invalidations.txt``); none says
    how to treat close == open, so a doji is reported as neither.
    """
    open_, close = float(bar["open"]), float(bar["close"])
    if close > open_:
        return "bullish"
    if close < open_:
        return "bearish"
    return None


def measure_candle(bar: Mapping[str, Any] | pd.Series) -> CandleMeasurements:
    """Wick/body measurements of a bar (a frame row or any open/high/low/close mapping).

    Source ``wick_size_matters_the_key_to_understanding_reversal_and_expansion_
    candles.txt``: an expansion candle "has a small wick on both sides and a large
    body"; a reversal candle has "a large wick and a small body". The transcripts
    give no numeric threshold for small vs large, so this returns raw sizes and
    leaves the threshold to the caller.
    """
    open_, high, low, close = (float(bar[name]) for name in _PRICE_COLUMNS)
    body_top, body_bottom = max(open_, close), min(open_, close)
    return CandleMeasurements(
        range=high - low,
        body=body_top - body_bottom,
        upper_wick=high - body_top,
        lower_wick=body_bottom - low,
        body_top=body_top,
        body_bottom=body_bottom,
        direction=candle_direction(bar),
    )


def known_as_of(events: Iterable[Event], as_of: datetime) -> list[Event]:
    """The events knowable at ``as_of``, in their original order.

    Keeps events with ``confirmed_at <= as_of`` and hides a fill / break that
    happened later (``filled_at`` / ``broken_at`` reset to ``None``). The result
    equals what the ``find_*`` function returns on bars truncated to those closed
    at ``as_of``.
    """
    known: list[Event] = []
    for event in events:
        if event.confirmed_at > as_of:
            continue
        if isinstance(event, FairValueGap):
            if event.filled_at is not None and event.filled_at > as_of:
                event = replace(event, filled_at=None)
        elif isinstance(event, ProtectedSwing):
            if event.broken_at is not None and event.broken_at > as_of:
                event = replace(event, broken_at=None)
        known.append(event)
    return known


# --- internals ---------------------------------------------------------------


@dataclass(frozen=True)
class _Arrays:
    opens: np.ndarray
    highs: np.ndarray
    lows: np.ndarray
    closes: np.ndarray
    open_times: list[pd.Timestamp]
    close_times: list[pd.Timestamp]

    def __len__(self) -> int:
        return len(self.open_times)


def _arrays(bars: pd.DataFrame, bar_duration: pd.Timedelta) -> _Arrays:
    missing = [name for name in _PRICE_COLUMNS if name not in bars.columns]
    if missing:
        raise ValueError(f"bars frame is missing columns: {missing}")
    if bar_duration <= pd.Timedelta(0):
        raise ValueError("bar_duration must be positive")
    opens, highs, lows, closes = (
        bars[name].to_numpy(dtype=float) for name in _PRICE_COLUMNS
    )
    return _Arrays(
        opens=opens,
        highs=highs,
        lows=lows,
        closes=closes,
        open_times=list(bars.index),
        close_times=list(bars.index + bar_duration),
    )


def _by_time(events: list[Event]) -> list[Event]:
    return sorted(events, key=lambda event: (event.time, event.confirmed_at))


def _first_beyond(values: np.ndarray, start: int, level: float, *, above: bool) -> int:
    """Index of the first value at or after ``start`` strictly beyond ``level``, else -1."""
    if start >= len(values):
        return -1
    segment = values[start:]
    hits = segment > level if above else segment < level
    position = int(hits.argmax())
    return start + position if hits[position] else -1


def _swing_indices(
    highs: np.ndarray, lows: np.ndarray, bars_each_side: int, allow_equal: bool
) -> tuple[np.ndarray, np.ndarray]:
    if bars_each_side < 1:
        raise ValueError("bars_each_side must be at least 1")
    count = len(highs)
    side = bars_each_side
    if count < 2 * side + 1:
        empty = np.empty(0, dtype=int)
        return empty, empty
    centre_highs = highs[side : count - side]
    centre_lows = lows[side : count - side]
    is_high = np.ones(count - 2 * side, dtype=bool)
    is_low = np.ones(count - 2 * side, dtype=bool)
    for offset in range(1, side + 1):
        left = slice(side - offset, count - side - offset)
        right = slice(side + offset, count - side + offset)
        is_high &= centre_highs > highs[left]
        is_low &= centre_lows < lows[left]
        if allow_equal:
            is_high &= centre_highs >= highs[right]
            is_low &= centre_lows <= lows[right]
        else:
            is_high &= centre_highs > highs[right]
            is_low &= centre_lows < lows[right]
    return np.flatnonzero(is_high) + side, np.flatnonzero(is_low) + side


@dataclass(frozen=True)
class _Gap:
    direction: Direction
    middle: int  # index of the middle candle
    top: float
    bottom: float
    fill: int  # index of the first bar closing through the far side, -1 if none


def _gaps(data: _Arrays) -> list[_Gap]:
    highs, lows, closes = data.highs, data.lows, data.closes
    if len(data) < 3:
        return []
    gaps: list[_Gap] = []
    bullish = lows[2:] > highs[:-2]
    bearish = highs[2:] < lows[:-2]
    for first in np.flatnonzero(bullish | bearish).tolist():
        third = first + 2
        if bullish[first]:
            top, bottom = float(lows[third]), float(highs[first])
            fill = _first_beyond(closes, third + 1, bottom, above=False)
            gaps.append(_Gap("bullish", first + 1, top, bottom, fill))
        else:
            top, bottom = float(lows[first]), float(highs[third])
            fill = _first_beyond(closes, third + 1, top, above=True)
            gaps.append(_Gap("bearish", first + 1, top, bottom, fill))
    return gaps


@dataclass
class _Leg:
    """A series of same-direction candles and the extreme it made (high-side view)."""

    start: int  # first candle of the series
    run_end: int  # last candle of the series so far
    level: float  # open of the first candle of the series
    extreme: float
    extreme_idx: int


@dataclass(frozen=True)
class _Change:
    """A confirmed change in the state of delivery, in real (un-mirrored) prices."""

    side: Literal["high", "low"]  # which extreme the change protects
    start: int
    extreme_idx: int
    extreme: float
    level: float
    confirm: int


def _track_high_side(
    opens: list[float],
    highs: list[float],
    closes: list[float],
    *,
    doji_in_series: bool,
    max_bars_to_confirm: int | None,
) -> list[tuple[int, list[_Leg]]]:
    """Single causal pass over the bars. Returns ``(confirming bar index, legs)``
    for every bar that closed below the opening price of one or more legs."""
    confirmed_groups: list[tuple[int, list[_Leg]]] = []
    pending: list[_Leg] = []
    latest: _Leg | None = None  # leg of the most recent series, while unconfirmed
    in_run = False
    for j in range(len(opens)):
        open_, high, close = opens[j], highs[j], closes[j]
        up_close = close > open_ or (doji_in_series and close == open_)
        if up_close:
            if in_run and latest is not None:
                current = latest
                current.run_end = j
                if high > current.extreme:
                    current.extreme, current.extreme_idx = high, j
            else:
                current = _Leg(start=j, run_end=j, level=open_, extreme=high, extreme_idx=j)
                pending.append(current)
                latest = current
            in_run = True
            # A newer series trading above an older leg's high made a new high:
            # the older series is no longer "the series that made the high".
            pending = [leg for leg in pending if leg is current or high <= leg.extreme]
        else:
            in_run = False
            kept: list[_Leg] = []
            for leg in pending:
                if high > leg.extreme:
                    if leg is not latest:
                        continue
                    # A non-series candle (e.g. the sweep candle that closes
                    # down) pushed the high further; the series leading into
                    # that high is still the most recent one.
                    leg.extreme, leg.extreme_idx = high, j
                kept.append(leg)
            pending = kept
        if max_bars_to_confirm is not None:
            pending = [leg for leg in pending if j - leg.extreme_idx <= max_bars_to_confirm]
        confirmed = [leg for leg in pending if j > leg.run_end and close < leg.level]
        if confirmed:
            pending = [leg for leg in pending if not (j > leg.run_end and close < leg.level)]
            if latest is not None and any(leg is latest for leg in confirmed):
                latest = None
            confirmed_groups.append((j, confirmed))
    return confirmed_groups


def _context_marks(
    data: _Arrays, gaps: list[_Gap], swing_bars: int, allow_equal: bool
) -> tuple[np.ndarray, np.ndarray]:
    """Per bar, the formation index of the oldest "important level" the bar reached
    on the high side / low side (``len(data)`` when it reached none).

    High side: the bar is the first to trade above a prior swing high, or its high
    reaches into a bearish fair value gap that is confirmed and not yet filled.
    Low side is the mirror image.
    """
    count = len(data)
    high_marks = np.full(count, count, dtype=int)
    low_marks = np.full(count, count, dtype=int)
    swing_highs, swing_lows = _swing_indices(data.highs, data.lows, swing_bars, allow_equal)
    for i in swing_highs.tolist():
        taken = _first_beyond(data.highs, i + swing_bars + 1, float(data.highs[i]), above=True)
        if taken >= 0 and i < high_marks[taken]:
            high_marks[taken] = i
    for i in swing_lows.tolist():
        taken = _first_beyond(data.lows, i + swing_bars + 1, float(data.lows[i]), above=False)
        if taken >= 0 and i < low_marks[taken]:
            low_marks[taken] = i
    for gap in gaps:
        third = gap.middle + 1
        stop = gap.fill if gap.fill >= 0 else count
        window = slice(third + 1, stop)
        if gap.direction == "bearish":
            reached = data.highs[window] > gap.bottom
            marks = high_marks[window]
        else:
            reached = data.lows[window] < gap.top
            marks = low_marks[window]
        marks[reached & (marks > third)] = third
    return high_marks, low_marks


def _delivery_changes(
    data: _Arrays,
    *,
    require_context: bool,
    swing_bars: int,
    allow_equal: bool,
    doji_in_series: bool,
    max_bars_to_confirm: int | None,
) -> list[_Change]:
    if max_bars_to_confirm is not None and max_bars_to_confirm < 1:
        raise ValueError("max_bars_to_confirm must be at least 1 or None")
    opens, highs, lows, closes = (
        data.opens.tolist(),
        data.highs.tolist(),
        data.lows.tolist(),
        data.closes.tolist(),
    )
    high_groups = _track_high_side(
        opens,
        highs,
        closes,
        doji_in_series=doji_in_series,
        max_bars_to_confirm=max_bars_to_confirm,
    )
    # The low side is the high side of the mirrored (negated) market.
    low_groups = _track_high_side(
        [-value for value in opens],
        [-value for value in lows],
        [-value for value in closes],
        doji_in_series=doji_in_series,
        max_bars_to_confirm=max_bars_to_confirm,
    )
    if require_context:
        high_marks, low_marks = _context_marks(data, _gaps(data), swing_bars, allow_equal)
    changes: list[_Change] = []
    for side, groups, sign in (("high", high_groups, 1.0), ("low", low_groups, -1.0)):
        for confirm, legs in groups:
            if require_context:
                marks = high_marks if side == "high" else low_marks
                # The series must have reached a level that existed before it began.
                legs = [
                    leg
                    for leg in legs
                    if bool((marks[leg.start : leg.extreme_idx + 1] < leg.start).any())
                ]
                if not legs:
                    continue
            # One bar can close through several nested series; the change belongs
            # to the one that made the actual high (ties: the most recent series).
            leg = max(legs, key=lambda item: (item.extreme, item.start))
            changes.append(
                _Change(
                    side=side,  # type: ignore[arg-type]
                    start=leg.start,
                    extreme_idx=leg.extreme_idx,
                    extreme=sign * leg.extreme,
                    level=sign * leg.level,
                    confirm=confirm,
                )
            )
    return changes


# --- public structure functions ------------------------------------------------


def find_swings(
    bars: pd.DataFrame,
    timeframe: str,
    bar_duration: pd.Timedelta,
    *,
    bars_each_side: int = 1,
    allow_equal: bool = False,
) -> list[Swing]:
    """Fractal swing highs and lows.

    Definition (``which_swing_highs_and_lows_matter_in_trading.txt``): "A bullish
    swing point is a candle that has a low and then a higher low to its right and
    to its left ... a bearish swing point has a high and then a lower high to its
    left and right." In the fractal model this is candle 2 of the 1-2-3 sequence
    (``fractal_model_fundamentals.txt``: "Candle 2 will always be the swing low or
    swing high").

    ``bars_each_side`` generalises the three-candle swing (default 1) to N bars on
    each side. ``confirmed_at`` is the close of the last right-hand bar.

    Open choice: the source says "lower high" / "higher low" and is silent on
    equal highs or lows. ``allow_equal=False`` (default) requires strictly lower
    highs (higher lows) on both sides, so a flat double top is no swing. With
    ``allow_equal=True`` later bars may tie, so a flat top yields one swing at its
    first bar.
    """
    data = _arrays(bars, bar_duration)
    high_idx, low_idx = _swing_indices(data.highs, data.lows, bars_each_side, allow_equal)
    swings: list[Swing] = []
    for kind, indices, prices in (("high", high_idx, data.highs), ("low", low_idx, data.lows)):
        for i in indices.tolist():
            swings.append(
                Swing(
                    kind=kind,  # type: ignore[arg-type]
                    time=data.open_times[i],
                    price=float(prices[i]),
                    confirmed_at=data.close_times[i + bars_each_side],
                    timeframe=timeframe,
                )
            )
    return _by_time(swings)


def find_sweeps(
    bars: pd.DataFrame,
    timeframe: str,
    bar_duration: pd.Timedelta,
    *,
    swing_bars: int = 1,
    allow_equal: bool = False,
) -> list[Sweep]:
    """A bar trades beyond a prior unswept swing level and closes back inside it.

    Definition (``candle_2_closure_foundation.txt``): "a reversal closure ... is
    when we sweep out the previous candle's low, but we don't close below it. We
    close back inside"; "take out its previous candle's high and then close back
    below it". Here the level is a swing high / low from :func:`find_swings`
    (``swing_bars``, ``allow_equal`` are passed through), which the source uses as
    the liquidity being run ("a high that we sweep out. That is a point of
    interest").

    Rules adopted:
    - "Trades beyond" is strict: an equal high / low is not a sweep.
    - "Closes back inside" is strict: close below a swept high, above a swept low.
    - A level is consumed by the FIRST bar that trades beyond it. If that bar
      closes beyond the level (a continuation closure, not a reversal closure) no
      sweep is recorded and later bars cannot sweep that level any more.
    - One bar can sweep several levels; each gives its own ``Sweep``.

    ``extreme`` is the sweeping bar's high (low); ``confirmed_at`` is its close.
    """
    data = _arrays(bars, bar_duration)
    high_idx, low_idx = _swing_indices(data.highs, data.lows, swing_bars, allow_equal)
    sweeps: list[Sweep] = []
    for i in high_idx.tolist():
        level = float(data.highs[i])
        j = _first_beyond(data.highs, i + swing_bars + 1, level, above=True)
        if j >= 0 and data.closes[j] < level:
            sweeps.append(
                Sweep(
                    side="high",
                    time=data.open_times[j],
                    swept_price=level,
                    extreme=float(data.highs[j]),
                    swept_swing_time=data.open_times[i],
                    confirmed_at=data.close_times[j],
                    timeframe=timeframe,
                )
            )
    for i in low_idx.tolist():
        level = float(data.lows[i])
        j = _first_beyond(data.lows, i + swing_bars + 1, level, above=False)
        if j >= 0 and data.closes[j] > level:
            sweeps.append(
                Sweep(
                    side="low",
                    time=data.open_times[j],
                    swept_price=level,
                    extreme=float(data.lows[j]),
                    swept_swing_time=data.open_times[i],
                    confirmed_at=data.close_times[j],
                    timeframe=timeframe,
                )
            )
    return _by_time(sweeps)


def find_fair_value_gaps(
    bars: pd.DataFrame,
    timeframe: str,
    bar_duration: pd.Timedelta,
) -> list[FairValueGap]:
    """Three-candle fair value gaps.

    Definition (``how_to_actually_trade_inversion_fair_value_gaps_ifvg.txt``): "A
    fair value gap is a three candlestick pattern 1 2 3 in which the wick of
    candle one and the wick of candle three do not overlap leaving a gap." Also
    ``reversal_sequence_ttrs_how_to_blend_pd_arrays.txt``: "the high of the third
    candle does not overlap the low of the first candle or ... the low of the
    third candle does not overlap the high of the first candle."

    Bullish: low of candle 3 > high of candle 1; ``bottom`` = candle 1 high,
    ``top`` = candle 3 low. Bearish: high of candle 3 < low of candle 1; ``top`` =
    candle 1 low, ``bottom`` = candle 3 high. Wicks that merely touch leave no
    gap. ``time`` is candle 2; ``confirmed_at`` is the close of candle 3.

    ``filled_at`` is the close time of the first later bar that CLOSES through the
    far side (below ``bottom`` for a bullish gap, above ``top`` for a bearish
    one). This is the source's inversion: the gap "is not respected and swiftly
    closed over". A wick through the gap does not fill it.
    """
    data = _arrays(bars, bar_duration)
    gaps = [
        FairValueGap(
            direction=gap.direction,
            time=data.open_times[gap.middle],
            top=gap.top,
            bottom=gap.bottom,
            confirmed_at=data.close_times[gap.middle + 1],
            timeframe=timeframe,
            filled_at=data.close_times[gap.fill] if gap.fill >= 0 else None,
        )
        for gap in _gaps(data)
    ]
    return _by_time(gaps)


def find_cisd(
    bars: pd.DataFrame,
    timeframe: str,
    bar_duration: pd.Timedelta,
    *,
    require_context: bool = True,
    swing_bars: int = 1,
    allow_equal: bool = False,
    doji_in_series: bool = False,
    max_bars_to_confirm: int | None = None,
) -> list[Cisd]:
    """Change in state of delivery (CISD).

    Definition (``cisd_validates_swing_points.txt``): "What defines a change in
    the state of delivery is price reaching into an important level, sweeping out
    a low or reaching into a fair value gap and then closing through the series of
    candles that reached into that important level." In practice: "I find the
    high. I find the series of [up-close] candles that made that high. Do we have
    a closure through that level?" The level is "the opening price in the series
    of candles that made the high" (TTrades page on protected swings) and is
    measured on bodies, not wicks (``equilibrium_for_expansions.txt``).

    Mechanical rules adopted (bearish; bullish is the mirror image):
    - A series is a maximal run of consecutive up-close candles; its level is the
      open of its first candle; its high is the highest high of the run.
    - If candles after the run (not up-close, e.g. the sweep candle that closes
      down) trade higher before any new up-close run starts, they extend that high
      and the series stays the same.
    - If a later up-close run trades above the high, the old series is dropped:
      the new run is now "the series that made the high" ("we have swept out a new
      high. So I'm just going to repeat the process",
      ``protected_swings_understanding_trend_and_invalidations.txt``).
    - The CISD is the first later bar that CLOSES strictly below the level.
      ``direction`` is ``"bearish"``, ``time`` is that bar, ``level`` the open
      closed through, ``confirmed_at`` that bar's close.
    - When one bar closes through several nested series, one CISD is reported, for
      the series with the highest high.

    Open choices:
    - ``require_context`` (default True): keep only changes whose series reached
      an "important level" on THIS frame before confirming: it was the first to
      trade above a prior swing high (``swing_bars`` / ``allow_equal`` as in
      :func:`find_swings`), or it traded into a bearish fair value gap that was
      confirmed and unfilled. The level must predate the series. Pass False to get
      every structural change, e.g. when the caller supplies the important level
      itself from a higher timeframe (previous-day high, HTF gap, candle 2 wick).
    - ``doji_in_series`` (default False): whether a close == open candle counts as
      part of a series. The source does not say; by default a doji ends a series.
    - ``max_bars_to_confirm`` (default None = unlimited): maximum number of bars
      from the high to the confirming close. The source says speed matters ("the
      best setups form within one to three candles",
      ``why_your_continuations_fail_order_blocks_cisd_explained``) but sets no
      hard limit.

    Not modelled: a high made by a down-close candle with no up-close run before
    it (the source's "it would just be that body right there"), and SMT-based
    context.
    """
    data = _arrays(bars, bar_duration)
    changes = _delivery_changes(
        data,
        require_context=require_context,
        swing_bars=swing_bars,
        allow_equal=allow_equal,
        doji_in_series=doji_in_series,
        max_bars_to_confirm=max_bars_to_confirm,
    )
    events = [
        Cisd(
            direction="bearish" if change.side == "high" else "bullish",
            time=data.open_times[change.confirm],
            level=change.level,
            confirmed_at=data.close_times[change.confirm],
            timeframe=timeframe,
        )
        for change in changes
    ]
    return _by_time(events)


def find_protected_swings(
    bars: pd.DataFrame,
    timeframe: str,
    bar_duration: pd.Timedelta,
    *,
    require_context: bool = True,
    swing_bars: int = 1,
    allow_equal: bool = False,
    doji_in_series: bool = False,
    max_bars_to_confirm: int | None = None,
    break_on: Literal["close", "wick"] = "close",
) -> list[ProtectedSwing]:
    """Protected highs and lows.

    Definition (``protected_swings_understanding_trend_and_invalidations.txt``):
    "A protected swing is a high or low in which I'm expecting to hold as the
    trend continues ... If we are bullish, I want to see a low or a short-term low
    be ran out or swept and then close through the series of down-close candles
    that made the low ... once price closes over that level. This is now a
    protected low." The second type is "one formed out of a fair value gap ...
    price reaching into a fair value gap. I then find the low ... the series of
    down-closed candles that form that low. Once price closes over that level, I
    then anticipate this low to hold."

    So a protected swing is the extreme behind a CISD: each event here pairs with
    the :func:`find_cisd` event of the same ``confirmed_at`` (protected high <->
    bearish CISD, protected low <-> bullish CISD) when both are called with the
    same parameters. ``time`` / ``price`` are the bar and wick price of the
    extreme; ``confirmed_at`` is the close of the bar that closed through the
    series. ``require_context``, ``swing_bars``, ``allow_equal``,
    ``doji_in_series`` and ``max_bars_to_confirm`` mean what they mean in
    :func:`find_cisd`. The SMT variant from the source is not modelled.

    ``broken_at`` is the close time of the first bar after confirmation that
    breaks the swing. Open choice ``break_on``: ``"close"`` (default) needs a
    close strictly beyond the swing price; ``"wick"`` needs only a trade beyond
    it. The source speaks of the wick "remaining intact" and of the swing being
    "taken out", which reads closer to ``"wick"``; the default follows the
    companion contract ("when a later close breaks it").
    """
    if break_on not in ("close", "wick"):
        raise ValueError("break_on must be 'close' or 'wick'")
    data = _arrays(bars, bar_duration)
    changes = _delivery_changes(
        data,
        require_context=require_context,
        swing_bars=swing_bars,
        allow_equal=allow_equal,
        doji_in_series=doji_in_series,
        max_bars_to_confirm=max_bars_to_confirm,
    )
    events: list[ProtectedSwing] = []
    for change in changes:
        is_high = change.side == "high"
        if break_on == "close":
            probe = data.closes
        else:
            probe = data.highs if is_high else data.lows
        broken = _first_beyond(probe, change.confirm + 1, change.extreme, above=is_high)
        events.append(
            ProtectedSwing(
                kind=change.side,
                time=data.open_times[change.extreme_idx],
                price=change.extreme,
                confirmed_at=data.close_times[change.confirm],
                timeframe=timeframe,
                broken_at=data.close_times[broken] if broken >= 0 else None,
            )
        )
    return _by_time(events)
