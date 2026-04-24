"""Unit tests for the Pydantic schema — round-trip and edge cases."""

from __future__ import annotations

from datetime import datetime, timezone

from oss_profanity.db import CodeAnalysis, CommitStats, GitHubMetadata, Repo


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


# ---------- GitHubMetadata (IP-007) ----------


def test_github_metadata_defaults() -> None:
    meta = GitHubMetadata(fetched_at=datetime.now(timezone.utc))

    assert meta.stargazers_count == 0
    assert meta.topics == []
    assert meta.languages_bytes == {}
    assert meta.archived is False
    assert meta.disabled is False


def test_github_metadata_full_roundtrip() -> None:
    now = datetime.now(timezone.utc)
    meta = GitHubMetadata(
        fetched_at=now,
        stargazers_count=1234,
        forks_count=56,
        watchers_count=1234,
        subscribers_count=42,
        open_issues_count=7,
        topics=["cli", "python"],
        license_spdx="MIT",
        language="Python",
        languages_bytes={"Python": 15000, "Shell": 200},
        size_kb=512,
        default_branch="main",
        fork=False,
        parent_full_name=None,
        archived=False,
        disabled=False,
        created_at=now,
        pushed_at=now,
        updated_at=now,
        description="A test repo",
    )
    dumped = meta.model_dump(mode="json")

    rehydrated = GitHubMetadata.model_validate(dumped)
    assert rehydrated == meta


def test_repo_github_metadata_optional() -> None:
    raw = {
        "_id": 99,
        "full_name": "acme/widget",
        "first_seen_at": datetime.now(timezone.utc),
    }
    repo = Repo.model_validate(raw)

    assert repo.github_metadata is None


def test_repo_github_metadata_roundtrip() -> None:
    now = datetime.now(timezone.utc)
    raw = {
        "_id": 42,
        "full_name": "foo/bar",
        "first_seen_at": now,
        "github_metadata": {
            "fetched_at": now,
            "stargazers_count": 10,
            "languages_bytes": {"Python": 1234},
        },
    }
    repo = Repo.model_validate(raw)

    assert repo.github_metadata is not None
    assert repo.github_metadata.stargazers_count == 10
    assert repo.github_metadata.languages_bytes == {"Python": 1234}


def test_github_metadata_absorbs_unknown_fields() -> None:
    """Shape drift on GitHub's side must not break the model."""
    meta = GitHubMetadata.model_validate(
        {
            "fetched_at": datetime.now(timezone.utc),
            "brand_new_field_from_the_future": "some value",
        }
    )
    dumped = meta.model_dump(mode="json")
    assert dumped["brand_new_field_from_the_future"] == "some value"
