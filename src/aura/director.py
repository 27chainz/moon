import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class PerformanceCue:
    emotion: str = "neutral"
    intensity: float = 0.4
    pacing: str = "natural"
    delivery: str = "clear audiobook narration"


@dataclass
class StoryBeat:
    beat_id: str
    kind: str
    text: str
    speaker: str = "Narrator"
    performance: PerformanceCue = field(default_factory=PerformanceCue)
    context: str = ""


@dataclass
class ScenePlan:
    scene_id: str
    title: str
    summary: str
    setting: str = "unknown"
    beats: List[StoryBeat] = field(default_factory=list)


@dataclass
class PerformancePlan:
    book_id: str
    title: str
    scenes: List[ScenePlan]
    characters: Dict[str, Dict[str, str]] = field(default_factory=dict)


QUOTE_RE = re.compile(r'"([^"]+)"|“([^”]+)”')
SPEAKER_RE = re.compile(
    r"\b([A-Z][a-z]+)\s+(said|asked|whispered|shouted|replied|muttered|cried|called)\b"
)
NAME_RE = re.compile(r"\b([A-Z][a-z]+)\b")


def split_scenes(text: str) -> List[str]:
    chunks = [chunk.strip() for chunk in re.split(r"\n\s*\n+", text) if chunk.strip()]
    return chunks or [text.strip()]


def infer_speaker(after_quote: str, before_quote: str = "") -> str:
    match = SPEAKER_RE.search(after_quote)
    if match:
        return match.group(1)
    before_names = [name for name in NAME_RE.findall(before_quote) if name not in {"The", "A", "An"}]
    if before_names and re.search(r"\b(he|she|they)\s+(said|asked|whispered|shouted|replied|muttered|cried|called)\b", after_quote, re.I):
        return before_names[-1]
    return "Unknown"


def infer_cue(text: str, speaker_verb: str = "") -> PerformanceCue:
    lowered = text.lower()
    if any(word in lowered for word in ["afraid", "fear", "terrified", "stop", "please"]):
        return PerformanceCue("fear", 0.75, "breathless", "quiet panic")
    if any(word in lowered for word in ["angry", "rage", "furious", "shouted"]):
        return PerformanceCue("anger", 0.75, "fast", "sharp and forceful")
    if any(word in lowered for word in ["whisper", "quiet", "hush"]):
        return PerformanceCue("tension", 0.55, "slow", "low and quiet")
    if speaker_verb == "asked":
        return PerformanceCue("curious", 0.45, "natural", "questioning")
    return PerformanceCue()


def paragraph_to_beats(paragraph: str, scene_id: str) -> List[StoryBeat]:
    beats: List[StoryBeat] = []
    cursor = 0
    beat_index = 1
    for match in QUOTE_RE.finditer(paragraph):
        before = paragraph[cursor : match.start()].strip()
        if before:
            beats.append(
                StoryBeat(
                    beat_id=f"{scene_id}_beat_{beat_index:03d}",
                    kind="narration",
                    text=before,
                    speaker="Narrator",
                )
            )
            beat_index += 1

        dialogue = next(group for group in match.groups() if group).strip()
        if dialogue.endswith(","):
            dialogue = dialogue[:-1]
        speaker_window = paragraph[match.end() : match.end() + 90]
        speaker = infer_speaker(speaker_window, before)
        beats.append(
            StoryBeat(
                beat_id=f"{scene_id}_beat_{beat_index:03d}",
                kind="dialogue",
                text=dialogue,
                speaker=speaker,
                performance=infer_cue(dialogue, speaker_window.lower()),
            )
        )
        beat_index += 1
        cursor = match.end()

    remaining = paragraph[cursor:].strip()
    if remaining:
        beats.append(
            StoryBeat(
                beat_id=f"{scene_id}_beat_{beat_index:03d}",
                kind="narration",
                text=remaining,
                speaker="Narrator",
            )
        )
    return beats


def build_fallback_plan(text: str, book_id: str, title: str) -> PerformancePlan:
    scenes = []
    characters: Dict[str, Dict[str, str]] = {
        "Narrator": {"role": "narrator", "notes": "default narration voice"}
    }
    for index, paragraph in enumerate(split_scenes(text), start=1):
        scene_id = f"scene_{index:03d}"
        beats = paragraph_to_beats(paragraph, scene_id)
        for beat in beats:
            if beat.speaker not in characters:
                characters[beat.speaker] = {"role": "character", "notes": "needs casting review"}
        scenes.append(
            ScenePlan(
                scene_id=scene_id,
                title=f"Scene {index}",
                summary=paragraph[:180],
                beats=beats,
            )
        )
    return PerformancePlan(book_id=book_id, title=title, scenes=scenes, characters=characters)


def plan_to_dict(plan: PerformancePlan) -> Dict:
    return asdict(plan)


DIRECTOR_PROMPT = """You are Aster's Director layer.

Convert manuscript text into strict JSON matching this shape:

{
  "book_id": "string",
  "title": "string",
  "characters": {
    "character_name": {"role": "string", "notes": "string"}
  },
  "scenes": [
    {
      "scene_id": "scene_001",
      "title": "short title",
      "summary": "what is happening emotionally and physically",
      "setting": "location/time if known",
      "beats": [
        {
          "beat_id": "scene_001_beat_001",
          "kind": "narration|dialogue",
          "speaker": "Narrator or character name",
          "text": "exact words to render",
          "context": "brief local context",
          "performance": {
            "emotion": "neutral|fear|anger|grief|relief|tension|...",
            "intensity": 0.0,
            "pacing": "slow|natural|fast|breathless|deliberate",
            "delivery": "brief performable direction"
          }
        }
      ]
    }
  ]
}

Rules:
- Preserve exact spoken text.
- Do not invent dialogue.
- Split narration and dialogue into separate beats.
- Keep each beat short enough for audio rendering.
- Identify recurring characters by stable names.
- Use "Narrator" for prose narration.
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert manuscript text into an Aura performance plan.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--book-id", default="book_001")
    parser.add_argument("--title", default="Untitled Book")
    args = parser.parse_args()

    text = args.input.read_text(encoding="utf-8")
    plan = build_fallback_plan(text, args.book_id, args.title)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan_to_dict(plan), indent=2), encoding="utf-8")
    print(f"Wrote performance plan: {args.output}")


if __name__ == "__main__":
    main()
