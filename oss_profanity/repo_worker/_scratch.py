"""Per-worker scratch directory layout + cleanup.

Clones land under ``{scratch_dir}/{worker_id}/{repo_id}``. The worker-id
namespace eliminates collisions with the stale-claim reaper's race
(where a second worker re-claims a repo while the first worker's
``finally: rmtree`` is still running on slow storage).
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from ..config import config

logger = logging.getLogger(__name__)


def clone_path(repo_id: int, worker_id: str) -> Path:
    """Per-worker, per-repo clone directory (no I/O)."""
    return Path(config.scratch_dir) / worker_id / str(repo_id)


def setup(worker_id: str) -> None:
    """Wipe the per-worker subtree at loop entry.

    Defends against a previous same-id run (random hex in worker ID makes
    collisions vanishingly rare but the sweep is cheap insurance).
    """
    root = Path(config.scratch_dir) / worker_id
    if root.exists():
        logger.info("scratch: sweeping stale subtree %s", root)
        shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)


def cleanup(path: Path) -> None:
    """Best-effort ``rmtree`` — never blocks exit, safe on non-existent paths."""
    shutil.rmtree(path, ignore_errors=True)
