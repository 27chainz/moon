import json
from pathlib import Path

import numpy as np
import soundfile as sf

from src.aura.chapter_audio_compiler import compile_audio, gap_for_exit_type


def write_wav(path: Path, seconds: float = 0.5, sample_rate: int = 24000, freq: float = 220.0) -> None:
    samples = int(seconds * sample_rate)
    t = np.linspace(0, seconds, samples, endpoint=False)
    audio = (0.05 * np.sin(2 * np.pi * freq * t)).astype(np.float32)
    sf.write(path, audio, sample_rate)


def test_gap_for_exit_type():
    assert gap_for_exit_type("interruption", 120) == 0
    assert gap_for_exit_type("natural_pause", 120) == 120
    assert gap_for_exit_type("sentence_end", 120) == 120
    assert gap_for_exit_type("scene_end", 120) == 360
    assert gap_for_exit_type("unknown", 120) == 120


def test_compile_uses_manifest_chunks_and_writes_clean_metadata(tmp_path):
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    first = audio_dir / "chunk_001.wav"
    second = audio_dir / "chunk_002.wav"
    write_wav(first)
    write_wav(second)

    manifest = {
        "qa_status": "approved",
        "chunks": [
            {
                "index": 1,
                "audio_file": str(first),
                "request_file": "requests/chunk_001.json",
                "scene_id": "scene_001",
                "scene_exit_type": "scene_end",
                "beat_ids": ["beat_001"],
            },
            {
                "index": 2,
                "audio_file": str(second),
                "request_file": "requests/chunk_002.json",
                "scene_id": "scene_002",
                "scene_exit_type": "natural_pause",
                "beat_ids": ["beat_002"],
            },
        ],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    output = tmp_path / "chapter_001.wav"
    result = compile_audio(manifest_path, output, target_lufs=-16.0, gap_ms=100)

    assert output.exists()
    assert (tmp_path / "chapter_001.json").exists()
    assert result["chunk_count"] == 2
    assert result["timeline"][0]["scene_exit_type"] == "scene_end"
    assert result["timeline"][0]["gap_after_ms"] == 300
    assert result["timeline"][1]["gap_after_ms"] == 0
    assert "chapter_stats" in result
    assert result["chapter_stats"]["duration"] == result["duration"]
    assert "spectral_centroid_hz" in result["timeline"][0]["stats_after"]
    assert result["timeline"][1]["neighbor_diagnostics"] is not None


def test_compile_flags_neighbour_tonal_jump(tmp_path):
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    first = audio_dir / "chunk_001.wav"
    second = audio_dir / "chunk_002.wav"
    write_wav(first, freq=220)
    write_wav(second, freq=2200)

    manifest = {
        "qa_status": "approved",
        "chunks": [
            {"index": 1, "audio_file": str(first), "scene_exit_type": "sentence_end"},
            {"index": 2, "audio_file": str(second), "scene_exit_type": "sentence_end"},
        ],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = compile_audio(manifest_path, tmp_path / "chapter.wav", target_lufs=-16.0, gap_ms=0)

    diagnostics = result["timeline"][1]["neighbor_diagnostics"]
    assert diagnostics["spectral_centroid_delta_hz"] > 450
    assert any("spectral centroid" in warning for warning in diagnostics["warnings"])
