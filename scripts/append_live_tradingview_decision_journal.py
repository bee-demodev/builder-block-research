from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


DEFAULT_DECISION_REPORT_PATH = Path("results") / "live_tradingview_decision_report.json"
DEFAULT_PIPELINE_REPORT_PATH = Path("results") / "live_tradingview_decision_pipeline_report.json"
DEFAULT_JOURNAL_PATH = Path("results") / "live_tradingview_decision_journal.jsonl"
OUTCOMES = (
    "win",
    "loss",
    "breakeven",
    "missed",
    "invalidated_before_entry",
    "not_applicable",
    "unknown",
)
CLASSIFICATIONS = (
    "valid_loss_part_of_odds",
    "model_error",
    "execution_error",
    "vision_error",
    "state_error",
    "retrieval_error",
    "risk_rule_error",
    "not_reviewed",
    "not_applicable",
)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def resolve(root_dir: Path, path: str | Path) -> Path:
    raw_path = Path(path)
    return raw_path if raw_path.is_absolute() else (root_dir / raw_path).resolve()


def relative_or_absolute(path: Path, root_dir: Path) -> str:
    try:
        return str(path.resolve().relative_to(root_dir.resolve()))
    except ValueError:
        return str(path.resolve())


def compact_hits(hits: Any, *, limit: int = 5) -> list[dict[str, Any]]:
    if not isinstance(hits, list):
        return []
    compacted: list[dict[str, Any]] = []
    for hit in hits[:limit]:
        if not isinstance(hit, dict):
            continue
        compacted.append(
            {
                "source_path": hit.get("source_path", ""),
                "example_id": hit.get("example_id", ""),
                "title": hit.get("title", ""),
                "checkpoint": hit.get("checkpoint", ""),
                "score": hit.get("score"),
                "matched_terms": hit.get("matched_terms", []),
            }
        )
    return compacted


def infer_outcome(verdict: str, requested_outcome: str | None) -> str:
    if requested_outcome:
        return requested_outcome
    if verdict in {"take", "watch"}:
        return "unknown"
    return "not_applicable"


def infer_classification(verdict: str, outcome: str, requested_classification: str | None) -> str:
    if requested_classification:
        return requested_classification
    if verdict in {"take", "watch"} and outcome == "loss":
        return "not_reviewed"
    if verdict in {"take", "watch"} and outcome in {"win", "breakeven", "missed", "invalidated_before_entry", "unknown"}:
        return "not_reviewed"
    return "not_applicable"


def infer_status(verdict: str, outcome: str, has_decision_report: bool) -> str:
    if not has_decision_report or verdict in {"no_trade", "insufficient_evidence"}:
        return "not_applicable"
    if outcome in {"unknown", "not_applicable"}:
        return "pending_outcome"
    return "outcome_logged"


def missing_or_unverified(decision_report: dict[str, Any]) -> list[str]:
    writeup = decision_report.get("decision_writeup", {})
    if isinstance(writeup, dict) and isinstance(writeup.get("missing_or_unverified"), list):
        return [str(item) for item in writeup["missing_or_unverified"]]
    checklist = decision_report.get("checklist", [])
    if not isinstance(checklist, list):
        return []
    missing: list[str] = []
    for item in checklist:
        if not isinstance(item, dict):
            continue
        if item.get("required_for_take") and item.get("status") != "passed":
            missing.append(str(item.get("field", "")))
    return [item for item in missing if item]


def event_type_for(*, has_decision_report: bool, verdict: str, status: str) -> str:
    if not has_decision_report:
        return "blocked_or_no_decision"
    if status == "outcome_logged":
        return "outcome_logged"
    if verdict in {"take", "watch"}:
        return "decision_pending_outcome"
    return "decision_no_trade_or_insufficient"


