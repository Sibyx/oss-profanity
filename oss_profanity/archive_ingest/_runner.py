"""Async orchestrator: download → queue → parse → upsert → mark done.

Single process tree:

* ``asyncio`` main loop with an ``httpx.AsyncClient(http2=True)`` for
  I/O-bound downloads, capped at :data:`_DOWNLOAD_CONCURRENCY` via a
  semaphore.
* ``ProcessPoolExecutor(max_workers=4)`` for CPU-bound parse + upsert.
  Sized for the Mongo-colocated ingest host (leaves ~2 cores for
  MongoDB + 1 for this loop + 1 margin on an 8-vCPU box).
* Bounded ``asyncio.Queue(maxsize=8)`` between the two sides provides
  natural backpressure: when parsers fall behind, the queue fills, the
  semaphore holds, and memory pressure stays bounded.

Each parse worker opens its own PyMongo client **inside** the process
(PyMongo is not fork-safe across an already-initialized client), via the
executor's ``initializer``. The main loop also holds a client for the
progress bookkeeping.
"""

from __future__ import annotations

import asyncio
import logging
import signal
from concurrent.futures import ProcessPoolExecutor
from functools import partial
from typing import Any, Final

import httpx
from pymongo import MongoClient

from ..config import config
from ..db import make_worker_id
from . import _finalizer, _http, _parser, _progress, _upserter
from ._urls import iter_file_ids

logger = logging.getLogger(__name__)

_DOWNLOAD_CONCURRENCY: Final[int] = 4
_PARSE_POOL_SIZE: Final[int] = 4
_QUEUE_MAXSIZE: Final[int] = 8
_HTTP_TIMEOUT = httpx.Timeout(300.0, connect=30.0)

# Per-process state inside ProcessPoolExecutor workers. PyMongo clients
# must be opened after fork; holding the client in a module-level global
# lets it be reused across tasks within the same worker.
_worker_mongo: MongoClient[dict[str, Any]] | None = None


def _worker_init(mongo_uri: str) -> None:
    """ProcessPoolExecutor initializer — one Mongo client per worker."""
    global _worker_mongo
    _worker_mongo = MongoClient(mongo_uri)


def _worker_parse_and_upsert(
    gz_bytes: bytes, sample_cap: int
) -> dict[str, Any]:
    """Worker-side: parse + bulk-write + return picklable stats dict."""
    assert _worker_mongo is not None, "worker initializer did not run"
    parsed = _parser.parse_bytes(gz_bytes, sample_cap=sample_cap)
    db = _worker_mongo.get_default_database()
    write_stats = _upserter.flush(db.repos, parsed.bulk_ops)
    return {
        "rows": parsed.rows,
        "push_events": parsed.push_events,
        "bots_filtered": parsed.bots_filtered,
        "commits_observed": parsed.commits_observed,
        "bytes": len(gz_bytes),
        "upserted": write_stats.upserted,
        "modified": write_stats.modified,
    }


async def run() -> None:
    """Main entrypoint: ingest the full window per ``config``."""
    file_ids = list(iter_file_ids(config.gha_start, config.gha_end))
    logger.info(
        "ingest window: %s..%s (%d files)",
        config.gha_start,
        config.gha_end,
        len(file_ids),
    )
    await _run_over_file_ids(file_ids, do_finalize=True)


async def run_one_file(file_id: str) -> dict[str, Any] | None:
    """Single-file entrypoint for tests and ad-hoc reruns.

    Does not run the finalizer. Returns the per-file stats dict the
    worker produced, or ``None`` if the file failed.
    """
    stats_holder: dict[str, Any] = {}

    async def _capture() -> None:
        await _run_over_file_ids([file_id], do_finalize=False, sink=stats_holder)

    await _capture()
    return stats_holder.get(file_id)


