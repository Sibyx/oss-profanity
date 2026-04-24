"""IP-009 smoke assertions — runs at the end of the smoke chain, exits 0/1.

Invoked by the ``assertions`` compose service after the worker profile
completes. Every PLAN.md bullet maps to one check here:

    1. ingest populated ≥ 100 repos
    2. ≥ 1 repo with IP-002 profanity signal
    3. ≥ 1 repo with IP-003 emoji signal
    4. ≥ 3 repos reached ``status="done"``
    5. every done repo has ``code_analysis.loc_total > 0`` AND
       ``code_analysis.comment_emoji_hits`` present (field presence, not value)
    6. every promoted repo carries a ``cohort`` label (IP-006 contract)

First line of defence before any read: refuse to run if the database name is
not literally ``profanity_smoke``. A misconfigured ``MONGO_URI`` pointing at
the operator's production ``profanity`` database would otherwise read
(not write, but still: surprising) from real data.

Output is one ``PASS``/``FAIL`` line per check. Exit code 0 if all pass, 1 if
any fail — ``docker compose up --exit-code-from assertions`` propagates this
to the shell wrapper as the smoke's verdict.
"""

from __future__ import annotations

import os
import sys
from typing import Any

from pymongo import MongoClient

_EXPECTED_DB = "profanity_smoke"


def main() -> int:
    uri = os.environ.get("MONGO_URI")
    if not uri:
        print("FAIL  safety: MONGO_URI not set", file=sys.stderr)
        return 1

    client: MongoClient[dict[str, Any]] = MongoClient(uri)
    try:
        db = client.get_default_database()
        if db.name != _EXPECTED_DB:
            print(
                f"FAIL  safety: expected database {_EXPECTED_DB!r}, got {db.name!r}",
                file=sys.stderr,
            )
            return 1

        checks: list[tuple[str, bool, str]] = []

        n_repos = db.repos.count_documents({})
        checks.append(
            ("ingest >= 100 repos", n_repos >= 100, f"{n_repos} repos")
        )

        n_prof = db.repos.count_documents(
            {"commit_stats.profanity_hits": {"$gt": 0}}
        )
        checks.append(
            (">= 1 profanity-hit repo", n_prof >= 1, f"{n_prof} repos")
        )

        n_emo = db.repos.count_documents(
            {"commit_stats.emoji_hits": {"$gt": 0}}
        )
        checks.append(
            (">= 1 emoji-hit repo", n_emo >= 1, f"{n_emo} repos")
        )

        n_done = db.repos.count_documents({"status": "done"})
        checks.append(
            (">= 3 done repos", n_done >= 3, f"{n_done} repos")
        )

        done_docs = list(db.repos.find({"status": "done"}))
        field_failures = [
            d["_id"]
            for d in done_docs
            if not (
                isinstance(d.get("code_analysis"), dict)
                and (d["code_analysis"].get("loc_total") or 0) > 0
                and "comment_emoji_hits" in d["code_analysis"]
            )
        ]
        checks.append(
            (
                "every done repo: loc_total>0 AND comment_emoji_hits set",
                not field_failures,
                f"{len(done_docs)} done docs; failures: {field_failures}"
                if field_failures
                else f"{len(done_docs)} done docs",
            )
        )

        promoted_filter = {
            "status": {"$in": ["pending", "claimed", "done", "failed"]}
        }
        promoted = list(
            db.repos.find(promoted_filter, projection={"_id": 1, "cohort": 1})
        )
        cohort_failures = [
            d["_id"]
            for d in promoted
            if d.get("cohort") not in ("profane", "clean")
        ]
        checks.append(
            (
                "every promoted repo has cohort label",
                not cohort_failures,
                f"{len(promoted)} promoted"
                if not cohort_failures
                else f"{len(promoted)} promoted; missing cohort on: {cohort_failures}",
            )
        )

        failed = 0
        for name, ok, detail in checks:
            status = "PASS" if ok else "FAIL"
            print(f"{status}  {name}  ({detail})")
            failed += int(not ok)

        if failed:
            print(f"\n{failed} check(s) failed", file=sys.stderr)
            return 1
        print("\nall checks passed")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())
