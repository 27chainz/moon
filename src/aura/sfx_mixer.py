import argparse
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import soundfile as sf
from scipy import signal

from src.aura.audio_levels import (
    SFX_ROLE_RELATIVE_DB,
    audio_stats,
    audio_window,
    db_to_gain,
    normalize_peak,
    recommended_sfx_gain_db,
)


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_audio(path: Path) -> Tuple[np.ndarray, int]:
    audio, sample_rate = sf.read(path, dtype="float32", always_2d=True)
    return audio, sample_rate


def match_channels(audio: np.ndarray, channels: int) -> np.ndarray:
    if audio.shape[1] == channels:
        return audio
    if channels == 1:
        return np.mean(audio, axis=1, keepdims=True)
    if audio.shape[1] == 1:
        return np.repeat(audio, channels, axis=1)
    return audio[:, :channels]


def resample_audio(audio: np.ndarray, source_rate: int, target_rate: int) -> np.ndarray:
    if source_rate == target_rate:
        return audio
    divisor = math.gcd(source_rate, target_rate)
    up = target_rate // divisor
    down = source_rate // divisor
    return signal.resample_poly(audio, up, down, axis=0).astype(np.float32)


def apply_fades(audio: np.ndarray, sample_rate: int, fade_in_ms: int = 0, fade_out_ms: int = 0) -> np.ndarray:
    result = audio.copy()
    if fade_in_ms:
        samples = min(len(result), int(sample_rate * fade_in_ms / 1000))
        if samples > 0:
            result[:samples] *= np.linspace(0.0, 1.0, samples, dtype=np.float32)[:, None]
    if fade_out_ms:
        samples = min(len(result), int(sample_rate * fade_out_ms / 1000))
        if samples > 0:
            result[-samples:] *= np.linspace(1.0, 0.0, samples, dtype=np.float32)[:, None]
    return result


def fit_to_duration(audio: np.ndarray, sample_count: int, loop: bool) -> np.ndarray:
    if sample_count <= 0:
        return np.zeros((0, audio.shape[1]), dtype=np.float32)
    if len(audio) >= sample_count:
        return audio[:sample_count]
    if not loop:
        padding = np.zeros((sample_count - len(audio), audio.shape[1]), dtype=np.float32)
        return np.concatenate([audio, padding], axis=0)
    repeats = math.ceil(sample_count / len(audio))
    tiled = np.tile(audio, (repeats, 1))
    return tiled[:sample_count]


def overlay(base: np.ndarray, layer: np.ndarray, start_sample: int) -> np.ndarray:
    if start_sample >= len(base) or len(layer) == 0:
        return base
    end_sample = min(len(base), start_sample + len(layer))
    layer_end = end_sample - start_sample
    base[start_sample:end_sample] += layer[:layer_end]
    return base


def effect_span(effect: Dict[str, Any], layer: np.ndarray, sample_rate: int) -> Tuple[float, float]:
    start_seconds = float(effect["start_seconds"])
    if effect.get("placement") == "time_span":
        end_seconds = float(effect["end_seconds"])
    else:
        end_seconds = start_seconds + len(layer) / sample_rate
    return start_seconds, end_seconds


def level_adjustment_db(
    effect: Dict[str, Any],
    voice_master: np.ndarray,
    asset_audio: np.ndarray,
    sample_rate: int,
    start_seconds: float,
    duration_seconds: float,
) -> Tuple[float, Dict[str, Any]]:
    if "level_db" in effect:
        return float(effect["level_db"]), {
            "mode": "manual",
            "level_db": float(effect["level_db"]),
        }

    mix_role = effect.get("mix_role") or effect.get("type") or "spot_soft"
    relative_db = float(effect.get("relative_to_voice_db", SFX_ROLE_RELATIVE_DB.get(mix_role, -14.0)))
    window_duration = max(2.0, min(8.0, duration_seconds))
    window_start = max(0.0, start_seconds - 1.0)
    voice = audio_window(voice_master, sample_rate, window_start, window_duration)
    voice_stats = audio_stats(voice, sample_rate)
    asset_stats = audio_stats(asset_audio, sample_rate)
    recommendation = recommended_sfx_gain_db(
        voice_stats=voice_stats,
        asset_stats=asset_stats,
        effect_type=str(effect.get("type") or ""),
        relative_to_voice_db=relative_db,
        duration_seconds=duration_seconds,
    )
    return float(recommendation["recommended_gain_db"]), {
        "mode": "relative_to_voice",
        "mix_role": mix_role,
        "relative_to_voice_db": relative_db,
        "voice_window": {
            "start_seconds": round(window_start, 3),
            "duration_seconds": round(window_duration, 3),
            "stats": voice_stats,
        },
        "asset_stats": asset_stats,
        "recommendation": recommendation,
    }


