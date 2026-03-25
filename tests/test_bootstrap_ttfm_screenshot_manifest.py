from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import bootstrap_ttfm_screenshot_manifest as btsm


class ExtractAndFilterImageUrlsTests(unittest.TestCase):
    def test_extracts_upload_urls_and_filters_non_chart_assets(self) -> None:
        html = """
        <img src="https://ttrades.com/wp-content/uploads/2025/07/cropped-TTrades_Favicon-32x32.png" />
        <img src="https://ttrades.com/wp-content/uploads/2025/08/EQ-1.png" />
        <img src="/wp-content/uploads/2025/08/EQ-2.png" />
        <img srcset="https://ttrades.com/wp-content/uploads/2025/08/EQ-3.png 1920w, https://ttrades.com/wp-content/uploads/2025/08/EQ-3-300x169.png 300w" />
        """

        extracted = btsm.extract_upload_image_urls(
            html,
            source_url="https://ttrades.com/using-equilibrium-in-continuations/",
        )
        filtered = btsm.filter_chart_image_urls(extracted)

        self.assertIn("https://ttrades.com/wp-content/uploads/2025/08/EQ-1.png", filtered)
        self.assertIn("https://ttrades.com/wp-content/uploads/2025/08/EQ-2.png", filtered)
        self.assertIn("https://ttrades.com/wp-content/uploads/2025/08/EQ-3.png", filtered)
        self.assertNotIn(
            "https://ttrades.com/wp-content/uploads/2025/07/cropped-TTrades_Favicon-32x32.png",
            filtered,
        )


class BuildManifestTests(unittest.TestCase):
    def test_builds_checkpoint_attachments_from_downloaded_images(self) -> None:
        case_packet_report = {
            "case_packets": [
                {
                    "case_ref": "demo_case",
                    "topic": "continuation",
                    "source_url": "https://ttrades.com/using-equilibrium-in-continuations/",
                    "checkpoints": [
                        {"checkpoint": "context", "screenshot_path": None},
                        {"checkpoint": "sweep", "screenshot_path": None},
                        {"checkpoint": "closure", "screenshot_path": None},
                    ],
                }
            ]
        }
        html_by_url = {
            "https://ttrades.com/using-equilibrium-in-continuations/": """
                <img src="https://ttrades.com/wp-content/uploads/2025/08/EQ-1.png" />
                <img src="https://ttrades.com/wp-content/uploads/2025/08/EQ-2.png" />
                <img src="https://ttrades.com/wp-content/uploads/2025/08/EQ-3.png" />
            """
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            def fake_fetch(url: str) -> str:
                return html_by_url[url]

            def fake_download(url: str, destination: Path) -> None:
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(b"fake-image")

            manifest = btsm.build_screenshot_manifest(
                case_packet_report,
                root=root,
                fetch_html=fake_fetch,
                download_image=fake_download,
            )

            self.assertEqual(manifest["summary"]["attachment_count"], 3)
            self.assertEqual(manifest["summary"]["downloaded_image_count"], 3)
            first_attachment = manifest["attachments"][0]
            self.assertEqual(first_attachment["checkpoint"], "context")
            self.assertTrue(first_attachment["screenshot_path"].startswith("artifacts/ttfm/screenshots/demo_case/"))
            self.assertIn("requires visual review", first_attachment["annotation_notes"][0].lower())
            self.assertTrue((root / first_attachment["screenshot_path"]).exists())

    def test_existing_manifest_entries_are_preserved_on_rerun(self) -> None:
        case_packet_report = {
            "case_packets": [
                {
                    "case_ref": "demo_case",
                    "topic": "continuation",
                    "source_url": "https://ttrades.com/using-equilibrium-in-continuations/",
                    "checkpoints": [
                        {"checkpoint": "context", "screenshot_path": "artifacts/ttfm/screenshots/demo_case/context_EQ-1.png"},
                        {"checkpoint": "sweep", "screenshot_path": "artifacts/ttfm/screenshots/demo_case/sweep_EQ-2.png"},
                    ],
                }
            ]
        }
        existing_manifest = {
            "attachments": [
                {
                    "case_ref": "demo_case",
                    "checkpoint": "context",
                    "screenshot_path": "artifacts/ttfm/screenshots/demo_case/context_EQ-1.png",
                    "source_image_url": "https://ttrades.com/wp-content/uploads/2025/08/EQ-1.png",
                    "annotation_notes": ["existing context"],
                    "evidence_refs": ["https://ttrades.com/using-equilibrium-in-continuations/"],
                    "zone_geometry": None,
                },
                {
                    "case_ref": "demo_case",
                    "checkpoint": "sweep",
                    "screenshot_path": "artifacts/ttfm/screenshots/demo_case/sweep_EQ-2.png",
                    "source_image_url": "https://ttrades.com/wp-content/uploads/2025/08/EQ-2.png",
                    "annotation_notes": ["existing sweep"],
                    "evidence_refs": ["https://ttrades.com/using-equilibrium-in-continuations/"],
                    "zone_geometry": None,
                },
            ]
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for attachment in existing_manifest["attachments"]:
                destination = root / attachment["screenshot_path"]
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(b"existing-image")

            fetch_calls: list[str] = []

            def fake_fetch(url: str) -> str:
                fetch_calls.append(url)
                return ""

            def fake_download(url: str, destination: Path) -> None:
                raise AssertionError("Existing attachments should not be re-downloaded")

            manifest = btsm.build_screenshot_manifest(
                case_packet_report,
                root=root,
                existing_manifest=existing_manifest,
                fetch_html=fake_fetch,
                download_image=fake_download,
            )

            self.assertEqual(manifest["summary"]["attachment_count"], 2)
            self.assertEqual(manifest["summary"]["downloaded_image_count"], 0)
            self.assertEqual(fetch_calls, [])
            self.assertEqual(manifest["attachments"][0]["annotation_notes"], ["existing context"])


if __name__ == "__main__":
    unittest.main()
