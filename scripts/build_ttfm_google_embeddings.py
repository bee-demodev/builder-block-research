from __future__ import annotations

import argparse
import json
from pathlib import Path

import ttfm_video_embeddings as tve


def build_embeddings(
    *,
    chunks_path: Path,
    index_path: Path,
    manifest_path: Path,
    model: str,
    output_dimensionality: int,
    batch_size: int,
) -> dict:
    api_key = tve.resolve_google_api_key()
    rows = tve.load_chunk_rows(chunks_path)
    documents = tve.prepare_embedding_documents(rows)
    vectors = tve.embed_texts_with_google(
        [document["embedding_text"] for document in documents],
        api_key=api_key,
        model=model,
        task_type="RETRIEVAL_DOCUMENT",
        output_dimensionality=output_dimensionality,
        batch_size=batch_size,
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
        source_path=chunks_path,
        source_fingerprint=tve.fingerprint_file(chunks_path),
    )
    return {
        **manifest,
        "ok": True,
        "chunks_path": tve.path_for_manifest(chunks_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a Google-backed embedding index for the TTFM video corpus.")
    parser.add_argument("--chunks-path", type=Path, default=tve.CHUNKS_PATH)
    parser.add_argument("--index-path", type=Path, default=tve.INDEX_PATH)
    parser.add_argument("--manifest-path", type=Path, default=tve.MANIFEST_PATH)
    parser.add_argument("--model", default=tve.DEFAULT_MODEL)
    parser.add_argument("--output-dimensionality", type=int, default=tve.DEFAULT_OUTPUT_DIMENSIONALITY)
    parser.add_argument("--batch-size", type=int, default=tve.DEFAULT_BATCH_SIZE)
    args = parser.parse_args()

    print(
        json.dumps(
            build_embeddings(
                chunks_path=args.chunks_path,
                index_path=args.index_path,
                manifest_path=args.manifest_path,
                model=args.model,
                output_dimensionality=args.output_dimensionality,
                batch_size=args.batch_size,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
