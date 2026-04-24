"""Stage 3 cohort sampling — promote a stratified profane/clean cohort to ``pending``.

One public name, :func:`run`, plus a ``python -m oss_profanity.sampling`` CLI.
The module flips every ``status="seen"`` repo to ``"skipped"``, selects the
top-N profane repos by ``commit_stats.profanity_rate`` descending, bins them
by ``total_commits_in_window`` using the log-spaced breakpoints in
:attr:`Config.sampling_commit_bins`, then draws a clean cohort via per-bin
``$sample`` aggregations to match cohort A's commit-count distribution.
Selected repos land with ``status="pending"`` and a ``cohort`` label so
IP-008 can run the Mann-Whitney U test without reconstructing membership.

All tunables come from :mod:`oss_profanity.config` — no module-level constants
(IP-006 Q6 resolution).
"""

from __future__ import annotations

import argparse
import bisect
import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from pymongo import UpdateOne
from pymongo.database import Database

from .config import config
from .db import get_db

logger = logging.getLogger(__name__)

_BULK_CHUNK = 1000


@dataclass(frozen=True, slots=True)
class _Candidate:
    """Internal result of a selector — the minimum we need to bin + promote."""

    id: int
    commits: int


@dataclass(frozen=True, slots=True)
class _SamplingReport:
    """Per-run summary printed to stdout and returned to callers / tests."""

    default_skipped: int
    profane_selected: int
    clean_selected: int
    bin_histogram: dict[int, tuple[int, int]] = field(default_factory=dict)
    shortfalls: dict[int, int] = field(default_factory=dict)
    total_promoted: int = 0


# ---------- pure helpers ----------


def _bin_candidates(
    candidates: Iterable[_Candidate], bins: Sequence[int]
) -> dict[int, list[_Candidate]]:
    """Bucket candidates by ``commits`` against ``bins`` left-closed intervals.

    ``bins = (20, 50, 200, 1000)`` produces buckets keyed by low-bound:
    ``{20: [20..49], 50: [50..199], 200: [200..999], 1000: [1000..∞]}``.
    Candidates with ``commits < bins[0]`` are dropped — they fail ``MIN_COMMITS``
    upstream and should never reach this helper, but we drop defensively.
    """
    bucketed: dict[int, list[_Candidate]] = {lo: [] for lo in bins}
    for cand in candidates:
        idx = bisect.bisect_right(bins, cand.commits) - 1
        if idx < 0:
            continue
        bucketed[bins[idx]].append(cand)
    return bucketed


def _bin_range(bins: Sequence[int], low: int) -> tuple[int, int | None]:
    """Return ``(low, high_exclusive)`` for a bin keyed by ``low``.

    The last bin is unbounded above; ``high`` is ``None`` to signal "no $lt".
    """
    idx = bins.index(low)
    if idx == len(bins) - 1:
        return (low, None)
    return (low, bins[idx + 1])


# ---------- selectors ----------


def _default_skip(db: Database[dict[str, Any]]) -> int:
    """Flip every ``status="seen"`` repo to ``"skipped"``; returns modified count."""
    result = db.repos.update_many(
        {"status": "seen"}, {"$set": {"status": "skipped"}}
    )
    return int(result.modified_count)


def _select_profane(
    db: Database[dict[str, Any]], n: int
) -> list[_Candidate]:
    """Top-``n`` repos by ``profanity_rate`` desc among eligible candidates."""
    cursor = (
        db.repos.find(
            {
                "status": {"$in": ["skipped", "seen"]},
                "commit_stats.total_commits_in_window": {
                    "$gte": config.sampling_min_commits
                },
                "commit_stats.profanity_hits": {"$gte": 1},
            },
            projection={
                "_id": 1,
                "commit_stats.total_commits_in_window": 1,
            },
        )
        .sort([("commit_stats.profanity_rate", -1)])
        .limit(n)
    )
    return [
        _Candidate(
            id=doc["_id"],
            commits=int(
                doc["commit_stats"]["total_commits_in_window"]
            ),
        )
        for doc in cursor
    ]


