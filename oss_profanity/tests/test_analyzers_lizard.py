"""Lizard wrapper: real runs on fixture code + percentile edge cases."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from oss_profanity.analyzers import _lizard
from oss_profanity.analyzers._lizard import LizardResult, run


_LIZARD_AVAILABLE = shutil.which("lizard") is not None
skip_without_lizard = pytest.mark.skipif(
    not _LIZARD_AVAILABLE,
    reason="lizard binary not on PATH",
)


@skip_without_lizard
def test_lizard_populates_metrics_on_real_fixture(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text(
        """
def simple():
    return 1

def branchy(x):
    if x > 0:
        if x > 10:
            return 'big'
        return 'small'
    return 'none'
""",
        encoding="utf-8",
    )
    result = run(tmp_path)
    assert result.functions is not None and result.functions >= 2
    assert result.avg_ccn is not None and result.avg_ccn > 0
    assert result.max_ccn is not None and result.max_ccn >= 3
    # Two functions is the minimum for percentiles.
    assert result.ccn_p50 is not None
    assert result.ccn_p90 is not None
    assert result.ccn_p99 is not None
    assert result.nloc_p90 is not None


@skip_without_lizard
def test_lizard_single_function_sets_mean_but_not_percentiles(
    tmp_path: Path,
) -> None:
    (tmp_path / "one.py").write_text(
        "def f():\n    return 1\n", encoding="utf-8"
    )
    result = run(tmp_path)
    assert result.functions == 1
    assert result.avg_ccn is not None
    assert result.max_ccn is not None
    # Percentiles need >= 2 samples — guard in the wrapper.
    assert result.ccn_p50 is None
    assert result.ccn_p90 is None
    assert result.ccn_p99 is None
    assert result.nloc_p90 is None


@skip_without_lizard
def test_lizard_empty_dir_returns_all_none(tmp_path: Path) -> None:
    result = run(tmp_path)
    assert result == LizardResult()


def test_lizard_returns_all_none_when_binary_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the binary is absent, ``_subprocess_util.run_tool`` returns
    ``None``; the wrapper must degrade to all-``None`` rather than
    crashing."""
    monkeypatch.setattr(_lizard, "run_tool", lambda *a, **k: None)
    result = run(tmp_path)
    assert result == LizardResult()


def test_lizard_parse_error_returns_all_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import subprocess

    fake = subprocess.CompletedProcess(
        args=["lizard"], returncode=0, stdout=b"<not-xml>garbage", stderr=b""
    )
    monkeypatch.setattr(_lizard, "run_tool", lambda *a, **k: fake)
    result = run(tmp_path)
    assert result == LizardResult()


def test_percentile_helper_interpolates() -> None:
    # p50 of [1, 2, 3, 4, 5] should be 3.0
    assert _lizard._percentile([1, 2, 3, 4, 5], 50) == 3.0
    # p0 → min, p100 → max
    assert _lizard._percentile([1, 2, 3, 4, 5], 0) == 1.0
    assert _lizard._percentile([1, 2, 3, 4, 5], 100) == 5.0
