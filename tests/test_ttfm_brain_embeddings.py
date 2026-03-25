from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import ttfm_brain_embeddings as tbe


EMBEDDING_DIM = 4


def fake_text_embedder(texts: list[str]) -> list[list[float]]:
    vectors: list[list[float]] = []
    for index, text in enumerate(texts):
        checksum = sum(ord(character) for character in text)
        vectors.append(
            [
                float((checksum % 9) + 1),
                float((len(text) % 5) + 1),
                float(index + 1),
                1.0,
            ]
        )
    return vectors


def fake_visual_embedder(asset_path: Path | None, text: str) -> tuple[list[float], bool]:
    stem = asset_path.stem if asset_path is not None else "missing"
    checksum = sum(ord(character) for character in f"{stem}:{text}")
    base = float((checksum % 4) + 1)
    return [base, base + 1.0, base + 2.0, 1.0], False


def fake_audio_summarizer(row: dict[str, object], audio_path: Path) -> tuple[str, str]:
    return (f"audio summary for {row['example_id']}", "gemini_audio_summary")


class BrainEmbeddingPrepTests(unittest.TestCase):
    def test_build_examples_from_google_embeddings_aligns_visual_transcript_and_audio_vectors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir)
            image_a = base_dir / "a.png"
            image_b = base_dir / "b.png"
            audio_a = base_dir / "a.wav"
            text_cache_path = base_dir / "text_cache.json"
            Image.new("RGB", (16, 16), color=(255, 0, 0)).save(image_a)
            Image.new("RGB", (16, 16), color=(0, 255, 0)).save(image_b)
            audio_a.write_bytes(b"fake-audio")
            audio_cache_path = base_dir / "audio_cache.json"

            rows = [
                {
                    "example_id": "case_a",
                    "case_ref": "case-a",
                    "checkpoint": "confirmation",
                    "active_labels": ["order_block"],
                    "screenshot_path": str(image_a),
                    "audio_path": str(audio_a),
                    "transcript_text": "order block confirmation",
                    "framework_slug": "ttfm",
                    "profile_slug": "ttrades_curriculum",
                    "brain_type": "setup_scorer",
                },
                {
                    "example_id": "case_b",
                    "case_ref": "case-b",
                    "checkpoint": "context",
                    "active_labels": ["fair_value_gap"],
                    "screenshot_path": str(image_b),
                    "transcript_text": "fair value gap context",
                },
            ]
            visual_index_lookup = {
                "case_a": {
                    "chunk_id": "case_a",
                    "vector": [9.0, 8.0, 7.0, 6.0],
                }
            }

            examples, skipped, prep_report = tbe.build_examples_from_google_embeddings(
                rows,
                label_to_index={"order_block": 0, "fair_value_gap": 1},
                output_dimensionality=EMBEDDING_DIM,
                audio_semantic_cache_path=audio_cache_path,
                text_embedding_cache_path=text_cache_path,
                visual_index_lookup=visual_index_lookup,
                text_embedder=fake_text_embedder,
                visual_embedder=fake_visual_embedder,
                audio_summarizer=fake_audio_summarizer,
            )

            cache_payload = json.loads(audio_cache_path.read_text(encoding="utf-8"))

        self.assertEqual(skipped, [])
        self.assertEqual(len(examples), 2)
        self.assertEqual(examples[0]["example_id"], "case_a")
        self.assertEqual(examples[0]["visual_embedding"], [9.0, 8.0, 7.0, 6.0])
        self.assertEqual(examples[0]["visual_embedding_source"], "visual_index")
        self.assertEqual(examples[0]["audio_semantic_mode"], "gemini_audio_summary")
        self.assertEqual(examples[1]["visual_embedding_source"], "direct_gemini_embed")
        self.assertEqual(examples[1]["has_audio"], False)
        self.assertEqual(examples[1]["has_audio_semantic"], False)
        self.assertNotEqual(examples[0]["transcript_embedding"], [0.0, 0.0, 0.0, 0.0])
        self.assertNotEqual(examples[0]["audio_semantic_embedding"], [0.0, 0.0, 0.0, 0.0])
        self.assertEqual(prep_report["visual_index_hit_count"], 1)
        self.assertEqual(prep_report["audio_semantic_embedding_count"], 1)
        self.assertEqual(prep_report["transcript_cache_miss_count"], 2)
        self.assertEqual(prep_report["audio_semantic_cache_miss_count"], 1)
        self.assertEqual(prep_report["embedding_backend"], "google_gemini")
        self.assertEqual(len(cache_payload["entries"]), 1)

    def test_text_embedding_cache_reuses_prepared_vectors_without_reembedding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir)
            image_path = base_dir / "frame.png"
            Image.new("RGB", (16, 16), color=(255, 0, 0)).save(image_path)
            text_cache_path = base_dir / "text_cache.json"

            rows = [
                {
                    "example_id": "case_a",
                    "checkpoint": "confirmation",
                    "active_labels": ["order_block"],
                    "screenshot_path": str(image_path),
                    "transcript_text": "order block confirmation",
                }
            ]

            first_examples, _first_skipped, first_report = tbe.build_examples_from_google_embeddings(
                rows,
                label_to_index={"order_block": 0},
                output_dimensionality=EMBEDDING_DIM,
                text_embedding_cache_path=text_cache_path,
                visual_index_lookup={},
                text_embedder=fake_text_embedder,
                visual_embedder=fake_visual_embedder,
                audio_summarizer=fake_audio_summarizer,
            )

            def fail_embedder(texts: list[str]) -> list[list[float]]:
                raise AssertionError("text embedder should not be called when cache is warm")

            second_examples, _second_skipped, second_report = tbe.build_examples_from_google_embeddings(
                rows,
                label_to_index={"order_block": 0},
                output_dimensionality=EMBEDDING_DIM,
                text_embedding_cache_path=text_cache_path,
                visual_index_lookup={},
                text_embedder=fail_embedder,
                visual_embedder=fake_visual_embedder,
                audio_summarizer=fake_audio_summarizer,
            )

        self.assertEqual(first_report["transcript_cache_miss_count"], 1)
        self.assertEqual(second_report["transcript_cache_hit_count"], 1)
        self.assertEqual(first_examples[0]["transcript_embedding"], second_examples[0]["transcript_embedding"])

    def test_manifest_helpers_report_expected_counts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            manifest_path = Path(tmp_dir) / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "item_count": 3,
                        "model": "models/gemini-embedding-001",
                        "index_path": "knowledge/ttfm_video_corpus/google_embedding_index.json",
                    }
                ),
                encoding="utf-8",
            )

            self.assertTrue(tbe.manifest_matches_expected_count(manifest_path, expected_count=3))
            self.assertFalse(tbe.manifest_matches_expected_count(manifest_path, expected_count=4))
            description = tbe.describe_manifest(manifest_path)

        self.assertTrue(description["exists"])
        self.assertEqual(description["item_count"], 3)
        self.assertEqual(description["model"], "models/gemini-embedding-001")

    def test_manifest_helpers_require_matching_source_path_and_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir)
            source_path = base_dir / "chunks.jsonl"
            source_path.write_text('{"chunk_id": "case_a"}\n', encoding="utf-8")
            manifest_path = base_dir / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "item_count": 1,
                        "model": "models/gemini-embedding-001",
                        "index_path": "knowledge/ttfm_video_corpus/google_embedding_index.json",
                        "source_path": tbe.path_for_manifest(source_path),
                        "source_fingerprint": tbe.tve.fingerprint_file(source_path),
                    }
                ),
                encoding="utf-8",
            )

            self.assertTrue(
                tbe.manifest_matches_expected_count(
                    manifest_path,
                    expected_count=1,
                    source_path=source_path,
                )
            )
            description = tbe.describe_manifest(manifest_path)

            source_path.write_text(
                '{"chunk_id": "case_a"}\n{"chunk_id": "case_b"}\n',
                encoding="utf-8",
            )

            self.assertFalse(
                tbe.manifest_matches_expected_count(
                    manifest_path,
                    expected_count=1,
                    source_path=source_path,
                )
            )

        self.assertEqual(description["source_path"], tbe.path_for_manifest(source_path))
        self.assertIsNotNone(description["source_fingerprint"])

    def test_build_transcript_source_text_strips_label_hints(self) -> None:
        transcript_source_text = tbe.build_transcript_source_text(
            {
                "title": "Fractal Model Fundamentals",
                "checkpoint": "confirmation",
                "embedding_text": (
                    "Title: Fractal Model Fundamentals\n"
                    "Checkpoint: confirmation\n"
                    "Candidate labels: order_block, fair_value_gap\n"
                    "Labels: order_block\n"
                    "Transcript window: Price returns into the zone."
                ),
            }
        )

        self.assertIn("Checkpoint: confirmation", transcript_source_text)
        self.assertIn("Transcript window: Price returns into the zone.", transcript_source_text)
        self.assertNotIn("Candidate labels:", transcript_source_text)
        self.assertNotIn("Labels:", transcript_source_text)
        self.assertNotIn("order_block", transcript_source_text)

    def test_build_visual_embedding_text_omits_candidate_labels(self) -> None:
        embedding_text = tbe.tve.build_visual_embedding_text(
            title="Fractal Model Fundamentals",
            checkpoint="confirmation",
            topics=["daily_bias", "continuation"],
            text="Price returns into the fair value gap.",
            cue_terms=["retest", "entry"],
            candidate_labels=["order_block", "fair_value_gap"],
        )

        self.assertIn("Cue terms: retest, entry", embedding_text)
        self.assertNotIn("Candidate labels:", embedding_text)
        self.assertNotIn("order_block", embedding_text)


if __name__ == "__main__":
    unittest.main()
