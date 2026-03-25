from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import export_reinforced_training_surface as erts


def make_base_example(*, case_ref: str, trade_model: str, relation_type: str, outcome: str = "trade") -> dict:
    return {
        "example_id": f"{case_ref}::{trade_model}::{relation_type}",
        "profile_slug": "ttrades_curriculum",
        "profile_name": "TTrades Curriculum",
        "profile_type": "teacher_style",
        "topic": "continuation",
        "case_ref": case_ref,
        "source_url": "https://example.com",
        "notes": "base example",
        "trade_model": trade_model,
        "relation_type": relation_type,
        "confidence": 1.0,
        "indicator_ready_in_profile": True,
        "features": {
            "topic": "continuation",
            "setup_variant": "base",
            "source_kind": "article",
            "timeframe_scope": ["fractal"],
            "session_scope": [],
            "profile_frameworks": ["canonical_price_action"],
            "profile_topics": ["continuation"],
            "profile_trade_model_roles": [f"{trade_model}:{relation_type}"],
            "annotation_key_paths": [],
            "annotation_value_tokens": ["equilibrium"],
            "chart_context_tokens": ["article", "fractal"],
        },
        "targets": {
            "trade_model": trade_model,
            "relation_type": relation_type,
            "outcome_decision": outcome,
            "is_no_trade": outcome == "no_trade",
            "has_outcome_label": True,
            "outcome_reason": "demo_reason",
        },
        "training_text": f"profile ttrades_curriculum | trade model {trade_model} | relation {relation_type}",
    }


def make_case_packet_report() -> dict:
    return {
        "summary": {"case_count": 2},
        "case_packets": [
            {
                "profile_slug": "ttrades_curriculum",
                "profile_name": "TTrades Curriculum",
                "case_ref": "bias_case",
                "topic": "bias",
                "source_url": "https://example.com/bias",
                "notes": "bias packet",
                "timeframe_stack": {"labels": ["higher", "lower"]},
                "trade_models": ["daily_bias_framework"],
                "relation_types": ["bias_framework"],
                "checkpoints": [
                    {"checkpoint": "context", "expected_component_labels": ["equilibrium"]},
                    {"checkpoint": "confirmation", "expected_component_labels": ["equilibrium"]},
                ],
                "outcome": {"decision": "trade", "reason": "bias_trade"},
            }
        ],
    }


