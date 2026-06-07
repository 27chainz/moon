import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict

from src.aura.gemini_production import (
    GEMINI_SAMPLE_RATE,
    GEMINI_TTS_MODEL,
    extract_pcm_from_response,
    request_output_path,
    save_wave,
    speaker_voices,
    validate_gemini_request,
    wave_info,
    write_json,
)


DEFAULT_MODEL = GEMINI_TTS_MODEL


def load_request(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_single_speaker_prompt(payload: Dict[str, Any]) -> str:
    performance = payload.get("performance") or {}
    style_prompt = performance.get("style_prompt") or ""
    text = payload["text"]
    if style_prompt:
        return f"Say in this performance style: {style_prompt}\n\n{text}"
    return text


def get_system_instruction(payload: Dict[str, Any]) -> str:
    performance = payload.get("performance") or {}
    return payload.get("chapter_context") or performance.get("system_instruction") or ""


def build_multi_speaker_prompt(payload: Dict[str, Any]) -> str:
    if payload.get("transcript"):
        return payload["transcript"]
    performance = payload.get("performance") or {}
    if performance.get("transcript"):
        return performance["transcript"]
    if performance.get("prompt"):
        return performance["prompt"]
    direction = performance.get("direction") or performance.get("style_prompt") or ""
    turns = payload["turns"]
    lines = ["TTS the following conversation exactly as written:"]
    if direction:
        lines.insert(0, direction)
    for turn in turns:
        lines.append(f"{turn['speaker']}: {turn['text']}")
    return "\n".join(lines)


def get_voice_name(voice: Dict[str, Any], fallback: str = "Kore") -> str:
    return voice.get("provider_voice") or voice.get("gemini_voice") or fallback


def get_speaker_voices(payload: Dict[str, Any]) -> Dict[str, str]:
    return speaker_voices(payload)


def synthesize_single(payload: Dict[str, Any], model: str) -> bytes:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    voice = payload["voice"]
    response = client.models.generate_content(
        model=model,
        contents=build_single_speaker_prompt(payload),
        config=types.GenerateContentConfig(
            system_instruction=get_system_instruction(payload) or None,
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=get_voice_name(voice),
                    )
                )
            ),
        ),
    )
    return extract_pcm_from_response(response)


def synthesize_multi(payload: Dict[str, Any], model: str) -> bytes:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    speaker_voices = get_speaker_voices(payload)
    response = client.models.generate_content(
        model=model,
        contents=build_multi_speaker_prompt(payload),
        config=types.GenerateContentConfig(
            system_instruction=get_system_instruction(payload) or None,
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
                    speaker_voice_configs=[
                        types.SpeakerVoiceConfig(
                            speaker=speaker,
                            voice_config=types.VoiceConfig(
                                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                    voice_name=voice_name,
                                )
                            ),
                        )
                        for speaker, voice_name in speaker_voices.items()
                    ]
                )
            ),
        ),
    )
    return extract_pcm_from_response(response)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render an Aura synthesis request with Gemini TTS.")
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()

    payload = load_request(args.request)
    warnings = validate_gemini_request(payload)
    model = payload.get("model") or args.model
    output_path = request_output_path(payload)

    if not os.getenv("GEMINI_API_KEY"):
        raise RuntimeError("Set GEMINI_API_KEY before running Gemini TTS.")

    if "speaker_voices" in payload or ("turns" in payload and "speakers" in payload):
        pcm = synthesize_multi(payload, model)
    else:
        pcm = synthesize_single(payload, model)

    save_wave(output_path, pcm)
    audio_info = wave_info(output_path)

    result_path = output_path.with_suffix(output_path.suffix + ".json")
    result_payload = {
        "output_path": str(output_path),
        "model": model,
        "sample_rate": GEMINI_SAMPLE_RATE,
        "warnings": warnings,
        "audio": audio_info,
        "chapter_context": payload.get("chapter_context"),
        "transcript": payload.get("transcript"),
        "speaker_voices": payload.get("speaker_voices"),
        "text": payload.get("text"),
        "voice": payload.get("voice"),
        "speakers": payload.get("speakers"),
        "performance": payload.get("performance") or {},
    }
    write_json(result_path, result_payload)
    print(f"Saved: {output_path}")
    print(f"Metadata: {result_path}")


if __name__ == "__main__":
    main()
