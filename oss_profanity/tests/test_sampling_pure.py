"""Pure (no Mongo) tests for the IP-006 sampling module.

Covers the binner, the ``_bin_range`` helper, and the public surface.
"""

from __future__ import annotations

import pytest

from oss_profanity import sampling


# ---------- public surface ----------


def test_public_surface() -> None:
    """Only ``run`` is the documented public name."""
    assert callable(sampling.run)


# ---------- _bin_candidates ----------


def _cand(repo_id: int, commits: int) -> sampling._Candidate:
    return sampling._Candidate(id=repo_id, commits=commits)


BINS = (20, 50, 200, 1000)


def test_bin_candidates_empty_input() -> None:
    assert sampling._bin_candidates([], BINS) == {
        20: [],
        50: [],
        200: [],
        1000: [],
    }


def test_bin_candidates_boundary_conditions() -> None:
    """Left-closed intervals: exactly 20 lands in [20,50), exactly 50 lands in [50,200)."""
    out = sampling._bin_candidates(
        [
            _cand(1, 20),
            _cand(2, 49),
            _cand(3, 50),
            _cand(4, 199),
            _cand(5, 200),
            _cand(6, 999),
            _cand(7, 1000),
            _cand(8, 50_000),
        ],
        BINS,
    )
    assert [c.id for c in out[20]] == [1, 2]
    assert [c.id for c in out[50]] == [3, 4]
    assert [c.id for c in out[200]] == [5, 6]
    assert [c.id for c in out[1000]] == [7, 8]


def test_bin_candidates_drops_below_floor() -> None:
    """Candidates under the smallest bin are dropped defensively."""
    out = sampling._bin_candidates(
        [_cand(1, 5), _cand(2, 19), _cand(3, 20)], BINS
    )
    assert [c.id for c in out[20]] == [3]
    assert out[50] == []


def test_bin_candidates_all_in_one_bin() -> None:
    out = sampling._bin_candidates(
        [_cand(i, 30) for i in range(10)], BINS
    )
    assert len(out[20]) == 10
    assert all(len(out[lo]) == 0 for lo in (50, 200, 1000))


# ---------- _bin_range ----------


def test_bin_range_interior() -> None:
    assert sampling._bin_range(BINS, 50) == (50, 200)
    assert sampling._bin_range(BINS, 200) == (200, 1000)


def test_bin_range_floor() -> None:
    assert sampling._bin_range(BINS, 20) == (20, 50)


def test_bin_range_top_is_unbounded() -> None:
    assert sampling._bin_range(BINS, 1000) == (1000, None)


def test_bin_range_unknown_low_raises() -> None:
    with pytest.raises(ValueError):
        sampling._bin_range(BINS, 75)
