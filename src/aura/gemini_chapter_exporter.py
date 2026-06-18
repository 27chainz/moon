import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from src.aura.aps_compiler import (
    beat_render_text,
    build_gemini_scene_packet,
    display_name,
    gemini_tone_tag,
    is_speakable_beat,
    load_json,
    performance_for_tts,
    provider_voice,
)
from src.aura.cast_bible import apply_cast_bible
from src.aura.gemini_production import (
    GEMINI_MAX_SPEAKERS,
    GEMINI_TTS_MODEL,
    validate_gemini_tts_prompt,
)


MAX_GEMINI_SPEAKERS = GEMINI_MAX_SPEAKERS
DEFAULT_MODEL = GEMINI_TTS_MODEL
MAX_SUMMARY_CHARS = 220
SCENE_POSITIONS = ("opening", "rising", "turning_point", "resolution")
DEFAULT_GOLDEN_LINE_COUNT = 2
MAX_DIRECTOR_NOTES = 8
SENTENCE_ENDINGS = (".", "?", "!", '"', "'")
DEFAULT_MAX_CHUNK_WORDS = 230

TagRule = Tuple[Tuple[str, ...], Optional[str], float]

TAG_RULES: List[TagRule] = [
    (("whisper", "hushed", "quietly"), "[whispers]", 0.0),
    (("crying", "weeping", "tears"), "[crying]", 0.6),
    (("grief", "sorrow"), "[crying]", 0.75),
    (("sad", "sadness"), "[crying]", 0.85),
    (("trembling", "shaking", "suppressed grief", "holding back"), "[trembling]", 0.5),
    (("gasp", "sudden shock", "startled"), "[gasp]", 0.6),
    (("shock", "stunned", "disbelief"), "[trembling]", 0.6),
    (("panic", "panicked", "frantic", "breathless"), "[panicked]", 0.5),
    (("laughs", "giggle", "comic"), "[laughs]", 0.5),
    (("amused", "wry", "playful teasing"), "[mischievously]", 0.4),
    (("sarcastic", "bitter", "cutting"), "[sarcastic]", 0.5),
    (("dry", "understated", "ironic"), None, 0.0),
    (("excited", "eager", "upbeat"), "[excitedly]", 0.5),
    (("cheerful", "bright"), "[excitedly]", 0.65),
    (("serious", "grave", "solemn"), "[serious]", 0.6),
    (("tired", "exhausted"), "[tired]", 0.6),
    (("weary", "resignation", "weary acceptance"), None, 0.0),
    (("curious", "wondering", "puzzled"), "[curious]", 0.4),
    (("amazed", "wonder", "awe"), "[amazed]", 0.5),
    (("sighs", "resigned acceptance"), "[sighs]", 0.4),
    (("mischievous", "teasing"), "[mischievously]", 0.4),
    (("angry", "furious", "hostile"), "[shouting]", 0.85),
]


def speaker_ids_for(beats: Iterable[Dict[str, Any]]) -> List[str]:
    speaker_ids: List[str] = []
    for beat in beats:
        if not is_speakable_beat(beat):
            continue
        speaker_id = beat.get("speaker", "narrator")
        if speaker_id not in speaker_ids:
            speaker_ids.append(speaker_id)
    return speaker_ids


def beat_word_count(beat: Dict[str, Any]) -> int:
    return len(beat_render_text(beat).split())


def split_scene_beats(
    scene: Dict[str, Any],
    max_chunk_words: Optional[int] = DEFAULT_MAX_CHUNK_WORDS,
) -> List[List[Dict[str, Any]]]:
    chunks: List[List[Dict[str, Any]]] = []
    current: List[Dict[str, Any]] = []
    current_speakers: List[str] = []
    current_words = 0

    for beat in scene.get("beats", []):
        if not is_speakable_beat(beat):
            continue
        speaker_id = beat.get("speaker", "narrator")
        words = beat_word_count(beat)
        next_speakers = list(current_speakers)
        if speaker_id not in next_speakers:
            next_speakers.append(speaker_id)

        exceeds_speaker_limit = len(next_speakers) > MAX_GEMINI_SPEAKERS
        exceeds_word_budget = bool(max_chunk_words) and current_words + words > max_chunk_words
        if current and (exceeds_speaker_limit or exceeds_word_budget):
            chunks.append(current)
            current = []
            current_speakers = []
            current_words = 0

        current.append(beat)
        current_words += words
        if speaker_id not in current_speakers:
            current_speakers.append(speaker_id)

    if current:
        chunks.append(current)

    return chunks


