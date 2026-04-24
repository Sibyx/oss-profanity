"""Lizard wrapper: cyclomatic complexity + length metrics with percentiles.

Lizard has no JSON output as of v1.22; its XML form (``-X``) is the
cleanest integration path. The footer summary lizard prints to stdout
isn't in the XML body, so we aggregate mean / max / count / p50 / p90 /
p99 from the per-function records ourselves.

All-``None`` return on any failure mode (timeout, non-zero exit, XML we
can't parse). The ``_runner`` propagates ``None`` into the final dict;
IP-008 treats ``None`` as "no data" rather than "zero."
"""

from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

from ._subprocess_util import run_tool

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class LizardResult:
    """Per-repo aggregate complexity metrics. Fields are ``None`` if
    lizard failed or the repo had no parseable source."""

    avg_ccn: float | None = None
    max_ccn: int | None = None
    functions: int | None = None
    ccn_p50: float | None = None
    ccn_p90: float | None = None
    ccn_p99: float | None = None
    nloc_p90: int | None = None


def run(repo_dir: Path, timeout: int = 120) -> LizardResult:
    """Run lizard on ``repo_dir``; return aggregated metrics."""
    proc = run_tool(["lizard", "-X", str(repo_dir)], timeout=timeout)
    if proc is None or proc.returncode != 0 or not proc.stdout:
        return LizardResult()
    return _parse_xml(proc.stdout)


def _parse_xml(xml_bytes: bytes) -> LizardResult:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        logger.warning("lizard XML parse error: %s", exc)
        return LizardResult()

    # lizard's cppncss-style XML nests per-function records under
    # <measure type="Function"><item name="..."> with <value> children.
    # Schema excerpt (stable since lizard 1.17):
    #   <measure type="Function">
    #     <labels> <label>NLOC</label> <label>CCN</label> ... </labels>
    #     <item name="foo@1-10@path"> <value>12</value> <value>3</value> ...
    function_measure = None
    for measure in root.iter("measure"):
        if measure.get("type") == "Function":
            function_measure = measure
            break
    if function_measure is None:
        return LizardResult()

    labels_element = function_measure.find("labels")
    labels: list[str] = (
        [lbl.text or "" for lbl in labels_element]
        if labels_element is not None
        else []
    )
    # lizard's own column name for lines-of-code is "NCSS" (Non-Commented
    # Source Statements); some forks / older versions emit "NLOC". Accept
    # either.
    nloc_idx = _first_label_index(labels, ("NCSS", "NLOC"))
    ccn_idx = _first_label_index(labels, ("CCN",))
    if nloc_idx is None or ccn_idx is None:
        logger.warning("lizard XML missing NCSS/CCN labels: %r", labels)
        return LizardResult()

    ccns: list[int] = []
    nlocs: list[int] = []
    for item in function_measure.iter("item"):
        values = [v.text or "" for v in item.findall("value")]
        if len(values) <= max(nloc_idx, ccn_idx):
            continue
        try:
            nlocs.append(int(values[nloc_idx]))
            ccns.append(int(values[ccn_idx]))
        except ValueError:
            continue

    if not ccns:
        return LizardResult()

    avg_ccn = statistics.mean(ccns)
    max_ccn = max(ccns)
    ccn_p50: float | None = None
    ccn_p90: float | None = None
    ccn_p99: float | None = None
    nloc_p90: int | None = None
    if len(ccns) >= 2:
        ccn_sorted = sorted(ccns)
        nloc_sorted = sorted(nlocs)
        ccn_p50 = _percentile(ccn_sorted, 50)
        ccn_p90 = _percentile(ccn_sorted, 90)
        ccn_p99 = _percentile(ccn_sorted, 99)
        nloc_p90 = int(_percentile(nloc_sorted, 90))

    return LizardResult(
        avg_ccn=avg_ccn,
        max_ccn=max_ccn,
        functions=len(ccns),
        ccn_p50=ccn_p50,
        ccn_p90=ccn_p90,
        ccn_p99=ccn_p99,
        nloc_p90=nloc_p90,
    )


def _first_label_index(
    labels: list[str], candidates: tuple[str, ...]
) -> int | None:
    for name in candidates:
        try:
            return labels.index(name)
        except ValueError:
            continue
    return None


def _percentile(sorted_values: list[int], q: int) -> float:
    """Linear-interpolation percentile on a pre-sorted ascending list.

    ``sorted_values`` must have at least 2 elements (callers guard).
    """
    if not sorted_values:
        return 0.0
    rank = (q / 100.0) * (len(sorted_values) - 1)
    lo = int(rank)
    hi = min(lo + 1, len(sorted_values) - 1)
    frac = rank - lo
    return sorted_values[lo] * (1 - frac) + sorted_values[hi] * frac
