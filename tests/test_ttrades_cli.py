from __future__ import annotations

from pathlib import Path

import main
from dataclasses import replace


def test_main_dispatches_phase_handlers(monkeypatch, tmp_path: Path) -> None:
    called: list[tuple[str, str | None]] = []

    monkeypatch.setattr(main, "run_phase_1", lambda config, anchors_path=None: called.append(("phase1", str(anchors_path) if anchors_path else None)))
    monkeypatch.setattr(main, "run_phase_2", lambda config: called.append(("phase2", None)))
    monkeypatch.setattr(main, "run_phase_3", lambda config: called.append(("phase3", None)))
    monkeypatch.setattr(main, "run_phase_4", lambda config: called.append(("phase4", None)))
    monkeypatch.setattr(main, "run_autonomous_workflow_loop", lambda config: called.append(("loop", None)))

    anchors_path = tmp_path / "anchors.json"
    anchors_path.write_text("[]", encoding="utf-8")

    main.main(["--phase", "1", "--anchors", str(anchors_path)])
    main.main(["--phase", "2"])
    main.main(["--phase", "3"])
    main.main(["--phase", "4"])
    main.main(["--phase", "loop"])

    assert called == [
        ("phase1", str(anchors_path)),
        ("phase2", None),
        ("phase3", None),
        ("phase4", None),
        ("loop", None),
    ]


