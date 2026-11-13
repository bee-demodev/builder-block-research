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
DEFAULT_OUTPUT_PATH = Path("results") / "live_tradingview_decision_brief.md"


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


def one_line(value: Any) -> str:
    return " ".join(str(value or "").split())


def yes_no(value: Any) -> str:
    return "yes" if bool(value) else "no"


def render_list(items: list[Any]) -> str:
    values = [one_line(item) for item in items if one_line(item)]
    return ", ".join(values) if values else "none"


def render_pipeline_fallback(pipeline_report: dict[str, Any]) -> str:
    blockers = render_list(pipeline_report.get("preflight_blocking_checks", []))
    warnings = render_list(pipeline_report.get("preflight_warning_checks", []) or pipeline_report.get("warnings", []))
    lines = [
        "# Live TradingView Decision Brief",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Verdict: {one_line(pipeline_report.get('verdict', 'insufficient_evidence'))}",
        f"Confidence: {pipeline_report.get('confidence', 0.0)}",
        f"Decision ready: {yes_no(pipeline_report.get('decision_ready'))}",
        f"Next action: {one_line(pipeline_report.get('next_action', 'fix_preflight_blockers'))}",
        "",
        "## Current Blockers",
        "",
        f"- Preflight ready: {yes_no(pipeline_report.get('preflight_ready'))}",
        f"- Blocking checks: {blockers}",
        f"- Warning checks: {warnings}",
        f"- Packet path: {one_line(pipeline_report.get('packet_path', '')) or 'none'}",
        "",
        "## Decision",
        "",
        "No trade decision was produced because the live pipeline did not reach a decision-ready packet.",
        "",
    ]
    return "\n".join(lines)


def render_checklist(checklist: list[Any]) -> list[str]:
    if not checklist:
        return ["- No checklist was recorded."]
    lines: list[str] = []
    for item in checklist:
        if not isinstance(item, dict):
            continue
        field = one_line(item.get("field", "unknown"))
        status = one_line(item.get("status", "unknown"))
        evidence = one_line(item.get("evidence", ""))
        lines.append(f"- {field}: {status}" + (f" - {evidence}" if evidence else ""))
    return lines or ["- No checklist was recorded."]


def render_retrieval_hits(hits: list[Any], *, limit: int = 4) -> list[str]:
    if not hits:
        return ["- No retrieval hits were recorded."]
    lines: list[str] = []
    for hit in hits[:limit]:
        if not isinstance(hit, dict):
            continue
        title = one_line(hit.get("title") or hit.get("example_id") or "untitled")
        source = one_line(hit.get("source_path", ""))
        checkpoint = one_line(hit.get("checkpoint", ""))
        excerpt = one_line(hit.get("excerpt", ""))
        suffix = f" ({checkpoint})" if checkpoint else ""
        source_text = f" - {source}" if source else ""
        excerpt_text = f": {excerpt}" if excerpt else ""
        lines.append(f"- {title}{suffix}{source_text}{excerpt_text}")
    return lines or ["- No retrieval hits were recorded."]


def render_decision_report(decision_report: dict[str, Any], pipeline_report: dict[str, Any]) -> str:
    writeup = decision_report.get("decision_writeup", {})
    if not isinstance(writeup, dict):
        writeup = {}
    warnings = render_list(decision_report.get("warnings", []) or pipeline_report.get("warnings", []))
    reasons = render_list(decision_report.get("reasons", []))
    chart_paths = decision_report.get("chart_paths", {})
    if not isinstance(chart_paths, dict):
        chart_paths = {}
    chart_items = [f"{key}={value}" for key, value in chart_paths.items() if value]
    lines = [
        "# Live TradingView Decision Brief",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Symbol: {one_line(decision_report.get('symbol', '')) or 'unknown'}",
        f"Verdict: {one_line(decision_report.get('verdict', 'insufficient_evidence'))}",
        f"Confidence: {decision_report.get('confidence', 0.0)}",
        f"Decision ready: {yes_no(decision_report.get('decision_ready'))}",
        f"Warnings: {warnings}",
        "",
        "## Decision",
        "",
        f"- Headline: {one_line(writeup.get('headline', 'No decision writeup was recorded.'))}",
        f"- Direction: {one_line(writeup.get('direction', 'none'))}",
        f"- Trigger needed: {one_line(writeup.get('trigger_needed', 'not recorded'))}",
        f"- Invalidation: {one_line(writeup.get('invalidation', 'unknown'))}",
        f"- Missing or unverified: {render_list(writeup.get('missing_or_unverified', []))}",
        f"- Reasons: {reasons}",
        "",
        "## Checklist",
        "",
        *render_checklist(decision_report.get("checklist", [])),
        "",
        "## Retrieval Evidence",
        "",
        *render_retrieval_hits(decision_report.get("retrieval_hits", [])),
        "",
        "## Artifacts",
        "",
        f"- Decision report: {one_line(pipeline_report.get('decision_report_path', '')) or one_line(decision_report.get('source_packet_path', '')) or 'current input'}",
        f"- Pipeline next action: {one_line(pipeline_report.get('next_action', 'not recorded'))}",
        f"- Chart paths: {render_list(chart_items)}",
        "",
    ]
    return "\n".join(lines)


def render_brief(*, decision_report: dict[str, Any], pipeline_report: dict[str, Any]) -> str:
    if decision_report:
        return render_decision_report(decision_report, pipeline_report)
    return render_pipeline_fallback(pipeline_report)


def write_brief(
    *,
    root_dir: Path,
    decision_report_path: Path,
    pipeline_report_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    decision_report = load_json(decision_report_path)
    pipeline_report = load_json(pipeline_report_path)
    brief = render_brief(decision_report=decision_report, pipeline_report=pipeline_report)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(brief + "\n", encoding="utf-8")
    return {
        "output_path": str(output_path),
        "used_decision_report": bool(decision_report),
        "used_pipeline_report": bool(pipeline_report),
        "verdict": one_line((decision_report or pipeline_report).get("verdict", "insufficient_evidence")),
        "decision_ready": bool((decision_report or pipeline_report).get("decision_ready")),
        "relative_output_path": str(output_path.resolve().relative_to(root_dir.resolve()))
        if output_path.resolve().is_relative_to(root_dir.resolve())
        else str(output_path.resolve()),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a concise markdown brief from live TradingView decision artifacts.")
    parser.add_argument("--root-dir", type=Path, default=Path("."))
    parser.add_argument("--decision-report", type=Path, default=DEFAULT_DECISION_REPORT_PATH)
    parser.add_argument("--pipeline-report", type=Path, default=DEFAULT_PIPELINE_REPORT_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root_dir = args.root_dir.resolve()
    summary = write_brief(
        root_dir=root_dir,
        decision_report_path=resolve(root_dir, args.decision_report),
        pipeline_report_path=resolve(root_dir, args.pipeline_report),
        output_path=resolve(root_dir, args.output),
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
