"""HTTP streaming: retry, Retry-After, transport errors, User-Agent.

Uses httpx's built-in ``MockTransport`` — no network, fully deterministic.
"""

from __future__ import annotations

import asyncio
from typing import Final

import httpx
import pytest

from oss_profanity.archive_ingest import _http
from oss_profanity.archive_ingest._http import stream_file

_SENTINEL: Final[bytes] = b"PAYLOAD_BYTES"


async def _run(coro):  # type: ignore[no-untyped-def]
    return await coro


@pytest.mark.asyncio
async def test_stream_file_returns_full_payload_on_200() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/2020-06-01-0.json.gz"
        assert "oss-profanity" in request.headers["user-agent"]
        return httpx.Response(200, content=_SENTINEL)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        out = await stream_file(client, "2020-06-01-00")
    assert out == _SENTINEL


@pytest.mark.asyncio
async def test_stream_file_retries_on_5xx_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            return httpx.Response(503, content=b"server error")
        return httpx.Response(200, content=_SENTINEL)

    # Zero the backoff sleeps so the test finishes fast.
    async def _no_sleep(_secs: float) -> None:
        return None

    monkeypatch.setattr(_http.asyncio, "sleep", _no_sleep)
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        out = await stream_file(client, "2020-06-01-00", max_retries=5)
    assert out == _SENTINEL
    assert call_count == 3


@pytest.mark.asyncio
async def test_stream_file_honors_retry_after_on_429(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleeps: list[float] = []

    async def fake_sleep(secs: float) -> None:
        sleeps.append(secs)

    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(
                429, headers={"Retry-After": "7"}, content=b""
            )
        return httpx.Response(200, content=_SENTINEL)

    monkeypatch.setattr(_http.asyncio, "sleep", fake_sleep)
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        out = await stream_file(client, "2020-06-01-00", max_retries=3)
    assert out == _SENTINEL
    # First sleep comes from the 429 Retry-After path.
    assert sleeps[0] == 7.0


@pytest.mark.asyncio
async def test_stream_file_raises_after_max_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(503, content=b"down")

    async def _no_sleep(_secs: float) -> None:
        return None

    monkeypatch.setattr(_http.asyncio, "sleep", _no_sleep)
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await stream_file(client, "2020-06-01-00", max_retries=3)


@pytest.mark.asyncio
async def test_stream_file_exponential_backoff_capped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleeps: list[float] = []

    async def fake_sleep(secs: float) -> None:
        sleeps.append(secs)

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(500, content=b"")

    monkeypatch.setattr(_http.asyncio, "sleep", fake_sleep)
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await stream_file(client, "2020-06-01-00", max_retries=8)
    # Sleeps follow 1, 2, 4, 8, 16, 30(cap), 30(cap) — 7 retries with
    # backoff between attempts; final attempt raises.
    assert max(sleeps) <= 30.0
    assert any(s == 30.0 for s in sleeps)


@pytest.mark.asyncio
async def test_stream_file_handles_chunked_bytes() -> None:
    # MockTransport's Response accepts bytes content; streaming
    # internally chunks it. We just validate we get the whole payload.
    big = b"X" * (1 << 17)  # 128 KB — exercises the chunked loop
    transport = httpx.MockTransport(
        lambda _r: httpx.Response(200, content=big)
    )
    async with httpx.AsyncClient(transport=transport) as client:
        out = await stream_file(client, "2020-06-01-00")
    assert out == big
