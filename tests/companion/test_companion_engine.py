"""Style registry, TTrades config and primitives, the engine renderers and the CLI."""

from __future__ import annotations

import json
from dataclasses import fields

import pandas as pd
import pytest

from companion import cli
from companion.bars import DATA_DIR
from companion.engine import analyze, render_json, render_text, verdict_to_dict
from companion.styles import Style, get_style, list_styles
from companion.styles.ttrades import TTradesConfig, TTradesStyle, describe_config, load_config
from companion.styles.ttrades.primitives import BEAR, BULL, Bars, anchored_cisd, poi_reached
from companion.styles.ttrades.risk import Trigger, find_continuation_triggers
from companion.timeframes import get_stack
from ttrades_scenarios import SYMBOL, continuation_scenario

DAILY = get_stack("1D / 1h / 5m")
Row = tuple[float, float, float, float]


def bars(rows: list[Row], side=BULL, timeframe: str = "5m") -> Bars:
    index = pd.date_range("2024-01-02 09:30", periods=len(rows), freq="5min", tz="America/New_York", name="timestamp")
    frame = pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=index)
    frame["volume"] = 1.0
    return Bars(frame, timeframe, side)


# --- registry ------------------------------------------------------------------


def test_registry_lists_and_fetches_styles() -> None:
    assert list_styles() == ["ttrades"]
    style = get_style("ttrades")
    assert isinstance(style, Style) and style.name == "ttrades"
    with pytest.raises(KeyError, match="No style named 'nope'"):
        get_style("nope")


# --- config --------------------------------------------------------------------


def test_config_file_documents_every_typed_parameter() -> None:
    config = load_config()
    described = describe_config()
    assert [item["name"] for item in described] == [item.name for item in fields(TTradesConfig)]
    for item in described:
        assert item["description"] and "open_question" in item and "rules" in item, item["name"]
    # the rules.md section 11 defaults
    assert (config.min_rr, config.cisd_max_bars, config.avg_range_bars) == (2.0, 3, 20)
    assert (config.wick_small_frac, config.wick_large_frac, config.closed_wick_large_frac) == (0.25, 0.5, 0.5)
    assert config.kill_zones == (("02:00", "05:00"), ("08:30", "11:00"))
    # the trader's answers of 2026-11-12 (rules.md section 12)
    assert (config.entry_mode_continuation, config.entry_mode_reversal, config.entry_either_pick) == (
        "either", "either", "first",
    )
    assert (config.target_mode, config.target_rr) == ("r_multiple", 2.0)
    assert (config.reward_check_role, config.objective_open_role, config.session_filter_role) == (
        "advisory", "advisory", "advisory",
    )
    assert (config.wick_yardstick, config.wick_body_small_frac, config.wick_body_large_frac) == ("avg_range", 0.5, 1.0)
    assert config.reversal_key_levels == ("previous_candle", "swing", "fvg")
    assert (config.reversal_level_tolerance_frac, config.reversal_expansion_test) == (0.1, "directional_run")
    assert (config.reversal_expansion_min_bars, config.reversal_expansion_min_travel_frac) == (1, 1.0)
    assert config.bias_lookback("1D") == 66 and config.bias_lookback("30m") == 60
    assert config.bias_bars_needed("1D") == 69


def test_config_rejects_bad_answers() -> None:
    with pytest.raises(ValueError, match="entry_mode_continuation"):
        load_config(overrides={"entry_mode_continuation": "yolo"})
    with pytest.raises(ValueError, match="Unknown parameter"):
        load_config(overrides={"not_a_parameter": 1})
    with pytest.raises(ValueError, match="ends before it starts"):
        load_config(overrides={"kill_zones": [["11:00", "08:30"]]})
    for name in ("target_mode", "reward_check_role", "objective_open_role", "session_filter_role", "wick_yardstick",
                 "entry_either_pick", "reversal_expansion_test"):  # fmt: skip
        with pytest.raises(ValueError, match=name):
            load_config(overrides={name: "yolo"})
    with pytest.raises(ValueError, match="reversal_key_levels"):
        load_config(overrides={"reversal_key_levels": ["round_number"]})
    with pytest.raises(ValueError, match="target_rr"):
        load_config(overrides={"target_rr": 0})
    with pytest.raises(ValueError, match="reversal_level_tolerance_frac"):
        load_config(overrides={"reversal_level_tolerance_frac": -0.1})


