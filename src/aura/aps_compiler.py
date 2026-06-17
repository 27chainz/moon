import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List


CANONICAL_EMOTIONS = {
    "neutral",
    "fatigue",
    "irritation",
    "humour",
    "suspicion",
    "dread",
    "wonder",
    "horror",
    "panic",
    "fear",
    "anger",
    "grief",
    "relief",
    "tension",
    "calm",
    "urgency",
    "discovery",
    "alarm",
}

EMOTION_KEYWORDS = [
    ("fatigue", ("fatigue", "tired", "exhaustion", "weary")),
    ("irritation", ("irritation", "irritated", "impatience", "vexed")),
    ("humour", ("humour", "humor", "amusement", "wry", "teasing", "comic")),
    ("suspicion", ("suspicion", "suspense", "mystery", "unease", "warning")),
    ("dread", ("dread", "ominous")),
    ("wonder", ("wonder", "bright", "impossible", "awe")),
    ("horror", ("horror", "terror")),
    ("panic", ("panic", "panicked")),
    ("fear", ("fear", "frightened")),
    ("anger", ("anger", "angry")),
    ("grief", ("grief", "sad")),
    ("relief", ("relief",)),
    ("tension", ("tension", "tense", "threat")),
    ("calm", ("calm", "controlled")),
    ("urgency", ("urgency", "urgent")),
    ("discovery", ("discovery", "realization", "realisation")),
    ("alarm", ("alarm", "alarmed")),
]


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def character(plan: Dict[str, Any], speaker_id: str) -> Dict[str, Any]:
    return plan.get("characters", {}).get(speaker_id, {})


def display_name(plan: Dict[str, Any], speaker_id: str) -> str:
    return character(plan, speaker_id).get("display_name") or speaker_id.title()


def provider_voice(plan: Dict[str, Any], speaker_id: str, provider: str, fallback: str) -> str:
    voices = character(plan, speaker_id).get("provider_voice") or {}
    return voices.get(provider) or fallback


def stable_voice(plan: Dict[str, Any], speaker_id: str) -> str:
    return character(plan, speaker_id).get("stable_voice", "")


def normalize_emotion(value: Any, fallback: str = "neutral") -> str:
    text = str(value or "").strip().lower().replace("_", " ")
    if not text:
        return fallback
    if text in CANONICAL_EMOTIONS:
        return text
    for canonical, keywords in EMOTION_KEYWORDS:
        if any(keyword in text for keyword in keywords):
            return canonical
    return fallback


def performance_for_tts(beat: Dict[str, Any]) -> Dict[str, Any]:
    performance = beat.get("performance") or {}
    modifier = performance.get("beat_modifier", beat.get("beat_modifier", 0))
    try:
        intensity = float(performance.get("intensity", 0.4)) + float(modifier or 0)
    except (TypeError, ValueError):
        intensity = 0.4
    intensity = max(0.0, min(1.0, intensity))
    return {
        **performance,
        "emotion": normalize_emotion(performance.get("emotion")),
        "intensity": round(intensity, 2),
    }


def beat_render_text(beat: Dict[str, Any]) -> str:
    value = beat.get("render_text")
    if value is None:
        value = beat.get("text", "")
    return str(value)


def is_speakable_beat(beat: Dict[str, Any]) -> bool:
    if beat.get("speakable") is False:
        return False
    return bool(beat_render_text(beat).strip())


def beat_direction(beat: Dict[str, Any]) -> str:
    performance = performance_for_tts(beat)
    parts = [
        f"emotion {performance['emotion']}",
        f"intensity {performance['intensity']}",
        performance.get("pacing", ""),
        performance.get("delivery", ""),
        beat.get("context", ""),
    ]
    return ", ".join(part for part in parts if part)


def sentence_join(parts: List[str]) -> str:
    cleaned = []
    for part in parts:
        value = part.strip().rstrip(".")
        if value:
            cleaned.append(value)
    return ". ".join(cleaned)


