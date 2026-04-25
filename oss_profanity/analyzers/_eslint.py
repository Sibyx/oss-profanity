"""ESLint wrapper: JS/TS linter under the flat-config regime.

ESLint v10 (Feb 2026) removed ``--no-eslintrc`` and the ``.eslintrc.*``
system entirely. The portable invocation is
``--no-config-lookup --config <path>`` pointed at a flat config file
shipped by IP-013's Dockerfile at ``/opt/node-tools/eslint.config.mjs``.

The config path is read from ``oss_profanity.config.config.eslint_config_path``
(env ``ESLINT_CONFIG_PATH``), so deployments that mount the toolchain
elsewhere can override it without touching this module.

On a worker host without ESLint installed (local dev, CI without Node),
the wrapper returns an all-``None`` ``EslintResult`` rather than crashing
— the field is recorded as missing and IP-008 filters those repos out
of JS/TS correlations.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from oss_profanity.config import config

from ._subprocess_util import run_tool

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class EslintResult:
    """ESLint findings broken into the six counts ESLint emits per file.

    ``total = errors + warnings``. ``fatal_errors`` are parse / config
    failures and intentionally do **not** roll into ``total`` — they
    represent files ESLint could not analyse, not lint findings.
    All six fields are populated together; all ``None`` on any failure
    path (missing binary, missing config, timeout, non-zero exit
    without valid JSON stdout, unparseable output).
    """

    errors: int | None = None
    warnings: int | None = None
    fatal_errors: int | None = None
    fixable_errors: int | None = None
    fixable_warnings: int | None = None
    total: int | None = None


def run(repo_dir: Path, timeout: int = 180) -> EslintResult:
    """Run eslint over ``repo_dir``; return a fully-populated ``EslintResult``."""
    proc = run_tool(
        [
            "eslint",
            "--no-config-lookup",
            "--config",
            config.eslint_config_path,
            "--format=json",
            str(repo_dir),
        ],
        timeout=timeout,
    )
    if proc is None:
        return EslintResult()
    # eslint exits non-zero when findings are present; that's fine. Empty
    # stdout with a non-zero exit means config/load error.
    if not proc.stdout and proc.returncode != 0:
        return EslintResult()

    try:
        per_file = json.loads(proc.stdout or b"[]")
    except json.JSONDecodeError as exc:
        logger.warning("eslint JSON parse error: %s", exc)
        return EslintResult()

    if not isinstance(per_file, list):
        return EslintResult()

    errors = 0
    warnings = 0
    fatal_errors = 0
    fixable_errors = 0
    fixable_warnings = 0
    for entry in per_file:
        if not isinstance(entry, dict):
            continue
        errors += int(entry.get("errorCount", 0) or 0)
        warnings += int(entry.get("warningCount", 0) or 0)
        fatal_errors += int(entry.get("fatalErrorCount", 0) or 0)
        fixable_errors += int(entry.get("fixableErrorCount", 0) or 0)
        fixable_warnings += int(entry.get("fixableWarningCount", 0) or 0)
    return EslintResult(
        errors=errors,
        warnings=warnings,
        fatal_errors=fatal_errors,
        fixable_errors=fixable_errors,
        fixable_warnings=fixable_warnings,
        total=errors + warnings,
    )
