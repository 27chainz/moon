import argparse
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, Optional

from src.aura.gemini_production import (
    GEMINI_SAMPLE_RATE,
    GEMINI_TTS_MODEL,
    extract_pcm_from_response,
    request_output_path,
    save_wave,
    speaker_voices,
    validate_gemini_request,
    validate_gemini_tts_prompt,
    wave_info,
    write_json,
)


DEFAULT_MODEL = GEMINI_TTS_MODEL
RETRYABLE_ERROR_RE = re.compile(r"\b(429|500|502|503|504|UNAVAILABLE|RESOURCE_EXHAUSTED|DEADLINE_EXCEEDED|INTERNAL)\b", re.I)


def load_request(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_single_speaker_prompt(payload: Dict[str, Any]) -> str:
    if payload.get("tts_prompt"):
        return payload["tts_prompt"]
    performance = payload.get("performance") or {}
    style_prompt = performance.get("style_prompt") or ""
    chapter_context = get_system_instruction(payload)
    text = payload["text"]
    parts = []
    if chapter_context:
        parts.append(chapter_context)
    if style_prompt:
        parts.append(f"Say in this performance style: {style_prompt}")
    parts.append(text)
    return "\n\n".join(parts)


def get_system_instruction(payload: Dict[str, Any]) -> str:
    performance = payload.get("performance") or {}
    return payload.get("chapter_context") or performance.get("system_instruction") or ""


def build_multi_speaker_prompt(payload: Dict[str, Any]) -> str:
    if payload.get("tts_prompt"):
        return payload["tts_prompt"]
    chapter_context = get_system_instruction(payload)
    if payload.get("transcript"):
        if chapter_context:
            return f"{chapter_context}\n\n{payload['transcript']}"
        return payload["transcript"]
    performance = payload.get("performance") or {}
    if performance.get("transcript"):
        if chapter_context:
            return f"{chapter_context}\n\n{performance['transcript']}"
        return performance["transcript"]
    if performance.get("prompt"):
        return performance["prompt"]
    direction = performance.get("direction") or performance.get("style_prompt") or ""
    turns = payload["turns"]
    lines = ["TTS the following conversation exactly as written:"]
    if chapter_context:
        lines.insert(0, chapter_context)
    if direction:
        lines.insert(0, direction)
    for turn in turns:
        lines.append(f"{turn['speaker']}: {turn['text']}")
    return "\n".join(lines)


def get_voice_name(voice: Dict[str, Any], fallback: str = "Kore") -> str:
    return voice.get("provider_voice") or voice.get("gemini_voice") or fallback


def get_speaker_voices(payload: Dict[str, Any]) -> Dict[str, str]:
    return speaker_voices(payload)


def should_use_multi_speaker(payload: Dict[str, Any]) -> bool:
    return len(get_speaker_voices(payload)) > 1


def get_single_speaker_voice(payload: Dict[str, Any]) -> Dict[str, Any]:
    voices = get_speaker_voices(payload)
    if len(voices) == 1:
        return {"provider_voice": next(iter(voices.values()))}
    return payload["voice"]


def synthesize_single(payload: Dict[str, Any], model: str) -> bytes:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    voice = get_single_speaker_voice(payload)
    response = client.models.generate_content(
        model=model,
        contents=build_single_speaker_prompt(payload),
        config=types.GenerateContentConfig(
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
    parser.add_argument("--model", default=None)
    parser.add_argument("--retries", default=3, type=int)
    parser.add_argument("--backoff", default=4.0, type=float)
    args = parser.parse_args()

    payload = load_request(args.request)
    warnings = validate_gemini_request(payload)
    warnings.extend(validate_gemini_tts_prompt(payload))
    model = args.model or payload.get("model") or DEFAULT_MODEL
    output_path = request_output_path(payload)

    if not os.getenv("GEMINI_API_KEY"):
        raise RuntimeError("Set GEMINI_API_KEY before running Gemini TTS.")

    last_error: Optional[Exception] = None
    for attempt in range(1, args.retries + 2):
        try:
            if should_use_multi_speaker(payload):
                pcm = synthesize_multi(payload, model)
            else:
                pcm = synthesize_single(payload, model)
            break
        except Exception as exc:
            last_error = exc
            message = str(exc)
            retryable = RETRYABLE_ERROR_RE.search(message) is not None
            if not retryable or attempt > args.retries:
                raise
            sleep_for = args.backoff * attempt
            print(f"Gemini TTS request failed temporarily on attempt {attempt}: {message}")
            print(f"Retrying in {sleep_for:.1f}s...")
            time.sleep(sleep_for)
    else:
        raise RuntimeError("Gemini TTS failed without returning audio.") from last_error

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
        "tts_prompt": payload.get("tts_prompt"),
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
