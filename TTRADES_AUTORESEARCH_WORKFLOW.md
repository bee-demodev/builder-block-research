# TTrades AutoResearch Workflow

This file is the startup workflow for any new Codex session working in this repo.

## Goal

The end state is:
- see TradingView-style charts across flexible timeframe stacks such as `daily + hourly + 5m`, `4H + 30m + 3m`, or whatever TTrades is teaching for that model
- recognize TTrades fractal-model structure
- mark up the chart correctly
- score setup quality
- later support backtested, rule-grounded automation

The current bottleneck is not infrastructure. It is supervised visual data volume and quality.

## Start Here Every Session

Read these files first:
- [results/workflow_status.json](C:\Users\satvi\Repos\builder-block-research\results\workflow_status.json)
- [results/phase2_dataset_stats.json](C:\Users\satvi\Repos\builder-block-research\results\phase2_dataset_stats.json)
- [results/phase3_report.json](C:\Users\satvi\Repos\builder-block-research\results\phase3_report.json)
- [results/phase2_dense_supervision_packet.json](C:\Users\satvi\Repos\builder-block-research\results\phase2_dense_supervision_packet.json)
- [results/phase2_dense_supervision_answers.json](C:\Users\satvi\Repos\builder-block-research\results\phase2_dense_supervision_answers.json)

## How To Invoke In A New Codex Session

This is a repo workflow, not a globally installed Codex skill.

Use one of these exact prompts in a fresh session:

```text
Follow TTRADES_AUTORESEARCH_WORKFLOW.md and results/workflow_status.json. Continue from the current next_action without asking me for permission unless something is destructive or ambiguous.
```

If you want the session to focus specifically on the TTrades data loop:

```text
Open TTRADES_AUTORESEARCH_WORKFLOW.md and results/workflow_status.json, then continue the dense TTrades supervision workflow. Keep refreshing Phase 2 and rerunning Phase 3 only when the workflow thresholds say it is worth it.
```

If you want a status-first session:

```text
Read TTRADES_AUTORESEARCH_WORKFLOW.md and results/workflow_status.json, summarize current status, then execute the next recommended step.
```

## Ground Rules

- Use `uv` for everything.
- Do not use external OpenAI keys for Phase 2 unless explicitly requested.
- Prefer Codex-supervised labeling from the dense TTrades packet.
- Retraining YOLO is only worth it after a meaningful label increase.
- Apply obvious workflow fixes without asking for permission unless the action is destructive or changes scope materially.
- Do not rebuild the dense corpus if [knowledge/ttfm_video_corpus/dense_visual_embedding_manifest.json](C:\Users\satvi\Repos\builder-block-research\knowledge\ttfm_video_corpus\dense_visual_embedding_manifest.json) is already fresh.
- Do not promote slide-like teaching frames into the dense supervision packet.

## The Loop

1. Review more dense TTrades images.
2. Add detections to [results/phase2_dense_supervision_answers.json](C:\Users\satvi\Repos\builder-block-research\results\phase2_dense_supervision_answers.json).
3. Refresh the dataset:

```bash
uv run python main.py --phase 2 --wandb-mode disabled
```

4. Check [results/workflow_status.json](C:\Users\satvi\Repos\builder-block-research\results\workflow_status.json).
5. Only retrain YOLO when the workflow says enough new labels have accumulated:

```bash
uv run python main.py --phase 3
```

If you want the repo to keep advancing without manual phase-by-phase nudges, use the autonomous loop:

```bash
uv run python main.py --phase loop --wandb-mode disabled
```

That loop:
- rebuilds the dense corpus only when stale
- refreshes Phase 2
- accumulates manual + heuristic labels
- retrains only when the configured gate is reached
- writes [results/workflow_loop_report.json](C:\Users\satvi\Repos\builder-block-research\results\workflow_loop_report.json) with an explicit stop reason

## Retrain Threshold

Default policy:
- Prefer to accumulate at least `10` new dense reviewed labels since the last completed Phase 3 run before retraining.
- Prefer at least `50` train images and `15` val images before trusting detector quality.

If below those thresholds:
- keep labeling
- do not assume small mAP changes mean real progress

## What Phase 2 and Phase 3 Mean

- Phase 2 is the dataset compiler.
  - It rebuilds [dataset/yolo](C:\Users\satvi\Repos\builder-block-research\dataset\yolo) from the latest reviewed labels.
- Phase 3 trains on that exact Phase 2-exported snapshot.

If Phase 2 is not rerun after adding labels, Phase 3 will train on stale data.

## Audio

Audio is present in the corpus and helps prioritization:
- [knowledge/ttfm_video_corpus/audio_clips](C:\Users\satvi\Repos\builder-block-research\knowledge\ttfm_video_corpus\audio_clips)
- [knowledge/ttfm_video_corpus/audio_semantic_cache.json](C:\Users\satvi\Repos\builder-block-research\knowledge\ttfm_video_corpus\audio_semantic_cache.json)

Right now audio is not a direct YOLO input.
It is used indirectly through transcript and semantic context to help select better frames for review.

## Dense Corpus

Dense visual corpus artifacts:
- [knowledge/ttfm_video_corpus/dense_visual_windows.jsonl](C:\Users\satvi\Repos\builder-block-research\knowledge\ttfm_video_corpus\dense_visual_windows.jsonl)
- [knowledge/ttfm_video_corpus/dense_visual_windows_report.json](C:\Users\satvi\Repos\builder-block-research\knowledge\ttfm_video_corpus\dense_visual_windows_report.json)
- [knowledge/ttfm_video_corpus/dense_visual_embedding_manifest.json](C:\Users\satvi\Repos\builder-block-research\knowledge\ttfm_video_corpus\dense_visual_embedding_manifest.json)

Dense supervision artifacts:
- [results/phase2_dense_supervision_packet.json](C:\Users\satvi\Repos\builder-block-research\results\phase2_dense_supervision_packet.json)
- [results/phase2_dense_supervision_answers.example.json](C:\Users\satvi\Repos\builder-block-research\results\phase2_dense_supervision_answers.example.json)
- [results/phase2_dense_supervision_answers.json](C:\Users\satvi\Repos\builder-block-research\results\phase2_dense_supervision_answers.json)
- [results/phase2_dense_heuristic_promotions.json](C:\Users\satvi\Repos\builder-block-research\results\phase2_dense_heuristic_promotions.json)

Benchmark artifacts:
- [results/benchmark_manifest.json](C:\Users\satvi\Repos\builder-block-research\results\benchmark_manifest.json)
- [dataset/yolo_benchmark](C:\Users\satvi\Repos\builder-block-research\dataset\yolo_benchmark)

## Labeling Policy

Only label structures that are visibly defensible:
- order blocks
- breaker-style zones
- inversion FVGs
- liquidity sweeps
- protected swings
- swing highs/lows
- candle 3 closure zones

Skip:
- abstract slides
- generic candlestick teaching diagrams unless the box target is unambiguous
- charts where the highlighted area is not visually clear
- metadata-only dense rows that look like lesson intros instead of real chart examples

## Session Close

Before ending a session:
- rerun `uv run pytest -q`
- refresh [results/workflow_status.json](C:\Users\satvi\Repos\builder-block-research\results\workflow_status.json) if needed
- leave the next action obvious in the workflow report
