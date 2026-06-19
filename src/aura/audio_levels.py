import warnings
from typing import Any, Dict, Optional

import numpy as np


PEAK_HEADROOM = 0.98
SILENCE_RMS_THRESHOLD = 0.0005
MAX_RECOMMENDED_GAIN_DB = 24.0
LUFS_EFFECT_TYPES = {"ambience", "room_tone", "music", "music_bed"}
SFX_ROLE_RELATIVE_DB = {
    "ambience": -22.0,
    "room_tone": -30.0,
    "motion": -16.0,
    "spot_soft": -14.0,
    "spot_important": -10.0,
    "music_bed": -26.0,
}


class LoudnessUnavailableError(RuntimeError):
    """Raised when loudness normalization cannot be performed."""


def to_2d(audio: np.ndarray) -> np.ndarray:
    if audio.ndim == 1:
        return audio[:, None]
    return audio


def db_to_gain(db: float) -> float:
    return float(10 ** (db / 20.0))


def amplitude_to_db(value: float) -> Optional[float]:
    if value <= 0:
        return None
    return float(20 * np.log10(value))


def rms(audio: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(audio)))) if audio.size else 0.0


def rms_db(audio: np.ndarray) -> Optional[float]:
    return amplitude_to_db(rms(audio))


def peak(audio: np.ndarray) -> float:
    return float(np.max(np.abs(audio))) if audio.size else 0.0


def peak_db(audio: np.ndarray) -> Optional[float]:
    return amplitude_to_db(peak(audio))


def normalize_peak(audio: np.ndarray, headroom: float = PEAK_HEADROOM) -> np.ndarray:
    current_peak = peak(audio)
    if current_peak <= headroom or current_peak <= 0:
        return audio
    return audio * (headroom / current_peak)


def measure_lufs(audio: np.ndarray, sample_rate: int) -> Optional[float]:
    try:
        import pyloudnorm as pyln
    except ImportError as exc:
        warnings.warn(f"pyloudnorm is unavailable; LUFS measurement skipped: {exc}", RuntimeWarning, stacklevel=2)
        return None
    if not audio.size:
        return None
    try:
        meter = pyln.Meter(sample_rate)
        # pyloudnorm expects (samples,) for mono or (samples, channels) for multi-channel.
        # Squeeze (samples, 1) -> (samples,) to avoid shape rejection on mono assets.
        audio_for_meter = audio.squeeze(axis=1) if audio.ndim == 2 and audio.shape[1] == 1 else audio
        value = float(meter.integrated_loudness(audio_for_meter))
    except Exception as exc:
        warnings.warn(f"LUFS measurement failed; falling back to RMS/peak metrics: {exc}", RuntimeWarning, stacklevel=2)
        return None
    if not np.isfinite(value):
        return None
    return value


def normalize_to_lufs(audio: np.ndarray, sample_rate: int, target_lufs: float, require_lufs: bool = True) -> np.ndarray:
    try:
        import pyloudnorm as pyln
    except ImportError as exc:
        if require_lufs:
            raise LoudnessUnavailableError("pyloudnorm is required for LUFS normalization.") from exc
        warnings.warn(f"pyloudnorm is unavailable; applying peak normalization only: {exc}", RuntimeWarning, stacklevel=2)
        return normalize_peak(audio)
    loudness = measure_lufs(audio, sample_rate)
    if loudness is None:
        if require_lufs:
            raise LoudnessUnavailableError("Could not measure LUFS for loudness normalization.")
        warnings.warn("Could not measure LUFS; applying peak normalization only.", RuntimeWarning, stacklevel=2)
        return normalize_peak(audio)
    normalized = pyln.normalize.loudness(audio, loudness, target_lufs)
    current_peak = float(np.max(np.abs(normalized))) if normalized.size else 0.0
    if current_peak > PEAK_HEADROOM:
        scale = PEAK_HEADROOM / current_peak
        loss_db = float(20 * np.log10(scale))
        warnings.warn(
            f"Post-LUFS peak normalization reduced level by {loss_db:.2f} dB; "
            f"actual LUFS will be below target {target_lufs:.1f} LUFS. "
            "Consider a true-peak limiter for precision mastering.",
            RuntimeWarning,
            stacklevel=2,
        )
    return normalize_peak(normalized)


def spectral_centroid(audio: np.ndarray, sample_rate: int) -> float:
    if not audio.size or sample_rate <= 0:
        return 0.0
    mono = np.mean(to_2d(audio), axis=1)
    if not np.any(mono):
        return 0.0
    window = np.hanning(len(mono))
    spectrum = np.abs(np.fft.rfft(mono * window))
    total = float(np.sum(spectrum))
    if total <= 0:
        return 0.0
    freqs = np.fft.rfftfreq(len(mono), d=1.0 / sample_rate)
    return float(np.sum(freqs * spectrum) / total)