def iter_beats(plan: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    for scene in plan.get("scenes", []):
        for beat in scene.get("beats", []):
            yield beat


def compile_resemble_prompts(plan: Dict[str, Any]) -> List[str]:
    prompts = []
    for beat in iter_beats(plan):
        if not is_speakable_beat(beat):
            continue
        speaker_id = beat.get("speaker", "narrator")
        speaker = display_name(plan, speaker_id)
        voice = provider_voice(plan, speaker_id, "resemble", stable_voice(plan, speaker_id))
        direction = beat_direction(beat)
        prefix = sentence_join([f"{speaker} is {voice}" if voice else speaker, direction])
        prompts.append(f'{prefix}. "{beat_render_text(beat)}"')
    return prompts


def compile_gemini_dialogue_request(plan: Dict[str, Any], scene_id: str, output_path: str) -> Dict[str, Any]:
    scene = next(scene for scene in plan["scenes"] if scene["scene_id"] == scene_id)
    dialogue_beats = [
        beat
        for beat in scene.get("beats", [])
        if beat.get("kind") == "dialogue" and is_speakable_beat(beat)
    ]
    speaker_ids = []
    for beat in dialogue_beats:
        if beat["speaker"] not in speaker_ids:
            speaker_ids.append(beat["speaker"])
    if len(speaker_ids) > 2:
        raise ValueError("Gemini multi-speaker requests support up to two speakers; split this scene first.")

    speaker_names = {speaker_id: display_name(plan, speaker_id) for speaker_id in speaker_ids}
    scene_direction = build_gemini_scene_packet(scene, plan, speaker_ids, speaker_names)
    compact_direction = sentence_join(
        [
            scene.get("summary", ""),
            *[
                f"{speaker_names[speaker_id]} should sound {stable_voice(plan, speaker_id)}"
                for speaker_id in speaker_ids
                if stable_voice(plan, speaker_id)
            ],
        ]
    )
    directions = []
    speaker_list = " and ".join(speaker_names[speaker_id] for speaker_id in speaker_ids)
    transcript_lines = [f"TTS the following conversation between {speaker_list}:"]
    for beat in dialogue_beats:
        tag = gemini_tone_tag(beat.get("performance") or {})
        if tag:
            transcript_lines.append(f"{speaker_names[beat['speaker']]}: [{tag}] {beat_render_text(beat)}")
        else:
            transcript_lines.append(f"{speaker_names[beat['speaker']]}: {beat_render_text(beat)}")
    transcript = "\n".join(transcript_lines)
    speaker_voices = {
        speaker_names[speaker_id]: provider_voice(plan, speaker_id, "gemini", "Kore")
        for speaker_id in speaker_ids
    }

    return {
        "output_file": output_path,
        "model": "gemini-2.5-pro-preview-tts",
        "chapter_context": scene_direction,
        "transcript": transcript,
        "speaker_voices": speaker_voices,
        "output_path": output_path,
        "performance": {
            "direction": compact_direction,
            "system_instruction": scene_direction,
            "transcript": transcript,
        },
        "speakers": [
            {
                "speaker": speaker_names[speaker_id],
                "voice_id": speaker_id,
                "provider_voice": provider_voice(plan, speaker_id, "gemini", "Kore"),
            }
            for speaker_id in speaker_ids
        ],
        "turns": [
            {
                "speaker": speaker_names[beat["speaker"]],
                "text": beat_render_text(beat),
            }
            for beat in dialogue_beats
        ],
    }


def gemini_tone_tag(performance: Dict[str, Any]) -> str:
    normalized = {
        **performance,
        "emotion": normalize_emotion(performance.get("emotion")),
    }
    parts = [
        f"emotion {normalized['emotion']}",
    ]
    if normalized.get("intensity") is not None:
        parts.append(f"intensity {normalized['intensity']}")
    for key in ["pacing", "delivery"]:
        value = str(normalized.get(key, "")).strip()
        if value:
            parts.append(value)
    return ", ".join(parts)


def build_gemini_scene_packet(
    scene: Dict[str, Any],
    plan: Dict[str, Any],
    speaker_ids: List[str],
    speaker_names: Dict[str, str],
) -> str:
    chapter_packet = plan.get("production_packet") or {}
    scene_context = scene.get("scene_context") or scene.get("summary") or ""
    notes = []
    notes.extend(chapter_packet.get("director_notes") or [])
    notes.extend(scene.get("director_notes") or [])
    for speaker_id in speaker_ids:
        voice = stable_voice(plan, speaker_id)
        if voice:
            notes.append(f"{speaker_names[speaker_id]} should sound {voice}.")
    sample_context = sentence_join(
        [
            chapter_packet.get("sample_context", ""),
            scene.get("sample_context") or scene.get("mood") or "",
        ]
    )

    sections = []
    if chapter_packet.get("the_scene"):
        sections.append(f"## CHAPTER CONTEXT\n{chapter_packet['the_scene']}")
    if scene_context:
        sections.append(f"## THE SCENE\n{scene_context}")
    if notes:
        sections.append("## DIRECTOR'S NOTES\n" + "\n".join(f"- {note}" for note in notes))
    if sample_context:
        sections.append(f"## SAMPLE CONTEXT\n{sample_context}")
    return "\n\n".join(sections)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compile APS into provider-specific practice artifacts.")
    parser.add_argument("--aps", required=True, type=Path)
    parser.add_argument("--provider", required=True, choices=["gemini", "resemble"])
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--scene-id", default="scene_001")
    parser.add_argument("--audio-output-path", default="data/generated_tests/aps_render.wav")
    args = parser.parse_args()

    plan = load_json(args.aps)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    if args.provider == "resemble":
        args.output.write_text("\n\n".join(compile_resemble_prompts(plan)), encoding="utf-8")
    else:
        request = compile_gemini_dialogue_request(plan, args.scene_id, args.audio_output_path)
        args.output.write_text(json.dumps(request, indent=2), encoding="utf-8")
    print(f"Wrote {args.provider} artifact: {args.output}")


if __name__ == "__main__":
    main()
