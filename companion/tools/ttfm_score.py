"""Readiness score of a TTFM backtest variant: one number per loop turn, five parts, each 0-10.

    python -m companion.tools.ttfm_score --runs results/backtest_tv_5y --variant ny_window \
        --stacks 1D-4h-15m 1W-1D-1h --max-per-day 1 --day-scope portfolio
    ... --compare baseline --log "ny_window + one trade a day"   # judge it and append to TTRADES/loop-log.md

The improvement loop (in the spirit of an auto-research loop) changes one thing per turn, scores it
with this fixed card, keeps the change only when it beats the current state on **train** (keep rule
below), and logs every turn, kept or not, with its out-of-sample result. The card, fixed before
any result was seen (2026-11-21):

| Part | What it measures | 10 when |
|---|---|---|
| edge | t-statistic of the weekly R (mean / sd * sqrt(weeks)) | t >= 3 |
| robustness | share of calendar years and of symbols with a positive total R | all positive |
| drawdown | R per year / abs(max drawdown in R) | >= 2 |
| teacher | share of the teacher's live trades (livestream notes, ``## Trades``) the engine also took: same trading day, symbol and direction | all of them |
| coverage | share of the rows in TTRADES/engine-gaps.md whose switch has been tested | all tested |

**Keep rule** (``--compare <variant>``): the paired weekly-R difference on train (this turn minus the
comparison, week by week) has t >= 1. Amended 2026-11-21 after the first ten turns, before any
was kept: the card's edge part is 0 for every losing variant, so it cannot rank one loser against
another; the paired difference can. The card stays the readiness grade.

Each part is linear between 0 and its 10. ``score`` is the mean of the five, per period; teacher
agreement counts only that period's live trades, and a period without one is scored on four.
The live trades come from his weekday sessions (New York open, his own sessions); the brain has
them for 2026 only, so teacher agreement is an out-of-sample check that never steers a train choice. **Ready to trade** means
score >= 8 *and* the out-of-sample edge >= 7 (the worse of validate and test). Edge, robustness and
drawdown are computed per walk-forward period (``weekly_r.PERIODS``); a turn is kept on its train
score; validate and test are reported, never used to choose.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from companion.tools.weekly_r import PERIODS, apply_filters, load_runs, max_drawdown, take, trading_day, weekly

REPO = Path(__file__).resolve().parents[2]
BRAIN = REPO / "knowledge" / "second_brain" / "TTRADES"
READY_SCORE, READY_EDGE = 8.0, 7.0

# Tickers the teacher names on stream -> the backtest symbol (micros, CFDs and spot map to the future).
SYMBOLS = {
    "NQ": ("NQ", "MNQ", "NAS100", "NAS100USD", "NDX", "US100"),
    "ES": ("ES", "MES", "MESZ", "SPX", "SPX500", "SPX500USD", "US500"),
    "YM": ("YM", "MYM", "US30"),
    "RTY": ("RTY", "M2K"),
    "GC": ("GC", "MGC", "XAUUSD"),
    "SI": ("SI", "SIL", "XAGUSD"),
    "CL": ("CL", "MCL", "USOIL"),
    "6E": ("6E", "M6E", "EURUSD"),
}
LIVE_SESSIONS = ("new_york_open", "_ttrades_")  # slugs of the teacher's own live trading sessions
_TRADE = re.compile(r"\s*-\s*\*\*([A-Za-z0-9!]+)[^*]*?\b(long|short|buy|sell)\b[^*]*\*\*", re.I)


def map_symbol(ticker: str) -> str | None:
    """``MNQ1!`` -> ``NQ``; None when the ticker is not one of the backtest symbols."""
    root = re.sub(r"(\d+!|!|[FGHJKMNQUVXZ](\d{2}|\d{4}))$", "", ticker.upper())  # 1! / Z25 / Z2025
    for symbol, names in SYMBOLS.items():
        if root in names or ticker.upper() in names:
            return symbol
    return None


def teacher_trades(sources: Path = BRAIN / "sources") -> pd.DataFrame:
    """The teacher's live trades from the livestream notes: one row per (day, symbol, direction)."""
    rows = []
    for path in sorted(sources.glob("livestream_*.md")):
        day = re.match(r"livestream_(\d{8})_", path.name)
        # only his own sessions held on a trading day: weekend recaps and guest streams review
        # trades from other days, so the stream date is not the trade date
        if not day or pd.Timestamp(day.group(1)).dayofweek > 4 or not any(k in path.name for k in LIVE_SESSIONS):
            continue
        section = re.search(r"^## Trades\s*$(.*?)(?=^## |\Z)", path.read_text(encoding="utf-8"), re.M | re.S)
        if not section:
            continue
        for line in section.group(1).splitlines():
            hit = _TRADE.match(line)
            symbol = map_symbol(hit.group(1)) if hit else None
            if symbol:
                side = hit.group(2).lower()
                rows.append({"day": pd.Timestamp(day.group(1)), "symbol": symbol,
                             "direction": "long" if side in ("long", "buy") else "short", "source": path.stem})
    frame = pd.DataFrame(rows, columns=["day", "symbol", "direction", "source"])
    return frame.drop_duplicates(["day", "symbol", "direction"]).reset_index(drop=True)


