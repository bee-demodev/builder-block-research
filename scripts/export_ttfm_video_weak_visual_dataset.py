from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WINDOWS_PATH = ROOT / "knowledge" / "ttfm_video_corpus" / "visual_windows.jsonl"
DEFAULT_DATASET_OUTPUT = ROOT / "results" / "ttfm_video_weak_visual_dataset.jsonl"
DEFAULT_REPORT_OUTPUT = ROOT / "results" / "ttfm_video_weak_visual_dataset_report.json"


def normalize_optional_string(value: object) -> str | None:
    cleaned = str(value or "").strip()
    if not cleaned or cleaned.lower() in {"none", "null"}:
        return None
    return cleaned


def determine_training_blockers(
    *,
    screenshot_path: str | None,
    frame_status: str,
    active_labels: list[str],
    transcript_source: str | None,
) -> list[str]:
    blockers: list[str] = []
    if not screenshot_path or frame_status != "extracted":
        blockers.append("missing_frame")
    if not active_labels:
        blockers.append("missing_weak_labels")
    if transcript_source == "synthetic_from_video_metadata":
        blockers.append("synthetic_transcript")
    return blockers


def review_status_for_blockers(blockers: list[str]) -> str:
    if not blockers:
        return "ready_for_weak_training"
    if "missing_frame" in blockers:
        return "missing_frame"
    if "missing_weak_labels" in blockers:
        return "needs_label_review"
    return "needs_teacher_review"


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            cleaned = line.strip()
            if cleaned:
                rows.append(json.loads(cleaned))
    return rows


