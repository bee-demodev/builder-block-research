"""Minute bars in, clean resampled bars out, never a bar that is still forming.

Everything here produces "bars frames" as defined in ``companion.types``.

Why the CSVs need cleaning
--------------------------
``data/databento/bars/{symbol}_minute.csv`` holds exactly one row per minute, but the
row is not always the front contract. Upstream collapsed every instrument of the
product (all contract months and the calendar spreads between them) into one row per
minute, and no instrument id survived. So a minute's row is one of:

- the lead (highest-volume) contract: what we want
- a calendar spread: a price near zero, often negative
- another contract month: a real price at a near-constant ratio to the lead, usually
  on a handful of contracts of volume

``clean_minute_bars`` removes the last two. Minutes whose row belonged to another
instrument stay missing: the lead contract's bar for that minute is not in the file.

The cleaning is causal. Whether a row is kept depends only on rows at or before it, so
filtering cleaned bars by ``as_of`` cannot leak later prices.
"""

from __future__ import annotations

import io
import math
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Protocol, runtime_checkable

import numpy as np
import pandas as pd

from companion import paths as _paths
from companion.timeframes import Timeframe, bar_close_time, parse_timeframe, to_new_york
from companion.types import BARS_COLUMNS, BARS_TIMEZONE

DATA_DIR = _paths.default_history_dir()  # the repo's data/databento/bars; packaged: <app>/history
SUPPORTED_SYMBOLS: tuple[str, ...] = ("NQ", "ES", "GC")

TimeLike = str | datetime | pd.Timestamp

_SESSION_OPEN_HOUR = 18  # the trading day runs 18:00 -> 17:00 New York
_WEEK_MINUTES = 7 * 1440
_INDEX_UNIT = "us"  # one resolution for every index built here, empty or not

# --- cleaning parameters ----------------------------------------------------
# Prices are compared as ratios, so the same numbers serve NQ, ES and GC.

SPREAD_LOOKBACK_ROWS = 1440  # trailing rows that define "the outright price level"
SPREAD_MAX_RATIO = 0.5  # a close under half that level is a spread, not an outright

STEP_TOLERANCE = 0.0005  # open vs the lead's last close, consecutive minutes
DRIFT_PER_SQRT_MINUTE = 0.0012  # extra tolerance per sqrt(minute) of missing time
DRIFT_CAP = 0.03
RATIO_BAND = 0.002  # how closely a row must sit on a known contract's ratio
RATIO_SMOOTHING = 0.2
MIN_CONTRACT_SEPARATION = 0.003  # other contracts are only tracked this far from the lead
FRESH_MINUTES = 5  # a contract's own last price is trusted this long
THIN_FRACTION = 0.25  # "thin" = under a quarter of the lead's recent typical volume
VOLUME_SMOOTHING = 0.1
LONG_GAP_MINUTES = 30  # after this much silence a thin row cannot resume the lead
CLAIM_VOLUME_FACTOR, CLAIM_VOLUME_SLACK = 4.0, 5.0  # volume that fits another contract
JUMP_VOLUME_FACTOR = 20.0  # volume that cannot be that contract, so the lead moved
SMALL_JUMP = 0.004  # moves this size are always attributed to the lead when not thin
LARGE_JUMP = 0.01  # larger moves need the next row to confirm them
CONFIRM_MINUTES = 5
ROLL_HALF_LIFE_ROWS = 720  # memory of the per-contract volume race (about a session)
ROLL_HYSTERESIS = 1.5  # the lead changes when another contract out-trades it 1.5:1
MAX_TRACKED_CONTRACTS = 8
WARMUP_ROWS = 120  # rows before a week that prime the tracker; their verdicts are unused


