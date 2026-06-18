import argparse
from pathlib import Path
from typing import Any, Dict, Iterable, List

from src.aura.gemini_production import load_json, write_json


QUEUE_VERSION = "0.1"


def chunk_id(index: int) -> str:
    return f"chunk_{index:03d}"


def normalize_chunk_ids(values: Iterable[str]) -> List[str]:
    output = []
    for value in values:
        cleaned = str(value).strip()
        if not cleaned:
            continue
        if cleaned.isdigit():
            cleaned = chunk_id(int(cleaned))
        if cleaned not in output:
            output.append(cleaned)
    return output


def manifest_chunk_lookup(manifest: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    lookup = {}
    for chunk in manifest.get("chunks", []):
        cid = chunk_id(int(chunk["index"]))
        lookup[cid] = chunk
    return lookup


def create_render_queue(
    manifest_path: Path,
    output_path: Path,
    chunks: List[str],
    purpose: str,
) -> Dict[str, Any]:
    manifest = load_json(manifest_path)
    lookup = manifest_chunk_lookup(manifest)
    normalized = normalize_chunk_ids(chunks)
    if not normalized:
        raise ValueError("Render queue needs at least one chunk.")

    queue_chunks = []
    for cid in normalized:
        if cid not in lookup:
            raise ValueError(f"Chunk {cid!r} is not present in {manifest_path}.")
        chunk = lookup[cid]
        queue_chunks.append(
            {
                "chunk_id": cid,
                "request_file": chunk["request_file"],
                "prompt_preview_file": chunk.get("prompt_preview_file"),
                "audio_file": chunk["audio_file"],
                "scene_id": chunk.get("scene_id"),
                "scene_position": chunk.get("scene_position"),
                "scene_exit_type": chunk.get("scene_exit_type"),
                "status": "pending",
                "reason": purpose,
            }
        )

    queue = {
        "queue_version": QUEUE_VERSION,
        "purpose": purpose,
        "status": "pending",
        "manifest": str(manifest_path),
        "chunks": queue_chunks,
    }
    write_json(output_path, queue)
    return queue


def queue_request_paths(queue_path: Path) -> List[Path]:
    queue = load_json(queue_path)
    base = queue_path.parent
    paths = []
    for chunk in queue.get("chunks", []):
        path = Path(chunk["request_file"])
        if not path.is_absolute():
            candidate = base / path
            path = candidate if candidate.exists() else path
        paths.append(path)
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Create targeted render queues for Gemini chunks.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create", help="Create a render queue from a manifest.")
    create_parser.add_argument("--manifest", required=True, type=Path)
    create_parser.add_argument("--output", required=True, type=Path)
    create_parser.add_argument("--chunks", nargs="+", required=True)
    create_parser.add_argument("--purpose", required=True)

    args = parser.parse_args()
    if args.command == "create":
        queue = create_render_queue(
            args.manifest,
            args.output,
            chunks=args.chunks,
            purpose=args.purpose,
        )
        print(f"Wrote render queue: {args.output}")
        print(f"Chunks: {', '.join(chunk['chunk_id'] for chunk in queue['chunks'])}")


if __name__ == "__main__":
    main()