# --- primitives ----------------------------------------------------------------

CISD_ROWS: list[Row] = [
    (10.0, 10.6, 9.9, 10.5),  # up-close: ends the series
    (10.5, 10.6, 9.0, 9.2),  # series starts: open 10.5 is the level
    (9.2, 9.2, 8.6, 9.2),  # doji inside the run
    (9.2, 9.3, 8.0, 8.2),  # the low
    (8.2, 9.5, 8.1, 9.4),
    (9.4, 10.8, 9.3, 10.7),  # closes above 10.5
]


def test_anchored_cisd_series_level_and_confirmation() -> None:
    read = anchored_cisd(bars(CISD_ROWS), 3, doji_in_series=True)
    assert read.series == (1, 3) and read.level == 10.5 and read.ob_bottom == 8.2
    assert (read.confirm, read.bars_to_confirm, read.lower_low) == (5, 2, None)
    assert read.mean_threshold == pytest.approx(9.35)
    # a doji that is not folded in ends the run: the series is the last candle alone
    strict = anchored_cisd(bars(CISD_ROWS), 3, doji_in_series=False)
    assert strict.series == (3, 3) and strict.level == 9.2 and strict.confirm == 4


def test_anchored_cisd_without_series_and_with_a_lower_low() -> None:
    rows: list[Row] = [(10, 11, 9.5, 10.8), (10.8, 11.2, 9.0, 11.0), (11.0, 11.1, 8.5, 9.0), (9.0, 12, 8.9, 11.9)]
    no_series = anchored_cisd(bars(rows), 1, doji_in_series=True)
    assert no_series.series is None and no_series.level == 11.0  # body top of the anchor
    assert no_series.confirm is None and no_series.lower_low == 2  # a lower low came first
    reanchored = anchored_cisd(bars(rows), 2, doji_in_series=True)
    assert reanchored.series == (2, 2) and reanchored.confirm == 3


def test_bearish_side_mirrors_prices_back_in_text() -> None:
    mirrored = [(20 - o, 20 - l, 20 - h, 20 - c) for o, h, l, c in CISD_ROWS]
    x = bars(mirrored, side=BEAR)
    read = anchored_cisd(x, 3, doji_in_series=True)
    assert read.confirm == 5 and x.p(read.level) == "9.50" and x.p(read.anchor_low) == "12.00"


def test_poi_swing_must_be_confirmed_and_untaken() -> None:
    rows: list[Row] = [
        (10, 11, 9, 10), (10, 10.5, 8, 9.5), (9.5, 11, 9, 10.5),  # swing low 8 at bar 1
        (10.5, 11, 9.5, 10), (10, 10.2, 7.5, 9.8),  # bar 4 takes it
        (9.8, 10, 7.0, 9.0),  # bar 5 trades lower still, but the swing is already taken
    ]  # fmt: skip
    x = bars(rows)
    hit = poi_reached(x, 7.5, 4, min_swing_pos=0, fvg_min_size=0.0)
    assert hit is not None and hit.kind == "swing" and hit.top == 8.0 and "8.00" in hit.text
    assert poi_reached(x, 7.0, 5, min_swing_pos=0, fvg_min_size=0.0) is None
    assert poi_reached(x, 7.5, 4, min_swing_pos=2, fvg_min_size=0.0) is None  # outside the lookback
    assert poi_reached(x, 8.5, 4, min_swing_pos=0, fvg_min_size=0.0) is None  # did not trade below it
    # the swing at bar 1 is not knowable until bar 2 has closed
    assert poi_reached(x, 7.5, 2, min_swing_pos=0, fvg_min_size=0.0) is None


