import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

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
from src.aura.gemini_production import GEMINI_MAX_SPEAKERS, GEMINI_TTS_MODEL


MAX_GEMINI_SPEAKERS = GEMINI_MAX_SPEAKERS
DEFAULT_MODEL = GEMINI_TTS_MODEL
MAX_SUMMARY_CHARS = 220
SCENE_POSITIONS = ("opening", "rising", "turning_point", "resolution")
DEFAULT_GOLDEN_LINE_COUNT = 2


def speaker_ids_for(beats: Iterable[Dict[str, Any]]) -> List[str]:
    speaker_ids: List[str] = []
    for beat in beats:
        if not is_speakable_beat(beat):
            continue
        speaker_id = beat.get("speaker", "narrator")
        if speaker_id not in speaker_ids:
            speaker_ids.append(speaker_id)
    return speaker_ids


def split_scene_beats(scene: Dict[str, Any]) -> List[List[Dict[str, Any]]]:
    chunks: List[List[Dict[str, Any]]] = []
    current: List[Dict[str, Any]] = []
    current_speakers: List[str] = []

    for beat in scene.get("beats", []):
        if not is_speakable_beat(beat):
            continue
        speaker_id = beat.get("speaker", "narrator")
        next_speakers = list(current_speakers)
        if speaker_id not in next_speakers:
            next_speakers.append(speaker_id)

        if current and len(next_speakers) > MAX_GEMINI_SPEAKERS:
            chunks.append(current)
            current = []
            current_speakers = []

        current.append(beat)
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
        "approved_reference_note": character.get("approved_reference_note", ""),
        "golden_lines": golden_lines,
    }


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
    return {
        "output_file": output_file,
        "model": model,
        "scene_position": scene_position(chunk_index_in_scene, scene_chunk_count),
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
        "transcript": build_transcript(plan, beats),
        "speaker_voices": {
            speaker_names[speaker_id]: provider_voice(plan, speaker_id, "gemini", "Kore")
            for speaker_id in speaker_ids
        },
        "source": {
            "book_id": plan.get("book_id"),
            "chapter_id": plan.get("chapter_id"),
            "scene_id": scene.get("scene_id"),
            "chunk_number": chunk_number,
            "scene_chunk_index": chunk_index_in_scene,
            "scene_chunk_count": scene_chunk_count,
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


def export_chapter(plan: Dict[str, Any], output_dir: Path, model: str) -> List[Path]:
    requests_dir = output_dir / "requests"
    audio_dir = output_dir / "audio"
    requests_dir.mkdir(parents=True, exist_ok=True)
    audio_dir.mkdir(parents=True, exist_ok=True)

    request_paths: List[Path] = []
    chunk_number = 1
    previous_beats: List[Dict[str, Any]] = []
    for scene in plan.get("scenes", []):
        scene_chunks = split_scene_beats(scene)
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
            request_path.write_text(json.dumps(request, indent=2), encoding="utf-8")
            request_paths.append(request_path)
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
        "requests": [str(path) for path in request_paths],
        "note": "Gemini TTS chunks are split to keep each request within the two-speaker limit.",
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return request_paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Export an APS chapter into runnable Gemini TTS chunks.")
    parser.add_argument("--aps", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()

    plan = load_json(args.aps)
    request_paths = export_chapter(plan, args.output_dir, args.model)
    print(f"Wrote {len(request_paths)} Gemini request chunk(s) to {args.output_dir}")
    print(f"Render with: python {args.output_dir / 'render_chapter.py'}")


if __name__ == "__main__":
    main()
