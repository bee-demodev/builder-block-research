"""``TradingViewBarSource``: the companion's bars, read from TradingView Desktop.

How each timeframe is sourced
-----------------------------
History (once per symbol and timeframe, the first time it is asked for)
    Read natively from TradingView, at that timeframe, through a private data series
    (``companion.tradingview.bridge``; no chart is involved), as deep as the caller's
    lookback needs (older bars are requested when the first read is too short). Times are converted by ``companion.tradingview.mapping``.
    ``4h`` is built from native ``1h`` bars when TradingView's own ``4h`` bars do not sit
    on the 18:00 New York grid.

Keeping current (``refresh``, called when an entry-timeframe bar closes)
    Only the entry timeframe is read again: its last few bars, from its private series,
    which TradingView keeps streaming. Higher timeframes follow from that:

    - intraday (up to 4h): a bar that has closed since the history was read is built
      from the entry bars with ``companion.bars.resample``, the same arithmetic the
      saved-history mode uses, so it equals TradingView's own bar by construction;
    - daily, weekly, monthly: when one closes (once a day at most) TradingView's own
      bar is read again, because its close can be the settlement price rather than the
      last trade. If that read fails, or ``daily_and_above`` is ``"derived"``, the bar
      is built from the entry bars instead;
    - a timeframe the entry bars do not nest in (a custom ``5m`` over ``3m``) is always
      read natively when one of its bars closes.

No lookahead
------------
Only bars whose scheduled close lies at least ``settle_seconds`` before the clock are
kept at all; the forming bar TradingView sends is dropped. A caller that asks for it
(``refresh(..., close_on_next_bar=True)``, the headless core's live loop) also keeps an
intraday entry bar as soon as TradingView has sent a newer bar after it: TradingView
opens the next bar on the first trade after the close, so every trade of the bar before
it has arrived, which is what the settle time waits for. The newest bar is never kept
that way. ``get_bars`` then returns
only bars closed at ``as_of``, so stepping back through the loaded history is as strict
as the saved-history mode.
"""

from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol, Sequence

import pandas as pd

from companion.bars import TimeLike, _empty_bars, bar_close_times, closed_bars, resample
from companion.timeframes import Timeframe, parse_timeframe, to_new_york
from companion.tradingview import symbols as _symbols
from companion.tradingview.errors import TradingViewError
from companion.tradingview.mapping import resolution_for, rows_to_frame
from companion.types import BARS_TIMEZONE

INITIAL_BARS = 300  # TradingView sends about this many with a chart anyway
MAX_BARS = 20_000
TAIL_MARGIN = 4


@dataclass(frozen=True)
class BarsPayload:
    """What a bridge returns for one read of the feed's chart."""

    rows: Sequence[Sequence[float]]  # [time, open, high, low, close, volume], oldest first, forming bar included
    exhausted: bool = False  # TradingView has no bars older than rows[0]
    ticker: str = ""  # the symbol as TradingView names it
    notes: tuple[str, ...] = ()  # e.g. "delayed by 600 seconds"
    forming_until: float | None = None  # UTC seconds: when TradingView says the newest row closes, if it says


class Bridge(Protocol):
    """The only thing the source knows about TradingView. Tests substitute a fake."""

    def fetch_bars(self, ticker: str, resolution: str, count: int) -> BarsPayload:
        """The last ``count`` bars of ``ticker`` at ``resolution``, forming bar included.

        Asks TradingView for older bars when fewer than ``count`` are held. Raises
        ``TradingViewError``.
        """
        ...

    def park(self, ticker: str, resolution: str) -> None:
        """Name the series the window rests on (the entry timeframe): it is the last to be closed to make room."""
        ...

    def close(self) -> None: ...

    # Optional. A bridge without it simply gives the watcher nothing (``TradingViewBarSource.peek`` -> None).
    def peek(self, ticker: str, resolution: str) -> dict[str, Any] | None:
        """``{"rows": [...]}`` with the newest two bars of an already open series (forming bar last),
        without waiting or connecting; ``None`` when that cannot be read right now. Never raises."""
        ...


