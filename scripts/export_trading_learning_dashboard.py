from __future__ import annotations

import argparse
import html
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "results" / "trading_learning_dashboard.html"
LOOP_SUMMARY_PATH = ROOT / "results" / "trading_learning_loop_summary.json"
NEURAL_REPORT_PATH = ROOT / "results" / "neural_net_readiness_report.json"
IMPROVEMENT_PLAN_PATH = ROOT / "results" / "trading_learning_improvement_plan.json"
ITERATION_CHALLENGER_REPORT_PATH = ROOT / "results" / "iteration_challenger_report.json"
ITERATION_PROMOTION_REPORT_PATH = ROOT / "results" / "iteration_promotion_report.json"
HISTORY_PATH = ROOT / "results" / "trading_learning_history.jsonl"


def load_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    entries: list[dict] = []
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


def extract_loop_scores(history_entries: list[dict], limit: int = 10) -> list[float]:
    scores: list[float] = []
    for entry in history_entries[-limit:]:
        metrics = entry.get("metrics", {})
        try:
            scores.append(float(metrics.get("loop_score", 0.0)))
        except (TypeError, ValueError):
            scores.append(0.0)
    return scores


def build_history_snapshot(history_entries: list[dict]) -> dict:
    recent_scores = extract_loop_scores(history_entries, limit=10)
    latest_entry = history_entries[-1] if history_entries else {}
    return {
        "entry_count": len(history_entries),
        "latest_recorded_at": latest_entry.get("recorded_at"),
        "latest_phase": latest_entry.get("phase"),
        "latest_status": latest_entry.get("status"),
        "latest_loop_score": recent_scores[-1] if recent_scores else 0.0,
        "recent_loop_scores": recent_scores,
        "recent_entries": [
            {
                "recorded_at": entry.get("recorded_at"),
                "phase": entry.get("phase"),
                "status": entry.get("status"),
                "loop_score": entry.get("metrics", {}).get("loop_score"),
            }
            for entry in history_entries[-5:]
        ],
    }


def grade_class(grade: str | None) -> str:
    normalized = (grade or "").strip().upper()
    if normalized.startswith("A"):
        return "good"
    if normalized.startswith("B"):
        return "good"
    if normalized.startswith("C"):
        return "warn"
    if normalized.startswith("D") or normalized.startswith("F"):
        return "bad"
    return "neutral"


def stage_rows(neural_report: dict) -> list[dict]:
    stages = neural_report.get("stages", {})
    ordered = [
        ("karpathy_style_autoresearch_loop", "Autoresearch"),
        ("offline_narrow_ml", "Offline Narrow ML"),
        ("real_time_neural_assist", "Real-Time Assist"),
        ("real_time_neural_execution", "Real-Time Execution"),
    ]
    rows: list[dict] = []
    for key, label in ordered:
        stage = stages.get(key, {})
        rows.append(
            {
                "name": label,
                "grade": stage.get("grade", "?"),
                "verdict": stage.get("verdict"),
                "ready": bool(stage.get("ready")),
                "blockers": list(stage.get("blockers", [])),
                "score": stage.get("score"),
            }
        )
    return rows


