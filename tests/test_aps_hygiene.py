from src.aura.aps_hygiene import normalize_json_strings, normalize_tts_punctuation, strip_markdown


def test_strip_markdown_emphasis() -> None:
    assert strip_markdown("A _Best of Gilbert and Sullivan_ LP") == "A Best of Gilbert and Sullivan LP"
    assert strip_markdown("See **important words** now") == "See important words now"


def test_preserve_internal_underscores_and_asterisks() -> None:
    assert strip_markdown("a drawn_out pause") == "a drawn_out pause"
    assert strip_markdown("variable foo_bar stays") == "variable foo_bar stays"
    assert strip_markdown("a*b should remain") == "a*b should remain"


def test_clean_spacing_before_punctuation() -> None:
    assert strip_markdown("Iolanthe , a play") == "Iolanthe, a play"


def test_normalize_tts_punctuation() -> None:
    assert normalize_tts_punctuation("I\u2019m \u201cgood\u201d - really\u2026") == "I'm \"good\" - really..."
    assert normalize_tts_punctuation("Iâ€™m good") == "I'm good"


def test_normalize_json_strings_recurses() -> None:
    payload = {"a": "Don\u2019t", "b": ["Iâ€™m"], "c": {"d": "fine"}}

    cleaned, changes = normalize_json_strings(payload)

    assert cleaned == {"a": "Don't", "b": ["I'm"], "c": {"d": "fine"}}
    assert changes == 2
