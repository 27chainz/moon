import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List

from src.aura.aps_compiler import (
    beat_render_text,
    display_name,
    is_speakable_beat,
    load_json,
    performance_for_tts,
    provider_voice,
    stable_voice,
)


PRESENCE_VERSION = "0.1"

SCENE_TYPE_KEYWORDS = {
    "battle": ["battle", "fight", "war", "soldier", "weapon", "blood"],
    "romance": ["romance", "kiss", "lover", "desire", "tender"],
    "mystery": ["mystery", "secret", "letter", "clue", "unknown"],
    "horror": ["horror", "terror", "dread", "haunted", "monster"],
    "suspense": ["hiding", "danger", "threat", "tense", "fear", "quiet"],
    "social": ["drawing-room", "banter", "party", "polished", "manners"],
    "calm": ["calm", "quiet", "peaceful", "rest"],
}

AMBIENCE_PRESETS = [
    ("forest", ["forest", "wood", "trees"], ["birds", "wind in trees"]),
    ("tavern", ["tavern", "inn", "public house"], ["low crowd", "hearth fire"]),
    ("cellar", ["cellar", "underground", "floorboards"], ["damp room tone", "distant floorboard creaks"]),
    ("drawing_room", ["drawing-room", "drawing room", "letter", "party"], ["quiet room tone", "paper and pen"]),
    ("battle", ["battle", "war", "fight"], ["distant chaos", "low impacts"]),
    ("rain", ["rain", "storm", "wet"], ["rainfall"]),
    ("ocean", ["ocean", "sea", "waves", "shore"], ["waves"]),
]

DEFAULT_SPATIAL_POSITIONS = {
    "narrator": "center",
    "ambience": "wide_background",
}


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def all_scene_text(scene: Dict[str, Any]) -> str:
    parts = [
        scene.get("title", ""),
        scene.get("summary", ""),
        scene.get("setting", ""),
        scene.get("mood", ""),
        scene.get("scene_context", ""),
        " ".join(scene.get("director_notes") or []),
    ]
    return " ".join(str(part).lower() for part in parts if part)


def has_keyword(text: str, keyword: str) -> bool:
    pattern = r"(?<![a-z0-9])" + re.escape(keyword.lower()) + r"(?![a-z0-9])"
    return re.search(pattern, text) is not None


def infer_scene_type(scene: Dict[str, Any]) -> str:
    explicit = scene.get("scene_type")
    if explicit:
        return explicit

    text = all_scene_text(scene)
    scores = {
        scene_type: sum(1 for keyword in keywords if has_keyword(text, keyword))
        for scene_type, keywords in SCENE_TYPE_KEYWORDS.items()
    }
    best_scene_type, score = max(scores.items(), key=lambda item: item[1])
    return best_scene_type if score else "general"


def infer_ambience(scene: Dict[str, Any]) -> Dict[str, Any]:
    explicit = scene.get("ambience") or scene.get("ambient_sound")
    if explicit:
        return explicit

    text = all_scene_text(scene)
    for ambience_id, keywords, loops in AMBIENCE_PRESETS:
        if any(has_keyword(text, keyword) for keyword in keywords):
            return {
                "ambience_id": ambience_id,
                "loops": loops,
                "level": "subtle",
                "notes": "Inferred from scene setting; keep below dialogue.",
            }

    return {
        "ambience_id": "room_tone",
        "loops": ["subtle room tone"],
        "level": "subtle",
        "notes": "Default bed; replace when scene setting is known.",
    }


def average_intensity(beats: List[Dict[str, Any]]) -> float:
    values = [
        float((beat.get("performance") or {}).get("intensity"))
        for beat in beats
        if (beat.get("performance") or {}).get("intensity") is not None
    ]
    if not values:
        return 0.4
    return round(sum(values) / len(values), 2)


def dominant_pace(beats: List[Dict[str, Any]]) -> str:
    values = [
        str((beat.get("performance") or {}).get("pacing", "")).strip()
        for beat in beats
        if str((beat.get("performance") or {}).get("pacing", "")).strip()
    ]
    if not values:
        return "normal"
    return Counter(values).most_common(1)[0][0]


