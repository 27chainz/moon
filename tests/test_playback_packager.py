from pathlib import Path

import numpy as np
import soundfile as sf

from src.aura.playback_packager import build_ffmpeg_hls_command, package_hls


def write_wav(path: Path, seconds: float = 0.2, sample_rate: int = 24000) -> None:
    samples = int(seconds * sample_rate)
    audio = np.zeros(samples, dtype=np.float32)
    sf.write(path, audio, sample_rate)


def test_build_ffmpeg_hls_command():
    command = build_ffmpeg_hls_command(
        input_audio=Path("chapter.wav"),
        playlist_path=Path("hls/chapter_001.m3u8"),
        segment_pattern=Path("hls/chapter_001_%05d.ts"),
        bitrate="96k",
        segment_seconds=8,
        codec="aac",
        ffmpeg_bin="ffmpeg",
    )

    assert command[:4] == ["ffmpeg", "-y", "-i", "chapter.wav"]
    assert "-hls_time" in command
    assert command[command.index("-hls_time") + 1] == "8"
    assert command[command.index("-b:a") + 1] == "96k"
    assert command[-1] == "hls\\chapter_001.m3u8" or command[-1] == "hls/chapter_001.m3u8"


def test_package_hls_dry_run_writes_manifest(tmp_path):
    input_audio = tmp_path / "chapter_001_master.wav"
    write_wav(input_audio)
    output_dir = tmp_path / "hls"

    manifest = package_hls(
        input_audio=input_audio,
        output_dir=output_dir,
        book_id="book_001",
        chapter_id="chapter_001",
        dry_run=True,
    )

    assert (output_dir / "playback_manifest.json").exists()
    assert manifest["book_id"] == "book_001"
    assert manifest["chapter_id"] == "chapter_001"
    assert manifest["format"] == "hls"
    assert manifest["dry_run"] is True
    assert manifest["playlist"].endswith("chapter_001.m3u8")
    assert manifest["segment_pattern"].endswith("chapter_001_%05d.ts")
    assert manifest["segment_count"] == 0
