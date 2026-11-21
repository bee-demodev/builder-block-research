---
title: "TTRADES knowledge base: index and reading guide"
type: ttrades-index
created: 2026-11-20
last_updated: 2026-11-21
source_count: 183
---

# TTRADES knowledge base

What TTrades (@TTrades_edu) teaches about the TTrades Fractal Model (TTFM) and the ICT concepts that
came before it, from 183 recordings (2022-01 to 2026-11): 118 education videos and 65 livestreams
("New York Open Live Q&A" and earlier Sunday / ICT-concepts streams). Written for LLM lookup first and
Obsidian reading second: every rule carries a source slug and a video timestamp, and every quote has
been checked against its transcript (4,638 of 4,718 rules `verified`, none `unverified`; the 55
`no_quote` rows are chart-only demonstrations).

Vik (the student) builds the companion app (`companion/`, style `companion/styles/ttrades/`) from
these rules. His decisions live in [[decisions]] (`TD-nnn`), apart from the teacher's words.
TCM is a different teacher with its own brain (`../TCM-CORE/`); never mix them.

## Fast path (use this first)

```bash
L="C:/Users/satvi/Repos/builder-block-research/knowledge/second_brain/TTRADES/_pipeline/tt_lookup.py"
python $L --map                       # the method: decision chain, pairings, eras, teacher vs engine
python $L cisd                        # concept card: place in the method, definition by era, conflicts, decisions
python $L "candle 2" --rules --grep wick   # merged, cited rules
python $L --search "small wick reversal"   # teacher's rules first, then transcript / page / playbook / journal hits
python $L --quote <slug> 12:34        # the transcript around a cited time (ground truth)
python $L --trades path=reversal session=ny_am   # journaled trades, win rate and R
python $L --day 2026-11-05            # one journal day
python $L --backtest tv-2026-baseline NQ   # a registered backtest, per stack, path and session
```

The project skill `ttrades-intent` (`.claude/skills/ttrades-intent/SKILL.md`) is the workflow: map,
card, check the quote, check the evidence, write the intent brief, ask Vik on an open conflict,
record the answer as `TD-nnn`.

## How to answer a question from this folder

1. Place it on [[method-map]] (draft until Vik reviews it).
2. Resolve the term in [[glossary]] (310 terms, 83 transcript mishearings); open the concept page.
   Its `Rules` table is the merged, cited rule set; `How it changed over time` matters because the
   method moved from ICT concepts (2022) to TTFM (2024-2026); `Engine notes` say where the companion
   differs from the teacher.
3. Check [[conflicts]] (332 rows) before calling a rule settled. Guests (GxTradez, AM Trades, AP
   Trades, Ash, Jokerszn, $niper, MMXM Trader, OTE Trader, DTR) are marked `(guest)`: not TTFM.
4. For detail, open the source note (`sources/<slug>.md`: Key rules, Worked examples, Q&A) and the
   transcript (`--quote`). Livestream notes also carry the day read, the live read table and trades.

Citation form everywhere: `[[<slug>]] mm:ss`. Confidence on rules: `stated`, `demonstrated`, `implied`.
A later video does not override an earlier one unless it says so; the explicit supersessions are
listed in the method map.

## Concept pages

| Page | Covers |
|---|---|
| [[concepts/fractal-model\|fractal-model]] | TTFM overview, timeframe pairing, top-down alignment |
| [[concepts/candle-closures\|candle-closures]] | C1-C4 numbering, candle 2 closure, candle 3 expansion, candle 4, wicks |
| [[concepts/cisd\|cisd]] | CISD, IC-CISD, MSS (2022) and the move to CISD |
| [[concepts/swings-and-structure\|swings-and-structure]] | swing points, protected swings, failure swings, market structure |
| [[concepts/daily-bias\|daily-bias]] | daily bias, invalidation, next-day model, OHLC / OLHC |
| [[concepts/profiles\|profiles]] | weekly, daily and session profiles, day of week |
| [[concepts/poi-and-pd-arrays\|poi-and-pd-arrays]] | FVG, IFVG, order blocks, breakers, gaps |
| [[concepts/liquidity\|liquidity]] | liquidity, sweeps, draw on liquidity, high / low resistance |
| [[concepts/smt-and-psp\|smt-and-psp]] | SMT divergence, PSP, asset strength across NQ / ES / YM |
| [[concepts/ranges-and-eq\|ranges-and-eq]] | EQ (0.5), premium / discount, ADR, dealing range, consolidation, expansion |
| [[concepts/entry-models\|entry-models]] | reversal and continuation setups, triggers, order type, named models |
| [[concepts/sessions-and-time\|sessions-and-time]] | Asia, London, New York, opens, news, time of day |
| [[concepts/risk-and-management\|risk-and-management]] | stops, 2R targets, break even, partials, risk per trade |
| [[concepts/psychology-and-process\|psychology-and-process]] | discipline, one trade a day, backtesting, journaling, prop accounts |
| [[concepts/ttfm-indicator\|ttfm-indicator]] | the TTFM indicator, its settings, table, T-spot |

All 183 sources by date: [[sources-index]].

## Journal (humans) and evidence (agents)

- `../trades/YYYY/*ttfm*.md`: one note per trade, written by `_pipeline/auto_journal.py` from the
  companion's backtest rows (or `--live`, its decision journal): quick log, the engine's checklist,
  `??` blanks, the teacher's rules that bear on it. Set `status: reviewed` when done; it is then never
  overwritten, and its verdict and mistakes become queryable (`--trades`).
- `../journal/YYYY/YYYY-MM-DD__ttfm.md`: the day's table, totals and patterns; `## My notes` is kept.
- `backtests/<id>.md`: registered runs (`_pipeline/ingest_backtest.py <folder> --id <id> --what "..."`).
  Evidence (the engine's own rules, no slippage), never a reason to change a rule without asking.

## Folder layout

| Path | Contents |
|---|---|
| `sources/` | 183 source notes (`type: ttrades-source`) |
| `concepts/` | 15 merged concept pages |
| `glossary.md`, `conflicts.md`, `method-map.md`, `decisions.md`, `sources-index.md` | cross-page files |
| `backtests/` | registered backtest runs |
| `ttrades-index.sqlite`, `rules.jsonl` | generated by `_pipeline/build_index.py` (the lookup rebuilds when notes change) |
| `_merge/` | per-page digests and the conflict / glossary fragments (`_pipeline/assemble.py` joins them) |
| `_pipeline/` | analyst and merge briefs, job files, and the scripts below |

Pipeline scripts: `make_jobs.py` (analyst batches), `livestream_to_sources.py` (livestream analyses to
notes), `retranscribe.py` (faster-whisper over placeholder transcripts; the 62 placeholders are kept in
`ttfm_video_corpus/transcripts/_placeholder_backup/`), `merge_digests.py`, `assemble.py`,
`build_sources_index.py`, `build_index.py`, `tt_lookup.py`, `auto_journal.py`, `ingest_backtest.py`.

Transcripts, frames and videos stay in `../../ttfm_video_corpus/`; education pages in
`artifacts/ttrades/pages/`; earlier playbooks in `../wiki/playbooks/` (seeds for the merge).
