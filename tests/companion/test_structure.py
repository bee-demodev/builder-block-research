"""Tests for companion.structure.

Frames are hand-made so the expected events can be read off the rows. Each row is
``(open, high, low, close)``; bar ``i`` opens at ``t(i)`` and closes at ``closed(i)``.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence

import numpy as np
import pandas as pd
import pytest

from companion.structure import (
    equilibrium,
    candle_direction,
    find_cisd,
    find_fair_value_gaps,
    find_protected_swings,
    find_sweeps,
    find_swings,
    known_as_of,
    measure_candle,
)
from companion.types import Cisd, FairValueGap, ProtectedSwing, Sweep, Swing

TF = "5m"
DUR = pd.Timedelta(minutes=5)
START = pd.Timestamp("2024-01-02 09:30", tz="America/New_York")

Row = tuple[float, float, float, float]


def t(slot: int) -> pd.Timestamp:
    """Open time of the bar in 5-minute slot ``slot``."""
    return START + slot * DUR


def closed(slot: int) -> pd.Timestamp:
    """Close time of the bar in slot ``slot``: the earliest it is knowable."""
    return t(slot) + DUR


def frame(rows: Sequence[Row], slots: Sequence[int] | None = None) -> pd.DataFrame:
    slots = list(range(len(rows))) if slots is None else list(slots)
    index = pd.DatetimeIndex([t(slot) for slot in slots], name="timestamp")
    bars = pd.DataFrame(list(rows), columns=["open", "high", "low", "close"], index=index)
    bars["volume"] = 1.0
    return bars


# --- swings ------------------------------------------------------------------

SWING_ROWS: list[Row] = [
    (10, 11, 9, 10),
    (10, 13, 10, 12),  # high 13 with lower highs both sides
    (12, 12, 8, 9),  # low 8 with higher lows both sides
    (9, 10, 9, 10),
]


def test_swings_three_candle_high_and_low_confirm_on_next_bar_close() -> None:
    assert find_swings(frame(SWING_ROWS), TF, DUR) == [
        Swing("high", t(1), 13.0, closed(2), TF),
        Swing("low", t(2), 8.0, closed(3), TF),
    ]


def test_swings_none_in_a_one_way_move() -> None:
    rows: list[Row] = [(10, 11, 9, 10.5), (10.5, 12, 10, 11.5), (11.5, 13, 11, 12.5), (12.5, 14, 12, 13.5)]
    assert find_swings(frame(rows), TF, DUR) == []


def test_swings_equal_highs_are_not_a_swing_unless_allowed() -> None:
    rows: list[Row] = [(10, 11, 9, 10), (10, 13, 10, 12), (12, 13, 10, 12), (12, 12, 9, 10)]
    bars = frame(rows)
    assert find_swings(bars, TF, DUR) == []
    # Allowed: the flat top gives one swing, at its first bar.
    assert find_swings(bars, TF, DUR, allow_equal=True) == [Swing("high", t(1), 13.0, closed(2), TF)]


def test_swings_two_bars_each_side_needs_two_closed_bars_after() -> None:
    highs = [10, 11, 14, 12, 13, 9]
    bars = frame([(h - 1, h, h - 2, h - 1) for h in highs])
    one_side = [s for s in find_swings(bars, TF, DUR) if s.kind == "high"]
    two_side = [s for s in find_swings(bars, TF, DUR, bars_each_side=2) if s.kind == "high"]
    assert one_side == [Swing("high", t(2), 14.0, closed(3), TF), Swing("high", t(4), 13.0, closed(5), TF)]
    assert two_side == [Swing("high", t(2), 14.0, closed(4), TF)]


def test_swings_missing_bars_confirm_at_the_close_of_the_next_bar_present() -> None:
    bars = frame(SWING_ROWS, slots=[0, 1, 2, 10])
    assert find_swings(bars, TF, DUR)[-1] == Swing("low", t(2), 8.0, closed(10), TF)


# --- sweeps ------------------------------------------------------------------

SWEEP_BASE: list[Row] = [
    (10, 11, 9, 10),
    (10, 13, 10, 12),  # swing high 13
    (12, 12, 10.5, 11),
    (11, 12.5, 10.6, 12),
]


def test_sweep_trades_above_swing_high_and_closes_back_below() -> None:
    bars = frame(SWEEP_BASE + [(12, 14, 11.5, 12.5)])
    assert find_sweeps(bars, TF, DUR) == [
        Sweep("high", t(4), 13.0, 14.0, t(1), closed(4), TF),
    ]


def test_sweep_that_closes_outside_is_not_a_sweep_and_consumes_the_level() -> None:
    bars = frame(SWEEP_BASE + [(12, 14, 11.5, 13.5), (13.5, 15, 12, 12.5)])
    # Bar 4 closes above 13: a break, not a sweep. Bar 5 closes back below 13, but
    # the level was already taken by bar 4.
    assert find_sweeps(bars, TF, DUR) == []


def test_sweep_equal_high_is_not_a_sweep_and_leaves_the_level_live() -> None:
    bars = frame(SWEEP_BASE + [(12, 13, 11.5, 12.5), (12.5, 13.5, 12, 12.4)])
    assert find_sweeps(bars, TF, DUR) == [
        Sweep("high", t(5), 13.0, 13.5, t(1), closed(5), TF),
    ]


def test_sweep_of_a_swing_low() -> None:
    rows: list[Row] = [(10, 11, 9, 10), (10, 10, 7, 8), (8, 9.5, 8, 9), (9, 9.2, 6, 8.5)]
    assert find_sweeps(frame(rows), TF, DUR) == [
        Sweep("low", t(3), 7.0, 6.0, t(1), closed(3), TF),
    ]


# --- fair value gaps ---------------------------------------------------------

BULLISH_GAP: list[Row] = [
    (10, 10.5, 9.5, 10),  # candle 1 high 10.5
    (10.2, 12.5, 10.1, 12.4),
    (12.4, 13, 11, 12.8),  # candle 3 low 11 -> gap 10.5..11
]


def test_fvg_bullish_gap_between_candle_one_high_and_candle_three_low() -> None:
    assert find_fair_value_gaps(frame(BULLISH_GAP), TF, DUR) == [
        FairValueGap("bullish", t(1), 11.0, 10.5, closed(2), TF, None),
    ]


@pytest.mark.parametrize("third_low", [10.4, 10.5])
def test_fvg_none_when_wicks_overlap_or_touch(third_low: float) -> None:
    rows = BULLISH_GAP[:2] + [(12.4, 13, third_low, 12.8)]
    assert find_fair_value_gaps(frame(rows), TF, DUR) == []


def test_fvg_fills_on_a_close_through_the_far_side_not_on_a_wick() -> None:
    rows = BULLISH_GAP + [
        (12.8, 12.9, 10.2, 10.8),  # wicks below 10.5 but closes above it
        (10.8, 11.2, 10, 10.3),  # closes below 10.5
    ]
    assert find_fair_value_gaps(frame(rows), TF, DUR) == [
        FairValueGap("bullish", t(1), 11.0, 10.5, closed(2), TF, closed(4)),
    ]


def test_fvg_bearish_gap_and_fill() -> None:
    rows: list[Row] = [
        (20, 20.5, 19.5, 19.8),  # candle 1 low 19.5
        (19.8, 19.9, 17.5, 17.6),
        (17.6, 18.9, 17, 17.2),  # candle 3 high 18.9 -> gap 18.9..19.5
        (17.2, 19.7, 17.1, 19.6),  # closes above 19.5
    ]
    assert find_fair_value_gaps(frame(rows), TF, DUR) == [
        FairValueGap("bearish", t(1), 19.5, 18.9, closed(2), TF, closed(3)),
    ]


def test_fvg_across_missing_bars_confirms_at_the_third_candles_own_close() -> None:
    bars = frame(BULLISH_GAP, slots=[0, 1, 7])
    assert find_fair_value_gaps(bars, TF, DUR) == [
        FairValueGap("bullish", t(1), 11.0, 10.5, closed(7), TF, None),
    ]


# --- change in state of delivery / protected swings -----------------------------

# A prior swing high at 13 is run by a two-candle up-close series (bars 4-5, first
# open 10.8, high 13.8); bar 7 then closes below 10.8.
BEARISH_CISD: list[Row] = [
    (10, 11, 9.5, 10.5),
    (10.5, 13, 10.4, 12.5),  # swing high 13
    (12.5, 12.6, 11, 11.2),
    (11.2, 11.5, 10.6, 10.8),
    (10.8, 12.2, 10.7, 12),  # series starts: open 10.8
    (12, 13.8, 11.9, 13.5),  # takes the 13 high; series high 13.8
    (13.5, 13.6, 12, 12.2),
    (12.2, 12.4, 10.2, 10.5),  # closes below 10.8
]


def test_cisd_bearish_close_through_the_series_that_swept_a_high() -> None:
    bars = frame(BEARISH_CISD)
    assert find_cisd(bars, TF, DUR) == [Cisd("bearish", t(7), 10.8, closed(7), TF)]
    assert find_protected_swings(bars, TF, DUR) == [
        ProtectedSwing("high", t(5), 13.8, closed(7), TF, None),
    ]


def test_cisd_none_without_a_close_through_the_series_open() -> None:
    bars = frame(BEARISH_CISD[:7] + [(12.2, 12.4, 10.9, 11)])  # closes 11, above 10.8
    assert find_cisd(bars, TF, DUR) == []
    assert find_protected_swings(bars, TF, DUR) == []


def test_cisd_without_context_also_reports_changes_that_reached_no_level() -> None:
    bars = frame(BEARISH_CISD)
    # The down-close series of bars 2-3 (open 12.5, low 10.6) is closed over by
    # bar 5, but it swept no low and reached no gap, so it only shows up here.
    assert find_cisd(bars, TF, DUR, require_context=False) == [
        Cisd("bullish", t(5), 12.5, closed(5), TF),
        Cisd("bearish", t(7), 10.8, closed(7), TF),
    ]
    assert find_protected_swings(bars, TF, DUR, require_context=False) == [
        ProtectedSwing("low", t(3), 10.6, closed(5), TF, closed(7)),  # bar 7 closes at 10.5
        ProtectedSwing("high", t(5), 13.8, closed(7), TF, None),
    ]


def test_cisd_sweep_candle_that_closes_down_extends_the_series_high() -> None:
    rows = list(BEARISH_CISD)
    rows[5] = (12, 12.9, 11.9, 12.8)  # series stops short of 13
    rows[6] = (12.8, 13.8, 12, 12.2)  # down-close candle makes the high and takes 13
    bars = frame(rows)
    assert find_cisd(bars, TF, DUR) == [Cisd("bearish", t(7), 10.8, closed(7), TF)]
    assert find_protected_swings(bars, TF, DUR) == [
        ProtectedSwing("high", t(6), 13.8, closed(7), TF, None),
    ]


FVG_CONTEXT: list[Row] = [
    (20, 20.5, 19.5, 19.8),
    (19.8, 19.9, 17.5, 17.6),
    (17.6, 18.9, 17, 17.2),  # bearish gap 18.9..19.5
    (17.2, 17.8, 16.8, 17.0),
    (17.0, 18.2, 16.9, 18.0),  # series starts: open 17.0
    (18.0, 19.2, 17.9, 19.0),  # reaches into the gap
    (19.0, 19.1, 17.5, 17.6),
    (17.6, 17.7, 16.5, 16.6),  # closes below 17.0
]


def test_cisd_bearish_out_of_a_fair_value_gap() -> None:
    bars = frame(FVG_CONTEXT)
    assert find_cisd(bars, TF, DUR) == [Cisd("bearish", t(7), 17.0, closed(7), TF)]
    assert find_protected_swings(bars, TF, DUR) == [
        ProtectedSwing("high", t(5), 19.2, closed(7), TF, None),
    ]


def test_cisd_same_leg_with_no_gap_and_no_swept_high_needs_context_off() -> None:
    rows = list(FVG_CONTEXT)
    rows[2] = (17.6, 19.6, 17, 17.2)  # high 19.6 overlaps candle 1: no gap
    bars = frame(rows)
    assert find_cisd(bars, TF, DUR) == []
    assert find_cisd(bars, TF, DUR, require_context=False) == [
        Cisd("bearish", t(7), 17.0, closed(7), TF),
    ]


def test_cisd_bullish_close_over_the_series_that_swept_a_low() -> None:
    rows: list[Row] = [
        (20, 20.5, 19, 19.5),
        (19.5, 19.6, 17, 17.5),  # swing low 17
        (17.5, 19, 17.4, 18.8),
        (18.8, 19.2, 18, 18.9),
        (18.9, 19, 17.8, 18),  # down-close series starts: open 18.9
        (18, 18.1, 16.5, 16.8),  # takes the 17 low; series low 16.5
        (16.8, 18.5, 16.7, 18.3),
        (18.3, 19.4, 18.2, 19.3),  # closes above 18.9
    ]
    bars = frame(rows)
    assert find_cisd(bars, TF, DUR) == [Cisd("bullish", t(7), 18.9, closed(7), TF)]
    assert find_protected_swings(bars, TF, DUR) == [
        ProtectedSwing("low", t(5), 16.5, closed(7), TF, None),
    ]


def test_cisd_one_close_through_nested_series_reports_the_one_that_made_the_high() -> None:
    rows: list[Row] = [
        (10, 12, 9.9, 11.8),  # series A: open 10, high 12
        (11.8, 11.9, 11, 11.2),
        (11.2, 11.7, 11.1, 11.6),  # series B: open 11.2, lower high 11.7
        (11.6, 11.65, 9, 9.5),  # closes below both opens
    ]
    bars = frame(rows)
    assert find_cisd(bars, TF, DUR, require_context=False) == [
        Cisd("bearish", t(3), 10.0, closed(3), TF),
    ]
    assert find_protected_swings(bars, TF, DUR, require_context=False) == [
        ProtectedSwing("high", t(0), 12.0, closed(3), TF, None),
    ]


def test_cisd_max_bars_to_confirm_counts_from_the_high() -> None:
    bars = frame(BEARISH_CISD)  # high at bar 5, confirming close at bar 7
    assert find_cisd(bars, TF, DUR, max_bars_to_confirm=1) == []
    assert len(find_cisd(bars, TF, DUR, max_bars_to_confirm=2)) == 1


def test_cisd_doji_ends_a_series_unless_included() -> None:
    rows: list[Row] = [
        (9.8, 10.5, 9.7, 9.8),  # doji
        (10, 11, 9.95, 10.8),  # up-close: open 10
        (10.8, 10.9, 9.85, 9.9),  # closes below 10 but not below 9.8
    ]
    bars = frame(rows)

    def bearish(**options: bool) -> list[Cisd]:
        found = find_cisd(bars, TF, DUR, require_context=False, **options)
        return [event for event in found if event.direction == "bearish"]

    assert bearish() == [Cisd("bearish", t(2), 10.0, closed(2), TF)]
    assert bearish(doji_in_series=True) == []


def test_protected_swing_breaks_on_close_by_default_and_on_wick_when_asked() -> None:
    rows = BEARISH_CISD + [
        (10.5, 14, 10.4, 11),  # wicks above 13.8, closes below
        (11, 14.5, 10.9, 14.2),  # closes above 13.8
    ]
    bars = frame(rows)

    def protected_high(**options: str) -> list[ProtectedSwing]:
        return [s for s in find_protected_swings(bars, TF, DUR, **options) if s.kind == "high"]

    assert protected_high() == [ProtectedSwing("high", t(5), 13.8, closed(7), TF, closed(9))]
    assert protected_high(break_on="wick") == [
        ProtectedSwing("high", t(5), 13.8, closed(7), TF, closed(8)),
    ]


# --- helpers -----------------------------------------------------------------


def test_equilibrium_is_the_midpoint_of_the_wick_to_wick_range() -> None:
    assert equilibrium(110.0, 100.0) == 105.0


def test_candle_direction_and_measurements() -> None:
    up = {"open": 10.0, "high": 13.0, "low": 9.0, "close": 12.0}
    down = frame([(12, 12.5, 9, 10)]).iloc[0]
    doji = {"open": 10.0, "high": 11.0, "low": 9.0, "close": 10.0}
    assert (candle_direction(up), candle_direction(down), candle_direction(doji)) == ("bullish", "bearish", None)

    measured = measure_candle(up)
    assert (measured.range, measured.body, measured.upper_wick, measured.lower_wick) == (4.0, 2.0, 1.0, 1.0)
    assert (measured.body_top, measured.body_bottom, measured.direction) == (12.0, 10.0, "bullish")
    measured_down = measure_candle(down)
    assert (measured_down.upper_wick, measured_down.lower_wick, measured_down.direction) == (0.5, 1.0, "bearish")
    # 0.5 of the lower wick, body to low.
    assert equilibrium(measured_down.body_bottom, 9.0) == 9.5


def test_known_as_of_drops_unconfirmed_events_and_hides_later_fills() -> None:
    rows = BULLISH_GAP + [(12.8, 12.9, 10.2, 10.8), (10.8, 11.2, 10, 10.3)]
    gaps = find_fair_value_gaps(frame(rows), TF, DUR)
    assert known_as_of(gaps, closed(1)) == []
    assert known_as_of(gaps, closed(3)) == [FairValueGap("bullish", t(1), 11.0, 10.5, closed(2), TF, None)]
    assert known_as_of(gaps, closed(4)) == gaps


def test_missing_price_column_is_rejected() -> None:
    with pytest.raises(ValueError, match="close"):
        find_swings(frame(SWING_ROWS).drop(columns=["close"]), TF, DUR)


# --- no lookahead ------------------------------------------------------------


def random_bars(count: int, seed: int, drop_every: int | None = None) -> pd.DataFrame:
    """A random walk on a 0.25 tick grid (so equal highs, dojis and touching wicks
    occur), optionally with bars removed to leave holes in the clock."""
    rng = np.random.default_rng(seed)
    closes = 100 + np.cumsum(rng.integers(-4, 5, size=count)) * 0.25
    opens = np.concatenate([[100.0], closes[:-1]]) + rng.integers(-1, 2, size=count) * 0.25
    highs = np.maximum(opens, closes) + rng.integers(0, 4, size=count) * 0.25
    lows = np.minimum(opens, closes) - rng.integers(0, 4, size=count) * 0.25
    bars = frame(list(zip(opens, highs, lows, closes)))
    if drop_every:
        bars = bars[np.arange(count) % drop_every != drop_every - 1]
    return bars


FINDERS: list[tuple[str, Callable[[pd.DataFrame], list]]] = [
    ("swings", lambda bars: find_swings(bars, TF, DUR)),
    ("swings_2_equal", lambda bars: find_swings(bars, TF, DUR, bars_each_side=2, allow_equal=True)),
    ("sweeps", lambda bars: find_sweeps(bars, TF, DUR)),
    ("sweeps_2_equal", lambda bars: find_sweeps(bars, TF, DUR, swing_bars=2, allow_equal=True)),
    ("fvg", lambda bars: find_fair_value_gaps(bars, TF, DUR)),
    ("cisd", lambda bars: find_cisd(bars, TF, DUR)),
    ("cisd_open", lambda bars: find_cisd(bars, TF, DUR, require_context=False, doji_in_series=True)),
    ("cisd_fast", lambda bars: find_cisd(bars, TF, DUR, max_bars_to_confirm=3, swing_bars=2)),
    ("protected", lambda bars: find_protected_swings(bars, TF, DUR)),
    ("protected_wick", lambda bars: find_protected_swings(bars, TF, DUR, require_context=False, break_on="wick")),
]


@pytest.mark.parametrize("seed, drop_every", [(1, None), (2, 7)])
def test_truncating_at_every_bar_matches_known_as_of_on_the_full_run(seed: int, drop_every: int | None) -> None:
    bars = random_bars(160, seed, drop_every)
    for name, finder in FINDERS:
        full = finder(bars)
        assert full, f"{name}: the random frame should produce events"
        for keep in range(len(bars) + 1):
            truncated = bars.iloc[:keep]
            as_of = truncated.index[-1] + DUR if keep else bars.index[0]
            assert finder(truncated) == known_as_of(full, as_of), f"{name} differs at bar {keep}"


def test_events_carry_fills_and_breaks_so_the_truncation_test_is_not_vacuous() -> None:
    bars = random_bars(160, 1)
    assert any(gap.filled_at is not None for gap in find_fair_value_gaps(bars, TF, DUR))
    assert any(swing.broken_at is not None for swing in find_protected_swings(bars, TF, DUR))


def test_a_few_thousand_bars_run_well_under_a_second() -> None:
    bars = random_bars(5000, 3)
    for name, finder in FINDERS:
        started = time.perf_counter()
        events = finder(bars)
        elapsed = time.perf_counter() - started
        assert events
        assert elapsed < 1.0, f"{name} took {elapsed:.2f}s on {len(bars)} bars"
