import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from src.aura.gemini_production import load_json, write_json


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Set chapter QA status on an exported production manifest.")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--status", required=True, choices=sorted(VALID_STATUSES))
    parser.add_argument("--note", default="")
    args = parser.parse_args()

    manifest = set_qa_status(args.manifest, args.status, args.note)
    print(f"{args.manifest}: qa_status={manifest['qa_status']}")


if __name__ == "__main__":
    main()
