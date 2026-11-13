from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


from config import AppConfig, build_config
from scripts.append_live_tradingview_decision_journal import DEFAULT_JOURNAL_PATH
from scripts.build_live_tradingview_decision_report import DEFAULT_OUTPUT_PATH as DEFAULT_DECISION_REPORT_PATH
from scripts.build_live_tradingview_visual_markup import DEFAULT_REQUEST_PATH as DEFAULT_MARKUP_REQUEST_PATH
from scripts.build_manual_tradingview_decision_packet import (
    DEFAULT_OUTPUT_PATH as DEFAULT_PACKET_PATH,
    build_manual_packet,
    resolve,
)
from scripts.render_live_tradingview_decision_brief import DEFAULT_OUTPUT_PATH as DEFAULT_BRIEF_PATH
from scripts.run_live_tradingview_decision_pipeline import (
    DEFAULT_PIPELINE_REPORT_PATH,
    run_live_decision_pipeline,
)
from scripts.run_live_tradingview_vlm_markup import (
    DEFAULT_MARKUP_OUTPUT_PATH as DEFAULT_VLM_MARKUP_OUTPUT_PATH,
    DEFAULT_RAW_RESPONSE_PATH as DEFAULT_VLM_RAW_RESPONSE_PATH,
)


DEFAULT_RUN_REPORT_PATH = Path("results") / "manual_tradingview_decision_run_report.json"
PipelineFunc = Callable[..., dict[str, Any]]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def relative_or_absolute(path: Path, root_dir: Path) -> str:
    try:
        return str(path.resolve().relative_to(root_dir.resolve()))
    except ValueError:
        return str(path.resolve())


