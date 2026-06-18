from pathlib import Path

from src.aura.gemini_chapter_exporter import build_tts_prompt, prompt_preview_markdown, split_scene_beats


def beat(text: str, speaker: str = "narrator"):
    return {
        "speaker": speaker,
        "text": text,
        "performance": {
            "emotion": "neutral",
            "intensity": 0.2,
            "pacing": "measured",
            "delivery": "clear",
        },
    }


def test_split_scene_beats_respects_word_budget():
    scene = {
        "beats": [
            beat("one two three four five"),
            beat("six seven eight nine ten"),
            beat("eleven twelve thirteen fourteen fifteen"),
        ]
    }

    chunks = split_scene_beats(scene, max_chunk_words=10)

    assert [len(chunk) for chunk in chunks] == [2, 1]


def test_split_scene_beats_still_respects_two_speaker_limit():
    scene = {
        "beats": [
            beat("hello there", "narrator"),
            beat("hello there", "opal_miner"),
            beat("hello there", "young_narrator"),
        ]
    }

    chunks = split_scene_beats(scene, max_chunk_words=100)

    assert [len(chunk) for chunk in chunks] == [2, 1]


def test_non_opening_tts_prompt_includes_continuity_bridge():
    plan = {
        "characters": {
            "narrator": {
                "display_name": "Narrator",
                "role": "narrator",
                "provider_voice": {"gemini": "Kore"},
                "stable_voice": "restrained literary narrator",
            },
            "opal_miner": {
                "display_name": "Opal Miner",
                "role": "supporting",
                "provider_voice": {"gemini": "Algenib"},
                "stable_voice": "gravelly clipped South African opal miner",
                "energy_profile": {
                    "baseline_intensity": 0.55,
                    "entry_instruction": "Enter as the same already-established Opal Miner.",
                    "do_not_do": ["Do not reset energy."],
                },
            }
        },
        "production_packet": {
            "director_notes": [],
            "sample_context": "Quiet literary audiobook.",
        },
    }
    scene = {
        "title": "Memory",
        "scene_context": "A quiet remembered moment.",
        "director_notes": [],
    }
    previous = [
        beat("The first memory ends quietly."),
        beat("Not to worry.", "opal_miner"),
    ]
    current = [
        beat("The next memory continues softly."),
        beat("Open it.", "opal_miner"),
    ]

    prompt = build_tts_prompt(
        plan,
        scene,
        current,
        ["narrator", "opal_miner"],
        {"narrator": "Speaker1", "opal_miner": "Speaker2"},
        previous_beats=previous,
        chunk_index_in_scene=2,
        scene_chunk_count=3,
    )

    assert "Casting lock: This is a stable cast voice" in prompt
    assert "Energy baseline: 0.55" in prompt
    assert "Energy entry: Enter as the same already-established Opal Miner." in prompt
    assert "enter as if already mid-scene" in prompt
    assert "Match the previous chunk's restraint, volume, pace, and vocal colour" in prompt
    assert "Do not brighten, accelerate, increase volume, or become more theatrical" in prompt
    assert "Voice continuity lock for Opal Miner: use the exact same character voice as earlier chunks" in prompt
    assert "#### TRANSCRIPT\nSpeaker1:" in prompt
    assert "Speaker2: Open it." in prompt


def test_new_scene_opening_preserves_previous_character_voice():
    plan = {
        "characters": {
            "opal_miner": {
                "display_name": "Opal Miner",
                "role": "supporting",
                "provider_voice": {"gemini": "Algenib"},
                "stable_voice": "gravelly clipped South African opal miner",
            }
        },
        "production_packet": {"director_notes": [], "sample_context": "Quiet literary audiobook."},
    }
    scene = {"title": "Second Scene", "scene_context": "The miner returns.", "director_notes": []}
    previous = [beat("Not to worry.", "opal_miner")]
    current = [beat("Bought it for you.", "opal_miner")]

    prompt = build_tts_prompt(
        plan,
        scene,
        current,
        ["opal_miner"],
        {"opal_miner": "Speaker1"},
        previous_beats=previous,
        chunk_index_in_scene=1,
        scene_chunk_count=1,
    )

    assert "Voice continuity lock for Opal Miner: use the exact same character voice as earlier chunks" in prompt
    assert "because this is a new scene" in prompt


def test_prompt_preview_markdown_contains_exact_prompt_and_speaker_map():
    request = {
        "output_file": "audio/chunk_001.wav",
        "model": "gemini-3.1-flash-tts-preview",
        "scene_position": "opening",
        "scene_exit_type": "sentence_end",
        "speaker_aliases": {
            "Speaker1": {
                "speaker_id": "narrator",
                "display_name": "Narrator",
                "provider_voice": "Kore",
            }
        },
        "speaker_voices": {"Speaker1": "Kore"},
        "source": {
            "chunk_number": 1,
            "scene_id": "scene_001",
            "beat_ids": ["beat_001"],
        },
        "tts_prompt": "# AUDIO PROFILE: Speaker1\n\n#### TRANSCRIPT\nSpeaker1: Hello.",
    }

    preview = prompt_preview_markdown(request, Path("requests/chunk_001.json"))

    assert "# Gemini Prompt Preview - Chunk 1" in preview
    assert "`Speaker1` -> `narrator`" in preview
    assert "This is the exact `tts_prompt` sent to Gemini." in preview
    assert "Speaker1: Hello." in preview