def compact_text(text: str, max_chars: int = MAX_SUMMARY_CHARS) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 3].rstrip() + "..."


def performance_summary(beat: Dict[str, Any]) -> str:
    performance = performance_for_tts(beat)
    parts = [
        f"emotion {performance['emotion']}",
        f"intensity {performance['intensity']}",
        performance.get("pacing", ""),
        performance.get("delivery", ""),
    ]
    return ", ".join(str(part).strip() for part in parts if str(part).strip())


def beat_summary(plan: Dict[str, Any], beat: Dict[str, Any]) -> str:
    speaker = display_name(plan, beat.get("speaker", "narrator"))
    perf = performance_summary(beat)
    text = compact_text(beat_render_text(beat), 140)
    if perf:
        return f"{speaker}: {perf}. Line: {text}"
    return f"{speaker}: {text}"


def summarize_beats(plan: Dict[str, Any], beats: List[Dict[str, Any]], limit: int = 3) -> List[str]:
    if not beats:
        return []
    selected = beats[-limit:]
    return [beat_summary(plan, beat) for beat in selected]


def build_voice_locks(plan: Dict[str, Any], speaker_ids: List[str]) -> List[str]:
    locks = []
    for speaker_id in speaker_ids:
        speaker = display_name(plan, speaker_id)
        character = plan.get("characters", {}).get(speaker_id, {})
        stable = character.get("stable_voice", "")
        do_not_change = character.get("do_not_change") or []
        voice = provider_voice(plan, speaker_id, "gemini", "Kore")
        lock = f"{speaker} uses Gemini voice {voice}"
        if stable:
            lock += f" and must stay {stable}"
        if do_not_change:
            lock += f". Do not change: {', '.join(do_not_change)}"
        locks.append(lock + ".")
    return locks


def build_voice_bible_lines(plan: Dict[str, Any], speaker_ids: List[str]) -> List[str]:
    golden_lines = collect_golden_lines(plan)
    lines = []
    for speaker_id in speaker_ids:
        bible = character_voice_bible(plan, speaker_id, golden_lines.get(speaker_id, []))
        parts = [
            f"{bible['display_name']}: {bible['voice_bible']}",
            f"Gemini voice {bible['provider_voice']}",
        ]
        if bible["approved_reference_note"]:
            parts.append(f"approved note: {bible['approved_reference_note']}")
        if bible["golden_lines"]:
            parts.append(f"golden line: {bible['golden_lines'][0]}")
        lines.append("; ".join(part for part in parts if part))
    return lines


def speaker_aliases(speaker_ids: List[str]) -> Dict[str, str]:
    return {
        speaker_id: f"Speaker{index}"
        for index, speaker_id in enumerate(speaker_ids, start=1)
    }


def dedupe_lines(lines: Iterable[str], limit: int = MAX_DIRECTOR_NOTES) -> List[str]:
    output: List[str] = []
    seen = set()
    for line in lines:
        cleaned = " ".join(str(line).split())
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        output.append(cleaned)
        seen.add(key)
        if len(output) >= limit:
            break
    return output


def performance_audio_tags(
    performance: Dict[str, Any],
    suppressed_tags: Iterable[str] = (),
) -> str:
    text = " ".join(
        str(performance.get(key, "")).lower()
        for key in ("emotion", "pacing", "delivery")
    )
    try:
        intensity = float(performance.get("intensity", 0.0))
    except (TypeError, ValueError):
        intensity = 0.0
    suppressed = set(suppressed_tags)
    tags: List[str] = []
    for keywords, tag, min_intensity in TAG_RULES:
        if not any(keyword in text for keyword in keywords):
            continue
        if intensity < min_intensity:
            continue
        if tag is None:
            continue
        if tag == "[trembling]" and "[gasp]" in tags:
            continue
        if tag not in suppressed and tag not in tags:
            tags.append(tag)
        if len(tags) >= 2:
            break
    return " ".join(tags)


