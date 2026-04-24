"""Thin wrapper around PyMongo ``bulk_write``.

Splits a list of ``UpdateOne`` into 1,000-op batches and dispatches each
with ``ordered=False`` (server parallelizes; one bad op doesn't kill the
batch). PyMongo auto-splits at MongoDB's 48 MB message cap anyway — our
1,000 cap is for latency locality, not correctness.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pymongo import UpdateOne
from pymongo.collection import Collection

_BATCH_SIZE_DEFAULT = 1000


@dataclass(frozen=True, slots=True)
class _UpserterStats:
    """Flush-level counters accumulated across all batches."""

    upserted: int = 0
    modified: int = 0
    matched: int = 0


def flush(
    collection: Collection[dict[str, Any]],
    ops: list[UpdateOne],
    batch_size: int = _BATCH_SIZE_DEFAULT,
) -> _UpserterStats:
    """Dispatch ``ops`` in ``batch_size`` chunks; return aggregate stats."""
    if not ops:
        return _UpserterStats()
    upserted = 0
    modified = 0
    matched = 0
    for i in range(0, len(ops), batch_size):
        batch = ops[i : i + batch_size]
        result = collection.bulk_write(batch, ordered=False)
        upserted += len(result.upserted_ids or {})
        modified += int(result.modified_count or 0)
        matched += int(result.matched_count or 0)
    return _UpserterStats(upserted=upserted, modified=modified, matched=matched)
