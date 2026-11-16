"""The backtest record shown on a plan (companion/evidence.py) and the dollar risk per contract."""

from __future__ import annotations

import json

import pytest

from companion import contracts, evidence
from companion.app_model import size_note

DATA = {
    "source": "test",
    "stacks": {
        "1D / 4h / 15m": {"n": 1200, "r": 0.031, "years_up": 4, "years": 6, "span": "2021-26", "exits_line": "2R +0.03R · 3R +0.05R"},
        "1D / 1h / 5m": {"n": 2000, "r": -0.012, "years_up": 2, "years": 4, "span": "2021, 2024-26", "exits_line": ""},
    },
    "setups": {
        "small_stop": {"max_risk_adr": 0.04, "n": 300, "r": -0.25, "years_up": 0, "years": 6, "span": "2021-26"},
        "best_measured": {
            "stacks": ["1D / 4h / 15m", "1W / 1D / 1h"], "trigger": "cisd", "min_risk_adr": 0.10,
            "n": 900, "r": 0.07, "years_up": 5, "years": 6, "span": "2021-26", "caveat": "Not significant: a lead, not an edge.",
        },
    },
}


def test_small_stop_wins_over_every_other_grade() -> None:
    found = evidence.grade("1D / 4h / 15m", "cisd", 0.03, DATA)
    assert found is not None and found.grade == "small_stop"
    assert "under 4% of the daily range" in found.line and "−0.25R a trade over 300" in found.line


def test_best_measured_needs_its_stack_trigger_and_stop() -> None:
    found = evidence.grade("1D / 4h / 15m", "cisd", 0.12, DATA)
    assert found is not None and found.grade == "best_measured"
    assert found.line.startswith("+0.07R a trade over 900 taken trades (2021-26), up in 5 of 6 years tested")
    assert found.exits == "2R +0.03R · 3R +0.05R"
    assert evidence.grade("1D / 4h / 15m", "order_block", 0.12, DATA).grade == "no_edge"
    assert evidence.grade("1D / 4h / 15m", "cisd", 0.08, DATA).grade == "no_edge"
    assert evidence.grade("1D / 1h / 5m", "cisd", 0.30, DATA).grade == "no_edge"


def test_a_failed_retest_is_not_shown_as_the_best_setup() -> None:
    failed = {**DATA, "setups": {**DATA["setups"], "best_measured": {**DATA["setups"]["best_measured"], "retest": "FAIL"}}}
    assert evidence.grade("1D / 4h / 15m", "cisd", 0.12, failed).grade == "no_edge"


def test_other_stacks_show_their_own_record_or_untested() -> None:
    found = evidence.grade("1D / 1h / 5m", "order_block", 0.2, DATA)
    assert found is not None and found.line == "This stack: −0.01R a trade over 2,000 taken trades (2021, 2024-26), up in 2 of 4 years tested."
    assert evidence.grade("1h / 5m / 1m", "cisd", 0.2, DATA).grade == "untested"


def test_no_file_means_no_evidence(tmp_path) -> None:
    assert evidence.grade("1D / 4h / 15m", "cisd", 0.2, {}) is None
    assert evidence.load(tmp_path / "missing.json") is None
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert evidence.load(bad) is None


def test_shipped_file_has_the_fields_the_grader_reads() -> None:
    data = json.loads(evidence.EVIDENCE_PATH.read_text(encoding="utf-8"))
    for name in ("1D / 1h / 5m", "1D / 4h / 15m", "1W / 4h / 15m", "1W / 1D / 1h"):
        record = data["stacks"][name]
        assert {"n", "r", "years_up", "years", "span", "exits_line"} <= set(record)
    assert evidence.grade("1D / 4h / 15m", "cisd", 0.2, data) is not None


@pytest.mark.parametrize(
    ("symbol", "risk", "micro", "mini"),
    [("CME_MINI:NQ1!", 69.5, "$141", "$1,400"), ("ES", 10.0, "$53", "$517"), ("XYZ", 10.0, None, None)],
)
def test_dollar_risk_per_contract(symbol: str, risk: float, micro: str | None, mini: str | None) -> None:
    note = size_note(symbol, risk)
    if micro is None:
        assert note == "" and contracts.risk_usd(symbol, risk) == (None, None)
    else:
        assert note == f"1 micro risks {micro} · 1 mini {mini}"


