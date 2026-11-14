"""Everything one evaluation reads: the three closed frames and the forming bias candle.

This is the only module of the style that talks to the ``BarSource``. It asks for bars
closed at ``as_of`` and nothing else, so nothing downstream can look ahead.

The forming bias candle ``B[0]`` is never read from the bias frame. It is synthesised
from the closed entry-timeframe bars that open at or after the close of ``B[-1]``
(rules.md 2.1).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from companion.bars import BarSource, bar_close_times
from companion.styles.ttrades.config import TTradesConfig, clock_minutes
from companion.styles.ttrades.primitives import BEAR, BULL, Bars, Side, WickRead, fmt, when
from companion.timeframes import bar_close_time, parse_timeframe
from companion.types import TimeframeStack


@dataclass(frozen=True)
class Forming:
    """The still-forming bias candle, in real prices, built from closed entry bars."""

    open_time: pd.Timestamp  # scheduled open of the bias candle
    close_time: pd.Timestamp  # scheduled close
    e_start: int  # position in the entry frame of its first bar
    open: float
    high: float
    low: float
    last: float
    high_pos: int  # entry-frame position of the bar that made the high
    low_pos: int
    high_time: pd.Timestamp
    low_time: pd.Timestamp


@dataclass
class Context:
    symbol: str
    as_of: pd.Timestamp
    stack: TimeframeStack
    cfg: TTradesConfig
    b: pd.DataFrame
    s: pd.DataFrame
    e: pd.DataFrame
    forming: Forming | None
    b_last_close: pd.Timestamp | None  # close time of B[-1] = where B[0] begins
    avg_range: float | None
    lookback: int
    adr: float | None = None  # mean high - low of the last ``adr_days`` closed 1D bars, whatever the stack
    d: pd.DataFrame | None = None  # those closed 1D bars
    # closed entry-timeframe bars covering the current trading day from its 18:00 open, for
    # the intraday reference levels (None when the entry timeframe is above 1h)
    sess: pd.DataFrame | None = None
    _views: dict[str, "View"] = field(default_factory=dict)

    def view(self, side: Side) -> "View":
        if side.direction not in self._views:
            self._views[side.direction] = View(self, side)
        return self._views[side.direction]

    @property
    def bull(self) -> "View":
        return self.view(BULL)

    @property
    def bear(self) -> "View":
        return self.view(BEAR)

    def clock(self, moment: pd.Timestamp) -> int:
        return moment.hour * 60 + moment.minute

    def in_window(self, moment: pd.Timestamp, window: tuple[str, str]) -> bool:
        return clock_minutes(window[0]) <= self.clock(moment) <= clock_minutes(window[1])


class View:
    """The context seen from one side: mirrored frames plus the forming candle."""

    def __init__(self, ctx: Context, side: Side) -> None:
        self.ctx = ctx
        self.side = side
        self.B = Bars(ctx.b, ctx.stack.bias, side)
        self.S = Bars(ctx.s, ctx.stack.setup, side)
        self.E = Bars(ctx.e, ctx.stack.entry, side)
        forming = ctx.forming
        self.has_forming = forming is not None
        if forming is not None:
            self.f_open = side.sign * forming.open
            self.f_last = side.sign * forming.last
            self.f_low = forming.low if side.bullish else -forming.high
            self.f_high = forming.high if side.bullish else -forming.low
            self.f_low_pos = forming.low_pos if side.bullish else forming.high_pos
            self.f_high_pos = forming.high_pos if side.bullish else forming.low_pos
            self.f_low_time = forming.low_time if side.bullish else forming.high_time
            self.f_high_time = forming.high_time if side.bullish else forming.low_time

    def forming_wick(self) -> WickRead | None:
        """Classify the forming bias candle's wick against this side (rules.md 3.8).

        The opposing run is open minus low so far. Small needs a small run made early;
        large is a large run or a late one; anything else is unclassified.
        """
        ctx, side, forming = self.ctx, self.side, self.ctx.forming
        if forming is None or ctx.avg_range is None or ctx.avg_range <= 0:
            return None
        cfg = ctx.cfg
        run = max(0.0, self.f_open - self.f_low)
        early, timing = self.wick_timing()
        if cfg.wick_yardstick == "body":
            # the alternative yardstick: the wick against this candle's own body so far
            body = abs(self.f_last - self.f_open)
            share = run / body if body > 0 else (0.0 if run == 0 else float("inf"))
            small_at, large_at = cfg.wick_body_small_frac, cfg.wick_body_large_frac
            measure = (
                f"{share:.2f} times the candle's body so far {fmt(body)} (open {side.p(self.f_open)}, last "
                f"{side.p(self.f_last)}; small <= {small_at:g}x, large >= {large_at:g}x)"
            )
        else:
            share = run / ctx.avg_range
            small_at, large_at = cfg.wick_small_frac, cfg.wick_large_frac
            measure = (
                f"{share:.0%} of the {cfg.avg_range_bars}-candle average {ctx.stack.bias} range {fmt(ctx.avg_range)} "
                f"(small <= {small_at:.0%}, large >= {large_at:.0%})"
            )
        if share <= small_at and early:
            size = "small"
        elif share >= large_at or early is False:
            size = "large"
        else:
            size = "unclassified"
        text = (
            f"opposing run {fmt(run)} from open {side.p(self.f_open)} to {side.lo} {side.p(self.f_low)} is "
            f"{measure}; {timing}; wick is {size}"
        )
        return WickRead(size, run, early, text)

    def wick_timing(self) -> tuple[bool | None, str]:
        """(made early?, description) for the forming candle's low on this side."""
        ctx, side, forming = self.ctx, self.side, self.ctx.forming
        if forming is None:
            return None, "no forming candle"
        cfg = ctx.cfg
        made = self.f_low_time
        if parse_timeframe(ctx.stack.bias).kind == "day":
            trading_day = (forming.open_time.tz_localize(None) + pd.Timedelta(hours=6)).normalize()
            deadline = (trading_day + pd.Timedelta(minutes=clock_minutes(cfg.daily_wick_deadline))).tz_localize(
                forming.open_time.tz
            )
            early = bool(made < deadline)
            return early, (
                f"{side.lo} made at {when(made)}, {'before' if early else 'not before'} the "
                f"{cfg.daily_wick_deadline} New York deadline"
            )
        duration = forming.close_time - forming.open_time
        if duration <= pd.Timedelta(0):
            return None, "bias candle duration unknown"
        elapsed = (made - forming.open_time) / duration
        early = bool(elapsed <= cfg.wick_time_frac_max)
        return early, (
            f"{side.lo} made at {when(made)}, {elapsed:.0%} into the {ctx.stack.bias} candle "
            f"({'within' if early else 'past'} the first {cfg.wick_time_frac_max:.0%})"
        )