def collect_golden_lines(plan: Dict[str, Any], limit: int = DEFAULT_GOLDEN_LINE_COUNT) -> Dict[str, List[str]]:
    lines: Dict[str, List[str]] = {
        speaker_id: list(character.get("golden_lines") or [])
        for speaker_id, character in (plan.get("characters") or {}).items()
    }
    for scene in plan.get("scenes", []):
        for beat in scene.get("beats", []):
            if not is_speakable_beat(beat):
                continue
            speaker_id = beat.get("speaker", "narrator")
            speaker_lines = lines.setdefault(speaker_id, [])
            text = " ".join(beat_render_text(beat).split())
            if text and text not in speaker_lines and len(speaker_lines) < limit:
                speaker_lines.append(text)
    return {speaker_id: values[:limit] for speaker_id, values in lines.items()}


def character_voice_bible(plan: Dict[str, Any], speaker_id: str, golden_lines: List[str]) -> Dict[str, Any]:
    character = plan.get("characters", {}).get(speaker_id, {})
    return {
        "character_id": speaker_id,
        "display_name": display_name(plan, speaker_id),
        "role": character.get("role", ""),
        "provider_voice": provider_voice(plan, speaker_id, "gemini", "Kore"),
        "voice_bible": character.get("voice_bible") or character.get("stable_voice", ""),
        "do_not_change": character.get("do_not_change") or [],
        "accent_profile": character.get("accent_profile") or {},
        "energy_profile": character.get("energy_profile") or {},
        "tag_suppress": character.get("tag_suppress") or [],
        "approved_reference_note": character.get("approved_reference_note", ""),
        "approved_reference_render": character.get("approved_reference_render") or {},
        "golden_lines": golden_lines,
    }


def build_audio_profile(plan: Dict[str, Any], speaker_ids: List[str], aliases: Dict[str, str]) -> str:
    golden_lines = collect_golden_lines(plan)
    sections = []
    for speaker_id in speaker_ids:
        bible = character_voice_bible(plan, speaker_id, golden_lines.get(speaker_id, []))
        alias = aliases[speaker_id]
        title = bible["display_name"]
        lines = [
            f"# AUDIO PROFILE: {alias} ({title})",
            f"Gemini voice: {bible['provider_voice']}",
            "Casting lock: This is a stable cast voice. Keep the same vocal identity every time this character appears; do not reinterpret the voice between chunks.",
        ]
        if bible["role"]:
            lines.append(f"Role: {bible['role']}")
        if bible["voice_bible"]:
            lines.append(f"Voice identity: {bible['voice_bible']}")
        if bible["do_not_change"]:
            lines.append(f"Do not change: {', '.join(bible['do_not_change'])}")
        accent_profile = bible.get("accent_profile") or {}
        if accent_profile:
            label = accent_profile.get("label")
            features = accent_profile.get("features") or []
            avoid = accent_profile.get("avoid") or []
            if label:
                lines.append(f"Accent profile: {label}")
            if features:
                lines.append(f"Accent features: {', '.join(features)}")
            if avoid:
                lines.append(f"Accent avoid: {', '.join(avoid)}")
        if bible["approved_reference_note"]:
            lines.append(f"Approved reference note: {bible['approved_reference_note']}")
        energy_profile = bible.get("energy_profile") or {}
        if energy_profile:
            if energy_profile.get("baseline_intensity") is not None:
                lines.append(f"Energy baseline: {energy_profile['baseline_intensity']}")
            if energy_profile.get("entry_instruction"):
                lines.append(f"Energy entry: {energy_profile['entry_instruction']}")
            if energy_profile.get("do_not_do"):
                lines.append(f"Energy avoid: {', '.join(energy_profile['do_not_do'])}")
        approved_reference_render = bible.get("approved_reference_render") or {}
        if approved_reference_render and approved_reference_render.get("status") == "approved":
            reference_bits = [
                approved_reference_render.get("chapter_id"),
                approved_reference_render.get("chunk_id"),
                approved_reference_render.get("notes"),
            ]
            lines.append(
                "Approved reference render: "
                + " | ".join(str(bit) for bit in reference_bits if bit)
            )
        if bible["golden_lines"]:
            lines.append("Golden reference lines:")
            lines.extend(f'- "{line}"' for line in bible["golden_lines"])
        sections.append("\n".join(lines))
    return "\n\n".join(sections)


