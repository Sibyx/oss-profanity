"""Integration tests for IP-006 sampling against a live MongoDB.

Gated by ``TEST_MONGO_URI`` via the ``clean_db`` fixture (see ``conftest.py``).
Each test seeds the ``repos`` collection with a controlled fixture, runs
``sampling.run``, and asserts on the resulting cohort state.
"""

from __future__ import annotations

import importlib
import logging
import os
from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Any

import pytest

from oss_profanity import sampling


@pytest.fixture
def db_module() -> Iterator[Any]:
    """Point the shared config at ``TEST_MONGO_URI`` for this test's scope."""
    import oss_profanity.config as cfg_module
    import oss_profanity.db as db_mod

    uri = os.environ.get("TEST_MONGO_URI", cfg_module.config.mongo_uri)
    original_uri = cfg_module.config.mongo_uri
    object.__setattr__(cfg_module.config, "mongo_uri", uri)
    original_client = db_mod._client
    db_mod._client = None
    try:
        yield db_mod
    finally:
        object.__setattr__(cfg_module.config, "mongo_uri", original_uri)
        if db_mod._client is not None:
            db_mod._client.close()
        db_mod._client = original_client


def _seed_repo(
    db: Any,
    repo_id: int,
    *,
    commits: int,
    profanity_hits: int,
    status: str = "seen",
) -> None:
    profanity_rate = (profanity_hits / commits) if commits > 0 else 0.0
    doc: dict[str, Any] = {
        "_id": repo_id,
        "full_name": f"owner/repo-{repo_id}",
        "first_seen_at": datetime.now(timezone.utc),
        "status": status,
        "commit_stats": {
            "total_commits_in_window": commits,
            "profanity_hits": profanity_hits,
            "profanity_rate": profanity_rate,
            "emoji_hits": 0,
            "emoji_rate": 0.0,
        },
    }
    db.repos.insert_one(doc)


