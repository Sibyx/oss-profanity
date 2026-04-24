"""Per-repo pipeline orchestrator (IP-007 `_processor`)."""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from oss_profanity.db import GitHubMetadata, Repo
from oss_profanity.repo_worker import _github, _processor, _scratch
from oss_profanity.repo_worker._errors import GitError


def _make_repo(repo_id: int = 1, full_name: str = "alice/widget") -> Repo:
    return Repo.model_validate(
        {
            "_id": repo_id,
            "full_name": full_name,
            "first_seen_at": datetime.now(timezone.utc),
            "claimed_by": "worker-1-abcd",
            "status": "claimed",
        }
    )


def _patch_scratch_dir(
    monkeypatch: pytest.MonkeyPatch, tmp: Path
) -> None:
    new_config = dataclasses.replace(_scratch.config, scratch_dir=str(tmp))
    monkeypatch.setattr(_scratch, "config", new_config)
    monkeypatch.setattr(_processor, "config", new_config)


def _stub_mark_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[int, str]]:
    """Collect (repo_id, reason) tuples instead of hitting Mongo."""
    collected: list[tuple[int, str]] = []

    def fake(
        repo_id: int, reason: str, elapsed_sec: float | None = None
    ) -> None:
        collected.append((repo_id, reason))

    monkeypatch.setattr(_processor, "mark_failed", fake)
    return collected


def _stub_cas_set(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[int, str, dict[str, Any]]]:
    """Collect (repo_id, worker_id, fields) tuples for every CAS write."""
    collected: list[tuple[int, str, dict[str, Any]]] = []

    def fake(repo_id: int, worker_id: str, fields: dict[str, Any]) -> bool:
        collected.append((repo_id, worker_id, dict(fields)))
        return True

    monkeypatch.setattr(_processor, "_cas_set", fake)
    return collected


def _metadata(
    *,
    size_kb: int = 100,
    archived: bool = False,
    disabled: bool = False,
) -> GitHubMetadata:
    return GitHubMetadata(
        fetched_at=datetime.now(timezone.utc),
        size_kb=size_kb,
        archived=archived,
        disabled=disabled,
    )


# ---------- happy path ----------


