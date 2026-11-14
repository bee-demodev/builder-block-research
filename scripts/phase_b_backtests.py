"""Score the four Phase B pre-registered backtests (results/backtest_phase_b/PREREGISTERED.md).

    <python> scripts/phase_b_backtests.py [--old-root C:/Users/satvi/Repos/builder-block-research/results]

Reads the trade files of ``companion.tools.backtest`` under results/backtest_phase_b/{core,htf,checks_off}
and writes results/backtest_phase_b/report/{summary.md, test1.csv, test2.csv, test3.csv, test4.csv}.
Every threshold below is the one in PREREGISTERED.md; nothing here is tuned on the results.
"""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("results/backtest_phase_b")
TICKS = {"NQ": 0.25, "ES": 0.25, "YM": 1.0, "RTY": 0.1, "GC": 0.1, "SI": 0.005, "CL": 0.01, "6E": 0.00005}
SYMBOLS = list(TICKS)
QUALITY_CHECKS = (
    "cont_setup_closure_body_aligned", "cont_entry_window_open", "cont_protected_swing_intact",
    "cont_trigger_clear_of_liquidity", "cont_trigger_v_shape", "cont_not_inside_consolidation",
    "cont_objective_open_at_trigger", "cont_entry_early_in_candle", "rev_expansion_into_level",
    "rev_opposing_run_small", "rev_formed_early", "rev_cisd_swift", "rev_wick_intact",
)
DROP = {"criteria", "why", "structural_targets"}


def read_runs(root: Path) -> pd.DataFrame:
    """Every trade row under ``root`` (layout <root>/<year>/<variant>/<SYM>_<stack>.jsonl.gz)."""
    rows = []
    for path in sorted(root.rglob("*.jsonl.gz")):
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            handle.readline()  # meta
            for line in handle:
                trade = json.loads(line)
                row = {k: v for k, v in trade.items() if k not in DROP}
                row["job_year"] = int(path.parent.parent.name)
                row["blocking"] = tuple(trade.get("blocking") or ())
                rows.append(row)
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame["check"] = pd.to_datetime(frame["check"], utc=True).dt.tz_convert("America/New_York")
    frame["year"] = frame["check"].dt.year
    frame["trading_day"] = (frame["check"] + pd.Timedelta(hours=6)).dt.date
    frame["tick"] = frame["symbol"].map(TICKS)
    return frame


def valid_market(frame: pd.DataFrame) -> pd.DataFrame:
    """The findings' row filters: a market fill inside the stop and a stop of at least two ticks."""
    ok = frame["risk"].notna() & frame["skipped"].isna() if "skipped" in frame else frame["risk"].notna()
    ok &= frame["risk"] >= 2 * frame["tick"]
    return frame[ok].copy()


def clustered_t(values: pd.Series, clusters: pd.Series) -> float:
    values = values.astype(float)
    keep = values.notna()
    values, clusters = values[keep], clusters[keep]
    if len(values) < 3:
        return float("nan")
    mu = values.mean()
    sums = (values - mu).groupby(clusters.astype(str).to_numpy()).sum()
    se = float(np.sqrt((sums ** 2).sum())) / len(values)
    return float(mu / se) if se > 0 else float("nan")


def clustered_se(values: pd.Series, clusters: pd.Series) -> float:
    values = values.astype(float)
    mu = values.mean()
    sums = (values - mu).groupby(clusters.astype(str).to_numpy()).sum()
    return float(np.sqrt((sums ** 2).sum())) / len(values) if len(values) else float("nan")


def day_cluster(frame: pd.DataFrame) -> pd.Series:
    return frame["symbol"] + "|" + frame["trading_day"].astype(str)


def md(frame: pd.DataFrame) -> str:
    flat = frame.reset_index(drop=True)
    head = "| " + " | ".join(map(str, flat.columns)) + " |"
    rule = "|" + "---|" * len(flat.columns)
    body = ["| " + " | ".join(f"{v:.3f}" if isinstance(v, float) else str(v) for v in row) + " |"
            for row in flat.itertuples(index=False)]
    return "\n".join([head, rule, *body])


def by_year(values: pd.Series, years: pd.Series) -> dict[int, float]:
    return {int(y): float(v) for y, v in values.groupby(years).mean().items()}


