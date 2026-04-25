"""Central configuration for the oss-profanity pipeline.

Every tunable lives here and is loaded from the environment once at import time
into a frozen dataclass. No other module should call ``os.getenv`` directly.

If a ``.env`` file sits next to the repo root (or anywhere up the cwd chain),
its contents are loaded **before** ``Config.from_env`` reads the environment.
Real environment variables always win over ``.env`` values — the file is a
developer convenience, not a production override. Missing ``.env`` is a no-op.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import timedelta

from dotenv import load_dotenv

# Load ``.env`` once at import time. ``override=False`` so explicit exports
# (including pytest fixtures and production deploy env) always take precedence.
load_dotenv(override=False)


_DEFAULT_USER_AGENT = "oss-profanity/0.1 (jakub.dubec@stuba.sk)"


@dataclass(frozen=True)
class Config:
    mongo_uri: str
    worker_concurrency: int
    gha_start: str
    gha_end: str
    scratch_dir: str
    bot_regex: re.Pattern[str]
    max_repo_size_mb: int
    per_repo_timeout: timedelta
    stale_claim_ttl: timedelta
    emoji_top_n: int
    sample_profane_n: int
    github_token: str | None
    github_user_agent: str
    git_subprocess_timeout: timedelta
    profane_cohort_size: int
    clean_cohort_size: int
    sampling_min_commits: int
    sampling_commit_bins: tuple[int, ...]
    cleanup_after_repo: bool
    eslint_config_path: str

    @classmethod
    def from_env(cls) -> Config:
        try:
            mongo_uri = os.environ["MONGO_URI"]
        except KeyError as exc:
            raise ValueError(
                "MONGO_URI is required but not set in the environment"
            ) from exc

        token = os.getenv("GITHUB_TOKEN")
        return cls(
            mongo_uri=mongo_uri,
            worker_concurrency=int(os.getenv("WORKER_CONCURRENCY", "12")),
            gha_start=os.getenv("GHA_START", "2020-06-01-00"),
            gha_end=os.getenv("GHA_END", "2020-06-30-23"),
            scratch_dir=os.getenv("SCRATCH_DIR", "/scratch"),
            bot_regex=re.compile(
                os.getenv(
                    "BOT_REGEX",
                    r"(bot|dependabot|renovate|github-actions|greenkeeper)",
                ),
                re.IGNORECASE,
            ),
            max_repo_size_mb=int(os.getenv("MAX_REPO_SIZE_MB", "2048")),
            per_repo_timeout=timedelta(
                seconds=int(os.getenv("PER_REPO_TIMEOUT_SEC", "600"))
            ),
            stale_claim_ttl=timedelta(
                minutes=int(os.getenv("STALE_CLAIM_TTL_MIN", "20"))
            ),
            emoji_top_n=int(os.getenv("EMOJI_TOP_N", "20")),
            sample_profane_n=int(os.getenv("SAMPLE_PROFANE_N", "5")),
            github_token=token if token else None,
            github_user_agent=os.getenv(
                "GITHUB_USER_AGENT", _DEFAULT_USER_AGENT
            ),
            git_subprocess_timeout=timedelta(
                seconds=int(os.getenv("GIT_SUBPROCESS_TIMEOUT_SEC", "300"))
            ),
            profane_cohort_size=int(
                os.getenv("PROFANE_COHORT_SIZE", "750")
            ),
            clean_cohort_size=int(os.getenv("CLEAN_COHORT_SIZE", "750")),
            sampling_min_commits=int(
                os.getenv("SAMPLING_MIN_COMMITS", "20")
            ),
            sampling_commit_bins=_parse_commit_bins(
                os.getenv("SAMPLING_COMMIT_BINS", "20,50,200,1000")
            ),
            cleanup_after_repo=_parse_bool(
                os.getenv("CLEANUP_AFTER_REPO", "true")
            ),
            eslint_config_path=os.getenv(
                "ESLINT_CONFIG_PATH",
                "/opt/node-tools/eslint.config.mjs",
            ),
        )


def _parse_bool(raw: str) -> bool:
    """Parse a boolean env var. Accepts ``true|false|1|0|yes|no`` (case-insensitive)."""
    v = raw.strip().lower()
    if v in ("true", "1", "yes", "on"):
        return True
    if v in ("false", "0", "no", "off"):
        return False
    raise ValueError(f"expected boolean, got {raw!r}")


def _parse_commit_bins(raw: str) -> tuple[int, ...]:
    """Parse ``SAMPLING_COMMIT_BINS`` — CSV of strictly-monotonic positive ints.

    Empty / whitespace-only input falls back to the default series. Non-integer
    tokens, non-positive values, and non-monotonic sequences raise ``ValueError``
    at import time so misconfigured runs fail before any MongoDB writes.
    """
    tokens = [t.strip() for t in raw.split(",") if t.strip()]
    if not tokens:
        return (20, 50, 200, 1000)
    try:
        values = tuple(int(t) for t in tokens)
    except ValueError as exc:
        raise ValueError(
            f"SAMPLING_COMMIT_BINS must be a CSV of ints; got {raw!r}"
        ) from exc
    if any(v <= 0 for v in values):
        raise ValueError(
            f"SAMPLING_COMMIT_BINS must be positive; got {values}"
        )
    if any(values[i] >= values[i + 1] for i in range(len(values) - 1)):
        raise ValueError(
            f"SAMPLING_COMMIT_BINS must be strictly monotonic; got {values}"
        )
    return values


config: Config = Config.from_env()
