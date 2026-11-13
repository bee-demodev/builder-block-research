from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


DEFAULT_PACKET_PATH = Path("results") / "ttrades_state_review_packet_20260622.json"
DEFAULT_ANSWERS_PATH = Path("results") / "ttrades_state_review_answers.seed_20260622.json"
DEFAULT_OUTPUT_PATH = Path("results") / "ttrades_state_review_dashboard_20260622.html"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve(root_dir: Path, path: Path) -> Path:
    return path if path.is_absolute() else root_dir / path


def image_src(path: str, *, root_dir: Path, output_path: Path) -> str:
    cleaned = str(path or "").strip()
    if not cleaned:
        return ""
    image_path = Path(cleaned)
    if not image_path.is_absolute():
        image_path = root_dir / image_path
    image_path = image_path.resolve()
    try:
        relative_to_output = image_path.relative_to(output_path.parent.resolve())
        return relative_to_output.as_posix()
    except ValueError:
        pass
    try:
        relative_to_root = image_path.relative_to(root_dir.resolve())
        return Path("..", *relative_to_root.parts).as_posix() if output_path.parent.resolve() == (root_dir / "results").resolve() else relative_to_root.as_posix()
    except ValueError:
        return image_path.as_uri()


def answer_lookup(answers: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("example_id", "")).strip(): item
        for item in answers.get("items", [])
        if str(item.get("example_id", "")).strip()
    }


def chips(values: list[str], *, class_name: str = "") -> str:
    suffix = f' class="{html.escape(class_name)}"' if class_name else ""
    return "".join(f"<span{suffix}>{html.escape(str(value))}</span>" for value in values)


def compact_state(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "path_family": state.get("path_family"),
        "direction": state.get("direction"),
        "fractal_stage": state.get("fractal_stage"),
        "htf_bias": state.get("htf_bias"),
        "timeframe_alignment": state.get("timeframe_alignment"),
        "poi": state.get("poi"),
        "setup_quality": state.get("setup_quality"),
        "entry_state": state.get("entry_state"),
        "invalidation": state.get("invalidation"),
        "state_confidence": state.get("state_confidence"),
    }


def evidence_block(evidence: list[dict[str, Any]]) -> str:
    if not evidence:
        return "<p>No corpus evidence attached.</p>"
    rows: list[str] = []
    for item in evidence[:3]:
        topics = ", ".join(str(topic) for topic in item.get("topics", []))
        rows.append(
            f"""
            <div class="evidence">
              <div class="evidence-head">
                <strong>{html.escape(str(item.get("title", "")))}</strong>
                <span>score {html.escape(str(item.get("score", "")))}</span>
              </div>
              <p class="meta">{html.escape(str(item.get("chunk_id", "")))} | {html.escape(topics)}</p>
              <p>{html.escape(str(item.get("claim", "")))}</p>
              <p class="meta">{html.escape(str(item.get("source_path", "")))}</p>
            </div>
            """
        )
    return "\n".join(rows)


def item_card(
    item: dict[str, Any],
    answer_item: dict[str, Any] | None,
    *,
    root_dir: Path,
    output_path: Path,
) -> str:
    example_id = str(item.get("example_id", ""))
    chart_paths = item.get("chart_paths", {}) if isinstance(item.get("chart_paths"), dict) else {}
    state = item.get("candidate_state", {}) if isinstance(item.get("candidate_state"), dict) else {}
    decision = item.get("candidate_decision", {}) if isinstance(item.get("candidate_decision"), dict) else {}
    answer_payload = answer_item or {
        "example_id": example_id,
        "review_outcome": "needs_review",
        "training_eligible": False,
        "state_labels": state,
        "decision_label": {"verdict": "insufficient_evidence"},
        "reviewer_notes": [],
    }
    missing = [str(value) for value in state.get("missing_evidence", [])]
    review_fields = [str(value) for value in item.get("review_fields_required", [])]
    selection_reasons = [str(value) for value in item.get("selection_reasons", [])]
    return f"""
    <article class="card">
      <div class="card-head">
        <div>
          <h2>{html.escape(example_id)}</h2>
          <p class="meta">{html.escape(str(item.get("source", "")))} | priority {html.escape(str(item.get("priority_score", "")))}</p>
        </div>
        <div class="status">
          <span>{html.escape(str(item.get("review_outcome", "")))}</span>
          <span>trainable: {html.escape(str(item.get("training_eligible", False)).lower())}</span>
        </div>
      </div>
      <div class="charts">
        <figure>
          <img src="{html.escape(image_src(str(chart_paths.get("daily", "")), root_dir=root_dir, output_path=output_path))}" alt="{html.escape(example_id)} daily" loading="lazy" />
          <figcaption>Daily / HTF</figcaption>
        </figure>
        <figure>
          <img src="{html.escape(image_src(str(chart_paths.get("h1", "")), root_dir=root_dir, output_path=output_path))}" alt="{html.escape(example_id)} h1" loading="lazy" />
          <figcaption>1h</figcaption>
        </figure>
        <figure>
          <img src="{html.escape(image_src(str(chart_paths.get("m5", "")), root_dir=root_dir, output_path=output_path))}" alt="{html.escape(example_id)} m5" loading="lazy" />
          <figcaption>5m</figcaption>
        </figure>
      </div>
      <div class="grid">
        <section>
          <h3>Missing Evidence</h3>
          <div class="chips danger">{chips(missing)}</div>
          <h3>Review Fields</h3>
          <div class="chips">{chips(review_fields)}</div>
          <h3>Selection Reasons</h3>
          <div class="chips">{chips(selection_reasons)}</div>
        </section>
        <section>
          <h3>Candidate State</h3>
          <pre>{html.escape(json.dumps(compact_state(state), indent=2))}</pre>
          <h3>Candidate Decision</h3>
          <pre>{html.escape(json.dumps(decision, indent=2))}</pre>
        </section>
        <section>
          <h3>Corpus Evidence</h3>
          {evidence_block(item.get("corpus_evidence", []))}
        </section>
        <section>
          <h3>Answer Template</h3>
          <pre>{html.escape(json.dumps(answer_payload, indent=2))}</pre>
        </section>
      </div>
    </article>
    """


