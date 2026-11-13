"""TradingView bar times -> the companion's bar conventions.

TradingView hands out ``[time, open, high, low, close, volume]`` with ``time`` in UTC
seconds. What that time means depends on the timeframe:

Intraday (1m .. 4h)
    The bar's open. Converted to New York it is already the companion's open time, as
    long as the bars sit on the grid the companion uses (anchored to the 18:00 New York
    session open). Minute and hour bars always do. ``4h`` does only if TradingView
    anchors it to the session open; when most bars are off the grid this module refuses
    them (``unexpected_bars``) and the source builds ``4h`` from ``1h`` bars instead.

Daily, weekly, monthly
    Not the companion's open, and not documented. Depending on the build it is the
    session open (18:00 New York the evening before), midnight UTC of the trading date,
    or midnight exchange time. All of these lie INSIDE the trading day the bar belongs
    to (18:00 the evening before -> 17:00), so the bar is placed by one rule that does
    not care which of them it is: *the trading day that contains the stamp*. From that
    trading date the companion's own open is computed with the same bucket arithmetic
    ``companion.bars.resample`` uses (daily: 18:00 the evening before; weekly: Sunday
    18:00; monthly: the evening before the month's first weekday).

    Verified on TradingView Desktop 3.5.0 (2026-11-12): the stamp is the session open,
    18:00 New York the evening before (Sunday 18:00 for a week; the evening before the
    month's first session), for futures and for stocks alike.

    Holidays: on a CME holiday with a shortened session (Martin Luther King Day, 4 July,
    Thanksgiving ...) TradingView has no bar for the holiday itself. That session is part
    of the NEXT trading day's bar, which is stamped at the holiday session's open. The
    companion keeps TradingView's bar as it is and places it on the day its stamp falls
    in (the holiday), so that day's bar also holds the following day and the following
    day has none. The saved-history mode would show two bars there.

    If a TradingView build ever stamps these bars outside their trading day, set
    ``daily_stamp_shift_days`` in ``companion/config/symbols.json`` (+1 / -1). A daily
    bar that lands on a Saturday or Sunday is refused rather than misread.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd

from companion.bars import _SESSION_OPEN_HOUR, _empty_bars, _wall_minutes, resample
from companion.timeframes import Timeframe, parse_timeframe
from companion.tradingview.errors import TradingViewError
from companion.types import BARS_COLUMNS, BARS_TIMEZONE

# companion label -> the string TradingView's chart calls the resolution
RESOLUTIONS: dict[str, str] = {
    "1m": "1", "3m": "3", "5m": "5", "15m": "15", "30m": "30", "1h": "60", "4h": "240", "1D": "1D", "1W": "1W", "1M": "1M",
}  # fmt: skip
_ALIASES = {"D": "1D", "W": "1W", "M": "1M"}
OFF_GRID_LIMIT = 0.05  # more than this share of bars off the companion's grid: refuse


def resolution_for(timeframe: str | Timeframe) -> str:
    return RESOLUTIONS[parse_timeframe(timeframe).label]


def same_resolution(left: object, right: object) -> bool:
    """``"D"`` and ``"1D"`` are the same chart resolution."""
    a, b = str(left).strip().upper(), str(right).strip().upper()
    return _ALIASES.get(a, a) == _ALIASES.get(b, b)


def same_ticker(wanted: str, shown: object) -> bool:
    """Whether the chart shows ``wanted``. ``NQZ2026`` matches ``CME_MINI:NQZ2026``."""
    a, b = str(wanted).strip().upper(), str(shown).strip().upper()
    if not a or not b:
        return False
    return a == b or (":" not in a and b.endswith(":" + a)) or (":" not in b and a.endswith(":" + b))


def stamps_to_new_york(times: Sequence[float]) -> pd.DatetimeIndex:
    """UTC epoch seconds (or milliseconds) -> New York timestamps."""
    values = np.asarray(times, dtype="float64")
    if len(values) and float(np.nanmax(values)) > 1e11:  # milliseconds
        values = values / 1000.0
    utc = pd.to_datetime(np.round(values).astype("int64"), unit="s", utc=True)
    return pd.DatetimeIndex(utc).tz_convert(BARS_TIMEZONE).as_unit("us").rename("timestamp")


def off_grid(index: pd.DatetimeIndex, timeframe: str | Timeframe) -> np.ndarray:
    """Which intraday opens are not on the companion's grid (anchored to 18:00 New York)."""
    minutes = parse_timeframe(timeframe).minutes
    if minutes is None or not len(index):
        return np.zeros(len(index), dtype=bool)
    return (_wall_minutes(index) - _SESSION_OPEN_HOUR * 60) % minutes != 0