async def _run_over_file_ids(
    file_ids: list[str],
    *,
    do_finalize: bool,
    sink: dict[str, Any] | None = None,
) -> None:
    worker_id = make_worker_id()
    mongo_client: MongoClient[dict[str, Any]] = MongoClient(config.mongo_uri)
    try:
        db = mongo_client.get_default_database()
        _progress.ensure_index(db)
        seeded = _progress.seed_pending(db, file_ids)
        reclaimed = _progress.reclaim_stale(db)
        logger.info(
            "ingest startup: seeded %d new pending, reclaimed %d stale",
            seeded,
            reclaimed,
        )

        queue: asyncio.Queue[tuple[str, bytes] | None] = asyncio.Queue(
            maxsize=_QUEUE_MAXSIZE
        )
        stop_event = asyncio.Event()
        loop = asyncio.get_running_loop()

        _install_signal_handlers(loop, stop_event)

        async with httpx.AsyncClient(
            http2=True, timeout=_HTTP_TIMEOUT, follow_redirects=True
        ) as http_client:
            with ProcessPoolExecutor(
                max_workers=_PARSE_POOL_SIZE,
                initializer=_worker_init,
                initargs=(config.mongo_uri,),
            ) as pool:
                download_task = asyncio.create_task(
                    _download_loop(
                        db=db,
                        worker_id=worker_id,
                        http_client=http_client,
                        queue=queue,
                        stop_event=stop_event,
                        expected_count=len(file_ids),
                    )
                )
                consume_task = asyncio.create_task(
                    _consume_loop(
                        db=db,
                        pool=pool,
                        loop=loop,
                        queue=queue,
                        sink=sink,
                    )
                )
                try:
                    await asyncio.gather(download_task, consume_task)
                except asyncio.CancelledError:
                    logger.warning("ingest cancelled; draining")
                    raise

        _remove_signal_handlers(loop)

        if do_finalize and not stop_event.is_set():
            fstats = _finalizer.finalize(db, emoji_top_n=config.emoji_top_n)
            logger.info(
                "finalize: %d repos processed, %d updated",
                fstats.repos_processed,
                fstats.repos_updated,
            )
    finally:
        mongo_client.close()


async def _download_loop(
    *,
    db: Any,
    worker_id: str,
    http_client: httpx.AsyncClient,
    queue: asyncio.Queue[tuple[str, bytes] | None],
    stop_event: asyncio.Event,
    expected_count: int,
) -> None:
    """Claim → download → enqueue, gated by a concurrency semaphore."""
    sem = asyncio.Semaphore(_DOWNLOAD_CONCURRENCY)
    in_flight: set[asyncio.Task[None]] = set()

    async def _one(file_id: str) -> None:
        async with sem:
            if stop_event.is_set():
                _progress.reclaim_stale(db, ttl_minutes=0)
                return
            try:
                gz_bytes = await _http.stream_file(http_client, file_id)
            except Exception as exc:  # noqa: BLE001
                logger.exception("download failed: %s", file_id)
                _progress.mark_failed(db, file_id, f"download: {exc!r}")
                return
            await queue.put((file_id, gz_bytes))

    try:
        claimed_count = 0
        while not stop_event.is_set() and claimed_count < expected_count:
            file_id = _progress.claim_next_file(db, worker_id)
            if file_id is None:
                break
            claimed_count += 1
            task = asyncio.create_task(_one(file_id))
            in_flight.add(task)
            task.add_done_callback(in_flight.discard)
        if in_flight:
            await asyncio.gather(*in_flight)
    finally:
        await queue.put(None)


async def _consume_loop(
    *,
    db: Any,
    pool: ProcessPoolExecutor,
    loop: asyncio.AbstractEventLoop,
    queue: asyncio.Queue[tuple[str, bytes] | None],
    sink: dict[str, Any] | None,
) -> None:
    """Dequeue downloaded payloads; fan out to the parse pool."""
    pending: set[asyncio.Task[None]] = set()
    while True:
        item = await queue.get()
        if item is None:
            break
        file_id, gz_bytes = item
        task = asyncio.create_task(
            _handle_parse(
                db=db,
                pool=pool,
                loop=loop,
                file_id=file_id,
                gz_bytes=gz_bytes,
                sink=sink,
            )
        )
        pending.add(task)
        task.add_done_callback(pending.discard)
    if pending:
        await asyncio.gather(*pending)


async def _handle_parse(
    *,
    db: Any,
    pool: ProcessPoolExecutor,
    loop: asyncio.AbstractEventLoop,
    file_id: str,
    gz_bytes: bytes,
    sink: dict[str, Any] | None,
) -> None:
    """Submit to the pool, record outcome; one task's crash stays isolated."""
    try:
        stats = await loop.run_in_executor(
            pool,
            partial(
                _worker_parse_and_upsert, gz_bytes, config.sample_profane_n
            ),
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("parse/upsert failed: %s", file_id)
        _progress.mark_failed(db, file_id, f"parse: {exc!r}")
        return
    _progress.mark_done(db, file_id, stats)
    logger.info(
        "done: %s (rows=%d push=%d commits=%d bots=%d upsert=%d)",
        file_id,
        stats["rows"],
        stats["push_events"],
        stats["commits_observed"],
        stats["bots_filtered"],
        stats["upserted"],
    )
    if sink is not None:
        sink[file_id] = stats


def _install_signal_handlers(
    loop: asyncio.AbstractEventLoop, stop_event: asyncio.Event
) -> None:
    def _request_stop() -> None:
        if not stop_event.is_set():
            logger.warning("stop requested; draining in-flight work")
            stop_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _request_stop)
        except (NotImplementedError, ValueError):
            # Not on a main thread / not supported (e.g., pytest loop).
            pass


def _remove_signal_handlers(loop: asyncio.AbstractEventLoop) -> None:
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.remove_signal_handler(sig)
        except (NotImplementedError, ValueError):
            pass
