from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from phase_one_focus import build_phase_one_focus


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "results" / "trading_learning_loop_summary.json"

CASE_PACKET_REPORT_PATH = ROOT / "results" / "ttfm_case_packets.json"
PINE_VERIFICATION_REPORT_PATH = ROOT / "results" / "ttfm_pine_verification_report.json"
TRADINGVIEW_PINE_REPORT_PATH = ROOT / "results" / "tradingview_pine_readiness_report.json"
FEEDBACK_QUEUE_PATH = ROOT / "data" / "ttfm_feedback_queue.json"
TRAINING_LOOP_REPORT_PATH = ROOT / "results" / "ttfm_training_loop_report.json"
NEURAL_REPORT_PATH = ROOT / "results" / "neural_net_readiness_report.json"
BACKTESTING_REPORT_PATH = ROOT / "results" / "backtesting_readiness_report.json"
IMPROVEMENT_PLAN_PATH = ROOT / "results" / "trading_learning_improvement_plan.json"
ITERATION_GRADING_REPORT_PATH = ROOT / "results" / "trading_iteration_grading_report.json"
REINFORCED_TRAINING_REPORT_PATH = ROOT / "results" / "reinforced_model_training_report.json"
ITERATION_RETRAINING_REPORT_PATH = ROOT / "results" / "iteration_retraining_report.json"
ITERATION_CHALLENGER_REPORT_PATH = ROOT / "results" / "iteration_challenger_report.json"
ITERATION_PROMOTION_REPORT_PATH = ROOT / "results" / "iteration_promotion_report.json"
TRADING_LEARNING_DASHBOARD_PATH = ROOT / "results" / "trading_learning_dashboard.html"


def load_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def build_loop_steps(
    python_executable: str,
    *,
    bootstrap_screenshots: bool = False,
    apply_safe_feedback: bool = False,
) -> list[dict]:
    steps = [
        {
            "id": "import_trader_annotation_cases",
            "cmd": [python_executable, "scripts/import_trader_annotation_cases.py"],
        },
        {
            "id": "export_ttfm_case_packets",
            "cmd": [python_executable, "scripts/export_ttfm_case_packets.py"],
        },
    ]

    if bootstrap_screenshots:
        steps.extend(
            [
                {
                    "id": "bootstrap_ttfm_screenshot_manifest",
                    "cmd": [python_executable, "scripts/bootstrap_ttfm_screenshot_manifest.py"],
                },
                {
                    "id": "export_ttfm_case_packets_after_screenshot_bootstrap",
                    "cmd": [python_executable, "scripts/export_ttfm_case_packets.py"],
                },
            ]
        )

    steps.extend(
        [
            {
                "id": "export_ttfm_pine_verification_queue",
                "cmd": [python_executable, "scripts/export_ttfm_pine_verification_queue.py"],
            },
            {
                "id": "export_ttfm_pine_verification_report",
                "cmd": [python_executable, "scripts/export_ttfm_pine_verification_report.py"],
            },
            {
                "id": "generate_pine_from_spec",
                "cmd": [python_executable, "scripts/generate_pine_from_spec.py"],
            },
            {
                "id": "export_tradingview_pine_readiness_report",
                "cmd": [python_executable, "scripts/export_tradingview_pine_readiness_report.py"],
            },
            {
                "id": "export_ttfm_feedback_queue",
                "cmd": [python_executable, "scripts/export_ttfm_feedback_queue.py"],
            },
        ]
    )

    if apply_safe_feedback:
        steps.append(
            {
                "id": "apply_ttfm_feedback",
                "cmd": [python_executable, "scripts/apply_ttfm_feedback.py"],
            }
        )

    steps.extend(
        [
            {
                "id": "export_ttfm_training_loop_report",
                "cmd": [python_executable, "scripts/export_ttfm_training_loop_report.py"],
            },
            {
                "id": "export_trading_iteration_grading_report",
                "cmd": [python_executable, "scripts/export_trading_iteration_grading_report.py"],
            },
            {
                "id": "export_reinforced_training_surface",
                "cmd": [python_executable, "scripts/export_reinforced_training_surface.py"],
            },
            {
                "id": "run_iteration_retraining",
                "cmd": [python_executable, "scripts/run_iteration_retraining.py"],
            },
            {
                "id": "export_iteration_challenger_report",
                "cmd": [python_executable, "scripts/export_iteration_challenger_report.py"],
            },
            {
                "id": "promote_iteration_challengers",
                "cmd": [python_executable, "scripts/promote_iteration_challengers.py"],
            },
            {
                "id": "export_neural_net_readiness_report",
                "cmd": [python_executable, "scripts/export_neural_net_readiness_report.py"],
            },
            {
                "id": "export_backtesting_readiness_report",
                "cmd": [python_executable, "scripts/export_backtesting_readiness_report.py"],
            },
            {
                "id": "export_trading_learning_improvement_plan",
                "cmd": [python_executable, "scripts/export_trading_learning_improvement_plan.py"],
            },
        ]
    )
    return steps


