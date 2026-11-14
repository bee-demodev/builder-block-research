"""Typed view of ``config.json``: every tunable of the TTrades checklist.

The JSON file holds one entry per parameter with ``value``, ``description``, the
rules.md section it comes from and the open question (rules.md section 12) it answers.
Answering a question is an edit to ``value``; nothing here needs to change.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, Mapping

from companion import paths as _paths

CONFIG_PATH = _paths.resource("styles", "ttrades", "config.json")

_ENTRY_MODES = ("either", "conservative", "aggressive")
_KEY_LEVEL_KINDS = ("previous_candle", "swing", "fvg")


def clock_minutes(text: str) -> int:
    """``"08:30"`` -> minutes after midnight."""
    try:
        hours, minutes = text.split(":")
        value = int(hours) * 60 + int(minutes)
    except (AttributeError, ValueError):
        raise ValueError(f"Expected a clock time such as '08:30', got {text!r}") from None
    if not 0 <= value <= 24 * 60:
        raise ValueError(f"Clock time out of range: {text!r}")
    return value


@dataclass(frozen=True)
class TTradesConfig:
    target_rr: float
    target_mode: str
    min_rr: float
    reward_check_role: str
    cisd_max_bars: int
    wait_for_clean_continuation: bool
    objective_at_trigger_role: str
    entry_latest_candle_frac: float
    entry_mode_continuation: str
    entry_mode_reversal: str
    entry_either_pick: str
    kill_zones: tuple[tuple[str, str], ...]
    session_filter_role: str
    kill_zone_applies_below_minutes: int
    reversal_entry_tf_confirm_bias: tuple[str, ...]
    reversal_entry_tf_confirm_window: tuple[str, str]
    sweep_reclaim_max_bars: Mapping[str, int]
    avg_range_bars: int
    wick_yardstick: str
    wick_small_frac: float
    wick_large_frac: float
    wick_body_small_frac: float
    wick_body_large_frac: float
    wick_time_frac_max: float
    daily_wick_deadline: str
    respect_level_mode: str
    closed_wick_large_frac: float
    eq_tolerance_frac: float
    objective_open_role: str
    candle3_body_edge: str
    doji_in_series: bool
    setup_body_alignment_required: bool
    fvg_min_size: float
    bias_poi_lookback_bars: Mapping[str, int]
    reversal_key_levels: tuple[str, ...]
    reversal_level_tolerance_frac: float
    reversal_expansion_test: str
    reversal_expansion_min_bars: int
    reversal_expansion_min_travel_frac: float
    protected_swing_break_on: str
    body_stop_allowed: bool
    body_stop_min_body_frac: float
    stop_buffer: float
    entry_window_extra_candles: int
    block_unstated_stacks: bool
    setup_cover_bias_bars: int
    entry_cover_bias_bars: int
    max_frame_bars: int
    stated_stacks: tuple[tuple[str, str, str], ...]
    stated_pairings: tuple[tuple[str, str], ...]
    adr_days: int
    min_stop_adr_frac: float
    stop_size_role: str
    actionable_entry_bars: int
    actionable_max_r: float

    def __post_init__(self) -> None:
        for name in ("entry_mode_continuation", "entry_mode_reversal"):
            if getattr(self, name) not in _ENTRY_MODES:
                raise ValueError(f"{name} must be one of {_ENTRY_MODES}")
        choices = {
            "entry_either_pick": ("first", "latest"),
            "target_mode": ("r_multiple", "structural"),
            "reward_check_role": ("advisory", "quality"),
            "session_filter_role": ("advisory", "quality"),
            "objective_open_role": ("advisory", "gate"),
            "objective_at_trigger_role": ("quality", "advisory"),
            "wick_yardstick": ("avg_range", "body"),
            "reversal_expansion_test": ("directional_run", "off"),
            "stop_size_role": ("advisory", "quality"),
        }
        for name, allowed in choices.items():
            if getattr(self, name) not in allowed:
                raise ValueError(f"{name} must be one of {allowed}")
        unknown = [kind for kind in self.reversal_key_levels if kind not in _KEY_LEVEL_KINDS]
        if unknown or not self.reversal_key_levels:
            raise ValueError(f"reversal_key_levels must be a non-empty selection of {_KEY_LEVEL_KINDS}")
        if self.respect_level_mode not in ("auto", "eq", "wick_mid"):
            raise ValueError("respect_level_mode must be 'auto', 'eq' or 'wick_mid'")
        if self.candle3_body_edge not in ("far", "open"):
            raise ValueError("candle3_body_edge must be 'far' or 'open'")
        if self.protected_swing_break_on not in ("wick", "close"):
            raise ValueError("protected_swing_break_on must be 'wick' or 'close'")
        if "default" not in self.bias_poi_lookback_bars:
            raise ValueError("bias_poi_lookback_bars needs a 'default' entry")
        for start, end in (*self.kill_zones, self.reversal_entry_tf_confirm_window):
            if clock_minutes(start) > clock_minutes(end):
                raise ValueError(f"Window {start}-{end} ends before it starts")
        clock_minutes(self.daily_wick_deadline)
        for name in ("min_rr", "target_rr", "cisd_max_bars", "avg_range_bars", "adr_days"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        for name in (
            "reversal_level_tolerance_frac", "reversal_expansion_min_bars", "reversal_expansion_min_travel_frac",
            "min_stop_adr_frac", "actionable_max_r", "actionable_entry_bars",
        ):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must not be negative")
        if not 0 < self.entry_latest_candle_frac <= 1:
            raise ValueError("entry_latest_candle_frac must be in (0, 1]")
        if not 0 < self.wick_body_small_frac <= self.wick_body_large_frac:
            raise ValueError("wick_body_small_frac must be positive and at most wick_body_large_frac")

    def bias_lookback(self, bias_timeframe: str) -> int:
        """Bars back a bias-timeframe point of interest may sit (rules.md 3.1 / 11)."""
        table = self.bias_poi_lookback_bars
        return int(table.get(bias_timeframe, table["default"]))

    def bias_bars_needed(self, bias_timeframe: str) -> int:
        """Closed bias bars ``data_sufficient`` asks for (rules.md section 6)."""
        return max(self.avg_range_bars, self.bias_lookback(bias_timeframe)) + 3


def _freeze(value: Any) -> Any:
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def load_config(path: Path | None = None, overrides: Mapping[str, Any] | None = None) -> TTradesConfig:
    """Read the config file into a ``TTradesConfig``.

    ``overrides`` replaces individual values (used by tests); keys must be parameters.
    """
    config_path = Path(path) if path is not None else CONFIG_PATH
    with config_path.open(encoding="utf-8") as handle:
        document = json.load(handle)
    parameters = document.get("parameters") if isinstance(document, dict) else None
    if not isinstance(parameters, dict):
        raise ValueError(f"{config_path}: expected an object with a 'parameters' object")
    names = [item.name for item in fields(TTradesConfig)]
    missing = [name for name in names if name not in parameters]
    unknown = [name for name in parameters if name not in names]
    if missing or unknown:
        raise ValueError(f"{config_path}: missing parameters {missing}, unknown parameters {unknown}")
    values: dict[str, Any] = {}
    for name in names:
        entry = parameters[name]
        if not isinstance(entry, dict) or "value" not in entry:
            raise ValueError(f"{config_path}: parameter {name!r} needs a 'value'")
        values[name] = entry["value"]
    for name, value in (overrides or {}).items():
        if name not in values:
            raise ValueError(f"Unknown parameter {name!r}")
        values[name] = value
    return TTradesConfig(**{name: _freeze(value) for name, value in values.items()})


def describe_config(path: Path | None = None) -> list[dict[str, Any]]:
    """The parameters with their descriptions, in file order (for a settings screen)."""
    config_path = Path(path) if path is not None else CONFIG_PATH
    with config_path.open(encoding="utf-8") as handle:
        parameters = json.load(handle)["parameters"]
    return [{"name": name, **entry} for name, entry in parameters.items()]
