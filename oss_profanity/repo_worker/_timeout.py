"""SIGALRM-based per-repo wall-time envelope.

POSIX ``setitimer(ITIMER_REAL)`` fires SIGALRM after ``seconds``; our
handler raises :class:`RepoTimeout`. The envelope is a backstop over
non-subprocess code paths (``rmtree`` on stuck NFS, Python-level
infinite loops) — the per-subprocess timeouts already bound each tool.

Linux / macOS / BSD support ``signal.setitimer`` natively. Windows
lacks it; on platforms without the attr (or with ``seconds <= 0``) the
context manager is a no-op — per-subprocess timeouts still apply.

Main-thread delivery: SIGALRM is delivered only to the main thread of
the receiving process. The worker process is single-threaded at the
``_loop.run`` level (IP-004's ``ThreadPoolExecutor`` inside ``run_all``
is joined before returning), so the only signal recipient is the loop
itself — the semantics are trivially satisfied.
"""

from __future__ import annotations

import signal
from collections.abc import Iterator
from contextlib import contextmanager
from types import FrameType
from typing import Any, cast

from ._errors import RepoTimeout


def _raise_timeout(
    signum: int, frame: FrameType | None
) -> None:  # pragma: no cover - exercised via signal
    raise RepoTimeout(f"SIGALRM after setitimer (signum={signum})")


@contextmanager
def envelope(seconds: float) -> Iterator[None]:
    """Raise :class:`RepoTimeout` if the wrapped block exceeds ``seconds``.

    ``seconds <= 0`` or a platform without ``signal.setitimer`` → no-op.
    """
    if seconds <= 0 or not hasattr(signal, "setitimer"):
        yield
        return

    setitimer = cast(Any, signal.setitimer)
    itimer_real = cast(Any, signal.ITIMER_REAL)

    prev_handler = signal.signal(signal.SIGALRM, _raise_timeout)
    setitimer(itimer_real, seconds)
    try:
        yield
    finally:
        setitimer(itimer_real, 0)
        signal.signal(signal.SIGALRM, prev_handler)