# --- the odds board ----------------------------------------------------------------


def _odds(n: int, win: float, breakeven: float = 0.34, open_: float = 0.0, target: float | None = 4.6, stop: float | None = 2.1) -> dict:
    return {"n": n, "win": win, "win_1r": 0.48, "open": open_, "breakeven": breakeven, "hours_to_target": target, "hours_to_stop": stop, "r": -0.05}


BOARD = {
    **DATA,
    "odds": {
        "stacks": {"1D / 1h / 5m": _odds(2262, 0.321), "1W / 1D / 1h": _odds(119, 0.13, open_=0.5)},
        "setups": {"1D / 1h / 5m": {"continuation/order_block": _odds(483, 0.30, 0.36, target=0.58, stop=0.25), "reversal/cisd": _odds(1113, 0.326, target=13.0, stop=6.0)}},
        "sessions": {"ny_pm": _odds(202, 0.257, target=67.3), "after_hours": _odds(14, 0.29), "ny_am": _odds(733, 0.33)},
    },
}


def test_the_odds_line_is_the_setups_win_rate_against_break_even_and_how_long_it_took() -> None:
    odds = evidence.odds("1D / 1h / 5m", "continuation/order_block", "ny_am", BOARD)
    assert odds is not None
    assert odds.line == "This setup wins 30% to 2R (breakeven 36%), target ~35 min, stop ~15 min, 483 trades"
    assert [(r.label, r.current) for r in odds.setups] == [("Continuation, order block", True), ("Reversal, CISD", False)]
    assert [r.label for r in odds.sessions] == ["NY AM", "NY PM", "After hours"]  # in the order of the day
    assert [r.current for r in odds.sessions] == [True, False, False]
    assert odds.sessions[1].to_target == "2.8 d" and odds.setups[1].to_target == "13 h"


def test_rows_without_an_honest_win_rate_say_why() -> None:
    odds = evidence.odds("1W / 1D / 1h", "reversal/cisd", "after_hours", BOARD)
    assert odds is not None
    weekly = next(r for r in odds.stacks if r.label == "1W / 1D / 1h")
    assert weekly.note == "Many still open after 10 days" and weekly.current
    assert odds.line == "This stack: many still open after 10 days, so no honest win rate (119 trades)"  # no setups measured: the stack's row
    assert odds.sessions[-1].note == "Too few trades to say (14)"


def test_an_unmeasured_stack_or_an_old_file_has_no_odds_line_or_no_board() -> None:
    odds = evidence.odds("1h / 5m / 1m", "continuation/cisd", "asia", BOARD)
    assert odds is not None and odds.line == "This stack was not backtested on complete data." and not odds.setups
    assert evidence.odds("1D / 1h / 5m", "reversal/cisd", "asia", DATA) is None  # a file from before the board
    graded = evidence.grade("1D / 1h / 5m", "cisd", 0.2, BOARD, path="reversal", session="ny_am")
    assert graded is not None and graded.odds is not None and graded.odds.line.startswith("This setup wins 33% to 2R (breakeven 34%)")


def test_the_live_session_buckets_are_the_backtests() -> None:
    import pandas as pd

    from companion.tools.backtest import session_label

    for minute in range(0, 24 * 60, 5):
        moment = pd.Timestamp("2026-11-13") + pd.Timedelta(minutes=minute)
        assert evidence.session_label(moment) == session_label(moment), moment


def test_the_shipped_file_has_a_board_for_every_measured_stack() -> None:
    data = evidence.load()
    assert data is not None and set(data["odds"]["stacks"]) == set(data["stacks"])
    for stack in data["stacks"]:
        assert data["odds"]["setups"][stack], stack
    assert set(data["odds"]["sessions"]) <= set(evidence.SESSIONS)
