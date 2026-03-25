from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from phase_one_focus import build_phase_one_focus, split_training_labels

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CASE_PACKET_REPORT_PATH = ROOT / "results" / "ttfm_case_packets.json"
DEFAULT_FEEDBACK_QUEUE_PATH = ROOT / "data" / "ttfm_feedback_queue.json"
DEFAULT_TRAINING_LOOP_REPORT_PATH = ROOT / "results" / "ttfm_training_loop_report.json"
DEFAULT_NEURAL_REPORT_PATH = ROOT / "results" / "neural_net_readiness_report.json"
DEFAULT_BACKTESTING_REPORT_PATH = ROOT / "results" / "backtesting_readiness_report.json"
DEFAULT_TRADINGVIEW_REPORT_PATH = ROOT / "results" / "tradingview_pine_readiness_report.json"
DEFAULT_ITERATION_GRADING_REPORT_PATH = ROOT / "results" / "trading_iteration_grading_report.json"
DEFAULT_OUTPUT = ROOT / "results" / "trading_learning_improvement_plan.json"
DEFAULT_HISTORY_PATH = ROOT / "results" / "trading_learning_history.jsonl"

SEVERITY_ORDER = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
}

DELTA_KEYS = (
    "loop_score",
    "workflow_score",
    "validation_coverage",
    "screenshot_coverage",
    "anchor_coverage",
    "feedback_item_count",
    "rules_backtest_score",
    "model_backtest_score",
    "iteration_understanding_score",
    "graded_iteration_episode_count",
    "reinforcement_example_count",
    "retrained_task_count",
)


