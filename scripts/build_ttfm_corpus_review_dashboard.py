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


DEFAULT_PACKET_PATH = Path("results") / "ttfm_corpus_prep_packet.json"
DEFAULT_TEMPLATE_PATH = Path("results") / "ttfm_corpus_prep_phase2_answers.example.json"
DEFAULT_OUTPUT_PATH = Path("results") / "ttfm_corpus_review_dashboard.html"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve(root_dir: Path, path: Path) -> Path:
    return path if path.is_absolute() else root_dir / path


def image_src(path: str, *, root_dir: Path, output_path: Path) -> str:
    cleaned = str(path or "").strip()
    if not cleaned:
        return ""
    image_path = Path(cleaned).resolve()
    try:
        relative = image_path.relative_to(root_dir)
    except ValueError:
        return image_path.as_uri()
    return Path("..", *relative.parts).as_posix() if output_path.parent == root_dir / "results" else relative.as_posix()


def answer_lookup(template: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("example_id", "")).strip(): item
        for item in template.get("items", [])
        if str(item.get("example_id", "")).strip()
    }


def item_card(
    item: dict[str, Any],
    answer_item: dict[str, Any] | None,
    *,
    root_dir: Path,
    output_path: Path,
) -> str:
    example_id = str(item.get("example_id", ""))
    labels = [str(label) for label in item.get("candidate_labels", [])]
    reasons = [str(reason) for reason in item.get("selection_reasons", [])]
    neighbors = item.get("embedding_neighbors", [])
    google_context = item.get("google_text_context", [])
    answer_payload = {
        "example_id": example_id,
        "detections": [],
        "review_outcome": "ambiguous",
        "note": str((answer_item or {}).get("note", "Review required before YOLO promotion.")),
    }
    answer_json = json.dumps(answer_payload, indent=2)
    neighbor_text = "\n".join(
        f"{neighbor.get('similarity')}: {neighbor.get('example_id')} [{', '.join(neighbor.get('class_names', []))}]"
        for neighbor in neighbors[:3]
    )
    context_text = "\n\n".join(
        f"{ctx.get('chunk_id')} (overlap {ctx.get('overlap_score')}): {ctx.get('text_excerpt')}"
        for ctx in google_context[:2]
    )
    return f"""
    <article class="card" data-action="{html.escape(str(item.get("recommended_action", "")))}">
      <div class="media">
        <img src="{html.escape(image_src(str(item.get("image_path", "")), root_dir=root_dir, output_path=output_path))}" alt="{html.escape(example_id)}" loading="lazy" />
      </div>
      <div class="body">
        <div class="topline">
          <span class="score">score {html.escape(str(item.get("score", "")))}</span>
          <span class="action">{html.escape(str(item.get("recommended_action", "")))}</span>
        </div>
        <h2>{html.escape(example_id)}</h2>
        <p class="meta">{html.escape(str(item.get("title", "")))} | {html.escape(str(item.get("checkpoint", "")))} | {html.escape(str(item.get("start", "")))}</p>
        <div class="chips">{''.join(f'<span>{html.escape(label)}</span>' for label in labels)}</div>
        <details open>
          <summary>Transcript / Audio</summary>
          <p>{html.escape(str(item.get("transcript_excerpt", "")))}</p>
          <p>{html.escape(str(item.get("audio_excerpt", "")))}</p>
        </details>
        <details>
          <summary>Evidence</summary>
          <pre>{html.escape("Reasons: " + ", ".join(reasons))}</pre>
          <pre>{html.escape(neighbor_text or "No embedding neighbors")}</pre>
          <pre>{html.escape(context_text or "No Google text context")}</pre>
        </details>
        <details>
          <summary>Phase 2 Answer Template</summary>
          <pre>{html.escape(answer_json)}</pre>
        </details>
      </div>
    </article>
    """


