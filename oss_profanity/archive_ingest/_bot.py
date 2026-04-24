"""Bot detection: extended frozenset + ``[bot]`` suffix + payload actor type.

Three independent predicates, any match drops the commit:

1. ``event["actor"]["type"] == "Bot"`` — authoritative when present
2. Author login ends in ``[bot]`` — GitHub Apps convention
3. Login is in the :data:`_EXTENDED_BOTS` frozenset — BIMAN-era named bots
4. Login matches :data:`config.bot_regex` — the env-driven override

The BIMAN content-heuristic classifier (Dey et al., MSR 2020) catches
bots whose login looks human; it is deferred to ``docs/IDEAS.md``.
"""

from __future__ import annotations

from typing import Final

from ..config import config

# BIMAN-era named bots active in June 2020. Stored lowercased; the caller
# lowercases the login before the membership check.
_EXTENDED_BOTS: Final[frozenset[str]] = frozenset(
    {
        "dependabot",
        "dependabot-preview",
        "renovate",
        "renovate-bot",
        "github-actions",
        "greenkeeper",
        "pyup-bot",
        "whitesource-bolt",
        "whitesource-bolt-for-github",
        "scala-steward",
        "snyk-bot",
        "depfu",
        "imgbot",
        "allcontributors",
        "stale",
        "codecov",
        "codecov-io",
        "mergify",
        "semantic-release-bot",
        "fossabot",
        "houndci-bot",
    }
)


def is_bot(actor_login: str | None, actor_type: str | None = None) -> bool:
    """Return True if the actor should be filtered out of the corpus."""
    if actor_type == "Bot":
        return True
    if not actor_login:
        return False
    lowered = actor_login.lower()
    if lowered.endswith("[bot]"):
        return True
    if lowered in _EXTENDED_BOTS:
        return True
    return bool(config.bot_regex.search(actor_login))
