"""Unicode-correct emoji extraction.

Returns ordered list-with-duplicates so callers can compute both totals
and per-glyph counts from one scan. Normalization strips skin-tone and
VS-16 variants to collapse rendering variants into counting-equivalent
identities; ZWJ compounds and regional indicators are preserved.

Sibling module to :mod:`oss_profanity.profanity` — same input type, same
return type shape (``list[str]``), different semantics: emoji callers
want totals and frequency, profanity callers want unique-hit membership.
"""

from __future__ import annotations

from typing import Final

from emoji import emoji_list

# U+1F3FB..U+1F3FF — Fitzpatrick skin-tone modifiers (5 shades)
_SKIN_TONE_CODEPOINTS: Final[frozenset[str]] = frozenset(
    chr(c) for c in range(0x1F3FB, 0x1F400)
)
# U+FE0F — Variation Selector-16, "display as emoji"
_VS16: Final[str] = "️"


def _normalize(e: str) -> str:
    """Return ``e`` with skin-tone modifiers and VS-16 stripped.

    ZWJ (U+200D), RIS codepoints, keycap combining characters, and every
    base glyph pass through untouched — the goal is to collapse tonal
    and presentation variants into a single counting identity, not to
    simplify the emoji's semantic shape.
    """
    return "".join(
        c for c in e if c not in _SKIN_TONE_CODEPOINTS and c != _VS16
    )


def extract(text: str) -> list[str]:
    """Return emoji in ``text`` in order of appearance, with duplicates.

    Each element is a normalized emoji string (see :func:`_normalize`).
    ``:rocket:`` and other shortcodes are not expanded; only rendered
    Unicode emoji are counted.
    """
    if not text:
        return []
    return [_normalize(m["emoji"]) for m in emoji_list(text)]


def count(text: str) -> int:
    """Return the total number of emoji occurrences in ``text``."""
    return len(extract(text))
