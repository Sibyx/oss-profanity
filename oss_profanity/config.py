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

    @classmethod
    def from_env(cls) -> Config:
        try:
            mongo_uri = os.environ["MONGO_URI"]
        except KeyError as exc:
            raise ValueError(
                "MONGO_URI is required but not set in the environment"
            ) from exc

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
        )


config: Config = Config.from_env()
