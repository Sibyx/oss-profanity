"""Parallel orchestrator: dispatch + composition + failure isolation."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

import pytest

from oss_profanity.analyzers import run_all
from oss_profanity.analyzers import (
    _bandit,
    _eslint,
    _jscpd,
    _lizard,
    _runner,
    _source_scan,
)
from oss_profanity.analyzers._bandit import BanditResult
from oss_profanity.analyzers._jscpd import JscpdResult
from oss_profanity.analyzers._lizard import LizardResult
from oss_profanity.analyzers._ruff import RuffResult
from oss_profanity.analyzers._source_scan import SourceScanResult


def _stub_source_scan(
    loc: int = 1000, files: int = 10
) -> SourceScanResult:
    return SourceScanResult(
        loc_total=loc,
        files_scanned=files,
        comment_nloc=200,
        comment_to_code_ratio=0.2,
        comment_profanity_hits=3,
        identifier_profanity_hits=1,
        comment_emoji_hits=5,
        identifier_emoji_hits=0,
        emoji_top={"🚀": 3, "🐛": 2},
        tech_debt_markers=4,
    )


def test_run_all_returns_code_analysis_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``run_all`` composes all sub-results into the expected dict shape
    with every field present, keyed to IP-001's ``CodeAnalysis``."""
    monkeypatch.setattr(
        _source_scan, "scan_source_tree", lambda p: _stub_source_scan()
    )
    monkeypatch.setattr(
        _lizard,
        "run",
        lambda p: LizardResult(
            avg_ccn=2.5,
            max_ccn=8,
            functions=12,
            ccn_p50=2.0,
            ccn_p90=6.0,
            ccn_p99=8.0,
            nloc_p90=15,
        ),
    )
    monkeypatch.setattr(
        _jscpd,
        "run",
        lambda p: JscpdResult(duplicate_lines=50, total_lines=1200),
    )
    monkeypatch.setattr(
        _runner._ruff,
        "run",
        lambda p: RuffResult(total=20, bug=5, style=15),
    )
    monkeypatch.setattr(
        _bandit,
        "run",
        lambda p: BanditResult(total=3, high_severity=1),
    )

    result = run_all(tmp_path, "python")

    # Load-bearing keys match the schema.
    expected_keys = {
        "loc_total",
        "files_scanned",
        "comment_nloc",
        "comment_to_code_ratio",
        "comment_profanity_hits",
        "identifier_profanity_hits",
        "comment_emoji_hits",
        "identifier_emoji_hits",
        "emoji_top",
        "tech_debt_markers",
        "ruff_issues",
        "ruff_bug_issues",
        "ruff_style_issues",
        "ruff_issues_per_kloc",
        "ruff_bug_issues_per_kloc",
        "ruff_style_issues_per_kloc",
        "bandit_issues",
        "bandit_high_severity",
        "bandit_issues_per_kloc",
        "eslint_issues",
        "eslint_issues_per_kloc",
        "jscpd_duplicate_lines",
        "jscpd_total_lines",
        "jscpd_duplicate_rate",
        "lizard_avg_ccn",
        "lizard_max_ccn",
        "lizard_functions",
        "lizard_ccn_p50",
        "lizard_ccn_p90",
        "lizard_ccn_p99",
        "lizard_nloc_p90",
    }
    assert set(result.keys()) == expected_keys


def test_run_all_per_kloc_normalization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        _source_scan, "scan_source_tree", lambda p: _stub_source_scan(loc=2000)
    )
    monkeypatch.setattr(_lizard, "run", lambda p: LizardResult())
    monkeypatch.setattr(_jscpd, "run", lambda p: JscpdResult())
    monkeypatch.setattr(
        _runner._ruff,
        "run",
        lambda p: RuffResult(total=20, bug=10, style=10),
    )
    monkeypatch.setattr(
        _bandit, "run", lambda p: BanditResult(total=4, high_severity=1)
    )

    result = run_all(tmp_path, "python")
    # 20 issues over 2000 LOC = 10 per KLOC.
    assert result["ruff_issues_per_kloc"] == 10.0
    assert result["ruff_bug_issues_per_kloc"] == 5.0
    assert result["bandit_issues_per_kloc"] == 2.0


