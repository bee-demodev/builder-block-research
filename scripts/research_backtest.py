"""Edge search on the enriched backtest: discover on 2025, confirm on 2024, forward-test 2026, cross-asset check.

    .venv/Scripts/python scripts/enrich_backtest.py --source tv
    .venv/Scripts/python scripts/research_backtest.py --source tv          # primary: TradingView 5m bars
    .venv/Scripts/python scripts/research_backtest.py --source databento   # 1m/3m-entry stacks, LOW CONFIDENCE

Output: ``<root>/report/research.md``, ``research_rules.csv``, ``research_cards.csv`` and ``figures/*.png``.

Periods (every table reports all of them side by side):
- ``D25`` discovery: core symbols (NQ ES GC), 2025. Rules are searched and ranked here only.
- ``H24`` confirmation: core symbols, 2024.
- ``F26`` forward out-of-sample: core symbols, 2026 to date.
- ``X`` cross-asset: YM RTY CL SI 6E, all years (never used for discovery).
Universe: variant ``baseline``, every trigger (taken and shadow). R is net of costs, 2R target unless named.
``ct``: t of the mean with errors clustered by symbol x trading day. Rule cards are one position at a time per
symbol and stack (a trigger is skipped while the previous kept trade on that symbol/stack is open at 2R / stop).
A rule "holds" when H24 and F26 have the D25 sign with n >= 50 each, and X has it too where n >= 50.

The Databento source keeps only the 1m/3m-entry stacks (its minute file misses 35-70% of NY-session minutes)
and has no 2026 or extra symbols. The TradingView report also compares the headline numbers with Databento on
the stacks both sources ran (5m+ entries, core symbols, 2024-2025).
"""

from __future__ import annotations

import argparse
import itertools
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CORE = ("NQ", "ES", "GC")
EXTRA = ("YM", "RTY", "CL", "SI", "6E")
STOP_MIN = 0.10  # minimum stop, fraction of the 14-day ADR
PERIODS = ("D25", "H24", "F26", "X")
COLORS = {"D25": "#2a78d6", "H24": "#eb6834", "F26": "#1baf7a", "X": "#6250d6"}  # reference categorical order
PERIOD_NAMES = {"D25": "2025 discovery", "H24": "2024 confirm", "F26": "2026 forward", "X": "5 other symbols"}
INK, INK2, SURF = "#0b0b0b", "#52514e", "#fcfcfb"
EXITS = {"net_1r": "1R target", "net_1.5r": "1.5R", "net_2r": "2R target", "net_3r": "3R target",
         "net_partial": "half at 1R, rest 2R, stop to BE", "net_be2r": "2R, stop to BE at 1R",
         "r_bias_close": "hold to bias-candle close", "r_t1100": "time exit 11:00", "r_t1600": "time exit 16:00"}
SESSION_BINS = [-1, 120, 300, 510, 570, 660, 810, 960, 1080, 1441]
SESSION_LABELS = ["18-02", "02-05", "05-0830", "0830-0930", "0930-11", "11-1330", "1330-16", "16-18", "18-02 "]


# --- periods and metrics ---------------------------------------------------------------------

def period_of(frame: pd.DataFrame) -> pd.Series:
    core = frame["symbol"].isin(CORE)
    out = pd.Series(np.where(~core, "X", ""), index=frame.index, dtype=object)
    out[core & (frame["year"] == 2025)] = "D25"
    out[core & (frame["year"] == 2024)] = "H24"
    out[core & (frame["year"] == 2026)] = "F26"
    return out


def clustered_t(g: pd.DataFrame, col: str = "net_2r") -> float:
    g = g[g[col].notna()]
    if len(g) < 3:
        return np.nan
    s = g.groupby(["symbol", "trading_day"])[col].agg(["sum", "count"])
    mu = g[col].mean()
    se = np.sqrt(((s["sum"] - mu * s["count"]) ** 2).sum()) / len(g)
    return float(mu / se) if se > 0 else np.nan


def one_at_a_time(g: pd.DataFrame) -> pd.DataFrame:
    """Keep a trigger only if the previous kept trade on the same symbol/stack has resolved."""
    keep = []
    for _, part in g.sort_values("check").groupby(["symbol", "stack"]):
        busy_until = None
        fills = pd.to_datetime(part["fill_time"], utc=True)
        done = fills + pd.to_timedelta(part["minutes_2r"].fillna(10 * 1440), unit="min")
        for idx, start, end in zip(part.index, fills, done):
            if busy_until is None or start >= busy_until:
                keep.append(idx)
                busy_until = end
    return g.loc[keep]


