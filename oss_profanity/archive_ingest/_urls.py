"""GH Archive URL + file-ID arithmetic.

File IDs are carried around internally as zero-padded ``YYYY-MM-DD-HH``
strings so lexicographic sort matches chronological order in MongoDB.
The URL template at https://data.gharchive.org uses a non-zero-padded
hour (``2020-06-01-0.json.gz``, not ``-00.json.gz``) — the mismatch is
load-bearing and verified by HEAD, not assumed.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from typing import Final

_BASE_URL: Final[str] = "https://data.gharchive.org"
# Accept either zero-padded hour (config convention) or non-padded (URL form).
_FILE_ID_RE: Final[re.Pattern[str]] = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})-(\d{1,2})$"
)


def parse_file_id(file_id: str) -> datetime:
    """Parse a ``YYYY-MM-DD-H[H]`` file ID into a UTC datetime."""
    m = _FILE_ID_RE.match(file_id)
    if m is None:
        raise ValueError(f"invalid file_id: {file_id!r}")
    year, month, day, hour = (int(g) for g in m.groups())
    return datetime(year, month, day, hour, tzinfo=timezone.utc)


def format_file_id(dt: datetime) -> str:
    """Render a datetime as the canonical zero-padded ``YYYY-MM-DD-HH``."""
    return dt.strftime("%Y-%m-%d-%H")


def url_for(file_id: str) -> str:
    """Build the GH Archive download URL for a file ID.

    GH Archive uses a non-zero-padded hour in its URL template; this
    function translates the canonical zero-padded internal form to the
    wire form.
    """
    dt = parse_file_id(file_id)
    return f"{_BASE_URL}/{dt.year:04d}-{dt.month:02d}-{dt.day:02d}-{dt.hour}.json.gz"


def iter_file_ids(start: str, end: str) -> Iterator[str]:
    """Yield every hourly file ID in ``[start, end]`` inclusive.

    Both endpoints are canonical zero-padded ``YYYY-MM-DD-HH`` strings.
    Output order is chronological.
    """
    start_dt = parse_file_id(start)
    end_dt = parse_file_id(end)
    if end_dt < start_dt:
        raise ValueError(f"end {end!r} precedes start {start!r}")
    cursor = start_dt
    step = timedelta(hours=1)
    while cursor <= end_dt:
        yield format_file_id(cursor)
        cursor += step
