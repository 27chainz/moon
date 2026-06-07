import json
import wave
from pathlib import Path
from typing import Any, Dict, List


GEMINI_TTS_MODEL = "gemini-2.5-pro-preview-tts"
GEMINI_TTS_FLASH_MODEL = "gemini-2.5-flash-preview-tts"
GEMINI_SAMPLE_RATE = 24000
GEMINI_SAMPLE_WIDTH = 2
GEMINI_CHANNELS = 1
GEMINI_MAX_SPEAKERS = 2
MIN_RENDERED_AUDIO_BYTES = 2048


class GeminiProductionError(RuntimeError):
    pass


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def request_output_path(payload: Dict[str, Any]) -> Path:
    value = payload.get("output_file") or payload.get("output_path")
    if not value:
        raise GeminiProductionError("Gemini request is missing output_file.")
    return Path(value)


def speaker_voices(payload: Dict[str, Any]) -> Dict[str, str]:
    voices = payload.get("speaker_voices")
    if voices:
        return voices
    return {
        speaker["speaker"]: speaker.get("provider_voice") or speaker.get("gemini_voice") or "Kore"
        for speaker in payload.get("speakers", [])
    }


def validate_gemini_request(payload: Dict[str, Any]) -> List[str]:
    warnings: List[str] = []
    request_output_path(payload)
    if not payload.get("chapter_context"):
        warnings.append("chapter_context is missing; performance consistency may drop.")
    if payload.get("speaker_voices"):
        if not payload.get("transcript"):
            raise GeminiProductionError("Multi-speaker Gemini request is missing transcript.")
        if len(payload["speaker_voices"]) > GEMINI_MAX_SPEAKERS:
            raise GeminiProductionError(
                f"Gemini multi-speaker TTS supports at most {GEMINI_MAX_SPEAKERS} speakers per request."
            )
    elif "voice" not in payload or "text" not in payload:
        raise GeminiProductionError("Gemini request must include either speaker_voices+transcript or voice+text.")

    model = payload.get("model")
    if model and model not in {GEMINI_TTS_MODEL, GEMINI_TTS_FLASH_MODEL}:
        warnings.append(f"Model {model!r} is not one of the configured Gemini TTS production models.")
    return warnings


def extract_pcm_from_response(response: Any) -> bytes:
    try:
        parts = response.candidates[0].content.parts
    except (AttributeError, IndexError) as exc:
        raise GeminiProductionError(f"Gemini response did not include an audio candidate: {response!r}") from exc

    for part in parts:
        inline_data = getattr(part, "inline_data", None)
        data = getattr(inline_data, "data", None)
        if data:
            return data
    raise GeminiProductionError("Gemini response did not include inline audio data.")


def save_wave(
    filename: Path,
    pcm: bytes,
    channels: int = GEMINI_CHANNELS,
    rate: int = GEMINI_SAMPLE_RATE,
    sample_width: int = GEMINI_SAMPLE_WIDTH,
) -> None:
    if len(pcm) < MIN_RENDERED_AUDIO_BYTES:
        raise GeminiProductionError(f"Rendered audio is suspiciously small: {len(pcm)} bytes.")
    filename.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(filename), "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(rate)
        wav_file.writeframes(pcm)


def wave_info(path: Path) -> Dict[str, Any]:
    with wave.open(str(path), "rb") as wav_file:
        frames = wav_file.getnframes()
        rate = wav_file.getframerate()
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
    return {
        "path": str(path),
        "frames": frames,
        "sample_rate": rate,
        "channels": channels,
        "sample_width": sample_width,
        "duration": round(frames / rate, 3) if rate else 0,
        "size_bytes": path.stat().st_size,
    }
