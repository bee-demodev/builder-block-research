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

import apply_ttfm_feedback as atf


class ApplyFeedbackQueueTests(unittest.TestCase):
    def test_feedback_updates_allowed_targets_and_blocks_rulebooks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            findings_path = root / "findings.md"
            findings_path.write_text("# Findings\n", encoding="utf-8")

            open_questions_path = root / "topics" / "continuation" / "open_questions.md"
            open_questions_path.parent.mkdir(parents=True, exist_ok=True)
            open_questions_path.write_text(
                "# Continuation Open Questions\n",
                encoding="utf-8",
            )

            draft_spec_path = root / "results" / "indicator_specs" / "demo.json"
            draft_spec_path.parent.mkdir(parents=True, exist_ok=True)
            draft_spec_path.write_text(
                json.dumps({"open_implementation_questions": []}, indent=2),
                encoding="utf-8",
            )

            rulebook_path = root / "topics" / "continuation" / "rulebook.json"
            rulebook_path.write_text(json.dumps({"rules": []}), encoding="utf-8")

            queue = {
                "items": [
                    {
                        "id": "finding-1",
                        "target_type": "finding",
                        "target_path": "findings.md",
                        "title": "POI boundary ambiguity",
                        "body": "Pine could not reproduce the discretionary POI boundary.",
                    },
                    {
                        "id": "open-question-1",
                        "target_type": "open_question",
                        "target_path": "topics/continuation/open_questions.md",
                        "question": "How should overlapping POI boundaries be ranked for Pine?",
                    },
                    {
                        "id": "draft-spec-1",
                        "target_type": "draft_spec",
                        "target_path": "results/indicator_specs/demo.json",
                        "question": "What deterministic boundary proxy should the first Pine draft use?",
                        "affected_component": "point_of_interest",
                        "topic_refs": ["continuation"],
                    },
                    {
                        "id": "blocked-1",
                        "target_type": "rulebook",
                        "target_path": "topics/continuation/rulebook.json",
                        "body": "This should not be applied.",
                    },
                ]
            }

            result = atf.apply_feedback_queue(queue, root)

            self.assertEqual(result["applied_count"], 3)
            self.assertEqual(result["blocked_count"], 1)
            self.assertIn("POI boundary ambiguity", findings_path.read_text(encoding="utf-8"))
            self.assertIn(
                "How should overlapping POI boundaries be ranked for Pine?",
                open_questions_path.read_text(encoding="utf-8"),
            )

            draft_spec = json.loads(draft_spec_path.read_text(encoding="utf-8"))
            self.assertEqual(len(draft_spec["open_implementation_questions"]), 1)
            self.assertEqual(
                draft_spec["open_implementation_questions"][0]["affected_component"],
                "point_of_interest",
            )


if __name__ == "__main__":
    unittest.main()
