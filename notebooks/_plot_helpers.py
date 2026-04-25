"""IP-008 plot helpers.

Shared by ``ip-008-results.ipynb`` so the notebook stays presentation-focused
and the helper logic stays testable. Mirrors the FIIT visual identity from
``presentation/style.css`` so PNGs drop into the deck without restyling.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

FIIT_BLUE = "#00A9E0"
FIIT_DARK = "#1a1a2e"
FIIT_GRAY = "#676767"
FIIT_LIGHT_GRAY = "#f5f7fa"
FIIT_ACCENT = "#ff6b6b"

CLEAN_COLOR = FIIT_GRAY
PROFANE_COLOR = FIIT_BLUE


def style_fiit() -> None:
    """Apply the FIIT palette + Open Sans + sensible matplotlib defaults."""
    mpl.rcParams.update(
        {
            "font.family": ["Open Sans", "DejaVu Sans", "sans-serif"],
            "font.size": 13,
            "axes.titlesize": 16,
            "axes.titleweight": "semibold",
            "axes.labelsize": 13,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.edgecolor": FIIT_GRAY,
            "axes.labelcolor": FIIT_DARK,
            "xtick.color": FIIT_GRAY,
            "ytick.color": FIIT_GRAY,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "figure.dpi": 120,
            "savefig.dpi": 240,
            "savefig.bbox": "tight",
            "savefig.facecolor": "white",
            "legend.frameon": False,
        }
    )


def rank_biserial(u: float, n1: int, n2: int) -> float:
    """Wendt (1972). Signed so positive ⇒ group 2 stochastically larger.

    With ``mwu_one(..., a=clean, b=profane)`` and U computed on (clean, profane),
    a positive ``r_rb`` means the profane cohort tends to rank higher.
    """
    if n1 == 0 or n2 == 0:
        return float("nan")
    return 1.0 - (2.0 * u) / (n1 * n2)


def mwu_one(
    df: pd.DataFrame, metric: str, alternative: str = "two-sided"
) -> dict[str, Any]:
    """One Mann-Whitney U test on ``metric``, comparing clean (a) vs profane (b)."""
    sub = df[["cohort", metric]].dropna()
    a = np.asarray(
        sub.loc[sub["cohort"] == "clean", metric].astype(float), dtype=np.float64
    )
    b = np.asarray(
        sub.loc[sub["cohort"] == "profane", metric].astype(float), dtype=np.float64
    )
    if len(a) < 5 or len(b) < 5:
        return {
            "metric": metric,
            "n_clean": int(len(a)),
            "n_prof": int(len(b)),
            "median_clean": float("nan"),
            "median_prof": float("nan"),
            "U": float("nan"),
            "p": float("nan"),
            "r_rb": float("nan"),
        }
    result = stats.mannwhitneyu(a, b, alternative=alternative)  # type: ignore[call-overload]
    u = float(result.statistic)
    p = float(result.pvalue)
    return {
        "metric": metric,
        "n_clean": int(len(a)),
        "n_prof": int(len(b)),
        "median_clean": float(np.median(a)),
        "median_prof": float(np.median(b)),
        "U": u,
        "p": p,
        "r_rb": rank_biserial(u, len(a), len(b)),
    }


def bootstrap_ci_rb(
    a: np.ndarray,
    b: np.ndarray,
    n_resamples: int = 1000,
    confidence: float = 0.95,
    random_state: int = 42,
) -> tuple[float, float]:
    """Bootstrap CI for rank-biserial. ``a`` = clean, ``b`` = profane."""
    rng = np.random.default_rng(random_state)
    n1, n2 = len(a), len(b)
    if n1 < 5 or n2 < 5:
        return (float("nan"), float("nan"))
    rs: list[float] = []
    for _ in range(n_resamples):
        a_s = rng.choice(a, size=n1, replace=True)
        b_s = rng.choice(b, size=n2, replace=True)
        u, _ = stats.mannwhitneyu(a_s, b_s, alternative="two-sided")
        rs.append(rank_biserial(float(u), n1, n2))
    lo = float(np.quantile(rs, (1.0 - confidence) / 2.0))
    hi = float(np.quantile(rs, 1.0 - (1.0 - confidence) / 2.0))
    return (lo, hi)


def mwu_table(
    df: pd.DataFrame, metrics: list[str], alpha_corrected: float
) -> pd.DataFrame:
    """Build a results DataFrame across metrics with corrected significance flag."""
    rows = [mwu_one(df, m) for m in metrics]
    out = pd.DataFrame(rows)
    out["significant"] = out["p"] < alpha_corrected
    return out


def save_plot(fig: "mpl.figure.Figure", name: str, plot_dir: Path) -> Path:
    """Save ``fig`` as ``{plot_dir}/{name}.png``; return the path."""
    plot_dir.mkdir(parents=True, exist_ok=True)
    out = plot_dir / f"{name}.png"
    fig.savefig(out)
    plt.close(fig)
    return out
