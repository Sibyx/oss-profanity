"""ESLint wrapper: JS/TS linter under the flat-config regime.

ESLint v10 (Feb 2026) removed ``--no-eslintrc`` and the ``.eslintrc.*``
system entirely. The portable invocation is
``--no-config-lookup --config <path>`` pointed at a flat config file
shipped by IP-009's Dockerfile at ``/opt/baseline-eslint.config.mjs``.

On a worker host without ESLint installed (local dev, CI without Node),
the wrapper returns ``None`` rather than crashing — the field is
recorded as missing and IP-008 filters those repos out of JS/TS
correlations.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Final

from ._subprocess_util import run_tool

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG: Final[str] = "/opt/baseline-eslint.config.mjs"


def run(
    repo_dir: Path,
    timeout: int = 180,
    config_path: str = _DEFAULT_CONFIG,
) -> int | None:
    """Run eslint over ``repo_dir``; return total (error + warning) count.

    ``None`` on missing binary, missing config, timeout, non-zero exit
    without valid JSON stdout, or unparseable output.
    """
    proc = run_tool(
        [
            "eslint",
            "--no-config-lookup",
            "--config",
            config_path,
            "--format=json",
            str(repo_dir),
        ],
        timeout=timeout,
    )
    if proc is None:
        return None
    # eslint exits non-zero when findings are present; that's fine. Empty
    # stdout with a non-zero exit means config/load error.
    if not proc.stdout and proc.returncode != 0:
        return None

    try:
        per_file = json.loads(proc.stdout or b"[]")
    except json.JSONDecodeError as exc:
        logger.warning("eslint JSON parse error: %s", exc)
        return None

    if not isinstance(per_file, list):
        return None

    total = 0
    for entry in per_file:
        if not isinstance(entry, dict):
            continue
        total += int(entry.get("errorCount", 0) or 0)
        total += int(entry.get("warningCount", 0) or 0)
    return total
