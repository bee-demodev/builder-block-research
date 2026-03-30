from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from config import Phase1Config, SETUP_LABELS
from data_loader import ChartExample, embed_chart_image, find_example_by_image


BOOTSTRAP_KEYWORDS = {
    "high_probability_long": (
        "bullish",
        "trade higher",
        "continuation higher",
        "move higher",
        "buy",
        "long",
    ),
    "high_probability_short": (
        "bearish",
        "trade lower",
        "continuation lower",
        "move lower",
        "sell",
        "short",
    ),
    "invalid_chop": (
        "no trade",
        "stand aside",
        "invalid",
        "chop",
        "range rotation",
        "whipsaw",
        "failure",
        "consolidating",
    ),
}


@dataclass(slots=True)
class AnchorExample:
    class_label: str
    image_path: str | None
    example_id: str | None
    note: str
    metadata: dict[str, Any]


@dataclass(slots=True)
class PseudoLabelRow:
    example_id: str
    pseudo_label: str | None
    confidence: float
    margin: float
    class_scores: dict[str, float]
    nearest_anchors: list[dict[str, Any]]
    reason: str
    time_index: int


@dataclass(slots=True)
class PseudoLabelResult:
    rows: list[PseudoLabelRow]
    anchors: list[AnchorExample]
    review_queue: list[dict[str, Any]]
    summary: dict[str, Any]


def _normalize(vector: np.ndarray) -> np.ndarray:
    flattened = np.asarray(vector, dtype=np.float32).reshape(-1)
    norm = float(np.linalg.norm(flattened))
    if norm == 0.0:
        return flattened
    return flattened / norm


def _score_text(example: ChartExample, keywords: tuple[str, ...]) -> int:
    haystack = f"{example.title} {example.text}".lower()
    return sum(1 for keyword in keywords if keyword in haystack)


def bootstrap_anchor_examples(
    examples: list[ChartExample],
    *,
    per_class: int,
) -> list[AnchorExample]:
    anchors: list[AnchorExample] = []
    used_ids: set[str] = set()
    for class_label in SETUP_LABELS:
        ranked = sorted(
            examples,
            key=lambda item: (_score_text(item, BOOTSTRAP_KEYWORDS[class_label]), -item.time_index),
            reverse=True,
        )
        picked = 0
        for example in ranked:
            if example.example_id in used_ids:
                continue
            score = _score_text(example, BOOTSTRAP_KEYWORDS[class_label])
            if score <= 0 and picked > 0:
                continue
            anchors.append(
                AnchorExample(
                    class_label=class_label,
                    image_path=str(example.image_path),
                    example_id=example.example_id,
                    note=f"Auto-bootstrapped from corpus text heuristics with score={score}.",
                    metadata={"time_index": example.time_index},
                )
            )
            used_ids.add(example.example_id)
            picked += 1
            if picked >= per_class:
                break
    return anchors


def load_anchor_examples(path: Path) -> list[AnchorExample]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload if isinstance(payload, list) else payload.get("anchors", [])
    anchors: list[AnchorExample] = []
    for row in rows:
        anchors.append(
            AnchorExample(
                class_label=str(row["class_label"]).strip(),
                image_path=str(row.get("image_path", "")).strip() or None,
                example_id=str(row.get("example_id", "")).strip() or None,
                note=str(row.get("note", "")).strip(),
                metadata=dict(row.get("metadata", {})),
            )
        )
    return anchors


