from __future__ import annotations

import argparse
import json
from pathlib import Path

import ttfm_video_embeddings as tve


def validate_corpus(*, manifest_path: Path, chunks_path: Path) -> dict:
    if not manifest_path.exists():
        raise FileNotFoundError(f"Video manifest not found: {manifest_path}")
    if not chunks_path.exists():
        raise FileNotFoundError(f"Chunk corpus not found: {chunks_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    chunk_rows = tve.load_chunk_rows(chunks_path)

    missing_paths: list[str] = []
    for video in manifest.get("videos", []):
        for key in ("transcript_path", "transcript_json_path"):
            path_value = str(video.get(key, "")).strip()
            if not path_value:
                missing_paths.append(f"(missing {key} in manifest)")
                continue
            artifact_path = tve.ROOT / Path(path_value)
            if not artifact_path.exists():
                missing_paths.append(str(artifact_path))

    if missing_paths:
        raise RuntimeError(
            f"TTFM corpus is incomplete. Missing {len(missing_paths)} referenced transcript artifacts."
        )

    return {
        "ok": True,
        "corpus_dir": tve.path_for_manifest(manifest_path.parent),
        "video_count": int(manifest.get("video_count", 0)),
        "chunk_count": len(chunk_rows),
        "manifest_path": tve.path_for_manifest(manifest_path),
        "chunks_path": tve.path_for_manifest(chunks_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the local TTFM video transcript corpus.")
    parser.add_argument("--manifest-path", type=Path, default=tve.CORPUS_DIR / "video_manifest.json")
    parser.add_argument("--chunks-path", type=Path, default=tve.CHUNKS_PATH)
    args = parser.parse_args()

    print(json.dumps(validate_corpus(manifest_path=args.manifest_path, chunks_path=args.chunks_path), indent=2))


if __name__ == "__main__":
    main()
