import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

from src.aura.gemini_production import (
    GEMINI_TTS_MODEL,
    load_json,
    request_output_path,
    validate_gemini_request,
    wave_info,
    write_json,
)


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
            return {
                "request": str(request_path),
                "output_file": str(output_path),
                "status": "rendered",
                "attempts": attempts,
                "warnings": warnings,
                "audio": wave_info(output_path),
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
) -> Dict[str, Any]:
    request_paths = manifest_requests(manifest_path)
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

    summary = {
        "manifest": str(manifest_path),
        "model": model,
        "total": len(results),
        "rendered": sum(1 for result in results if result["status"] == "rendered"),
        "skipped_existing": sum(1 for result in results if result["status"] == "skipped_existing"),
        "failed": sum(1 for result in results if result["status"] in {"failed", "missing"}),
        "results": results,
    }
    write_json(manifest_path.with_suffix(".render_log.json"), summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Render Gemini chapter chunks with retry/resume.")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--model", default=GEMINI_TTS_MODEL)
    parser.add_argument("--retries", default=2, type=int)
    parser.add_argument("--backoff", default=2.0, type=float)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    summary = render_manifest(args.manifest, args.model, args.retries, args.backoff, args.force)
    print(
        f"Done: {summary['rendered']} rendered, "
        f"{summary['skipped_existing']} skipped, {summary['failed']} failed."
    )
    if summary["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
