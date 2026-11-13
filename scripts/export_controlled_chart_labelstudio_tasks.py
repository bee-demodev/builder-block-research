from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import YOLO_CLASS_NAMES


DEFAULT_INPUT_MANIFEST = Path("results") / "controlled_charts" / "controlled_chart_lineage_manifest.json"
DEFAULT_OUTPUT_DIR = Path("results") / "controlled_charts" / "label_studio"
REVIEW_ACTIONS = ("accept", "adjust", "reject", "defer")


def resolve(root_dir: Path, path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else root_dir / candidate


def relative_or_absolute(path: Path, root_dir: Path) -> str:
    try:
        return str(path.resolve().relative_to(root_dir.resolve()))
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def posix_path(value: str) -> str:
    return value.replace("\\", "/")


def label_config_xml() -> str:
    class_lines = "\n".join(
        f'    <Label value="{class_name}" background="#2B6CB0"/>'
        for class_name in YOLO_CLASS_NAMES
    )
    review_lines = "\n".join(
        f'    <Choice value="{action}"/>'
        for action in REVIEW_ACTIONS
    )
    return f"""<View>
  <Header value="Controlled raw-bar TTrades chart review"/>
  <Image name="image" value="$image"/>
  <Choices name="review_action" toName="image" choice="single-radio" required="true">
{review_lines}
  </Choices>
  <RectangleLabels name="detections" toName="image">
{class_lines}
  </RectangleLabels>
  <TextArea name="review_notes" toName="image" placeholder="Reason for accept, adjustment, rejection, or defer."/>
</View>
"""


def task_from_image(
    image: dict[str, Any],
    *,
    root_dir: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    image_path = resolve(root_dir, image["image_path"])
    relative_image_path = relative_or_absolute(image_path, root_dir)
    return {
        "id": image["image_id"],
        "data": {
            "image": posix_path(relative_image_path),
            "image_abs": str(image_path),
            "image_id": image["image_id"],
            "symbol": image["symbol"],
            "contract": image["contract"],
            "timeframe": image["timeframe"],
            "source_timeframe": image["source_timeframe"],
            "visible_range_start": image["visible_range"]["start"],
            "visible_range_end": image["visible_range"]["end"],
            "visible_bar_count": image["visible_range"]["bar_count"],
            "raw_timestamp_start": image["raw_timestamp_range"]["start"],
            "raw_timestamp_end": image["raw_timestamp_range"]["end"],
            "raw_row_count": image["raw_timestamp_range"]["row_count"],
            "session_dominant": image["session"]["dominant"],
            "session_values": ", ".join(image["session"]["values"]),
            "quality_filter_removed_ratio": image.get("quality_filter", {}).get("removed_ratio", 0),
            "lineage_manifest_path": posix_path(relative_or_absolute(manifest_path, root_dir)),
        },
        "meta": {
            "review_policy": "candidate_only",
            "training_eligible": False,
            "allowed_actions": list(REVIEW_ACTIONS),
            "source_csv_path": image.get("source_csv_path", ""),
            "source_raw_path": image.get("source_raw_path", ""),
            "quality_filter": image.get("quality_filter", {}),
        },
    }


def export_labelstudio_tasks(
    *,
    root_dir: Path,
    input_manifest_path: Path,
    output_dir: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    root_dir = root_dir.resolve()
    manifest_path = resolve(root_dir, input_manifest_path)
    output_dir = resolve(root_dir, output_dir)
    manifest = read_json(manifest_path)
    tasks: list[dict[str, Any]] = []
    missing_images: list[str] = []
    for item in manifest.get("items", []):
        for image in item.get("images", []):
            if image.get("status") != "captured":
                continue
            image_path = resolve(root_dir, str(image.get("image_path") or ""))
            if not image_path.exists():
                missing_images.append(str(image.get("image_id") or image_path))
                continue
            tasks.append(task_from_image(image, root_dir=root_dir, manifest_path=manifest_path))

    xml = label_config_xml()
    export_manifest = {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tool": "label_studio",
        "source_lineage_manifest": relative_or_absolute(manifest_path, root_dir),
        "output_dir": relative_or_absolute(output_dir, root_dir),
        "review_policy": {
            "candidate_only": True,
            "training_eligible_default": False,
            "allowed_actions": list(REVIEW_ACTIONS),
            "promotion_requires_visual_review": True,
        },
        "task_count": len(tasks),
        "missing_image_count": len(missing_images),
        "missing_images": missing_images,
        "label_config_path": relative_or_absolute(output_dir / "label_config.xml", root_dir),
        "tasks_path": relative_or_absolute(output_dir / "tasks.json", root_dir),
    }
    return export_manifest, tasks, xml


def write_outputs(
    export_manifest: dict[str, Any],
    tasks: list[dict[str, Any]],
    label_config: str,
    *,
    root_dir: Path,
    output_dir: Path,
) -> None:
    output_dir = resolve(root_dir, output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "manifest.json").write_text(json.dumps(export_manifest, indent=2) + "\n", encoding="utf-8")
    (output_dir / "tasks.json").write_text(json.dumps(tasks, indent=2) + "\n", encoding="utf-8")
    (output_dir / "label_config.xml").write_text(label_config, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export controlled chart lineage images to Label Studio tasks.")
    parser.add_argument("--root-dir", type=Path, default=Path("."))
    parser.add_argument("--input-manifest", type=Path, default=DEFAULT_INPUT_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root_dir = args.root_dir.resolve()
    export_manifest, tasks, label_config = export_labelstudio_tasks(
        root_dir=root_dir,
        input_manifest_path=args.input_manifest,
        output_dir=args.output_dir,
    )
    write_outputs(export_manifest, tasks, label_config, root_dir=root_dir, output_dir=args.output_dir)
    print(
        "Built Label Studio controlled chart export: "
        f"{relative_or_absolute(resolve(root_dir, args.output_dir) / 'tasks.json', root_dir)} "
        f"tasks={len(tasks)} missing_images={export_manifest['missing_image_count']}"
    )


if __name__ == "__main__":
    main()
