from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from export_ttfm_case_packets import (
    DEFAULT_OUTPUT as DEFAULT_CASE_PACKET_PATH,
    DEFAULT_SCREENSHOT_MANIFEST_PATH,
)


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SCREENSHOT_DIR = ROOT / "artifacts" / "ttfm" / "screenshots"
CHECKPOINT_SEQUENCE = ("context", "sweep", "closure", "confirmation", "outcome")
UPLOAD_IMAGE_PATTERN = re.compile(
    r"""(?P<url>(?:https?://[^"'\\s>]+)?/wp-content/uploads/[^"'\\s>,]+\.(?:png|jpg|jpeg|webp))""",
    re.IGNORECASE,
)
EXCLUDED_IMAGE_TOKENS = (
    "favicon",
    "cropped-",
    "logo",
    "apex",
    "journaling20trades",
)


def load_case_packet_report(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_existing_manifest(path: Path) -> dict:
    if not path.exists():
        return {"attachments": []}
    return json.loads(path.read_text(encoding="utf-8"))


def fetch_html(url: str) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            )
        },
    )
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def extract_upload_image_urls(html: str, *, source_url: str) -> list[str]:
    seen: set[str] = set()
    urls: list[str] = []
    for match in UPLOAD_IMAGE_PATTERN.finditer(html):
        candidate = urljoin(source_url, match.group("url"))
        if candidate not in seen:
            seen.add(candidate)
            urls.append(candidate)
    return urls


def filter_chart_image_urls(urls: list[str]) -> list[str]:
    filtered: list[str] = []
    seen: set[str] = set()
    for url in urls:
        filename = Path(urlparse(url).path).name.lower()
        if any(token in filename for token in EXCLUDED_IMAGE_TOKENS):
            continue
        if url not in seen:
            seen.add(url)
            filtered.append(url)
    return filtered


def sanitize_filename(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return safe or "image"


def default_download_image(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            )
        },
    )
    with urlopen(request, timeout=30) as response:
        destination.write_bytes(response.read())


def build_attachment_plan(case_packet: dict, image_urls: list[str], *, screenshot_root: Path) -> list[dict]:
    attachments: list[dict] = []
    pending_checkpoints = [
        checkpoint
        for checkpoint in case_packet.get("checkpoints", [])
        if checkpoint.get("checkpoint") in CHECKPOINT_SEQUENCE and not checkpoint.get("screenshot_path")
    ]
    for checkpoint, image_url in zip(pending_checkpoints, image_urls):
        checkpoint_name = str(checkpoint["checkpoint"])
        filename = sanitize_filename(Path(urlparse(image_url).path).name)
        relative_path = Path("artifacts") / "ttfm" / "screenshots" / case_packet["case_ref"] / f"{checkpoint_name}_{filename}"
        attachments.append(
            {
                "case_ref": case_packet["case_ref"],
                "checkpoint": checkpoint_name,
                "screenshot_path": relative_path.as_posix(),
                "source_image_url": image_url,
                "annotation_notes": [
                    (
                        f"Bootstrapped from source article image {filename}; "
                        "requires visual review before anchor promotion."
                    )
                ],
                "evidence_refs": [case_packet.get("source_url")] if case_packet.get("source_url") else [],
                "zone_geometry": None,
            }
        )
    return attachments


def index_attachments(manifest: dict | None) -> dict[tuple[str, str], dict]:
    indexed: dict[tuple[str, str], dict] = {}
    for attachment in (manifest or {}).get("attachments", []):
        case_ref = str(attachment.get("case_ref", "")).strip()
        checkpoint = str(attachment.get("checkpoint", "")).strip()
        if not case_ref or not checkpoint:
            continue
        indexed[(case_ref, checkpoint)] = attachment
    return indexed


def build_screenshot_manifest(
    case_packet_report: dict,
    *,
    root: Path = ROOT,
    existing_manifest: dict | None = None,
    fetch_html: Callable[[str], str] = fetch_html,
    download_image: Callable[[str, Path], None] = default_download_image,
) -> dict:
    attachments: list[dict] = []
    source_page_count = 0
    downloaded_image_count = 0
    existing_attachment_lookup = index_attachments(existing_manifest)

    for case_packet in case_packet_report.get("case_packets", []):
        source_url = str(case_packet.get("source_url", "")).strip()
        pending_checkpoints = [
            checkpoint
            for checkpoint in case_packet.get("checkpoints", [])
            if checkpoint.get("checkpoint") in CHECKPOINT_SEQUENCE
            and (case_packet.get("case_ref"), checkpoint.get("checkpoint")) not in existing_attachment_lookup
        ]

        html: str | None = None
        image_urls: list[str] = []
        if source_url and pending_checkpoints:
            html = fetch_html(source_url)
            source_page_count += 1
            image_urls = filter_chart_image_urls(extract_upload_image_urls(html, source_url=source_url))

        pending_attachment_lookup = {
            (attachment["case_ref"], attachment["checkpoint"]): attachment
            for attachment in build_attachment_plan(
                case_packet,
                image_urls,
                screenshot_root=DEFAULT_SCREENSHOT_DIR,
            )
        }

        for checkpoint in case_packet.get("checkpoints", []):
            checkpoint_name = str(checkpoint.get("checkpoint", "")).strip()
            if checkpoint_name not in CHECKPOINT_SEQUENCE:
                continue

            key = (case_packet.get("case_ref"), checkpoint_name)
            attachment = existing_attachment_lookup.get(key) or pending_attachment_lookup.get(key)
            if not attachment:
                continue

            destination = root / attachment["screenshot_path"]
            if not destination.exists() and attachment.get("source_image_url"):
                download_image(attachment["source_image_url"], destination)
                downloaded_image_count += 1
            attachments.append(attachment)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "source_page_count": source_page_count,
            "attachment_count": len(attachments),
            "downloaded_image_count": downloaded_image_count,
        },
        "attachments": attachments,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bootstrap TTFM screenshot manifest entries by downloading article-embedded chart images."
    )
    parser.add_argument("--case-packets", default=str(DEFAULT_CASE_PACKET_PATH))
    parser.add_argument("--output", default=str(DEFAULT_SCREENSHOT_MANIFEST_PATH))
    args = parser.parse_args()

    case_packet_report = load_case_packet_report(Path(args.case_packets))
    output_path = Path(args.output)
    manifest = build_screenshot_manifest(
        case_packet_report,
        existing_manifest=load_existing_manifest(output_path),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output_path),
                "attachment_count": manifest["summary"]["attachment_count"],
                "downloaded_image_count": manifest["summary"]["downloaded_image_count"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
