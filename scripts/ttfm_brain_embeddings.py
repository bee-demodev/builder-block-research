from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import ttfm_video_embeddings as tve


ROOT = Path(__file__).resolve().parent.parent
CORPUS_DIR = ROOT / "knowledge" / "ttfm_video_corpus"
DEFAULT_CHUNKS_PATH = tve.CHUNKS_PATH
DEFAULT_TEXT_INDEX_PATH = tve.INDEX_PATH
DEFAULT_TEXT_MANIFEST_PATH = tve.MANIFEST_PATH
DEFAULT_VISUAL_WINDOWS_PATH = CORPUS_DIR / "visual_windows.jsonl"
DEFAULT_VISUAL_INDEX_PATH = CORPUS_DIR / "visual_embedding_index.json"
DEFAULT_VISUAL_MANIFEST_PATH = CORPUS_DIR / "visual_embedding_manifest.json"
DEFAULT_AUDIO_SEMANTIC_CACHE_PATH = CORPUS_DIR / "audio_semantic_cache.json"
DEFAULT_TEXT_EMBEDDING_CACHE_PATH = CORPUS_DIR / "multimodal_text_embedding_cache.json"
DEFAULT_AUDIO_UNDERSTANDING_MODEL = "models/gemini-2.0-flash"

TextEmbedder = Callable[[list[str]], list[list[float]]]
VisualEmbedder = Callable[[Path | None, str], tuple[list[float], bool]]
AudioSummarizer = Callable[[dict[str, Any], Path], tuple[str, str]]


