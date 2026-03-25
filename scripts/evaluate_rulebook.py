from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
TOPICS_DIR = ROOT / "topics"

REQUIRED_RULE_FIELDS = [
    "id",
    "name",
    "timeframeScope",
    "marketPhasePrecondition",
    "direction",
    "setupAnchor",
    "confirmationTrigger",
    "protectedSwingDefinition",
    "invalidationCondition",
    "targetLogic",
    "exceptions",
    "evidenceRefs",
    "visualVerificationRefs",
    "pineInputsNeeded",
    "machineChecks",
    "ambiguityNotes"
]

DISCRETIONARY_MARKERS = [
    "important level",
    "point of interest",
    "key level",
    "relevant point of interest",
    "clarity",
    "looks strong",
    "clean move",
    "good reaction",
    "obvious",
    "nice trend"
]

UNRESOLVED_MARKERS = [
    "not yet numeric",
    "still contains discretion",
    "needs a stricter algorithm",
    "need narrowing",
    "heuristic",
    "probably be optional",
    "needs a strict implementation rule",
    "need explicit precedence rules"
]

NUMERIC_HINT_MARKERS = [
    "percentile",
    "ratio",
    "count",
    "threshold",
    "bar-close",
    "opening price",
    "equilibrium",
    "previous day",
    "high",
    "low",
    "body",
    "wick"
]


@dataclass
class TopicScore:
    topic: str
    grounding_score: float
    determinism_score: float
    visual_verification_score: float
    pine_translatability_score: float
    contradiction_penalty: int
    weighted_score: float
    rule_count: int


def clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def load_rulebook(topic: str) -> dict:
    path = TOPICS_DIR / topic / "rulebook.json"
    if not path.exists():
        raise FileNotFoundError(f"Rulebook not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def score_grounding(rules: list[dict]) -> float:
    if not rules:
        return 0.0
    grounded = sum(1 for rule in rules if rule.get("evidenceRefs"))
    return grounded / len(rules)


def score_determinism(rules: list[dict]) -> float:
    if not rules:
        return 0.0
    per_rule_scores: list[float] = []
    for rule in rules:
        present_fields = 0
        for field in REQUIRED_RULE_FIELDS:
            value = rule.get(field)
            if isinstance(value, list):
                if value:
                    present_fields += 1
            elif isinstance(value, str):
                if value.strip():
                    present_fields += 1
            elif value is not None:
                present_fields += 1

        field_score = present_fields / len(REQUIRED_RULE_FIELDS)
        machine_score = 1.0 if rule.get("machineChecks") else 0.0
        text_blob = " ".join(
            [
                str(rule.get("setupAnchor", "")),
                str(rule.get("confirmationTrigger", "")),
                str(rule.get("protectedSwingDefinition", "")),
                str(rule.get("invalidationCondition", "")),
                str(rule.get("targetLogic", "")),
                " ".join(rule.get("machineChecks", [])),
                " ".join(rule.get("ambiguityNotes", []))
            ]
        ).lower()
        unresolved_hits = sum(1 for marker in UNRESOLVED_MARKERS if marker in text_blob)
        ambiguity_penalty = min((len(rule.get("ambiguityNotes", [])) * 0.08) + (unresolved_hits * 0.07), 0.45)
        numeric_hints = sum(1 for marker in NUMERIC_HINT_MARKERS if marker in text_blob)
        quantification_bonus = min(numeric_hints * 0.02, 0.12)
        per_rule_scores.append(clamp((field_score * 0.7) + (machine_score * 0.18) + quantification_bonus - ambiguity_penalty))
    return sum(per_rule_scores) / len(per_rule_scores)


def score_visual_verification(rules: list[dict]) -> float:
    if not rules:
        return 0.0
    verified = sum(1 for rule in rules if rule.get("visualVerificationRefs"))
    return verified / len(rules)


def score_pine_translatability(rules: list[dict]) -> float:
    if not rules:
        return 0.0
    values: list[float] = []
    for rule in rules:
        inputs_ok = 1.0 if rule.get("pineInputsNeeded") else 0.0
        checks_ok = 1.0 if rule.get("machineChecks") else 0.0
        text_blob = " ".join(
            [
                str(rule.get("setupAnchor", "")),
                str(rule.get("confirmationTrigger", "")),
                str(rule.get("invalidationCondition", "")),
                str(rule.get("targetLogic", "")),
                " ".join(rule.get("ambiguityNotes", []))
            ]
        ).lower()
        marker_hits = sum(1 for marker in DISCRETIONARY_MARKERS if marker in text_blob)
        unresolved_hits = sum(1 for marker in UNRESOLVED_MARKERS if marker in text_blob)
        marker_penalty = min((marker_hits * 0.12) + (unresolved_hits * 0.08), 0.55)
        values.append(clamp((inputs_ok * 0.40) + (checks_ok * 0.40) + 0.08 - marker_penalty))
    return sum(values) / len(values)


def score_contradictions(rulebook: dict) -> int:
    contradictions = rulebook.get("contradictions", [])
    open_questions = rulebook.get("openQuestions", [])
    return len(contradictions) + max(0, len(open_questions) - 2)


def evaluate(topic: str) -> TopicScore:
    rulebook = load_rulebook(topic)
    rules = rulebook.get("rules", [])
    grounding = score_grounding(rules)
    determinism = score_determinism(rules)
    visual = score_visual_verification(rules)
    pine = score_pine_translatability(rules)
    contradiction_penalty = score_contradictions(rulebook)

    weighted = clamp(
        (grounding * 0.30)
        + (determinism * 0.30)
        + (visual * 0.15)
        + (pine * 0.25)
        - (contradiction_penalty * 0.03)
    )

    return TopicScore(
        topic=topic,
        grounding_score=round(grounding, 4),
        determinism_score=round(determinism, 4),
        visual_verification_score=round(visual, 4),
        pine_translatability_score=round(pine, 4),
        contradiction_penalty=contradiction_penalty,
        weighted_score=round(weighted, 4),
        rule_count=len(rules)
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a topic rulebook for research quality.")
    parser.add_argument("--topic", required=True, help="Topic folder name under topics/")
    args = parser.parse_args()

    score = evaluate(args.topic)
    print(json.dumps(score.__dict__, indent=2))


if __name__ == "__main__":
    main()
