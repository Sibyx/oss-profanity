"""Config module tests — env parsing, defaults, required vars.

Every test constructs a fresh ``Config`` via ``Config.from_env()`` after
monkeypatching the environment. We deliberately avoid ``importlib.reload``:
other modules (``_runner``, ``db``) import ``config`` by name at import
time, and reloading mid-suite swaps the singleton out from under them,
producing stale references and flaky failures across unrelated tests.
"""

from __future__ import annotations

import re

import pytest

from oss_profanity.config import Config


def test_defaults_applied_with_only_mongo_uri(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for var in (
        "WORKER_CONCURRENCY",
        "GHA_START",
        "GHA_END",
        "SCRATCH_DIR",
        "BOT_REGEX",
        "MAX_REPO_SIZE_MB",
        "PER_REPO_TIMEOUT_SEC",
        "STALE_CLAIM_TTL_MIN",
        "EMOJI_TOP_N",
        "SAMPLE_PROFANE_N",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("MONGO_URI", "mongodb://localhost:27017/test")

    cfg = Config.from_env()

    assert cfg.mongo_uri == "mongodb://localhost:27017/test"
    assert cfg.worker_concurrency == 12
    assert cfg.gha_start == "2020-06-01-00"
    assert cfg.gha_end == "2020-06-30-23"
    assert cfg.scratch_dir == "/scratch"
    assert cfg.max_repo_size_mb == 2048
    assert cfg.per_repo_timeout.total_seconds() == 600
    assert cfg.stale_claim_ttl.total_seconds() == 20 * 60
    assert cfg.emoji_top_n == 20
    assert cfg.sample_profane_n == 5
    assert isinstance(cfg.bot_regex, re.Pattern)
    assert cfg.bot_regex.search("dependabot[bot]") is not None


def test_env_overrides_apply(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MONGO_URI", "mongodb://db:27017/foo")
    monkeypatch.setenv("WORKER_CONCURRENCY", "4")
    monkeypatch.setenv("EMOJI_TOP_N", "50")
    monkeypatch.setenv("STALE_CLAIM_TTL_MIN", "15")

    cfg = Config.from_env()

    assert cfg.worker_concurrency == 4
    assert cfg.emoji_top_n == 50
    assert cfg.stale_claim_ttl.total_seconds() == 15 * 60


def test_missing_mongo_uri_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MONGO_URI", raising=False)
    with pytest.raises(ValueError, match="MONGO_URI"):
        Config.from_env()


def test_bot_regex_is_case_insensitive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MONGO_URI", "mongodb://localhost:27017/test")
    cfg = Config.from_env()

    assert cfg.bot_regex.search("GitHub-Actions") is not None
    assert cfg.bot_regex.search("RENOVATE-BOT") is not None
    assert cfg.bot_regex.search("alice") is None
