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
EXIT_TYPE_GAP_MULTIPLIERS = {
    "interruption": 0.0,
    "natural_pause": 1.0,
    "sentence_end": 1.0,
    "scene_end": 3.0,
}


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def request_audio_items(manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
    chunks = manifest.get("chunks") or []
    if chunks:
        return [
            {
                "index": chunk.get("index", index),
                "audio_file": Path(chunk["audio_file"]),
                "request_file": chunk.get("request_file"),
                "scene_id": chunk.get("scene_id"),
                "scene_exit_type": chunk.get("scene_exit_type", "natural_pause"),
                "beat_ids": chunk.get("beat_ids") or [],
            }
            for index, chunk in enumerate(chunks, start=1)
        ]

    items = []
    for index, request_path in enumerate(manifest.get("requests", []), start=1):
        request = load_json(Path(request_path))
        source = request.get("source") or {}
        items.append(
            {
                "index": index,
                "audio_file": Path(request["output_file"]),
                "request_file": str(request_path),
                "scene_id": source.get("scene_id"),
                "scene_exit_type": request.get("scene_exit_type")
                or source.get("scene_exit_type")
                or "natural_pause",
                "beat_ids": source.get("beat_ids") or [],
            }
        )
    return items


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


def gap_for_exit_type(exit_type: str, base_gap_ms: int) -> int:
    multiplier = EXIT_TYPE_GAP_MULTIPLIERS.get(exit_type, 1.0)
    return int(round(base_gap_ms * multiplier))


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
    audio_items = request_audio_items(manifest)
    if not audio_items:
        raise ValueError("Manifest has no request audio paths.")

    rendered = []
    sample_rate = None
    channels = None
    timeline = []
    cursor = 0.0

    for index, item in enumerate(audio_items, start=1):
        audio_path = item["audio_file"]
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
                "request_file": item.get("request_file"),
                "scene_id": item.get("scene_id"),
                "scene_exit_type": item.get("scene_exit_type", "natural_pause"),
                "beat_ids": item.get("beat_ids") or [],
                "start_time": round(cursor, 3),
                "duration": round(duration, 3),
                "stats_before": before_stats,
                "stats_after": after_stats,
                "warnings": warnings,
            }
        )
        cursor += duration
        rendered.append(audio)
        if gap_ms and index < len(audio_items):
            effective_gap_ms = gap_for_exit_type(item.get("scene_exit_type", "natural_pause"), gap_ms)
            gap = silence(rate, channels, effective_gap_ms).astype(audio.dtype, copy=False)
            rendered.append(gap)
            cursor += len(gap) / rate
            timeline[-1]["gap_after_ms"] = effective_gap_ms
        else:
            timeline[-1]["gap_after_ms"] = 0

    chapter_audio = np.concatenate(rendered, axis=0)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(output_path, chapter_audio, sample_rate)
    chapter_stats = audio_stats(chapter_audio, sample_rate)

    result = {
        "output_file": str(output_path),
        "sample_rate": sample_rate,
        "target_lufs": target_lufs,
        "gap_ms": gap_ms,
        "qa_status": qa_status,
        "duration": round(len(chapter_audio) / sample_rate, 3),
        "chunk_count": len(audio_items),
        "chapter_stats": chapter_stats,
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
    metadata_path = output_path.with_suffix(".json")
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
