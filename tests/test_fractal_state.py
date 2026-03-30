import json
from pathlib import Path

from fractal_state import DEFAULT_STATE_SPEC_PATH, load_state_machine


def test_load_state_machine_default_spec() -> None:
    machine = load_state_machine()

    assert machine.version == "1.0.0"
    assert machine.supports_path_family("continuation")
    assert machine.supports_path_family("reversal")
    assert machine.supports_stage("c4")
    assert machine.poi_mappings["bullish_reaction_zone"]["poi_type"] == "reaction_zone"


def test_state_spec_file_exists() -> None:
    assert Path(DEFAULT_STATE_SPEC_PATH).exists()


def test_bundle_benchmark_target_file_exists_and_has_targets() -> None:
    benchmark_path = Path("data") / "bundle_benchmark_targets.json"
    payload = json.loads(benchmark_path.read_text(encoding="utf-8"))

    assert benchmark_path.exists()
    assert payload["rules"]["real_data_only"] is True
    assert len(payload["targets"]) >= 18