def build_summary(
    loop_summary: dict,
    neural_report: dict,
    improvement_plan: dict,
    challengers: dict,
    promotions: dict,
) -> dict:
    iteration_learning = loop_summary.get("iteration_learning", {})
    iteration_retraining = loop_summary.get("iteration_retraining", {})
    backtesting = loop_summary.get("backtesting", {})
    phase_one_focus = loop_summary.get("phase_one_focus", {})
    challenger_summary = loop_summary.get("iteration_challengers") or challengers.get("summary", {})
    promotion_summary = loop_summary.get("iteration_promotions") or promotions.get("summary", {})
    return {
        "generated_at": loop_summary.get("generated_at"),
        "step_count": int(loop_summary.get("step_count", 0)),
        "loop_score": float(loop_summary.get("training_loop", {}).get("loop_score", 0.0)),
        "workflow_score": float(loop_summary.get("tradingview_pine", {}).get("workflow_score", 0.0)),
        "validation_coverage": float(loop_summary.get("tradingview_pine", {}).get("validation_coverage", 0.0)),
        "training_loop_grade": loop_summary.get("training_loop", {}).get("grade"),
        "training_loop_verdict": loop_summary.get("training_loop", {}).get("verdict"),
        "iteration_understanding_grade": iteration_learning.get("grade"),
        "iteration_understanding_score": iteration_learning.get("average_understanding_score"),
        "retrained_task_count": int(iteration_retraining.get("trained_task_count", 0)),
        "retrained_task_names": list(iteration_retraining.get("trained_task_names", [])),
        "promotion_candidate_count": int(challenger_summary.get("promotion_candidate_count", 0)),
        "promotion_candidate_tasks": list(challenger_summary.get("promotion_candidate_tasks", [])),
        "iteration_challenger_wins": int(challenger_summary.get("challenger_win_count", 0)),
        "challenger_win_count": int(challenger_summary.get("challenger_win_count", 0)),
        "champion_win_count": int(challenger_summary.get("champion_win_count", 0)),
        "tie_task_count": int(challenger_summary.get("tie_task_count", 0)),
        "promoted_task_count": int(promotion_summary.get("promoted_task_count", 0)),
        "promoted_tasks": list(promotion_summary.get("promoted_tasks", [])),
        "skipped_promotion_count": int(promotion_summary.get("skipped_task_count", 0)),
        "backtesting_priority": backtesting.get("current_priority"),
        "phase_one_target": phase_one_focus.get("current_training_target"),
        "phase_one_status": phase_one_focus.get("status"),
        "phase_one_gap": int(phase_one_focus.get("additional_positive_examples_needed", 0) or 0),
        "phase_one_execution_spec": phase_one_focus.get("execution_spec"),
        "improvement_phase": improvement_plan.get("phase"),
        "improvement_status": improvement_plan.get("status"),
        "priority_action_count": int(improvement_plan.get("priority_action_count", 0))
        if "priority_action_count" in improvement_plan
        else len(improvement_plan.get("priority_actions", [])),
        "top_priority_action": improvement_plan.get("top_priority_action")
        or (
            improvement_plan.get("priority_actions", [{}])[0].get("title")
            if improvement_plan.get("priority_actions")
            else None
        ),
        "neural_blocker_count": len(neural_report.get("global_blockers", [])),
    }


def sparkline_points(values: list[float], *, width: int = 300, height: int = 72, padding: int = 8) -> tuple[str, str]:
    if not values:
        return "", ""
    min_value = min(values)
    max_value = max(values)
    span = max(0.0001, max_value - min_value)
    usable_width = max(1, width - padding * 2)
    usable_height = max(1, height - padding * 2)
    points: list[str] = []
    count = len(values)
    for index, value in enumerate(values):
        x = padding + (usable_width * index / max(1, count - 1))
        y = padding + (usable_height * (1 - ((value - min_value) / span)))
        points.append(f"{x:.1f},{y:.1f}")
    return " ".join(points), f"{min_value:.4f} to {max_value:.4f}"