def card(g: pd.DataFrame) -> dict:
    """Metrics of one period, one position at a time per symbol/stack."""
    if g.empty:
        return {"n": 0}
    s = one_at_a_time(g).sort_values("check")
    r = s["net_2r"]
    curve = r.cumsum()
    months = max(1, s["check"].dt.tz_localize(None).dt.to_period("M").nunique())
    streams = s.groupby(["symbol", "stack"]).ngroups
    return {"n": len(s), "n_all": len(g), "win1": (s["first_1r"] == "win").mean(), "win2": (s["first_2r"] == "win").mean(),
            "e2": r.mean(), "e1": s["net_1r"].mean(), "e_body": s["r_bias_close"].mean(), "e_part": s["net_partial"].mean(),
            "pf2": r[r > 0].sum() / max(1e-9, -r[r < 0].sum()), "maxdd2": float((curve - curve.cummax()).min()),
            "per_month_stream": len(s) / months / max(1, streams), "ct": clustered_t(s), "e2_all": g["net_2r"].mean()}


def cards(g: pd.DataFrame) -> dict:
    out: dict = {}
    for p in PERIODS:
        out |= {f"{k}_{p}": v for k, v in card(g[g["period"] == p]).items()}
    for sym in CORE + EXTRA:
        part = g[g["symbol"] == sym]
        if len(part):
            out[f"e2_{sym}"] = part["net_2r"].mean()
    signs = [np.sign(out.get(f"e2_{p}", np.nan)) for p in ("D25", "H24", "F26")]
    ns = [out.get(f"n_{p}", 0) for p in ("H24", "F26")]
    x_ok = out.get("n_X", 0) < 50 or np.sign(out.get("e2_X", np.nan)) == signs[0]
    out["holds"] = bool(signs[0] == signs[1] == signs[2] and min(ns) >= 50 and x_ok)
    return out


def by_period(g: pd.DataFrame, by: list[str], col: str = "net_2r", min_n: int = 0) -> pd.DataFrame:
    t = g.groupby(by + ["period"], observed=True)[col].agg(["size", "mean"]).unstack("period")
    t.columns = [f"{'n' if a == 'size' else 'e'}_{b}" for a, b in t.columns]
    t = t[[c for p in PERIODS for c in (f"n_{p}", f"e_{p}") if c in t.columns]]
    if min_n:
        ncols = [c for c in t.columns if c.startswith("n_") and c != "n_X"]
        t = t[t[ncols].min(axis=1) >= min_n]
    return t


def md(frame: pd.DataFrame, floatfmt: str = "{:.3f}") -> str:
    flat = frame.reset_index() if not isinstance(frame.index, pd.RangeIndex) else frame
    rows = ["| " + " | ".join(map(str, flat.columns)) + " |", "|" + "---|" * len(flat.columns)]
    for row in flat.itertuples(index=False):
        rows.append("| " + " | ".join(floatfmt.format(v) if isinstance(v, (float, np.floating)) else str(v)
                                      for v in row) + " |")
    return "\n".join(rows)


# --- conditions and search ---------------------------------------------------------------------

def add_derived(b: pd.DataFrame) -> pd.DataFrame:
    b = b.copy()
    with_bias = ((b["direction"] == "long") & (b["bias"] == "bullish")) | ((b["direction"] == "short") & (b["bias"] == "bearish"))
    b["bias_rel"] = np.where(b["bias"] == "neutral", "neutral", np.where(with_bias, "with", "against"))
    b["tod"] = b["check"].dt.hour * 60 + b["check"].dt.minute
    b["bias_tf"] = b["stack"].str.split(" / ").str[0]
    b["window"] = pd.cut(b["tod"], SESSION_BINS, labels=SESSION_LABELS, ordered=False).astype(str).str.strip()
    b["period"] = period_of(b)
    return b


