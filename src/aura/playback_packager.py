import argparse
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List


DEFAULT_BITRATE = "128k"
DEFAULT_SEGMENT_SECONDS = 6
DEFAULT_CODEC = "aac"


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def hls_paths(output_dir: Path, chapter_id: str) -> Dict[str, Path]:
    return {
        "playlist": output_dir / f"{chapter_id}.m3u8",
        "segment_pattern": output_dir / f"{chapter_id}_%05d.ts",
        "manifest": output_dir / "playback_manifest.json",
    }


def build_ffmpeg_hls_command(
    input_audio: Path,
    playlist_path: Path,
    segment_pattern: Path,
    bitrate: str = DEFAULT_BITRATE,
    segment_seconds: int = DEFAULT_SEGMENT_SECONDS,
    codec: str = DEFAULT_CODEC,
    ffmpeg_bin: str = "ffmpeg",
) -> List[str]:
    return [
        ffmpeg_bin,
        "-y",
        "-i",
        str(input_audio),
        "-vn",
        "-c:a",
        codec,
        "-b:a",
        bitrate,
        "-hls_time",
        str(segment_seconds),
        "-hls_playlist_type",
        "vod",
        "-hls_segment_filename",
        str(segment_pattern),
        str(playlist_path),
    ]


def discover_segments(output_dir: Path, chapter_id: str) -> List[Path]:
    return sorted(output_dir.glob(f"{chapter_id}_*.ts"))


def create_playback_manifest(
    input_audio: Path,
    output_dir: Path,
    book_id: str,
    chapter_id: str,
    bitrate: str,
    segment_seconds: int,
    codec: str,
    command: List[str],
    dry_run: bool,
) -> Dict[str, Any]:
    paths = hls_paths(output_dir, chapter_id)
    segments = discover_segments(output_dir, chapter_id)
    return {
        "playback_manifest_version": "0.1",
        "book_id": book_id,
        "chapter_id": chapter_id,
        "source_master_audio": str(input_audio),
        "format": "hls",
        "playlist": str(paths["playlist"]),
        "segment_pattern": str(paths["segment_pattern"]),
        "segments": [str(segment) for segment in segments],
        "segment_count": len(segments),
        "codec": codec,
        "bitrate": bitrate,
        "segment_duration_seconds": segment_seconds,
        "dry_run": dry_run,
        "ffmpeg_command": command,
    }


def package_hls(
    input_audio: Path,
    output_dir: Path,
    book_id: str,
    chapter_id: str,
    bitrate: str = DEFAULT_BITRATE,
    segment_seconds: int = DEFAULT_SEGMENT_SECONDS,
    codec: str = DEFAULT_CODEC,
    ffmpeg_bin: str = "ffmpeg",
    dry_run: bool = False,
) -> Dict[str, Any]:
    if not input_audio.exists():
        raise FileNotFoundError(f"Missing chapter master audio: {input_audio}")
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = hls_paths(output_dir, chapter_id)
    command = build_ffmpeg_hls_command(
        input_audio=input_audio,
        playlist_path=paths["playlist"],
        segment_pattern=paths["segment_pattern"],
        bitrate=bitrate,
        segment_seconds=segment_seconds,
        codec=codec,
        ffmpeg_bin=ffmpeg_bin,
    )

    if not dry_run:
        subprocess.run(command, check=True)
        if not paths["playlist"].exists():
            raise FileNotFoundError(f"FFmpeg did not create HLS playlist: {paths['playlist']}")

    manifest = create_playback_manifest(
        input_audio=input_audio,
        output_dir=output_dir,
        book_id=book_id,
        chapter_id=chapter_id,
        bitrate=bitrate,
        segment_seconds=segment_seconds,
        codec=codec,
        command=command,
        dry_run=dry_run,
    )
    write_json(paths["manifest"], manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Package a chapter master audio file into HLS playback assets.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--book-id", required=True)
    parser.add_argument("--chapter-id", required=True)
    parser.add_argument("--bitrate", default=DEFAULT_BITRATE)
    parser.add_argument("--segment-seconds", default=DEFAULT_SEGMENT_SECONDS, type=int)
    parser.add_argument("--codec", default=DEFAULT_CODEC)
    parser.add_argument("--ffmpeg-bin", default="ffmpeg")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    manifest = package_hls(
        input_audio=args.input,
        output_dir=args.output_dir,
        book_id=args.book_id,
        chapter_id=args.chapter_id,
        bitrate=args.bitrate,
        segment_seconds=args.segment_seconds,
        codec=args.codec,
        ffmpeg_bin=args.ffmpeg_bin,
        dry_run=args.dry_run,
    )
    print(f"Wrote playback manifest: {args.output_dir / 'playback_manifest.json'}")
    print(f"Playlist: {manifest['playlist']}")
    print(f"Segments: {manifest['segment_count']}")


if __name__ == "__main__":
    main()
