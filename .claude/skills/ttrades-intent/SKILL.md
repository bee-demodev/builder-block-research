---
name: ttrades-intent
description: Look up what TTrades actually teaches before answering a question about a TTrades / TTFM concept or changing how the companion's TTrades style behaves (candle 2 / candle 3, CISD, protected swings, bias, profiles, POI, SMT, sessions, stops, targets, reversal and continuation setups). Use it whenever a task touches trading logic under companion/styles/ttrades or the engine's checklist, when asked "what does he mean by X", "why does the model do X", "what did the journal / backtest show for X", and before writing or reviewing such code. It surfaces contradictions between videos and tells you when to stop and ask Vik.
---

# TTrades intent

The TTrades brain is `C:/Users/satvi/Repos/builder-block-research/knowledge/second_brain/TTRADES/`:
cited source notes for 118 education videos and 65 livestreams (2022-2026), 15 merged concept pages,
a glossary, conflicts, a method map, Vik's decisions (`TD-nnn`), registered backtests and the
auto-journal. Every rule carries `slug mm:ss` and a quote check against the transcript. Set once per shell:

```bash
L="C:/Users/satvi/Repos/builder-block-research/knowledge/second_brain/TTRADES/_pipeline/tt_lookup.py"
```

## Steps

1. **Big picture first.** `python $L --map` once per task: the decision chain (bias → profile →
   setup → entry → manage), the timeframe pairings, the eras. Place the task on the chain.
2. **Card per concept.** `python $L "<concept or phrase>"` for each concept the task touches and for
   its `requires` neighbours. Add `--rules` (and `--grep WORD`). `--search "<words>"` when you do not
   know the concept name: teacher's rules first, then transcript / page / playbook / journal evidence.
3. **Check the wording you depend on.** For the 2-3 rules a change rests on, run
   `python $L --quote <slug> mm:ss` (the transcript is the ground truth; notes were written by
   models). A rule whose quote check is `unverified` or `elsewhere` must be checked this way.
4. **Check the evidence.** `python $L --trades path=<reversal|continuation> session=<asia|london|ny_am|...>`
   for the journaled trades and their R; `python $L --backtest <id> [SYMBOL]` for a registered run
   (`tv-2026-baseline`, `tv-2025-baseline`, `tv-2025-aggressive`, `tv-2025-no_clean_wait`).
   `python $L --evidence <word>` for the evidence ledger: every switch already backtested, its
   walk-forward R per week and verdict. `TTRADES/engine-gaps.md` lists where the engine still differs
   from the teacher, with checked citations; its "improvement loop" (in `ttrades-index.md`) is how a
   new switch gets tested and filed.
   Backtests and journals are evidence (no slippage), never a reason to override the teacher unasked.
5. **Write the intent brief** in your reply before any code: what TTrades teaches (cited), how it
   changed over time, Vik's decisions, open conflicts, where the feature sits on the chain.
6. **Stop and ask Vik** (AskUserQuestion, one question per conflict) when a card lists an UNDECIDED
   conflict the change depends on, the request contradicts a stated rule, a number or window the code
   needs is not taught, a rule is only `implied`, or the lookup says NOT FOUND. Each option carries the
   quote and `slug mm:ss`; offer "make it a setting" when both sides are plausible; recommend one.
7. **Record the answer** as a new row in `TTRADES/decisions.md` (next `TD-nnn`, date, question,
   choice, reason, conflict ids it settles, code path) and cite the id beside the rule in code:
   `# TD-004: CISD needs a body close through the series' open (Vik, 2026-11-21)`.

## Journal

`python TTRADES/_pipeline/auto_journal.py --date YYYY-MM-DD [--symbol NQ ES] [--stack 1D-1h-5m]`
(or `--last 5`, `--live` for the companion's own decision journal) writes one trade note per trade
to `second_brain/trades/YYYY/` and a day note `second_brain/journal/YYYY/YYYY-MM-DD__ttfm.md`, then
refreshes the index. Reviewed notes are never overwritten; a day note keeps its `## My notes`.

## Rules

- Never fill a gap with general ICT/SMC knowledge; TTrades differs from it in places.
- Keep three voices apart: the teacher's (and named guests') words, Vik's decisions, your inference.
- A later video does not override an earlier one unless it says so. A disagreement stays open until
  Vik decides.
- TCM is a different teacher with its own brain (`TCM-CORE/`, `tcm-intent`); never mix them.
