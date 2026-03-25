from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from export_ttfm_case_packets import DEFAULT_OUTPUT as DEFAULT_CASE_PACKET_PATH
from export_understanding_report import grade_from_score


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "results" / "ttfm_training_loop_report.json"
DEFAULT_DISAGREEMENT_REPORT_PATH = ROOT / "results" / "ttfm_disagreement_report.json"
DEFAULT_PINE_VERIFICATION_REPORT_PATH = ROOT / "results" / "ttfm_pine_verification_report.json"
DEFAULT_TRADINGVIEW_PINE_REPORT_PATH = ROOT / "results" / "tradingview_pine_readiness_report.json"

BUCKET_WEIGHTS = {
    "data_quality": 0.20,
    "label_quality": 0.25,
    "model_quality": 0.25,
    "research_yield": 0.15,
    "regression_safety": 0.15,
}


def clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def safe_divide(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def normalize_metrics(metrics: dict) -> dict[str, float]:
    return {
        bucket: round(clamp(float(metrics.get(bucket, 0.0))), 4)
        for bucket in BUCKET_WEIGHTS
    }


def build_warnings(metrics: dict, bucket_scores: dict[str, float]) -> list[str]:
    warnings: list[str] = []
    rule_mismatch_rate = float(metrics.get("rule_mismatch_rate", 0.0))
    if int(metrics.get("anchor_case_regressions", 0)) > 0:
        warnings.append("Anchor-case regressions were detected in this loop.")
    if float(metrics.get("rule_mismatch_delta", 0.0)) > 0.02:
        warnings.append("Rule mismatch increased relative to the previous loop.")
    if rule_mismatch_rate > 0.10:
        warnings.append("Rule mismatch rate remains high for a visually grounded loop.")
    if float(metrics.get("relabel_churn", 0.0)) > 0.30:
        warnings.append("Relabel churn is high; review whether the loop is over-correcting weak labels.")
    if bucket_scores["regression_safety"] < 0.60:
        warnings.append("Regression safety is below the acceptable threshold.")
    if float(metrics.get("tradingview_workflow_score", 0.0)) < 0.40:
        warnings.append("TradingView and Pine workflow coverage is still too weak to trust script translation progress.")
    if float(metrics.get("tradingview_validation_coverage", 0.0)) == 0.0:
        warnings.append("No TradingView-validated Pine drafts are present in the current loop.")
    return warnings


def determine_verdict(metrics: dict, bucket_scores: dict[str, float], loop_score: float) -> str:
    anchor_case_regressions = int(metrics.get("anchor_case_regressions", 0))
    rule_mismatch_delta = float(metrics.get("rule_mismatch_delta", 0.0))
    rule_mismatch_rate = float(metrics.get("rule_mismatch_rate", 0.0))
    relabel_churn = float(metrics.get("relabel_churn", 0.0))
    regression_safety = bucket_scores["regression_safety"]

    if regression_safety < 0.50 and (
        anchor_case_regressions > 0 or rule_mismatch_delta > 0.05 or rule_mismatch_rate > 0.20
    ):
        return "discard"
    if (
        regression_safety < 0.60
        or anchor_case_regressions > 0
        or rule_mismatch_delta > 0.02
        or rule_mismatch_rate > 0.10
    ):
        return "investigate"
    if relabel_churn > 0.30:
        return "keep_with_warnings"
    if loop_score >= 0.80:
        return "keep"
    return "keep_with_warnings"


def build_training_loop_report(metrics: dict) -> dict:
    bucket_scores = normalize_metrics(metrics)
    loop_score = round(
        sum(bucket_scores[bucket] * weight for bucket, weight in BUCKET_WEIGHTS.items()),
        4,
    )
    warnings = build_warnings(metrics, bucket_scores)
    verdict = determine_verdict(metrics, bucket_scores, loop_score)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "bucket_scores": bucket_scores,
        "loop_score": loop_score,
        "grade": grade_from_score(loop_score),
        "verdict": verdict,
        "warnings": warnings,
        "metrics": metrics,
    }


