from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import build_ttfm_daily_intake as btdi
import evaluate_ttfm_frozen_benchmark as etfb
import export_ttfm_brain_dashboard as etbd
import export_ttfm_dense_review_samples as etdrs
import export_ttfm_progress_snapshot as etps
import refresh_ttfm_video_corpus as rtvc
import run_ttfm_brain_loop as rtbl


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "results" / "ttfm_brain_workflow_report.json"
DEFAULT_HISTORY_PATH = ROOT / "results" / "ttfm_brain_workflow_history.jsonl"
DEFAULT_DASHBOARD_PATH = ROOT / "results" / "ttfm_brain_dashboard.html"
DEFAULT_SNAPSHOT_PATH = ROOT / "results" / "ttfm_progress_snapshot.md"
DEFAULT_BENCHMARK_OUTPUT = ROOT / "results" / "ttfm_frozen_benchmark_pack.jsonl"
DEFAULT_DENSE_REVIEW_OUTPUT = ROOT / "results" / "ttfm_dense_review_samples.jsonl"
DEFAULT_DENSE_REVIEW_REPORT = ROOT / "results" / "ttfm_dense_review_samples_report.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return dict(default or {})
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue
        payload = json.loads(cleaned)
        if isinstance(payload, dict):
            entries.append(payload)
    return entries


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def append_history_entry(path: Path, entry: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")


def normalize_embedding_stage(stage_payload: dict[str, Any]) -> dict[str, Any]:
    stage_status = str(stage_payload.get("status", "")).strip()
    normalized_status = "cache_hit" if stage_status == "reused" else "ran"
    return {
        "status": normalized_status,
        "item_count": int(stage_payload.get("item_count", stage_payload.get("expected_count", 0)) or 0),
        "manifest_path": stage_payload.get("manifest_path"),
        "index_path": stage_payload.get("index_path"),
    }


def stage_record(
    *,
    name: str,
    status: str,
    started_at: str,
    ended_at: str,
    counts: dict[str, Any] | None = None,
    output_paths: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "started_at": started_at,
        "ended_at": ended_at,
        "counts": counts or {},
        "output_paths": output_paths or {},
    }


def top_disagreement_cases(review_queue: dict[str, Any], *, limit: int = 10) -> list[dict[str, Any]]:
    items = review_queue.get("items", [])
    if not isinstance(items, list):
        return []
    return [dict(item) for item in items[:limit]]


def build_workflow_report(
    *,
    prior_history_entry: dict[str, Any] | None,
    intake_report: dict[str, Any],
    corpus_refresh_report: dict[str, Any],
    text_embedding_stage: dict[str, Any],
    visual_embedding_stage: dict[str, Any],
    multimodal_loop_report: dict[str, Any],
    review_queue: dict[str, Any],
    benchmark_build_report: dict[str, Any],
    champion_evaluation: dict[str, Any],
    challenger_evaluation: dict[str, Any],
    dense_review_report: dict[str, Any],
    stages: list[dict[str, Any]],
    outputs: dict[str, str],
) -> dict[str, Any]:
    prior_corpus = dict((prior_history_entry or {}).get("corpus", {}))
    active_manifest = dict(corpus_refresh_report.get("active_manifest", {}))
    weak_multimodal = dict(multimodal_loop_report.get("weak_multimodal_dataset", {}))
    blended_multimodal = dict(multimodal_loop_report.get("blended_multimodal_dataset", {}))
    benchmark_comparison = etfb.compare_benchmark_metrics(
        champion=champion_evaluation,
        challenger=challenger_evaluation,
    )

    current_video_count = int(active_manifest.get("video_count", 0) or 0)
    prior_video_count = int(prior_corpus.get("current_video_count", 0) or 0)
    trainable_row_count = int(weak_multimodal.get("eligible_for_training_count", 0) or 0)
    weak_row_count = int(weak_multimodal.get("row_count", 0) or 0)
    blocked_row_count = max(0, weak_row_count - trainable_row_count)

    return {
        "generated_at": now_iso(),
        "corpus": {
            "current_video_count": current_video_count,
            "prior_video_count": prior_video_count,
            "delta_video_count": current_video_count - prior_video_count,
            "partition_counts": dict(active_manifest.get("partition_counts", {})),
            "discovery_source_counts": dict(active_manifest.get("discovery_source_counts", {})),
        },
        "daily_intake": dict(intake_report.get("summary", {})),
        "embeddings": {
            "text": dict(text_embedding_stage),
            "visual": dict(visual_embedding_stage),
        },
        "trainability": {
            "weak_row_count": weak_row_count,
            "trainable_row_count": trainable_row_count,
            "blocked_row_count": blocked_row_count,
            "blocked_reason_counts": dict(weak_multimodal.get("training_blocker_counts", {})),
            "blended_row_count": int(blended_multimodal.get("row_count", 0) or 0),
            "excluded_weak_row_count": int(blended_multimodal.get("excluded_weak_row_count", 0) or 0),
        },
        "frozen_benchmark": {
            "benchmark_row_count": int(benchmark_build_report.get("row_count", 0) or 0),
            "benchmark_status": benchmark_build_report.get("status"),
            "champion": champion_evaluation,
            "challenger": challenger_evaluation,
            "comparison": benchmark_comparison,
        },
        "review_queue": dict(review_queue.get("summary", {})),
        "dense_review": dict(dense_review_report),
        "top_disagreement_cases": top_disagreement_cases(review_queue),
        "stages": stages,
        "outputs": outputs,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the full TTFM Brain Workflow v2.")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--history-output", type=Path, default=DEFAULT_HISTORY_PATH)
    parser.add_argument("--dashboard-output", type=Path, default=DEFAULT_DASHBOARD_PATH)
    parser.add_argument("--snapshot-output", type=Path, default=DEFAULT_SNAPSHOT_PATH)
    parser.add_argument("--benchmark-output", type=Path, default=DEFAULT_BENCHMARK_OUTPUT)
    args = parser.parse_args()

    history_entries = load_jsonl(args.history_output)
    prior_history_entry = history_entries[-1] if history_entries else {}
    stages: list[dict[str, Any]] = []

    started_at = now_iso()
    intake_report = btdi.scan_daily_intake(
        intake_videos_dir=btdi.DEFAULT_INTAKE_VIDEOS_DIR,
        intake_images_dir=btdi.DEFAULT_INTAKE_IMAGES_DIR,
        video_manifest_output=btdi.DEFAULT_VIDEO_MANIFEST_OUTPUT,
        image_cases_output=btdi.DEFAULT_IMAGE_CASES_OUTPUT,
        report_output=btdi.DEFAULT_REPORT_OUTPUT,
    )
    stages.append(
        stage_record(
            name="daily_intake",
            status="ran",
            started_at=started_at,
            ended_at=now_iso(),
            counts=dict(intake_report.get("summary", {})),
            output_paths={
                "video_manifest_output": str(btdi.DEFAULT_VIDEO_MANIFEST_OUTPUT),
                "image_cases_output": str(btdi.DEFAULT_IMAGE_CASES_OUTPUT),
                "report_output": str(btdi.DEFAULT_REPORT_OUTPUT),
            },
        )
    )

    started_at = now_iso()
    corpus_refresh_report = rtvc.refresh_corpus(
        channel_url=rtvc.dtrv.DEFAULT_CHANNEL_URL,
        yt_dlp_bin="yt-dlp",
        include_review_categories=set(rtvc.dtrv.REVIEW_CATEGORY_PATTERNS),
        include_educational_categories=set(rtvc.dtrv.EDUCATIONAL_CATEGORY_PATTERNS),
        output_dir=rtvc.CORPUS_DIR,
        inventory_output=rtvc.DEFAULT_CHANNEL_INVENTORY_PATH,
        trade_review_manifest_output=rtvc.DEFAULT_TRADE_REVIEW_MANIFEST_PATH,
        educational_manifest_output=rtvc.DEFAULT_EDUCATIONAL_MANIFEST_PATH,
        active_manifest_output=rtvc.DEFAULT_ACTIVE_MANIFEST_PATH,
        intake_video_manifest_path=btdi.DEFAULT_VIDEO_MANIFEST_OUTPUT,
        video_dir=rtvc.dtyv.DEFAULT_VIDEO_DIR,
        video_download_report_output=rtvc.DEFAULT_VIDEO_DOWNLOAD_REPORT_OUTPUT,
        windows_output=rtvc.DEFAULT_WINDOWS_OUTPUT,
        windows_report_output=rtvc.DEFAULT_WINDOWS_REPORT_OUTPUT,
        weak_dataset_output=rtvc.DEFAULT_WEAK_DATASET_OUTPUT,
        weak_dataset_report_output=rtvc.DEFAULT_WEAK_DATASET_REPORT_OUTPUT,
        report_output=rtvc.DEFAULT_REPORT_OUTPUT,
        ffmpeg_bin="ffmpeg",
        extract_frames=True,
        overwrite_transcripts=False,
        overwrite_videos=False,
    )
    stages.append(
        stage_record(
            name="corpus_refresh",
            status="ran",
            started_at=started_at,
            ended_at=now_iso(),
            counts={
                "video_count": corpus_refresh_report.get("active_manifest", {}).get("video_count", 0),
            },
            output_paths={"report_output": str(rtvc.DEFAULT_REPORT_OUTPUT)},
        )
    )

    started_at = now_iso()
    text_embedding_payload = rtbl.maybe_refresh_text_embedding_index()
    text_embedding_stage = normalize_embedding_stage(text_embedding_payload)
    stages.append(
        stage_record(
            name="text_embeddings",
            status=text_embedding_stage["status"],
            started_at=started_at,
            ended_at=now_iso(),
            counts={"item_count": text_embedding_stage["item_count"]},
            output_paths={"manifest_path": str(text_embedding_stage.get("manifest_path"))},
        )
    )

    started_at = now_iso()
    visual_embedding_payload = rtbl.maybe_refresh_visual_embedding_index()
    visual_embedding_stage = normalize_embedding_stage(visual_embedding_payload)
    stages.append(
        stage_record(
            name="visual_embeddings",
            status=visual_embedding_stage["status"],
            started_at=started_at,
            ended_at=now_iso(),
            counts={"item_count": visual_embedding_stage["item_count"]},
            output_paths={"manifest_path": str(visual_embedding_stage.get("manifest_path"))},
        )
    )

    started_at = now_iso()
    rtbl.run_script_stage(
        python_executable=args.python,
        script_name="run_ttfm_visual_teacher_loop.py",
        args=[],
    )
    stages.append(
        stage_record(
            name="visual_teacher_loop",
            status="ran",
            started_at=started_at,
            ended_at=now_iso(),
            output_paths={"report_output": str(rtbl.DEFAULT_VISUAL_LOOP_REPORT_PATH)},
        )
    )

    teacher_rows = etfb.load_jsonl(etfb.DEFAULT_TEACHER_DATASET_PATH)
    existing_weak_rows = etfb.load_jsonl(etfb.DEFAULT_WEAK_DATASET_PATH)
    existing_review_queue = etfb.load_json(etfb.DEFAULT_REVIEW_QUEUE_PATH, {"items": []})

    started_at = now_iso()
    benchmark_build_report = etfb.ensure_frozen_benchmark_pack(
        benchmark_output=args.benchmark_output,
        teacher_rows=teacher_rows,
        weak_rows=existing_weak_rows,
        review_queue=existing_review_queue,
        force_rebuild=False,
    )
    benchmark_rows = etfb.load_jsonl(args.benchmark_output)
    stages.append(
        stage_record(
            name="frozen_benchmark",
            status=str(benchmark_build_report.get("status", "ran")),
            started_at=started_at,
            ended_at=now_iso(),
            counts={"row_count": benchmark_build_report.get("row_count", 0)},
            output_paths={"benchmark_output": str(args.benchmark_output)},
        )
    )

    current_model_path = etfb.DEFAULT_REPORT_OUTPUT.parent / "neural_models" / "ttfm_blended_multimodal" / "ttfm_blended_multimodal_pattern_net.pt"
    if not current_model_path.exists():
        current_model_path = ROOT / "results" / "neural_models" / "ttfm_blended_multimodal" / "ttfm_blended_multimodal_pattern_net.pt"
    started_at = now_iso()
    champion_evaluation = etfb.evaluate_model_against_benchmark(
        model_path=current_model_path,
        benchmark_rows=benchmark_rows,
        device_preference=args.device,
    )
    stages.append(
        stage_record(
            name="champion_benchmark_eval",
            status=str(champion_evaluation.get("status", "skipped")),
            started_at=started_at,
            ended_at=now_iso(),
            counts={"scored_example_count": champion_evaluation.get("scored_example_count", 0)},
            output_paths={"model_path": str(current_model_path)},
        )
    )

    started_at = now_iso()
    multimodal_args = [
        "--device",
        args.device,
        "--framework-slug",
        "ttfm",
        "--profile-slug",
        "ttrades_curriculum",
        "--brain-type",
        "setup_scorer",
    ]
    if btdi.DEFAULT_IMAGE_CASES_OUTPUT.exists():
        multimodal_args.extend(
            [
                "--additional-weak-multimodal-dataset",
                str(btdi.DEFAULT_IMAGE_CASES_OUTPUT),
            ]
        )
    rtbl.run_script_stage(
        python_executable=args.python,
        script_name="run_ttfm_multimodal_teacher_loop.py",
        args=multimodal_args,
    )
    multimodal_loop_report = load_json(rtbl.DEFAULT_MULTIMODAL_LOOP_REPORT_PATH, {})
    review_queue = load_json(rtbl.DEFAULT_REVIEW_QUEUE_PATH, {"summary": {}, "items": []})
    stages.append(
        stage_record(
            name="multimodal_teacher_loop",
            status="ran",
            started_at=started_at,
            ended_at=now_iso(),
            counts={
                "weak_row_count": multimodal_loop_report.get("weak_multimodal_dataset", {}).get("row_count", 0),
            },
            output_paths={
                "report_output": str(rtbl.DEFAULT_MULTIMODAL_LOOP_REPORT_PATH),
                "review_queue_output": str(rtbl.DEFAULT_REVIEW_QUEUE_PATH),
            },
        )
    )

    started_at = now_iso()
    dense_samples, dense_review_report = etdrs.build_dense_review_samples(
        review_queue_items=etdrs.normalize_review_queue_items(review_queue),
        multimodal_rows=etdrs.load_jsonl(etdrs.DEFAULT_MULTIMODAL_DATASET_PATH),
        frame_output_dir=etdrs.DEFAULT_FRAME_OUTPUT_DIR,
        audio_output_dir=etdrs.DEFAULT_AUDIO_OUTPUT_DIR,
    )
    dense_review_report.update(etdrs.materialize_dense_review_samples(dense_samples, ffmpeg_bin="ffmpeg"))
    etdrs.write_jsonl(DEFAULT_DENSE_REVIEW_OUTPUT, dense_samples)
    etdrs.write_json(DEFAULT_DENSE_REVIEW_REPORT, dense_review_report)
    stages.append(
        stage_record(
            name="dense_review_samples",
            status="ran",
            started_at=started_at,
            ended_at=now_iso(),
            counts={"sample_count": dense_review_report.get("sample_count", 0)},
            output_paths={
                "output": str(DEFAULT_DENSE_REVIEW_OUTPUT),
                "report_output": str(DEFAULT_DENSE_REVIEW_REPORT),
            },
        )
    )

    challenger_model_path = ROOT / "results" / "neural_models" / "ttfm_blended_multimodal" / "ttfm_blended_multimodal_pattern_net.pt"
    started_at = now_iso()
    challenger_evaluation = etfb.evaluate_model_against_benchmark(
        model_path=challenger_model_path,
        benchmark_rows=benchmark_rows,
        device_preference=args.device,
    )
    stages.append(
        stage_record(
            name="challenger_benchmark_eval",
            status=str(challenger_evaluation.get("status", "skipped")),
            started_at=started_at,
            ended_at=now_iso(),
            counts={"scored_example_count": challenger_evaluation.get("scored_example_count", 0)},
            output_paths={"model_path": str(challenger_model_path)},
        )
    )

    outputs = {
        "dashboard": str(args.dashboard_output).replace("\\", "/"),
        "snapshot": str(args.snapshot_output).replace("\\", "/"),
        "report": str(args.output).replace("\\", "/"),
        "history": str(args.history_output).replace("\\", "/"),
    }
    workflow_report = build_workflow_report(
        prior_history_entry=prior_history_entry,
        intake_report=intake_report,
        corpus_refresh_report=corpus_refresh_report,
        text_embedding_stage=text_embedding_stage,
        visual_embedding_stage=visual_embedding_stage,
        multimodal_loop_report=multimodal_loop_report,
        review_queue=review_queue,
        benchmark_build_report=benchmark_build_report,
        champion_evaluation=champion_evaluation,
        challenger_evaluation=challenger_evaluation,
        dense_review_report=dense_review_report,
        stages=stages,
        outputs=outputs,
    )
    write_json(args.output, workflow_report)
    append_history_entry(args.history_output, workflow_report)

    dashboard_html = etbd.build_dashboard_html(workflow_report, history_entries + [workflow_report])
    args.dashboard_output.parent.mkdir(parents=True, exist_ok=True)
    args.dashboard_output.write_text(dashboard_html, encoding="utf-8")

    snapshot_text = etps.build_workflow_snapshot(workflow_report)
    args.snapshot_output.parent.mkdir(parents=True, exist_ok=True)
    args.snapshot_output.write_text(snapshot_text, encoding="utf-8")

    print(json.dumps({"report_output": str(args.output), "dashboard_output": str(args.dashboard_output), "snapshot_output": str(args.snapshot_output)}, indent=2))


if __name__ == "__main__":
    main()
