"""Shared subprocess wrapper for the five external tool runners.

Catches the three failure modes every wrapper has to handle identically
(``TimeoutExpired``, ``FileNotFoundError`` for a missing binary, generic
``OSError`` for exec failures) and returns ``None`` on any of them so
callers never have to think about subprocess exceptions.
"""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Sequence

logger = logging.getLogger(__name__)


def run_tool(
    argv: Sequence[str], timeout: int
) -> subprocess.CompletedProcess[bytes] | None:
    """Run ``argv`` with a ``timeout``; return ``None`` on any failure.

    Captures stdout + stderr as bytes (callers parse either JSON or XML;
    bytes avoid decode errors on ill-formed tool output). ``check=False``
    because every caller inspects the return code itself — most tools
    signal "findings present" with non-zero exits we want to treat as
    success.
    """
    try:
        return subprocess.run(
            list(argv),
            capture_output=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        logger.warning("tool timed out after %ss: %s", timeout, argv[0])
        return None
    except FileNotFoundError:
        logger.warning("tool binary not found on PATH: %s", argv[0])
        return None
    except OSError as exc:
        logger.warning("tool %s failed to exec: %s", argv[0], exc)
        return None