def path_for_manifest(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def load_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return dict(default or {})
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def count_jsonl_rows(path: Path) -> int:
    if not path.exists():
        return 0
    count = 0
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                count += 1
    return count


def load_embedding_lookup(index_path: Path) -> dict[str, dict[str, Any]]:
    if not index_path.exists():
        return {}
    index = tve.load_embedding_index(index_path)
    return {
        str(item.get("chunk_id", "")).strip(): item
        for item in index.get("items", [])
        if str(item.get("chunk_id", "")).strip()
    }


def manifest_matches_expected_count(
    manifest_path: Path,
    *,
    expected_count: int,
    source_path: Path | None = None,
) -> bool:
    manifest = load_json(manifest_path, {})
    if int(manifest.get("item_count", -1)) != int(expected_count):
        return False
    if source_path is None:
        return True
    expected_source_path = path_for_manifest(source_path)
    manifest_source_path = str(manifest.get("source_path", "")).strip()
    if manifest_source_path != expected_source_path:
        return False
    expected_fingerprint = tve.fingerprint_file(source_path) if source_path.exists() else None
    manifest_fingerprint = str(manifest.get("source_fingerprint", "")).strip() or None
    return manifest_fingerprint == expected_fingerprint


def describe_manifest(path: Path) -> dict[str, Any]:
    manifest = load_json(path, {})
    return {
        "exists": path.exists(),
        "manifest_path": path_for_manifest(path),
        "item_count": int(manifest.get("item_count", 0) or 0),
        "model": str(manifest.get("model", "")).strip() or None,
        "index_path": manifest.get("index_path"),
        "source_path": manifest.get("source_path"),
        "source_fingerprint": manifest.get("source_fingerprint"),
    }


def resolve_repo_path(path_value: object) -> Path | None:
    cleaned = str(path_value or "").strip()
    if not cleaned or cleaned.lower() in {"none", "null"}:
        return None
    candidate = Path(cleaned)
    if candidate.is_absolute():
        return candidate
    return ROOT / candidate


def resolve_visual_asset_path(row: dict[str, Any]) -> Path | None:
    for key in ("chart_crop_path", "frame_path", "screenshot_path"):
        resolved = resolve_repo_path(row.get(key))
        if resolved is not None:
            return resolved
    return None


def guess_mime_type(path: Path) -> str:
    mime_type, _encoding = mimetypes.guess_type(path.name)
    return mime_type or "application/octet-stream"


def google_generate_content_endpoint(model: str) -> str:
    return f"https://generativelanguage.googleapis.com/v1beta/{model}:generateContent"


def extract_generated_text(body: dict[str, Any]) -> str:
    candidates = body.get("candidates", [])
    for candidate in candidates:
        content = candidate.get("content", {})
        for part in content.get("parts", []):
            text = str(part.get("text", "")).strip()
            if text:
                return text
    return ""


def default_text_embedder(
    *,
    model: str,
    output_dimensionality: int,
    task_type: str = "RETRIEVAL_DOCUMENT",
) -> TextEmbedder:
    api_key = tve.resolve_google_api_key()

    def embed(texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return tve.embed_texts_with_google(
            texts,
            api_key=api_key,
            model=model,
            task_type=task_type,
            output_dimensionality=output_dimensionality,
        )

    return embed


def default_visual_embedder(
    *,
    model: str,
    output_dimensionality: int,
    task_type: str = "RETRIEVAL_DOCUMENT",
) -> VisualEmbedder:
    api_key = tve.resolve_google_api_key()

    def embed(asset_path: Path | None, text: str) -> tuple[list[float], bool]:
        parts = tve.build_google_content_parts(text=text, asset_path=asset_path)
        return tve.embed_content_with_google(
            parts,
            api_key=api_key,
            model=model,
            task_type=task_type,
            output_dimensionality=output_dimensionality,
            fallback_text=text,
        )

    return embed


def default_audio_summarizer(
    *,
    model: str,
    timeout_seconds: int = tve.DEFAULT_TIMEOUT_SECONDS,
) -> AudioSummarizer:
    api_key = tve.resolve_google_api_key()

    def summarize(row: dict[str, Any], audio_path: Path) -> tuple[str, str]:
        transcript_text = str(row.get("transcript_text", "")).strip()
        prompt = (
            "Summarize the trading explanation in this audio clip for a TTrades Fractal Model "
            "training example. Focus on setup confirmation, invalidation, point of interest, "
            "timeframe alignment, and named TTFM concepts. Return plain text only."
        )
        inline_data = {
            "mime_type": guess_mime_type(audio_path),
            "data": base64.b64encode(audio_path.read_bytes()).decode("ascii"),
        }
        payload = {
            "contents": [
                {
                    "parts": [
                        {"inline_data": inline_data},
                        {"text": prompt},
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.0,
            },
        }
        try:
            body = tve.post_google_request(
                google_generate_content_endpoint(model),
                payload,
                api_key=api_key,
                timeout_seconds=timeout_seconds,
            )
            summary_text = extract_generated_text(body)
            if summary_text:
                return summary_text, "gemini_audio_summary"
        except RuntimeError:
            pass

        if transcript_text:
            return transcript_text, "transcript_fallback"
        return "", "audio_unavailable"

    return summarize


def zero_vector(*, output_dimensionality: int) -> list[float]:
    return [0.0] * output_dimensionality


def normalize_string_list(values: object) -> list[str]:
    if values is None:
        return []
    if isinstance(values, list):
        return [str(value).strip() for value in values if str(value).strip()]
    if isinstance(values, str):
        cleaned = values.strip()
        return [cleaned] if cleaned else []
    return []


def strip_label_hint_lines(text: str) -> str:
    cleaned_lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lowered = line.lower()
        if lowered.startswith("candidate labels:") or lowered.startswith("labels:"):
            continue
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines).strip()


def build_transcript_source_text(row: dict[str, Any]) -> str:
    embedding_text = str(row.get("embedding_text", "")).strip()
    if embedding_text:
        sanitized_embedding_text = strip_label_hint_lines(embedding_text)
        if sanitized_embedding_text:
            return sanitized_embedding_text

    transcript_text = str(row.get("transcript_text", "")).strip()
    checkpoint = str(row.get("checkpoint", "")).strip() or "unknown"
    title = str(row.get("title", "")).strip()
    evidence_refs = normalize_string_list(row.get("evidence_refs"))
    lines = [f"Checkpoint: {checkpoint}"]
    if title:
        lines.insert(0, f"Title: {title}")
    if evidence_refs:
        lines.append(f"Evidence refs: {', '.join(evidence_refs)}")
    if transcript_text:
        lines.append(f"Transcript: {transcript_text}")
    return "\n".join(lines).strip()


def audio_cache_key(audio_path: Path) -> str:
    stat = audio_path.stat()
    signature = f"{audio_path.resolve()}::{stat.st_mtime_ns}::{stat.st_size}"
    return hashlib.sha1(signature.encode("utf-8")).hexdigest()


def load_audio_semantic_cache(cache_path: Path) -> dict[str, Any]:
    payload = load_json(cache_path, {"entries": {}})
    entries = payload.get("entries")
    if not isinstance(entries, dict):
        payload["entries"] = {}
    return payload


def save_audio_semantic_cache(cache_path: Path, cache: dict[str, Any]) -> None:
    cache["updated_at"] = datetime.now(timezone.utc).isoformat()
    write_json(cache_path, cache)


def text_embedding_cache_key(
    text: str,
    *,
    namespace: str,
    model: str,
    output_dimensionality: int,
) -> str:
    signature = f"{namespace}::{model}::{output_dimensionality}::{text}"
    return hashlib.sha1(signature.encode("utf-8")).hexdigest()


def load_text_embedding_cache(cache_path: Path) -> dict[str, Any]:
    payload = load_json(cache_path, {"entries": {}})
    entries = payload.get("entries")
    if not isinstance(entries, dict):
        payload["entries"] = {}
    return payload


def save_text_embedding_cache(cache_path: Path, cache: dict[str, Any]) -> None:
    cache["updated_at"] = datetime.now(timezone.utc).isoformat()
    write_json(cache_path, cache)


def embed_texts_with_cache(
    texts: list[str],
    *,
    namespace: str,
    cache_path: Path,
    model: str,
    output_dimensionality: int,
    text_embedder: TextEmbedder,
) -> tuple[list[list[float]], int, int]:
    if not texts:
        return [], 0, 0

    cache = load_text_embedding_cache(cache_path)
    entries = cache.setdefault("entries", {})
    cache_hits = 0
    miss_positions: list[int] = []
    miss_texts: list[str] = []
    vectors: list[list[float] | None] = [None] * len(texts)

    for index, text in enumerate(texts):
        key = text_embedding_cache_key(
            text,
            namespace=namespace,
            model=model,
            output_dimensionality=output_dimensionality,
        )
        cached_entry = entries.get(key)
        if isinstance(cached_entry, dict) and isinstance(cached_entry.get("vector"), list):
            vectors[index] = [float(value) for value in cached_entry.get("vector", [])]
            cache_hits += 1
            continue
        miss_positions.append(index)
        miss_texts.append(text)

    if miss_texts:
        embedded_vectors = text_embedder(miss_texts)
        for position, text, vector in zip(miss_positions, miss_texts, embedded_vectors):
            normalized_vector = [float(value) for value in vector]
            vectors[position] = normalized_vector
            key = text_embedding_cache_key(
                text,
                namespace=namespace,
                model=model,
                output_dimensionality=output_dimensionality,
            )
            entries[key] = {
                "namespace": namespace,
                "model": model,
                "output_dimensionality": output_dimensionality,
                "text": text,
                "vector": normalized_vector,
            }
        save_text_embedding_cache(cache_path, cache)

    return [
        vector if vector is not None else zero_vector(output_dimensionality=output_dimensionality)
        for vector in vectors
    ], cache_hits, len(miss_texts)


def get_audio_semantic_text(
    row: dict[str, Any],
    *,
    audio_path: Path | None,
    cache_path: Path,
    summarizer: AudioSummarizer,
) -> tuple[str, str]:
    if audio_path is None or not audio_path.exists():
        return "", "missing_audio"

    cache = load_audio_semantic_cache(cache_path)
    key = audio_cache_key(audio_path)
    cached_entry = cache.get("entries", {}).get(key)
    if isinstance(cached_entry, dict):
        return (
            str(cached_entry.get("semantic_text", "")).strip(),
            str(cached_entry.get("semantic_mode", "cache")).strip() or "cache",
        )

    semantic_text, semantic_mode = summarizer(row, audio_path)
    cache.setdefault("entries", {})[key] = {
        "audio_path": path_for_manifest(audio_path),
        "semantic_text": semantic_text,
        "semantic_mode": semantic_mode,
    }
    save_audio_semantic_cache(cache_path, cache)
    return semantic_text, semantic_mode


def target_vector_from_labels(
    labels: list[str],
    *,
    label_to_index: dict[str, int],
) -> list[float]:
    vector = [0.0] * len(label_to_index)
    for label_name in labels:
        index = label_to_index.get(label_name)
        if index is not None:
            vector[index] = 1.0
    return vector


def build_examples_from_google_embeddings(
    rows: list[dict[str, Any]],
    *,
    label_to_index: dict[str, int],
    output_dimensionality: int = tve.DEFAULT_OUTPUT_DIMENSIONALITY,
    text_embedding_model: str = tve.DEFAULT_MODEL,
    visual_embedding_model: str = tve.DEFAULT_MULTIMODAL_MODEL,
    audio_understanding_model: str = DEFAULT_AUDIO_UNDERSTANDING_MODEL,
    audio_semantic_cache_path: Path = DEFAULT_AUDIO_SEMANTIC_CACHE_PATH,
    text_embedding_cache_path: Path = DEFAULT_TEXT_EMBEDDING_CACHE_PATH,
    visual_index_lookup: dict[str, dict[str, Any]] | None = None,
    text_embedder: TextEmbedder | None = None,
    visual_embedder: VisualEmbedder | None = None,
    audio_summarizer: AudioSummarizer | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    text_embedder = text_embedder or default_text_embedder(
        model=text_embedding_model,
        output_dimensionality=output_dimensionality,
    )
    visual_embedder = visual_embedder or default_visual_embedder(
        model=visual_embedding_model,
        output_dimensionality=output_dimensionality,
    )
    audio_summarizer = audio_summarizer or default_audio_summarizer(
        model=audio_understanding_model,
    )
    visual_index_lookup = visual_index_lookup or {}

    examples: list[dict[str, Any]] = []
    skipped_examples: list[dict[str, Any]] = []
    transcript_texts: list[str] = []
    audio_semantic_texts: list[str] = []
    transcript_positions: list[int] = []
    audio_positions: list[int] = []
    audio_semantic_mode_counts: dict[str, int] = {}
    visual_index_hits = 0
    visual_on_demand_count = 0
    visual_text_fallback_count = 0

    for row in rows:
        example_id = str(row.get("example_id", "")).strip() or "unknown"
        active_labels = normalize_string_list(row.get("active_labels"))
        screenshot_path = resolve_visual_asset_path(row)
        audio_path = resolve_repo_path(row.get("audio_path"))
        if screenshot_path is None or not screenshot_path.exists():
            skipped_examples.append(
                {
                    "example_id": example_id,
                    "reason": "missing_image",
                    "screenshot_path": path_for_manifest(screenshot_path) if screenshot_path else None,
                }
            )
            continue
        if audio_path is not None and not audio_path.exists():
            skipped_examples.append(
                {
                    "example_id": example_id,
                    "reason": "missing_audio_asset",
                    "audio_path": path_for_manifest(audio_path),
                }
            )
            continue

        transcript_source_text = build_transcript_source_text(row)
        audio_semantic_text, audio_semantic_mode = get_audio_semantic_text(
            row,
            audio_path=audio_path,
            cache_path=audio_semantic_cache_path,
            summarizer=audio_summarizer,
        )
        audio_semantic_mode_counts[audio_semantic_mode] = (
            audio_semantic_mode_counts.get(audio_semantic_mode, 0) + 1
        )

        visual_lookup_item = visual_index_lookup.get(example_id)
        if visual_lookup_item and isinstance(visual_lookup_item.get("vector"), list):
            visual_embedding = [
                float(value) for value in visual_lookup_item.get("vector", [])
            ]
            visual_embedding_source = "visual_index"
            visual_used_text_fallback = False
            visual_index_hits += 1
        else:
            visual_embedding, visual_used_text_fallback = visual_embedder(
                screenshot_path,
                transcript_source_text,
            )
            visual_embedding_source = "direct_gemini_embed"
            visual_on_demand_count += 1
            if visual_used_text_fallback:
                visual_text_fallback_count += 1

        example = {
            "example_id": example_id,
            "case_ref": str(row.get("case_ref", "")).strip(),
            "checkpoint": str(row.get("checkpoint", "")).strip() or "unknown",
            "active_labels": active_labels,
            "target": target_vector_from_labels(active_labels, label_to_index=label_to_index),
            "sample_weight": float(row.get("sample_weight", row.get("weak_label_confidence", 1.0)) or 1.0),
            "weak_label_confidence": float(row.get("weak_label_confidence", 0.35) or 0.35),
            "screenshot_path": path_for_manifest(screenshot_path),
            "audio_path": path_for_manifest(audio_path) if audio_path else None,
            "transcript_text": str(row.get("transcript_text", "")).strip(),
            "transcript_source_text": transcript_source_text,
            "audio_semantic_text": audio_semantic_text,
            "audio_semantic_mode": audio_semantic_mode,
            "has_visual": True,
            "has_transcript": bool(transcript_source_text),
            "has_audio": bool(audio_path),
            "has_audio_semantic": bool(audio_semantic_text),
            "visual_embedding": visual_embedding
            if len(visual_embedding) == output_dimensionality
            else zero_vector(output_dimensionality=output_dimensionality),
            "visual_embedding_source": visual_embedding_source,
            "visual_used_text_fallback": visual_used_text_fallback,
            "transcript_embedding": zero_vector(output_dimensionality=output_dimensionality),
            "audio_semantic_embedding": zero_vector(output_dimensionality=output_dimensionality),
            "framework_slug": str(row.get("framework_slug", "ttfm")).strip() or "ttfm",
            "profile_slug": str(row.get("profile_slug", "ttrades_curriculum")).strip()
            or "ttrades_curriculum",
            "brain_type": str(row.get("brain_type", "setup_scorer")).strip() or "setup_scorer",
            "embedding_backend": "google_gemini",
            "visual_embedding_model": visual_embedding_model,
            "text_embedding_model": text_embedding_model,
            "audio_semantic_mode_config": audio_understanding_model,
        }
        examples.append(example)
        transcript_positions.append(len(examples) - 1)
        transcript_texts.append(transcript_source_text)
        if audio_semantic_text:
            audio_positions.append(len(examples) - 1)
            audio_semantic_texts.append(audio_semantic_text)

    transcript_vectors, transcript_cache_hits, transcript_cache_misses = embed_texts_with_cache(
        transcript_texts,
        namespace="transcript",
        cache_path=text_embedding_cache_path,
        model=text_embedding_model,
        output_dimensionality=output_dimensionality,
        text_embedder=text_embedder,
    )
    audio_vectors, audio_cache_hits, audio_cache_misses = embed_texts_with_cache(
        audio_semantic_texts,
        namespace="audio_semantic",
        cache_path=text_embedding_cache_path,
        model=text_embedding_model,
        output_dimensionality=output_dimensionality,
        text_embedder=text_embedder,
    )

    for position, vector in zip(transcript_positions, transcript_vectors):
        examples[position]["transcript_embedding"] = [float(value) for value in vector]
    for position, vector in zip(audio_positions, audio_vectors):
        examples[position]["audio_semantic_embedding"] = [float(value) for value in vector]

    prep_report = {
        "example_count": len(examples),
        "skipped_example_count": len(skipped_examples),
        "visual_index_hit_count": visual_index_hits,
        "visual_on_demand_count": visual_on_demand_count,
        "visual_text_fallback_count": visual_text_fallback_count,
        "transcript_embedding_count": len(transcript_vectors),
        "audio_semantic_embedding_count": len(audio_vectors),
        "audio_semantic_mode_counts": dict(sorted(audio_semantic_mode_counts.items())),
        "output_dimensionality": output_dimensionality,
        "embedding_backend": "google_gemini",
        "visual_embedding_model": visual_embedding_model,
        "text_embedding_model": text_embedding_model,
        "audio_understanding_model": audio_understanding_model,
        "audio_semantic_cache_path": path_for_manifest(audio_semantic_cache_path),
        "text_embedding_cache_path": path_for_manifest(text_embedding_cache_path),
        "transcript_cache_hit_count": transcript_cache_hits,
        "transcript_cache_miss_count": transcript_cache_misses,
        "audio_semantic_cache_hit_count": audio_cache_hits,
        "audio_semantic_cache_miss_count": audio_cache_misses,
    }
    return examples, skipped_examples, prep_report