def score_cell(values: pd.Series, frame: pd.DataFrame, clusters: pd.Series, years_needed: int,
               symbols_needed: int | None) -> dict:
    """Pooled mean, t, per-year and per-symbol means, and the pre-registered PASS rule."""
    keep = values.notna()
    values, frame, clusters = values[keep], frame[keep], clusters[keep]
    years = by_year(values, frame["year"])
    symbols = values.groupby(frame["symbol"]).mean()
    mean, t = float(values.mean()) if len(values) else float("nan"), clustered_t(values, clusters)
    years_pos = sum(v > 0 for v in years.values())
    symbols_pos = int((symbols > 0).sum())
    passed = bool(mean > 0 and t >= 2.0 and years_pos >= years_needed
                  and (symbols_needed is None or symbols_pos >= symbols_needed))
    return {"n": int(len(values)), "mean": mean, "t": t, "years_pos": f"{years_pos}/{len(years)}",
            "symbols_pos": f"{symbols_pos}/{len(symbols)}", "by_year": " / ".join(f"{y}: {v:+.3f}" for y, v in years.items()),
            "verdict": "PASS" if passed else "FAIL"}


# --- test 1 -------------------------------------------------------------------------------------


def test1(out: Path) -> tuple[pd.DataFrame, list[str]]:
    frame = valid_market(read_runs(ROOT / "htf"))
    rows, notes = [], []
    for stack in ("1W / 4h / 15m", "1W / 1D / 1h", "1M / 1D / 1h"):
        part = frame[(frame["stack"] == stack) & (frame["risk_adr"] >= 0.10)]
        need = 3 if stack.startswith("1M") else 4
        clusters = part["symbol"] + "|" + part["bias_open"].astype(str)
        for metric, label in (("net_2r", "H1a net_2r, 35 d"), ("r_bias_close", "H1b r_bias_close")):
            cell = score_cell(part[metric], part, clusters, need, 5)
            taken = part[part["taken"]][metric]
            rows.append({"stack": stack, "hypothesis": label, **cell, "taken_n": int(taken.notna().sum()),
                         "taken_mean": float(taken.mean())})
        notes.append(
            f"{stack}: n {len(part)}; 2R open at 10 d {(part['h10_first_2r'] == 'open').mean():.1%}, at 35 d "
            f"{(part['first_2r'] == 'open').mean():.1%}; r_bias_close unresolved {part['r_bias_close'].isna().mean():.1%} "
            f"(10 d: {part['h10_r_bias_close'].isna().mean():.1%}); mean net_2r 10 d {part['h10_net_2r'].mean():+.3f} vs 35 d "
            f"{part['net_2r'].mean():+.3f}; r_bias_close 10 d {part['h10_r_bias_close'].mean():+.3f} vs 35 d "
            f"{part['r_bias_close'].mean():+.3f}")
    table = pd.DataFrame(rows)
    table.to_csv(out / "test1.csv", index=False)
    return table, notes


# --- test 2 -------------------------------------------------------------------------------------


def limit_view(part: pd.DataFrame, window: int) -> pd.DataFrame:
    status = part[f"lim{window}_status"]
    usable = part[status.isin(["filled", "no_fill"])].copy()
    filled = usable[f"lim{window}_status"] == "filled"
    risk_ok = usable[f"lim{window}_risk"].fillna(0) >= 2 * usable["tick"]
    usable = usable[~filled | risk_ok]
    filled = usable[f"lim{window}_status"] == "filled"
    usable["lim_signal"] = np.where(filled, usable[f"lim{window}_net_2r"], 0.0)
    usable["lim_filled"] = filled
    return usable


def test2(out: Path) -> tuple[pd.DataFrame, list[str]]:
    frame = valid_market(read_runs(ROOT / "core"))
    core = frame[frame["stack"].isin(["1D / 1h / 5m", "1D / 4h / 15m"])]
    rows, notes = [], []
    for population, part in (("taken", core[core["taken"]]), ("all triggers", core)):
        for window in (3, 1, 12):
            view = limit_view(part, window)
            filled = view[view["lim_filled"]]
            primary = population == "taken" and window == 3
            a = score_cell(filled[f"lim{window}_net_2r"], filled, day_cluster(filled), 4, 6)
            diff = view["lim_signal"] - view["net_2r"]
            b = score_cell(diff, view, day_cluster(view), 4, None)
            rows.append({"population": population, "window_bars": window, "scored": "yes" if primary else "no",
                         "fill_rate": float(view["lim_filled"].mean()),
                         "at_open": float(filled[f"lim{window}_at_open"].astype(bool).mean()) if len(filled) else np.nan,
                         "market_mean": float(view["net_2r"].mean()),
                         "H2a_n": a["n"], "H2a_mean_filled": a["mean"], "H2a_t": a["t"], "H2a_years": a["years_pos"],
                         "H2a_symbols": a["symbols_pos"], "H2a": a["verdict"], "H2a_by_year": a["by_year"],
                         "H2b_diff": b["mean"], "H2b_t": b["t"], "H2b_years": b["years_pos"], "H2b": b["verdict"],
                         "H2b_by_year": b["by_year"],
                         "excluded_gap_or_nodata": int(len(part) - len(view))})
    for stack in ("1D / 1h / 5m", "1D / 4h / 15m"):
        view = limit_view(core[(core["stack"] == stack) & core["taken"]], 3)
        filled = view[view["lim_filled"]]
        notes.append(f"{stack} taken, W=3: n {len(view)}, fill rate {view['lim_filled'].mean():.1%}, filled mean "
                     f"{filled['lim3_net_2r'].mean():+.3f}, per signal {view['lim_signal'].mean():+.3f} vs market "
                     f"{view['net_2r'].mean():+.3f}")
    htf = valid_market(read_runs(ROOT / "htf"))
    for stack, part in htf[htf["taken"]].groupby("stack"):
        view = limit_view(part, 3)
        filled = view[view["lim_filled"]]
        notes.append(f"{stack} taken (35-day horizon, not scored), W=3: n {len(view)}, fill rate "
                     f"{view['lim_filled'].mean():.1%}, filled mean {filled['lim3_net_2r'].mean():+.3f}, per signal "
                     f"{view['lim_signal'].mean():+.3f} vs market {view['net_2r'].mean():+.3f}")
    table = pd.DataFrame(rows)
    table.to_csv(out / "test2.csv", index=False)
    return table, notes


