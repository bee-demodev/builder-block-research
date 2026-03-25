# autoresearch for trading basics and Pine indicators

This repository adapts Karpathy-style autoresearch to a trading knowledge-base workflow.

## Setup
Work with the human to:
1. Agree on the first active topic. Start with `expansion`.
2. Keep the repo small and the evaluator fixed.
3. Read the in-scope files before each loop:
   - `IMPLEMENTATION_PLAN.md`
   - `knowledge/trading_basics.md` when present
   - `knowledge/modeling_strategy.md` when present
   - `knowledge/pine_basics.md` when present
   - `topics/<topic>/rulebook.json`
   - `topics/<topic>/examples.md`
   - `topics/<topic>/open_questions.md`
   - `results/research_runs.tsv`
4. Keep `results/research_runs.tsv` append-only.

## What the loop optimizes
The goal is not more notes. The goal is a more explicit and more codable rulebook.

Primary metrics:
- grounding
- determinism
- visual verification
- Pine translatability
- contradiction count

## What you can change
- one active topic rulebook
- that topic's examples file
- that topic's open questions file

## What you should not change casually
- evaluator logic
- schema
- overall repo structure

## The loop
1. Pick 1-3 sources from TTrades or official Pine docs.
2. Extract atomic claims.
3. Convert claims into structured rules or open questions.
4. Use Playwriter for visual confirmation where needed.
5. Sync the topic rulebook into SQLite.
6. Score the topic.
7. Log the run.
8. Keep the changes only if the rulebook becomes more deterministic and more Pine-translatable.
9. Repeat until interrupted.

## Simplicity rule
If a change adds complexity without making the rulebook more explicit, discard it.
