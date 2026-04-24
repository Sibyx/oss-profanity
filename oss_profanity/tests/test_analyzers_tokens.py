"""Tree-sitter-backed comment + identifier extraction."""

from __future__ import annotations

from pathlib import Path

from oss_profanity.analyzers._tokens import (
    ExtractedTokens,
    extract,
    resolve_language,
)


def test_python_docstring_is_recognized_as_code_not_comment(
    tmp_path: Path,
) -> None:
    """Triple-quoted strings are NOT comment nodes in tree-sitter's
    Python grammar — they are strings used as docstrings. Regex would
    fail this test; AST-level extraction gets it right."""
    src = '''"""This is a module docstring."""

# this is a real comment
def foo():
    """Function docstring, also a string."""
    return 1
'''
    p = tmp_path / "a.py"
    p.write_text(src, encoding="utf-8")
    result = extract(p, "python")
    assert result is not None
    # Only the `# this is a real comment` is a comment node.
    assert len(result.comments) == 1
    assert "real comment" in result.comments[0]


def test_js_comment_in_string_literal_is_not_a_comment(
    tmp_path: Path,
) -> None:
    """The core AST-correctness claim from the proposal: regex over
    ``//`` would falsely match inside a string. Tree-sitter does not."""
    src = """const url = "https://example.com/path"; // real
const fake = "// not a comment, just a string";
"""
    p = tmp_path / "a.js"
    p.write_text(src, encoding="utf-8")
    result = extract(p, "javascript")
    assert result is not None
    # Exactly one real comment (the `// real` after the URL).
    assert len(result.comments) == 1
    assert "real" in result.comments[0]


def test_rust_uses_distinct_comment_node_types(tmp_path: Path) -> None:
    src = """// line comment
/* block comment */
fn main() {
    let x = 1;
}
"""
    p = tmp_path / "a.rs"
    p.write_text(src, encoding="utf-8")
    result = extract(p, "rust")
    assert result is not None
    # Both a `line_comment` and a `block_comment` get collected.
    assert len(result.comments) == 2
    assert any("line comment" in c for c in result.comments)
    assert any("block comment" in c for c in result.comments)


def test_identifiers_include_parameters_and_locals(tmp_path: Path) -> None:
    """Proposal invariant: we collect every identifier occurrence, not
    just declared symbols, so emoji-in-identifier occurrence counts are
    accurate (the profanity path dedups, the emoji path doesn't)."""
    src = """def handler(request_id):
    local_var = request_id + 1
    return local_var
"""
    p = tmp_path / "a.py"
    p.write_text(src, encoding="utf-8")
    result = extract(p, "python")
    assert result is not None
    # Expect multiple identifier occurrences: handler, request_id (decl),
    # request_id (use), local_var (decl), local_var (return).
    assert "handler" in result.identifiers
    # request_id appears twice
    assert result.identifiers.count("request_id") >= 2
    # local_var appears twice
    assert result.identifiers.count("local_var") >= 2


def test_comment_nloc_counts_newlines_in_comment_nodes(
    tmp_path: Path,
) -> None:
    src = """# one
# two
def foo():
    return 1  # three
"""
    p = tmp_path / "a.py"
    p.write_text(src, encoding="utf-8")
    result = extract(p, "python")
    assert result is not None
    assert len(result.comments) == 3
    # Each `#` comment spans a single line.
    assert result.comment_nloc == 3


def test_extract_returns_none_on_nonexistent_file(tmp_path: Path) -> None:
    missing = tmp_path / "nope.py"
    assert extract(missing, "python") is None


def test_extract_survives_invalid_utf8(tmp_path: Path) -> None:
    p = tmp_path / "bad.py"
    p.write_bytes(b"# valid\n\xff\xfe garbage\nx = 1\n")
    # Should not crash; tree-sitter tolerates bad bytes, we decode with
    # errors="replace".
    result = extract(p, "python")
    assert result is not None
    # Still finds at least the first valid comment.
    assert any("valid" in c for c in result.comments)


def test_emoji_in_comment_is_extracted(tmp_path: Path) -> None:
    """Emoji in comments is the common case — PEP 3131 actually
    disallows emoji in identifiers (``So`` category), so the interesting
    signal lives in comment text."""
    src = """# 🚀 ship it
def launch():
    return 1
"""
    p = tmp_path / "a.py"
    p.write_text(src, encoding="utf-8")
    result = extract(p, "python")
    assert result is not None
    assert any("🚀" in c for c in result.comments)


def test_cjk_identifier_is_extracted(tmp_path: Path) -> None:
    """PEP 3131 explicitly permits non-ASCII letter categories in
    identifiers. Tree-sitter's Python grammar honors that; our bytes-
    based text reconstruction must survive multi-byte UTF-8."""
    src = """def 計算():
    合計 = 1
    return 合計
"""
    p = tmp_path / "a.py"
    p.write_text(src, encoding="utf-8")
    result = extract(p, "python")
    assert result is not None
    assert "計算" in result.identifiers
    assert "合計" in result.identifiers


def test_resolve_language_maps_identify_tags() -> None:
    assert resolve_language({"python", "file", "text"}) == "python"
    assert resolve_language({"rust", "file"}) == "rust"
    assert resolve_language({"c++", "file"}) == "cpp"
    assert resolve_language({"tsx", "typescript", "file"}) in {"tsx", "typescript"}


def test_resolve_language_returns_none_for_unknown() -> None:
    assert resolve_language({"file", "text", "unknown-xyz"}) is None
    assert resolve_language(set()) is None


def test_extracted_tokens_is_frozen() -> None:
    tok = ExtractedTokens(comments=[], identifiers=[], comment_nloc=0)
    try:
        tok.comment_nloc = 5  # type: ignore[misc]
    except Exception:
        return
    raise AssertionError("ExtractedTokens should be frozen")
