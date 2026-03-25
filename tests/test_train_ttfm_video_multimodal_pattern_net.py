from __future__ import annotations

import math
import sys
import tempfile
import unittest
import wave
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import train_ttfm_video_multimodal_pattern_net as tmvpn


EMBEDDING_DIM = 4


def write_sine_wave(path: Path, *, frequency_hz: float, duration_seconds: float = 0.5) -> None:
    sample_rate = 16000
    amplitude = 12000
    sample_count = int(sample_rate * duration_seconds)
    samples = bytearray()
    for index in range(sample_count):
        value = int(amplitude * math.sin(2.0 * math.pi * frequency_hz * (index / sample_rate)))
        samples.extend(int(value).to_bytes(2, byteorder="little", signed=True))

    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(bytes(samples))


def fake_text_embedder(texts: list[str]) -> list[list[float]]:
    vectors: list[list[float]] = []
    for index, text in enumerate(texts):
        checksum = sum(ord(character) for character in text)
        vectors.append(
            [
                float((checksum % 11) + 1),
                float((len(text) % 7) + 1),
                float(index + 1),
                1.0,
            ]
        )
    return vectors


def fake_visual_embedder(asset_path: Path | None, text: str) -> tuple[list[float], bool]:
    stem = asset_path.stem if asset_path is not None else "missing"
    checksum = sum(ord(character) for character in f"{stem}:{text}")
    base = float((checksum % 5) + 1)
    return [base, base + 1.0, 0.5, 1.0], False


def fake_audio_summarizer(row: dict[str, object], audio_path: Path) -> tuple[str, str]:
    return (f"audio semantic summary for {row['example_id']}", "gemini_audio_summary")


def make_visual_index(path: Path) -> None:
    path.write_text(
        """
{
  "items": [
    {
      "chunk_id": "row_a",
      "vector": [9.0, 8.0, 7.0, 6.0]
    }
  ]
}
        """.strip(),
        encoding="utf-8",
    )


def make_rows(base_dir: Path) -> list[dict]:
    image_a = base_dir / "a.png"
    image_b = base_dir / "b.png"
    image_c = base_dir / "c.png"
    image_d = base_dir / "d.png"
    Image.new("RGB", (32, 32), color=(255, 0, 0)).save(image_a)
    Image.new("RGB", (32, 32), color=(0, 255, 0)).save(image_b)
    Image.new("RGB", (32, 32), color=(0, 0, 255)).save(image_c)
    Image.new("RGB", (32, 32), color=(255, 255, 0)).save(image_d)

    audio_a = base_dir / "a.wav"
    audio_b = base_dir / "b.wav"
    audio_c = base_dir / "c.wav"
    audio_d = base_dir / "d.wav"
    write_sine_wave(audio_a, frequency_hz=220.0)
    write_sine_wave(audio_b, frequency_hz=330.0)
    write_sine_wave(audio_c, frequency_hz=440.0)
    write_sine_wave(audio_d, frequency_hz=550.0)

    return [
        {
            "example_id": "row_a",
            "case_ref": "case_a",
            "checkpoint": "context",
            "active_labels": ["equilibrium", "point_of_interest"],
            "screenshot_path": str(image_a),
            "audio_path": str(audio_a),
            "transcript_text": "equilibrium and point of interest remain intact",
            "sample_weight": 1.0,
        },
        {
            "example_id": "row_b",
            "case_ref": "case_b",
            "checkpoint": "closure",
            "active_labels": ["equilibrium"],
            "screenshot_path": str(image_b),
            "audio_path": str(audio_b),
            "transcript_text": "equilibrium confirmation after closure",
            "sample_weight": 0.35,
        },
        {
            "example_id": "row_c",
            "case_ref": "case_c",
            "checkpoint": "sweep",
            "active_labels": ["liquidity_sweep"],
            "screenshot_path": str(image_c),
            "audio_path": str(audio_c),
            "transcript_text": "liquidity sweep and displacement appear together",
            "sample_weight": 0.35,
        },
        {
            "example_id": "row_d",
            "case_ref": "case_d",
            "checkpoint": "confirmation",
            "active_labels": ["point_of_interest", "liquidity_sweep"],
            "screenshot_path": str(image_d),
            "audio_path": str(audio_d),
            "transcript_text": "point of interest sweep gets confirmation",
            "sample_weight": 1.0,
        },
        {
            "example_id": "row_teacher_image_only",
            "case_ref": "case_e",
            "checkpoint": "outcome",
            "active_labels": ["point_of_interest"],
            "screenshot_path": str(image_d),
            "transcript_text": "",
            "sample_weight": 1.0,
        },
        {
            "example_id": "row_missing_audio_asset",
            "case_ref": "case_f",
            "checkpoint": "outcome",
            "active_labels": ["liquidity_sweep"],
            "screenshot_path": str(image_d),
            "audio_path": str(base_dir / "missing.wav"),
            "transcript_text": "missing audio should be skipped",
            "sample_weight": 1.0,
        },
    ]


