"""Exception vocabulary for the Stage 4 worker.

Separated from the orchestrator so other modules can raise these without
pulling in subprocess / httpx dependencies.
"""

from __future__ import annotations


class SkipRepo(Exception):
    """Raised when a repo should not be deep-analysed.

    The string argument becomes the ``"skip: <reason>"`` suffix written
    to ``repos.failure_reason`` and histogrammed by IP-008.
    """


class RepoTimeout(Exception):
    """Raised when the outer 10-minute envelope fires via SIGALRM."""


class GitError(Exception):
    """Raised when a git subprocess returns a non-zero exit code.

    The string argument carries the captured stderr tail for logging.
    """