def trading_dates(index: pd.DatetimeIndex, shift_days: int = 0) -> pd.DatetimeIndex:
    """The trading day (18:00 the evening before -> 17:00) containing each stamp."""
    wall = index.tz_convert(BARS_TIMEZONE).tz_localize(None)
    return (wall + pd.Timedelta(hours=24 - _SESSION_OPEN_HOUR)).normalize() + pd.Timedelta(days=shift_days)


def rows_to_frame(rows: Sequence[Sequence[float]], timeframe: str | Timeframe, shift_days: int = 0) -> pd.DataFrame:
    """TradingView rows -> a bars frame in the companion's conventions.

    The result still contains the forming bar if TradingView sent one: whether a bar is
    closed is decided by the caller, against the clock.
    """
    tf = parse_timeframe(timeframe)
    clean = [row for row in rows if row is not None and len(row) >= 5 and all(value is not None for value in row[:5])]
    if not clean:
        return _empty_bars()
    table = np.asarray([[*row[:5], row[5] if len(row) > 5 and row[5] is not None else 0.0] for row in clean], dtype="float64")
    stamps = stamps_to_new_york(table[:, 0])
    frame = pd.DataFrame(table[:, 1:6], index=stamps, columns=list(BARS_COLUMNS))
    frame = frame[~frame.index.duplicated(keep="last")].sort_index()

    if tf.is_intraday:
        wrong = off_grid(frame.index, tf)
        if wrong.mean() > OFF_GRID_LIMIT:
            sample = ", ".join(moment.strftime("%a %H:%M") for moment in frame.index[wrong][-3:])
            raise TradingViewError(
                "unexpected_bars",
                f"its {tf.label} bars open at {sample} New York, not on the 18:00 session grid",
                technical=f"{int(wrong.sum())} of {len(frame)} {tf.label} bars off grid",
            )
        return resample(frame, tf) if wrong.any() else frame

    dates = trading_dates(frame.index, shift_days)
    if tf.kind == "day" and bool((dates.weekday >= 5).any()):
        bad = dates[dates.weekday >= 5][-1]
        raise TradingViewError(
            "unexpected_bars",
            f"a daily bar landed on {bad.strftime('%A %Y-%m-%d')}; adjust daily_stamp_shift_days in companion/config/symbols.json",
            technical=f"raw stamp {frame.index[dates.weekday >= 5][-1].tz_convert('UTC').isoformat()}",
        )
    # A weekly or monthly bar that starts with a shortened holiday session starts early: CME
    # books that session to the next trading day, so TradingView opens the next week's bar
    # on a Thursday evening (Friday holiday) and the next month's bar on the last evening
    # of the month before (seen for NQ: weeks of 4 July and Juneteenth, June 2010 and 2021).
    # The week is therefore the one three days after the stamp's trading date, the month
    # the one a week after it; a normal bar (Monday, or the 1st to 4th) is not moved by this.
    if tf.kind == "week":
        later = dates + pd.Timedelta(days=3)
        dates = later - pd.to_timedelta(later.weekday, unit="D") + pd.Timedelta(days=2)  # that week's Wednesday
    elif tf.kind == "month":
        later = dates + pd.Timedelta(days=7)
        middle = later - pd.to_timedelta(later.day - 15, unit="D")  # the 15th of that month
        dates = middle + pd.to_timedelta(np.where(middle.weekday == 5, -1, np.where(middle.weekday == 6, 1, 0)), unit="D")
    # Noon of a trading date lies inside the trading day, so resampling the bars placed
    # there yields exactly the open the companion gives that day, week or month.
    placed = frame.copy()
    placed.index = (dates + pd.Timedelta(hours=12)).tz_localize(BARS_TIMEZONE).as_unit("us").rename("timestamp")
    if not placed.index.is_unique:
        raise TradingViewError("unexpected_bars", f"two {tf.label} bars fall on the same trading day")
    mapped = resample(placed, tf)
    if len(mapped) != len(placed):
        raise TradingViewError("unexpected_bars", f"two {tf.label} bars fall in the same {tf.kind}")
    return mapped
