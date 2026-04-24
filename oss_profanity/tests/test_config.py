"""Config module tests — env parsing, defaults, required vars.

Every test constructs a fresh ``Config`` via ``Config.from_env()`` after
monkeypatching the environment. We deliberately avoid ``importlib.reload``:
other modules (``_runner``, ``db``) import ``config`` by name at import
time, and reloading mid-suite swaps the singleton out from under them,
producing stale references and flaky failures across unrelated tests.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from dotenv import load_dotenv

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
        "GITHUB_TOKEN",
        "GITHUB_USER_AGENT",
        "GIT_SUBPROCESS_TIMEOUT_SEC",
        "PROFANE_COHORT_SIZE",
        "CLEAN_COHORT_SIZE",
        "SAMPLING_MIN_COMMITS",
        "SAMPLING_COMMIT_BINS",
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
    assert cfg.github_token is None
    assert cfg.github_user_agent.startswith("oss-profanity/")
    assert cfg.git_subprocess_timeout.total_seconds() == 300
    assert isinstance(cfg.bot_regex, re.Pattern)
    assert cfg.bot_regex.search("dependabot[bot]") is not None
    assert cfg.profane_cohort_size == 750
    assert cfg.clean_cohort_size == 750
    assert cfg.sampling_min_commits == 20
    assert cfg.sampling_commit_bins == (20, 50, 200, 1000)


def test_env_overrides_apply(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MONGO_URI", "mongodb://db:27017/foo")
    monkeypatch.setenv("WORKER_CONCURRENCY", "4")
    monkeypatch.setenv("EMOJI_TOP_N", "50")
    monkeypatch.setenv("STALE_CLAIM_TTL_MIN", "15")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_fake_token")
    monkeypatch.setenv("GITHUB_USER_AGENT", "test-agent/1.0")
    monkeypatch.setenv("GIT_SUBPROCESS_TIMEOUT_SEC", "120")

    cfg = Config.from_env()

    assert cfg.worker_concurrency == 4
    assert cfg.emoji_top_n == 50
    assert cfg.stale_claim_ttl.total_seconds() == 15 * 60
    assert cfg.github_token == "ghp_fake_token"
    assert cfg.github_user_agent == "test-agent/1.0"
    assert cfg.git_subprocess_timeout.total_seconds() == 120


def test_empty_github_token_is_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty GITHUB_TOKEN env var is treated as unset (not an empty string)."""
    monkeypatch.setenv("MONGO_URI", "mongodb://localhost:27017/test")
    monkeypatch.setenv("GITHUB_TOKEN", "")

    cfg = Config.from_env()

    assert cfg.github_token is None


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


# ---------- .env loading ----------


def test_dotenv_fills_unset_variables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A `.env` pointed at via explicit path seeds missing env vars."""
    monkeypatch.delenv("GHA_START", raising=False)
    monkeypatch.delenv("GHA_END", raising=False)
    monkeypatch.setenv("MONGO_URI", "mongodb://localhost:27017/test")
    env_file = tmp_path / ".env"
    env_file.write_text("GHA_START=2020-06-15-00\nGHA_END=2020-06-15-03\n")
    load_dotenv(dotenv_path=env_file, override=False)

    cfg = Config.from_env()
    assert cfg.gha_start == "2020-06-15-00"
    assert cfg.gha_end == "2020-06-15-03"


def test_real_env_wins_over_dotenv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Explicit env exports must beat `.env` values (override=False)."""
    monkeypatch.setenv("MONGO_URI", "mongodb://localhost:27017/test")
    monkeypatch.setenv("GHA_START", "2020-01-01-00")
    env_file = tmp_path / ".env"
    env_file.write_text("GHA_START=9999-12-31-23\n")
    load_dotenv(dotenv_path=env_file, override=False)

    cfg = Config.from_env()
    assert cfg.gha_start == "2020-01-01-00"


def test_missing_dotenv_is_a_noop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Production deploys without `.env` must not break config import."""
    monkeypatch.setenv("MONGO_URI", "mongodb://localhost:27017/test")
    missing = tmp_path / ".env"  # does not exist
    # load_dotenv returns False but does not raise when the path is absent.
    assert load_dotenv(dotenv_path=missing, override=False) is False

    cfg = Config.from_env()
    assert cfg.mongo_uri == "mongodb://localhost:27017/test"


# ---------- IP-006 sampling knobs ----------


def test_sampling_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MONGO_URI", "mongodb://localhost:27017/test")
    monkeypatch.setenv("PROFANE_COHORT_SIZE", "1000")
    monkeypatch.setenv("CLEAN_COHORT_SIZE", "1000")
    monkeypatch.setenv("SAMPLING_MIN_COMMITS", "10")
    monkeypatch.setenv("SAMPLING_COMMIT_BINS", "10,100,1000")

    cfg = Config.from_env()

    assert cfg.profane_cohort_size == 1000
    assert cfg.clean_cohort_size == 1000
    assert cfg.sampling_min_commits == 10
    assert cfg.sampling_commit_bins == (10, 100, 1000)


def test_sampling_commit_bins_empty_string_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MONGO_URI", "mongodb://localhost:27017/test")
    monkeypatch.setenv("SAMPLING_COMMIT_BINS", "   ")

    cfg = Config.from_env()
    assert cfg.sampling_commit_bins == (20, 50, 200, 1000)


def test_sampling_commit_bins_rejects_non_monotonic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MONGO_URI", "mongodb://localhost:27017/test")
    monkeypatch.setenv("SAMPLING_COMMIT_BINS", "20,50,40,1000")

    with pytest.raises(ValueError, match="monotonic"):
        Config.from_env()


def test_sampling_commit_bins_rejects_non_positive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MONGO_URI", "mongodb://localhost:27017/test")
    monkeypatch.setenv("SAMPLING_COMMIT_BINS", "0,50,200")

    with pytest.raises(ValueError, match="positive"):
        Config.from_env()


def test_sampling_commit_bins_rejects_non_integer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MONGO_URI", "mongodb://localhost:27017/test")
    monkeypatch.setenv("SAMPLING_COMMIT_BINS", "20,fifty,200")

    with pytest.raises(ValueError, match="CSV of ints"):
        Config.from_env()
