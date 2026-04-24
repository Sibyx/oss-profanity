"""Technical-debt marker counter for comment text.

Recognizes the four markers developers conventionally use to flag
work-to-do in comments: TODO, FIXME, HACK, XXX. Case-sensitive by design
— "todo" in prose (e.g. "this is a todo list") is not a marker.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Final

_MARKER_RE: Final[re.Pattern[str]] = re.compile(r"\b(TODO|FIXME|HACK|XXX)\b")


def count(comments: Iterable[str]) -> int:
    """Return the total marker occurrences across ``comments``."""
    total = 0
    for text in comments:
        total += len(_MARKER_RE.findall(text))
    return total
