import argparse
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import soundfile as sf
from scipy import signal


PEAK_HEADROOM = 0.98


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def db_to_gain(db: float) -> float:
    return float(10 ** (db / 20.0))


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


def normalize_peak(audio: np.ndarray) -> np.ndarray:
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if peak <= PEAK_HEADROOM or peak <= 0:
        return audio
    return audio * (PEAK_HEADROOM / peak)


def overlay(base: np.ndarray, layer: np.ndarray, start_sample: int) -> np.ndarray:
    if start_sample >= len(base) or len(layer) == 0:
        return base
    end_sample = min(len(base), start_sample + len(layer))
    layer_end = end_sample - start_sample
    base[start_sample:end_sample] += layer[:layer_end]
    return base


def prepare_layer(effect: Dict[str, Any], sample_rate: int, channels: int) -> Tuple[np.ndarray, Dict[str, Any]]:
    asset_path = Path(effect["asset_path"])
    if not asset_path.exists():
        raise FileNotFoundError(f"Missing SFX asset: {asset_path}")
    audio, asset_rate = load_audio(asset_path)
    audio = resample_audio(audio, asset_rate, sample_rate)
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

    audio = apply_fades(
        audio,
        sample_rate,
        fade_in_ms=int(effect.get("fade_in_ms") or 0),
        fade_out_ms=int(effect.get("fade_out_ms") or 0),
    )
    audio = audio * db_to_gain(float(effect.get("level_db", -24)))
    resolved = {
        "sfx_id": effect.get("sfx_id"),
        "asset_id": effect.get("asset_id"),
        "asset_path": str(asset_path),
        "placement": placement,
        "start_seconds": round(start_seconds, 3),
        "duration_seconds": round(len(audio) / sample_rate, 3),
        "level_db": effect.get("level_db", -24),
    }
    if placement == "time_span":
        resolved["end_seconds"] = round(float(effect["end_seconds"]), 3)
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
        layer, resolved = prepare_layer(effect, sample_rate, channels)
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
