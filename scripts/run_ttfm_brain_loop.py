from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import build_ttfm_google_embeddings as btge
import build_ttfm_video_visual_embeddings as btvve
import ttfm_brain_embeddings as tbe


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CORPUS_REFRESH_REPORT_PATH = ROOT / "knowledge" / "ttfm_video_corpus" / "corpus_refresh_report.json"
DEFAULT_VISUAL_LOOP_REPORT_PATH = ROOT / "results" / "ttfm_visual_teacher_loop_report.json"
DEFAULT_MULTIMODAL_LOOP_REPORT_PATH = ROOT / "results" / "ttfm_multimodal_teacher_loop_report.json"
DEFAULT_REVIEW_QUEUE_PATH = ROOT / "results" / "ttfm_multimodal_review_queue.json"
DEFAULT_REVIEW_PACKETS_PATH = ROOT / "results" / "ttfm_brain_review_packets.json"
DEFAULT_IMPROVEMENT_PLAN_PATH = ROOT / "results" / "ttfm_brain_improvement_plan.json"
DEFAULT_OUTPUT = ROOT / "results" / "ttfm_brain_loop_report.json"
DEFAULT_HISTORY_PATH = ROOT / "results" / "ttfm_brain_loop_history.jsonl"
REVIEWED_ALIGNMENT_PRECISION_THRESHOLD = 0.75
MEAN_DISAGREEMENT_THRESHOLD = 1.5
MIN_REVIEWED_ROW_COUNT = 3
MIN_TRADE_REVIEW_REVIEWED_ROW_COUNT = 3


