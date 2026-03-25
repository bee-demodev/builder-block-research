from __future__ import annotations

import argparse
import html
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_QUEUE_PATH = ROOT / "results" / "ttfm_market_context_review_queue.json"
DEFAULT_HTML_OUTPUT = ROOT / "results" / "ttfm_market_context_review_dashboard.html"
DEFAULT_OVERRIDE_OUTPUT = ROOT / "results" / "ttfm_market_context_override_templates.json"


def load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def relative_asset_href(path_value: str | None, *, html_output_path: Path) -> str | None:
    normalized = str(path_value or "").strip()
    if not normalized:
        return None
    candidate = Path(normalized)
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    relative = Path(os.path.relpath(candidate, html_output_path.parent))
    return relative.as_posix()


def build_override_seed_map(queue: dict[str, Any]) -> dict[str, Any]:
    items = queue.get("items", [])
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "notes": [
            "Fill symbol and anchor_timestamp for each reviewed case, then copy the approved entries into data/ttfm_market_context_map.json.",
            "Keep anchor_timestamp empty when the source image does not expose a trustworthy chart time.",
            "The existing trade-model proxy suggestions are included as starting points only and still require visual confirmation.",
            "Cases marked `find_alternate_chart_evidence` still need a real chart capture before anchor_timestamp should be set.",
        ],
        "case_overrides": [item.get("override_template", {}) for item in items],
    }


def build_review_dashboard_report(
    queue: dict[str, Any],
    *,
    html_output_path: Path,
) -> dict[str, Any]:
    normalized_items: list[dict[str, Any]] = []
    for item in queue.get("items", []):
        checkpoint_samples = []
        for sample in item.get("checkpoint_samples", []):
            screenshot_path = sample.get("screenshot_path")
            checkpoint_samples.append(
                {
                    "checkpoint": sample.get("checkpoint"),
                    "timeframe": sample.get("timeframe"),
                    "timeframe_role": sample.get("timeframe_role"),
                    "active_labels": list(sample.get("active_labels", [])),
                    "annotation_notes": list(sample.get("annotation_notes", [])),
                    "screenshot_path": screenshot_path,
                    "image_src": relative_asset_href(
                        screenshot_path,
                        html_output_path=html_output_path,
                    ),
                }
            )

        override_template = item.get("override_template", {})
        normalized_items.append(
            {
                "case_ref": item.get("case_ref"),
                "topic": item.get("topic"),
                "trade_models": list(item.get("trade_models", [])),
                "relation_types": list(item.get("relation_types", [])),
                "source_url": item.get("source_url"),
                "alignment_status": item.get("alignment_status"),
                "mapping_provenance": item.get("mapping_provenance"),
                "recommended_action": item.get("recommended_action"),
                "source_image_kind": item.get("source_image_kind"),
                "symbol_suggestion": item.get("symbol_suggestion"),
                "source_chart_symbol": item.get("source_chart_symbol"),
                "bars_path_suggestion": item.get("bars_path_suggestion"),
                "anchor_timestamp": item.get("anchor_timestamp"),
                "market_context_notes": item.get("market_context_notes"),
                "confidence": item.get("confidence"),
                "evidence_refs": list(item.get("evidence_refs", [])),
                "checkpoint_samples": checkpoint_samples,
                "override_template": override_template,
                "override_template_json": json.dumps(override_template, indent=2),
            }
        )

    return {
        "generated_at": queue.get("generated_at") or datetime.now(timezone.utc).isoformat(),
        "summary": queue.get("summary", {}),
        "items": normalized_items,
    }


def escape(value: object) -> str:
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def render_list(items: list[str], *, empty_text: str) -> str:
    if not items:
        return f'<p class="muted">{escape(empty_text)}</p>'
    return "<ul>" + "".join(f"<li>{escape(item)}</li>" for item in items) + "</ul>"


def render_checkpoint_gallery(samples: list[dict[str, Any]]) -> str:
    cards: list[str] = []
    for sample in samples:
        labels = ", ".join(sample.get("active_labels", [])) or "No active labels"
        notes = render_list(
            sample.get("annotation_notes", []),
            empty_text="No annotation notes.",
        )
        image_src = sample.get("image_src")
        image_markup = (
            f'<img src="{escape(image_src)}" alt="{escape(sample.get("checkpoint"))} screenshot" loading="lazy" />'
            if image_src
            else '<div class="image-missing">Image missing</div>'
        )
        cards.append(
            '<article class="checkpoint-card">'
            f'<div class="checkpoint-image">{image_markup}</div>'
            '<div class="checkpoint-body">'
            f'<div class="checkpoint-kicker">{escape(sample.get("timeframe_role"))} · {escape(sample.get("timeframe"))}</div>'
            f'<h4>{escape(sample.get("checkpoint"))}</h4>'
            f'<p><strong>Labels:</strong> {escape(labels)}</p>'
            f"{notes}"
            "</div>"
            "</article>"
        )
    return "".join(cards)


