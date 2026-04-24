"""MongoDB client, claim primitives, and Pydantic schema for the ``repos`` collection.

Exposes the only three mutation primitives the rest of the pipeline is allowed
to call (``claim_next_repo``, ``reclaim_stale``, ``mark_failed``), a
``make_worker_id`` helper that guarantees uniqueness across Docker replicas,
and a Pydantic ``Repo`` model that hydrates raw Mongo documents on read.
"""

from __future__ import annotations

import os
import secrets
import socket
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from pymongo import MongoClient, ReturnDocument
from pymongo.database import Database

from .config import config

Status = Literal["seen", "pending", "claimed", "done", "failed", "skipped"]


class CommitStats(BaseModel):
    model_config = ConfigDict(extra="allow")

    total_commits_in_window: int = 0
    unique_authors: list[str] = Field(default_factory=list)
    languages_detected: dict[str, int] = Field(default_factory=dict)
    profanity_hits: int = 0
    profanity_rate: float = 0.0
    profanity_top: dict[str, int] = Field(default_factory=dict)
    sample_profane_messages: list[str] = Field(default_factory=list)
    emoji_hits: int = 0
    emoji_rate: float = 0.0
    emoji_commits: int = 0
    emoji_top: dict[str, int] = Field(default_factory=dict)


class CodeAnalysis(BaseModel):
    model_config = ConfigDict(extra="allow")

    loc_total: int = 0
    files_scanned: int = 0
    comment_profanity_hits: int = 0
    identifier_profanity_hits: int = 0
    comment_emoji_hits: int = 0
    identifier_emoji_hits: int = 0
    emoji_top: dict[str, int] = Field(default_factory=dict)
    ruff_issues: int | None = None
    ruff_issues_per_kloc: float | None = None
    eslint_issues: int | None = None
    eslint_issues_per_kloc: float | None = None
    lizard_avg_ccn: float | None = None
    lizard_max_ccn: int | None = None
    lizard_functions: int | None = None


class GitHubMetadata(BaseModel):
    """GitHub REST API `/repos/{full_name}` + `/languages` payload (IP-007).

    Field-by-field descriptions live in ``docs/SCHEMA.md``. ``extra="allow"``
    absorbs future GitHub response-shape changes without code updates.
    """

    model_config = ConfigDict(extra="allow")

    fetched_at: datetime
    # Popularity / activity
    stargazers_count: int = 0
    forks_count: int = 0
    watchers_count: int = 0
    subscribers_count: int = 0
    open_issues_count: int = 0
    # Classification
    topics: list[str] = Field(default_factory=list)
    license_spdx: str | None = None
    language: str | None = None
    languages_bytes: dict[str, int] = Field(default_factory=dict)
    # Size + branch
    size_kb: int = 0
    default_branch: str | None = None
    # Fork relationship
    fork: bool = False
    parent_full_name: str | None = None
    # Status flags
    archived: bool = False
    disabled: bool = False
    # Timestamps
    created_at: datetime | None = None
    pushed_at: datetime | None = None
    updated_at: datetime | None = None
    # Free text
    description: str | None = None


class Repo(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    id: int = Field(alias="_id")
    full_name: str
    first_seen_at: datetime
    commit_stats: CommitStats = Field(default_factory=CommitStats)
    status: Status = "seen"
    claimed_by: str | None = None
    claimed_at: datetime | None = None
    primary_language: str | None = None
    code_analysis: CodeAnalysis | None = None
    github_metadata: GitHubMetadata | None = None
    failure_reason: str | None = None
    processing_time_sec: float | None = None


def make_worker_id() -> str:
    """Return a worker ID unique even under Docker replicas sharing hostname + PID namespace."""
    return f"{socket.gethostname()}-{os.getpid()}-{secrets.token_hex(2)}"


_client: MongoClient[dict[str, Any]] | None = None


def get_db() -> Database[dict[str, Any]]:
    """Return the default database, creating indexes on first call per process."""
    global _client
    if _client is None:
        _client = MongoClient(config.mongo_uri)
        _ensure_indexes(_client.get_default_database())
    return _client.get_default_database()


def _ensure_indexes(db: Database[dict[str, Any]]) -> None:
    db.repos.create_index([("status", 1), ("commit_stats.profanity_rate", -1)])
    db.repos.create_index([("status", 1), ("commit_stats.emoji_rate", -1)])


def claim_next_repo(worker_id: str) -> Repo | None:
    """Atomically claim the highest-profanity pending repo for this worker."""
    doc = get_db().repos.find_one_and_update(
        {"status": "pending"},
        {
            "$set": {
                "status": "claimed",
                "claimed_by": worker_id,
                "claimed_at": datetime.now(timezone.utc),
            }
        },
        sort=[("commit_stats.profanity_rate", -1)],
        return_document=ReturnDocument.AFTER,
    )
    return Repo.model_validate(doc) if doc else None


def reclaim_stale() -> int:
    """Flip ``claimed`` docs older than the TTL back to ``pending``; returns count."""
    cutoff = datetime.now(timezone.utc) - config.stale_claim_ttl
    result = get_db().repos.update_many(
        {"status": "claimed", "claimed_at": {"$lt": cutoff}},
        {
            "$set": {"status": "pending"},
            "$unset": {"claimed_by": "", "claimed_at": ""},
        },
    )
    return result.modified_count


def mark_failed(
    repo_id: int, reason: str, elapsed_sec: float | None = None
) -> None:
    """Record a permanent failure for the given repo."""
    update: dict[str, Any] = {"status": "failed", "failure_reason": reason}
    if elapsed_sec is not None:
        update["processing_time_sec"] = elapsed_sec
    get_db().repos.update_one({"_id": repo_id}, {"$set": update})
