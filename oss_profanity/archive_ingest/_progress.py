"""Lifecycle tracking for the ``ingest_runs`` collection.

One document per hourly file. Fields:

* ``_id`` — canonical zero-padded ``YYYY-MM-DD-HH`` file ID (lexicographic
  sort matches chronological order, so the default-sort claim pattern
  drains the window in order)
* ``status`` — ``pending`` / ``in_progress`` / ``done`` / ``failed``
* ``worker_id`` — set while ``in_progress``
* ``attempts`` — bumped on every ``claim_next_file``
* ``started_at`` / ``heartbeat_at`` / ``finished_at``
* ``error`` — last failure reason, never the raw line content

The primary claim index is ``(status, heartbeat_at)``. A stale-claim
sweep on startup reclaims ``in_progress`` rows whose heartbeat predates
the TTL (same pattern IP-001 uses for ``repos``).
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from typing import Any, Final

from pymongo import ReturnDocument, UpdateOne
from pymongo.database import Database

_STALE_TTL_MINUTES_DEFAULT: Final[int] = 30


def ensure_index(db: Database[dict[str, Any]]) -> None:
    """Create the `(status, heartbeat_at)` compound index idempotently."""
    db.ingest_runs.create_index([("status", 1), ("heartbeat_at", 1)])


def seed_pending(
    db: Database[dict[str, Any]], file_ids: Iterable[str]
) -> int:
    """Upsert ``status="pending"`` rows for the given file IDs.

    Returns the number of newly-created documents; pre-existing rows
    are left alone (idempotent relaunch after a partial run).
    """
    ops = [
        UpdateOne(
            {"_id": fid},
            {
                "$setOnInsert": {
                    "status": "pending",
                    "attempts": 0,
                }
            },
            upsert=True,
        )
        for fid in file_ids
    ]
    if not ops:
        return 0
    result = db.ingest_runs.bulk_write(ops, ordered=False)
    return len(result.upserted_ids or {})


def claim_next_file(
    db: Database[dict[str, Any]], worker_id: str
) -> str | None:
    """Atomically claim the oldest pending file; return its ID or ``None``."""
    now = datetime.now(timezone.utc)
    doc = db.ingest_runs.find_one_and_update(
        {"status": "pending"},
        {
            "$set": {
                "status": "in_progress",
                "worker_id": worker_id,
                "started_at": now,
                "heartbeat_at": now,
            },
            "$inc": {"attempts": 1},
        },
        sort=[("_id", 1)],
        return_document=ReturnDocument.AFTER,
    )
    if doc is None:
        return None
    file_id = doc.get("_id")
    return file_id if isinstance(file_id, str) else None


def heartbeat(db: Database[dict[str, Any]], file_id: str) -> None:
    """Touch ``heartbeat_at`` on an in-progress claim."""
    db.ingest_runs.update_one(
        {"_id": file_id, "status": "in_progress"},
        {"$set": {"heartbeat_at": datetime.now(timezone.utc)}},
    )


def mark_done(
    db: Database[dict[str, Any]], file_id: str, stats: dict[str, Any]
) -> None:
    """Close the lifecycle successfully with per-file counters attached."""
    payload: dict[str, Any] = {
        "status": "done",
        "finished_at": datetime.now(timezone.utc),
    }
    payload.update(stats)
    db.ingest_runs.update_one({"_id": file_id}, {"$set": payload})


def mark_failed(
    db: Database[dict[str, Any]], file_id: str, error: str
) -> None:
    """Record a terminal failure so the stale-reaper can leave it alone."""
    db.ingest_runs.update_one(
        {"_id": file_id},
        {
            "$set": {
                "status": "failed",
                "finished_at": datetime.now(timezone.utc),
                "error": error,
            }
        },
    )


def reclaim_stale(
    db: Database[dict[str, Any]],
    ttl_minutes: int = _STALE_TTL_MINUTES_DEFAULT,
) -> int:
    """Flip long-in-progress rows back to ``pending``; returns count."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=ttl_minutes)
    result = db.ingest_runs.update_many(
        {"status": "in_progress", "heartbeat_at": {"$lt": cutoff}},
        {
            "$set": {"status": "pending"},
            "$unset": {
                "worker_id": "",
                "started_at": "",
                "heartbeat_at": "",
            },
        },
    )
    return result.modified_count