def build_scene_section(scene: Dict[str, Any], plan: Dict[str, Any]) -> str:
    packet = plan.get("production_packet") or {}
    scene_bits = [
        scene.get("scene_context"),
        scene.get("summary"),
        packet.get("the_scene"),
    ]
    context = next((str(bit).strip() for bit in scene_bits if str(bit or "").strip()), "")
    setting = scene.get("setting")
    mood = scene.get("mood")
    title = scene.get("title") or plan.get("chapter_title") or "Scene"

    lines = [f"## THE SCENE: {title}"]
    if setting:
        lines.append(f"Setting: {setting}")
    if mood:
        lines.append(f"Mood: {mood}")
    if context:
        lines.append(context)
    return "\n".join(lines)


def build_prompt_continuity_notes(
    plan: Dict[str, Any],
    previous_beats: List[Dict[str, Any]],
    current_beats: List[Dict[str, Any]],
    chunk_index_in_scene: int,
    scene_chunk_count: int,
) -> List[str]:
    speaker_ids = speaker_ids_for(current_beats)
    if chunk_index_in_scene <= 1 or not previous_beats:
        notes = ["This is the first render chunk for this scene. Establish the scene tone without rushing."]
        for speaker_id in speaker_ids:
            character_name = display_name(plan, speaker_id)
            previous_speaker_beat = latest_speaker_beat(speaker_id, previous_beats)
            if previous_speaker_beat:
                notes.append(
                    f"Voice continuity lock for {character_name}: use the exact same character voice as earlier chunks; "
                    "do not reinterpret this character because this is a new scene."
                )
            else:
                notes.append(
                    f"{character_name} is a locked cast voice. Do not invent a new voice for this character."
                )
        return notes

    previous = latest_speaker_beat(
        current_beats[0].get("speaker", "narrator"),
        previous_beats,
    )
    previous_note = beat_summary(plan, previous) if previous else beat_summary(plan, previous_beats[-1])
    position = scene_position(chunk_index_in_scene, scene_chunk_count)
    notes = [
        f"This chunk continues an already-started scene at the {position} point; enter as if already mid-scene, not as a fresh take.",
        f"Enter with the same vocal level, pace, and emotional temperature as the previous moment: {previous_note}",
        "Match the previous chunk's restraint, volume, pace, and vocal colour at the start of this chunk.",
        "Do not brighten, accelerate, increase volume, or become more theatrical just because this is a new audio request.",
    ]
    for speaker_id in speaker_ids:
        previous_speaker_beat = latest_speaker_beat(speaker_id, previous_beats)
        character_name = display_name(plan, speaker_id)
        if previous_speaker_beat:
            notes.append(
                f"Voice continuity lock for {character_name}: use the exact same character voice as earlier chunks; "
                "do not reinterpret this character because the co-speaker, scene, or emotional beat changed."
            )
        else:
            notes.append(
                f"Voice continuity lock for {character_name}: establish this as a stable cast voice for all future chunks."
            )
    return notes


def build_director_notes(
    scene: Dict[str, Any],
    plan: Dict[str, Any],
    continuity_notes: Optional[List[str]] = None,
) -> str:
    packet = plan.get("production_packet") or {}
    notes = dedupe_lines(
        [
            "The following is a speech synthesis request. Do not read these instructions aloud.",
            "Begin speaking only when you reach TRANSCRIPT.",
            *(continuity_notes or []),
            *list(packet.get("director_notes") or []),
            *list(scene.get("director_notes") or []),
            "Keep the transcript exact. Do not add, remove, modernize, or summarize spoken words.",
            "Use audio tags as performance cues, not as literal words.",
        ],
        limit=MAX_DIRECTOR_NOTES + 3,
    )
    return "### DIRECTOR'S NOTES\n" + "\n".join(f"* {note}" for note in notes)


