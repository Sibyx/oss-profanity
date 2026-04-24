"""Source-tree iteration with the skip rules centralized here.

Single source of truth for "which files count as source." Every downstream
consumer (language histogram, token extraction, source scan) iterates the
same set; divergence between them would silently break the one-walk DRY
contract the study relies on.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Final

_SKIP_DIRS: Final[frozenset[str]] = frozenset(
    {
        "node_modules",
        "vendor",
        ".git",
        ".hg",
        ".svn",
        "dist",
        "build",
        ".venv",
        "venv",
        "__pycache__",
        ".tox",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "target",
    }
)
_SKIP_NAME_SUBSTRINGS: Final[tuple[str, ...]] = (".min.", ".bundle.")
_MAX_FILE_BYTES: Final[int] = 1_048_576


def iter_source_files(repo_dir: Path) -> Iterator[Path]:
    """Yield every candidate source file under ``repo_dir``.

    Skips directories in :data:`_SKIP_DIRS`, filenames containing any of
    :data:`_SKIP_NAME_SUBSTRINGS`, files larger than :data:`_MAX_FILE_BYTES`,
    and anything that raises on ``os.stat`` (symlink loops, permission
    errors). Non-regular files (sockets, pipes) are skipped too.
    """
    for root, dirnames, filenames in os.walk(repo_dir, followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for name in filenames:
            if any(s in name for s in _SKIP_NAME_SUBSTRINGS):
                continue
            path = Path(root) / name
            try:
                st = path.stat()
            except OSError:
                continue
            if not _is_regular_file(st.st_mode):
                continue
            if st.st_size > _MAX_FILE_BYTES:
                continue
            yield path


def _is_regular_file(mode: int) -> bool:
    import stat

    return stat.S_ISREG(mode)
