"""Per-process claim loop (IP-007 `_loop`)."""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from pymongo import MongoClient

from oss_profanity import db as db_module
from oss_profanity.repo_worker import _loop, _processor, _scratch


@pytest.fixture
def clean_worker_db(
    mongo_uri: str, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Any]:
    """Drop repos before + after; reset the shared pymongo client singleton."""
    monkeypatch.setenv("MONGO_URI", mongo_uri)
    # Reset the shared client so it picks up the test URI.
    monkeypatch.setattr(db_module, "_client", None, raising=False)

    client: MongoClient[dict[str, Any]] = MongoClient(mongo_uri)
    db = client.get_default_database()
    db.repos.drop()
    yield db
    db.repos.drop()
    client.close()


def _insert_pending(
    db: Any,
    repo_id: int,
    full_name: str = "alice/widget",
    profanity_rate: float = 0.0,
) -> None:
    db.repos.insert_one(
        {
            "_id": repo_id,
            "full_name": full_name,
            "first_seen_at": datetime.now(timezone.utc),
            "status": "pending",
            "commit_stats": {
                "total_commits_in_window": 25,
                "profanity_hits": 1 if profanity_rate > 0 else 0,
                "profanity_rate": profanity_rate,
            },
        }
    )


def test_loop_exits_when_cohort_fully_drained(
    clean_worker_db: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With zero pending AND zero claimed repos, `run()` returns promptly."""
    new_config = dataclasses.replace(_scratch.config, scratch_dir=str(tmp_path))
    monkeypatch.setattr(_scratch, "config", new_config)

    _loop.run(worker_id="host-0000-aaaa")


def test_loop_processes_pending_then_exits(
    clean_worker_db: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`run()` claims one pending repo, processes it, then exits on drain."""
    new_config = dataclasses.replace(_scratch.config, scratch_dir=str(tmp_path))
    monkeypatch.setattr(_scratch, "config", new_config)
    monkeypatch.setattr(_processor._scratch, "config", new_config)

    _insert_pending(clean_worker_db, 101, "alice/widget", profanity_rate=0.5)

    seen: list[int] = []

    def fake_process_one(repo: Any, worker_id: str) -> None:
        seen.append(repo.id)
        # Simulate mark-done so the claim drains.
        clean_worker_db.repos.update_one(
            {"_id": repo.id, "claimed_by": worker_id},
            {"$set": {"status": "done"}},
        )

    monkeypatch.setattr(_processor, "process_one", fake_process_one)
    monkeypatch.setattr(_loop._processor, "process_one", fake_process_one)

    _loop.run(worker_id="host-1111-bbbb")

    assert seen == [101]
    doc = clean_worker_db.repos.find_one({"_id": 101})
    assert doc["status"] == "done"


def test_loop_reclaims_stale_before_declaring_drained(
    clean_worker_db: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A stale `claimed` doc older than the TTL is reclaimed then processed."""
    new_config = dataclasses.replace(
        _scratch.config,
        scratch_dir=str(tmp_path),
        stale_claim_ttl=timedelta(minutes=1),
    )
    monkeypatch.setattr(_scratch, "config", new_config)
    monkeypatch.setattr(db_module, "config", new_config)

    # Seed a stale claim older than the TTL.
    old = datetime.now(timezone.utc) - timedelta(minutes=30)
    clean_worker_db.repos.insert_one(
        {
            "_id": 202,
            "full_name": "bob/stale",
            "first_seen_at": old,
            "status": "claimed",
            "claimed_by": "dead-worker-0000",
            "claimed_at": old,
            "commit_stats": {
                "total_commits_in_window": 20,
                "profanity_hits": 0,
                "profanity_rate": 0.0,
            },
        }
    )

    processed: list[int] = []

    def fake_process_one(repo: Any, worker_id: str) -> None:
        processed.append(repo.id)
        clean_worker_db.repos.update_one(
            {"_id": repo.id, "claimed_by": worker_id},
            {"$set": {"status": "done"}},
        )

    monkeypatch.setattr(_processor, "process_one", fake_process_one)
    monkeypatch.setattr(_loop._processor, "process_one", fake_process_one)

    _loop.run(worker_id="host-rescue-cccc")

    assert processed == [202]


def test_loop_processes_interesting_first(
    clean_worker_db: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With two pending repos, the higher profanity_rate is claimed first."""
    new_config = dataclasses.replace(_scratch.config, scratch_dir=str(tmp_path))
    monkeypatch.setattr(_scratch, "config", new_config)

    _insert_pending(clean_worker_db, 300, "clean/repo", profanity_rate=0.0)
    _insert_pending(clean_worker_db, 301, "spicy/repo", profanity_rate=0.8)

    order: list[int] = []

    def fake_process_one(repo: Any, worker_id: str) -> None:
        order.append(repo.id)
        clean_worker_db.repos.update_one(
            {"_id": repo.id, "claimed_by": worker_id},
            {"$set": {"status": "done"}},
        )

    monkeypatch.setattr(_processor, "process_one", fake_process_one)
    monkeypatch.setattr(_loop._processor, "process_one", fake_process_one)

    _loop.run(worker_id="host-priority-dddd")

    assert order == [301, 300]
