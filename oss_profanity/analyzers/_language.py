"""Primary-language detection via a file-extension histogram.

Uses ``identify`` tags as the canonical language name. Ties are broken
deterministically (alphabetical) so repeated runs produce the same
answer. Empty / all-skipped directories return ``None``.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Final

from identify import identify

from ._walk import iter_source_files

# Programming-language tags we vote on for the primary-language histogram.
# Intentionally excludes markup / data formats (markdown, json, yaml, toml,
# html, css, sql) — a README-heavy Go repo should be classified as "go", not
# "markdown". The linter dispatch in ``_runner`` only fires on a small subset
# of these (python → ruff+bandit, javascript/typescript/jsx/tsx → eslint);
# the rest still get a meaningful primary-language label for the study's
# per-language breakdown in IP-008.
_LANGUAGE_TAGS: Final[frozenset[str]] = frozenset(
    {
        "python",
        "javascript",
        "typescript",
        "jsx",
        "tsx",
        "go",
        "rust",
        "ruby",
        "java",
        "kotlin",
        "scala",
        "swift",
        "c",
        "c++",
        "c#",
        "php",
        "shell",
        "bash",
        "lua",
        "r",
        "perl",
        "haskell",
        "ocaml",
        "elixir",
        "erlang",
        "dart",
        "julia",
        "groovy",
        "objective-c",
        "clojure",
    }
)


def detect_primary_language(repo_dir: Path) -> str | None:
    """Return the dominant language tag under ``repo_dir`` or ``None``.

    A "dominant" language is the one with the most files after the skip
    rules in :func:`_walk.iter_source_files` apply. Files with no language
    tag (binaries, unknown extensions) don't vote. Ties break
    alphabetically to keep runs deterministic.
    """
    counts: Counter[str] = Counter()
    for path in iter_source_files(repo_dir):
        for tag in identify.tags_from_filename(path.name):
            if tag in _LANGUAGE_TAGS:
                counts[tag] += 1
    if not counts:
        return None
    max_count = max(counts.values())
    winners = sorted(tag for tag, c in counts.items() if c == max_count)
    return winners[0]
