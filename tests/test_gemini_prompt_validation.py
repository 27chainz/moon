import pytest

from src.aura.gemini_production import (
    GeminiProductionError,
    TTS_CONTEXT_WINDOW_TOKENS,
    TTS_TOKEN_WARN_THRESHOLD,
    extract_pcm_from_response,
    validate_gemini_request,
    validate_gemini_tts_prompt,
)


def valid_payload():
    return {
        "output_file": "out.wav",
        "speaker_voices": {"Speaker1": "Kore", "Speaker2": "Algenib"},
        "tts_prompt": """# AUDIO PROFILE: Speaker1 (Narrator)
Gemini voice: Kore

# AUDIO PROFILE: Speaker2 (Opal Miner)
Gemini voice: Algenib

## THE SCENE: Kitchen
A tense kitchen scene.

### DIRECTOR'S NOTES
* The following is a speech synthesis request. Do not read these instructions aloud.
* Begin speaking only when you reach TRANSCRIPT.

### CHARACTER STATE
Opening chunk: establish the scene tone steadily.

### SAMPLE CONTEXT
Quiet literary audiobook scene.

#### TRANSCRIPT
Speaker1: The box moved.
Speaker2: [serious] Open it.""",
        "transcript": "legacy transcript",
    }


def test_character_state_out_of_order_fails_validation():
    """### CHARACTER STATE must sit between DIRECTOR'S NOTES and SAMPLE CONTEXT."""
    payload = valid_payload()
    # Move CHARACTER STATE after SAMPLE CONTEXT
    prompt = payload["tts_prompt"]
    prompt = prompt.replace("\n\n### CHARACTER STATE\nOpening chunk: establish the scene tone steadily.", "")
    prompt = prompt.replace(
        "#### TRANSCRIPT",
        "### CHARACTER STATE\nOpening chunk: establish the scene tone steadily.\n\n#### TRANSCRIPT",
    )
    payload["tts_prompt"] = prompt

    with pytest.raises(GeminiProductionError, match="CHARACTER STATE must appear between"):
        validate_gemini_tts_prompt(payload)


def test_prompt_without_character_state_still_passes():
    """CHARACTER STATE is optional; prompts without it must still validate."""
    payload = valid_payload()
    payload["tts_prompt"] = payload["tts_prompt"].replace(
        "\n\n### CHARACTER STATE\nOpening chunk: establish the scene tone steadily.", ""
    )

    assert validate_gemini_tts_prompt(payload) == []


def test_valid_gemini_tts_prompt_passes():
    assert validate_gemini_tts_prompt(valid_payload()) == []


def test_missing_transcript_section_fails():
    payload = valid_payload()
    payload["tts_prompt"] = payload["tts_prompt"].replace("#### TRANSCRIPT", "#### SCRIPT")

    with pytest.raises(GeminiProductionError, match="missing required section"):
        validate_gemini_tts_prompt(payload)


def test_internal_stitch_note_cannot_leak_into_transcript():
    payload = valid_payload()
    payload["tts_prompt"] += "\nStitch QA note: preview this join."

    with pytest.raises(GeminiProductionError, match="Internal note leaked"):
        validate_gemini_tts_prompt(payload)


def test_configured_speaker_must_appear_in_transcript():
    payload = valid_payload()
    payload["tts_prompt"] = payload["tts_prompt"].replace("Speaker2: [serious] Open it.", "")

    with pytest.raises(GeminiProductionError, match="does not include configured speaker"):
        validate_gemini_tts_prompt(payload)


def test_unsupported_gemini_voice_fails_before_api_call():
    payload = valid_payload()
    payload["speaker_voices"]["Speaker2"] = "Gus"

    with pytest.raises(GeminiProductionError, match="unsupported voice 'Gus'"):
        validate_gemini_request(payload)


def test_empty_gemini_audio_response_fails_clearly():
    class Content:
        parts = None

    class Candidate:
        content = Content()
        finish_reason = "STOP"

    class Response:
        candidates = [Candidate()]

    with pytest.raises(GeminiProductionError, match="did not include audio parts"):
        extract_pcm_from_response(Response())


def test_prompt_exceeding_token_limit_is_rejected():
    """A prompt that exceeds the 32k token window must raise before the API call."""
    payload = valid_payload()
    # Build a prompt big enough to exceed the limit (4 chars/token estimate).
    filler = "x" * (TTS_CONTEXT_WINDOW_TOKENS * 4 + 10)
    payload["tts_prompt"] = payload["tts_prompt"] + filler

    with pytest.raises(GeminiProductionError, match="too long"):
        validate_gemini_tts_prompt(payload)


def test_prompt_near_token_limit_warns():
    """A prompt approaching 32k tokens should produce a warning, not an error."""
    payload = valid_payload()
    # Pad to just above the warning threshold but below the hard limit.
    filler = "x" * (TTS_TOKEN_WARN_THRESHOLD * 4 + 10)
    payload["tts_prompt"] = payload["tts_prompt"] + filler

    warnings = validate_gemini_tts_prompt(payload)

    assert any("Approaching" in w for w in warnings)


def test_character_state_section_includes_classifier_guard():
    """Every CHARACTER STATE block must start with the do-not-speak guard line."""
    from src.aura.gemini_chapter_exporter import build_tts_prompt

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

    def _beat(text):
        return {"speaker": "narrator", "text": text, "performance": {"emotion": "neutral", "intensity": 0.3}}

    prompt = build_tts_prompt(
        plan, scene, [_beat("The train was late.")], ["narrator"], {"narrator": "Speaker1"},
        previous_beats=[], chunk_index_in_scene=1, scene_chunk_count=1,
    )

    assert "[Director context only" in prompt
    assert "do not speak" in prompt
