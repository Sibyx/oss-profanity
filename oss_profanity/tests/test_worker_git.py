"""Git subprocess layer (IP-007 `_git`)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from oss_profanity.repo_worker import _git
from oss_profanity.repo_worker._errors import GitError, RepoTimeout


class _FakeCompletedProcess:
    def __init__(
        self, returncode: int = 0, stdout: str = "", stderr: str = ""
    ) -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _stub_run(
    monkeypatch: pytest.MonkeyPatch,
    *,
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
    raises: Exception | None = None,
    seen: list[list[str]] | None = None,
) -> None:
    def fake(argv: list[str], **_: Any) -> _FakeCompletedProcess:
        if seen is not None:
            seen.append(list(argv))
        if raises is not None:
            raise raises
        return _FakeCompletedProcess(
            returncode=returncode, stdout=stdout, stderr=stderr
        )

    monkeypatch.setattr(subprocess, "run", fake)


def test_partial_clone_success_invokes_correct_argv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[list[str]] = []
    _stub_run(monkeypatch, seen=seen)

    dest = tmp_path / "owner-repo"
    _git.partial_clone(
        "https://github.com/owner/repo.git", dest, timeout_sec=300
    )

    assert seen == [
        [
            "git",
            "clone",
            "--filter=blob:none",
            "--no-checkout",
            "https://github.com/owner/repo.git",
            str(dest),
        ]
    ]


def test_partial_clone_nonzero_exit_raises_git_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_run(
        monkeypatch,
        returncode=128,
        stderr="fatal: remote not found",
    )

    dest = tmp_path / "owner-repo"
    with pytest.raises(GitError) as exc:
        _git.partial_clone("https://x/y.git", dest, timeout_sec=300)

    assert "remote not found" in str(exc.value)


def test_partial_clone_timeout_raises_repo_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_run(
        monkeypatch,
        raises=subprocess.TimeoutExpired(cmd=["git"], timeout=1),
    )

    dest = tmp_path / "owner-repo"
    with pytest.raises(RepoTimeout):
        _git.partial_clone("https://x/y.git", dest, timeout_sec=1)


def test_resolve_sha_before_returns_sha(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_run(monkeypatch, stdout="abc1234\n")

    sha = _git.resolve_sha_before(tmp_path, "2020-07-01", 300)

    assert sha == "abc1234"


def test_resolve_sha_before_empty_stdout_returns_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_run(monkeypatch, stdout="")

    sha = _git.resolve_sha_before(tmp_path, "2020-07-01", 300)

    assert sha is None


def test_checkout_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[list[str]] = []
    _stub_run(monkeypatch, seen=seen)

    _git.checkout(tmp_path, "abc1234", timeout_sec=300)

    assert seen == [["git", "checkout", "abc1234"]]


def test_checkout_nonzero_raises_git_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_run(
        monkeypatch,
        returncode=1,
        stderr="error: pathspec 'xyz' did not match any file(s)",
    )

    with pytest.raises(GitError) as exc:
        _git.checkout(tmp_path, "xyz", timeout_sec=300)

    assert "did not match" in str(exc.value)


def test_run_git_disables_terminal_prompt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, Any] = {}

    def fake(argv: list[str], **kwargs: Any) -> _FakeCompletedProcess:
        captured.update(kwargs)
        return _FakeCompletedProcess(returncode=0, stdout="")

    monkeypatch.setattr(subprocess, "run", fake)

    _git.checkout(tmp_path, "abc", timeout_sec=30)

    env = captured.get("env", {})
    assert env.get("GIT_TERMINAL_PROMPT") == "0"
    assert env.get("GIT_ASKPASS") == "/bin/true"
