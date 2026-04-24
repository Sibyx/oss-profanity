"""Subprocess-backed tool wrappers: ruff, bandit, eslint, jscpd.

Bandit runs for real (it's a Python dep and lives in the venv). Ruff,
eslint, and jscpd are typically not installed on the test machine — the
accepted proposal explicitly notes those are "real in the Docker harness
only." Here we exercise them by monkeypatching ``_subprocess_util.run_tool``
with known outputs, which is how the proposal's Phase 5 test plan reads.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from oss_profanity.analyzers import _bandit, _eslint, _jscpd, _ruff
from oss_profanity.analyzers._bandit import BanditResult, run as bandit_run
from oss_profanity.analyzers._eslint import run as eslint_run
from oss_profanity.analyzers._jscpd import JscpdResult, run as jscpd_run
from oss_profanity.analyzers._ruff import RuffResult, run as ruff_run


def _fake_proc(
    stdout: bytes = b"", returncode: int = 0
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.CompletedProcess(
        args=["x"], returncode=returncode, stdout=stdout, stderr=b""
    )


# ---------- ruff ----------


def test_ruff_partitions_bug_vs_style(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    findings = [
        {"code": "F401", "message": "unused import"},
        {"code": "F811", "message": "redefinition"},
        {"code": "B008", "message": "mutable default"},
        {"code": "E501", "message": "line too long"},
        {"code": "W605", "message": "invalid escape"},
        {"code": "I001", "message": "unsorted imports"},
        {"code": "N806", "message": "uppercase variable"},
        {"code": "RUF100", "message": "unused noqa"},
    ]
    monkeypatch.setattr(
        _ruff,
        "run_tool",
        lambda *a, **k: _fake_proc(json.dumps(findings).encode()),
    )
    result = ruff_run(tmp_path)
    # F* and B* and RUF* are bugs → 4; the rest (E, W, I, N) → 4 style.
    assert result.bug == 4
    assert result.style == 4
    assert result.total == 8
    # Parity assertion from Success Criteria.
    assert result.total == (result.bug or 0) + (result.style or 0)


def test_ruff_empty_findings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        _ruff, "run_tool", lambda *a, **k: _fake_proc(b"[]")
    )
    result = ruff_run(tmp_path)
    assert result == RuffResult(total=0, bug=0, style=0)


def test_ruff_exit_code_2_is_tool_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        _ruff, "run_tool", lambda *a, **k: _fake_proc(b"", returncode=2)
    )
    result = ruff_run(tmp_path)
    assert result == RuffResult()


def test_ruff_returns_default_when_binary_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_ruff, "run_tool", lambda *a, **k: None)
    result = ruff_run(tmp_path)
    assert result == RuffResult()


def test_ruff_invalid_json_returns_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        _ruff, "run_tool", lambda *a, **k: _fake_proc(b"not-json")
    )
    result = ruff_run(tmp_path)
    assert result == RuffResult()


# ---------- bandit ----------


_BANDIT_AVAILABLE = shutil.which("bandit") is not None


@pytest.mark.skipif(
    not _BANDIT_AVAILABLE, reason="bandit binary not on PATH"
)
def test_bandit_flags_real_eval_call(tmp_path: Path) -> None:
    (tmp_path / "unsafe.py").write_text(
        "def run(code):\n    return eval(code)\n",
        encoding="utf-8",
    )
    result = bandit_run(tmp_path)
    # eval() is a classic B307; bandit should flag at least one issue.
    assert result.total is not None and result.total >= 1
    # It's high-severity — assert the severity path is wired correctly.
    assert result.high_severity is not None


@pytest.mark.skipif(
    not _BANDIT_AVAILABLE, reason="bandit binary not on PATH"
)
def test_bandit_clean_file_zero_findings(tmp_path: Path) -> None:
    (tmp_path / "clean.py").write_text(
        "def add(a, b):\n    return a + b\n", encoding="utf-8"
    )
    result = bandit_run(tmp_path)
    assert result.total == 0
    assert result.high_severity == 0


def test_bandit_missing_binary_returns_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_bandit, "run_tool", lambda *a, **k: None)
    result = bandit_run(tmp_path)
    assert result == BanditResult()


def test_bandit_handles_bad_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        _bandit, "run_tool", lambda *a, **k: _fake_proc(b"garbage")
    )
    result = bandit_run(tmp_path)
    assert result == BanditResult()


# ---------- eslint ----------


def test_eslint_sums_errors_and_warnings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    per_file = [
        {"filePath": "a.js", "errorCount": 2, "warningCount": 1},
        {"filePath": "b.js", "errorCount": 0, "warningCount": 3},
        {"filePath": "c.js", "errorCount": 5, "warningCount": 0},
    ]
    monkeypatch.setattr(
        _eslint,
        "run_tool",
        lambda *a, **k: _fake_proc(json.dumps(per_file).encode()),
    )
    assert eslint_run(tmp_path) == 2 + 1 + 0 + 3 + 5 + 0


def test_eslint_empty_output_returns_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        _eslint, "run_tool", lambda *a, **k: _fake_proc(b"[]")
    )
    assert eslint_run(tmp_path) == 0


def test_eslint_missing_binary_returns_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_eslint, "run_tool", lambda *a, **k: None)
    assert eslint_run(tmp_path) is None


def test_eslint_empty_stdout_with_nonzero_exit_is_config_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        _eslint,
        "run_tool",
        lambda *a, **k: _fake_proc(b"", returncode=2),
    )
    assert eslint_run(tmp_path) is None


def test_eslint_invalid_json_returns_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        _eslint, "run_tool", lambda *a, **k: _fake_proc(b"{not valid")
    )
    assert eslint_run(tmp_path) is None


# ---------- jscpd ----------


def test_jscpd_reads_report_totals(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = {
        "statistics": {
            "total": {"duplicatedLines": 42, "lines": 1000},
        }
    }

    def fake_run_tool(
        argv: list[str], timeout: int
    ) -> subprocess.CompletedProcess[bytes]:
        # ``jscpd`` writes its JSON report to the ``--output`` dir; find
        # that path in the argv and write the fake report there.
        out_idx = argv.index("--output")
        out_dir = Path(argv[out_idx + 1])
        (out_dir / "jscpd-report.json").write_bytes(
            json.dumps(report).encode()
        )
        return _fake_proc(b"")

    monkeypatch.setattr(_jscpd, "run_tool", fake_run_tool)
    result = jscpd_run(tmp_path)
    assert result == JscpdResult(duplicate_lines=42, total_lines=1000)


def test_jscpd_missing_binary_returns_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_jscpd, "run_tool", lambda *a, **k: None)
    assert jscpd_run(tmp_path) == JscpdResult()


def test_jscpd_missing_report_file_returns_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Binary "ran" but didn't produce the report JSON.
    monkeypatch.setattr(
        _jscpd, "run_tool", lambda *a, **k: _fake_proc(b"")
    )
    assert jscpd_run(tmp_path) == JscpdResult()


def test_jscpd_bad_schema_returns_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_run_tool(
        argv: list[str], timeout: int
    ) -> subprocess.CompletedProcess[bytes]:
        out_idx = argv.index("--output")
        out_dir = Path(argv[out_idx + 1])
        (out_dir / "jscpd-report.json").write_bytes(b'{"wrong": "shape"}')
        return _fake_proc(b"")

    monkeypatch.setattr(_jscpd, "run_tool", fake_run_tool)
    assert jscpd_run(tmp_path) == JscpdResult()
