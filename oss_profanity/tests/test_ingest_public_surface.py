"""Pin the public surface of the archive_ingest subpackage."""

from __future__ import annotations

import oss_profanity.archive_ingest as ingest


def test_public_surface_is_exactly_two_names() -> None:
    assert set(ingest.__all__) == {"run", "run_one_file"}


def test_public_callables_are_present() -> None:
    assert callable(ingest.run)
    assert callable(ingest.run_one_file)