def build_bootstrap_metrics(case_packet_report: dict) -> dict:
    summary = case_packet_report.get("summary", {})
    case_count = int(summary.get("case_count", 0))
    checkpoint_count = int(summary.get("checkpoint_count", 0))
    missing_screenshot_count = int(summary.get("missing_screenshot_count", 0))
    multi_timeframe_ratio = float(summary.get("multi_timeframe_case_ratio", 0.0))

    screenshot_coverage = 0.0
    if checkpoint_count:
        screenshot_coverage = 1.0 - (missing_screenshot_count / checkpoint_count)

    data_quality = (
        0.45 * clamp(case_count / 20.0)
        + 0.30 * multi_timeframe_ratio
        + 0.25 * screenshot_coverage
    )
    label_quality = 0.55 * clamp(case_count / 20.0) + 0.45 * screenshot_coverage

    return {
        "data_quality": round(clamp(data_quality), 4),
        "label_quality": round(clamp(label_quality), 4),
        "model_quality": 0.0,
        "research_yield": round(clamp(case_count / 25.0), 4),
        "regression_safety": 1.0,
        "anchor_case_regressions": 0,
        "rule_mismatch_rate": 0.0,
        "rule_mismatch_delta": 0.0,
        "relabel_churn": 0.0,
        "tradingview_workflow_score": 0.0,
        "tradingview_generated_script_coverage": 0.0,
        "tradingview_validation_coverage": 0.0,
        "bootstrap_only": True,
    }


