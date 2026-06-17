from src.aura.gemini_tts_runner import (
    build_single_speaker_prompt,
    get_single_speaker_voice,
    should_use_multi_speaker,
)


def test_one_speaker_voice_request_uses_single_speaker_mode():
    payload = {
        "speaker_voices": {"Speaker1": "Kore"},
        "tts_prompt": "# AUDIO PROFILE: Speaker1\n\n#### TRANSCRIPT\nSpeaker1: Hello.",
    }

    assert should_use_multi_speaker(payload) is False
    assert get_single_speaker_voice(payload) == {"provider_voice": "Kore"}
    assert build_single_speaker_prompt(payload) == payload["tts_prompt"]


def test_two_speaker_voice_request_uses_multi_speaker_mode():
    payload = {
        "speaker_voices": {"Speaker1": "Kore", "Speaker2": "Algenib"},
        "tts_prompt": "# AUDIO PROFILE: Speaker1\n\n#### TRANSCRIPT\nSpeaker1: Hello.\nSpeaker2: Hello.",
    }

    assert should_use_multi_speaker(payload) is True
