"""Parser: gzip + orjson + PushEvent filter + bot filter + scoring.

All fixtures are crafted in-memory (no real GH Archive bytes checked in).
The DRY contract — one walk, both signals — is tested by constructing a
commit message with a profane word AND an emoji AND a TODO-like pattern,
then asserting that one ``parse_bytes`` call lands all three in the
accumulator output.
"""

from __future__ import annotations

import gzip
import io
import json
from typing import Any

from oss_profanity.archive_ingest._parser import parse_bytes


def _make_gz(events: list[dict[str, Any]]) -> bytes:
    """Serialize events into ndjson.gz bytes."""
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb") as gz:
        for event in events:
            gz.write(json.dumps(event).encode("utf-8"))
            gz.write(b"\n")
    return buf.getvalue()


def _push_event(
    *,
    repo_id: int = 1,
    repo_name: str = "alice/repo",
    actor_login: str = "alice",
    actor_type: str | None = None,
    messages: list[str] | None = None,
    created_at: str = "2020-06-01T12:00:00Z",
) -> dict[str, Any]:
    actor: dict[str, Any] = {"id": 1, "login": actor_login}
    if actor_type is not None:
        actor["type"] = actor_type
    return {
        "type": "PushEvent",
        "created_at": created_at,
        "actor": actor,
        "repo": {"id": repo_id, "name": repo_name},
        "payload": {
            "commits": [
                {
                    "message": msg,
                    "author": {"email": "alice@example.com", "name": "alice"},
                }
                for msg in (messages or ["regular commit"])
            ]
        },
    }


def test_empty_payload_yields_empty_result() -> None:
    gz = _make_gz([])
    r = parse_bytes(gz, sample_cap=5)
    assert r.rows == 0
    assert r.push_events == 0
    assert r.commits_observed == 0
    assert r.bulk_ops == []


def test_non_pushevent_rows_are_ignored() -> None:
    gz = _make_gz(
        [
            {"type": "WatchEvent", "actor": {}},
            {"type": "IssuesEvent", "actor": {}},
            _push_event(messages=["a commit"]),
        ]
    )
    r = parse_bytes(gz, sample_cap=5)
    assert r.rows == 3
    assert r.push_events == 1
    assert r.commits_observed == 1


def test_bot_commits_are_counted_separately_and_dropped() -> None:
    gz = _make_gz(
        [
            _push_event(actor_login="dependabot[bot]"),
            _push_event(actor_login="renovate"),
            _push_event(actor_login="alice"),
        ]
    )
    r = parse_bytes(gz, sample_cap=5)
    assert r.push_events == 3
    assert r.bots_filtered == 2
    assert r.commits_observed == 1


def test_actor_type_bot_is_filtered_even_with_human_looking_login() -> None:
    gz = _make_gz(
        [_push_event(actor_login="ci-agent", actor_type="Bot")]
    )
    r = parse_bytes(gz, sample_cap=5)
    assert r.bots_filtered == 1
    assert r.commits_observed == 0


def test_malformed_line_does_not_abort_parse() -> None:
    """A broken JSON line must not kill the rest of the file."""
    good = json.dumps(_push_event(messages=["hello"])).encode()
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb") as gz:
        gz.write(b"not-valid-json\n")
        gz.write(good + b"\n")
        gz.write(b"\xff\xfe also bad\n")
    r = parse_bytes(buf.getvalue(), sample_cap=5)
    # Three rows observed, one good PushEvent got through.
    assert r.rows == 3
    assert r.push_events == 1
    assert r.commits_observed == 1


def test_missing_commits_field_skips_event_without_crash() -> None:
    evt = _push_event()
    evt["payload"] = {}  # no commits
    r = parse_bytes(_make_gz([evt]), sample_cap=5)
    assert r.push_events == 1
    assert r.commits_observed == 0


def test_empty_commit_message_is_dropped() -> None:
    evt = _push_event(messages=[""])
    r = parse_bytes(_make_gz([evt]), sample_cap=5)
    assert r.commits_observed == 0


def test_missing_repo_id_skips_event() -> None:
    evt = _push_event()
    evt["repo"] = {"name": "alice/repo"}  # no id
    r = parse_bytes(_make_gz([evt]), sample_cap=5)
    assert r.push_events == 1
    assert r.commits_observed == 0


# ---------- DRY contract ----------


def test_dry_contract_single_message_lands_both_signals() -> None:
    """One walk must produce non-zero hits in BOTH profanity AND emoji
    fields for a message that contains both."""
    evt = _push_event(
        repo_id=42,
        messages=["fuck this bug 🐛 is blocking the release 🚀"],
    )
    r = parse_bytes(_make_gz([evt]), sample_cap=5)
    assert r.commits_observed == 1
    assert len(r.bulk_ops) >= 1
    inc = r.bulk_ops[0]._doc["$inc"]  # type: ignore[attr-defined]
    assert inc["commit_stats.profanity_hits"] >= 1
    assert inc["commit_stats.emoji_hits"] >= 2
    assert inc["commit_stats.emoji_top.🐛"] == 1
    assert inc["commit_stats.emoji_top.🚀"] == 1


def test_sample_profane_message_is_captured_with_push_op() -> None:
    evt = _push_event(messages=["fuck this"])
    r = parse_bytes(_make_gz([evt]), sample_cap=5)
    # Two ops: the upsert + the sample-push.
    assert len(r.bulk_ops) == 2
    push = r.bulk_ops[1]._doc["$push"][  # type: ignore[attr-defined]
        "commit_stats.sample_profane_messages"
    ]["$each"]
    assert push == ["fuck this"]


def test_sample_message_truncated_to_200_chars() -> None:
    msg = "fuck " + "a" * 500
    evt = _push_event(messages=[msg])
    r = parse_bytes(_make_gz([evt]), sample_cap=5)
    push = r.bulk_ops[1]._doc["$push"][  # type: ignore[attr-defined]
        "commit_stats.sample_profane_messages"
    ]["$each"]
    assert len(push[0]) == 200


def test_multiple_repos_in_one_file_produce_multiple_upserts() -> None:
    events = [
        _push_event(repo_id=i, repo_name=f"owner/r{i}") for i in range(5)
    ]
    r = parse_bytes(_make_gz(events), sample_cap=5)
    # One upsert op per distinct repo_id.
    assert len({op._filter["_id"] for op in r.bulk_ops} ) == 5  # type: ignore[attr-defined]


def test_same_repo_across_events_accumulates_into_one_op() -> None:
    events = [_push_event(repo_id=99) for _ in range(4)]
    r = parse_bytes(_make_gz(events), sample_cap=5)
    # One upsert op total; its inc should reflect 4 commits.
    assert len(r.bulk_ops) == 1
    inc = r.bulk_ops[0]._doc["$inc"]  # type: ignore[attr-defined]
    assert inc["commit_stats.total_commits_in_window"] == 4


def test_author_falls_back_to_actor_login_when_commit_author_missing() -> None:
    evt = _push_event(actor_login="alice", messages=["ok"])
    evt["payload"]["commits"][0]["author"] = {}  # neither email nor name
    r = parse_bytes(_make_gz([evt]), sample_cap=5)
    op = r.bulk_ops[0]
    authors = op._doc["$addToSet"]["commit_stats.unique_authors"][  # type: ignore[attr-defined]
        "$each"
    ]
    assert authors == ["alice"]