def build_dashboard_report() -> dict:
    loop_summary = load_json(LOOP_SUMMARY_PATH, {})
    neural_report = load_json(NEURAL_REPORT_PATH, {})
    improvement_plan = load_json(IMPROVEMENT_PLAN_PATH, {})
    challengers = load_json(ITERATION_CHALLENGER_REPORT_PATH, {"summary": {}})
    promotions = load_json(ITERATION_PROMOTION_REPORT_PATH, {"summary": {}})
    history_entries = load_jsonl(HISTORY_PATH)
    history = build_history_snapshot(history_entries)

    report = {
        "title": "Trading Learning Dashboard",
        "generated_at": loop_summary.get("generated_at")
        or neural_report.get("generated_at")
        or datetime.now(timezone.utc).isoformat(),
        "summary": build_summary(loop_summary, neural_report, improvement_plan, challengers, promotions),
        "stage_grades": stage_rows(neural_report),
        "blockers": list(neural_report.get("global_blockers", [])),
        "next_actions": list(neural_report.get("next_actions", [])),
        "challengers": {
            "compared_task_count": int(challengers.get("summary", {}).get("compared_task_count", 0)),
            "challenger_win_count": int(challengers.get("summary", {}).get("challenger_win_count", 0)),
            "champion_win_count": int(challengers.get("summary", {}).get("champion_win_count", 0)),
            "tie_task_count": int(challengers.get("summary", {}).get("tie_task_count", 0)),
            "promotion_candidate_count": int(
                challengers.get("summary", {}).get("promotion_candidate_count", 0)
            ),
            "promotion_candidate_tasks": list(
                challengers.get("summary", {}).get("promotion_candidate_tasks", [])
            ),
        },
        "promotions": {
            "promoted_task_count": int(promotions.get("summary", {}).get("promoted_task_count", 0)),
            "promoted_tasks": list(promotions.get("summary", {}).get("promoted_tasks", [])),
            "skipped_task_count": int(promotions.get("summary", {}).get("skipped_task_count", 0)),
        },
        "phase_one_focus": loop_summary.get("phase_one_focus", {})
        or neural_report.get("phase_one_focus", {}),
        "improvement_plan": {
            "phase": improvement_plan.get("phase"),
            "status": improvement_plan.get("status"),
            "top_priority_action": report_top_priority_action(improvement_plan),
            "priority_actions": list(improvement_plan.get("priority_actions", [])),
        },
        "backtesting": loop_summary.get("backtesting", {}),
        "history": history,
    }

    if not report["next_actions"]:
        report["next_actions"] = list(improvement_plan.get("progress_signals", []))
    if improvement_plan.get("priority_actions"):
        report["next_actions"] = _unique_lines(
            report["next_actions"]
            + [str(action.get("title", "")).strip() for action in improvement_plan["priority_actions"]]
        )
    return report


def report_top_priority_action(improvement_plan: dict) -> str | None:
    if improvement_plan.get("top_priority_action"):
        return improvement_plan["top_priority_action"]
    priority_actions = improvement_plan.get("priority_actions", [])
    if priority_actions:
        return priority_actions[0].get("title")
    return None


def _unique_lines(lines: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for line in lines:
        cleaned = line.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def escape(value: object) -> str:
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def format_metric(value: object, *, decimals: int = 4) -> str:
    if value is None or value == "":
        return "n/a"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (int, float)):
        return f"{value:.{decimals}f}".rstrip("0").rstrip(".")
    return escape(value)


def card(label: str, value: object, sublabel: str | None = None, *, tone: str = "neutral") -> str:
    sub = f'<div class="card-subtitle">{escape(sublabel)}</div>' if sublabel else ""
    return (
        f'<article class="metric-card metric-card--{tone}">'
        f'<div class="card-label">{escape(label)}</div>'
        f'<div class="card-value">{format_metric(value)}</div>'
        f"{sub}"
        f"</article>"
    )


def render_sparkline(values: list[float]) -> str:
    points, span = sparkline_points(values)
    if not points:
        return '<div class="sparkline-empty">No history yet.</div>'
    return (
        '<div class="sparkline-wrap">'
        '<svg viewBox="0 0 300 72" role="img" aria-label="Loop score trend">'
        '<defs>'
        '<linearGradient id="spark-fill" x1="0" x2="0" y1="0" y2="1">'
        '<stop offset="0%" stop-color="rgba(255, 196, 102, 0.45)" />'
        '<stop offset="100%" stop-color="rgba(255, 196, 102, 0.02)" />'
        "</linearGradient>"
        "</defs>"
        '<polyline fill="none" stroke="var(--accent)" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" points="'
        + points
        + '" />'
        f'<text x="12" y="18" class="sparkline-caption">Range {escape(span)}</text>'
        "</svg>"
        "</div>"
    )


