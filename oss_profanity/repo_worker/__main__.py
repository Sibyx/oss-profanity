"""Entrypoint: ``python -m oss_profanity.repo_worker``."""

from __future__ import annotations

import logging
import os
import sys

from ._launcher import launch


def main() -> int:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    return launch()


if __name__ == "__main__":
    sys.exit(main())