# --- test 3 -------------------------------------------------------------------------------------


def taken_vs_shadow(frame: pd.DataFrame, label: str, metric: str = "net_2r") -> list[dict]:
    part = frame[(frame["stack"] == "1D / 4h / 15m") & (frame["stage"] == "c4")]
    held = part["blocking"].apply(len) > 0
    taken = part[part["taken"]]
    shadow = part[(part["decision"] == "watch") & held]
    excluded = int(((part["decision"] == "watch") & ~held).sum())
    rows = []
    for years, name in (((2024,), "2024"), ((2025,), "2025"), ((2026,), "2026"), ((2024, 2025, 2026), "2024-26"),
                        ((2022,), "2022 (ref)"), ((2023,), "2023 (ref)"), ((2022, 2023), "2022-23 (ref)")):
        t_part, s_part = taken[taken["year"].isin(years)], shadow[shadow["year"].isin(years)]
        if t_part.empty or s_part.empty:
            continue
        gap = t_part[metric].mean() - s_part[metric].mean()
        se = np.hypot(clustered_se(t_part[metric], day_cluster(t_part)), clustered_se(s_part[metric], day_cluster(s_part)))
        rows.append({"engine": label, "metric": metric, "years": name, "taken_n": len(t_part),
                     "taken_mean": t_part[metric].mean(), "shadow_n": len(s_part), "shadow_mean": s_part[metric].mean(),
                     "gap": gap, "t": gap / se if se > 0 else np.nan, "excluded_played_out_only": excluded})
    return rows


def test3(out: Path, old_root: Path | None) -> tuple[pd.DataFrame, str]:
    frame = valid_market(read_runs(ROOT / "core"))
    rows = taken_vs_shadow(frame, "05209b4") + taken_vs_shadow(frame, "05209b4", "r_bias_close")
    if old_root is not None:
        parts = [read_runs(old_root / "backtest_tv"), read_runs(old_root / "backtest_tv_holdout")]
        old = pd.concat([p for p in parts if not p.empty], ignore_index=True)
        if "variant" in old:
            old = old[old["variant"] == "baseline"]
        rows += taken_vs_shadow(valid_market(old), "a146893 (earlier study files)")
    table = pd.DataFrame(rows)
    table.to_csv(out / "test3.csv", index=False)
    primary = table[(table["engine"] == "05209b4") & (table["metric"] == "net_2r")].set_index("years")
    yearly = all(primary.loc[y, "gap"] > 0 for y in ("2024", "2025", "2026") if y in primary.index) \
        and all(y in primary.index for y in ("2024", "2025", "2026"))
    pooled = primary.loc["2024-26"] if "2024-26" in primary.index else None
    passed = bool(yearly and pooled is not None and pooled["gap"] > 0 and pooled["t"] >= 2.0)
    return table, "PASS" if passed else "FAIL"


# --- test 4 -------------------------------------------------------------------------------------

KEY = ["job_year", "symbol", "direction", "path", "trigger_open", "entry_key", "stop_key"]


def traded(frame: pd.DataFrame, metric: str) -> pd.DataFrame:
    frame = frame[frame["stack"] == "1D / 4h / 15m"].copy()
    frame["entry_key"] = frame["plan_entry"].round(4)
    frame["stop_key"] = frame["plan_stop"].round(4)
    ok = frame["elig_check"].notna()
    if "elig_skipped" in frame:
        ok &= frame["elig_skipped"].isna()
    ok &= frame["elig_risk"].fillna(0) >= 2 * frame["tick"]
    frame["is_traded"] = ok
    frame["o"] = np.where(ok, frame[f"elig_{metric}"].astype(float), 0.0)
    frame.loc[ok & frame[f"elig_{metric}"].isna(), "o"] = np.nan
    return frame[[*KEY, "check", "trading_day", "year", "is_traded", "elig_check", "o"]]


