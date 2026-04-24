"""HTTP streaming: pulls one `.json.gz` into memory with retry discipline.

No disk, no ``.part`` files. A mid-stream failure re-downloads from
zero on the next attempt — which is cheaper than the bookkeeping
needed for a mid-file resume at our 30–60 s / file budget.

Rate-limit discipline:

* 429 response → sleep for ``Retry-After`` seconds and retry
* 5xx / transport error → exponential backoff capped at 30 s
* Descriptive ``User-Agent`` so Cloudflare analytics can identify us
"""

from __future__ import annotations

import asyncio
import logging
from typing import Final

import httpx

from ._urls import url_for

logger = logging.getLogger(__name__)

_USER_AGENT: Final[str] = (
    "oss-profanity/0.1 (+https://github.com/jdubec/oss-profanity)"
)
_CHUNK_SIZE: Final[int] = 1 << 16
_BACKOFF_CAP_SEC: Final[float] = 30.0


async def stream_file(
    client: httpx.AsyncClient,
    file_id: str,
    max_retries: int = 5,
) -> bytes:
    """Download one hourly payload as ``bytes``; raise on exhausted retries."""
    url = url_for(file_id)
    last_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            async with client.stream(
                "GET", url, headers={"User-Agent": _USER_AGENT}
            ) as resp:
                if resp.status_code == 429:
                    retry_after = _parse_retry_after(resp.headers)
                    logger.warning(
                        "stream_file: 429 on %s, sleeping %.1fs",
                        file_id,
                        retry_after,
                    )
                    await asyncio.sleep(retry_after)
                    continue
                resp.raise_for_status()
                buf = bytearray()
                async for chunk in resp.aiter_bytes(chunk_size=_CHUNK_SIZE):
                    buf.extend(chunk)
                return bytes(buf)
        except (httpx.HTTPError, asyncio.TimeoutError) as exc:
            last_error = exc
            if attempt == max_retries - 1:
                break
            backoff = min(2**attempt, _BACKOFF_CAP_SEC)
            logger.warning(
                "stream_file: %s on %s (attempt %d/%d), backing off %.1fs",
                type(exc).__name__,
                file_id,
                attempt + 1,
                max_retries,
                backoff,
            )
            await asyncio.sleep(backoff)
    assert last_error is not None
    raise last_error


def _parse_retry_after(headers: httpx.Headers) -> float:
    """Parse the ``Retry-After`` header value; default to 1 s on anything odd."""
    value = headers.get("retry-after")
    if not value:
        return 1.0
    try:
        return float(value)
    except ValueError:
        return 1.0
