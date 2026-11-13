from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from companion.bars import (
    DATA_DIR,
    BarSource,
    HistoricalBarSource,
    clean_minute_bars,
    closed_bars,
    load_minute_bars,
    read_raw_minute_bars,
    resample,
)
from companion.timeframes import SUPPORTED_TIMEFRAMES, bar_close_time
from companion.types import BARS_COLUMNS

NY = "America/New_York"


def ny(text: str) -> pd.Timestamp:
    return pd.Timestamp(text, tz=NY)


def session_minutes(start: str, end: str) -> pd.DatetimeIndex:
    """Every minute the futures market is open in [start, end): 18:00 -> 17:00, Sun-Fri."""
    utc = pd.date_range(ny(start).tz_convert("UTC"), ny(end).tz_convert("UTC"), freq="1min", inclusive="left")
    index = utc.tz_convert(NY)
    halted = index.hour == 17
    weekday = index.dayofweek
    weekend = (weekday == 5) | ((weekday == 4) & (index.hour >= 17)) | ((weekday == 6) & (index.hour < 18))
    return index[~(halted | weekend)].rename("timestamp")


def minute_frame(start: str, end: str, base: float = 20000.0) -> pd.DataFrame:
    """Synthetic lead-contract minutes: a slow, smooth price path with ordinary volume."""
    index = session_minutes(start, end)
    step = np.arange(len(index), dtype="float64")
    close = base * (1 + 0.004 * np.sin(step / 500.0)) + 0.01 * step
    open_ = np.r_[close[0], close[:-1]]
    return pd.DataFrame(
        {
            "open": open_,
            "high": np.maximum(open_, close) + 1.0,
            "low": np.minimum(open_, close) - 1.0,
            "close": close,
            "volume": 100.0 + (step % 7),
        },
        index=index,
    )


def assert_bars_frame(frame: pd.DataFrame) -> None:
    assert list(frame.columns) == list(BARS_COLUMNS)
    assert all(dtype == "float64" for dtype in frame.dtypes)
    assert frame.index.name == "timestamp"
    assert str(frame.index.tz) == NY
    assert frame.index.is_monotonic_increasing and frame.index.is_unique


# --- resample: aggregation and anchors -------------------------------------


def test_resample_aggregates_open_high_low_close_volume() -> None:
    minutes = minute_frame("2025-06-01 18:00", "2025-06-01 18:10")

    bars = resample(minutes, "5m")

    assert_bars_frame(bars)
    assert list(bars.index) == [ny("2025-06-01 18:00"), ny("2025-06-01 18:05")]
    first = minutes.iloc[:5]
    assert bars.iloc[0].to_dict() == {
        "open": first["open"].iloc[0],
        "high": first["high"].max(),
        "low": first["low"].min(),
        "close": first["close"].iloc[-1],
        "volume": first["volume"].sum(),
    }


def test_one_minute_resample_returns_the_minutes() -> None:
    minutes = minute_frame("2025-06-01 18:00", "2025-06-01 19:00")

    pd.testing.assert_frame_equal(resample(minutes, "1m"), minutes)


def test_resample_of_nothing_is_an_empty_bars_frame() -> None:
    empty = resample(minute_frame("2025-06-01 18:00", "2025-06-01 18:10").iloc[:0], "1h")

    assert empty.empty
    assert_bars_frame(empty)


@pytest.mark.parametrize(
    ("label", "expected_opens"),
    [
        ("3m", ["18:00", "18:03", "18:06"]),
        ("5m", ["18:00", "18:05", "18:10"]),
        ("15m", ["18:00", "18:15", "18:30"]),
        ("30m", ["18:00", "18:30", "19:00"]),
        ("1h", ["18:00", "19:00", "20:00"]),
    ],
)
def test_intraday_bars_start_at_the_session_open(label: str, expected_opens: list[str]) -> None:
    bars = resample(minute_frame("2025-06-01 18:00", "2025-06-02 17:00"), label)

    assert [stamp.strftime("%H:%M") for stamp in bars.index[:3]] == expected_opens
    assert bars.index[0] == ny("2025-06-01 18:00")


