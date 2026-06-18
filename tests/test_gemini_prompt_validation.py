import pytest

from src.aura.gemini_production import (
    GeminiProductionError,
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

### SAMPLE CONTEXT
Quiet literary audiobook scene.

#### TRANSCRIPT
Speaker1: The box moved.
Speaker2: [serious] Open it.""",
        "transcript": "legacy transcript",
    }


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
