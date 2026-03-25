# TradingView Pine Workflow

## Purpose

Make TradingView usage and Pine development a core part of the repo's learning loop rather than an external manual step.

This workflow exists so the project can move through a deterministic chain:

1. `chart understanding`
2. `rule/spec drafting`
3. `spec -> Pine draft generation`
4. `TradingView editor validation`
5. `backtest or chart replay review`
6. `write-back into findings, draft specs, and training reports`

## Core Principle

TradingView is not just where Pine scripts are pasted.

It is the validation surface for whether a visually learned trading concept can be expressed as a stable, editor-checked, chart-visible artifact.

If a concept cannot survive TradingView validation, it is not ready to be treated as a machine-expressible edge.

## Repo Artifacts

### Pine-target specs

- `results/indicator_specs/*.json`

These are the source-of-truth draft specs for Pine-capable concepts.

### Generated Pine drafts

- `results/pine_scripts/*.pine`
- `results/pine_scripts_manifest.json`

These are generated from indicator specs and should be treated as build artifacts, not hand-authored truth.

### TradingView validation log

- `data/tradingview_pine_validation.json`

This records whether a generated script was:

- opened in the editor
- compiled
- added to chart
- rejected
- or blocked by ambiguity

### TradingView workflow readiness report

- `results/tradingview_pine_readiness_report.json`

This is the bridge artifact consumed by higher-level readiness and training-loop reports.

## Operating Loop

### 1. Build or refresh indicator specs

Use the existing draft-spec pipeline so the system has:

- explicit inputs
- derived series
- state models
- signal pipeline
- provisional proxies

### 2. Generate Pine drafts

Run:

```bash
python scripts/generate_pine_from_spec.py
```

This produces one Pine draft per Pine-target indicator spec.

### 3. Open TradingView

Use Playwriter MCP against an authenticated TradingView chart session.

TradingView should be treated as the editor and chart-validation runtime for Pine drafts.

### 4. Validate the draft in the editor

For each generated Pine draft:

- open the Pine editor
- create or switch to a safe draft script
- paste the generated code
- verify that the actual Monaco editor buffer reflects the generated draft, not only the editor title or store metadata
- compile or update on chart
- capture whether the script compiles
- capture whether the chart output matches the intended concept

Current Playwriter-safe sync path:

- focus the Monaco-backed editor textarea
- replace the full buffer through keyboard selection replacement (`Ctrl+A` then insert the generated draft)
- use `Update on chart`

Do not count title-only or store-only mutations as validation. TradingView can show a new script name while still compiling stale Monaco content.

### 5. Log the outcome

Append validation entries to `data/tradingview_pine_validation.json`.

Suggested entry shape:

```json
{
  "spec_key": "daily_bias_framework",
  "script_path": "results/pine_scripts/daily_bias_framework.pine",
  "validation_status": "compiled",
  "validation_method": "playwriter",
  "notes": "Compiled in TradingView and rendered the expected range/equilibrium overlays."
}
```

### 6. Export readiness

Run:

```bash
python scripts/export_tradingview_pine_readiness_report.py
```

This report is then consumed by:

- `scripts/export_neural_net_readiness_report.py`
- `scripts/export_ttfm_training_loop_report.py`

## What Counts As Success

A Pine draft is only meaningfully successful when it satisfies all of the following:

- it was generated from a repo spec
- it compiles in TradingView
- it can be added to a chart
- the visible output matches the intended component logic closely enough to avoid false confidence

## What Counts As Failure

Failure is useful and should be logged, not hidden.

Important failure modes:

- generated script does not compile
- script compiles but cannot express the concept faithfully
- chart output contradicts screenshot truth
- Playwriter or UI state changes the editor title without changing the Monaco source buffer
- the concept depends on discretionary drawing that Pine cannot express cleanly
- the script only works by introducing repaint-prone shortcuts

These should become:

- findings
- draft-spec revisions
- open questions

They should not silently mutate labels or inflate readiness.

## Why This Is Core To The Neural Loop

The project goal is not only to train a classifier.

The project goal is to build a trading brain that can:

- learn a trading framework visually
- express stable parts of that framework as Pine
- validate those translations in the actual chart environment
- backtest the resulting logic
- and improve from mismatch

That means TradingView and Pine are part of the core learning circuit, not a downstream convenience layer.