def build_dashboard(packet: dict[str, Any], answers: dict[str, Any], *, root_dir: Path, output_path: Path) -> str:
    lookup = answer_lookup(answers)
    items = list(packet.get("items", []))
    summary = packet.get("selection_summary", {}) if isinstance(packet.get("selection_summary"), dict) else {}
    missing_counts = summary.get("missing_evidence_counts", {}) if isinstance(summary.get("missing_evidence_counts"), dict) else {}
    cards = "\n".join(
        item_card(
            item,
            lookup.get(str(item.get("example_id", "")).strip()),
            root_dir=root_dir,
            output_path=output_path,
        )
        for item in items
    )
    missing_text = " | ".join(f"{key}: {value}" for key, value in sorted(missing_counts.items()))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>TTrades State Review Dashboard</title>
  <style>
    :root {{
      color-scheme: dark;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #101416;
      color: #edf2f0;
    }}
    body {{
      margin: 0;
      background: #101416;
    }}
    header {{
      position: sticky;
      top: 0;
      z-index: 2;
      padding: 14px 18px;
      border-bottom: 1px solid #314041;
      background: #151b1e;
    }}
    h1 {{
      margin: 0 0 4px;
      font-size: 20px;
      font-weight: 650;
    }}
    header p, .meta {{
      margin: 0;
      color: #aebdba;
      font-size: 12px;
      overflow-wrap: anywhere;
    }}
    main {{
      display: grid;
      gap: 14px;
      padding: 14px;
    }}
    .card {{
      border: 1px solid #2d3a3c;
      background: #161d20;
      border-radius: 8px;
      overflow: hidden;
    }}
    .card-head {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      padding: 12px;
      border-bottom: 1px solid #293537;
    }}
    h2 {{
      margin: 0 0 4px;
      font-size: 15px;
      overflow-wrap: anywhere;
    }}
    h3 {{
      margin: 0 0 8px;
      font-size: 12px;
      color: #d7e1df;
      text-transform: uppercase;
      letter-spacing: 0;
    }}
    .status {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      justify-content: flex-end;
      align-content: flex-start;
    }}
    .status span, .chips span {{
      padding: 3px 7px;
      border-radius: 999px;
      background: #223436;
      border: 1px solid #3f5d60;
      color: #d9fffb;
      font-size: 11px;
    }}
    .charts {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 1px;
      background: #293537;
    }}
    figure {{
      margin: 0;
      min-height: 260px;
      background: #080b0c;
      display: grid;
      grid-template-rows: 1fr auto;
    }}
    img {{
      width: 100%;
      height: 100%;
      max-height: 440px;
      object-fit: contain;
      display: block;
    }}
    figcaption {{
      padding: 6px 8px;
      background: #111719;
      color: #aebdba;
      font-size: 12px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      padding: 12px;
    }}
    section {{
      min-width: 0;
    }}
    .chips {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-bottom: 12px;
    }}
    .chips.danger span {{
      border-color: #7f4f24;
      background: #2f2418;
      color: #ffe1ba;
    }}
    pre {{
      margin: 0 0 12px;
      padding: 8px;
      background: #0f1416;
      border-radius: 6px;
      border: 1px solid #263335;
      color: #c6d2cf;
      font-size: 12px;
      line-height: 1.45;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }}
    .evidence {{
      border: 1px solid #263335;
      border-radius: 6px;
      padding: 8px;
      margin-bottom: 8px;
      background: #111719;
    }}
    .evidence-head {{
      display: flex;
      justify-content: space-between;
      gap: 8px;
      font-size: 12px;
    }}
    .evidence p {{
      margin: 6px 0 0;
      color: #c6d2cf;
      font-size: 12px;
      line-height: 1.45;
      overflow-wrap: anywhere;
    }}
    @media (max-width: 1100px) {{
      .charts, .grid {{
        grid-template-columns: 1fr;
      }}
      .card-head {{
        display: block;
      }}
      .status {{
        justify-content: flex-start;
        margin-top: 8px;
      }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>TTrades State Review Dashboard</h1>
    <p>{len(items)} candidates | corpus evidence rows: {html.escape(str(summary.get("corpus_evidence_item_count", 0)))} | {html.escape(missing_text)}</p>
  </header>
  <main>
    {cards}
  </main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a visual dashboard for TTrades state-review candidates.")
    parser.add_argument("--root-dir", type=Path, default=Path("."))
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    parser.add_argument("--answers", type=Path, default=DEFAULT_ANSWERS_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root_dir = args.root_dir.resolve()
    packet_path = resolve(root_dir, args.packet)
    answers_path = resolve(root_dir, args.answers)
    output_path = resolve(root_dir, args.output)
    packet = load_json(packet_path)
    answers = load_json(answers_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        build_dashboard(packet, answers, root_dir=root_dir, output_path=output_path),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output_path": str(output_path),
                "candidate_count": len(packet.get("items", [])),
                "corpus_evidence_item_count": packet.get("selection_summary", {}).get("corpus_evidence_item_count", 0),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
