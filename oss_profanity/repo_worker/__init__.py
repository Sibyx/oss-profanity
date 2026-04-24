"""Stage 4 worker subpackage (IP-007).

Public surface: two names.

* :func:`run` — per-process main loop. Claims ``pending`` repos one at a
  time, enriches them with GitHub REST metadata, clones, analyses via
  IP-004, and writes results back. Exits cleanly when the cohort drains
  or on SIGTERM.

* :func:`launch` — per-host launcher. Forks ``config.worker_concurrency``
  copies of :func:`run`, supervises them, forwards SIGTERM, and returns
  the worst-case child exit code.

Every other symbol is internal (``_``-prefixed module) and must not be
imported from outside this package.
"""

from __future__ import annotations

from ._launcher import launch
from ._loop import run

__all__ = ["launch", "run"]