def load_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def safe_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def safe_int(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def active_extra_training_labels(neural_snapshot: dict) -> list[str]:
    label_space = neural_snapshot.get("label_space", {})
    labels = label_space.get("all_extra_training_labels_without_indicator_specs")
    if labels is None:
        labels = label_space.get("extra_training_labels_without_indicator_specs", [])
    active_labels, _ = split_training_labels(labels)
    return active_labels


def clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def format_target_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def select_run_generated_at(
    *,
    training_loop_report: dict,
    tradingview_report: dict,
    backtesting_report: dict,
    neural_report: dict,
    iteration_grading_report: dict,
) -> str:
    for payload in (
        training_loop_report,
        tradingview_report,
        backtesting_report,
        neural_report,
        iteration_grading_report,
    ):
        generated_at = str(payload.get("generated_at", "")).strip()
        if generated_at:
            return generated_at
    return datetime.now(timezone.utc).isoformat()


def load_history_entries(path: Path) -> list[dict]:
    if not path.exists():
        return []
    entries: list[dict] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        cleaned = raw_line.strip()
        if not cleaned:
            continue
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            entries.append(payload)
    return entries


def find_previous_history_entry(entries: list[dict], run_generated_at: str) -> dict | None:
    for entry in reversed(entries):
        if str(entry.get("run_generated_at", "")).strip() != run_generated_at:
            return entry
    return None


def build_current_metrics(
    *,
    case_packet_report: dict,
    feedback_queue: dict,
    training_loop_report: dict,
    neural_report: dict,
    backtesting_report: dict,
    tradingview_report: dict,
    iteration_grading_report: dict,
) -> dict[str, float | int]:
    case_summary = case_packet_report.get("summary", {})
    feedback_summary = feedback_queue.get("summary", {})
    training_metrics = training_loop_report.get("metrics", {})
    neural_snapshot = neural_report.get("snapshot", {})
    backtesting_stages = backtesting_report.get("stages", {})
    tradingview_summary = tradingview_report.get("summary", {})
    iteration_summary = iteration_grading_report.get("summary", {})

    return {
        "loop_score": round(safe_float(training_loop_report.get("loop_score")), 4),
        "workflow_score": round(safe_float(tradingview_summary.get("workflow_score")), 4),
        "validation_coverage": round(safe_float(tradingview_summary.get("validation_coverage")), 4),
        "screenshot_coverage": round(safe_float(case_summary.get("screenshot_coverage")), 4),
        "anchor_coverage": round(safe_float(case_summary.get("anchor_coverage")), 4),
        "feedback_item_count": safe_int(feedback_summary.get("item_count")),
        "tradingview_failure_count": safe_int(feedback_summary.get("tradingview_failure_count")),
        "rules_backtest_score": round(
            safe_float(
                backtesting_stages.get("rules_based_historical_backtesting", {}).get("score")
            ),
            4,
        ),
        "model_backtest_score": round(
            safe_float(
                backtesting_stages.get("model_assisted_historical_backtesting", {}).get("score")
            ),
            4,
        ),
        "ready_indicator_binary_count": safe_int(
            neural_snapshot.get("training_surface", {}).get("ready_indicator_binary_count")
        ),
        "non_draft_spec_count": safe_int(
            neural_snapshot.get("indicator_specs", {}).get("non_draft_status_count")
        ),
        "generated_script_count": safe_int(tradingview_summary.get("generated_script_count")),
        "validated_script_count": safe_int(tradingview_summary.get("validated_script_count")),
        "playwriter_validated_count": safe_int(
            tradingview_summary.get("playwriter_validated_count")
        ),
        "translatability_score": round(
            safe_float(training_metrics.get("tradingview_generated_script_coverage")), 4
        ),
        "iteration_understanding_score": round(
            safe_float(iteration_summary.get("average_understanding_score")),
            4,
        ),
        "iteration_trade_model_accuracy": round(
            safe_float(iteration_summary.get("trade_model_accuracy")),
            4,
        ),
        "iteration_relation_type_accuracy": round(
            safe_float(iteration_summary.get("relation_type_accuracy")),
            4,
        ),
        "graded_iteration_episode_count": safe_int(
            iteration_summary.get("graded_episode_count")
        ),
        "reinforcement_example_count": safe_int(
            neural_snapshot.get("training_surface", {}).get("reinforcement_example_count")
        ),
        "retrained_task_count": safe_int(
            neural_snapshot.get("iteration_retraining", {}).get("trained_task_count")
        ),
    }


def build_delta(previous_metrics: dict, current_metrics: dict) -> dict[str, float] | None:
    if not previous_metrics:
        return None

    delta: dict[str, float] = {}
    for key in DELTA_KEYS:
        if key not in current_metrics or key not in previous_metrics:
            continue
        delta[key] = round(
            safe_float(current_metrics.get(key)) - safe_float(previous_metrics.get(key)),
            4,
        )
    return delta


def build_progress_signals(delta: dict[str, float] | None) -> tuple[list[str], list[str]]:
    if not delta:
        return (["No prior loop history exists; this run establishes the baseline."], [])

    progress: list[str] = []
    regressions: list[str] = []

    if delta.get("loop_score", 0.0) > 0.01:
        progress.append(f"Loop score improved by {delta['loop_score']:+.4f}.")
    elif delta.get("loop_score", 0.0) < -0.01:
        regressions.append(f"Loop score regressed by {delta['loop_score']:+.4f}.")

    if delta.get("workflow_score", 0.0) > 0.01:
        progress.append(f"TradingView workflow score improved by {delta['workflow_score']:+.4f}.")
    elif delta.get("workflow_score", 0.0) < -0.01:
        regressions.append(
            f"TradingView workflow score regressed by {delta['workflow_score']:+.4f}."
        )

    if delta.get("validation_coverage", 0.0) > 0.0:
        progress.append(
            f"TradingView validation coverage improved by {delta['validation_coverage']:+.4f}."
        )
    elif delta.get("validation_coverage", 0.0) < 0.0:
        regressions.append(
            f"TradingView validation coverage regressed by {delta['validation_coverage']:+.4f}."
        )

    if delta.get("feedback_item_count", 0.0) < 0.0:
        progress.append(
            f"Feedback queue shrank by {abs(delta['feedback_item_count']):.0f} item(s)."
        )
    elif delta.get("feedback_item_count", 0.0) > 0.0:
        regressions.append(
            f"Feedback queue grew by {delta['feedback_item_count']:.0f} item(s)."
        )

    if delta.get("screenshot_coverage", 0.0) > 0.01:
        progress.append(
            f"Screenshot coverage improved by {delta['screenshot_coverage']:+.4f}."
        )
    if delta.get("anchor_coverage", 0.0) > 0.01:
        progress.append(f"Anchor coverage improved by {delta['anchor_coverage']:+.4f}.")
    if delta.get("iteration_understanding_score", 0.0) > 0.01:
        progress.append(
            f"Iteration understanding score improved by {delta['iteration_understanding_score']:+.4f}."
        )
    elif delta.get("iteration_understanding_score", 0.0) < -0.01:
        regressions.append(
            "Iteration understanding score regressed by "
            f"{delta['iteration_understanding_score']:+.4f}."
        )
    if delta.get("graded_iteration_episode_count", 0.0) > 0.0:
        progress.append(
            f"Graded iteration coverage grew by {delta['graded_iteration_episode_count']:.0f} episode(s)."
        )
    if delta.get("reinforcement_example_count", 0.0) > 0.0:
        progress.append(
            f"Reinforcement surface grew by {delta['reinforcement_example_count']:.0f} example(s)."
        )
    if delta.get("retrained_task_count", 0.0) > 0.0:
        progress.append(
            f"Retrained challenger coverage grew by {delta['retrained_task_count']:.0f} task(s)."
        )

    if not progress and not regressions:
        progress.append("No major loop-level metric changed versus the previous recorded run.")

    return progress, regressions


def determine_phase(
    *,
    current_metrics: dict,
    case_packet_report: dict,
    feedback_queue: dict,
    backtesting_report: dict,
) -> tuple[str, str, str]:
    case_summary = case_packet_report.get("summary", {})
    feedback_summary = feedback_queue.get("summary", {})
    rules_backtest_stage = backtesting_report.get("stages", {}).get(
        "rules_based_historical_backtesting",
        {},
    )

    if (
        safe_float(current_metrics.get("validation_coverage")) == 0.0
        and safe_int(feedback_summary.get("workflow_feedback_count")) > 0
    ):
        return (
            "blocked_translation",
            "blocked",
            "The loop can generate Pine drafts, but TradingView validation is blocked and the current run is not yet learning from editor-confirmed scripts.",
        )

    if (
        safe_float(case_summary.get("screenshot_coverage")) < 0.5
        or safe_float(case_summary.get("anchor_coverage")) < 0.5
    ):
        return (
            "evidence_bootstrap",
            "bootstrapping",
            "The loop has durable cases, but screenshot and anchor coverage are still too thin to support strong self-correction.",
        )

    if not bool(rules_backtest_stage.get("ready")):
        return (
            "historical_harness",
            "building",
            "The loop understands the system historically, but it still needs a repeatable replay/backtest harness to turn that understanding into structured learning.",
        )

    return (
        "advancing",
        "improving",
        "The loop has cleared the current bottleneck set and can continue tightening validation and historical evaluation depth.",
    )


def build_bottlenecks(
    *,
    current_metrics: dict,
    feedback_queue: dict,
    neural_report: dict,
    backtesting_report: dict,
) -> list[dict]:
    items: list[dict] = []
    neural_snapshot = neural_report.get("snapshot", {})
    feedback_items = list(feedback_queue.get("items", []))
    backtesting_snapshot = backtesting_report.get("snapshot", {})
    backtesting_stages = backtesting_report.get("stages", {})

    if safe_float(current_metrics.get("validation_coverage")) == 0.0:
        items.append(
            {
                "id": "no_tradingview_validation",
                "severity": "critical",
                "signal": 1.0,
                "summary": "No spec-generated Pine draft has been validated in TradingView yet.",
                "evidence": [
                    item.get("title")
                    for item in feedback_items
                    if item.get("target_type") == "finding"
                ][:2],
            }
        )

    if safe_float(current_metrics.get("screenshot_coverage")) < 0.5:
        items.append(
            {
                "id": "low_screenshot_coverage",
                "severity": "high",
                "signal": round(1.0 - safe_float(current_metrics.get("screenshot_coverage")), 4),
                "summary": "Historical case packets are missing screenshot evidence.",
                "evidence": [
                    f"screenshot_coverage={safe_float(current_metrics.get('screenshot_coverage')):.4f}"
                ],
            }
        )

    if safe_float(current_metrics.get("anchor_coverage")) < 0.5:
        items.append(
            {
                "id": "low_anchor_coverage",
                "severity": "high",
                "signal": round(1.0 - safe_float(current_metrics.get("anchor_coverage")), 4),
                "summary": "Anchor labels are too sparse for strong disagreement-driven learning.",
                "evidence": [
                    f"anchor_coverage={safe_float(current_metrics.get('anchor_coverage')):.4f}"
                ],
            }
        )

    if safe_float(backtesting_snapshot.get("historical_harness", {}).get("harness_score")) == 0.0:
        items.append(
            {
                "id": "missing_historical_harness",
                "severity": "critical",
                "signal": 1.0,
                "summary": "There is no repeatable historical replay/backtest harness in the repo.",
                "evidence": backtesting_stages.get("rules_based_historical_backtesting", {}).get(
                    "blockers",
                    [],
                )[:2],
            }
        )

    if (
        safe_float(backtesting_snapshot.get("backtesting_specs", {}).get("cost_model_average"))
        == 0.0
    ):
        items.append(
            {
                "id": "missing_transaction_cost_model",
                "severity": "high",
                "signal": 1.0,
                "summary": "Backtesting specs do not encode spread, slippage, commission, or fees yet.",
                "evidence": ["cost_model_average=0.0"],
            }
        )

    if safe_int(neural_snapshot.get("indicator_specs", {}).get("non_draft_status_count")) == 0:
        items.append(
            {
                "id": "draft_only_specs",
                "severity": "high",
                "signal": 1.0,
                "summary": "All indicator specs are still in `draft`, so translation maturity is capped.",
                "evidence": ["non_draft_status_count=0"],
            }
        )

    if safe_int(neural_snapshot.get("training_surface", {}).get("ready_indicator_binary_count")) < 2:
        items.append(
            {
                "id": "narrow_label_surface",
                "severity": "medium",
                "signal": round(
                    1.0
                    - clamp(
                        safe_float(
                            neural_snapshot.get("training_surface", {}).get(
                                "ready_indicator_binary_coverage"
                            )
                        )
                    ),
                    4,
                ),
                "summary": "Only one indicator-ready trade model is ready for narrow binary learning.",
                "evidence": [
                    f"ready_indicator_binary_count={safe_int(neural_snapshot.get('training_surface', {}).get('ready_indicator_binary_count'))}"
                ],
            }
        )

    extra_labels = active_extra_training_labels(neural_snapshot)
    if extra_labels:
        items.append(
            {
                "id": "out_of_set_training_labels",
                "severity": "medium",
                "signal": 1.0,
                "summary": "The training label surface still includes models outside the indicator-spec set.",
                "evidence": list(extra_labels),
            }
        )

    items.sort(key=lambda item: (SEVERITY_ORDER[item["severity"]], -safe_float(item["signal"])))
    return items


def build_priority_actions(
    *,
    phase: str,
    current_metrics: dict,
    case_packet_report: dict,
    feedback_queue: dict,
    neural_report: dict,
    backtesting_report: dict,
    tradingview_report: dict,
) -> list[dict]:
    actions: list[dict] = []
    feedback_items = list(feedback_queue.get("items", []))
    neural_snapshot = neural_report.get("snapshot", {})
    backtesting_snapshot = backtesting_report.get("snapshot", {})
    backtesting_next_actions = list(backtesting_report.get("next_actions", []))
    tradingview_summary = tradingview_report.get("summary", {})
    case_summary = case_packet_report.get("summary", {})

    if safe_float(current_metrics.get("validation_coverage")) == 0.0:
        top_finding = next(
            (
                item
                for item in feedback_items
                if item.get("target_type") == "finding"
            ),
            {},
        )
        focus_spec = None
        finding_id = str(top_finding.get("id", "")).strip()
        if finding_id.startswith("tradingview::"):
            finding_parts = finding_id.split("::")
            if len(finding_parts) >= 3:
                focus_spec = finding_parts[1]
        if not focus_spec:
            focus_spec = (
                tradingview_summary.get("pending_spec_keys", [None])[0]
                if tradingview_summary.get("pending_spec_keys")
                else None
            )
        actions.append(
            {
                "id": "validate_first_pine_draft",
                "priority": 1,
                "lane": "tradingview_validation",
                "title": "Fix the TradingView editor sync path and validate the first spec-generated Pine draft.",
                "why_now": str(top_finding.get("body", "")).strip()
                or "No generated Pine draft has been validated in TradingView yet.",
                "success_metric": "validated_script_count >= 1 and playwriter_validated_count >= 1",
                "artifacts": [
                    "knowledge/tradingview_pine_workflow.md",
                    "data/tradingview_pine_validation.json",
                    f"results/pine_scripts/{focus_spec}.pine" if focus_spec else "results/pine_scripts/",
                ],
            }
        )

    if (
        safe_float(case_summary.get("screenshot_coverage")) < 0.5
        or safe_float(case_summary.get("anchor_coverage")) < 0.5
    ):
        actions.append(
            {
                "id": "bootstrap_visual_evidence",
                "priority": len(actions) + 1,
                "lane": "visual_grounding",
                "title": "Bootstrap screenshot and anchor coverage for the historical case packets.",
                "why_now": (
                    f"screenshot_coverage={safe_float(case_summary.get('screenshot_coverage')):.4f}, "
                    f"anchor_coverage={safe_float(case_summary.get('anchor_coverage')):.4f}"
                ),
                "success_metric": "screenshot_coverage > 0.50 and anchor_coverage > 0.50",
                "artifacts": [
                    "data/ttfm_screenshot_manifest.json",
                    "data/ttfm_anchor_labels.json",
                    "results/ttfm_case_packets.json",
                ],
                "command_hint": "python scripts/run_trading_learning_loop.py --bootstrap-screenshots",
            }
        )

    if safe_int(current_metrics.get("graded_iteration_episode_count")) == 0:
        actions.append(
            {
                "id": "record_first_iteration_episodes",
                "priority": len(actions) + 1,
                "lane": "learning_progress",
                "title": "Start recording graded TTrades iteration episodes.",
                "why_now": "The loop has no graded learning episodes yet, so pattern-recognition progress cannot be tracked over time.",
                "success_metric": "graded_iteration_episode_count >= 3",
                "artifacts": [
                    "data/trading_iteration_episodes.json",
                    "results/trading_iteration_grading_report.json",
                ],
            }
        )
    elif safe_float(current_metrics.get("iteration_understanding_score")) < 0.7:
        actions.append(
            {
                "id": "improve_iteration_understanding",
                "priority": len(actions) + 1,
                "lane": "learning_progress",
                "title": "Improve checkpoint-level TTrades understanding on graded episodes.",
                "why_now": (
                    "Current graded understanding score is "
                    f"{safe_float(current_metrics.get('iteration_understanding_score')):.4f}, "
                    "which is still below reliable pattern-recognition quality."
                ),
                "success_metric": "iteration_understanding_score >= 0.70",
                "artifacts": [
                    "results/trading_iteration_grading_report.json",
                    "results/trading_learning_improvement_plan.json",
                ],
            }
        )

    if safe_float(backtesting_snapshot.get("historical_harness", {}).get("harness_score")) == 0.0:
        actions.append(
            {
                "id": "build_historical_harness",
                "priority": len(actions) + 1,
                "lane": "historical_backtesting",
                "title": "Add the minimal historical replay/backtest harness.",
                "why_now": backtesting_next_actions[1]
                if len(backtesting_next_actions) > 1
                else "The repo cannot turn rules into repeatable historical learning until a harness exists.",
                "success_metric": "historical_harness.harness_score > 0.0",
                "artifacts": [
                    "results/backtesting_readiness_report.json",
                    "runtime/harness.py",
                    "scripts/backtest_analyzer.py",
                ],
            }
        )

    if safe_float(backtesting_snapshot.get("backtesting_specs", {}).get("cost_model_average")) == 0.0:
        actions.append(
            {
                "id": "encode_transaction_costs",
                "priority": len(actions) + 1,
                "lane": "historical_backtesting",
                "title": "Encode spread, slippage, and commission assumptions in the backtest contracts.",
                "why_now": "Rules-based historical backtesting is capped until transaction costs are explicit.",
                "success_metric": "backtesting_specs.cost_model_average > 0.0",
                "artifacts": [
                    "results/backtesting_readiness_report.json",
                    "results/indicator_specs/",
                ],
            }
        )

    if safe_int(neural_snapshot.get("iteration_retraining", {}).get("trained_task_count")) > 0:
        challenger_snapshot = neural_snapshot.get("iteration_challengers", {})
        promotion_snapshot = neural_snapshot.get("iteration_promotions", {})
        trained_task_names = ", ".join(
            neural_snapshot.get("iteration_retraining", {}).get("trained_task_names", [])
        )
        compared_task_count = safe_int(challenger_snapshot.get("compared_task_count"))
        trained_task_count = safe_int(
            neural_snapshot.get("iteration_retraining", {}).get("trained_task_count")
        )
        promoted_tasks = list(promotion_snapshot.get("promoted_tasks", []))
        pending_promotion_reviews = [
            task
            for task in challenger_snapshot.get("promotion_candidate_tasks", [])
            if task not in set(promoted_tasks)
        ]
        if trained_task_count > compared_task_count:
            actions.append(
                {
                    "id": "benchmark_retrained_challengers",
                    "priority": len(actions) + 1,
                    "lane": "model_evaluation",
                    "title": "Benchmark the latest iteration-retrained challengers before promoting them.",
                    "why_now": trained_task_names
                    or "Fresh retrained challengers are available and need offline comparison before any promotion.",
                    "success_metric": "compared_task_count >= retrained_task_count",
                    "artifacts": [
                        "results/iteration_retraining_report.json",
                        "results/iteration_challenger_report.json",
                        "results/neural_models/iteration_retrained/",
                    ],
                }
            )
        elif promoted_tasks:
            actions.append(
                {
                    "id": "monitor_promoted_champions",
                    "priority": len(actions) + 1,
                    "lane": "model_evaluation",
                    "title": "Track the newly promoted champions through the next reinforcement cycle.",
                    "why_now": ", ".join(promoted_tasks)
                    or "A challenger was promoted into the champion slot and now needs follow-through monitoring.",
                    "success_metric": "The next challenger benchmark still confirms the promoted model as the leader.",
                    "artifacts": [
                        "results/iteration_promotion_report.json",
                        "results/iteration_challenger_report.json",
                        "results/neural_models/",
                    ],
                }
            )
        elif pending_promotion_reviews:
            actions.append(
                {
                    "id": "review_promotable_challengers",
                    "priority": len(actions) + 1,
                    "lane": "model_evaluation",
                    "title": "Review the winning challenger benchmarks for possible promotion.",
                    "why_now": ", ".join(pending_promotion_reviews)
                    or "At least one challenger outperformed the current champion on the reinforced surface benchmark.",
                    "success_metric": "A promotion decision is recorded for each winning challenger.",
                    "artifacts": [
                        "results/iteration_challenger_report.json",
                        "results/iteration_retraining_report.json",
                        "results/neural_models/iteration_retrained/",
                    ],
                }
            )

    positive_gaps = [
        task
        for task in neural_snapshot.get("training_surface", {}).get("trade_model_binary_tasks", [])
        if task.get("trade_model") in neural_snapshot.get("indicator_ready_trade_models", [])
        and not task.get("ready")
    ]
    if positive_gaps:
        prioritized = ", ".join(
            f"{task['trade_model']} (+{task['additional_positive_examples_needed']})"
            for task in positive_gaps
        )
        actions.append(
            {
                "id": "expand_positive_examples",
                "priority": len(actions) + 1,
                "lane": "label_growth",
                "title": "Collect the next positive labeled cases for the indicator-ready models that are still short.",
                "why_now": prioritized,
                "success_metric": "ready_indicator_binary_count >= 2",
                "artifacts": [
                    "data/trader_annotation_cases.json",
                    "results/neural_net_readiness_report.json",
                ],
            }
        )

    if safe_int(neural_snapshot.get("indicator_specs", {}).get("non_draft_status_count")) == 0:
        actions.append(
            {
                "id": "graduate_first_specs",
                "priority": len(actions) + 1,
                "lane": "spec_quality",
                "title": "Graduate at least one Pine-target spec beyond `draft`.",
                "why_now": "Draft-only specs cap both Pine validation credibility and historical backtesting readiness.",
                "success_metric": "non_draft_spec_count >= 1",
                "artifacts": [
                    "results/indicator_specs/",
                    "results/neural_net_readiness_report.json",
                    "results/backtesting_readiness_report.json",
                ],
            }
        )

    extra_labels = active_extra_training_labels(neural_snapshot)
    if extra_labels:
        actions.append(
            {
                "id": "resolve_out_of_set_labels",
                "priority": len(actions) + 1,
                "lane": "label_surface",
                "title": "Resolve the remaining training labels that sit outside the indicator-spec set.",
                "why_now": ", ".join(extra_labels),
                "success_metric": "extra_training_labels_without_indicator_specs == []",
                "artifacts": [
                    "results/neural_net_readiness_report.json",
                    "data/trader_annotation_cases.json",
                ],
            }
        )

    if phase == "advancing" and not actions:
        actions.append(
            {
                "id": "maintain_loop",
                "priority": 1,
                "lane": "maintenance",
                "title": "Keep the learning loop on its current trajectory and extend the next narrow benchmark.",
                "why_now": "No blocking gaps were detected in the current run.",
                "success_metric": "loop_score improves on the next recorded run",
                "artifacts": [format_target_path(DEFAULT_OUTPUT)],
            }
        )

    return actions[:6]


def build_history_entry(
    *,
    current_run: dict,
    phase: str,
    status: str,
    priority_actions: list[dict],
) -> dict:
    return {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "run_generated_at": current_run.get("generated_at"),
        "phase": phase,
        "status": status,
        "metrics": current_run.get("metrics", {}),
        "top_action_ids": [action.get("id") for action in priority_actions[:3]],
    }


def write_history_entry(path: Path, entry: dict) -> int:
    entries = load_history_entries(path)
    if entries and str(entries[-1].get("run_generated_at", "")).strip() == str(
        entry.get("run_generated_at", "")
    ).strip():
        entries[-1] = entry
    else:
        entries.append(entry)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(item, sort_keys=True) for item in entries) + "\n",
        encoding="utf-8",
    )
    return len(entries)


