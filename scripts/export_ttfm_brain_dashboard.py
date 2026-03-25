from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WORKFLOW_REPORT_PATH = ROOT / "results" / "ttfm_brain_workflow_report.json"
DEFAULT_HISTORY_PATH = ROOT / "results" / "ttfm_brain_workflow_history.jsonl"
DEFAULT_OUTPUT = ROOT / "results" / "ttfm_brain_dashboard.html"


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


def escape(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def render_key_values(items: dict[str, Any]) -> str:
    if not items:
        return '<p class="muted">No data available.</p>'
    rows = "".join(
        f"<tr><th>{escape(key)}</th><td>{escape(value)}</td></tr>"
        for key, value in items.items()
    )
    return f'<table class="kv-table">{rows}</table>'


def render_disagreement_cases(cases: list[dict[str, Any]]) -> str:
    if not cases:
        return '<p class="muted">No disagreement cases recorded.</p>'
    cards: list[str] = []
    for case in cases:
        probabilities = ", ".join(
            f"{item.get('label')}={float(item.get('probability', 0.0)):.2f}"
            for item in case.get("top_predicted_labels", [])
        ) or "(none)"
        cards.append(
            "".join(
                [
                    '<article class="case-card">',
                    f"<h3>{escape(case.get('example_id'))}</h3>",
                    f"<p><strong>Screenshot:</strong> {escape(case.get('screenshot_path'))}</p>",
                    f"<p><strong>Audio:</strong> {escape(case.get('audio_path'))}</p>",
                    f"<p><strong>Weak labels:</strong> {escape(', '.join(case.get('weak_active_labels', [])) or '(none)')}</p>",
                    f"<p><strong>Predicted labels:</strong> {escape(', '.join(case.get('predicted_labels', [])) or '(none)')}</p>",
                    f"<p><strong>Top probabilities:</strong> {escape(probabilities)}</p>",
                    "</article>",
                ]
            )
        )
    return "".join(cards)


def build_dashboard_html(report: dict[str, Any], history_entries: list[dict[str, Any]]) -> str:
    corpus = report.get("corpus", {})
    daily_intake = report.get("daily_intake", {})
    embeddings = report.get("embeddings", {})
    trainability = report.get("trainability", {})
    benchmark = report.get("frozen_benchmark", {})
    benchmark_comparison = benchmark.get("comparison", {})
    stages = report.get("stages", [])
    stage_rows = "".join(
        f"<tr><td>{escape(stage.get('name'))}</td><td>{escape(stage.get('status'))}</td></tr>"
        for stage in stages
    ) or '<tr><td colspan="2">No stage data</td></tr>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>TTFM Brain Workflow Dashboard</title>
  <style>
    body {{
      font-family: ui-sans-serif, system-ui, sans-serif;
      margin: 0;
      padding: 24px;
      background: #0b1220;
      color: #e5edf7;
      line-height: 1.5;
    }}
    h1, h2, h3 {{ margin: 0 0 12px; }}
    section {{
      margin: 0 0 20px;
      padding: 18px;
      background: #111a2b;
      border: 1px solid #243247;
      border-radius: 14px;
    }}
    .muted {{ color: #9fb0c9; }}
    .kv-table, .stage-table {{
      width: 100%;
      border-collapse: collapse;
    }}
    .kv-table th, .kv-table td, .stage-table td, .stage-table th {{
      text-align: left;
      padding: 8px 10px;
      border-bottom: 1px solid #243247;
      vertical-align: top;
    }}
    .case-card {{
      margin: 0 0 12px;
      padding: 12px;
      border: 1px solid #31415c;
      border-radius: 12px;
      background: #0f1727;
    }}
  </style>
</head>
<body>
  <header>
    <h1>TTFM Brain Workflow Dashboard</h1>
    <p class="muted">Generated at {escape(report.get("generated_at"))}. History entries: {len(history_entries)}</p>
  </header>

  <section>
    <h2>Corpus Size and Deltas</h2>
    {render_key_values({
        "Current video count": corpus.get("current_video_count"),
        "Delta video count": corpus.get("delta_video_count"),
        "Partition counts": corpus.get("partition_counts"),
    })}
  </section>

  <section>
    <h2>Embedding Counts and Cache Behavior</h2>
    {render_key_values({
        "Text embeddings": f"{embeddings.get('text', {}).get('item_count')} ({embeddings.get('text', {}).get('status')})",
        "Visual embeddings": f"{embeddings.get('visual', {}).get('item_count')} ({embeddings.get('visual', {}).get('status')})",
    })}
  </section>

  <section>
    <h2>Trainable vs Blocked Rows</h2>
    {render_key_values({
        "Trainable rows": trainability.get("trainable_row_count"),
        "Blocked rows": trainability.get("blocked_row_count"),
        "Blocked reasons": trainability.get("blocked_reason_counts"),
    })}
  </section>

  <section>
    <h2>Frozen Benchmark Results</h2>
    {render_key_values({
        "Benchmark rows": benchmark.get("benchmark_row_count"),
        "Winner": benchmark_comparison.get("winner"),
        "Champion": benchmark.get("champion"),
        "Challenger": benchmark.get("challenger"),
        "Delta": benchmark_comparison.get("delta"),
    })}
  </section>

  <section>
    <h2>Top Disagreement Cases</h2>
    {render_disagreement_cases(report.get("top_disagreement_cases", []))}
  </section>

  <section>
    <h2>Daily Intake Summary</h2>
    {render_key_values({
        "Video files": daily_intake.get("video_file_count"),
        "Image files": daily_intake.get("image_file_count"),
        "Added to trainable videos": daily_intake.get("trainable_video_count"),
        "Queued videos": daily_intake.get("queued_video_count"),
        "Added to weak training images": daily_intake.get("trainable_image_count"),
        "Held for review images": daily_intake.get("review_only_image_count"),
    })}
  </section>

  <section>
    <h2>Stage Status</h2>
    <table class="stage-table">
      <tr><th>Stage</th><th>Status</th></tr>
      {stage_rows}
    </table>
  </section>
</body>
</html>"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Render the TTFM brain workflow dashboard.")
    parser.add_argument("--workflow-report", type=Path, default=DEFAULT_WORKFLOW_REPORT_PATH)
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    report = load_json(args.workflow_report, {})
    history_entries = load_jsonl(args.history)
    html_text = build_dashboard_html(report, history_entries)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html_text, encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