def conditions(b: pd.DataFrame) -> dict[str, np.ndarray]:
    tod = b["tod"]
    rr_ok = (b["c:cont_reward_at_least_2r"] == True) | ((b["path"] == "reversal") & (b["c:rev_reward_at_least_2r"] == True))  # noqa: E712
    c: dict[str, pd.Series] = {
        "stop>=.10": b["risk_adr"] >= STOP_MIN, "stop>=.2": b["risk_adr"] >= 0.2, "stop<.07": b["risk_adr"] < 0.07,
        "cont": b["path"] == "continuation", "rev": b["path"] == "reversal", "ob": b["trigger_kind"] == "order_block",
        "taken": b["taken"], "fresh": b["fresh"], "lag>15": b["lag_min"] > 15,
        "t0830-1100": (tod >= 510) & (tod < 660), "t0930-1100": (tod >= 570) & (tod < 660),
        "t0830-0930": (tod >= 510) & (tod < 570), "t0200-0500": (tod >= 120) & (tod < 300),
        "t1100-1600": (tod >= 660) & (tod < 960), "t1330-1600": (tod >= 810) & (tod < 960),
        "t1800-0200": (tod >= 1080) | (tod < 120), "t0500-0830": (tod >= 300) & (tod < 510),
        "t0930-1000": (tod >= 570) & (tod < 600), "t1000-1100": (tod >= 600) & (tod < 660),
        "setup_frac<.5": b["setup_frac"] < 0.5, "setup_frac>=.5": b["setup_frac"] >= 0.5,
        "bias_frac<.25": b["bias_frac"] < 0.25, "bias_frac<.5": b["bias_frac"] < 0.5, "bias_frac>=.75": b["bias_frac"] >= 0.75,
        "adr_used<.5": b["adr_used"] < 0.5, "adr_used.5-.78": (b["adr_used"] >= 0.5) & (b["adr_used"] < 0.78),
        "adr_used>=.78": b["adr_used"] >= 0.78, "adr_used>=1": b["adr_used"] >= 1,
        "pd_disc<.25": b["pd_pos_dir"] < 0.25, "pd_prem>.75": b["pd_pos_dir"] > 0.75,
        "pd_out<0": b["pd_pos_dir"] < 0, "pd_out>1": b["pd_pos_dir"] > 1,
        "tgt>=2R": b["tgt_dist_r"] >= 2, "tgt<1R": b["tgt_dist_r"] < 1, "tgt_beyond": b["tgt_dist_r"] < 0,
        "tgt_adr>=.5": b["tgt_dist_adr"] >= 0.5,
        "mon": b["weekday"] == 0, "fri": b["weekday"] == 4, "tue-thu": b["weekday"].isin([1, 2, 3]),
        "first_of_day": b["trade_seq_day"] == 1,
        "moved_with>0": b["day_move_dir"] > 0, "moved_against": b["day_move_dir"] < 0,
        "opp_run<.25": b["opp_run_adr"] < 0.25, "opp_run>=.5": b["opp_run_adr"] >= 0.5,
        "rr2_ok": rr_ok,
        "opened_against_first": b["c:cont_opened_against_bias_first"] == True,  # noqa: E712
        "rev_small_wick": b["c:rev_opposing_run_small"] == True,  # noqa: E712
        "rev_reclaim": b["c:rev_reclaim"] == True,  # noqa: E712
        "session_ok": b["c:session_filter_ok"] == True,  # noqa: E712
    }
    for s in sorted(b["stack"].unique()):
        c["stk=" + s] = b["stack"] == s
    for k in ("pd_target_taken", "pd_stop_swept", "on_target_taken", "on_stop_swept", "inside_prev_day",
              "fomc_day", "first_day_of_month"):
        c[k] = b[k] == True  # noqa: E712
        c["not_" + k] = b[k] == False  # noqa: E712
    for k in ("smt_with", "smt_against", "rs_self_stronger"):
        c[k] = b[k] == 1
        c["not_" + k] = b[k] == 0
    for v in ("with", "against", "neutral"):
        c["bias_" + v] = b["bias_rel"] == v
    return {k: v.fillna(False).to_numpy(bool) for k, v in c.items()}


def search(b: pd.DataFrame, cond: dict[str, np.ndarray], min_n: int) -> pd.DataFrame:
    r = b["net_2r"].to_numpy()
    masks = {p: (b["period"] == p).to_numpy() for p in PERIODS}
    rows = []

    def ev(name: str, mask: np.ndarray) -> None:
        if (mask & masks["D25"]).sum() < min_n:
            return
        row: dict = {"rule": name}
        for p in PERIODS:
            z = mask & masks[p]
            n = int(z.sum())
            sd = r[z].std() if n > 2 else 0.0
            row[f"n_{p}"] = n
            row[f"e_{p}"] = r[z].mean() if n else np.nan
            row[f"t_{p}"] = r[z].mean() / (sd / np.sqrt(n)) if sd > 0 else np.nan
        rows.append(row)

    names = list(cond)
    for k in names:
        ev(k, cond[k])
    for k1, k2 in itertools.combinations(names, 2):
        ev(f"{k1} & {k2}", cond[k1] & cond[k2])
    base = cond["stop>=.10"]
    others = [n for n in names if not n.startswith("stop")]
    for k1, k2 in itertools.combinations(others, 2):
        ev(f"stop>=.10 & {k1} & {k2}", base & cond[k1] & cond[k2])
    return pd.DataFrame(rows)


# --- figures -----------------------------------------------------------------------------------

def _style(ax, title: str, ylabel: str) -> None:
    ax.set_facecolor(SURF)
    ax.set_title(title, loc="left", color=INK, fontsize=11)
    ax.set_ylabel(ylabel, color=INK2)
    ax.tick_params(colors=INK2, labelsize=8)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#c9c8c3")
    ax.axhline(0, color="#8a8984", lw=0.8)
    ax.grid(axis="y", color="#e6e5e0", lw=0.6)
    ax.set_axisbelow(True)


