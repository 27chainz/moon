from src.aura.gemini_chapter_exporter import performance_audio_tags


def test_dry_delivery_does_not_become_sarcastic():
    tags = performance_audio_tags(
        {
            "emotion": "dry amusement",
            "intensity": 0.7,
            "delivery": "controlled understatement",
        }
    )

    assert tags == ""


def test_low_intensity_sadness_does_not_become_crying():
    tags = performance_audio_tags(
        {
            "emotion": "quiet sadness",
            "intensity": 0.3,
            "delivery": "restrained",
        }
    )

    assert tags == ""


def test_high_intensity_sadness_can_become_crying():
    tags = performance_audio_tags(
        {
            "emotion": "sadness",
            "intensity": 0.9,
            "delivery": "raw and exposed",
        }
    )

    assert tags == "[crying]"


def test_shock_prefers_trembling_unless_gasp_is_explicit():
    tags = performance_audio_tags(
        {
            "emotion": "shock and disbelief",
            "intensity": 0.7,
            "delivery": "stunned",
        }
    )

    assert tags == "[trembling]"


def test_explicit_gasp_can_use_gasp_tag():
    tags = performance_audio_tags(
        {
            "emotion": "sudden shock",
            "intensity": 0.7,
            "delivery": "gasp",
        }
    )

    assert tags == "[gasp]"


def test_character_tag_suppression_removes_matching_tag():
    tags = performance_audio_tags(
        {
            "emotion": "bitter",
            "intensity": 0.7,
            "delivery": "cutting",
        },
        suppressed_tags=["[sarcastic]"],
    )

    assert tags == ""
