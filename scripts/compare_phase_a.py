"""Phase A confirmation: which triggers changed between the old and new engine on the same data.

    .venv/Scripts/python -m scripts.compare_phase_a

Old: results/backtest_tv/2025/baseline/{SYM}_1D-1h-5m.jsonl.gz (engine before Phase A).
New: results/backtest_phase_a/{SYM}_1D-1h-5m.jsonl.gz (Phase A, defaults).
A trigger is keyed by (symbol, trigger bar open, direction). Expected: the trigger set is
identical, and the only taken -> not-taken changes are triggers first reported after their
2R target or stop had already traded ("already played out" in the summary).
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pandas as pd

from companion.bars import HistoricalBarSource
from companion.styles.ttrades import TTradesStyle
from companion.timeframes import get_stack
from companion.tools.backtest import read_bars_file

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ("check", "decision", "taken", "why", "net_2r", "risk_adr", "lag_min")


def load(path: Path) -> pd.DataFrame:
    rows = []
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        handle.readline()
        for line in handle:
            trade = json.loads(line)
            if trade.get("skipped") or trade.get("risk") is None:
                continue
            rows.append({"key": (trade["symbol"], trade["trigger_open"], trade["direction"]), **{k: trade.get(k) for k in FIELDS}})
    frame = pd.DataFrame(rows)
    # a trigger can be recorded twice (reported again after a gap): keep its first report
    return frame.drop_duplicates("key", keep="first").set_index("key")


def main() -> int:
    for symbol in ("NQ", "ES"):
        old = load(ROOT / f"results/backtest_tv/2025/baseline/{symbol}_1D-1h-5m.jsonl.gz")
        new_path = ROOT / f"results/backtest_phase_a/{symbol}_1D-1h-5m.jsonl.gz"
        if not new_path.exists():
            print(f"{symbol}: new run not finished")
            continue
        new = load(new_path)
        both = old.join(new, lsuffix="_old", rsuffix="_new", how="inner")
        only_old, only_new = old.index.difference(new.index), new.index.difference(old.index)
        changed = both[both["taken_old"] != both["taken_new"]]
        demoted = changed[changed["taken_old"] & ~changed["taken_new"]]
        played = pd.Series(False, index=demoted.index)
        if len(demoted):
            source = HistoricalBarSource(minute_bars={symbol: read_bars_file(ROOT / f"data/external/tradingview/{symbol}_5m.csv")})
            style, stack = TTradesStyle(), get_stack("1D / 1h / 5m")
            for key, row in demoted.iterrows():
                verdict = style.evaluate(symbol, pd.Timestamp(row["check_new"]).to_pydatetime(), stack, source)
                played[key] = verdict.plan is not None and verdict.plan.stage_label == "played_out" and "played out" in verdict.summary
        print(f"{symbol}: triggers old {len(old)} new {len(new)} (only old {len(only_old)}, only new {len(only_new)})")
        print(f"  taken old {int(old['taken'].sum())} new {int(new['taken'].sum())}; changed {len(changed)}, "
              f"taken->watch {len(demoted)} of which 'played out' {int(played.sum())}, watch->taken {len(changed) - len(demoted)}")
        if len(demoted):
            print(f"  demoted: mean net_2r {demoted['net_2r_old'].mean():+.3f}, median lag {demoted['lag_min_old'].median():.0f} min")
        kept = both[both["taken_old"] & both["taken_new"]]
        print(f"  taken in both: n {len(kept)}, mean net_2r {kept['net_2r_new'].mean():+.3f}; "
              f"all old taken {old.loc[old['taken'], 'net_2r'].mean():+.3f} -> all new taken {new.loc[new['taken'], 'net_2r'].mean():+.3f}")
        other = demoted[~played]
        if len(other):
            print("  demoted for another reason:")
            print(other[["check_old", "check_new", "decision_new"]].head(10).to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
