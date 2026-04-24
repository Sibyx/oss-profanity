"""Per-process main loop (IP-007).

Claims ``pending`` repos one at a time via IP-001's atomic primitive;
on empty queue, reclaims stale claims and checks the terminal
condition (``claimed`` count drops to 0 → all work done). Honours a
cooperative shutdown flag tripped by SIGTERM / SIGINT so an in-flight
repo finishes before exit rather than dying mid-analysis.
"""

from __future__ import annotations

import logging
import signal
import time
from types import FrameType

from ..db import claim_next_repo, get_db, make_worker_id, reclaim_stale
from . import _processor, _scratch

logger = logging.getLogger(__name__)

_EMPTY_QUEUE_SLEEP_SEC = 10.0

_shutdown_requested = False


def _request_shutdown(
    signum: int, frame: FrameType | None
) -> None:  # pragma: no cover - exercised via signal
    global _shutdown_requested
    if _shutdown_requested:
        logger.warning(
            "loop: second shutdown signal %d received; kernel SIGKILL next", signum
        )
        return
    logger.info("loop: shutdown signal %d received; finishing current repo", signum)
    _shutdown_requested = True


def run(worker_id: str | None = None) -> None:
    """Main per-process claim loop; returns when the cohort is drained."""
    global _shutdown_requested
    _shutdown_requested = False

    wid = worker_id or make_worker_id()
    signal.signal(signal.SIGTERM, _request_shutdown)
    signal.signal(signal.SIGINT, _request_shutdown)

    _scratch.setup(wid)
    logger.info("loop: started", extra={"worker_id": wid})

    while not _shutdown_requested:
        repo = claim_next_repo(wid)
        if repo is not None:
            _processor.process_one(repo, wid)
            continue

        # Empty pending queue → try to reclaim stale claims; exit if drained.
        reclaimed = reclaim_stale()
        if reclaimed > 0:
            logger.info("loop: reclaimed %d stale claims", reclaimed)
            continue

        claimed = get_db().repos.count_documents({"status": "claimed"})
        if claimed == 0:
            logger.info("loop: cohort drained; exiting")
            return

        # Other workers still processing; wait and retry.
        time.sleep(_EMPTY_QUEUE_SLEEP_SEC)

    logger.info("loop: exiting on cooperative shutdown", extra={"worker_id": wid})
