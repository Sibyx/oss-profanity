"""GitHub REST enrichment (IP-007).

Two public functions against two endpoints — both best-effort
(``None`` on any error), both routed through a single ``_request``
helper that centralises the rate-limit discipline:

* ``fetch_metadata(full_name)`` → ``GET /repos/{full_name}``
* ``fetch_languages(full_name)`` → ``GET /repos/{full_name}/languages``

Rate-limit discipline (per the IP-007 spec):

* Set ``User-Agent`` + ``Authorization`` + ``X-GitHub-Api-Version`` on
  every request.
* Proactive back-off when ``X-RateLimit-Remaining < 100`` until
  ``X-RateLimit-Reset``; capped at 60 s.
* Honour ``Retry-After`` on 403/429; single retry; cap 60 s.
* Single retry on 5xx after 2 s.
* Any network error → log WARNING, return ``None``.
"""

from __future__ import annotations

import atexit
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any

import httpx

from ..config import config
from ..db import GitHubMetadata

logger = logging.getLogger(__name__)

_API_BASE = "https://api.github.com"
_DEFAULT_HTTP_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
_HARD_CAP_SLEEP_SEC = 60.0
_BACKOFF_REMAINING_THRESHOLD = 100

_client: httpx.Client | None = None
_client_lock = threading.Lock()
_token_warning_emitted = False


def _get_client() -> httpx.Client:
    """Return the process-global ``httpx.Client``, constructing on first use."""
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                headers: dict[str, str] = {
                    "User-Agent": config.github_user_agent,
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                }
                if config.github_token:
                    headers["Authorization"] = f"Bearer {config.github_token}"
                _client = httpx.Client(
                    http2=False,
                    timeout=_DEFAULT_HTTP_TIMEOUT,
                    headers=headers,
                )
                atexit.register(_close_client)
    return _client


def _close_client() -> None:  # pragma: no cover - atexit-only path
    global _client
    if _client is not None:
        try:
            _client.close()
        except Exception:  # noqa: BLE001 - close must never raise at shutdown
            logger.debug("github: error closing client at exit", exc_info=True)
        _client = None


def _warn_missing_token_once() -> None:
    global _token_warning_emitted
    if _token_warning_emitted:
        return
    _token_warning_emitted = True
    if config.github_token is None:
        logger.warning(
            "github: GITHUB_TOKEN not set; REST rate-limit will be 60/hour "
            "per IP (useless for 36-worker Stage 4). See docs/CONFIGURATION.md."
        )


def _throttle_if_needed(headers: httpx.Headers) -> None:
    """Sleep if the remaining budget falls below threshold."""
    try:
        remaining = int(headers.get("x-ratelimit-remaining", "5000"))
    except ValueError:
        return
    if remaining >= _BACKOFF_REMAINING_THRESHOLD:
        return
    try:
        reset = float(headers.get("x-ratelimit-reset", "0"))
    except ValueError:
        return
    now = time.time()
    sleep_for = max(0.0, min(_HARD_CAP_SLEEP_SEC, reset - now))
    if sleep_for > 0:
        logger.info(
            "github: %d remaining; throttling %.1fs until reset",
            remaining,
            sleep_for,
        )
        time.sleep(sleep_for)


def _retry_after_sleep(headers: httpx.Headers, default: float = 10.0) -> None:
    try:
        retry_after = float(headers.get("retry-after", str(default)))
    except ValueError:
        retry_after = default
    time.sleep(min(_HARD_CAP_SLEEP_SEC, retry_after))


def _request(url: str) -> Any | None:
    """Perform a single authenticated GET with full rate-limit discipline."""
    _warn_missing_token_once()
    client = _get_client()
    for attempt in range(2):
        try:
            resp = client.get(url)
        except httpx.HTTPError as exc:
            logger.warning("github: network error for %s: %s", url, exc)
            return None

        if resp.status_code == 200:
            _throttle_if_needed(resp.headers)
            try:
                return resp.json()
            except ValueError:
                logger.warning("github: %s returned non-JSON 200", url)
                return None

        if resp.status_code == 404:
            logger.info("github: %s returned 404; skipping metadata", url)
            return None

        if resp.status_code in (403, 429):
            if attempt == 0:
                logger.info(
                    "github: %s rate-limited (status %d); retrying once",
                    url,
                    resp.status_code,
                )
                _retry_after_sleep(resp.headers)
                continue
            logger.warning(
                "github: %s still rate-limited after retry; giving up", url
            )
            return None

        if 500 <= resp.status_code < 600:
            if attempt == 0:
                logger.info(
                    "github: %s returned %d; retrying once after 2s",
                    url,
                    resp.status_code,
                )
                time.sleep(2.0)
                continue
            logger.warning(
                "github: %s returned %d after retry; giving up",
                url,
                resp.status_code,
            )
            return None

        logger.warning(
            "github: %s returned unexpected status %d", url, resp.status_code
        )
        return None
    return None


def _to_metadata(payload: dict[str, Any]) -> GitHubMetadata:
    """Map a ``/repos/{full_name}`` response to :class:`GitHubMetadata`."""
    license_block = payload.get("license") or {}
    parent_block = payload.get("parent") or {}
    return GitHubMetadata(
        fetched_at=datetime.now(timezone.utc),
        stargazers_count=int(payload.get("stargazers_count", 0) or 0),
        forks_count=int(payload.get("forks_count", 0) or 0),
        watchers_count=int(payload.get("watchers_count", 0) or 0),
        subscribers_count=int(payload.get("subscribers_count", 0) or 0),
        open_issues_count=int(payload.get("open_issues_count", 0) or 0),
        topics=list(payload.get("topics") or []),
        license_spdx=(
            license_block.get("spdx_id")
            if isinstance(license_block, dict)
            else None
        ),
        language=payload.get("language"),
        size_kb=int(payload.get("size", 0) or 0),
        default_branch=payload.get("default_branch"),
        fork=bool(payload.get("fork", False)),
        parent_full_name=(
            parent_block.get("full_name")
            if isinstance(parent_block, dict)
            else None
        ),
        archived=bool(payload.get("archived", False)),
        disabled=bool(payload.get("disabled", False)),
        created_at=_parse_ts(payload.get("created_at")),
        pushed_at=_parse_ts(payload.get("pushed_at")),
        updated_at=_parse_ts(payload.get("updated_at")),
        description=payload.get("description"),
    )


def _parse_ts(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def fetch_metadata(full_name: str) -> GitHubMetadata | None:
    """Return parsed metadata for ``full_name`` or ``None`` on any error."""
    payload = _request(f"{_API_BASE}/repos/{full_name}")
    if not isinstance(payload, dict):
        return None
    try:
        return _to_metadata(payload)
    except Exception as exc:  # noqa: BLE001 - never let a bad payload crash worker
        logger.warning(
            "github: failed to map /repos/%s payload: %s", full_name, exc
        )
        return None


def fetch_languages(full_name: str) -> dict[str, int] | None:
    """Return ``{language: bytes}`` for ``full_name`` or ``None`` on error."""
    payload = _request(f"{_API_BASE}/repos/{full_name}/languages")
    if not isinstance(payload, dict):
        return None
    # Coerce values to int; skip non-int entries defensively.
    out: dict[str, int] = {}
    for name, count in payload.items():
        if not isinstance(name, str):
            continue
        try:
            out[name] = int(count)
        except (TypeError, ValueError):
            continue
    return out
