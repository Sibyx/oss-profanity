"""Exception vocabulary (IP-007 `_errors`)."""

from __future__ import annotations

from oss_profanity.repo_worker._errors import GitError, RepoTimeout, SkipRepo


def test_exceptions_carry_string_reason() -> None:
    assert str(SkipRepo("archived")) == "archived"
    assert str(RepoTimeout("SIGALRM after setitimer")) == "SIGALRM after setitimer"
    assert str(GitError("fatal: not a git repository")) == "fatal: not a git repository"


def test_exceptions_are_distinct_types() -> None:
    assert not issubclass(SkipRepo, RepoTimeout)
    assert not issubclass(SkipRepo, GitError)
    assert not issubclass(RepoTimeout, GitError)