def load_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return dict(default or {})
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_history_entries(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            entries.append(payload)
    return entries


def append_history_entry(path: Path, entry: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(entry)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(serialized + "\n")


def maybe_refresh_text_embedding_index() -> dict[str, Any]:
    expected_count = tbe.count_jsonl_rows(tbe.DEFAULT_CHUNKS_PATH)
    if tbe.manifest_matches_expected_count(
        tbe.DEFAULT_TEXT_MANIFEST_PATH,
        expected_count=expected_count,
        source_path=tbe.DEFAULT_CHUNKS_PATH,
    ):
        return {
            "status": "reused",
            "expected_count": expected_count,
            **tbe.describe_manifest(tbe.DEFAULT_TEXT_MANIFEST_PATH),
        }

    manifest = btge.build_embeddings(
        chunks_path=tbe.DEFAULT_CHUNKS_PATH,
        index_path=tbe.DEFAULT_TEXT_INDEX_PATH,
        manifest_path=tbe.DEFAULT_TEXT_MANIFEST_PATH,
        model=tbe.tve.DEFAULT_MODEL,
        output_dimensionality=tbe.tve.DEFAULT_OUTPUT_DIMENSIONALITY,
        batch_size=tbe.tve.DEFAULT_BATCH_SIZE,
    )
    return {
        "status": "refreshed",
        "expected_count": expected_count,
        **manifest,
    }


def maybe_refresh_visual_embedding_index() -> dict[str, Any]:
    expected_count = tbe.count_jsonl_rows(tbe.DEFAULT_VISUAL_WINDOWS_PATH)
    if tbe.manifest_matches_expected_count(
        tbe.DEFAULT_VISUAL_MANIFEST_PATH,
        expected_count=expected_count,
        source_path=tbe.DEFAULT_VISUAL_WINDOWS_PATH,
    ):
        return {
            "status": "reused",
            "expected_count": expected_count,
            **tbe.describe_manifest(tbe.DEFAULT_VISUAL_MANIFEST_PATH),
        }

    manifest = btvve.build_visual_embeddings(
        windows_path=tbe.DEFAULT_VISUAL_WINDOWS_PATH,
        index_path=tbe.DEFAULT_VISUAL_INDEX_PATH,
        manifest_path=tbe.DEFAULT_VISUAL_MANIFEST_PATH,
        report_path=btvve.DEFAULT_REPORT_PATH,
        model=tbe.tve.DEFAULT_MULTIMODAL_MODEL,
        output_dimensionality=tbe.tve.DEFAULT_OUTPUT_DIMENSIONALITY,
    )
    return {
        "status": "refreshed",
        "expected_count": expected_count,
        **manifest,
    }


def run_script_stage(
    *,
    python_executable: str,
    script_name: str,
    args: list[str],
) -> dict[str, Any]:
    command = [python_executable, str(ROOT / "scripts" / script_name), *args]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()
    payload: dict[str, Any] = {
        "script_name": script_name,
        "status": "ok",
        "stdout": stdout,
        "stderr": stderr,
    }
    if stdout:
        try:
            payload["stdout_json"] = json.loads(stdout)
        except json.JSONDecodeError:
            pass
    return payload


def select_fallback_next_action(
    *,
    status: str,
    review_queue: dict[str, Any],
    pine_status: str = "not_ready",
) -> str:
    if pine_status == "ready_for_translation":
        return "brain_ready_for_pine"
    queue_summary = review_queue.get("summary", {})
    if status == "degraded":
        return "report_first"
    if int(queue_summary.get("model_disagreement_count", 0) or 0) > 0:
        return "review_top_disagreements"
    if int(queue_summary.get("ready_to_promote_count", 0) or 0) > 0:
        return "promote_clean_labels"
    return "retrain_after_review"


def compute_health_flags(
    *,
    status: str,
    review_queue: dict[str, Any],
    multimodal_loop_report: dict[str, Any],
    trade_review_readiness: dict[str, Any],
) -> tuple[bool, str]:
    queue_summary = review_queue.get("summary", {})
    model_summary = multimodal_loop_report.get("multimodal_model", {})
    reviewed_row_count = int(queue_summary.get("reviewed_row_count", 0) or 0)
    reviewed_alignment_precision = float(
        queue_summary.get("reviewed_alignment_precision", 0.0) or 0.0
    )
    mean_disagreement_count = float(queue_summary.get("mean_disagreement_count", 0.0) or 0.0)
    validation_precision = float(model_summary.get("validation_micro_precision", 0.0) or 0.0)
    trade_review_row_count = int(trade_review_readiness.get("row_count", 0) or 0)
    trade_review_reviewed_row_count = int(trade_review_readiness.get("reviewed_row_count", 0) or 0)
    trade_review_alignment_precision = float(
        trade_review_readiness.get("reviewed_alignment_precision", 0.0) or 0.0
    )
    trade_review_mean_disagreement_count = float(
        trade_review_readiness.get("mean_disagreement_count", 0.0) or 0.0
    )

    if reviewed_row_count < MIN_REVIEWED_ROW_COUNT:
        return False, "deferred"
    if (
        trade_review_row_count > 0
        and trade_review_reviewed_row_count < MIN_TRADE_REVIEW_REVIEWED_ROW_COUNT
    ):
        return False, "deferred"
    if (
        status == "ok"
        and reviewed_alignment_precision >= REVIEWED_ALIGNMENT_PRECISION_THRESHOLD
        and validation_precision >= REVIEWED_ALIGNMENT_PRECISION_THRESHOLD
        and mean_disagreement_count <= MEAN_DISAGREEMENT_THRESHOLD
        and (
            trade_review_row_count == 0
            or (
                trade_review_alignment_precision >= REVIEWED_ALIGNMENT_PRECISION_THRESHOLD
                and trade_review_mean_disagreement_count <= MEAN_DISAGREEMENT_THRESHOLD
            )
        )
    ):
        return True, "healthy"
    return False, "not_ready"


def compute_healthy_streak(history_entries: list[dict[str, Any]], current_healthy: bool) -> int:
    streak = 1 if current_healthy else 0
    if not current_healthy:
        return streak
    for entry in reversed(history_entries):
        if bool(entry.get("healthy")):
            streak += 1
            continue
        break
    return streak


def build_brain_loop_report(
    *,
    framework_slug: str,
    profile_slug: str,
    brain_type: str,
    status: str,
    corpus_refresh_stage: dict[str, Any] | None,
    text_embedding_stage: dict[str, Any],
    visual_embedding_stage: dict[str, Any],
    visual_loop_report: dict[str, Any],
    multimodal_loop_report: dict[str, Any],
    review_queue: dict[str, Any],
    trade_review_readiness: dict[str, Any],
    review_packets: dict[str, Any] | None,
    improvement_plan: dict[str, Any] | None,
    failed_optional_stages: list[str],
    pine_status: str,
    healthy_streak: int,
) -> dict[str, Any]:
    next_action = (
        str(improvement_plan.get("next_action", "")).strip()
        if improvement_plan
        else select_fallback_next_action(
            status=status,
            review_queue=review_queue,
            pine_status=pine_status,
        )
    ) or select_fallback_next_action(
        status=status,
        review_queue=review_queue,
        pine_status=pine_status,
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "framework_slug": framework_slug,
        "profile_slug": profile_slug,
        "brain_type": brain_type,
        "status": status,
        "failed_optional_stages": failed_optional_stages,
        "video_corpus_stage": corpus_refresh_stage or {},
        "embedding_backend": "google_gemini",
        "text_embedding_stage": text_embedding_stage,
        "visual_embedding_stage": visual_embedding_stage,
        "visual_teacher_loop": visual_loop_report,
        "multimodal_teacher_loop": multimodal_loop_report,
        "multimodal_model": multimodal_loop_report.get("multimodal_model", {}),
        "review_queue": review_queue.get("summary", {}),
        "trade_review_readiness": trade_review_readiness,
        "review_packets": (review_packets or {}).get("summary", {}),
        "improvement_plan": improvement_plan or {},
        "next_action": next_action,
        "pine_status": pine_status,
        "healthy_streak": healthy_streak,
    }


def summarize_partition_readiness(
    review_queue: dict[str, Any],
    *,
    corpus_partition: str,
) -> dict[str, Any]:
    items = [
        item
        for item in review_queue.get("items", [])
        if str(item.get("corpus_partition", "")).strip() == corpus_partition
    ]
    reviewed_items = [
        item
        for item in items
        if str(item.get("review_status", "")).strip() in {"approved_for_teacher", "teacher_approved", "promoted_to_teacher"}
    ]
    disagreement_items = [item for item in items if int(item.get("disagreement_count", 0) or 0) > 0]
    video_slugs = {
        str(item.get("video_slug", "")).strip()
        for item in items
        if str(item.get("video_slug", "")).strip()
    }
    recommended_action_counts: dict[str, int] = {}
    for item in items:
        action = str(item.get("recommended_action", "")).strip() or "unknown"
        recommended_action_counts[action] = recommended_action_counts.get(action, 0) + 1
    reviewed_alignment_precision = 0.0
    if reviewed_items:
        reviewed_alignment_precision = sum(
            float(item.get("label_jaccard", 0.0) or 0.0) for item in reviewed_items
        ) / float(len(reviewed_items))
    mean_disagreement_count = 0.0
    if items:
        mean_disagreement_count = sum(
            float(item.get("disagreement_count", 0.0) or 0.0) for item in items
        ) / float(len(items))
    return {
        "corpus_partition": corpus_partition,
        "row_count": len(items),
        "video_count": len(video_slugs),
        "model_disagreement_count": len(disagreement_items),
        "reviewed_row_count": len(reviewed_items),
        "reviewed_alignment_precision": round(reviewed_alignment_precision, 6),
        "mean_disagreement_count": round(mean_disagreement_count, 6),
        "recommended_action_counts": dict(sorted(recommended_action_counts.items())),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the Gemini-first TTFM brain loop end-to-end with a single command."
    )
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--framework-slug", default="ttfm")
    parser.add_argument("--profile-slug", default="ttrades_curriculum")
    parser.add_argument("--brain-type", default="setup_scorer")
    parser.add_argument("--review-packet-limit", type=int, default=10)
    parser.add_argument("--skip-corpus-refresh", action="store_true")
    parser.add_argument("--skip-review-packets", action="store_true")
    parser.add_argument("--skip-improvement-plan", action="store_true")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--history-output", default=str(DEFAULT_HISTORY_PATH))
    args = parser.parse_args()

    corpus_refresh_stage: dict[str, Any] | None = None
    if not args.skip_corpus_refresh:
        run_script_stage(
            python_executable=args.python,
            script_name="refresh_ttfm_video_corpus.py",
            args=[],
        )
        corpus_refresh_stage = load_json(DEFAULT_CORPUS_REFRESH_REPORT_PATH, {})

    text_embedding_stage = maybe_refresh_text_embedding_index()
    visual_embedding_stage = maybe_refresh_visual_embedding_index()

    run_script_stage(
        python_executable=args.python,
        script_name="run_ttfm_visual_teacher_loop.py",
        args=[],
    )
    visual_loop_report = load_json(DEFAULT_VISUAL_LOOP_REPORT_PATH, {})

    run_script_stage(
        python_executable=args.python,
        script_name="run_ttfm_multimodal_teacher_loop.py",
        args=[
            "--device",
            args.device,
            "--framework-slug",
            args.framework_slug,
            "--profile-slug",
            args.profile_slug,
            "--brain-type",
            args.brain_type,
        ],
    )
    multimodal_loop_report = load_json(DEFAULT_MULTIMODAL_LOOP_REPORT_PATH, {})
    review_queue = load_json(DEFAULT_REVIEW_QUEUE_PATH, {"summary": {}, "items": []})

    failed_optional_stages: list[str] = []
    review_packets: dict[str, Any] | None = None
    if not args.skip_review_packets:
        try:
            run_script_stage(
                python_executable=args.python,
                script_name="export_ttfm_brain_review_packets.py",
                args=[
                    "--limit",
                    str(args.review_packet_limit),
                ],
            )
            review_packets = load_json(DEFAULT_REVIEW_PACKETS_PATH, {"summary": {}, "packets": []})
        except subprocess.CalledProcessError:
            failed_optional_stages.append("review_packets")

    improvement_plan: dict[str, Any] | None = None
    if not args.skip_improvement_plan:
        try:
            output_path = Path(args.output)
            temporary_report = build_brain_loop_report(
                framework_slug=args.framework_slug,
                profile_slug=args.profile_slug,
                brain_type=args.brain_type,
                status="ok",
                corpus_refresh_stage=corpus_refresh_stage,
                text_embedding_stage=text_embedding_stage,
                visual_embedding_stage=visual_embedding_stage,
                visual_loop_report=visual_loop_report,
                multimodal_loop_report=multimodal_loop_report,
                review_queue=review_queue,
                trade_review_readiness=summarize_partition_readiness(
                    review_queue,
                    corpus_partition="trade_review",
                ),
                review_packets=review_packets,
                improvement_plan=None,
                failed_optional_stages=failed_optional_stages,
                pine_status="deferred",
                healthy_streak=0,
            )
            write_json(output_path, temporary_report)
            run_script_stage(
                python_executable=args.python,
                script_name="export_ttfm_brain_improvement_plan.py",
                args=[
                    "--brain-loop-report",
                    str(output_path),
                ],
            )
            improvement_plan = load_json(DEFAULT_IMPROVEMENT_PLAN_PATH, {})
        except subprocess.CalledProcessError:
            failed_optional_stages.append("improvement_plan")

    status = "degraded" if failed_optional_stages else "ok"
    history_entries = load_history_entries(Path(args.history_output))
    trade_review_readiness = summarize_partition_readiness(
        review_queue,
        corpus_partition="trade_review",
    )
    healthy, pine_gate_status = compute_health_flags(
        status=status,
        review_queue=review_queue,
        multimodal_loop_report=multimodal_loop_report,
        trade_review_readiness=trade_review_readiness,
    )
    healthy_streak = compute_healthy_streak(history_entries, healthy)
    if pine_gate_status == "deferred":
        pine_status = "deferred"
    elif healthy and healthy_streak >= 2:
        pine_status = "ready_for_translation"
    else:
        pine_status = "not_ready"

    final_report = build_brain_loop_report(
        framework_slug=args.framework_slug,
        profile_slug=args.profile_slug,
        brain_type=args.brain_type,
        status=status,
        corpus_refresh_stage=corpus_refresh_stage,
        text_embedding_stage=text_embedding_stage,
        visual_embedding_stage=visual_embedding_stage,
        visual_loop_report=visual_loop_report,
        multimodal_loop_report=multimodal_loop_report,
        review_queue=review_queue,
        trade_review_readiness=trade_review_readiness,
        review_packets=review_packets,
        improvement_plan=improvement_plan,
        failed_optional_stages=failed_optional_stages,
        pine_status=pine_status,
        healthy_streak=healthy_streak,
    )
    output_path = Path(args.output)
    write_json(output_path, final_report)
    append_history_entry(
        Path(args.history_output),
        {
            "run_generated_at": final_report["generated_at"],
            "status": status,
            "healthy": healthy,
            "pine_status": pine_status,
            "reviewed_alignment_precision": final_report["review_queue"].get(
                "reviewed_alignment_precision"
            ),
            "mean_disagreement_count": final_report["review_queue"].get(
                "mean_disagreement_count"
            ),
            "validation_micro_precision": final_report["multimodal_model"].get(
                "validation_micro_precision"
            ),
        },
    )

    print(
        json.dumps(
            {
                "output": str(output_path),
                "status": status,
                "pine_status": pine_status,
                "next_action": final_report["next_action"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