def grouped_bars(t: pd.DataFrame, path: Path, title: str, xlabel: str = "", rotate: int = 0) -> None:
    periods = [p for p in PERIODS if p in t.columns]
    fig, ax = plt.subplots(figsize=(9, 4), facecolor=SURF)
    x = np.arange(len(t))
    width = 0.8 / max(1, len(periods))
    for i, p in enumerate(periods):
        ax.bar(x - 0.4 + width * (i + 0.5), t[p], width * 0.92, color=COLORS[p], label=PERIOD_NAMES[p])
    ax.set_xticks(x, t.index, color=INK2, rotation=rotate, ha="right" if rotate else "center", fontsize=8)
    if xlabel:
        ax.set_xlabel(xlabel, color=INK2)
    _style(ax, title, "mean R")
    ax.legend(frameon=False, fontsize=8, ncol=len(periods))
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig_replication(rules: pd.DataFrame, path: Path) -> None:
    v = rules[rules["n_H24"] >= 50]
    top = v.sort_values("t_D25", ascending=False).head(50)
    fig, ax = plt.subplots(figsize=(6, 5), facecolor=SURF)
    ax.scatter(v["e_D25"], v["e_H24"], s=4, color="#b7b6b0", label=f"all rules (n={len(v)})")
    ax.scatter(top["e_D25"], top["e_H24"], s=14, color=COLORS["D25"], label="top 50 by 2025 t-stat")
    ax.axvline(0, color="#8a8984", lw=0.8)
    _style(ax, "2025 discovery vs 2024 confirmation, mean R per rule", "2024 mean R")
    ax.set_xlabel("2025 mean R", color=INK2)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig_equity(sets: dict[str, pd.DataFrame], path: Path, title: str) -> None:
    fig, ax = plt.subplots(figsize=(9, 4), facecolor=SURF)
    for (name, g), col in zip(sets.items(), ["#2a78d6", "#eb6834", "#1baf7a", "#6250d6"]):
        s = one_at_a_time(g).sort_values("check")
        if len(s):
            ax.plot(s["check"].dt.tz_localize(None), s["net_2r"].cumsum(), color=col, lw=2, label=f"{name} (n={len(s)})")
    _style(ax, title, "cumulative R")
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