def agreement(taken: pd.DataFrame, teacher: pd.DataFrame, start: str, end: str) -> tuple[int, int]:
    """(matched, total): teacher trades inside [start, end) whose day, symbol and direction the engine took."""
    inside = teacher[(teacher["day"] >= pd.Timestamp(start)) & (teacher["day"] < pd.Timestamp(end))]
    if inside.empty:
        return 0, 0
    days = taken["fill_time"].map(trading_day) if not taken.empty else pd.Series(dtype="datetime64[ns]")
    engine = set(zip(days, taken.get("symbol", []), taken.get("direction", [])))
    matched = sum((row.day, row.symbol, row.direction) in engine for row in inside.itertuples())
    return matched, len(inside)


def coverage(gaps: Path = BRAIN / "engine-gaps.md") -> tuple[int, int]:
    """(tested, total) rows of the engine-gaps tables (the last column is the status)."""
    tested = total = 0
    for line in gaps.read_text(encoding="utf-8").splitlines() if gaps.exists() else []:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 5 and cells[-1] and not set(cells[-1]) <= set("-") and cells[0] not in ("Gap",):
            if cells[-1] == "—":
                continue
            total += 1
            tested += cells[-1].startswith("tested")
    return tested, total


def _linear(value: float, full: float) -> float:
    return float(np.clip(value / full * 10.0, 0.0, 10.0)) if full else 0.0


@dataclass
class PeriodScore:
    weeks: int
    trades: int
    mean_week: float
    t_stat: float
    edge: float
    robustness: float
    drawdown: float


def period_score(taken: pd.DataFrame, start: str, end: str) -> PeriodScore:
    days = taken["fill_time"].map(trading_day) if not taken.empty else pd.Series(dtype="datetime64[ns]")
    inside = taken[(days >= pd.Timestamp(start)) & (days < pd.Timestamp(end))] if not taken.empty else taken
    week = weekly(inside, start, end)
    sd = float(week.std(ddof=1)) if len(week) > 1 else 0.0
    t = float(week.mean() / sd * np.sqrt(len(week))) if sd > 0 else 0.0
    if inside.empty:
        years_pos = symbols_pos = 0.0
        dd, per_year = 0.0, 0.0
    else:
        by_year = inside.groupby(inside["fill_time"].map(lambda x: x.year))["r"].sum()
        by_symbol = inside.groupby("symbol")["r"].sum()
        years_pos, symbols_pos = float((by_year > 0).mean()), float((by_symbol > 0).mean())
        dd = max_drawdown(inside["r"].to_numpy(dtype=float))
        per_year = float(inside["r"].sum()) / (len(week) / 52.0)
    calmar = per_year / abs(dd) if dd < 0 else (2.0 if per_year > 0 else 0.0)
    return PeriodScore(
        weeks=len(week), trades=len(inside), mean_week=float(week.mean()), t_stat=t,
        edge=_linear(t, 3.0), robustness=10.0 * (years_pos + symbols_pos) / 2.0, drawdown=_linear(calmar, 2.0),
    )


def scorecard(taken: pd.DataFrame, teacher: pd.DataFrame, gaps: Path = BRAIN / "engine-gaps.md") -> dict:
    periods = {name: period_score(taken, *span) for name, span in PERIODS.items()}
    tested, rows = coverage(gaps)
    coverage_part = 10.0 * tested / rows if rows else 0.0
    out: dict = {"periods": periods, "teacher": {}, "coverage": (tested, rows, coverage_part)}
    for name, p in periods.items():
        # teacher agreement per period, so the train score never sees later trades; a period with
        # no live trade (2025) is scored on the other four parts
        matched, total = agreement(taken, teacher, *PERIODS[name])
        out["teacher"][name] = (matched, total)
        parts = [p.edge, p.robustness, p.drawdown, coverage_part] + ([10.0 * matched / total] if total else [])
        out[f"score_{name}"] = float(np.mean(parts))
    oos_edge = min(periods["validate"].edge, periods["test"].edge)
    oos_score = min(out["score_validate"], out["score_test"])
    out["oos_edge"], out["oos_score"] = oos_edge, oos_score
    out["ready"] = oos_score >= READY_SCORE and oos_edge >= READY_EDGE
    return out