def save_anchor_examples(path: Path, anchors: list[AnchorExample]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "anchors": [
            {
                "class_label": anchor.class_label,
                "image_path": anchor.image_path,
                "example_id": anchor.example_id,
                "note": anchor.note,
                "metadata": anchor.metadata,
            }
            for anchor in anchors
        ]
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _resolve_anchor_vectors(
    examples: list[ChartExample],
    anchors: list[AnchorExample],
    *,
    config: Any | None = None,
) -> list[dict[str, Any]]:
    resolved: list[dict[str, Any]] = []
    for anchor in anchors:
        matched: ChartExample | None = None
        if anchor.example_id:
            matched = next((item for item in examples if item.example_id == anchor.example_id), None)
        if matched is None and anchor.image_path:
            matched = find_example_by_image(examples, Path(anchor.image_path))

        if matched is not None:
            resolved.append(
                {
                    "class_label": anchor.class_label,
                    "example_id": matched.example_id,
                    "image_path": str(matched.image_path),
                    "vector": matched.embedding,
                }
            )
            continue

        if not anchor.image_path or config is None:
            raise ValueError(
                f"Anchor {anchor.class_label!r} could not be resolved from the current corpus and "
                "no config was supplied for live embedding."
            )

        vector = embed_chart_image(Path(anchor.image_path), config)
        resolved.append(
            {
                "class_label": anchor.class_label,
                "example_id": anchor.example_id,
                "image_path": anchor.image_path,
                "vector": vector,
            }
        )
    return resolved


def _weighted_average(scores: list[tuple[float, float]]) -> float:
    total_weight = sum(weight for weight, _ in scores)
    if total_weight <= 0:
        return 0.0
    return sum(weight * value for weight, value in scores) / total_weight


def label_examples_with_anchors(
    examples: list[ChartExample],
    anchors: list[AnchorExample],
    phase1_config: Phase1Config,
    *,
    config: Any | None = None,
) -> PseudoLabelResult:
    resolved_anchors = _resolve_anchor_vectors(examples, anchors, config=config)
    if not resolved_anchors:
        raise ValueError("At least one anchor example is required for pseudo-labeling.")
    anchor_label_lookup = {
        anchor.example_id: anchor.class_label
        for anchor in anchors
        if anchor.example_id
    }

    class_to_vectors: dict[str, list[np.ndarray]] = {label: [] for label in SETUP_LABELS}
    for anchor in resolved_anchors:
        class_to_vectors[anchor["class_label"]].append(_normalize(anchor["vector"]))

    prototypes = {
        class_label: _normalize(np.mean(vectors, axis=0))
        for class_label, vectors in class_to_vectors.items()
        if vectors
    }

    rows: list[PseudoLabelRow] = []
    review_queue: list[dict[str, Any]] = []
    anchor_count = len(resolved_anchors)
    k = max(1, min(phase1_config.knn_k, anchor_count))

    for example in examples:
        if example.example_id in anchor_label_lookup:
            rows.append(
                PseudoLabelRow(
                    example_id=example.example_id,
                    pseudo_label=anchor_label_lookup[example.example_id],
                    confidence=1.0,
                    margin=1.0,
                    class_scores={
                        label: 1.0 if label == anchor_label_lookup[example.example_id] else 0.0
                        for label in SETUP_LABELS
                    },
                    nearest_anchors=[],
                    reason="anchor_seed",
                    time_index=example.time_index,
                )
            )
            continue

        vector = _normalize(example.embedding)
        proto_scores = {
            label: float(np.dot(vector, prototype))
            for label, prototype in prototypes.items()
        }

        anchor_scores: list[dict[str, Any]] = []
        for anchor in resolved_anchors:
            if anchor["example_id"] and anchor["example_id"] == example.example_id:
                continue
            similarity = float(np.dot(vector, anchor["vector"]))
            anchor_scores.append(
                {
                    "class_label": anchor["class_label"],
                    "example_id": anchor["example_id"],
                    "image_path": anchor["image_path"],
                    "similarity": similarity,
                }
            )
        anchor_scores.sort(key=lambda item: item["similarity"], reverse=True)
        nearest_anchors = anchor_scores[:k]
        knn_scores = {label: 0.0 for label in SETUP_LABELS}
        if nearest_anchors:
            total_similarity = sum(max(item["similarity"], 0.0) for item in nearest_anchors) or 1.0
            for item in nearest_anchors:
                knn_scores[item["class_label"]] += max(item["similarity"], 0.0) / total_similarity

        combined_scores: dict[str, float] = {}
        for class_label in SETUP_LABELS:
            weighted_inputs: list[tuple[float, float]] = []
            if class_label in proto_scores:
                weighted_inputs.append((phase1_config.prototype_weight, max(proto_scores[class_label], 0.0)))
            if nearest_anchors:
                weighted_inputs.append((phase1_config.knn_weight, knn_scores[class_label]))
            combined_scores[class_label] = _weighted_average(weighted_inputs)

        ordered_scores = sorted(combined_scores.items(), key=lambda item: item[1], reverse=True)
        best_label, best_score = ordered_scores[0]
        second_score = ordered_scores[1][1] if len(ordered_scores) > 1 else 0.0
        margin = best_score - second_score

        pseudo_label: str | None
        reason = "confident"
        if best_score < phase1_config.abstain_threshold:
            pseudo_label = None
            reason = "below_abstain_threshold"
        elif best_score < phase1_config.confidence_floor:
            pseudo_label = None
            reason = "below_confidence_floor"
        elif margin < phase1_config.min_margin:
            pseudo_label = None
            reason = "low_margin"
        else:
            pseudo_label = best_label

        row = PseudoLabelRow(
            example_id=example.example_id,
            pseudo_label=pseudo_label,
            confidence=round(best_score, 6),
            margin=round(margin, 6),
            class_scores={label: round(score, 6) for label, score in combined_scores.items()},
            nearest_anchors=[
                {
                    "example_id": item["example_id"],
                    "class_label": item["class_label"],
                    "similarity": round(item["similarity"], 6),
                }
                for item in nearest_anchors
            ],
            reason=reason,
            time_index=example.time_index,
        )
        rows.append(row)
        if pseudo_label is None:
            review_queue.append(
                {
                    "example_id": example.example_id,
                    "image_path": str(example.image_path),
                    "confidence": row.confidence,
                    "margin": row.margin,
                    "reason": reason,
                    "class_scores": row.class_scores,
                }
            )

    label_counts = {label: 0 for label in SETUP_LABELS}
    for row in rows:
        if row.pseudo_label:
            label_counts[row.pseudo_label] += 1
    summary = {
        "row_count": len(rows),
        "labeled_count": sum(label_counts.values()),
        "abstained_count": len(review_queue),
        "label_counts": label_counts,
        "anchor_count": len(anchors),
    }
    return PseudoLabelResult(rows=rows, anchors=anchors, review_queue=review_queue, summary=summary)


def save_pseudo_label_outputs(result: PseudoLabelResult, *, pseudo_labels_path: Path, review_queue_path: Path) -> None:
    pseudo_labels_path.parent.mkdir(parents=True, exist_ok=True)
    with pseudo_labels_path.open("w", encoding="utf-8") as handle:
        for row in result.rows:
            handle.write(
                json.dumps(
                    {
                        "example_id": row.example_id,
                        "pseudo_label": row.pseudo_label,
                        "confidence": row.confidence,
                        "margin": row.margin,
                        "class_scores": row.class_scores,
                        "nearest_anchors": row.nearest_anchors,
                        "reason": row.reason,
                        "time_index": row.time_index,
                    }
                )
                + "\n"
            )
    review_queue_path.write_text(
        json.dumps({"summary": result.summary, "items": result.review_queue}, indent=2),
        encoding="utf-8",
    )


def select_representative_examples(
    examples: list[ChartExample],
    *,
    cluster_method: str,
    min_clusters: int,
    max_clusters: int,
    representative_budget: int,
    random_samples_per_cluster: int,
    seed: int,
) -> dict[str, Any]:
    if not examples:
        raise ValueError("At least one example is required for representative selection.")

    matrix = np.vstack([example.embedding for example in examples]).astype(np.float32)
    n_examples = len(examples)

    if n_examples < min_clusters:
        target_clusters = max(2, int(round(np.sqrt(n_examples))))
    else:
        target_clusters = min(max_clusters, max(min_clusters, int(round(np.sqrt(n_examples * 10)))))
    target_clusters = min(target_clusters, n_examples)

    labels: np.ndarray

    def simple_kmeans(samples: np.ndarray, cluster_count: int, random_seed: int, max_iterations: int = 25) -> np.ndarray:
        rng = np.random.default_rng(random_seed)
        centroid_indices = rng.choice(len(samples), size=cluster_count, replace=False)
        centroids = samples[centroid_indices].copy()
        assignments = np.zeros(len(samples), dtype=np.int64)
        for _ in range(max_iterations):
            distances = np.linalg.norm(samples[:, None, :] - centroids[None, :, :], axis=2)
            new_assignments = np.argmin(distances, axis=1)
            if np.array_equal(assignments, new_assignments):
                break
            assignments = new_assignments
            for centroid_index in range(cluster_count):
                members = samples[assignments == centroid_index]
                if len(members) == 0:
                    centroids[centroid_index] = samples[rng.integers(0, len(samples))]
                else:
                    centroids[centroid_index] = np.mean(members, axis=0)
        return assignments
    used_method = cluster_method
    if cluster_method == "hdbscan":
        try:
            import hdbscan  # type: ignore
        except Exception:
            used_method = "kmeans"
        else:
            clusterer = hdbscan.HDBSCAN(min_cluster_size=max(2, min(12, n_examples // 8 or 2)))
            labels = clusterer.fit_predict(matrix)
    if cluster_method != "hdbscan" or used_method == "kmeans":
        try:
            from sklearn.cluster import KMeans
        except Exception:
            labels = simple_kmeans(matrix, target_clusters, seed)
            used_method = "simple_kmeans"
        else:
            clusterer = KMeans(n_clusters=target_clusters, n_init=10, random_state=seed)
            labels = clusterer.fit_predict(matrix)

    cluster_map: dict[int, list[ChartExample]] = {}
    for label, example in zip(labels, examples):
        cluster_map.setdefault(int(label), []).append(example)

    rng = np.random.default_rng(seed)
    selected_ids: set[str] = set()
    selected_examples: list[ChartExample] = []
    for cluster_examples in cluster_map.values():
        cluster_matrix = np.vstack([example.embedding for example in cluster_examples])
        centroid = np.mean(cluster_matrix, axis=0)
        distances = np.linalg.norm(cluster_matrix - centroid, axis=1)
        medoid_index = int(np.argmin(distances))
        medoid = cluster_examples[medoid_index]
        selected_examples.append(medoid)
        selected_ids.add(medoid.example_id)

    budget = min(max(1, representative_budget), n_examples)
    remaining_budget = max(0, budget - len(selected_examples))
    for cluster_examples in cluster_map.values():
        if remaining_budget <= 0:
            break
        candidates = [example for example in cluster_examples if example.example_id not in selected_ids]
        if not candidates:
            continue
        rng.shuffle(candidates)
        for example in candidates[: min(random_samples_per_cluster, remaining_budget)]:
            selected_examples.append(example)
            selected_ids.add(example.example_id)
            remaining_budget -= 1
            if remaining_budget <= 0:
                break

    selected_examples.sort(key=lambda item: item.time_index)
    return {
        "method": used_method,
        "cluster_count": len(cluster_map),
        "requested_budget": representative_budget,
        "selected_count": len(selected_examples),
        "examples": selected_examples,
        "cluster_assignments": {
            example.example_id: int(label) for example, label in zip(examples, labels)
        },
    }
