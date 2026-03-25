from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from train_narrow_pattern_net import load_surface_examples, prepare_task_examples


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REINFORCED_SURFACE_PATH = ROOT / "results" / "reinforced_model_training_surface.jsonl"
DEFAULT_TEACHER_VISUAL_DATASET_PATH = ROOT / "results" / "ttfm_teacher_visual_dataset.jsonl"
DEFAULT_REPORT_OUTPUT = ROOT / "results" / "phase_one_daily_bias_gap_report.json"
TARGET_TRADE_MODEL = "daily_bias_framework"
TARGET_RECOMMENDED_POSITIVE_EXAMPLES = 5
TARGET_RECOMMENDED_NEGATIVE_EXAMPLES = 5
CHECKPOINT_PRIORITY = {
    "context": 0,
    "confirmation": 1,
    "outcome": 2,
    "closure": 3,
    "sweep": 4,
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            cleaned = line.strip()
            if cleaned:
                rows.append(json.loads(cleaned))
    return rows


def normalize_string_list(values: object) -> list[str]:
    if values is None:
        return []
    if isinstance(values, list):
        return [str(value).strip() for value in values if str(value).strip()]
    if isinstance(values, str):
        cleaned = values.strip()
        return [cleaned] if cleaned else []
    return []


def classify_source_image_kind(row: dict[str, Any]) -> str:
    notes = " ".join(note.lower() for note in normalize_string_list(row.get("annotation_notes")))
    if "source article image" in notes:
        return "source_article_image"
    return "unknown"


def build_promotion_blockers(row: dict[str, Any], *, source_image_kind: str) -> list[str]:
    blockers: list[str] = []
    alignment_status = str(row.get("market_context", {}).get("alignment_status") or "").strip()
    if alignment_status != "fully_aligned":
        blockers.append("missing_fully_aligned_market_context")
    if source_image_kind == "source_article_image":
        blockers.append("source_article_image_only")
    return blockers


def select_daily_bias_gap_candidates(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for row in rows:
        if TARGET_TRADE_MODEL not in set(row.get("trade_models", [])):
            continue
        if str(row.get("outcome", {}).get("decision", "")).strip() != "trade":
            continue
        active_labels = [
            str(label).strip()
            for label in row.get("active_labels", [])
            if str(label).strip()
        ]
        source_image_kind = classify_source_image_kind(row)
        promotion_blockers = build_promotion_blockers(
            row,
            source_image_kind=source_image_kind,
        )
        candidates.append(
            {
                "example_id": row.get("example_id"),
                "case_ref": row.get("case_ref"),
                "checkpoint": row.get("checkpoint"),
                "source_file": "results/ttfm_teacher_visual_dataset.jsonl",
                "source_url": row.get("source_url"),
                "screenshot_path": row.get("screenshot_path"),
                "active_labels": active_labels,
                "active_label_provenance": row.get("active_label_provenance"),
                "trade_model": TARGET_TRADE_MODEL,
                "decision": row.get("outcome", {}).get("decision"),
                "source_spec_key": row.get("market_context", {}).get("source_spec_key"),
                "alignment_status": row.get("market_context", {}).get("alignment_status"),
                "mapping_provenance": row.get("market_context", {}).get("mapping_provenance"),
                "annotation_notes": normalize_string_list(row.get("annotation_notes")),
                "source_image_kind": source_image_kind,
                "promotion_ready": not promotion_blockers,
                "promotion_blockers": promotion_blockers,
            }
        )

    def sort_key(candidate: dict[str, Any]) -> tuple[int, int, int, str]:
        provenance_rank = 0 if candidate["active_label_provenance"] == "rule_derived" else 1
        label_count_rank = -len(candidate["active_labels"])
        checkpoint_rank = CHECKPOINT_PRIORITY.get(str(candidate["checkpoint"]), 99)
        case_ref = str(candidate["case_ref"] or "")
        return (provenance_rank, label_count_rank, checkpoint_rank, case_ref)

    return sorted(candidates, key=sort_key)


def build_gap_blocker(
    *,
    additional_positive_examples_needed: int,
    promotable_candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    if additional_positive_examples_needed <= 0:
        return {
            "type": "none",
            "missing_replay_evidence": False,
            "missing_tradingview_validation": False,
            "details": "The daily-bias positive-example gap is already closed.",
        }
    if promotable_candidates:
        return {
            "type": "missing_tradingview_validation",
            "missing_replay_evidence": False,
            "missing_tradingview_validation": True,
            "details": (
                "At least one daily-bias teacher case is chart-backed and promotable, "
                "but it still needs a passing TradingView QA entry before it can be "
                "added to the reinforced surface."
            ),
        }
    return {
        "type": "missing_chart_state_alignment",
        "missing_replay_evidence": True,
        "missing_tradingview_validation": False,
        "details": (
            "The current daily-bias teacher visuals are still bootstrapped from source "
            "article images and remain market_context_only. They are not promotable via "
            "live TradingView QA alone because the underlying teacher cases still lack "
            "fully aligned chart-state evidence."
        ),
    }


def build_next_step(
    *,
    additional_positive_examples_needed: int,
    promotable_candidates: list[dict[str, Any]],
    blocked_candidates: list[dict[str, Any]],
) -> str:
    if additional_positive_examples_needed <= 0:
        return (
            "Rebuild the reinforced surface and retrain daily_bias_framework because the "
            "recommended positive-example floor has already been met."
        )
    if promotable_candidates:
        return (
            "Validate the top promotable daily-bias teacher case in TradingView, then "
            "rebuild the reinforced surface before retraining daily_bias_framework and "
            "trade_vs_no_trade."
        )
    top_blocked_example_id = blocked_candidates[0]["example_id"] if blocked_candidates else "unknown"
    return (
        "Backfill anchor timestamps and replay-aligned chart evidence for the blocked "
        f"daily-bias teacher cases starting with {top_blocked_example_id}, then rerun "
        "the phase-one replay export and rebuild the reinforced surface."
    )


def build_phase_one_daily_bias_gap_report(
    *,
    reinforced_surface_path: Path = DEFAULT_REINFORCED_SURFACE_PATH,
    teacher_visual_dataset_path: Path = DEFAULT_TEACHER_VISUAL_DATASET_PATH,
) -> dict[str, Any]:
    surface_examples = load_surface_examples(reinforced_surface_path)
    prepared = prepare_task_examples(surface_examples, task_name=TARGET_TRADE_MODEL)
    positive_count = sum(1 for item in prepared["examples"] if int(item["label"]) == 1)
    negative_count = sum(1 for item in prepared["examples"] if int(item["label"]) == 0)
    candidate_rows = load_jsonl(teacher_visual_dataset_path)
    candidates = select_daily_bias_gap_candidates(candidate_rows)
    additional_positive_examples_needed = max(
        0, TARGET_RECOMMENDED_POSITIVE_EXAMPLES - positive_count
    )
    promotable_candidates = [candidate for candidate in candidates if candidate["promotion_ready"]]
    blocked_candidates = [candidate for candidate in candidates if not candidate["promotion_ready"]]
    blocker = build_gap_blocker(
        additional_positive_examples_needed=additional_positive_examples_needed,
        promotable_candidates=promotable_candidates,
    )
    alignment_status_counts = Counter(
        str(candidate.get("alignment_status") or "missing") for candidate in candidates
    )
    source_image_kind_counts = Counter(
        str(candidate.get("source_image_kind") or "unknown") for candidate in candidates
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "target_trade_model": TARGET_TRADE_MODEL,
        "recommended_positive_examples": TARGET_RECOMMENDED_POSITIVE_EXAMPLES,
        "recommended_negative_examples": TARGET_RECOMMENDED_NEGATIVE_EXAMPLES,
        "additional_positive_examples_needed": additional_positive_examples_needed,
        "current_counts": {
            "positive": positive_count,
            "negative": negative_count,
            "total": len(prepared["examples"]),
        },
        "readiness": {
            "trainable": positive_count >= 2 and negative_count >= 2,
            "ready_for_recommendation": positive_count >= TARGET_RECOMMENDED_POSITIVE_EXAMPLES
            and negative_count >= TARGET_RECOMMENDED_NEGATIVE_EXAMPLES,
        },
        "candidate_summary": {
            "teacher_visual_candidate_count": len(candidates),
            "promotable_candidate_count": len(promotable_candidates),
            "blocked_candidate_count": len(blocked_candidates),
            "alignment_status_counts": dict(sorted(alignment_status_counts.items())),
            "source_image_kind_counts": dict(sorted(source_image_kind_counts.items())),
        },
        "fastest_positive_candidates": promotable_candidates[:3],
        "blocked_teacher_visual_candidates": blocked_candidates[:3],
        "blocker": blocker,
        "source_files": {
            "reinforced_surface": str(reinforced_surface_path).replace("\\", "/"),
            "teacher_visual_dataset": str(teacher_visual_dataset_path).replace("\\", "/"),
        },
        "next_step": build_next_step(
            additional_positive_examples_needed=additional_positive_examples_needed,
            promotable_candidates=promotable_candidates,
            blocked_candidates=blocked_candidates,
        ),
    }


def export_phase_one_daily_bias_gap_report(
    *,
    report_output: Path = DEFAULT_REPORT_OUTPUT,
    reinforced_surface_path: Path = DEFAULT_REINFORCED_SURFACE_PATH,
    teacher_visual_dataset_path: Path = DEFAULT_TEACHER_VISUAL_DATASET_PATH,
) -> dict[str, Any]:
    report = build_phase_one_daily_bias_gap_report(
        reinforced_surface_path=reinforced_surface_path,
        teacher_visual_dataset_path=teacher_visual_dataset_path,
    )
    persisted_report = {
        **report,
        "report_output": str(report_output).replace("\\", "/"),
    }
    report_output.parent.mkdir(parents=True, exist_ok=True)
    report_output.write_text(json.dumps(persisted_report, indent=2) + "\n", encoding="utf-8")
    return persisted_report


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Summarize the current phase-one daily_bias_framework gap and identify the "
            "fastest promotable positive chart state."
        )
    )
    parser.add_argument("--reinforced-surface-path", default=str(DEFAULT_REINFORCED_SURFACE_PATH))
    parser.add_argument("--teacher-visual-dataset-path", default=str(DEFAULT_TEACHER_VISUAL_DATASET_PATH))
    parser.add_argument("--report-output", default=str(DEFAULT_REPORT_OUTPUT))
    args = parser.parse_args()

    report = export_phase_one_daily_bias_gap_report(
        report_output=Path(args.report_output),
        reinforced_surface_path=Path(args.reinforced_surface_path),
        teacher_visual_dataset_path=Path(args.teacher_visual_dataset_path),
    )
    print(
        json.dumps(
            {
                "target_trade_model": report["target_trade_model"],
                "current_counts": report["current_counts"],
                "fastest_positive_example_id": report["fastest_positive_candidates"][0]["example_id"]
                if report["fastest_positive_candidates"]
                else None,
                "top_blocked_example_id": report["blocked_teacher_visual_candidates"][0]["example_id"]
                if report["blocked_teacher_visual_candidates"]
                else None,
                "blocker": report["blocker"]["type"],
                "report_path": report["report_output"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
