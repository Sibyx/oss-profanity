"""SIGALRM wall-time envelope (IP-007 `_timeout`)."""

from __future__ import annotations

import signal
import time

import pytest

from oss_profanity.repo_worker._errors import RepoTimeout
from oss_profanity.repo_worker._timeout import envelope


@pytest.mark.skipif(
    not hasattr(signal, "setitimer"),
    reason="signal.setitimer unavailable on this platform",
)
def test_envelope_raises_repotimeout_on_slow_block() -> None:
    with pytest.raises(RepoTimeout):
        with envelope(0.2):
            time.sleep(5.0)


@pytest.mark.skipif(
    not hasattr(signal, "setitimer"),
    reason="signal.setitimer unavailable on this platform",
)
def test_envelope_returns_cleanly_under_budget() -> None:
    with envelope(1.0):
        time.sleep(0.01)
    # If we reach here, no RepoTimeout fired; envelope restored state.


@pytest.mark.skipif(
    not hasattr(signal, "setitimer"),
    reason="signal.setitimer unavailable on this platform",
)
def test_envelope_restores_prior_signal_handler() -> None:
    sentinel = signal.getsignal(signal.SIGALRM)
    with envelope(1.0):
        pass
    assert signal.getsignal(signal.SIGALRM) == sentinel


def test_envelope_zero_seconds_is_noop() -> None:
    with envelope(0):
        time.sleep(0.01)  # should not be interrupted


def test_envelope_negative_seconds_is_noop() -> None:
    with envelope(-1):
        time.sleep(0.01)
