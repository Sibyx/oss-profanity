"""Single-pass source-tree walk feeding every in-line signal.

The load-bearing DRY contract: we walk the tree once, and every file
goes through one tree-sitter parse and one ``identify`` tag lookup.
From that single pass we emit **all** the fields that don't need an
external tool — profanity hits (IP-002), emoji occurrences (IP-003),
tech-debt markers, comment-to-code ratio, loc_total, files_scanned.

Adding a new "free" signal later plugs in at the ``for file in files:``
loop body; it does not open a second walk.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from identify import identify

from ..config import config
from ..emoji_scan import extract as emoji_extract
from ..profanity import scan as profanity_scan
from . import _markers, _tokens
from ._walk import iter_source_files


@dataclass(frozen=True, slots=True)
class SourceScanResult:
    """The subset of ``CodeAnalysis`` fields produced by the walk."""

    loc_total: int
    files_scanned: int
    comment_nloc: int
    comment_to_code_ratio: float | None
    comment_profanity_hits: int
    identifier_profanity_hits: int
    comment_emoji_hits: int
    identifier_emoji_hits: int
    emoji_top: dict[str, int] = field(default_factory=dict)
    tech_debt_markers: int = 0


def scan_source_tree(repo_dir: Path) -> SourceScanResult:
    """Walk ``repo_dir`` once and return every in-line signal."""
    loc_total = 0
    files_scanned = 0
    comment_nloc = 0
    comment_prof = 0
    ident_prof = 0
    comment_emoji_total = 0
    ident_emoji_total = 0
    emoji_counter: Counter[str] = Counter()
    markers_total = 0

    for path in iter_source_files(repo_dir):
        files_scanned += 1
        loc_total += _nonblank_line_count(path)

        tags = identify.tags_from_filename(path.name)
        language = _tokens.resolve_language(tags)
        if language is None:
            continue

        tokens = _tokens.extract(path, language)
        if tokens is None:
            continue

        comment_nloc += tokens.comment_nloc
        markers_total += _markers.count(tokens.comments)

        comment_blob = "\n".join(tokens.comments)
        identifier_blob = "\n".join(tokens.identifiers)

        if comment_blob:
            comment_prof += len(profanity_scan(comment_blob))
            comment_emoji = emoji_extract(comment_blob)
            comment_emoji_total += len(comment_emoji)
            emoji_counter.update(comment_emoji)

        if identifier_blob:
            ident_prof += len(profanity_scan(identifier_blob))
            ident_emoji = emoji_extract(identifier_blob)
            ident_emoji_total += len(ident_emoji)
            emoji_counter.update(ident_emoji)

    ratio: float | None = (
        comment_nloc / loc_total if loc_total > 0 else None
    )
    emoji_top = dict(emoji_counter.most_common(config.emoji_top_n))

    return SourceScanResult(
        loc_total=loc_total,
        files_scanned=files_scanned,
        comment_nloc=comment_nloc,
        comment_to_code_ratio=ratio,
        comment_profanity_hits=comment_prof,
        identifier_profanity_hits=ident_prof,
        comment_emoji_hits=comment_emoji_total,
        identifier_emoji_hits=ident_emoji_total,
        emoji_top=emoji_top,
        tech_debt_markers=markers_total,
    )


def _nonblank_line_count(path: Path) -> int:
    """Count non-blank lines without loading the whole file into memory."""
    count = 0
    try:
        with path.open("rb") as f:
            for line in f:
                if line.strip():
                    count += 1
    except OSError:
        return 0
    return count