@dataclass(frozen=True)
class CleaningReport:
    """Row accounting for one ``clean_minute_bars`` call."""

    rows_in: int
    dropped_invalid: int  # NaN prices, high < low, duplicate timestamps
    dropped_spread: int  # non-positive or far below the outright price level
    dropped_other_contract: int  # an outright that does not continue the lead contract
    rows_out: int

    @property
    def dropped_total(self) -> int:
        return self.rows_in - self.rows_out

    def as_dict(self) -> dict[str, int]:
        return {**asdict(self), "dropped_total": self.dropped_total}


# --- time helpers -----------------------------------------------------------


def _empty_bars() -> pd.DataFrame:
    index = pd.DatetimeIndex([], tz=BARS_TIMEZONE, name="timestamp").as_unit(_INDEX_UNIT)
    return pd.DataFrame({column: pd.Series(dtype="float64") for column in BARS_COLUMNS}, index=index)


def _wall_minutes(index: pd.DatetimeIndex) -> np.ndarray:
    """New York wall-clock minutes since 1970-01-01 00:00 (a Thursday)."""
    return index.tz_localize(None).values.astype("datetime64[m]").astype("int64")


def _week_ids(index: pd.DatetimeIndex) -> np.ndarray:
    """Integer id of the trading week (Sunday 18:00 -> next Sunday 18:00) of each row."""
    since_sunday_open = _wall_minutes(index) - (3 * 1440 + _SESSION_OPEN_HOUR * 60)
    return since_sunday_open // _WEEK_MINUTES


def _week_start(moment: pd.Timestamp) -> pd.Timestamp:
    """The Sunday 18:00 New York that opens the trading week containing ``moment``."""
    wall = moment.tz_localize(None)
    shifted = wall - pd.Timedelta(hours=_SESSION_OPEN_HOUR)
    sunday = shifted.normalize() - pd.Timedelta(days=(shifted.weekday() + 1) % 7)
    return (sunday + pd.Timedelta(hours=_SESSION_OPEN_HOUR)).tz_localize(BARS_TIMEZONE)


# --- reading ----------------------------------------------------------------


def _parse_timestamps(text: pd.Series) -> pd.DatetimeIndex:
    """ISO timestamps with a UTC offset -> New York index.

    The files mix ``-05:00`` and ``-04:00``; parsing the wall clock and the handful of
    distinct offsets separately is several times faster than a generic parse.
    """
    text = text.astype(str)
    if len(text) and bool((text.str.len() == 25).all()):
        offsets = text.str.slice(19)
        deltas = {}
        try:
            for offset in offsets.unique():
                sign = -1 if offset[0] == "-" else 1
                deltas[offset] = sign * pd.Timedelta(hours=int(offset[1:3]), minutes=int(offset[4:6]))
            wall = pd.to_datetime(text.str.slice(0, 19), format="%Y-%m-%dT%H:%M:%S")
            utc = pd.DatetimeIndex(wall - offsets.map(deltas)).tz_localize("UTC")
            return utc.tz_convert(BARS_TIMEZONE).as_unit(_INDEX_UNIT).rename("timestamp")
        except (ValueError, IndexError):
            pass
    parsed = pd.DatetimeIndex(pd.to_datetime(text, utc=True))
    return parsed.tz_convert(BARS_TIMEZONE).as_unit(_INDEX_UNIT).rename("timestamp")


def _line_timestamp(line: bytes) -> pd.Timestamp:
    return pd.Timestamp(line.split(b",", 1)[0].decode("ascii"))


def _offset_of_first_row_at_or_after(handle: io.BufferedReader, target: pd.Timestamp, low: int, size: int) -> int:
    """Byte offset of the first data line whose timestamp is >= target.

    Binary search over a file whose rows are in time order. ``low`` must be the start
    of a line.
    """
    high = size
    while low < high:
        middle = (low + high) // 2
        handle.seek(middle - 1)
        handle.readline()  # finish the line containing byte middle-1
        line_start = handle.tell()
        if line_start >= high:
            high = middle
            continue
        line = handle.readline()
        if _line_timestamp(line) < target:
            low = line_start + len(line)
        else:
            high = line_start
    handle.seek(low - 1)
    handle.readline()
    return handle.tell()


