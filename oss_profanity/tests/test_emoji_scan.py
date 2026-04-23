"""Unit tests for emoji_scan.py — extract, count, Unicode edge cases."""

from __future__ import annotations

import time

import pytest

from oss_profanity.emoji_scan import count, extract


# -------- extract: basics --------


def test_extract_empty_returns_empty() -> None:
    assert extract("") == []


def test_extract_whitespace_returns_empty() -> None:
    assert extract("   \n\t  ") == []


def test_extract_ascii_only_returns_empty() -> None:
    assert extract("hello world this is fine") == []


def test_extract_single_emoji() -> None:
    assert extract("🚀") == ["🚀"]


def test_extract_preserves_order() -> None:
    assert extract("Release 🚀 and fix 🐛") == ["🚀", "🐛"]


def test_extract_preserves_duplicates() -> None:
    assert extract("🚀🚀🚀 launch!") == ["🚀", "🚀", "🚀"]


def test_extract_mixed_unicode_and_ascii() -> None:
    assert extract("PR #42 ✅ merged") == ["✅"]


# -------- extract: normalization --------


def test_extract_collapses_skin_tone_to_base_glyph() -> None:
    plain = extract("👍")
    tone = extract("👍🏽")
    dark_tone = extract("👍🏿")
    assert plain == tone == dark_tone == ["👍"]


def test_extract_strips_vs16_from_warning_emoji() -> None:
    """⚠️ is U+26A0 U+FE0F; post-normalize the VS-16 is stripped."""
    assert extract("⚠️ careful") == ["⚠"]


def test_extract_preserves_zwj_compound() -> None:
    """👨‍💻 = U+1F468 U+200D U+1F4BB — single unit, ZWJ survives normalization."""
    result = extract("👨‍💻 at work")
    assert len(result) == 1
    assert "‍" in result[0]  # ZWJ preserved


def test_extract_preserves_rainbow_flag_zwj() -> None:
    """🏳️‍🌈 = U+1F3F3 U+FE0F U+200D U+1F308 — VS-16 stripped, ZWJ preserved."""
    result = extract("🏳️‍🌈 pride")
    assert len(result) == 1
    assert "‍" in result[0]
    assert "️" not in result[0]


def test_extract_regional_indicator_flag_stays_single_unit() -> None:
    """🇺🇸 is a RIS pair (U+1F1FA U+1F1F8); must not split into two emoji."""
    assert extract("🇺🇸") == ["🇺🇸"]


def test_extract_two_flags_side_by_side() -> None:
    assert extract("🇺🇸🇩🇪") == ["🇺🇸", "🇩🇪"]


def test_extract_keycap_sequence_is_single_unit() -> None:
    """1️⃣ = U+0031 U+FE0F U+20E3 — VS-16 stripped, keycap combiner kept."""
    result = extract("1️⃣ first")
    assert len(result) == 1
    assert "1" in result[0]
    assert "⃣" in result[0]  # combining enclosing keycap preserved
    assert "️" not in result[0]


def test_extract_family_emoji_is_single_unit() -> None:
    """👨‍👩‍👧‍👦 is a multi-ZWJ compound."""
    result = extract("👨‍👩‍👧‍👦")
    assert len(result) == 1


# -------- extract: shortcodes are NOT expanded --------


@pytest.mark.parametrize(
    "text",
    [
        ":rocket: launch",
        ":bug: fix",
        "see :heart: for details",
        "::double-colons::",
    ],
)
def test_extract_ignores_shortcodes(text: str) -> None:
    assert extract(text) == []


# -------- count: mirrors extract --------


@pytest.mark.parametrize(
    "text",
    [
        "",
        "hello",
        "🚀",
        "🚀🚀🚀",
        "Release 🚀 and fix 🐛",
        "👨‍💻 👩‍💻",
        "🇺🇸🇩🇪🇯🇵",
    ],
)
def test_count_matches_len_extract(text: str) -> None:
    assert count(text) == len(extract(text))


def test_count_zero_for_no_emoji() -> None:
    assert count("hello world") == 0
    assert count("") == 0
    assert count(":rocket:") == 0


def test_count_three_for_three_emoji() -> None:
    assert count("🚀🚀🚀") == 3


# -------- performance smoke --------


def test_extract_10k_messages_under_one_second() -> None:
    messages = [
        "Release 🚀 new version",
        "fix bug 🐛",
        "plain commit message",
        "👍 looks good",
        "merge conflict 💥",
    ] * 2000
    start = time.perf_counter()
    for msg in messages:
        extract(msg)
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0, f"10k extracts took {elapsed:.2f}s (ceiling: 1.0s)"


# -------- module introspection / contract --------


def test_public_surface_is_extract_and_count_only() -> None:
    """Contract: the only public names are extract and count."""
    import oss_profanity.emoji_scan as mod

    public = {name for name in dir(mod) if not name.startswith("_")}
    expected_public = {"extract", "count"}
    allowed_reexports = {
        "annotations",
        "Final",
        "emoji_list",
    }
    leaked = public - expected_public - allowed_reexports
    assert not leaked, f"unexpected public names: {leaked}"


# -------- sibling-contract test with IP-002 --------


def test_returns_list_of_str_matching_ip002_shape() -> None:
    """IP-002 scan() and IP-003 extract() both return list[str]."""
    result = extract("🚀 release")
    assert isinstance(result, list)
    assert all(isinstance(e, str) for e in result)
