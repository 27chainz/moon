from src.aura.aps_validator import validate_aps


def base_aps():
    source_text = "He ran hastily across the street."
    return {
        "schema_version": "0.2",
        "renderer_constraints": {
            "max_speakers": 2,
            "chunk_strategy": "speaker_pair",
        },
        "source_document": {"text": source_text},
        "characters": {"narrator": {"display_name": "Narrator"}},
        "scenes": [
            {
                "scene_id": "scene_001",
                "beats": [
                    {
                        "beat_id": "scene_001_beat_001",
                        "sequence_index": 1,
                        "kind": "narration",
                        "speaker": "narrator",
                        "speakable": True,
                        "text": "He ran hastily across the street.",
                        "render_text": "He ran hastily across the street.",
                        "source_trace": {
                            "source_start": 0,
                            "source_end": len(source_text),
                            "source_text": source_text,
                            "spoken_text_span": {
                                "source_start": 0,
                                "source_end": len(source_text),
                                "text": source_text,
                            },
                        },
                        "delivery_archetype": "urgency",
                        "performance": {
                            "emotion": "fear",
                            "intensity": 0.5,
                        },
                    }
                ],
            }
        ],
    }


def test_validate_phrase_level_sfx_with_fallback():
    aps = base_aps()
    aps["scenes"][0]["sfx"] = [
        {
            "sfx_id": "sfx_001",
            "type": "motion",
            "description": "hurried footsteps on pavement",
            "placement": "phrase_span",
            "anchor_text": "ran hastily across the street",
            "anchor_beat": "scene_001_beat_001",
            "min_alignment_confidence": 0.82,
            "fallback_placement": "beat_span",
            "on_alignment_failure": "degrade_to_fallback",
            "duration_policy": {
                "policy": "loop_crossfade",
                "crossfade_ms": 80,
            },
            "ducking": {
                "enabled": True,
                "duck_by_db": 6,
                "attack_ms": 40,
                "release_ms": 250,
            },
        }
    ]

    assert validate_aps(aps) == []


def test_phrase_level_sfx_requires_confidence_and_fallback():
    aps = base_aps()
    aps["scenes"][0]["sfx"] = [
        {
            "sfx_id": "sfx_001",
            "type": "motion",
            "placement": "phrase_span",
            "anchor_text": "ran hastily",
            "anchor_beat": "scene_001_beat_001",
        }
    ]

    errors = validate_aps(aps)

    assert any("min_alignment_confidence" in error for error in errors)
    assert any("fallback_placement" in error for error in errors)
    assert any("on_alignment_failure" in error for error in errors)


def test_scene_span_sfx_requires_start_and_end_beats():
    aps = base_aps()
    aps["scenes"][0]["sfx"] = [
        {
            "sfx_id": "sfx_001",
            "type": "ambience",
            "description": "distant traffic",
            "placement": "scene_span",
        }
    ]

    errors = validate_aps(aps)

    assert any("start_beat and end_beat" in error for error in errors)


def test_sfx_anchor_must_match_scene_beat():
    aps = base_aps()
    aps["scenes"][0]["sfx"] = [
        {
            "sfx_id": "sfx_001",
            "type": "spot",
            "placement": "after_text",
            "anchor_beat": "scene_999_beat_001",
        }
    ]

    errors = validate_aps(aps)

    assert any("does not match a beat" in error for error in errors)
