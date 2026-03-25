from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from score_pattern_state import default_model_path, score_pattern_state


def summarize_score(scored: dict[str, Any], *, case_ref: str | None) -> dict[str, Any]:
    return {
        "case_ref": case_ref,
        "task_name": scored["task_name"],
        "probability": scored["probability"],
        "prediction": scored["prediction"],
        "threshold": scored["threshold"],
        "device": scored["device"],
        "matched_vocabulary_token_count": scored["matched_vocabulary_token_count"],
        "input_token_count": scored["input_token_count"],
    }


def score_states_to_signals(
    states: list[dict[str, Any]],
    *,
    model_path: Path,
    device_preference: str = "auto",
    threshold: float = 0.5,
) -> dict[str, Any]:
    scores: list[dict[str, Any]] = []
    signals: list[dict[str, Any]] = []

    for state in states:
        scored = score_pattern_state(
            state,
            model_path=model_path,
            device_preference=device_preference,
            threshold=threshold,
        )
        scores.append(summarize_score(scored, case_ref=state.get("case_ref")))
        if scored["signal"] is not None:
            signals.append(scored["signal"])

    task_name = scores[0]["task_name"] if scores else None
    return {
        "task_name": task_name,
        "state_count": len(states),
        "accepted_signal_count": len(signals),
        "scores": scores,
        "signals": signals,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Score a batch of structured chart states and emit runtime-compatible signals "
            "for the states that clear the configured model threshold."
        )
    )
    parser.add_argument("--states-json", required=True)
    parser.add_argument("--task-name")
    parser.add_argument("--model-path")
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda", "mps"])
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--output", default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    loaded = json.loads(Path(args.states_json).read_text(encoding="utf-8"))
    if isinstance(loaded, dict):
        states = list(loaded.get("states", []))
    elif isinstance(loaded, list):
        states = loaded
    else:
        raise ValueError("Batch state input must be a list or a {'states': [...]} object.")

    model_path = Path(args.model_path) if args.model_path else default_model_path(str(args.task_name))
    result = score_states_to_signals(
        states,
        model_path=model_path,
        device_preference=args.device,
        threshold=args.threshold,
    )

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