def build_sample_context(scene: Dict[str, Any], plan: Dict[str, Any]) -> str:
    packet = plan.get("production_packet") or {}
    samples = dedupe_lines(
        [packet.get("sample_context", ""), scene.get("sample_context", "")],
        limit=3,
    )
    if not samples:
        samples = ["Audiobook performance with consistent character identity and natural scene continuity."]
    return "### SAMPLE CONTEXT\n" + "\n".join(samples)


def build_prompt_transcript(plan: Dict[str, Any], beats: List[Dict[str, Any]], aliases: Dict[str, str]) -> str:
    lines = ["#### TRANSCRIPT"]
    for beat in beats:
        speaker_id = beat.get("speaker", "narrator")
        alias = aliases[speaker_id]
        character = plan.get("characters", {}).get(speaker_id, {})
        tag = performance_audio_tags(
            performance_for_tts(beat),
            character.get("tag_suppress") or (),
        )
        text = beat_render_text(beat)
        if tag:
            lines.append(f"{alias}: {tag} {text}")
        else:
            lines.append(f"{alias}: {text}")
    return "\n".join(lines)


def build_tts_prompt(
    plan: Dict[str, Any],
    scene: Dict[str, Any],
    beats: List[Dict[str, Any]],
    speaker_ids: List[str],
    aliases: Dict[str, str],
    previous_beats: Optional[List[Dict[str, Any]]] = None,
    chunk_index_in_scene: int = 1,
    scene_chunk_count: int = 1,
) -> str:
    continuity_notes = build_prompt_continuity_notes(
        plan,
        previous_beats or [],
        beats,
        chunk_index_in_scene,
        scene_chunk_count,
    )
    return "\n\n".join(
        [
            build_audio_profile(plan, speaker_ids, aliases),
            build_scene_section(scene, plan),
            build_director_notes(scene, plan, continuity_notes),
            build_sample_context(scene, plan),
            build_prompt_transcript(plan, beats, aliases),
        ]
    )


