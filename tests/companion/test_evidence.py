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