@dataclass(frozen=True)
class LiveUpdate:
    """Result of one ``refresh``."""

    symbol: str
    ticker: str
    timeframe: str
    last_open: pd.Timestamp  # open of the last closed entry bar (New York)
    last_close: pd.Timestamp  # its close: the moment the data is good for
    new_bars: int  # closed entry bars that were not known before
    notes: tuple[str, ...] = ()
    revised: int = 0  # bars already held whose prices or volume changed on this read


@dataclass(frozen=True)
class FeedPeek:
    """The newest bars TradingView holds for one timeframe, read cheaply (``TradingViewBarSource.peek``)."""

    symbol: str
    timeframe: str
    bars: pd.DataFrame  # the newest one or two bars in the companion's conventions; the last may still be forming
    followed_close: pd.Timestamp | None  # close of the bar TradingView has already followed with a newer one (New York)

    @property
    def newest(self) -> pd.Series:
        return self.bars.iloc[-1]


@dataclass
class _Series:
    frame: pd.DataFrame
    exhausted: bool = False
    origin: dict[str, int] = field(default_factory=lambda: {"native": 0, "derived": 0})


def nests(lower: Timeframe, higher: Timeframe) -> bool:
    """Whether whole ``lower`` bars make up every ``higher`` bar on the companion's grid."""
    if lower.nominal_minutes >= higher.nominal_minutes:
        return False
    if lower.minutes is not None:
        return 1440 % lower.minutes == 0 and (higher.minutes is None or higher.minutes % lower.minutes == 0)
    return lower.kind == "day" and lower.count == 1  # days make weeks and months; weeks do not make months


