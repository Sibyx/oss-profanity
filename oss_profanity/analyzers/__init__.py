"""Static-analyzer subpackage (IP-004).

Public surface: two names.

* :func:`detect_primary_language` — file-extension histogram → dominant
  ``identify`` tag or ``None``.
* :func:`run_all` — run every applicable analyzer in parallel and
  return the ``code_analysis`` sub-document.

Every other symbol is internal (``_``-prefixed module) and must not be
imported from outside this package.
"""

from __future__ import annotations

from ._language import detect_primary_language
from ._runner import run_all

__all__ = ["detect_primary_language", "run_all"]