def load_case_packet_report(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_optional_report(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def build_metrics_from_reports(
    case_packet_report: dict,
    *,
    disagreement_report: dict | None = None,
    pine_verification_report: dict | None = None,
    tradingview_pine_report: dict | None = None,
) -> dict:
    summary = case_packet_report.get("summary", {})
    case_count = int(summary.get("case_count", 0))
    screenshot_coverage = float(summary.get("screenshot_coverage", 0.0))
    anchor_coverage = float(summary.get("anchor_coverage", 0.0))
    multi_timeframe_ratio = float(summary.get("multi_timeframe_case_ratio", 0.0))
    missing_evidence_ref_count = int(summary.get("missing_evidence_ref_count", 0))
    checkpoint_count = int(summary.get("checkpoint_count", 0))
    evidence_coverage = 1.0 - (missing_evidence_ref_count / checkpoint_count) if checkpoint_count else 0.0

    data_quality = (
        0.25 * clamp(case_count / 20.0)
        + 0.25 * clamp(screenshot_coverage)
        + 0.20 * clamp(anchor_coverage)
        + 0.20 * clamp(multi_timeframe_ratio)
        + 0.10 * clamp(evidence_coverage)
    )

    effective_disagreement = disagreement_report is not None and int(
        disagreement_report.get("summary", {}).get("evaluated_checkpoint_count", 0)
    ) > 0

    if not effective_disagreement:
        disagreement_summary = {}
    else:
        disagreement_summary = disagreement_report.get("summary", {})

    macro_f1 = float(disagreement_summary.get("macro_f1", 0.0))
    timeframe_consistency = float(disagreement_summary.get("timeframe_consistency", 0.0))
    sequence_consistency = float(disagreement_summary.get("sequence_consistency", 0.0))
    anchor_case_regressions = int(disagreement_summary.get("anchor_case_regressions", 0))
    anchor_checkpoint_count = int(disagreement_summary.get("anchor_checkpoint_count", 0))
    anchor_label_agreement = float(disagreement_summary.get("anchor_label_agreement", 0.0))
    rule_mismatch_rate = float(disagreement_summary.get("rule_mismatch_rate", 0.0))
    rule_mismatch_delta = float(disagreement_summary.get("rule_mismatch_delta", 0.0))
    mistake_cluster_count = int(disagreement_summary.get("mistake_cluster_count", 0))
    mistake_cluster_signal = clamp(mistake_cluster_count / 6.0)

    if not effective_disagreement:
        label_quality = 0.55 * clamp(case_count / 20.0) + 0.45 * clamp(screenshot_coverage)
        model_quality = 0.0
        regression_safety = 1.0
    else:
        if anchor_checkpoint_count <= 0:
            anchor_label_agreement = 0.0
        label_quality = (
            0.40 * clamp(anchor_label_agreement)
            + 0.25 * clamp(1.0 - rule_mismatch_rate)
            + 0.20 * clamp(sequence_consistency)
            + 0.15 * clamp(anchor_coverage)
        )
        model_quality = (
            0.45 * clamp(macro_f1)
            + 0.30 * clamp(timeframe_consistency)
            + 0.25 * clamp(sequence_consistency)
        )
        regression_safety = (
            0.55 * clamp(1.0 - safe_divide(anchor_case_regressions, anchor_checkpoint_count or 1))
            + 0.25 * clamp(1.0 - rule_mismatch_rate)
            + 0.20 * clamp(1.0 - float(disagreement_summary.get("relabel_churn", 0.0)))
        )

    pine_summary = (pine_verification_report or {}).get("summary", {})
    translatability_score = float(pine_summary.get("translatability_score", 0.0))
    queue_ready_component_count = int(pine_summary.get("queue_ready_component_count", 0))
    feedback_candidate_count = int(pine_summary.get("feedback_candidate_count", 0))
    pine_maturity = clamp(queue_ready_component_count / 5.0)
    pine_feedback_signal = clamp(feedback_candidate_count / 8.0)
    tradingview_summary = (tradingview_pine_report or {}).get("summary", {})
    tradingview_workflow_score = float(tradingview_summary.get("workflow_score", 0.0))
    tradingview_generated_script_coverage = float(
        tradingview_summary.get("generated_script_coverage", 0.0)
    )
    tradingview_validation_coverage = float(tradingview_summary.get("validation_coverage", 0.0))

    research_yield = (
        0.35 * mistake_cluster_signal
        + 0.20 * clamp(translatability_score)
        + 0.10 * pine_maturity
        + 0.10 * pine_feedback_signal
        + 0.15 * clamp(tradingview_workflow_score)
        + 0.05 * clamp(tradingview_generated_script_coverage)
        + 0.05 * clamp(tradingview_validation_coverage)
    )

    return {
        "data_quality": round(clamp(data_quality), 4),
        "label_quality": round(clamp(label_quality), 4),
        "model_quality": round(clamp(model_quality), 4),
        "research_yield": round(clamp(research_yield), 4),
        "regression_safety": round(clamp(regression_safety), 4),
        "anchor_case_regressions": anchor_case_regressions,
        "rule_mismatch_rate": round(clamp(rule_mismatch_rate), 4),
        "rule_mismatch_delta": round(rule_mismatch_delta, 4),
        "relabel_churn": round(float(disagreement_summary.get("relabel_churn", 0.0)), 4),
        "tradingview_workflow_score": round(clamp(tradingview_workflow_score), 4),
        "tradingview_generated_script_coverage": round(clamp(tradingview_generated_script_coverage), 4),
        "tradingview_validation_coverage": round(clamp(tradingview_validation_coverage), 4),
        "bootstrap_only": not effective_disagreement,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export a graded TTFM training-loop report from bucket metrics or the current case-packet bootstrap."
    )
    parser.add_argument("--metrics-json")
    parser.add_argument("--case-packets", default=str(DEFAULT_CASE_PACKET_PATH))
    parser.add_argument("--disagreement-report", default=str(DEFAULT_DISAGREEMENT_REPORT_PATH))
    parser.add_argument("--pine-verification-report", default=str(DEFAULT_PINE_VERIFICATION_REPORT_PATH))
    parser.add_argument("--tradingview-pine-report", default=str(DEFAULT_TRADINGVIEW_PINE_REPORT_PATH))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    if args.metrics_json:
        metrics = json.loads(args.metrics_json)
    else:
        case_packet_report = load_case_packet_report(Path(args.case_packets))
        disagreement_report = load_optional_report(Path(args.disagreement_report))
        pine_verification_report = load_optional_report(Path(args.pine_verification_report))
        tradingview_pine_report = load_optional_report(Path(args.tradingview_pine_report))
        if disagreement_report is None and pine_verification_report is None and tradingview_pine_report is None:
            metrics = build_bootstrap_metrics(case_packet_report)
        else:
            metrics = build_metrics_from_reports(
                case_packet_report,
                disagreement_report=disagreement_report,
                pine_verification_report=pine_verification_report,
                tradingview_pine_report=tradingview_pine_report,
            )

    report = build_training_loop_report(metrics)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output_path),
                "loop_score": report["loop_score"],
                "grade": report["grade"],
                "verdict": report["verdict"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
