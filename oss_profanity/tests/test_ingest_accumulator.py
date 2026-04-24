"""Per-file aggregator + ``UpdateOne`` builder."""

from __future__ import annotations

from datetime import datetime, timezone

from oss_profanity.archive_ingest._accumulator import _PerFileAggregator


def _observe(
    agg: _PerFileAggregator,
    repo_id: int,
    *,
    repo_name: str = "alice/repo",
    author: str | None = "alice@example.com",
    language: str = "en",
    profanity_occurrences: list[str] | None = None,
    emoji_occurrences: list[str] | None = None,
    sample_message: str | None = None,
    sample_cap: int = 5,
) -> None:
    agg.observe(
        repo_id=repo_id,
        repo_name=repo_name,
        first_seen_at=datetime(2020, 6, 1, 12, tzinfo=timezone.utc),
        author=author,
        language=language,
        profanity_occurrences=profanity_occurrences or [],
        emoji_occurrences=emoji_occurrences or [],
        sample_message=sample_message,
        sample_cap=sample_cap,
    )


def test_single_observation_builds_one_upsert() -> None:
    agg = _PerFileAggregator()
    _observe(agg, 42, profanity_occurrences=["shit"], emoji_occurrences=["🚀"])
    ops = agg.to_bulk_ops(sample_cap=5)
    assert len(ops) == 1
    payload = ops[0]._doc  # type: ignore[attr-defined]
    inc = payload["$inc"]
    assert inc["commit_stats.total_commits_in_window"] == 1
    assert inc["commit_stats.profanity_hits"] == 1
    assert inc["commit_stats.profanity_top.shit"] == 1
    assert inc["commit_stats.emoji_hits"] == 1
    assert inc["commit_stats.emoji_commits"] == 1
    assert inc["commit_stats.emoji_top.🚀"] == 1
    assert inc["commit_stats.languages_detected.en"] == 1


def test_multiple_observations_same_repo_accumulate() -> None:
    agg = _PerFileAggregator()
    for _ in range(3):
        _observe(
            agg,
            42,
            profanity_occurrences=["shit", "damn"],
            emoji_occurrences=["🚀", "🐛"],
        )
    assert len(agg) == 1
    inc = agg.to_bulk_ops(sample_cap=5)[0]._doc["$inc"]  # type: ignore[attr-defined]
    assert inc["commit_stats.total_commits_in_window"] == 3
    assert inc["commit_stats.profanity_hits"] == 6
    assert inc["commit_stats.profanity_top.shit"] == 3
    assert inc["commit_stats.profanity_top.damn"] == 3
    assert inc["commit_stats.emoji_hits"] == 6
    assert inc["commit_stats.emoji_commits"] == 3
    assert inc["commit_stats.emoji_top.🚀"] == 3
    assert inc["commit_stats.emoji_top.🐛"] == 3


def test_profanity_top_accumulates_per_word() -> None:
    agg = _PerFileAggregator()
    _observe(agg, 1, profanity_occurrences=["shit", "damn"])
    _observe(agg, 1, profanity_occurrences=["shit"])
    inc = agg.to_bulk_ops(sample_cap=5)[0]._doc["$inc"]  # type: ignore[attr-defined]
    assert inc["commit_stats.profanity_hits"] == 3
    assert inc["commit_stats.profanity_top.shit"] == 2
    assert inc["commit_stats.profanity_top.damn"] == 1


def test_emoji_commits_only_counted_once_per_commit() -> None:
    agg = _PerFileAggregator()
    # One commit with 5 emoji → emoji_hits=5, emoji_commits=1.
    _observe(agg, 1, emoji_occurrences=["🚀", "🚀", "🐛", "✨", "🎉"])
    inc = agg.to_bulk_ops(sample_cap=5)[0]._doc["$inc"]  # type: ignore[attr-defined]
    assert inc["commit_stats.emoji_hits"] == 5
    assert inc["commit_stats.emoji_commits"] == 1


def test_observation_without_emoji_does_not_increment_emoji_commits() -> None:
    agg = _PerFileAggregator()
    _observe(agg, 1)
    inc = agg.to_bulk_ops(sample_cap=5)[0]._doc["$inc"]  # type: ignore[attr-defined]
    assert inc["commit_stats.emoji_commits"] == 0
    assert inc["commit_stats.emoji_hits"] == 0


def test_authors_deduplicated_via_set() -> None:
    agg = _PerFileAggregator()
    _observe(agg, 1, author="alice@ex.com")
    _observe(agg, 1, author="alice@ex.com")
    _observe(agg, 1, author="bob@ex.com")
    ops = agg.to_bulk_ops(sample_cap=5)
    add_to_set = ops[0]._doc["$addToSet"]["commit_stats.unique_authors"]["$each"]  # type: ignore[attr-defined]
    assert add_to_set == ["alice@ex.com", "bob@ex.com"]


def test_no_authors_means_no_addtoset_clause() -> None:
    agg = _PerFileAggregator()
    _observe(agg, 1, author=None)
    ops = agg.to_bulk_ops(sample_cap=5)
    payload = ops[0]._doc  # type: ignore[attr-defined]
    assert "$addToSet" not in payload


def test_sample_profane_capped_at_sample_cap() -> None:
    agg = _PerFileAggregator()
    for i in range(10):
        _observe(
            agg,
            1,
            profanity_occurrences=["shit"],
            sample_message=f"profane message {i}",
            sample_cap=3,
        )
    ops = agg.to_bulk_ops(sample_cap=3)
    # First op is the upsert; second is the $push with guard.
    assert len(ops) == 2
    push_op = ops[1]._doc  # type: ignore[attr-defined]
    pushed = push_op["$push"]["commit_stats.sample_profane_messages"]["$each"]
    assert len(pushed) == 3
    # Guard path: the $push only fires when index (cap-1) does not exist.
    assert ops[1]._filter[  # type: ignore[attr-defined]
        "commit_stats.sample_profane_messages.2"
    ] == {"$exists": False}


def test_no_sample_push_when_no_profane_messages() -> None:
    agg = _PerFileAggregator()
    _observe(agg, 1, profanity_occurrences=[], sample_message=None)
    ops = agg.to_bulk_ops(sample_cap=5)
    assert len(ops) == 1


def test_different_repos_emit_separate_upserts() -> None:
    agg = _PerFileAggregator()
    _observe(agg, 1, repo_name="a/a")
    _observe(agg, 2, repo_name="b/b")
    _observe(agg, 3, repo_name="c/c")
    ops = agg.to_bulk_ops(sample_cap=5)
    ids = {op._filter["_id"] for op in ops}  # type: ignore[attr-defined]
    assert ids == {1, 2, 3}


def test_languages_counter_accumulates() -> None:
    agg = _PerFileAggregator()
    _observe(agg, 1, language="en")
    _observe(agg, 1, language="en")
    _observe(agg, 1, language="ru")
    inc = agg.to_bulk_ops(sample_cap=5)[0]._doc["$inc"]  # type: ignore[attr-defined]
    assert inc["commit_stats.languages_detected.en"] == 2
    assert inc["commit_stats.languages_detected.ru"] == 1


def test_empty_aggregator_emits_nothing() -> None:
    agg = _PerFileAggregator()
    assert agg.to_bulk_ops(sample_cap=5) == []
    assert len(agg) == 0


def test_upsert_true_on_main_op() -> None:
    agg = _PerFileAggregator()
    _observe(agg, 1)
    op = agg.to_bulk_ops(sample_cap=5)[0]
    # Private attribute access — we rely on pymongo's UpdateOne
    # construction detail for the contract check.
    assert op._upsert is True  # type: ignore[attr-defined]
