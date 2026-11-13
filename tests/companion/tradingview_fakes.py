"""A fake TradingView for the live-feed tests: a made-up minute market behind the ``Bridge`` interface.

``FakeTradingView`` answers ``fetch_bars`` the way the real chart would: bars of the
asked resolution built from every minute traded up to its clock (so the newest bar is
still forming), stamped the way TradingView stamps them, at most as many as were asked
for. It counts chart switches and history loads so tests can assert what a refresh cost.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from companion.bars import resample
from companion.tradingview.errors import TradingViewError
from companion.tradingview.mapping import RESOLUTIONS
from companion.tradingview.source import BarsPayload
from companion.types import BARS_TIMEZONE

TICKER = "CME_MINI:NQ1!"
LABEL_OF = {resolution: label for label, resolution in RESOLUTIONS.items()}


def market_minutes(start: str = "2026-01-04 18:00", end: str = "2026-03-20 17:00", seed: int = 7) -> pd.DataFrame:
    """One-minute bars for every minute the futures market is open between two New York times."""
    wall = pd.date_range(start, end, freq="1min", inclusive="left")
    minute_of_day = wall.hour * 60 + wall.minute
    weekday = wall.weekday
    shut = (
        ((minute_of_day >= 17 * 60) & (minute_of_day < 18 * 60))
        | (weekday == 5)
        | ((weekday == 4) & (minute_of_day >= 17 * 60))
        | ((weekday == 6) & (minute_of_day < 18 * 60))
    )
    wall = wall[~shut]
    rng = np.random.default_rng(seed)
    steps = rng.normal(0.0, 2.0, len(wall))
    close = 21000.0 + np.cumsum(steps)
    open_ = np.r_[21000.0, close[:-1]]
    spread = np.abs(rng.normal(0.0, 1.5, (2, len(wall))))
    frame = pd.DataFrame(
        {
            "open": open_,
            "high": np.maximum(open_, close) + spread[0],
            "low": np.minimum(open_, close) - spread[1],
            "close": close,
            "volume": rng.integers(1, 500, len(wall)).astype("float64"),
        },
        index=pd.DatetimeIndex(wall).tz_localize(BARS_TIMEZONE).as_unit("us").rename("timestamp"),
    )
    return frame.round(2)


def epoch(index: pd.DatetimeIndex) -> np.ndarray:
    return index.tz_convert("UTC").tz_localize(None).values.astype("datetime64[s]").astype("int64")


def stamp_daily(index: pd.DatetimeIndex, how: str) -> np.ndarray:
    """TradingView-style stamps for daily / weekly / monthly bars whose companion opens are ``index``."""
    if how == "session_open":  # 18:00 New York the evening before
        return epoch(index)
    trading_date = (index.tz_localize(None) + pd.Timedelta(hours=6)).normalize()
    if how == "utc_midnight":  # midnight UTC of the trading date
        return epoch(trading_date.tz_localize("UTC"))
    if how == "exchange_midnight":  # midnight Chicago of the trading date
        return epoch(trading_date.tz_localize("America/Chicago"))
    if how == "day_early":  # a build that stamps the day before: must be refused or corrected
        return epoch((trading_date - pd.Timedelta(days=1)).tz_localize("UTC"))
    raise ValueError(how)


class FakeTradingView:
    """``Bridge`` over a minute market. ``now`` is the clock; move it to let time pass."""

    def __init__(
        self,
        minutes: pd.DataFrame,
        now: str | pd.Timestamp,
        *,
        tickers: tuple[str, ...] = (TICKER,),
        daily_stamp: str = "session_open",
        preloaded: int = 300,
        history_limit: int | None = None,
        utc_anchored_4h: bool = False,
    ) -> None:
        self.minutes = minutes
        self.now = pd.Timestamp(now, tz=BARS_TIMEZONE) if pd.Timestamp(now).tzinfo is None else pd.Timestamp(now)
        self.tickers = tickers
        self.daily_stamp = daily_stamp
        self.preloaded = preloaded
        self.history_limit = history_limit
        self.utc_anchored_4h = utc_anchored_4h
        self.error: Exception | None = None
        self.calls: list[tuple[str, str, int]] = []
        self.parks: list[tuple[str, str]] = []
        self.deepened: list[tuple[str, int]] = []
        self.loaded: dict[tuple[str, str], int] = {}
        self.chart: tuple[str, str] | None = None
        self.switches = 0
        self.closed = False
        self.peeks = 0
        self.peek_fails = False
        self._cache: dict[tuple[str, pd.Timestamp], pd.DataFrame] = {}

    def clock(self) -> pd.Timestamp:
        return self.now

    def advance(self, **delta: float) -> pd.Timestamp:
        self.now = self.now + pd.Timedelta(**delta)
        return self.now

    def visible(self) -> pd.DataFrame:
        """Every minute bar that has opened: the newest one is still forming."""
        return self.minutes[self.minutes.index < self.now]

    def native(self, label: str) -> pd.DataFrame:
        """The chart's bars at a timeframe, companion-indexed, forming bar included."""
        key = (label, self.now)
        if key not in self._cache:
            self._cache.clear() if len(self._cache) > 40 else None
            self._cache[key] = resample(self.visible(), label)
        return self._cache[key]

    def _show(self, ticker: str, resolution: str) -> None:
        if self.chart != (ticker, resolution):
            self.switches += 1
            self.chart = (ticker, resolution)

    def fetch_bars(self, ticker: str, resolution: str, count: int) -> BarsPayload:
        self.calls.append((ticker, resolution, count))
        if self.error is not None:
            raise self.error
        if ticker not in self.tickers:
            raise TradingViewError("symbol_not_found", ticker)
        self._show(ticker, resolution)
        label = LABEL_OF[resolution]
        frame = self.native(label)
        if label == "4h" and self.utc_anchored_4h:
            visible = self.visible()
            bucket = epoch(visible.index) // 14400
            grouped = visible.groupby(bucket)
            frame = grouped.agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
            stamps = frame.index.to_numpy() * 14400
        elif label in ("1D", "1W", "1M"):
            stamps = stamp_daily(frame.index, self.daily_stamp)
        else:
            stamps = epoch(frame.index)
        available = len(frame) if self.history_limit is None else min(len(frame), self.history_limit)
        if count > self.loaded.get((ticker, resolution), self.preloaded):
            self.deepened.append((resolution, count))
            self.loaded[(ticker, resolution)] = count
        take = min(count, available)
        values = frame[["open", "high", "low", "close", "volume"]].to_numpy()[-take:]
        rows = [[int(stamp), *map(float, row)] for stamp, row in zip(stamps[-take:], values)]
        return BarsPayload(rows=rows, exhausted=count > available, ticker=ticker)

    def peek(self, ticker: str, resolution: str) -> dict[str, object] | None:
        """The newest two intraday bars, forming one last, as the page feed's ``peek`` answers. ``None`` when ``peek_fails``."""
        self.peeks += 1
        if self.peek_fails or ticker not in self.tickers:
            return None
        frame = self.native(LABEL_OF[resolution]).iloc[-2:]
        values = frame[["open", "high", "low", "close", "volume"]].to_numpy()
        return {"state": "ready", "rows": [[int(stamp), *map(float, row)] for stamp, row in zip(epoch(frame.index), values)]}

    def park(self, ticker: str, resolution: str) -> None:
        self.parks.append((ticker, resolution))
        if self.error is None:
            self._show(ticker, resolution)

    def close(self) -> None:
        self.closed = True


def write_symbols(path: Path, symbols: dict[str, object] | None = None, **settings: object) -> Path:
    """A symbols.json for a test; settle time 3 s unless given."""
    body = {
        "symbols": symbols if symbols is not None else {"NQ": {"ticker": TICKER}},
        "settings": {"settle_seconds": 3, **settings},
    }
    path.write_text(json.dumps(body), encoding="utf-8")
    return path
