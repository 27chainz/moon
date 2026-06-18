import argparse
import copy
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict

from src.aura.gemini_production import GEMINI_VOICE_NAMES, write_json


CAST_BIBLE_VERSION = "0.1"
CAST_FIELDS = [
    "display_name",
    "role",
    "stable_voice",
    "provider_voice",
    "do_not_change",
    "voice_bible",
    "golden_lines",
    "approved_reference_note",
    "approved_reference_render",
    "accent_profile",
    "energy_profile",
    "tag_suppress",
]

ENFORCEMENT_RULES = {
    "override_from_cast_bible": [
        "provider_voice",
        "stable_voice",
        "voice_bible",
        "do_not_change",
        "accent_profile",
        "energy_profile",
        "tag_suppress",
        "approved_reference_note",
        "approved_reference_render",
    ],
    "preserve_from_chapter_aps": [
        "display_name",
        "role",
        "chapter_only_note",
        "scene-specific performance",
        "beat performance metadata",
    ],
    "manual_recast_required_for": [
        "provider_voice",
        "stable_voice",
        "voice_bible",
        "accent_profile",
        "energy_profile",
    ],
}


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def cast_entry(character: Dict[str, Any]) -> Dict[str, Any]:
    entry = {
        key: copy.deepcopy(character[key])
        for key in CAST_FIELDS
        if key in character and character[key] not in (None, "", [], {})
    }
    provider = entry.get("provider_voice") or {}
    gemini_voice = provider.get("gemini")
    if gemini_voice and gemini_voice not in GEMINI_VOICE_NAMES:
        raise ValueError(f"Unsupported Gemini voice in cast bible: {gemini_voice!r}")
    entry.setdefault("casting_lock", "stable")
    return entry


def extract_cast_bible(plan: Dict[str, Any]) -> Dict[str, Any]:
    characters = {
        character_id: cast_entry(character)
        for character_id, character in (plan.get("characters") or {}).items()
    }
    return {
        "cast_bible_version": CAST_BIBLE_VERSION,
        "book_id": plan.get("book_id"),
        "title": plan.get("title"),
        "source_chapter_id": plan.get("chapter_id"),
        "version_history": [
            {
                "version": CAST_BIBLE_VERSION,
                "date": date.today().isoformat(),
                "changed_by": "system",
                "change": f"Initial extraction from {plan.get('chapter_id') or 'unknown chapter'}",
                "affected_characters": sorted(characters.keys()),
            }
        ],
        "enforcement": copy.deepcopy(ENFORCEMENT_RULES),
        "rules": [
            "Use these cast entries as the source of truth for voice identity across chapters.",
            "Do not change provider_voice, stable_voice, voice_bible, accent_profile, or do_not_change unless a human approves a recast.",
            "Scene emotion may change, but base vocal identity must not.",
        ],
        "characters": characters,
    }


def apply_cast_bible(plan: Dict[str, Any], cast_bible: Dict[str, Any]) -> Dict[str, Any]:
    merged = copy.deepcopy(plan)
    merged.setdefault("characters", {})
    for character_id, locked_character in (cast_bible.get("characters") or {}).items():
        existing = merged["characters"].get(character_id, {})
        updated = copy.deepcopy(existing)
        for key in CAST_FIELDS:
            if key in locked_character:
                updated[key] = copy.deepcopy(locked_character[key])
        if "casting_lock" in locked_character:
            updated["casting_lock"] = locked_character["casting_lock"]
        merged["characters"][character_id] = updated

    merged["_cast_bible_applied"] = {
        "cast_bible_version": cast_bible.get("cast_bible_version"),
        "book_id": cast_bible.get("book_id"),
        "enforcement": copy.deepcopy(cast_bible.get("enforcement") or ENFORCEMENT_RULES),
        "character_ids": sorted((cast_bible.get("characters") or {}).keys()),
    }
    return merged


def mark_approved_reference_render(
    cast_bible: Dict[str, Any],
    character_id: str,
    chapter_id: str,
    chunk_id: str,
    notes: str = "",
) -> Dict[str, Any]:
    if character_id not in (cast_bible.get("characters") or {}):
        raise ValueError(f"Character {character_id!r} is not in the cast bible.")
    updated = copy.deepcopy(cast_bible)
    reference = {
        "chapter_id": chapter_id,
        "chunk_id": chunk_id,
        "render_date": date.today().isoformat(),
        "status": "approved",
    }
    if notes:
        reference["notes"] = notes
    updated["characters"][character_id]["approved_reference_render"] = reference
    updated.setdefault("version_history", []).append(
        {
            "version": updated.get("cast_bible_version", CAST_BIBLE_VERSION),
            "date": datetime.now(timezone.utc).isoformat(),
            "changed_by": "human",
            "change": f"Approved reference render set for {character_id}: {chapter_id}/{chunk_id}",
            "affected_characters": [character_id],
        }
    )
    return updated


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or apply an Aster cast bible.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    extract_parser = subparsers.add_parser("extract", help="Extract a cast bible from an APS file.")
    extract_parser.add_argument("--aps", required=True, type=Path)
    extract_parser.add_argument("--output", required=True, type=Path)

    apply_parser = subparsers.add_parser("apply", help="Apply a cast bible to an APS file.")
    apply_parser.add_argument("--aps", required=True, type=Path)
    apply_parser.add_argument("--cast-bible", required=True, type=Path)
    apply_parser.add_argument("--output", required=True, type=Path)

    approve_parser = subparsers.add_parser("approve-reference", help="Mark a cast member's approved reference render.")
    approve_parser.add_argument("--cast-bible", required=True, type=Path)
    approve_parser.add_argument("--character-id", required=True)
    approve_parser.add_argument("--chapter-id", required=True)
    approve_parser.add_argument("--chunk-id", required=True)
    approve_parser.add_argument("--notes", default="")
    approve_parser.add_argument("--output", type=Path)

    args = parser.parse_args()
    if args.command == "extract":
        plan = load_json(args.aps)
        write_json(args.output, extract_cast_bible(plan))
        print(f"Wrote cast bible: {args.output}")
        return

    if args.command == "apply":
        plan = load_json(args.aps)
        cast_bible = load_json(args.cast_bible)
        write_json(args.output, apply_cast_bible(plan, cast_bible))
        print(f"Wrote APS with cast bible applied: {args.output}")
        return

    if args.command == "approve-reference":
        cast_bible = load_json(args.cast_bible)
        output = args.output or args.cast_bible
        write_json(
            output,
            mark_approved_reference_render(
                cast_bible,
                args.character_id,
                args.chapter_id,
                args.chunk_id,
                args.notes,
            ),
        )
        print(f"Wrote cast bible reference approval: {output}")


if __name__ == "__main__":
    main()
