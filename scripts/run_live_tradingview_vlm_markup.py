from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


from config import build_config
from scripts.build_live_tradingview_visual_markup import (
    DEFAULT_PACKET_PATH,
    DEFAULT_REQUEST_PATH,
    attach_visual_markup,
    build_markup_request,
    load_json,
    resolve,
    validate_visual_markup,
)


DEFAULT_MARKUP_OUTPUT_PATH = Path("results") / "live_tradingview_visual_markup.json"
DEFAULT_RAW_RESPONSE_PATH = Path("results") / "live_tradingview_visual_markup_response.json"
ResponsesPost = Callable[[dict[str, Any], str, int], dict[str, Any]]


def openai_api_key() -> str:
    return (
        os.getenv("OPENAI_API_KEY")
        or os.getenv("OPENAI_APIKEY")
        or os.getenv("OPENAI_KEY")
        or ""
    ).strip()


def encode_image_to_data_url(path: Path) -> str:
    mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def extract_response_text(payload: dict[str, Any]) -> str:
    output_text = str(payload.get("output_text", "")).strip()
    if output_text:
        return output_text
    chunks: list[str] = []
    for output_item in payload.get("output", []):
        if not isinstance(output_item, dict):
            continue
        for content in output_item.get("content", []):
            if not isinstance(content, dict):
                continue
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                chunks.append(str(content["text"]))
    return "\n".join(chunks).strip()


def parse_markup_text(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.lower().startswith("json"):
            stripped = stripped[4:].strip()
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start < 0 or end <= start:
            raise
        payload = json.loads(stripped[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("VLM markup response must be a JSON object.")
    return payload


def post_responses(payload: dict[str, Any], api_key: str, timeout_seconds: int) -> dict[str, Any]:
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:  # pragma: no cover - depends on live API
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"VLM markup failed with status {exc.code}: {details}") from exc
    except urllib.error.URLError as exc:  # pragma: no cover - depends on live API
        raise RuntimeError(f"VLM markup failed: {exc.reason}") from exc


def request_payload_for_markup(
    request: dict[str, Any],
    *,
    root_dir: Path,
    model: str,
) -> dict[str, Any]:
    user_content: list[dict[str, Any]] = [
        {
            "type": "input_text",
            "text": (
                "Return only JSON matching output_schema. "
                "Use visible evidence from the attached Daily, H1, and M5 screenshots. "
                "Do not make a trade decision; only produce visual_markup evidence.\n\n"
                f"{json.dumps(request, indent=2)}"
            ),
        }
    ]
    for image in request.get("images", []):
        if not isinstance(image, dict) or not image.get("path"):
            continue
        path = resolve(root_dir, str(image["path"]))
        if not path.exists():
            continue
        user_content.append(
            {
                "type": "input_text",
                "text": f"Image timeframe: {image.get('timeframe')}",
            }
        )
        user_content.append(
            {
                "type": "input_image",
                "image_url": encode_image_to_data_url(path),
                "detail": "high",
            }
        )
    return {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "You are a strict TTrades visual markup assistant. "
                            "Mark only evidence visible in the screenshots. "
                            "Never infer hidden context. Return only a JSON object."
                        ),
                    }
                ],
            },
            {
                "role": "user",
                "content": user_content,
            },
        ],
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def run_vlm_markup(
    *,
    packet_path: Path,
    request_path: Path,
    markup_output_path: Path,
    raw_response_path: Path,
    root_dir: Path,
    model: str,
    timeout_seconds: int,
    update_packet: bool = True,
    api_key: str | None = None,
    post_func: ResponsesPost = post_responses,
) -> dict[str, Any]:
    packet = load_json(packet_path, {})
    if not isinstance(packet, dict) or not packet:
        raise FileNotFoundError(f"Decision packet not found or invalid: {packet_path}")
    request = build_markup_request(packet, root_dir=root_dir, packet_path=packet_path)
    write_json(request_path, request)

    effective_key = (api_key if api_key is not None else openai_api_key()).strip()
    if not effective_key:
        result = {
            "mode": "live_tradingview_vlm_markup",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "missing_api_key",
            "request_path": str(request_path),
            "markup_output_path": str(markup_output_path),
            "raw_response_path": str(raw_response_path),
            "packet_updated": False,
            "message": "OPENAI_API_KEY is not configured; visual markup request was written but no VLM call was made.",
        }
        write_json(markup_output_path, result)
        return result

    api_payload = request_payload_for_markup(request, root_dir=root_dir, model=model)
    response_payload = post_func(api_payload, effective_key, timeout_seconds)
    write_json(raw_response_path, response_payload)
    response_text = extract_response_text(response_payload)
    raw_markup = parse_markup_text(response_text)
    validated = validate_visual_markup(raw_markup, packet)
    write_json(markup_output_path, validated)
    if update_packet:
        updated_packet = attach_visual_markup(packet, validated)
        write_json(packet_path, updated_packet)
    return {
        "mode": "live_tradingview_vlm_markup",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": validated["status"],
        "verified": validated["verified"],
        "request_path": str(request_path),
        "markup_output_path": str(markup_output_path),
        "raw_response_path": str(raw_response_path),
        "packet_updated": update_packet,
        "blocking_issues": validated["blocking_issues"],
        "validation_issues": validated["validation_issues"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Call an optional VLM to fill visual markup for a live TradingView decision packet.")
    parser.add_argument("--root-dir", type=Path, default=Path("."))
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    parser.add_argument("--request-output", type=Path, default=DEFAULT_REQUEST_PATH)
    parser.add_argument("--markup-output", type=Path, default=DEFAULT_MARKUP_OUTPUT_PATH)
    parser.add_argument("--raw-response", type=Path, default=DEFAULT_RAW_RESPONSE_PATH)
    parser.add_argument("--model", default=os.getenv("TTRADES_VLM_MODEL", "gpt-5.4-pro"))
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--no-update-packet", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root_dir = args.root_dir.resolve()
    build_config(root_dir=root_dir)
    result = run_vlm_markup(
        packet_path=resolve(root_dir, args.packet),
        request_path=resolve(root_dir, args.request_output),
        markup_output_path=resolve(root_dir, args.markup_output),
        raw_response_path=resolve(root_dir, args.raw_response),
        root_dir=root_dir,
        model=args.model,
        timeout_seconds=args.timeout_seconds,
        update_packet=not args.no_update_packet,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
