"""The criteria of the TTrades checklist: keys, labels, stage and class.

Keys, classes and stages are those of rules.md sections 6 and 7. The class decides how
a criterion feeds the decision (rules.md section 10):

- gate: ``False`` kills the path until the next bias candle
- step: ``False`` means "has not happened yet"; steps set the stage
- quality: ``False`` blocks entry-ready but keeps the path alive
- advisory: reported, never changes the decision

The class written in a ``Spec`` is the default. Five criteria take theirs from the config
(``session_filter_role``, ``stop_size_role``, ``objective_open_role``, ``reward_check_role`` and, through
``reversal_expansion_test``, ``rev_expansion_into_level``); the path modules pass the
configured class in ``roles``. ``cont_objective_open_at_trigger`` takes its class from
``objective_at_trigger_role`` the same way.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from companion.styles.ttrades.primitives import Side
from companion.types import CriterionResult, TimeframeStack

GATE, STEP, QUALITY, ADVISORY = "gate", "step", "quality", "advisory"
STAGES: tuple[str, ...] = ("c1", "c2", "c3", "c4")


@dataclass(frozen=True)
class Spec:
    key: str
    label: str  # may use {lo} / {hi} (the extreme on the trade's stop / target side), {above}, {down_close}
    path: str  # "shared" | "continuation" | "reversal"
    stage: str  # "" for shared, else c1..c4
    role: str
    tf: str | None  # "bias" | "setup" | "entry" | None (all)


SHARED: tuple[Spec, ...] = (
    Spec("data_sufficient", "Enough history on all three timeframes", "shared", "", GATE, None),
    Spec("stack_pairing_stated", "Stack is one TTrades teaches", "shared", "", ADVISORY, None),
)

SESSION = Spec("session_filter_ok", "Inside a kill zone (information)", "shared", "", ADVISORY, "entry")

# Class from ``stop_size_role`` (advisory by default). Measured on the trigger's own stop.
STOP_SIZE = Spec("stop_size_ok", "Stop is wide enough for its costs (share of the daily range)", "shared", "", ADVISORY, "entry")

CONTINUATION: tuple[Spec, ...] = (
    Spec("bias_closure_directional", "Bias candle closed with a direction", "continuation", "c1", GATE, "bias"),
    Spec("bias_poi_present", "Bias swing formed at a point of interest", "continuation", "c1", GATE, "bias"),
    Spec("bias_cisd_confirmed", "Lower timeframe confirms the bias swing", "continuation", "c1", STEP, "setup"),
    Spec("bias_candle_index_ok", "Forming bias candle is Candle 3 or Candle 4", "continuation", "c1", GATE, "bias"),
    Spec("bias_swing_intact", "Bias swing has not been broken", "continuation", "c1", GATE, "bias"),
    Spec(
        "cont_objective_open",
        "Previous bias candle's {hi} (the structural level) is not yet taken",
        "continuation",
        "c1",
        ADVISORY,
        "bias",
    ),
    Spec(
        "bias_c2_not_expanded",
        "Bias Candle 2 was a reversal candle, not an expansion",
        "continuation",
        "c1",
        ADVISORY,
        "bias",
    ),
    Spec(
        "cont_eq_respected", "Correct half of the previous bias candle is holding", "continuation", "c2", GATE, "setup"
    ),
    Spec(
        "cont_poi_tagged", "Price has reached a setup-timeframe point of interest", "continuation", "c2", STEP, "setup"
    ),
    Spec(
        "cont_opened_against_bias_first",
        "Bias candle moved against the bias first",
        "continuation",
        "c2",
        ADVISORY,
        "bias",
    ),
    Spec(
        "cont_setup_closure",
        "Setup timeframe printed a Candle 2 or Candle 3 closure at the POI",
        "continuation",
        "c3",
        STEP,
        "setup",
    ),
    Spec(
        "cont_setup_closure_body_aligned",
        "Closing candle's body agrees with the direction",
        "continuation",
        "c3",
        QUALITY,
        "setup",
    ),
    Spec(
        "cont_entry_cisd_confirmed", "Entry timeframe confirms the setup swing", "continuation", "c3", STEP, "entry"
    ),
    Spec(
        "cont_entry_cisd_swift", "That confirmation was a quick, V-shaped turn", "continuation", "c3", ADVISORY, "entry"
    ),
    Spec(
        "cont_entry_window_open",
        "Still inside setup Candle 3 (or allowed Candle 4)",
        "continuation",
        "c4",
        QUALITY,
        "setup",
    ),
    Spec("cont_entry_trigger", "Entry trigger has formed", "continuation", "c4", STEP, "entry"),
    Spec("cont_protected_swing_intact", "Stop swing has not been taken", "continuation", "c4", QUALITY, "entry"),
    Spec(
        "cont_trigger_clear_of_liquidity",
        "Trigger did not form while running short-term {hi}s",
        "continuation",
        "c4",
        QUALITY,
        "entry",
    ),
    Spec("cont_trigger_v_shape", "Trigger closed through in a quick V", "continuation", "c4", QUALITY, "entry"),
    Spec(
        "cont_not_inside_consolidation",
        "Trigger is not an internal move inside a consolidation",
        "continuation",
        "c4",
        QUALITY,
        "entry",
    ),
    Spec(
        "cont_objective_open_at_trigger",
        "Higher-timeframe target (previous bias candle's {hi}) was still open at the trigger",
        "continuation",
        "c4",
        QUALITY,
        "bias",
    ),
    Spec(
        "cont_entry_early_in_candle",
        "Trigger closed early enough in its setup candle",
        "continuation",
        "c4",
        QUALITY,
        "setup",
    ),
    Spec(
        "cont_newer_protected_low",
        "Newer protected {lo} since the entry (stop can trail)",
        "continuation",
        "c4",
        ADVISORY,
        "entry",
    ),
    Spec(
        "cont_reward_at_least_2r",
        "Structural level (previous bias candle's {hi}) is at least 2R away",
        "continuation",
        "c4",
        ADVISORY,
        "entry",
    ),
)

REVERSAL: tuple[Spec, ...] = (
    Spec(
        "rev_key_level_reached",
        "Forming bias candle has expanded to, or near, a key level",
        "reversal",
        "c1",
        STEP,
        "bias",
    ),
    Spec(
        "rev_expansion_into_level",
        "The move into the level was a directional run, not a drift",
        "reversal",
        "c1",
        QUALITY,
        "setup",
    ),
    Spec("rev_opposing_run_small", "The wick so far is small", "reversal", "c1", QUALITY, "bias"),
    Spec("rev_formed_early", "The wick formed early in the bias candle", "reversal", "c1", QUALITY, "bias"),
    Spec("rev_reclaim", "Setup timeframe has closed back {above} the key level", "reversal", "c2", STEP, "setup"),
    Spec(
        "rev_cisd_confirmed",
        "Change in state of delivery at the level: a close through the run of {down_close} candles",
        "reversal",
        "c3",
        STEP,
        "setup",
    ),
    Spec("rev_cisd_swift", "The turn was quick", "reversal", "c3", QUALITY, "setup"),
    Spec("rev_entry_trigger", "Entry trigger has formed", "reversal", "c4", STEP, "entry"),
    Spec("rev_wick_intact", "The reversal {lo} has not been taken again", "reversal", "c4", QUALITY, "bias"),
    Spec(
        "rev_reward_at_least_2r",
        "Structural level (previous bias candle's equilibrium) is at least 2R away",
        "reversal",
        "c4",
        ADVISORY,
        "entry",
    ),
)


class Checklist:
    """Collects the results of one group of criteria, in specification order."""

    def __init__(
        self,
        specs: Sequence[Spec],
        stack: TimeframeStack,
        side: Side | None = None,
        roles: dict[str, str] | None = None,
    ) -> None:
        self.specs = tuple(specs)
        self.stack = stack
        self.side = side
        self._roles = roles or {}
        self._by_key = {spec.key: spec for spec in self.specs}
        self._results: dict[str, CriterionResult] = {}

    def role(self, key: str) -> str:
        return self._roles.get(key, self._by_key[key].role)

    def set(self, key: str, passed: bool | None, detail: str, timeframe: str | None = None) -> None:
        spec = self._by_key[key]
        if self.side is not None:
            side = self.side
            words = {"lo": side.lo, "hi": side.hi, "above": side.above, "down_close": side.down_close}
        else:
            words = {"lo": "high or low", "hi": "high or low", "above": "beyond", "down_close": "opposite-close"}
        frame = timeframe if timeframe is not None else (getattr(self.stack, spec.tf) if spec.tf else None)
        self._results[key] = CriterionResult(
            key=key,
            label=spec.label.format(**words),
            passed=None if passed is None else bool(passed),
            detail=detail,
            timeframe=frame,
            group=f"{spec.path} {spec.stage}".strip(),
            role=self.role(key),
        )

    def fill(self, reason: str) -> None:
        """Mark every criterion not set yet as not evaluated."""
        for spec in self.specs:
            if spec.key not in self._results:
                self.set(spec.key, None, f"Not evaluated: {reason}")

    def passed(self, key: str) -> bool | None:
        result = self._results.get(key)
        return result.passed if result is not None else None

    def has(self, key: str) -> bool:
        return key in self._results

    def results(self) -> list[CriterionResult]:
        missing = [spec.key for spec in self.specs if spec.key not in self._results]
        if missing:
            raise RuntimeError(f"criteria not evaluated: {missing}")
        return [self._results[spec.key] for spec in self.specs]

    def keys(self, role: str) -> list[str]:
        return [spec.key for spec in self.specs if self.role(spec.key) == role]

    def gates_pass(self) -> bool:
        return all(self.passed(key) is True for key in self.keys(GATE))

    def gate_unknown(self) -> list[str]:
        return [key for key in self.keys(GATE) if self.passed(key) is None]

    def stage(self) -> str:
        """Highest stage whose step criteria, and those of every earlier stage, all passed."""
        reached = "none"
        for stage in STAGES:
            steps = [spec.key for spec in self.specs if spec.stage == stage and self.role(spec.key) == STEP]
            if any(self.passed(key) is not True for key in steps):
                break
            reached = stage
        return reached

    def failing_quality(self) -> list[str]:
        return [key for key in self.keys(QUALITY) if self.passed(key) is not True]
