"""Bandit wrapper: Python security scanner.

Reports total findings and the high-severity subset. Bandit's JSON
output has a ``results`` array with per-issue ``issue_severity``
(``LOW`` / ``MEDIUM`` / ``HIGH``). ``--exit-zero`` so we only read
non-zero as "tool error" (bandit exits non-zero when findings exist,
which is not an error for our purposes).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from ._subprocess_util import run_tool

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class BanditResult:
    """Bandit total + high-severity counts."""

    total: int | None = None
    high_severity: int | None = None


def run(repo_dir: Path, timeout: int = 120) -> BanditResult:
    """Run bandit recursively over ``repo_dir``."""
    proc = run_tool(
        [
            "bandit",
            "-r",
            "-f",
            "json",
            "--exit-zero",
            "--quiet",
            str(repo_dir),
        ],
        timeout=timeout,
    )
    if proc is None or proc.returncode != 0 or not proc.stdout:
        return BanditResult()

    try:
        report = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        logger.warning("bandit JSON parse error: %s", exc)
        return BanditResult()

    results = report.get("results") if isinstance(report, dict) else None
    if not isinstance(results, list):
        return BanditResult(total=0, high_severity=0)

    total = len(results)
    high = sum(
        1
        for r in results
        if isinstance(r, dict) and r.get("issue_severity") == "HIGH"
    )
    return BanditResult(total=total, high_severity=high)
