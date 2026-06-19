import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.aura.gemini_production import (
    GEMINI_TTS_MODEL,
    load_json,
    request_output_path,
    validate_gemini_request,
    wave_info,
    write_json,
)
from src.aura.render_queue import queue_request_paths

# Audiobook pace: ~130 words per minute is a natural narrator speed.
# We use 0.35× as a very loose lower bound — a chunk rendered faster than this
# almost certainly truncated or hallucinated.
AUDIOBOOK_WPM = 130
MIN_DURATION_RATIO = 0.35  # flag if actual < expected * this ratio

DEFAULT_INTER_CHUNK_DELAY = 0.0  # seconds; increase to 1.0–2.0 for quota safety


def manifest_requests(manifest_path: Path) -> List[Path]:
    manifest = load_json(manifest_path)
    base = manifest_path.parent
    requests = []
    for request in manifest.get("requests", []):
        path = Path(request)
        if not path.is_absolute():
            candidate = base / path
            path = candidate if candidate.exists() else path
        requests.append(path)
    return requests


def already_rendered(request_path: Path) -> bool:
    payload = load_json(request_path)
    output_path = request_output_path(payload)
    if not output_path.exists():
        return False
    try:
        info = wave_info(output_path)
    except Exception:
        return False
    return info["duration"] > 0 and info["size_bytes"] > 2048


def count_prompt_words(payload: Dict[str, Any]) -> int:
    """Count words in the spoken transcript portion of a request payload."""
    transcript = payload.get("transcript", "")
    if not transcript:
        # Fall back to tts_prompt — count only lines after #### TRANSCRIPT
        prompt = payload.get("tts_prompt", "")
        marker = "#### TRANSCRIPT"
        if marker in prompt:
            transcript = prompt[prompt.index(marker) + len(marker):]
        else:
            transcript = prompt
    # Strip SpeakerN: prefixes and audio tags, then count words
    import re
    text = re.sub(r"^Speaker\d+:\s*", "", transcript, flags=re.MULTILINE)
    text = re.sub(r"\[.*?\]", "", text)
    return len(text.split())


def check_duration(payload: Dict[str, Any], audio_info: Dict[str, Any]) -> Optional[str]:
    """Return a warning string if the rendered duration seems suspiciously short."""
    word_count = count_prompt_words(payload)
    if word_count < 5:
        return None  # too short to measure meaningfully
    expected_min = (word_count / AUDIOBOOK_WPM) * 60 * MIN_DURATION_RATIO
    actual = audio_info.get("duration", 0)
    if actual < expected_min:
        return (
            f"Render may be truncated: {actual:.1f}s actual vs "
            f"~{expected_min:.1f}s minimum expected for {word_count} words. "
            "Re-render or QA carefully."
        )
    return None


def render_one(request_path: Path, model: str) -> None:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "src.aura.gemini_tts_runner",
            "--request",
            str(request_path),
            "--model",
            model,
        ],
        check=True,
    )


def render_with_retries(request_path: Path, model: str, retries: int, backoff: float) -> Dict[str, Any]:
    payload = load_json(request_path)
    warnings = validate_gemini_request(payload)
    output_path = request_output_path(payload)
    attempts = 0
    last_error = ""

    while attempts <= retries:
        attempts += 1
        try:
            render_one(request_path, payload.get("model") or model)
            audio = wave_info(output_path)
            duration_warning = check_duration(payload, audio)
            if duration_warning:
                warnings.append(duration_warning)
            return {
                "request": str(request_path),
                "output_file": str(output_path),
                "status": "rendered",
                "attempts": attempts,
                "warnings": warnings,
                "audio": audio,
            }
        except Exception as exc:
            last_error = str(exc)
            if attempts > retries:
                break
            time.sleep(backoff * attempts)

    return {
        "request": str(request_path),
        "output_file": str(output_path),
        "status": "failed",
        "attempts": attempts,
        "warnings": warnings,
        "error": last_error,
    }


def render_manifest(
    manifest_path: Path,
    model: str,
    retries: int,
    backoff: float,
    force: bool,
    request_paths: List[Path] | None = None,
    inter_chunk_delay: float = DEFAULT_INTER_CHUNK_DELAY,
) -> Dict[str, Any]:
    request_paths = request_paths or manifest_requests(manifest_path)
    results = []

    for index, request_path in enumerate(request_paths, start=1):
        if not request_path.exists():
            results.append({"request": str(request_path), "status": "missing"})
            continue

        if not force and already_rendered(request_path):
            payload = load_json(request_path)
            output_path = request_output_path(payload)
            results.append(
                {
                    "request": str(request_path),
                    "output_file": str(output_path),
                    "status": "skipped_existing",
                    "attempts": 0,
                    "audio": wave_info(output_path),
                }
            )
            print(f"[{index}/{len(request_paths)}] Skipped existing {output_path}")
            continue

        print(f"[{index}/{len(request_paths)}] Rendering {request_path}")
        result = render_with_retries(request_path, model, retries, backoff)
        results.append(result)

        if result["status"] == "failed":
            print(f"Failed {request_path}: {result.get('error')}")
        else:
            print(f"Rendered {result['output_file']}")
            if result.get("warnings"):
                for w in result["warnings"]:
                    print(f"  ⚠ {w}")

        # Inter-chunk delay: avoids sustained quota pressure on long chapters.
        # Only applied after successful renders, not after skips or failures.
        if inter_chunk_delay > 0 and result["status"] == "rendered" and index < len(request_paths):
            time.sleep(inter_chunk_delay)

    summary = {
        "manifest": str(manifest_path),
        "model": model,
        "total": len(results),
        "rendered": sum(1 for result in results if result["status"] == "rendered"),
        "skipped_existing": sum(1 for result in results if result["status"] == "skipped_existing"),
        "failed": sum(1 for result in results if result["status"] in {"failed", "missing"}),
        "duration_warnings": sum(
            1 for result in results
            if any("truncated" in w for w in result.get("warnings", []))
        ),
        "results": results,
    }
    write_json(manifest_path.with_suffix(".render_log.json"), summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Render Gemini chapter chunks with retry/resume.")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--queue", type=Path, help="Optional render queue. Only queued chunks will render.")
    parser.add_argument("--model", default=GEMINI_TTS_MODEL)
    parser.add_argument("--retries", default=2, type=int)
    parser.add_argument("--backoff", default=2.0, type=float)
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--inter-chunk-delay",
        default=DEFAULT_INTER_CHUNK_DELAY,
        type=float,
        dest="inter_chunk_delay",
        help=(
            "Seconds to wait between successful chunk renders. "
            "Use 1.0-2.0 on long chapters to avoid Gemini quota errors (429s). "
            f"Default: {DEFAULT_INTER_CHUNK_DELAY}."
        ),
    )
    args = parser.parse_args()

    request_paths = queue_request_paths(args.queue) if args.queue else None
    summary = render_manifest(
        args.manifest,
        args.model,
        args.retries,
        args.backoff,
        args.force,
        request_paths,
        inter_chunk_delay=args.inter_chunk_delay,
    )
    print(
        f"Done: {summary['rendered']} rendered, "
        f"{summary['skipped_existing']} skipped, {summary['failed']} failed."
    )
    if summary.get("duration_warnings"):
        print(f"⚠ {summary['duration_warnings']} chunk(s) flagged for possible truncation — check render log.")
    if summary["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
