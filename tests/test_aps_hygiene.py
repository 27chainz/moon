from src.aura.aps_hygiene import strip_markdown


def test_strip_markdown_emphasis() -> None:
    assert strip_markdown("A _Best of Gilbert and Sullivan_ LP") == "A Best of Gilbert and Sullivan LP"
    assert strip_markdown("See **important words** now") == "See important words now"


def test_preserve_internal_underscores_and_asterisks() -> None:
    assert strip_markdown("a drawn_out pause") == "a drawn_out pause"
    assert strip_markdown("variable foo_bar stays") == "variable foo_bar stays"
    assert strip_markdown("a*b should remain") == "a*b should remain"


def test_clean_spacing_before_punctuation() -> None:
    assert strip_markdown("Iolanthe , a play") == "Iolanthe, a play"
