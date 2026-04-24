"""Git subprocess layer (IP-007).

Three public functions — ``partial_clone``, ``resolve_sha_before``,
``checkout`` — each wrapping ``subprocess.run`` with a per-call timeout,
``GIT_TERMINAL_PROMPT=0`` so credential prompts cannot hang workers,
and structured error classification on non-zero exit.

On any non-zero exit, :class:`GitError` is raised with the captured
stderr tail. On ``subprocess.TimeoutExpired``, :class:`RepoTimeout` is
raised (covers the rare pathological hang inside git itself). Both
exceptions are caught by ``_processor.process_one``'s classifier and
mapped to the appropriate ``mark_failed`` reason prefix.
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

from ._errors import GitError, RepoTimeout

logger = logging.getLogger(__name__)

_STDERR_TAIL_CHARS = 300


def _run_git(argv: list[str], timeout_sec: float, cwd: Path | None = None) -> str:
    """Run ``git`` with a timeout and credential-prompt disabled.

    Returns ``stdout``. Raises :class:`GitError` on non-zero exit
    (with captured stderr tail), :class:`RepoTimeout` on timeout.
    """
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "/bin/true"}
    try:
        result = subprocess.run(
            argv,
            cwd=str(cwd) if cwd is not None else None,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RepoTimeout(f"git timeout: {' '.join(argv[:3])}") from exc

    if result.returncode != 0:
        tail = (result.stderr or "").strip()[-_STDERR_TAIL_CHARS:]
        raise GitError(tail or f"git failed: {' '.join(argv[:3])}")
    return result.stdout


def partial_clone(url: str, dest: Path, timeout_sec: float) -> None:
    """``git clone --filter=blob:none --no-checkout`` into ``dest``.

    Blobless clone — pulls commit + tree metadata only; the checkout
    step that follows materializes only the blobs reachable from the
    target SHA. Cuts bandwidth by ~10x vs a full clone.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    _run_git(
        [
            "git",
            "clone",
            "--filter=blob:none",
            "--no-checkout",
            url,
            str(dest),
        ],
        timeout_sec=timeout_sec,
    )


def resolve_sha_before(
    repo_dir: Path, cutoff: str, timeout_sec: float
) -> str | None:
    """Return the last commit SHA on ``HEAD`` strictly before ``cutoff``.

    Empty stdout → no commits before the cutoff; caller raises
    :class:`SkipRepo("no commits in window")`.
    """
    stdout = _run_git(
        ["git", "rev-list", "-1", f'--before={cutoff}', "HEAD"],
        timeout_sec=timeout_sec,
        cwd=repo_dir,
    )
    sha = stdout.strip()
    return sha or None


def checkout(repo_dir: Path, sha: str, timeout_sec: float) -> None:
    """Check out ``sha`` in ``repo_dir``; materializes working-tree blobs."""
    _run_git(
        ["git", "checkout", sha],
        timeout_sec=timeout_sec,
        cwd=repo_dir,
    )
