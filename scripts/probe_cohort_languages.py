"""Probe GitHub metadata for the Stage 3 cohort.

Before committing 5–7 hours of Stage 4 worker time to analyze a cohort whose
language composition we don't yet know, this script hits GitHub REST for each
``status="pending"`` repo (plus any already-``claimed`` / ``done`` / ``failed``
cohort members to keep the histogram complete) and stores the result on
``repos.github_metadata``.

Reuses ``oss_profanity.repo_worker._github`` so rate-limit discipline, retries,
and authentication are identical to what IP-007 uses in production. A repo
fetched here will not be re-fetched by IP-007 later — the worker's ``_processor``
only re-fetches when ``github_metadata`` is unset — so this probe doubles as a
Stage 4 warm-up.

Usage::

    # Probe every unseen pending repo (idempotent; skips already-probed rows):
    python -m scripts.probe_cohort_languages

    # Just print the histogram without fetching:
    python -m scripts.probe_cohort_languages --summary-only

    # Re-fetch every cohort repo (slow; only needed after a GitHub schema change):
    python -m scripts.probe_cohort_languages --refetch

    # Probe at most N repos (for smoke-checking the script):
    python -m scripts.probe_cohort_languages --limit 20

Requires ``MONGO_URI`` + ``GITHUB_TOKEN`` in the environment. Without a token the
rate limit drops to 60/hour, which is useless for the 1,500-repo cohort.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from pymongo.database import Database

from oss_profanity.db import get_db
from oss_profanity.repo_worker import _github

logger = logging.getLogger("probe_cohort_languages")


# Tool coverage by GitHub's canonical language name (what `/repos/{full_name}`
# returns). Keys match the ``language`` field case exactly. A given repo's
# primary language is the `language` string; a missing value (null) happens
# for repos GitHub cannot classify.
_RUFF_BANDIT_LANGS: frozenset[str] = frozenset({"Python"})
_ESLINT_LANGS: frozenset[str] = frozenset({"JavaScript", "TypeScript"})
_LIZARD_LANGS: frozenset[str] = frozenset(
    {
        "Python",
        "JavaScript",
        "TypeScript",
        "Java",
        "C",
        "C++",
        "C#",
        "Objective-C",
        "Ruby",
        "PHP",
        "Scala",
        "Go",
        "Lua",
        "Rust",
        "Swift",
        "Fortran",
        "Kotlin",
    }
)
_TREE_SITTER_LANGS: frozenset[str] = _LIZARD_LANGS | frozenset(
    {
        "Shell",
        "R",
        "Perl",
        "Haskell",
        "OCaml",
        "Elixir",
        "Erlang",
        "Dart",
        "Julia",
        "Groovy",
        "Clojure",
    }
)


def _cohort_query(refetch: bool) -> dict[str, Any]:
    base: dict[str, Any] = {
        "status": {"$in": ["pending", "claimed", "done", "failed"]},
        "cohort": {"$in": ["profane", "clean"]},
    }
    if refetch:
        return base
    base["github_metadata.fetched_at"] = {"$exists": False}
    return base


def _probe_one(db: Database[dict[str, Any]], doc: dict[str, Any]) -> bool:
    """Fetch metadata + languages for one repo; returns True on success."""
    full_name = doc["full_name"]
    meta = _github.fetch_metadata(full_name)
    if meta is None:
        db.repos.update_one(
            {"_id": doc["_id"]},
            {
                "$set": {
                    "github_metadata_probe_missing_at": datetime.now(
                        timezone.utc
                    )
                }
            },
        )
        return False

    languages = _github.fetch_languages(full_name) or {}
    meta.languages_bytes = languages
    db.repos.update_one(
        {"_id": doc["_id"]},
        {
            "$set": {
                "github_metadata": meta.model_dump(mode="json"),
            },
            "$unset": {"github_metadata_probe_missing_at": ""},
        },
    )
    return True


def _probe_all(
    db: Database[dict[str, Any]], refetch: bool, limit: int | None
) -> tuple[int, int]:
    query = _cohort_query(refetch)
    projection = {"_id": 1, "full_name": 1, "cohort": 1}
    cursor = db.repos.find(query, projection=projection)
    todo: list[dict[str, Any]] = list(cursor)
    if limit is not None:
        todo = todo[:limit]

    already_probed = db.repos.count_documents(
        {
            "status": {"$in": ["pending", "claimed", "done", "failed"]},
            "cohort": {"$in": ["profane", "clean"]},
            "github_metadata.fetched_at": {"$exists": True},
        }
    )
    total = len(todo)
    logger.info(
        "probe: %d cohort repos to fetch; %d already probed",
        total,
        already_probed,
    )
    if total == 0:
        return (0, 0)

    fetched = 0
    missing = 0
    start_t = time.monotonic()
    try:
        for i, doc in enumerate(todo, 1):
            ok = _probe_one(db, doc)
            if ok:
                fetched += 1
            else:
                missing += 1
            if i % 25 == 0 or i == total:
                elapsed = time.monotonic() - start_t
                rate_min = (i / elapsed) * 60.0 if elapsed > 0 else 0.0
                logger.info(
                    "probe %d/%d  (%.0f req/min; %d fetched, %d missing)",
                    i,
                    total,
                    rate_min,
                    fetched,
                    missing,
                )
    except KeyboardInterrupt:
        logger.warning("probe: interrupted; progress saved — rerun to resume")
    return (fetched, missing)


def _print_summary(db: Database[dict[str, Any]]) -> None:
    cursor = db.repos.find(
        {
            "status": {"$in": ["pending", "claimed", "done", "failed"]},
            "cohort": {"$in": ["profane", "clean"]},
        },
        projection={
            "cohort": 1,
            "github_metadata.language": 1,
            "github_metadata_probe_missing_at": 1,
        },
    )
    counts: dict[str, Counter[str]] = {
        "profane": Counter(),
        "clean": Counter(),
    }
    missing = 0
    not_probed = 0
    for d in cursor:
        cohort = d.get("cohort")
        if cohort not in ("profane", "clean"):
            continue
        gm = d.get("github_metadata") or {}
        if not gm:
            if d.get("github_metadata_probe_missing_at"):
                missing += 1
            else:
                not_probed += 1
            counts[cohort]["<not-probed>" if not d.get(
                "github_metadata_probe_missing_at"
            ) else "<missing>"] += 1
            continue
        lang = gm.get("language") or "<null>"
        counts[cohort][lang] += 1

    all_langs = sorted(set(counts["profane"]) | set(counts["clean"]))
    all_langs.sort(
        key=lambda lang: -(counts["profane"][lang] + counts["clean"][lang])
    )

    print()
    print("=" * 62)
    print("Primary-language histogram by cohort")
    print("=" * 62)
    print(f"{'Language':<24} {'profane':>10} {'clean':>10} {'total':>10}")
    print("-" * 62)
    for lang in all_langs:
        p = counts["profane"][lang]
        c = counts["clean"][lang]
        print(f"{lang:<24} {p:>10} {c:>10} {p + c:>10}")
    total_p = sum(counts["profane"].values())
    total_c = sum(counts["clean"].values())
    print("-" * 62)
    print(
        f"{'TOTAL':<24} {total_p:>10} {total_c:>10} {total_p + total_c:>10}"
    )

    combined: Counter[str] = counts["profane"] + counts["clean"]
    total = sum(combined.values())
    if total == 0:
        return

    ruff_n = sum(
        n for lang, n in combined.items() if lang in _RUFF_BANDIT_LANGS
    )
    eslint_n = sum(
        n for lang, n in combined.items() if lang in _ESLINT_LANGS
    )
    lizard_n = sum(
        n for lang, n in combined.items() if lang in _LIZARD_LANGS
    )
    ts_n = sum(
        n for lang, n in combined.items() if lang in _TREE_SITTER_LANGS
    )
    python_js = ruff_n + eslint_n
    null_lang = combined.get("<null>", 0)
    not_probed_combined = combined.get("<not-probed>", 0)

    def pct(n: int) -> str:
        return f"{n:4d}  ({100.0 * n / total:5.1f} %)"

    print()
    print("=" * 62)
    print(
        f"Tool coverage over {total} cohort repos "
        f"(profane + clean combined)"
    )
    print("=" * 62)
    print(f"  ruff + bandit (Python)     : {pct(ruff_n)}")
    print(f"  eslint (JavaScript/TS)     : {pct(eslint_n)}")
    print(f"  Python + JS/TS subtotal    : {pct(python_js)}  <-- decision line")
    print(f"  lizard-supported           : {pct(lizard_n)}")
    print(f"  tree-sitter source scan    : {pct(ts_n)}")
    print(f"  null language (GitHub)     : {pct(null_lang)}")
    if not_probed_combined:
        print(f"  not yet probed             : {pct(not_probed_combined)}")
    if missing:
        print(f"  deleted / 404 on GitHub    : {missing}")
    print()
    print(
        "Guidance: Python + JS/TS  >= 40 %  -> proceed with current cohort;\n"
        "          Python + JS/TS  >= 20 %  -> proceed, report ruff/eslint on the subset;\n"
        "          Python + JS/TS  <  20 %  -> consider re-sampling with language stratification."
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Probe GitHub metadata for the Stage 3 cohort"
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Skip fetching; just print the current histogram",
    )
    parser.add_argument(
        "--refetch",
        action="store_true",
        help=(
            "Re-fetch repos that already have github_metadata set "
            "(normally skipped)"
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Probe at most N repos (useful for smoke-checking the script)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    db = get_db()
    if not args.summary_only:
        fetched, missing = _probe_all(db, args.refetch, args.limit)
        logger.info("probe: done — %d fetched, %d missing", fetched, missing)
    _print_summary(db)
    return 0


if __name__ == "__main__":
    sys.exit(main())
