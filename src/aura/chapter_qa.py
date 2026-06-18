import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable

from src.aura.gemini_production import load_json, write_json
from src.aura.render_queue import chunk_id, normalize_chunk_ids


VALID_STATUSES = {"pending", "approved", "needs_rerender", "rejected"}


def set_qa_status(manifest_path: Path, status: str, note: str = "") -> Dict[str, Any]:
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid QA status {status!r}. Use one of: {', '.join(sorted(VALID_STATUSES))}")
    manifest = load_json(manifest_path)
    manifest["qa_status"] = status
    entry = {
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if note:
        entry["note"] = note
    manifest.setdefault("qa_notes", []).append(entry)
    write_json(manifest_path, manifest)
    return manifest


def set_chunk_qa_status(
    manifest_path: Path,
    chunks: Iterable[str],
    status: str,
    note: str = "",
) -> Dict[str, Any]:
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid QA status {status!r}. Use one of: {', '.join(sorted(VALID_STATUSES))}")
    manifest = load_json(manifest_path)
    requested = set(normalize_chunk_ids(chunks))
    if not requested:
        raise ValueError("At least one chunk id is required.")

    found = set()
    timestamp = datetime.now(timezone.utc).isoformat()
    for chunk in manifest.get("chunks", []):
        cid = chunk_id(int(chunk["index"]))
        if cid not in requested:
            continue
        found.add(cid)
        chunk["qa_status"] = status
        entry = {"status": status, "timestamp": timestamp}
        if note:
            entry["note"] = note
        chunk.setdefault("qa_notes", []).append(entry)

    missing = requested - found
    if missing:
        raise ValueError(f"Chunk(s) not found in manifest: {', '.join(sorted(missing))}")

    write_json(manifest_path, manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Set chapter QA status on an exported production manifest.")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--status", required=True, choices=sorted(VALID_STATUSES))
    parser.add_argument("--note", default="")
    parser.add_argument("--chunks", nargs="*", help="Optional chunk ids/numbers. If omitted, sets chapter QA.")
    args = parser.parse_args()

    if args.chunks:
        set_chunk_qa_status(args.manifest, args.chunks, args.status, args.note)
        print(f"{args.manifest}: chunks {', '.join(normalize_chunk_ids(args.chunks))} qa_status={args.status}")
    else:
        manifest = set_qa_status(args.manifest, args.status, args.note)
        print(f"{args.manifest}: qa_status={manifest['qa_status']}")


if __name__ == "__main__":
    main()
