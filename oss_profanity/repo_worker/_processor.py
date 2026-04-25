"""Per-repo pipeline orchestrator (IP-007).

Given a claimed :class:`Repo`, :func:`process_one` drives the full
pipeline inside a SIGALRM envelope:

1. Fetch GitHub metadata + languages; merge into a single CAS ``$set``
   so archived / disabled / oversize repos still carry their metadata
   into IP-008.
2. Short-circuit on archived / disabled / oversize flags.
3. Partial-clone → resolve SHA before 2020-07-01 → checkout.
4. Run IP-004's language detection + ``run_all``.
5. CAS mark-done with the analysis dict + timing.

Any exception is classified and routed to :func:`db.mark_failed` with a
stable reason prefix IP-008 histograms on.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from .. import analyzers
from ..config import config
from ..db import Repo, get_db, mark_failed
from ._errors import GitError, RepoTimeout, SkipRepo
from . import _git, _github, _scratch, _timeout

logger = logging.getLogger(__name__)

_FAILURE_DETAIL_MAX_CHARS = 200
_WINDOW_CUTOFF = "2020-07-01 00:00:00"


def process_one(repo: Repo, worker_id: str) -> None:
    """Run the full pipeline for one repo. Never raises."""
    start = time.monotonic()
    clone = _scratch.clone_path(repo.id, worker_id)
    try:
        with _timeout.envelope(config.per_repo_timeout.total_seconds()):
            _pipeline(repo, worker_id, clone, start)
    except RepoTimeout:
        mark_failed(
            repo.id, "timeout", elapsed_sec=time.monotonic() - start
        )
        logger.warning("process: timeout on repo %d", repo.id)
    except SkipRepo as exc:
        mark_failed(
            repo.id,
            f"skip: {exc}",
            elapsed_sec=time.monotonic() - start,
        )
        logger.info("process: skip repo %d (%s)", repo.id, exc)
    except GitError as exc:
        detail = str(exc)[:_FAILURE_DETAIL_MAX_CHARS]
        mark_failed(
            repo.id,
            f"git: {detail}",
            elapsed_sec=time.monotonic() - start,
        )
        logger.info("process: git error on repo %d (%s)", repo.id, detail)
    except Exception as exc:  # noqa: BLE001 - classifier must catch everything
        detail = str(exc)[:_FAILURE_DETAIL_MAX_CHARS]
        mark_failed(
            repo.id,
            f"{type(exc).__name__}: {detail}",
            elapsed_sec=time.monotonic() - start,
        )
        logger.exception("process: unexpected error on repo %d", repo.id)
    finally:
        if config.cleanup_after_repo:
            _scratch.cleanup(clone)
        else:
            logger.debug(
                "process: leaving clone in place (CLEANUP_AFTER_REPO=false): %s",
                clone,
            )


def _pipeline(
    repo: Repo, worker_id: str, clone: Any, start: float
) -> None:
    """Inner orchestration; raises on any failure for the outer classifier."""
    metadata = _github.fetch_metadata(repo.full_name)
    if metadata is not None:
        languages = _github.fetch_languages(repo.full_name)
        metadata.languages_bytes = languages or {}
        _cas_set(
            repo.id,
            worker_id,
            {"github_metadata": metadata.model_dump(mode="json")},
        )
        if metadata.archived:
            raise SkipRepo("archived")
        if metadata.disabled:
            raise SkipRepo("disabled")
        if metadata.size_kb > config.max_repo_size_mb * 1024:
            raise SkipRepo(f"oversize: {metadata.size_kb // 1024} MiB")

    url = f"https://github.com/{repo.full_name}.git"
    git_timeout = config.git_subprocess_timeout.total_seconds()
    _git.partial_clone(url, clone, git_timeout)
    sha = _git.resolve_sha_before(clone, _WINDOW_CUTOFF, git_timeout)
    if not sha:
        raise SkipRepo("no commits in window")
    _git.checkout(clone, sha, git_timeout)

    primary_lang = analyzers.detect_primary_language(clone)
    analysis = analyzers.run_all(clone, primary_lang)
    elapsed = time.monotonic() - start
    _mark_done(repo.id, worker_id, primary_lang, analysis, elapsed)


def _mark_done(
    repo_id: int,
    worker_id: str,
    primary_lang: str | None,
    analysis: dict[str, Any],
    elapsed: float | None,
) -> bool:
    """Compare-and-set writer for the ``status=done`` terminal state."""
    fields: dict[str, Any] = {
        "status": "done",
        "primary_language": primary_lang,
        "code_analysis": analysis,
    }
    if elapsed is not None:
        fields["processing_time_sec"] = elapsed
    return _cas_set(repo_id, worker_id, fields)


def _cas_set(
    repo_id: int, worker_id: str, fields: dict[str, Any]
) -> bool:
    """``update_one`` guarded by ``claimed_by`` match. Returns match status."""
    result = get_db().repos.update_one(
        {"_id": repo_id, "claimed_by": worker_id},
        {"$set": fields},
    )
    if result.matched_count == 0:
        logger.warning(
            "cas miss: repo %d no longer claimed by %s (fields=%s)",
            repo_id,
            worker_id,
            sorted(fields),
        )
        return False
    return True
