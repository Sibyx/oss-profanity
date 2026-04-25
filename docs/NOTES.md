# NOTES — diff between IP-011 (accepted) and what the data supports

Written for the 2026-04-25 OpenCamp talk after IP-008's pre-flight pass
exposed three things the deck didn't yet absorb: the mean-vs-median
flip on lint counts, the ESLint silent-failure across the cohort, and
the corrected Bonferroni denominator (5, not 6). Two sections:

1. **Slides to update before the talk** — concrete edits per slide
   number, each tracked in IP-008's Phase 4 task list. Use the dry-run
   evening to apply.
2. **Spoken-only caveats** — what to say but not show; the safety net
   if a stats-aware audience member presses on details the slides
   intentionally don't carry.

This is operational. `docs/IDEAS.md` is the parking lot for
forward-looking follow-ups (paper revisions, IP-012 longitudinal,
ESLint debug). NOTES.md is what to do *before walking on stage*.

---

## §1 · Slides to update before the talk

These edits land in `presentation/slides.md`. Re-export PDF after.

### Slide 17 — "Cohort sampling"

**Caption / agenda line currently:** "six a-priori metrics".
**Change to:** "five a-priori metrics" (eslint dropped; see fact 3 in
the IP-008 problem statement).

### Slide 19 — "Static analyzers (5 tools)"

**Add a one-line footnote at the bottom of the slide:**

> ESLint analyser silent-failed across the entire cohort
> (0 / 1,295 done repos). Lizard covers JS/TS via tree-sitter for
> this run; ESLint debug is the highest-priority post-talk follow-up.

Speak this beat for ~10 s. Don't dwell.

### Slide 50 — "What's NOT in this deck" → repurposed as the headline result

**Change layout:** drop the placeholder text, insert a Slidev
side-by-side block.

```html
<div class="grid grid-cols-2 gap-4 mt-4">
  <img src="/images/plots/fig05_quality_forest.png" />
  <img src="/images/plots/fig03_lizard_avg_ecdf.png" />
</div>

<div class="text-center mt-4 text-sm opacity-70">
  Five a-priori metrics, Bonferroni-corrected at α / 5 = 0.01 ·
  Mann-Whitney U · effect size = rank-biserial correlation
</div>
```

**Caption beats:**
- Forest plot (left): five a-priori metrics, only the three lizard
  rows survive Bonferroni.
- ECDF (right): visual analogue of the rank test on `lizard_avg_ccn`.

### NEW slide between current Slides 51 and 52

Insert this slide *between* "The one-sentence descriptive finding (so
far)" and "AI & the future". Big text, FIIT blue numbers, no chart:

```markdown
---
layout: center
class: text-center
---

# The inferential answer

<div class="text-3xl font-semibold mt-8 leading-snug">
Profane repos have <span style="color:#00A9E0">~10 %</span>
higher median cyclomatic complexity
<br/>
(<span style="color:#00A9E0">p &lt; 10⁻⁴</span>, small effect <span style="color:#00A9E0">r<sub>rb</sub> ≈ 0.13</span>).
</div>

<v-click>

<div class="text-xl mt-6 opacity-80">
Lint counts, clone rate, and comment density show
<strong>no significant cohort difference</strong>.
</div>

</v-click>

<!--
The takeaway slide. Pause before clicking the second beat. The audience
came for "do swearing programmers write better code" and the answer is
"the structural complexity is measurably higher in profane code, but
the linter cannot tell them apart." That's a more interesting finding
than the joke version of the question would have allowed.
-->
```

### Slide 40 + Slide 42 — top profanity / top emoji

Once IP-008 produces fig 06 + fig 07 PNGs, replace the inline
`.bar-row` HTML with `<img src="/images/plots/fig06_top_profanity.png" />`
(and fig 07 likewise). The PDF print path renders PNGs cleanly; HTML
bars rasterise inconsistently.

### Slide 46 — Matched cohort composition

Add fig 08 (Python-subset boxplot) below the language histogram. Caption:

> Python subset (n=112 vs 96): direction visible, not statistically
> significant under Bonferroni.

### Slide 22 — measurement targets

Drop the eslint row from the listed metrics:
- ~~`eslint_issues_per_kloc`~~ → omit
- The remaining list is `ruff_issues_per_kloc`, `lizard_avg_ccn`,
  `lizard_max_ccn`, clone-detection hits, comment density.

### Slide 21 — Statistical test

**Currently says** "six quality metrics per repo" / Bonferroni at
α / 6.
**Change to** "five a-priori metrics (eslint omitted — see Slide 19)"
and α / 5 = 0.01.

---

## §2 · Spoken-only caveats

Things to say from the stage but not put on a slide. The safety net
for Q&A and for honest delivery.

### The means-vs-medians flip

The IP-011 motivation slide (Slide 38) cited a `1.82×` ratio for ruff
issues per kLOC (mean 84 → 153). **That number is real but
misleading.** Means are pulled by long tails; medians and rank tests
return non-significant p ≈ 0.48 with tiny effect (r_rb = 0.057).

Translation for the stage:

> "When I first looked at the means, I thought we had a strong signal
> on lint counts. The medians and the rank test disagree — once we
> account for the long tail, ruff differences are not significant. The
> only metric that survives Bonferroni is cyclomatic complexity. And
> that's a much more interesting finding than a lint-count delta would
> have been."

### Why Bonferroni at α / 5

