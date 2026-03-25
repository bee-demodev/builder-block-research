from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from evaluate_rulebook import evaluate


ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "research.db"
RESULTS_PATH = ROOT / "results" / "research_runs.tsv"


def append_row(topic: str, status: str, description: str) -> dict:
    score = evaluate(topic)
    timestamp = datetime.now(timezone.utc).isoformat()
    row = "\t".join(
        [
            timestamp,
            score.topic,
            f"{score.grounding_score:.4f}",
            f"{score.determinism_score:.4f}",
            f"{score.visual_verification_score:.4f}",
            f"{score.pine_translatability_score:.4f}",
            str(score.contradiction_penalty),
            f"{score.weighted_score:.4f}",
            status,
            description.replace("\t", " ").strip()
        ]
    )
    with RESULTS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(row + "\n")

    with sqlite3.connect(DB_PATH) as connection:
        connection.execute(
            """
            INSERT INTO research_runs (
                topic_slug,
                grounding_score,
                determinism_score,
                visual_verification_score,
                pine_translatability_score,
                contradiction_penalty,
                weighted_score,
                status,
                description
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                score.topic,
                score.grounding_score,
                score.determinism_score,
                score.visual_verification_score,
                score.pine_translatability_score,
                score.contradiction_penalty,
                score.weighted_score,
                status,
                description.replace("\t", " ").strip(),
            ),
        )
        connection.commit()

    return {
        "run_at": timestamp,
        "topic": score.topic,
        "status": status,
        "weighted_score": score.weighted_score,
        "determinism_score": score.determinism_score,
        "pine_translatability_score": score.pine_translatability_score,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Append a research run evaluation to results/research_runs.tsv")
    parser.add_argument("--topic", required=True)
    parser.add_argument("--status", required=True, choices=["keep", "discard", "crash", "note"])
    parser.add_argument("--description", required=True)
    args = parser.parse_args()

    summary = append_row(args.topic, args.status, args.description)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
