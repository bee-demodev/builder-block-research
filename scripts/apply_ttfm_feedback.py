from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_QUEUE_PATH = ROOT / "data" / "ttfm_feedback_queue.json"


def timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def append_markdown_block(path: Path, lines: list[str]) -> None:
    ensure_parent(path)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    block = "\n".join(lines).rstrip() + "\n"
    if block.strip() in existing:
        return
    prefix = "\n" if existing and not existing.endswith("\n") else ""
    path.write_text(existing + prefix + block, encoding="utf-8")


def append_finding(root: Path, item: dict) -> None:
    path = root / str(item["target_path"])
    title = str(item.get("title", "TTFM Feedback")).strip()
    body = str(item.get("body", "")).strip()
    append_markdown_block(
        path,
        [
            f"## {title}",
            f"- Added by autonomous TTFM feedback on {timestamp()}.",
            f"- {body}",
        ],
    )


def append_open_question(root: Path, item: dict) -> None:
    path = root / str(item["target_path"])
    question = str(item.get("question", "")).strip()
    append_markdown_block(path, [f"- {question}"])


def append_draft_spec_question(root: Path, item: dict) -> None:
    path = root / str(item["target_path"])
    ensure_parent(path)
    spec = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    questions = spec.setdefault("open_implementation_questions", [])
    question_entry = {
        "question": str(item.get("question", "")).strip(),
        "affected_component": str(item.get("affected_component", "")).strip(),
        "topic_refs": [str(topic).strip() for topic in item.get("topic_refs", []) if str(topic).strip()],
    }
    if question_entry not in questions:
        questions.append(question_entry)
    path.write_text(json.dumps(spec, indent=2), encoding="utf-8")


def is_blocked_target(item: dict) -> bool:
    target_type = str(item.get("target_type", "")).strip()
    target_path = str(item.get("target_path", "")).strip().lower()
    return target_type == "rulebook" or target_path.endswith("rulebook.json")


def apply_feedback_queue(queue: dict, root: Path = ROOT) -> dict:
    applied: list[str] = []
    blocked: list[str] = []

    for item in queue.get("items", []):
        item_id = str(item.get("id", "")).strip() or "unknown"
        if is_blocked_target(item):
            blocked.append(item_id)
            continue

        target_type = str(item.get("target_type", "")).strip()
        if target_type == "finding":
            append_finding(root, item)
            applied.append(item_id)
        elif target_type == "open_question":
            append_open_question(root, item)
            applied.append(item_id)
        elif target_type == "draft_spec":
            append_draft_spec_question(root, item)
            applied.append(item_id)
        else:
            blocked.append(item_id)

    return {
        "applied_count": len(applied),
        "blocked_count": len(blocked),
        "applied_ids": applied,
        "blocked_ids": blocked,
    }


def load_queue(path: Path) -> dict:
    if not path.exists():
        return {"items": []}
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply safe TTFM feedback items to findings, draft specs, and topic open questions."
    )
    parser.add_argument("--queue", default=str(DEFAULT_QUEUE_PATH))
    parser.add_argument("--root", default=str(ROOT))
    args = parser.parse_args()

    result = apply_feedback_queue(load_queue(Path(args.queue)), Path(args.root))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
