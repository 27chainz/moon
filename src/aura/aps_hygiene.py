import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from src.aura.gemini_production import write_json


MARKDOWN_PATTERNS = [
    re.compile(r"\*\*(.*?)\*\*"),
    re.compile(r"__(.*?)__"),
    re.compile(r"(?<!\w)\*(.*?)\*(?!\w)"),
    re.compile(r"(?<!\w)_(.*?)_(?!\w)"),
    re.compile(r"`([^`]+)`"),
]
MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+")
LIST_MARKER_RE = re.compile(r"^\s*([-*+]|\d+[.)])\s+")
PUNCTUATION_REPLACEMENTS = {
    "\u2018": "'",
    "\u2019": "'",
    "\u201a": "'",
    "\u201b": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u201e": '"',
    "\u201f": '"',
    "\u2013": "-",
    "\u2014": "-",
    "\u2212": "-",
    "\u2026": "...",
    "\u00a0": " ",
}
MOJIBAKE_REPLACEMENTS = {
    "â€™": "'",
    "â€˜": "'",
    "â€œ": '"',
    "â€\u009d": '"',
    "â€": '"',
    "â€“": "-",
    "â€”": "-",
    "â€¦": "...",
}


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


def normalize_tts_punctuation(text: str) -> str:
    cleaned = text
    for before, after in MOJIBAKE_REPLACEMENTS.items():
        cleaned = cleaned.replace(before, after)
    for before, after in PUNCTUATION_REPLACEMENTS.items():
        cleaned = cleaned.replace(before, after)
    return cleaned


def normalize_json_strings(value: Any) -> Tuple[Any, int]:
    if isinstance(value, str):
        cleaned = normalize_tts_punctuation(value)
        return cleaned, int(cleaned != value)
    if isinstance(value, list):
        total = 0
        output = []
        for item in value:
            cleaned, changes = normalize_json_strings(item)
            output.append(cleaned)
            total += changes
        return output, total
    if isinstance(value, dict):
        total = 0
        output = {}
        for key, item in value.items():
            cleaned, changes = normalize_json_strings(item)
            output[key] = cleaned
            total += changes
        return output, total
    return value, 0


def sanitize_aps_text(plan: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, str]]]:
    changes: List[Dict[str, str]] = []
    for scene in plan.get("scenes", []):
        for beat in scene.get("beats", []):
            original = beat.get("text")
            if not isinstance(original, str):
                continue
            cleaned = strip_markdown(original)
            cleaned = normalize_tts_punctuation(cleaned)
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
    parser = argparse.ArgumentParser(description="Strip non-spoken Markdown syntax and unsafe punctuation from APS/production JSON.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--all-strings",
        action="store_true",
        help="Normalize punctuation in every JSON string, not only APS beat.text fields.",
    )
    args = parser.parse_args()

    plan = load_json(args.input)
    plan, changes = sanitize_aps_text(plan)
    all_string_changes = 0
    if args.all_strings:
        plan, all_string_changes = normalize_json_strings(plan)
    if changes:
        plan["_hygiene_changes"] = changes
    write_json(args.output, plan)
    print(f"Wrote sanitized APS: {args.output}")
    print(f"Beat text changes: {len(changes)}")
    print(f"All-string punctuation changes: {all_string_changes}")


if __name__ == "__main__":
    main()