def _frame_bars(cfg: TTradesConfig, higher: str, lower: str, cover: int) -> int:
    ratio = parse_timeframe(higher).nominal_minutes / parse_timeframe(lower).nominal_minutes
    return int(min(cfg.max_frame_bars, math.ceil(ratio) * cover + 10))


def _forming(stack: TimeframeStack, b_last_close: pd.Timestamp, e: pd.DataFrame) -> Forming | None:
    start = int(e.index.searchsorted(b_last_close, side="left"))
    if start >= len(e):
        return None
    first = e.index[start]
    # The scheduled open is the close of B[-1], moved on past any bias candle that has
    # no bars at all (weekends, holidays).
    open_time = b_last_close
    for _ in range(1000):
        next_open = bar_close_time(open_time, stack.bias)
        if next_open > first:
            break
        open_time = next_open
    inside = e.iloc[start:]
    highs, lows = inside["high"].to_numpy(dtype=float), inside["low"].to_numpy(dtype=float)
    high_pos, low_pos = start + int(np.argmax(highs)), start + int(np.argmin(lows))
    return Forming(
        open_time=open_time,
        close_time=bar_close_time(open_time, stack.bias),
        e_start=start,
        open=float(inside["open"].iloc[0]),
        high=float(highs.max()),
        low=float(lows.min()),
        last=float(inside["close"].iloc[-1]),
        high_pos=high_pos,
        low_pos=low_pos,
        high_time=e.index[high_pos],
        low_time=e.index[low_pos],
    )