def _seed_fixture(db: Any) -> None:
    """Deterministic fixture spanning all four bins.

    200 profane (50 per bin), 800 clean (200 per bin). Profanity rates
    decrease per repo so the top-N sort is stable.
    """
    bins = [(20, 49), (50, 199), (200, 999), (1000, 5000)]
    repo_id = 1
    for (lo, hi), rate_base in zip(bins, (0.9, 0.7, 0.5, 0.3)):
        for i in range(50):
            commits = lo + (i * (hi - lo + 1) // 50)
            profanity_hits = max(
                1, int(commits * (rate_base - i * 0.005))
            )
            _seed_repo(
                db,
                repo_id,
                commits=commits,
                profanity_hits=profanity_hits,
            )
            repo_id += 1
    for (lo, hi) in bins:
        for i in range(200):
            commits = lo + (i * (hi - lo + 1) // 200)
            _seed_repo(db, repo_id, commits=commits, profanity_hits=0)
            repo_id += 1


def _reload_sampling() -> Any:
    """Fresh import of sampling after config mutation; avoids stale refs."""
    return importlib.reload(sampling)


def _set_cohort_sizes(profane: int, clean: int) -> None:
    import oss_profanity.config as cfg_module

    object.__setattr__(cfg_module.config, "profane_cohort_size", profane)
    object.__setattr__(cfg_module.config, "clean_cohort_size", clean)


# ---------- happy path ----------


def test_run_promotes_both_cohorts_with_labels(
    clean_db: None, db_module: Any
) -> None:
    _set_cohort_sizes(200, 200)
    db = db_module.get_db()
    _seed_fixture(db)

    mod = _reload_sampling()
    report = mod.run(db)

    assert report.profane_selected == 200
    assert report.clean_selected == 200
    assert report.total_promoted == 400
    assert sum(report.shortfalls.values()) == 0
    assert db.repos.count_documents({"status": "pending", "cohort": "profane"}) == 200
    assert db.repos.count_documents({"status": "pending", "cohort": "clean"}) == 200
    assert db.repos.count_documents({"status": "skipped"}) == 1000 - 400


def test_run_bin_match_matches_profane_distribution(
    clean_db: None, db_module: Any
) -> None:
    _set_cohort_sizes(200, 200)
    db = db_module.get_db()
    _seed_fixture(db)

    mod = _reload_sampling()
    report = mod.run(db)

    for _, (profane_count, clean_count) in report.bin_histogram.items():
        assert profane_count == 50
        assert clean_count == 50


# ---------- idempotence ----------


def test_run_is_idempotent(clean_db: None, db_module: Any) -> None:
    _set_cohort_sizes(200, 200)
    db = db_module.get_db()
    _seed_fixture(db)

    mod = _reload_sampling()
    first = mod.run(db)
    assert first.total_promoted == 400

    second = mod.run(db)
    assert second.profane_selected == 0
    assert second.clean_selected == 0
    assert second.total_promoted == 0


# ---------- edge cases ----------


def test_run_zero_profanity_exits_cleanly(
    clean_db: None,
    db_module: Any,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _set_cohort_sizes(200, 200)
    db = db_module.get_db()
    for i in range(50):
        _seed_repo(db, i + 1, commits=30, profanity_hits=0)

    mod = _reload_sampling()
    with caplog.at_level(logging.WARNING, logger="oss_profanity.sampling"):
        report = mod.run(db)

    assert report.profane_selected == 0
    assert report.clean_selected == 0
    assert report.total_promoted == 0
    assert any(
        "nothing to promote" in rec.message for rec in caplog.records
    )


def test_run_records_bin_shortfall(
    clean_db: None, db_module: Any
) -> None:
    _set_cohort_sizes(100, 100)
    db = db_module.get_db()
    # 50 profane in the [1000, ∞) bin
    for i in range(50):
        _seed_repo(db, 1_000 + i, commits=1500, profanity_hits=100)
    # Only 10 clean in [1000, ∞) → shortfall 40.
    for i in range(10):
        _seed_repo(db, 2_000 + i, commits=1500, profanity_hits=0)
    # Fill the [20, 50) bin to round out the rest.
    for i in range(50):
        _seed_repo(db, 3_000 + i, commits=30, profanity_hits=5)
    for i in range(200):
        _seed_repo(db, 4_000 + i, commits=30, profanity_hits=0)

    mod = _reload_sampling()
    report = mod.run(db)

    assert report.profane_selected == 100
    assert report.shortfalls.get(1000) == 40
    assert report.clean_selected == 100 - 40
    assert db.repos.count_documents({"cohort": "profane"}) == 100


# ---------- cohort field schema ----------


def test_cohort_field_persisted_on_repo(
    clean_db: None, db_module: Any
) -> None:
    _set_cohort_sizes(50, 50)
    db = db_module.get_db()
    _seed_fixture(db)

    mod = _reload_sampling()
    mod.run(db)

    profane_sample = db.repos.find_one({"cohort": "profane"})
    clean_sample = db.repos.find_one({"cohort": "clean"})
    assert profane_sample is not None
    assert profane_sample["status"] == "pending"
    assert profane_sample["cohort"] == "profane"
    assert clean_sample is not None
    assert clean_sample["status"] == "pending"
    assert clean_sample["cohort"] == "clean"


# ---------- top-up ----------


def test_top_up_demotes_missing_and_fills_gap(
    clean_db: None, db_module: Any
) -> None:
    """Probe-404 cohort repos flip to status=missing; top-up then draws the gap."""
    _set_cohort_sizes(100, 100)
    db = db_module.get_db()
    _seed_fixture(db)

    mod = _reload_sampling()
    first = mod.run(db)
    assert first.total_promoted == 200

    # Mark 20 profane + 15 clean pending rows as probe-404.
    profane_ids = [
        doc["_id"]
        for doc in db.repos.find(
            {"cohort": "profane", "status": "pending"}, projection={"_id": 1}
        ).limit(20)
    ]
    clean_ids = [
        doc["_id"]
        for doc in db.repos.find(
            {"cohort": "clean", "status": "pending"}, projection={"_id": 1}
        ).limit(15)
    ]
    db.repos.update_many(
        {"_id": {"$in": profane_ids + clean_ids}},
        {"$set": {"github_metadata_probe_missing_at": datetime.now(timezone.utc)}},
    )

    report = mod.run_top_up(db)

    # 404s demoted out of the queue.
    assert db.repos.count_documents(
        {"cohort": "profane", "status": "missing"}
    ) == 20
    assert db.repos.count_documents(
        {"cohort": "clean", "status": "missing"}
    ) == 15
    # Gap filled: live cohort count back at target.
    assert db.repos.count_documents(
        {"cohort": "profane", "status": "pending"}
    ) == 100
    assert db.repos.count_documents(
        {"cohort": "clean", "status": "pending"}
    ) == 100
    assert report.profane_selected == 20
    assert report.clean_selected == 15


def test_top_up_is_noop_when_at_target(
    clean_db: None, db_module: Any
) -> None:
    _set_cohort_sizes(100, 100)
    db = db_module.get_db()
    _seed_fixture(db)

    mod = _reload_sampling()
    mod.run(db)

    report = mod.run_top_up(db)
    assert report.profane_selected == 0
    assert report.clean_selected == 0
    assert report.total_promoted == 0
