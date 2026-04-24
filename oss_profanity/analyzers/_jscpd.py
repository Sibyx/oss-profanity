"""jscpd wrapper: polyglot copy-paste duplication.

Writes its JSON report to a temp dir via ``--output``; we read
``jscpd-report.json`` after the run. The ``statistics.total`` block
carries the repo-level totals we need (``duplicatedLines``, ``lines``).

All-``None`` on any failure mode (missing binary, timeout, missing
report, unexpected schema).
"""

from __future__ import annotations

import json
import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path

from ._subprocess_util import run_tool

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class JscpdResult:
    """Absolute duplicated-line and total-line counts from one jscpd run."""

    duplicate_lines: int | None = None
    total_lines: int | None = None


def run(repo_dir: Path, timeout: int = 180) -> JscpdResult:
    """Run jscpd on ``repo_dir``; return duplicate + total line counts."""
    with tempfile.TemporaryDirectory(prefix="jscpd-") as tmp:
        proc = run_tool(
            [
                "jscpd",
                "--silent",
                "--reporters",
                "json",
                "--output",
                tmp,
                str(repo_dir),
            ],
            timeout=timeout,
        )
        if proc is None:
            return JscpdResult()
        report_path = Path(tmp) / "jscpd-report.json"
        if not report_path.exists():
            return JscpdResult()
        try:
            report = json.loads(report_path.read_bytes())
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("jscpd report read error: %s", exc)
            return JscpdResult()

    stats = (
        report.get("statistics") if isinstance(report, dict) else None
    )
    total_block = (
        stats.get("total") if isinstance(stats, dict) else None
    )
    if not isinstance(total_block, dict):
        return JscpdResult()

    try:
        duplicated = int(total_block.get("duplicatedLines", 0))
        lines = int(total_block.get("lines", 0))
    except (TypeError, ValueError):
        return JscpdResult()
    return JscpdResult(duplicate_lines=duplicated, total_lines=lines)