def test_poi_fair_value_gap_until_it_is_closed_through() -> None:
    rows: list[Row] = [
        (10, 10.5, 9.8, 10.4), (10.4, 12.2, 10.3, 12.0), (12.0, 12.8, 11.0, 12.6),  # gap 10.5-11.0
        (12.6, 12.7, 10.8, 11.5),  # trades into it
        (11.5, 11.6, 10.0, 10.2),  # closes below 10.5: filled
        (10.2, 10.9, 10.1, 10.8),
    ]  # fmt: skip
    x = bars(rows)
    hit = poi_reached(x, 10.8, 3, min_swing_pos=0, fvg_min_size=0.0)
    assert hit is not None and hit.kind == "fvg" and (hit.top, hit.bottom) == (11.0, 10.5)
    assert poi_reached(x, 10.8, 3, min_swing_pos=0, fvg_min_size=0.0, min_fvg_top=11.5) is None
    assert poi_reached(x, 10.8, 3, min_swing_pos=0, fvg_min_size=1.0) is None
    assert poi_reached(x, 10.1, 5, min_swing_pos=0, fvg_min_size=0.0) is None  # filled by bar 4


def test_continuation_trigger_needs_a_point_of_interest_that_still_stands() -> None:
    def rows(pullback_low_bar: Row) -> list[Row]:
        return [
            (95.0, 96.0, 90.0, 95.5),  # the protected low 90
            (95.5, 97.0, 95.4, 96.8),
            (96.8, 99.5, 96.7, 99.3),
            (99.3, 101.0, 98.0, 100.8),  # leaves the gap 97-98
            (100.8, 101.0, 97.5, 97.6),  # pulls back into it
            pullback_low_bar,
            (96.2, 101.5, 96.1, 101.2),  # closes above 100.8, the open of the pullback's series
        ]

    def triggers(pullback_low_bar: Row) -> list[Trigger]:
        return find_continuation_triggers(
            bars(rows(pullback_low_bar)), start=1, protected_low=90.0, protected_pos=0, order_block=None, cfg=load_config()
        )

    held = triggers((97.6, 97.8, 97.1, 97.2))  # the gap holds: no close below 97
    assert len(held) == 1
    assert (held[0].pos, held[0].entry, held[0].wick_stop) == (6, 101.2, 97.1)
    assert held[0].poi is not None and held[0].poi.kind == "fvg" and held[0].stopped_at is None
    assert triggers((97.6, 97.8, 96.0, 96.2)) == []  # closes through the gap: nothing was respected


# --- engine --------------------------------------------------------------------


def test_analyze_uses_the_given_source_and_named_style() -> None:
    scenario = continuation_scenario(DAILY)
    source = scenario.source()
    verdict = analyze(SYMBOL, scenario.times["trigger"], DAILY, style_name="ttrades", source=source)
    direct = TTradesStyle().evaluate(SYMBOL, scenario.times["trigger"].to_pydatetime(), DAILY, source)
    assert verdict == direct and verdict.decision == "long"
    # a naive moment is read as New York time
    naive = scenario.times["trigger"].tz_localize(None)
    assert analyze(SYMBOL, str(naive), DAILY, source=source) == verdict
    with pytest.raises(KeyError):
        analyze(SYMBOL, scenario.times["trigger"], DAILY, style_name="nope", source=source)