def test_run_phase_2_falls_back_to_supervision_when_openai_key_missing(monkeypatch, tmp_path: Path) -> None:
    config = main.build_config(root_dir=tmp_path)
    examples = [
        type(
            "Example",
            (),
            {
                "example_id": "demo::1",
                "image_path": tmp_path / "demo.png",
                "time_index": 1,
                "text": "bullish continuation",
                "title": "Demo",
                "source_type": "visual_embedding_index",
                "metadata": {"checkpoint": "confirmation", "candidate_labels": ["protected_swing"]},
            },
        )()
    ]
    examples[0].image_path.write_bytes(b"img")

    monkeypatch.setattr(main, "load_chart_corpus", lambda config: type("Corpus", (), {"examples": examples})())
    monkeypatch.setattr(main, "ensure_corpus_size", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should not expand corpus when key is missing")))
    monkeypatch.setattr(
        main,
        "select_representative_examples",
        lambda *args, **kwargs: {
            "method": "kmeans",
            "cluster_count": 1,
            "selected_count": 1,
            "examples": examples,
        },
    )
    monkeypatch.setattr(main, "_init_wandb", lambda *args, **kwargs: type("Run", (), {"log": lambda *a, **k: None, "finish": lambda *a, **k: None})())
    monkeypatch.setattr(main, "has_openai_api_key", lambda: False)

    called = {"label": False, "export": False}
    monkeypatch.setattr(main, "label_representative_examples", lambda *args, **kwargs: called.__setitem__("label", True))
    monkeypatch.setattr(main, "export_yolo_dataset", lambda *args, **kwargs: called.__setitem__("export", True))

    report = main.run_phase_2(config)

    assert report["mode"] == "supervision_only"
    assert report["review_queue_count"] == 1
    assert Path(report["supervision_packet_path"]).exists()
    assert Path(report["supervision_answers_example_path"]).exists()
    assert Path(report["bundle_artifacts"]["bundle_dataset_path"]).exists()
    assert Path(report["bundle_artifacts"]["bundle_dataset_report_path"]).exists()
    assert Path(report["bundle_artifacts"]["bundle_gold_seed_path"]).exists()
    assert Path(report["bundle_artifacts"]["bundle_gold_seed_report_path"]).exists()
    assert called == {"label": False, "export": False}


def test_run_phase_2_uses_supervision_answers_when_present(monkeypatch, tmp_path: Path) -> None:
    config = main.build_config(root_dir=tmp_path)
    config = replace(config, phase2=replace(config.phase2, synthetic_sidecar_enabled=False))
    examples = [
        type(
            "Example",
            (),
            {
                "example_id": "demo::1",
                "image_path": tmp_path / "demo.png",
                "time_index": 1,
                "text": "bullish continuation",
                "title": "Demo",
                "source_type": "visual_embedding_index",
                "metadata": {"checkpoint": "confirmation"},
            },
        )()
    ]
    examples[0].image_path.write_bytes(b"img")
    all_corpus_examples = examples + [
        type(
            "Example",
            (),
            {
                "example_id": "demo::2",
                "image_path": tmp_path / "demo2.png",
                "time_index": 2,
                "text": "other chart",
                "title": "Other",
                "source_type": "visual_embedding_index",
                "metadata": {"checkpoint": "outcome"},
            },
        )()
    ]
    all_corpus_examples[1].image_path.write_bytes(b"img2")
    config.paths.phase2_supervision_answers_path.write_text(
        '{"items":[{"example_id":"demo::1","detections":[{"class_id":0,"bbox":[0.5,0.5,0.2,0.2]}]}]}',
        encoding="utf-8",
    )

    monkeypatch.setattr(main, "load_chart_corpus", lambda config: type("Corpus", (), {"examples": all_corpus_examples})())
    monkeypatch.setattr(
        main,
        "select_representative_examples",
        lambda *args, **kwargs: {
            "method": "kmeans",
            "cluster_count": 1,
            "selected_count": 1,
            "examples": [all_corpus_examples[1]],
        },
    )
    monkeypatch.setattr(main, "_init_wandb", lambda *args, **kwargs: type("Run", (), {"log": lambda *a, **k: None, "finish": lambda *a, **k: None})())
    monkeypatch.setattr(main, "has_openai_api_key", lambda: False)

    captured_rows = {}

    def fake_export(rows, config):
        captured_rows["rows"] = rows
        return {"train_count": 1, "val_count": 0}

    monkeypatch.setattr(main, "export_yolo_dataset", fake_export)

    report = main.run_phase_2(config)

    assert report["mode"] == "supervision_answers"
    assert report["used_answer_count"] == 1
    assert Path(report["bundle_artifacts"]["bundle_dataset_path"]).exists()
    assert captured_rows["rows"][0]["example_id"] == "demo::1"


def test_run_phase_2_merges_dense_supervision_answers_when_present(monkeypatch, tmp_path: Path) -> None:
    config = main.build_config(root_dir=tmp_path)
    config = replace(config, phase2=replace(config.phase2, synthetic_sidecar_enabled=False))
    examples = [
        type(
            "Example",
            (),
            {
                "example_id": "other::1",
                "image_path": tmp_path / "dense.png",
                "time_index": 3,
                "text": "dense chart",
                "title": "Dense",
                "source_type": "youtube_dense_window",
                "metadata": {"checkpoint": "dense"},
            },
        )()
    ]
    examples[0].image_path.write_bytes(b"img")
    config.paths.dense_visual_windows_path.parent.mkdir(parents=True, exist_ok=True)
    dense_image = tmp_path / "dense_source.png"
    dense_image.write_bytes(b"img2")
    config.paths.dense_visual_windows_path.write_text(
        '{"example_id":"dense::1","frame_path":"' + str(dense_image).replace("\\", "\\\\") + '","start":1.25,"title":"Dense Source","source_type":"youtube_dense_window"}\n',
        encoding="utf-8",
    )
    config.paths.phase2_dense_supervision_answers_path.write_text(
        '{"items":[{"example_id":"dense::1","detections":[{"class_id":2,"bbox":[0.5,0.5,0.2,0.2]}]}]}',
        encoding="utf-8",
    )

    monkeypatch.setattr(main, "load_chart_corpus", lambda config: type("Corpus", (), {"examples": examples})())
    monkeypatch.setattr(
        main,
        "select_representative_examples",
        lambda *args, **kwargs: {
            "method": "kmeans",
            "cluster_count": 1,
            "selected_count": 0,
            "examples": [],
        },
    )
    monkeypatch.setattr(main, "_init_wandb", lambda *args, **kwargs: type("Run", (), {"log": lambda *a, **k: None, "finish": lambda *a, **k: None})())
    monkeypatch.setattr(main, "has_openai_api_key", lambda: False)

    captured_rows = {}

    def fake_export(rows, config):
        captured_rows["rows"] = rows
        return {"train_count": 1, "val_count": 0}

    monkeypatch.setattr(main, "export_yolo_dataset", fake_export)

    report = main.run_phase_2(config)

    assert report["mode"] == "supervision_answers"
    assert report["used_answer_count"] == 1
    assert captured_rows["rows"][0]["example_id"] == "dense::1"


def test_run_phase_2_includes_heuristic_promotions(monkeypatch, tmp_path: Path) -> None:
    config = main.build_config(root_dir=tmp_path)
    config = replace(config, phase2=replace(config.phase2, synthetic_sidecar_enabled=False))
    dense_image = tmp_path / "dense_source.png"
    dense_image.write_bytes(b"img")
    config.paths.dense_visual_windows_path.parent.mkdir(parents=True, exist_ok=True)
    config.paths.dense_visual_windows_path.write_text(
        '{"example_id":"dense::1","frame_path":"' + str(dense_image).replace("\\", "\\\\") + '","start":1.25,"title":"Dense Source","source_type":"youtube_dense_window","video_slug":"dense_video"}\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(main, "load_chart_corpus", lambda config: type("Corpus", (), {"examples": []})())
    monkeypatch.setattr(
        main,
        "select_representative_examples",
        lambda *args, **kwargs: {
            "method": "kmeans",
            "cluster_count": 1,
            "selected_count": 0,
            "examples": [],
        },
    )
    monkeypatch.setattr(main, "_init_wandb", lambda *args, **kwargs: type("Run", (), {"log": lambda *a, **k: None, "finish": lambda *a, **k: None})())
    monkeypatch.setattr(main, "has_openai_api_key", lambda: False)
    monkeypatch.setattr(
        main,
        "build_dense_supervision_packet_from_rows",
        lambda *args, **kwargs: {
            "items": [
                {
                    "example_id": "dense::1",
                    "candidate_detections": [{"class_id": 3, "bbox": [0.5, 0.5, 0.2, 0.2]}],
                    "title": "Trade Continuations Using Order Blocks",
                    "candidate_labels": ["bullish_reaction_zone"],
                    "cue_terms": ["order block"],
                }
            ]
        },
    )

    captured_rows = {}

    def fake_export(rows, config):
        captured_rows["rows"] = rows
        return {"train_count": 1, "val_count": 0}

    monkeypatch.setattr(main, "export_yolo_dataset", fake_export)

    report = main.run_phase_2(config)

    assert report["mode"] == "supervision_answers"
    assert report["heuristic_auto_label_count"] == 1
    assert captured_rows["rows"][0]["example_id"] == "dense::1"


def test_run_phase_2_accumulates_existing_dense_promotions(monkeypatch, tmp_path: Path) -> None:
    config = main.build_config(root_dir=tmp_path)
    config = replace(config, phase2=replace(config.phase2, synthetic_sidecar_enabled=False))
    dense_image = tmp_path / "dense_source.png"
    dense_image.write_bytes(b"img")
    config.paths.dense_visual_windows_path.parent.mkdir(parents=True, exist_ok=True)
    config.paths.dense_visual_windows_path.write_text(
        '{"example_id":"dense::2","frame_path":"' + str(dense_image).replace("\\", "\\\\") + '","start":1.25,"title":"Dense Source","source_type":"youtube_dense_window","video_slug":"dense_video"}\n',
        encoding="utf-8",
    )
    config.paths.phase2_dense_heuristic_promotions_path.write_text(
        '{"items":[{"example_id":"dense::1","detections":[{"class_id":2,"bbox":[0.5,0.5,0.2,0.2]}]}]}',
        encoding="utf-8",
    )

    monkeypatch.setattr(main, "load_chart_corpus", lambda config: type("Corpus", (), {"examples": []})())
    monkeypatch.setattr(
        main,
        "select_representative_examples",
        lambda *args, **kwargs: {
            "method": "kmeans",
            "cluster_count": 1,
            "selected_count": 0,
            "examples": [],
        },
    )
    monkeypatch.setattr(main, "_init_wandb", lambda *args, **kwargs: type("Run", (), {"log": lambda *a, **k: None, "finish": lambda *a, **k: None})())
    monkeypatch.setattr(main, "has_openai_api_key", lambda: False)
    monkeypatch.setattr(
        main,
        "build_dense_supervision_packet_from_rows",
        lambda *args, **kwargs: {
            "items": [
                {
                    "example_id": "dense::2",
                    "candidate_detections": [{"class_id": 3, "bbox": [0.4, 0.4, 0.2, 0.2]}],
                    "title": "Trade Continuations Using Order Blocks",
                    "candidate_labels": ["bullish_reaction_zone"],
                    "cue_terms": ["order block"],
                }
            ]
        },
    )

    captured_rows = {}

    def fake_export(rows, config):
        captured_rows["rows"] = rows
        return {"train_count": 2, "val_count": 0}

    monkeypatch.setattr(main, "export_yolo_dataset", fake_export)

    report = main.run_phase_2(config)

    assert report["heuristic_auto_label_count"] == 1
    persisted = main.load_supervision_answers(config.paths.phase2_dense_heuristic_promotions_path)
    assert {row["example_id"] for row in persisted} == {"dense::1", "dense::2"}
    assert {row["example_id"] for row in captured_rows["rows"]} == {"dense::2"}


def test_run_phase_2_includes_setup_quality_auto_promotions(monkeypatch, tmp_path: Path) -> None:
    config = main.build_config(root_dir=tmp_path)
    config = replace(config, phase2=replace(config.phase2, synthetic_sidecar_enabled=False))
    dense_image = tmp_path / "dense_source.png"
    dense_image.write_bytes(b"img")
    dense_image_bad = tmp_path / "dense_bad.png"
    dense_image_bad.write_bytes(b"img2")
    config.paths.dense_visual_windows_path.parent.mkdir(parents=True, exist_ok=True)
    config.paths.dense_visual_windows_path.write_text(
        '{"example_id":"dense::good","frame_path":"' + str(dense_image).replace("\\", "\\\\") + '","start":1.25,"title":"Dense Source","source_type":"youtube_dense_window","video_slug":"dense_video"}\n'
        + '{"example_id":"dense::bad","frame_path":"' + str(dense_image_bad).replace("\\", "\\\\") + '","start":2.25,"title":"Dense Bad","source_type":"youtube_dense_window","video_slug":"dense_video"}\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(main, "load_chart_corpus", lambda config: type("Corpus", (), {"examples": []})())
    monkeypatch.setattr(
        main,
        "select_representative_examples",
        lambda *args, **kwargs: {
            "method": "kmeans",
            "cluster_count": 1,
            "selected_count": 0,
            "examples": [],
        },
    )
    monkeypatch.setattr(main, "_init_wandb", lambda *args, **kwargs: type("Run", (), {"log": lambda *a, **k: None, "finish": lambda *a, **k: None})())
    monkeypatch.setattr(main, "has_openai_api_key", lambda: False)
    monkeypatch.setattr(
        main,
        "build_dense_supervision_packet_from_rows",
        lambda *args, **kwargs: {
            "items": [
                {
                    "example_id": "dense::good",
                    "candidate_detections": [{"class_id": 3, "bbox": [0.5, 0.5, 0.2, 0.2]}],
                    "title": "Trade Continuations Using Order Blocks",
                    "candidate_labels": ["bullish_reaction_zone"],
                    "cue_terms": ["order block"],
                    "recommended_action": "accept",
                    "setup_type": "high_probability_long",
                    "setup_confidence": 0.91,
                },
                {
                    "example_id": "dense::bad",
                    "candidate_detections": [],
                    "title": "Invalid Chop Example",
                    "candidate_labels": [],
                    "cue_terms": ["range", "chop"],
                    "recommended_action": "no_setup",
                    "setup_type": "invalid_chop",
                    "setup_confidence": 0.87,
                },
            ]
        },
    )

    captured_rows = {}

    def fake_export(rows, config):
        captured_rows["rows"] = rows
        return {"train_count": 2, "val_count": 0}

    monkeypatch.setattr(main, "export_yolo_dataset", fake_export)

    report = main.run_phase_2(config)

    assert report["mode"] == "supervision_answers"
    assert report["heuristic_auto_label_count"] == 2
    assert report["setup_quality_auto_label_count"] == 1
    assert {row["example_id"] for row in captured_rows["rows"]} == {"dense::good", "dense::bad"}


def test_run_phase_2_includes_accept_packet_auto_promotions(monkeypatch, tmp_path: Path) -> None:
    config = main.build_config(root_dir=tmp_path)
    config = replace(config, phase2=replace(config.phase2, synthetic_sidecar_enabled=False))
    dense_image = tmp_path / "dense_source.png"
    dense_image.write_bytes(b"img")
    config.paths.dense_visual_windows_path.parent.mkdir(parents=True, exist_ok=True)
    config.paths.dense_visual_windows_path.write_text(
        '{"example_id":"dense::accept","frame_path":"' + str(dense_image).replace("\\", "\\\\") + '","start":1.25,"title":"Dense Source","source_type":"youtube_dense_window","video_slug":"dense_video"}\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(main, "load_chart_corpus", lambda config: type("Corpus", (), {"examples": []})())
    monkeypatch.setattr(
        main,
        "select_representative_examples",
        lambda *args, **kwargs: {
            "method": "kmeans",
            "cluster_count": 1,
            "selected_count": 0,
            "examples": [],
        },
    )
    monkeypatch.setattr(main, "_init_wandb", lambda *args, **kwargs: type("Run", (), {"log": lambda *a, **k: None, "finish": lambda *a, **k: None})())
    monkeypatch.setattr(main, "has_openai_api_key", lambda: False)
    monkeypatch.setattr(
        main,
        "build_dense_supervision_packet_from_rows",
        lambda *args, **kwargs: {
            "items": [
                {
                    "example_id": "dense::accept",
                    "candidate_detections": [{"class_id": 4, "bbox": [0.4, 0.4, 0.2, 0.1], "confidence": 0.61}],
                    "title": "Dense Accept",
                    "candidate_labels": [],
                    "cue_terms": ["wick", "continuation"],
                    "recommended_action": "accept",
                }
            ]
        },
    )
    monkeypatch.setattr(main, "_enrich_packet_with_detector_proposals", lambda packet, config: packet)
    monkeypatch.setattr(main, "_enrich_packet_with_setup_quality", lambda packet, lookup, config: packet)

    captured_rows = {}

    def fake_export(rows, config):
        captured_rows["rows"] = rows
        return {"train_count": 1, "val_count": 0}

    monkeypatch.setattr(main, "export_yolo_dataset", fake_export)

    report = main.run_phase_2(config)

    assert report["mode"] == "supervision_answers"
    assert report["accept_packet_auto_label_count"] == 1
    assert report["heuristic_auto_label_count"] == 1
    assert {row["example_id"] for row in captured_rows["rows"]} == {"dense::accept"}


def test_run_phase_2_includes_scarce_accept_packet_auto_promotions(monkeypatch, tmp_path: Path) -> None:
    config = main.build_config(root_dir=tmp_path)
    config = replace(config, phase2=replace(config.phase2, synthetic_sidecar_enabled=False))
    dense_image = tmp_path / "dense_source.png"
    dense_image.write_bytes(b"img")
    config.paths.dense_visual_windows_path.parent.mkdir(parents=True, exist_ok=True)
    config.paths.dense_visual_windows_path.write_text(
        '{"example_id":"dense::scarce","frame_path":"' + str(dense_image).replace("\\", "\\\\") + '","start":1.25,"title":"Dense Scarce","source_type":"youtube_dense_window","video_slug":"dense_video"}\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(main, "load_chart_corpus", lambda config: type("Corpus", (), {"examples": []})())
    monkeypatch.setattr(
        main,
        "select_representative_examples",
        lambda *args, **kwargs: {
            "method": "kmeans",
            "cluster_count": 1,
            "selected_count": 0,
            "examples": [],
        },
    )
    monkeypatch.setattr(main, "_init_wandb", lambda *args, **kwargs: type("Run", (), {"log": lambda *a, **k: None, "finish": lambda *a, **k: None})())
    monkeypatch.setattr(main, "has_openai_api_key", lambda: False)
    monkeypatch.setattr(
        main,
        "build_dense_supervision_packet_from_rows",
        lambda *args, **kwargs: {
            "items": [
                {
                    "example_id": "dense::scarce",
                    "candidate_detections": [{"class_id": 4, "bbox": [0.4, 0.4, 0.2, 0.1], "confidence": 0.24}],
                    "title": "Dense Scarce",
                    "candidate_labels": ["bearish_reaction_zone"],
                    "cue_terms": ["wick", "continuation"],
                    "recommended_action": "adjust",
                }
            ]
        },
    )
    monkeypatch.setattr(main, "_enrich_packet_with_detector_proposals", lambda packet, config: packet)
    monkeypatch.setattr(main, "_enrich_packet_with_setup_quality", lambda packet, lookup, config: packet)

    captured_rows = {}

    def fake_export(rows, config):
        captured_rows["rows"] = rows
        return {"train_count": 1, "val_count": 0}

    monkeypatch.setattr(main, "export_yolo_dataset", fake_export)

    report = main.run_phase_2(config)

    assert report["mode"] == "supervision_answers"
    assert report["heuristic_auto_label_count"] == 1
    assert report["heuristic_auto_label_count"] == 1
    assert {row["example_id"] for row in captured_rows["rows"]} == {"dense::scarce"}


def test_merge_candidate_detections_deduplicates_boxes() -> None:
    existing = [{"class_id": 3, "bbox": [0.5, 0.5, 0.2, 0.2]}]
    incoming = [
        {"class_id": 3, "bbox": [0.5, 0.5, 0.2, 0.2], "confidence": 0.88},
        {"class_id": 4, "bbox": [0.4, 0.4, 0.1, 0.1], "confidence": 0.72},
    ]

    merged = main._merge_candidate_detections(existing, incoming)

    assert merged == [
        {"class_id": 3, "bbox": [0.5, 0.5, 0.2, 0.2]},
        {"class_id": 4, "bbox": [0.4, 0.4, 0.1, 0.1], "confidence": 0.72},
    ]


def test_dedupe_labeled_rows_merges_duplicate_examples() -> None:
    rows = [
        {
            "example_id": "dense::1",
            "image_path": "a.jpg",
            "time_index": 1,
            "detections": [{"class_id": 1, "bbox": [0.5, 0.5, 0.2, 0.2]}],
            "review_outcome": "accepted",
            "note": "",
        },
        {
            "example_id": "dense::1",
            "image_path": "a.jpg",
            "time_index": 1,
            "detections": [{"class_id": 2, "bbox": [0.4, 0.4, 0.1, 0.1]}],
            "review_outcome": "accepted",
            "note": "later note",
        },
    ]

    deduped = main._dedupe_labeled_rows(rows)

    assert len(deduped) == 1
    assert deduped[0]["note"] == "later note"
    assert deduped[0]["detections"] == [
        {"class_id": 1, "bbox": [0.5, 0.5, 0.2, 0.2]},
        {"class_id": 2, "bbox": [0.4, 0.4, 0.1, 0.1]},
    ]


def test_run_autonomous_workflow_loop_stops_when_phase2_growth_stalls(monkeypatch, tmp_path: Path) -> None:
    config = main.build_config(root_dir=tmp_path)
    config.paths.phase2_dataset_stats_path.write_text('{"train_count": 41, "val_count": 10}', encoding="utf-8")

    monkeypatch.setattr(main, "dense_visual_corpus_is_fresh", lambda _config: True)
    monkeypatch.setattr(main, "build_dense_visual_corpus", lambda _config: (_ for _ in ()).throw(AssertionError("should not rebuild fresh dense corpus")))
    monkeypatch.setattr(
        main,
        "run_phase_2",
        lambda _config: (
            config.paths.workflow_status_path.write_text(
                '{"metrics":{"yolo_train_count":41,"yolo_val_count":10,"heuristic_auto_label_count":0},"assessment":{"next_action":"label_more_dense_examples"}}',
                encoding="utf-8",
            )
            or {"mode": "supervision_answers"}
        ),
    )
    monkeypatch.setattr(main, "run_phase_3", lambda _config: (_ for _ in ()).throw(AssertionError("should not retrain when phase2 did not grow")))

    report = main.run_autonomous_workflow_loop(config)

    assert report["mode"] == "workflow_loop"
    assert report["stopped_reason"] == "phase2_growth_stalled"
    assert report["cycle_count"] == 1
