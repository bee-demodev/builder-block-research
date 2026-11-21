"""Per-concept-page evidence digests for the cross-video merge.

  python merge_digests.py        writes TTRADES/_merge/<page>/{rules,definitions,note-conflicts,qa}.md

Every Key-rules row of every source note goes to the page its concept id maps to (PAGES, then
keyword fallbacks). Definitions, Q&A and conflict bullets go to a page when they mention one of its
keywords. Rows are sorted by date (recorded, else YouTube upload date) so eras are visible.
"""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

import yaml

KB = Path(__file__).resolve().parent.parent
OUT = KB / "_merge"
UPLOADS = KB / "_pipeline" / "upload_dates.txt"

# page id -> (title, concept ids it owns, extra keywords for bullets, seed playbooks in wiki/playbooks)
PAGES: dict[str, tuple[str, list[str], list[str], list[str]]] = {
    "fractal-model": ("The TTrades Fractal Model (TTFM) and timeframe pairing", ["fractal-model", "timeframe-pairing", "top-down-alignment", "timeframe-alignment", "ttfm"], ["fractal", "pairing", "timeframe", "top down", "top-down"], ["2026-06-21__three-step-daily-bias-profile-ttfm-model"]),
    "candle-closures": ("Candle numbering: C1-C4, candle 2 closure, candle 3 expansion, wicks", ["candle-2", "candle-3", "candle-4", "candle-1", "candle-closure", "wick", "c2", "c3"], ["candle 2", "candle 3", "candle 4", "c2", "c3", "closure", "wick"], []),
    "cisd": ("CISD and IC-CISD (change in the state of delivery)", ["cisd", "ic-cisd", "intra-candle-cisd", "displacement", "market-structure-shift"], ["cisd", "change in the state", "state of delivery", "displacement"], ["ttfm-swing-quality-cisd-ic-cisd"]),
    "swings-and-structure": ("Swing points, protected swings and market structure", ["protected-swing", "swing-points", "market-structure", "swing-high", "swing-low", "failure-swing", "equal-highs", "equal-lows"], ["protected", "swing", "structure", "equal high", "equal low"], ["ttfm-swing-quality-cisd-ic-cisd"]),
    "daily-bias": ("Daily bias, bias invalidation and the next-day model", ["daily-bias", "bias", "htf-bias", "next-day-model", "bias-invalidation", "ohlc"], ["bias", "invalidat", "next day", "ohlc", "olhc"], ["ttfm-daily-bias-invalidation-and-intraday-reversals", "2026-06-21__three-step-daily-bias-profile-ttfm-model"]),
    "profiles": ("Weekly, daily and session profiles", ["weekly-profile", "daily-profile", "session-profile", "profiles", "protraction"], ["profile", "protraction", "weekly", "day of the week", "tuesday", "wednesday"], ["ttfm-weekly-profiles"]),
    "poi-and-pd-arrays": ("Points of interest: FVG, IFVG, order blocks, breakers, gaps", ["poi", "fvg", "ifvg", "order-block", "breaker", "breaker-block", "gap", "volume-imbalance", "pd-array", "bpr"], ["poi", "point of interest", "fvg", "fair value gap", "ifvg", "inversion", "order block", "breaker", "gap"], ["ttfm-liquidity-and-poi-selection"]),
    "liquidity": ("Liquidity, sweeps and draw on liquidity", ["liquidity", "liquidity-sweep", "draw-on-liquidity", "key-levels", "high-resistance-liquidity", "low-resistance-liquidity", "stop-hunt"], ["liquidity", "sweep", "draw", "key level", "resistance"], ["ttfm-liquidity-and-poi-selection"]),
    "smt-and-psp": ("SMT divergence, PSP and asset strength", ["smt", "psp", "asset-strength", "correlation", "relative-strength"], ["smt", "psp", "divergence", "strongest", "weakest", "correlat"], ["ttfm-smt-and-psp"]),
    "ranges-and-eq": ("Ranges, EQ, premium / discount, ADR, consolidation, expansion and retracement", ["equilibrium", "premium-discount", "adr", "dealing-range", "consolidation", "expansion", "retracement", "range", "phases-of-price"], ["equilibrium", " eq", "0.5", "premium", "discount", "adr", "range", "consolidat", "expansion", "retrac"], ["ttfm-ranges-adr-dealing-range-eq", "ttfm-consolidations-why-continuations-fail"]),
    "entry-models": ("Setups and entry models: reversal, continuation, the playbooks", ["reversal", "continuation", "entry", "entry-model", "setup", "model", "unicorn-model", "three-step-model"], ["reversal", "continuation", "entry", "model", "setup", "limit", "market order"], ["ttfm-entry-timing-and-order-type"]),
    "sessions-and-time": ("Sessions, opens and time of day", ["asia-session", "london-session", "new-york-session", "time-of-day", "news", "killzones", "sessions", "macro", "opening-price"], ["asia", "london", "new york", "session", "open", "killzone", "kill zone", "news", "cpi", "fomc", "time"], ["ttfm-sessions-asia-london-ny"]),
    "risk-and-management": ("Stops, targets, trade management and risk", ["stop-placement", "targets", "trade-management", "risk", "position-sizing", "partials", "break-even"], ["stop", "target", "partial", "break even", "breakeven", "risk", "manage", "r:r", "1r", "2r"], ["ttfm-stop-placement", "ttfm-exits-and-trade-management"]),
    "psychology-and-process": ("Psychology, backtesting, journaling and process", ["psychology", "backtesting", "journaling", "process", "prep-routine", "discipline", "funded-accounts", "prop-firms"], ["psycholog", "backtest", "journal", "patien", "disciplin", "prop", "funded", "routine"], []),
    "ttfm-indicator": ("The TTFM indicator and tooling", ["ttfm-indicator", "indicator", "tooling", "tradingview"], ["indicator", "table", "tradingview", "setting"], ["ttfm-indicator-full-guide"]),
}
LOOSE = {"time", "open", "range", "model", "entry", "setup", "table", "setting", "stop", "risk", "draw", "level", "target",
         "weekly", "session", "manage", "swing", "structure", "closure", "wick", "bias"}
