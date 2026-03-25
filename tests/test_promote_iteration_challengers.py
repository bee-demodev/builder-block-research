from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import promote_iteration_challengers as pic


class PromoteIterationChallengersTests(unittest.TestCase):
    def make_benchmark_report(self, champion_dir: Path, challenger_dir: Path) -> dict:
        return {
            "summary": {
                "promotion_candidate_count": 1,
                "promotion_candidate_tasks": ["continuation_entry_model"],
            },
            "task_reports": [
                {
                    "task_name": "continuation_entry_model",
                    "status": "compared",
                    "winner": "challenger",
                    "recommendation": "promote_after_review",
                    "champion_model_path": str(champion_dir / "continuation_entry_model.pt"),
                    "challenger_model_path": str(challenger_dir / "continuation_entry_model.pt"),
                    "full_surface": {
                        "winner": "challenger",
                        "metric_delta": {"accuracy": 0.05, "f1": 0.06},
                    },
                    "reinforcement_only": {
                        "winner": "tie",
                        "metric_delta": {"accuracy": 0.0, "f1": 0.0},
                    },
                    "challenger_training_report": {
                        "task_name": "continuation_entry_model",
                        "model_path": str(challenger_dir / "continuation_entry_model.pt"),
                        "report_path": str(challenger_dir / "continuation_entry_model_report.json"),
                        "metrics": {"validation": {"accuracy": 1.0}},
                    },
                },
                {
                    "task_name": "trade_vs_no_trade",
                    "status": "compared",
                    "winner": "tie",
                    "recommendation": "collect_more_examples",
                    "champion_model_path": str(champion_dir / "trade_vs_no_trade.pt"),
                    "challenger_model_path": str(challenger_dir / "trade_vs_no_trade.pt"),
                    "full_surface": {
                        "winner": "tie",
                        "metric_delta": {"accuracy": 0.0, "f1": 0.0},
                    },
                    "reinforcement_only": {
                        "winner": "tie",
                        "metric_delta": {"accuracy": 0.0, "f1": 0.0},
                    },
                    "challenger_training_report": {
                        "task_name": "trade_vs_no_trade",
                        "model_path": str(challenger_dir / "trade_vs_no_trade.pt"),
                        "report_path": str(challenger_dir / "trade_vs_no_trade_report.json"),
                        "metrics": {"validation": {"accuracy": 0.8}},
                    },
                },
            ],
        }

    def test_apply_promotion_report_promotes_and_archives_champion(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            champion_dir = temp_path / "champion"
            challenger_dir = temp_path / "challenger"
            archive_dir = temp_path / "archive"
            history_path = temp_path / "history.jsonl"
            champion_dir.mkdir(parents=True, exist_ok=True)
            challenger_dir.mkdir(parents=True, exist_ok=True)

            (champion_dir / "continuation_entry_model.pt").write_text("old-model", encoding="utf-8")
            (champion_dir / "continuation_entry_model_report.json").write_text(
                json.dumps({"task_name": "continuation_entry_model", "model_path": "old-path"}),
                encoding="utf-8",
            )
            (challenger_dir / "continuation_entry_model.pt").write_text("new-model", encoding="utf-8")
            (challenger_dir / "continuation_entry_model_report.json").write_text(
                json.dumps({"task_name": "continuation_entry_model", "model_path": "new-path"}),
                encoding="utf-8",
            )

            report = pic.apply_promotion_report(
                iteration_challenger_report=self.make_benchmark_report(champion_dir, challenger_dir),
                champion_model_dir=champion_dir,
                archive_root=archive_dir,
                history_path=history_path,
            )

            self.assertEqual(report["summary"]["promoted_task_count"], 1)
            self.assertEqual(report["summary"]["skipped_task_count"], 1)
            self.assertEqual(
                (champion_dir / "continuation_entry_model.pt").read_text(encoding="utf-8"),
                "new-model",
            )
            archived_model = Path(report["promotions"][0]["archived_model_path"])
            self.assertEqual(archived_model.read_text(encoding="utf-8"), "old-model")
            champion_report_payload = json.loads(
                (champion_dir / "continuation_entry_model_report.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                champion_report_payload["promotion"]["source_model_path"],
                str(challenger_dir / "continuation_entry_model.pt"),
            )
            history_lines = history_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(history_lines), 1)

    def test_build_promotion_candidates_skips_non_promotable_tasks(self) -> None:
        candidates = pic.build_promotion_candidates(
            {
                "task_reports": [
                    {
                        "task_name": "trade_vs_no_trade",
                        "status": "compared",
                        "winner": "tie",
                        "recommendation": "collect_more_examples",
                        "full_surface": {"winner": "tie", "metric_delta": {"accuracy": 0.0, "f1": 0.0}},
                        "reinforcement_only": {"winner": "tie", "metric_delta": {"accuracy": 0.0, "f1": 0.0}},
                    }
                ]
            }
        )

        self.assertEqual(candidates, [])


if __name__ == "__main__":
    unittest.main()
