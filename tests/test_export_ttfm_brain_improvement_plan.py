from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import export_ttfm_brain_improvement_plan as etbip


class BrainImprovementPlanTests(unittest.TestCase):
    def test_selects_review_top_disagreements_when_queue_has_disagreements(self) -> None:
        plan = etbip.build_brain_improvement_plan(
            brain_loop_report={
                "framework_slug": "ttfm",
                "profile_slug": "ttrades_curriculum",
                "brain_type": "setup_scorer",
                "status": "ok",
                "pine_status": "not_ready",
                "multimodal_model": {"validation_micro_precision": 0.64},
            },
            review_queue={
                "summary": {
                    "model_disagreement_count": 4,
                    "ready_to_promote_count": 1,
                    "mean_disagreement_count": 1.8,
                }
            },
            review_packets={"summary": {"packet_count": 3}, "packets": [{"example_id": "a"}]},
        )

        self.assertEqual(plan["next_action"], "review_top_disagreements")
        self.assertEqual(plan["priority_actions"][0]["action"], "review_top_disagreements")

    def test_selects_brain_ready_for_pine_when_gate_is_green(self) -> None:
        plan = etbip.build_brain_improvement_plan(
            brain_loop_report={
                "status": "ok",
                "pine_status": "ready_for_translation",
            },
            review_queue={"summary": {}},
            review_packets={"summary": {}, "packets": []},
        )

        self.assertEqual(plan["next_action"], "brain_ready_for_pine")
        self.assertEqual(plan["priority_actions"][0]["action"], "brain_ready_for_pine")

    def test_selects_report_first_for_degraded_runs(self) -> None:
        plan = etbip.build_brain_improvement_plan(
            brain_loop_report={
                "status": "degraded",
                "pine_status": "not_ready",
                "failed_optional_stages": ["review_packets"],
                "multimodal_model": {"validation_micro_precision": 0.58},
            },
            review_queue={"summary": {"model_disagreement_count": 0}},
            review_packets={"summary": {"packet_count": 0}, "packets": []},
        )

        self.assertEqual(plan["next_action"], "report_first")
        self.assertEqual(plan["priority_actions"][0]["action"], "stabilize_degraded_stage")


if __name__ == "__main__":
    unittest.main()
