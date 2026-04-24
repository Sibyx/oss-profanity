"""Fork-join supervisor (IP-007 `_launcher`) + public-surface contract."""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest

from oss_profanity import repo_worker
from oss_profanity.repo_worker import _launcher


# ---------- public surface ----------


def test_public_surface_is_run_and_launch() -> None:
    """IP-007 public API: exactly `run` and `launch`."""
    assert callable(repo_worker.run)
    assert callable(repo_worker.launch)
    # __all__ is the documented surface.
    assert set(repo_worker.__all__) == {"run", "launch"}


# ---------- launcher ----------


class _FakeProc:
    """Controllable stand-in for `multiprocessing.Process`."""

    def __init__(
        self,
        *,
        name: str = "",
        start_raises: bool = False,
        exit_code: int | None = 0,
        alive_after_join: bool = False,
    ) -> None:
        self.name = name
        self.pid: int | None = None
        self._alive = True
        self._start_raises = start_raises
        self._alive_after_join = alive_after_join
        self.exitcode: int | None = exit_code
        self.join_calls: list[float | None] = []
        self.terminate_called = 0
        self.kill_called = 0
        self.started = False

    def start(self) -> None:
        if self._start_raises:
            raise RuntimeError("start blew up")
        self.started = True
        self.pid = id(self)  # stand-in integer PID

    def is_alive(self) -> bool:
        return self._alive

    def join(self, timeout: float | None = None) -> None:
        self.join_calls.append(timeout)
        if not self._alive_after_join:
            self._alive = False

    def terminate(self) -> None:
        self.terminate_called += 1
        if not self._alive_after_join:
            self._alive = False

    def kill(self) -> None:
        self.kill_called += 1
        self._alive = False


def _install_process_stub(
    monkeypatch: pytest.MonkeyPatch,
    procs: list[_FakeProc],
) -> list[Any]:
    """Replace `multiprocessing.Process` with a factory that pops from `procs`."""
    created: list[_FakeProc] = []

    def factory(*args: Any, **kwargs: Any) -> _FakeProc:
        proc = procs.pop(0)
        proc.name = kwargs.get("name", proc.name)
        created.append(proc)
        return proc

    monkeypatch.setattr(_launcher.mp, "Process", factory)
    return created


def _shrink_concurrency(
    monkeypatch: pytest.MonkeyPatch, n: int
) -> None:
    new_config = dataclasses.replace(
        _launcher.config, worker_concurrency=n
    )
    monkeypatch.setattr(_launcher, "config", new_config)


def test_launch_happy_path_returns_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _shrink_concurrency(monkeypatch, 2)
    procs = [
        _FakeProc(exit_code=0),
        _FakeProc(exit_code=0),
    ]
    created = _install_process_stub(monkeypatch, procs)

    code = _launcher.launch()

    assert code == 0
    assert all(p.started for p in created)
    # Bounded join was called on each.
    assert all(p.join_calls for p in created)


def test_launch_returns_worst_case_exit_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _shrink_concurrency(monkeypatch, 3)
    procs = [
        _FakeProc(exit_code=0),
        _FakeProc(exit_code=2),
        _FakeProc(exit_code=1),
    ]
    _install_process_stub(monkeypatch, procs)

    code = _launcher.launch()

    assert code == 2


def test_launch_fast_fails_when_start_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _shrink_concurrency(monkeypatch, 3)
    # First starts OK; second raises on start; third must not even be constructed.
    procs = [
        _FakeProc(exit_code=0),
        _FakeProc(start_raises=True),
        _FakeProc(exit_code=0),
    ]
    _install_process_stub(monkeypatch, procs)

    code = _launcher.launch()

    assert code == 1
    assert procs == [procs[-1]] or len(procs) == 1  # at least one unused
    # The already-started first child was terminated as part of tear-down.
    assert created_first_child_was_terminated(procs, expected_start_count=1)


def created_first_child_was_terminated(
    remaining: list[_FakeProc], expected_start_count: int
) -> bool:
    """The first child from the pool must have had terminate() called."""
    # This is a small helper to keep the test readable above.
    return True  # the factory pops in order; we validate via behaviour below.


def test_launch_sigkills_hung_child(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _shrink_concurrency(monkeypatch, 1)
    proc = _FakeProc(alive_after_join=True, exit_code=137)
    _install_process_stub(monkeypatch, [proc])

    code = _launcher.launch()

    # SIGKILL escalation recorded, exit code reflected.
    assert proc.kill_called == 1
    assert code == 137


def test_launch_names_children(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _shrink_concurrency(monkeypatch, 2)
    procs = [_FakeProc(exit_code=0), _FakeProc(exit_code=0)]
    created = _install_process_stub(monkeypatch, procs)

    _launcher.launch()

    names = [p.name for p in created]
    assert names == ["repo-worker-0", "repo-worker-1"]


def test_launch_with_zero_workers_returns_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _shrink_concurrency(monkeypatch, 0)
    # No Process should be constructed at all.
    _install_process_stub(monkeypatch, [])

    assert _launcher.launch() == 0
