from __future__ import annotations

import json
from pathlib import Path

from labeler.vision_labeler import load_supervision_answers
from scripts.import_labelstudio_controlled_chart_answers import (
    import_labelstudio_answers,
    write_report,
)


def _rectangle_result(label: str, *, x: float = 10.0, y: float = 20.0, width: float = 30.0, height: float = 40.0) -> dict:
    return {
        "from_name": "detections",
        "to_name": "image",
        "type": "rectanglelabels",
        "value": {
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "rectanglelabels": [label],
        },
    }


def _choice_result(action: str) -> dict:
    return {
        "from_name": "review_action",
        "to_name": "image",
        "type": "choices",
        "value": {"choices": [action]},
    }


def _note_result(text: str) -> dict:
    return {
        "from_name": "review_notes",
        "to_name": "image",
        "type": "textarea",
        "value": {"text": [text]},
    }


def _task(example_id: str, results: list[dict] | None) -> dict:
    task = {
        "id": example_id,
        "data": {
            "image": f"results/controlled_charts/images/{example_id}.png",
            "image_id": example_id,
        },
    }
    if results is not None:
        task["annotations"] = [{"result": results}]
    return task


def test_import_labelstudio_accept_and_adjust_to_validated_answers(tmp_path: Path) -> None:
    export_path = tmp_path / "labelstudio_export.json"
    export_path.write_text(
        json.dumps(
            [
                _task(
                    "accepted-case",
                    [
                        _choice_result("accept"),
                        _rectangle_result("liquidity_sweep_high"),
                        _note_result("Clean sweep marker."),
                    ],
                ),
                _task(
                    "adjusted-case",
                    [
                        _choice_result("adjust"),
                        _rectangle_result("bullish_reaction_zone", x=40, y=50, width=10, height=20),
                    ],
                ),
            ]
        ),
        encoding="utf-8",
    )
    answers_path = tmp_path / "answers.json"
    report_path = tmp_path / "report.json"

    answers, report = import_labelstudio_answers(
        root_dir=tmp_path,
        labelstudio_export_path=export_path,
        output_answers_path=answers_path,
    )
    write_report(report, root_dir=tmp_path, output_report_path=report_path)
    validated = load_supervision_answers(answers_path)

    assert report["training_gate"] == "pass"
    assert report["validated_trainable_item_count"] == 2
    assert report["review_outcome_counts"] == {"accepted": 1, "adjusted": 1}
    assert [item["review_outcome"] for item in answers["items"]] == ["accepted", "adjusted"]
    assert answers["items"][0]["detections"] == [{"class_id": 0, "bbox": [0.25, 0.4, 0.3, 0.4]}]
    assert answers["items"][1]["detections"] == [{"class_id": 3, "bbox": [0.45, 0.6, 0.1, 0.2]}]
    assert len(validated) == 2
    assert report_path.exists()


def test_import_labelstudio_keeps_unreviewed_rejected_and_deferred_non_trainable(tmp_path: Path) -> None:
    export_path = tmp_path / "labelstudio_export.json"
    export_path.write_text(
        json.dumps(
            [
                _task("unreviewed-case", None),
                _task("rejected-case", [_choice_result("reject"), _rectangle_result("protected_swing")]),
                _task("deferred-case", [_choice_result("defer")]),
                _task("bad-accept-case", [_choice_result("accept")]),
            ]
        ),
        encoding="utf-8",
    )
    answers_path = tmp_path / "answers.json"

    answers, report = import_labelstudio_answers(
        root_dir=tmp_path,
        labelstudio_export_path=export_path,
        output_answers_path=answers_path,
    )
    validated = load_supervision_answers(answers_path)

    assert validated == []
    assert report["training_gate"] == "blocked_no_reviewed_trainable_items"
    assert report["validated_trainable_item_count"] == 0
    assert report["review_outcome_counts"] == {"ambiguous": 3, "rejected": 1}
    assert report["issue_counts"] == {
        "accepted_or_adjusted_without_detections": 1,
        "missing_annotation": 1,
    }
    assert [item["training_eligible"] for item in answers["items"]] == [False, False, False, False]
