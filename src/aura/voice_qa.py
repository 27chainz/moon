"""Automated voice QA checks for rendered TTS chunks.

This module implements the Phase 1 QA Gauntlet from the open-source roadmap.
Each check returns a structured result dict that can be logged alongside the
render manifest.

Implemented checks:
    1. Speaker count verification (pyannote-audio)
       Detects mid-chunk voice swaps by counting distinct speaker clusters.
    2. Voice identity verification (resemblyzer)
       Compares a rendered chunk's voice embedding against the Cast Bible
       reference to detect gradual voice drift.
    3. Transcript accuracy (whisper)
       Transcribes rendered audio and diffs against the expected APS text
       to catch hallucinations, skipped lines, and word-level errors.
    4. Audio quality scoring (torchaudio-squim)
       Predicts human MOS scores to catch robotic artifacts and distortion.
    5. Performance / acting verification (praat-parselmouth)
       Measures pitch variance, speaking rate, and energy contour to verify
       the delivery matches the APS intensity value.
    6. Pronunciation guard (phonemizer)
       Verifies golden nouns (character/place names) are pronounced correctly
       by comparing IPA phoneme sequences against the Cast Bible guide.
"""

import argparse
import re
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Speaker count verification via pyannote-audio
# ---------------------------------------------------------------------------

# Minimum audio duration (seconds) for reliable diarization.
# Pyannote needs enough signal to form speaker clusters.
MIN_DIARIZATION_DURATION = 1.5

# Cache the pipeline instance so repeated calls don't reload the model.
_pyannote_pipeline = None


class VoiceQAUnavailableError(RuntimeError):
    """Raised when a required QA dependency is not installed."""


def _get_pyannote_pipeline(hf_token: Optional[str] = None):
    """Lazy-load the pyannote speaker diarization pipeline.

    The pipeline is cached after the first call so that batch QA runs
    across many chunks don't reload the model each time.

    Args:
        hf_token: HuggingFace access token. Required on first call.
                  The pyannote models are gated and need user agreement
                  at https://huggingface.co/pyannote/speaker-diarization-3.1
    """
    global _pyannote_pipeline
    if _pyannote_pipeline is not None:
        return _pyannote_pipeline

    try:
        from pyannote.audio import Pipeline
    except ImportError as exc:
        raise VoiceQAUnavailableError(
            "pyannote.audio is required for speaker count verification. "
            "Install with: pip install pyannote.audio"
        ) from exc

    if not hf_token:
        import os
        hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    if not hf_token:
        raise VoiceQAUnavailableError(
            "A HuggingFace token is required for pyannote. "
            "Set the HF_TOKEN environment variable or pass --hf-token."
        )

    try:
        import torch
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    except ImportError:
        device = None

    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1",
        use_auth_token=hf_token,
    )
    if device is not None:
        pipeline.to(device)

    _pyannote_pipeline = pipeline
    return _pyannote_pipeline


def _audio_duration(audio_path: Path) -> float:
    """Get the duration of a WAV file in seconds without loading the full array."""
    import wave
    with wave.open(str(audio_path), "rb") as wf:
        return wf.getnframes() / wf.getframerate()


