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
from labeler.tradingview_weak_labeler import capture_live_tradingview_bundle
from scripts.build_live_tradingview_decision_report import (
    DEFAULT_OUTPUT_PATH as DEFAULT_DECISION_REPORT_PATH,
    build_decision_report,
    load_json,
    resolve,
)
from scripts.build_live_tradingview_visual_markup import (
    DEFAULT_REQUEST_PATH as DEFAULT_MARKUP_REQUEST_PATH,
    attach_visual_markup,
    build_markup_request,
    validate_visual_markup,
)
from scripts.check_live_tradingview_decision_preflight import (
    DEFAULT_OUTPUT_PATH as DEFAULT_PREFLIGHT_REPORT_PATH,
    build_preflight_report,
)
from scripts.append_live_tradingview_decision_journal import (
    DEFAULT_JOURNAL_PATH,
    append_event,
    build_journal_event,
)
from scripts.render_live_tradingview_decision_brief import (
    DEFAULT_OUTPUT_PATH as DEFAULT_BRIEF_PATH,
    write_brief,
)
from scripts.run_live_tradingview_vlm_markup import (
    DEFAULT_MARKUP_OUTPUT_PATH as DEFAULT_VLM_MARKUP_OUTPUT_PATH,
    DEFAULT_RAW_RESPONSE_PATH as DEFAULT_VLM_RAW_RESPONSE_PATH,
    run_vlm_markup,
)


DEFAULT_PACKET_PATH = Path("results") / "live_tradingview_decision_packet.json"
DEFAULT_PIPELINE_REPORT_PATH = Path("results") / "live_tradingview_decision_pipeline_report.json"
CaptureFunc = Callable[..., dict[str, Any]]
VlmFunc = Callable[..., dict[str, Any]]
PreflightFunc = Callable[..., dict[str, Any]]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def relative_or_absolute(path: Path, root_dir: Path) -> str:
    try:
        return str(path.resolve().relative_to(root_dir.resolve()))
    except ValueError:
        return str(path.resolve())


def finalize_optional_outputs(
    *,
    config: AppConfig,
    decision_report_path: Path,
    pipeline_report_path: Path,
    brief_path: Path,
    journal_path: Path,
    render_brief: bool,
    append_journal: bool,
    journal_notes: list[str] | None = None,
    journal_follow_up_labels: list[str] | None = None,
) -> dict[str, Any]:
    outputs: dict[str, Any] = {
        "brief_rendered": False,
        "brief_path": "",
        "journal_appended": False,
        "journal_path": "",
        "journal_event_id": "",
    }
    if render_brief:
        summary = write_brief(
            root_dir=config.root_dir,
            decision_report_path=decision_report_path,
            pipeline_report_path=pipeline_report_path,
            output_path=brief_path,
        )
        outputs["brief_rendered"] = True
        outputs["brief_path"] = relative_or_absolute(Path(summary["output_path"]), config.root_dir)
    if append_journal:
        event = build_journal_event(
            root_dir=config.root_dir,
            decision_report_path=decision_report_path,
            pipeline_report_path=pipeline_report_path,
            decision_report=load_json(decision_report_path, {}),
            pipeline_report=load_json(pipeline_report_path, {}),
            notes=journal_notes or [],
            follow_up_labels=journal_follow_up_labels or [],
        )
        append_event(journal_path, event)
        outputs["journal_appended"] = True
        outputs["journal_path"] = relative_or_absolute(journal_path, config.root_dir)
        outputs["journal_event_id"] = str(event.get("event_id", ""))
    return outputs


