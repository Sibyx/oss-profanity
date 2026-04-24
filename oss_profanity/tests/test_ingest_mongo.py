"""Mongo-backed tests: ``ingest_runs`` lifecycle, upserter flush,
finalizer rate/top-N computation.

All tests here need a live Mongo instance and skip unless
``TEST_MONGO_URI`` is set (same pattern as the IP-001 db tests).
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from pymongo import MongoClient, UpdateOne

from oss_profanity.archive_ingest import _finalizer, _progress, _upserter


@pytest.fixture
def clean_ingest_db(
    mongo_uri: str, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Any]:
    """Drop ingest_runs + repos before and after each test."""
    monkeypatch.setenv("MONGO_URI", mongo_uri)
    client: MongoClient[dict[str, Any]] = MongoClient(mongo_uri)
    db = client.get_default_database()
    db.ingest_runs.drop()
    db.repos.drop()
    yield db
    db.ingest_runs.drop()
    db.repos.drop()
    client.close()


# ---------- _progress ----------


def test_seed_pending_is_idempotent(clean_ingest_db: Any) -> None:
    db = clean_ingest_db
    ids = ["2020-06-01-00", "2020-06-01-01", "2020-06-01-02"]
    created = _progress.seed_pending(db, ids)
    assert created == 3
    # Re-run should upsert zero new docs.
    again = _progress.seed_pending(db, ids)
    assert again == 0
    assert db.ingest_runs.count_documents({"status": "pending"}) == 3


def test_claim_next_file_flips_to_in_progress(clean_ingest_db: Any) -> None:
    db = clean_ingest_db
    _progress.seed_pending(db, ["2020-06-01-00", "2020-06-01-01"])
    claimed = _progress.claim_next_file(db, worker_id="w1")
    assert claimed == "2020-06-01-00"
    doc = db.ingest_runs.find_one({"_id": "2020-06-01-00"})
    assert doc is not None
    assert doc["status"] == "in_progress"
    assert doc["worker_id"] == "w1"
    assert doc["attempts"] == 1


def test_claim_next_file_returns_none_when_nothing_pending(
    clean_ingest_db: Any,
) -> None:
    assert _progress.claim_next_file(clean_ingest_db, worker_id="w") is None


def test_claim_sort_order_is_chronological(clean_ingest_db: Any) -> None:
    db = clean_ingest_db
    # Insert in non-chronological order; claim should still go oldest-first.
    _progress.seed_pending(
        db, ["2020-06-01-05", "2020-06-01-00", "2020-06-01-10"]
    )
    claimed = [
        _progress.claim_next_file(db, worker_id="w"),
        _progress.claim_next_file(db, worker_id="w"),
        _progress.claim_next_file(db, worker_id="w"),
    ]
    assert claimed == ["2020-06-01-00", "2020-06-01-05", "2020-06-01-10"]


def test_mark_done_closes_lifecycle(clean_ingest_db: Any) -> None:
    db = clean_ingest_db
    _progress.seed_pending(db, ["2020-06-01-00"])
    _progress.claim_next_file(db, worker_id="w")
    _progress.mark_done(
        db,
        "2020-06-01-00",
        {"rows": 1000, "push_events": 500, "commits_observed": 400},
    )
    doc = db.ingest_runs.find_one({"_id": "2020-06-01-00"})
    assert doc["status"] == "done"
    assert doc["rows"] == 1000
    assert "finished_at" in doc


def test_mark_failed_records_error(clean_ingest_db: Any) -> None:
    db = clean_ingest_db
    _progress.seed_pending(db, ["2020-06-01-00"])
    _progress.claim_next_file(db, worker_id="w")
    _progress.mark_failed(db, "2020-06-01-00", "ValueError: test")
    doc = db.ingest_runs.find_one({"_id": "2020-06-01-00"})
    assert doc["status"] == "failed"
    assert "ValueError" in doc["error"]


def test_reclaim_stale_flips_old_in_progress_to_pending(
    clean_ingest_db: Any,
) -> None:
    db = clean_ingest_db
    db.ingest_runs.insert_one(
        {
            "_id": "2020-06-01-00",
            "status": "in_progress",
            "worker_id": "dead-worker",
            "heartbeat_at": datetime.now(timezone.utc)
            - timedelta(hours=2),
        }
    )
    # Young in-progress should NOT be reclaimed.
    db.ingest_runs.insert_one(
        {
            "_id": "2020-06-01-01",
            "status": "in_progress",
            "worker_id": "alive",
            "heartbeat_at": datetime.now(timezone.utc),
        }
    )
    reclaimed = _progress.reclaim_stale(db, ttl_minutes=30)
    assert reclaimed == 1
    stale = db.ingest_runs.find_one({"_id": "2020-06-01-00"})
    assert stale["status"] == "pending"
    assert "worker_id" not in stale
    live = db.ingest_runs.find_one({"_id": "2020-06-01-01"})
    assert live["status"] == "in_progress"


def test_heartbeat_updates_heartbeat_at(clean_ingest_db: Any) -> None:
    db = clean_ingest_db
    _progress.seed_pending(db, ["2020-06-01-00"])
    _progress.claim_next_file(db, worker_id="w")
    before = db.ingest_runs.find_one({"_id": "2020-06-01-00"})["heartbeat_at"]
    _progress.heartbeat(db, "2020-06-01-00")
    after = db.ingest_runs.find_one({"_id": "2020-06-01-00"})["heartbeat_at"]
    assert after >= before


# ---------- _upserter ----------


def test_upserter_flush_empty_ops_returns_zero(clean_ingest_db: Any) -> None:
    stats = _upserter.flush(clean_ingest_db.repos, [])
    assert stats.upserted == 0
    assert stats.modified == 0


def test_upserter_flush_upserts_new_docs(clean_ingest_db: Any) -> None:
    ops = [
        UpdateOne(
            {"_id": 1},
            {
                "$setOnInsert": {"full_name": "a/b"},
                "$inc": {"commit_stats.total_commits_in_window": 3},
            },
            upsert=True,
        )
    ]
    stats = _upserter.flush(clean_ingest_db.repos, ops)
    assert stats.upserted == 1
    doc = clean_ingest_db.repos.find_one({"_id": 1})
    assert doc["full_name"] == "a/b"
    assert doc["commit_stats"]["total_commits_in_window"] == 3


def test_upserter_flush_splits_into_batches(clean_ingest_db: Any) -> None:
    # 2,500 ops with batch_size=1,000 → 3 batches.
    ops = [
        UpdateOne(
            {"_id": i},
            {"$setOnInsert": {"full_name": f"a/{i}"}},
            upsert=True,
        )
        for i in range(2500)
    ]
    stats = _upserter.flush(clean_ingest_db.repos, ops, batch_size=1000)
    assert stats.upserted == 2500
    assert clean_ingest_db.repos.count_documents({}) == 2500


# ---------- _finalizer ----------


def test_finalizer_computes_rates_and_truncates_emoji_top(
    clean_ingest_db: Any,
) -> None:
    db = clean_ingest_db
    db.repos.insert_one(
        {
            "_id": 1,
            "commit_stats": {
                "total_commits_in_window": 100,
                "profanity_hits": 5,
                "emoji_hits": 20,
                "emoji_top": {chr(0x1F680 + i): (10 - i) for i in range(10)},
            },
        }
    )
    stats = _finalizer.finalize(db, emoji_top_n=3)
    assert stats.repos_processed == 1
    doc = db.repos.find_one({"_id": 1})
    cs = doc["commit_stats"]
    assert cs["profanity_rate"] == 0.05
    assert cs["emoji_rate"] == 0.2
    assert len(cs["emoji_top"]) == 3


def test_finalizer_is_idempotent(clean_ingest_db: Any) -> None:
    db = clean_ingest_db
    db.repos.insert_one(
        {
            "_id": 1,
            "commit_stats": {
                "total_commits_in_window": 10,
                "profanity_hits": 3,
                "emoji_hits": 5,
                "emoji_top": {"🚀": 5},
            },
        }
    )
    _finalizer.finalize(db, emoji_top_n=20)
    first = db.repos.find_one({"_id": 1})["commit_stats"]
    _finalizer.finalize(db, emoji_top_n=20)
    second = db.repos.find_one({"_id": 1})["commit_stats"]
    assert first == second


def test_finalizer_handles_zero_commit_repo(clean_ingest_db: Any) -> None:
    db = clean_ingest_db
    db.repos.insert_one(
        {"_id": 1, "commit_stats": {"total_commits_in_window": 0}}
    )
    stats = _finalizer.finalize(db, emoji_top_n=10)
    assert stats.repos_processed == 1
    doc = db.repos.find_one({"_id": 1})
    assert doc["commit_stats"]["profanity_rate"] == 0.0
    assert doc["commit_stats"]["emoji_rate"] == 0.0


def test_finalizer_skips_emoji_top_prune_when_already_small(
    clean_ingest_db: Any,
) -> None:
    db = clean_ingest_db
    db.repos.insert_one(
        {
            "_id": 1,
            "commit_stats": {
                "total_commits_in_window": 10,
                "profanity_hits": 1,
                "emoji_hits": 2,
                "emoji_top": {"🚀": 2},
            },
        }
    )
    _finalizer.finalize(db, emoji_top_n=20)
    cs = db.repos.find_one({"_id": 1})["commit_stats"]
    assert cs["emoji_top"] == {"🚀": 2}
