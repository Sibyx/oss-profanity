"""GH Archive ingest subpackage (IP-005).

Public surface: two names.

* :func:`run` — ingest the full window described by
  ``config.gha_start`` / ``config.gha_end`` into MongoDB, then finalize
  ``commit_stats.profanity_rate`` / ``emoji_rate`` / ``emoji_top``.
* :func:`run_one_file` — ingest a single hourly file (for tests and
  ad-hoc reruns).

Every other symbol is internal (``_``-prefixed module) and must not be
imported from outside this package.
"""

from __future__ import annotations

from ._runner import run, run_one_file

__all__ = ["run", "run_one_file"]