def test4(out: Path) -> tuple[pd.DataFrame, int]:
    base_all = read_runs(ROOT / "core")
    rows, missing = [], 0
    for check in QUALITY_CHECKS:
        runs = [ROOT / "checks_off" / str(year) / f"off-{check}" for year in range(2022, 2027)]
        if not all(r.exists() and len(list(r.glob("*.jsonl.gz"))) == 8 for r in runs):
            missing += 1
            rows.append({"check": check, "verdict": "not run"})
            continue
        variant_all = pd.concat([read_runs(r) for r in runs], ignore_index=True)
        for metric in ("net_2r", "r_bias_close"):
            base = traded(base_all, metric)
            assert not base.duplicated(KEY).any()
            variant = traded(variant_all, metric)
            both = base.merge(variant, on=KEY, how="outer", suffixes=("_b", "_v"), indicator=True)
            for side in ("b", "v"):
                both[f"is_traded_{side}"] = both[f"is_traded_{side}"].astype("boolean").fillna(False).astype(bool)
                both[f"o_{side}"] = both[f"o_{side}"].where(both[f"is_traded_{side}"], 0.0)
            both["check"] = both["check_b"].fillna(both["check_v"])
            both["trading_day"] = both["trading_day_b"].fillna(both["trading_day_v"])
            both["year"] = both["year_b"].fillna(both["year_v"]).astype(int)
            retimed = both["is_traded_b"] & both["is_traded_v"] & (both["elig_check_b"] != both["elig_check_v"])
            affected = (both["is_traded_b"] != both["is_traded_v"]) | retimed
            part = both[affected].copy()
            part = part[part["o_b"].notna() & part["o_v"].notna()]
            part["d"] = part["o_v"] - part["o_b"]
            clusters = part["symbol"] + "|" + part["trading_day"].astype(str)
            mean, t = (float(part["d"].mean()), clustered_t(part["d"], clusters)) if len(part) else (np.nan, np.nan)
            sums = part.groupby("year")["d"].sum()
            added = both[both["is_traded_v"] & ~both["is_traded_b"]]
            if len(part) < 30:
                verdict = "untestable"
            elif mean < 0 and t <= -2.9 and (sums < 0).sum() >= 4:
                verdict = "helps"
            elif mean > 0 and t >= 2.9 and (sums > 0).sum() >= 4:
                verdict = "hurts"
            else:
                verdict = "no measurable effect"
            base_traded = both[both["is_traded_b"]]["o_b"]
            var_traded = both[both["is_traded_v"]]["o_v"]
            rows.append({
                "check": check, "metric": metric, "affected": int(len(part)), "added": int(len(added)),
                "removed": int((both["is_traded_b"] & ~both["is_traded_v"]).sum()), "retimed": int(retimed.sum()),
                "mean_d": mean, "t": t, "sum_d_by_year": " / ".join(f"{int(y)}: {v:+.1f}" for y, v in sums.items()),
                "added_mean": float(added["o_v"].mean()) if len(added) else np.nan,
                "base_traded_n": int(len(base_traded)), "base_traded_mean": float(base_traded.mean()),
                "per_trade_change": float(var_traded.mean() - base_traded.mean()), "verdict": verdict,
            })
    table = pd.DataFrame(rows)
    table.to_csv(out / "test4.csv", index=False)
    return table, missing


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--old-root", help="main checkout results/ (earlier study files, read-only)")
    parser.add_argument("--tests", nargs="*", type=int, default=[1, 2, 3, 4])
    args = parser.parse_args()
    out = ROOT / "report"
    out.mkdir(parents=True, exist_ok=True)
    lines = ["# Phase B backtests: scored against PREREGISTERED.md", ""]
    if 1 in args.tests:
        table, notes = test1(out)
        lines += ["## Test 1: weekly / monthly stacks, 35-day horizon (risk_adr >= 0.10, all triggers)", "", md(table), "",
                  *[f"- {n}" for n in notes], ""]
    if 2 in args.tests:
        table, notes = test2(out)
        lines += ["## Test 2: limit at the plan entry (1D/1h/5m + 1D/4h/15m)", "", md(table), "", *[f"- {n}" for n in notes], ""]
    if 3 in args.tests:
        table, verdict = test3(out, Path(args.old_root) if args.old_root else None)
        lines += [f"## Test 3: taken vs shadow, 1D/4h/15m, stage c4: **{verdict}**", "", md(table), ""]
    if 4 in args.tests:
        table, missing = test4(out)
        lines += [f"## Test 4: eligibility replay, 1D/4h/15m ({missing} check-metric cells not run)", "", md(table), ""]
    (out / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
