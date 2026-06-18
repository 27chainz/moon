from typing import Any, Dict, Optional

import numpy as np


PEAK_HEADROOM = 0.98
SILENCE_RMS_THRESHOLD = 0.0005
SFX_ROLE_RELATIVE_DB = {
    "ambience": -22.0,
    "room_tone": -30.0,
    "motion": -16.0,
    "spot_soft": -14.0,
    "spot_important": -10.0,
    "music_bed": -26.0,
}


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
    except ImportError:
        return None
    if not audio.size:
        return None
    try:
        meter = pyln.Meter(sample_rate)
        value = float(meter.integrated_loudness(audio))
    except Exception:
        return None
    if not np.isfinite(value):
        return None
    return value


def normalize_to_lufs(audio: np.ndarray, sample_rate: int, target_lufs: float) -> np.ndarray:
    try:
        import pyloudnorm as pyln
    except ImportError:
        return normalize_peak(audio)
    loudness = measure_lufs(audio, sample_rate)
    if loudness is None:
        return normalize_peak(audio)
    normalized = pyln.normalize.loudness(audio, loudness, target_lufs)
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
    if effect_type in {"ambience", "room_tone", "music"} and duration_seconds >= 3.0:
        return "lufs"
    if duration_seconds >= 3.0:
        return "lufs"
    return "rms_db"


def recommended_sfx_gain_db(
    voice_stats: Dict[str, Any],
    asset_stats: Dict[str, Any],
    effect_type: str,
    relative_to_voice_db: float,
    duration_seconds: float,
) -> Dict[str, Any]:
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
        return {
            "metric": metric,
            "recommended_gain_db": 0.0,
            "target_sfx_level": None,
            "fallback_used": True,
            "warning": "Could not measure voice or SFX level; using 0dB gain.",
        }
    target = float(voice_value) + float(relative_to_voice_db)
    gain = target - float(asset_value)
    return {
        "metric": metric,
        "recommended_gain_db": round(gain, 3),
        "target_sfx_level": round(target, 3),
        "fallback_used": fallback_used,
    }
