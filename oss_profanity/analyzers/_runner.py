"""Parallel orchestrator: fan out the walk + every applicable tool.

A small ``ThreadPoolExecutor(max_workers=4)`` dispatches the source walk
and each applicable tool concurrently. Subprocess-backed tools release
the GIL while blocked on I/O, and tree-sitter parsing runs in C (also
GIL-releasing), so threads capture the full parallel benefit without the
fork overhead that ``multiprocessing.Pool`` would add on top of IP-007's
existing 12-worker process pool.

Peak concurrent tasks: 5 for a Python repo (walk + lizard + jscpd + ruff
+ bandit), which the pool serializes the 5th against. Effective peak
depth is 4; ruff almost always finishes first in practice, so queueing
is a non-issue.

Any runner exception lands in ``future.result()`` and is caught here so
one tool's failure never takes down ``run_all`` — the tool's fields
become ``None`` and the rest of the dict still ships.
"""

from __future__ import annotations

import logging
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Any, TypeVar

from . import _bandit, _eslint, _jscpd, _lizard, _ruff, _source_scan

logger = logging.getLogger(__name__)

_PYTHON_TAGS: frozenset[str] = frozenset({"python"})
_JS_TS_TAGS: frozenset[str] = frozenset(
    {"javascript", "typescript", "jsx", "tsx"}
)

_T = TypeVar("_T")


def run_all(repo_dir: Path, primary_lang: str | None) -> dict[str, Any]:
    """Run every applicable analyzer and return the composed ``code_analysis``.

    The returned dict's field names match IP-001's ``CodeAnalysis``
    schema; IP-001's ``extra="allow"`` absorbs the new fields added by
    IP-004. The worker (IP-007) writes the dict directly into
    ``repos.code_analysis``.
    """
    with ThreadPoolExecutor(max_workers=4) as pool:
        walk_fut = pool.submit(_source_scan.scan_source_tree, repo_dir)
        lizard_fut = pool.submit(_lizard.run, repo_dir)
        jscpd_fut = pool.submit(_jscpd.run, repo_dir)

        ruff_fut: Future[_ruff.RuffResult] | None = None
        bandit_fut: Future[_bandit.BanditResult] | None = None
        eslint_fut: Future[_eslint.EslintResult] | None = None

        if primary_lang in _PYTHON_TAGS:
            ruff_fut = pool.submit(_ruff.run, repo_dir)
            bandit_fut = pool.submit(_bandit.run, repo_dir)
        elif primary_lang in _JS_TS_TAGS:
            eslint_fut = pool.submit(_eslint.run, repo_dir)

        source = _resolve(walk_fut, _source_scan.SourceScanResult(
            loc_total=0,
            files_scanned=0,
            comment_nloc=0,
            comment_to_code_ratio=None,
            comment_profanity_hits=0,
            identifier_profanity_hits=0,
            comment_emoji_hits=0,
            identifier_emoji_hits=0,
        ))
        lizard = _resolve(lizard_fut, _lizard.LizardResult())
        jscpd = _resolve(jscpd_fut, _jscpd.JscpdResult())
        ruff = _resolve(ruff_fut, _ruff.RuffResult()) if ruff_fut else _ruff.RuffResult()
        bandit = (
            _resolve(bandit_fut, _bandit.BanditResult())
            if bandit_fut
            else _bandit.BanditResult()
        )
        eslint = (
            _resolve(eslint_fut, _eslint.EslintResult())
            if eslint_fut
            else _eslint.EslintResult()
        )

    return _compose(source, lizard, jscpd, ruff, bandit, eslint)


def _resolve(fut: Future[_T], default: _T) -> _T:
    try:
        return fut.result()
    except Exception:  # noqa: BLE001 — one tool's crash must not sink the rest
        logger.exception("analyzer future raised; recording default result")
        return default


def _per_kloc(count: int | None, loc_total: int) -> float | None:
    if count is None or loc_total <= 0:
        return None
    return count / (loc_total / 1000.0)


def _compose(
    source: _source_scan.SourceScanResult,
    lizard: _lizard.LizardResult,
    jscpd: _jscpd.JscpdResult,
    ruff: _ruff.RuffResult,
    bandit: _bandit.BanditResult,
    eslint: _eslint.EslintResult,
) -> dict[str, Any]:
    loc = source.loc_total
    jscpd_rate: float | None = None
    if jscpd.duplicate_lines is not None and jscpd.total_lines:
        jscpd_rate = jscpd.duplicate_lines / jscpd.total_lines

    return {
        # Source-walk fields (all from one tree-sitter pass).
        "loc_total": source.loc_total,
        "files_scanned": source.files_scanned,
        "comment_nloc": source.comment_nloc,
        "comment_to_code_ratio": source.comment_to_code_ratio,
        "comment_profanity_hits": source.comment_profanity_hits,
        "identifier_profanity_hits": source.identifier_profanity_hits,
        "comment_emoji_hits": source.comment_emoji_hits,
        "identifier_emoji_hits": source.identifier_emoji_hits,
        "emoji_top": source.emoji_top,
        "tech_debt_markers": source.tech_debt_markers,
        # Ruff: sum stays as ``ruff_issues`` for IP-001 back-compat.
        "ruff_issues": ruff.total,
        "ruff_bug_issues": ruff.bug,
        "ruff_style_issues": ruff.style,
        "ruff_fixable": ruff.fixable,
        "ruff_issues_per_kloc": _per_kloc(ruff.total, loc),
        "ruff_bug_issues_per_kloc": _per_kloc(ruff.bug, loc),
        "ruff_style_issues_per_kloc": _per_kloc(ruff.style, loc),
        "ruff_fixable_per_kloc": _per_kloc(ruff.fixable, loc),
        # Bandit.
        "bandit_issues": bandit.total,
        "bandit_high_severity": bandit.high_severity,
        "bandit_issues_per_kloc": _per_kloc(bandit.total, loc),
        # ESLint (IP-013): six-field shape; ``eslint_issues`` kept as
        # ``errors + warnings`` for IP-001 / IP-008 back-compat.
        "eslint_issues": eslint.total,
        "eslint_errors": eslint.errors,
        "eslint_warnings": eslint.warnings,
        "eslint_fatal_errors": eslint.fatal_errors,
        "eslint_fixable_errors": eslint.fixable_errors,
        "eslint_fixable_warnings": eslint.fixable_warnings,
        "eslint_issues_per_kloc": _per_kloc(eslint.total, loc),
        "eslint_errors_per_kloc": _per_kloc(eslint.errors, loc),
        "eslint_warnings_per_kloc": _per_kloc(eslint.warnings, loc),
        "eslint_fixable_errors_per_kloc": _per_kloc(eslint.fixable_errors, loc),
        "eslint_fixable_warnings_per_kloc": _per_kloc(
            eslint.fixable_warnings, loc
        ),
        # jscpd.
        "jscpd_duplicate_lines": jscpd.duplicate_lines,
        "jscpd_total_lines": jscpd.total_lines,
        "jscpd_duplicate_rate": jscpd_rate,
        # Lizard aggregates + percentiles.
        "lizard_avg_ccn": lizard.avg_ccn,
        "lizard_max_ccn": lizard.max_ccn,
        "lizard_functions": lizard.functions,
        "lizard_ccn_p50": lizard.ccn_p50,
        "lizard_ccn_p90": lizard.ccn_p90,
        "lizard_ccn_p99": lizard.ccn_p99,
        "lizard_nloc_p90": lizard.nloc_p90,
    }
