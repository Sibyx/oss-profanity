"""Pure-Python ingest helpers: URL/date arithmetic and bot detection."""

from __future__ import annotations

import pytest

from oss_profanity.archive_ingest._bot import is_bot
from oss_profanity.archive_ingest._urls import (
    format_file_id,
    iter_file_ids,
    parse_file_id,
    url_for,
)


# ---------- _urls ----------


def test_parse_and_format_are_inverse() -> None:
    dt = parse_file_id("2020-06-15-12")
    assert format_file_id(dt) == "2020-06-15-12"


def test_parse_accepts_single_digit_hour() -> None:
    dt = parse_file_id("2020-06-01-0")
    assert dt.hour == 0


def test_url_for_uses_non_padded_hour() -> None:
    """GH Archive serves 2020-06-01-0.json.gz (not -00); HEAD confirms."""
    assert (
        url_for("2020-06-01-00")
        == "https://data.gharchive.org/2020-06-01-0.json.gz"
    )
    assert (
        url_for("2020-06-15-12")
        == "https://data.gharchive.org/2020-06-15-12.json.gz"
    )


def test_iter_file_ids_is_chronological_and_inclusive() -> None:
    ids = list(iter_file_ids("2020-06-01-00", "2020-06-01-02"))
    assert ids == ["2020-06-01-00", "2020-06-01-01", "2020-06-01-02"]


def test_iter_file_ids_crosses_day_boundary() -> None:
    ids = list(iter_file_ids("2020-06-30-22", "2020-07-01-01"))
    assert ids == [
        "2020-06-30-22",
        "2020-06-30-23",
        "2020-07-01-00",
        "2020-07-01-01",
    ]


def test_iter_file_ids_rejects_inverted_range() -> None:
    with pytest.raises(ValueError):
        list(iter_file_ids("2020-06-02-00", "2020-06-01-00"))


def test_iter_file_ids_single_hour_range() -> None:
    ids = list(iter_file_ids("2020-06-01-00", "2020-06-01-00"))
    assert ids == ["2020-06-01-00"]


def test_parse_file_id_rejects_malformed() -> None:
    for bad in ["", "2020-06-01", "2020-06-01-X", "2020-6-1-0", "not-a-date"]:
        with pytest.raises(ValueError):
            parse_file_id(bad)


def test_file_ids_sort_lexicographically_same_as_chronologically() -> None:
    """Zero-padding matters — lexical sort must match chronological sort."""
    ids = list(iter_file_ids("2020-06-01-00", "2020-06-03-23"))
    assert sorted(ids) == ids


# ---------- _bot ----------


def test_bot_actor_type_overrides_everything() -> None:
    assert is_bot("alice", actor_type="Bot") is True


@pytest.mark.parametrize(
    "login",
    [
        "dependabot[bot]",
        "renovate[bot]",
        "github-actions[bot]",
        "Anything[bot]",
    ],
)
def test_bot_suffix_catches_github_apps(login: str) -> None:
    assert is_bot(login) is True


@pytest.mark.parametrize(
    "login",
    [
        "dependabot",
        "renovate-bot",
        "snyk-bot",
        "scala-steward",
        "imgbot",
        "pyup-bot",
        "mergify",
    ],
)
def test_bot_extended_frozenset(login: str) -> None:
    assert is_bot(login) is True


def test_bot_case_insensitive_on_frozenset() -> None:
    assert is_bot("Dependabot") is True
    assert is_bot("RENOVATE-BOT") is True


def test_bot_regex_catches_config_pattern() -> None:
    # config.bot_regex default includes "bot"; any login containing
    # "bot" matches.
    assert is_bot("ci-bot-agent") is True


def test_human_login_is_not_bot() -> None:
    assert is_bot("alice") is False
    assert is_bot("jakub.dubec") is False


def test_none_login_is_not_bot() -> None:
    assert is_bot(None) is False
    assert is_bot("") is False
