import argparse
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List

from src.aura.gemini_production import write_json


DEFAULT_DIRECTOR_MODEL = "gemini-2.5-flash"
APS_VERSION = "0.1"
DEFAULT_GEMINI_VOICES = [
    "Kore",
    "Charon",
    "Leda",
    "Aoede",
    "Fenrir",
    "Puck",
    "Algenib",
    "Orus",
]


DIRECTOR_SYSTEM_PROMPT = """You are Aster's Director.

Your job is to convert book chapter text into an Aster Performance Script (APS) for audiobook production.

Return ONLY valid JSON. Do not use Markdown. Do not wrap the response in ```json fences.

APS must match this exact top-level shape:

{
  "aps_version": "0.1",
  "book_id": "string",
  "title": "string",
  "chapter_id": "string",
  "chapter_title": "string",
  "production_packet": {
    "the_scene": "chapter-level dramatic and sensory context",
    "director_notes": ["performable audiobook direction"],
    "sample_context": "brief performance lane"
  },
  "characters": {
    "narrator": {
      "display_name": "Narrator",
      "role": "narrator",
      "stable_voice": "stable voice description",
      "provider_voice": {"gemini": "Kore"},
      "do_not_change": ["clarity", "base tone"],
      "voice_bible": "long-range voice consistency note",
      "golden_lines": ["short representative line"]
    }
  },
  "scenes": [
    {
      "scene_id": "scene_001",
      "title": "short scene title",
      "summary": "what happens emotionally and physically",
      "setting": "location/time if known",
      "mood": "performable mood words",
      "scene_context": "local context the Actor should understand",
      "director_notes": ["specific performable direction"],
      "sample_context": "local performance lane",
      "beats": [
        {
          "beat_id": "scene_001_beat_001",
          "kind": "narration or dialogue",
          "speaker": "narrator or stable_character_id",
          "text": "exact source text to speak",
          "context": "brief local context",
          "performance": {
            "emotion": "performable emotional state",
            "intensity": 0.0,
            "pacing": "slow, measured, natural, quick, breathless, etc.",
            "delivery": "brief performable vocal direction"
          }
        }
      ]
    }
  ]
}

Rules:
- Preserve source wording exactly inside every beat.text.
- Do not invent new spoken lines.
- Do not summarize source prose inside beat.text.
- Split narration and dialogue into separate beats.
- Use speaker "narrator" for narration.
- Use stable lowercase snake_case ids for characters.
- Include every spoken dialogue line.
- Keep beats renderable; split very long paragraphs into smaller narration beats.
- Put stage/performance direction in context/performance, never inside text.
- Do not use copyrighted-style imitation of living actors or celebrities.
- Use Gemini prebuilt voices from this pool: Kore, Charon, Leda, Aoede, Fenrir, Puck, Algenib, Orus.
- If uncertain about a speaker, use "unknown_speaker" and explain briefly in context.
- Make director_notes practical and audible, not literary analysis.
"""


def build_user_prompt(book_id: str, title: str, chapter_id: str, chapter_title: str, text: str) -> str:
    return f"""Create APS JSON for this chapter.

book_id: {book_id}
title: {title}
chapter_id: {chapter_id}
chapter_title: {chapter_title}

CHAPTER TEXT:
{text}
"""


def strip_json_fences(raw: str) -> str:
    value = raw.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", value, re.S | re.I)
    if fence:
        value = fence.group(1).strip()
    start = value.find("{")
    end = value.rfind("}")
    if start != -1 and end != -1 and end > start:
        value = value[start : end + 1]
    return value


def parse_json_response(raw: str) -> Dict[str, Any]:
    return json.loads(strip_json_fences(raw))


def validate_aps(plan: Dict[str, Any]) -> List[str]:
    warnings = []
    required = ["aps_version", "book_id", "title", "chapter_id", "chapter_title", "production_packet", "characters", "scenes"]
    for key in required:
        if key not in plan:
            raise ValueError(f"APS is missing required field: {key}")
    if plan["aps_version"] != APS_VERSION:
        warnings.append(f"Unexpected aps_version: {plan['aps_version']!r}")
    if "narrator" not in plan["characters"]:
        warnings.append("APS is missing narrator character.")
    if not plan["scenes"]:
        raise ValueError("APS has no scenes.")

    for scene_index, scene in enumerate(plan["scenes"], start=1):
        if not scene.get("beats"):
            warnings.append(f"Scene {scene.get('scene_id', scene_index)} has no beats.")
            continue
        for beat_index, beat in enumerate(scene["beats"], start=1):
            if beat.get("kind") not in {"narration", "dialogue"}:
                warnings.append(f"Beat {beat.get('beat_id', beat_index)} has unusual kind: {beat.get('kind')!r}")
            if not beat.get("speaker"):
                raise ValueError(f"Beat {beat.get('beat_id', beat_index)} is missing speaker.")
            if not beat.get("text"):
                raise ValueError(f"Beat {beat.get('beat_id', beat_index)} is missing text.")
            performance = beat.get("performance") or {}
            intensity = performance.get("intensity", 0.4)
            if not isinstance(intensity, (int, float)) or intensity < 0 or intensity > 1:
                warnings.append(f"Beat {beat.get('beat_id', beat_index)} intensity should be 0.0-1.0.")
    return warnings


def create_aps(
    chapter_text: str,
    book_id: str,
    title: str,
    chapter_id: str,
    chapter_title: str,
    model: str,
) -> Dict[str, Any]:
    if not os.getenv("GEMINI_API_KEY"):
        raise RuntimeError("Set GEMINI_API_KEY before running Gemini Director.")

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    response = client.models.generate_content(
        model=model,
        contents=build_user_prompt(book_id, title, chapter_id, chapter_title, chapter_text),
        config=types.GenerateContentConfig(
            system_instruction=DIRECTOR_SYSTEM_PROMPT,
            response_mime_type="application/json",
            temperature=0.3,
        ),
    )
    raw = response.text or ""
    plan = parse_json_response(raw)
    warnings = validate_aps(plan)
    if warnings:
        plan.setdefault("_director_warnings", warnings)
    return plan


def main() -> None:
    parser = argparse.ArgumentParser(description="Use Gemini to convert raw chapter text into APS JSON.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--book-id", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--chapter-id", required=True)
    parser.add_argument("--chapter-title", required=True)
    parser.add_argument("--model", default=DEFAULT_DIRECTOR_MODEL)
    args = parser.parse_args()

    chapter_text = args.input.read_text(encoding="utf-8")
    plan = create_aps(
        chapter_text=chapter_text,
        book_id=args.book_id,
        title=args.title,
        chapter_id=args.chapter_id,
        chapter_title=args.chapter_title,
        model=args.model,
    )
    write_json(args.output, plan)
    print(f"Wrote APS: {args.output}")


if __name__ == "__main__":
    main()