def test_four_hour_bars_anchor_to_18_00() -> None:
    minutes = minute_frame("2025-06-01 18:00", "2025-06-03 17:00")

    bars = resample(minutes, "4h")

    assert [stamp.strftime("%a %H:%M") for stamp in bars.index] == [
        "Sun 18:00", "Sun 22:00", "Mon 02:00", "Mon 06:00", "Mon 10:00", "Mon 14:00",
        "Mon 18:00", "Mon 22:00", "Tue 02:00", "Tue 06:00", "Tue 10:00", "Tue 14:00",
    ]  # fmt: skip
    # the 14:00 bar only has the three hours up to the 17:00 halt
    counts = minutes.groupby(np.searchsorted(bars.index, minutes.index, side="right") - 1).size()
    assert counts.tolist() == [240, 240, 240, 240, 240, 180] * 2


def test_daily_bar_opens_at_18_00_the_evening_before() -> None:
    minutes = minute_frame("2025-06-01 18:00", "2025-06-04 17:00")

    bars = resample(minutes, "1D")

    assert list(bars.index) == [ny("2025-06-01 18:00"), ny("2025-06-02 18:00"), ny("2025-06-03 18:00")]
    monday = minutes[(minutes.index >= ny("2025-06-01 18:00")) & (minutes.index < ny("2025-06-02 18:00"))]
    assert len(monday) == 23 * 60
    assert bars["open"].iloc[0] == monday["open"].iloc[0]
    assert bars["close"].iloc[0] == monday["close"].iloc[-1]  # the 16:59 minute
    assert bars["volume"].iloc[0] == monday["volume"].sum()
    # 18:00 belongs to the next trading day
    assert bars["open"].iloc[1] == minutes.loc[ny("2025-06-02 18:00"), "open"]


def test_weekly_bar_runs_from_sunday_18_00_to_friday() -> None:
    minutes = minute_frame("2025-06-01 18:00", "2025-06-15 18:00")

    bars = resample(minutes, "1W")

    assert list(bars.index) == [ny("2025-06-01 18:00"), ny("2025-06-08 18:00")]
    first_week = minutes[minutes.index < ny("2025-06-08 18:00")]
    assert first_week.index[-1] == ny("2025-06-06 16:59")
    assert bars["close"].iloc[0] == first_week["close"].iloc[-1]
    assert bars["volume"].iloc[0] == first_week["volume"].sum()
    assert bars["open"].iloc[1] == minutes.loc[ny("2025-06-08 18:00"), "open"]


def test_monthly_bar_holds_the_trading_days_of_a_calendar_month() -> None:
    # August 31 2025 is a Sunday: its evening session is trading day Monday September 1.
    minutes = minute_frame("2025-08-28 18:00", "2025-10-02 17:00")

    bars = resample(minutes, "1M")

    assert list(bars.index) == [ny("2025-07-31 18:00"), ny("2025-08-31 18:00"), ny("2025-09-30 18:00")]
    september = minutes[(minutes.index >= ny("2025-08-31 18:00")) & (minutes.index < ny("2025-09-30 18:00"))]
    assert september.index[-1] == ny("2025-09-30 16:59")
    assert bars["open"].iloc[1] == september["open"].iloc[0]
    assert bars["close"].iloc[1] == september["close"].iloc[-1]
    assert bars["high"].iloc[1] == september["high"].max()
    # the August bar ends with Friday August 29, the October bar starts Tuesday evening
    assert bars["close"].iloc[0] == minutes.loc[ny("2025-08-29 16:59"), "close"]
    assert bars["open"].iloc[2] == minutes.loc[ny("2025-09-30 18:00"), "open"]


def test_month_starting_on_a_weekend_opens_on_the_sunday_evening() -> None:
    # February 1 2025 is a Saturday.
    bars = resample(minute_frame("2025-01-30 18:00", "2025-02-04 17:00"), "1M")

    assert list(bars.index) == [ny("2024-12-31 18:00"), ny("2025-02-02 18:00")]


