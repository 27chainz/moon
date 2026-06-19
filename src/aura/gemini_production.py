import json
import re
import wave
from pathlib import Path
from typing import Any, Dict, List


GEMINI_TTS_MODEL = "gemini-3.1-flash-tts-preview"
GEMINI_TTS_FLASH_MODEL = "gemini-3.1-flash-tts-preview"
GEMINI_SAMPLE_RATE = 24000
GEMINI_SAMPLE_WIDTH = 2
GEMINI_CHANNELS = 1
GEMINI_MAX_SPEAKERS = 2
MIN_RENDERED_AUDIO_BYTES = 2048
GEMINI_VOICE_NAMES = {
    "Zephyr",
    "Puck",
    "Charon",
    "Kore",
    "Fenrir",
    "Leda",
    "Orus",
    "Aoede",
    "Callirrhoe",
    "Autonoe",
    "Enceladus",
    "Iapetus",
    "Umbriel",
    "Algieba",
    "Despina",
    "Erinome",
    "Algenib",
    "Rasalgethi",
    "Laomedeia",
    "Achernar",
    "Alnilam",
    "Schedar",
    "Gacrux",
    "Pulcherrima",
    "Achird",
    "Zubenelgenubi",
    "Vindemiatrix",
    "Sadachbia",
    "Sadaltager",
    "Sulafat",
}
GEMINI_PROMPT_HEADINGS = [
    "# AUDIO PROFILE:",
    "## THE SCENE",
    "### DIRECTOR'S NOTES",
    "### CHARACTER STATE",
    "### SAMPLE CONTEXT",
    "#### TRANSCRIPT",
]
GEMINI_REQUIRED_HEADINGS = [
    "# AUDIO PROFILE:",
    "## THE SCENE",
    "### DIRECTOR'S NOTES",
    "### SAMPLE CONTEXT",
    "#### TRANSCRIPT",
]
TRANSCRIPT_LINE_RE = re.compile(r"^Speaker\d+:\s+\S", re.M)
# Gemini TTS context window (documented hard limit: 32k tokens).
# We use a conservative 4 chars-per-token estimate for English text.
TTS_CONTEXT_WINDOW_TOKENS = 32_768
TTS_TOKEN_WARN_THRESHOLD = 28_000  # warn at ~85% of limit


class GeminiProductionError(RuntimeError):
    pass