def build_improvement_plan(
    *,
    run_generated_at: str,
    case_packet_report: dict,
    feedback_queue: dict,
    training_loop_report: dict,
    neural_report: dict,
    backtesting_report: dict,
    tradingview_report: dict,
    iteration_grading_report: dict,
    previous_entry: dict | None = None,
) -> dict:
    neural_snapshot = neural_report.get("snapshot", {})
    phase_one_focus = neural_report.get("phase_one_focus") or build_phase_one_focus(
        neural_snapshot.get("training_surface", {}),
        indicator_ready_trade_models=neural_snapshot.get("indicator_ready_trade_models", []),
    )
    current_run = {
        "generated_at": run_generated_at,
        "metrics": build_current_metrics(
            case_packet_report=case_packet_report,
            feedback_queue=feedback_queue,
            training_loop_report=training_loop_report,
            neural_report=neural_report,
            backtesting_report=backtesting_report,
            tradingview_report=tradingview_report,
            iteration_grading_report=iteration_grading_report,
        ),
        "training_loop_grade": training_loop_report.get("grade"),
        "training_loop_verdict": training_loop_report.get("verdict"),
        "feedback_summary": feedback_queue.get("summary", {}),
        "pending_spec_keys": list(tradingview_report.get("summary", {}).get("pending_spec_keys", [])),
        "phase_one_focus": phase_one_focus,
    }

    previous_metrics = (previous_entry or {}).get("metrics", {})
    delta = build_delta(previous_metrics, current_run["metrics"])
    progress_signals, regression_signals = build_progress_signals(delta)
    phase, status, phase_summary = determine_phase(
        current_metrics=current_run["metrics"],
        case_packet_report=case_packet_report,
        feedback_queue=feedback_queue,
        backtesting_report=backtesting_report,
    )

    bottlenecks = build_bottlenecks(
        current_metrics=current_run["metrics"],
        feedback_queue=feedback_queue,
        neural_report=neural_report,
        backtesting_report=backtesting_report,
    )
    priority_actions = build_priority_actions(
        phase=phase,
        current_metrics=current_run["metrics"],
        case_packet_report=case_packet_report,
        feedback_queue=feedback_queue,
        neural_report=neural_report,
        backtesting_report=backtesting_report,
        tradingview_report=tradingview_report,
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "phase": phase,
        "status": status,
        "phase_summary": phase_summary,
        "current_run": current_run,
        "previous_run": previous_entry,
        "delta": delta,
        "progress_signals": progress_signals,
        "regression_signals": regression_signals,
        "bottlenecks": bottlenecks,
        "priority_actions": priority_actions,
        "phase_one_focus": phase_one_focus,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export a self-improvement plan for the trading learning loop and persist run history."
    )
    parser.add_argument("--case-packets", default=str(DEFAULT_CASE_PACKET_REPORT_PATH))
    parser.add_argument("--feedback-queue", default=str(DEFAULT_FEEDBACK_QUEUE_PATH))
    parser.add_argument("--training-loop-report", default=str(DEFAULT_TRAINING_LOOP_REPORT_PATH))
    parser.add_argument("--neural-report", default=str(DEFAULT_NEURAL_REPORT_PATH))
    parser.add_argument("--backtesting-report", default=str(DEFAULT_BACKTESTING_REPORT_PATH))
    parser.add_argument("--tradingview-report", default=str(DEFAULT_TRADINGVIEW_REPORT_PATH))
    parser.add_argument("--iteration-grading-report", default=str(DEFAULT_ITERATION_GRADING_REPORT_PATH))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--history-output", default=str(DEFAULT_HISTORY_PATH))
    args = parser.parse_args()

    history_path = Path(args.history_output)
    history_entries = load_history_entries(history_path)
    training_loop_report = load_json(Path(args.training_loop_report), {})
    neural_report = load_json(Path(args.neural_report), {})
    backtesting_report = load_json(Path(args.backtesting_report), {})
    tradingview_report = load_json(Path(args.tradingview_report), {"summary": {}})
    iteration_grading_report = load_json(Path(args.iteration_grading_report), {"summary": {}})
    run_generated_at = select_run_generated_at(
        training_loop_report=training_loop_report,
        tradingview_report=tradingview_report,
        backtesting_report=backtesting_report,
        neural_report=neural_report,
        iteration_grading_report=iteration_grading_report,
    )
    previous_entry = find_previous_history_entry(history_entries, run_generated_at)

    plan = build_improvement_plan(
        run_generated_at=run_generated_at,
        case_packet_report=load_json(Path(args.case_packets), {"summary": {}}),
        feedback_queue=load_json(Path(args.feedback_queue), {"summary": {}, "items": []}),
        training_loop_report=training_loop_report,
        neural_report=neural_report,
        backtesting_report=backtesting_report,
        tradingview_report=tradingview_report,
        iteration_grading_report=iteration_grading_report,
        previous_entry=previous_entry,
    )

    history_entry = build_history_entry(
        current_run=plan["current_run"],
        phase=plan["phase"],
        status=plan["status"],
        priority_actions=plan["priority_actions"],
    )
    history_count = write_history_entry(history_path, history_entry)

    plan["history"] = {
        "path": format_target_path(history_path),
        "entry_count": history_count,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output_path),
                "phase": plan["phase"],
                "priority_action_count": len(plan["priority_actions"]),
                "history_entry_count": history_count,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