def build_journal_event(
    *,
    root_dir: Path,
    decision_report_path: Path,
    pipeline_report_path: Path,
    decision_report: dict[str, Any],
    pipeline_report: dict[str, Any],
    outcome: str | None = None,
    classification: str | None = None,
    notes: list[str] | None = None,
    follow_up_labels: list[str] | None = None,
) -> dict[str, Any]:
    has_decision_report = bool(decision_report)
    source = decision_report if has_decision_report else pipeline_report
    verdict = str(source.get("verdict") or "insufficient_evidence")
    resolved_outcome = infer_outcome(verdict, outcome)
    resolved_classification = infer_classification(verdict, resolved_outcome, classification)
    status = infer_status(verdict, resolved_outcome, has_decision_report)
    warnings = source.get("warnings", [])
    if not isinstance(warnings, list):
        warnings = []
    blockers = pipeline_report.get("preflight_blocking_checks", [])
    if not isinstance(blockers, list):
        blockers = []
    warning_checks = pipeline_report.get("preflight_warning_checks", [])
    if not isinstance(warning_checks, list):
        warning_checks = []
    return {
        "mode": "live_tradingview_decision_journal_event",
        "event_version": "live_decision_journal_v1",
        "event_id": f"live-tv-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}",
        "logged_at": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type_for(
            has_decision_report=has_decision_report,
            verdict=verdict,
            status=status,
        ),
        "source_artifacts": {
            "decision_report_path": relative_or_absolute(decision_report_path, root_dir) if decision_report_path.exists() else "",
            "pipeline_report_path": relative_or_absolute(pipeline_report_path, root_dir) if pipeline_report_path.exists() else "",
            "packet_path": str(source.get("source_packet_path") or pipeline_report.get("packet_path") or ""),
            "chart_paths": source.get("chart_paths", {}),
        },
        "decision": {
            "symbol": str(source.get("symbol") or "unknown"),
            "verdict": verdict,
            "confidence": source.get("confidence", 0.0),
            "decision_ready": bool(source.get("decision_ready")),
            "warnings": [str(item) for item in warnings],
            "reasons": source.get("reasons", []) if isinstance(source.get("reasons", []), list) else [],
            "missing_or_unverified": missing_or_unverified(decision_report) if has_decision_report else [],
            "next_action": str(pipeline_report.get("next_action") or ""),
        },
        "preflight": {
            "executed": bool(pipeline_report.get("preflight_executed")),
            "ready": bool(pipeline_report.get("preflight_ready")),
            "blocking_checks": [str(item) for item in blockers],
            "warning_checks": [str(item) for item in warning_checks],
        },
        "retrieval_evidence": compact_hits(decision_report.get("retrieval_hits", [])),
        "journal": {
            "status": status,
            "outcome": resolved_outcome,
            "classification": resolved_classification,
            "notes": notes or [],
            "follow_up_labels": follow_up_labels or [],
        },
    }


def append_event(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Append a structured journal event for a live TradingView decision run.")
    parser.add_argument("--root-dir", type=Path, default=Path("."))
    parser.add_argument("--decision-report", type=Path, default=DEFAULT_DECISION_REPORT_PATH)
    parser.add_argument("--pipeline-report", type=Path, default=DEFAULT_PIPELINE_REPORT_PATH)
    parser.add_argument("--journal", type=Path, default=DEFAULT_JOURNAL_PATH)
    parser.add_argument("--outcome", choices=OUTCOMES, default=None)
    parser.add_argument("--classification", choices=CLASSIFICATIONS, default=None)
    parser.add_argument("--note", action="append", default=[])
    parser.add_argument("--follow-up-label", action="append", default=[])
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root_dir = args.root_dir.resolve()
    decision_report_path = resolve(root_dir, args.decision_report)
    pipeline_report_path = resolve(root_dir, args.pipeline_report)
    journal_path = resolve(root_dir, args.journal)
    event = build_journal_event(
        root_dir=root_dir,
        decision_report_path=decision_report_path,
        pipeline_report_path=pipeline_report_path,
        decision_report=load_json(decision_report_path),
        pipeline_report=load_json(pipeline_report_path),
        outcome=args.outcome,
        classification=args.classification,
        notes=list(args.note or []),
        follow_up_labels=list(args.follow_up_label or []),
    )
    append_event(journal_path, event)
    print(
        json.dumps(
            {
                "journal_path": str(journal_path),
                "event_id": event["event_id"],
                "event_type": event["event_type"],
                "verdict": event["decision"]["verdict"],
                "journal_status": event["journal"]["status"],
                "outcome": event["journal"]["outcome"],
                "classification": event["journal"]["classification"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
