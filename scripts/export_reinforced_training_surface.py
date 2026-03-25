from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from export_model_training_surface import (
    build_training_text,
    extract_key_paths,
    flatten_strings,
    normalize_outcome_decision,
    normalize_token,
    summarize_training_surface,
)
from export_tradingview_pine_readiness_report import validation_passed_qa_gate
import ttfm_video_embeddings as tve


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASE_DATASET_PATH = ROOT / "results" / "model_training_surface.jsonl"
DEFAULT_CASE_PACKET_REPORT_PATH = ROOT / "results" / "ttfm_case_packets.json"
DEFAULT_ITERATION_GRADING_REPORT_PATH = ROOT / "results" / "trading_iteration_grading_report.json"
DEFAULT_TRADINGVIEW_VALIDATION_LOG_PATH = ROOT / "data" / "tradingview_pine_validation.json"
DEFAULT_TTFM_VIDEO_CHUNKS_PATH = ROOT / "knowledge" / "ttfm_video_corpus" / "chunks.jsonl"
DEFAULT_TTFM_VIDEO_EMBEDDING_INDEX_PATH = ROOT / "knowledge" / "ttfm_video_corpus" / "google_embedding_index.json"
DEFAULT_DATASET_OUTPUT = ROOT / "results" / "reinforced_model_training_surface.jsonl"
DEFAULT_REPORT_OUTPUT = ROOT / "results" / "reinforced_model_training_report.json"

DEFAULT_TRADE_MODEL_TOPIC = {
    "continuation_entry_model": "continuation",
    "daily_bias_c123_map": "bias",
    "daily_bias_framework": "bias",
    "daily_profile_models": "daily_profiles",
    "fractal_closure_model": "candle_2_closure",
    "reversal_sequence_model": "reversal",
}

DEFAULT_TRADE_MODEL_RELATION_TYPE = {
    "continuation_entry_model": "execution_model",
    "daily_bias_c123_map": "execution_model",
    "daily_bias_framework": "bias_framework",
    "daily_profile_models": "session_profile",
    "fractal_closure_model": "confirmation_framework",
    "reversal_sequence_model": "execution_model",
}

DEFAULT_YOUTUBE_VIDEO_TRAINING_MAP: dict[str, dict[str, Any]] = {
    "fractal_model_fundamentals": {
        "trade_model": "daily_bias_c123_map",
        "relation_type": "execution_model",
        "topic": "bias",
        "confidence": 0.8,
        "mapping_rationale": (
            "Maps the daily, hourly, and 5-minute fractal workflow that powers the "
            "Daily Bias C1/C2/C3 execution model."
        ),
    },
    "equilibrium_for_expansions": {
        "trade_model": "continuation_entry_model",
        "relation_type": "execution_model",
        "topic": "continuation",
        "confidence": 0.8,
        "mapping_rationale": (
            "Focuses on continuation entries that use equilibrium as the pullback "
            "reference for expansions."
        ),
    },
    "easy_daily_bias_mechanical_framework": {
        "trade_model": "daily_bias_framework",
        "relation_type": "bias_framework",
        "topic": "bias",
        "confidence": 0.85,
        "mapping_rationale": (
            "Direct daily-bias curriculum source covering continuation versus reversal "
            "classification."
        ),
    },
    "candle_2_closure_foundation": {
        "trade_model": "fractal_closure_model",
        "relation_type": "confirmation_framework",
        "topic": "candle_2_closure",
        "confidence": 0.85,
        "mapping_rationale": (
            "Direct Candle 2 closure source for the fractal closure confirmation path."
        ),
    },
    "trading_candle_3": {
        "trade_model": "fractal_closure_model",
        "relation_type": "confirmation_framework",
        "topic": "candle_3_closure",
        "confidence": 0.8,
        "mapping_rationale": (
            "Direct Candle 3 continuation source for the fractal closure confirmation path."
        ),
    },
    "cisd_validates_swing_points": {
        "trade_model": "daily_bias_c123_map",
        "relation_type": "execution_model",
        "topic": "bias",
        "confidence": 0.75,
        "mapping_rationale": (
            "Explains how lower-time-frame CISD validates higher-time-frame Candle 2/Candle 3 "
            "swing points, which is a core prerequisite for the daily bias C1/C2/C3 execution map."
        ),
    },
}


