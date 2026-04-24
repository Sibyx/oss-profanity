"""One-shot finalizer: compute rates + prune ``emoji_top``.

Runs after every file in the window is ``done``. Iterates the ``repos``
collection, computes ``commit_stats.profanity_rate`` / ``emoji_rate``
from the accumulated totals, and truncates ``commit_stats.emoji_top``
to the top ``emoji_top_n`` entries so per-doc size stays bounded on
heavy-emoji repos.

Idempotent: running twice produces identical field values.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from pymongo import UpdateOne
from pymongo.database import Database

logger = logging.getLogger(__name__)

_BULK_CHUNK = 1000


@dataclass(frozen=True, slots=True)
class _FinalizerStats:
    repos_processed: int = 0
    repos_updated: int = 0


def finalize(
    db: Database[dict[str, Any]], emoji_top_n: int
) -> _FinalizerStats:
    """Set rates on every repo; prune ``emoji_top`` to the top N glyphs."""
    processed = 0
    updated = 0
    pending_ops: list[UpdateOne] = []
    cursor = db.repos.find({}, projection={"_id": 1, "commit_stats": 1})
    for doc in cursor:
        processed += 1
        stats = doc.get("commit_stats") or {}
        total = int(stats.get("total_commits_in_window", 0) or 0)

        set_fields: dict[str, Any] = {
            "commit_stats.profanity_rate": (
                (stats.get("profanity_hits", 0) or 0) / total
                if total > 0
                else 0.0
            ),
            "commit_stats.emoji_rate": (
                (stats.get("emoji_hits", 0) or 0) / total
                if total > 0
                else 0.0
            ),
        }

        emoji_top = stats.get("emoji_top") or {}
        if isinstance(emoji_top, dict) and len(emoji_top) > emoji_top_n:
            pruned = dict(
                sorted(
                    emoji_top.items(),
                    key=lambda kv: (-(int(kv[1]) if isinstance(kv[1], int) else 0), kv[0]),
                )[:emoji_top_n]
            )
            set_fields["commit_stats.emoji_top"] = pruned

        pending_ops.append(
            UpdateOne({"_id": doc["_id"]}, {"$set": set_fields})
        )
        updated += 1

        if len(pending_ops) >= _BULK_CHUNK:
            db.repos.bulk_write(pending_ops, ordered=False)
            pending_ops.clear()

    if pending_ops:
        db.repos.bulk_write(pending_ops, ordered=False)

    logger.info(
        "finalize: processed %d repos, issued %d updates", processed, updated
    )
    return _FinalizerStats(repos_processed=processed, repos_updated=updated)
