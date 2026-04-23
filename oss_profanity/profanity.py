"""Deterministic, multilingual profanity scoring.

Uses vendored LDNOOBW word lists (28 languages) plus lingua-py for short-text
language detection. No ML. No dormant deps. Callable from both ingest
(commit messages) and the worker (source comments + identifiers).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

from lingua import IsoCode639_1, LanguageDetector, LanguageDetectorBuilder

_LDNOOBW_DIR: Final[Path] = Path(__file__).parent / "wordlists" / "ldnoobw"
_MIN_DETECT_LEN: Final[int] = 20
_LEETSPEAK_ENABLED: Final[bool] = True
# Common leetspeak substitutions. Digit/symbol → base letter it visually mimics.
# Intentionally conservative; unusual forms (`fuckk`, `fuk`) are not covered.
_LEETSPEAK_TABLE: Final[dict[int, int]] = str.maketrans("4103$5@!", "aioessai")
_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"\b[\w']+\b", re.UNICODE)

# Lingua uses NB/NN for Norwegian; LDNOOBW has a single `no` file.
_LINGUA_TO_LDNOOBW: Final[dict[str, str]] = {"nb": "no", "nn": "no"}

# ISO 639-1 codes that (a) have an LDNOOBW word list AND (b) Lingua knows.
# Four LDNOOBW codes have no Lingua model (fil, kab, tlh, fr-CA-u-sd-caqc) —
# their word lists still load and match via explicit lang= argument.
_DETECTOR_CODES: Final[tuple[IsoCode639_1, ...]] = (
    IsoCode639_1.AR, IsoCode639_1.CS, IsoCode639_1.DA, IsoCode639_1.DE,
    IsoCode639_1.EN, IsoCode639_1.EO, IsoCode639_1.ES, IsoCode639_1.FA,
    IsoCode639_1.FI, IsoCode639_1.FR, IsoCode639_1.HI, IsoCode639_1.HU,
    IsoCode639_1.IT, IsoCode639_1.JA, IsoCode639_1.KO, IsoCode639_1.NL,
    IsoCode639_1.NB, IsoCode639_1.PL, IsoCode639_1.PT, IsoCode639_1.RU,
    IsoCode639_1.SV, IsoCode639_1.TH, IsoCode639_1.TR, IsoCode639_1.ZH,
)

_WORDLISTS: dict[str, frozenset[str]] = {}
_DETECTOR: LanguageDetector | None = None


def _load_wordlists() -> None:
    if _WORDLISTS:
        return
    for path in _LDNOOBW_DIR.iterdir():
        if not path.is_file() or path.suffix == ".md":
            continue
        words = frozenset(
            w.strip().lower()
            for w in path.read_text(encoding="utf-8").splitlines()
            if w.strip() and not w.startswith("#")
        )
        _WORDLISTS[path.name] = words


def _get_detector() -> LanguageDetector:
    global _DETECTOR
    if _DETECTOR is None:
        _DETECTOR = LanguageDetectorBuilder.from_iso_codes_639_1(
            *_DETECTOR_CODES
        ).build()
    return _DETECTOR


def detect_language(text: str) -> str:
    """Return the ISO 639-1 code for ``text``; fall back to ``"en"``.

    Short text (< :data:`_MIN_DETECT_LEN` chars) or text Lingua cannot
    confidently classify returns ``"en"``. Norwegian Bokmål/Nynorsk are
    remapped to ``"no"`` so they match the single LDNOOBW Norwegian list.
    """
    if not text or len(text) < _MIN_DETECT_LEN:
        return "en"
    detected = _get_detector().detect_language_of(text)
    if detected is None:
        return "en"
    code = detected.iso_code_639_1.name.lower()
    return _LINGUA_TO_LDNOOBW.get(code, code)


def scan(text: str, lang: str = "en") -> list[str]:
    """Return sorted unique profanity hits in ``text``.

    Matches against the ``lang``-specific LDNOOBW word set **and** the
    English set — OSS source comments and identifiers are near-universally
    English regardless of the commit-message language, so always including
    the English layer catches the common case.

    Leetspeak variants (``f4ck``, ``sh1t``) are normalized to their
    plain-alphabetic form before matching when
    :data:`_LEETSPEAK_ENABLED` is true.
    """
    if not text:
        return []
    _load_wordlists()
    lowered = text.lower()
    tokens = set(_TOKEN_RE.findall(lowered))
    if _LEETSPEAK_ENABLED:
        # Normalize the whole string first so that symbol substitutions (@, !)
        # survive tokenization — the token regex excludes non-\w characters,
        # so translating after tokenizing would miss @ss, f@ck, sh!t, etc.
        tokens |= set(_TOKEN_RE.findall(lowered.translate(_LEETSPEAK_TABLE)))

    hits: set[str] = set()
    for code in {lang, "en"}:
        wordlist = _WORDLISTS.get(code)
        if wordlist:
            hits |= tokens & wordlist
    return sorted(hits)
