"""Unit tests for the Pydantic schema — round-trip and edge cases."""

from __future__ import annotations

from datetime import datetime, timezone

from oss_profanity.db import CodeAnalysis, CommitStats, Repo


def test_repo_roundtrips_mongo_underscore_id() -> None:
    raw = {
        "_id": 42,
        "full_name": "foo/bar",
        "first_seen_at": datetime.now(timezone.utc),
    }
    repo = Repo.model_validate(raw)

    assert repo.id == 42
    dumped = repo.model_dump(by_alias=True)
    assert dumped["_id"] == 42


def test_extra_fields_are_preserved() -> None:
    raw = {
        "_id": 1,
        "full_name": "foo/bar",
        "first_seen_at": datetime.now(timezone.utc),
        "some_future_field": "added by later IP",
    }
    repo = Repo.model_validate(raw)

    dumped = repo.model_dump(by_alias=True)
    assert dumped["some_future_field"] == "added by later IP"


def test_commit_stats_defaults_are_empty_not_missing() -> None:
    stats = CommitStats()
    assert stats.profanity_hits == 0
    assert stats.emoji_top == {}
    assert stats.unique_authors == []


def test_code_analysis_nullable_linters() -> None:
    ca = CodeAnalysis()
    assert ca.ruff_issues is None
    assert ca.eslint_issues is None
    assert ca.loc_total == 0


def test_both_signals_present_in_commit_stats() -> None:
    """Guardrail for the two-signal invariant from PLAN.md."""
    fields = set(CommitStats.model_fields)
    assert {"profanity_hits", "profanity_rate"} <= fields
    assert {"emoji_hits", "emoji_rate", "emoji_commits", "emoji_top"} <= fields


def test_both_signals_present_in_code_analysis() -> None:
    fields = set(CodeAnalysis.model_fields)
    assert {
        "comment_profanity_hits",
        "identifier_profanity_hits",
    } <= fields
    assert {
        "comment_emoji_hits",
        "identifier_emoji_hits",
        "emoji_top",
    } <= fields
