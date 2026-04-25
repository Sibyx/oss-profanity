"""Ruff wrapper with bug-vs-style single-run partition.

One ``ruff check`` invocation with a broad ``--select`` set; the JSON
array comes back with a ``code`` field per finding. We partition locally
by rule-code prefix — bug-class prefixes (``F``, ``E9``, ``B``, ``S``,
``RUF``) get counted as bugs; everything else is style. An unknown
upstream rule family defaults to style, which under-reports bugs rather
than inventing them.

``--exit-zero`` so we only read non-zero as "tool error." Exit code 2
explicitly means ruff crashed.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from ._subprocess_util import run_tool

logger = logging.getLogger(__name__)

_SELECT: Final[str] = "E,W,F,I,N,UP,B,A,C4,SIM,RUF,S"
_BUG_PREFIXES: Final[tuple[str, ...]] = ("F", "E9", "B", "S", "RUF")


@dataclass(frozen=True, slots=True)
class RuffResult:
    """Ruff findings broken into total / bug / style / fixable counts.

    ``fixable`` counts findings whose JSON ``fix`` element is non-null
    (ruff would auto-apply a fix with ``--fix``). Provides a fix-rate
    axis comparable to ESLint's ``fixable_errors + fixable_warnings``.
    """

    total: int | None = None
    bug: int | None = None
    style: int | None = None
    fixable: int | None = None


def run(repo_dir: Path, timeout: int = 120) -> RuffResult:
    """Run ruff over ``repo_dir``; return split findings."""
    proc = run_tool(
        [
            "ruff",
            "check",
            "--output-format=json",
            "--exit-zero",
            f"--select={_SELECT}",
            str(repo_dir),
        ],
        timeout=timeout,
    )
    if proc is None or proc.returncode != 0:
        return RuffResult()

    try:
        findings = json.loads(proc.stdout or b"[]")
    except json.JSONDecodeError as exc:
        logger.warning("ruff JSON parse error: %s", exc)
        return RuffResult()

    if not isinstance(findings, list):
        return RuffResult()

    bug = 0
    style = 0
    fixable = 0
    for item in findings:
        if not isinstance(item, dict):
            continue
        code = item.get("code", "")
        if _is_bug_code(code):
            bug += 1
        else:
            style += 1
        if item.get("fix") is not None:
            fixable += 1
    return RuffResult(total=bug + style, bug=bug, style=style, fixable=fixable)


def _is_bug_code(code: str) -> bool:
    return any(code.startswith(p) for p in _BUG_PREFIXES)
