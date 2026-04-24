"""Per-file, per-repo aggregator + ``UpdateOne`` builder.

The parser walks one hourly file and calls :meth:`_PerFileAggregator.observe`
once per surviving commit. When the file is exhausted,
:meth:`_PerFileAggregator.to_bulk_ops` produces the ``UpdateOne`` batch
that the upserter flushes via ``bulk_write(ordered=False)``.

Aggregating within one file — instead of per-commit upserts as DRAFT
originally suggested — cuts MongoDB round-trips by 2–10× (each file has
roughly ~54K commits across ~5–20K distinct repos). The upsert math is
identical because ``$inc`` and ``$addToSet`` are both associative.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from pymongo import UpdateOne


@dataclass(slots=True)
class _RepoUpdate:
    """Rolling accumulator for one repo's contribution from one file."""

    full_name: str
    first_seen_at: datetime
    total_commits: int = 0
    profanity_hits: int = 0
    emoji_hits: int = 0
    emoji_commits: int = 0
    authors: set[str] = field(default_factory=set)
    languages: Counter[str] = field(default_factory=Counter)
    profanity_top: Counter[str] = field(default_factory=Counter)
    emoji_top: Counter[str] = field(default_factory=Counter)
    sample_profane: list[str] = field(default_factory=list)


class _PerFileAggregator:
    """Mutable ``dict[repo_id, _RepoUpdate]``; the parser's write target.

    Order-of-observation is preserved by keeping the first ``first_seen_at``
    we see for a repo within the file; subsequent commits accumulate into
    the same entry.
    """

    __slots__ = ("_items",)

    def __init__(self) -> None:
        self._items: dict[int, _RepoUpdate] = {}

    def __len__(self) -> int:
        return len(self._items)

    def observe(
        self,
        *,
        repo_id: int,
        repo_name: str,
        first_seen_at: datetime,
        author: str | None,
        language: str,
        profanity_occurrences: Iterable[str],
        emoji_occurrences: Iterable[str],
        sample_message: str | None,
        sample_cap: int,
    ) -> None:
        upd = self._items.get(repo_id)
        if upd is None:
            upd = _RepoUpdate(
                full_name=repo_name, first_seen_at=first_seen_at
            )
            self._items[repo_id] = upd
        upd.total_commits += 1
        prof_list = list(profanity_occurrences)
        upd.profanity_hits += len(prof_list)
        if prof_list:
            upd.profanity_top.update(prof_list)
        emo_list = list(emoji_occurrences)
        upd.emoji_hits += len(emo_list)
        if emo_list:
            upd.emoji_commits += 1
            upd.emoji_top.update(emo_list)
        if author:
            upd.authors.add(author)
        upd.languages[language] += 1
        if sample_message and len(upd.sample_profane) < sample_cap:
            upd.sample_profane.append(sample_message)

    def to_bulk_ops(self, sample_cap: int) -> list[UpdateOne]:
        """Emit one or two ``UpdateOne`` per repo in insertion order.

        Separate ``UpdateOne`` for the sample-message push because
        ``$push`` shares an array target with ``$addToSet`` semantics
        that MongoDB forbids combining in a single update.
        """
        ops: list[UpdateOne] = []
        for repo_id, upd in self._items.items():
            inc_fields: dict[str, int] = {
                "commit_stats.total_commits_in_window": upd.total_commits,
                "commit_stats.profanity_hits": upd.profanity_hits,
                "commit_stats.emoji_hits": upd.emoji_hits,
                "commit_stats.emoji_commits": upd.emoji_commits,
            }
            for lang, count in upd.languages.items():
                inc_fields[f"commit_stats.languages_detected.{lang}"] = count
            for word, count in upd.profanity_top.items():
                inc_fields[f"commit_stats.profanity_top.{word}"] = count
            for glyph, count in upd.emoji_top.items():
                inc_fields[f"commit_stats.emoji_top.{glyph}"] = count

            update_doc: dict[str, Any] = {
                "$setOnInsert": {
                    "full_name": upd.full_name,
                    "first_seen_at": upd.first_seen_at,
                    "status": "seen",
                },
                "$inc": inc_fields,
            }
            if upd.authors:
                update_doc["$addToSet"] = {
                    "commit_stats.unique_authors": {
                        "$each": sorted(upd.authors)
                    },
                }
            ops.append(
                UpdateOne({"_id": repo_id}, update_doc, upsert=True)
            )

            if upd.sample_profane:
                ops.append(
                    UpdateOne(
                        {
                            "_id": repo_id,
                            f"commit_stats.sample_profane_messages.{sample_cap - 1}": {
                                "$exists": False
                            },
                        },
                        {
                            "$push": {
                                "commit_stats.sample_profane_messages": {
                                    "$each": upd.sample_profane,
                                    "$slice": sample_cap,
                                }
                            }
                        },
                    )
                )
        return ops
