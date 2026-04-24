"""Tree-sitter-backed comment + identifier extraction.

One parse per file via ``_native.parse_string`` (the tree-sitter-
language-pack 1.6.2 Rust/PyO3 binding, imported from the package's
``_native`` submodule). From the resulting tree we pull:

- **Comment nodes** — node-type names vary per grammar (Rust uses
  ``line_comment`` / ``block_comment``, most others use ``comment``).
  We keep a small per-language override map; unknowns default to
  ``('comment',)``.
- **Identifier nodes** — most grammars use ``identifier``; Haskell is
  the notable exception (``variable``). We collect *every* occurrence,
  not just declarations, so emoji-in-identifier occurrence counts stay
  accurate (the profanity path dedups, but the emoji path doesn't).

Text is reconstructed by slicing the UTF-8 encoded source bytes on each
node's ``start_byte`` / ``end_byte`` — tree-sitter is UTF-8 native, so
``errors="replace"`` on decode handles pathological files without
crashing the walk.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from tree_sitter_language_pack import _native  # type: ignore[attr-defined]

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ExtractedTokens:
    """Comments + identifiers pulled from one file."""

    comments: list[str]
    identifiers: list[str]
    comment_nloc: int


# identify-tag → tree-sitter-language-pack language name. Keys are the
# subset of tags that the language pack provides grammars for *and* that
# appear in :data:`_language._LANGUAGE_TAGS`.
_LANGUAGE_TAG_TO_TS: Final[dict[str, str]] = {
    "python": "python",
    "javascript": "javascript",
    "typescript": "typescript",
    "jsx": "javascript",
    "tsx": "tsx",
    "go": "go",
    "rust": "rust",
    "ruby": "ruby",
    "java": "java",
    "kotlin": "kotlin",
    "scala": "scala",
    "swift": "swift",
    "c": "c",
    "c++": "cpp",
    "c#": "csharp",
    "php": "php",
    "shell": "bash",
    "bash": "bash",
    "lua": "lua",
    "r": "r",
    "perl": "perl",
    "haskell": "haskell",
    "ocaml": "ocaml",
    "elixir": "elixir",
    "erlang": "erlang",
    "dart": "dart",
    "julia": "julia",
    "groovy": "groovy",
    "objective-c": "objc",
    "clojure": "clojure",
    "css": "css",
    "html": "html",
    "json": "json",
    "yaml": "yaml",
    "toml": "toml",
    "markdown": "markdown",
    "sql": "sql",
}

_COMMENT_NODE_TYPES: Final[dict[str, tuple[str, ...]]] = {
    "rust": ("line_comment", "block_comment"),
}
_DEFAULT_COMMENT_NODE_TYPES: Final[tuple[str, ...]] = ("comment",)

_IDENTIFIER_NODE_TYPES: Final[dict[str, tuple[str, ...]]] = {
    "haskell": ("variable",),
}
_DEFAULT_IDENTIFIER_NODE_TYPES: Final[tuple[str, ...]] = ("identifier",)


def resolve_language(identify_tags: frozenset[str] | set[str]) -> str | None:
    """Return the tree-sitter language name for a file's ``identify`` tags.

    ``None`` if no tag maps into the language pack — the file still
    counts toward ``files_scanned`` / ``loc_total`` but contributes no
    comment/identifier signal.
    """
    for tag in identify_tags:
        if tag in _LANGUAGE_TAG_TO_TS:
            return _LANGUAGE_TAG_TO_TS[tag]
    return None


def extract(path: Path, language: str) -> ExtractedTokens | None:
    """Parse ``path`` as ``language``; return extracted tokens or ``None``.

    ``None`` signals the file could not be read or the grammar is
    unavailable — the caller records it as scanned-but-empty.
    """
    try:
        raw_bytes = path.read_bytes()
    except OSError as exc:
        logger.debug("_tokens.extract: unreadable %s (%s)", path, exc)
        return None

    source_str = raw_bytes.decode("utf-8", errors="replace")
    source_bytes = source_str.encode("utf-8")

    try:
        tree = _native.parse_string(language, source_str)
    except Exception as exc:  # noqa: BLE001 — native parser errors vary
        logger.debug(
            "_tokens.extract: parse failed for %s as %s (%s)",
            path,
            language,
            exc,
        )
        return None

    comment_types = _COMMENT_NODE_TYPES.get(
        language, _DEFAULT_COMMENT_NODE_TYPES
    )
    identifier_types = _IDENTIFIER_NODE_TYPES.get(
        language, _DEFAULT_IDENTIFIER_NODE_TYPES
    )

    comment_nodes = _collect_nodes(tree, comment_types)
    identifier_nodes = _collect_nodes(tree, identifier_types)

    comments = [_node_text(n, source_bytes) for n in comment_nodes]
    identifiers = [_node_text(n, source_bytes) for n in identifier_nodes]
    comment_nloc = sum(
        (n["end_row"] - n["start_row"] + 1) for n in comment_nodes
    )

    return ExtractedTokens(
        comments=comments,
        identifiers=identifiers,
        comment_nloc=comment_nloc,
    )


def _collect_nodes(tree: Any, types: tuple[str, ...]) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    for t in types:
        nodes.extend(tree.find_nodes_by_type(t))
    return nodes


def _node_text(node: dict[str, Any], source_bytes: bytes) -> str:
    return source_bytes[node["start_byte"] : node["end_byte"]].decode(
        "utf-8", errors="replace"
    )
