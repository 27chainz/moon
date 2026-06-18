from src.aura.cast_bible import apply_cast_bible, extract_cast_bible, mark_approved_reference_render


def test_extract_cast_bible_keeps_voice_identity_fields():
    plan = {
        "book_id": "book_001",
        "title": "Test Book",
        "chapter_id": "chapter_001",
        "characters": {
            "opal_miner": {
                "display_name": "Opal Miner",
                "role": "supporting",
                "stable_voice": "gravelly clipped South African opal miner",
                "provider_voice": {"gemini": "Algenib"},
                "do_not_change": ["gravelly texture"],
                "voice_bible": "Keep him blunt and practical.",
                "golden_lines": ["Not to worry."],
                "energy_profile": {
                    "baseline_intensity": 0.55,
                    "entry_instruction": "Enter mid-scene.",
                    "do_not_do": ["Do not reset energy."],
                },
                "approved_reference_render": {
                    "chapter_id": "chapter_001",
                    "chunk_id": "chunk_004",
                    "notes": "Best current render.",
                },
                "accent_profile": {
                    "label": "South African English",
                    "features": ["clipped final consonants"],
                    "avoid": ["polished British diction"],
                },
            }
        },
    }

    cast_bible = extract_cast_bible(plan)

    opal = cast_bible["characters"]["opal_miner"]
    assert opal["provider_voice"]["gemini"] == "Algenib"
    assert opal["voice_bible"] == "Keep him blunt and practical."
    assert opal["energy_profile"]["baseline_intensity"] == 0.55
    assert opal["approved_reference_render"]["chunk_id"] == "chunk_004"
    assert opal["casting_lock"] == "stable"
    assert "version_history" in cast_bible
    assert "enforcement" in cast_bible


def test_apply_cast_bible_overrides_chapter_character_identity():
    plan = {
        "characters": {
            "opal_miner": {
                "display_name": "Opal Miner",
                "provider_voice": {"gemini": "Kore"},
                "stable_voice": "wrong voice",
                "chapter_only_note": "preserve this",
            }
        }
    }
    cast_bible = {
        "cast_bible_version": "0.1",
        "book_id": "book_001",
        "characters": {
            "opal_miner": {
                "provider_voice": {"gemini": "Algenib"},
                "stable_voice": "locked voice",
                "voice_bible": "locked bible",
                "energy_profile": {"baseline_intensity": 0.4},
                "casting_lock": "stable",
            }
        },
    }

    merged = apply_cast_bible(plan, cast_bible)

    opal = merged["characters"]["opal_miner"]
    assert opal["provider_voice"]["gemini"] == "Algenib"
    assert opal["stable_voice"] == "locked voice"
    assert opal["voice_bible"] == "locked bible"
    assert opal["energy_profile"]["baseline_intensity"] == 0.4
    assert opal["chapter_only_note"] == "preserve this"
    assert merged["_cast_bible_applied"]["character_ids"] == ["opal_miner"]
    assert "enforcement" in merged["_cast_bible_applied"]


def test_mark_approved_reference_render_updates_character_and_history():
    cast_bible = {
        "cast_bible_version": "0.1",
        "characters": {
            "opal_miner": {
                "display_name": "Opal Miner",
            }
        },
    }

    updated = mark_approved_reference_render(
        cast_bible,
        "opal_miner",
        "chapter_001",
        "chunk_004",
        "accent held",
    )

    reference = updated["characters"]["opal_miner"]["approved_reference_render"]
    assert reference["status"] == "approved"
    assert reference["chapter_id"] == "chapter_001"
    assert reference["chunk_id"] == "chunk_004"
    assert reference["notes"] == "accent held"
    assert updated["version_history"][0]["affected_characters"] == ["opal_miner"]