def test_run_all_only_dispatches_language_applicable_tools(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A JS/TS repo must not invoke ruff or bandit, only eslint."""
    called: set[str] = set()

    def mark(name: str) -> Any:
        def _f(p: Path) -> Any:
            called.add(name)
            if name == "ruff":
                return RuffResult()
            if name == "bandit":
                return BanditResult()
            if name == "eslint":
                return 0
            if name == "lizard":
                return LizardResult()
            if name == "jscpd":
                return JscpdResult()
            return _stub_source_scan()

        return _f

    monkeypatch.setattr(_source_scan, "scan_source_tree", mark("walk"))
    monkeypatch.setattr(_lizard, "run", mark("lizard"))
    monkeypatch.setattr(_jscpd, "run", mark("jscpd"))
    monkeypatch.setattr(_runner._ruff, "run", mark("ruff"))
    monkeypatch.setattr(_bandit, "run", mark("bandit"))
    monkeypatch.setattr(_eslint, "run", mark("eslint"))

    run_all(tmp_path, "javascript")
    assert "eslint" in called
    assert "ruff" not in called
    assert "bandit" not in called


def test_run_all_dispatches_walk_and_tools_in_parallel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The Success Criterion: every applicable runner starts within a
    ~50 ms window. If anything is accidentally serialized, the spread
    grows to the sum of per-task sleeps."""
    start_times: dict[str, float] = {}
    lock = threading.Lock()

    def tagged(name: str, ret: Any) -> Any:
        def _f(p: Path) -> Any:
            with lock:
                start_times[name] = time.monotonic()
            time.sleep(0.2)
            return ret

        return _f

    monkeypatch.setattr(
        _source_scan,
        "scan_source_tree",
        tagged("walk", _stub_source_scan()),
    )
    monkeypatch.setattr(_lizard, "run", tagged("lizard", LizardResult()))
    monkeypatch.setattr(_jscpd, "run", tagged("jscpd", JscpdResult()))
    monkeypatch.setattr(_runner._ruff, "run", tagged("ruff", RuffResult()))
    monkeypatch.setattr(
        _bandit, "run", tagged("bandit", BanditResult())
    )

    t0 = time.monotonic()
    run_all(tmp_path, "python")
    elapsed = time.monotonic() - t0

    assert set(start_times) == {"walk", "lizard", "jscpd", "ruff", "bandit"}
    # Pool cap is 4: four tasks fire immediately; the 5th waits for one
    # to free the pool. Measure the first 4 starts.
    spread_of_first_four = sorted(start_times.values())[3] - min(
        start_times.values()
    )
    assert spread_of_first_four < 0.05, (
        f"first-four dispatch spread {spread_of_first_four:.3f}s — serialized?"
    )
    # End-to-end should be ~ 0.4s (two waves of 0.2s each), well under
    # the serial worst-case of 1.0s.
    assert elapsed < 0.6, f"run_all elapsed {elapsed:.3f}s suggests serial"


def test_run_all_isolates_runner_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A runner that raises must not crash the orchestrator — it
    records the default result and the rest of the dict ships."""

    def boom(p: Path) -> LizardResult:
        raise RuntimeError("simulated tool crash")

    monkeypatch.setattr(
        _source_scan, "scan_source_tree", lambda p: _stub_source_scan()
    )
    monkeypatch.setattr(_lizard, "run", boom)
    monkeypatch.setattr(_jscpd, "run", lambda p: JscpdResult())
    monkeypatch.setattr(
        _runner._ruff,
        "run",
        lambda p: RuffResult(total=5, bug=2, style=3),
    )
    monkeypatch.setattr(_bandit, "run", lambda p: BanditResult())

    result = run_all(tmp_path, "python")
    # Lizard fields are None (default result), other fields survived.
    assert result["lizard_avg_ccn"] is None
    assert result["lizard_functions"] is None
    assert result["ruff_issues"] == 5


def test_run_all_with_no_language_skips_linters(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unknown language → no ruff, bandit, or eslint; walk + lizard +
    jscpd still run."""
    calls: list[str] = []

    def mark(name: str, ret: Any) -> Any:
        def _f(p: Path) -> Any:
            calls.append(name)
            return ret

        return _f

    monkeypatch.setattr(
        _source_scan,
        "scan_source_tree",
        mark("walk", _stub_source_scan()),
    )
    monkeypatch.setattr(_lizard, "run", mark("lizard", LizardResult()))
    monkeypatch.setattr(_jscpd, "run", mark("jscpd", JscpdResult()))
    monkeypatch.setattr(_runner._ruff, "run", mark("ruff", RuffResult()))
    monkeypatch.setattr(_bandit, "run", mark("bandit", BanditResult()))
    monkeypatch.setattr(_eslint, "run", mark("eslint", None))

    run_all(tmp_path, None)
    assert "walk" in calls
    assert "lizard" in calls
    assert "jscpd" in calls
    assert "ruff" not in calls
    assert "bandit" not in calls
    assert "eslint" not in calls


def test_per_kloc_helper_guards_zero_loc() -> None:
    # Direct unit: zero LOC → None, never divide-by-zero.
    assert _runner._per_kloc(5, 0) is None
    assert _runner._per_kloc(None, 1000) is None
    assert _runner._per_kloc(5, 1000) == 5.0