def _select_clean_matched(
    db: Database[dict[str, Any]],
    bin_counts: dict[int, int],
    bins: Sequence[int],
) -> tuple[list[_Candidate], dict[int, int]]:
    """Draw clean repos per bin to match ``bin_counts``; record shortfalls.

    One ``$sample`` aggregation per bin against the ``profanity_hits == 0``
    predicate plus the bin's commit-count range. Never cross-draws: if a bin
    runs dry, the shortfall is recorded and logged; cohort A is *not* trimmed
    here (the paired test in IP-008 uses actual promoted sizes).
    """
    chosen: list[_Candidate] = []
    shortfalls: dict[int, int] = {}
    for bin_low, target in bin_counts.items():
        if target <= 0:
            continue
        low, high = _bin_range(bins, bin_low)
        commits_range: dict[str, int] = {"$gte": low}
        if high is not None:
            commits_range["$lt"] = high
        pipeline: list[dict[str, Any]] = [
            {
                "$match": {
                    "status": {"$in": ["skipped", "seen"]},
                    "commit_stats.profanity_hits": 0,
                    "commit_stats.total_commits_in_window": commits_range,
                }
            },
            {"$sample": {"size": target}},
            {
                "$project": {
                    "_id": 1,
                    "commit_stats.total_commits_in_window": 1,
                }
            },
        ]
        drawn = list(db.repos.aggregate(pipeline))
        for doc in drawn:
            chosen.append(
                _Candidate(
                    id=doc["_id"],
                    commits=int(
                        doc["commit_stats"]["total_commits_in_window"]
                    ),
                )
            )
        actual = len(drawn)
        if actual < target:
            gap = target - actual
            shortfalls[bin_low] = gap
            logger.warning(
                "sampling: clean bin [%d, %s) short by %d (wanted %d, got %d)",
                low,
                "∞" if high is None else str(high),
                gap,
                target,
                actual,
            )
    return chosen, shortfalls


# ---------- promotion ----------


def _promote(
    db: Database[dict[str, Any]],
    profane: Sequence[_Candidate],
    clean: Sequence[_Candidate],
) -> int:
    """Stamp ``status="pending"`` + ``cohort`` on both cohorts; returns modified count.

    One ``bulk_write(ordered=False)`` call; PyMongo auto-splits at its internal
    48 MB / 100K-op caps, but we also chunk at ``_BULK_CHUNK`` (1,000) to match
    IP-005's precedent and keep per-batch log lines readable.
    """
    ops: list[UpdateOne] = []
    for cand in profane:
        ops.append(
            UpdateOne(
                {"_id": cand.id},
                {"$set": {"status": "pending", "cohort": "profane"}},
            )
        )
    for cand in clean:
        ops.append(
            UpdateOne(
                {"_id": cand.id},
                {"$set": {"status": "pending", "cohort": "clean"}},
            )
        )
    if not ops:
        return 0

    modified = 0
    for start in range(0, len(ops), _BULK_CHUNK):
        chunk = ops[start : start + _BULK_CHUNK]
        result = db.repos.bulk_write(chunk, ordered=False)
        modified += int(result.modified_count)
    return modified


# ---------- reporting ----------


def _build_histogram(
    profane: Sequence[_Candidate],
    clean: Sequence[_Candidate],
    bins: Sequence[int],
) -> dict[int, tuple[int, int]]:
    binned_a = _bin_candidates(profane, bins)
    binned_b = _bin_candidates(clean, bins)
    return {
        lo: (len(binned_a[lo]), len(binned_b[lo])) for lo in bins
    }


def _log_report(report: _SamplingReport, bins: Sequence[int]) -> None:
    logger.info("sampling: default_skipped  = %d", report.default_skipped)
    logger.info("sampling: profane_selected = %d", report.profane_selected)
    logger.info("sampling: clean_selected   = %d", report.clean_selected)
    for lo in bins:
        a, b = report.bin_histogram.get(lo, (0, 0))
        _, high = _bin_range(bins, lo)
        high_str = "∞" if high is None else str(high)
        shortfall = report.shortfalls.get(lo, 0)
        logger.info(
            "sampling: bin [%d, %s)  profane=%d clean=%d  shortfall=%d",
            lo,
            high_str,
            a,
            b,
            shortfall,
        )
    logger.info("sampling: total_promoted   = %d", report.total_promoted)


# ---------- public entrypoint ----------


def run(
    db: Database[dict[str, Any]] | None = None,
    *,
    profane_n: int | None = None,
    clean_n: int | None = None,
) -> _SamplingReport:
    """Run the full sampling pipeline and return a typed report.

    Pass ``db`` to inject a test database; production call sites rely on the
    ``get_db()`` default. ``profane_n`` / ``clean_n`` override the config
    cohort sizes — top-up mode uses this to draw only the shortfall.

    Safe to re-run: every selector narrows to ``status in ["seen", "skipped"]``
    so previously-promoted repos are invisible.
    """
    db = db if db is not None else get_db()
    bins = config.sampling_commit_bins
    profane_target = (
        profane_n if profane_n is not None else config.profane_cohort_size
    )
    clean_target = (
        clean_n if clean_n is not None else config.clean_cohort_size
    )

    default_skipped = _default_skip(db)

    profane = _select_profane(db, profane_target)

    binned_a = _bin_candidates(profane, bins)
    # Cap cohort B's target at ``clean_target`` proportional to A's bin shape.
    # In the common case (CLEAN = PROFANE) the per-bin target equals
    # len(binned_a[bin]); if the operator deliberately skews (e.g. CLEAN = 500
    # with PROFANE = 750), scale each bin's target down proportionally.
    profane_total = sum(len(v) for v in binned_a.values())
    bin_counts: dict[int, int] = {}
    if profane_total == 0:
        bin_counts = {lo: 0 for lo in bins}
    elif clean_target == profane_total:
        bin_counts = {lo: len(binned_a[lo]) for lo in bins}
    else:
        scale = clean_target / profane_total
        raw = {lo: int(round(len(binned_a[lo]) * scale)) for lo in bins}
        # Repair rounding drift so totals match exactly.
        drift = clean_target - sum(raw.values())
        if drift != 0:
            biggest_bin = max(bins, key=lambda lo: len(binned_a[lo]))
            raw[biggest_bin] += drift
        bin_counts = raw

    clean, shortfalls = _select_clean_matched(db, bin_counts, bins)

    promoted = _promote(db, profane, clean)

    histogram = _build_histogram(profane, clean, bins)
    report = _SamplingReport(
        default_skipped=default_skipped,
        profane_selected=len(profane),
        clean_selected=len(clean),
        bin_histogram=histogram,
        shortfalls=shortfalls,
        total_promoted=promoted,
    )
    _log_report(report, bins)
    if report.profane_selected == 0:
        logger.warning(
            "sampling: no profane candidates found — nothing to promote"
        )
    return report