class BuildExamplesTests(unittest.TestCase):
    def test_build_examples_uses_google_vector_contract_and_skips_missing_audio_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir)
            rows = make_rows(base_dir)
            visual_index_path = base_dir / "visual_index.json"
            audio_cache_path = base_dir / "audio_cache.json"
            make_visual_index(visual_index_path)
            label_to_index = {
                "equilibrium": 0,
                "liquidity_sweep": 1,
                "point_of_interest": 2,
            }

            examples, skipped, prep_report = tmvpn.build_examples(
                rows,
                label_to_index=label_to_index,
                output_dimensionality=EMBEDDING_DIM,
                visual_index_path=visual_index_path,
                audio_semantic_cache_path=audio_cache_path,
                text_embedder=fake_text_embedder,
                visual_embedder=fake_visual_embedder,
                audio_summarizer=fake_audio_summarizer,
            )

        self.assertEqual(len(examples), 5)
        self.assertEqual(len(skipped), 1)
        self.assertEqual(skipped[0]["reason"], "missing_audio_asset")
        self.assertEqual(prep_report["visual_index_hit_count"], 1)
        self.assertEqual(prep_report["audio_semantic_embedding_count"], 4)
        self.assertEqual(examples[0]["target"], [1.0, 0.0, 1.0])
        self.assertEqual(examples[0]["visual_embedding"], [9.0, 8.0, 7.0, 6.0])
        self.assertEqual(examples[0]["visual_embedding_source"], "visual_index")
        self.assertEqual(examples[1]["visual_embedding_source"], "direct_gemini_embed")
        self.assertEqual(examples[4]["has_audio"], False)
        self.assertEqual(examples[4]["has_audio_semantic"], False)
        self.assertTrue(examples[4]["has_transcript"])
        self.assertEqual(examples[4]["embedding_backend"], "google_gemini")


@unittest.skipIf(tmvpn.torch is None, "PyTorch is required for trainer tests.")
class TensorAndTrainingTests(unittest.TestCase):
    def build_examples_for_training(self, base_dir: Path) -> list[dict]:
        rows = make_rows(base_dir)
        visual_index_path = base_dir / "visual_index.json"
        audio_cache_path = base_dir / "audio_cache.json"
        make_visual_index(visual_index_path)
        label_to_index = {
            "equilibrium": 0,
            "liquidity_sweep": 1,
            "point_of_interest": 2,
        }
        examples, _skipped, _prep_report = tmvpn.build_examples(
            rows,
            label_to_index=label_to_index,
            output_dimensionality=EMBEDDING_DIM,
            visual_index_path=visual_index_path,
            audio_semantic_cache_path=audio_cache_path,
            text_embedder=fake_text_embedder,
            visual_embedder=fake_visual_embedder,
            audio_summarizer=fake_audio_summarizer,
        )
        return examples

    def test_build_tensors_creates_embedding_fusion_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            examples = self.build_examples_for_training(Path(tmp_dir))

            visuals, transcripts, audios, modalities, labels, weights = tmvpn.build_tensors(
                examples,
                device="cpu",
            )

        self.assertEqual(visuals.shape, (5, EMBEDDING_DIM))
        self.assertEqual(transcripts.shape, (5, EMBEDDING_DIM))
        self.assertEqual(audios.shape, (5, EMBEDDING_DIM))
        self.assertEqual(modalities.shape, (5, 3))
        self.assertEqual(labels.shape, (5, 3))
        self.assertAlmostEqual(float(weights[1].item()), 0.35, places=6)
        self.assertEqual(modalities[4].tolist(), [1.0, 1.0, 0.0])

    def test_train_multimodal_classifier_runs_smoke_training_with_embedding_fusion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir)
            examples = self.build_examples_for_training(base_dir)
            label_to_index = {
                "equilibrium": 0,
                "liquidity_sweep": 1,
                "point_of_interest": 2,
            }
            output_dir = base_dir / "models"

            report = tmvpn.train_multimodal_classifier(
                examples,
                label_to_index=label_to_index,
                output_dir=output_dir,
                model_name="smoke_multimodal",
                device_preference="cpu",
                validation_ratio=0.25,
                epochs=1,
                learning_rate=1e-3,
                batch_size=2,
                embedding_dim=EMBEDDING_DIM,
                seed=7,
                brain_type="setup_scorer",
                framework_slug="ttfm",
                profile_slug="ttrades_curriculum",
            )

            try:
                artifact = tmvpn.torch.load(Path(report["model_path"]), map_location="cpu", weights_only=False)
            except TypeError:
                artifact = tmvpn.torch.load(Path(report["model_path"]), map_location="cpu")
            self.assertTrue(Path(report["model_path"]).exists())
            self.assertEqual(report["model_name"], "smoke_multimodal")
            self.assertEqual(report["example_count"], 5)
            self.assertEqual(report["audio_semantic_example_count"], 4)
            self.assertEqual(report["embedding_backend"], "google_gemini")
            self.assertIn("best_prediction_threshold_mode", report)
            self.assertIn("best_prediction_thresholds", report)
            self.assertIn("average_setup_confidence", report["train_metrics"])
            self.assertEqual(artifact["model_type"], "GoogleEmbeddingFusionPatternNet")
            self.assertEqual(artifact["embedding_dim"], EMBEDDING_DIM)
            self.assertEqual(artifact["framework_slug"], "ttfm")


if __name__ == "__main__":
    unittest.main()
