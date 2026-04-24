"""End-to-end orchestrator: downloader → queue → parse pool → upsert.

Mocks the HTTP layer to return crafted ndjson.gz bytes; runs against a
real Mongo (gated on ``TEST_MONGO_URI``, same pattern as the other
Mongo tests). Asserts ``ingest_runs`` lifecycle lands correctly and
``repos.commit_stats`` populates for both signals in one pass.
"""

from __future__ import annotations

import asyncio
import gzip
import io
import json
from collections.abc import Iterator
from typing import Any

import pytest
from pymongo import MongoClient

from oss_profanity.archive_ingest import _http, _runner


def _make_gz(events: list[dict[str, Any]]) -> bytes:
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb") as gz:
        for evt in events:
            gz.write(json.dumps(evt).encode("utf-8"))
            gz.write(b"\n")
    return buf.getvalue()


def _push(
    repo_id: int, messages: list[str], actor_login: str = "alice"
) -> dict[str, Any]:
    return {
        "type": "PushEvent",
        "created_at": "2020-06-01T12:00:00Z",
        "actor": {"id": 1, "login": actor_login},
        "repo": {"id": repo_id, "name": f"owner/r{repo_id}"},
        "payload": {
            "commits": [
                {"message": m, "author": {"email": "a@ex.com"}}
                for m in messages
            ]
        },
    }


@pytest.fixture
def clean_runner_db(
    mongo_uri: str, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Any]:
    monkeypatch.setenv("MONGO_URI", mongo_uri)
    # Reload config.config so the new env var takes effect for this
    # test's scope.
    from oss_profanity import config as cfg_module

    object.__setattr__(cfg_module.config, "mongo_uri", mongo_uri)
    object.__setattr__(cfg_module.config, "gha_start", "2020-06-01-00")
    object.__setattr__(cfg_module.config, "gha_end", "2020-06-01-01")
    client: MongoClient[dict[str, Any]] = MongoClient(mongo_uri)
    db = client.get_default_database()
    db.ingest_runs.drop()
    db.repos.drop()
    yield db
    db.ingest_runs.drop()
    db.repos.drop()
    client.close()


@pytest.fixture
def canned_bytes() -> dict[str, bytes]:
    """Per-file-id canned payloads for the stream_file mock."""
    return {
        "2020-06-01-00": _make_gz(
            [
                _push(1, ["regular commit 🚀"]),
                _push(2, ["fuck this bug 🐛 ruins release 🚀"]),
                _push(3, ["normal work"], actor_login="dependabot[bot]"),  # bot filter
            ]
        ),
        "2020-06-01-01": _make_gz(
            [
                _push(2, ["merge branch 'main'"]),
                _push(4, ["new feature ✨"]),
            ]
        ),
    }


@pytest.mark.asyncio
async def test_run_end_to_end(
    clean_runner_db: Any,
    canned_bytes: dict[str, bytes],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = clean_runner_db

    async def fake_stream(
        _client: Any, file_id: str, max_retries: int = 5
    ) -> bytes:
        return canned_bytes[file_id]

    monkeypatch.setattr(_http, "stream_file", fake_stream)
    monkeypatch.setattr(_runner._http, "stream_file", fake_stream)

    await _runner.run()

    # ingest_runs: all done
    assert (
        db.ingest_runs.count_documents({"status": "done"}) == 2
    ), list(db.ingest_runs.find({}))
    # repos: 3 unique repos (ids 1, 2, 4); repo 3 was bot-filtered
    repo_ids = {d["_id"] for d in db.repos.find({}, {"_id": 1})}
    assert repo_ids == {1, 2, 4}

    # repo 2 appears in both files; counts accumulate
    r2 = db.repos.find_one({"_id": 2})
    assert r2["commit_stats"]["total_commits_in_window"] == 2

    # Both-signals contract: some repo has profanity; some has emoji
    has_profanity = db.repos.count_documents(
        {"commit_stats.profanity_hits": {"$gt": 0}}
    )
    has_emoji = db.repos.count_documents(
        {"commit_stats.emoji_hits": {"$gt": 0}}
    )
    assert has_profanity >= 1
    assert has_emoji >= 1

    # Finalizer ran → rates populated
    assert r2["commit_stats"]["profanity_rate"] is not None


@pytest.mark.asyncio
async def test_run_one_file(
    clean_runner_db: Any,
    canned_bytes: dict[str, bytes],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = clean_runner_db

    async def fake_stream(
        _client: Any, file_id: str, max_retries: int = 5
    ) -> bytes:
        return canned_bytes[file_id]

    monkeypatch.setattr(_http, "stream_file", fake_stream)
    monkeypatch.setattr(_runner._http, "stream_file", fake_stream)

    stats = await _runner.run_one_file("2020-06-01-00")
    assert stats is not None
    assert stats["push_events"] == 3
    assert stats["bots_filtered"] == 1
    assert stats["commits_observed"] == 2
    assert stats["upserted"] == 2  # repos 1 and 2

    # ingest_runs marks the single file done; the second file stays pending
    assert db.ingest_runs.count_documents({"status": "done"}) == 1


@pytest.mark.asyncio
async def test_run_marks_failed_on_download_error(
    clean_runner_db: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = clean_runner_db

    async def always_fail(
        _client: Any, file_id: str, max_retries: int = 5
    ) -> bytes:
        raise RuntimeError("simulated network outage")

    monkeypatch.setattr(_http, "stream_file", always_fail)
    monkeypatch.setattr(_runner._http, "stream_file", always_fail)

    await _runner.run()

    failed = db.ingest_runs.count_documents({"status": "failed"})
    done = db.ingest_runs.count_documents({"status": "done"})
    assert failed >= 1
    assert done == 0
    # repos collection has no new entries
    assert db.repos.count_documents({}) == 0
