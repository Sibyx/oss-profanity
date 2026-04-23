"""Fetch LDNOOBW word lists at a pinned commit SHA.

Vendors the `List of Dirty, Naughty, Obscene, and Otherwise Bad Words` repo
into ``oss_profanity/wordlists/ldnoobw/`` for reproducible profanity scanning.

Usage::

    python -m scripts.fetch_ldnoobw

To refresh to a newer upstream revision: bump ``LDNOOBW_SHA`` below, rerun,
and commit the resulting files. The script is idempotent — safe to rerun.
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

LDNOOBW_REPO = "LDNOOBW/List-of-Dirty-Naughty-Obscene-and-Otherwise-Bad-Words"
LDNOOBW_SHA = "5faf2ba42d7b1c0977169ec3611df25a3c08eb13"

TARGET = Path(__file__).resolve().parent.parent / "oss_profanity" / "wordlists" / "ldnoobw"
SKIP_FILES = {"LICENSE", "README.md", "USERS.md"}


def _api(path: str) -> list[dict]:
    url = f"https://api.github.com/repos/{LDNOOBW_REPO}/contents/{path}?ref={LDNOOBW_SHA}"
    with urllib.request.urlopen(url) as response:
        return json.loads(response.read())


def _fetch_file(url: str) -> bytes:
    with urllib.request.urlopen(url) as response:
        return response.read()


def main() -> None:
    TARGET.mkdir(parents=True, exist_ok=True)

    entries = _api("")
    wordlist_count = 0
    for entry in entries:
        if entry["type"] != "file" or entry["name"] in SKIP_FILES:
            continue
        dest = TARGET / entry["name"]
        content = _fetch_file(entry["download_url"])
        dest.write_bytes(content)
        wordlist_count += 1
        print(f"  wrote {entry['name']} ({len(content):>6} bytes)")

    license_path = TARGET / "LICENSE.md"
    license_path.write_text(
        f"""# Attribution

Word lists in this directory are vendored from the public
[LDNOOBW repository]({f"https://github.com/{LDNOOBW_REPO}"}) at commit
`{LDNOOBW_SHA}`.

Licensed under Creative Commons Attribution 4.0 International (CC-BY-4.0).
See <https://creativecommons.org/licenses/by/4.0/> for the full license text.

To refresh: bump ``LDNOOBW_SHA`` in ``scripts/fetch_ldnoobw.py`` and rerun.
"""
    )
    print(f"  wrote LICENSE.md")
    print(f"\n{wordlist_count} word lists vendored at pinned SHA {LDNOOBW_SHA[:12]}")


if __name__ == "__main__":
    main()
