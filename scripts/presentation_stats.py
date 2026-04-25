"""IP-011: generate ``presentation/opencamp/stats.json`` from the live Mongo.

Five aggregations, one JSON blob, one command. Runs in ~15 s against the
~3.7 M-doc ``repos`` collection. Every numeric slide in the OpenCamp deck
traces back to a key in the produced file.

Curated commit-message samples are hand-maintained in this module (the
grandma filter is a human) — see IP-011 Review Question Q2 resolution.

Usage::

    # Write JSON to stdout (pipe or redirect):
    python -m scripts.presentation_stats --json > presentation/opencamp/stats.json

    # Print a summary to the terminal (no JSON):
    python -m scripts.presentation_stats
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

from pymongo.database import Database

from oss_profanity.db import get_db

logger = logging.getLogger("presentation_stats")


# Hand-picked in-module per IP-011 Q2 resolution. Three universal,
# PG-13, no-author/no-repo-attribution commit messages drawn from a
# 50-row sample of profane-rated repos during proposal drafting.
_CURATED_SAMPLES: list[dict[str, str]] = [
    {"msg": "fuck mono"},
    {"msg": "i fucking hate git sometimes"},
    {"msg": "Fuck emojis.  You heard me."},
]


def _ingest_summary(db: Database[dict[str, Any]]) -> dict[str, Any]:
    """Per-status row counts + totals for the hero numbers in Act V."""
    pipeline: list[dict[str, Any]] = [
        {
            "$group": {
                "_id": "$status",
                "n": {"$sum": 1},
                "total_commits": {
                    "$sum": "$commit_stats.total_commits_in_window"
                },
                "total_profanity": {"$sum": "$commit_stats.profanity_hits"},
                "total_emoji": {"$sum": "$commit_stats.emoji_hits"},
            }
        },
        {"$sort": {"n": -1}},
    ]
    rows = list(db.repos.aggregate(pipeline))
    return {
        "by_status": rows,
        "total_repos": sum(int(r["n"]) for r in rows),
        "total_commits": sum(int(r["total_commits"]) for r in rows),
        "total_profanity": sum(int(r["total_profanity"]) for r in rows),
        "total_emoji": sum(int(r["total_emoji"]) for r in rows),
    }


def _top_profanity(
    db: Database[dict[str, Any]], n: int = 30
) -> list[dict[str, Any]]:
    """Top-N profanity words across all scored repos (unfiltered)."""
    pipeline: list[dict[str, Any]] = [
        {"$match": {"commit_stats.profanity_hits": {"$gte": 1}}},
        {
            "$project": {
                "words": {"$objectToArray": "$commit_stats.profanity_top"}
            }
        },
        {"$unwind": "$words"},
        {"$group": {"_id": "$words.k", "n": {"$sum": "$words.v"}}},
        {"$sort": {"n": -1}},
        {"$limit": n},
    ]
    return [
        {"word": r["_id"], "n": int(r["n"])}
        for r in db.repos.aggregate(pipeline)
    ]


def _top_emoji(
    db: Database[dict[str, Any]], n: int = 30
) -> list[dict[str, Any]]:
    """Top-N emoji glyphs across all scored repos."""
    pipeline: list[dict[str, Any]] = [
        {"$match": {"commit_stats.emoji_hits": {"$gte": 1}}},
        {
            "$project": {
                "emoji": {"$objectToArray": "$commit_stats.emoji_top"}
            }
        },
        {"$unwind": "$emoji"},
        {"$group": {"_id": "$emoji.k", "n": {"$sum": "$emoji.v"}}},
        {"$sort": {"n": -1}},
        {"$limit": n},
    ]
    return [
        {"emoji": r["_id"], "n": int(r["n"])}
        for r in db.repos.aggregate(pipeline)
    ]


def _cohort_languages(
    db: Database[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Per-cohort primary-language histogram for the 1,500-repo subset."""
    pipeline: list[dict[str, Any]] = [
        {"$match": {"cohort": {"$in": ["profane", "clean"]}}},
        {
            "$group": {
                "_id": {
                    "lang": "$github_metadata.language",
                    "cohort": "$cohort",
                },
                "n": {"$sum": 1},
            }
        },
        {"$sort": {"n": -1}},
    ]
    return [
        {
            "language": r["_id"].get("lang"),
            "cohort": r["_id"]["cohort"],
            "n": int(r["n"]),
        }
        for r in db.repos.aggregate(pipeline)
    ]


def _curated_samples() -> list[dict[str, str]]:
    """Hand-picked commit-message quotes for Slide 47."""
    return list(_CURATED_SAMPLES)


def collect(db: Database[dict[str, Any]]) -> dict[str, Any]:
    """Run all five aggregations and bundle them with a timestamp."""
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ingest": _ingest_summary(db),
        "top_profanity": _top_profanity(db),
        "top_emoji": _top_emoji(db),
        "cohort_languages": _cohort_languages(db),
        "samples": _curated_samples(),
    }


def _print_summary(payload: dict[str, Any]) -> None:
    ingest = payload["ingest"]
    print(f"generated_at:     {payload['generated_at']}")
    print(f"total_repos:      {ingest['total_repos']:>12,}")
    print(f"total_commits:    {ingest['total_commits']:>12,}")
    print(f"total_profanity:  {ingest['total_profanity']:>12,}")
    print(f"total_emoji:      {ingest['total_emoji']:>12,}")
    print()
    print("top-10 profanity words:")
    for row in payload["top_profanity"][:10]:
        print(f"  {row['word']:<20} {row['n']:>8,}")
    print()
    print("top-10 emoji:")
    for row in payload["top_emoji"][:10]:
        print(f"  {row['emoji']:<8} {row['n']:>8,}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate IP-011 presentation stats from the live Mongo"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Write JSON to stdout (otherwise: human-readable summary)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    db = get_db()
    payload = collect(db)

    if args.json:
        json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        _print_summary(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
