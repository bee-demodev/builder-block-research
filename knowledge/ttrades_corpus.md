# TTrades Corpus Baseline

This file captures the current source baseline for the TTrades-driven autoresearch loop.

## Snapshot

As of 2026-03-21, the repo has:
- 85 visible Education Center entries discovered from the main library page
- 28 core concept pages enriched with embedded media discovery
- 28 local markdown extracts for those core concept pages
- a broader imported embedded-media baseline from the full manifest
- 53 embedded YouTube links discovered across the original core concept crawl
- 31 document/media asset links discovered across the original core concept crawl

After import, the SQLite database contains:
- 640 total sources
- 674 source artifacts
- 3 framework records:
  - `canonical_price_action`
  - `ttrades_curriculum`
  - `tradingview_reference`
- 541 normalized `source_topics` links
- 282 normalized `source_trade_models` links
- 82 materialized `trade_model_topic_requirements` rows
- 7 topic rulebooks with scored baselines:
  - `bias`
  - `continuation`
  - `consolidation`
  - `expansion`
  - `protected_swings`
  - `retracement`
  - `reversal`
- 6 active trade models, with one older teacher-named model archived after canonicalization into `fractal_closure_model`

The large jump in link counts is expected too. The repo now preserves both:
- original source hints and embedded-parent links,
- and framework-term matches that keep teacher vocabulary outside the canonical graph while still connecting sources to the right topics and models.

## Core concept coverage

The current core crawl focuses on:
- bias
- expansion
- protected swings
- continuation
- retracement
- reversal
- consolidation

Representative pages include:
- `Easy Daily Bias: A Mechanical Trading Framework`
- `Next Day Model: A Fractal Way to Build Trading Bias`
- `Phases of Price – Part 1..5`
- `Protected Swings in Trading`
- `Stop Loss Mastery`
- `Using Equilibrium in Continuations`
- `Trading Breaker Blocks for Continuations`
- `Mastering Candlestick Wicks`

## Why this matters

This baseline changes the project from a small set of manual notes into a source inventory that can support a proper loop:
- discover sources
- register them in SQLite
- map source-family vocabulary into canonical topics and trade models
- normalize their topic and model coverage
- identify missing artifacts
- ingest markdown or transcripts
- update topic rulebooks
- score the rulebooks
- export trader-specific datasets

## Current backlog snapshot

The current backlog report identifies:
- 60 article or doc sources still missing text artifacts
- 79 video sources still missing transcripts

Those counts define the next ingestion work:
1. attach markdown extracts or manual notes to the highest-value non-ingested article pages
2. attach transcripts to the newly expanded YouTube/video inventory
3. use those artifacts to tighten rulebooks for candle-closure and profile topics
4. bring similar non-TTrades curricula into the same canonical graph by adding framework-scoped terms rather than new one-off topic names
