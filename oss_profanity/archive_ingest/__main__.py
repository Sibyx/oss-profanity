"""CLI entry — ``python -m oss_profanity.archive_ingest``."""

from __future__ import annotations

import asyncio
import logging

from ._runner import run


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    asyncio.run(run())


if __name__ == "__main__":
    main()
