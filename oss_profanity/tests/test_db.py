"""Integration tests for the db module.

Require a live MongoDB at ``TEST_MONGO_URI`` (see ``conftest.py``). The suite
exercises the Pydantic schema, atomic claim primitives, and stale-claim
reclamation; everything that IP-001 promises end-to-end.
"""

from __future__ import annotations

import importlib
from datetime import datetime, timedelta, timezone

import pytest


@pytest.fixture
def db_module():
    """Reload db so it picks up the TEST_MONGO_URI-backed config."""
    import oss_profanity.config
    import oss_profanity.db

    importlib.reload(oss_profanity.config)
    mod = importlib.reload(oss_profanity.db)
    mod._client = None  # force a fresh MongoClient + ensure_indexes on first get_db
    return mod


def _insert_repo(db, repo_id: int, **overrides) -> None:
    doc = {
        "_id": repo_id,
        "full_name": f"owner/repo-{repo_id}",
        "first_seen_at": datetime.now(timezone.utc),
        "status": "pending",
        "commit_stats": {
            "total_commits_in_window": 42,
            "profanity_hits": 0,
            "profanity_rate": 0.0,
            "emoji_hits": 0,
            "emoji_rate": 0.0,
        },
    }
    doc.update(overrides)
    db.repos.insert_one(doc)


def test_indexes_created_on_first_get_db(clean_db, db_module) -> None:
    db = db_module.get_db()
    index_info = db.repos.index_information()
    index_keys = {tuple(v["key"]) for v in index_info.values()}

    assert (("status", 1), ("commit_stats.profanity_rate", -1)) in index_keys
    assert (("status", 1), ("commit_stats.emoji_rate", -1)) in index_keys


def test_claim_next_repo_returns_pydantic_model(clean_db, db_module) -> None:
    db = db_module.get_db()
    _insert_repo(db, 1, commit_stats={
        "total_commits_in_window": 42,
        "profanity_rate": 0.5,
        "emoji_rate": 0.1,
    })

    claimed = db_module.claim_next_repo("worker-a")

    assert claimed is not None
    assert claimed.id == 1
    assert claimed.status == "claimed"
    assert claimed.claimed_by == "worker-a"
    assert claimed.commit_stats.profanity_rate == 0.5


def test_claim_next_repo_is_atomic(clean_db, db_module) -> None:
    db = db_module.get_db()
    _insert_repo(db, 1)

    first = db_module.claim_next_repo("worker-a")
    second = db_module.claim_next_repo("worker-b")

    assert first is not None and first.claimed_by == "worker-a"
    assert second is None


def test_claim_ordering_prefers_higher_profanity_rate(
    clean_db, db_module
) -> None:
    db = db_module.get_db()
    _insert_repo(
        db,
        1,
        commit_stats={
            "total_commits_in_window": 20,
            "profanity_rate": 0.1,
            "emoji_rate": 0.0,
        },
    )
    _insert_repo(
        db,
        2,
        commit_stats={
            "total_commits_in_window": 20,
            "profanity_rate": 0.9,
            "emoji_rate": 0.0,
        },
    )

    first = db_module.claim_next_repo("worker-a")
    assert first is not None
    assert first.id == 2


def test_reclaim_stale_moves_old_claims_back_to_pending(
    clean_db, db_module
) -> None:
    db = db_module.get_db()
    stale_at = datetime.now(timezone.utc) - timedelta(minutes=30)
    fresh_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    _insert_repo(
        db, 1, status="claimed", claimed_by="worker-dead", claimed_at=stale_at
    )
    _insert_repo(
        db, 2, status="claimed", claimed_by="worker-live", claimed_at=fresh_at
    )

    count = db_module.reclaim_stale()

    assert count == 1
    assert db.repos.find_one({"_id": 1})["status"] == "pending"
    assert db.repos.find_one({"_id": 2})["status"] == "claimed"


def test_mark_failed_sets_failure_state(clean_db, db_module) -> None:
    db = db_module.get_db()
    _insert_repo(db, 1, status="claimed", claimed_by="worker-a")

    db_module.mark_failed(1, "timeout", elapsed_sec=123.4)

    doc = db.repos.find_one({"_id": 1})
    assert doc["status"] == "failed"
    assert doc["failure_reason"] == "timeout"
    assert doc["processing_time_sec"] == 123.4


def test_make_worker_id_is_unique_per_call(db_module) -> None:
    ids = {db_module.make_worker_id() for _ in range(20)}
    assert len(ids) == 20
    # Every ID carries hostname + pid for log readability.
    for wid in ids:
        assert "-" in wid
        parts = wid.rsplit("-", 2)
        assert len(parts) == 3
        assert parts[1].isdigit()  # pid segment
        assert len(parts[2]) == 4  # 2-byte hex suffix
