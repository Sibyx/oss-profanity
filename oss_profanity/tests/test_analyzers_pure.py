"""Pure-Python analyzer helpers: walker, marker counter, language histogram."""

from __future__ import annotations

from pathlib import Path

import pytest

from oss_profanity.analyzers import detect_primary_language
from oss_profanity.analyzers._markers import count as markers_count
from oss_profanity.analyzers._walk import iter_source_files


# ---------- _walk ----------


def test_walk_yields_files_in_flat_dir(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("x = 1")
    (tmp_path / "b.js").write_text("var x = 1")
    files = {p.name for p in iter_source_files(tmp_path)}
    assert files == {"a.py", "b.js"}


@pytest.mark.parametrize(
    "skipped_dir",
    [
        "node_modules",
        "vendor",
        ".git",
        "dist",
        "build",
        "__pycache__",
        ".venv",
        "venv",
        ".tox",
        ".mypy_cache",
        ".ruff_cache",
        "target",
    ],
)
def test_walk_skips_blocklisted_directories(
    tmp_path: Path, skipped_dir: str
) -> None:
    (tmp_path / "keep.py").write_text("x = 1")
    nested = tmp_path / skipped_dir
    nested.mkdir()
    (nested / "hidden.py").write_text("x = 2")
    files = {p.name for p in iter_source_files(tmp_path)}
    assert files == {"keep.py"}


@pytest.mark.parametrize(
    "name",
    ["bundle.min.js", "app.bundle.js", "vendor.min.css"],
)
def test_walk_skips_filename_patterns(tmp_path: Path, name: str) -> None:
    (tmp_path / "keep.js").write_text("var x = 1")
    (tmp_path / name).write_text("var x = 1")
    files = {p.name for p in iter_source_files(tmp_path)}
    assert files == {"keep.js"}


def test_walk_skips_files_over_1_mb(tmp_path: Path) -> None:
    (tmp_path / "small.py").write_text("x = 1")
    big = tmp_path / "big.py"
    big.write_bytes(b"x = 1\n" * 200_000)  # ~1.2 MB
    assert big.stat().st_size > 1_048_576
    files = {p.name for p in iter_source_files(tmp_path)}
    assert files == {"small.py"}


def test_walk_handles_empty_directory(tmp_path: Path) -> None:
    assert list(iter_source_files(tmp_path)) == []


# ---------- _markers ----------


def test_markers_counts_all_four() -> None:
    comments = [
        "# TODO: implement this",
        "// FIXME later",
        "/* HACK workaround for bug */",
        "# XXX don't ship",
    ]
    assert markers_count(comments) == 4


def test_markers_case_sensitive_by_design() -> None:
    # Lowercase prose mentions should NOT match.
    assert markers_count(["# this is a todo list entry"]) == 0
    assert markers_count(["# fixme spelled wrong"]) == 0


def test_markers_requires_word_boundaries() -> None:
    assert markers_count(["# TODOS list is long"]) == 0
    assert markers_count(["# FIXMEN is not the word"]) == 0


def test_markers_multiple_in_one_comment() -> None:
    assert markers_count(["# TODO: fix this; XXX also HACK here"]) == 3


def test_markers_empty_input() -> None:
    assert markers_count([]) == 0
    assert markers_count([""]) == 0


# ---------- _language ----------


def test_language_detects_python_majority(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("x = 1")
    (tmp_path / "b.py").write_text("y = 2")
    (tmp_path / "c.js").write_text("var z = 3")
    assert detect_primary_language(tmp_path) == "python"


def test_language_ties_break_alphabetically(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("x = 1")
    (tmp_path / "b.rs").write_text("fn main() {}")
    # python vs rust — alphabetical → python
    assert detect_primary_language(tmp_path) == "python"


def test_language_empty_dir_returns_none(tmp_path: Path) -> None:
    assert detect_primary_language(tmp_path) is None


def test_language_ignores_skipped_dirs(tmp_path: Path) -> None:
    (tmp_path / "real.py").write_text("x = 1")
    nested = tmp_path / "node_modules"
    nested.mkdir()
    (nested / "phantom.js").write_text("var x = 1")
    (nested / "phantom2.js").write_text("var x = 2")
    (nested / "phantom3.js").write_text("var x = 3")
    # If node_modules counted, js would win 3–1; it must not.
    assert detect_primary_language(tmp_path) == "python"


def test_language_non_source_files_dont_vote(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# title")
    (tmp_path / "notes.txt").write_text("hi")
    (tmp_path / "code.py").write_text("x = 1")
    # Only python file votes for a supported language tag we count.
    assert detect_primary_language(tmp_path) == "python"
