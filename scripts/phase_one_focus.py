from __future__ import annotations

from typing import Iterable


DEFERRED_TRAINING_LABELS = frozenset({"phases_of_price_framework"})
PHASE_ONE_PRIMARY_TRADE_MODEL = "daily_bias_framework"
PHASE_ONE_EXECUTION_SPEC = "daily_bias_c123_map"
ALLOWED_PHASE_ONE_EXTRA_TRAINING_LABELS = frozenset({PHASE_ONE_EXECUTION_SPEC})
PHASE_ONE_BOOTSTRAP_POSITIVE_MINIMUMS = {
    PHASE_ONE_PRIMARY_TRADE_MODEL: 4,
}
PHASE_ONE_TIMEFRAME_STACK = {
    "bias": "D",
    "structure": "60",
    "execution": "5",
}
PHASE_ONE_GOAL = (
    "Train the neural network to understand daily bias, higher-time-frame levels, "
    "and 1H-to-5m C1/C2/C3 alignment."
)


def split_training_labels(
    labels: Iterable[str],
) -> tuple[list[str], list[str]]:
    filtered_labels = filter_extra_training_labels(labels)
    active: list[str] = []
    deferred: list[str] = []
    for label in filtered_labels:
        if label in DEFERRED_TRAINING_LABELS:
            deferred.append(label)
        else:
            active.append(label)
    return active, deferred


def filter_extra_training_labels(labels: Iterable[str]) -> list[str]:
    return [
        label
        for label in sorted({str(label).strip() for label in labels if str(label).strip()})
        if label not in ALLOWED_PHASE_ONE_EXTRA_TRAINING_LABELS
    ]


def build_phase_one_focus(
    training_surface: dict,
    *,
    indicator_ready_trade_models: list[str] | None = None,
) -> dict:
    indicator_ready_trade_models = indicator_ready_trade_models or []
    trade_model_tasks = {
        str(task.get("trade_model", "")).strip(): task
        for task in training_surface.get("trade_model_binary_tasks", [])
        if isinstance(task, dict) and str(task.get("trade_model", "")).strip()
    }
    task = trade_model_tasks.get(PHASE_ONE_PRIMARY_TRADE_MODEL, {})
    positive_examples = int(task.get("positive_examples", 0) or 0)
    negative_examples = int(task.get("negative_examples", 0) or 0)
    additional_positive_examples_needed = int(
        task.get("additional_positive_examples_needed", 0) or 0
    )
    recommended_negative_examples = int(
        task.get("recommended_negative_examples", 0) or 0
    )
    bootstrap_positive_minimum = PHASE_ONE_BOOTSTRAP_POSITIVE_MINIMUMS.get(
        PHASE_ONE_PRIMARY_TRADE_MODEL,
        0,
    )
    bootstrap_ready = (
        positive_examples >= bootstrap_positive_minimum
        and negative_examples >= recommended_negative_examples
    )
    ready_now = bool(task.get("ready"))
    if ready_now:
        status = "ready"
    elif bootstrap_ready:
        status = "bootstrap_ready"
    else:
        status = "needs_more_examples"
    return {
        "goal": PHASE_ONE_GOAL,
        "primary_trade_model": PHASE_ONE_PRIMARY_TRADE_MODEL,
        "execution_spec": PHASE_ONE_EXECUTION_SPEC,
        "timeframe_stack": dict(PHASE_ONE_TIMEFRAME_STACK),
        "indicator_ready": PHASE_ONE_PRIMARY_TRADE_MODEL in indicator_ready_trade_models,
        "status": status,
        "ready_now": ready_now,
        "bootstrap_ready": bootstrap_ready,
        "positive_examples": positive_examples,
        "negative_examples": negative_examples,
        "additional_positive_examples_needed": additional_positive_examples_needed,
        "bootstrap_positive_examples_required": bootstrap_positive_minimum,
        "current_training_target": PHASE_ONE_PRIMARY_TRADE_MODEL,
    }