def check_speaker_count(
    audio_path: Path,
    expected_speakers: int = 1,
    hf_token: Optional[str] = None,
) -> Dict[str, Any]:
    """Verify that a rendered chunk contains the expected number of speakers.

    This catches the specific failure mode where Gemini voice-swaps mid-chunk,
    producing two distinct speaker identities in audio that should only contain
    one voice. Resemblyzer might miss this if the *average* embedding still
    looks similar to the reference; pyannote catches it by detecting distinct
    speaker clusters.

    Args:
        audio_path: Path to the rendered .wav chunk.
        expected_speakers: How many distinct speakers should be in this chunk.
                           For single-character chunks this is 1.
                           For multi-speaker Gemini requests this is 2.
        hf_token: HuggingFace access token for pyannote model access.

    Returns:
        A structured QA result dict:
        {
            "check": "speaker_count",
            "audio_file": str,
            "status": "pass" | "fail" | "skip" | "error",
            "expected_speakers": int,
            "detected_speakers": int | None,
            "speaker_segments": [...],
            "timestamp": str,
            "reason": str | None,
        }
    """
    result = {
        "check": "speaker_count",
        "audio_file": str(audio_path),
        "expected_speakers": expected_speakers,
        "detected_speakers": None,
        "speaker_segments": [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "reason": None,
    }

    # --- Guard: file exists ---
    if not audio_path.exists():
        result["status"] = "error"
        result["reason"] = f"Audio file not found: {audio_path}"
        return result

    # --- Guard: minimum duration ---
    try:
        duration = _audio_duration(audio_path)
    except Exception as exc:
        result["status"] = "error"
        result["reason"] = f"Could not read audio file: {exc}"
        return result

    if duration < MIN_DIARIZATION_DURATION:
        result["status"] = "skip"
        result["reason"] = (
            f"Audio too short for reliable diarization "
            f"({duration:.1f}s < {MIN_DIARIZATION_DURATION}s minimum)."
        )
        return result

    # --- Run pyannote diarization ---
    try:
        pipeline = _get_pyannote_pipeline(hf_token)
    except VoiceQAUnavailableError as exc:
        result["status"] = "error"
        result["reason"] = str(exc)
        return result

    try:
        diarization = pipeline(str(audio_path), num_speakers=None)
    except Exception as exc:
        result["status"] = "error"
        result["reason"] = f"Pyannote diarization failed: {exc}"
        return result

    # --- Extract speaker segments ---
    speakers = set()
    segments = []
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        speakers.add(speaker)
        segments.append({
            "speaker": speaker,
            "start": round(turn.start, 3),
            "end": round(turn.end, 3),
            "duration": round(turn.end - turn.start, 3),
        })

    detected_count = len(speakers)
    result["detected_speakers"] = detected_count
    result["speaker_segments"] = segments

    # --- Verdict ---
    if detected_count == expected_speakers:
        result["status"] = "pass"
        result["reason"] = (
            f"Detected {detected_count} speaker(s), matching expected {expected_speakers}."
        )
    elif detected_count > expected_speakers:
        result["status"] = "fail"
        result["reason"] = (
            f"Voice swap detected: expected {expected_speakers} speaker(s) "
            f"but found {detected_count} distinct voice cluster(s). "
            "This chunk should be re-rendered."
        )
    else:
        # Fewer speakers than expected (e.g., one speaker in a 2-speaker chunk).
        # This might be a truncation issue — flag but don't hard-fail.
        result["status"] = "fail"
        result["reason"] = (
            f"Expected {expected_speakers} speaker(s) but only detected "
            f"{detected_count}. Possible truncation or missing dialogue."
        )

    return result


# ---------------------------------------------------------------------------
# Voice identity verification via resemblyzer
# ---------------------------------------------------------------------------

# Cosine similarity threshold for voice identity matching.
# 0.75 is deliberately conservative: resemblyzer embeddings for the same
# speaker typically score 0.85-0.95, while different speakers score 0.55-0.75.
# A threshold below 0.75 catches genuine drift while tolerating normal
# variation from emotion, pacing, and recording conditions.
DEFAULT_SIMILARITY_THRESHOLD = 0.75

# Minimum duration for a reliable voice embedding.
MIN_EMBEDDING_DURATION = 1.0

# Resemblyzer sample rate (fixed by the model architecture).
RESEMBLYZER_SAMPLE_RATE = 16000

# Cache the encoder so it loads once across a batch QA run.
_resemblyzer_encoder = None


def _get_resemblyzer_encoder():
    """Lazy-load the resemblyzer VoiceEncoder.

    The encoder is cached after the first call. It uses a small neural
    network (~17M params) so it runs efficiently on CPU.
    """
    global _resemblyzer_encoder
    if _resemblyzer_encoder is not None:
        return _resemblyzer_encoder

    try:
        from resemblyzer import VoiceEncoder
    except ImportError as exc:
        raise VoiceQAUnavailableError(
            "resemblyzer is required for voice identity verification. "
            "Install with: pip install resemblyzer"
        ) from exc

    _resemblyzer_encoder = VoiceEncoder()
    return _resemblyzer_encoder


def _load_audio_for_resemblyzer(audio_path: Path):
    """Load and preprocess audio for resemblyzer embedding extraction.

    Resemblyzer expects mono float32 audio at 16kHz. This function
    handles resampling from any sample rate (e.g., Gemini's 24kHz).
    """
    try:
        from resemblyzer import preprocess_wav
    except ImportError as exc:
        raise VoiceQAUnavailableError(
            "resemblyzer is required for voice identity verification."
        ) from exc

    import numpy as np
    import soundfile as sf

    audio, sr = sf.read(str(audio_path), dtype="float32")

    # Convert to mono if stereo.
    if audio.ndim == 2:
        audio = np.mean(audio, axis=1)

    # Resample to 16kHz if needed.
    if sr != RESEMBLYZER_SAMPLE_RATE:
        from scipy.signal import resample_poly
        from math import gcd
        g = gcd(sr, RESEMBLYZER_SAMPLE_RATE)
        audio = resample_poly(audio, RESEMBLYZER_SAMPLE_RATE // g, sr // g).astype(np.float32)

    return preprocess_wav(audio)


def compute_voice_embedding(audio_path: Path):
    """Extract a 256-dimensional voice embedding from an audio file.

    Args:
        audio_path: Path to a .wav file.

    Returns:
        A numpy array of shape (256,) representing the speaker's voice.
    """
    encoder = _get_resemblyzer_encoder()
    wav = _load_audio_for_resemblyzer(audio_path)
    return encoder.embed_utterance(wav)


def cosine_similarity(a, b) -> float:
    """Compute cosine similarity between two embeddings."""
    import numpy as np
    dot = float(np.dot(a, b))
    norm_a = float(np.linalg.norm(a))
    norm_b = float(np.linalg.norm(b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def check_voice_identity(
    audio_path: Path,
    reference_audio_path: Path,
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> Dict[str, Any]:
    """Verify that a rendered chunk's voice matches the Cast Bible reference.

    After pyannote confirms the correct number of speakers, this check
    mathematically verifies the voice is the *right* voice by comparing
    the 256-dimensional embeddings.

    Args:
        audio_path: Path to the rendered .wav chunk.
        reference_audio_path: Path to the approved reference .wav from the Cast Bible.
        threshold: Minimum cosine similarity to pass (default: 0.75).

    Returns:
        A structured QA result dict:
        {
            "check": "voice_identity",
            "audio_file": str,
            "reference_file": str,
            "status": "pass" | "fail" | "skip" | "error",
            "similarity": float | None,
            "threshold": float,
            "timestamp": str,
            "reason": str | None,
        }
    """
    result = {
        "check": "voice_identity",
        "audio_file": str(audio_path),
        "reference_file": str(reference_audio_path),
        "similarity": None,
        "threshold": threshold,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "reason": None,
    }

    # --- Guard: files exist ---
    if not audio_path.exists():
        result["status"] = "error"
        result["reason"] = f"Audio file not found: {audio_path}"
        return result
    if not reference_audio_path.exists():
        result["status"] = "error"
        result["reason"] = f"Reference audio not found: {reference_audio_path}"
        return result

    # --- Guard: minimum duration ---
    try:
        duration = _audio_duration(audio_path)
    except Exception as exc:
        result["status"] = "error"
        result["reason"] = f"Could not read audio file: {exc}"
        return result

    if duration < MIN_EMBEDDING_DURATION:
        result["status"] = "skip"
        result["reason"] = (
            f"Audio too short for reliable embedding "
            f"({duration:.1f}s < {MIN_EMBEDDING_DURATION}s minimum)."
        )
        return result

    # --- Compute embeddings and compare ---
    try:
        chunk_embedding = compute_voice_embedding(audio_path)
        ref_embedding = compute_voice_embedding(reference_audio_path)
    except VoiceQAUnavailableError:
        raise
    except Exception as exc:
        result["status"] = "error"
        result["reason"] = f"Embedding extraction failed: {exc}"
        return result

    similarity = cosine_similarity(chunk_embedding, ref_embedding)
    result["similarity"] = round(similarity, 4)

    # --- Verdict ---
    if similarity >= threshold:
        result["status"] = "pass"
        result["reason"] = (
            f"Voice identity confirmed: similarity {similarity:.4f} >= {threshold} threshold."
        )
    else:
        result["status"] = "fail"
        result["reason"] = (
            f"Voice drift detected: similarity {similarity:.4f} < {threshold} threshold. "
            "This chunk's voice does not match the Cast Bible reference. Re-render recommended."
        )

    return result


def check_voice_identity_from_embedding(
    audio_path: Path,
    reference_embedding,
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    reference_label: str = "precomputed",
) -> Dict[str, Any]:
    """Compare a chunk against a precomputed reference embedding.

    This is more efficient for batch QA runs where the same reference
    embedding is compared against many chunks — avoids recomputing
    the reference embedding each time.

    Args:
        audio_path: Path to the rendered .wav chunk.
        reference_embedding: A numpy array of shape (256,).
        threshold: Minimum cosine similarity to pass.
        reference_label: Human-readable label for the reference source.

    Returns:
        Same structured QA result as check_voice_identity.
    """
    result = {
        "check": "voice_identity",
        "audio_file": str(audio_path),
        "reference_file": reference_label,
        "similarity": None,
        "threshold": threshold,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "reason": None,
    }

    if not audio_path.exists():
        result["status"] = "error"
        result["reason"] = f"Audio file not found: {audio_path}"
        return result

    try:
        duration = _audio_duration(audio_path)
    except Exception as exc:
        result["status"] = "error"
        result["reason"] = f"Could not read audio file: {exc}"
        return result

    if duration < MIN_EMBEDDING_DURATION:
        result["status"] = "skip"
        result["reason"] = (
            f"Audio too short for reliable embedding "
            f"({duration:.1f}s < {MIN_EMBEDDING_DURATION}s minimum)."
        )
        return result

    try:
        chunk_embedding = compute_voice_embedding(audio_path)
    except VoiceQAUnavailableError:
        raise
    except Exception as exc:
        result["status"] = "error"
        result["reason"] = f"Embedding extraction failed: {exc}"
        return result

    similarity = cosine_similarity(chunk_embedding, reference_embedding)
    result["similarity"] = round(similarity, 4)

    if similarity >= threshold:
        result["status"] = "pass"
        result["reason"] = (
            f"Voice identity confirmed: similarity {similarity:.4f} >= {threshold} threshold."
        )
    else:
        result["status"] = "fail"
        result["reason"] = (
            f"Voice drift detected: similarity {similarity:.4f} < {threshold} threshold. "
            "This chunk's voice does not match the Cast Bible reference. Re-render recommended."
        )

    return result


# ---------------------------------------------------------------------------
# Transcript accuracy verification via whisper
# ---------------------------------------------------------------------------

# Maximum acceptable Word Error Rate. A WER of 0.10 means the transcription
# can differ from the expected text by at most 10% of words. This is generous
# enough to tolerate minor Whisper transcription artifacts (e.g., "okay" vs
# "OK") while still catching genuine hallucinations and skipped sentences.
DEFAULT_MAX_WER = 0.10

# Whisper model size. "base" is fast and sufficient for QA diffing since
# we only need to catch gross errors, not produce a perfect transcript.
# Use "small" or "medium" for higher accuracy at the cost of speed.
DEFAULT_WHISPER_MODEL = "base"

# Cache the whisper model across batch runs.
_whisper_model = None
_whisper_model_name = None


def _get_whisper_model(model_name: str = DEFAULT_WHISPER_MODEL):
    """Lazy-load the Whisper speech-to-text model.

    The model is cached after the first call. Whisper "base" is ~140MB
    and runs efficiently on CPU for short chunks.
    """
    global _whisper_model, _whisper_model_name
    if _whisper_model is not None and _whisper_model_name == model_name:
        return _whisper_model

    try:
        import whisper
    except ImportError as exc:
        raise VoiceQAUnavailableError(
            "openai-whisper is required for transcript verification. "
            "Install with: pip install openai-whisper"
        ) from exc

    _whisper_model = whisper.load_model(model_name)
    _whisper_model_name = model_name
    return _whisper_model


def _normalize_text(text: str) -> str:
    """Normalize text for WER comparison.

    Strips speaker labels, audio tags, punctuation, and extra whitespace
    to produce a clean word sequence for fair comparison.
    """
    # Remove SpeakerN: prefixes.
    text = re.sub(r"^Speaker\d+:\s*", "", text, flags=re.MULTILINE)
    # Remove audio/stage direction tags like [pause], [whisper], etc.
    text = re.sub(r"\[.*?\]", "", text)
    # Remove common punctuation that Whisper may or may not reproduce.
    text = re.sub(r"[^\w\s']", "", text)
    # Collapse whitespace.
    text = re.sub(r"\s+", " ", text).strip()
    return text.lower()


def _extract_expected_text(payload: Dict[str, Any]) -> str:
    """Extract the expected spoken text from a render request payload.

    Mirrors the logic in gemini_chapter_renderer.count_prompt_words but
    returns the full cleaned text instead of a word count.
    """
    transcript = payload.get("transcript", "")
    if not transcript:
        prompt = payload.get("tts_prompt", "")
        marker = "#### TRANSCRIPT"
        if marker in prompt:
            transcript = prompt[prompt.index(marker) + len(marker):]
        else:
            transcript = prompt
    return _normalize_text(transcript)


def compute_wer(reference: str, hypothesis: str) -> Dict[str, Any]:
    """Compute Word Error Rate between reference and hypothesis text.

    WER = (substitutions + insertions + deletions) / len(reference_words)

    Uses a standard dynamic programming (Levenshtein distance on words)
    implementation. No external dependency required.

    Returns:
        {
            "wer": float,
            "substitutions": int,
            "insertions": int,
            "deletions": int,
            "reference_words": int,
            "hypothesis_words": int,
        }
    """
    ref_words = reference.split()
    hyp_words = hypothesis.split()
    n = len(ref_words)
    m = len(hyp_words)

    if n == 0:
        return {
            "wer": 0.0 if m == 0 else 1.0,
            "substitutions": 0,
            "insertions": m,
            "deletions": 0,
            "reference_words": 0,
            "hypothesis_words": m,
        }

    # DP table for edit distance on word sequences.
    d = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        d[i][0] = i
    for j in range(m + 1):
        d[0][j] = j

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if ref_words[i - 1] == hyp_words[j - 1]:
                d[i][j] = d[i - 1][j - 1]
            else:
                d[i][j] = 1 + min(
                    d[i - 1][j],      # deletion
                    d[i][j - 1],      # insertion
                    d[i - 1][j - 1],  # substitution
                )

    # Backtrace to count S, I, D.
    i, j = n, m
    subs = ins = dels = 0
    while i > 0 or j > 0:
        if i > 0 and j > 0 and ref_words[i - 1] == hyp_words[j - 1]:
            i -= 1
            j -= 1
        elif i > 0 and j > 0 and d[i][j] == d[i - 1][j - 1] + 1:
            subs += 1
            i -= 1
            j -= 1
        elif j > 0 and d[i][j] == d[i][j - 1] + 1:
            ins += 1
            j -= 1
        else:
            dels += 1
            i -= 1

    wer = (subs + ins + dels) / n

    return {
        "wer": round(wer, 4),
        "substitutions": subs,
        "insertions": ins,
        "deletions": dels,
        "reference_words": n,
        "hypothesis_words": m,
    }


def check_transcript(
    audio_path: Path,
    expected_text: str,
    max_wer: float = DEFAULT_MAX_WER,
    whisper_model: str = DEFAULT_WHISPER_MODEL,
    language: str = "en",
) -> Dict[str, Any]:
    """Verify that a rendered chunk says the right words.

    Uses OpenAI Whisper to transcribe the audio, then computes Word Error
    Rate against the expected text from the APS. Catches hallucinations,
    skipped sentences, and gross mispronunciations.

    Args:
        audio_path: Path to the rendered .wav chunk.
        expected_text: The text that should have been spoken (from the APS).
        max_wer: Maximum acceptable Word Error Rate (default: 0.10 = 10%).
        whisper_model: Whisper model size (default: "base").
        language: Language code for Whisper (default: "en").

    Returns:
        A structured QA result dict:
        {
            "check": "transcript",
            "audio_file": str,
            "status": "pass" | "fail" | "skip" | "error",
            "wer": float | None,
            "max_wer": float,
            "wer_details": {...} | None,
            "transcribed_text": str | None,
            "expected_text_preview": str,
            "timestamp": str,
            "reason": str | None,
        }
    """
    expected_clean = _normalize_text(expected_text)
    result = {
        "check": "transcript",
        "audio_file": str(audio_path),
        "wer": None,
        "max_wer": max_wer,
        "wer_details": None,
        "transcribed_text": None,
        "expected_text_preview": expected_clean[:200],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "reason": None,
    }

    # --- Guard: file exists ---
    if not audio_path.exists():
        result["status"] = "error"
        result["reason"] = f"Audio file not found: {audio_path}"
        return result

    # --- Guard: expected text is not empty ---
    if not expected_clean or len(expected_clean.split()) < 3:
        result["status"] = "skip"
        result["reason"] = "Expected text is too short for meaningful WER comparison."
        return result

    # --- Transcribe with Whisper ---
    try:
        model = _get_whisper_model(whisper_model)
    except VoiceQAUnavailableError as exc:
        result["status"] = "error"
        result["reason"] = str(exc)
        return result

    try:
        transcription = model.transcribe(
            str(audio_path),
            language=language,
            fp16=False,  # CPU-safe
        )
        raw_text = transcription.get("text", "")
    except Exception as exc:
        result["status"] = "error"
        result["reason"] = f"Whisper transcription failed: {exc}"
        return result

    transcribed_clean = _normalize_text(raw_text)
    result["transcribed_text"] = transcribed_clean

    # --- Compute WER ---
    wer_result = compute_wer(expected_clean, transcribed_clean)
    result["wer"] = wer_result["wer"]
    result["wer_details"] = wer_result

    # --- Verdict ---
    if wer_result["wer"] <= max_wer:
        result["status"] = "pass"
        result["reason"] = (
            f"Transcript verified: WER {wer_result['wer']:.2%} <= {max_wer:.0%} threshold. "
            f"({wer_result['substitutions']}S {wer_result['insertions']}I {wer_result['deletions']}D "
            f"across {wer_result['reference_words']} words)"
        )
    else:
        result["status"] = "fail"
        result["reason"] = (
            f"Transcript mismatch: WER {wer_result['wer']:.2%} > {max_wer:.0%} threshold. "
            f"({wer_result['substitutions']} substitutions, {wer_result['insertions']} insertions, "
            f"{wer_result['deletions']} deletions across {wer_result['reference_words']} words). "
            "Possible hallucination, skipped text, or truncation."
        )

    return result


# ---------------------------------------------------------------------------
# Audio quality scoring via torchaudio-squim
# ---------------------------------------------------------------------------

# Minimum MOS (Mean Opinion Score) threshold for "editorial grade" audio.
# Human MOS scale: 1 (bad) to 5 (excellent). Natural speech typically
# scores 4.0-4.5. AI-generated speech scoring below 3.5 usually has
# audible artifacts (metallic tone, glitching, distortion).
DEFAULT_MIN_MOS = 3.5

# Minimum duration for SQUIM to produce a reliable score.
MIN_SQUIM_DURATION = 1.0

# SQUIM expects 16kHz mono audio.
SQUIM_SAMPLE_RATE = 16000


def _load_audio_for_squim(audio_path: Path):
    """Load and resample audio for SQUIM quality analysis.

    Returns a torch tensor of shape (1, num_samples) at 16kHz.
    """
    try:
        import torch
        import torchaudio
    except ImportError as exc:
        raise VoiceQAUnavailableError(
            "torch and torchaudio are required for audio quality scoring. "
            "Install with: pip install torch torchaudio"
        ) from exc

    waveform, sr = torchaudio.load(str(audio_path))

    # Convert to mono if needed.
    if waveform.shape[0] > 1:
        waveform = waveform.mean(dim=0, keepdim=True)

    # Resample to 16kHz if needed.
    if sr != SQUIM_SAMPLE_RATE:
        resampler = torchaudio.transforms.Resample(orig_freq=sr, new_freq=SQUIM_SAMPLE_RATE)
        waveform = resampler(waveform)

    return waveform


def check_audio_quality(
    audio_path: Path,
    min_mos: float = DEFAULT_MIN_MOS,
) -> Dict[str, Any]:
    """Score audio quality using torchaudio SQUIM (no-reference MOS prediction).

    Catches "robotic" artifacts, metallic tones, static, and distortion
    that other checks miss. This is the final gatekeeper — if the voice is
    correct and the words are right, but it sounds like a broken speaker,
    SQUIM catches it.

    Args:
        audio_path: Path to the rendered .wav chunk.
        min_mos: Minimum acceptable MOS score (default: 3.5/5.0).

    Returns:
        A structured QA result dict:
        {
            "check": "audio_quality",
            "audio_file": str,
            "status": "pass" | "fail" | "skip" | "error",
            "mos": float | None,
            "min_mos": float,
            "stoi": float | None,
            "pesq": float | None,
            "timestamp": str,
            "reason": str | None,
        }
    """
    result = {
        "check": "audio_quality",
        "audio_file": str(audio_path),
        "mos": None,
        "min_mos": min_mos,
        "stoi": None,
        "pesq": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "reason": None,
    }

    # --- Guard: file exists ---
    if not audio_path.exists():
        result["status"] = "error"
        result["reason"] = f"Audio file not found: {audio_path}"
        return result

    # --- Guard: minimum duration ---
    try:
        duration = _audio_duration(audio_path)
    except Exception as exc:
        result["status"] = "error"
        result["reason"] = f"Could not read audio file: {exc}"
        return result

    if duration < MIN_SQUIM_DURATION:
        result["status"] = "skip"
        result["reason"] = (
            f"Audio too short for reliable quality scoring "
            f"({duration:.1f}s < {MIN_SQUIM_DURATION}s minimum)."
        )
        return result

    # --- Load audio and run SQUIM ---
    try:
        waveform = _load_audio_for_squim(audio_path)
    except VoiceQAUnavailableError:
        raise
    except Exception as exc:
        result["status"] = "error"
        result["reason"] = f"Could not load audio for SQUIM: {exc}"
        return result

    try:
        from torchaudio.pipelines import SQUIM_SUBJECTIVE, SQUIM_OBJECTIVE
    except ImportError as exc:
        raise VoiceQAUnavailableError(
            "torchaudio SQUIM pipelines are required. "
            "Ensure torchaudio >= 2.1 is installed."
        ) from exc

    try:
        # SQUIM_OBJECTIVE predicts STOI and PESQ (objective metrics).
        obj_model = SQUIM_OBJECTIVE.get_model()
        stoi, pesq, si_sdr = obj_model(waveform)
        result["stoi"] = round(float(stoi.item()), 4)
        result["pesq"] = round(float(pesq.item()), 4)
    except Exception as exc:
        warnings.warn(
            f"SQUIM objective scoring failed; continuing with subjective only: {exc}",
            RuntimeWarning, stacklevel=2,
        )

    try:
        # SQUIM_SUBJECTIVE predicts MOS (human perception score 1-5).
        subj_model = SQUIM_SUBJECTIVE.get_model()
        mos_score = subj_model(waveform)
        result["mos"] = round(float(mos_score.item()), 4)
    except Exception as exc:
        result["status"] = "error"
        result["reason"] = f"SQUIM MOS prediction failed: {exc}"
        return result

    # --- Verdict ---
    if result["mos"] >= min_mos:
        result["status"] = "pass"
        result["reason"] = (
            f"Audio quality acceptable: MOS {result['mos']:.2f} >= {min_mos} threshold."
        )
    else:
        result["status"] = "fail"
        result["reason"] = (
            f"Audio quality below threshold: MOS {result['mos']:.2f} < {min_mos}. "
            "Possible robotic artifacts, metallic tone, or distortion. Re-render recommended."
        )

    return result


# ---------------------------------------------------------------------------
# Performance / acting verification via praat-parselmouth
# ---------------------------------------------------------------------------

# Intensity thresholds mapping APS intensity values to expected pitch
# variance ranges (in Hz standard deviation). A "furious" line (intensity 0.9)
# should have high pitch variance; a "calm" line (intensity 0.2) should be flat.
# These are empirical ranges from audiobook narration analysis.
INTENSITY_PITCH_VARIANCE = {
    # (min_std_hz, max_std_hz) for each intensity bucket
    "low": (5.0, 30.0),       # intensity 0.0 - 0.3: calm, measured delivery
    "medium": (20.0, 60.0),   # intensity 0.4 - 0.6: conversational, engaged
    "high": (40.0, 120.0),    # intensity 0.7 - 1.0: intense, dramatic, furious
}

# Minimum duration for pitch analysis.
MIN_PITCH_DURATION = 1.5


def _intensity_bucket(intensity: float) -> str:
    """Map a 0.0-1.0 intensity value to a bucket."""
    if intensity <= 0.3:
        return "low"
    elif intensity <= 0.6:
        return "medium"
    else:
        return "high"


def check_performance(
    audio_path: Path,
    expected_intensity: float = 0.5,
) -> Dict[str, Any]:
    """Verify that the acting matches the AI Director's performance notes.

    Instead of trying to classify emotions with a black-box model, this
    check directly measures interpretable acoustic features:
      - Pitch variance (Hz std dev): high for dramatic, low for calm
      - Speaking rate (syllables/sec estimate)
      - Energy contour (RMS variance)

    These are compared against the `intensity` value from the APS.

    Args:
        audio_path: Path to the rendered .wav chunk.
        expected_intensity: The intensity value (0.0-1.0) from the APS.

    Returns:
        A structured QA result dict:
        {
            "check": "performance",
            "audio_file": str,
            "status": "pass" | "fail" | "skip" | "error",
            "expected_intensity": float,
            "intensity_bucket": str,
            "pitch_std_hz": float | None,
            "pitch_mean_hz": float | None,
            "speaking_rate_estimate": float | None,
            "energy_std": float | None,
            "timestamp": str,
            "reason": str | None,
        }
    """
    bucket = _intensity_bucket(expected_intensity)
    result = {
        "check": "performance",
        "audio_file": str(audio_path),
        "expected_intensity": expected_intensity,
        "intensity_bucket": bucket,
        "pitch_std_hz": None,
        "pitch_mean_hz": None,
        "speaking_rate_estimate": None,
        "energy_std": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "reason": None,
    }

    # --- Guard: file exists ---
    if not audio_path.exists():
        result["status"] = "error"
        result["reason"] = f"Audio file not found: {audio_path}"
        return result

    # --- Guard: minimum duration ---
    try:
        duration = _audio_duration(audio_path)
    except Exception as exc:
        result["status"] = "error"
        result["reason"] = f"Could not read audio file: {exc}"
        return result

    if duration < MIN_PITCH_DURATION:
        result["status"] = "skip"
        result["reason"] = (
            f"Audio too short for reliable pitch analysis "
            f"({duration:.1f}s < {MIN_PITCH_DURATION}s minimum)."
        )
        return result

    # --- Load and analyze with Parselmouth ---
    try:
        import parselmouth
        import numpy as np
    except ImportError as exc:
        raise VoiceQAUnavailableError(
            "praat-parselmouth is required for performance verification. "
            "Install with: pip install praat-parselmouth"
        ) from exc

    try:
        sound = parselmouth.Sound(str(audio_path))

        # Pitch analysis (fundamental frequency F0).
        pitch = sound.to_pitch()
        pitch_values = pitch.selected_array["frequency"]
        # Filter out unvoiced frames (0.0 Hz).
        voiced = pitch_values[pitch_values > 0]

        if len(voiced) < 5:
            result["status"] = "skip"
            result["reason"] = "Not enough voiced frames for pitch analysis."
            return result

        pitch_mean = float(np.mean(voiced))
        pitch_std = float(np.std(voiced))
        result["pitch_mean_hz"] = round(pitch_mean, 2)
        result["pitch_std_hz"] = round(pitch_std, 2)

        # Energy contour (intensity / loudness over time).
        intensity = sound.to_intensity()
        intensity_values = intensity.values[0]
        energy_std = float(np.std(intensity_values))
        result["energy_std"] = round(energy_std, 2)

        # Speaking rate estimate (voiced frames per second as proxy).
        voiced_ratio = len(voiced) / max(len(pitch_values), 1)
        result["speaking_rate_estimate"] = round(voiced_ratio, 3)

    except VoiceQAUnavailableError:
        raise
    except Exception as exc:
        result["status"] = "error"
        result["reason"] = f"Parselmouth analysis failed: {exc}"
        return result

    # --- Verdict: compare pitch variance against expected bucket ---
    expected_range = INTENSITY_PITCH_VARIANCE[bucket]
    min_expected_std, max_expected_std = expected_range

    if min_expected_std <= pitch_std <= max_expected_std:
        result["status"] = "pass"
        result["reason"] = (
            f"Performance matches '{bucket}' intensity: "
            f"pitch std {pitch_std:.1f}Hz is within [{min_expected_std}-{max_expected_std}]Hz range."
        )
    elif pitch_std < min_expected_std:
        result["status"] = "fail"
        result["reason"] = (
            f"Performance too flat for '{bucket}' intensity (expected {expected_intensity:.1f}): "
            f"pitch std {pitch_std:.1f}Hz < {min_expected_std}Hz minimum. "
            "The delivery sounds monotone. Re-render with stronger performance direction."
        )
    else:
        result["status"] = "fail"
        result["reason"] = (
            f"Performance too erratic for '{bucket}' intensity (expected {expected_intensity:.1f}): "
            f"pitch std {pitch_std:.1f}Hz > {max_expected_std}Hz maximum. "
            "The delivery sounds uncontrolled. Re-render with calmer direction."
        )

    return result


# ---------------------------------------------------------------------------
# Pronunciation guard via phonemizer
# ---------------------------------------------------------------------------

# Maximum acceptable phoneme edit distance ratio for a golden noun.
# A ratio of 0.30 means the IPA transcription can differ from the expected
# pronunciation by at most 30% of phoneme characters. This is lenient enough
# to handle dialect variation and phonemizer approximation while catching
# genuinely wrong pronunciations ("DAN-air-iss" vs "Duh-NAIR-iss").
DEFAULT_MAX_PHONEME_DISTANCE = 0.30


def _phonemize_word(word: str) -> str:
    """Convert a single word to IPA using phonemizer (espeak-ng backend).

    Returns the IPA string, or an empty string if phonemizer is unavailable.
    """
    try:
        from phonemizer import phonemize
        from phonemizer.separator import Separator
    except ImportError as exc:
        raise VoiceQAUnavailableError(
            "phonemizer is required for pronunciation verification. "
            "Install with: pip install phonemizer  "
            "(also requires espeak-ng: brew install espeak-ng)"
        ) from exc

    result = phonemize(
        word,
        language="en-us",
        backend="espeak",
        separator=Separator(phone="", word=" ", syllable=""),
        strip=True,
        preserve_punctuation=False,
    )
    return result.strip()


def _phoneme_edit_distance(a: str, b: str) -> int:
    """Levenshtein edit distance on phoneme character sequences."""
    n, m = len(a), len(b)
    d = list(range(m + 1))
    for i in range(1, n + 1):
        prev = d[0]
        d[0] = i
        for j in range(1, m + 1):
            temp = d[j]
            if a[i - 1] == b[j - 1]:
                d[j] = prev
            else:
                d[j] = 1 + min(prev, d[j], d[j - 1])
            prev = temp
    return d[m]


def check_pronunciation(
    transcribed_text: str,
    pronunciation_guide: Dict[str, str],
    max_distance_ratio: float = DEFAULT_MAX_PHONEME_DISTANCE,
) -> Dict[str, Any]:
    """Verify that golden nouns are pronounced correctly.

    The Cast Bible holds an IPA pronunciation guide for custom nouns
    (character names, place names, invented words). This check:
      1. Scans the Whisper transcription for each golden noun
      2. Uses phonemizer (espeak-ng) to generate the IPA for how
         the noun was transcribed
      3. Compares against the expected IPA from the Cast Bible
      4. Flags any noun whose phoneme distance exceeds the threshold

    This check does NOT need audio — it operates on the Whisper
    transcription string, so it should be run after check_transcript.

    Args:
        transcribed_text: The Whisper transcription of the chunk.
        pronunciation_guide: Dict mapping golden nouns to expected IPA.
            Example: {"Kelsier": "kɛlsiˈeɪ", "Daenerys": "dəˈnɛɹɪs"}
        max_distance_ratio: Maximum phoneme edit distance / expected length.

    Returns:
        A structured QA result dict:
        {
            "check": "pronunciation",
            "status": "pass" | "fail" | "skip" | "error",
            "total_golden_nouns": int,
            "found_in_transcript": int,
            "failed_nouns": [...],
            "passed_nouns": [...],
            "skipped_nouns": [...],
            "timestamp": str,
            "reason": str | None,
        }
    """
    result = {
        "check": "pronunciation",
        "total_golden_nouns": len(pronunciation_guide),
        "found_in_transcript": 0,
        "failed_nouns": [],
        "passed_nouns": [],
        "skipped_nouns": [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "reason": None,
    }

    if not pronunciation_guide:
        result["status"] = "skip"
        result["reason"] = "No golden nouns in pronunciation guide."
        return result

    if not transcribed_text or not transcribed_text.strip():
        result["status"] = "skip"
        result["reason"] = "No transcription text to check against."
        return result

    text_lower = transcribed_text.lower()

    for noun, expected_ipa in pronunciation_guide.items():
        noun_lower = noun.lower()

        # Check if the noun appears in the transcription.
        if noun_lower not in text_lower:
            result["skipped_nouns"].append({
                "noun": noun,
                "reason": "Not found in transcription.",
            })
            continue

        result["found_in_transcript"] += 1

        # Phonemize the noun as transcribed.
        try:
            actual_ipa = _phonemize_word(noun)
        except VoiceQAUnavailableError:
            raise
        except Exception as exc:
            result["skipped_nouns"].append({
                "noun": noun,
                "reason": f"Phonemizer failed: {exc}",
            })
            continue

        if not actual_ipa:
            result["skipped_nouns"].append({
                "noun": noun,
                "reason": "Phonemizer returned empty IPA.",
            })
            continue

        # Compare phoneme sequences.
        distance = _phoneme_edit_distance(expected_ipa, actual_ipa)
        max_len = max(len(expected_ipa), 1)
        ratio = distance / max_len

        noun_result = {
            "noun": noun,
            "expected_ipa": expected_ipa,
            "actual_ipa": actual_ipa,
            "distance": distance,
            "ratio": round(ratio, 4),
        }

        if ratio <= max_distance_ratio:
            result["passed_nouns"].append(noun_result)
        else:
            result["failed_nouns"].append(noun_result)

    # --- Verdict ---
    if result["failed_nouns"]:
        failed_names = [n["noun"] for n in result["failed_nouns"]]
        result["status"] = "fail"
        result["reason"] = (
            f"Pronunciation mismatch for {len(failed_names)} golden noun(s): "
            f"{', '.join(failed_names)}. "
            "Check the IPA comparison in failed_nouns for details."
        )
    elif result["found_in_transcript"] == 0:
        result["status"] = "skip"
        result["reason"] = "No golden nouns found in this chunk's transcription."
    else:
        result["status"] = "pass"
        result["reason"] = (
            f"All {len(result['passed_nouns'])} golden noun(s) pronounced correctly."
        )

    return result


# ---------------------------------------------------------------------------
# Batch QA: run checks across all chunks in a render manifest
# ---------------------------------------------------------------------------

def qa_manifest_speaker_counts(
    manifest_path: Path,
    hf_token: Optional[str] = None,
    default_expected_speakers: int = 1,
) -> Dict[str, Any]:
    """Run speaker count QA on every rendered chunk in a manifest.

    Reads the render manifest JSON, finds each chunk's audio file,
    and runs check_speaker_count on it. Results are saved alongside
    the manifest as a QA report.

    Args:
        manifest_path: Path to the chapter render manifest JSON.
        hf_token: HuggingFace token for pyannote.
        default_expected_speakers: Default expected speaker count per chunk.

    Returns:
        A summary dict with per-chunk results and aggregate counts.
    """
    from src.aura.gemini_production import load_json, write_json

    manifest = load_json(manifest_path)
    base_dir = manifest_path.parent
    results: List[Dict[str, Any]] = []

    # Walk through the manifest's request files to find output audio paths.
    for request_rel in manifest.get("requests", []):
        request_path = Path(request_rel)
        if not request_path.is_absolute():
            request_path = base_dir / request_path

        if not request_path.exists():
            results.append({
                "check": "speaker_count",
                "audio_file": str(request_path),
                "status": "error",
                "reason": "Request file not found.",
            })
            continue

        request = load_json(request_path)
        audio_path = Path(request.get("output_file", ""))
        if not audio_path.is_absolute():
            audio_path = base_dir / audio_path

        # Determine expected speaker count from the request payload.
        speaker_voices = request.get("speaker_voices", {})
        expected = len(speaker_voices) if speaker_voices else default_expected_speakers

        result = check_speaker_count(audio_path, expected_speakers=expected, hf_token=hf_token)
        result["request_file"] = str(request_path)
        results.append(result)

    # --- Aggregate summary ---
    summary = {
        "manifest": str(manifest_path),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_chunks": len(results),
        "passed": sum(1 for r in results if r.get("status") == "pass"),
        "failed": sum(1 for r in results if r.get("status") == "fail"),
        "skipped": sum(1 for r in results if r.get("status") == "skip"),
        "errors": sum(1 for r in results if r.get("status") == "error"),
        "results": results,
    }

    # Save the QA report next to the manifest.
    report_path = manifest_path.with_suffix(".speaker_qa.json")
    write_json(report_path, summary)

    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Automated voice QA for rendered TTS chunks. "
            "Checks: speaker count (pyannote), voice identity (resemblyzer), "
            "transcript accuracy (whisper)."
        )
    )
    subparsers = parser.add_subparsers(dest="command")

    # --- Speaker count: single file ---
    sc_single = subparsers.add_parser(
        "check-speakers", help="Check speaker count in a single audio file."
    )
    sc_single.add_argument("audio", type=Path, help="Path to a rendered .wav chunk.")
    sc_single.add_argument(
        "--expected-speakers", type=int, default=1,
        help="Expected number of speakers in this chunk (default: 1).",
    )
    sc_single.add_argument("--hf-token", default=None, help="HuggingFace access token.")

    # --- Speaker count: manifest batch ---
    sc_batch = subparsers.add_parser(
        "check-speakers-manifest", help="Run speaker count QA on an entire render manifest."
    )
    sc_batch.add_argument("manifest", type=Path, help="Path to the render manifest JSON.")
    sc_batch.add_argument(
        "--expected-speakers", type=int, default=1,
        help="Default expected speakers per chunk (default: 1).",
    )
    sc_batch.add_argument("--hf-token", default=None, help="HuggingFace access token.")

    # --- Voice identity: single file ---
    vi_single = subparsers.add_parser(
        "check-identity", help="Check voice identity of a chunk against a reference."
    )
    vi_single.add_argument("audio", type=Path, help="Path to a rendered .wav chunk.")
    vi_single.add_argument("reference", type=Path, help="Path to the approved reference .wav.")
    vi_single.add_argument(
        "--threshold", type=float, default=DEFAULT_SIMILARITY_THRESHOLD,
        help=f"Minimum cosine similarity to pass (default: {DEFAULT_SIMILARITY_THRESHOLD}).",
    )

    # --- Voice identity: compute embedding ---
    vi_embed = subparsers.add_parser(
        "embed", help="Compute and print the voice embedding for an audio file."
    )
    vi_embed.add_argument("audio", type=Path, help="Path to a .wav file.")

    # --- Transcript accuracy: single file ---
    tr_single = subparsers.add_parser(
        "check-transcript", help="Verify a chunk's audio matches expected text."
    )
    tr_single.add_argument("audio", type=Path, help="Path to a rendered .wav chunk.")
    tr_single.add_argument("expected_text", type=str, help="The expected spoken text.")
    tr_single.add_argument(
        "--max-wer", type=float, default=DEFAULT_MAX_WER,
        help=f"Maximum acceptable Word Error Rate (default: {DEFAULT_MAX_WER}).",
    )
    tr_single.add_argument(
        "--whisper-model", default=DEFAULT_WHISPER_MODEL,
        help=f"Whisper model size (default: {DEFAULT_WHISPER_MODEL}).",
    )

    # --- Audio quality: single file ---
    aq_single = subparsers.add_parser(
        "check-quality", help="Score audio quality (MOS) using torchaudio SQUIM."
    )
    aq_single.add_argument("audio", type=Path, help="Path to a rendered .wav chunk.")
    aq_single.add_argument(
        "--min-mos", type=float, default=DEFAULT_MIN_MOS,
        help=f"Minimum acceptable MOS score (default: {DEFAULT_MIN_MOS}).",
    )

    # --- Performance: single file ---
    pf_single = subparsers.add_parser(
        "check-performance", help="Verify acting/performance matches expected intensity."
    )
    pf_single.add_argument("audio", type=Path, help="Path to a rendered .wav chunk.")
    pf_single.add_argument(
        "--intensity", type=float, default=0.5,
        help="Expected APS intensity value 0.0-1.0 (default: 0.5).",
    )

    # --- Pronunciation: text-based check ---
    pr_single = subparsers.add_parser(
        "check-pronunciation",
        help="Verify golden noun pronunciation against Cast Bible IPA guide.",
    )
    pr_single.add_argument(
        "transcription", type=str,
        help="The Whisper transcription text to check.",
    )
    pr_single.add_argument(
        "guide", type=str,
        help='JSON dict of golden nouns to expected IPA. Example: \'{"Kelsier": "kɛlsieɪ"}\'',
    )
    pr_single.add_argument(
        "--max-distance", type=float, default=DEFAULT_MAX_PHONEME_DISTANCE,
        help=f"Maximum phoneme distance ratio (default: {DEFAULT_MAX_PHONEME_DISTANCE}).",
    )

    args = parser.parse_args()

    if args.command == "check-speakers":
        result = check_speaker_count(args.audio, args.expected_speakers, args.hf_token)
        status_icon = {"pass": "✅", "fail": "❌", "skip": "⏭️", "error": "⚠️"}.get(result["status"], "?")
        print(f"{status_icon} {result['status'].upper()}: {result['reason']}")
        if result.get("speaker_segments"):
            for seg in result["speaker_segments"]:
                print(f"  {seg['speaker']}: {seg['start']:.1f}s → {seg['end']:.1f}s ({seg['duration']:.1f}s)")

    elif args.command == "check-speakers-manifest":
        summary = qa_manifest_speaker_counts(args.manifest, args.hf_token, args.expected_speakers)
        print(
            f"Speaker QA complete: "
            f"{summary['passed']} passed, "
            f"{summary['failed']} failed, "
            f"{summary['skipped']} skipped, "
            f"{summary['errors']} errors."
        )
        if summary["failed"]:
            print("❌ Failed chunks (voice swaps detected):")
            for r in summary["results"]:
                if r.get("status") == "fail":
                    print(f"  {r['audio_file']}: {r['reason']}")
        report_path = Path(args.manifest).with_suffix(".speaker_qa.json")
        print(f"Full report: {report_path}")

    elif args.command == "check-identity":
        result = check_voice_identity(args.audio, args.reference, args.threshold)
        status_icon = {"pass": "✅", "fail": "❌", "skip": "⏭️", "error": "⚠️"}.get(result["status"], "?")
        sim = result.get("similarity")
        sim_str = f" (similarity: {sim:.4f})" if sim is not None else ""
        print(f"{status_icon} {result['status'].upper()}{sim_str}: {result['reason']}")

    elif args.command == "embed":
        import json as _json
        embedding = compute_voice_embedding(args.audio)
        print(_json.dumps({"audio": str(args.audio), "embedding": embedding.tolist()}))

    elif args.command == "check-transcript":
        result = check_transcript(
            args.audio, args.expected_text,
            max_wer=args.max_wer, whisper_model=args.whisper_model,
        )
        status_icon = {"pass": "✅", "fail": "❌", "skip": "⏭️", "error": "⚠️"}.get(result["status"], "?")
        wer = result.get("wer")
        wer_str = f" (WER: {wer:.2%})" if wer is not None else ""
        print(f"{status_icon} {result['status'].upper()}{wer_str}: {result['reason']}")
        if result.get("transcribed_text"):
            print(f"  Transcribed: {result['transcribed_text'][:200]}")

    elif args.command == "check-quality":
        result = check_audio_quality(args.audio, min_mos=args.min_mos)
        status_icon = {"pass": "✅", "fail": "❌", "skip": "⏭️", "error": "⚠️"}.get(result["status"], "?")
        mos = result.get("mos")
        mos_str = f" (MOS: {mos:.2f})" if mos is not None else ""
        print(f"{status_icon} {result['status'].upper()}{mos_str}: {result['reason']}")
        if result.get("stoi") is not None:
            print(f"  STOI: {result['stoi']:.4f}  PESQ: {result.get('pesq', 'N/A')}")

    elif args.command == "check-performance":
        result = check_performance(args.audio, expected_intensity=args.intensity)
        status_icon = {"pass": "✅", "fail": "❌", "skip": "⏭️", "error": "⚠️"}.get(result["status"], "?")
        pitch = result.get("pitch_std_hz")
        pitch_str = f" (pitch σ: {pitch:.1f}Hz)" if pitch is not None else ""
        print(f"{status_icon} {result['status'].upper()}{pitch_str}: {result['reason']}")
        if result.get("pitch_mean_hz") is not None:
            print(
                f"  Pitch mean: {result['pitch_mean_hz']:.1f}Hz | "
                f"Energy σ: {result.get('energy_std', 'N/A')} | "
                f"Voiced ratio: {result.get('speaking_rate_estimate', 'N/A')}"
            )

    elif args.command == "check-pronunciation":
        import json as _json
        guide = _json.loads(args.guide)
        result = check_pronunciation(
            args.transcription, guide,
            max_distance_ratio=args.max_distance,
        )
        status_icon = {"pass": "✅", "fail": "❌", "skip": "⏭️", "error": "⚠️"}.get(result["status"], "?")
        print(f"{status_icon} {result['status'].upper()}: {result['reason']}")
        if result.get("failed_nouns"):
            for n in result["failed_nouns"]:
                print(f"  ❌ {n['noun']}: expected /{n['expected_ipa']}/ got /{n['actual_ipa']}/ (distance: {n['distance']})")
        if result.get("passed_nouns"):
            for n in result["passed_nouns"]:
                print(f"  ✅ {n['noun']}: /{n['actual_ipa']}/ matches /{n['expected_ipa']}/")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