def _csv_path(symbol: str, data_dir: Path | None) -> Path:
    if symbol.upper() not in SUPPORTED_SYMBOLS:
        raise ValueError(f"Unknown symbol {symbol!r}; supported: {', '.join(SUPPORTED_SYMBOLS)}")
    return Path(data_dir if data_dir is not None else DATA_DIR) / f"{symbol.lower()}_minute.csv"


def read_raw_minute_bars(
    symbol: str,
    start: TimeLike | None = None,
    end: TimeLike | None = None,
    *,
    data_dir: Path | None = None,
) -> pd.DataFrame:
    """The CSV rows with ``start <= open time < end``, uncleaned, as a bars frame.

    With a window only the matching byte range of the file is read. Unlike a cleaned
    frame, the result can contain spread and other-contract rows.
    """
    path = _csv_path(symbol, data_dir)
    columns = ["timestamp", *BARS_COLUMNS]
    if start is None and end is None:
        table = pd.read_csv(path, usecols=columns)
    else:
        with path.open("rb") as handle:
            header = handle.readline()
            data_start, size = handle.tell(), path.stat().st_size
            first = data_start
            last = size
            if start is not None:
                first = _offset_of_first_row_at_or_after(handle, to_new_york(start), data_start, size)
            if end is not None:
                last = _offset_of_first_row_at_or_after(handle, to_new_york(end), first, size)
            handle.seek(first)
            body = handle.read(max(0, last - first))
        table = pd.read_csv(io.BytesIO(header + body), usecols=columns)
    frame = table[list(BARS_COLUMNS)].astype("float64")
    frame.index = _parse_timestamps(table["timestamp"])
    return frame


# --- cleaning ---------------------------------------------------------------


def _spread_mask(frame: pd.DataFrame) -> np.ndarray:
    """Rows that cannot be an outright contract: non-positive, or under half the level.

    The level is the highest high of the previous ``SPREAD_LOOKBACK_ROWS`` rows. Spreads
    trade at a few percent of the outright price at most, outrights of every month sit
    within a few percent of each other, so half the level separates them cleanly.
    """
    level = frame["high"].rolling(SPREAD_LOOKBACK_ROWS, min_periods=1).max().shift(1)
    level = level.fillna(frame["high"])
    return ((frame["low"] <= 0) | (frame["close"] < SPREAD_MAX_RATIO * level)).to_numpy()