def run_manual_decision_pipeline(
    *,
    config: AppConfig,
    symbol: str,
    daily_path: Path,
    h1_path: Path,
    m5_path: Path,
    packet_path: Path,
    markup_request_path: Path,
    decision_report_path: Path,
    pipeline_report_path: Path,
    run_report_path: Path,
    source_note: str = "",
    markup_path: Path | None = None,
    call_vlm: bool = False,
    vlm_markup_output_path: Path | None = None,
    vlm_raw_response_path: Path | None = None,
    vlm_model: str = "gpt-5.4-pro",
    vlm_timeout_seconds: int = 180,
    render_brief: bool = False,
    brief_path: Path | None = None,
    append_journal: bool = False,
    journal_path: Path | None = None,
    journal_notes: list[str] | None = None,
    journal_follow_up_labels: list[str] | None = None,
    allow_blocked_packet: bool = False,
    max_retrieval_hits: int = 6,
    pipeline_func: PipelineFunc = run_live_decision_pipeline,
) -> dict[str, Any]:
    if markup_path is not None and call_vlm:
        raise ValueError("Use either markup_path or call_vlm, not both.")

    packet = build_manual_packet(
        root_dir=config.root_dir,
        symbol=symbol,
        daily_path=daily_path,
        h1_path=h1_path,
        m5_path=m5_path,
        source_note=source_note,
    )
    write_json(packet_path, packet)

    run_report: dict[str, Any] = {
        "mode": "manual_tradingview_decision_pipeline",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol,
        "packet_path": relative_or_absolute(packet_path, config.root_dir),
        "decision_ready": bool(packet.get("decision_ready")),
        "blocked_reasons": packet.get("blocked_reasons", []),
        "pipeline_executed": False,
        "pipeline_report_path": "",
        "decision_report_path": "",
        "markup_request_path": "",
        "brief_path": "",
        "journal_path": "",
        "verdict": "insufficient_evidence",
        "confidence": 0.0,
        "next_action": "continue_to_visual_markup" if packet.get("decision_ready") else "recapture_manual_screenshots",
    }

    if not packet.get("decision_ready") and not allow_blocked_packet:
        write_json(run_report_path, run_report)
        return run_report

    pipeline_report = pipeline_func(
        config=config,
        packet_path=packet_path,
        markup_request_path=markup_request_path,
        decision_report_path=decision_report_path,
        pipeline_report_path=pipeline_report_path,
        brief_path=brief_path,
        journal_path=journal_path,
        markup_path=markup_path,
        call_vlm=call_vlm,
        vlm_markup_output_path=vlm_markup_output_path,
        vlm_raw_response_path=vlm_raw_response_path,
        vlm_model=vlm_model,
        vlm_timeout_seconds=vlm_timeout_seconds,
        skip_capture=True,
        render_brief=render_brief,
        append_journal=append_journal,
        journal_notes=journal_notes or [],
        journal_follow_up_labels=journal_follow_up_labels or [],
        max_retrieval_hits=max_retrieval_hits,
    )
    run_report.update(
        {
            "pipeline_executed": True,
            "pipeline_report_path": relative_or_absolute(pipeline_report_path, config.root_dir),
            "decision_report_path": relative_or_absolute(decision_report_path, config.root_dir),
            "markup_request_path": relative_or_absolute(markup_request_path, config.root_dir),
            "brief_path": str(pipeline_report.get("brief_path", "")),
            "journal_path": str(pipeline_report.get("journal_path", "")),
            "verdict": pipeline_report.get("verdict", "insufficient_evidence"),
            "confidence": pipeline_report.get("confidence", 0.0),
            "next_action": pipeline_report.get("next_action", ""),
            "markup_verified": pipeline_report.get("markup_verified", False),
            "warnings": pipeline_report.get("warnings", []),
        }
    )
    write_json(run_report_path, run_report)
    return run_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the standardized manual TradingView Daily/H1/M5 decision pipeline.")
    parser.add_argument("--root-dir", type=Path, default=Path("."))
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--daily", type=Path, required=True)
    parser.add_argument("--h1", type=Path, required=True)
    parser.add_argument("--m5", type=Path, required=True)
    parser.add_argument("--source-note", default="")
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    parser.add_argument("--markup-request", type=Path, default=DEFAULT_MARKUP_REQUEST_PATH)
    parser.add_argument("--decision-report", type=Path, default=DEFAULT_DECISION_REPORT_PATH)
    parser.add_argument("--pipeline-report", type=Path, default=DEFAULT_PIPELINE_REPORT_PATH)
    parser.add_argument("--run-report", type=Path, default=DEFAULT_RUN_REPORT_PATH)
    parser.add_argument("--markup", type=Path, default=None, help="Optional verified visual markup JSON to import.")
    parser.add_argument("--call-vlm", action="store_true", help="Call the configured VLM to fill visual markup.")
    parser.add_argument("--vlm-markup-output", type=Path, default=DEFAULT_VLM_MARKUP_OUTPUT_PATH)
    parser.add_argument("--vlm-raw-response", type=Path, default=DEFAULT_VLM_RAW_RESPONSE_PATH)
    parser.add_argument("--vlm-model", default="gpt-5.4-pro")
    parser.add_argument("--vlm-timeout-seconds", type=int, default=180)
    parser.add_argument("--render-brief", action="store_true")
    parser.add_argument("--brief", type=Path, default=DEFAULT_BRIEF_PATH)
    parser.add_argument("--append-journal", action="store_true")
    parser.add_argument("--journal", type=Path, default=DEFAULT_JOURNAL_PATH)
    parser.add_argument("--journal-note", action="append", default=[])
    parser.add_argument("--journal-follow-up-label", action="append", default=[])
    parser.add_argument("--allow-blocked-packet", action="store_true")
    parser.add_argument("--max-retrieval-hits", type=int, default=6)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root_dir = args.root_dir.resolve()
    config = build_config(root_dir=root_dir)
    report = run_manual_decision_pipeline(
        config=config,
        symbol=args.symbol,
        daily_path=resolve(root_dir, args.daily),
        h1_path=resolve(root_dir, args.h1),
        m5_path=resolve(root_dir, args.m5),
        packet_path=resolve(root_dir, args.packet),
        markup_request_path=resolve(root_dir, args.markup_request),
        decision_report_path=resolve(root_dir, args.decision_report),
        pipeline_report_path=resolve(root_dir, args.pipeline_report),
        run_report_path=resolve(root_dir, args.run_report),
        source_note=args.source_note,
        markup_path=resolve(root_dir, args.markup) if args.markup is not None else None,
        call_vlm=args.call_vlm,
        vlm_markup_output_path=resolve(root_dir, args.vlm_markup_output),
        vlm_raw_response_path=resolve(root_dir, args.vlm_raw_response),
        vlm_model=args.vlm_model,
        vlm_timeout_seconds=args.vlm_timeout_seconds,
        render_brief=args.render_brief,
        brief_path=resolve(root_dir, args.brief),
        append_journal=args.append_journal,
        journal_path=resolve(root_dir, args.journal),
        journal_notes=args.journal_note,
        journal_follow_up_labels=args.journal_follow_up_label,
        allow_blocked_packet=args.allow_blocked_packet,
        max_retrieval_hits=args.max_retrieval_hits,
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
