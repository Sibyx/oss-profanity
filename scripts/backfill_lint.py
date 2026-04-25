"""Backfill the ESLint and ruff schema upgrades shipped by IP-013.

Two targets, one script:

    python -m scripts.backfill_lint --target=eslint
        Iterate ``status="done"`` JS/TS repos with ``eslint_issues=null``,
        re-clone, run ``_eslint.run``, write the six-field ESLint family
        plus ``_per_kloc`` siblings.

    python -m scripts.backfill_lint --target=ruff_fixable
        Iterate ``status="done"`` Python repos missing
        ``ruff_fixable``, re-clone, run ``_ruff.run``, write
        ``ruff_fixable`` + ``ruff_fixable_per_kloc``.

Idempotent: each target's filter excludes already-populated docs, so a
re-run resumes after a crash. Reuses the existing ``_git`` partial-clone
helpers and the IP-007 scratch-dir convention so the backfill behaves
exactly like a worker on the same toolchain.

The IP-008 forest plot wants a fully-populated ESLint column on the
canonical 1 295-repo cohort and a fully-populated ``ruff_fixable``
column for the Python subset; running this script with both targets
delivers both.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Any

from pymongo.database import Database

from oss_profanity.analyzers import _eslint, _ruff
from oss_profanity.config import config
from oss_profanity.db import get_db
from oss_profanity.repo_worker import _git, _scratch

logger = logging.getLogger("backfill_lint")

_WORKER_ID = "backfill-lint"
_WINDOW_CUTOFF = "2020-07-01 00:00:00"
_JS_TS_LANGS: frozenset[str] = frozenset(
    {"javascript", "typescript", "jsx", "tsx"}
)


def _eslint_query() -> dict[str, Any]:
    return {
        "status": "done",
        "primary_language": {"$in": list(_JS_TS_LANGS)},
        "code_analysis.eslint_issues": None,
    }


def _ruff_fixable_query() -> dict[str, Any]:
    return {
        "status": "done",
        "primary_language": "python",
        "code_analysis.ruff_fixable": {"$exists": False},
    }


def _per_kloc(count: int | None, loc: int | None) -> float | None:
    if count is None or not loc or loc <= 0:
        return None
    return count / (loc / 1000.0)


def _clone_and_checkout(full_name: str, clone: Path) -> bool:
    """Partial-clone + window-cutoff checkout. Returns True on success."""
    url = f"https://github.com/{full_name}.git"
    timeout = config.git_subprocess_timeout.total_seconds()
    try:
        _git.partial_clone(url, clone, timeout)
        sha = _git.resolve_sha_before(clone, _WINDOW_CUTOFF, timeout)
        if not sha:
            logger.info("skip %s: no commits in window", full_name)
            return False
        _git.checkout(clone, sha, timeout)
        return True
    except Exception as exc:  # noqa: BLE001 — backfill must not crash on one repo
        logger.warning("clone failed for %s: %s", full_name, exc)
        return False


def _backfill_eslint_one(
    db: Database[dict[str, Any]], doc: dict[str, Any]
) -> bool:
    repo_id = doc["_id"]
    full_name = doc["full_name"]
    clone = _scratch.clone_path(repo_id, _WORKER_ID)
    try:
        if not _clone_and_checkout(full_name, clone):
            return False
        result = _eslint.run(clone)
        if result.total is None:
            logger.warning("eslint returned all-None for %s", full_name)
            return False
        loc = (doc.get("code_analysis") or {}).get("loc_total")
        update = {
            "code_analysis.eslint_issues": result.total,
            "code_analysis.eslint_errors": result.errors,
            "code_analysis.eslint_warnings": result.warnings,
            "code_analysis.eslint_fatal_errors": result.fatal_errors,
            "code_analysis.eslint_fixable_errors": result.fixable_errors,
            "code_analysis.eslint_fixable_warnings": result.fixable_warnings,
            "code_analysis.eslint_issues_per_kloc": _per_kloc(result.total, loc),
            "code_analysis.eslint_errors_per_kloc": _per_kloc(result.errors, loc),
            "code_analysis.eslint_warnings_per_kloc": _per_kloc(
                result.warnings, loc
            ),
            "code_analysis.eslint_fixable_errors_per_kloc": _per_kloc(
                result.fixable_errors, loc
            ),
            "code_analysis.eslint_fixable_warnings_per_kloc": _per_kloc(
                result.fixable_warnings, loc
            ),
        }
        db.repos.update_one({"_id": repo_id}, {"$set": update})
        return True
    finally:
        if config.cleanup_after_repo:
            _scratch.cleanup(clone)


def _backfill_ruff_fixable_one(
    db: Database[dict[str, Any]], doc: dict[str, Any]
) -> bool:
    repo_id = doc["_id"]
    full_name = doc["full_name"]
    clone = _scratch.clone_path(repo_id, _WORKER_ID)
    try:
        if not _clone_and_checkout(full_name, clone):
            return False
        result = _ruff.run(clone)
        if result.fixable is None:
            logger.warning("ruff returned all-None for %s", full_name)
            return False
        loc = (doc.get("code_analysis") or {}).get("loc_total")
        update = {
            "code_analysis.ruff_fixable": result.fixable,
            "code_analysis.ruff_fixable_per_kloc": _per_kloc(
                result.fixable, loc
            ),
        }
        db.repos.update_one({"_id": repo_id}, {"$set": update})
        return True
    finally:
        if config.cleanup_after_repo:
            _scratch.cleanup(clone)


def _run(
    db: Database[dict[str, Any]],
    target: str,
    limit: int | None,
) -> tuple[int, int]:
    if target == "eslint":
        query = _eslint_query()
        worker = _backfill_eslint_one
    elif target == "ruff_fixable":
        query = _ruff_fixable_query()
        worker = _backfill_ruff_fixable_one
    else:
        raise ValueError(f"unknown target: {target}")

    todo = list(
        db.repos.find(
            query,
            projection={
                "_id": 1,
                "full_name": 1,
                "code_analysis.loc_total": 1,
            },
        )
    )
    if limit is not None:
        todo = todo[:limit]

    total = len(todo)
    logger.info("backfill %s: %d repos to process", target, total)
    if total == 0:
        return (0, 0)

    ok = 0
    miss = 0
    start_t = time.monotonic()
    try:
        for i, doc in enumerate(todo, 1):
            if worker(db, doc):
                ok += 1
            else:
                miss += 1
            if i % 25 == 0 or i == total:
                rate = i / max(time.monotonic() - start_t, 1e-9)
                logger.info(
                    "backfill %s %d/%d  (%.1f repos/min; %d ok, %d miss)",
                    target,
                    i,
                    total,
                    rate * 60.0,
                    ok,
                    miss,
                )
    except KeyboardInterrupt:
        logger.warning("backfill: interrupted; progress saved — rerun to resume")
    return (ok, miss)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill ESLint or ruff_fixable on the cohort (IP-013)"
    )
    parser.add_argument(
        "--target",
        choices=["eslint", "ruff_fixable"],
        required=True,
        help="Which schema upgrade to backfill",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process at most N repos (smoke check)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    db = get_db()
    ok, miss = _run(db, args.target, args.limit)
    logger.info("backfill %s: done — %d ok, %d miss", args.target, ok, miss)
    return 0


if __name__ == "__main__":
    sys.exit(main())
