import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from src.aura.gemini_production import write_json


MARKDOWN_PATTERNS = [
    re.compile(r"\*\*(.*?)\*\*"),
    re.compile(r"__(.*?)__"),
    re.compile(r"\*(.*?)\*"),
    re.compile(r"_(.*?)_"),
    re.compile(r"`([^`]+)`"),
]
MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+")
LIST_MARKER_RE = re.compile(r"^\s*([-*+]|\d+[.)])\s+")


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def strip_markdown(text: str) -> str:
    cleaned = text
    cleaned = MARKDOWN_LINK_RE.sub(r"\1", cleaned)
    cleaned = HEADING_RE.sub("", cleaned)
    cleaned = LIST_MARKER_RE.sub("", cleaned)
    for pattern in MARKDOWN_PATTERNS:
        cleaned = pattern.sub(r"\1", cleaned)
    cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
    return cleaned


def sanitize_aps_text(plan: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, str]]]:
    changes: List[Dict[str, str]] = []
    for scene in plan.get("scenes", []):
        for beat in scene.get("beats", []):
            original = beat.get("text")
            if not isinstance(original, str):
                continue
            cleaned = strip_markdown(original)
            if cleaned != original:
                beat["text"] = cleaned
                changes.append(
                    {
                        "scene_id": scene.get("scene_id", ""),
                        "beat_id": beat.get("beat_id", ""),
                        "before": original,
                        "after": cleaned,
                    }
                )
    return plan, changes


def main() -> None:
    parser = argparse.ArgumentParser(description="Strip non-spoken Markdown syntax from APS beat text.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    plan = load_json(args.input)
    plan, changes = sanitize_aps_text(plan)
    if changes:
        plan["_hygiene_changes"] = changes
    write_json(args.output, plan)
    print(f"Wrote sanitized APS: {args.output}")
    print(f"Changes: {len(changes)}")


if __name__ == "__main__":
    main()