class ExportReinforcedTrainingSurfaceTests(unittest.TestCase):
    def test_build_reinforced_training_surface_merges_episode_examples(self) -> None:
        report = erts.build_reinforced_training_surface(
            base_examples=[
                make_base_example(
                    case_ref="base_continuation",
                    trade_model="continuation_entry_model",
                    relation_type="execution_model",
                )
            ],
            case_packet_report=make_case_packet_report(),
            iteration_grading_report={
                "episodes": [
                    {
                        "episode_id": "episode_bias",
                        "case_ref": "bias_case",
                        "status": "graded",
                        "predicted_trade_model": "continuation_entry_model",
                        "predicted_relation_type": "execution_model",
                        "understanding_score": 0.32,
                        "checkpoint_results": [
                            {
                                "checkpoint": "context",
                                "expected_component_labels": ["equilibrium"],
                                "predicted_component_labels": ["equilibrium"],
                            },
                            {
                                "checkpoint": "confirmation",
                                "expected_component_labels": ["equilibrium"],
                                "predicted_component_labels": [],
                            },
                        ],
                    }
                ]
            },
        )

        self.assertEqual(report["summary"]["base_example_count"], 1)
        self.assertEqual(report["summary"]["reinforcement_example_count"], 1)
        self.assertEqual(report["summary"]["merged_example_count"], 2)
        self.assertEqual(report["summary"]["graded_episode_count"], 1)
        self.assertEqual(report["summary"]["trade_model_counts"]["daily_bias_framework"], 1)
        reinforcement = next(
            example
            for example in report["examples"]
            if example["example_id"].startswith("iteration::episode_bias")
        )
        self.assertEqual(reinforcement["features"]["source_kind"], "graded_iteration")
        self.assertEqual(reinforcement["targets"]["trade_model"], "daily_bias_framework")
        self.assertIn("attempt trade model continuation entry model", reinforcement["training_text"])

    def test_build_reinforced_training_surface_skips_unknown_and_ungraded_episodes(self) -> None:
        report = erts.build_reinforced_training_surface(
            base_examples=[],
            case_packet_report=make_case_packet_report(),
            iteration_grading_report={
                "episodes": [
                    {"episode_id": "unknown", "case_ref": "missing_case", "status": "unknown_case_ref"},
                    {"episode_id": "pending", "case_ref": "bias_case", "status": "pending"},
                ]
            },
        )

        self.assertEqual(report["summary"]["reinforcement_example_count"], 0)
        self.assertEqual(report["summary"]["skipped_episode_count"], 2)
        self.assertEqual(report["examples"], [])

    def test_build_reinforced_training_surface_adds_passed_tradingview_validation_examples(self) -> None:
        report = erts.build_reinforced_training_surface(
            base_examples=[
                make_base_example(
                    case_ref="base_bias",
                    trade_model="daily_bias_framework",
                    relation_type="bias_framework",
                )
            ],
            case_packet_report={"summary": {}, "case_packets": []},
            iteration_grading_report={"episodes": []},
            tradingview_validation_log={
                "validations": [
                    {
                        "recorded_at": "2026-03-23T20:00:00+00:00",
                        "spec_key": "daily_bias_c123_map",
                        "validation_status": "compiled_on_chart",
                        "validation_method": "playwriter",
                        "qa_status": "pass",
                        "semantic_score": 0.9,
                        "visual_score": 0.88,
                        "scope_score": 0.9,
                        "notes": "Validated fallback state on live chart.",
                        "qa_notes": "Daily bias banner and POI were visible with the wait cue.",
                        "chart_url": "https://www.tradingview.com/chart/demo/",
                        "chart_symbol": "CME_MINI:NQM2026",
                    },
                    {
                        "recorded_at": "2026-03-23T20:05:00+00:00",
                        "spec_key": "daily_bias_framework",
                        "validation_status": "added_to_chart",
                        "validation_method": "playwriter",
                        "qa_status": "fail",
                        "semantic_score": 0.2,
                        "visual_score": 0.3,
                        "scope_score": 0.4,
                    },
                ]
            },
        )

        self.assertEqual(report["summary"]["iteration_reinforcement_example_count"], 0)
        self.assertEqual(report["summary"]["tradingview_validation_example_count"], 1)
        self.assertEqual(report["summary"]["reinforcement_example_count"], 1)
        self.assertEqual(report["summary"]["merged_example_count"], 2)

        validation_example = next(
            example
            for example in report["examples"]
            if example["example_id"].startswith("tradingview_validation::")
        )
        self.assertEqual(validation_example["trade_model"], "daily_bias_c123_map")
        self.assertEqual(validation_example["relation_type"], "execution_model")
        self.assertEqual(validation_example["features"]["source_kind"], "tradingview_validation")
        self.assertFalse(validation_example["targets"]["has_outcome_label"])
        self.assertIn("validated tradingview pine overlay", validation_example["training_text"])

    def test_build_reinforced_training_surface_adds_youtube_transcript_examples(self) -> None:
        report = erts.build_reinforced_training_surface(
            base_examples=[
                make_base_example(
                    case_ref="base_bias",
                    trade_model="daily_bias_framework",
                    relation_type="bias_framework",
                )
            ],
            case_packet_report={"summary": {}, "case_packets": []},
            iteration_grading_report={"episodes": []},
            tradingview_validation_log={"validations": []},
            youtube_chunk_rows=[
                {
                    "video_slug": "easy_daily_bias_mechanical_framework",
                    "video_id": "-KKuZb5Z5aU",
                    "title": "Easy Daily Bias - Mechanical Framework",
                    "topics": ["daily_bias", "continuation", "reversal"],
                    "start": 10.0,
                    "end": 70.0,
                    "text": (
                        "When looking for a continuation, I want to see price open, trade lower "
                        "first, respect the EQ of the previous day's range, and then trade higher."
                    ),
                },
                {
                    "video_slug": "unknown_curriculum_video",
                    "video_id": "demo123",
                    "title": "Unknown Curriculum Video",
                    "topics": ["unknown_topic"],
                    "start": 20.0,
                    "end": 80.0,
                    "text": "This row is intentionally left unmapped and should be skipped.",
                },
            ],
            youtube_embedding_index={
                "items": [
                    {
                        "chunk_id": "easy_daily_bias_mechanical_framework:0000",
                        "video_slug": "easy_daily_bias_mechanical_framework",
                        "video_id": "-KKuZb5Z5aU",
                        "title": "Easy Daily Bias - Mechanical Framework",
                        "vector": [1.0, 0.0],
                    },
                    {
                        "chunk_id": "daily_bias_neighbor:0001",
                        "video_slug": "fractal_model_fundamentals",
                        "video_id": "TNybDCtwBnc",
                        "title": "TTrades Playbook | Fractal Model Fundamentals (TTFM)",
                        "vector": [0.95, 0.05],
                    },
                ]
            },
        )

        self.assertEqual(report["summary"]["youtube_transcript_example_count"], 1)
        self.assertEqual(report["summary"]["merged_example_count"], 2)

        youtube_example = next(
            example
            for example in report["examples"]
            if example["example_id"].startswith("youtube::")
        )
        self.assertEqual(youtube_example["trade_model"], "daily_bias_framework")
        self.assertEqual(youtube_example["relation_type"], "bias_framework")
        self.assertEqual(youtube_example["features"]["source_kind"], "youtube_transcript")
        self.assertFalse(youtube_example["targets"]["has_outcome_label"])
        self.assertTrue(youtube_example["features"]["embedding_index_present"])
        self.assertEqual(
            youtube_example["source_group"],
            "youtube_video::easy_daily_bias_mechanical_framework",
        )
        self.assertEqual(
            youtube_example["features"]["semantic_neighbor_chunk_ids"],
            ["daily_bias_neighbor:0001"],
        )
        self.assertIn("youtube transcript curriculum chunk", youtube_example["training_text"])

    def test_build_reinforced_training_surface_maps_cisd_video_into_execution_surface(self) -> None:
        report = erts.build_reinforced_training_surface(
            base_examples=[],
            case_packet_report={"summary": {}, "case_packets": []},
            iteration_grading_report={"episodes": []},
            tradingview_validation_log={"validations": []},
            youtube_chunk_rows=[
                {
                    "video_slug": "cisd_validates_swing_points",
                    "video_id": "vn1RYjhJUnQ",
                    "title": "Validating Swing Points Using Lower Timeframe Confirmation (CISD)",
                    "topics": ["cisd", "candle_2", "candle_3", "continuation"],
                    "start": 10.0,
                    "end": 70.0,
                    "text": (
                        "When I have a candle 2 or candle 3 closure on the higher time frame, "
                        "I need the lower time frame change in the state of delivery before I "
                        "look for continuation."
                    ),
                }
            ],
            youtube_embedding_index={"items": []},
        )

        self.assertEqual(report["summary"]["youtube_transcript_example_count"], 1)
        youtube_example = report["youtube_transcript_examples"][0]
        self.assertEqual(youtube_example["trade_model"], "daily_bias_c123_map")
        self.assertEqual(youtube_example["relation_type"], "execution_model")
        self.assertEqual(youtube_example["topic"], "bias")
        self.assertEqual(
            youtube_example["source_group"],
            "youtube_video::cisd_validates_swing_points",
        )
        self.assertIn("cisd", youtube_example["training_text"])

    def test_build_reinforced_training_surface_labels_explicit_cisd_outcomes(self) -> None:
        report = erts.build_reinforced_training_surface(
            base_examples=[],
            case_packet_report={"summary": {}, "case_packets": []},
            iteration_grading_report={"episodes": []},
            tradingview_validation_log={"validations": []},
            youtube_chunk_rows=[
                {
                    "video_slug": "cisd_validates_swing_points",
                    "video_id": "vn1RYjhJUnQ",
                    "title": "Validating Swing Points Using Lower Timeframe Confirmation (CISD)",
                    "topics": ["cisd", "candle_2", "continuation"],
                    "start": 200.0,
                    "end": 260.0,
                    "text": (
                        "It is a valid continuation and we do get that continuation lower."
                    ),
                },
                {
                    "video_slug": "cisd_validates_swing_points",
                    "video_id": "vn1RYjhJUnQ",
                    "title": "Validating Swing Points Using Lower Timeframe Confirmation (CISD)",
                    "topics": ["cisd", "candle_2", "continuation"],
                    "start": 336.0,
                    "end": 406.0,
                    "text": (
                        "This is not a valid bearish setup and I saved myself from taking losses."
                    ),
                },
                {
                    "video_slug": "cisd_validates_swing_points",
                    "video_id": "vn1RYjhJUnQ",
                    "title": "Validating Swing Points Using Lower Timeframe Confirmation (CISD)",
                    "topics": ["cisd", "candle_3", "continuation"],
                    "start": 130.0,
                    "end": 201.0,
                    "text": (
                        "This meets both the requirements and is valid to be looking for a continuation "
                        "in candle 4, but the next scenario is not a valid candle 3 closure."
                    ),
                },
            ],
            youtube_embedding_index={"items": []},
        )

        by_case_ref = {example["case_ref"]: example for example in report["youtube_transcript_examples"]}
        self.assertEqual(
            by_case_ref["youtube::cisd_validates_swing_points:0000"]["targets"]["outcome_decision"],
            "trade",
        )
        self.assertTrue(
            by_case_ref["youtube::cisd_validates_swing_points:0000"]["targets"]["has_outcome_label"]
        )
        self.assertEqual(
            by_case_ref["youtube::cisd_validates_swing_points:0001"]["targets"]["outcome_decision"],
            "no_trade",
        )
        self.assertTrue(
            by_case_ref["youtube::cisd_validates_swing_points:0001"]["targets"]["is_no_trade"]
        )
        self.assertEqual(
            by_case_ref["youtube::cisd_validates_swing_points:0002"]["targets"]["outcome_decision"],
            "unknown",
        )
        self.assertFalse(
            by_case_ref["youtube::cisd_validates_swing_points:0002"]["targets"]["has_outcome_label"]
        )

    def test_split_youtube_transcript_document_breaks_mixed_cisd_chunk_on_example_markers(
        self,
    ) -> None:
        segments = erts.split_youtube_transcript_document(
            {
                "chunk_id": "cisd_validates_swing_points:0001",
                "video_slug": "cisd_validates_swing_points",
                "video_id": "vn1RYjhJUnQ",
                "title": "Validating Swing Points Using Lower Timeframe Confirmation (CISD)",
                "topics": ["cisd", "candle_2", "continuation"],
                "start": 71.92,
                "end": 136.08,
                "text": (
                    "continuation. Going to wait for that change in the state of delivery to occur "
                    "or I'm going to ignore the setup. Let's take a look at what this looks like in "
                    "my fractal model. So, here you can see we have a valid candle 2 closure. So you "
                    "can see we have a candle 2 closure as price sweeps out its previous candle and "
                    "closes back in. Now what do I look for on the lower time frame? I need to have "
                    "that change in the state of delivery. So I find the high. I find the series of "
                    "candles that made that high. Do we have a closure through that level? We do. So "
                    "this meets both of the requirements and it is valid to be looking for a "
                    "continuation lower. Now let's take a look at an example of an invalid case. Here "
                    "you can see we have a candle to closure. It sweeps out the previous, closes back "
                    "in. Do we have a change in this delivery? I find the high. I find the series of "
                    "candles that made that high. Did we close below that level? No. So, this is not "
                    "a valid fractal model and I would not be looking for a continuation yet. Now, "
                    "let's take a look at another invalid case. Here you can see we don't have a "
                    "candle to closure. So, even though we have a change in the state of delivery, "
                    "it does not mean"
                ),
            }
        )

        self.assertEqual(
            [segment["chunk_id"] for segment in segments],
            [
                "cisd_validates_swing_points:0001#segment_00",
                "cisd_validates_swing_points:0001#segment_01",
                "cisd_validates_swing_points:0001#segment_02",
            ],
        )
        self.assertTrue(segments[0]["text"].startswith("continuation. Going to wait"))
        self.assertTrue(
            segments[1]["text"].startswith(
                "Now let's take a look at an example of an invalid case."
            )
        )
        self.assertTrue(
            segments[2]["text"].startswith(
                "Now, let's take a look at another invalid case."
            )
        )

    def test_build_reinforced_training_surface_splits_mixed_cisd_chunk_into_labeled_windows(
        self,
    ) -> None:
        report = erts.build_reinforced_training_surface(
            base_examples=[],
            case_packet_report={"summary": {}, "case_packets": []},
            iteration_grading_report={"episodes": []},
            tradingview_validation_log={"validations": []},
            youtube_chunk_rows=[
                {
                    "video_slug": "cisd_validates_swing_points",
                    "video_id": "vn1RYjhJUnQ",
                    "title": "Validating Swing Points Using Lower Timeframe Confirmation (CISD)",
                    "topics": ["cisd", "candle_2", "continuation"],
                    "start": 71.92,
                    "end": 136.08,
                    "text": (
                        "continuation. Going to wait for that change in the state of delivery to occur "
                        "or I'm going to ignore the setup. Let's take a look at what this looks like in "
                        "my fractal model. So, here you can see we have a valid candle 2 closure. So you "
                        "can see we have a candle 2 closure as price sweeps out its previous candle and "
                        "closes back in. Now what do I look for on the lower time frame? I need to have "
                        "that change in the state of delivery. So I find the high. I find the series of "
                        "candles that made that high. Do we have a closure through that level? We do. So "
                        "this meets both of the requirements and it is valid to be looking for a "
                        "continuation lower. Now let's take a look at an example of an invalid case. Here "
                        "you can see we have a candle to closure. It sweeps out the previous, closes back "
                        "in. Do we have a change in this delivery? I find the high. I find the series of "
                        "candles that made that high. Did we close below that level? No. So, this is not "
                        "a valid fractal model and I would not be looking for a continuation yet. Now, "
                        "let's take a look at another invalid case. Here you can see we don't have a "
                        "candle to closure. So, even though we have a change in the state of delivery, "
                        "it does not mean"
                    ),
                }
            ],
            youtube_embedding_index={"items": []},
        )

        by_case_ref = {example["case_ref"]: example for example in report["youtube_transcript_examples"]}
        self.assertEqual(report["summary"]["youtube_transcript_example_count"], 4)
        self.assertEqual(
            by_case_ref["youtube::cisd_validates_swing_points:0000"]["targets"]["outcome_decision"],
            "unknown",
        )
        self.assertFalse(
            by_case_ref["youtube::cisd_validates_swing_points:0000"]["targets"][
                "outcome_segment_only"
            ]
        )
        self.assertEqual(
            by_case_ref["youtube::cisd_validates_swing_points:0000#segment_00"]["targets"][
                "outcome_decision"
            ],
            "trade",
        )
        self.assertTrue(
            by_case_ref["youtube::cisd_validates_swing_points:0000#segment_00"]["targets"][
                "outcome_segment_only"
            ]
        )
        self.assertEqual(
            by_case_ref["youtube::cisd_validates_swing_points:0000#segment_01"]["targets"][
                "outcome_decision"
            ],
            "no_trade",
        )
        self.assertEqual(
            by_case_ref["youtube::cisd_validates_swing_points:0000#segment_02"]["targets"][
                "outcome_decision"
            ],
            "no_trade",
        )

    def test_build_reinforced_training_surface_labels_explicit_false_positive_sources_as_no_trade(
        self,
    ) -> None:
        report = erts.build_reinforced_training_surface(
            base_examples=[],
            case_packet_report={"summary": {}, "case_packets": []},
            iteration_grading_report={"episodes": []},
            tradingview_validation_log={"validations": []},
            youtube_chunk_rows=[
                {
                    "video_slug": "fractal_model_fundamentals",
                    "video_id": "TNybDCtwBnc",
                    "title": "TTrades Playbook | Fractal Model Fundamentals (TTFM)",
                    "topics": ["fractal_model", "daily_bias"],
                    "start": 355.68,
                    "end": 433.28,
                    "text": (
                        "Our point of interest wasn't really there. It wasn't being respected. "
                        "We get stopped out."
                    ),
                },
                {
                    "video_slug": "easy_daily_bias_mechanical_framework",
                    "video_id": "-KKuZb5Z5aU",
                    "title": "Easy Daily Bias - Mechanical Framework",
                    "topics": ["daily_bias", "equilibrium"],
                    "start": 200.239,
                    "end": 269.36,
                    "text": (
                        "It's not ideal to have closures on the hourly chart below that. "
                        "I don't want to see a closure below that EQ level."
                    ),
                },
                {
                    "video_slug": "equilibrium_for_expansions",
                    "video_id": "IPZjNI1B5a0",
                    "title": "You Are Using Discount and Premium Wrong! - EQ For Expansions",
                    "topics": ["equilibrium", "continuation"],
                    "start": 596.68,
                    "end": 679.32,
                    "text": "Without that confirmation there is no bullish setup there.",
                },
                {
                    "video_slug": "trading_candle_3",
                    "video_id": "qdQYhePcvGE",
                    "title": "TTrades Fractal Model - Trading Candle 3",
                    "topics": ["candle_3", "continuation"],
                    "start": 1290.159,
                    "end": 1358.32,
                    "text": (
                        "The setup fails before forming that continuation. If I was just to "
                        "trade the reversal, I would get stopped out there."
                    ),
                },
            ],
            youtube_embedding_index={"items": []},
        )

        by_case_ref = {example["case_ref"]: example for example in report["youtube_transcript_examples"]}
        self.assertEqual(report["summary"]["youtube_transcript_example_count"], 4)
        self.assertEqual(
            by_case_ref["youtube::fractal_model_fundamentals:0000"]["targets"]["outcome_decision"],
            "no_trade",
        )
        self.assertEqual(
            by_case_ref["youtube::easy_daily_bias_mechanical_framework:0000"]["targets"][
                "outcome_decision"
            ],
            "no_trade",
        )
        self.assertEqual(
            by_case_ref["youtube::equilibrium_for_expansions:0000"]["targets"]["outcome_decision"],
            "no_trade",
        )
        self.assertEqual(
            by_case_ref["youtube::trading_candle_3:0000"]["targets"]["outcome_decision"],
            "no_trade",
        )
        self.assertTrue(
            by_case_ref["youtube::trading_candle_3:0000"]["targets"]["is_no_trade"]
        )

    def test_build_reinforced_training_surface_labels_failed_cisd_confirmations_as_no_trade(
        self,
    ) -> None:
        report = erts.build_reinforced_training_surface(
            base_examples=[],
            case_packet_report={"summary": {}, "case_packets": []},
            iteration_grading_report={"episodes": []},
            tradingview_validation_log={"validations": []},
            youtube_chunk_rows=[
                {
                    "video_slug": "cisd_validates_swing_points",
                    "video_id": "vn1RYjhJUnQ",
                    "title": "Validating Swing Points Using Lower Timeframe Confirmation (CISD)",
                    "topics": ["cisd", "candle_2", "continuation"],
                    "start": 403.6,
                    "end": 478.72,
                    "text": (
                        "Price fails to go and close below this level. The indicator will not "
                        "print a bearish setup and we are just in a consolidation."
                    ),
                }
            ],
            youtube_embedding_index={"items": []},
        )

        youtube_example = report["youtube_transcript_examples"][0]
        self.assertEqual(youtube_example["targets"]["outcome_decision"], "no_trade")
        self.assertTrue(youtube_example["targets"]["is_no_trade"])

    def test_build_reinforced_training_surface_skips_generic_chunks_from_mixed_curriculum_sources(
        self,
    ) -> None:
        report = erts.build_reinforced_training_surface(
            base_examples=[],
            case_packet_report={"summary": {}, "case_packets": []},
            iteration_grading_report={"episodes": []},
            tradingview_validation_log={"validations": []},
            youtube_chunk_rows=[
                {
                    "video_slug": "fractal_model_fundamentals",
                    "video_id": "TNybDCtwBnc",
                    "title": "TTrades Playbook | Fractal Model Fundamentals (TTFM)",
                    "topics": ["fractal_model", "daily_bias"],
                    "start": 5.49,
                    "end": 87.439,
                    "text": (
                        "The foundation of the fractal model is based off the idea that price "
                        "cannot reverse without a swing point."
                    ),
                },
                {
                    "video_slug": "fractal_model_fundamentals",
                    "video_id": "TNybDCtwBnc",
                    "title": "TTrades Playbook | Fractal Model Fundamentals (TTFM)",
                    "topics": ["fractal_model", "daily_bias", "cisd"],
                    "start": 85.28,
                    "end": 153.28,
                    "text": (
                        "If I do not have a daily bias I do not drop down to the hourly time "
                        "frame. Once I have both the closure and the change in the state of "
                        "delivery, then I can look for entries."
                    ),
                },
            ],
            youtube_embedding_index={"items": []},
        )

        self.assertEqual(report["summary"]["youtube_transcript_example_count"], 1)
        youtube_example = report["youtube_transcript_examples"][0]
        self.assertEqual(youtube_example["case_ref"], "youtube::fractal_model_fundamentals:0001")
        self.assertEqual(youtube_example["trade_model"], "daily_bias_c123_map")
        self.assertFalse(youtube_example["targets"]["has_outcome_label"])


if __name__ == "__main__":
    unittest.main()