def build_dashboard(packet: dict[str, Any], template: dict[str, Any], *, root_dir: Path, output_path: Path) -> str:
    lookup = answer_lookup(template)
    items = list(packet.get("items", []))
    counts: dict[str, int] = {}
    for item in items:
        action = str(item.get("recommended_action", ""))
        counts[action] = counts.get(action, 0) + 1
    cards = "\n".join(
        item_card(
            item,
            lookup.get(str(item.get("example_id", "")).strip()),
            root_dir=root_dir,
            output_path=output_path,
        )
        for item in items
    )
    counts_text = " | ".join(f"{key}: {value}" for key, value in sorted(counts.items()))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>TTFM Corpus Review Dashboard</title>
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
      padding: 14px 20px;
      border-bottom: 1px solid #314041;
      background: #151b1e;
    }}
    h1 {{
      margin: 0 0 4px;
      font-size: 20px;
      font-weight: 650;
    }}
    header p {{
      margin: 0;
      color: #aebdba;
      font-size: 13px;
    }}
    main {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(520px, 1fr));
      gap: 12px;
      padding: 12px;
    }}
    .card {{
      display: grid;
      grid-template-columns: minmax(220px, 42%) 1fr;
      min-height: 340px;
      border: 1px solid #2d3a3c;
      background: #161d20;
      border-radius: 8px;
      overflow: hidden;
    }}
    .media {{
      background: #080b0c;
      display: flex;
      align-items: center;
      justify-content: center;
      min-width: 0;
    }}
    img {{
      width: 100%;
      height: 100%;
      object-fit: contain;
      display: block;
    }}
    .body {{
      padding: 12px;
      min-width: 0;
    }}
    .topline {{
      display: flex;
      justify-content: space-between;
      gap: 8px;
      color: #aebdba;
      font-size: 12px;
      margin-bottom: 8px;
    }}
    h2 {{
      margin: 0 0 6px;
      font-size: 14px;
      line-height: 1.25;
      overflow-wrap: anywhere;
    }}
    .meta {{
      margin: 0 0 8px;
      font-size: 12px;
      color: #aebdba;
      overflow-wrap: anywhere;
    }}
    .chips {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-bottom: 10px;
    }}
    .chips span {{
      padding: 3px 7px;
      border-radius: 999px;
      background: #223436;
      border: 1px solid #3f5d60;
      color: #d9fffb;
      font-size: 11px;
    }}
    details {{
      border-top: 1px solid #293537;
      padding-top: 8px;
      margin-top: 8px;
    }}
    summary {{
      cursor: pointer;
      color: #d7e1df;
      font-size: 12px;
      font-weight: 650;
    }}
    p, pre {{
      font-size: 12px;
      line-height: 1.45;
      color: #c6d2cf;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }}
    pre {{
      padding: 8px;
      background: #0f1416;
      border-radius: 6px;
      border: 1px solid #263335;
    }}
    @media (max-width: 720px) {{
      main {{
        grid-template-columns: 1fr;
      }}
      .card {{
        grid-template-columns: 1fr;
      }}
      .media {{
        min-height: 260px;
      }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>TTFM Corpus Review Dashboard</h1>
    <p>{len(items)} candidates | {html.escape(counts_text)} | candidates are not training labels until reviewed</p>
  </header>
  <main>
    {cards}
  </main>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> Path:
    parser = argparse.ArgumentParser(description="Build an HTML review dashboard for the TTFM corpus prep packet.")
    parser.add_argument("--root-dir", type=Path, default=Path.cwd())
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args(argv)

    root_dir = args.root_dir.resolve()
    packet = load_json(resolve(root_dir, args.packet))
    template = load_json(resolve(root_dir, args.template))
    output_path = resolve(root_dir, args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_dashboard(packet, template, root_dir=root_dir, output_path=output_path), encoding="utf-8")
    print(json.dumps({"output_path": str(output_path.resolve()), "item_count": len(packet.get("items", []))}, indent=2))
    return output_path


if __name__ == "__main__":
    main()