def run_live_decision_pipeline(
    *,
    config: AppConfig,
    packet_path: Path,
    markup_request_path: Path,
    decision_report_path: Path,
    pipeline_report_path: Path,
    preflight_report_path: Path | None = None,
    brief_path: Path | None = None,
    journal_path: Path | None = None,
    markup_path: Path | None = None,
    preflight: bool = False,
    preflight_timeout_seconds: int = 8,
    render_brief: bool = False,
    append_journal: bool = False,
    journal_notes: list[str] | None = None,
    journal_follow_up_labels: list[str] | None = None,
    call_vlm: bool = False,
    vlm_markup_output_path: Path | None = None,
    vlm_raw_response_path: Path | None = None,
    vlm_model: str = "gpt-5.4-pro",
    vlm_timeout_seconds: int = 180,
    skip_capture: bool = False,
    allow_quality_fail: bool = False,
    max_quality_attempts: int = 2,
    retry_delay_seconds: float = 1.0,
    max_retrieval_hits: int = 6,
    capture_func: CaptureFunc = capture_live_tradingview_bundle,
    vlm_func: VlmFunc = run_vlm_markup,
    preflight_func: PreflightFunc = build_preflight_report,
) -> dict[str, Any]:
    if markup_path is not None and call_vlm:
        raise ValueError("Use either markup_path or call_vlm, not both.")
    preflight_report: dict[str, Any] | None = None
    preflight_output_path = preflight_report_path or (config.root_dir / DEFAULT_PREFLIGHT_REPORT_PATH)
    resolved_brief_path = brief_path or (config.root_dir / DEFAULT_BRIEF_PATH)
    resolved_journal_path = journal_path or (config.root_dir / DEFAULT_JOURNAL_PATH)
    if preflight:
        preflight_report = preflight_func(
            root_dir=config.root_dir,
            packet_path=packet_path,
            timeout_seconds=preflight_timeout_seconds,
            require_packet=skip_capture,
            require_openai_key=call_vlm,
        )
        write_json(preflight_output_path, preflight_report)
        if not preflight_report.get("ready"):
            pipeline_report = {
                "mode": "live_tradingview_decision_pipeline",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "capture_executed": False,
                "capture_report_path": "",
                "preflight_executed": True,
                "preflight_report_path": relative_or_absolute(preflight_output_path, config.root_dir),
                "preflight_ready": False,
                "preflight_blocking_checks": [
                    str(check.get("name", "")) for check in preflight_report.get("blocking_checks", [])
                ],
                "preflight_warning_checks": [
                    str(check.get("name", "")) for check in preflight_report.get("warning_checks", [])
                ],
                "packet_path": relative_or_absolute(packet_path, config.root_dir),
                "markup_request_path": "",
                "markup_imported": False,
                "markup_status": "",
                "markup_verified": False,
                "vlm_called": False,
                "vlm_status": "",
                "decision_report_path": "",
                "verdict": "insufficient_evidence",
                "confidence": 0.0,
                "decision_ready": False,
                "warnings": ["preflight_blocked"],
                "next_action": "fix_preflight_blockers",
            }
            write_json(pipeline_report_path, pipeline_report)
            pipeline_report.update(
                finalize_optional_outputs(
                    config=config,
                    decision_report_path=decision_report_path,
                    pipeline_report_path=pipeline_report_path,
                    brief_path=resolved_brief_path,
                    journal_path=resolved_journal_path,
                    render_brief=render_brief,
                    append_journal=append_journal,
                    journal_notes=journal_notes,
                    journal_follow_up_labels=journal_follow_up_labels,
                )
            )
            write_json(pipeline_report_path, pipeline_report)
            return pipeline_report

    capture_report: dict[str, Any] | None = None
    if not skip_capture:
        capture_report = capture_func(
            config,
            allow_quality_fail=allow_quality_fail,
            max_quality_attempts=max_quality_attempts,
            retry_delay_seconds=retry_delay_seconds,
        )
        packet_path = Path(str(capture_report.get("decision_packet_path") or packet_path))

    packet = load_json(packet_path, {})
    if not isinstance(packet, dict) or not packet:
        raise FileNotFoundError(f"Decision packet not found or invalid: {packet_path}")

    markup_request = build_markup_request(packet, root_dir=config.root_dir, packet_path=packet_path)
    write_json(markup_request_path, markup_request)

    visual_markup: dict[str, Any] | None = None
    vlm_result: dict[str, Any] | None = None
    if call_vlm:
        vlm_result = vlm_func(
            packet_path=packet_path,
            request_path=markup_request_path,
            markup_output_path=vlm_markup_output_path or (config.root_dir / DEFAULT_VLM_MARKUP_OUTPUT_PATH),
            raw_response_path=vlm_raw_response_path or (config.root_dir / DEFAULT_VLM_RAW_RESPONSE_PATH),
            root_dir=config.root_dir,
            model=vlm_model,
            timeout_seconds=vlm_timeout_seconds,
            update_packet=True,
        )
        packet = load_json(packet_path, {})
        if not isinstance(packet, dict) or not packet:
            raise FileNotFoundError(f"Decision packet not found or invalid after VLM call: {packet_path}")
        visual_markup = packet.get("visual_markup") if isinstance(packet.get("visual_markup"), dict) else None

    if markup_path is not None:
        raw_markup = load_json(markup_path, {})
        if not isinstance(raw_markup, dict) or not raw_markup:
            raise FileNotFoundError(f"Markup JSON not found or invalid: {markup_path}")
        visual_markup = validate_visual_markup(raw_markup, packet)
        packet = attach_visual_markup(packet, visual_markup)
        write_json(packet_path, packet)

    decision_report = build_decision_report(
        packet,
        root_dir=config.root_dir,
        packet_path=packet_path,
        max_hits=max_retrieval_hits,
    )
    write_json(decision_report_path, decision_report)

    pipeline_report = {
        "mode": "live_tradingview_decision_pipeline",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "capture_executed": not skip_capture,
        "capture_report_path": str(config.paths.live_tradingview_report_path.resolve()) if capture_report else "",
        "preflight_executed": preflight,
        "preflight_report_path": relative_or_absolute(preflight_output_path, config.root_dir) if preflight_report else "",
        "preflight_ready": bool(preflight_report.get("ready")) if preflight_report else None,
        "preflight_blocking_checks": [
            str(check.get("name", "")) for check in (preflight_report or {}).get("blocking_checks", [])
        ],
        "preflight_warning_checks": [
            str(check.get("name", "")) for check in (preflight_report or {}).get("warning_checks", [])
        ],
        "packet_path": relative_or_absolute(packet_path, config.root_dir),
        "markup_request_path": relative_or_absolute(markup_request_path, config.root_dir),
        "markup_imported": visual_markup is not None,
        "markup_status": (visual_markup or {}).get("status", ""),
        "markup_verified": bool((visual_markup or {}).get("verified", False)),
        "vlm_called": call_vlm,
        "vlm_status": (vlm_result or {}).get("status", ""),
        "decision_report_path": relative_or_absolute(decision_report_path, config.root_dir),
        "verdict": decision_report["verdict"],
        "confidence": decision_report["confidence"],
        "decision_ready": decision_report["decision_ready"],
        "warnings": decision_report["warnings"],
        "next_action": (
            "review_trade_decision"
            if visual_markup and visual_markup.get("verified")
            else "send_markup_request_to_codex_vlm"
        ),
    }
    write_json(pipeline_report_path, pipeline_report)
    pipeline_report.update(
        finalize_optional_outputs(
            config=config,
            decision_report_path=decision_report_path,
            pipeline_report_path=pipeline_report_path,
            brief_path=resolved_brief_path,
            journal_path=resolved_journal_path,
            render_brief=render_brief,
            append_journal=append_journal,
            journal_notes=journal_notes,
            journal_follow_up_labels=journal_follow_up_labels,
        )
    )
    write_json(pipeline_report_path, pipeline_report)
    return pipeline_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the live TradingView TTrades decision-support pipeline.")
    parser.add_argument("--root-dir", type=Path, default=Path("."))
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    parser.add_argument("--markup-request", type=Path, default=DEFAULT_MARKUP_REQUEST_PATH)
    parser.add_argument("--decision-report", type=Path, default=DEFAULT_DECISION_REPORT_PATH)
    parser.add_argument("--pipeline-report", type=Path, default=DEFAULT_PIPELINE_REPORT_PATH)
    parser.add_argument("--preflight", action="store_true", help="Run live prerequisites before capture or VLM work.")
    parser.add_argument("--preflight-report", type=Path, default=DEFAULT_PREFLIGHT_REPORT_PATH)
    parser.add_argument("--preflight-timeout-seconds", type=int, default=8)
    parser.add_argument("--render-brief", action="store_true", help="Render the markdown trader brief after the pipeline report.")
    parser.add_argument("--brief", type=Path, default=DEFAULT_BRIEF_PATH)
    parser.add_argument("--append-journal", action="store_true", help="Append a journal event after the pipeline report.")
    parser.add_argument("--journal", type=Path, default=DEFAULT_JOURNAL_PATH)
    parser.add_argument("--journal-note", action="append", default=[])
    parser.add_argument("--journal-follow-up-label", action="append", default=[])
    parser.add_argument("--markup", type=Path, default=None, help="Optional Codex/VLM markup JSON to import before decision.")
    parser.add_argument("--call-vlm", action="store_true", help="Call the configured VLM to fill visual markup before decision.")
    parser.add_argument("--vlm-markup-output", type=Path, default=DEFAULT_VLM_MARKUP_OUTPUT_PATH)
    parser.add_argument("--vlm-raw-response", type=Path, default=DEFAULT_VLM_RAW_RESPONSE_PATH)
    parser.add_argument("--vlm-model", default="gpt-5.4-pro")
    parser.add_argument("--vlm-timeout-seconds", type=int, default=180)
    parser.add_argument("--skip-capture", action="store_true", help="Use an existing decision packet instead of driving TradingView.")
    parser.add_argument("--allow-quality-fail", action="store_true")
    parser.add_argument("--max-quality-attempts", type=int, default=2)
    parser.add_argument("--retry-delay-seconds", type=float, default=1.0)
    parser.add_argument("--max-retrieval-hits", type=int, default=6)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root_dir = args.root_dir.resolve()
    config = build_config(root_dir=root_dir)
    report = run_live_decision_pipeline(
        config=config,
        packet_path=resolve(root_dir, args.packet),
        markup_request_path=resolve(root_dir, args.markup_request),
        decision_report_path=resolve(root_dir, args.decision_report),
        pipeline_report_path=resolve(root_dir, args.pipeline_report),
        preflight_report_path=resolve(root_dir, args.preflight_report),
        brief_path=resolve(root_dir, args.brief),
        journal_path=resolve(root_dir, args.journal),
        markup_path=resolve(root_dir, args.markup) if args.markup else None,
        preflight=args.preflight,
        preflight_timeout_seconds=args.preflight_timeout_seconds,
        render_brief=args.render_brief,
        append_journal=args.append_journal,
        journal_notes=list(args.journal_note or []),
        journal_follow_up_labels=list(args.journal_follow_up_label or []),
        call_vlm=args.call_vlm,
        vlm_markup_output_path=resolve(root_dir, args.vlm_markup_output),
        vlm_raw_response_path=resolve(root_dir, args.vlm_raw_response),
        vlm_model=args.vlm_model,
        vlm_timeout_seconds=args.vlm_timeout_seconds,
        skip_capture=args.skip_capture,
        allow_quality_fail=args.allow_quality_fail,
        max_quality_attempts=args.max_quality_attempts,
        retry_delay_seconds=args.retry_delay_seconds,
        max_retrieval_hits=args.max_retrieval_hits,
    )
    print(
        json.dumps(
            {
                "pipeline_report_path": str(resolve(root_dir, args.pipeline_report)),
                "verdict": report["verdict"],
                "confidence": report["confidence"],
                "decision_ready": report["decision_ready"],
                "warnings": report["warnings"],
                "next_action": report["next_action"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
