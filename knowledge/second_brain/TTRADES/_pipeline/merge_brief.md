# TTRADES concept merge brief

You write concept pages of the TTRADES knowledge base from every source note (118 education
videos + 65 livestreams of the teacher TTrades, 2022-2026). The reader is an LLM that builds and
reviews the companion trading app (`companion/` in builder-block-research) and must know what the
teacher teaches, how it changed over the years, and what is still undecided. Humans read the same
pages in Obsidian.

KB root: `C:/Users/satvi/Repos/builder-block-research/knowledge/second_brain/TTRADES/` (below `KB/`).

## Inputs per page (read all of them)

1. `KB/_merge/<page>/rules.md`: every Key-rules row mapped to the page, sorted by date. Format:
   `- <date> <slug>#<n> <time> (<conf>) <rule>`. `(upload)` means YouTube upload date, not the
   recording date. Large: read in chunks with offset/limit to the end. Some rows are loosely related;
   use judgement and leave them to their real page.
2. `KB/_merge/<page>/definitions.md` and `note-conflicts.md` (read fully; skim if over 150 KB) and
   `qa.md` (grep it for the questions you need; do not read it whole): bullets that name the page's terms.
3. `KB/_merge/<page>/seeds.md`: earlier playbooks written from the same corpus. Useful structure;
   every claim you keep must still be backed by a source row.
4. `KB/decisions.md`: Vik's decisions (TD-nnn). Never contradict one silently.
5. The companion's own rule text, for "engine" notes only (what the app currently does, kept apart
   from the teacher): `C:/Users/satvi/Repos/builder-block-research/companion/styles/ttrades/rules.md`.
6. A source note (`KB/sources/<slug>.md`) only when a row is unclear. The transcript
   (`C:/Users/satvi/Repos/builder-block-research/knowledge/ttfm_video_corpus/transcripts/<slug>.txt`,
   lines `[seconds] text`) only to settle a specific doubt.

Three voices, always apart: the teacher's words (and guests', named), Vik's decisions, your
inference (label it "inference"). Eras (refine from the dates you see): **2022** ICT-concepts Q&A
streams (MMXM, order blocks, market structure shift); **2023-2024** TTFM takes shape (candle 2 /
candle 3, protected swings, AM Trades guest lessons, weekly profiles); **2025** TTFM indicator,
playbook videos, candle 2 confirmations; **2026** New York Open Live Q&A streams, education-centre
pages, the 3-step model. Never let a later video override an earlier one by being later; only an
explicit "I used to... now I..." supersedes.

## Output 1: `KB/concepts/<page>.md`

Frontmatter (YAML):

```yaml
---
id: <page>
title: "<title>"
type: ttrades-concept
created: 2026-11-21
last_updated: 2026-11-21
aliases: [names, abbreviations, mishearings that should resolve to this page]
covers: [the concept ids this page owns]
sources: [15-25 most important slugs, most important first]
confidence: high | medium | low        # how consistently the corpus defines it
chain_step: [where it sits in the method chain, e.g. "1 bias", "2 profile", "3 setup", "4 entry", "5 manage"]
timeframe_role: [htf, setup, entry, any]
requires: [page ids upstream]
feeds: [page ids downstream]
---
```

Body, in order:

- `## Definition`: the latest definition first (cited), then one short paragraph per earlier era
  where the meaning differed. 4-12 sentences.
- `## Rules`: table `| # | Rule (operational, one sentence) | Conf. | Source (slug, time) |`, rows
  numbered 1..n (bold group rows `| **Group** | | | |` allowed). Merge duplicates into one row with
  several citations. Era tag at the start when a rule belongs to one era, e.g. `(2022)`. Aim for what
  a rule engine or a reviewer needs: 30-80 rows. Citations `[[<slug>]] mm:ss`.
- `## Engine notes`: 3-8 bullets: what the companion's rules.md does for this concept, and where it
  differs from or goes beyond the teacher (inference, cite both).
- `## How it changed over time`: chronological bullets by era, each cited.
- `## Examples`: 3-6 worked examples, one line of context + `[[slug]] mm:ss`.
- `## Conflicts and open questions`: ids from your fragment with one line each.
- `## Related`: `[[<page-id>]]` links with one-line relations.
- `## Questions this page answers`: 6-12 retrieval questions.

No invented content: every rule has a source and time. Dense, not chatty. 20-45 KB.

## Output 2: `KB/_merge/<page>/conflicts-fragment.md`

Starts with the heading line `## [[<page>]]`, then
`| # | Conflict / open question | Side A (slug, time) | Side B (slug, time) | Kind | Status |`.
Ids `<PREFIX>-<n>` from 1 (prefix given in your job). Kinds: cross-video, speech-vs-chart,
teacher-vs-engine, undefined-for-engine, transcription, teacher-vs-convention (ICT/SMC). Status:
`open`, `likely slip`, or `superseded by <slug>`. Rows that block a rule engine first (a number, a
window, a boundary the teacher leaves vague that the companion must pick). 8-30 rows.

## Output 3: `KB/_merge/<page>/glossary-fragment.md`

`| Term | Aliases / mishearings | Meaning (as TTrades uses it) | Concept page | Main source (slug, time) |`
for the page's terms, concept page cell `[[<page>]]`; then a list of mishearings
(`"spelling" -> term (slug)`).

Write only these files (for each page in your job). Do not edit any other file; no git; no subagents.

## Reply

At most 6 lines per page: paths, rule rows, conflict ids, up to 3 findings for the method map.

Page ids: fractal-model, candle-closures, cisd, swings-and-structure, daily-bias, profiles,
poi-and-pd-arrays, liquidity, smt-and-psp, ranges-and-eq, entry-models, sessions-and-time,
risk-and-management, psychology-and-process, ttfm-indicator.
