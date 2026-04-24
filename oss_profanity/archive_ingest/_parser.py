"""Parse one hourly `.json.gz` payload into a bulk-upsert batch.

In-memory ``gzip.GzipFile(fileobj=BytesIO(gz_bytes))`` + ``orjson.loads``
per line. We filter to ``type == "PushEvent"`` rows, drop bot-authored
commits, compute profanity + emoji on every surviving commit message,
and push observations into the per-file aggregator.

Called inside a ``ProcessPoolExecutor`` worker. The returned
:class:`_ParseResult` is picklable (plain dataclasses + a list of
``UpdateOne`` objects, which PyMongo defines as picklable).
"""

from __future__ import annotations

import gzip
import io
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import orjson
from pymongo import UpdateOne

from .. import emoji_scan
from .. import profanity
from ._accumulator import _PerFileAggregator
from ._bot import is_bot

logger = logging.getLogger(__name__)

_SAMPLE_TRUNCATE_CHARS = 200


@dataclass(frozen=True, slots=True)
class _ParseResult:
    """What the worker hands back after parsing one file."""

    bulk_ops: list[UpdateOne] = field(default_factory=list)
    rows: int = 0
    push_events: int = 0
    bots_filtered: int = 0
    commits_observed: int = 0


def parse_bytes(gz_bytes: bytes, *, sample_cap: int) -> _ParseResult:
    """Decode the compressed NDJSON payload and build an upsert batch."""
    aggregator = _PerFileAggregator()
    rows = 0
    push_events = 0
    bots_filtered = 0
    commits_observed = 0

    with gzip.GzipFile(fileobj=io.BytesIO(gz_bytes)) as gz:
        for line in gz:
            rows += 1
            event = _safe_loads(line)
            if event is None:
                continue
            if event.get("type") != "PushEvent":
                continue
            push_events += 1

            actor = event.get("actor") or {}
            actor_login = actor.get("login")
            actor_type = actor.get("type")
            if is_bot(actor_login, actor_type):
                bots_filtered += 1
                continue

            repo = event.get("repo") or {}
            repo_id = repo.get("id")
            repo_name = repo.get("name")
            if not isinstance(repo_id, int) or not isinstance(repo_name, str):
                continue

            first_seen = _event_timestamp(event)

            payload = event.get("payload") or {}
            commits = payload.get("commits") or []
            if not isinstance(commits, list):
                continue

            for commit in commits:
                if not isinstance(commit, dict):
                    continue
                message = commit.get("message")
                if not isinstance(message, str) or not message:
                    continue
                author_data = commit.get("author") or {}
                author = _commit_author(author_data) or actor_login
                language = profanity.detect_language(message)
                profanity_hits = profanity.scan(message, language)
                emoji_hits = emoji_scan.extract(message)
                sample = (
                    message[:_SAMPLE_TRUNCATE_CHARS] if profanity_hits else None
                )
                aggregator.observe(
                    repo_id=repo_id,
                    repo_name=repo_name,
                    first_seen_at=first_seen,
                    author=author,
                    language=language,
                    profanity_occurrences=profanity_hits,
                    emoji_occurrences=emoji_hits,
                    sample_message=sample,
                    sample_cap=sample_cap,
                )
                commits_observed += 1

    return _ParseResult(
        bulk_ops=aggregator.to_bulk_ops(sample_cap=sample_cap),
        rows=rows,
        push_events=push_events,
        bots_filtered=bots_filtered,
        commits_observed=commits_observed,
    )


def _safe_loads(line: bytes) -> dict[str, Any] | None:
    """Return the decoded JSON dict, or ``None`` if the line is malformed.

    One pathological line must not abort an entire hourly file.
    """
    try:
        value = orjson.loads(line)
    except orjson.JSONDecodeError:
        return None
    if not isinstance(value, dict):
        return None
    return value


def _event_timestamp(event: dict[str, Any]) -> datetime:
    """Best-effort parse of ``event.created_at`` (ISO 8601 ``Z`` form)."""
    created = event.get("created_at")
    if isinstance(created, str):
        try:
            return datetime.fromisoformat(created.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def _commit_author(author: dict[str, Any]) -> str | None:
    """Prefer email, fall back to name; both are free-form strings upstream."""
    for key in ("email", "name"):
        v = author.get(key)
        if isinstance(v, str) and v:
            return v
    return None
