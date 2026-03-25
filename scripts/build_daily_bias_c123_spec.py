from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import refresh_daily_bias_c123_rulepack as rdcr
import ttfm_video_embeddings as tve


ROOT = Path(__file__).resolve().parent.parent
SPEC_PATH = ROOT / "results" / "indicator_specs" / "daily_bias_c123_map.json"


def build_indicator_spec(rulepack: dict) -> dict:
    artifact_path = SPEC_PATH
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "artifact_type": "indicator_spec",
        "artifact_path": tve.path_for_manifest(artifact_path),
        "trader_profile": {
            "display_name": "TTrades Curriculum",
        },
        "trade_model": {
            "slug": "daily_bias_c123_map",
            "name": "Daily Bias C1/C2/C3 Map",
        },
        "implementation_scope": {
            "target_language": "pine",
        },
        "implementation_summary": "Daily bias phase 1 map for D bias, active 1H C1/C2/C3 structure near the daily POI, and 5m continuation refinement inside hourly Candle 3.",
        "timeframe_contract": {
            "chart": "60",
            "bias": "D",
            "structure": "60",
            "execution": "5",
        },
        "source_priority": rulepack.get("source_priority", {}),
        "rulepack_ref": tve.path_for_manifest(rdcr.RULEPACK_PATH),
        "display_contract": {
            "active_sequence_only": True,
            "historical_backfill": False,
            "unsupported_timeframe_message": "Unsupported chart timeframe. Load this indicator on a 1H chart.",
        },
        "input_groups": [
            {
                "group": "Visibility",
                "inputs": [
                    {
                        "key": "showDailyBiasBanner",
                        "type": "bool",
                        "default": True,
                        "description": "Show the current daily bias banner.",
                    },
                    {
                        "key": "showDailyPoiZone",
                        "type": "bool",
                        "default": True,
                        "description": "Show the active daily POI zone on the hourly chart.",
                    },
                    {
                        "key": "showHourlySequence",
                        "type": "bool",
                        "default": True,
                        "description": "Show the active 1H C1/C2/C3 labels and entry guide when they form inside the daily POI, otherwise show one small waiting cue while the 5m refinement stays alert-driven only.",
                    },
                ],
            }
        ],
        "sequence_contract": {
            "daily_bias_rules": rulepack.get("daily_bias_rules", {}),
            "daily_poi_rules": rulepack.get("daily_poi_rules", {}),
            "hourly_sequence_rules": rulepack.get("hourly_sequence_rules", {}),
            "lower_timeframe_refinement_rules": rulepack.get("lower_timeframe_refinement_rules", {}),
            "gating_rules": rulepack.get("gating_rules", {}),
        },
        "acceptance_checks": [
            "The script only supports 1H charts and shows a clear message otherwise.",
            "Daily bias is shown without targets, ladders, dashboards, or lower-timeframe overlays.",
            "The daily POI zone is visible on the hourly chart.",
            "Hourly C1/C2/C3 labels only appear when the hourly sequence forms inside the daily POI.",
            "Entry guide appears at the open of hourly Candle 3 when the sequence activates.",
            "Five-minute continuation confirmation is derived only after the hourly sequence activates and is emitted through rule states or alerts rather than a second on-chart candle map.",
            "When no hourly sequence is active, a single waiting cue shows the next Candle 2 direction to watch for inside the daily POI.",
            "Only the current active hourly sequence is visible.",
        ],
    }


def write_indicator_spec(*, rulepack_path: Path = rdcr.RULEPACK_PATH, output_path: Path = SPEC_PATH) -> dict:
    rulepack = json.loads(rulepack_path.read_text(encoding="utf-8"))
    spec = build_indicator_spec(rulepack)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(spec, indent=2), encoding="utf-8")
    return {
        "ok": True,
        "slug": spec["trade_model"]["slug"],
        "spec_path": tve.path_for_manifest(output_path),
        "rulepack_path": tve.path_for_manifest(rulepack_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the narrow daily bias C1/C2/C3 indicator spec.")
    parser.add_argument("--rulepack-path", type=Path, default=rdcr.RULEPACK_PATH)
    parser.add_argument("--output-path", type=Path, default=SPEC_PATH)
    args = parser.parse_args()

    print(
        json.dumps(
            write_indicator_spec(rulepack_path=args.rulepack_path, output_path=args.output_path),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
