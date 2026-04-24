"""GitHub REST enrichment (IP-007 `_github`)."""

from __future__ import annotations

import time
from collections.abc import Callable

import httpx
import pytest

from oss_profanity.repo_worker import _github


def _install_client(
    monkeypatch: pytest.MonkeyPatch, handler: Callable[[httpx.Request], httpx.Response]
) -> None:
    """Replace the module-level client with one backed by MockTransport."""
    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        headers={
            "User-Agent": "oss-profanity-test/0 (jakub.dubec@stuba.sk)",
        },
        timeout=httpx.Timeout(5.0),
    )
    monkeypatch.setattr(_github, "_client", client)
    # Reset the token-warning flag so tests stay independent.
    monkeypatch.setattr(_github, "_token_warning_emitted", True)


_REPOS_PAYLOAD = {
    "id": 123,
    "full_name": "alice/widget",
    "stargazers_count": 42,
    "forks_count": 7,
    "watchers_count": 42,
    "subscribers_count": 3,
    "open_issues_count": 2,
    "topics": ["cli", "python"],
    "license": {"spdx_id": "MIT"},
    "language": "Python",
    "size": 1024,
    "default_branch": "main",
    "fork": False,
    "parent": None,
    "archived": False,
    "disabled": False,
    "created_at": "2019-01-01T00:00:00Z",
    "pushed_at": "2020-06-15T10:00:00Z",
    "updated_at": "2020-06-20T12:30:00Z",
    "description": "A widget",
}


def test_fetch_metadata_200_maps_all_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_REPOS_PAYLOAD)

    _install_client(monkeypatch, handler)

    meta = _github.fetch_metadata("alice/widget")

    assert meta is not None
    assert meta.stargazers_count == 42
    assert meta.forks_count == 7
    assert meta.topics == ["cli", "python"]
    assert meta.license_spdx == "MIT"
    assert meta.language == "Python"
    assert meta.size_kb == 1024
    assert meta.default_branch == "main"
    assert meta.archived is False
    assert meta.description == "A widget"
    assert meta.created_at is not None
    assert meta.pushed_at is not None


def test_fetch_metadata_404_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "Not Found"})

    _install_client(monkeypatch, handler)

    assert _github.fetch_metadata("ghost/repo") is None


def test_fetch_metadata_retries_on_rate_limit_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        if call_count["n"] == 1:
            return httpx.Response(
                429, json={}, headers={"Retry-After": "0"}
            )
        return httpx.Response(200, json=_REPOS_PAYLOAD)

    _install_client(monkeypatch, handler)
    # Avoid real sleep
    monkeypatch.setattr(time, "sleep", lambda _s: None)

    meta = _github.fetch_metadata("alice/widget")

    assert meta is not None
    assert call_count["n"] == 2


def test_fetch_metadata_gives_up_after_second_rate_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={}, headers={"Retry-After": "0"})

    _install_client(monkeypatch, handler)
    monkeypatch.setattr(time, "sleep", lambda _s: None)

    assert _github.fetch_metadata("alice/widget") is None


def test_fetch_metadata_retries_on_5xx(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        if call_count["n"] == 1:
            return httpx.Response(503, json={"message": "down"})
        return httpx.Response(200, json=_REPOS_PAYLOAD)

    _install_client(monkeypatch, handler)
    monkeypatch.setattr(time, "sleep", lambda _s: None)

    meta = _github.fetch_metadata("alice/widget")

    assert meta is not None
    assert call_count["n"] == 2


def test_fetch_metadata_network_error_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    _install_client(monkeypatch, handler)

    assert _github.fetch_metadata("alice/widget") is None


def test_fetch_metadata_proactive_throttle_on_low_remaining(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    slept: list[float] = []

    def fake_sleep(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr(time, "sleep", fake_sleep)
    monkeypatch.setattr(time, "time", lambda: 1000.0)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_REPOS_PAYLOAD,
            headers={
                "X-RateLimit-Remaining": "50",
                "X-RateLimit-Reset": "1003",  # now + 3s
            },
        )

    _install_client(monkeypatch, handler)

    meta = _github.fetch_metadata("alice/widget")

    assert meta is not None
    assert any(2.5 < s <= 3.0 for s in slept), slept


def test_fetch_metadata_does_not_throttle_when_plenty_remaining(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    slept: list[float] = []
    monkeypatch.setattr(time, "sleep", lambda s: slept.append(s))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_REPOS_PAYLOAD,
            headers={
                "X-RateLimit-Remaining": "4500",
                "X-RateLimit-Reset": "9999999999",
            },
        )

    _install_client(monkeypatch, handler)

    _github.fetch_metadata("alice/widget")

    assert slept == []


def test_fetch_metadata_handles_missing_license_block(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = dict(_REPOS_PAYLOAD)
    payload["license"] = None

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    _install_client(monkeypatch, handler)

    meta = _github.fetch_metadata("alice/widget")

    assert meta is not None
    assert meta.license_spdx is None


def test_fetch_languages_200_coerces_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"Python": 15000, "Shell": 200, "HTML": "not-a-number"}
        )

    _install_client(monkeypatch, handler)

    languages = _github.fetch_languages("alice/widget")

    assert languages == {"Python": 15000, "Shell": 200}


def test_fetch_languages_404_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "Not Found"})

    _install_client(monkeypatch, handler)

    assert _github.fetch_languages("ghost/repo") is None


def test_fetch_languages_empty_dict_for_empty_repo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    _install_client(monkeypatch, handler)

    assert _github.fetch_languages("alice/empty") == {}


def test_fetch_metadata_picks_correct_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json=_REPOS_PAYLOAD)

    _install_client(monkeypatch, handler)

    _github.fetch_metadata("alice/widget")

    assert captured["url"] == "https://api.github.com/repos/alice/widget"


def test_fetch_languages_picks_correct_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"Python": 10})

    _install_client(monkeypatch, handler)

    _github.fetch_languages("alice/widget")

    assert captured["url"] == "https://api.github.com/repos/alice/widget/languages"


def test_fetch_metadata_malformed_payload_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        # 200 but the "created_at" is garbage — make sure we still map what
        # we can and tolerate a bad timestamp
        bad = dict(_REPOS_PAYLOAD)
        bad["created_at"] = "not-a-date"
        return httpx.Response(200, json=bad)

    _install_client(monkeypatch, handler)

    meta = _github.fetch_metadata("alice/widget")

    assert meta is not None
    assert meta.created_at is None  # bad timestamp becomes None
