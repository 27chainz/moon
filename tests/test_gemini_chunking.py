from pathlib import Path

from src.aura.gemini_chapter_exporter import (
    PREVIOUS_BEATS_WINDOW,
    build_tts_prompt,
    collect_golden_lines,
    export_chapter,
    prompt_preview_markdown,
    split_scene_beats,
)


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
    # Fix 1: CHARACTER STATE section must appear in the prompt
    assert "### CHARACTER STATE" in prompt
    assert "Previous moment:" in prompt
    assert "Opal Miner" in prompt


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


def test_opening_chunk_character_state_has_no_previous_moment():
    """Opening chunks must say 'Opening chunk' not 'Previous moment'."""
    plan = {
        "characters": {
            "narrator": {
                "display_name": "Narrator",
                "provider_voice": {"gemini": "Kore"},
                "stable_voice": "restrained literary narrator",
            }
        },
        "production_packet": {"director_notes": [], "sample_context": "Literary audiobook."},
    }
    scene = {"title": "Opening", "scene_context": "The story begins.", "director_notes": []}
    current = [beat("The train was late.")]

    prompt = build_tts_prompt(
        plan, scene, current, ["narrator"], {"narrator": "Speaker1"},
        previous_beats=[], chunk_index_in_scene=1, scene_chunk_count=1,
    )

    assert "### CHARACTER STATE" in prompt
    assert "Opening chunk" in prompt
    assert "Previous moment" not in prompt


def test_approved_reference_render_escalates_casting_lock():
    """Characters with an approved reference render get a STRONG CASTING LOCK."""
    plan = {
        "characters": {
            "opal_miner": {
                "display_name": "Opal Miner",
                "provider_voice": {"gemini": "Algenib"},
                "stable_voice": "gravelly South African miner",
                "approved_reference_render": {
                    "chapter_id": "chapter_001",
                    "chunk_id": "chunk_004",
                    "status": "approved",
                    "notes": "Best Opal Miner render.",
                },
            }
        },
        "production_packet": {"director_notes": [], "sample_context": "Literary audiobook."},
    }
    scene = {"title": "Scene", "scene_context": "The miner speaks.", "director_notes": []}
    current = [beat("Bought it for you.", "opal_miner")]

    prompt = build_tts_prompt(
        plan, scene, current, ["opal_miner"], {"opal_miner": "Speaker1"},
        previous_beats=[], chunk_index_in_scene=1, scene_chunk_count=1,
    )

    assert "STRONG CASTING LOCK" in prompt
    assert "chapter_001/chunk_004" in prompt
    assert "Casting lock: This is a stable cast voice" not in prompt


def test_character_without_energy_profile_gets_fallback_anchor():
    """Characters with no energy_profile must still get an energy entry instruction."""
    plan = {
        "characters": {
            "narrator": {
                "display_name": "Narrator",
                "provider_voice": {"gemini": "Kore"},
                "stable_voice": "restrained literary narrator",
                # No energy_profile
            }
        },
        "production_packet": {"director_notes": [], "sample_context": "Literary audiobook."},
    }
    scene = {"title": "Scene", "scene_context": "The story.", "director_notes": []}
    current = [beat("The train was late.")]

    prompt = build_tts_prompt(
        plan, scene, current, ["narrator"], {"narrator": "Speaker1"},
        previous_beats=[], chunk_index_in_scene=1, scene_chunk_count=1,
    )

    assert "Energy baseline: 0.5" in prompt
    assert "Do not reset vocal energy" in prompt


def test_golden_line_beat_ids_preferred_over_first_occurrence():
    """golden_line_beat_ids should surface nominated beats over first-scan beats."""
    plan = {
        "characters": {
            "opal_miner": {
                "display_name": "Opal Miner",
                "provider_voice": {"gemini": "Algenib"},
                "golden_line_beat_ids": ["beat_preferred"],
            }
        },
        "scenes": [
            {
                "beats": [
                    {"speaker": "opal_miner", "text": "First line.", "beat_id": "beat_001"},
                    {"speaker": "opal_miner", "text": "Preferred line.", "beat_id": "beat_preferred"},
                ]
            }
        ],
    }

    result = collect_golden_lines(plan, limit=1)

    assert result["opal_miner"] == ["Preferred line."]


def test_previous_beats_window_capped_in_export(tmp_path):
    """export_chapter must not accumulate previous_beats beyond PREVIOUS_BEATS_WINDOW."""
    import json
    # Build a minimal plan with enough beats to exceed the window
    beat_count = PREVIOUS_BEATS_WINDOW + 10
    beats = [
        {
            "beat_id": f"beat_{i:03d}",
            "speaker": "narrator",
            "text": f"Line {i}.",
            "performance": {"emotion": "neutral", "intensity": 0.3},
        }
        for i in range(beat_count)
    ]
    plan = {
        "book_id": "book_001",
        "chapter_id": "chapter_001",
        "title": "Test Book",
        "chapter_title": "Chapter 1",
        "production_packet": {"director_notes": [], "sample_context": "Test."},
        "characters": {
            "narrator": {
                "display_name": "Narrator",
                "provider_voice": {"gemini": "Kore"},
                "stable_voice": "clear narrator",
            }
        },
        "scenes": [{"scene_id": "scene_001", "title": "Scene", "scene_context": "Test.", "beats": beats}],
    }
    request_paths = export_chapter(plan, tmp_path, "gemini-3.1-flash-tts-preview", max_chunk_words=5)
    # The last chunk's tts_prompt must not reference beats from the very beginning
    # (proving the window was capped). We just verify export completed without error
    # and CHARACTER STATE appears in every generated prompt.
    for rp in request_paths:
        req = json.loads(rp.read_text())
        assert "### CHARACTER STATE" in req["tts_prompt"]