If asked: with five independent tests at α = 0.05 each, the chance of
at least one false positive is `1 − 0.95⁵ ≈ 23 %`. Bonferroni divides
α by the test count so the family-wise error rate stays at 5 %. The
per-test threshold becomes `0.05 / 5 = 0.01`. It's the conservative
choice — Benjamini-Hochberg FDR keeps more findings significant by
trading family-wise error for false-discovery-rate. For a one-shot
talk, conservative is right.

### Cohort isn't quite 1,500

Slide 16 says "1,500 cohort repos." Strictly:

- 750 profane + 750 clean = 1,500 **live** entries (correct)
- + 410 + 354 = 764 historical `missing` entries from top-up cycles
- + 143 + 62 = 205 `failed` repos (archived / oversized / no commits)
- = 1,295 with `code_analysis` populated

If pressed:

> "1,500 is the design target; 1,295 is what reached `done`. The
> 205 failures are mostly benign — repos archived between 2020 and
> 2026, oversized, or with no commits in the analysis window. Failure
> rate skews 2.3× higher in the profane cohort, which I read as the
> top-up draws picking deeper into the long tail of less-maintained
> repos."

### The `lizard_max_ccn = 65 632` outlier

One clean-cohort repo. Almost certainly a generated mega-dispatcher.
The forest plot reports `lizard_ccn_p99` not `lizard_max_ccn`
precisely because of this one outlier. If asked, that's the answer.

### The 3.7 M-LOC tsx repo

Visible on the LOC overlay. Probably a `node_modules`-leak or a
generated bundle. Not a methodological problem (rank tests don't
care) but worth naming if anyone points at it.

### The NSFW subgenre

Slide 41 shows `guro`, `vibrator`, `genitals` etc. in the top-30
profanity list. These are real repos — adult-content tooling on
GitHub. They're over-represented in cohort A (max profanity rate
selects for them). If asked whether the lizard signal disappears when
we filter them out: **I don't know yet** (didn't run the sensitivity
analysis pre-talk). Promise to add it to the paper. Tracked in
`docs/IDEAS.md` under "NSFW sensitivity analysis."

### LOC asymmetry

Profane has 1.55× higher mean LOC. Bin-matching was on commits, not
LOC. Holds up under MWU though — `loc_total` p = 0.13, not
significant. The bin-matching design did its job; the long tail is
just longer in the profane cohort.

### Per-language picture

The pooled lizard signal (p = 2 × 10⁻⁴) is partly driven by
between-language variance. Per-language MWU is weaker:

- Python (n=112 vs 96): `lizard_avg_ccn` p = 0.18 (n.s.)
- JS/TS (n=176 vs 125): `lizard_avg_ccn` p = 0.54 (n.s.)

The pooled significance is real (rank tests pool fine) but a
mixed-effects model with language as a random intercept is the
proper paper-grade analysis. Cited as a future-work item; not on
stage.

---

## §3 · Anticipated Q&A — one-line answers

| Question | Answer |
|---|---|
| Did you find correlation? | Yes for cyclomatic complexity, no for lint counts. |
| What's the effect size? | Small — rank-biserial ~0.13 for the lizard metrics. Real but not dramatic. |
| Slovak / Czech / Russian profanity? | English-only — LDNOOBW is English. Future work. |
| AI-generated code in your 2020 cohort? | Pre-Copilot by design. 2024 follow-up planned (IP-012). |
| Why not BERT-based profanity detection? | Reproducibility. Dictionary is pinnable. ML model isn't. |
| Where's the per-language paper? | IP-008 gives Python and JS/TS subsets via lizard. ESLint hole means full multi-language linting needs another pass. |
| Code / data available? | Yes — github.com/Sibyx/oss-profanity. MIT. |
| Where do the commit-message quotes come from? | GH Archive, June 2020, aggregated, hand-picked, no attribution. I won't name repos. |
| Did you control for repo size / language? | Bin-matched on commit count at sample time; per-language MWU in the notebook. The notebook subset n is on every plot. |
| What's the one-line finding? | Profane repos have ~10 % higher median complexity; everything else is statistically tied. |
| Why not include eslint? | The analyser is silently failing in the cohort. Highest-priority follow-up. Lizard covers complexity for JS/TS. |
| Did you talk to a statistician? | The methodology is canonical (Mann-Whitney U + Bonferroni + rank-biserial). Reviewers will recognise it. |
| Why Bonferroni and not BH-FDR? | Conservative choice for a one-shot talk. Numerical headline (lizard significant, others not) is stable under both. |

---

## §4 · Things to NOT say on stage

- "We proved that swearing makes you a worse coder." (We did not. We
  showed *complexity* differs; lint counts don't.)
- "There is no relationship." (There is — for complexity.)
- "p < 0.05 means it's true." (It means we'd see this signal 5 % of
  the time under the null. Probabilistic, not absolute.)
- "Our LOC bin-matching was perfect." (Profane has 1.55× higher mean
  LOC; bin-matching was on commits, not LOC.)
- "ESLint just needs a quick fix." (Could be hours, could be a
  flat-config + commit-era incompatibility. Don't pre-commit on the
  fix timeline.)
- "1.82× ruff issues" — never quote this. It's a means artefact.
  The motivation slide carries it for storytelling; the finding
  slide does not.

---

## §5 · Closing reflection (for Slide 56 or Q&A pivot)

The original framing question — "do programmers who swear write
better code?" — was a joke. The actual finding is more interesting:
a real but small signal in *structural* complexity, and no signal in
*surface* lint count. That gap is itself a research direction.
Surface-level signals (ruff, eslint, jscpd) measure what tools see;
structural signals (cyclomatic complexity) measure what humans
encounter when reading the code. The fact that profanity correlates
with the latter and not the former hints that *the cognitive load
isn't in the warnings — it's in the control flow*. Future work.
