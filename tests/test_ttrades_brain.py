"""The TTrades brain's pipeline: quote checking, the auto-journal's write rules, the trade lookup."""
from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path

PIPE = Path(__file__).resolve().parents[1] / "knowledge" / "second_brain" / "TTRADES" / "_pipeline"


def load(name: str):
    spec = importlib.util.spec_from_file_location(f"ttrades_{name}", PIPE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(PIPE))
    spec.loader.exec_module(mod)
    return mod


SEGS = [
    {"start": 10.0, "end": 20.0, "text": "so we wait for the candle 2 closure"},
    {"start": 20.0, "end": 30.0, "text": "back inside the previous candle's range, right?"},
    {"start": 400.0, "end": 410.0, "text": "and then the change in the state of delivery confirms it"},
]


def test_quote_check_grades_by_place_in_the_transcript():
    b = load("build_index")
    assert b.check_quote('"wait for the candle 2 closure back inside the previous candle\'s range"', [15], SEGS) == "verified"
    assert b.check_quote('"the change in the state of delivery confirms it"', [15], SEGS) == "elsewhere"
    assert b.check_quote('"close below the opening price of the series"', [15], SEGS) == "unverified"
    assert b.check_quote('"[CISD] confirms it"', [400], SEGS) == "no_quote"  # under three words once the analyst's fix is dropped


def test_the_evidence_ledger_rows_are_read_from_their_section_only():
    b = load("build_index")
    text = ("# Evidence\n\n## Ledger\n\n"
            "| Rules | Concept | Switch | Variant | Stacks | Cap | Train | Validate | Test | Verdict | Run |\n"
            "|---|---|---|---|---|---|---|---|---|---|---|\n"
            "| SES-1 | sessions-and-time | kill_zones 08:00-10:30 | ny_window | 1D/4h/15m | 1/day | -0.04 | +0.59 | +0.28 | passes | tv-5y |\n"
            "\n## Notes\n\n| a | b |\n|---|---|\n| x | y |\n")
    rows = b.evidence_rows(text)
    assert rows == [("SES-1", "sessions-and-time", "kill_zones 08:00-10:30", "ny_window", "1D/4h/15m", "1/day",
                     "-0.04", "+0.59", "+0.28", "passes", "tv-5y")]


def row(**kw):
    base = {"symbol": "NQ", "stack": "1D / 1h / 5m", "direction": "short", "path": "reversal", "stage": "c4", "trigger_kind": "cisd",
            "bias": "neutral", "session": "asia", "fill": 100.0, "plan_stop": 110.0, "risk": 10.0, "structural_targets": [80.0],
            "why": "turned at the previous day's high", "net_1r": 1.0, "net_2r": -1.0, "net_3r": -1.0, "first_2r": "loss",
            "criteria": {"rev_cisd_confirmed": True, "rev_reward_at_least_2r": False, "cont_eq_respected": False},
            "_when": datetime(2026, 11, 3, 20, 0), "_source": "backtest baseline", "_file": "results/x.jsonl.gz"}
    base.update(kw)
    return base


def test_trade_note_judges_a_reversal_by_its_own_checklist_only():
    j = load("auto_journal")
    text, meta = j.trade_note(row(), None)
    assert meta["outcome"] == "loss" and meta["result_r"] == -1.0 and meta["strategy"] == "ttfm"
    assert "reward at least 2R" in text and "EQ was respected" not in text  # continuation criteria are not shown
    assert meta["criteria_failed"] == ["rev_reward_at_least_2r"]


def test_day_note_keeps_the_humans_notes_and_review_status():
    j = load("auto_journal")
    _, meta = j.trade_note(row(), None)
    old = "---\nstatus: reviewed\n---\n# old\n\n## My notes\nI would have skipped this: no SMT.\n"
    new = j.day_note(date(2026, 11, 3), [("n", meta)], old)
    assert new.rstrip().endswith("I would have skipped this: no SMT.")
    assert "status: reviewed" in new and "1 trade on NQ" in new


def test_trades_lookup_filters_and_totals(tmp_path, capsys):
    t = load("tt_lookup")
    db = sqlite3.connect(tmp_path / "x.sqlite")
    db.executescript(load("build_index").SCHEMA)
    for i, (sess, r) in enumerate([("asia", 2.0), ("asia", -1.0), ("ny_am", -1.0)]):
        db.execute("insert into trades (id, date, time, symbol, stack, path_kind, session, direction, result_r, outcome, status, note_path) "
                   "values (?,?,?,?,?,?,?,?,?,?,?,?)", (f"t{i}", "2026-11-03", f"0{i}:00", "NQ", "1D / 1h / 5m", "reversal", sess, "short", r,
                                                         "win" if r > 0 else "loss", "draft", f"trades/2026/t{i}.md"))
    t.trades(db, ["session=asia", "path=reversal"])
    out = capsys.readouterr().out
    assert "2 trades" in out and "win rate 50%" in out and "+1.00 R" in out
    t.trades(db, ["colour=red"])
    assert "unknown filter colour" in capsys.readouterr().out