def build_video_weak_visual_dataset_rows(window_rows: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for window in window_rows:
        screenshot_path = normalize_optional_string(window.get("frame_path"))
        frame_status = str(window.get("frame_status", "")).strip() or "unknown"
        transcript_source = normalize_optional_string(window.get("transcript_source"))
        source_url = normalize_optional_string(window.get("source_url"))
        source_page = normalize_optional_string(window.get("source_page"))
        source_chunk_id = normalize_optional_string(window.get("source_chunk_id"))
        evidence_refs = [value for value in [source_url, source_page, source_chunk_id] if value]
        active_labels = [
            str(label).strip()
            for label in window.get("candidate_labels", [])
            if str(label).strip()
        ]
        training_blockers = determine_training_blockers(
            screenshot_path=screenshot_path,
            frame_status=frame_status,
            active_labels=active_labels,
            transcript_source=transcript_source,
        )
        review_status = review_status_for_blockers(training_blockers)

        rows.append(
            {
                "example_id": str(window.get("example_id", "")).strip()
                or str(window.get("window_id", "")).strip(),
                "case_ref": str(window.get("case_ref", "")).strip()
                or str(window.get("video_slug", "")).strip(),
                "source_type": str(window.get("source_type", "")).strip() or "youtube_visual_window",
                "video_slug": str(window.get("video_slug", "")).strip(),
                "video_id": str(window.get("video_id", "")).strip(),
                "title": str(window.get("title", "")).strip(),
                "source_url": source_url,
                "source_page": source_page,
                "corpus_partition": str(window.get("corpus_partition", "seed_curriculum")).strip()
                or "seed_curriculum",
                "review_categories": [
                    str(category).strip()
                    for category in window.get("review_categories", [])
                    if str(category).strip()
                ],
                "checkpoint": str(window.get("checkpoint", "")).strip() or "unknown",
                "timeframe": str(window.get("timeframe", "")).strip() or None,
                "timeframe_role": str(window.get("timeframe_role", "")).strip() or None,
                "topics": [str(topic).strip() for topic in window.get("topics", []) if str(topic).strip()],
                "supporting_topics": [
                    str(topic).strip()
                    for topic in window.get("supporting_topics", [])
                    if str(topic).strip()
                ],
                "active_labels": active_labels,
                "active_label_provenance": str(
                    window.get("candidate_label_provenance", "")
                ).strip()
                or "youtube_transcript_checkpoint_heuristic",
                "weak_label_confidence": float(
                    window.get("market_context", {}).get("confidence", 0.35) or 0.35
                ),
                "cue_terms": [
                    str(term).strip() for term in window.get("cue_terms", []) if str(term).strip()
                ],
                "transcript_window": str(
                    window.get("nearby_transcript_text", "")
                ).strip()
                or str(window.get("text", "")).strip(),
                "annotation_notes": [
                    (
                        "Weak labels inferred from YouTube transcript checkpoint heuristics. "
                        "Use for weak supervision, retrieval support, and contradiction review "
                        "before promoting into the high-confidence teacher set."
                    )
                ],
                "evidence_refs": evidence_refs,
                "source_chunk_id": source_chunk_id,
                "transcript_source": transcript_source,
                "screenshot_path": screenshot_path,
                "frame_status": frame_status,
                "market_context": window.get("market_context", {}),
                "review_status": review_status,
                "training_blockers": training_blockers,
                "eligible_for_training": not training_blockers,
                "contradiction_status": "unreviewed",
                "embedding_text": str(window.get("embedding_text", "")).strip() or None,
            }
        )
    return rows


def summarize_video_weak_visual_dataset(rows: list[dict], window_rows: list[dict]) -> dict:
    checkpoint_counts: Counter[str] = Counter()
    frame_status_counts: Counter[str] = Counter()
    review_status_counts: Counter[str] = Counter()
    active_label_counts: Counter[str] = Counter()
    training_blocker_counts: Counter[str] = Counter()
    video_slugs: set[str] = set()

    for row in rows:
        checkpoint_counts[str(row.get("checkpoint", "unknown"))] += 1
        frame_status_counts[str(row.get("frame_status", "unknown"))] += 1
        review_status_counts[str(row.get("review_status", "unknown"))] += 1
        active_label_counts.update(
            str(label).strip() for label in row.get("active_labels", []) if str(label).strip()
        )
        training_blocker_counts.update(
            str(blocker).strip()
            for blocker in row.get("training_blockers", [])
            if str(blocker).strip()
        )
        video_slug = str(row.get("video_slug", "")).strip()
        if video_slug:
            video_slugs.add(video_slug)

    return {
        "row_count": len(rows),
        "window_count": len(window_rows),
        "video_count": len(video_slugs),
        "ready_for_weak_training_count": sum(
            1 for row in rows if str(row.get("review_status", "")) == "ready_for_weak_training"
        ),
        "eligible_for_training_count": sum(1 for row in rows if bool(row.get("eligible_for_training"))),
        "weak_labeled_row_count": sum(1 for row in rows if row.get("active_labels")),
        "skipped_missing_frame_count": sum(1 for row in rows if not row.get("screenshot_path")),
        "synthetic_transcript_count": sum(
            1 for row in rows if str(row.get("transcript_source", "")).strip() == "synthetic_from_video_metadata"
        ),
        "checkpoint_counts": dict(sorted(checkpoint_counts.items())),
        "frame_status_counts": dict(sorted(frame_status_counts.items())),
        "review_status_counts": dict(sorted(review_status_counts.items())),
        "active_label_counts": dict(sorted(active_label_counts.items())),
        "training_blocker_counts": dict(sorted(training_blocker_counts.items())),
    }


def build_video_weak_visual_dataset_report(window_rows: list[dict]) -> tuple[list[dict], dict]:
    rows = build_video_weak_visual_dataset_rows(window_rows)
    summary = summarize_video_weak_visual_dataset(rows, window_rows)
    return rows, {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Export the YouTube visual windows as a weakly labeled screenshot dataset "
            "for visual retraining and contradiction review."
        )
    )
    parser.add_argument("--windows-path", default=str(DEFAULT_WINDOWS_PATH))
    parser.add_argument("--output", default=str(DEFAULT_DATASET_OUTPUT))
    parser.add_argument("--report-output", default=str(DEFAULT_REPORT_OUTPUT))
    args = parser.parse_args()

    window_rows = load_jsonl(Path(args.windows_path))
    rows, report = build_video_weak_visual_dataset_report(window_rows)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "\n".join(json.dumps(row) for row in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )

    report_path = Path(args.report_output)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "dataset_output": str(output_path),
                "report_output": str(report_path),
                "row_count": report["summary"]["row_count"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
