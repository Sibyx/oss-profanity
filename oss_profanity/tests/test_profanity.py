"""Unit tests for profanity.py — scan, detect_language, edge cases."""

from __future__ import annotations

import time

import pytest

from oss_profanity.profanity import detect_language, scan


# -------- scan: basics --------


def test_scan_empty_returns_empty() -> None:
    assert scan("") == []


def test_scan_whitespace_returns_empty() -> None:
    assert scan("   \n\t  ") == []


def test_scan_clean_text_returns_empty() -> None:
    assert scan("hello world this is fine") == []


def test_scan_returns_sorted_unique_hits() -> None:
    assert scan("fuck this shit and fuck that again") == ["fuck", "shit"]


def test_scan_is_case_insensitive() -> None:
    assert scan("FUCK this SHIT") == ["fuck", "shit"]


def test_scan_always_checks_english_even_with_other_lang() -> None:
    """Source comments are ~universally English; always include the en layer."""
    assert scan("fuck this", lang="ru") == ["fuck"]


# -------- scan: Scunthorpe / false-positive resistance --------


@pytest.mark.parametrize(
    "text",
    [
        "this is class code",
        "the scunthorpe united match",
        "the assassin creed game",
        "pass the butter please",
        "grass is green",
    ],
)
def test_scan_no_false_positives_on_substrings(text: str) -> None:
    assert scan(text) == []


# -------- scan: leetspeak --------


def test_scan_leetspeak_digit_substitution() -> None:
    assert scan("sh1t y0u") == ["shit"]


def test_scan_leetspeak_at_sign_for_a() -> None:
    assert scan("@ss") == ["ass"]


def test_scan_leetspeak_exclamation_for_i() -> None:
    assert scan("sh!t") == ["shit"]


def test_scan_leetspeak_dollar_for_s() -> None:
    assert scan("$hit") == ["shit"]


# -------- scan: Russian (Cyrillic) --------


def test_scan_russian_with_explicit_lang() -> None:
    assert "дерьмо" in scan("это полное дерьмо", lang="ru")


# -------- scan: performance smoke --------


def test_scan_10k_messages_under_one_second() -> None:
    messages = [
        "add feature",
        "fix bug",
        "fuck this shit",
        "refactor module",
        "update deps",
    ] * 2000
    start = time.perf_counter()
    for msg in messages:
        scan(msg)
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0, f"10k scans took {elapsed:.2f}s (ceiling: 1.0s)"


# -------- detect_language --------


def test_detect_language_short_text_falls_back_to_english() -> None:
    assert detect_language("hi") == "en"
    assert detect_language("") == "en"
    assert detect_language("ok") == "en"


def test_detect_language_english() -> None:
    assert detect_language("this is a regular English commit message about bugs") == "en"


def test_detect_language_russian() -> None:
    assert detect_language("это полное дерьмо, все сломалось и ничего не работает") == "ru"


def test_detect_language_german() -> None:
    assert detect_language("das ist eine Katastrophe, alles ist kaputt") == "de"


def test_detect_language_spanish() -> None:
    assert detect_language("esto es una mierda, todo está roto") == "es"


def test_detect_language_norwegian_bokmal_maps_to_no() -> None:
    """Lingua detects NB/NN; LDNOOBW has a single `no` list — remap."""
    result = detect_language("dette er en katastrofe, alt er ødelagt og fungerer ikke")
    assert result in {"no", "en"}, f"expected no or en fallback, got {result}"


# -------- integration: scan + detect_language --------


def test_scan_uses_detected_language_for_non_english_profanity() -> None:
    text = "это полное дерьмо, проект сломался окончательно"
    lang = detect_language(text)
    hits = scan(text, lang=lang)
    assert "дерьмо" in hits


# -------- module introspection / contract --------


def test_public_surface_is_just_detect_language_and_scan() -> None:
    """Contract: the only public names are detect_language and scan."""
    import oss_profanity.profanity as mod

    public = {name for name in dir(mod) if not name.startswith("_")}
    # Non-underscore names we deliberately export:
    expected_public = {"detect_language", "scan"}
    # Imports that are not underscore-prefixed but are module-internal:
    allowed_reexports = {
        "annotations",
        "Path",
        "Final",
        "re",
        "IsoCode639_1",
        "LanguageDetector",
        "LanguageDetectorBuilder",
    }
    leaked = public - expected_public - allowed_reexports
    assert not leaked, f"unexpected public names: {leaked}"
