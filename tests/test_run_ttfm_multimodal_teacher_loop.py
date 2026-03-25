from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import run_ttfm_multimodal_teacher_loop as rtmvl


class BuildMultimodalTeacherLoopReportTests(unittest.TestCase):
    def test_merge_additional_weak_rows_appends_intake_images_without_replacing_video_rows(self) -> None:
        merged_rows, merge_report = rtmvl.merge_additional_weak_multimodal_rows(
            primary_rows=[
                {
                    "example_id": "youtube_case::confirmation",
                    "review_status": "ready_for_weak_training",
                    "eligible_for_training": True,
                }
            ],
            additional_rows=[
                {
                    "example_id": "image_case::confirmation",
                    "review_status": "ready_for_weak_training",
                    "eligible_for_training": True,
                    "source_type": "daily_intake_image",
                },
                {
                    "example_id": "youtube_case::confirmation",
                    "review_status": "ready_for_weak_training",
                    "eligible_for_training": True,
                    "source_type": "daily_intake_image",
                },
            ],
        )

        self.assertEqual(len(merged_rows), 2)
        self.assertEqual(merge_report["primary_row_count"], 1)
        self.assertEqual(merge_report["additional_row_count"], 2)
        self.assertEqual(merge_report["added_additional_row_count"], 1)
        self.assertEqual(merge_report["duplicate_example_id_count"], 1)
        self.assertEqual(merge_report["additional_source_type_counts"]["daily_intake_image"], 2)

    def test_build_multimodal_teacher_loop_report_summarizes_dataset_and_model_metrics(self) -> None:
        report = rtmvl.build_multimodal_teacher_loop_report(
            weak_multimodal_report={
                "summary": {
                    "row_count": 30,
                    "audio_clips_extracted_count": 30,
                }
            },
            blended_multimodal_report={
                "summary": {
                    "row_count": 80,
                    "teacher_row_count": 50,
                    "weak_row_count": 30,
                    "audio_enabled_row_count": 30,
                }
            },
            training_report={
                "device": "cuda",
                "brain_type": "setup_scorer",
                "embedding_backend": "google_gemini",
                "visual_embedding_model": "models/gemini-embedding-exp-03-07",
                "text_embedding_model": "models/gemini-embedding-001",
                "audio_semantic_mode": "models/gemini-2.0-flash",
                "label_space_size": 13,
                "audio_enabled_example_count": 30,
                "audio_semantic_example_count": 28,
                "text_enabled_example_count": 30,
                "best_epoch": 14,
                "best_validation_f1": 0.39,
                "best_prediction_threshold": 0.35,
                "best_prediction_threshold_mode": "per_label",
                "best_prediction_thresholds": {"order_block": 0.41},
                "train_metrics": {"micro_f1": 0.37},
                "validation_metrics": {
                    "micro_f1": 0.39,
                    "micro_precision": 0.25,
                    "micro_recall": 0.85,
                    "positive_predictions": 118,
                    "positive_labels": 35,
                    "average_setup_confidence": 0.73,
                },
            },
            review_queue={
                "summary": {
                    "row_count": 30,
                    "model_disagreement_count": 8,
                    "ready_to_promote_count": 2,
                }
            },
            weak_multimodal_dataset_path=Path("results/ttfm_video_multimodal_dataset.jsonl"),
            blended_multimodal_dataset_path=Path("results/ttfm_blended_multimodal_dataset.jsonl"),
            review_queue_output_path=Path("results/ttfm_multimodal_review_queue.json"),
            model_path=Path("results/neural_models/ttfm_blended_multimodal/model.pt"),
            model_report_path=Path("results/neural_models/ttfm_blended_multimodal/model_report.json"),
        )

        self.assertEqual(report["weak_multimodal_dataset"]["row_count"], 30)
        self.assertEqual(report["blended_multimodal_dataset"]["row_count"], 80)
        self.assertEqual(report["multimodal_review_queue"]["row_count"], 30)
        self.assertEqual(report["multimodal_review_queue"]["model_disagreement_count"], 8)
        self.assertEqual(report["multimodal_model"]["label_space_size"], 13)
        self.assertEqual(report["multimodal_model"]["brain_type"], "setup_scorer")
        self.assertEqual(report["multimodal_model"]["embedding_backend"], "google_gemini")
        self.assertEqual(report["multimodal_model"]["audio_enabled_example_count"], 30)
        self.assertEqual(report["multimodal_model"]["audio_semantic_example_count"], 28)
        self.assertEqual(report["multimodal_model"]["best_prediction_threshold_mode"], "per_label")
        self.assertEqual(report["multimodal_model"]["best_prediction_thresholds"]["order_block"], 0.41)
        self.assertEqual(report["multimodal_model"]["validation_average_setup_confidence"], 0.73)
        self.assertEqual(report["multimodal_model"]["validation_micro_f1"], 0.39)


if __name__ == "__main__":
    unittest.main()
