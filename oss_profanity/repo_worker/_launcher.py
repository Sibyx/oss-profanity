"""Fork-join supervisor for the per-host worker pool (IP-007).

Spawns :data:`config.worker_concurrency` copies of :func:`_loop.run`
as ``multiprocessing.Process`` children and supervises them:

* typed ``int`` exit code (worst non-zero across children; 0 on full success)
* named children for clean ``ps`` / ``htop`` output
* SIGTERM / SIGINT forwarding from parent to every child
* bounded ``join`` with SIGKILL escalation (``per_repo_timeout + 30 s``)
* fast-fail-on-startup: if any child fails to ``start()``, tear down the
  already-started siblings instead of running with a mixed state
* structured start / exit log lines per child for post-mortem traceability

Matches the lifecycle conventions gunicorn / uvicorn ``--workers`` /
celery-multi use for the same fork-join problem.
"""

from __future__ import annotations

import logging
import multiprocessing as mp
import signal
from types import FrameType

from ..config import config
from ..db import make_worker_id
from ._loop import run

logger = logging.getLogger(__name__)

_STARTUP_GRACE_SEC = 10.0
_FINAL_JOIN_GRACE_SEC = 5.0
_EXTRA_JOIN_GRACE_SEC = 30.0


def launch() -> int:
    """Fork-join supervisor. Returns the worst-case non-zero child exit code."""
    children: list[mp.Process] = []

    for idx in range(config.worker_concurrency):
        wid = make_worker_id()
        proc = mp.Process(
            target=run,
            kwargs={"worker_id": wid},
            name=f"repo-worker-{idx}",
        )
        try:
            proc.start()
        except Exception:  # noqa: BLE001 - fast-fail any startup failure
            logger.exception(
                "launcher: failed to start child %d; tearing down started", idx
            )
            _terminate_all(children, grace=_STARTUP_GRACE_SEC)
            return 1
        logger.info(
            "launcher: child started",
            extra={"worker_id": wid, "pid": proc.pid, "event": "start"},
        )
        children.append(proc)

    _install_forwarding_handlers(children)

    join_timeout = config.per_repo_timeout.total_seconds() + _EXTRA_JOIN_GRACE_SEC
    worst = 0
    for proc in children:
        proc.join(timeout=join_timeout)
        if proc.is_alive():
            logger.error(
                "launcher: child %s did not exit within join timeout; SIGKILL",
                proc.name,
                extra={"child_name": proc.name, "pid": proc.pid},
            )
            proc.kill()
            proc.join(timeout=_FINAL_JOIN_GRACE_SEC)
        code = proc.exitcode if proc.exitcode is not None else 1
        logger.info(
            "launcher: child exited",
            extra={
                "pid": proc.pid,
                "exit_code": code,
                "event": "exit",
            },
        )
        worst = max(worst, abs(code))
    return worst


def _install_forwarding_handlers(children: list[mp.Process]) -> None:
    """Forward SIGTERM / SIGINT to every child so cooperative shutdown trips."""

    def _forward(
        signum: int, frame: FrameType | None
    ) -> None:  # pragma: no cover
        logger.info(
            "launcher: forwarding signal %d to %d children", signum, len(children)
        )
        _terminate_all(children, grace=0.0, send_only=True)

    signal.signal(signal.SIGTERM, _forward)
    signal.signal(signal.SIGINT, _forward)


def _terminate_all(
    children: list[mp.Process], grace: float, send_only: bool = False
) -> None:
    """Send SIGTERM to every alive child; optionally wait and SIGKILL."""
    for proc in children:
        if proc.is_alive():
            proc.terminate()
    if send_only:
        return
    for proc in children:
        proc.join(timeout=grace)
        if proc.is_alive():
            proc.kill()
            proc.join(timeout=_FINAL_JOIN_GRACE_SEC)
