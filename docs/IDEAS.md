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

## Emoji-first cohort sampling

**Source:** [IP-006](proposals/posts/ip-006-cohort-sampling.md) Q5 resolution.

IP-006 samples two profanity-based cohorts (top-750 `profanity_rate` vs matched clean). Emoji signal is retained on every deep-analysed repo, but emoji cohorts are sliced *post-hoc* in IP-008 rather than sampled at Stage 3 — because doubling the sampling pass would either double the IP-007 worker-time budget (4 cohorts × 750 = 3,000 vs 1,500) or halve each cohort.

A follow-up study could flip the primary axis: draw the top-750 high-emoji repos and a commit-count-matched zero-emoji cohort, and run the same Mann-Whitney battery. The design is symmetric — the `_select_profane` / `_select_clean_matched` pair becomes `_select_emoji_high` / `_select_emoji_low_matched`, `cohort` gains `"emoji_high"` / `"emoji_low"` labels, and every existing helper (binning, promote, report) is reused unchanged. Implementation cost is roughly one day; the bigger cost is another 2 hours of worker time for the new 1,500-repo cohort.

**Trigger to promote:** IP-008's post-hoc emoji slice shows meaningful correlation between emoji rate and any quality metric (comparable in magnitude to the profanity correlation). At that point a dedicated matched-cohort analysis is worth doing cleanly rather than relying on the post-hoc slice, which is statistically valid but visually harder to present to a non-expert audience.

---

## Language-aware identifier splitting

**Source:** [IP-004](proposals/posts/ip-004-static-analyzers.md) Future Considerations.

Tree-sitter returns raw identifiers. A follow-up could split `CamelCase` / `snake_case` / `kebab-case` into word parts before feeding to profanity scan, catching things like `assHat` where `asshat` is in LDNOOBW but `assHat` is not.

**Trigger to promote:** Stage 5 validation finds a meaningful profane-identifier miss rate from the unsplit text path.

---

# Promoted to high priority — surfaced by IP-008's pre-flight pass (2026-04-25)

## ESLint analyser silent-failure

**Source:** IP-008 pre-flight Mann-Whitney pass over the `done` cohort.

`code_analysis.eslint_issues` is `null` on **0 / 1,295** done repos — i.e., 100 % missingness. The analyser exec succeeds (no `git: ...` failure reasons; the worker's `_processor.py` doesn't crash) but the field never lands on the document. Likely culprits, ranked by suspicion:

1. The flat-config v10 invocation (`/opt/baseline-eslint.config.mjs`) is exiting non-zero on every invocation, and `_eslint.run()` swallows the failure into a `None` rather than logging the stderr.
2. `oss_profanity.analyzers._eslint.run()` returns the count under a different key than `code_analysis._writer` is looking for — silent shape mismatch.
3. ESLint's flat-config rule set rejects every JS/TS file as un-parseable on the cohort's older commit shas (2020-era source against eslint v10).

**Trigger to promote:** the talk lands 2026-04-25; this is the highest-priority post-talk follow-up. The ESLint hole leaves the JS/TS column of the paper empty. Next step: open a one-off `npm run` invocation against one of the JS-primary cohort repos manually and capture stderr to identify the failure mode.

---

## Sensitivity analysis — drop NSFW subgenre, re-run MWU

**Source:** IP-008 pre-flight + Slide 41 (NSFW subgenre footnote).

Top-30 profanity contains a cluster (`guro`, `vibrator`, `genitals`, `porn`, `cum`, `hentai`, `hardcore`) that signals adult-content tooling on GitHub rather than "developers being grumpy." These repos sit at the maximum-profanity end of cohort A and may be driving the lizard complexity signal disproportionately.

A sensitivity analysis would: (a) classify cohort A repos by NSFW topic from `github_metadata.topics` + a hand-curated keyword list against `description`; (b) re-run the six a-priori MWU tests with the NSFW subset excluded; (c) report whether the `lizard_avg_ccn` p-value survives.

**Trigger to promote:** anyone in Q&A asks "are your results NSFW-driven?" — at which point the answer "I don't know yet" becomes the answer "let me check." For the paper revision this is a must-do; for the talk it's a nice-to-have if there's notebook time before the dry run.

---

## LOC-and-language stratified sub-analysis for the paper

**Source:** IP-008 pre-flight; Python subset (n=112 vs 96) and JS/TS subset (lizard only — eslint hole) already produce different effect sizes than the pooled analysis. Per-language `lizard_avg_ccn`:

- Python: median 2.72 → 3.10, p = 0.18 (not significant on its own)
- JS/TS: median 1.67 → 1.83, p = 0.54 (not significant on its own)
- Pooled: p = 2 × 10⁻⁴

The pooled significance is partially driven by between-language variance (Python repos are more complex than JS repos at the median, in both cohorts). A proper paper-grade analysis would: (a) run a mixed-effects model with language as a random intercept, or (b) report per-language MWU + meta-analyse the effect sizes.

**Trigger to promote:** paper revision. For the talk, the pooled lizard signal is the headline; the per-language footnote stays in NOTES.md.

---

## Outlier audit — `lizard_max_ccn = 65,632`

**Source:** IP-008 pre-flight; one clean-cohort repo carries a `lizard_max_ccn` of 65,632 (the next-highest is ~11,000). The other extreme: `loc_total = 3,738,122` in one tsx-primary repo (likely a `node_modules`-leak or generated bundle).

A 30-minute audit pass: pull the worst-N rows for `lizard_max_ccn`, `lizard_ccn_p99`, `loc_total`, and `files_scanned`, eyeball the `full_name`, decide whether they're legitimate or analyser bugs (e.g., did our `_walk.py` skip rule miss a vendored bundle?). If three or more are spurious, add a vendored-bundle skip rule to IP-004.

**Trigger to promote:** paper supplement section 3 — outlier handling.

---

## Effect-size CIs in the paper, not just the deck

**Source:** IP-008 pre-flight; the notebook reports rank-biserial correlation but the bootstrap 95 % CIs are only on the forest plot. For the paper, every reported `r_rb` should carry its CI in the table.

Cheap to add — `scipy.stats.bootstrap` already in the notebook. Trigger: paper revision.

---

## Cross-window comparison (2020-06 vs 2024-06 vs 2026-06)

**Source:** IP-011 Act VI hypothesis; IP-012 placeholder.

Same pipeline, three windows. The lizard complexity finding becomes the *baseline*; the question is whether the gap shrinks, stays, or grows in the post-LLM era. The pipeline is window-agnostic — `GHA_START` / `GHA_END` env flip. Cost: ~10 h compute per window.

**Trigger to promote:** paper revision; or IP-012 if a window-comparison paper becomes a goal of its own.
