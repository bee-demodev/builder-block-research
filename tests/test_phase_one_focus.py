from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import phase_one_focus as pof


class PhaseOneFocusTests(unittest.TestCase):
    def test_filter_extra_training_labels_excludes_phase_one_execution_spec(self) -> None:
        labels = [
            "daily_bias_c123_map",
            "phases_of_price_framework",
            "daily_bias_framework",
            "daily_bias_c123_map",
        ]

        filtered = pof.filter_extra_training_labels(labels)

        self.assertEqual(
            filtered,
            ["daily_bias_framework", "phases_of_price_framework"],
        )

    def test_split_training_labels_ignores_phase_one_execution_spec(self) -> None:
        active, deferred = pof.split_training_labels(
            [
                "daily_bias_c123_map",
                "continuation_entry_model",
                "phases_of_price_framework",
            ]
        )

        self.assertEqual(active, ["continuation_entry_model"])
        self.assertEqual(deferred, ["phases_of_price_framework"])


if __name__ == "__main__":
    unittest.main()