FALLBACK = [("candle", "candle-closures"), ("cisd", "cisd"), ("swing", "swings-and-structure"), ("structure", "swings-and-structure"),
            ("bias", "daily-bias"), ("profile", "profiles"), ("fvg", "poi-and-pd-arrays"), ("gap", "poi-and-pd-arrays"), ("block", "poi-and-pd-arrays"),
            ("poi", "poi-and-pd-arrays"), ("liquid", "liquidity"), ("sweep", "liquidity"), ("level", "liquidity"), ("smt", "smt-and-psp"), ("psp", "smt-and-psp"),
            ("range", "ranges-and-eq"), ("eq", "ranges-and-eq"), ("consolid", "ranges-and-eq"), ("expan", "ranges-and-eq"), ("retrac", "ranges-and-eq"),
            ("session", "sessions-and-time"), ("time", "sessions-and-time"), ("open", "sessions-and-time"), ("news", "sessions-and-time"),
            ("stop", "risk-and-management"), ("target", "risk-and-management"), ("risk", "risk-and-management"), ("manage", "risk-and-management"),
            ("entry", "entry-models"), ("model", "entry-models"), ("reversal", "entry-models"), ("continu", "entry-models"),
            ("psych", "psychology-and-process"), ("backtest", "psychology-and-process"), ("journal", "psychology-and-process"),
            ("indicator", "ttfm-indicator"), ("tool", "ttfm-indicator"), ("fractal", "fractal-model"), ("timeframe", "fractal-model")]


def frontmatter(text: str) -> dict:
    try:
        return yaml.safe_load(text.split("---", 2)[1]) or {}
    except yaml.YAMLError:
        return {}


def section(text: str, heading: str) -> str:
    m = re.search(rf"^## {re.escape(heading)}\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    return m.group(1) if m else ""


def cells(line: str) -> list[str]:
    return [p.strip() for p in re.split(r"(?<!\\)\|", line.strip())[1:-1]]


def page_of(concept: str) -> str:
    c = concept.strip().lower()
    for pid, (_, owns, _, _) in PAGES.items():
        if c in owns:
            return pid
    for key, pid in FALLBACK:
        if key in c:
            return pid
    return "entry-models"


def main() -> None:
    uploads = {}
    if UPLOADS.exists():
        for line in UPLOADS.read_text(encoding="utf-8").split("\n"):
            p = line.split()
            if len(p) == 2 and re.fullmatch(r"\d{8}", p[1]):
                uploads[p[0]] = f"{p[1][:4]}-{p[1][4:6]}-{p[1][6:]}"
    rules, defs, confs, qa = (defaultdict(list) for _ in range(4))
    for p in sorted((KB / "sources").glob("*.md")):
        text = p.read_text(encoding="utf-8")
        fm = frontmatter(text)
        slug = fm.get("slug") or p.stem
        rec = str(fm.get("recorded") or "unknown")
        when = rec if re.match(r"\d{4}-\d{2}-\d{2}", rec) else (uploads.get(str(fm.get("youtube_id"))) or "unknown") + " (upload)"
        for line in section(text, "Key rules").splitlines():
            c = cells(line) if line.lstrip().startswith("|") else []
            if len(c) >= 6 and re.fullmatch(r"\d+", c[0]):
                for concept in c[2].split(","):
                    rules[page_of(concept)].append((when, f"- {when} {slug}#{c[0]} {c[4]} ({c[3]}) {c[1]}"))
        for name, bucket in (("Definitions", defs), ("Conflicts and open questions", confs), ("Q&A", qa), ("Mistakes and warnings", confs)):
            for line in section(text, name).splitlines():
                if not line.strip().startswith("-"):
                    continue
                low = line.lower()
                # the one or two pages whose terms the bullet names most; loose words alone ("time") do not count
                score = {pid: sum(k in low for k in kw if len(k.strip()) > 3 and k.strip() not in LOOSE) +
                         2 * sum(o.replace("-", " ") in low for o in owns) for pid, (_, owns, kw, _) in PAGES.items()}
                best = sorted((v, pid) for pid, v in score.items() if v >= 2)[-2:]
                for _, pid in best:
                    bucket[pid].append((when, f"- {when} [[{slug}]] {line.strip()[2:]}"))
    for pid, (title, owns, kw, seeds) in PAGES.items():
        d = OUT / pid
        d.mkdir(parents=True, exist_ok=True)
        for name, bucket in (("rules", rules), ("definitions", defs), ("note-conflicts", confs), ("qa", qa)):
            rows = [r for _, r in sorted(bucket[pid], key=lambda x: x[0])]
            (d / f"{name}.md").write_text(f"# {title}: {name} ({len(rows)} rows, sorted by date)\n\n" + "\n".join(rows) + "\n", encoding="utf-8")
        (d / "seeds.md").write_text("Seed playbooks (earlier synthesis from the same corpus; verify against the rules):\n" +
                                    "\n".join(f"- C:/Users/satvi/Repos/builder-block-research/knowledge/second_brain/wiki/playbooks/{s}.md" for s in seeds) + "\n", encoding="utf-8")
        print(f"{pid}: {len(rules[pid])} rules, {len(defs[pid])} definitions, {len(confs[pid])} conflict/warning bullets, {len(qa[pid])} Q&A")


if __name__ == "__main__":
    main()
