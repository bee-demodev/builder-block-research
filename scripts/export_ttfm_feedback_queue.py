from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from export_tradingview_pine_readiness_report import validation_passed_qa_gate


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PINE_VERIFICATION_REPORT_PATH = ROOT / "results" / "ttfm_pine_verification_report.json"
DEFAULT_TRADINGVIEW_VALIDATION_LOG_PATH = ROOT / "data" / "tradingview_pine_validation.json"
DEFAULT_SPEC_DIR = ROOT / "results" / "indicator_specs"
DEFAULT_OUTPUT = ROOT / "data" / "ttfm_feedback_queue.json"

SPEC_TRANSLATION_FAILURE_STATUSES = {
    "compile_error",
    "not_reproducible",
    "partial_translation",
    "rejected",
    "runtime_error",
}


def load_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_text(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def derive_spec_path(spec_key: str, spec_dir: Path) -> Path | None:
    candidate = spec_dir / f"{spec_key}.json"
    return candidate if candidate.exists() else None


def format_target_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def add_item(items: list[dict], item: dict, seen_ids: set[str]) -> None:
    item_id = normalize_text(item.get("id"))
    if not item_id or item_id in seen_ids:
        return
    seen_ids.add(item_id)
    items.append(item)


def build_feedback_queue(
    *,
    pine_verification_report: dict | None = None,
    tradingview_validation_log: dict | None = None,
    spec_dir: Path = DEFAULT_SPEC_DIR,
) -> dict:
    pine_verification_report = pine_verification_report or {"feedback_candidates": []}
    tradingview_validation_log = tradingview_validation_log or {"validations": []}

    items: list[dict] = []
    seen_ids: set[str] = set()

    for candidate in pine_verification_report.get("feedback_candidates", []):
        add_item(items, dict(candidate), seen_ids)

    tradingview_failure_count = 0
    spec_feedback_count = 0
    workflow_feedback_count = 0

    for entry in tradingview_validation_log.get("validations", []):
        spec_key = normalize_text(entry.get("spec_key"))
        status = normalize_text(entry.get("validation_status"))
        method = normalize_text(entry.get("validation_method"))
        qa_failed_after_render = bool(status) and not validation_passed_qa_gate(entry)
        if not spec_key or not status or not qa_failed_after_render:
            continue

        tradingview_failure_count += 1
        notes = normalize_text(entry.get("notes")) or (
            f"TradingView validation attempt ended with `{status}` for `{spec_key}`."
        )
        qa_status = normalize_text(entry.get("qa_status"))
        chart_symbol = normalize_text(entry.get("chart_symbol"))
        script_path = normalize_text(entry.get("script_path"))
        semantic_score = entry.get("semantic_score")
        visual_score = entry.get("visual_score")
        scope_score = entry.get("scope_score")
        failure_key = "qa_gate_failed" if qa_status and qa_status != "pass" and status in {"compiled", "added_to_chart", "validated"} else status

        finding_body_parts = [
            f"TradingView validation for `{spec_key}` failed with status `{status}`.",
        ]
        if method:
            finding_body_parts.append(f"Method: `{method}`.")
        if chart_symbol:
            finding_body_parts.append(f"Chart symbol: `{chart_symbol}`.")
        if script_path:
            finding_body_parts.append(f"Script path: `{script_path}`.")
        if qa_status:
            finding_body_parts.append(f"QA status: `{qa_status}`.")
        if semantic_score is not None and visual_score is not None and scope_score is not None:
            finding_body_parts.append(
                f"Scores semantic/visual/scope: `{semantic_score}` / `{visual_score}` / `{scope_score}`."
            )
        if notes:
            finding_body_parts.append(notes)

        add_item(
            items,
            {
                "id": f"tradingview::{spec_key}::{failure_key}::finding",
                "target_type": "finding",
                "target_path": "findings.md",
                "title": f"TradingView validation blocked for {spec_key}",
                "body": " ".join(finding_body_parts),
            },
            seen_ids,
        )
        workflow_feedback_count += 1

        if status in SPEC_TRANSLATION_FAILURE_STATUSES:
            spec_path = derive_spec_path(spec_key, spec_dir)
            if spec_path is not None:
                add_item(
                    items,
                    {
                        "id": f"tradingview::{spec_key}::{status}::draft-spec",
                        "target_type": "draft_spec",
                        "target_path": format_target_path(spec_path),
                        "question": notes
                        or f"Clarify why TradingView rejected or could not reproduce `{spec_key}`.",
                        "affected_component": spec_key,
                        "topic_refs": [],
                    },
                    seen_ids,
                )
                spec_feedback_count += 1

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "item_count": len(items),
            "pine_feedback_candidate_count": len(
                pine_verification_report.get("feedback_candidates", [])
            ),
            "tradingview_failure_count": tradingview_failure_count,
            "workflow_feedback_count": workflow_feedback_count,
            "spec_feedback_count": spec_feedback_count,
        },
        "items": items,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Merge Pine verification feedback candidates with TradingView validation failures."
    )
    parser.add_argument("--pine-verification-report", default=str(DEFAULT_PINE_VERIFICATION_REPORT_PATH))
    parser.add_argument("--tradingview-validation-log", default=str(DEFAULT_TRADINGVIEW_VALIDATION_LOG_PATH))
    parser.add_argument("--spec-dir", default=str(DEFAULT_SPEC_DIR))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    queue = build_feedback_queue(
        pine_verification_report=load_json(
            Path(args.pine_verification_report), {"feedback_candidates": []}
        ),
        tradingview_validation_log=load_json(
            Path(args.tradingview_validation_log), {"validations": []}
        ),
        spec_dir=Path(args.spec_dir),
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(queue, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output_path),
                "item_count": queue["summary"]["item_count"],
                "tradingview_failure_count": queue["summary"]["tradingview_failure_count"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