def parse_step_stdout(stdout: str) -> dict:
    cleaned = stdout.strip()
    if not cleaned:
        return {}
    try:
        payload = json.loads(cleaned)
        return payload if isinstance(payload, dict) else {"value": payload}
    except json.JSONDecodeError:
        return {"stdout": cleaned}


def run_step(step: dict) -> dict:
    completed = subprocess.run(
        step["cmd"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return {
        "id": step["id"],
        "cmd": step["cmd"],
        "result": parse_step_stdout(completed.stdout),
    }


def build_loop_summary(
    *,
    bootstrap_screenshots: bool,
    apply_safe_feedback: bool,
    step_results: list[dict],
    case_packet_report: dict,
    pine_verification_report: dict,
    tradingview_pine_report: dict,
    feedback_queue: dict,
    training_loop_report: dict,
    neural_report: dict,
    backtesting_report: dict,
    iteration_grading_report: dict,
    reinforced_training_report: dict,
    iteration_retraining_report: dict,
    iteration_challenger_report: dict,
    iteration_promotion_report: dict,
    improvement_plan_report: dict,
) -> dict:
    case_summary = case_packet_report.get("summary", {})
    pine_summary = pine_verification_report.get("summary", {})
    tradingview_summary = tradingview_pine_report.get("summary", {})
    feedback_summary = feedback_queue.get("summary", {})
    training_summary = {
        "loop_score": training_loop_report.get("loop_score"),
        "grade": training_loop_report.get("grade"),
        "verdict": training_loop_report.get("verdict"),
        "warnings": training_loop_report.get("warnings", []),
    }
    iteration_summary = iteration_grading_report.get("summary", {})
    reinforced_summary = reinforced_training_report.get("summary", {})
    challenger_summary = iteration_challenger_report.get("summary", {})
    promotion_summary = iteration_promotion_report.get("summary", {})
    stages = neural_report.get("stages", {})
    neural_summary = {
        "autoresearch_grade": stages.get("karpathy_style_autoresearch_loop", {}).get("grade"),
        "offline_ml_grade": stages.get("offline_narrow_ml", {}).get("grade"),
        "real_time_assist_grade": stages.get("real_time_neural_assist", {}).get("grade"),
        "real_time_execution_grade": stages.get("real_time_neural_execution", {}).get("grade"),
        "global_blockers": neural_report.get("global_blockers", []),
        "next_actions": neural_report.get("next_actions", []),
    }
    phase_one_focus = neural_report.get("phase_one_focus") or build_phase_one_focus(
        neural_report.get("snapshot", {}).get("training_surface", {}),
        indicator_ready_trade_models=neural_report.get("snapshot", {}).get(
            "indicator_ready_trade_models",
            [],
        ),
    )

    backtesting_stage_summaries: dict[str, dict] = {}
    for key, value in backtesting_report.get("stages", {}).items():
        if isinstance(value, dict):
            backtesting_stage_summaries[key] = {
                "grade": value.get("grade"),
                "ready": value.get("ready"),
                "verdict": value.get("verdict"),
            }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "bootstrap_screenshots": bootstrap_screenshots,
        "apply_safe_feedback": apply_safe_feedback,
        "step_count": len(step_results),
        "steps": step_results,
        "case_packets": {
            "case_count": case_summary.get("case_count", 0),
            "checkpoint_count": case_summary.get("checkpoint_count", 0),
            "screenshot_coverage": case_summary.get("screenshot_coverage", 0.0),
            "anchor_coverage": case_summary.get("anchor_coverage", 0.0),
            "missing_screenshot_count": case_summary.get("missing_screenshot_count", 0),
            "missing_anchor_label_count": case_summary.get("missing_anchor_label_count", 0),
        },
        "pine_verification": {
            "queue_item_count": pine_summary.get("queue_item_count", 0),
            "attempted_item_count": pine_summary.get("attempted_item_count", 0),
            "translatability_score": pine_summary.get("translatability_score", 0.0),
            "feedback_candidate_count": pine_summary.get("feedback_candidate_count", 0),
        },
        "tradingview_pine": {
            "generated_script_count": tradingview_summary.get("generated_script_count", 0),
            "validated_script_count": tradingview_summary.get("validated_script_count", 0),
            "playwriter_validated_count": tradingview_summary.get("playwriter_validated_count", 0),
            "workflow_score": tradingview_summary.get("workflow_score", 0.0),
            "validation_coverage": tradingview_summary.get("validation_coverage", 0.0),
            "pending_spec_keys": tradingview_summary.get("pending_spec_keys", []),
        },
        "feedback_queue": {
            "item_count": feedback_summary.get("item_count", 0),
            "tradingview_failure_count": feedback_summary.get("tradingview_failure_count", 0),
            "workflow_feedback_count": feedback_summary.get("workflow_feedback_count", 0),
            "spec_feedback_count": feedback_summary.get("spec_feedback_count", 0),
        },
        "training_loop": training_summary,
        "iteration_learning": {
            "episode_count": iteration_summary.get("episode_count", 0),
            "graded_episode_count": iteration_summary.get("graded_episode_count", 0),
            "average_understanding_score": iteration_summary.get(
                "average_understanding_score",
                0.0,
            ),
            "trade_model_accuracy": iteration_summary.get("trade_model_accuracy", 0.0),
            "relation_type_accuracy": iteration_summary.get("relation_type_accuracy", 0.0),
            "checkpoint_component_score": iteration_summary.get("checkpoint_component_score", 0.0),
            "latest_understanding_score": iteration_summary.get("latest_understanding_score", 0.0),
            "grade": iteration_summary.get("grade"),
        },
        "iteration_retraining": {
            "base_example_count": reinforced_summary.get("base_example_count", 0),
            "reinforcement_example_count": reinforced_summary.get("reinforcement_example_count", 0),
            "merged_example_count": reinforced_summary.get("merged_example_count", 0),
            "graded_episode_count": reinforced_summary.get("graded_episode_count", 0),
            "trained_task_count": iteration_retraining_report.get("trained_task_count", 0),
            "trained_task_names": iteration_retraining_report.get("trained_task_names", []),
        },
        "iteration_challengers": {
            "compared_task_count": challenger_summary.get("compared_task_count", 0),
            "challenger_win_count": challenger_summary.get("challenger_win_count", 0),
            "champion_win_count": challenger_summary.get("champion_win_count", 0),
            "tie_task_count": challenger_summary.get("tie_task_count", 0),
            "promotion_candidate_count": challenger_summary.get("promotion_candidate_count", 0),
            "promotion_candidate_tasks": challenger_summary.get("promotion_candidate_tasks", []),
        },
        "iteration_promotions": {
            "candidate_task_count": promotion_summary.get("candidate_task_count", 0),
            "promoted_task_count": promotion_summary.get("promoted_task_count", 0),
            "skipped_task_count": promotion_summary.get("skipped_task_count", 0),
            "promoted_tasks": promotion_summary.get("promoted_tasks", []),
            "skipped_tasks": promotion_summary.get("skipped_tasks", []),
        },
        "neural_net": neural_summary,
        "phase_one_focus": phase_one_focus,
        "backtesting": {
            "current_priority": backtesting_report.get("current_priority"),
            "stages": backtesting_stage_summaries,
        },
        "improvement_plan": {
            "phase": improvement_plan_report.get("phase"),
            "status": improvement_plan_report.get("status"),
            "priority_action_count": len(improvement_plan_report.get("priority_actions", [])),
            "top_priority_action": (
                improvement_plan_report.get("priority_actions", [{}])[0].get("title")
                if improvement_plan_report.get("priority_actions")
                else None
            ),
            "history_entry_count": improvement_plan_report.get("history", {}).get("entry_count"),
        },
        "next_actions": neural_report.get("next_actions", []),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the reproducible trading learning loop from historical cases through Pine readiness artifacts."
    )
    parser.add_argument("--bootstrap-screenshots", action="store_true")
    parser.add_argument("--apply-safe-feedback", action="store_true")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    step_results = [
        run_step(step)
        for step in build_loop_steps(
            args.python,
            bootstrap_screenshots=args.bootstrap_screenshots,
            apply_safe_feedback=args.apply_safe_feedback,
        )
    ]

    summary = build_loop_summary(
        bootstrap_screenshots=args.bootstrap_screenshots,
        apply_safe_feedback=args.apply_safe_feedback,
        step_results=step_results,
        case_packet_report=load_json(CASE_PACKET_REPORT_PATH, {"summary": {}}),
        pine_verification_report=load_json(PINE_VERIFICATION_REPORT_PATH, {"summary": {}}),
        tradingview_pine_report=load_json(TRADINGVIEW_PINE_REPORT_PATH, {"summary": {}}),
        feedback_queue=load_json(FEEDBACK_QUEUE_PATH, {"summary": {}, "items": []}),
        training_loop_report=load_json(TRAINING_LOOP_REPORT_PATH, {}),
        neural_report=load_json(NEURAL_REPORT_PATH, {}),
        backtesting_report=load_json(BACKTESTING_REPORT_PATH, {}),
        iteration_grading_report=load_json(ITERATION_GRADING_REPORT_PATH, {"summary": {}}),
        reinforced_training_report=load_json(REINFORCED_TRAINING_REPORT_PATH, {"summary": {}}),
        iteration_retraining_report=load_json(ITERATION_RETRAINING_REPORT_PATH, {}),
        iteration_challenger_report=load_json(ITERATION_CHALLENGER_REPORT_PATH, {"summary": {}}),
        iteration_promotion_report=load_json(ITERATION_PROMOTION_REPORT_PATH, {"summary": {}}),
        improvement_plan_report=load_json(IMPROVEMENT_PLAN_PATH, {}),
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary["dashboard_output"] = str(TRADING_LEARNING_DASHBOARD_PATH)
    output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    subprocess.run(
        [
            args.python,
            "scripts/export_trading_learning_dashboard.py",
            "--output",
            str(TRADING_LEARNING_DASHBOARD_PATH),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    print(
        json.dumps(
            {
                "output": str(output_path),
                "dashboard_output": str(TRADING_LEARNING_DASHBOARD_PATH),
                "step_count": summary["step_count"],
                "workflow_score": summary["tradingview_pine"]["workflow_score"],
                "loop_grade": summary["training_loop"]["grade"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
