# Cohort sampling — the plain-language version

This doc explains what [IP-006](proposals/posts/ip-006-cohort-sampling.md) actually does, in the smallest words that still get the point across. It is the talk-preparation source for the "how do you pick which repos to study?" slide.

If you already know what a Mann-Whitney U test is and what *stratified matched sampling* means, you don't need this doc — read IP-006 directly. This doc is for everyone else.

## The question we are trying to answer

**Do developers who swear in commit messages write worse code?**

"Worse code" has to be measurable. We use four knobs: linter issues per 1,000 lines of code (ruff/eslint), average cyclomatic complexity (lizard), and code-clone rate (jscpd). "Swearing" is measured by scanning commit-message text for profanity with a real language detector + a curated bad-word list.

If we find a relationship — good or bad, profanity correlates with better code, worse code, or no code difference at all — the talk gets a story. If we find nothing, the talk still gets a story: "we looked, it's not there."

## Why can't we just look at every repo?

Two reasons.

1. **Too much data.** GH Archive for June 2020 has 3.7 million distinct repos in it. Cloning and deep-analysing 3.7M repos would take weeks of worker time on the budget we have. We have 2 days.
2. **The signal is rare.** Only about 16,000 of the 3.7M repos (~0.4 %) have *any* profanity in their June 2020 commit messages. The other 99.6 % are silent on this axis. Studying "all of them" wastes cycles on repos that cannot help answer the question.

So we pick a small, well-chosen subset — a *cohort*.

## Why two cohorts?

Because "profane repos have X linter issues per KLOC" alone tells you nothing. The number needs a baseline: "*compared to what?*"

- **Cohort A (profane):** 750 repos that swear the most in commits.
- **Cohort B (clean):** 750 repos that never swear in commits.

We run the same analysis on both piles and compare. Statistically we use the Mann-Whitney U test, which is a non-parametric way of asking *"are the two piles drawn from the same underlying distribution, or not?"*

## Why exactly 750?

It's borrowed from DRAFT.md (the original experiment spec). The number is a compromise:

- **Big enough** that the statistical test has power — with 750 per pile, a Mann-Whitney U at α=0.05 can detect even a tiny effect size (r ≈ 0.10) with 80 % power. We are not going to miss a real signal if one exists.
- **Small enough** that 1,500 deep-analyses fit in our time budget. At roughly 3 minutes per repo on the worker pool (clone + ruff/eslint/lizard/jscpd + GitHub API enrichment), 1,500 repos × 3 min / 36 workers ≈ 2 hours. Plenty of buffer.

Both cohorts are the same size (750 = 750) because unequal sizes don't buy extra power here — Mann-Whitney is balanced.

## The subtle problem: size bias

Here is the subtle part. Let's play a quick game.

Suppose we pick cohort A = the 750 most-profane repos. What do those look like? In practice, they are a mix of sizes, but the *really* profane ones tend to have a reasonable number of commits (you can't have much swearing with just 3 commits).

Now what if for cohort B we just take a random 750 clean repos? Because small repos vastly outnumber big repos (319,681 of our clean candidates have 20–49 commits, vs only 1,676 with 1,000–9,999 commits), a random draw gives us mostly *small* clean repos.

So now we compare:

- **Profane pile:** mostly medium-sized repos
- **Clean pile:** mostly tiny repos

Any difference we measure in code quality is now contaminated. A bigger repo has more code surface → more linter issues → higher complexity on average. The "profane vs clean" difference we'd report is actually a "medium vs tiny" difference. **Size is a confounder.**

## How bin-matching fixes it

We look at the shape of cohort A, then draw cohort B with the same shape.

Here is cohort A's actual shape on June 2020 data, split by commit count:

| Commit-count bin | Cohort A has |
|---|---:|
| 20–49 | 568 repos |
| 50–199 | 158 repos |
| 200–999 | 22 repos |
| 1,000–9,999 | 2 repos |
| **Total** | **750** |

Bin-matching means we go into the clean pool *separately* for each bin and draw the same count:

| Commit-count bin | We draw from cohort B | Available in pool |
|---|---:|---:|
| 20–49 | 568 | 319,681 |
| 50–199 | 158 | 129,778 |
| 200–999 | 22 | 20,581 |
| 1,000–9,999 | 2 | 1,676 |
| **Total** | **750** | 471,767 |

Now both piles have the same commit-count distribution. If cohort A has 568 medium-sized repos, cohort B has 568 medium-sized repos too. If A has 22 big repos, B has 22 big repos. The *size* variable is held constant across the comparison. Any remaining difference in code quality is attributable to the *only* thing the two piles differ on: profanity.

The pool column shows we have massive headroom — 500× to 900× more clean candidates than we need in every bin. There is no risk of running out.

## What `$sample` does (the Mongo bit)

"Randomly draw 568 repos from a pool of 319,681" is a standard database operation. MongoDB has a pipeline stage called `$sample` that does exactly that, server-side, efficiently, without pulling all 319,681 candidates across the network.

For each bin we run one small query:

```
"give me 568 random clean repos where commit count is between 20 and 49"
```

Mongo does the random draw internally (it uses a pseudo-random without-replacement algorithm) and hands back exactly 568 documents. Four queries total, one per bin. Milliseconds each.

## What the tool actually outputs

At the end of the sampling run, IP-006 prints a histogram to the log. Something like:

```
sampling: default-skipped  = 3,702,633
sampling: profane_selected = 750
sampling: clean_selected   = 750
sampling: bin 20-49       profane=568 clean=568  shortfall=0
sampling: bin 50-199      profane=158 clean=158  shortfall=0
sampling: bin 200-999     profane=22  clean=22   shortfall=0
sampling: bin 1000-9999   profane=2   clean=2    shortfall=0
sampling: total_promoted   = 1500
```

Zero shortfalls in every bin = perfect match. If the clean pool ever ran out for a bin (hypothetically, on a future smaller window), you'd see `shortfall=5` and a warning, and you'd know to either trim the profane side or widen the window.

## What happens next

Every repo in both cohorts gets marked `status="pending"` in MongoDB, plus a `cohort: "profane"` or `cohort: "clean"` label so the downstream steps (IP-007 deep-analysis, IP-008 aggregation) know which pile each result came from.

The 36-worker deep-analysis pool ([IP-007](proposals/posts/ip-007-repo-worker.md)) then picks them off one at a time: clone, run ruff/eslint/lizard/jscpd, fetch GitHub metadata, write results back. ~2 hours later we have the per-repo numbers. [IP-008](proposals/posts/ip-008-aggregation-and-plots.md) then runs the Mann-Whitney U test and makes the plots.

## The simple version for the slide

> We took the 750 most-profane repos and matched each one against a same-sized clean repo in the same commit-count bucket. Now any measured difference in code quality is about profanity, not about repo size.

That is the whole sampling story in one sentence.

## See also

- [IP-006](proposals/posts/ip-006-cohort-sampling.md) — formal proposal, all edge cases, every query and constant
- [IP-005](proposals/posts/ip-005-gh-archive-ingest.md) — how the 3.7M repo pool got populated in the first place
- [IP-008](proposals/posts/ip-008-aggregation-and-plots.md) — the statistical test that consumes these cohorts *(forthcoming)*
- [DRAFT §5.2](DRAFT.md) — the original experiment spec that fixed 750-per-cohort and the `commits ≥ 20` floor
- [Stuart (2010), "Matching methods for causal inference: A review"](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC2943670/) — the academic framing of why matched cohorts work
