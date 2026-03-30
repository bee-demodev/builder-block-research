from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_STATE_SPEC_PATH = Path("data") / "fractal_state_machine.json"


@dataclass(frozen=True)
class FractalStateMachine:
    version: str
    path_families: tuple[str, ...]
    stages: tuple[str, ...]
    enums: dict[str, tuple[str, ...]]
    poi_mappings: dict[str, dict[str, str]]
    path_specs: dict[str, dict[str, Any]]
    entry_rules: dict[str, Any]
    raw: dict[str, Any]

    def supports_path_family(self, value: str) -> bool:
        return value in self.path_families

    def supports_stage(self, value: str) -> bool:
        return value in self.stages

    def validate_enum(self, enum_name: str, value: str) -> None:
        allowed = self.enums.get(enum_name)
        if allowed is None:
            raise ValueError(f"Unknown enum '{enum_name}' in fractal state machine.")
        if value not in allowed:
            raise ValueError(
                f"Invalid value '{value}' for enum '{enum_name}'. Allowed: {sorted(allowed)}"
            )


def _require_keys(payload: dict[str, Any], keys: tuple[str, ...]) -> None:
    missing = [key for key in keys if key not in payload]
    if missing:
        raise ValueError(f"Fractal state machine is missing required keys: {missing}")


def _normalize_enums(payload: dict[str, Any]) -> dict[str, tuple[str, ...]]:
    enums = payload.get("enums")
    if not isinstance(enums, dict):
        raise ValueError("Fractal state machine 'enums' must be an object.")
    normalized: dict[str, tuple[str, ...]] = {}
    for name, values in enums.items():
        if not isinstance(values, list) or not values or not all(
            isinstance(value, str) for value in values
        ):
            raise ValueError(
                f"Fractal state machine enum '{name}' must be a non-empty list of strings."
            )
        normalized[name] = tuple(values)
    return normalized


def load_state_machine(path: str | Path = DEFAULT_STATE_SPEC_PATH) -> FractalStateMachine:
    spec_path = Path(path)
    payload = json.loads(spec_path.read_text(encoding="utf-8"))
    _require_keys(
        payload,
        (
            "version",
            "enums",
            "poi_mappings",
            "path_specs",
            "entry_rules",
        ),
    )
    enums = _normalize_enums(payload)
    path_families = enums.get("path_family")
    stages = enums.get("fractal_stage")
    if path_families is None or stages is None:
        raise ValueError(
            "Fractal state machine must define 'path_family' and 'fractal_stage' enums."
        )

    path_specs = payload["path_specs"]
    if not isinstance(path_specs, dict):
        raise ValueError("Fractal state machine 'path_specs' must be an object.")
    for family in path_families:
        if family not in path_specs:
            raise ValueError(f"Missing path specification for '{family}'.")

    poi_mappings = payload["poi_mappings"]
    if not isinstance(poi_mappings, dict):
        raise ValueError("Fractal state machine 'poi_mappings' must be an object.")

    machine = FractalStateMachine(
        version=str(payload["version"]),
        path_families=path_families,
        stages=stages,
        enums=enums,
        poi_mappings=poi_mappings,
        path_specs=path_specs,
        entry_rules=payload["entry_rules"],
        raw=payload,
    )
    return machine