# --- main --------------------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=("tv", "databento"), default="tv")
    parser.add_argument("--root", help="default: results/backtest_tv (tv) or results/backtest (databento)")
    parser.add_argument("--min-n", type=int, default=100, help="minimum D25 trades for a rule in the search")
    args = parser.parse_args()
    root = ROOT / (args.root or ("results/backtest_tv" if args.source == "tv" else "results/backtest"))
    report = root / "report"
    fig = report / "figures"
    fig.mkdir(parents=True, exist_ok=True)
    data = pd.read_pickle(report / "trades_enriched.pkl")
    data = data[data["net_2r"].notna()]
    if args.source == "databento":
        data = data[data["stack"].str.split(" / ").str[2].isin(["1m", "3m"])]
    b = add_derived(data[data["variant"] == "baseline"])
    b = b[b["period"] != ""]
    f = b[b["risk_adr"] >= STOP_MIN]
    taken = b[b["taken"]]
    sections: list[tuple[str, str]] = []
    sections.append(("Triggers per period and symbol", md(b.groupby(["period", "symbol"]).size().unstack(fill_value=0).astype(object))))

    # 1. headline re-derivation
    head = pd.DataFrame({"taken (app today)": cards(taken), "all triggers": cards(b), "shadow (held at watch)": cards(b[~b["taken"]]),
                         f"stop >= {STOP_MIN:.0%} ADR": cards(f)}).T
    keep = [f"{k}_{p}" for p in PERIODS for k in ("n_all", "e2_all", "e2", "ct")]
    sections.append(("Headline: taken vs shadow vs all (e2_all = every trigger; e2 = one position at a time)",
                     md(head[[c for c in keep if c in head.columns]].astype(object))))
    stop_edges = [0, .02, .04, .07, .10, .15, .2, .35, 10]
    stop_labels = ["<2%", "2-4%", "4-7%", "7-10%", "10-15%", "15-20%", "20-35%", ">35%"]
    sb = b.assign(stop_bucket=pd.cut(b["risk_adr"], stop_edges, labels=stop_labels))
    t = by_period(sb, ["stop_bucket"])
    t["cost_r"] = sb.groupby("stop_bucket", observed=True)["cost_r"].mean()
    sections.append(("Stop size (risk / ADR14), all triggers", md(t)))
    grouped_bars(t[[c for c in t.columns if c.startswith("e_")]].rename(columns=lambda c: c[2:]), fig / "stop_size.png",
                 "Mean R per trigger (2R target, net) by stop size", "stop size, % of 14-day ADR")
    rows = []
    for th in (0, .04, .06, .08, .10, .15, .2, .3):
        g = b[b["risk_adr"] >= th]
        rows.append({"min_stop_adr": th} | {f"e_{p}": g.loc[g["period"] == p, "net_2r"].mean() for p in PERIODS}
                    | {f"ct_{p}": clustered_t(g[g["period"] == p]) for p in PERIODS})
    sections.append(("Minimum stop threshold (all triggers above it)", md(pd.DataFrame(rows))))
    sections.append(("Path x trigger kind, all triggers", md(by_period(b, ["path", "trigger_kind"]))))
    sections.append((f"Path, stop >= {STOP_MIN:.0%} ADR", md(by_period(f, ["path"]))))
    rows = []
    for key in sorted({k for keys in b["blocking"] for k in keys}):
        alone = b[b["blocking"].apply(lambda keys, k=key: keys == (k,))]
        row: dict = {"held only by": key}
        for p in PERIODS:
            part = alone[alone["period"] == p]
            row[f"n_{p}"], row[f"e_{p}"] = len(part), part["net_2r"].mean() if len(part) else np.nan
        rows.append(row)
    row = {"held only by": "(taken)"}
    for p in PERIODS:
        part = taken[taken["period"] == p]
        row[f"n_{p}"], row[f"e_{p}"] = len(part), part["net_2r"].mean() if len(part) else np.nan
    rows.append(row)
    sections.append(("Quality checks: triggers held back by one check only vs taken", md(pd.DataFrame(rows))))
    sections.append(("Time windows (NY), all triggers", md(by_period(b, ["window"]))))
    sections.append((f"Time windows (NY), stop >= {STOP_MIN:.0%} ADR", md(by_period(f, ["window"]))))

    # 2. rule search: discovery on D25 only
    cond = conditions(b)
    rules = search(b, cond, args.min_n)
    rules.to_csv(report / "research_rules.csv", index=False)
    v = rules[rules["n_H24"] >= 50]
    rep = []
    for k in (20, 50, 200, len(v)):
        top = v.sort_values("t_D25", ascending=False).head(k)
        rep.append({"top_k by D25 t": k} | {f"mean_e_{p}": top[f"e_{p}"].mean() for p in PERIODS}
                   | {f"share_{p}>0": (top[f"e_{p}"] > 0).mean() for p in ("H24", "F26", "X")})
    pos, neg = v[v["t_D25"] >= 2.5], v[v["t_D25"] <= -2.5]
    corr = {p: v[["e_D25", f"e_{p}"]].corr("spearman").iloc[0, 1] for p in ("H24", "F26", "X")}
    note = (f"{len(cond)} conditions, {len(rules)} rules with n_D25 >= {args.min_n}. Spearman of D25 vs H24 / F26 / X mean R "
            f"across rules: {corr['H24']:.2f} / {corr['F26']:.2f} / {corr['X']:.2f}. D25 t >= 2.5: {len(pos)} rules; of these "
            f"H24 t >= 2: {(pos['t_H24'] >= 2).sum()}, and also F26 > 0: {((pos['t_H24'] >= 2) & (pos['e_F26'] > 0)).sum()}. "
            f"D25 t <= -2.5: {len(neg)}; of these H24 t <= -2: {(neg['t_H24'] <= -2).sum()}, and also F26 < 0: "
            f"{((neg['t_H24'] <= -2) & (neg['e_F26'] < 0)).sum()}.")
    sections.append(("Rule search: does the 2025 ranking carry forward?", note + "\n\n" + md(pd.DataFrame(rep))))
    surv = pos[(pos["t_H24"] >= 2) & (pos["e_F26"] > 0)].sort_values("t_H24", ascending=False)
    cols = ["rule"] + [f"{a}_{p}" for p in PERIODS for a in ("n", "e")]
    sections.append(("Positive rules: D25 t >= 2.5, H24 t >= 2, F26 > 0 (plain t, overlapping triggers)", md(surv[cols].head(40))))
    fig_replication(rules, fig / "replication.png")

    # 3. pre-registered rules (from the Databento study) and new candidates
    on_ok = f["on_stop_swept"] == False  # noqa: E712
    cands = {
        "all triggers": b, "taken only (app today)": taken,
        f"S: stop >= {STOP_MIN:.0%} ADR": f, "S + taken": f[f["taken"]],
        "S + reversal": f[f["path"] == "reversal"], "S + continuation": f[f["path"] == "continuation"],
        "R*: S + ADR used >= 78% + ON level behind intact": f[(f["adr_used"] >= .78) & on_ok],
        "R* + taken": f[(f["adr_used"] >= .78) & on_ok & f["taken"]],
        "S + ADR used >= 78%": f[f["adr_used"] >= .78],
        "S + ADR used < 78%": f[f["adr_used"] < .78],
        "S + ON level behind intact": f[on_ok],
        "skip: stop < 4% ADR": b[b["risk_adr"] < .04],
        "skip: continuation, stop < 10% ADR": b[(b["path"] == "continuation") & (b["risk_adr"] < STOP_MIN)],
        "skip: FOMC day": b[b["fomc_day"] == True],  # noqa: E712
        "skip: S + ON level behind taken": f[f["on_stop_swept"] == True],  # noqa: E712
    }
    for rule in surv["rule"].head(5):
        mask = np.ones(len(b), bool)
        for part in rule.split(" & "):
            mask &= cond[part]
        cands[f"search: {rule}"] = b[mask]
    cc = pd.DataFrame({k: cards(g) for k, g in cands.items()}).T
    cc.to_csv(report / "research_cards.csv")
    main_cols = [f"{k}_{p}" for k in ("n", "e2", "ct") for p in PERIODS] + [f"{k}_{p}" for k in ("win2", "pf2", "maxdd2") for p in PERIODS]
    sym_cols = [f"e2_{s}" for s in CORE + EXTRA] + ["holds"]
    sections.append(("Rules, one position at a time per symbol/stack", md(cc[[c for c in main_cols if c in cc]].astype(object))))
    sections.append(("Rules by symbol (all periods, all triggers)", md(cc[[c for c in sym_cols if c in cc]].astype(object))))
    exit_cols = [f"{k}_{p}" for k in ("e1", "e_part", "e_body", "e2", "per_month_stream") for p in PERIODS]
    sections.append(("Rules: other exits and trades per month per symbol/stack (one at a time)",
                     md(cc[[c for c in exit_cols if c in cc]].astype(object))))
    rstar = cands["R*: S + ADR used >= 78% + ON level behind intact"]
    for by in ("stack", "symbol", "path", "window"):
        sections.append((f"R* by {by}", md(by_period(rstar, [by]))))
    sections.append(("S + ADR used >= 78%, by stack", md(by_period(cands["S + ADR used >= 78%"], ["stack"]))))
    core, other = b["symbol"].isin(CORE), ~b["symbol"].isin(CORE)
    fig_equity({"all triggers": b[core], f"stop >= {STOP_MIN:.0%} ADR": f[f["symbol"].isin(CORE)],
                "R* (stop + ADR used >= 78% + ON behind intact)": rstar[rstar["symbol"].isin(CORE)]},
               fig / "equity_core.png", "Cumulative R, NQ/ES/GC, one position at a time per symbol/stack")
    if other.any():
        fig_equity({"all triggers": b[other], f"stop >= {STOP_MIN:.0%} ADR": f[~f["symbol"].isin(CORE)],
                    "R*": rstar[~rstar["symbol"].isin(CORE)]},
                   fig / "equity_other.png", "Cumulative R, YM/RTY/CL/SI/6E (never used for discovery)")

    # 4. stacks and windows
    sections.append((f"Stacks, stop >= {STOP_MIN:.0%} ADR (all triggers)", md(by_period(f, ["stack"]))))
    sections.append((f"Stacks, stop >= {STOP_MIN:.0%} ADR (taken only)", md(by_period(f[f["taken"]], ["stack"]))))
    sections.append(("Stacks, all triggers", md(by_period(b, ["stack"]))))
    tw = by_period(f, ["stack", "window"], min_n=50)
    if len(tw):
        ecols = [c for c in ("e_D25", "e_H24", "e_F26") if c in tw.columns]
        signs = np.sign(tw[ecols])
        tw["one_sign"] = (signs.nunique(axis=1) == 1)
        chance = len(tw) * 2 * 0.5 ** len(ecols)
        sections.append((f"Stack x window, stop >= {STOP_MIN:.0%} ADR, n >= 50 in each core period "
                         f"({int(tw['one_sign'].sum())} of {len(tw)} keep one sign across {len(ecols)} periods; chance about {chance:.0f})",
                         md(tw.astype(object))))

    # 5. exits
    pre11 = f[f["r_t1100"].notna()]
    ex = pre11.groupby("period")[list(EXITS)].mean().T.rename(index=EXITS)
    ex = ex[[p for p in PERIODS if p in ex.columns]]
    sections.append((f"Exits on the same trades (stop >= {STOP_MIN:.0%} ADR, filled before 11:00)", md(ex)))
    grouped_bars(ex, fig / "exits.png", f"Exit methods on the same trades (stop >= {STOP_MIN:.0%} ADR, filled before 11:00)", rotate=30)
    ex_all = f.groupby("period")[["net_1r", "net_1.5r", "net_2r", "net_3r", "net_partial", "net_be2r", "r_bias_close"]].mean().T.rename(index=EXITS)
    sections.append(("Exits, all stop-filtered trades (no time exits)", md(ex_all[[p for p in PERIODS if p in ex_all.columns]])))
    h = b[b["reached_1r"] == True]  # noqa: E712
    be = pd.DataFrame({"P(back to entry before 2R | +1R)": h.groupby("period")["be_after_1r"].mean(),
                       "P(2R before stop | +1R)": (h["first_2r"] == "win").groupby(h["period"]).mean(),
                       "P(+1R before -1R)": (b["first_1r"] == "win").groupby(b["period"]).mean()})
    sections.append(("Path after entry", md(be)))

    # 6. teacher's top-10 claims
    hyp = []

    def claim(name: str, a: pd.DataFrame, z: pd.DataFrame, la: str, lz: str) -> None:
        row = {"claim": name, "A": la, "B": lz}
        for p in PERIODS:
            pa, pz = a[a["period"] == p], z[z["period"] == p]
            row[p] = f"{pa['net_2r'].mean():+.3f} vs {pz['net_2r'].mean():+.3f} ({len(pa)}/{len(pz)})" if len(pa) and len(pz) else ""
        hyp.append(row)

    def only(key: str) -> pd.DataFrame:
        return b[b["blocking"].apply(lambda k: k == (key,))]

    claim("B2 continuation > reversal", b[b["path"] == "continuation"], b[b["path"] == "reversal"], "continuation", "reversal")
    claim("B2 within stop filter", f[f["path"] == "continuation"], f[f["path"] == "reversal"], "continuation", "reversal")
    claim("D10 fresh > stale", b[b["lag_min"] <= 0], b[b["lag_min"] > 15], "lag 0", "lag > 15")
    claim("D10 within stop filter", f[f["lag_min"] <= 0], f[f["lag_min"] > 15], "lag 0", "lag > 15")
    cont = f[f["path"] == "continuation"]
    claim("D1/F1 range left (continuation, stop filter)", cont[cont["adr_used"] < .78], cont[cont["adr_used"] >= .78], "ADR used < 78%", ">= 78%")
    claim("D1/F1 range left (all, stop filter)", f[f["adr_used"] < .78], f[f["adr_used"] >= .78], "ADR used < 78%", ">= 78%")
    rr_ok = (b["c:cont_reward_at_least_2r"] == True) | ((b["path"] == "reversal") & (b["c:rev_reward_at_least_2r"] == True))  # noqa: E712
    rr_bad = ((b["path"] == "continuation") & (b["c:cont_reward_at_least_2r"] == False)) | (  # noqa: E712
        (b["path"] == "reversal") & (b["c:rev_reward_at_least_2r"] == False))  # noqa: E712
    claim("E2 2R fits before structure", b[rr_ok], b[rr_bad], "fits", "does not")
    claim("E2 within stop filter", f[rr_ok.loc[f.index]], f[rr_bad.loc[f.index]], "fits", "does not")
    claim("D9 first half of setup candle (stop filter)", f[f["setup_frac"] < .5], f[f["setup_frac"] >= .5], "first half", "second half")
    for key in ("rev_cisd_swift", "cont_trigger_v_shape", "cont_not_inside_consolidation", "cont_objective_open_at_trigger"):
        claim(f"D7/D2 taken vs held only by {key}", taken, only(key), "taken", "held")
    ct_ = b[b["path"] == "continuation"]
    claim("D2 objective open (continuation)", ct_[ct_["c:cont_objective_open"] == True],  # noqa: E712
          ct_[ct_["c:cont_objective_open"] == False], "open", "already taken")  # noqa: E712
    idx = f[f["symbol"].isin(["NQ", "ES", "YM", "RTY"])]
    am = (idx["tod"] >= 570) & (idx["tod"] < 660)
    claim("A1 NY AM best (index futures, stop filter)", idx[am], idx[~am], "09:30-11:00", "other hours")
    claim("A3 nothing after 11:00 (index futures)", idx[(idx["tod"] >= 510) & (idx["tod"] < 660)],
          idx[(idx["tod"] >= 660) & (idx["tod"] < 960)], "08:30-11:00", "11:00-16:00")
    s5 = f[f["stack"] == "1D / 1h / 5m"]
    tc = s5["trigger_close"].dt.hour * 60 + s5["trigger_close"].dt.minute
    claim("A5 no 5m entries before 09:30 (1D/1h/5m)", s5[(tc >= 570) & (tc < 960)], s5[(tc >= 300) & (tc < 570)], "09:30-16:00", "05:00-09:30")
    d1 = f[f["bias_tf"] == "1D"]
    small, large = d1[d1["opp_run_adr"] < .25], d1[d1["opp_run_adr"] >= .5]
    claim("E5 hold to bias close, small wick (1D bias)", small.assign(net_2r=small["r_bias_close"]), small, "hold to close", "fixed 2R")
    claim("E5 hold to bias close, large wick (1D bias)", large.assign(net_2r=large["r_bias_close"]), large, "hold to close", "fixed 2R")
    pair = f[f["rs_self_stronger"].notna()]
    claim("D11 trade the stronger of the pair", pair[pair["rs_self_stronger"] == 1], pair[pair["rs_self_stronger"] == 0], "stronger", "weaker")
    rv = f[(f["path"] == "reversal") & f["smt_with"].notna()]
    claim("B3 reversal with SMT", rv[rv["smt_with"] == 1], rv[rv["smt_with"] == 0], "SMT", "no SMT")
    sections.append(("Teacher's top-10 claims: mean R A vs B (n A / n B) per period", md(pd.DataFrame(hyp))))

    # 7. TradingView vs Databento on the same stacks / symbols / years
    if args.source == "tv":
        db_path = ROOT / "results/backtest/report/trades_enriched.pkl"
        if db_path.exists():
            db = add_derived(pd.read_pickle(db_path).query("variant == 'baseline'"))
            db = db[db["stack"].isin(set(b["stack"])) & db["period"].isin(["D25", "H24"])]
            tv = b[b["period"].isin(["D25", "H24"])]
            rows = []
            cuts = (("taken", lambda g: g[g["taken"]]), ("all triggers", lambda g: g), ("shadow", lambda g: g[~g["taken"]]),
                    ("stop < 4% ADR", lambda g: g[g["risk_adr"] < .04]), ("stop >= 10% ADR", lambda g: g[g["risk_adr"] >= STOP_MIN]),
                    ("continuation", lambda g: g[g["path"] == "continuation"]), ("reversal", lambda g: g[g["path"] == "reversal"]),
                    ("R*", lambda g: g[(g["risk_adr"] >= STOP_MIN) & (g["adr_used"] >= .78) & (g["on_stop_swept"] == False)]),  # noqa: E712
                    ("S + ADR used >= 78%", lambda g: g[(g["risk_adr"] >= STOP_MIN) & (g["adr_used"] >= .78)]),
                    ("09:30-11:00", lambda g: g[g["window"] == "0930-11"]), ("05:00-08:30", lambda g: g[g["window"] == "05-0830"]))
            for label, fn in cuts:
                row = {"cut": label}
                for p in ("D25", "H24"):
                    a, z = fn(tv[tv["period"] == p]), fn(db[db["period"] == p])
                    row |= {f"tv_n_{p}": len(a), f"tv_e_{p}": a["net_2r"].mean(), f"db_n_{p}": len(z), f"db_e_{p}": z["net_2r"].mean()}
                rows.append(row)
            sections.append(("TradingView vs Databento, same stacks (5m+ entry), NQ/ES/GC, 2024-2025", md(pd.DataFrame(rows))))

    # 8. variants (footnote: whatever exists)
    var = data[data["variant"] != "baseline"]
    if len(var):
        rows = []
        for (name, stack), part in var.groupby(["variant", "stack"]):
            syms = sorted(part["symbol"].unique())
            base = data[(data["variant"] == "baseline") & (data["stack"] == stack) & data["symbol"].isin(syms)
                        & data["year"].isin(part["year"].unique())]
            for label, g in (("baseline", base), (name, part)):
                rows.append({"variant": name, "stack": stack, "symbols": "/".join(syms), "run": label, "n": len(g),
                             "e2": g["net_2r"].mean(), "med_stop_adr": g["risk_adr"].median(),
                             "e2_stop": g.loc[g["risk_adr"] >= STOP_MIN, "net_2r"].mean()})
        sections.append(("Variants vs baseline (same symbol/stack/year)", md(pd.DataFrame(rows))))

    title = "TradingView 5m (primary)" if args.source == "tv" else "Databento 1m/3m-entry stacks (LOW CONFIDENCE: partial minute data)"
    lines = [f"# Backtest research tables: {title}", "",
             "Generated by `scripts/research_backtest.py`. Periods: D25 = NQ/ES/GC 2025 (discovery), H24 = NQ/ES/GC 2024 "
             "(confirmation), F26 = NQ/ES/GC 2026 to date (forward), X = YM/RTY/CL/SI/6E all years (cross-asset). "
             "Mean R net of costs, 2R target unless named. ct = day-clustered t.", ""]
    for heading, body in sections:
        lines += [f"## {heading}", "", body, ""]
    (report / "research.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {report / 'research.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
