"""Write companion/config/evidence.json: the backtest record the plan panel shows.

    .venv/Scripts/python -m scripts.phase_b_evidence

Descriptive numbers from the Phase B runs on the current engine (results/phase_b, baseline,
taken trades, market entry, net of costs): per stack, the small-stop cut, and the
best-measured setup with the verdict of its pre-registered re-test (T4 in
results/phase_b/report.md), and the odds board: how often each stack, setup (path and
trigger) and session reached 2R before the stop, the win rate needed to break even after
costs, and how long a target or a stop took. Every year group counts once (2021 is August
to December).
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

import pandas as pd

from scripts.phase_b_tests import GROUPS, load

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "companion/config/evidence.json"
STACKS = ("1D / 1h / 5m", "1D / 4h / 15m", "1W / 4h / 15m", "1W / 1D / 1h")
BEST = {"stacks": ["1D / 4h / 15m", "1W / 1D / 1h"], "trigger": "cisd", "min_risk_adr": 0.10}
SMALL = 0.04
YEAR = {"u21": 2021, "2022": 2022, "2023": 2023, "2024": 2024, "2025": 2025, "2026": 2026}


def span(groups: list[str]) -> str:
    years = sorted(YEAR[g] for g in groups)
    runs: list[list[int]] = []
    for year in years:
        if runs and year == runs[-1][-1] + 1:
            runs[-1].append(year)
        else:
            runs.append([year])
    return ", ".join(f"{r[0]}" if len(r) == 1 else f"{r[0]}-{str(r[-1])[2:]}" for r in runs)


def record(frame: pd.DataFrame) -> dict[str, object]:
    by_group = frame.groupby("group")["net_2r"].mean()
    groups = [g for g in GROUPS if g in by_group.index]
    return {
        "n": int(len(frame)),
        "r": round(float(frame["net_2r"].mean()), 4),
        "years_up": int((by_group > 0).sum()),
        "years": len(groups),
        "span": span(groups),
    }


def odds(frame: pd.DataFrame) -> dict[str, object]:
    """How often 2R came before the stop, the break-even rate after costs and the median times."""
    won = frame["first_2r"] == "win"
    lost = frame["first_2r"] == "loss"
    win_r = float(frame.loc[won, "net_2r"].median()) if won.any() else 2.0
    loss_r = float(-frame.loc[lost, "net_2r"].median()) if lost.any() else 1.0

    def hours(mask: pd.Series) -> float | None:
        return round(float(frame.loc[mask, "minutes_2r"].median()) / 60, 2) if mask.any() else None

    return {
        "n": int(len(frame)),
        "win": round(float(won.mean()), 4),
        "win_1r": round(float((frame["first_1r"] == "win").mean()), 4),
        "open": round(float((frame["first_2r"] == "open").mean()), 4),
        "breakeven": round(loss_r / (win_r + loss_r), 4),
        "hours_to_target": hours(won),
        "hours_to_stop": hours(lost),
        "r": round(float(frame["net_2r"].mean()), 4),
    }


def r_text(value: float) -> str:
    return f"{'−' if value < 0 else '+'}{abs(value):.2f}R"


def main() -> int:
    base = pd.concat([load(g, "baseline") for g in GROUPS], ignore_index=True)
    taken = base[base["taken"]]
    stacks: dict[str, dict[str, object]] = {}
    for name in STACKS:
        part = taken[taken["stack"] == name]
        if part.empty:
            continue
        entry = record(part)
        bias = name.split(" / ")[0]
        exits = [f"2R {r_text(part['net_2r'].mean())}", f"3R {r_text(part['net_3r'].mean())}"]
        if bias == "1D":  # a weekly bias candle often outlives the 10-day horizon: no honest number
            held = part["r_bias_close"].dropna()
            exits.append(f"hold to the 1D close {r_text(held.mean())}")
        entry["exits_line"] = "Exits here: " + " · ".join(exits) + " a trade."
        stacks[name] = entry

    small = taken[(taken["risk_adr"] < SMALL) & taken["stack"].isin(STACKS)]
    best = taken[taken["stack"].isin(BEST["stacks"]) & (taken["trigger_kind"] == BEST["trigger"])
                 & (taken["risk_adr"] >= BEST["min_risk_adr"])]
    report = (ROOT / "results/phase_b/report.md").read_text(encoding="utf-8")
    t4 = re.search(r"\*\*T4 (PASS|FAIL)\*\*", report)
    retest = t4.group(1) if t4 else "not run"
    caveat = {
        "PASS": "Passed two pre-registered tests (2022-23, then 2021), but not significant: a lead, not an edge.",
        "FAIL": "Passed its 2022-23 test, then failed the 2021 re-test: not an edge.",
    }.get(retest, "Passed its 2022-23 test; not significant: a lead, not an edge.")
    measured = taken[taken["stack"].isin(STACKS)].copy()
    measured["setup"] = measured["path"] + "/" + measured["trigger_kind"]
    board = {
        "stacks": {name: odds(measured[measured["stack"] == name]) for name in STACKS if (measured["stack"] == name).any()},
        "setups": {
            name: {key: odds(part) for key, part in measured[measured["stack"] == name].groupby("setup")}
            for name in STACKS
            if (measured["stack"] == name).any()
        },
        "sessions": {key: odds(part) for key, part in measured.groupby("session")},
    }
    data = {
        "generated": date.today().isoformat(),
        "source": "results/phase_b: TradingView 5m, NQ ES GC YM RTY CL SI 6E, Aug 2021 to Nov 2026, taken trades, "
                  "market entry at the first report, 2R target, net of costs",
        "stacks": stacks,
        "setups": {
            "small_stop": {"max_risk_adr": SMALL, **record(small)},
            "best_measured": {**BEST, **record(best), "retest": retest, "caveat": caveat},
        },
        "odds": board,
    }
    OUT.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(data, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
