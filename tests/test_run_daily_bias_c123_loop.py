from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import run_daily_bias_c123_loop as rdbcl


class RunDailyBiasC123LoopTests(unittest.TestCase):
    def test_build_loop_steps_matches_narrow_lane(self) -> None:
        steps = rdbcl.build_loop_steps("python")

        self.assertEqual(
            [step["id"] for step in steps],
            [
                "validate_ttfm_video_corpus",
                "build_ttfm_google_embeddings",
                "refresh_daily_bias_c123_rulepack",
                "build_daily_bias_c123_spec",
                "generate_daily_bias_c123_pine",
            ],
        )

    def test_build_loop_summary_surfaces_rulepack_and_pine_status(self) -> None:
        summary = rdbcl.build_loop_summary(
            step_results=[{"id": "demo", "result": {"ok": True}}],
            corpus_manifest={"video_count": 6},
            embedding_manifest={"item_count": 32, "model": "models/gemini-embedding-001"},
            rulepack={"trade_model": {"slug": "daily_bias_c123_map"}, "query_groups": ["daily_bias", "htf_sequence"]},
            spec={"trade_model": {"slug": "daily_bias_c123_map"}},
            pine_manifest={
                "summary": {"generated_script_count": 1, "generated_candidate_contract_count": 1},
                "generated_scripts": [{"spec_key": "daily_bias_c123_map", "output_path": "results/pine_scripts/daily_bias_c123_map.pine"}],
                "candidate_event_contracts": [{"spec_key": "daily_bias_c123_map", "output_path": "results/pine_candidate_event_contracts/daily_bias_c123_map.candidate_event_contract.json"}],
            },
        )

        self.assertEqual(summary["step_count"], 1)
        self.assertEqual(summary["corpus"]["video_count"], 6)
        self.assertEqual(summary["embeddings"]["item_count"], 32)
        self.assertEqual(summary["rulepack"]["slug"], "daily_bias_c123_map")
        self.assertEqual(summary["pine"]["generated_script_count"], 1)
        self.assertEqual(summary["pine"]["candidate_contract_count"], 1)


if __name__ == "__main__":
    unittest.main()
