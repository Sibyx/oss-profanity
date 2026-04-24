"""Single-walk source scan: the DRY contract — one tree-sitter parse
per file feeds profanity + emoji + markers + comment-NLOC."""

from __future__ import annotations

from pathlib import Path

from oss_profanity.analyzers._source_scan import scan_source_tree


def test_scan_empty_repo_returns_zeros(tmp_path: Path) -> None:
    result = scan_source_tree(tmp_path)
    assert result.loc_total == 0
    assert result.files_scanned == 0
    assert result.comment_nloc == 0
    assert result.comment_to_code_ratio is None
    assert result.comment_profanity_hits == 0
    assert result.identifier_profanity_hits == 0
    assert result.comment_emoji_hits == 0
    assert result.identifier_emoji_hits == 0
    assert result.emoji_top == {}
    assert result.tech_debt_markers == 0


def test_dry_contract_one_comment_hits_all_three_signals(
    tmp_path: Path,
) -> None:
    """Load-bearing DRY contract from IP-004: a single comment that
    contains a profane word, an emoji, and a TODO marker increments
    **all three** counters from one walk."""
    src = """# TODO: fuck this 🚀 nonsense
def launch():
    return 1
"""
    (tmp_path / "file.py").write_text(src, encoding="utf-8")

    result = scan_source_tree(tmp_path)

    assert result.files_scanned == 1
    assert result.comment_profanity_hits >= 1
    assert result.comment_emoji_hits >= 1
    assert result.tech_debt_markers == 1
    assert result.emoji_top.get("🚀", 0) >= 1


def test_comment_to_code_ratio_set_when_loc_positive(
    tmp_path: Path,
) -> None:
    src = """# line one
# line two
def f():
    return 1
"""
    (tmp_path / "a.py").write_text(src, encoding="utf-8")
    result = scan_source_tree(tmp_path)
    assert result.loc_total > 0
    assert result.comment_nloc >= 2
    assert result.comment_to_code_ratio is not None
    assert 0 < result.comment_to_code_ratio <= 1


def test_unsupported_language_still_counts_as_scanned(
    tmp_path: Path,
) -> None:
    """A file whose extension has no tree-sitter grammar still
    contributes to files_scanned and loc_total; it just does not emit
    comment/identifier signals. The walker's skip rules are the only
    place a file can fall out of files_scanned."""
    (tmp_path / "weird.xyz").write_text("arbitrary\ntext\nhere\n")
    result = scan_source_tree(tmp_path)
    assert result.files_scanned == 1
    assert result.loc_total > 0
    # No signals — no grammar to extract from.
    assert result.comment_profanity_hits == 0
    assert result.comment_emoji_hits == 0
    assert result.tech_debt_markers == 0


def test_walker_skip_rules_propagate_to_scan(tmp_path: Path) -> None:
    (tmp_path / "real.py").write_text("# 🚀\nx = 1\n")
    skipped = tmp_path / "node_modules"
    skipped.mkdir()
    (skipped / "phantom.py").write_text("# 🐛\ny = 2\n")
    result = scan_source_tree(tmp_path)
    assert result.files_scanned == 1
    # The phantom emoji must not land in the top map.
    assert result.emoji_top.get("🐛", 0) == 0


def test_emoji_top_is_bounded_by_config(
    tmp_path: Path, monkeypatch: __import__("pytest").MonkeyPatch
) -> None:
    from oss_profanity import config as cfg_module

    # Build a file with a lot of distinct emoji.
    glyphs = "🚀🐛✨🔥💥🎉📝🛠️🧪🔧🎯📦"
    lines = [f"# {g}" for g in glyphs]
    (tmp_path / "many.py").write_text(
        "\n".join(lines) + "\nx = 1\n", encoding="utf-8"
    )
    # Shrink the cap.
    object.__setattr__(cfg_module.config, "emoji_top_n", 3)
    try:
        result = scan_source_tree(tmp_path)
    finally:
        object.__setattr__(cfg_module.config, "emoji_top_n", 20)
    assert len(result.emoji_top) == 3


def test_polyglot_repo_collects_from_each_file(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("# py 🚀\nx = 1\n", encoding="utf-8")
    (tmp_path / "b.js").write_text(
        "// js 🐛\nvar y = 2;\n", encoding="utf-8"
    )
    result = scan_source_tree(tmp_path)
    assert result.files_scanned == 2
    assert result.emoji_top.get("🚀", 0) >= 1
    assert result.emoji_top.get("🐛", 0) >= 1