def render_case_card(item: dict[str, Any]) -> str:
    checklist = render_list(
        [
            f"Recommended action: {item.get('recommended_action')}",
            f"Alignment status: {item.get('alignment_status')}",
            f"Suggested symbol: {item.get('symbol_suggestion') or 'n/a'}",
            f"Source chart symbol: {item.get('source_chart_symbol') or 'n/a'}",
            f"Anchor timestamp: {item.get('anchor_timestamp') or 'pending'}",
            f"Mapping provenance: {item.get('mapping_provenance') or 'n/a'}",
            f"Source image kind: {item.get('source_image_kind') or 'unknown'}",
        ],
        empty_text="No case checklist available.",
    )
    evidence = render_list(
        item.get("evidence_refs", []),
        empty_text="No evidence refs recorded.",
    )
    return (
        '<section class="case-card">'
        '<div class="case-header">'
        f'<div><div class="eyebrow">{escape(item.get("topic"))}</div><h2>{escape(item.get("case_ref"))}</h2></div>'
        f'<div class="status">{escape(item.get("alignment_status"))}</div>'
        "</div>"
        '<div class="case-meta">'
        f'<p><strong>Source:</strong> <a href="{escape(item.get("source_url"))}">{escape(item.get("source_url"))}</a></p>'
        f'<p><strong>Trade models:</strong> {escape(", ".join(item.get("trade_models", [])) or "n/a")}</p>'
        f'<p><strong>Relation types:</strong> {escape(", ".join(item.get("relation_types", [])) or "n/a")}</p>'
        f'<p><strong>Confidence:</strong> {escape(item.get("confidence") if item.get("confidence") is not None else "n/a")}</p>'
        f'<p><strong>Bars suggestion:</strong> {escape(item.get("bars_path_suggestion") or "n/a")}</p>'
        f'<p><strong>Source image kind:</strong> {escape(item.get("source_image_kind") or "unknown")}</p>'
        f'<p><strong>Notes:</strong> {escape(item.get("market_context_notes") or "n/a")}</p>'
        "</div>"
        '<div class="case-columns">'
        f'<div class="case-panel"><h3>Review Checklist</h3>{checklist}</div>'
        f'<div class="case-panel"><h3>Evidence Refs</h3>{evidence}</div>'
        "</div>"
        '<div class="case-panel">'
        "<h3>Checkpoint Gallery</h3>"
        f'<div class="checkpoint-grid">{render_checkpoint_gallery(item.get("checkpoint_samples", []))}</div>'
        "</div>"
        '<div class="case-panel">'
        "<h3>Override Template</h3>"
        f'<pre>{escape(item.get("override_template_json"))}</pre>'
        "</div>"
        "</section>"
    )