def test_empty_buckets_are_dropped() -> None:
    minutes = minute_frame("2025-06-01 18:00", "2025-06-02 02:00")
    with_hole = minutes[(minutes.index < ny("2025-06-01 20:00")) | (minutes.index >= ny("2025-06-01 23:00"))]

    hourly = resample(with_hole, "1h")

    assert [stamp.strftime("%H:%M") for stamp in hourly.index] == ["18:00", "19:00", "23:00", "00:00", "01:00"]
    # no bar is produced for the weekend or the daily halt either
    week = resample(minute_frame("2025-06-05 18:00", "2025-06-09 17:00"), "1h")
    assert not ((week.index.hour == 17) | (week.index.dayofweek == 5)).any()


@pytest.mark.parametrize(
    ("change", "sunday", "offset_before", "offset_after"),
    [
        ("spring forward", "2025-03-09", -5, -4),
        ("fall back", "2025-11-02", -4, -5),
    ],
)
def test_anchors_hold_through_a_dst_change_week(
    change: str, sunday: str, offset_before: int, offset_after: int
) -> None:
    wall_open = pd.Timestamp(f"{sunday} 18:00")
    sunday_open = wall_open.tz_localize(NY)
    start = (wall_open - pd.Timedelta(days=7)).tz_localize(NY)  # the Sunday before, 18:00 on the old offset
    minutes = minute_frame(str(wall_open - pd.Timedelta(days=7)), str(wall_open + pd.Timedelta(days=5)))

    daily = resample(minutes, "1D")
    four_hour = resample(minutes, "4h")
    hourly = resample(minutes, "1h")
    weekly = resample(minutes, "1W")

    # every daily bar opens at 18:00 wall clock and holds a full 23-hour session
    assert set(daily.index.strftime("%H:%M")) == {"18:00"}
    assert len(daily) == 10
    sessions = np.searchsorted(daily.index, minutes.index, side="right") - 1
    assert set(np.bincount(sessions).tolist()) == {23 * 60}
    # the UTC offset of the labels flips exactly at the Sunday open after the change
    hours = lambda index: [int(stamp.utcoffset().total_seconds() // 3600) for stamp in index]  # noqa: E731
    assert set(hours(daily.index[daily.index < sunday_open])) == {offset_before}
    assert set(hours(daily.index[daily.index >= sunday_open])) == {offset_after}
    # 4h and 1h bars keep their wall-clock anchors on both sides
    assert set(four_hour.index.strftime("%H:%M")) == {"18:00", "22:00", "02:00", "06:00", "10:00", "14:00"}
    assert len(four_hour) == 60
    assert set(hourly.index.minute) == {0} and len(hourly) == 230
    # weeks open Sunday 18:00 local on both sides of the change
    assert list(weekly.index) == [start, sunday_open]
    assert weekly.index[1] - weekly.index[0] == pd.Timedelta(hours=168 + (offset_before - offset_after))


# --- no lookahead -----------------------------------------------------------

LOOKAHEAD_START, LOOKAHEAD_END = "2025-08-24 18:00", "2025-09-12 17:00"
AS_OF_MOMENTS = [
    "2025-09-03 09:30",  # on a 5m/15m/30m boundary
    "2025-09-03 09:31",
    "2025-09-03 10:00",  # closes 1h and the 06:00 4h bar
    "2025-09-03 13:59",
    "2025-09-03 16:59",
    "2025-09-03 17:00",  # the halt begins
    "2025-09-03 18:00",  # closes the daily bar, opens the next
    "2025-09-03 18:01",
    "2025-09-05 17:30",  # Friday after the close
    "2025-09-06 12:00",  # Saturday
    "2025-09-07 18:00",  # closes the weekly bar
    "2025-09-07 18:07",
    "2025-08-31 18:00",  # closes the August monthly bar
    "2025-09-01 03:13",
]


@pytest.fixture(scope="module")
def lookahead_minutes() -> pd.DataFrame:
    return minute_frame(LOOKAHEAD_START, LOOKAHEAD_END)


@pytest.mark.parametrize("label", SUPPORTED_TIMEFRAMES)
def test_get_bars_never_returns_a_bar_still_forming(lookahead_minutes: pd.DataFrame, label: str) -> None:
    source = HistoricalBarSource(minute_bars={"NQ": lookahead_minutes})

    for moment in AS_OF_MOMENTS:
        as_of = ny(moment)
        bars = source.get_bars("NQ", label, as_of, lookback=10_000)

        assert_bars_frame(bars)
        assert len(bars) > 0
        assert all(bar_close_time(opened, label) <= as_of for opened in bars.index)
        # the newest closed bar is there: the next bar of the full series closes after as_of
        full = resample(lookahead_minutes, label)
        following = full.index[full.index > bars.index[-1]]
        assert len(following) == 0 or bar_close_time(following[0], label) > as_of


@pytest.mark.parametrize("label", SUPPORTED_TIMEFRAMES)
def test_get_bars_is_blind_to_everything_after_as_of(lookahead_minutes: pd.DataFrame, label: str) -> None:
    for moment in AS_OF_MOMENTS:
        as_of = ny(moment)
        # A world that ends at as_of: only minutes fully closed by then exist.
        known = lookahead_minutes[lookahead_minutes.index + pd.Timedelta(minutes=1) <= as_of]
        # A world with a very different future.
        altered = lookahead_minutes.copy()
        altered.loc[altered.index + pd.Timedelta(minutes=1) > as_of, list(BARS_COLUMNS)] *= 3.0

        with_future = HistoricalBarSource(minute_bars={"NQ": lookahead_minutes}).get_bars("NQ", label, as_of, 10_000)
        without_future = HistoricalBarSource(minute_bars={"NQ": known}).get_bars("NQ", label, as_of, 10_000)
        other_future = HistoricalBarSource(minute_bars={"NQ": altered}).get_bars("NQ", label, as_of, 10_000)

        pd.testing.assert_frame_equal(with_future, without_future)
        pd.testing.assert_frame_equal(with_future, other_future)


@pytest.mark.parametrize(
    ("label", "opened", "closes"),
    [
        ("1m", "2025-09-03 09:30", "2025-09-03 09:31"),
        ("3m", "2025-09-03 09:30", "2025-09-03 09:33"),
        ("5m", "2025-09-03 09:30", "2025-09-03 09:35"),
        ("15m", "2025-09-03 09:30", "2025-09-03 09:45"),
        ("30m", "2025-09-03 09:30", "2025-09-03 10:00"),
        ("1h", "2025-09-03 09:00", "2025-09-03 10:00"),
        ("4h", "2025-09-03 06:00", "2025-09-03 10:00"),
        ("1D", "2025-09-02 18:00", "2025-09-03 18:00"),
        ("1W", "2025-08-31 18:00", "2025-09-07 18:00"),
        ("1M", "2025-07-31 18:00", "2025-08-31 18:00"),
    ],
)
def test_a_bar_appears_exactly_at_its_close(
    lookahead_minutes: pd.DataFrame, label: str, opened: str, closes: str
) -> None:
    source = HistoricalBarSource(minute_bars={"NQ": lookahead_minutes})
    close_time = ny(closes)

    just_before = source.get_bars("NQ", label, close_time - pd.Timedelta(seconds=1), 3)
    at_close = source.get_bars("NQ", label, close_time, 3)

    assert ny(opened) not in just_before.index
    assert at_close.index[-1] == ny(opened)
    # the last minute of the bar is the last minute that had closed
    bucket = lookahead_minutes[(lookahead_minutes.index >= ny(opened)) & (lookahead_minutes.index < close_time)]
    assert at_close["close"].iloc[-1] == bucket["close"].iloc[-1]
    assert at_close["high"].iloc[-1] == bucket["high"].max()


def test_get_bars_lookback_and_edges(lookahead_minutes: pd.DataFrame) -> None:
    source = HistoricalBarSource(minute_bars={"nq": lookahead_minutes})
    as_of = ny("2025-09-03 10:00")

    three = source.get_bars("NQ", "1h", as_of, 3)

    assert list(three.index) == [ny("2025-09-03 07:00"), ny("2025-09-03 08:00"), ny("2025-09-03 09:00")]
    assert source.get_bars("NQ", "1h", as_of, 0).empty
    assert source.get_bars("NQ", "1h", ny("2025-08-24 18:30"), 5).empty  # nothing closed yet
    assert source.get_bars("NQ", "1D", ny("2020-01-01 00:00"), 5).empty  # before the data
    # naive as_of is New York time; other zones are converted
    pd.testing.assert_frame_equal(source.get_bars("NQ", "1h", "2025-09-03 10:00", 3), three)
    pd.testing.assert_frame_equal(source.get_bars("NQ", "1h", pd.Timestamp("2025-09-03 14:00", tz="UTC"), 3), three)
    with pytest.raises(ValueError):
        source.get_bars("NQ", "1h", as_of, -1)
    with pytest.raises(ValueError, match="Unknown timeframe"):
        source.get_bars("NQ", "2h", as_of, 3)


def test_returned_bars_are_a_copy(lookahead_minutes: pd.DataFrame) -> None:
    source = HistoricalBarSource(minute_bars={"NQ": lookahead_minutes})
    as_of = ny("2025-09-03 10:00")
    first = source.get_bars("NQ", "1h", as_of, 3)
    expected = first.copy()

    first.loc[:, "close"] = -1.0

    pd.testing.assert_frame_equal(source.get_bars("NQ", "1h", as_of, 3), expected)


def test_closed_bars_filters_a_resampled_frame(lookahead_minutes: pd.DataFrame) -> None:
    hourly = resample(lookahead_minutes, "1h")

    closed = closed_bars(hourly, "1h", ny("2025-09-03 09:59"))

    assert closed.index[-1] == ny("2025-09-03 08:00")
    assert closed_bars(hourly, "1h", ny("2025-09-03 10:00")).index[-1] == ny("2025-09-03 09:00")


def test_historical_source_satisfies_the_protocol(lookahead_minutes: pd.DataFrame) -> None:
    assert isinstance(HistoricalBarSource(minute_bars={"NQ": lookahead_minutes}), BarSource)


# --- cleaning ---------------------------------------------------------------


def replace_rows(frame: pd.DataFrame, positions: np.ndarray, price: np.ndarray | float, volume: float) -> pd.DataFrame:
    """Overwrite rows with a flat bar at ``price``: what a minute looks like when the
    vendor row came from another instrument."""
    result = frame.copy()
    stamps = result.index[positions]
    for column in ("open", "high", "low", "close"):
        result.loc[stamps, column] = price
    result.loc[stamps, "volume"] = volume
    return result


def test_clean_keeps_an_uncontaminated_series_whole() -> None:
    minutes = minute_frame("2025-06-01 18:00", "2025-06-06 17:00")

    cleaned, report = clean_minute_bars(minutes)

    pd.testing.assert_frame_equal(cleaned, minutes)
    assert report.as_dict() == {
        "rows_in": len(minutes),
        "dropped_invalid": 0,
        "dropped_spread": 0,
        "dropped_other_contract": 0,
        "rows_out": len(minutes),
        "dropped_total": 0,
    }


def test_clean_removes_spread_and_other_contract_rows_and_counts_them() -> None:
    lead = minute_frame("2025-06-01 18:00", "2025-06-06 17:00")
    positions = np.arange(len(lead))
    spreads = positions[(positions % 17 == 5) & (positions > 0)]
    negative_spreads = spreads[::2]
    positive_spreads = spreads[1::2]
    back_month = positions[(positions % 11 == 3) & (positions % 17 != 5)]
    far_month = positions[(positions % 53 == 7) & (positions % 17 != 5) & (positions % 11 != 3)]
    dirty = replace_rows(lead, negative_spreads, -14.85, 3.0)
    dirty = replace_rows(dirty, positive_spreads, 219.3, 2.0)
    dirty = replace_rows(dirty, back_month, lead["close"].to_numpy()[back_month] * 1.011, 2.0)
    dirty = replace_rows(dirty, far_month, lead["close"].to_numpy()[far_month] * 1.022, 1.0)

    cleaned, report = clean_minute_bars(dirty)

    contaminated = np.concatenate([spreads, back_month, far_month])
    expected = lead.drop(lead.index[contaminated])
    assert_bars_frame(cleaned)
    assert report.dropped_spread == len(spreads)
    assert report.dropped_invalid == 0
    assert report.rows_in == len(lead) and report.rows_out == len(cleaned)
    # no off-contract row survives, and nearly every lead row does
    assert cleaned.index.isin(lead.index[contaminated]).sum() == 0
    assert len(cleaned) >= 0.999 * len(expected)
    assert report.dropped_other_contract == report.rows_in - report.dropped_spread - report.rows_out
    assert (cleaned["close"] > 0).all()
    assert ((cleaned["open"] / cleaned["close"].shift(1) - 1).abs().dropna() < 0.004).all()


def test_clean_drops_invalid_rows() -> None:
    minutes = minute_frame("2025-06-01 18:00", "2025-06-02 17:00")
    broken = minutes.copy()
    broken.iloc[10, broken.columns.get_loc("close")] = np.nan
    broken.iloc[20, broken.columns.get_loc("high")] = broken["low"].iloc[20] - 5.0

    cleaned, report = clean_minute_bars(broken)

    assert report.dropped_invalid == 2
    assert not cleaned.index.isin(minutes.index[[10, 20]]).any()
    assert len(cleaned) == len(minutes) - 2


def test_clean_keeps_a_real_move_that_trades_real_volume() -> None:
    minutes = minute_frame("2025-06-01 18:00", "2025-06-04 17:00")
    jumped = minutes.copy()
    after = jumped.index >= ny("2025-06-03 08:30")
    jumped.loc[after, ["open", "high", "low", "close"]] *= 1.008  # a news release: +0.8% in one bar
    jumped.loc[ny("2025-06-03 08:30"), "open"] = minutes.loc[ny("2025-06-03 08:30"), "open"]
    jumped.loc[ny("2025-06-03 08:30"), "low"] = minutes.loc[ny("2025-06-03 08:30"), "low"]

    cleaned, report = clean_minute_bars(jumped)

    assert report.dropped_total == 0
    pd.testing.assert_frame_equal(cleaned, jumped)


def test_clean_follows_a_gap_larger_than_the_confirmation_threshold_after_one_bar() -> None:
    minutes = minute_frame("2025-06-01 18:00", "2025-06-04 17:00")
    gapped = minutes.copy()
    after = gapped.index >= ny("2025-06-03 08:30")
    gapped.loc[after, ["open", "high", "low", "close"]] *= 1.025  # opens 2.5% away

    cleaned, report = clean_minute_bars(gapped)

    # the first bar at the new level waits for confirmation; everything else is kept
    assert report.dropped_total == 1
    assert ny("2025-06-03 08:30") not in cleaned.index
    assert ny("2025-06-03 08:31") in cleaned.index


def test_clean_rolls_once_when_the_next_contract_takes_over_the_volume() -> None:
    lead = minute_frame("2025-06-01 18:00", "2025-06-06 17:00")
    positions = np.arange(len(lead))
    ratio = 1.012
    roll_starts = lead.index.get_loc(ny("2025-06-03 09:30"))
    dirty = lead.copy()
    # before the roll the next contract trades thinly on every fifth minute
    early = positions[(positions % 5 == 2) & (positions < roll_starts)]
    dirty = replace_rows(dirty, early, lead["close"].to_numpy()[early] * ratio, 3.0)
    # afterwards it prints most minutes with heavy volume; the old contract fades
    late_new = positions[(positions % 3 != 0) & (positions >= roll_starts)]
    late_old = positions[(positions % 3 == 0) & (positions >= roll_starts)]
    dirty = replace_rows(dirty, late_new, lead["close"].to_numpy()[late_new] * ratio, 900.0)
    dirty.loc[dirty.index[late_old], "volume"] = 60.0

    cleaned, _ = clean_minute_bars(dirty)

    steps = (cleaned["open"] / cleaned["close"].shift(1) - 1).dropna()
    switches = steps[steps.abs() > 0.006]
    assert len(switches) == 1  # one roll, no flip-flopping between contracts
    assert switches.iloc[0] == pytest.approx(ratio - 1, abs=0.002)
    switched_at = switches.index[0]
    assert ny("2025-06-03 09:30") < switched_at < ny("2025-06-04 17:00")
    # before the roll only the old contract, after it only the new one
    assert not cleaned.index[cleaned.index < switched_at].isin(lead.index[np.r_[early, late_new]]).any()
    assert not cleaned.index[cleaned.index > switched_at].isin(lead.index[late_old]).any()


def contaminated_weeks() -> pd.DataFrame:
    lead = minute_frame("2025-06-01 18:00", "2025-06-20 17:00")
    positions = np.arange(len(lead))
    dirty = replace_rows(lead, positions[positions % 13 == 4], -7.5, 4.0)
    other = positions[(positions % 9 == 1) & (positions % 13 != 4)]
    return replace_rows(dirty, other, lead["close"].to_numpy()[other] * 0.989, 2.0)


def test_cleaning_is_causal() -> None:
    """A row's verdict never changes when later rows are added or altered."""
    dirty = contaminated_weeks()
    cleaned, _ = clean_minute_bars(dirty)

    for cut in (ny("2025-06-03 09:37"), ny("2025-06-08 18:00"), ny("2025-06-12 14:02"), ny("2025-06-15 19:15")):
        prefix, _ = clean_minute_bars(dirty[dirty.index < cut])
        pd.testing.assert_frame_equal(prefix, cleaned[cleaned.index < cut])

        altered = dirty.copy()
        altered.loc[altered.index >= cut, ["open", "high", "low", "close"]] *= 1.5
        altered_clean, _ = clean_minute_bars(altered)
        pd.testing.assert_frame_equal(altered_clean[altered_clean.index < cut], cleaned[cleaned.index < cut])


def test_cleaning_a_window_matches_cleaning_everything() -> None:
    dirty = contaminated_weeks()
    cleaned, _ = clean_minute_bars(dirty)

    # a window that starts a full trading week before the rows compared
    window, _ = clean_minute_bars(dirty[dirty.index >= ny("2025-06-08 18:00")])

    third_week = ny("2025-06-15 18:00")
    pd.testing.assert_frame_equal(window[window.index >= third_week], cleaned[cleaned.index >= third_week])


# --- CSV loading ------------------------------------------------------------


def write_csv(directory: Path, symbol: str, frame: pd.DataFrame) -> Path:
    path = directory / f"{symbol.lower()}_minute.csv"
    lines = ["timestamp,open,high,low,close,volume,session"]
    for stamp, row in zip(frame.index, frame.itertuples(index=False)):
        lines.append(f"{stamp.isoformat()},{row.open!r},{row.high!r},{row.low!r},{row.close!r},{int(row.volume)},other")
    path.write_bytes(("\n".join(lines) + "\n").encode("ascii"))
    return path


@pytest.fixture(scope="module")
def csv_dir(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, pd.DataFrame]:
    # three weeks spanning the March 2025 clock change, so both UTC offsets appear
    lead = minute_frame("2025-02-23 18:00", "2025-03-14 17:00")
    positions = np.arange(len(lead))
    dirty = replace_rows(lead, positions[positions % 19 == 6], -12.25, 2.0)
    directory = tmp_path_factory.mktemp("bars")
    write_csv(directory, "NQ", dirty)
    return directory, dirty


def test_read_raw_minute_bars_parses_the_csv(csv_dir: tuple[Path, pd.DataFrame]) -> None:
    directory, dirty = csv_dir

    raw = read_raw_minute_bars("NQ", data_dir=directory)

    assert_bars_frame(raw)
    pd.testing.assert_frame_equal(raw, dirty, check_freq=False)
    assert raw.index[0] == ny("2025-02-23 18:00") and raw.index[-1] == ny("2025-03-14 16:59")
    assert {stamp.utcoffset().total_seconds() / 3600 for stamp in raw.index[[0, -1]]} == {-5.0, -4.0}


@pytest.mark.parametrize(
    ("start", "end"),
    [
        ("2025-03-05 09:30", "2025-03-05 16:00"),
        ("2025-03-07 12:00", "2025-03-10 03:00"),  # across the weekend and the clock change
        ("2025-02-23 18:00", "2025-02-23 18:01"),
        (None, "2025-02-24 00:00"),
        ("2025-03-14 16:00", None),
        ("2025-03-08 10:00", "2025-03-09 12:00"),  # nothing trades in this window
        ("2024-01-01", "2024-02-01"),  # before the file
        ("2026-01-01", None),  # after the file
    ],
)
def test_windowed_read_returns_exactly_the_rows_in_the_window(
    csv_dir: tuple[Path, pd.DataFrame], start: str | None, end: str | None
) -> None:
    directory, dirty = csv_dir
    expected = dirty
    if start is not None:
        expected = expected[expected.index >= ny(start)]
    if end is not None:
        expected = expected[expected.index < ny(end)]

    window = read_raw_minute_bars("NQ", start, end, data_dir=directory)

    pd.testing.assert_frame_equal(window, expected, check_freq=False)


def test_load_minute_bars_cleans_and_reports(csv_dir: tuple[Path, pd.DataFrame]) -> None:
    directory, dirty = csv_dir

    loaded = load_minute_bars("nq", data_dir=directory)

    assert_bars_frame(loaded)
    report = loaded.attrs["cleaning"]
    assert report.rows_in == len(dirty)
    assert report.dropped_spread == int((dirty["close"] < 0).sum())
    assert report.rows_out == len(loaded)
    assert (loaded["close"] > 0).all()
    assert HistoricalBarSource(directory).cleaning_report("NQ") == report


def test_load_minute_bars_window_equals_the_slice_of_a_full_load(csv_dir: tuple[Path, pd.DataFrame]) -> None:
    directory, _ = csv_dir
    full = load_minute_bars("NQ", data_dir=directory)
    start, end = ny("2025-03-10 09:30"), ny("2025-03-12 16:00")

    window = load_minute_bars("NQ", "2025-03-10 09:30", "2025-03-12 16:00", data_dir=directory)

    pd.testing.assert_frame_equal(window, full[(full.index >= start) & (full.index < end)], check_freq=False)


def test_historical_source_reads_the_csv_without_lookahead(csv_dir: tuple[Path, pd.DataFrame]) -> None:
    directory, _ = csv_dir
    source = HistoricalBarSource(directory)
    as_of = ny("2025-03-11 10:07")

    for label in SUPPORTED_TIMEFRAMES:
        bars = source.get_bars("NQ", label, as_of, 50)
        assert len(bars) > 0
        assert all(bar_close_time(opened, label) <= as_of for opened in bars.index)
    assert source.get_bars("NQ", "5m", as_of, 1).index[-1] == ny("2025-03-11 10:00")


def test_unknown_symbol_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unknown symbol"):
        load_minute_bars("CL", data_dir=tmp_path)


# --- the real files (skipped when they are not present) -----------------------


def real_file(symbol: str) -> Path:
    return DATA_DIR / f"{symbol.lower()}_minute.csv"


@pytest.mark.parametrize("symbol", ["NQ", "ES", "GC"])
def test_real_data_window_is_clean_and_window_independent(symbol: str) -> None:
    if not real_file(symbol).exists():
        pytest.skip(f"{real_file(symbol)} is not present")

    narrow = load_minute_bars(symbol, "2024-06-03 18:00", "2024-06-07 17:00")
    wide = load_minute_bars(symbol, "2024-05-20", "2024-06-10")
    raw = read_raw_minute_bars(symbol, "2024-06-03 18:00", "2024-06-07 17:00")

    assert_bars_frame(narrow)
    assert 0 < len(narrow) < len(raw)
    assert (raw["close"] <= 0).any() or (raw["close"] < 0.5 * raw["close"].median()).any()
    assert (narrow[["open", "high", "low", "close"]] > 0.5 * narrow["close"].median()).all().all()
    pd.testing.assert_frame_equal(narrow, wide[(wide.index >= narrow.index[0]) & (wide.index <= narrow.index[-1])])
    # consecutive lead-contract minutes do not jump by a contract spread
    steps = (narrow["open"] / narrow["close"].shift(1) - 1).abs()
    consecutive = narrow.index.to_series().diff() == pd.Timedelta(minutes=1)
    assert steps[consecutive].max() < 0.004


def test_real_nq_rows_called_out_as_bad_are_gone() -> None:
    if not real_file("NQ").exists():
        pytest.skip(f"{real_file('NQ')} is not present")

    first = load_minute_bars("NQ", None, "2021-01-04 00:00")
    last = load_minute_bars("NQ", "2026-03-04 18:00", None)

    assert ny("2021-01-03 18:02") not in first.index  # 12857.25 on 4 contracts: a back month
    assert ny("2021-01-03 18:01") in first.index and ny("2021-01-03 18:03") in first.index
    assert not last.index.isin([ny("2026-03-04 18:57"), ny("2026-03-04 18:58")]).any()  # 219.x: a spread
    assert last["close"].min() > 20000