def _lead_contract_rows(
    minutes: list[int], opens: list[float], closes: list[float], volumes: list[float]
) -> list[bool]:
    """Mark the rows that continue the lead (highest-volume) contract.

    Walks the rows once, in time order, using only what came before each row:

    1. The lead contract has a last close and a typical volume. Every other contract seen
       is remembered by its price ratio to the lead (stable for hours) and its own
       typical volume.
    2. A row that sits on a known other contract and trades that contract's kind of
       volume belongs to it and is dropped.
    3. Otherwise a row whose open continues the lead's last close (within a tolerance
       that widens with the minutes missing in between) is the lead and is kept. After
       a long gap a thin row is not enough to resume the lead.
    4. Otherwise a row that is not thin is a real move of the lead and is kept: volume
       decides. Moves over ``LARGE_JUMP`` must be confirmed by the following row.
    5. Anything left is a thin row away from the lead: dropped, and remembered as a
       contract if it is far enough away to be one.
    6. Each contract accumulates decayed volume. When another contract out-trades the
       lead by ``ROLL_HYSTERESIS``, it becomes the lead: that is the roll.
    """
    count = len(opens)
    keep = [False] * count
    if count == 0:
        return keep
    sqrt = math.sqrt
    growth = 2.0 ** (1.0 / ROLL_HALF_LIFE_ROWS)

    lead_close, lead_minute, lead_volume = closes[0], minutes[0], volumes[0]
    lead_weight, weight_unit = volumes[0], 1.0
    keep[0] = True
    # other contracts, as parallel lists
    ratios: list[float] = []
    typical: list[float] = []
    weights: list[float] = []
    last_close: list[float] = []
    last_minute: list[int] = []
    pending_close, pending_minute = 0.0, 0

    for i in range(1, count):
        open_, close, volume, minute = opens[i], closes[i], volumes[i], minutes[i]
        weight_unit *= growth  # newer volume counts for more: an exponential decay
        ratio = open_ / lead_close
        lead_distance = abs(ratio - 1.0)
        gap = minute - lead_minute - 1
        drift = min(DRIFT_PER_SQRT_MINUTE * sqrt(gap), DRIFT_CAP) if gap > 0 else 0.0

        other, other_distance = -1, math.inf
        for k in range(len(ratios)):
            distance = abs(ratio - ratios[k])
            matches = distance <= RATIO_BAND + drift
            own_distance = abs(open_ / last_close[k] - 1.0)
            if own_distance < distance or not matches:
                own_gap = minute - last_minute[k] - 1
                if own_gap <= FRESH_MINUTES and own_distance <= STEP_TOLERANCE + (
                    DRIFT_PER_SQRT_MINUTE * sqrt(own_gap) if own_gap > 0 else 0.0
                ):
                    matches = True
                    distance = min(distance, own_distance)
            if matches and distance < other_distance:
                other, other_distance = k, distance
        on_other = other >= 0 and other_distance < lead_distance
        not_thin = volume >= THIN_FRACTION * lead_volume

        is_lead = False
        claimed = False
        if on_other and volume <= CLAIM_VOLUME_FACTOR * typical[other] + CLAIM_VOLUME_SLACK:
            claimed = True
        elif lead_distance <= STEP_TOLERANCE + drift:
            if gap < LONG_GAP_MINUTES or not_thin:
                is_lead = True
            else:  # unconfirmed after a long gap; let the volume bar come down
                lead_volume += VOLUME_SMOOTHING * (volume - lead_volume)
        elif not_thin and (
            not on_other
            or lead_distance <= SMALL_JUMP + drift
            or volume > JUMP_VOLUME_FACTOR * typical[other] + JUMP_VOLUME_FACTOR
        ):
            since_pending = minute - pending_minute
            if lead_distance <= LARGE_JUMP + drift:
                is_lead = True
            elif (
                pending_close
                and since_pending <= CONFIRM_MINUTES
                and abs(open_ / pending_close - 1.0)
                <= STEP_TOLERANCE + (DRIFT_PER_SQRT_MINUTE * sqrt(since_pending - 1) if since_pending > 1 else 0.0)
            ):
                is_lead = True
            else:
                pending_close, pending_minute = close, minute
        elif on_other:
            claimed = True
        elif lead_distance >= MIN_CONTRACT_SEPARATION:
            if len(ratios) >= MAX_TRACKED_CONTRACTS:
                weakest = min(range(len(weights)), key=weights.__getitem__)
                for column in (ratios, typical, weights, last_close, last_minute):
                    del column[weakest]
            ratios.append(close / lead_close)
            typical.append(volume)
            weights.append(volume * weight_unit)
            last_close.append(close)
            last_minute.append(minute)

        if is_lead:
            keep[i] = True
            lead_close, lead_minute = close, minute
            lead_volume += VOLUME_SMOOTHING * (volume - lead_volume)
            lead_weight += volume * weight_unit
            pending_close = 0.0
        elif claimed:
            ratios[other] += RATIO_SMOOTHING * (close / lead_close - ratios[other])
            typical[other] += VOLUME_SMOOTHING * (volume - typical[other])
            weights[other] += volume * weight_unit
            last_close[other], last_minute[other] = close, minute
            if weights[other] > ROLL_HYSTERESIS * lead_weight:  # the roll: swap roles
                new_ratio = ratios[other]
                old = (lead_close, lead_minute, lead_volume, lead_weight)
                lead_close, lead_minute = last_close[other], last_minute[other]
                lead_volume, lead_weight = typical[other], weights[other]
                ratios = [value / new_ratio for value in ratios]
                ratios[other] = old[0] / lead_close
                last_close[other], last_minute[other], typical[other], weights[other] = old
                keep[i] = True
    return keep


