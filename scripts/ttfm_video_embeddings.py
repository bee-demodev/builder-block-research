from __future__ import annotations

import base64
import hashlib
import json
import math
import mimetypes
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parent.parent
CORPUS_DIR = ROOT / "knowledge" / "ttfm_video_corpus"
CHUNKS_PATH = CORPUS_DIR / "chunks.jsonl"
INDEX_PATH = CORPUS_DIR / "google_embedding_index.json"
MANIFEST_PATH = CORPUS_DIR / "google_embedding_manifest.json"

DEFAULT_MODEL = "models/gemini-embedding-001"
DEFAULT_MULTIMODAL_MODEL = "models/gemini-embedding-2-preview"
DEFAULT_OUTPUT_DIMENSIONALITY = 768
DEFAULT_BATCH_SIZE = 24
DEFAULT_TIMEOUT_SECONDS = 90
GOOGLE_API_KEY_ENV_NAMES = (
    "GOOGLE_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_GENAI_API_KEY",
)
DEFAULT_GOOGLE_API_KEY_FILES = (
    ROOT / ".env.local",
    ROOT / ".env",
)


def path_for_manifest(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def fingerprint_file(path: Path) -> str:
    hasher = hashlib.sha1()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def parse_env_assignment(line: str) -> tuple[str, str] | None:
    cleaned = line.strip()
    if not cleaned or cleaned.startswith("#"):
        return None
    if cleaned.startswith("export "):
        cleaned = cleaned[len("export ") :].strip()
    if "=" not in cleaned:
        return None
    key, raw_value = cleaned.split("=", 1)
    key = key.strip()
    if not key:
        return None
    value = raw_value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    elif " #" in value:
        value = value.split(" #", 1)[0].rstrip()
    return key, value


def load_env_values(paths: Sequence[Path]) -> dict[str, str]:
    values: dict[str, str] = {}
    for path in paths:
        if not path.exists() or not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            parsed = parse_env_assignment(line)
            if parsed is None:
                continue
            key, value = parsed
            values.setdefault(key, value)
    return values


def resolve_google_api_key(
    env: Mapping[str, str] | None = None,
    *,
    env_files: Sequence[Path] | None = None,
) -> str:
    source = env if env is not None else os.environ
    for name in GOOGLE_API_KEY_ENV_NAMES:
        api_key = str(source.get(name, "")).strip()
        if api_key:
            return api_key

    file_values = load_env_values(
        tuple(env_files) if env_files is not None else DEFAULT_GOOGLE_API_KEY_FILES
    )
    for name in GOOGLE_API_KEY_ENV_NAMES:
        api_key = str(file_values.get(name, "")).strip()
        if api_key:
            return api_key

    accepted_names = ", ".join(GOOGLE_API_KEY_ENV_NAMES)
    searched_files = ", ".join(path_for_manifest(path) for path in DEFAULT_GOOGLE_API_KEY_FILES)
    raise RuntimeError(
        "A Google Gemini API key is required to build or query the Google embedding index. "
        f"Set one of: {accepted_names}. "
        f"Also checked repo env files: {searched_files}."
    )


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_chunk_rows(chunks_path: Path = CHUNKS_PATH) -> list[dict]:
    rows: list[dict] = []
    with chunks_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            cleaned = line.strip()
            if cleaned:
                rows.append(json.loads(cleaned))
    return rows


def prepare_embedding_documents(rows: Sequence[dict]) -> list[dict]:
    counters: dict[str, int] = {}
    documents: list[dict] = []
    for row in rows:
        video_slug = str(row.get("video_slug", "")).strip()
        if not video_slug:
            raise ValueError("Chunk rows must include a video_slug.")
        index = counters.get(video_slug, 0)
        counters[video_slug] = index + 1

        chunk_id = str(row.get("chunk_id", "")).strip() or f"{video_slug}:{index:04d}"
        title = str(row.get("title", "")).strip()
        topics = [str(topic).strip() for topic in row.get("topics", []) if str(topic).strip()]
        text = str(row.get("text", "")).strip()

        documents.append(
            {
                "chunk_id": chunk_id,
                "video_slug": video_slug,
                "video_id": str(row.get("video_id", "")).strip(),
                "title": title,
                "topics": topics,
                "start": float(row.get("start", 0.0)),
                "end": float(row.get("end", 0.0)),
                "text": text,
                "embedding_text": build_embedding_text(title=title, topics=topics, text=text),
                "source_type": "video",
            }
        )
    return documents


def build_embedding_text(*, title: str, topics: Sequence[str], text: str) -> str:
    topic_text = ", ".join(topics)
    if topic_text:
        return f"Title: {title}\nTopics: {topic_text}\nTranscript: {text}"
    return f"Title: {title}\nTranscript: {text}"


def chunked(items: Sequence[str], size: int) -> Iterable[list[str]]:
    for start in range(0, len(items), size):
        yield list(items[start : start + size])


def normalize_vector(vector: Sequence[float]) -> list[float]:
    magnitude = math.sqrt(sum(float(value) * float(value) for value in vector))
    if magnitude == 0.0:
        return [0.0 for _ in vector]
    return [float(value) / magnitude for value in vector]


def dot_product(left: Sequence[float], right: Sequence[float]) -> float:
    return sum(float(a) * float(b) for a, b in zip(left, right))


def google_batch_embed_endpoint(model: str) -> str:
    return f"https://generativelanguage.googleapis.com/v1beta/{model}:batchEmbedContents"


def google_single_embed_endpoint(model: str) -> str:
    return f"https://generativelanguage.googleapis.com/v1beta/{model}:embedContent"


def post_google_request(
    endpoint: str,
    payload: dict,
    *,
    api_key: str,
    timeout_seconds: int,
) -> dict:
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Google embeddings request failed with status {exc.code}: {details}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Google embeddings request failed: {exc.reason}") from exc


def embed_texts_with_google(
    texts: Sequence[str],
    *,
    api_key: str,
    model: str = DEFAULT_MODEL,
    task_type: str,
    output_dimensionality: int = DEFAULT_OUTPUT_DIMENSIONALITY,
    batch_size: int = DEFAULT_BATCH_SIZE,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> list[list[float]]:
    embeddings: list[list[float]] = []
    endpoint = google_batch_embed_endpoint(model)

    for batch in chunked(list(texts), batch_size):
        payload = {
            "requests": [
                {
                    "model": model,
                    "content": {"parts": [{"text": text}]},
                    "taskType": task_type,
                    "outputDimensionality": output_dimensionality,
                }
                for text in batch
            ]
        }
        body = post_google_request(
            endpoint,
            payload,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
        )

        batch_embeddings = body.get("embeddings", [])
        if len(batch_embeddings) != len(batch):
            raise RuntimeError(
                f"Google embeddings response count mismatch: expected {len(batch)}, got {len(batch_embeddings)}."
            )

        for embedding in batch_embeddings:
            values = embedding.get("values", [])
            embeddings.append(normalize_vector(values))

    return embeddings


def resolve_optional_asset_path(path_value: str | None) -> Path | None:
    cleaned = str(path_value or "").strip()
    if cleaned.lower() in {"none", "null"}:
        return None
    if not cleaned:
        return None
    candidate = Path(cleaned)
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    return candidate


def resolve_first_available_asset_path(*path_values: object) -> Path | None:
    for path_value in path_values:
        resolved = resolve_optional_asset_path(
            path_value if isinstance(path_value, str | type(None)) else str(path_value)
        )
        if resolved is not None:
            return resolved
    return None


def guess_mime_type(path: Path) -> str:
    mime_type, _ = mimetypes.guess_type(path.name)
    return mime_type or "application/octet-stream"


def build_google_content_parts(*, text: str, asset_path: Path | None = None) -> list[dict]:
    parts: list[dict] = []
    if asset_path is not None:
        if not asset_path.exists():
            raise FileNotFoundError(f"Embedding asset does not exist: {asset_path}")
        parts.append(
            {
                "inline_data": {
                    "mime_type": guess_mime_type(asset_path),
                    "data": base64.b64encode(asset_path.read_bytes()).decode("ascii"),
                }
            }
        )
    parts.append({"text": text})
    return parts


def build_visual_embedding_text(
    *,
    title: str,
    checkpoint: str,
    topics: Sequence[str],
    text: str,
    cue_terms: Sequence[str] = (),
    candidate_labels: Sequence[str] = (),
) -> str:
    lines = [
        f"Title: {title}",
        f"Checkpoint: {checkpoint}",
    ]
    if topics:
        lines.append(f"Topics: {', '.join(str(topic).strip() for topic in topics if str(topic).strip())}")
    if cue_terms:
        lines.append(
            "Cue terms: " + ", ".join(str(term).strip() for term in cue_terms if str(term).strip())
        )
    lines.append(f"Transcript window: {text}")
    return "\n".join(lines)


def prepare_multimodal_embedding_documents(rows: Sequence[dict]) -> list[dict]:
    documents: list[dict] = []
    for index, row in enumerate(rows):
        video_slug = str(row.get("video_slug", "")).strip()
        if not video_slug:
            raise ValueError("Visual window rows must include a video_slug.")

        checkpoint = str(row.get("checkpoint", "")).strip() or "unknown"
        window_id = (
            str(row.get("window_id", "")).strip()
            or str(row.get("example_id", "")).strip()
            or f"{video_slug}:{checkpoint}:{index:04d}"
        )
        title = str(row.get("title", "")).strip()
        topics = [str(topic).strip() for topic in row.get("topics", []) if str(topic).strip()]
        text = (
            str(row.get("nearby_transcript_text", "")).strip()
            or str(row.get("text", "")).strip()
        )
        cue_terms = [str(term).strip() for term in row.get("cue_terms", []) if str(term).strip()]
        candidate_labels = [
            str(label).strip()
            for label in row.get("candidate_labels", [])
            if str(label).strip()
        ]
        frame_path = resolve_first_available_asset_path(
            row.get("chart_crop_path"),
            row.get("frame_path"),
            row.get("screenshot_path"),
        )
        embedding_text = (
            str(row.get("embedding_text", "")).strip()
            or build_visual_embedding_text(
                title=title,
                checkpoint=checkpoint,
                topics=topics,
                text=text,
                cue_terms=cue_terms,
                candidate_labels=candidate_labels,
            )
        )

        documents.append(
            {
                "chunk_id": window_id,
                "video_slug": video_slug,
                "video_id": str(row.get("video_id", "")).strip(),
                "title": title,
                "topics": topics,
                "checkpoint": checkpoint,
                "start": float(row.get("start", 0.0)),
                "end": float(row.get("end", 0.0)),
                "text": text,
                "cue_terms": cue_terms,
                "candidate_labels": candidate_labels,
                "frame_path": path_for_manifest(frame_path) if frame_path else None,
                "asset_path": frame_path,
                "embedding_text": embedding_text,
                "source_type": str(row.get("source_type", "")).strip() or "video_visual_window",
            }
        )
    return documents


def embed_content_with_google(
    parts: Sequence[dict],
    *,
    api_key: str,
    model: str = DEFAULT_MULTIMODAL_MODEL,
    task_type: str,
    output_dimensionality: int = DEFAULT_OUTPUT_DIMENSIONALITY,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    fallback_text: str | None = None,
) -> tuple[list[float], bool]:
    endpoint = google_single_embed_endpoint(model)
    payload = {
        "content": {"parts": list(parts)},
        "taskType": task_type,
        "outputDimensionality": output_dimensionality,
    }

    used_text_fallback = False
    try:
        body = post_google_request(
            endpoint,
            payload,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
        )
    except RuntimeError:
        has_inline_data = any("inline_data" in part for part in parts)
        if not has_inline_data or not fallback_text:
            raise
        body = post_google_request(
            endpoint,
            {
                "content": {"parts": [{"text": fallback_text}]},
                "taskType": task_type,
                "outputDimensionality": output_dimensionality,
            },
            api_key=api_key,
            timeout_seconds=timeout_seconds,
        )
        used_text_fallback = True

    values = body.get("embedding", {}).get("values", [])
    if not values:
        raise RuntimeError("Google embeddings response did not include embedding values.")
    return normalize_vector(values), used_text_fallback


def embed_multimodal_documents_with_google(
    documents: Sequence[dict],
    *,
    api_key: str,
    model: str = DEFAULT_MULTIMODAL_MODEL,
    task_type: str,
    output_dimensionality: int = DEFAULT_OUTPUT_DIMENSIONALITY,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> tuple[list[list[float]], list[dict]]:
    vectors: list[list[float]] = []
    diagnostics: list[dict] = []

    for document in documents:
        asset_path = document.get("asset_path")
        parts = build_google_content_parts(
            text=str(document.get("embedding_text", "")).strip(),
            asset_path=asset_path,
        )
        vector, used_text_fallback = embed_content_with_google(
            parts,
            api_key=api_key,
            model=model,
            task_type=task_type,
            output_dimensionality=output_dimensionality,
            timeout_seconds=timeout_seconds,
            fallback_text=str(document.get("embedding_text", "")).strip(),
        )
        vectors.append(vector)
        diagnostics.append(
            {
                "chunk_id": document.get("chunk_id"),
                "used_asset": asset_path is not None,
                "used_text_fallback": used_text_fallback,
                "asset_path": path_for_manifest(asset_path) if asset_path else None,
            }
        )

    return vectors, diagnostics


def build_embedding_index(
    documents: Sequence[dict],
    vectors: Sequence[Sequence[float]],
    *,
    model: str = DEFAULT_MODEL,
    output_dimensionality: int = DEFAULT_OUTPUT_DIMENSIONALITY,
) -> dict:
    if len(documents) != len(vectors):
        raise ValueError("Document and vector counts must match.")

    items: list[dict] = []
    for document, vector in zip(documents, vectors):
        items.append(
            {
                "chunk_id": document["chunk_id"],
                "video_slug": document["video_slug"],
                "video_id": document["video_id"],
                "title": document["title"],
                "topics": document["topics"],
                "start": document["start"],
                "end": document["end"],
                "text": document["text"],
                "vector": [round(float(value), 8) for value in vector],
            }
        )
        if document.get("source_type"):
            items[-1]["source_type"] = document["source_type"]
        if document.get("checkpoint"):
            items[-1]["checkpoint"] = document["checkpoint"]
        if document.get("frame_path"):
            items[-1]["frame_path"] = document["frame_path"]
        if document.get("cue_terms"):
            items[-1]["cue_terms"] = document["cue_terms"]
        if document.get("candidate_labels"):
            items[-1]["candidate_labels"] = document["candidate_labels"]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "output_dimensionality": output_dimensionality,
        "normalization": "l2",
        "item_count": len(items),
        "items": items,
    }


def build_embedding_manifest(
    index: dict,
    *,
    index_path: Path = INDEX_PATH,
    source_path: Path | None = None,
    source_fingerprint: str | None = None,
) -> dict:
    manifest = {
        "generated_at": index.get("generated_at"),
        "model": index.get("model", DEFAULT_MODEL),
        "output_dimensionality": index.get(
            "output_dimensionality", DEFAULT_OUTPUT_DIMENSIONALITY
        ),
        "normalization": index.get("normalization", "l2"),
        "item_count": int(index.get("item_count", len(index.get("items", [])))),
        "index_path": path_for_manifest(index_path),
    }
    if source_path is not None:
        manifest["source_path"] = path_for_manifest(source_path)
        manifest["source_fingerprint"] = (
            source_fingerprint
            if source_fingerprint is not None
            else fingerprint_file(source_path)
        )
    return manifest


def save_embedding_index(
    index: dict,
    *,
    index_path: Path = INDEX_PATH,
    manifest_path: Path = MANIFEST_PATH,
    source_path: Path | None = None,
    source_fingerprint: str | None = None,
) -> dict:
    index_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")

    manifest = build_embedding_manifest(
        index,
        index_path=index_path,
        source_path=source_path,
        source_fingerprint=source_fingerprint,
    )
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def load_embedding_index(index_path: Path = INDEX_PATH) -> dict:
    return load_json(index_path)


def query_embedding_index(index: dict, *, query_vector: Sequence[float], top_k: int = 5) -> list[dict]:
    normalized_query = normalize_vector(query_vector)
    matches: list[dict] = []
    for item in index.get("items", []):
        item_vector = item.get("vector", [])
        score = dot_product(normalized_query, item_vector)
        matches.append(
            {
                "chunk_id": item.get("chunk_id"),
                "video_slug": item.get("video_slug"),
                "video_id": item.get("video_id"),
                "title": item.get("title"),
                "topics": item.get("topics", []),
                "start": item.get("start"),
                "end": item.get("end"),
                "text": item.get("text", ""),
                "score": round(float(score), 6),
            }
        )
        if item.get("source_type"):
            matches[-1]["source_type"] = item.get("source_type")
        if item.get("checkpoint"):
            matches[-1]["checkpoint"] = item.get("checkpoint")
        if item.get("frame_path"):
            matches[-1]["frame_path"] = item.get("frame_path")
        if item.get("candidate_labels"):
            matches[-1]["candidate_labels"] = item.get("candidate_labels")

    matches.sort(key=lambda item: item["score"], reverse=True)
    return matches[: max(0, int(top_k))]


def embed_query_text(
    query: str,
    *,
    api_key: str,
    model: str = DEFAULT_MODEL,
    output_dimensionality: int = DEFAULT_OUTPUT_DIMENSIONALITY,
) -> list[float]:
    [vector] = embed_texts_with_google(
        [query],
        api_key=api_key,
        model=model,
        task_type="RETRIEVAL_QUERY",
        output_dimensionality=output_dimensionality,
        batch_size=1,
    )
    return vector


def search_embedding_index(
    index: dict,
    *,
    query: str,
    api_key: str,
    top_k: int = 5,
) -> list[dict]:
    query_vector = embed_query_text(
        query,
        api_key=api_key,
        model=str(index.get("model", DEFAULT_MODEL)),
        output_dimensionality=int(
            index.get("output_dimensionality", DEFAULT_OUTPUT_DIMENSIONALITY)
        ),
    )
    return query_embedding_index(index, query_vector=query_vector, top_k=top_k)
