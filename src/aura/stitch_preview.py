import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import soundfile as sf

from src.aura.gemini_production import load_json, write_json


DEFAULT_WINDOW_SECONDS = 2.0


def request_audio_paths(manifest: Dict[str, Any], manifest_path: Path) -> List[Path]:
    paths = []
    base = manifest_path.parent
    for request_path in manifest.get("requests", []):
        request_file = Path(request_path)
        if not request_file.is_absolute():
            candidate = base / request_file
            request_file = candidate if candidate.exists() else request_file
        request = load_json(request_file)
        audio_path = Path(request["output_file"])
        paths.append(audio_path)
    return paths


def tail(audio: np.ndarray, sample_rate: int, seconds: float) -> np.ndarray:
    samples = int(sample_rate * seconds)
    return audio[-samples:] if len(audio) > samples else audio


def head(audio: np.ndarray, sample_rate: int, seconds: float) -> np.ndarray:
    samples = int(sample_rate * seconds)
    return audio[:samples] if len(audio) > samples else audio


def build_stitch_previews(manifest_path: Path, output_dir: Path, seconds: float) -> Dict[str, Any]:
    manifest = load_json(manifest_path)
    audio_paths = request_audio_paths(manifest, manifest_path)
    if len(audio_paths) < 2:
        raise ValueError("Need at least two rendered chunks to create stitch previews.")

    output_dir.mkdir(parents=True, exist_ok=True)
    previews = []

    for index, (left_path, right_path) in enumerate(zip(audio_paths, audio_paths[1:]), start=1):
        if not left_path.exists() or not right_path.exists():
            previews.append(
                {
                    "index": index,
                    "left": str(left_path),
                    "right": str(right_path),
                    "status": "missing_audio",
                }
            )
            continue

        left, left_rate = sf.read(left_path, dtype="float32", always_2d=True)
        right, right_rate = sf.read(right_path, dtype="float32", always_2d=True)
        if left_rate != right_rate:
            previews.append(
                {
                    "index": index,
                    "left": str(left_path),
                    "right": str(right_path),
                    "status": "sample_rate_mismatch",
                }
            )
            continue
        if left.shape[1] != right.shape[1]:
            previews.append(
                {
                    "index": index,
                    "left": str(left_path),
                    "right": str(right_path),
                    "status": "channel_mismatch",
                }
            )
            continue

        preview_audio = np.concatenate([tail(left, left_rate, seconds), head(right, right_rate, seconds)], axis=0)
        preview_path = output_dir / f"stitch_{index:03d}.wav"
        sf.write(preview_path, preview_audio, left_rate)
        previews.append(
            {
                "index": index,
                "left": str(left_path),
                "right": str(right_path),
                "preview_file": str(preview_path),
                "duration": round(len(preview_audio) / left_rate, 3),
                "status": "created",
                "qa_status": "pending",
            }
        )

    result = {
        "manifest": str(manifest_path),
        "window_seconds": seconds,
        "preview_count": len(previews),
        "previews": previews,
    }
    write_json(output_dir / "stitch_previews.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Create short stitch QA previews between rendered chunks.")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--seconds", default=DEFAULT_WINDOW_SECONDS, type=float)
    args = parser.parse_args()

    output_dir = args.output_dir or args.manifest.parent / "qa" / "stitches"
    result = build_stitch_previews(args.manifest, output_dir, args.seconds)
    print(f"Wrote {result['preview_count']} stitch preview record(s) to {output_dir}")


if __name__ == "__main__":
    main()
