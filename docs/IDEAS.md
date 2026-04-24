# Ideas

A parking lot for enhancements that aren't in scope for any current IP but are worth remembering. Entries here are **not commitments** — they are pointers for future IPs or follow-up studies.

Format per entry: short title, the IP (if any) that spawned it, a one-paragraph description, and a "trigger" line describing what would make it worth promoting to a proper proposal.

---

## BIMAN full bot classifier

**Source:** [IP-005](proposals/posts/ip-005-gh-archive-ingest.md) Q5 resolution.

IP-005's bot filter is the author-login side of the problem: regex match + `[bot]` suffix + `actor.type == "Bot"` from the event payload. This catches the dominant cases (Dey et al. report ~90% coverage with login-based rules for the 2020 era). The remaining ~10% are bots whose login is indistinguishable from a human account — they commit under names like `build-agent` or `ci-release`.

[Dey et al., "Detecting and Characterizing Bots that Commit Code" (BIMAN, MSR 2020)](https://cmustrudel.github.io/papers/msr20bots.pdf) publishes a **content-heuristic classifier** that looks at commit-message patterns ("Bump dependencies from X to Y", "Auto-generated release commit", uniform timing, etc.) to flag bots beyond the login layer. Integrating it would:

- Catch bots whose login doesn't match the extended frozenset / `[bot]` suffix
- Introduce commit-content pattern matching into the ingest hot path (roughly 2–5× CPU cost per commit, per the paper's benchmarks)
- Require a decision on how to weigh content-heuristic flags against login flags (hard filter vs soft-score)

**Trigger to promote:** post-ingest validation of the author-login filter shows residual bot noise materially biasing at least one correlation in IP-008's Stage 5 output. Cheap to assess — count author-login distributions of commits flagged as profane/emoji-heavy; if a handful of dominant unflagged "bot-like" logins drive the tails, BIMAN content rules are warranted.

---

## msgspec decode with typed `PushEvent` Struct

**Source:** [IP-005](proposals/posts/ip-005-gh-archive-ingest.md) Future Considerations.

`orjson.loads` + dict access is the current IP-005 choice. `msgspec.json.Decoder(PushEvent)` with a declared Struct peaks ~6–9× lower memory and ~20–30% faster decode, at the cost of a formal PushEvent schema that is strict against GH Archive evolution.

**Trigger to promote:** profiler output from a real ingest shows JSON decode in the top-3 hottest functions, OR the in-memory streaming queue peaks above the 3 GB budget (see IP-005 Q2 resolution). Either signals that the memory-efficient Struct decoder would pay for the schema-declaration churn.

---

## Language-detection caching in ingest

**Source:** [IP-005](proposals/posts/ip-005-gh-archive-ingest.md) Future Considerations.

`profanity.detect_language` is called ~40M times during the June 2020 ingest. Many short messages short-circuit to `"en"` via the `_MIN_DETECT_LEN` guard, but the rest invoke Lingua's detector per call. An LRU cache keyed by the first 200 chars of the message (or the full message for short ones) would amortize detector cost on repeated merge-commit messages.

**Trigger to promote:** profiler output from a real ingest shows `detect_language` is more than ~5% of per-commit CPU time.

---

## Sentiment annotation for emoji

**Source:** [IP-003](proposals/posts/ip-003-emoji-detection.md) Future Considerations.

IP-003 counts emoji occurrences but does not interpret them. A hand-labeled lookup (positive: 🚀 ✨ 🎉; negative: 🐛 💥 😡; neutral: 👀 📝; sarcastic: 💩 🫠) would enable an emoji-sentiment-vs-quality correlation alongside the raw-rate axis.

**Trigger to promote:** Stage 5 results show emoji rate is meaningfully correlated with something, and the talk's Q&A could benefit from a sentiment-sliced view. Out of scope for the current study; would be a standalone follow-up.

---

## Per-language correlation in Stage 5

**Source:** [IP-004](proposals/posts/ip-004-static-analyzers.md) Future Considerations.

IP-008 currently plans to report profanity/emoji rates globally. A per-primary-language breakdown (profanity vs quality **within** each of Python / JavaScript / Go / etc.) would control for cross-language baseline differences in linting strictness, identifier conventions, and comment density.

**Trigger to promote:** global correlations are weak but Stage 5 data shows visible within-language clustering.

---

## Observability — Prometheus metrics for ingest

**Source:** [IP-005](proposals/posts/ip-005-gh-archive-ingest.md) Future Considerations.

`ingest_files_done`, `ingest_bots_filtered`, `ingest_write_batch_ms`, `ingest_queue_depth`. Not in the 2-day experiment budget; would be first thing for a long-lived deploy or for debugging a misbehaving ingest mid-run.

**Trigger to promote:** the pipeline becomes a production pipeline (not just a research one-shot), or debugging a slow/wedged ingest ever requires more than log-level visibility.

---

## Heartbeat-based distributed lease for Stage 4 workers

**Source:** [IP-001](proposals/posts/ip-001-foundations.md) Future Considerations.

Stage 4's `claim + fixed TTL + reclaim_stale` is the simplest form of a distributed lease on a Mongo document. A heartbeat variant (each worker `$set claimed_at` periodically during long operations) would shrink TTL to single-digit minutes and speed recovery from real worker deaths.

**Trigger to promote:** worker deaths happen often enough mid-run that the current 20-minute TTL is the bottleneck on tail latency.

---

## Language-aware identifier splitting

**Source:** [IP-004](proposals/posts/ip-004-static-analyzers.md) Future Considerations.

Tree-sitter returns raw identifiers. A follow-up could split `CamelCase` / `snake_case` / `kebab-case` into word parts before feeding to profanity scan, catching things like `assHat` where `asshat` is in LDNOOBW but `assHat` is not.

**Trigger to promote:** Stage 5 validation finds a meaningful profane-identifier miss rate from the unsplit text path.