def test_render_text_is_ascii_and_groups_the_checklist_by_stage() -> None:
    scenario = continuation_scenario(DAILY)
    text = render_text(analyze(SYMBOL, scenario.times["trigger"], DAILY, source=scenario.source()))
    assert text.isascii()
    lines = text.splitlines()
    assert lines[1] == "DECISION: LONG"
    assert lines[2] == "Bias: bullish   Path: continuation   Stage: c4"
    assert lines[3] == "Entry: 97.50   Stop: 91.00 (risk 6.50)   T1: 110.50 (2.00R)"
    headers = [line for line in lines if line and line == line.upper() and not line.startswith(("DECISION", " "))]
    assert headers == [
        "SHARED", "CONTINUATION C1", "CONTINUATION C2", "CONTINUATION C3", "CONTINUATION C4",
        "CONTINUATION C4 - WHY CONTINUATIONS FAIL",
        "REVERSAL C1", "REVERSAL C2", "REVERSAL C3", "REVERSAL C4",
    ]  # fmt: skip
    assert "  [PASS] Entry trigger has formed  (cont_entry_trigger; step, 5m)" in lines
    assert "  [FAIL] Entry trigger has formed  (rev_entry_trigger; step, 5m)" in lines
    assert any(line.startswith("  [ -- ] ") for line in lines)
    waiting = render_text(analyze(SYMBOL, scenario.times["before_setup"], DAILY, source=scenario.source()))
    assert "Entry: -   Stop: -   Targets: -" in waiting


def test_verdict_json_has_iso_datetimes() -> None:
    scenario = continuation_scenario(DAILY)
    verdict = analyze(SYMBOL, scenario.times["trigger"], DAILY, source=scenario.source())
    data = json.loads(render_json(verdict))
    assert data == verdict_to_dict(verdict)
    assert data["as_of"] == scenario.times["trigger"].isoformat()
    assert data["decision"] == "long" and data["stack"]["name"] == "1D / 1h / 5m"
    assert data["targets"] == [110.5]
    assert pd.Timestamp(data["markup"][0]["start"]).tzinfo is not None
    assert {"key", "label", "passed", "detail", "timeframe", "group", "role"} <= set(data["criteria"][0])


# --- CLI -----------------------------------------------------------------------


def test_cli_lists_stacks_and_styles(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["--list-stacks"]) == 0
    listed = capsys.readouterr().out.splitlines()
    assert listed[0] == "1D / 1h / 5m  (default)" and "4h / 15m / 1m" in listed
    assert cli.main(["check", "--list-styles"]) == 0
    assert capsys.readouterr().out.split() == ["ttrades"]


def test_cli_rejects_incomplete_requests(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["check", "--symbol", "NQ", "--at", "2025-01-06 10:00", "--bias", "1D"]) == 2
    assert "--bias, --setup and --entry together" in capsys.readouterr().err
    assert cli.main(["check", "--symbol", "NQ", "--at", "2025-01-06 10:00", "--stack", "9h / 1h / 5m"]) == 2
    assert "No stack named" in capsys.readouterr().err
    assert cli.main(["check", "--symbol", "NQ", "--at", "2025-01-06 10:00", "--style", "nope"]) == 2
    with pytest.raises(SystemExit):
        cli.main(["check", "--symbol", "NQ"])


@pytest.mark.skipif(not (DATA_DIR / "nq_minute.csv").exists(), reason="minute data not present")
def test_cli_check_runs_on_real_data(capsys: pytest.CaptureFixture[str]) -> None:
    arguments = ["check", "--symbol", "NQ", "--at", "2025-11-12 10:45", "--style", "ttrades"]
    assert cli.main([*arguments, "--stack", "1D / 1h / 5m"]) == 0
    text = capsys.readouterr().out
    assert text.isascii() and text.splitlines()[1].startswith("DECISION: ")
    assert cli.main([*arguments, "--bias", "4h", "--setup", "15m", "--entry", "1m", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["stack"] == {"name": "4h / 15m / 1m", "bias": "4h", "setup": "15m", "entry": "1m"}
    assert data["as_of"] == "2025-11-12T10:45:00-05:00"
    assert data["decision"] in ("long", "short", "watch", "no_trade")
