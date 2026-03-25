from __future__ import annotations

import argparse
import json
from pathlib import Path

import ttfm_video_embeddings as tve


def run_query(*, query: str, index_path: Path, top_k: int) -> dict:
    api_key = tve.resolve_google_api_key()
    index = tve.load_embedding_index(index_path)
    matches = tve.search_embedding_index(index, query=query, api_key=api_key, top_k=top_k)
    return {
        "query": query,
        "top_k": top_k,
        "model": index.get("model", tve.DEFAULT_MODEL),
        "output_dimensionality": index.get(
            "output_dimensionality", tve.DEFAULT_OUTPUT_DIMENSIONALITY
        ),
        "index_path": tve.path_for_manifest(index_path),
        "matches": matches,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Search the TTFM video corpus using Google embeddings.")
    parser.add_argument("--query", required=True)
    parser.add_argument("--index-path", type=Path, default=tve.INDEX_PATH)
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    print(json.dumps(run_query(query=args.query, index_path=args.index_path, top_k=args.top_k), indent=2))


if __name__ == "__main__":
    main()