# ---------- top-up ----------


def _demote_missing(
    db: Database[dict[str, Any]],
) -> tuple[int, int]:
    """Flip probe-404 cohort repos from pending/claimed/failed to ``missing``.

    The probe script tags repos GitHub returned 404 on with
    ``github_metadata_probe_missing_at``. Those stay in the cohort for
    bookkeeping but must not block Stage 4 — this helper moves them out of
    the claimable queue.

    Returns ``(profane_demoted, clean_demoted)``.
    """
    query_profane: dict[str, Any] = {
        "cohort": "profane",
        "status": {"$in": ["pending", "claimed", "failed"]},
        "github_metadata_probe_missing_at": {"$exists": True},
    }
    query_clean: dict[str, Any] = {
        "cohort": "clean",
        "status": {"$in": ["pending", "claimed", "failed"]},
        "github_metadata_probe_missing_at": {"$exists": True},
    }
    update: dict[str, Any] = {
        "$set": {"status": "missing"},
        "$unset": {"claimed_by": "", "claimed_at": ""},
    }
    profane_result = db.repos.update_many(query_profane, update)
    clean_result = db.repos.update_many(query_clean, update)
    return (int(profane_result.modified_count), int(clean_result.modified_count))


def _live_cohort_counts(
    db: Database[dict[str, Any]],
) -> tuple[int, int]:
    """Return ``(profane_live, clean_live)`` — cohort rows still in the pipeline.

    "Live" means any status that still counts toward the cohort target: every
    status except ``missing`` (explicitly excluded) and the un-promoted
    ``seen`` / ``skipped`` pool.
    """
    live_statuses = ["pending", "claimed", "done", "failed"]
    profane = db.repos.count_documents(
        {"cohort": "profane", "status": {"$in": live_statuses}}
    )
    clean = db.repos.count_documents(
        {"cohort": "clean", "status": {"$in": live_statuses}}
    )
    return (int(profane), int(clean))


def run_top_up(
    db: Database[dict[str, Any]] | None = None,
) -> _SamplingReport:
    """Demote probe-404 cohort repos and draw a fresh batch to hit cohort targets.

    Steps:
      1. Move probe-404 cohort repos to ``status="missing"``.
      2. Count live cohort survivors per side.
      3. Run :func:`run` with ``profane_n`` / ``clean_n`` set to the shortfall
         against ``config.profane_cohort_size`` / ``config.clean_cohort_size``.

    No-op when both cohorts are already at target.
    """
    db = db if db is not None else get_db()

    profane_demoted, clean_demoted = _demote_missing(db)
    logger.info(
        "top-up: demoted %d profane + %d clean probe-404 repos to status=missing",
        profane_demoted,
        clean_demoted,
    )

    profane_live, clean_live = _live_cohort_counts(db)
    profane_gap = max(0, config.profane_cohort_size - profane_live)
    clean_gap = max(0, config.clean_cohort_size - clean_live)
    logger.info(
        "top-up: profane live=%d target=%d gap=%d | clean live=%d target=%d gap=%d",
        profane_live,
        config.profane_cohort_size,
        profane_gap,
        clean_live,
        config.clean_cohort_size,
        clean_gap,
    )
    if profane_gap == 0 and clean_gap == 0:
        logger.info("top-up: cohorts already at target — nothing to draw")
        return _SamplingReport(
            default_skipped=0,
            profane_selected=0,
            clean_selected=0,
        )

    return run(db, profane_n=profane_gap, clean_n=clean_gap)


def _main() -> None:
    parser = argparse.ArgumentParser(
        description="Promote a stratified profane/clean cohort to status=pending"
    )
    parser.add_argument(
        "--top-up",
        action="store_true",
        help=(
            "Demote probe-404 cohort repos to status=missing, then draw only "
            "the shortfall against PROFANE_COHORT_SIZE / CLEAN_COHORT_SIZE"
        ),
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    if args.top_up:
        run_top_up()
    else:
        run()


if __name__ == "__main__":
    _main()