def clean_minute_bars(raw: pd.DataFrame) -> tuple[pd.DataFrame, CleaningReport]:
    """Keep only the lead contract's rows. Returns the clean frame and the row counts.

    Steps, in order:

    1. invalid: NaN prices, ``high < low`` or a repeated timestamp
    2. spread: non-positive price, or a close under half the recent outright level
    3. other contract: see ``_lead_contract_rows``

    Each trading week (Sunday 18:00 New York onward) is processed on its own, primed
    with the ``WARMUP_ROWS`` rows before it. A row's verdict therefore depends only on
    earlier rows of its own week and the tail of the previous one, which makes the
    result identical whether the whole history or a window of it is cleaned, as long
    as the window starts at least one trading week before the rows that matter.
    """
    frame = raw[list(BARS_COLUMNS)]
    rows_in = len(frame)
    if not frame.index.is_monotonic_increasing:
        frame = frame.sort_index(kind="stable")
    valid = (
        frame[["open", "high", "low", "close"]].notna().all(axis=1).to_numpy()
        & (frame["high"] >= frame["low"]).to_numpy()
        & ~frame.index.duplicated(keep="first")
    )
    frame = frame[valid]
    dropped_invalid = rows_in - len(frame)

    spread = _spread_mask(frame)
    outright = np.flatnonzero(~spread)
    keep = np.zeros(len(frame), dtype=bool)
    if len(outright):
        index = frame.index[outright]
        minutes = index.tz_convert("UTC").tz_localize(None).values.astype("datetime64[m]").astype("int64")
        opens = frame["open"].to_numpy()[outright]
        closes = frame["close"].to_numpy()[outright]
        volumes = frame["volume"].fillna(0.0).to_numpy()[outright]
        weeks = _week_ids(index)
        edges = np.flatnonzero(np.r_[True, weeks[1:] != weeks[:-1], True])
        for begin, stop in zip(edges[:-1], edges[1:]):
            primed = max(0, begin - WARMUP_ROWS)
            verdicts = _lead_contract_rows(
                minutes[primed:stop].tolist(),
                opens[primed:stop].tolist(),
                closes[primed:stop].tolist(),
                volumes[primed:stop].tolist(),
            )
            keep[outright[begin:stop]] = verdicts[begin - primed :]

    cleaned = frame[keep].astype("float64")
    report = CleaningReport(
        rows_in=rows_in,
        dropped_invalid=dropped_invalid,
        dropped_spread=int(spread.sum()),
        dropped_other_contract=int(len(outright) - keep.sum()),
        rows_out=len(cleaned),
    )
    return cleaned, report


def load_minute_bars(
    symbol: str,
    start: TimeLike | None = None,
    end: TimeLike | None = None,
    *,
    data_dir: Path | None = None,
) -> pd.DataFrame:
    """Cleaned one-minute bars for ``symbol`` with ``start <= open time < end``.

    A window reads only its part of the file, extended back to the start of the
    previous trading week so the cleaning sees the same history it would in a full
    load. ``frame.attrs["cleaning"]`` holds the ``CleaningReport`` of the rows that
    were read (including that lead-in).
    """
    begin = to_new_york(start) if start is not None else None
    stop = to_new_york(end) if end is not None else None
    read_from = _week_start(begin) - pd.Timedelta(days=7) if begin is not None else None
    raw = read_raw_minute_bars(symbol, read_from, stop, data_dir=data_dir)
    cleaned, report = clean_minute_bars(raw)
    if begin is not None:
        cleaned = cleaned[cleaned.index >= begin]
    cleaned.attrs["cleaning"] = report
    return cleaned