class TradingViewBarSource:
    """``BarSource`` over TradingView Desktop. See the module text for what comes from where."""

    def __init__(
        self,
        bridge: Bridge | None = None,
        *,
        symbols_path: Path | None = None,
        clock: Callable[[], pd.Timestamp] | None = None,
        bridge_factory: Callable[[], Bridge] | None = None,
    ) -> None:
        self._bridge = bridge
        self._bridge_factory = bridge_factory
        self._symbols_path = symbols_path
        self._clock = clock
        self._store: dict[tuple[str, str], _Series] = {}
        self._lock = threading.RLock()
        self._parked: tuple[str, str] | None = None  # (ticker, resolution) the chart should rest on
        self._last: LiveUpdate | None = None
        self._notes: tuple[str, ...] = ()
        self._revised = 0  # bars already held that the reads of the running refresh changed
        self.load_seconds = 0.0  # wall clock spent reading bars from TradingView, all reads together

    # --- what the window shows ---

    @property
    def description(self) -> str:
        last = self._last
        if last is None:
            return "TradingView live — not connected yet"
        extra = "".join(f" — {note}" for note in last.notes)
        return f"TradingView live — {last.ticker} — last bar closed {last.last_close.strftime('%H:%M')}{extra}"

    def has_symbol(self, symbol: str) -> bool:
        try:
            ticker = self.ticker(symbol)
        except TradingViewError:
            return True  # nothing will be loaded: the check fails with the reason at once
        return any(key[0] == ticker for key in list(self._store))

    def symbols(self) -> list[str]:
        return _symbols.list_symbols(self._symbols_path)

    def ticker(self, symbol: str) -> str:
        return _symbols.ticker_for(symbol, self._symbols_path)

    def settings(self) -> _symbols.FeedSettings:
        return _symbols.settings(self._symbols_path)

    def now(self) -> pd.Timestamp:
        """The clock, as a New York timestamp."""
        # whole milliseconds: the bar index is in microseconds and refuses a finer moment
        if self._clock is not None:
            return to_new_york(self._clock()).floor("ms")
        return pd.Timestamp.now(tz=BARS_TIMEZONE).floor("ms")

    def last_closed(self, symbol: str, timeframe: str) -> pd.Timestamp | None:
        """Close time of the newest closed bar held for ``timeframe``, or ``None``."""
        covered = self.coverage(symbol, timeframe)
        return covered[1] if covered else None

    def coverage(self, symbol: str, timeframe: str) -> tuple[pd.Timestamp, pd.Timestamp] | None:
        """(close of the oldest bar held, close of the newest) for ``timeframe``, or ``None``."""
        tf = parse_timeframe(timeframe)
        # no lock: the window asks this from its own thread while a check may hold the lock
        series = self._store.get((self.ticker(symbol), tf.label))
        frame = series.frame if series is not None else None
        if frame is None or frame.empty:
            return None
        closes = bar_close_times(frame.iloc[[0, -1]], tf)
        return closes[0], closes[1]

    def origin(self, symbol: str, timeframe: str) -> dict[str, int]:
        """How many reads of this timeframe were native and how many bars were derived."""
        series = self._store.get((self.ticker(symbol), parse_timeframe(timeframe).label))
        return dict(series.origin) if series is not None else {}

    def close(self) -> None:
        """Drop the link. Does not wait for a read that is still running."""
        if self._lock.acquire(timeout=0.5):
            try:
                if self._bridge is not None:
                    self._bridge.close()
            finally:
                self._lock.release()

    # --- BarSource ---

    def get_bars(self, symbol: str, timeframe: str, as_of: TimeLike, lookback: int) -> pd.DataFrame:
        if lookback < 0:
            raise ValueError("lookback must be >= 0")
        tf = parse_timeframe(timeframe)
        moment = to_new_york(as_of).floor("us")
        with self._lock:
            ticker = self.ticker(symbol)
            key = (ticker, tf.label)
            series = self._store.get(key)
            if series is None:
                series = self._read_native(ticker, tf, lookback + max(20, lookback // 10))
            have = self._closed_at(series.frame, tf, moment)
            if have < lookback and not series.exhausted and len(series.frame) < MAX_BARS:
                short = lookback - have
                series = self._read_native(ticker, tf, len(series.frame) + short + max(20, short // 10))
                have = self._closed_at(series.frame, tf, moment)
            return series.frame.iloc[max(0, have - lookback) : have].copy()

    # --- keeping current ---

    def refresh(self, symbol: str, entry_timeframe: str, *, close_on_next_bar: bool = False) -> LiveUpdate:
        """Read the newest entry-timeframe bars and bring every loaded timeframe up to date.

        Cheap when nothing has to be switched: one read of a handful of bars from the
        parked chart. Raises ``TradingViewError`` when TradingView cannot be read.

        ``close_on_next_bar``: an intraday entry bar TradingView has already followed with
        a newer one counts as closed before the settle time (see the module text).
        """
        tf = parse_timeframe(entry_timeframe)
        with self._lock:
            ticker = self.ticker(symbol)
            key = (ticker, tf.label)
            now = self.now()
            series = self._store.get(key)
            before = series.frame.index[-1] if series is not None and len(series.frame) else None
            self._revised = 0
            if series is None or before is None:
                series = self._read_native(ticker, tf, INITIAL_BARS, park=False, next_bar_closes=close_on_next_bar)
            else:
                last_close = bar_close_times(series.frame.iloc[-1:], tf)[0]
                behind = max(0.0, (now - last_close) / pd.Timedelta(minutes=tf.nominal_minutes))
                count = int(min(MAX_BARS, math.ceil(behind) + TAIL_MARGIN + 2))
                while True:
                    series, first = self._read_native(ticker, tf, count, park=False, first_read=True, next_bar_closes=close_on_next_bar)
                    # the read must reach back to a bar already held, or bars in between are missing
                    if first is None or first <= before or series.exhausted or count >= MAX_BARS:
                        break
                    count = min(MAX_BARS, count * 4)
            self._parked = (ticker, resolution_for(tf))
            if series.frame.empty:
                raise TradingViewError("no_permission", ticker, technical="no closed bars in the entry timeframe")
            for (other_ticker, label), other in list(self._store.items()):
                if other_ticker == ticker and label != tf.label:
                    self._advance(ticker, parse_timeframe(label), other, tf, series.frame, now, close_on_next_bar)
            last_open = series.frame.index[-1]
            new_bars = int((series.frame.index > before).sum()) if before is not None else len(series.frame)
            self._last = LiveUpdate(
                symbol=symbol.upper(),
                ticker=ticker,
                timeframe=tf.label,
                last_open=last_open,
                last_close=bar_close_times(series.frame.iloc[-1:], tf)[0],
                new_bars=new_bars,
                notes=self._notes,
                revised=self._revised,
            )
            return self._last

    def peek(self, symbol: str, timeframe: str) -> FeedPeek | None:
        """The newest bars TradingView holds for ``timeframe``, forming bar included, from one
        cheap read of the series a ``refresh`` has opened. ``None`` when they cannot be read
        right now (no link yet, a read is running, the page does not answer). Never raises,
        never waits for the lock a check holds, and never feeds the store: what it returns is
        for display and for noticing that a bar has closed, never for a verdict.
        """
        bridge = self._bridge
        peek = getattr(bridge, "peek", None)
        if bridge is None or not callable(peek):
            return None
        try:
            tf = parse_timeframe(timeframe)
            answer = peek(self.ticker(symbol), resolution_for(tf))
            rows = answer.get("rows") if isinstance(answer, dict) else None
            if not rows:
                return None
            frame = rows_to_frame(rows, tf, self.settings().daily_stamp_shift_days)
        except Exception:  # a watcher must never break the live mode
            return None
        if frame.empty:
            return None
        followed = bar_close_times(frame.iloc[-2:-1], tf)[0] if len(frame) > 1 and tf.is_intraday else None
        return FeedPeek(symbol.upper(), tf.label, frame, followed)

    # --- internals ---

    def _bridge_or_raise(self) -> Bridge:
        if self._bridge is None:
            if self._bridge_factory is not None:
                self._bridge = self._bridge_factory()
            else:
                from companion.tradingview.bridge import CdpBridge  # the fake-bridge tests never import it

                self._bridge = CdpBridge(self.settings())
        return self._bridge

    @staticmethod
    def _closed_at(frame: pd.DataFrame, tf: Timeframe, moment: pd.Timestamp) -> int:
        if frame.empty:
            return 0
        return int(bar_close_times(frame, tf).searchsorted(moment, side="right"))

    def _fetch_frame(self, ticker: str, tf: Timeframe, count: int) -> tuple[pd.DataFrame, BarsPayload]:
        """One native read, converted, its time added to ``load_seconds``."""
        started = time.perf_counter()
        try:
            return self._fetch_frame_once(ticker, tf, count)
        finally:
            self.load_seconds += time.perf_counter() - started

    def _fetch_frame_once(self, ticker: str, tf: Timeframe, count: int) -> tuple[pd.DataFrame, BarsPayload]:
        """One native read, converted. ``4h`` falls back to native ``1h`` bars when it has to."""
        bridge = self._bridge_or_raise()
        shift = self.settings().daily_stamp_shift_days
        payload = bridge.fetch_bars(ticker, resolution_for(tf), count)
        try:
            return rows_to_frame(payload.rows, tf, shift), payload
        except TradingViewError as error:
            if error.kind != "unexpected_bars" or tf.label != "4h":
                raise
        hourly = bridge.fetch_bars(ticker, resolution_for("1h"), min(MAX_BARS, count * 4 + 8))
        built = resample(rows_to_frame(hourly.rows, "1h", shift), tf)
        return built.iloc[1:], hourly  # the first bucket may have started before the bars read

    def _read_native(self, ticker: str, tf: Timeframe, count: int, *, park: bool = True, first_read: bool = False, next_bar_closes: bool = False):  # type: ignore[no-untyped-def]
        """Read ``count`` bars natively and merge the closed ones into the store.

        Returns the series, or ``(series, open of the first bar read)`` with ``first_read``.
        ``next_bar_closes``: an intraday bar followed by a newer one in this read is closed.
        """
        count = int(min(MAX_BARS, max(count, 8)))
        frame, payload = self._fetch_frame(ticker, tf, count)
        if not len(payload.rows):
            raise TradingViewError("no_permission", ticker, technical=f"no {tf.label} bars at all")
        if payload.notes:
            self._notes = tuple(payload.notes)
        settled = self.now() - pd.Timedelta(seconds=self.settings().settle_seconds)
        closed = closed_bars(frame, tf, settled)
        if next_bar_closes and tf.is_intraday and len(frame) > len(closed) + 1:
            closed = frame.iloc[:-1]  # TradingView has opened the bar after each of these: they are final
        if payload.forming_until is not None and not tf.is_intraday and len(closed) and closed.index[-1] == frame.index[-1]:
            # TradingView's own close time for its newest daily / weekly / monthly bar wins over the
            # calendar: around a holiday that bar runs on into the next trading day (see mapping).
            if pd.Timestamp(float(payload.forming_until), unit="s", tz="UTC") > settled:
                closed = closed.iloc[:-1]
        key = (ticker, tf.label)
        series = self._store.get(key)
        if series is None:
            series = self._store[key] = _Series(_empty_bars())
        self._revised += self._changed(series.frame, closed)
        series.frame = self._merge(series.frame, closed)
        series.exhausted = bool(payload.exhausted or len(payload.rows) < count) if count >= len(series.frame) else series.exhausted
        series.origin["native"] += 1
        if park and self._parked is not None and self._parked != (ticker, resolution_for(tf)):
            try:
                self._bridge_or_raise().park(*self._parked)
            except TradingViewError:
                pass  # the next refresh switches back itself
        if first_read:
            return series, (frame.index[0] if len(frame) else None)
        return series

    @staticmethod
    def _changed(old: pd.DataFrame, new: pd.DataFrame) -> int:
        """How many bars of ``new`` were held already with other values."""
        if old.empty or new.empty:
            return 0
        both = new.index.intersection(old.index)
        if not len(both):
            return 0
        return int((old.loc[both, list(new.columns)] != new.loc[both]).any(axis=1).sum())

    @staticmethod
    def _merge(old: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
        if old.empty:
            return new.copy()
        if new.empty:
            return old
        kept = old[~old.index.isin(new.index)]
        return pd.concat([kept, new]).sort_index(kind="stable")

    def _advance(
        self, ticker: str, tf: Timeframe, series: _Series, entry_tf: Timeframe, entry: pd.DataFrame, now: pd.Timestamp, early: bool = False
    ) -> None:
        """Add the ``tf`` bars that have closed since ``series`` was last brought up to date.

        ``early``: the entry bars were kept on TradingView's next bar rather than the settle
        time, so a bar built from them is complete once the last of them has closed.
        """
        if series.frame.empty or entry.empty or tf.nominal_minutes <= entry_tf.nominal_minutes:
            return
        settings = self.settings()
        settled = now - pd.Timedelta(seconds=settings.settle_seconds)
        if early:
            settled = max(settled, bar_close_times(entry.iloc[-1:], entry_tf)[0])
        last_close = bar_close_times(series.frame.iloc[-1:], tf)[0]
        fresh = entry[entry.index >= last_close]
        if fresh.empty:
            return
        derived = closed_bars(resample(fresh, tf), tf, settled)
        if derived.empty:
            return  # the bar after the last one held is still forming
        can_derive = nests(entry_tf, tf) and entry.index[0] <= last_close
        want_native = not can_derive or (not tf.is_intraday and settings.daily_and_above != "derived")
        if want_native:
            try:
                self._read_native(ticker, tf, len(derived) + TAIL_MARGIN)
            except TradingViewError:
                if not can_derive:
                    raise
            else:
                held = bar_close_times(series.frame.iloc[-1:], tf)[0]
                derived = derived[derived.index >= held]  # what TradingView has not published yet, if anything
                if derived.empty or not can_derive:
                    return
        series.frame = self._merge(series.frame, derived)
        series.origin["derived"] += len(derived)