def dialogue_positions(speaker_ids: Iterable[str]) -> Dict[str, str]:
    positions = {}
    sides = ["slightly_left", "slightly_right"]
    dialogue_index = 0
    for speaker_id in speaker_ids:
        if speaker_id == "narrator":
            positions[speaker_id] = DEFAULT_SPATIAL_POSITIONS["narrator"]
        else:
            positions[speaker_id] = sides[dialogue_index % len(sides)]
            dialogue_index += 1
    return positions


def speaker_ids_for(scene: Dict[str, Any]) -> List[str]:
    speaker_ids: List[str] = []
    for beat in scene.get("beats", []):
        speaker_id = beat.get("speaker", "narrator")
        if speaker_id not in speaker_ids:
            speaker_ids.append(speaker_id)
    return speaker_ids


def character_manifest(plan: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    manifest = {}
    for speaker_id, character in (plan.get("characters") or {}).items():
        manifest[speaker_id] = {
            "character_id": speaker_id,
            "name": character.get("display_name") or display_name(plan, speaker_id),
            "role": character.get("role", ""),
            "stable_voice": stable_voice(plan, speaker_id),
            "voice_id": character.get("voice_id", ""),
            "provider_voice": {
                "gemini": provider_voice(plan, speaker_id, "gemini", ""),
                "resemble": provider_voice(plan, speaker_id, "resemble", ""),
            },
            "do_not_change": character.get("do_not_change") or [],
        }
    return manifest


def segment_for(
    plan: Dict[str, Any],
    scene: Dict[str, Any],
    beat: Dict[str, Any],
    index: int,
    ambience: Dict[str, Any],
    positions: Dict[str, str],
) -> Dict[str, Any]:
    speaker_id = beat.get("speaker", "narrator")
    performance = performance_for_tts(beat)
    return {
        "segment_id": f"{scene.get('scene_id', 'scene')}_segment_{index:03d}",
        "source_beat_id": beat.get("beat_id"),
        "kind": beat.get("kind", "narration"),
        "speaker": speaker_id,
        "speaker_name": display_name(plan, speaker_id),
        "text": beat_render_text(beat),
        "speakable": is_speakable_beat(beat),
        "context": beat.get("context", ""),
        "performance": {
            "emotion": performance.get("emotion", "neutral"),
            "intensity": performance.get("intensity", 0.4),
            "pace": performance.get("pacing", "normal"),
            "delivery": performance.get("delivery", ""),
        },
        "audio": {
            "ambience": ambience,
            "spatial_position": positions.get(speaker_id, "center"),
            "sfx_cues": beat.get("sfx_cues") or beat.get("sfx") or [],
        },
    }


def scene_state(plan: Dict[str, Any], scene: Dict[str, Any]) -> Dict[str, Any]:
    beats = scene.get("beats", [])
    ambience = infer_ambience(scene)
    speaker_ids = speaker_ids_for(scene)
    positions = dialogue_positions(speaker_ids)
    positions["ambience"] = DEFAULT_SPATIAL_POSITIONS["ambience"]

    return {
        "scene_id": scene.get("scene_id"),
        "title": scene.get("title", ""),
        "summary": scene.get("summary", ""),
        "setting": scene.get("setting", ""),
        "scene_type": infer_scene_type(scene),
        "emotion": scene.get("emotion") or scene.get("mood", ""),
        "intensity": scene.get("intensity", average_intensity(beats)),
        "pace": scene.get("pace", dominant_pace(beats)),
        "ambience": ambience,
        "spatial_mix": scene.get("spatial_mix") or positions,
        "segments": [
            segment_for(plan, scene, beat, index, ambience, positions)
            for index, beat in enumerate(beats, start=1)
        ],
    }


def export_presence_state(plan: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "presence_version": PRESENCE_VERSION,
        "source": {
            "aps_version": plan.get("aps_version"),
            "book_id": plan.get("book_id"),
            "title": plan.get("title"),
            "chapter_id": plan.get("chapter_id"),
            "chapter_title": plan.get("chapter_title"),
        },
        "production_packet": plan.get("production_packet") or {},
        "characters": character_manifest(plan),
        "scenes": [scene_state(plan, scene) for scene in plan.get("scenes", [])],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Export APS into provider-neutral Presence production state.")
    parser.add_argument("--aps", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    plan = load_json(args.aps)
    write_json(args.output, export_presence_state(plan))
    print(f"Wrote Presence production state: {args.output}")


if __name__ == "__main__":
    main()
