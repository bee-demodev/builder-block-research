from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import discover_ttfm_trade_review_videos as dtrv


def make_channel_payload() -> dict:
    return {
        "title": "TTrades - Videos",
        "entries": [
            {"id": "abc123", "title": "MARA Trade Review | H1 Market Maker Buy Model [MMXM]"},
            {"id": "def456", "title": "TTrades Top-Down Chart Lessons #2"},
            {"id": "ghi789", "title": "Easy Daily Bias - Mechanical Framework"},
        ],
    }


class DiscoverTtfmTradeReviewVideosTests(unittest.TestCase):
    def test_classify_review_categories_matches_reviewish_titles(self) -> None:
        self.assertEqual(dtrv.classify_review_categories("MARA Trade Review"), ["trade_review"])
        self.assertEqual(
            dtrv.classify_review_categories("TTrades Top-Down Chart Lessons #2"),
            ["chart_lesson"],
        )
        self.assertEqual(dtrv.classify_review_categories("Easy Daily Bias - Mechanical Framework"), [])

    def test_classify_educational_categories_matches_curriculum_titles(self) -> None:
        self.assertEqual(
            dtrv.classify_educational_categories("Easy Daily Bias - Mechanical Framework"),
            ["bias_framework"],
        )
        self.assertEqual(
            dtrv.classify_educational_categories("CISD and Equilibrium Entry Model"),
            ["execution_model", "trading_framework"],
        )
        self.assertEqual(
            dtrv.classify_educational_categories("TradingView Setup Walkthrough"),
            [],
        )

    def test_build_trade_review_manifest_selects_only_review_video_rows(self) -> None:
        inventory, manifest = dtrv.build_trade_review_manifest(
            make_channel_payload(),
            channel_url=dtrv.DEFAULT_CHANNEL_URL,
            include_categories={"trade_review", "chart_lesson"},
        )

        self.assertEqual(inventory["entry_count"], 3)
        self.assertEqual(inventory["trade_review_candidate_count"], 2)
        self.assertEqual(manifest["video_count"], 2)
        self.assertEqual(
            [video["video_id"] for video in manifest["videos"]],
            ["abc123", "def456"],
        )
        self.assertEqual(manifest["videos"][0]["corpus_partition"], "trade_review")
        self.assertIn("trade_review", manifest["videos"][0]["topics"])
        self.assertEqual(manifest["videos"][1]["review_categories"], ["chart_lesson"])

    def test_build_channel_corpus_manifests_includes_educational_titles(self) -> None:
        inventory, educational_manifest, trade_review_manifest = dtrv.build_channel_corpus_manifests(
            make_channel_payload(),
            channel_url=dtrv.DEFAULT_CHANNEL_URL,
            include_review_categories={"trade_review", "chart_lesson"},
            include_educational_categories={"bias_framework", "timeframe_alignment"},
        )

        self.assertEqual(inventory["educational_candidate_count"], 3)
        self.assertEqual(trade_review_manifest["video_count"], 2)
        self.assertEqual(educational_manifest["video_count"], 3)
        self.assertEqual(
            [video["video_id"] for video in educational_manifest["videos"]],
            ["abc123", "def456", "ghi789"],
        )
        self.assertEqual(educational_manifest["videos"][2]["corpus_partition"], "educational_youtube")
        self.assertEqual(educational_manifest["videos"][2]["educational_categories"], ["bias_framework"])
        self.assertIn("educational_channel", educational_manifest["videos"][2]["topics"])


if __name__ == "__main__":
    unittest.main()
