from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import run_ttfm_visual_teacher_loop as rtvtl


def make_weak_rows() -> list[dict]:
    return [
        {
            "example_id": "weak_case::confirmation",
            "case_ref": "weak_case",
            "checkpoint": "confirmation",
            "timeframe": "ltf",
            "timeframe_role": "ltf",
            "topics": ["equilibrium", "fair_value_gap"],
            "supporting_topics": ["equilibrium"],
            "active_labels": ["equilibrium", "fair_value_gap"],
            "annotation_notes": ["Reviewed from YouTube frame."],
            "evidence_refs": ["https://youtu.be/example", "chunk:0001"],
            "source_url": "https://youtu.be/example",
            "source_page": "https://ttrades.com/example",
            "source_chunk_id": "chunk:0001",
            "screenshot_path": "knowledge/ttfm_video_corpus/frames/example/confirmation.jpg",
            "market_context": {"confidence": 0.7},
            "weak_label_confidence": 0.7,
            "review_status": "approved_for_teacher",
            "contradiction_status": "resolved",
        },
        {
            "example_id": "pending_case::context",
            "case_ref": "pending_case",
            "checkpoint": "context",
            "active_labels": ["breaker"],
            "screenshot_path": "knowledge/ttfm_video_corpus/frames/example/context.jpg",
            "review_status": "ready_for_weak_training",
            "contradiction_status": "unreviewed",
        },
        {
            "example_id": "blocked_case::closure",
            "case_ref": "blocked_case",
            "checkpoint": "closure",
            "active_labels": ["order_block"],
            "screenshot_path": "knowledge/ttfm_video_corpus/frames/example/closure.jpg",
            "review_status": "approved_for_teacher",
            "contradiction_status": "blocked",
        },
    ]


class ReviewedWeakPromotionTests(unittest.TestCase):
    def test_promote_reviewed_weak_visual_rows_builds_teacher_ready_rows(self) -> None:
        promoted_rows, report = rtvtl.promote_reviewed_weak_visual_rows(make_weak_rows())

        self.assertEqual(len(promoted_rows), 1)
        promoted = promoted_rows[0]
        self.assertEqual(promoted["example_id"], "weak_case::confirmation")
        self.assertEqual(promoted["active_label_provenance"], "weak_visual_review_promoted")
        self.assertEqual(promoted["labels_by_provenance"]["weak_visual_review_promoted"], ["equilibrium", "fair_value_gap"])
        self.assertEqual(promoted["sample_weight"], 1.0)
        self.assertEqual(promoted["source_tier"], "teacher_promoted_weak")
        self.assertEqual(report["summary"]["promoted_row_count"], 1)
        self.assertEqual(report["summary"]["pending_review_count"], 1)
        self.assertEqual(report["summary"]["blocked_contradiction_count"], 1)


class VisualTeacherLoopReportTests(unittest.TestCase):
    def test_build_visual_teacher_loop_report_summarizes_alignment_and_model_metrics(self) -> None:
        teacher_dataset_report = {
            "summary": {
                "row_count": 50,
                "mapped_case_count": 2,
                "fully_aligned_case_count": 0,
                "alignment_status_counts": {"market_context_only": 10, "unmapped": 40},
                "mapping_provenance_counts": {"tradingview_validation_proxy": 10, "unmapped": 40},
            }
        }
        review_queue = {
            "summary": {
                "case_count": 10,
                "recommended_action_counts": {"confirm_anchor_timestamp": 2},
            }
        }
        training_report = {
            "device": "cuda",
            "label_space_size": 12,
            "best_epoch": 18,
            "best_validation_f1": 0.2105,
            "best_prediction_threshold": 0.45,
            "train_metrics": {"micro_f1": 0.2561},
            "validation_metrics": {
                "micro_f1": 0.2105,
                "micro_precision": 0.1212,
                "micro_recall": 0.8,
                "positive_predictions": 66,
                "positive_labels": 10,
            },
        }
        weak_promotion_report = {
            "summary": {
                "promoted_row_count": 3,
                "pending_review_count": 12,
                "blocked_contradiction_count": 2,
            }
        }
        weak_promotion_queue_report = {
            "summary": {
                "row_count": 30,
                "review_candidate_count": 12,
                "ready_to_promote_count": 3,
            }
        }

        report = rtvtl.build_visual_teacher_loop_report(
            sync_applied=False,
            teacher_dataset_report=teacher_dataset_report,
            review_queue=review_queue,
            training_report=training_report,
            weak_promotion_report=weak_promotion_report,
            weak_promotion_queue_report=weak_promotion_queue_report,
            phase_one_replay_report={
                "dataset_output": str(ROOT / "results" / "ttfm_phase_one_replay_dataset.jsonl"),
                "report_output": str(ROOT / "results" / "ttfm_phase_one_replay_dataset_report.json"),
                "summary": {
                    "phase_one_case_count": 2,
                    "exported_case_count": 0,
                    "skipped_case_counts": {"not_fully_aligned": 2},
                },
            },
            review_dashboard_path=ROOT / "results" / "ttfm_market_context_review_dashboard.html",
            override_template_path=ROOT / "results" / "ttfm_market_context_override_templates.json",
            model_path=ROOT / "results" / "neural_models" / "ttfm_visual" / "ttfm_visual_pattern_net.pt",
            model_report_path=ROOT / "results" / "neural_models" / "ttfm_visual" / "ttfm_visual_pattern_net_report.json",
        )

        self.assertFalse(report["sync_applied"])
        self.assertEqual(report["teacher_dataset"]["row_count"], 50)
        self.assertEqual(report["teacher_dataset"]["mapped_case_count"], 2)
        self.assertEqual(report["visual_model"]["device"], "cuda")
        self.assertEqual(report["visual_model"]["best_prediction_threshold"], 0.45)
        self.assertEqual(report["visual_model"]["validation_positive_predictions"], 66)
        self.assertEqual(report["phase_one_replay_dataset"]["phase_one_case_count"], 2)
        self.assertEqual(report["phase_one_replay_dataset"]["exported_case_count"], 0)
        self.assertEqual(report["weak_promotions"]["promoted_row_count"], 3)
        self.assertEqual(report["weak_promotion_queue"]["ready_to_promote_count"], 3)
        self.assertIn("dashboard_path", report["review_artifacts"])


if __name__ == "__main__":
    unittest.main()