def test_happy_path_writes_metadata_and_mark_done(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_scratch_dir(monkeypatch, tmp_path)
    cas = _stub_cas_set(monkeypatch)
    failed = _stub_mark_failed(monkeypatch)

    monkeypatch.setattr(
        _github, "fetch_metadata", lambda _n: _metadata(size_kb=100)
    )
    monkeypatch.setattr(
        _github, "fetch_languages", lambda _n: {"Python": 1234}
    )
    monkeypatch.setattr(
        _processor._git, "partial_clone", lambda *a, **k: None
    )
    monkeypatch.setattr(
        _processor._git, "resolve_sha_before", lambda *a, **k: "abc1234"
    )
    monkeypatch.setattr(_processor._git, "checkout", lambda *a, **k: None)
    monkeypatch.setattr(
        _processor.analyzers, "detect_primary_language", lambda _d: "python"
    )
    monkeypatch.setattr(
        _processor.analyzers,
        "run_all",
        lambda _d, _l: {"loc_total": 123, "files_scanned": 5},
    )

    _processor.process_one(_make_repo(), "worker-1-abcd")

    assert failed == []
    # First write: github_metadata (incl. merged languages). Second: status=done.
    assert len(cas) == 2
    assert "github_metadata" in cas[0][2]
    assert cas[0][2]["github_metadata"]["languages_bytes"] == {"Python": 1234}
    assert cas[1][2]["status"] == "done"
    assert cas[1][2]["primary_language"] == "python"
    assert cas[1][2]["code_analysis"]["loc_total"] == 123
    assert "processing_time_sec" in cas[1][2]


# ---------- skip branches ----------


def test_archived_repo_short_circuits_before_clone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_scratch_dir(monkeypatch, tmp_path)
    _stub_cas_set(monkeypatch)
    failed = _stub_mark_failed(monkeypatch)
    clone_calls: list[Any] = []

    monkeypatch.setattr(
        _github, "fetch_metadata", lambda _n: _metadata(archived=True)
    )
    monkeypatch.setattr(_github, "fetch_languages", lambda _n: {})
    monkeypatch.setattr(
        _processor._git,
        "partial_clone",
        lambda *a, **k: clone_calls.append(a),
    )

    _processor.process_one(_make_repo(), "worker-1-abcd")

    assert clone_calls == []
    assert failed == [(1, "skip: archived")]


def test_disabled_repo_short_circuits_before_clone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_scratch_dir(monkeypatch, tmp_path)
    _stub_cas_set(monkeypatch)
    failed = _stub_mark_failed(monkeypatch)

    monkeypatch.setattr(
        _github, "fetch_metadata", lambda _n: _metadata(disabled=True)
    )
    monkeypatch.setattr(_github, "fetch_languages", lambda _n: {})

    _processor.process_one(_make_repo(), "worker-1-abcd")

    assert failed == [(1, "skip: disabled")]


def test_oversize_repo_short_circuits_before_clone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_scratch_dir(monkeypatch, tmp_path)
    _stub_cas_set(monkeypatch)
    failed = _stub_mark_failed(monkeypatch)

    # Config default max_repo_size_mb = 2048; we exceed it.
    monkeypatch.setattr(
        _github, "fetch_metadata", lambda _n: _metadata(size_kb=3_000_000)
    )
    monkeypatch.setattr(_github, "fetch_languages", lambda _n: {})

    _processor.process_one(_make_repo(), "worker-1-abcd")

    assert len(failed) == 1
    assert failed[0][0] == 1
    assert failed[0][1].startswith("skip: oversize")


def test_no_commits_in_window_skip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_scratch_dir(monkeypatch, tmp_path)
    _stub_cas_set(monkeypatch)
    failed = _stub_mark_failed(monkeypatch)

    monkeypatch.setattr(_github, "fetch_metadata", lambda _n: _metadata())
    monkeypatch.setattr(_github, "fetch_languages", lambda _n: {})
    monkeypatch.setattr(
        _processor._git, "partial_clone", lambda *a, **k: None
    )
    # Empty stdout → None → SkipRepo
    monkeypatch.setattr(
        _processor._git, "resolve_sha_before", lambda *a, **k: None
    )

    _processor.process_one(_make_repo(), "worker-1-abcd")

    assert failed == [(1, "skip: no commits in window")]


# ---------- error branches ----------


def test_git_error_classified_as_git(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_scratch_dir(monkeypatch, tmp_path)
    _stub_cas_set(monkeypatch)
    failed = _stub_mark_failed(monkeypatch)

    monkeypatch.setattr(_github, "fetch_metadata", lambda _n: _metadata())
    monkeypatch.setattr(_github, "fetch_languages", lambda _n: {})

    def boom(*a: Any, **k: Any) -> None:
        raise GitError("fatal: remote not found")

    monkeypatch.setattr(_processor._git, "partial_clone", boom)

    _processor.process_one(_make_repo(), "worker-1-abcd")

    assert len(failed) == 1
    assert failed[0][1].startswith("git: fatal: remote not found")


def test_unexpected_exception_classified_as_typename(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_scratch_dir(monkeypatch, tmp_path)
    _stub_cas_set(monkeypatch)
    failed = _stub_mark_failed(monkeypatch)

    monkeypatch.setattr(_github, "fetch_metadata", lambda _n: _metadata())
    monkeypatch.setattr(_github, "fetch_languages", lambda _n: {})
    monkeypatch.setattr(
        _processor._git, "partial_clone", lambda *a, **k: None
    )
    monkeypatch.setattr(
        _processor._git, "resolve_sha_before", lambda *a, **k: "abc"
    )
    monkeypatch.setattr(_processor._git, "checkout", lambda *a, **k: None)
    monkeypatch.setattr(
        _processor.analyzers,
        "detect_primary_language",
        lambda _d: "python",
    )

    def boom(*a: Any, **k: Any) -> None:
        raise RuntimeError("analyzer exploded")

    monkeypatch.setattr(_processor.analyzers, "run_all", boom)

    _processor.process_one(_make_repo(), "worker-1-abcd")

    assert len(failed) == 1
    assert failed[0][1].startswith("RuntimeError: analyzer exploded")


def test_metadata_none_proceeds_with_clone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Best-effort metadata: an API error still lets the clone path run."""
    _patch_scratch_dir(monkeypatch, tmp_path)
    cas = _stub_cas_set(monkeypatch)
    failed = _stub_mark_failed(monkeypatch)

    monkeypatch.setattr(_github, "fetch_metadata", lambda _n: None)
    monkeypatch.setattr(_github, "fetch_languages", lambda _n: None)
    monkeypatch.setattr(
        _processor._git, "partial_clone", lambda *a, **k: None
    )
    monkeypatch.setattr(
        _processor._git, "resolve_sha_before", lambda *a, **k: "abc"
    )
    monkeypatch.setattr(_processor._git, "checkout", lambda *a, **k: None)
    monkeypatch.setattr(
        _processor.analyzers,
        "detect_primary_language",
        lambda _d: "python",
    )
    monkeypatch.setattr(
        _processor.analyzers,
        "run_all",
        lambda _d, _l: {"loc_total": 10, "files_scanned": 1},
    )

    _processor.process_one(_make_repo(), "worker-1-abcd")

    assert failed == []
    # Only the mark-done CAS write — no github_metadata write.
    assert len(cas) == 1
    assert cas[0][2]["status"] == "done"