def estimate_prompt_tokens(text: str) -> int:
    """Conservative token estimate for Gemini TTS prompts.

    Gemini uses a subword tokeniser; English text averages 3-5 chars per token.
    We use 4 chars/token as a safe middle estimate. This is intentionally
    conservative to avoid silently approaching the 32k TTS context limit.
    """
    return max(1, len(text) // 4)


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
        for speaker, voice in payload["speaker_voices"].items():
            if voice not in GEMINI_VOICE_NAMES:
                raise GeminiProductionError(
                    f"Gemini speaker {speaker!r} uses unsupported voice {voice!r}. "
                    f"Use one of: {', '.join(sorted(GEMINI_VOICE_NAMES))}"
                )
    elif "voice" not in payload or "text" not in payload:
        raise GeminiProductionError("Gemini request must include either speaker_voices+transcript or voice+text.")
    else:
        voice = payload.get("voice") or {}
        voice_name = voice.get("provider_voice") or voice.get("gemini_voice")
        if voice_name and voice_name not in GEMINI_VOICE_NAMES:
            raise GeminiProductionError(
                f"Gemini request uses unsupported voice {voice_name!r}. "
                f"Use one of: {', '.join(sorted(GEMINI_VOICE_NAMES))}"
            )

    model = payload.get("model")
    if model and model not in {GEMINI_TTS_MODEL, GEMINI_TTS_FLASH_MODEL}:
        warnings.append(f"Model {model!r} is not one of the configured Gemini TTS production models.")
    return warnings


def validate_gemini_tts_prompt(payload: Dict[str, Any]) -> List[str]:
    """Validate the Gemini-facing prompt before paid rendering starts."""
    warnings: List[str] = []
    prompt = payload.get("tts_prompt")
    if not prompt:
        warnings.append("tts_prompt is missing; runner will fall back to legacy prompt construction.")
        return warnings

    missing = [heading for heading in GEMINI_REQUIRED_HEADINGS if heading not in prompt]
    if missing:
        raise GeminiProductionError(f"Gemini tts_prompt is missing required section(s): {', '.join(missing)}")

    # Token size guard — Gemini TTS has a 32k token context window (documented).
    estimated_tokens = estimate_prompt_tokens(prompt)
    if estimated_tokens > TTS_CONTEXT_WINDOW_TOKENS:
        raise GeminiProductionError(
            f"tts_prompt is too long (~{estimated_tokens:,} tokens estimated; "
            f"limit is {TTS_CONTEXT_WINDOW_TOKENS:,}). "
            "Split into smaller chunks or reduce prompt content."
        )
    if estimated_tokens > TTS_TOKEN_WARN_THRESHOLD:
        warnings.append(
            f"tts_prompt is large (~{estimated_tokens:,} tokens estimated). "
            f"Approaching the {TTS_CONTEXT_WINDOW_TOKENS:,}-token Gemini TTS context limit."
        )


    # Check required headings are in order; CHARACTER STATE is optional but must appear
    # between DIRECTOR'S NOTES and SAMPLE CONTEXT when present.
    required_positions = [prompt.index(h) for h in GEMINI_REQUIRED_HEADINGS]
    if required_positions != sorted(required_positions):
        raise GeminiProductionError(
            "Gemini tts_prompt sections must appear in order: "
            + " -> ".join(GEMINI_REQUIRED_HEADINGS)
        )
    if "### CHARACTER STATE" in prompt:
        state_pos = prompt.index("### CHARACTER STATE")
        notes_pos = prompt.index("### DIRECTOR'S NOTES")
        context_pos = prompt.index("### SAMPLE CONTEXT")
        if not (notes_pos < state_pos < context_pos):
            raise GeminiProductionError(
                "### CHARACTER STATE must appear between ### DIRECTOR'S NOTES and ### SAMPLE CONTEXT."
            )

    transcript_index = prompt.index("#### TRANSCRIPT")
    transcript = prompt[transcript_index:]
    if not TRANSCRIPT_LINE_RE.search(transcript):
        raise GeminiProductionError("Gemini tts_prompt transcript must contain SpeakerN lines.")

    if "Do not read these instructions aloud." not in prompt:
        raise GeminiProductionError("Gemini tts_prompt is missing the anti-read-aloud preamble.")
    if "Begin speaking only when you reach TRANSCRIPT." not in prompt:
        raise GeminiProductionError("Gemini tts_prompt is missing the TRANSCRIPT boundary instruction.")

    for speaker in speaker_voices(payload):
        if f"{speaker}:" not in transcript:
            raise GeminiProductionError(f"Gemini tts_prompt transcript does not include configured speaker {speaker!r}.")

    forbidden_after_transcript = [
        "Stitch QA note:",
        "QA note:",
        "CONTINUITY PACKET",
        "JOIN CONTEXT",
        "DO NOT SPEAK",
    ]
    for phrase in forbidden_after_transcript:
        if phrase in transcript:
            raise GeminiProductionError(f"Internal note leaked into Gemini transcript: {phrase}")

    return warnings


def extract_pcm_from_response(response: Any) -> bytes:
    response_summary = summarize_gemini_response(response)
    try:
        parts = response.candidates[0].content.parts
    except (AttributeError, IndexError) as exc:
        raise GeminiProductionError(
            "Gemini response did not include an audio candidate. "
            f"Response summary: {response_summary}"
        ) from exc

    if not parts:
        raise GeminiProductionError(
            "Gemini response candidate did not include audio parts. "
            f"Response summary: {response_summary}"
        )

    for part in parts:
        inline_data = getattr(part, "inline_data", None)
        data = getattr(inline_data, "data", None)
        if data:
            return data
    raise GeminiProductionError(
        "Gemini response did not include inline audio data. "
        f"Response summary: {response_summary}"
    )


def summarize_gemini_response(response: Any) -> Dict[str, Any]:
    summary: Dict[str, Any] = {}
    for field in ("prompt_feedback", "usage_metadata", "model_version"):
        value = getattr(response, field, None)
        if value is not None:
            summary[field] = repr(value)

    candidates = getattr(response, "candidates", None) or []
    summary["candidate_count"] = len(candidates)
    candidate_summaries = []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        parts = getattr(content, "parts", None) if content is not None else None
        part_summaries = []
        for part in parts or []:
            inline_data = getattr(part, "inline_data", None)
            text = getattr(part, "text", None)
            part_summaries.append(
                {
                    "has_inline_data": bool(getattr(inline_data, "data", None)),
                    "mime_type": getattr(inline_data, "mime_type", None),
                    "text_preview": text[:200] if isinstance(text, str) else None,
                }
            )
        candidate_summaries.append(
            {
                "finish_reason": getattr(candidate, "finish_reason", None),
                "parts": part_summaries,
            }
        )
    summary["candidates"] = candidate_summaries
    return summary


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
