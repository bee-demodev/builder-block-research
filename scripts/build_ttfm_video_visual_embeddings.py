from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import ttfm_video_embeddings as tve


ROOT = Path(__file__).resolve().parent.parent
CORPUS_DIR = ROOT / "knowledge" / "ttfm_video_corpus"
DEFAULT_WINDOWS_PATH = CORPUS_DIR / "visual_windows.jsonl"
DEFAULT_INDEX_PATH = CORPUS_DIR / "visual_embedding_index.json"
DEFAULT_MANIFEST_PATH = CORPUS_DIR / "visual_embedding_manifest.json"
DEFAULT_REPORT_PATH = CORPUS_DIR / "visual_embedding_report.json"


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            cleaned = line.strip()
            if cleaned:
                rows.append(json.loads(cleaned))
    return rows


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def build_visual_embeddings(
    *,
    windows_path: Path,
    index_path: Path,
    manifest_path: Path,
    report_path: Path,
    model: str,
    output_dimensionality: int,
) -> dict:
    api_key = tve.resolve_google_api_key()
    rows = load_jsonl(windows_path)
    documents = tve.prepare_multimodal_embedding_documents(rows)
    vectors, diagnostics = tve.embed_multimodal_documents_with_google(
        documents,
        api_key=api_key,
        model=model,
        task_type="RETRIEVAL_DOCUMENT",
        output_dimensionality=output_dimensionality,
    )
    index = tve.build_embedding_index(
        documents,
        vectors,
        model=model,
        output_dimensionality=output_dimensionality,
    )
    manifest = tve.save_embedding_index(
        index,
        index_path=index_path,
        manifest_path=manifest_path,
        source_path=windows_path,
        source_fingerprint=tve.fingerprint_file(windows_path),
    )

    frame_status_counts: Counter[str] = Counter(
        str(row.get("frame_status", "unknown")) for row in rows
    )
    diagnostics_summary = {
        "document_count": len(documents),
        "asset_backed_document_count": sum(1 for item in diagnostics if item.get("used_asset")),
        "text_fallback_count": sum(
            1 for item in diagnostics if item.get("used_text_fallback")
        ),
        "frame_status_counts": dict(sorted(frame_status_counts.items())),
    }
    write_json(
        report_path,
        {
            "windows_path": tve.path_for_manifest(windows_path),
            "index_path": tve.path_for_manifest(index_path),
            "manifest_path": tve.path_for_manifest(manifest_path),
            "model": model,
            "output_dimensionality": output_dimensionality,
            "summary": diagnostics_summary,
            "diagnostics": diagnostics,
        },
    )
    return {
        **manifest,
        "ok": True,
        "windows_path": tve.path_for_manifest(windows_path),
        "report_path": tve.path_for_manifest(report_path),
        "text_fallback_count": diagnostics_summary["text_fallback_count"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build a Gemini Embedding 2 multimodal index for checkpoint-level TTFM YouTube visual windows."
        )
    )
    parser.add_argument("--windows-path", type=Path, default=DEFAULT_WINDOWS_PATH)
    parser.add_argument("--index-path", type=Path, default=DEFAULT_INDEX_PATH)
    parser.add_argument("--manifest-path", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--report-path", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--model", default=tve.DEFAULT_MULTIMODAL_MODEL)
    parser.add_argument(
        "--output-dimensionality",
        type=int,
        default=tve.DEFAULT_OUTPUT_DIMENSIONALITY,
    )
    args = parser.parse_args()

    print(
        json.dumps(
            build_visual_embeddings(
                windows_path=args.windows_path,
                index_path=args.index_path,
                manifest_path=args.manifest_path,
                report_path=args.report_path,
                model=args.model,
                output_dimensionality=args.output_dimensionality,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