def render_review_dashboard_html(report: dict[str, Any]) -> str:
    summary = report.get("summary", {})
    items_markup = "".join(render_case_card(item) for item in report.get("items", []))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>TTFM Market Context Review</title>
  <style>
    :root {{
      --bg: #0d1016;
      --panel: #151b24;
      --panel-2: #10151d;
      --text: #eef3fa;
      --muted: #96a2b3;
      --line: rgba(255,255,255,0.08);
      --accent: #ffc266;
      --accent-2: #77d9c3;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(255, 194, 102, 0.18), transparent 25%),
        linear-gradient(180deg, #121722 0%, var(--bg) 100%);
      font-family: "Aptos", "Segoe UI", sans-serif;
    }}
    .shell {{ max-width: 1440px; margin: 0 auto; padding: 28px 20px 60px; }}
    .hero, .case-card, .summary-grid article {{
      border: 1px solid var(--line);
      background: linear-gradient(180deg, rgba(21, 27, 36, 0.96), rgba(11, 16, 23, 0.98));
      border-radius: 22px;
      box-shadow: 0 20px 44px rgba(0,0,0,0.28);
    }}
    .hero {{ padding: 28px; margin-bottom: 18px; }}
    .eyebrow {{
      color: var(--accent);
      text-transform: uppercase;
      letter-spacing: 0.18em;
      font-size: 12px;
      margin-bottom: 10px;
    }}
    h1 {{ margin: 0; font-size: clamp(2rem, 4vw, 3.6rem); line-height: 0.95; letter-spacing: -0.04em; }}
    h2 {{ margin: 0; font-size: 1.35rem; line-height: 1.2; }}
    h3 {{ margin: 0 0 12px; font-size: 1rem; text-transform: uppercase; letter-spacing: 0.12em; color: var(--accent); }}
    h4 {{ margin: 0 0 10px; font-size: 1rem; }}
    p, li {{ color: var(--muted); line-height: 1.65; }}
    a {{ color: var(--accent-2); }}
    .summary-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 14px;
      margin-bottom: 18px;
    }}
    .summary-grid article {{ padding: 18px; }}
    .summary-label {{ color: var(--muted); font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.08em; }}
    .summary-value {{ margin-top: 12px; font-size: 2rem; font-weight: 700; }}
    .case-list {{ display: grid; gap: 18px; }}
    .case-card {{ padding: 22px; }}
    .case-header {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: start;
      margin-bottom: 14px;
    }}
    .status {{
      padding: 8px 12px;
      border-radius: 999px;
      border: 1px solid rgba(255, 194, 102, 0.25);
      background: rgba(255, 194, 102, 0.08);
      color: var(--accent);
      white-space: nowrap;
      text-transform: uppercase;
      font-size: 12px;
      letter-spacing: 0.12em;
    }}
    .case-meta {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px 18px;
      margin-bottom: 16px;
    }}
    .case-meta p {{ margin: 0; }}
    .case-columns {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
      margin-bottom: 16px;
    }}
    .case-panel {{
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 16px;
      background: var(--panel-2);
    }}
    .checkpoint-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
    }}
    .checkpoint-card {{
      border: 1px solid var(--line);
      border-radius: 16px;
      overflow: hidden;
      background: rgba(255,255,255,0.02);
    }}
    .checkpoint-image {{
      background: #0a0e14;
      min-height: 220px;
      display: flex;
      align-items: center;
      justify-content: center;
    }}
    .checkpoint-image img {{
      display: block;
      width: 100%;
      height: auto;
      object-fit: contain;
    }}
    .checkpoint-body {{ padding: 14px; }}
    .checkpoint-kicker {{
      color: var(--accent);
      font-size: 12px;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      margin-bottom: 10px;
    }}
    pre {{
      margin: 0;
      padding: 14px;
      overflow-x: auto;
      border-radius: 14px;
      background: #0b1016;
      color: #dce6f2;
      border: 1px solid var(--line);
      line-height: 1.5;
    }}
    .muted {{ color: var(--muted); }}
    .image-missing {{ color: var(--muted); }}
    ul {{ margin: 0; padding-left: 18px; }}
    @media (max-width: 1080px) {{
      .summary-grid, .case-meta, .case-columns, .checkpoint-grid {{ grid-template-columns: 1fr; }}
      .case-header {{ flex-direction: column; }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <div class="eyebrow">Teacher Visual Review</div>
      <h1>Market-context promotion queue for TTFM.</h1>
      <p class="muted">Use this dashboard to decide whether each teacher case can accept a trusted anchor timestamp now or still needs alternate chart evidence before any anchor should be set in <code>data/ttfm_market_context_map.json</code>.</p>
      <p class="muted">Generated at {escape(report.get("generated_at"))}</p>
    </section>
    <section class="summary-grid">
      <article><div class="summary-label">Cases</div><div class="summary-value">{escape(summary.get("case_count", 0))}</div></article>
      <article><div class="summary-label">Market Context Only</div><div class="summary-value">{escape(summary.get("alignment_status_counts", {}).get("market_context_only", 0))}</div></article>
      <article><div class="summary-label">Unmapped</div><div class="summary-value">{escape(summary.get("alignment_status_counts", {}).get("unmapped", 0))}</div></article>
      <article><div class="summary-label">Need Anchors</div><div class="summary-value">{escape(summary.get("recommended_action_counts", {}).get("confirm_anchor_timestamp", 0))}</div></article>
      <article><div class="summary-label">Need Alt Evidence</div><div class="summary-value">{escape(summary.get("recommended_action_counts", {}).get("find_alternate_chart_evidence", 0))}</div></article>
      <article><div class="summary-label">Article Images</div><div class="summary-value">{escape(summary.get("source_image_kind_counts", {}).get("source_article_image", 0))}</div></article>
    </section>
    <section class="case-list">
      {items_markup}
    </section>
  </div>
</body>
</html>
"""


def write_outputs(
    report: dict[str, Any],
    override_seed_map: dict[str, Any],
    *,
    html_output_path: Path,
    override_output_path: Path,
) -> None:
    html_output_path.parent.mkdir(parents=True, exist_ok=True)
    html_output_path.write_text(render_review_dashboard_html(report), encoding="utf-8")
    override_output_path.parent.mkdir(parents=True, exist_ok=True)
    override_output_path.write_text(json.dumps(override_seed_map, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export a visual review dashboard and override template pack for TTFM market-context promotion."
    )
    parser.add_argument("--queue", default=str(DEFAULT_QUEUE_PATH))
    parser.add_argument("--html-output", default=str(DEFAULT_HTML_OUTPUT))
    parser.add_argument("--override-output", default=str(DEFAULT_OVERRIDE_OUTPUT))
    args = parser.parse_args()

    html_output_path = Path(args.html_output)
    queue = load_json(Path(args.queue), {"summary": {}, "items": []})
    report = build_review_dashboard_report(queue, html_output_path=html_output_path)
    override_seed_map = build_override_seed_map(queue)
    override_output_path = Path(args.override_output)
    write_outputs(
        report,
        override_seed_map,
        html_output_path=html_output_path,
        override_output_path=override_output_path,
    )
    print(
        json.dumps(
            {
                "html_output": str(html_output_path),
                "override_output": str(override_output_path),
                "case_count": report.get("summary", {}).get("case_count", 0),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