def render_list(items: list[str], *, empty_text: str) -> str:
    if not items:
        return f'<p class="muted">{escape(empty_text)}</p>'
    return "<ul>" + "".join(f"<li>{escape(item)}</li>" for item in items) + "</ul>"


def render_stage_grid(stage_grades: list[dict]) -> str:
    blocks = []
    for stage in stage_grades:
        tone = grade_class(stage.get("grade"))
        block = (
            f'<article class="stage-row stage-row--{tone}">'
            f'<div class="stage-name">{escape(stage.get("name"))}</div>'
            f'<div class="stage-grade">{escape(stage.get("grade"))}</div>'
            f'<div class="stage-meta">{escape(stage.get("verdict") or "n/a")} · '
            f'{"ready" if stage.get("ready") else "not ready"}</div>'
            "</article>"
        )
        blocks.append(block)
    return "".join(blocks)


def render_dashboard_html(report: dict) -> str:
    summary = report.get("summary", {})
    history = report.get("history", {})
    challengers = report.get("challengers", {})
    promotions = report.get("promotions", {})
    phase_one_focus = report.get("phase_one_focus", {})
    improvement_plan = report.get("improvement_plan", {})
    backtesting = report.get("backtesting", {})
    sparkline = render_sparkline(history.get("recent_loop_scores", []))

    promotion_candidates = challengers.get("promotion_candidate_tasks", [])
    promoted_tasks = promotions.get("promoted_tasks", [])
    backtesting_priority = backtesting.get("current_priority") or "n/a"
    backtesting_stage = backtesting.get("stages", {})
    backtesting_cards = "".join(
        card(
            stage_name.replace("_", " ").title(),
            stage_info.get("grade"),
            stage_info.get("verdict"),
            tone=grade_class(stage_info.get("grade")),
        )
        for stage_name, stage_info in backtesting_stage.items()
    )

    head = f"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape(report.get("title"))}</title>
  <style>
    :root {{
      --bg: #0b0f14;
      --panel: rgba(18, 25, 35, 0.9);
      --panel-strong: rgba(25, 33, 45, 0.96);
      --line: rgba(255, 255, 255, 0.09);
      --text: #eef3fa;
      --muted: #9ca9ba;
      --accent: #ffc266;
      --accent-2: #77d9c3;
      --danger: #ff8a7a;
      --warn: #ffd36b;
      --good: #88e0a9;
      --shadow: 0 18px 44px rgba(0, 0, 0, 0.35);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(255, 194, 102, 0.18), transparent 28%),
        radial-gradient(circle at top right, rgba(119, 217, 195, 0.14), transparent 24%),
        linear-gradient(180deg, #11161d 0%, #0b0f14 100%);
      font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", Georgia, serif;
    }}
    .shell {{
      max-width: 1240px;
      margin: 0 auto;
      padding: 32px 20px 56px;
    }}
    .hero {{
      display: grid;
      grid-template-columns: 1.45fr 0.95fr;
      gap: 20px;
      align-items: stretch;
      margin-bottom: 18px;
    }}
    .hero-panel, .panel {{
      border: 1px solid var(--line);
      background: linear-gradient(180deg, var(--panel), rgba(12, 17, 24, 0.92));
      backdrop-filter: blur(12px);
      box-shadow: var(--shadow);
      border-radius: 24px;
      overflow: hidden;
    }}
    .hero-main {{
      padding: 28px;
      min-height: 258px;
      position: relative;
    }}
    .eyebrow {{
      text-transform: uppercase;
      letter-spacing: 0.24em;
      font-size: 12px;
      color: var(--accent);
      margin-bottom: 14px;
    }}
    h1 {{
      margin: 0;
      font-size: clamp(2.4rem, 5vw, 4.8rem);
      line-height: 0.95;
      letter-spacing: -0.05em;
      max-width: 9ch;
    }}
    .hero-copy {{
      margin-top: 14px;
      max-width: 58ch;
      color: var(--muted);
      font-size: 1rem;
      line-height: 1.7;
      font-family: "Aptos", "Segoe UI", sans-serif;
    }}
    .hero-side {{
      padding: 24px;
      display: grid;
      gap: 14px;
      align-content: start;
    }}
    .status-pill {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      width: fit-content;
      padding: 10px 14px;
      border-radius: 999px;
      background: rgba(255, 194, 102, 0.12);
      border: 1px solid rgba(255, 194, 102, 0.28);
      color: var(--accent);
      font-family: "Aptos", "Segoe UI", sans-serif;
      font-size: 13px;
    }}
    .status-pill strong {{
      color: var(--text);
      font-weight: 700;
    }}
    .support {{
      color: var(--muted);
      font-family: "Aptos", "Segoe UI", sans-serif;
      line-height: 1.6;
      font-size: 0.95rem;
    }}
    .section {{
      margin-top: 20px;
    }}
    .section h2 {{
      margin: 0 0 14px;
      font-size: 1.15rem;
      text-transform: uppercase;
      letter-spacing: 0.14em;
      font-family: "Aptos", "Segoe UI", sans-serif;
    }}
    .metric-grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 14px;
    }}
    .metric-card {{
      padding: 18px;
      border: 1px solid var(--line);
      border-radius: 18px;
      background: var(--panel-strong);
      min-height: 112px;
    }}
    .metric-card--good {{ box-shadow: inset 0 0 0 1px rgba(136, 224, 169, 0.14); }}
    .metric-card--warn {{ box-shadow: inset 0 0 0 1px rgba(255, 211, 107, 0.14); }}
    .metric-card--bad {{ box-shadow: inset 0 0 0 1px rgba(255, 138, 122, 0.14); }}
    .card-label {{
      color: var(--muted);
      font-family: "Aptos", "Segoe UI", sans-serif;
      font-size: 0.85rem;
      letter-spacing: 0.05em;
      text-transform: uppercase;
    }}
    .card-value {{
      font-size: 2rem;
      line-height: 1.1;
      margin-top: 10px;
      font-weight: 700;
    }}
    .card-subtitle {{
      margin-top: 8px;
      color: var(--muted);
      font-family: "Aptos", "Segoe UI", sans-serif;
      line-height: 1.5;
      font-size: 0.92rem;
    }}
    .two-col {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 18px;
    }}
    .panel-inner {{
      padding: 22px;
    }}
    .stage-grid {{
      display: grid;
      gap: 10px;
    }}
    .stage-row {{
      display: grid;
      grid-template-columns: minmax(0, 1.7fr) 72px minmax(0, 1fr);
      gap: 12px;
      align-items: center;
      padding: 14px 16px;
      border-radius: 16px;
      background: rgba(255, 255, 255, 0.03);
      border: 1px solid var(--line);
      font-family: "Aptos", "Segoe UI", sans-serif;
    }}
    .stage-row--good {{ border-color: rgba(136, 224, 169, 0.26); }}
    .stage-row--warn {{ border-color: rgba(255, 211, 107, 0.26); }}
    .stage-row--bad {{ border-color: rgba(255, 138, 122, 0.26); }}
    .stage-name {{ font-weight: 650; }}
    .stage-grade {{
      justify-self: end;
      font-size: 1.05rem;
      font-weight: 800;
      color: var(--accent);
    }}
    .stage-meta {{ color: var(--muted); text-align: right; }}
    .cols {{
      display: grid;
      grid-template-columns: 1.3fr 0.9fr;
      gap: 18px;
    }}
    .list {{
      margin: 0;
      padding-left: 20px;
      color: var(--text);
      line-height: 1.75;
      font-family: "Aptos", "Segoe UI", sans-serif;
    }}
    .list li {{ margin-bottom: 8px; }}
    .muted {{
      color: var(--muted);
      font-family: "Aptos", "Segoe UI", sans-serif;
      line-height: 1.65;
    }}
    .sparkline-wrap {{
      margin-top: 14px;
      border: 1px solid var(--line);
      border-radius: 16px;
      background: rgba(255, 255, 255, 0.03);
      padding: 8px;
    }}
    .sparkline-caption {{
      font-size: 11px;
      fill: var(--muted);
      font-family: "Aptos", "Segoe UI", sans-serif;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}
    .sparkline-empty {{
      padding: 20px;
      color: var(--muted);
      font-family: "Aptos", "Segoe UI", sans-serif;
    }}
    .history-list {{
      display: grid;
      gap: 10px;
      margin-top: 14px;
    }}
    .history-item {{
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 12px;
      padding: 12px 14px;
      border-radius: 14px;
      background: rgba(255, 255, 255, 0.03);
      border: 1px solid var(--line);
      font-family: "Aptos", "Segoe UI", sans-serif;
    }}
    .history-item strong {{ color: var(--accent); }}
    .footer-note {{
      margin-top: 18px;
      color: var(--muted);
      font-size: 0.92rem;
      font-family: "Aptos", "Segoe UI", sans-serif;
    }}
    @media (max-width: 980px) {{
      .hero, .metric-grid, .two-col, .cols {{
        grid-template-columns: 1fr;
      }}
      .stage-row {{
        grid-template-columns: 1fr;
      }}
      .stage-grade, .stage-meta {{
        justify-self: start;
        text-align: left;
      }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <article class="hero-panel hero-main">
        <div class="eyebrow">Training Loop</div>
        <h1>Where the loop stands right now.</h1>
        <p class="hero-copy">
          This dashboard compresses the current research loop, retraining pass, challenger
          comparison, and readiness gates into one view. The center of gravity is still
          TradingView validation and narrow-model promotion review.
        </p>
      </article>
      <aside class="hero-panel hero-side">
        <div class="status-pill"><strong>{escape(summary.get("training_loop_grade"))}</strong> training loop grade</div>
        <div class="support">Status: <strong>{escape(summary.get("training_loop_verdict"))}</strong></div>
        <div class="support">Phase: <strong>{escape(report.get("improvement_plan", {}).get("phase"))}</strong></div>
        <div class="support">Phase 1 target: <strong>{escape(summary.get("phase_one_target") or phase_one_focus.get("current_training_target") or "n/a")}</strong></div>
        <div class="support">Last generated: <strong>{escape(report.get("generated_at"))}</strong></div>
        <div class="support">Top priority: <strong>{escape(summary.get("top_priority_action") or "n/a")}</strong></div>
      </aside>
    </section>

    <section class="section">
        <h2>Summary</h2>
      <div class="metric-grid">
        {card("Loop score", summary.get("loop_score"), "Overall learning-loop score", tone=grade_class(summary.get("training_loop_grade")))}
        {card("Training grade", summary.get("training_loop_grade"), summary.get("training_loop_verdict"), tone=grade_class(summary.get("training_loop_grade")))}
        {card("Understanding", summary.get("iteration_understanding_grade"), f"{summary.get('iteration_understanding_score', 'n/a')} average score", tone=grade_class(summary.get("iteration_understanding_grade")))}
        {card("Re-trained tasks", summary.get("retrained_task_count"), ", ".join(summary.get("retrained_task_names", [])) or "No task list", tone="neutral")}
        {card("Promotion candidates", summary.get("promotion_candidate_count"), ", ".join(promotion_candidates) or "None yet", tone="warn" if summary.get("promotion_candidate_count") else "neutral")}
        {card("Promoted champions", summary.get("promoted_task_count"), ", ".join(promoted_tasks) or "None yet", tone="good" if summary.get("promoted_task_count") else "neutral")}
        {card("Challenger wins", challengers.get("challenger_win_count"), f"vs {challengers.get('champion_win_count', 0)} champion wins", tone="good" if challengers.get("challenger_win_count") else "neutral")}
        {card("Backtesting priority", backtesting_priority, "Current validation focus", tone="neutral")}
        {card("Phase 1 target", summary.get("phase_one_target") or phase_one_focus.get("current_training_target"), summary.get("phase_one_status") or phase_one_focus.get("status") or "n/a", tone="warn" if (summary.get("phase_one_gap") or 0) else "good")}
        {card("Phase 1 gap", summary.get("phase_one_gap"), summary.get("phase_one_execution_spec") or phase_one_focus.get("execution_spec") or "n/a", tone="warn" if (summary.get("phase_one_gap") or 0) else "good")}
        {card("Priority actions", summary.get("priority_action_count"), summary.get("top_priority_action") or "No priority action", tone="warn" if summary.get("priority_action_count") else "neutral")}
      </div>
    </section>

    <section class="section two-col">
      <article class="panel">
        <div class="panel-inner">
          <h2>Stage Ladder</h2>
          <div class="stage-grid">{render_stage_grid(report.get("stage_grades", []))}</div>
        </div>
      </article>
      <article class="panel">
        <div class="panel-inner">
          <h2>Trend</h2>
          <p class="muted">History entries: <strong>{history.get("entry_count", 0)}</strong></p>
          {sparkline}
          <div class="history-list">
            {"".join(
                f'<div class="history-item"><div><strong>{escape(entry.get("recorded_at"))}</strong><br />'
                f'<span class="muted">{escape(entry.get("phase") or "n/a")} · {escape(entry.get("status") or "n/a")}</span></div>'
                f'<div><strong>{format_metric(entry.get("loop_score"))}</strong></div></div>'
                for entry in history.get("recent_entries", [])
            )}
          </div>
        </div>
      </article>
    </section>

    <section class="section cols">
      <article class="panel">
        <div class="panel-inner">
          <h2>Blockers</h2>
          {render_list(report.get("blockers", []), empty_text="No blockers recorded at the moment.")}
        </div>
      </article>
      <article class="panel">
        <div class="panel-inner">
          <h2>Next Actions</h2>
          {render_list(report.get("next_actions", []), empty_text="No next actions recorded.")}
        </div>
      </article>
    </section>

    <section class="section two-col">
      <article class="panel">
        <div class="panel-inner">
          <h2>Iteration Challengers</h2>
          <div class="metric-grid" style="grid-template-columns: repeat(2, minmax(0, 1fr));">
            {card("Compared tasks", challengers.get("compared_task_count"), "Champions vs challengers", tone="neutral")}
            {card("Promotion candidates", challengers.get("promotion_candidate_count"), ", ".join(promotion_candidates) or "None", tone="warn" if challengers.get("promotion_candidate_count") else "neutral")}
            {card("Challenger wins", challengers.get("challenger_win_count"), "Challengers ahead on full surface", tone="good" if challengers.get("challenger_win_count") else "neutral")}
            {card("Ties", challengers.get("tie_task_count"), "No clear winner", tone="neutral")}
          </div>
          <h2 style="margin-top: 20px;">Promoted Champions</h2>
          {render_list(promoted_tasks, empty_text="No challenger has been promoted yet.")}
        </div>
      </article>
      <article class="panel">
        <div class="panel-inner">
          <h2>Backtesting</h2>
          <p class="muted">Current priority: <strong>{escape(backtesting_priority)}</strong></p>
          <div class="metric-grid" style="grid-template-columns: repeat(2, minmax(0, 1fr));">
            {backtesting_cards}
          </div>
        </div>
      </article>
    </section>

    <div class="footer-note">
      Generated from `trading_learning_loop_summary.json`, `neural_net_readiness_report.json`,
      `trading_learning_improvement_plan.json`, `iteration_challenger_report.json`,
      `iteration_promotion_report.json`, and `trading_learning_history.jsonl`.
    </div>
  </div>
</body>
</html>
"""
    return head


def write_dashboard(report: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_dashboard_html(report), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export a static dashboard for the trading learning loop.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    output_path = Path(args.output)
    report = build_dashboard_report()
    write_dashboard(report, output_path)
    print(
        json.dumps(
            {
                "output": str(output_path),
                "title": report["title"],
                "training_loop_grade": report["summary"].get("training_loop_grade"),
                "promotion_candidate_count": report["summary"].get("promotion_candidate_count"),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
