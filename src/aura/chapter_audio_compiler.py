import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import soundfile as sf


TARGET_LUFS = -16.0
PEAK_HEADROOM = 0.98
MIN_CHUNK_DURATION = 0.25
SILENCE_RMS_THRESHOLD = 0.0005


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def request_audio_paths(manifest: Dict[str, Any]) -> List[Path]:
    paths = []
    for request_path in manifest.get("requests", []):
        request = load_json(Path(request_path))
        paths.append(Path(request["output_file"]))
    return paths


def to_2d(audio: np.ndarray) -> np.ndarray:
    if audio.ndim == 1:
        return audio[:, None]
    return audio


def normalize_peak(audio: np.ndarray) -> np.ndarray:
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if peak <= 0:
        return audio
    if peak <= PEAK_HEADROOM:
        return audio
    return audio * (PEAK_HEADROOM / peak)


def audio_stats(audio: np.ndarray, sample_rate: int) -> Dict[str, Any]:
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    rms = float(np.sqrt(np.mean(np.square(audio)))) if audio.size else 0.0
    duration = len(audio) / sample_rate if sample_rate else 0.0
    stats = {
        "duration": round(duration, 3),
        "peak": round(peak, 6),
        "rms": round(rms, 6),
        "near_silent": rms < SILENCE_RMS_THRESHOLD,
    }
    try:
        import pyloudnorm as pyln

        meter = pyln.Meter(sample_rate)
        stats["lufs"] = round(float(meter.integrated_loudness(audio)), 3)
    except Exception:
        stats["lufs"] = None
    return stats


def normalize_loudness(audio: np.ndarray, sample_rate: int, target_lufs: float) -> np.ndarray:
    try:
        import pyloudnorm as pyln
    except ImportError:
        return normalize_peak(audio)

    meter = pyln.Meter(sample_rate)
    loudness = meter.integrated_loudness(audio)
    normalized = pyln.normalize.loudness(audio, loudness, target_lufs)
    return normalize_peak(normalized)


def silence(sample_rate: int, channels: int, gap_ms: int) -> np.ndarray:
    samples = int(sample_rate * gap_ms / 1000)
    return np.zeros((samples, channels), dtype=np.float32)


def compile_audio(
    manifest_path: Path,
    output_path: Path,
    target_lufs: float,
    gap_ms: int,
    require_approved: bool = True,
) -> Dict[str, Any]:
    manifest = load_json(manifest_path)
    qa_status = manifest.get("qa_status", "pending")
    if require_approved and qa_status != "approved":
        raise ValueError(
            f"Chapter QA status is {qa_status!r}. Mark it approved or pass --allow-unapproved for a test compile."
        )
    audio_paths = request_audio_paths(manifest)
    if not audio_paths:
        raise ValueError("Manifest has no request audio paths.")

    rendered = []
    sample_rate = None
    channels = None
    timeline = []
    cursor = 0.0

    for index, audio_path in enumerate(audio_paths, start=1):
        if not audio_path.exists():
            raise FileNotFoundError(f"Missing rendered chunk audio: {audio_path}")

        audio, rate = sf.read(audio_path, dtype="float32", always_2d=True)
        if sample_rate is None:
            sample_rate = rate
            channels = audio.shape[1]
        if rate != sample_rate:
            raise ValueError(f"Sample-rate mismatch in {audio_path}: {rate} != {sample_rate}")
        if audio.shape[1] != channels:
            raise ValueError(f"Channel-count mismatch in {audio_path}: {audio.shape[1]} != {channels}")

        before_stats = audio_stats(audio, rate)
        audio = normalize_loudness(audio, rate, target_lufs)
        after_stats = audio_stats(audio, rate)
        duration = len(audio) / rate
        warnings = []
        if duration < MIN_CHUNK_DURATION:
            warnings.append(f"Chunk is very short: {duration:.3f}s.")
        if before_stats["near_silent"]:
            warnings.append("Chunk appears near-silent before normalization.")
        if after_stats["near_silent"]:
            warnings.append("Chunk appears near-silent after normalization.")
        timeline.append(
            {
                "index": index,
                "audio_file": str(audio_path),
                "start_time": round(cursor, 3),
                "duration": round(duration, 3),
                "stats_before": before_stats,
                "stats_after": after_stats,
                "warnings": warnings,
            }
        )
        cursor += duration
        rendered.append(audio)
        if gap_ms and index < len(audio_paths):
            gap = silence(rate, channels, gap_ms)
            rendered.append(gap)
            cursor += len(gap) / rate

    chapter_audio = np.concatenate(rendered, axis=0)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(output_path, chapter_audio, sample_rate)

    result = {
        "output_file": str(output_path),
        "sample_rate": sample_rate,
        "target_lufs": target_lufs,
        "gap_ms": gap_ms,
        "qa_status": qa_status,
        "duration": round(len(chapter_audio) / sample_rate, 3),
        "chunk_count": len(audio_paths),
        "qa": {
            "failed": any(item["warnings"] for item in timeline),
            "warnings": [
                {"index": item["index"], "warnings": item["warnings"]}
                for item in timeline
                if item["warnings"]
            ],
        },
        "timeline": timeline,
    }
    metadata_path = output_path.with_suffix(output_path.suffix + ".json")
    metadata_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize and stitch Gemini audiobook chunks.")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--target-lufs", default=TARGET_LUFS, type=float)
    parser.add_argument("--gap-ms", default=120, type=int)
    parser.add_argument("--allow-unapproved", action="store_true")
    args = parser.parse_args()

    result = compile_audio(
        args.manifest,
        args.output,
        args.target_lufs,
        args.gap_ms,
        require_approved=not args.allow_unapproved,
    )
    print(f"Wrote chapter audio: {result['output_file']}")
    print(f"Duration: {result['duration']}s")


if __name__ == "__main__":
    main()