def load_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl_examples(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    examples: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            cleaned = line.strip()
            if cleaned:
                examples.append(json.loads(cleaned))
    return examples


def normalize_string(value: object) -> str:
    return str(value or "").strip()


def normalize_labels(values: object) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        cleaned = values.strip()
        return [cleaned] if cleaned else []
    if isinstance(values, list):
        output: list[str] = []
        for value in values:
            cleaned = str(value).strip()
            if cleaned and cleaned not in output:
                output.append(cleaned)
        return output
    return []


def normalize_slug(value: object) -> str:
    return normalize_string(value).lower().replace(" ", "_")


def build_source_group_from_url(value: object) -> str:
    url = normalize_string(value)
    if not url:
        return ""

    parsed = urlparse(url)
    host = normalize_slug(parsed.netloc)
    path = normalize_string(parsed.path).rstrip("/").lower()
    if host and path:
        return f"url::{host}{path}"
    if host:
        return f"url::{host}"
    return ""


def infer_source_group(example: dict[str, Any]) -> str:
    explicit_source_group = normalize_string(example.get("source_group"))
    if explicit_source_group:
        return explicit_source_group

    split_group = normalize_string(example.get("split_group"))
    if split_group.startswith("youtube_video::"):
        parts = split_group.split("::")
        if len(parts) >= 2:
            return "::".join(parts[:2])

    if normalize_slug(example.get("profile_type")) == "youtube_transcript":
        chunk_id = normalize_string(example.get("features", {}).get("chunk_id"))
        if ":" in chunk_id:
            return f"youtube_video::{chunk_id.split(':', 1)[0]}"

    if normalize_slug(example.get("profile_type")) == "tradingview_validation":
        trade_model = normalize_slug(example.get("trade_model"))
        if trade_model:
            return f"tradingview_validation::{trade_model}"

    if normalize_slug(example.get("profile_type")) == "graded_iteration":
        case_ref = normalize_string(example.get("case_ref"))
        if case_ref:
            return f"graded_iteration::{case_ref}"

    source_group_from_url = build_source_group_from_url(example.get("source_url"))
    if source_group_from_url:
        return source_group_from_url

    case_ref = normalize_string(example.get("case_ref"))
    if case_ref.startswith("youtube::"):
        youtube_case_ref = case_ref.split("::", 1)[1]
        if ":" in youtube_case_ref:
            return f"youtube_video::{youtube_case_ref.split(':', 1)[0]}"
    if case_ref:
        return f"case::{case_ref}"

    return normalize_string(example.get("example_id"))


def annotate_source_groups(examples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    annotated_examples: list[dict[str, Any]] = []
    for example in examples:
        source_group = infer_source_group(example)
        if source_group:
            annotated_examples.append({**example, "source_group": source_group})
        else:
            annotated_examples.append(dict(example))
    return annotated_examples


def build_case_packet_lookup(case_packet_report: dict) -> dict[str, dict]:
    return {
        normalize_string(packet.get("case_ref")): packet
        for packet in case_packet_report.get("case_packets", [])
        if normalize_string(packet.get("case_ref"))
    }


def build_trade_model_priors(examples: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    priors: dict[str, dict[str, Counter[str]]] = {}
    for example in examples:
        trade_model = normalize_slug(example.get("trade_model"))
        if not trade_model:
            continue
        topic = normalize_string(example.get("topic"))
        relation_type = normalize_string(example.get("relation_type"))
        counters = priors.setdefault(
            trade_model,
            {"topic": Counter(), "relation_type": Counter()},
        )
        if topic:
            counters["topic"][topic] += 1
        if relation_type:
            counters["relation_type"][relation_type] += 1

    resolved: dict[str, dict[str, str]] = {}
    for trade_model, counters in priors.items():
        resolved[trade_model] = {
            "topic": counters["topic"].most_common(1)[0][0] if counters["topic"] else "",
            "relation_type": counters["relation_type"].most_common(1)[0][0]
            if counters["relation_type"]
            else "",
        }
    return resolved


def load_optional_embedding_index(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"items": []}
    return tve.load_embedding_index(path)


def build_embedding_item_lookup(index: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        normalize_string(item.get("chunk_id")): item
        for item in index.get("items", [])
        if isinstance(item, dict) and normalize_string(item.get("chunk_id"))
    }


def build_semantic_neighbors(
    *,
    chunk_id: str,
    embedding_lookup: dict[str, dict[str, Any]],
    top_k: int = 2,
) -> list[dict[str, Any]]:
    current = embedding_lookup.get(chunk_id)
    if current is None:
        return []

    current_vector = current.get("vector", [])
    neighbors: list[dict[str, Any]] = []
    for candidate_chunk_id, item in embedding_lookup.items():
        if candidate_chunk_id == chunk_id:
            continue
        score = tve.dot_product(current_vector, item.get("vector", []))
        neighbors.append(
            {
                "chunk_id": candidate_chunk_id,
                "video_slug": normalize_string(item.get("video_slug")),
                "video_id": normalize_string(item.get("video_id")),
                "title": normalize_string(item.get("title")),
                "score": round(float(score), 6),
            }
        )

    neighbors.sort(key=lambda item: item["score"], reverse=True)
    return neighbors[: max(0, int(top_k))]


TRANSCRIPT_POSITIVE_OUTCOME_CUES: dict[str, tuple[str, ...]] = {
    "cisd_validates_swing_points": (
        "it is a valid continuation",
        "valid to be looking for a continuation",
        "this meets both of the requirements",
        "this meets both the requirements",
        "we have a valid candle to closure",
        "we have the sweep, we have the change in the state of delivery",
        "we have the sweep we have the change in the state of delivery",
    ),
}

TRANSCRIPT_NEGATIVE_OUTCOME_CUES: dict[str, tuple[str, ...]] = {
    "cisd_validates_swing_points": (
        "not a valid fractal model",
        "would not be looking for a continuation",
        "not a valid candle 3 closure",
        "we don't have a candle to closure",
        "means nothing to me",
        "saved myself from taking losses",
        "not a valid bearish setup",
        "we haven't yet",
        "fails to go and close below",
        "indicator will not print",
        "just in a consolidation",
        "not a good closure over",
    ),
    "fractal_model_fundamentals": (
        "we get stopped out",
        "invalidate my bias and not continue to look short",
        "our point of interest wasn't really there",
        "it wasn't being respected",
    ),
    "easy_daily_bias_mechanical_framework": (
        "not ideal to have closures on the hourly chart below that",
        "i don't want to see a closure below that eq level",
    ),
    "equilibrium_for_expansions": (
        "without that confirmation there is no bullish setup there",
        "there is no bullish setup there",
    ),
    "trading_candle_3": (
        "setup fails before forming that continuation",
        "if i was just to trade the reversal, i would get stopped out there",
        "we don't want to see that closure there",
    ),
}

TRANSCRIPT_SEGMENT_BOUNDARY_PATTERNS: dict[str, tuple[str, ...]] = {
    "cisd_validates_swing_points": (
        r"now let's take a look at an example of an invalid case\.?",
        r"now,\s*let's take a look at another invalid case\.?",
        r"now,\s*let's take a look at a candle 3 closure scenario\.?",
        r"now let's take a look at an invalid scenario\.?",
        r"now let's take a look at another scenario\.?",
        r"let's take a look at another example that looks like this\.?",
        r"let's go through one final example",
        r"so now that you understand why i look for a change in the state of delivery",
    ),
}

TRANSCRIPT_REQUIRED_MODEL_CUES: dict[str, tuple[str, ...]] = {
    "fractal_model_fundamentals": (
        "if i do not have a daily bias i do not drop down to the hourly time frame",
        "once i have both the closure and the change in the state of delivery",
        "with all of that criteria met then i'll go down to my entry time frame",
        "it is valid to look for shorts in this following candle",
        "with that, i can be looking long in the following candle",
    ),
    "equilibrium_for_expansions": (
        "looking for the upper half to respect for price to trade higher",
        "the lower half to respect for price to trade lower",
        "if the eq is respected then we can trade lower",
        "we get a reaction a change in the state of delivery and then we continue to expand",
        "each day we respected the previous day's eq to trade higher",
    ),
    "easy_daily_bias_mechanical_framework": (
        "if i'm going to be looking for a continuation i'll look for price to open",
        "when looking for a continuation, i want to see price open",
        "this is a good example of a continuation",
        "price open, make a low or this lower wick, and then trade higher",
        "we want to see price open, trade lower first, respect the eq",
    ),
    "trading_candle_3": (
        "then i can look for a continuation in candle 3",
        "this is where i could then look to take an entry on the open",
        "focus on those candle twos that have a nice reversal candle",
        "we can be looking for continuations lower in this next candle",
        "i could then look to take a long setup on the open of this new candle",
    ),
}


def infer_youtube_transcript_outcome(
    *,
    video_slug: str,
    transcript_text: str,
) -> tuple[str, str | None]:
    normalized_text = normalize_string(transcript_text).lower()
    if not normalized_text:
        return "unknown", None

    positive_cues = TRANSCRIPT_POSITIVE_OUTCOME_CUES.get(video_slug, ())
    negative_cues = TRANSCRIPT_NEGATIVE_OUTCOME_CUES.get(video_slug, ())
    has_positive_cue = any(cue in normalized_text for cue in positive_cues)
    has_negative_cue = any(cue in normalized_text for cue in negative_cues)

    if has_positive_cue and has_negative_cue:
        return "unknown", None
    if has_positive_cue:
        return "trade", "explicit_transcript_valid_setup"
    if has_negative_cue:
        return "no_trade", "explicit_transcript_invalid_setup"
    return "unknown", None


def should_include_youtube_transcript_chunk(
    *,
    video_slug: str,
    transcript_text: str,
) -> bool:
    normalized_text = normalize_string(transcript_text).lower()
    if not normalized_text:
        return False

    required_model_cues = TRANSCRIPT_REQUIRED_MODEL_CUES.get(video_slug, ())
    if not required_model_cues:
        return True

    positive_cues = TRANSCRIPT_POSITIVE_OUTCOME_CUES.get(video_slug, ())
    negative_cues = TRANSCRIPT_NEGATIVE_OUTCOME_CUES.get(video_slug, ())
    return any(
        cue in normalized_text
        for cue in (*required_model_cues, *positive_cues, *negative_cues)
    )


def split_youtube_transcript_document(document: dict[str, Any]) -> list[dict[str, Any]]:
    transcript_text = normalize_string(document.get("text"))
    if not transcript_text:
        return []

    video_slug = normalize_string(document.get("video_slug"))
    boundary_patterns = TRANSCRIPT_SEGMENT_BOUNDARY_PATTERNS.get(video_slug, ())
    if not boundary_patterns:
        return [dict(document)]

    boundary_regex = re.compile(
        "|".join(f"(?:{pattern})" for pattern in boundary_patterns),
        flags=re.IGNORECASE,
    )
    boundary_offsets = [0]
    for match in boundary_regex.finditer(transcript_text):
        if match.start() > 0:
            boundary_offsets.append(match.start())
    boundary_offsets = sorted(set(boundary_offsets))

    if len(boundary_offsets) <= 1:
        return [dict(document)]

    base_chunk_id = normalize_string(document.get("chunk_id"))
    segments: list[dict[str, Any]] = []
    for index, start_offset in enumerate(boundary_offsets):
        end_offset = (
            boundary_offsets[index + 1]
            if index + 1 < len(boundary_offsets)
            else len(transcript_text)
        )
        segment_text = transcript_text[start_offset:end_offset].strip()
        if not segment_text:
            continue

        segment_document = dict(document)
        segment_document["chunk_id"] = f"{base_chunk_id}#segment_{index:02d}"
        segment_document["parent_chunk_id"] = base_chunk_id
        segment_document["text"] = segment_text
        segments.append(segment_document)
    return segments


def build_youtube_transcript_example(
    *,
    document: dict[str, Any],
    mapping: dict[str, Any],
    video_slug: str,
    trade_model: str,
    relation_type: str,
    topic: str,
    embedding_lookup: dict[str, Any],
    outcome_segment_only: bool = False,
    override_outcome_decision: str | None = None,
    override_outcome_reason: str | None = None,
) -> dict[str, Any]:
    transcript_text = normalize_string(document.get("text"))
    outcome_decision, outcome_reason = infer_youtube_transcript_outcome(
        video_slug=video_slug,
        transcript_text=transcript_text,
    )
    if override_outcome_decision is not None:
        outcome_decision = override_outcome_decision
        outcome_reason = override_outcome_reason

    chunk_id = normalize_string(document.get("chunk_id"))
    parent_chunk_id = normalize_string(document.get("parent_chunk_id"))
    semantic_lookup_chunk_id = parent_chunk_id or chunk_id
    chunk_bucket_suffix = 0
    if ":" in semantic_lookup_chunk_id:
        _, _, chunk_tail = semantic_lookup_chunk_id.rpartition(":")
        if chunk_tail.isdigit():
            chunk_bucket_suffix = int(chunk_tail) // 4
    neighbors = build_semantic_neighbors(
        chunk_id=semantic_lookup_chunk_id,
        embedding_lookup=embedding_lookup,
        top_k=2,
    )
    neighbor_chunk_ids = [item["chunk_id"] for item in neighbors]
    neighbor_titles = sorted(
        {
            normalize_token(item["title"])
            for item in neighbors
            if normalize_string(item.get("title"))
        }
    )
    annotation_payload = {
        "video_title": normalize_string(document.get("title")),
        "video_topics": document.get("topics", []),
        "transcript_excerpt": transcript_text,
        "video_id": normalize_string(document.get("video_id")),
        "chunk_start": float(document.get("start", 0.0)),
        "chunk_end": float(document.get("end", 0.0)),
        "mapping_rationale": normalize_string(mapping.get("mapping_rationale")),
        "semantic_neighbor_chunk_ids": neighbor_chunk_ids,
        "semantic_neighbor_titles": neighbor_titles,
    }
    annotation_key_paths = sorted(set(extract_key_paths(annotation_payload)))
    annotation_value_tokens = sorted(
        {
            normalize_token(value)
            for value in flatten_strings(annotation_payload)
            if normalize_token(value)
        }
    )
    chart_context_tokens = sorted(
        token
        for token in {
            "youtube_transcript",
            normalize_token(document.get("title", "")),
            *(normalize_token(topic_name) for topic_name in document.get("topics", [])),
            *neighbor_titles,
        }
        if token
    )

    training_text = build_training_text(
        [
            "profile ttrades_curriculum",
            f"topic {topic}",
            f"trade model {trade_model}",
            f"relation {relation_type}",
            "setup youtube transcript curriculum chunk",
            f"context {' '.join(chart_context_tokens)}",
            f"annotation {' '.join(annotation_value_tokens)}",
            "outcome unknown",
        ]
    )

    return {
        "example_id": f"youtube::{chunk_id}::{trade_model}::{relation_type}",
        "split_group": f"youtube_video::{video_slug}::bucket_{chunk_bucket_suffix:02d}",
        "source_group": f"youtube_video::{video_slug}",
        "profile_slug": "ttrades_curriculum",
        "profile_name": "TTrades Curriculum",
        "profile_type": "youtube_transcript",
        "topic": topic,
        "case_ref": f"youtube::{chunk_id}",
        "source_url": f"https://youtu.be/{normalize_string(document.get('video_id'))}",
        "notes": normalize_string(mapping.get("mapping_rationale"))
        or "Transcript-derived training example from the TTrades YouTube corpus.",
        "trade_model": trade_model,
        "relation_type": relation_type,
        "confidence": float(mapping.get("confidence", 0.75) or 0.75),
        "indicator_ready_in_profile": True,
        "features": {
            "topic": topic,
            "setup_variant": "youtube_transcript_curriculum_chunk",
            "source_kind": "youtube_transcript",
            "timeframe_scope": [],
            "session_scope": [],
            "profile_frameworks": ["ttfm"],
            "profile_topics": [topic] if topic else [],
            "profile_trade_model_roles": [f"{trade_model}:{relation_type}"],
            "annotation_key_paths": annotation_key_paths,
            "annotation_value_tokens": annotation_value_tokens,
            "chart_context_tokens": chart_context_tokens,
            "chunk_id": chunk_id,
            "parent_chunk_id": parent_chunk_id or None,
            "semantic_neighbor_chunk_ids": neighbor_chunk_ids,
            "semantic_neighbor_scores": [item["score"] for item in neighbors],
            "embedding_index_present": semantic_lookup_chunk_id in embedding_lookup,
        },
        "targets": {
            "trade_model": trade_model,
            "relation_type": relation_type,
            "outcome_decision": outcome_decision,
            "is_no_trade": outcome_decision == "no_trade",
            "has_outcome_label": outcome_decision != "unknown",
            "outcome_reason": outcome_reason,
            "outcome_segment_only": outcome_segment_only,
        },
        "training_text": training_text,
    }


def build_youtube_transcript_examples(
    *,
    youtube_chunk_rows: list[dict[str, Any]],
    youtube_embedding_index: dict[str, Any] | None,
    video_training_map: dict[str, dict[str, Any]] = DEFAULT_YOUTUBE_VIDEO_TRAINING_MAP,
) -> list[dict[str, Any]]:
    if not youtube_chunk_rows:
        return []

    prepared_documents = tve.prepare_embedding_documents(youtube_chunk_rows)
    embedding_lookup = build_embedding_item_lookup(youtube_embedding_index or {"items": []})
    examples: list[dict[str, Any]] = []

    for document in prepared_documents:
        video_slug = normalize_string(document.get("video_slug"))
        mapping = video_training_map.get(video_slug)
        if mapping is None:
            continue

        trade_model = normalize_slug(mapping.get("trade_model"))
        relation_type = normalize_string(mapping.get("relation_type"))
        topic = normalize_string(mapping.get("topic"))
        transcript_text = normalize_string(document.get("text"))
        if not trade_model or not relation_type or not transcript_text:
            continue
        if not should_include_youtube_transcript_chunk(
            video_slug=video_slug,
            transcript_text=transcript_text,
        ):
            continue
        segment_documents = split_youtube_transcript_document(document)
        force_unknown_parent_outcome = len(segment_documents) > 1
        examples.append(
            build_youtube_transcript_example(
                document=document,
                mapping=mapping,
                video_slug=video_slug,
                trade_model=trade_model,
                relation_type=relation_type,
                topic=topic,
                embedding_lookup=embedding_lookup,
                override_outcome_decision="unknown" if force_unknown_parent_outcome else None,
                override_outcome_reason=None,
            )
        )

        for segment_document in segment_documents:
            if normalize_string(segment_document.get("chunk_id")) == normalize_string(
                document.get("chunk_id")
            ):
                continue
            segment_text = normalize_string(segment_document.get("text"))
            if not should_include_youtube_transcript_chunk(
                video_slug=video_slug,
                transcript_text=segment_text,
            ):
                continue
            outcome_decision, _ = infer_youtube_transcript_outcome(
                video_slug=video_slug,
                transcript_text=segment_text,
            )
            if outcome_decision == "unknown":
                continue
            examples.append(
                build_youtube_transcript_example(
                    document=segment_document,
                    mapping=mapping,
                    video_slug=video_slug,
                    trade_model=trade_model,
                    relation_type=relation_type,
                    topic=topic,
                    embedding_lookup=embedding_lookup,
                    outcome_segment_only=True,
                )
            )

    return examples


def build_timeframe_scope_from_spec(trade_model: str) -> list[str]:
    spec_path = ROOT / "results" / "indicator_specs" / f"{trade_model}.json"
    if not spec_path.exists():
        return []
    payload = json.loads(spec_path.read_text(encoding="utf-8"))
    timeframe_contract = payload.get("timeframe_contract")
    if not isinstance(timeframe_contract, dict):
        return []
    scope: list[str] = []
    for key in ("chart", "bias", "structure", "execution"):
        value = normalize_string(timeframe_contract.get(key))
        if value:
            scope.append(f"{key}_{value}")
    return scope


def build_checkpoint_result_lookup(episode: dict) -> dict[str, dict]:
    output: dict[str, dict] = {}
    for item in episode.get("checkpoint_results", []):
        if not isinstance(item, dict):
            continue
        checkpoint = normalize_string(item.get("checkpoint"))
        if checkpoint:
            output[checkpoint] = item
    return output


def flatten_checkpoint_component_tokens(case_packet: dict, episode: dict) -> list[str]:
    checkpoint_lookup = build_checkpoint_result_lookup(episode)
    tokens: list[str] = []
    for checkpoint in case_packet.get("checkpoints", []):
        if not isinstance(checkpoint, dict):
            continue
        checkpoint_name = normalize_string(checkpoint.get("checkpoint"))
        graded_checkpoint = checkpoint_lookup.get(checkpoint_name, {})
        payload = {
            "expected": checkpoint.get("expected_component_labels", []),
            "predicted": graded_checkpoint.get("predicted_component_labels", []),
        }
        for value in flatten_strings(payload):
            cleaned = normalize_token(value)
            if cleaned:
                tokens.append(cleaned)
    return sorted(set(tokens))


def build_profile_trade_model_roles(expected_trade_models: list[str], expected_relation_types: list[str]) -> list[str]:
    roles: list[str] = []
    if not expected_relation_types:
        return expected_trade_models
    for trade_model in expected_trade_models:
        for relation_type in expected_relation_types:
            roles.append(f"{trade_model}:{relation_type}")
    return sorted(set(roles))


def resolve_trade_model_topic(trade_model: str, priors: dict[str, dict[str, str]]) -> str:
    return (
        priors.get(trade_model, {}).get("topic")
        or DEFAULT_TRADE_MODEL_TOPIC.get(trade_model, "")
    )


def resolve_trade_model_relation_type(trade_model: str, priors: dict[str, dict[str, str]]) -> str:
    return (
        priors.get(trade_model, {}).get("relation_type")
        or DEFAULT_TRADE_MODEL_RELATION_TYPE.get(trade_model, "")
    )


def build_tradingview_validation_example(
    entry: dict[str, Any],
    *,
    trade_model_priors: dict[str, dict[str, str]],
) -> dict[str, Any] | None:
    trade_model = normalize_slug(entry.get("spec_key"))
    if not trade_model or not validation_passed_qa_gate(entry):
        return None

    topic = resolve_trade_model_topic(trade_model, trade_model_priors)
    relation_type = resolve_trade_model_relation_type(trade_model, trade_model_priors) or "execution_model"
    timeframe_scope = build_timeframe_scope_from_spec(trade_model)
    chart_symbol = normalize_string(entry.get("chart_symbol"))
    validation_status = normalize_string(entry.get("validation_status"))
    validation_method = normalize_string(entry.get("validation_method"))

    annotation_payload = {
        "validation_status": validation_status,
        "validation_method": validation_method,
        "qa_status": normalize_string(entry.get("qa_status")),
        "semantic_score": entry.get("semantic_score"),
        "visual_score": entry.get("visual_score"),
        "scope_score": entry.get("scope_score"),
        "notes": normalize_string(entry.get("notes")),
        "qa_notes": normalize_string(entry.get("qa_notes")),
    }
    annotation_key_paths = sorted(set(extract_key_paths(annotation_payload)))
    annotation_value_tokens = sorted(
        {
            normalize_token(value)
            for value in flatten_strings(annotation_payload)
            if normalize_token(value)
        }
    )
    chart_context_tokens = sorted(
        token
        for token in {
            "tradingview_validation",
            validation_status,
            validation_method,
            *(normalize_token(value) for value in timeframe_scope),
            normalize_token(chart_symbol),
            normalize_token(topic),
            normalize_token(trade_model),
        }
        if token
    )

    training_text = build_training_text(
        [
            "profile ttrades_curriculum",
            f"topic {topic}",
            f"trade model {trade_model}",
            f"relation {relation_type}",
            "setup validated tradingview pine overlay",
            f"context {' '.join(chart_context_tokens)}",
            f"annotation {' '.join(annotation_value_tokens)}",
            "outcome unknown",
        ]
    )

    recorded_at = normalize_string(entry.get("recorded_at")) or "unknown_time"
    return {
        "example_id": f"tradingview_validation::{recorded_at}::{trade_model}::{relation_type}",
        "profile_slug": "ttrades_curriculum",
        "profile_name": "TTrades Curriculum",
        "profile_type": "tradingview_validation",
        "topic": topic,
        "case_ref": f"tradingview_validation::{recorded_at}::{trade_model}",
        "source_url": normalize_string(entry.get("chart_url")),
        "notes": normalize_string(entry.get("notes"))
        or "Validated TradingView chart-side example.",
        "trade_model": trade_model,
        "relation_type": relation_type,
        "confidence": 1.0,
        "indicator_ready_in_profile": True,
        "features": {
            "topic": topic,
            "setup_variant": "validated_tradingview_pine_overlay",
            "source_kind": "tradingview_validation",
            "timeframe_scope": timeframe_scope,
            "session_scope": [],
            "profile_frameworks": ["ttfm"],
            "profile_topics": [topic] if topic else [],
            "profile_trade_model_roles": [f"{trade_model}:{relation_type}"],
            "annotation_key_paths": annotation_key_paths,
            "annotation_value_tokens": annotation_value_tokens,
            "chart_context_tokens": chart_context_tokens,
        },
        "targets": {
            "trade_model": trade_model,
            "relation_type": relation_type,
            "outcome_decision": "unknown",
            "is_no_trade": False,
            "has_outcome_label": False,
            "outcome_reason": None,
        },
        "training_text": training_text,
    }


def build_tradingview_validation_examples(
    *,
    base_examples: list[dict[str, Any]],
    validation_log: dict[str, Any],
) -> list[dict[str, Any]]:
    trade_model_priors = build_trade_model_priors(base_examples)
    examples: list[dict[str, Any]] = []
    for entry in validation_log.get("validations", []):
        if not isinstance(entry, dict):
            continue
        example = build_tradingview_validation_example(
            entry,
            trade_model_priors=trade_model_priors,
        )
        if example is not None:
            examples.append(example)
    return examples


def build_reinforcement_example(episode: dict, case_packet: dict) -> dict | None:
    case_ref = normalize_string(episode.get("case_ref"))
    episode_id = normalize_string(episode.get("episode_id")) or case_ref
    expected_trade_models = normalize_labels(
        episode.get("expected_trade_models") or case_packet.get("trade_models")
    )
    expected_relation_types = normalize_labels(
        episode.get("expected_relation_types") or case_packet.get("relation_types")
    )
    if not expected_trade_models or not expected_relation_types:
        return None

    trade_model = expected_trade_models[0]
    relation_type = expected_relation_types[0]
    topic = normalize_string(case_packet.get("topic"))
    timeframe_scope = normalize_labels(case_packet.get("timeframe_stack", {}).get("labels"))
    supporting_topics = normalize_labels(case_packet.get("supporting_topics"))
    predicted_trade_model = normalize_string(episode.get("predicted_trade_model"))
    predicted_relation_type = normalize_string(episode.get("predicted_relation_type"))
    outcome = case_packet.get("outcome") or {}
    outcome_decision = normalize_outcome_decision(outcome)
    checkpoint_component_tokens = flatten_checkpoint_component_tokens(case_packet, episode)
    chart_context_tokens = sorted(
        {
            "graded_iteration",
            *(normalize_token(value) for value in timeframe_scope),
            *(normalize_token(value) for value in supporting_topics),
            normalize_token(topic),
        }
    )
    chart_context_tokens = [token for token in chart_context_tokens if token]
    annotation_payload = {
        "expected_trade_models": expected_trade_models,
        "expected_relation_types": expected_relation_types,
        "attempt_trade_model": predicted_trade_model or "unknown",
        "attempt_relation_type": predicted_relation_type or "unknown",
        "checkpoint_results": episode.get("checkpoint_results", []),
    }
    annotation_key_paths = sorted(set(extract_key_paths(annotation_payload)))
    annotation_value_tokens = sorted(
        {
            normalize_token(value)
            for value in flatten_strings(annotation_payload)
            if normalize_token(value)
        }
        | set(checkpoint_component_tokens)
    )

    training_text = build_training_text(
        [
            f"profile {normalize_string(case_packet.get('profile_slug'))}",
            f"topic {topic}",
            f"trade model {trade_model}",
            f"relation {relation_type}",
            "setup graded iteration reinforcement",
            f"context {' '.join(chart_context_tokens)}",
            f"annotation {' '.join(annotation_value_tokens)}",
            f"attempt trade model {normalize_token(predicted_trade_model) or 'unknown'}",
            f"attempt relation type {normalize_token(predicted_relation_type) or 'unknown'}",
            f"understanding score {episode.get('understanding_score', 0.0)}",
            f"outcome {outcome_decision}",
        ]
    )

    return {
        "example_id": f"iteration::{episode_id}::{trade_model}::{relation_type}",
        "profile_slug": normalize_string(case_packet.get("profile_slug")),
        "profile_name": normalize_string(case_packet.get("profile_name")),
        "profile_type": "graded_iteration",
        "topic": topic,
        "case_ref": case_ref,
        "source_url": normalize_string(case_packet.get("source_url")),
        "notes": normalize_string(case_packet.get("notes"))
        or "Reinforcement example derived from a graded TTrades iteration.",
        "trade_model": trade_model,
        "relation_type": relation_type,
        "confidence": 1.0,
        "indicator_ready_in_profile": True,
        "features": {
            "topic": topic,
            "setup_variant": "graded_iteration_reinforcement",
            "source_kind": "graded_iteration",
            "timeframe_scope": timeframe_scope,
            "session_scope": [],
            "profile_frameworks": [normalize_string(case_packet.get("framework_slug"))]
            if normalize_string(case_packet.get("framework_slug"))
            else [],
            "profile_topics": sorted(set([topic, *supporting_topics])) if topic else supporting_topics,
            "profile_trade_model_roles": build_profile_trade_model_roles(
                expected_trade_models,
                expected_relation_types,
            ),
            "annotation_key_paths": annotation_key_paths,
            "annotation_value_tokens": annotation_value_tokens,
            "chart_context_tokens": chart_context_tokens,
        },
        "targets": {
            "trade_model": trade_model,
            "relation_type": relation_type,
            "outcome_decision": outcome_decision,
            "is_no_trade": outcome_decision == "no_trade",
            "has_outcome_label": outcome_decision != "unknown",
            "outcome_reason": outcome.get("reason"),
        },
        "training_text": training_text,
    }


def build_reinforced_training_surface(
    *,
    base_examples: list[dict[str, Any]],
    case_packet_report: dict,
    iteration_grading_report: dict,
    tradingview_validation_log: dict | None = None,
    youtube_chunk_rows: list[dict[str, Any]] | None = None,
    youtube_embedding_index: dict[str, Any] | None = None,
) -> dict[str, Any]:
    case_lookup = build_case_packet_lookup(case_packet_report)
    iteration_reinforcement_examples: list[dict[str, Any]] = []
    skipped_episode_count = 0
    graded_episode_count = 0

    for episode in iteration_grading_report.get("episodes", []):
        if normalize_string(episode.get("status")) != "graded":
            skipped_episode_count += 1
            continue
        graded_episode_count += 1
        case_packet = case_lookup.get(normalize_string(episode.get("case_ref")))
        if case_packet is None:
            skipped_episode_count += 1
            continue
        example = build_reinforcement_example(episode, case_packet)
        if example is None:
            skipped_episode_count += 1
            continue
        iteration_reinforcement_examples.append(example)

    tradingview_validation_examples = build_tradingview_validation_examples(
        base_examples=[*base_examples, *iteration_reinforcement_examples],
        validation_log=tradingview_validation_log or {"validations": []},
    )
    youtube_transcript_examples = build_youtube_transcript_examples(
        youtube_chunk_rows=youtube_chunk_rows or [],
        youtube_embedding_index=youtube_embedding_index,
    )
    reinforcement_examples = [
        *iteration_reinforcement_examples,
        *tradingview_validation_examples,
    ]
    merged_examples = [
        *base_examples,
        *reinforcement_examples,
        *youtube_transcript_examples,
    ]
    merged_examples = annotate_source_groups(merged_examples)
    surface_summary = summarize_training_surface(merged_examples)
    summary = {
        **surface_summary,
        "base_example_count": len(base_examples),
        "iteration_reinforcement_example_count": len(iteration_reinforcement_examples),
        "tradingview_validation_example_count": len(tradingview_validation_examples),
        "youtube_transcript_example_count": len(youtube_transcript_examples),
        "reinforcement_example_count": len(reinforcement_examples),
        "merged_example_count": len(merged_examples),
        "graded_episode_count": graded_episode_count,
        "skipped_episode_count": skipped_episode_count,
    }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "examples": merged_examples,
        "reinforcement_examples": reinforcement_examples,
        "iteration_reinforcement_examples": iteration_reinforcement_examples,
        "tradingview_validation_examples": tradingview_validation_examples,
        "youtube_transcript_examples": youtube_transcript_examples,
    }


def export_reinforced_training_surface(
    *,
    base_dataset_path: Path,
    case_packet_report_path: Path,
    iteration_grading_report_path: Path,
    tradingview_validation_log_path: Path,
    youtube_chunks_path: Path,
    youtube_embedding_index_path: Path,
    dataset_output: Path,
    report_output: Path,
) -> dict[str, Any]:
    report = build_reinforced_training_surface(
        base_examples=load_jsonl_examples(base_dataset_path),
        case_packet_report=load_json(case_packet_report_path, {"case_packets": [], "summary": {}}),
        iteration_grading_report=load_json(iteration_grading_report_path, {"episodes": [], "summary": {}}),
        tradingview_validation_log=load_json(tradingview_validation_log_path, {"validations": []}),
        youtube_chunk_rows=tve.load_chunk_rows(youtube_chunks_path) if youtube_chunks_path.exists() else [],
        youtube_embedding_index=load_optional_embedding_index(youtube_embedding_index_path),
    )

    dataset_output.parent.mkdir(parents=True, exist_ok=True)
    with dataset_output.open("w", encoding="utf-8") as handle:
        for example in report["examples"]:
            handle.write(json.dumps(example, sort_keys=True) + "\n")

    persisted_report = {
        "generated_at": report["generated_at"],
        "summary": report["summary"],
        "dataset_output": str(dataset_output),
        "report_output": str(report_output),
    }
    report_output.parent.mkdir(parents=True, exist_ok=True)
    report_output.write_text(json.dumps(persisted_report, indent=2) + "\n", encoding="utf-8")
    return persisted_report


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Merge the base TTrades training surface with graded iteration episodes so "
            "future narrow models can learn from supervised correction loops and "
            "YouTube transcript evidence."
        )
    )
    parser.add_argument("--base-dataset", default=str(DEFAULT_BASE_DATASET_PATH))
    parser.add_argument("--case-packets", default=str(DEFAULT_CASE_PACKET_REPORT_PATH))
    parser.add_argument("--iteration-grading", default=str(DEFAULT_ITERATION_GRADING_REPORT_PATH))
    parser.add_argument("--validation-log", default=str(DEFAULT_TRADINGVIEW_VALIDATION_LOG_PATH))
    parser.add_argument("--youtube-chunks", default=str(DEFAULT_TTFM_VIDEO_CHUNKS_PATH))
    parser.add_argument("--youtube-embedding-index", default=str(DEFAULT_TTFM_VIDEO_EMBEDDING_INDEX_PATH))
    parser.add_argument("--dataset-output", default=str(DEFAULT_DATASET_OUTPUT))
    parser.add_argument("--report-output", default=str(DEFAULT_REPORT_OUTPUT))
    args = parser.parse_args()

    report = export_reinforced_training_surface(
        base_dataset_path=Path(args.base_dataset),
        case_packet_report_path=Path(args.case_packets),
        iteration_grading_report_path=Path(args.iteration_grading),
        tradingview_validation_log_path=Path(args.validation_log),
        youtube_chunks_path=Path(args.youtube_chunks),
        youtube_embedding_index_path=Path(args.youtube_embedding_index),
        dataset_output=Path(args.dataset_output),
        report_output=Path(args.report_output),
    )
    print(
        json.dumps(
            {
                "dataset_output": report["dataset_output"],
                "report_output": report["report_output"],
                "merged_example_count": report["summary"]["merged_example_count"],
                "reinforcement_example_count": report["summary"]["reinforcement_example_count"],
                "youtube_transcript_example_count": report["summary"]["youtube_transcript_example_count"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
