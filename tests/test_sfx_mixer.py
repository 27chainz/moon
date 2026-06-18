import json
from pathlib import Path

import numpy as np
import soundfile as sf

from src.aura.sfx_mixer import db_to_gain, mix_sfx_plan


def write_wav(path: Path, seconds: float, sample_rate: int = 24000, channels: int = 1, value: float = 0.0) -> None:
    samples = int(seconds * sample_rate)
    audio = np.full((samples, channels), value, dtype=np.float32)
    sf.write(path, audio, sample_rate)


def test_db_to_gain():
    assert round(db_to_gain(-6), 3) == 0.501
    assert db_to_gain(0) == 1.0


def test_mix_sfx_plan_time_point(tmp_path):
    master = tmp_path / "master.wav"
    asset = tmp_path / "click.wav"
    output = tmp_path / "mix.wav"
    write_wav(master, seconds=1.0, value=0.0)
    write_wav(asset, seconds=0.1, value=0.5)
    plan = {
        "voice_master": str(master),
        "output_mix": str(output),
        "sfx": [
            {
                "sfx_id": "sfx_001",
                "asset_id": "click",
                "asset_path": str(asset),
                "placement": "time_point",
                "start_seconds": 0.5,
                "level_db": 0,
            }
        ],
    }
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    result = mix_sfx_plan(plan_path)
    mixed, sample_rate = sf.read(output, dtype="float32")

    assert result["layers"][0]["start_seconds"] == 0.5
    assert output.exists()
    assert output.with_suffix(".json").exists()
    assert np.max(np.abs(mixed[int(0.5 * sample_rate) : int(0.6 * sample_rate)])) > 0


def test_mix_sfx_plan_time_span_loops(tmp_path):
    master = tmp_path / "master.wav"
    asset = tmp_path / "ambience.wav"
    output = tmp_path / "mix.wav"
    write_wav(master, seconds=1.0, value=0.0)
    write_wav(asset, seconds=0.2, value=0.25)
    plan = {
        "voice_master": str(master),
        "output_mix": str(output),
        "sfx": [
            {
                "sfx_id": "sfx_001",
                "asset_id": "ambience",
                "asset_path": str(asset),
                "placement": "time_span",
                "start_seconds": 0.0,
                "end_seconds": 0.8,
                "level_db": -6,
                "duration_policy": {"policy": "loop_crossfade"},
            }
        ],
    }
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    result = mix_sfx_plan(plan_path)

    assert result["layers"][0]["duration_seconds"] == 0.8
    assert output.exists()


def test_mix_sfx_plan_relative_level(tmp_path):
    master = tmp_path / "master.wav"
    asset = tmp_path / "click.wav"
    output = tmp_path / "mix.wav"
    write_wav(master, seconds=1.0, value=0.1)
    write_wav(asset, seconds=0.1, value=0.1)
    plan = {
        "voice_master": str(master),
        "output_mix": str(output),
        "sfx": [
            {
                "sfx_id": "sfx_001",
                "asset_id": "click",
                "asset_path": str(asset),
                "placement": "time_point",
                "start_seconds": 0.5,
                "mix_role": "spot_important",
                "relative_to_voice_db": -10,
            }
        ],
    }
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    result = mix_sfx_plan(plan_path)

    layer = result["layers"][0]
    assert layer["level"]["mode"] == "relative_to_voice"
    assert layer["level"]["mix_role"] == "spot_important"
    assert layer["level"]["recommendation"]["recommended_gain_db"] < 0
