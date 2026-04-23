"""Shared pytest fixtures for the oss-profanity test suite.

``oss_profanity.config`` validates ``MONGO_URI`` at import time, so we seed a
harmless placeholder here to let schema-only and config-only tests import the
package without a live MongoDB. Tests that actually need MongoDB use the
``mongo_uri`` fixture, which skips unless ``TEST_MONGO_URI`` is set.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from pymongo import MongoClient

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017/profanity_test")


@pytest.fixture(scope="session")
def mongo_uri() -> str:
    uri = os.getenv("TEST_MONGO_URI")
    if not uri:
        pytest.skip(
            "TEST_MONGO_URI not set; skipping live-DB tests (start Mongo with "
            "`docker run --rm -p 27017:27017 mongo:7` and export "
            "TEST_MONGO_URI=mongodb://localhost:27017/profanity_test)"
        )
    return uri


@pytest.fixture
def clean_db(
    mongo_uri: str, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    """Drop the ``repos`` collection before and after each test, and point
    ``oss_profanity.config`` at the test Mongo for this test's scope."""
    monkeypatch.setenv("MONGO_URI", mongo_uri)
    client: MongoClient[dict] = MongoClient(mongo_uri)
    db = client.get_default_database()
    db.repos.drop()
    yield
    db.repos.drop()
    client.close()
