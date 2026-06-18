import numpy as np

from src.aura.audio_levels import (
    audio_stats,
    db_to_gain,
    recommended_sfx_gain_db,
    rms_db,
)


def test_rms_db_and_gain():
    audio = np.ones((1000, 1), dtype=np.float32) * 0.5

    assert round(rms_db(audio), 3) == -6.021
    assert round(db_to_gain(-6), 3) == 0.501


def test_audio_stats_contains_loudness_fields():
    audio = np.ones((24000, 1), dtype=np.float32) * 0.05
    stats = audio_stats(audio, 24000)

    assert stats["duration"] == 1.0
    assert stats["rms_db"] is not None
    assert "lufs" in stats


def test_recommended_sfx_gain_uses_relative_level():
    voice_stats = {"rms_db": -20.0, "lufs": None}
    asset_stats = {"rms_db": -30.0, "lufs": None}

    result = recommended_sfx_gain_db(
        voice_stats=voice_stats,
        asset_stats=asset_stats,
        effect_type="spot",
        relative_to_voice_db=-10.0,
        duration_seconds=1.0,
    )

    assert result["metric"] == "rms_db"
    assert result["target_sfx_level"] == -30.0
    assert result["recommended_gain_db"] == 0.0