def audio_stats(audio: np.ndarray, sample_rate: int) -> Dict[str, Any]:
    current_rms = rms(audio)
    stats = {
        "duration": round(len(audio) / sample_rate, 3) if sample_rate else 0.0,
        "peak": round(peak(audio), 6),
        "peak_db": round(peak_db(audio), 3) if peak_db(audio) is not None else None,
        "rms": round(current_rms, 6),
        "rms_db": round(rms_db(audio), 3) if rms_db(audio) is not None else None,
        "near_silent": current_rms < SILENCE_RMS_THRESHOLD,
        "spectral_centroid_hz": round(spectral_centroid(audio, sample_rate), 3),
    }
    lufs = measure_lufs(audio, sample_rate)
    stats["lufs"] = round(lufs, 3) if lufs is not None else None
    return stats


def audio_window(audio: np.ndarray, sample_rate: int, start_seconds: float, duration_seconds: float) -> np.ndarray:
    start_sample = max(0, int(start_seconds * sample_rate))
    end_sample = min(len(audio), start_sample + int(duration_seconds * sample_rate))
    return audio[start_sample:end_sample]


def choose_level_metric(effect_type: str, duration_seconds: float) -> str:
    if effect_type in LUFS_EFFECT_TYPES and duration_seconds >= 3.0:
        return "lufs"
    return "rms_db"


def clamp_gain_db(gain_db: float, max_abs_gain_db: float = MAX_RECOMMENDED_GAIN_DB) -> Dict[str, Any]:
    if abs(gain_db) <= max_abs_gain_db:
        return {
            "gain_db": round(gain_db, 3),
            "clamped": False,
            "warning": None,
        }
    clamped = max(-max_abs_gain_db, min(max_abs_gain_db, gain_db))
    return {
        "gain_db": round(clamped, 3),
        "clamped": True,
        "warning": (
            f"Recommended gain {gain_db:.3f}dB exceeds +/-{max_abs_gain_db:.1f}dB; "
            f"clamped to {clamped:.3f}dB."
        ),
    }


def recommended_sfx_gain_db(
    voice_stats: Dict[str, Any],
    asset_stats: Dict[str, Any],
    effect_type: str,
    relative_to_voice_db: float,
    duration_seconds: float,
    reference_voice_stats: Optional[Dict[str, Any]] = None,
    max_abs_gain_db: float = MAX_RECOMMENDED_GAIN_DB,
) -> Dict[str, Any]:
    warnings_list = []
    reference_used = False
    near_silent_unresolved = False
    if voice_stats.get("near_silent"):
        if reference_voice_stats:
            voice_stats = reference_voice_stats
            reference_used = True
            warnings_list.append("Local voice window was near-silent; used reference voice loudness.")
        else:
            near_silent_unresolved = True
            warnings_list.append(
                "Local voice window was near-silent and no reference was provided; "
                "gain recommendation may be unreliable."
            )

    metric = choose_level_metric(effect_type, duration_seconds)
    voice_value = voice_stats.get(metric)
    asset_value = asset_stats.get(metric)
    fallback_used = False
    if voice_value is None or asset_value is None:
        metric = "rms_db"
        voice_value = voice_stats.get(metric)
        asset_value = asset_stats.get(metric)
        fallback_used = True
    if voice_value is None or asset_value is None:
        result = {
            "metric": metric,
            "recommended_gain_db": 0.0,
            "unclamped_gain_db": 0.0,
            "target_sfx_level": None,
            "fallback_used": True,
            "reference_used": reference_used,
            "clamped": False,
            "warning": "Could not measure voice or SFX level; using 0dB gain.",
        }
        if warnings_list:
            result["warnings"] = warnings_list
        return result
    target = float(voice_value) + float(relative_to_voice_db)
    unclamped_gain = target - float(asset_value)
    clamped = clamp_gain_db(unclamped_gain, max_abs_gain_db=max_abs_gain_db)
    if clamped["warning"]:
        warnings_list.append(clamped["warning"])
    result = {
        "metric": metric,
        "recommended_gain_db": clamped["gain_db"],
        "unclamped_gain_db": round(unclamped_gain, 3),
        "target_sfx_level": round(target, 3),
        "fallback_used": fallback_used,
        "reference_used": reference_used,
        "near_silent_unresolved": near_silent_unresolved,
        "clamped": clamped["clamped"],
    }
    if warnings_list:
        result["warnings"] = warnings_list
    return result