KEEP_T = 1.0


def paired(taken: pd.DataFrame, base: pd.DataFrame) -> dict[str, tuple[float, float]]:
    """Per period: (mean, t) of the weekly-R difference, this run minus the comparison."""
    out = {}
    for name, span in PERIODS.items():
        diff = weekly(taken, *span) - weekly(base, *span)
        sd = float(diff.std(ddof=1)) if len(diff) > 1 else 0.0
        out[name] = (float(diff.mean()), float(diff.mean() / sd * np.sqrt(len(diff))) if sd > 0 else 0.0)
    return out


def keep(diff: dict[str, tuple[float, float]]) -> bool:
    """The keep rule: the train difference has t >= KEEP_T. Validate and test are reported only."""
    return diff["train"][1] >= KEEP_T


def render_diff(diff: dict[str, tuple[float, float]], against: str) -> str:
    cells = ", ".join(f"{name} {mean:+.3f} R/wk (t {t:+.2f})" for name, (mean, t) in diff.items())
    return f"Against `{against}`: {cells}. Keep rule (train t >= {KEEP_T:g}): **{'keep' if keep(diff) else 'drop'}**."


def render(card: dict, label: str) -> str:
    lines = [f"### {label}", "",
             "| Period | Weeks | Trades | Mean R/wk | t | Edge | Robust | Drawdown | Teacher | Score |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for name, p in card["periods"].items():
        matched, total = card["teacher"][name]
        teacher = f"{matched}/{total}" if total else "none"
        lines.append(f"| {name} | {p.weeks} | {p.trades} | {p.mean_week:+.2f} | {p.t_stat:+.2f} | {p.edge:.1f} | "
                     f"{p.robustness:.1f} | {p.drawdown:.1f} | {teacher} | {card[f'score_{name}']:.1f} |")
    tested, rows, cpart = card["coverage"]
    lines += ["", f"Teacher = the teacher's live trades the engine also took. Coverage {tested}/{rows} engine gaps tested ({cpart:.1f}). "
              f"Out-of-sample score {card['oos_score']:.1f}, edge {card['oos_edge']:.1f}: "
              + ("**ready to trade**." if card["ready"] else f"not ready (needs score >= {READY_SCORE:g} and edge >= {READY_EDGE:g}).")]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="companion.tools.ttfm_score", description=__doc__.splitlines()[0])
    parser.add_argument("--runs", required=True)
    parser.add_argument("--variant", default="baseline")
    parser.add_argument("--stacks", nargs="*", default=[])
    parser.add_argument("--symbols", nargs="*", default=[])
    parser.add_argument("--filter", nargs="*", default=[])
    parser.add_argument("--target", type=float, default=2.0)
    parser.add_argument("--max-per-day", type=int, default=0)
    parser.add_argument("--day-scope", choices=("stack", "portfolio"), default="stack")
    parser.add_argument("--compare", metavar="VARIANT", help="the run this turn is judged against (keep rule)")
    parser.add_argument("--log", metavar="CHANGE", help="append this turn to TTRADES/loop-log.md")
    args = parser.parse_args(argv)

    def run(variant: str) -> pd.DataFrame:
        trades = apply_filters(load_runs(Path(args.runs), variant, args.stacks, args.symbols), args.filter)
        return take(trades, args.target, args.max_per_day, args.day_scope)

    taken = run(args.variant)
    card = scorecard(taken, teacher_trades())
    setup = (f"variant `{args.variant}`, stacks {' '.join(args.stacks) or 'all'}, filters {' '.join(args.filter) or 'none'}, "
             f"target {args.target:g}R, cap {args.max_per_day or 'none'} per {args.day_scope}")
    text = render(card, setup)
    kept = None
    if args.compare:
        diff = paired(taken, run(args.compare))
        kept = keep(diff)
        text += "\n\n" + render_diff(diff, args.compare)
    print(text)
    if args.log:
        log = BRAIN / "loop-log.md"
        verdict = "no comparison" if kept is None else ("kept" if kept else "dropped")
        entry = (f"\n## {date.today()}: {args.log} ({verdict})\n\n{text}\n")
        with log.open("a", encoding="utf-8") as handle:
            handle.write(entry)
    return 0


if __name__ == "__main__":
    sys.exit(main())
