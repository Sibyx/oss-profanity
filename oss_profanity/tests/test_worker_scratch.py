"""Per-worker scratch directory helpers (IP-007 `_scratch`)."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from oss_profanity.repo_worker import _scratch


def _patch_scratch(monkeypatch: pytest.MonkeyPatch, tmp: Path) -> None:
    """Swap the module-level config reference with a fresh frozen copy."""
    new_config = dataclasses.replace(_scratch.config, scratch_dir=str(tmp))
    monkeypatch.setattr(_scratch, "config", new_config)


def test_clone_path_composes_worker_and_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_scratch(monkeypatch, tmp_path)

    path = _scratch.clone_path(42, "host-123-abcd")

    assert path == tmp_path / "host-123-abcd" / "42"


def test_setup_creates_fresh_per_worker_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_scratch(monkeypatch, tmp_path)

    _scratch.setup("host-123-abcd")

    root = tmp_path / "host-123-abcd"
    assert root.is_dir()


def test_setup_wipes_prior_per_worker_subtree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_scratch(monkeypatch, tmp_path)

    # Seed stale clones as if a prior run had left them.
    stale = tmp_path / "host-123-abcd" / "99"
    stale.mkdir(parents=True)
    (stale / "junk.bin").write_bytes(b"leftover")
    assert stale.exists()

    _scratch.setup("host-123-abcd")

    assert not stale.exists()
    assert (tmp_path / "host-123-abcd").is_dir()


def test_cleanup_is_safe_on_missing_path(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"
    _scratch.cleanup(missing)  # must not raise


def test_cleanup_removes_subtree(tmp_path: Path) -> None:
    target = tmp_path / "cloned-repo"
    (target / "subdir").mkdir(parents=True)
    (target / "subdir" / "file.txt").write_text("content")

    _scratch.cleanup(target)

    assert not target.exists()