def build_character_voice_bibles(plan: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    golden_lines = collect_golden_lines(plan)
    return {
        speaker_id: character_voice_bible(plan, speaker_id, golden_lines.get(speaker_id, []))
        for speaker_id in (plan.get("characters") or {})
    }


def scene_position(chunk_index: int, chunk_count: int) -> str:
    if chunk_count <= 1:
        return "complete_scene"
    ratio = chunk_index / chunk_count
    if ratio <= 0.25:
        return SCENE_POSITIONS[0]
    if ratio <= 0.6:
        return SCENE_POSITIONS[1]
    if ratio < 1:
        return SCENE_POSITIONS[2]
    return SCENE_POSITIONS[3]


def chunk_exit_type(beats: List[Dict[str, Any]], chunk_index: int, chunk_count: int) -> str:
    if chunk_index >= chunk_count:
        return "scene_end"
    if not beats:
        return "natural_pause"
    last_beat = beats[-1]
    if last_beat.get("chunk_boundary_hint") is True:
        return "natural_pause"
    text = beat_render_text(last_beat).strip()
    if text.endswith(SENTENCE_ENDINGS):
        return "sentence_end"
    return "interruption"


def latest_speaker_beat(speaker_id: str, beats: List[Dict[str, Any]]) -> Dict[str, Any]:
    for beat in reversed(beats):
        if beat.get("speaker", "narrator") == speaker_id:
            return beat
    return {}


def build_character_states(
    plan: Dict[str, Any],
    speaker_ids: List[str],
    previous_beats: List[Dict[str, Any]],
    current_beats: List[Dict[str, Any]],
) -> Dict[str, str]:
    states: Dict[str, str] = {}
    for speaker_id in speaker_ids:
        current = latest_speaker_beat(speaker_id, current_beats)
        previous = latest_speaker_beat(speaker_id, previous_beats)
        character = plan.get("characters", {}).get(speaker_id, {})
        base = character.get("stable_voice", "")
        current_perf = performance_summary(current) if current else ""
        previous_perf = performance_summary(previous) if previous else ""

        parts = []
        if base:
            parts.append(f"baseline: {base}")
        if previous_perf:
            parts.append(f"entering from: {previous_perf}")
        if current_perf:
            parts.append(f"current beat: {current_perf}")
        states[speaker_id] = "; ".join(parts) or "maintain established voice and scene tone"
    return states


def build_continuity_packet(
    plan: Dict[str, Any],
    scene: Dict[str, Any],
    beats: List[Dict[str, Any]],
    previous_beats: List[Dict[str, Any]],
    chunk_number: int,
    chunk_index_in_scene: int,
    scene_chunk_count: int,
) -> str:
    speaker_ids = speaker_ids_for(beats)
    previous = summarize_beats(plan, previous_beats, limit=2)
    current = summarize_beats(plan, beats, limit=4)
    voice_locks = build_voice_locks(plan, speaker_ids)
    voice_bible_lines = build_voice_bible_lines(plan, speaker_ids)
    states = build_character_states(plan, speaker_ids, previous_beats, beats)
    position = scene_position(chunk_index_in_scene, scene_chunk_count)

    sections = [
        "## CONTINUITY PACKET",
        f"Chunk {chunk_number} continues scene {scene.get('scene_id', 'unknown_scene')}: {scene.get('title', 'Untitled scene')}. Scene position: {position}.",
    ]

    if previous:
        join_line = beat_summary(plan, previous_beats[-1])
        sections.append(
            "### JOIN CONTEXT - DO NOT SPEAK\n"
            f"The previous spoken beat was: {join_line}"
        )
        sections.append("### PREVIOUS MOMENT\n" + "\n".join(f"- {item}" for item in previous))
    else:
        sections.append("### PREVIOUS MOMENT\n- This is the opening render chunk for the scene. Establish the scene tone without rushing.")

    if current:
        sections.append("### CURRENT MOMENT\n" + "\n".join(f"- {item}" for item in current))

    if states:
        state_lines = [
            f"- {display_name(plan, speaker_id)}: {state}"
            for speaker_id, state in states.items()
        ]
        sections.append("### CHARACTER STATE\n" + "\n".join(state_lines))

    if voice_bible_lines:
        sections.append("### CHARACTER VOICE BIBLE\n" + "\n".join(f"- {line}" for line in voice_bible_lines))

    if voice_locks:
        sections.append("### VOICE LOCKS\n" + "\n".join(f"- {item}" for item in voice_locks))

    sections.append(
        "### JOINING INSTRUCTIONS\n"
        "- Preserve the same scene energy as the surrounding chunks.\n"
        "- Do not restart the performance as if this is a new scene.\n"
        "- Keep pauses natural at the beginning and end so this audio can be stitched into an audiobook."
    )
    return "\n\n".join(sections)


def build_transcript(plan: Dict[str, Any], beats: List[Dict[str, Any]]) -> str:
    speaker_ids = speaker_ids_for(beats)
    speaker_names = {speaker_id: display_name(plan, speaker_id) for speaker_id in speaker_ids}

    if len(speaker_names) == 1:
        header = f"TTS the following passage as {next(iter(speaker_names.values()))}:"
    else:
        header = "TTS the following conversation exactly as written:"

    lines = [header]
    for beat in beats:
        if not is_speakable_beat(beat):
            continue
        speaker = speaker_names[beat.get("speaker", "narrator")]
        tag = gemini_tone_tag(beat.get("performance") or {})
        text = beat_render_text(beat)
        if tag:
            lines.append(f"{speaker}: [{tag}] {text}")
        else:
            lines.append(f"{speaker}: {text}")
    return "\n\n".join(lines)


def build_request(
    plan: Dict[str, Any],
    scene: Dict[str, Any],
    beats: List[Dict[str, Any]],
    output_file: str,
    model: str,
    previous_beats: List[Dict[str, Any]],
    chunk_number: int,
    chunk_index_in_scene: int,
    scene_chunk_count: int,
) -> Dict[str, Any]:
    speaker_ids = speaker_ids_for(beats)
    speaker_names = {speaker_id: display_name(plan, speaker_id) for speaker_id in speaker_ids}
    aliases = speaker_aliases(speaker_ids)
    scene_packet = build_gemini_scene_packet(scene, plan, speaker_ids, speaker_names)
    continuity_packet = build_continuity_packet(
        plan,
        scene,
        beats,
        previous_beats,
        chunk_number,
        chunk_index_in_scene,
        scene_chunk_count,
    )
    states = build_character_states(plan, speaker_ids, previous_beats, beats)
    tts_prompt = build_tts_prompt(
        plan,
        scene,
        beats,
        speaker_ids,
        aliases,
        previous_beats,
        chunk_index_in_scene,
        scene_chunk_count,
    )
    exit_type = chunk_exit_type(beats, chunk_index_in_scene, scene_chunk_count)
    return {
        "output_file": output_file,
        "model": model,
        "scene_position": scene_position(chunk_index_in_scene, scene_chunk_count),
        "scene_exit_type": exit_type,
        "character_states": states,
        "character_voice_bibles": {
            speaker_id: character_voice_bible(
                plan,
                speaker_id,
                collect_golden_lines(plan).get(speaker_id, []),
            )
            for speaker_id in speaker_ids
        },
        "chapter_context": f"{scene_packet}\n\n{continuity_packet}",
        "continuity_packet": continuity_packet,
        "tts_prompt": tts_prompt,
        "transcript": build_transcript(plan, beats),
        "speaker_aliases": {
            aliases[speaker_id]: {
                "speaker_id": speaker_id,
                "display_name": speaker_names[speaker_id],
                "provider_voice": provider_voice(plan, speaker_id, "gemini", "Kore"),
            }
            for speaker_id in speaker_ids
        },
        "speaker_voices": {
            aliases[speaker_id]: provider_voice(plan, speaker_id, "gemini", "Kore")
            for speaker_id in speaker_ids
        },
        "source": {
            "book_id": plan.get("book_id"),
            "chapter_id": plan.get("chapter_id"),
            "scene_id": scene.get("scene_id"),
            "chunk_number": chunk_number,
            "scene_chunk_index": chunk_index_in_scene,
            "scene_chunk_count": scene_chunk_count,
            "scene_exit_type": exit_type,
            "beat_ids": [beat.get("beat_id") for beat in beats],
        },
    }


def render_script(request_paths: List[Path], model: str) -> str:
    return f'''"""Render this exported Gemini chapter pack.

Set GEMINI_API_KEY first, then run:
    python render_chapter.py
"""

from pathlib import Path
import subprocess
import sys


MODEL = {model!r}
MANIFEST = Path(__file__).with_name("manifest.json")


def main() -> None:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "src.aura.gemini_chapter_renderer",
            "--manifest",
            MANIFEST,
            "--model",
            MODEL,
        ],
        check=True,
    )


if __name__ == "__main__":
    main()
'''


def prompt_preview_markdown(request: Dict[str, Any], request_path: Path) -> str:
    source = request.get("source") or {}
    aliases = request.get("speaker_aliases") or {}
    speaker_voices = request.get("speaker_voices") or {}
    lines = [
        f"# Gemini Prompt Preview - Chunk {source.get('chunk_number', '?')}",
        "",
        "## Metadata",
        "",
        f"- Request file: `{request_path}`",
        f"- Output file: `{request.get('output_file', '')}`",
        f"- Model: `{request.get('model', '')}`",
        f"- Scene: `{source.get('scene_id', '')}`",
        f"- Scene position: `{request.get('scene_position', '')}`",
        f"- Scene exit type: `{request.get('scene_exit_type', '')}`",
        f"- Beat ids: `{', '.join(str(beat_id) for beat_id in source.get('beat_ids', []))}`",
        "",
        "## Speaker Map",
        "",
    ]
    for alias, details in aliases.items():
        lines.append(
            f"- `{alias}` -> `{details.get('speaker_id', '')}` "
            f"({details.get('display_name', '')}), voice `{speaker_voices.get(alias, details.get('provider_voice', ''))}`"
        )

    lines.extend(
        [
            "",
            "## Gemini-Facing Prompt",
            "",
            "This is the exact `tts_prompt` sent to Gemini.",
            "",
            "```text",
            request.get("tts_prompt", ""),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def export_chapter(
    plan: Dict[str, Any],
    output_dir: Path,
    model: str,
    max_chunk_words: Optional[int] = DEFAULT_MAX_CHUNK_WORDS,
    cast_bible_path: Optional[Path] = None,
) -> List[Path]:
    requests_dir = output_dir / "requests"
    audio_dir = output_dir / "audio"
    prompt_preview_dir = output_dir / "qa" / "prompts"
    requests_dir.mkdir(parents=True, exist_ok=True)
    audio_dir.mkdir(parents=True, exist_ok=True)
    prompt_preview_dir.mkdir(parents=True, exist_ok=True)

    request_paths: List[Path] = []
    prompt_preview_paths: List[Path] = []
    chunk_records: List[Dict[str, Any]] = []
    chunk_number = 1
    previous_beats: List[Dict[str, Any]] = []
    for scene in plan.get("scenes", []):
        scene_chunks = split_scene_beats(scene, max_chunk_words=max_chunk_words)
        for scene_index, beats in enumerate(scene_chunks, start=1):
            request_path = requests_dir / f"chunk_{chunk_number:03d}.json"
            audio_path = audio_dir / f"chunk_{chunk_number:03d}.wav"
            request = build_request(
                plan,
                scene,
                beats,
                str(audio_path),
                model,
                previous_beats,
                chunk_number,
                scene_index,
                len(scene_chunks),
            )
            validate_gemini_tts_prompt(request)
            request_path.write_text(json.dumps(request, indent=2), encoding="utf-8")
            prompt_preview_path = prompt_preview_dir / f"chunk_{chunk_number:03d}.md"
            prompt_preview_path.write_text(
                prompt_preview_markdown(request, request_path),
                encoding="utf-8",
            )
            request_paths.append(request_path)
            prompt_preview_paths.append(prompt_preview_path)
            chunk_records.append(
                {
                    "index": chunk_number,
                    "request_file": str(request_path),
                    "prompt_preview_file": str(prompt_preview_path),
                    "audio_file": str(audio_path),
                    "scene_id": scene.get("scene_id"),
                    "scene_position": request["scene_position"],
                    "scene_exit_type": request["scene_exit_type"],
                    "beat_ids": request["source"]["beat_ids"],
                }
            )
            previous_beats.extend(beats)
            chunk_number += 1

    (output_dir / "render_chapter.py").write_text(render_script(request_paths, model), encoding="utf-8")
    manifest = {
        "book_id": plan.get("book_id"),
        "chapter_id": plan.get("chapter_id"),
        "model": model,
        "qa_status": "pending",
        "qa_notes": [],
        "character_voice_bibles": build_character_voice_bibles(plan),
        "cast_bible": str(cast_bible_path) if cast_bible_path else None,
        "chunks": chunk_records,
        "requests": [str(path) for path in request_paths],
        "prompt_previews": [str(path) for path in prompt_preview_paths],
        "chunking": {
            "max_chunk_words": max_chunk_words,
            "estimated_duration": "roughly 1-2 minutes at normal audiobook pace",
        },
        "note": "Gemini TTS chunks are split to keep each request within the two-speaker limit and the configured word budget.",
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return request_paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Export an APS chapter into runnable Gemini TTS chunks.")
    parser.add_argument("--aps", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--max-chunk-words",
        default=DEFAULT_MAX_CHUNK_WORDS,
        type=int,
        help="Approximate chunk word budget. Use 180-260 for 1-2 minute audiobook chunks.",
    )
    parser.add_argument(
        "--cast-bible",
        type=Path,
        help="Optional book-level cast bible. When provided, it overrides APS character voice identity fields.",
    )
    args = parser.parse_args()

    plan = load_json(args.aps)
    if args.cast_bible:
        plan = apply_cast_bible(plan, load_json(args.cast_bible))
    request_paths = export_chapter(
        plan,
        args.output_dir,
        args.model,
        max_chunk_words=args.max_chunk_words,
        cast_bible_path=args.cast_bible,
    )
    print(f"Wrote {len(request_paths)} Gemini request chunk(s) to {args.output_dir}")
    print(f"Render with: python {args.output_dir / 'render_chapter.py'}")


if __name__ == "__main__":
    main()
