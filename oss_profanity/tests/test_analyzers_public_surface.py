"""Pin the public surface of the analyzers subpackage.

Exactly two names are importable from ``oss_profanity.analyzers``:
``detect_primary_language`` and ``run_all``. Anything else leaking out
is a contract break — callers outside the package must go through these
two entrypoints.
"""

from __future__ import annotations

import oss_profanity.analyzers as analyzers


def test_public_surface_is_exactly_two_names() -> None:
    assert set(analyzers.__all__) == {"detect_primary_language", "run_all"}


def test_public_callables_are_present() -> None:
    assert callable(analyzers.detect_primary_language)
    assert callable(analyzers.run_all)