# --- resampling -------------------------------------------------------------


def _bucket_open_minutes(wall_minutes: np.ndarray, timeframe: Timeframe) -> np.ndarray:
    """Open of the ``timeframe`` bar holding each minute, in New York wall-clock minutes.

    Wall-clock arithmetic is exact here: every supported intraday length divides the
    24-hour session grid that starts at 18:00, and no session spans a DST change
    (clocks move on Sunday 02:00, while the market is shut).
    """
    session_open = _SESSION_OPEN_HOUR * 60
    since_anchor = wall_minutes - session_open  # minutes since 1970-01-01 18:00
    if timeframe.minutes is not None:
        return (since_anchor // timeframe.minutes) * timeframe.minutes + session_open
    trading_day = since_anchor // 1440 + 1  # days since 1970-01-01, a Thursday
    if timeframe.kind == "day":
        first_day = trading_day
    elif timeframe.kind == "week":
        first_day = trading_day - (trading_day + 3) % 7  # back to Monday
    else:
        month_start = trading_day.astype("datetime64[D]").astype("datetime64[M]").astype("datetime64[D]")
        first_day = month_start.astype("int64")
        weekday = (first_day + 3) % 7
        first_day = first_day + np.where(weekday == 5, 2, np.where(weekday == 6, 1, 0))
    return (first_day - 1) * 1440 + session_open


def resample(minute_bars: pd.DataFrame, timeframe: str | Timeframe) -> pd.DataFrame:
    """Aggregate one-minute bars into ``timeframe`` bars labelled by open time.

    Intraday bars are anchored to the 18:00 New York session open (so ``4h`` bars open
    at 18, 22, 02, 06, 10 and 14), ``1D`` opens at 18:00 the evening before, ``1W`` on
    Sunday 18:00 and ``1M`` on the evening before the month's first weekday. Buckets
    with no minutes are absent. The result says nothing about whether its last bar is
    complete; use ``closed_bars`` or a ``BarSource`` for that.
    """
    tf = parse_timeframe(timeframe)
    if minute_bars.empty:
        return _empty_bars()
    bars = minute_bars[list(BARS_COLUMNS)].astype("float64")
    if tf.label == "1m":
        return bars
    if not bars.index.is_monotonic_increasing:
        bars = bars.sort_index(kind="stable")
    keys = _bucket_open_minutes(_wall_minutes(bars.index), tf)
    starts = np.flatnonzero(np.r_[True, keys[1:] != keys[:-1]])
    ends = np.r_[starts[1:], len(keys)] - 1
    values = {name: bars[name].to_numpy() for name in BARS_COLUMNS}
    index = pd.DatetimeIndex(keys[starts].astype("datetime64[m]")).tz_localize(BARS_TIMEZONE).as_unit(bars.index.unit)
    return pd.DataFrame(
        {
            "open": values["open"][starts],
            "high": np.maximum.reduceat(values["high"], starts),
            "low": np.minimum.reduceat(values["low"], starts),
            "close": values["close"][ends],
            "volume": np.add.reduceat(values["volume"], starts),
        },
        index=index.rename("timestamp"),
    )


def bar_close_times(bars: pd.DataFrame, timeframe: str | Timeframe) -> pd.DatetimeIndex:
    """Close time of every bar in ``bars`` (see ``timeframes.bar_close_time``)."""
    tf = parse_timeframe(timeframe)
    index = bars.index
    if tf.minutes is not None:
        return index + pd.Timedelta(minutes=tf.minutes)
    if tf.kind in ("day", "week"):
        days = tf.count * (7 if tf.kind == "week" else 1)
        return (index.tz_localize(None) + pd.Timedelta(days=days)).tz_localize(BARS_TIMEZONE)
    return pd.DatetimeIndex([bar_close_time(opened, tf) for opened in index], tz=BARS_TIMEZONE)


def closed_bars(bars: pd.DataFrame, timeframe: str | Timeframe, as_of: TimeLike) -> pd.DataFrame:
    """The bars of ``bars`` that are fully closed at ``as_of`` (close time <= as_of)."""
    if bars.empty:
        return bars
    closes = bar_close_times(bars, timeframe)
    return bars.iloc[: int(closes.searchsorted(to_new_york(as_of), side="right"))]


# --- sources ----------------------------------------------------------------


HISTORICAL_SOURCE_NOTE = "Historical data (saved 1-minute bars) — not live TradingView"


def describe_source(source: object) -> str:
    """Where a source's bars come from, in the source's own words (its ``description``)."""
    text = getattr(source, "description", "")
    return text if isinstance(text, str) and text else f"Bars from {type(source).__name__}"


@runtime_checkable
class BarSource(Protocol):
    """Where the companion gets its bars. Implementations must never look ahead."""

    def get_bars(self, symbol: str, timeframe: str, as_of: TimeLike, lookback: int) -> pd.DataFrame:
        """The last ``lookback`` bars of ``timeframe`` that are fully closed at ``as_of``.

        Returns a bars frame, oldest first, possibly shorter than ``lookback`` or
        empty. A bar whose close time is after ``as_of`` must not be returned, in whole
        or as a partial aggregate.
        """
        ...


class HistoricalBarSource:
    """``BarSource`` over the minute CSVs (or over minute frames supplied directly).

    Minute bars are loaded and cleaned once per symbol, and each timeframe is resampled
    once and cached. Because a higher-timeframe bar is built only from the minutes
    inside it, and the cleaning is causal, returning cached bars whose close time is
    at or before ``as_of`` is the same as rebuilding them from the minutes known then.
    """

    # Shown to the trader as it is, so nobody mistakes replayed history for a live feed.
    # A live source says something else here.
    description = HISTORICAL_SOURCE_NOTE

    def __init__(
        self,
        data_dir: Path | None = None,
        *,
        start: TimeLike | None = None,
        end: TimeLike | None = None,
        minute_bars: Mapping[str, pd.DataFrame] | None = None,
    ) -> None:
        self._data_dir = data_dir
        self._start = start
        self._end = end
        self._minutes: dict[str, pd.DataFrame] = {
            symbol.upper(): frame for symbol, frame in (minute_bars or {}).items()
        }
        self._resampled: dict[tuple[str, str], tuple[pd.DataFrame, pd.DatetimeIndex]] = {}

    def minute_bars(self, symbol: str) -> pd.DataFrame:
        key = symbol.upper()
        if key not in self._minutes:
            self._minutes[key] = load_minute_bars(key, self._start, self._end, data_dir=self._data_dir)
        return self._minutes[key]

    def cleaning_report(self, symbol: str) -> CleaningReport | None:
        """Row accounting for a symbol loaded from CSV; ``None`` for supplied frames."""
        report: Any = self.minute_bars(symbol).attrs.get("cleaning")
        return report if isinstance(report, CleaningReport) else None

    def get_bars(self, symbol: str, timeframe: str, as_of: TimeLike, lookback: int) -> pd.DataFrame:
        if lookback < 0:
            raise ValueError("lookback must be >= 0")
        tf = parse_timeframe(timeframe)
        key = (symbol.upper(), tf.label)
        if key not in self._resampled:
            bars = resample(self.minute_bars(symbol), tf)
            self._resampled[key] = (bars, bar_close_times(bars, tf))
        bars, closes = self._resampled[key]
        closed = int(closes.searchsorted(to_new_york(as_of), side="right"))
        return bars.iloc[max(0, closed - lookback) : closed].copy()
