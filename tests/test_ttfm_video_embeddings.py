from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import ttfm_video_embeddings as tve


class ResolveGoogleApiKeyTests(unittest.TestCase):
    def test_missing_google_api_key_raises_clean_error(self) -> None:
        previous = os.environ.pop("GOOGLE_API_KEY", None)
        previous_gemini = os.environ.pop("GEMINI_API_KEY", None)
        previous_google_genai = os.environ.pop("GOOGLE_GENAI_API_KEY", None)
        try:
            with self.assertRaisesRegex(
                RuntimeError,
                "GOOGLE_API_KEY|GEMINI_API_KEY|GOOGLE_GENAI_API_KEY",
            ):
                tve.resolve_google_api_key()
        finally:
            if previous is not None:
                os.environ["GOOGLE_API_KEY"] = previous
            if previous_gemini is not None:
                os.environ["GEMINI_API_KEY"] = previous_gemini
            if previous_google_genai is not None:
                os.environ["GOOGLE_GENAI_API_KEY"] = previous_google_genai

    def test_resolves_gemini_api_key_alias(self) -> None:
        resolved = tve.resolve_google_api_key(
            env={
                "GEMINI_API_KEY": "gemini-alias-key",
            }
        )

        self.assertEqual(resolved, "gemini-alias-key")

    def test_resolves_google_api_key_from_env_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env.local"
            env_path.write_text(
                "\n".join(
                    [
                        "# local dev credentials",
                        "GOOGLE_API_KEY=dotenv-google-key",
                    ]
                ),
                encoding="utf-8",
            )

            resolved = tve.resolve_google_api_key(env={}, env_files=[env_path])

        self.assertEqual(resolved, "dotenv-google-key")


class PrepareEmbeddingDocumentsTests(unittest.TestCase):
    def test_prepare_embedding_documents_preserves_chunk_metadata(self) -> None:
        rows = [
            {
                "video_slug": "fractal_model_fundamentals",
                "video_id": "TNybDCtwBnc",
                "title": "Fractal Model Fundamentals",
                "topics": ["daily_bias", "candle_2"],
                "start": 5.49,
                "end": 87.44,
                "text": "Daily bias comes first and Candle 2 is the swing point.",
            }
        ]

        documents = tve.prepare_embedding_documents(rows)

        self.assertEqual(len(documents), 1)
        self.assertEqual(documents[0]["chunk_id"], "fractal_model_fundamentals:0000")
        self.assertEqual(documents[0]["video_id"], "TNybDCtwBnc")
        self.assertEqual(documents[0]["topics"], ["daily_bias", "candle_2"])
        self.assertEqual(documents[0]["start"], 5.49)
        self.assertIn("Daily bias comes first", documents[0]["text"])


class QueryEmbeddingIndexTests(unittest.TestCase):
    def test_query_embedding_index_returns_ranked_matches_with_metadata(self) -> None:
        index = {
            "model": "models/gemini-embedding-001",
            "items": [
                {
                    "chunk_id": "daily_bias:0000",
                    "video_id": "vid-a",
                    "title": "Daily Bias",
                    "topics": ["daily_bias"],
                    "start": 10.0,
                    "end": 35.0,
                    "text": "Daily bias starts with the prior daily close.",
                    "vector": [1.0, 0.0],
                },
                {
                    "chunk_id": "candle3:0001",
                    "video_id": "vid-b",
                    "title": "Trading Candle 3",
                    "topics": ["candle_3"],
                    "start": 40.0,
                    "end": 72.0,
                    "text": "Candle 3 follows Candle 2 in the sequence.",
                    "vector": [0.0, 1.0],
                },
            ]
        }

        matches = tve.query_embedding_index(index, query_vector=[1.0, 0.0], top_k=2)

        self.assertEqual(matches[0]["chunk_id"], "daily_bias:0000")
        self.assertGreater(matches[0]["score"], matches[1]["score"])
        self.assertEqual(matches[0]["video_id"], "vid-a")
        self.assertEqual(matches[0]["topics"], ["daily_bias"])
        self.assertIn("prior daily close", matches[0]["text"])


class MultimodalEmbeddingHelpersTests(unittest.TestCase):
    def test_prepare_multimodal_embedding_documents_ignores_null_chart_crop_and_uses_frame(self) -> None:
        rows = [
            {
                "window_id": "youtube_fractal_model_visual_v1::confirmation",
                "video_slug": "fractal_model_fundamentals",
                "video_id": "TNybDCtwBnc",
                "title": "Fractal Model Fundamentals",
                "topics": ["daily_bias", "cisd"],
                "checkpoint": "confirmation",
                "start": 120.0,
                "end": 155.0,
                "nearby_transcript_text": "Order block confirmation after the closure.",
                "cue_terms": ["order block", "closure"],
                "candidate_labels": ["order_block"],
                "chart_crop_path": None,
                "frame_path": "knowledge/ttfm_video_corpus/frames/fractal_model_fundamentals/confirmation_00120000.jpg",
            }
        ]

        documents = tve.prepare_multimodal_embedding_documents(rows)

        self.assertEqual(len(documents), 1)
        self.assertEqual(
            Path(documents[0]["frame_path"]).as_posix(),
            "knowledge/ttfm_video_corpus/frames/fractal_model_fundamentals/confirmation_00120000.jpg",
        )
        self.assertNotIn("None", str(documents[0]["asset_path"]))

    def test_build_google_content_parts_includes_inline_data_for_assets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "frame.png"
            image_path.write_bytes(b"not-a-real-png-but-good-enough-for-base64")

            parts = tve.build_google_content_parts(
                text="Checkpoint frame with transcript context.",
                asset_path=image_path,
            )

        self.assertEqual(parts[0]["inline_data"]["mime_type"], "image/png")
        self.assertEqual(parts[1]["text"], "Checkpoint frame with transcript context.")
        self.assertTrue(parts[0]["inline_data"]["data"])

    def test_prepare_multimodal_embedding_documents_preserves_visual_metadata(self) -> None:
        rows = [
            {
                "window_id": "youtube_fractal_model_visual_v1::closure",
                "video_slug": "fractal_model_fundamentals",
                "video_id": "TNybDCtwBnc",
                "title": "Fractal Model Fundamentals",
                "topics": ["daily_bias", "cisd"],
                "checkpoint": "closure",
                "start": 120.0,
                "end": 155.0,
                "nearby_transcript_text": "Candle 2 closure and CISD confirm the state change.",
                "cue_terms": ["candle 2", "cisd"],
                "candidate_labels": ["candle_2_closure"],
                "frame_path": "artifacts/ttfm/youtube/frame.jpg",
            }
        ]

        documents = tve.prepare_multimodal_embedding_documents(rows)

        self.assertEqual(len(documents), 1)
        self.assertEqual(documents[0]["chunk_id"], "youtube_fractal_model_visual_v1::closure")
        self.assertEqual(documents[0]["checkpoint"], "closure")
        self.assertEqual(documents[0]["candidate_labels"], ["candle_2_closure"])
        self.assertEqual(
            Path(documents[0]["frame_path"]).as_posix(),
            "artifacts/ttfm/youtube/frame.jpg",
        )
        self.assertIn("Checkpoint: closure", documents[0]["embedding_text"])
        self.assertIn("CISD confirm the state change", documents[0]["embedding_text"])


if __name__ == "__main__":
    unittest.main()