def prepare_layer(
    effect: Dict[str, Any],
    voice_master: np.ndarray,
    sample_rate: int,
    channels: int,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    asset_path = Path(effect["asset_path"])
    if not asset_path.exists():
        raise FileNotFoundError(f"Missing SFX asset: {asset_path}")
    raw_audio, asset_rate = load_audio(asset_path)
    audio = resample_audio(raw_audio, asset_rate, sample_rate)
    audio = match_channels(audio, channels)

    placement = effect.get("placement")
    if placement == "time_span":
        start_seconds = float(effect["start_seconds"])
        end_seconds = float(effect["end_seconds"])
        target_samples = int(max(0.0, end_seconds - start_seconds) * sample_rate)
        duration_policy = effect.get("duration_policy") or {}
        if isinstance(duration_policy, str):
            loop = duration_policy == "loop_crossfade"
        else:
            loop = duration_policy.get("policy") == "loop_crossfade"
        audio = fit_to_duration(audio, target_samples, loop=loop)
    elif placement == "time_point":
        start_seconds = float(effect["start_seconds"])
    else:
        raise ValueError(f"Unsupported sample mixer placement: {placement!r}")

    start_seconds, end_seconds = effect_span(effect, audio, sample_rate)
    duration_seconds = len(audio) / sample_rate
    gain_db, level = level_adjustment_db(effect, voice_master, audio, sample_rate, start_seconds, duration_seconds)

    audio = apply_fades(
        audio,
        sample_rate,
        fade_in_ms=int(effect.get("fade_in_ms") or 0),
        fade_out_ms=int(effect.get("fade_out_ms") or 0),
    )
    audio = audio * db_to_gain(gain_db)
    resolved = {
        "sfx_id": effect.get("sfx_id"),
        "asset_id": effect.get("asset_id"),
        "asset_path": str(asset_path),
        "placement": placement,
        "start_seconds": round(start_seconds, 3),
        "duration_seconds": round(duration_seconds, 3),
        "applied_gain_db": round(gain_db, 3),
        "level": level,
    }
    if placement == "time_span":
        resolved["end_seconds"] = round(end_seconds, 3)
    return audio.astype(np.float32), resolved


def mix_sfx_plan(plan_path: Path, output_path: Path | None = None) -> Dict[str, Any]:
    plan = load_json(plan_path)
    voice_master = Path(plan["voice_master"])
    if not voice_master.exists():
        raise FileNotFoundError(f"Missing voice master: {voice_master}")

    mix, sample_rate = load_audio(voice_master)
    channels = mix.shape[1]
    resolved_layers: List[Dict[str, Any]] = []

    for effect in plan.get("sfx", []):
        layer, resolved = prepare_layer(effect, mix, sample_rate, channels)
        start_sample = int(float(effect["start_seconds"]) * sample_rate)
        mix = overlay(mix, layer, start_sample)
        resolved_layers.append(resolved)

    mix = normalize_peak(mix)
    final_output = output_path or Path(plan["output_mix"])
    final_output.parent.mkdir(parents=True, exist_ok=True)
    sf.write(final_output, mix, sample_rate)

    result = {
        "sfx_mix_version": "0.1",
        "plan": str(plan_path),
        "voice_master": str(voice_master),
        "output_mix": str(final_output),
        "sample_rate": sample_rate,
        "channels": channels,
        "duration_seconds": round(len(mix) / sample_rate, 3),
        "layers": resolved_layers,
    }
    write_json(final_output.with_suffix(".json"), result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Mix time-based SFX layers onto a chapter voice master.")
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = mix_sfx_plan(args.plan, args.output)
    print(f"Wrote SFX mix: {result['output_mix']}")
    print(f"Layers: {len(result['layers'])}")


if __name__ == "__main__":
    main()
