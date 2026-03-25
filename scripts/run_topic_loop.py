from __future__ import annotations

import argparse
import json

from evaluate_rulebook import evaluate
from log_research_run import append_row
from sync_rulebook_to_db import sync_topic


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run one topic autoresearch bookkeeping cycle: sync rulebook, evaluate it, and log the run."
    )
    parser.add_argument("--topic", required=True, help="Topic folder name under topics/")
    parser.add_argument(
        "--status",
        default="note",
        choices=["keep", "discard", "crash", "note"],
        help="Run disposition to log after scoring.",
    )
    parser.add_argument(
        "--description",
        default="automated topic loop",
        help="Short note describing what this loop iteration represents.",
    )
    args = parser.parse_args()

    sync_summary = sync_topic(args.topic)
    score = evaluate(args.topic)
    log_summary = append_row(args.topic, args.status, args.description)

    print(
        json.dumps(
            {
                "sync": sync_summary,
                "score": score.__dict__,
                "log": log_summary,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