def trading_day(moment: pd.Timestamp) -> pd.Timestamp:
    """Calendar date (naive midnight) of the trading day ``moment`` belongs to: it opens at 18:00 the evening before."""
    return (moment.tz_localize(None) + pd.Timedelta(hours=6)).normalize()


def at_clock(day: pd.Timestamp, tz: object, hours: float) -> pd.Timestamp:
    """New York wall clock ``hours`` after midnight of calendar ``day`` (negative: the evening before)."""
    return (day + pd.Timedelta(hours=hours)).tz_localize(tz, nonexistent="shift_forward", ambiguous=False)


def _session_frame(
    symbol: str, as_of: pd.Timestamp, stack: TimeframeStack, source: BarSource, e: pd.DataFrame
) -> pd.DataFrame | None:
    """Closed entry-timeframe bars from the 18:00 open of the current trading day. The entry
    frame is reused when it reaches back that far; otherwise the same timeframe is asked for
    with a longer lookback (the entry frame's length serves the rules, not the session
    levels). Always the entry timeframe: it is the series a live feed keeps current, where a
    finer one would go stale between checks. So a 1h entry has no 09:30 open."""
    entry_minutes = parse_timeframe(stack.entry).nominal_minutes
    if entry_minutes > 60 or not len(e):
        return None
    opened = at_clock(trading_day(e.index[-1]), e.index.tz, -6.0)
    if e.index[0] <= opened:
        return e
    try:
        return source.get_bars(symbol, stack.entry, as_of, int(math.ceil(25 * 60 / entry_minutes)) + 10)
    except Exception:  # noqa: BLE001 - information-only levels must never fail the read
        return None


def load_context(
    symbol: str, as_of: pd.Timestamp, stack: TimeframeStack, source: BarSource, cfg: TTradesConfig
) -> Context:
    """Fetch the closed bars this evaluation may use and derive the forming bias candle."""
    needed = cfg.bias_bars_needed(stack.bias)
    b = source.get_bars(symbol, stack.bias, as_of, needed + 2)
    s = source.get_bars(symbol, stack.setup, as_of, _frame_bars(cfg, stack.bias, stack.setup, cfg.setup_cover_bias_bars))
    e = source.get_bars(symbol, stack.entry, as_of, _frame_bars(cfg, stack.bias, stack.entry, cfg.entry_cover_bias_bars))
    b_last_close: pd.Timestamp | None = None
    forming: Forming | None = None
    avg_range: float | None = None
    if len(b):
        b_last_close = bar_close_times(b.iloc[-1:], stack.bias)[0]
        forming = _forming(stack, b_last_close, e)
        recent = b.iloc[-cfg.avg_range_bars :]
        avg_range = float((recent["high"] - recent["low"]).mean())
    daily: pd.DataFrame | None = b
    if stack.bias != "1D":
        try:
            daily = source.get_bars(symbol, "1D", as_of, cfg.adr_days)
        except Exception:  # noqa: BLE001 - an information-only number must never fail the read
            daily = None
    recent_days = daily.iloc[-cfg.adr_days :] if daily is not None else None
    adr = float((recent_days["high"] - recent_days["low"]).mean()) if recent_days is not None and len(recent_days) else None
    return Context(
        symbol=symbol,
        as_of=as_of,
        stack=stack,
        cfg=cfg,
        b=b,
        s=s,
        e=e,
        forming=forming,
        b_last_close=b_last_close,
        avg_range=avg_range,
        lookback=cfg.bias_lookback(stack.bias),
        adr=adr,
        d=daily,
        sess=_session_frame(symbol, as_of, stack, source, e),
    )
