import numpy as np

from src.aura.audio_levels import (
    MAX_RECOMMENDED_GAIN_DB,
    audio_stats,
    choose_level_metric,
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


def test_choose_level_metric_keeps_spot_and_motion_on_rms():
    assert choose_level_metric("ambience", 10.0) == "lufs"
    assert choose_level_metric("music", 10.0) == "lufs"
    assert choose_level_metric("spot", 10.0) == "rms_db"
    assert choose_level_metric("motion", 10.0) == "rms_db"
    assert choose_level_metric("ambience", 1.0) == "rms_db"


def test_recommended_sfx_gain_uses_reference_for_near_silent_voice():
    result = recommended_sfx_gain_db(
        voice_stats={"rms_db": -80.0, "near_silent": True},
        asset_stats={"rms_db": -30.0},
        effect_type="spot",
        relative_to_voice_db=-10.0,
        duration_seconds=1.0,
        reference_voice_stats={"rms_db": -20.0, "near_silent": False},
    )

    assert result["reference_used"] is True
    assert result["target_sfx_level"] == -30.0
    assert result["recommended_gain_db"] == 0.0


def test_recommended_sfx_gain_clamps_extreme_gain():
    result = recommended_sfx_gain_db(
        voice_stats={"rms_db": -20.0, "near_silent": False},
        asset_stats={"rms_db": -70.0},
        effect_type="spot",
        relative_to_voice_db=-10.0,
        duration_seconds=1.0,
    )

    assert result["clamped"] is True
    assert result["recommended_gain_db"] == MAX_RECOMMENDED_GAIN_DB
    assert result["unclamped_gain_db"] == 40.0
