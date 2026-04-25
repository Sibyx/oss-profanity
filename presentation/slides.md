---
theme: seriph
layout: cover
background: '#fff'
title: "Vulgarizmy, otvorený kód a jeho kvalita"
info: |
  OpenCamp Bratislava 2026 — Jakub Dubec (FIIT STU)
  A serious answer to a silly question.
author: Jakub Dubec
lang: en-US
transition: slide-left
mdc: true
lineNumbers: false
colorSchema: light
fonts:
  sans: Open Sans
  mono: Fira Code
drawings:
  persist: false
---

# Vulgarizmy, otvorený kód a jeho kvalita

<div class="mt-4 text-xl opacity-80">
  Profanity, open-source code, and its quality
</div>

<div class="mt-2 text-base opacity-60">
  A serious answer to a silly question
</div>

<div class="abs-bl m-8">
  <img src="/images/logo_fiit.svg" class="h-10" alt="FIIT STU" />
</div>

<div class="abs-br m-8 text-sm opacity-40">
  Jakub Dubec · OpenCamp · 2026-04-25
</div>

<!--
Hello. This talk is 60 minutes about a question that sounds like a joke
but turned into 3 months of rigorous software: do programmers who swear
write better code? I'll tell you what I built, what I found, and what
I did not find yet. Pragmatic, academic, occasionally funny. Let's go.
-->

---

# The stereotype

> **"NVIDIA, fuck you!"**
>
> — Linus Torvalds, LKML, 17 June 2012

<v-click>

Linus on the kernel mailing list, middle finger on camera, rejecting
NVIDIA's out-of-tree driver approach. Public record. Now a meme.

</v-click>

<v-click>

Programmers have opinions. They put them in writing. Sometimes in
`git commit -m`.

</v-click>

<!--
The Linus moment is the canonical public artifact of the
"programmers-who-swear" stereotype. It's real, it's citable, it's the
anchor for the rest of the talk. We're not debating whether programmers
swear — they do. The question is whether it correlates with anything
measurable.
-->

---
layout: two-cols
---

# The tweet that started this

<div class="text-base mt-4 leading-relaxed">

February 2023. Prof. Alexandros Stamatakis tweets about a
Bachelor's thesis from his lab at <strong>KIT Karlsruhe</strong>:

</div>

<blockquote class="mt-4 italic text-lg border-l-4 pl-4 border-[#00A9E0]">
"A Bachelor thesis in my lab makes a seminal contribution to software
engineering — open source codes written in C on github have higher
code quality when they contain swear words."
</blockquote>

<div class="mt-4 text-sm opacity-70">
644k views · 1.4k retweets · 8.4k likes
</div>

<v-click>

<div class="mt-4 text-base">
The internet did what the internet does. The thesis itself
is a serious piece of work, and it deserves engagement — not memes.
</div>

</v-click>

::right::

<div class="ml-4">
  <img src="/images/origin/stamatakis_tweet.png" class="rounded-lg shadow-md" alt="Stamatakis tweet" />
</div>

<!--
Show the meme honestly. The audience either remembers it or wants to
see it. Stamatakis is the reviewer named on the thesis cover; the
tweet is what made the thesis go viral. Pause briefly so people can
read the histograms — clean repos in the left, swear repos on the right,
visibly shifted to higher SoftWipe scores. The hook beat is "this is
where the question came from for me." Don't dwell — the next slide is
the actual thesis.
-->

---

# The actual thesis

**Strehmel, J. (2023).** *Is there a Correlation between the Use of
Swearwords and Code Quality in Open Source Code?* Bachelor's thesis,
Karlsruhe Institute of Technology, ITI. Supervisor: Stamatakis.

<v-clicks>

- **C source only** — GitHub code-search, ~3,800 swear-repos vs ~7,600 star-repos
- Quality measured via [**SoftWipe**](https://www.nature.com/articles/s41598-021-89495-8) — single 0–10 score, dynamic + static analysers
- Stats: KS-test, Welch's t-test, Jarque-Bera, bootstrapped CIs
- **Result:** swear-repos mean **5.87** vs star-repos **5.41** (p ≈ 10⁻⁶¹)
- Conclusion: *"a statistically significant correlation between swearing and an improvement in code quality"*

</v-clicks>

<v-click>

<div class="fiit-callout-info mt-4 text-sm">
Honest, well-documented work. The thesis explicitly flags that this
is observational, that correlation ≠ causation, and that practical
significance need not follow statistical significance.
</div>

</v-click>

<!--
Dead serious slide. Strehmel did good honest research. The methodology
is replicable, the data is documented, and the limitations are named
in the thesis itself. We are not here to dunk on a Bachelor thesis;
we are here to extend it. Critical points the audience should leave
with: (1) C-only, (2) star-repos as proxy for quality (popularity ≠
quality), (3) means + Welch's t-test on a heavy-tailed distribution
is statistically defensible but vulnerable to long-tail outliers, (4)
no matched cohort — comparing "repos with swearwords" against "repos
with ≥4 stars" measures whatever else differs between those groups.
-->

---

# What we wanted to fix

<div class="grid grid-cols-2 gap-6 mt-4 text-sm">

<div>

**Strehmel 2023**

- C only
- Star-repos as proxy for quality
- One quality dimension (SoftWipe)
- Means + Welch's t-test
- Code-search snapshot, not time-bounded
- ~11k repos total

</div>

<div>

**This work — 2026**

- 18 languages via tree-sitter
- Bin-matched commit-activity cohorts
- Five separate quality dimensions
- Rank tests + Bonferroni + effect size
- GH Archive 2020-06 — frozen window, pre-Copilot
- 3.7 M repos seen, 1,295 deeply analysed

</div>

</div>

<v-click>

<div class="mt-4 text-base opacity-80">
Same question, harder methodology. Same direction in the answer
(spoiler: no, not quite — read on).
</div>

</v-click>

<!--
This slide names the deltas without snark. Each row is a defensible
methodology improvement, not a personal critique. The point: research
is iterative. Strehmel asked the question; we tighten the
measurement. By the time we land on the inferential slide later in
the deck, the audience already knows we're looking at five
independent metrics rather than one composite — and that's why our
"significant" answer is more constrained than the original headline.
-->

---

# The question

<div class="text-3xl font-semibold mt-8 leading-snug">
Is there a statistically significant correlation between
<span style="color: #00A9E0">profanity</span> in commits / code and
<span style="color: #00A9E0">measurable code quality</span>?
</div>

<!--
Big type, single beat. This is the research question. Not "do
programmers swear" (trivially yes) and not "does swearing make better
programmers" (untestable without a mind-reading experiment). The
question that CAN be answered: is there a statistical relationship
between a text-level signal (profanity frequency) and a tool-level
signal (ruff/eslint/lizard quality metrics)?
-->

---
layout: center
---

# The answer

<div class="text-3xl font-semibold mt-8">
I don't know yet.
</div>

<v-click>

<div class="text-xl mt-6 opacity-80">
But I built a pipeline that <strong>will</strong>.
</div>

</v-click>

<v-click>

<div class="mt-8 text-base opacity-60">
And that pipeline is the interesting part.
</div>

</v-click>

<!--
Own the joke upfront. The audience came for a punchline; they're
getting methodology. If I pretend to have the p-value already, some
grad student will corner me at the coffee break and catch me out. So:
be honest, be self-aware, move on. The rest of the talk is the build,
the measurement, the descriptive stats, and the epistemics.
-->

---

# Today's agenda

<v-clicks>

1. **Prior art** — what has been studied, what hasn't
2. **Methodology** — the four-stage pipeline, in detail
3. **Tech stack** — how it's built, what's boring, what's clever
4. **Results so far** — the descriptive stats from 3.7 million repos
5. **AI & the future** — what Copilot might do to commit messages
6. **Q & A** — and the reading list

</v-clicks>

<!--
Seven acts total if you count the title; six after the hook. Pacing:
methodology and results each get 15 minutes; the AI act is a short
5-minute speculation; Q&A closes. Watch the clock on methodology — it's
the dense one.
-->

---
layout: section
---

# Prior art

*The research gap this talk lives in*

---

# What has been studied

<v-clicks>

- **Strehmel (KIT 2023)** — the thesis we already covered: C only, SoftWipe, means
- **Guzman & Azócar (MSR 2014)** — commit-message sentiment analysis
- **Miller et al. (ICSE 2022)** — toxicity in OSS communication
- **Baruch et al. (J. Managerial Psychology 2017)** — *"Swearing at work: the mixed outcomes of profanity"*
- Various — profanity in chat, issues, code review
- Sadly-many — "top 10 worst commit messages" blog posts

</v-clicks>

<!--
There's real work on sentiment and toxicity in OSS. Strehmel 2023 is
the closest methodological neighbour — same question, narrower
scope. Guzman/Azócar mined commit messages for sentiment. Miller et
al. looked at toxicity specifically. Baruch is the workplace
psychology angle — swearing as stress relief, not necessarily
correlation with output. None of them asked "does this correlate with
multiple code-quality metrics at scale, with matched cohorts, on a
modern language mix?" That's the gap.
-->

---

# What has NOT been studied rigorously

<v-clicks>

- Profanity vs. **multiple** code-quality dimensions on the **same** cohort
- **Matched cohorts** — profane vs. clean, same commit activity
- **Multi-language** — beyond C, with the right linter per primary language
- **AST-level** signal — profanity in *identifiers*, not just messages
- **Reproducible pipeline** — someone else can re-run our numbers, byte-identical

</v-clicks>

<v-click>

> The gap isn't "nobody thought of it." Strehmel asked the question.
> We tighten the measurement.

</v-click>

<!--
The list is short, specific, and falsifiable. If anyone knows a paper
that does this rigorously — please tell me at the break. I'll gladly
cite it. The closest approach (Strehmel 2023) hits one quality metric
on one language; we extend it. The matched-cohort + multi-metric +
multi-language + reproducible combo is where this work sits.
-->

---

# The hypothesis — in plain English

<div class="grid grid-cols-2 gap-6 mt-6">
<div>

**The boring outcome**

Pick a profane repo and a clean repo at random. Their code-quality
numbers look about the same. Profanity is just noise.

</div>

<div>

**The interesting outcome**

The two pools <strong>tilt</strong>. One side tends to score higher
than the other on at least one quality measurement.

</div>
</div>

<v-click>

<div class="mt-6 text-base opacity-90">
Our job: line up every repo by quality, ask whether profane repos
cluster on the high end or the low end of that line — and prove the
clustering didn't happen by chance.
</div>

</v-click>

<!--
Translate the H₀ / H₁ pair into plain English. The boring outcome is
the null hypothesis: no difference, profanity tells us nothing about
quality. The interesting outcome is what we test for. The "line up
every repo by quality" line is a soft introduction to rank tests —
we'll come back to it on the statistical-test slide. Keep it light;
the audience hasn't seen the numbers yet.
-->

---

# Why GH Archive?

<div class="grid grid-cols-2 gap-6">
<div>

**What it is**

- Every public GitHub event
- Hourly `.json.gz` dumps
- Free, unauthenticated HTTPS
- Lineage back to 2011

</div>

<div>

**Why 2020-06**

- **Mature** repos — we see them today with 4+ years of commits
- **Pre-Copilot** — humans wrote these commits, not LLMs
- **One month** = 744 files = manageable batch

</div>
</div>

<v-click>

Downside: 34% of the 2020 repos were gone from GitHub by 2026 —
renamed, privated, deleted. We'll handle that in Stage 3.

</v-click>

<!--
GH Archive is gwern-tier infrastructure. Free, stable, well-documented,
archive.org-mirrored. Choosing June 2020 is deliberate: we wanted
repos mature enough to have code-quality signals (not "day-old empty
scaffold") but pre-LLM (so the signal is human, not GPT). The 34%
attrition surprised me — I'll talk about that in Stage 3.
-->

---
layout: section
---

# Methodology

*15 minutes — the dense act*

---

# Pipeline overview

```mermaid
graph LR
    S1[Stage 1<br/>Collect<br/>every public commit] --> S2[Stage 2<br/>Score<br/>profanity + emoji]
    S2 --> S3[Stage 3<br/>Match<br/>profane vs. clean pools]
    S3 --> S4[Stage 4<br/>Analyse<br/>five quality lenses]
    S4 --> S5[Stage 5<br/>Compare<br/>does the tilt exist?]

    style S5 fill:#e6f6fc,stroke:#00A9E0
```

<v-click>

Five stages. Each one zooms in on the one before. The next dozen
slides walk through them.

</v-click>

<!--
The picture is the whole talk in one slide. Every subsequent
methodology slide zooms in on one box. Plain-English labels: collect,
score, match, analyse, compare. The technical names (Mann-Whitney U,
Bonferroni etc.) live on the dedicated stats slide, not here.
-->

---

# Stage 1 · GH Archive ingest

<v-clicks>

- **744 files** — every hour of June 2020
- `~50 GB` compressed, streamed through Python
- Filter: `PushEvent` only (drops issues, stars, forks)
- Flatten: one row per *commit*, not per event
- Deduplicate: identical commit SHA across multiple events
- Drop bots: `BOT_REGEX` matches dependabot, renovate, greenkeeper, GitHub Actions

</v-clicks>

<v-click>

Output: `~49 M` commit-level rows aggregated per repo.

</v-click>

<!--
Streaming is the key word. At 50 GB compressed, naive "download all,
then process" would need ~200 GB disk and a day of wait. Streaming
lets us process each hourly file as it arrives and discard the raw
bytes. The bot filter is aggressive but leaky — we'll see in the
Results act that 🤖 is the #3 most-common emoji, because humans
copy bot-style conventions.
-->

---

# Stage 2a · Profanity scoring

<v-clicks>

- **[LDNOOBW](https://github.com/LDNOOBW/List-of-Dirty-Naughty-Obscene-and-Otherwise-Bad-Words)** — List of Dirty, Naughty, Obscene and Otherwise Bad Words
- Shopify's open dataset, ~2 500 English terms
- Word-boundary match — not substring
- Per-repo counters: `profanity_hits`, `profanity_rate`, top-N word histogram

</v-clicks>

<v-click>

<div class="fiit-callout-info mt-4">
Why a dictionary, not ML? Reproducibility (Shopify pins the list), explainability (you can look up every match), and speed (49 M messages in ~5 h on one host).
</div>

</v-click>

<!--
LDNOOBW is the canonical "bad words" list in the open-source world.
Shopify maintains it, multiple languages, versioned. A neural model
would give me slightly better recall but lose reproducibility — a
year from now the model weights would be different and my numbers
would be non-replayable. Word-boundary + lingua guards against the
"xxx in hex strings" false-positive cluster we'll see in results.
-->

---

# Stage 2b · Emoji scoring

<v-clicks>

- **Unicode CLDR** via the `emoji` Python package
- **Grapheme-cluster** aware — `👨‍👩‍👧` is ONE emoji, not three
- **ZWJ-joiner** aware — "man + woman + girl" joined by U+200D
- Per-repo counters: `emoji_hits`, `emoji_rate`, top-20 emoji

</v-clicks>

<v-click>

<div class="fiit-callout mt-4">
<code>len("👨‍👩‍👧")</code> is <strong>8</strong> in Python. Using <code>len()</code> for emoji counting is one of the top sources of off-by-N bugs in text pipelines.
</div>

</v-click>

<!--
Unicode is where naive text processing goes to die. A "family" emoji
is visually one glyph but 8 code points (or more). The `emoji` package
handles the grammar correctly. CLDR is the authoritative source for
"what counts as an emoji" — you don't want to write that logic
yourself. Trust me.
-->

---

# Stage 3 · Cohort sampling

<v-clicks>

- **Cohort A — profane**: top 750 by `profanity_rate desc`
- **Cohort B — clean**: `profanity_hits == 0`, sampled per bin
- **Bins** (commit-count): `[20, 50)  [50, 200)  [200, 1000)  [1000, ∞)`
- Clean cohort **matches** profane's bin distribution

</v-clicks>

<v-click>

<div class="fiit-callout-info mt-4">
Why bin-matching? Without it, big projects would dominate cohort A (more commits = more chances to swear), and the clean cohort would be biased toward tiny repos. We'd be measuring project size, not profanity.
</div>

</v-click>

<!--
Stratified matching is the single most important methodology choice
in this pipeline. A naive "all profane vs. all clean" comparison would
be confounded by repo size, language, activity, whatever. By matching
on commit count, we're asking: "given two repos of similar activity,
does the profane one have different quality?" That's the comparison
that can answer the question.
-->

---

# Stage 3 · The top-up story

When the cohort was probed against GitHub — surprise:

<v-clicks>

- **509 / 1 500 repos were GONE** — 34% attrition
- Deleted, renamed, privated, transferred
- 2020 was a long time ago in GitHub years

</v-clicks>

<v-click>

<div class="mt-6">

Fix: `python -m oss_profanity.sampling --top-up`
</div>

- Demotes probe-404 rows to `status="missing"`
- Redraws the shortfall from the unused pool
- Back to 1 500 live. 1.7% residual 404s.

</v-click>

<!--
SKIPPABLE IF SHORT ON TIME — this slide is a good "data-hygiene
lessons" story but the hypothesis test doesn't depend on it. If we're
running tight, jump to Stage 4. Worth saying: the top-up's bias
effect is that we draw the #751..#1019 most-profane repos on the
second pass, so average rate drifts down slightly — documented in
IP-006's methodology appendix.
-->

---

# Stage 4 · Repo worker

<v-clicks>

- **36 concurrent repos** — 3 hosts × 12 processes
- `multiprocessing.Pool` per host, not Celery, not Airflow
- **MongoDB CAS** is the queue primitive
- Partial clone, resolve SHA < 2020-07-01, checkout, analyze, write back

</v-clicks>

<v-click>

<div class="fiit-callout-info mt-4">
One <code>find_one_and_update</code> per claim. Mongo serialises per-document updates, so 36 concurrent claims hand out 36 distinct documents. No Redis, no lock manager.
</div>

</v-click>

<!--
This is the "boring is a feature" moment. We had Redis on the plan;
we deleted Redis from the plan. The CAS primitive on the document
collection IS the queue. It scales perfectly for our workload — 36
claims per second max, Mongo barely notices.
-->

---

# Stage 4 · Five separate quality lenses

<v-clicks>

- **Lint warnings (Python)** — `ruff` · "your code probably has a bug or a style problem here"
- **Security smells (Python)** — `bandit` · "this looks like a way an attacker could get in"
- **Lint warnings (JS / TS)** — `eslint` · *failed across the cohort, see footnote*
- **Code complexity** — `lizard` · "how many decisions does the reader have to follow inside one function?"
- **Copy-paste rate** — `jscpd` · "how much of the codebase is duplicated chunks?"

</v-clicks>

<v-click>

<div class="mt-4 text-base">
Each lens asks a different question. We <strong>never</strong> mash
them into one "quality score" — that's where snake-oil lives.
A repo can be lint-clean and still impossibly complex; another can
have warnings everywhere and beautifully simple control flow.
</div>

</v-click>

<v-click>

<div class="fiit-callout mt-4 text-sm">
ESLint produced no data on any of our 1 295 repos — the analyser is
silently failing on 2020-era JavaScript. The complexity lens
covers JS / TS instead. Fixing ESLint is the top follow-up.
</div>

</v-click>

<!--
Translated for a popular audience. Linter = "your code probably has a
bug here." Cyclomatic complexity = "decisions in one function." Clone
detection = "duplicated chunks." This is the slide where we let go of
brand names and let go of file extensions; the next slide on
statistical method needs an audience that already understands
"five different questions, five different answers." If anyone asks
"why not SonarCube / CodeClimate / Codacy" — those are vendor tools,
black-box, versioned outside our control. For reproducibility we
needed self-hosted pinned versions. That rules out the SaaS cluster.
-->

---

# Stage 4 · AST-level source scan

<div class="grid grid-cols-2 gap-4">
<div>

**Regex approach — WRONG**

```javascript
const url = "https://a.com/x";   // real
const fake = "// not a comment";
```

Regex `//.*$` matches *both* `//`s. The second is inside a string
literal.

</div>

<div>

**Tree-sitter — RIGHT**

```text
parse_string(lang, src)
  → tree.find_nodes_by_type("comment")
  → only the real // comment
```

40 language grammars, one API,
one pinned version.

</div>
</div>

<v-click>

<div class="mt-4">

Same logic for identifiers: comments + identifier names get profanity
and emoji scanned separately. A `def fuck_it()` would score on
identifiers, not comments.

</div>

</v-click>

<!--
This is the "clever bit" slide. Regex for code parsing works until it
doesn't — and it doesn't in the pathological cases that dominate at
49 M rows of scale. Tree-sitter solves it properly. The Rust/PyO3
binding is fast (parses a typical source file in microseconds).
-->

---

# Stage 5 · How we ask the question

<div class="text-base mt-2 leading-relaxed">

Imagine all 1 295 repos lined up on a long bench, sorted by one
quality measurement. Two colours: <span style="color:#676767;font-weight:600">grey</span> for
clean, <span style="color:#00A9E0;font-weight:600">blue</span> for profane. If profanity is noise,
the colours should be shuffled randomly. If profanity matters, blue
should clump on one end.

</div>

<v-clicks>

- The actual test counts how often a blue repo ranks higher than a grey one and asks: *is that count further from 50 % than chance allows?*
  <span class="text-xs opacity-60">(textbook name: Mann–Whitney <em>U</em> rank test — non-parametric, ignores outliers)</span>
- We run this <strong>five times</strong> — one per quality lens.
- Five tries at finding "something interesting" inflates false alarms. We tighten the bar five-fold so a finding has to be five-times-more-convincing before we report it.
  <span class="text-xs opacity-60">(textbook name: Bonferroni correction at α / 5 = 0.01)</span>
- And we ask "<em>how big</em> is the tilt?" — small, medium, or strong — separately from "is it real?"
  <span class="text-xs opacity-60">(textbook name: rank-biserial correlation, effect size)</span>

</v-clicks>

<v-click>

<div class="fiit-callout-info mt-3 text-sm">
Why the bench-sort framing? Code-quality numbers have nasty outliers
— one giant monorepo can drag any "average" to nonsense. Ranks ignore
how big the outlier is, only where it sits in line.
</div>

</v-click>

<!--
This is the popular-science version of the methodology slide.
Mann-Whitney U is "line up the repos and count blue-above-grey
swaps." Bonferroni is "tighten the bar because we're looking five
times." Effect size is "how big is the tilt." The technical names
stay on screen as faint footnotes — the audience can google them
later if they want — but the load-bearing story is told in plain
English. The bench-sort metaphor is the one I want them to leave
with; it's also the metaphor that makes ECDFs make sense on the
results slide.
-->

---

# Reproducibility claim

Every pinned tool, every pinned version, one image SHA:

<div class="grid grid-cols-2 gap-4 mt-4 text-sm">

<div>

**Python side**

- Python 3.14
- `tree-sitter-language-pack==1.6.2`
- `ruff==0.15.12`
- `bandit==1.9.4`
- `lizard==1.17.25`
- `lingua==2.2`
- `emoji>=2.15`

</div>

<div>

**Node side**

- `eslint@10.2.1`
- `@eslint/js@10.0.1`
- `typescript-eslint@8.59.0`
- `jscpd@4.0.9`

</div>

</div>

<v-click>

<div class="mt-4">

Image tag: `ghcr.io/sibyx/oss-profanity:sha-<...>`. Re-run on 2032-01-01
— byte-identical results.

</div>

</v-click>

<!--
Reproducibility isn't a nice-to-have for this project; it's the
difference between "interesting paper" and "curiosity." Every tool is
pinned, the image SHA is captured, the GH Archive slice is frozen in
time (it's archival data by definition). If the paper lands in a
journal, a reviewer can literally re-run the numbers.
-->

---

# Limitations we know about

<v-clicks>

- **English-only swearword list** — Slovak, Czech, Russian profanity slips through
- **Short commit messages are noisy** — one `fuck` in 3 commits ≠ a culture
- **Forks inherit parent history** — we don't yet deduplicate forked commits
- **The window is June 2020** — predates Copilot deliberately; won't generalise to today
- **Tools are imperfect proxies** — a "warning count" of zero doesn't make code good

</v-clicks>

<!--
Name the limits BEFORE the results. It's cheap and it earns trust.
The English-only caveat is the biggest one — the dataset certainly
contains Slovak and Czech commit messages, and our dictionary misses
them entirely. If someone asks about Slovak profanity in Q&A, the
answer is: future work, yes, happy to collaborate.
-->

---

# Ethics

<div class="text-lg">

<v-clicks>

- Scored at the **repository** level, never the author
- No `commits[].author` values in this deck
- Top-N words shown in aggregate across 3.7 M repos
- Commit-message quotes: **hand-picked, grandma-filtered, no attribution**

</v-clicks>

</div>

<v-click>

<div class="mt-6 fiit-callout-info">
The point is never to embarrass an individual. The point is whether
the signal, in aggregate, correlates with anything measurable.
</div>

</v-click>

<!--
Dead serious slide. Research on public data still has ethical weight.
Anyone could grep for the "worst commits" list and go punch down. That
would destroy the academic value of the work. So: aggregate only,
anonymised quotes, repository-level only. If the paper becomes
popular, someone will ask for the list of "the most profane repos" —
the answer is no.
-->

---

# Tech stack

*10 minutes — boring is a feature*

---

# The stack at a glance

<v-clicks>

- **Python 3.14** — everything ingest + analysis
- **MongoDB 7** — one collection, 3.7 M documents, 1.3 GB on disk
- **Docker + Compose** — one image, four role profiles
- **GitHub Actions → GHCR** — every push publishes an image
- **Tree-sitter + LDNOOBW + lingua + `emoji`** — the detection libs

</v-clicks>

<v-click>

<div class="mt-6 opacity-70">
What's NOT here: Redis, Kafka, Airflow, Celery, Kubernetes, a vector DB.
</div>

</v-click>

<!--
Deliberately boring. Every additional component has a maintenance
cost and a debuggability cost. The minimum stack that does the job is
the best stack. If we ever scale to 100 M repos or go real-time, the
picture changes. For now: the less moving parts, the less to debug
at midnight.
-->

---

# Why MongoDB

<v-clicks>

- **Document-per-repo** is the natural shape
- `$group` does 90 % of what we need for stats
- `find_one_and_update` gives us atomic **CAS** for free
- No migrations — add a field, write it, query it
- `extra="allow"` in our Pydantic models absorbs GitHub API drift

</v-clicks>

<v-click>

<div class="fiit-callout-info mt-4">
We planned Redis as a work queue. We deleted Redis from the plan. Mongo's CAS on one document IS the queue.
</div>

</v-click>

<!--
The Mongo choice gets pushback from database-traditionalists. Fair.
For THIS workload — append-heavy writes, document-shaped data,
compare-and-set as the only concurrency primitive — Mongo fits like a
glove. A proper RDBMS would also work; the point is that we never
hit the joins / transactions / referential-integrity problems that
usually push people toward Postgres.
-->

---

# Pydantic schema

```python
class Repo(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    id: int = Field(alias="_id")
    full_name: str
    first_seen_at: datetime
    commit_stats: CommitStats
    status: Status = "seen"
    cohort: Cohort | None = None
    code_analysis: CodeAnalysis | None = None
    github_metadata: GitHubMetadata | None = None
```

<v-click>

<div class="mt-4">

One source of truth between Python and Mongo. `extra="allow"` is the
"GitHub added a new field" escape hatch.

</div>

</v-click>

<!--
Pydantic validates at the boundary and gives us type hints all the way
down. `extra="allow"` is crucial for this project — GitHub's REST API
changes shape every few months and we'd rather absorb new fields than
break on deploy. If a field becomes load-bearing, we add it to the
model; otherwise it rides along as unstructured data.
-->

---

# Parallelism without tears

<div class="grid grid-cols-2 gap-4">
<div>

**The claim**

```python
doc = db.repos.find_one_and_update(
    {"status": "pending"},
    {"$set": {"status": "claimed",
              "claimed_by": worker_id,
              "claimed_at": now()}},
    sort=[("commit_stats.profanity_rate", -1)],
    return_document=AFTER,
)
```

</div>

<div>

**The guarantee**

- Atomic per document
- Concurrent callers get distinct documents
- Failure mode: `None` → sleep + retry

</div>
</div>

<v-click>

36 concurrent workers, no lock manager, no duplicate claims. Ever.

</v-click>

<!--
This is the slide engineers in the audience nerd out over. It's 10
lines of code that replaces an entire Celery deployment. Mongo's
per-document atomicity does the heavy lifting. We don't need a
broker, we don't need acks, we don't need dead-letter queues. The
primitive IS the queue.
-->

---

# Docker everywhere

<v-clicks>

- **One Dockerfile** — ingest, sampling, worker, assertions all share it
- **Role-based profiles** — `docker compose --profile ingest run ingest`
- **Same image, different entrypoints** — less drift between test and prod
- Faculty hosts pull `ghcr.io/sibyx/oss-profanity:master`
- Laptop builds the same image locally (M1 Max — see `docs/deploy/local`)

</v-clicks>

<!--
"Same bits everywhere" is the IP-009 + IP-010 story condensed. The
smoke test that gates merges uses the exact image that drains the
1,500-repo cohort. If it's green on your laptop, it's green on the
faculty. That's the Docker promise — we just leaned all the way in.
-->

---

# GHA → GHCR

```mermaid
graph LR
    push[git push master] --> build[GitHub Actions]
    build --> img[ghcr.io/sibyx/oss-profanity:master<br/>+ :sha-<short><br/>+ :v0.1.0]
    img --> w1[worker 1]
    img --> w2[worker 2]
    img --> w3[worker 3]
```

<v-click>

<div class="mt-4">

Rollback = `git revert + git push + docker compose pull && up -d`.
No bespoke tooling.

</div>

</v-click>

<!--
Content-addressed deploy is one of the most valuable things you can
do for a small project. GHCR is free for public packages, integrated
with Actions, and operator-facing pulls are unauthenticated. The SHA
tag is what the paper's "Reproducibility" section cites.
-->

---

# "Boring" is a feature

<v-clicks>

- No Kafka
- No Airflow
- No Kubernetes
- No Celery
- No service mesh
- No vector DB

</v-clicks>

<v-click>

<div class="mt-6 text-xl">

The boring scaffolding buys us the freedom to ask the <strong>interesting</strong> question.

</div>

</v-click>

<!--
Resist the temptation to over-engineer research infrastructure. Every
component you add is a component you have to debug at midnight two
days before the conference. The goal is answering the question, not
showing off the toolchain. Boring = reliable = more time for the
actual research.
-->

---
layout: section
---

# Results so far

*15 minutes — the numbers*

---

# Ingest by the numbers

<div class="grid grid-cols-2 gap-4 mt-6">

<div class="stat-big">
  <div class="value">3,702,633</div>
  <div class="label">repos seen</div>
</div>

<div class="stat-big">
  <div class="value">~49 M</div>
  <div class="label">commits scored</div>
</div>

<div class="stat-big">
  <div class="value">744</div>
  <div class="label">hourly files parsed</div>
</div>

<div class="stat-big">
  <div class="value">~50 GB</div>
  <div class="label">compressed throughput</div>
</div>

</div>

<v-click>

<div class="text-center mt-6 text-sm opacity-60">
June 2020 — 30 days × 24 hours — one GH Archive slice
</div>

</v-click>

<!--
Four big numbers. The 3.7 M repos number always surprises people — GH
Archive captures everything public, including tiny one-commit
experiments. Of those 3.7 M, only ~700 k hit our minimum-activity
floor of 20 commits in-window. The cohort (1,500 repos) is drawn from
that filtered subset.
-->

---

# Profanity prevalence

<div class="mt-8 text-center">

<div class="text-5xl font-bold text-[#00A9E0]">0.08 %</div>

<div class="text-lg mt-4 opacity-80">
of commit messages contain at least one LDNOOBW match
</div>

</div>

<v-click>

<div class="mt-6 text-center opacity-60">

38 468 profane commits out of ~49 M total

</div>

</v-click>

<v-click>

<div class="fiit-callout mt-6">
The audience expected more. So did I. Turns out <strong>professional
software developers are professionally polite in public Git</strong> —
at least in English.
</div>

</v-click>

<!--
This was the first genuinely surprising number for me. If you'd asked
me "what fraction of commits contain profanity" I would have said
5-10%. The answer is 80× lower. Public-facing Git history is more
polite than you'd think. Which means the signal we ARE seeing is
concentrated — the repos that swear really swear a lot.
-->

---

# Emoji prevalence

<div class="mt-8 text-center">

<div class="text-5xl font-bold text-[#00A9E0]">0.49 %</div>

<div class="text-lg mt-4 opacity-80">
of commit messages contain at least one emoji
</div>

</div>

<v-click>

<div class="mt-6 text-center">

239 253 emoji commits — <strong>6× more than profanity</strong>

</div>

</v-click>

<v-click>

<div class="fiit-callout-info mt-6">
Developers emoji more than they swear. Probably because 🚀 is a commit
convention now, whereas "fuck" is still a personal choice.
</div>

</v-click>

<!--
The 6× factor is my second favorite finding. Emoji entered the
commit-message mainstream via conventional-commits, semantic-release,
and gitmoji. "I shipped this" became 🚀; "I fixed a bug" became 🐛.
Conventions propagate through ecosystems faster than individual
expression. Which is also why the AI act at the end predicts
emoji-per-commit stays flat or rises even as profanity declines.
-->

---

# Top profanity words

<img src="/images/plots/fig06_top_profanity.png" class="max-h-[420px] mx-auto" alt="Top-30 profanity words" />

<v-click>

<div class="fiit-callout mt-4 text-sm">
Wait — <code>xxx</code>? <code>xx</code>? Those aren't profanity. Those are <code>xxx-placeholder</code>, hex strings, version stubs. LDNOOBW matches the substring inside longer tokens.
</div>

</v-click>

<!--
The `xxx` and `xx` at the top are a methodology footnote. LDNOOBW
has "xxx" because it's slang for adult content, but in code it's 10×
more common as a placeholder. This is the "your detector finds things
that are not what you think" lesson. For the Mann-Whitney test we'll
either strip these or annotate them as "known false-positive cluster."
-->

---

# The NSFW subgenre

Down the top-30 list…

<v-clicks>

- `porn`, `sex`, `sexy`, `sexual`
- `vibrator`, `genitals`, `hentai`, `guro`
- `hardcore`, `cum`, `anal`, `dick`, `bitch`

</v-clicks>

<v-click>

<div class="fiit-callout mt-6">
There is a <strong>cottage industry of NSFW codebases on GitHub</strong>.
We did not plan for this. It's a methodology footnote and an
unexpected sampling challenge — in the cohort, they'll be
over-represented in cohort A unless we filter.
</div>

</v-click>

<!--
Genuinely didn't see this coming at design time. Adult-content repos
(fanfic tooling, adult-game mods, "toys" libraries) are a real
subgenre on GitHub and they're scored as maximally-profane by LDNOOBW.
For IP-008 we'll look at whether they skew results and consider either
(a) a topic-filter to exclude them, or (b) reporting the analysis with
and without. Either is a defensible choice; both need to be declared
in advance.
-->

---

# Top emoji

<div class="mt-4 text-sm">

<div class="bar-row"><div class="label">🚀</div><div class="bar" style="width: 100%"></div><div class="count">19 161</div></div>
<div class="bar-row"><div class="label">🐛</div><div class="bar" style="width: 50%"></div><div class="count">9 627</div></div>
<div class="bar-row"><div class="label">🤖</div><div class="bar" style="width: 50%"></div><div class="count">9 581</div></div>
<div class="bar-row"><div class="label">✨</div><div class="bar" style="width: 48%"></div><div class="count">9 249</div></div>
<div class="bar-row"><div class="label">🎩</div><div class="bar" style="width: 40%"></div><div class="count">7 779</div></div>
<div class="bar-row"><div class="label">⬆️</div><div class="bar" style="width: 34%"></div><div class="count">6 627</div></div>
<div class="bar-row"><div class="label">❤️</div><div class="bar" style="width: 34%"></div><div class="count">6 621</div></div>
<div class="bar-row"><div class="label">🎸</div><div class="bar" style="width: 23%"></div><div class="count">4 578</div></div>
<div class="bar-row"><div class="label">🎨</div><div class="bar" style="width: 21%"></div><div class="count">4 081</div></div>
<div class="bar-row"><div class="label">📝</div><div class="bar" style="width: 17%"></div><div class="count">3 378</div></div>

</div>

<!--
The emoji distribution is more concentrated than profanity — 🚀 alone
is ~40 % of the top-10. Next three slides unpack the meaning of the
leaders. Short version: emoji in commits is almost entirely
conventional (release, bugfix, feature) rather than expressive. We
keep this slide as inline HTML rather than a generated PNG because
matplotlib doesn't ship a colour-emoji font, so the chart rendered
as tofu boxes. The browser draws the glyphs natively.
-->

---

# 🚀 — the king of commits

<div class="text-center mt-8">

<div class="text-8xl">🚀</div>

<div class="text-3xl mt-4 font-semibold">19 161 commits</div>

<div class="mt-4 opacity-70">
Twice the next contender. The universal "ship it" glyph.
</div>

</div>

<v-click>

<div class="mt-6 text-center opacity-60">
Also: semantic-release, conventional-commits, "first release", "deploy to prod."
</div>

</v-click>

<!--
🚀 is the most commercialised emoji in open source. gitmoji.dev has
it listed as "ship new features." A generation of release automation
tools emit it by default. It's barely "expression" at this point — it's
more like punctuation for a specific event type.
-->

---

# 🤖 — the bot uprising

<div class="grid grid-cols-2 gap-6 mt-6">

<div>

**Expected**: 🤖 represents bot commits. Our `BOT_REGEX` should have
filtered them.

</div>

<div>

**Reality**: 🤖 is the **#3 most common emoji**. 9 581 commits.

</div>

</div>

<v-click>

<div class="mt-6">

Why? `BOT_REGEX` matches the **author name**. It doesn't filter
human authors who write `🤖 build(deps): bump ...` in the conventional
style bots taught them.

</div>

</v-click>

<v-click>

<div class="fiit-callout mt-6">
Methodology refinement for IP-008: strip <code>🤖</code>-prefixed messages before aggregating — or keep them as a separate "bot-adjacent" category.
</div>

</v-click>

<!--
Loved discovering this one. It's genuinely hard to filter bots when
humans imitate bot conventions. The `BOT_REGEX` is doing what it was
told — matching dependabot, renovate, greenkeeper etc as *authors* —
but not catching humans who've adopted the 🤖 prefix. A good reminder
that filters are always leaky and need validation at the output.
-->

---

# 🎩 and 🎸 — the Angular effect

<v-clicks>

- **🎩** — 7 779 commits. `angular/commit-message-convention` uses it for "hat tip."
- **🎸** — 4 578 commits. Not emotion. Code-style / formatting changes in the Angular style guide.
- The 🎸 count is **essentially one convention propagating through an ecosystem**.

</v-clicks>

<v-click>

<div class="mt-6 opacity-70">
Emoji in commits is ecosystem-level norms, not individual expression.
Gitmoji and friends made sure of that.
</div>

</v-click>

<!--
Most people don't know what 🎸 "means" in a commit. They know because
they adopted Angular's convention and then propagated it to the rest
of their stack. One style guide, thousands of commits. That's how
conventions spread.
-->

---

# Matched cohort — what actually drained

<div class="grid grid-cols-2 gap-4 mt-2">

<img src="/images/plots/fig01_cohort_funnel.png" alt="Cohort funnel"/>

<div class="text-sm leading-relaxed">

<v-clicks>

- **1 500 design target** · 2 × 750 bin-matched
- **1 295 done** with `code_analysis` populated
- **205 failed** — archived, oversized, no commits in window
- **764 missing** — top-up cycles for 404s
- Failure skews <strong>2.3×</strong> higher in the profane cohort — top-up draws hit deeper into the long tail

</v-clicks>

</div>

</div>

<v-click>

<div class="fiit-callout-info mt-3 text-sm">
Per-language: ruff numbers cite the 208-repo Python subset;
JS/TS goes through tree-sitter + lizard since ESLint silent-failed
across the cohort.
</div>

</v-click>

<!--
Honest subset reporting. You don't have to pretend you have 1,500
Python repos when you have 200. The matched design still holds — the
2.3× skew in failures is mechanical (top-up draws further into the
long tail of less-maintained repos), not a methodology break. The
fig01 funnel makes the n's concrete; the next slide does the
per-language complexity panel.
-->

---

# A few commit quotes

<div class="space-y-4 mt-6">

<div class="commit-msg">fuck mono</div>

<div class="commit-msg">i fucking hate git sometimes</div>

<div class="commit-msg">Fuck emojis.  You heard me.</div>

</div>

<v-click>

<div class="mt-6 opacity-60 text-sm">
Hand-picked from the 50-row sample · no repo or author attribution · grandma-approved
</div>

</v-click>

<!--
Three. One about a build tool (every dev has had this fight). One about
git (universal). One about emoji, which is a meta-callback to the
previous slide set — the audience laughs at themselves for counting 🚀
and then reading "fuck emojis." Hand-picked, no attribution. If anyone
asks where they came from: GH Archive, June 2020, aggregated,
unattributed. I'm not going to name repos.
-->

---

# What Stage 4 writes back

```json
{
  "_id": 123456789,
  "status": "done",
  "primary_language": "python",
  "code_analysis": {
    "loc_total": 12843,
    "files_scanned": 87,
    "comment_profanity_hits": 4,
    "identifier_profanity_hits": 0,
    "comment_emoji_hits": 1,
    "identifier_emoji_hits": 0,
    "ruff_issues": 234,
    "ruff_issues_per_kloc": 18.22,
    "lizard_avg_ccn": 3.4,
    "lizard_max_ccn": 22
  }
}
```

<v-click>

<div class="mt-4">

This is the input to Stage 5. 1 295 of these → 5 Mann-Whitney tests.

</div>

</v-click>

<!--
One document per repo. `code_analysis` is the structured payload
Stage 5 reads. Every field is a pre-computed quality dimension. The
Mann-Whitney test compares distributions of `ruff_issues_per_kloc`
etc. between the two cohorts. Five tests, Bonferroni-corrected (eslint
dropped — silent-failure on the cohort).
-->

---

# What lights up

<img src="/images/plots/fig03_lizard_avg_ecdf.png" class="max-h-[440px] mx-auto" alt="Cumulative distribution of code complexity per cohort"/>

<div class="text-center mt-2 text-sm opacity-70">
Read this as <em>"% of repos at or below this complexity score."</em>
The <span style="color:#00A9E0;font-weight:600">blue</span> (profane)
curve sits to the right of the
<span style="color:#676767;font-weight:600">grey</span> (clean) one
across the whole range — <strong>more decisions per function,
everywhere along the distribution</strong>.
</div>

<!--
The headline result, single-chart edition. ECDF is the visual
analogue of the rank test: profane curve sits to the right of clean
across the whole range, which is the picture our test is detecting
as a tilt. Pause here for a beat. The lint-count / clone-rate / comment
density results show no such gap — they're not on this slide because
there's nothing to see; we mention the negatives one slide later.
-->

---

# The worst function in each repo

<img src="/images/plots/fig04_lizard_p99_ecdf.png" class="max-h-[440px] mx-auto" alt="Cumulative distribution — worst-1 % function complexity per repo"/>

<div class="text-center mt-2 text-sm opacity-70">
Same chart, different question — instead of the <em>average</em>
function in each repo, this asks <em>"how convoluted is the
<strong>worst</strong> function in there?"</em> The gap is even
wider. Profane repos carry a heavier tail of nasty functions, even
when the bulk of the code looks similar.
</div>

<!--
Backup slide for the inferential answer. The previous chart showed
average-function complexity; this one shows the 99th-percentile —
"the worst function we found in each repo." The gap is wider here
than on the average, so the story is "profane repos hide more
pathological functions in their tails." Skippable if running long;
useful for Q&A. Avoid the term "p99" on stage; use "the worst
function" language so the audience never has to translate.
-->

---

# The descriptive picture (June 2020 cohort)

<div class="text-2xl mt-8 leading-relaxed">

<v-clicks>

- Profanity is <strong>rare</strong> — 0.08 % of commits.
- Emoji is <strong>6× more common</strong> — 0.49 %.
- Bots infiltrated commit conventions.
- The matched cohort drained: <strong>1,295 done</strong>.

</v-clicks>

</div>

<!--
Descriptive layer. The big numbers from the ingest. After this we hit
the inferential answer slide.
-->

---
layout: center
---

# The answer

<div class="text-3xl font-semibold mt-6 leading-snug">
Code in profane repos is <span style="color:#00A9E0">measurably more
convoluted</span> — about <span style="color:#00A9E0">10 %</span>
more decisions per function on average.
</div>

<v-click>

<div class="text-xl mt-5 opacity-80">
Real signal, but a <strong>small</strong> one. You'd have to look at
many repos before you noticed it from the outside.
<span class="text-sm opacity-70">(less than one chance in ten thousand it's a fluke)</span>
</div>

</v-click>

<v-click>

<div class="text-xl mt-5 opacity-80">
Lint warnings, copy-paste rate, and comment density?
<strong>No measurable difference between the two pools.</strong>
</div>

</v-click>

<v-click>

<div class="mt-6 text-base opacity-60">
1 295 repos analysed · five quality lenses · the JavaScript linter
silently failed and was excluded.
</div>

</v-click>

<!--
The takeaway slide, in plain English. The headline reads "more
convoluted" not "higher cyclomatic complexity." The p-value gets
translated to "less than one chance in ten thousand it's a fluke" —
this is technically loose but practically right and the audience can
hold onto it. The effect size translates to "small — you'd have to
look at many repos before noticing." Pause before clicking the lint
beat — that's the actual surprise. The audience came for "do swearing
programmers write better code" and the answer is "their code is
measurably more tangled but the linter cannot tell them apart." Q6/A
resolution slide — DO NOT skip this beat.
-->

---
layout: center
---

# Same direction. Different conclusion.

<div class="grid grid-cols-2 gap-8 mt-6 text-base">

<div>

**Strehmel 2023 — C only**

Profane repos scored higher on a single composite quality
score (5.87 vs 5.41 out of 10).

→ "swearing correlates with <strong>better</strong> code"

</div>

<div>

**This work — 18 languages, five lenses**

Profane repos have <strong>more convoluted code</strong>;
lint counts, copy-paste rate, and comment density are
indistinguishable.

→ swearing correlates with <strong>tangled</strong> code,
not bad code

</div>

</div>

<v-click>

<div class="mt-8 text-lg opacity-80">
Both signals point the same way: <strong>profane repos differ</strong>.
The 2023 headline read this as "better"; once we ask five separate
questions instead of one, "better" turns into "more tangled" — which
is no longer obviously good.
</div>

</v-click>

<!--
Reconciliation slide. The 2023 thesis is not "wrong"; SoftWipe is a
heterogeneous composite that mixes "code style" with "absence of
warnings." On a finer-grained stack — separating cyclomatic complexity
from lint counts from clone rate — the signal lives in *one* of those
dimensions. The audience should leave thinking "the picture got
sharper, not contradicted." That's the honest scientific outcome of
methodology iteration.
-->

---
layout: section
---

# AI & the future

*5 minutes — speculation, clearly marked*

---

# The LLM question

<v-clicks>

- Copilot GA: mid-2022
- Cursor: 2023. Claude: 2024. Cody + ChatGPT Desktop: 2024.
- By 2026, an unknown-but-non-trivial fraction of commits are AI-assisted
- **AI assistants are rigorously polite.** They don't swear.

</v-clicks>

<v-click>

<div class="text-xl mt-6">

What happens to <strong>🚀</strong>, <strong>shit</strong>, and
<strong>🐛</strong> as human-drafted commits dilute with AI-drafted ones?

</div>

</v-click>

<!--
This is the speculative act. Everything here is pattern-matching
hypothesis, not measured fact. The 2020 window was chosen specifically
because it predates Copilot — so any LLM effect on our data is zero
by construction. The interesting question is what a 2024 or 2026
re-run would show.
-->

---

# Hypothesis 1 · Profanity declines

<v-clicks>

- Baseline swear-in-commit rate is human-driven (our 0.08 %)
- AI assistants produce sanitised text by default
- If x% of future commits are AI-drafted, the aggregate rate falls by ~x%
- The <strong>per-developer</strong> baseline probably also declines
  — once your workflow is "Copilot drafts, you edit," you edit out the
  `fix: this is horrible`

</v-clicks>

<v-click>

<div class="fiit-callout mt-6">
Testable prediction: mean profanity-per-commit declines monotonically
from 2022 onward.
</div>

</v-click>

<!--
Falsifiable prediction. Run the pipeline on 2022, 2023, 2024 windows
and plot. If the prediction is right, the line slopes down. If it's
wrong, we learn something more interesting — maybe humans swear MORE
around AI code ("why are you like this, Copilot").
-->

---

# Hypothesis 2 · Emoji convention survives

<v-clicks>

- 🚀, 🐛, ✨ are **ecosystem norms**, not individual expression
- AI autocomplete is **trained on the past** — it reinforces conventions
- Human using Copilot writes "fix" → Copilot suggests "fix: 🐛 ..."
- The conventional-commits style PROPAGATES faster, not slower

</v-clicks>

<v-click>

<div class="fiit-callout mt-6">
Testable prediction: emoji-per-commit stays flat or <strong>rises</strong>
2022 onward — especially the conventional-commit emoji set.
</div>

</v-click>

<!--
This is the counter-intuitive prediction. You'd think AI would smooth
out all personality, and it does — but convention ISN'T personality.
Convention is structure. LLMs are pattern-matchers par excellence, so
they reinforce structured patterns. Emoji commit conventions are
exactly the kind of pattern they'd amplify.
-->

---

# Future work — the longitudinal redo

<v-clicks>

- Same pipeline, three windows: **2020-06**, **2024-06**, **2026-06**
- GH Archive is window-agnostic — one env var flip: `GHA_START` / `GHA_END`
- Each window: ~5 h ingest + ~6 h Stage 4 + an afternoon of Stage 5
- Publishable year-over-year finding
- Plus: ESLint debug, NSFW sensitivity, Slovak / Czech / Russian
  swearword lists, mixed-effects per-language model

</v-clicks>

<v-click>

<div class="fiit-callout-info mt-4 text-sm">
The pipeline is deliberately time-, language-, and dictionary-agnostic.
Most of these follow-ups are env-var flips, not new pipelines.
</div>

</v-click>

<!--
The pipeline is deliberately time-agnostic. Everything from Stage 1
to Stage 5 runs on whatever window you tell it. So the longitudinal
study is already within reach — it's just another run. That's the
upside of being boring: marginal experiments are cheap.
-->

---

# The meta-question

<div class="text-xl mt-8 leading-relaxed">

If AI assistants iron out the rough edges of code, do we
<strong>lose signal</strong>?

</div>

<v-click>

<div class="mt-6 opacity-80">
A grumpy <code>// this is horrible</code> comment is a canary for how
much of the <strong>author</strong> is still in the work.
</div>

</v-click>

<v-click>

<div class="mt-6 opacity-80">
When the comment disappears, so does a cultural marker.
</div>

</v-click>

<v-click>

<div class="mt-4 opacity-70 text-sm">
Not a bad outcome, not a good outcome — <em>a measurable outcome</em>.
</div>

</v-click>

<!--
End Act VI on the actually-interesting philosophical note. The joke
opening was "do swearing programmers write better code?" The end is
"does AI homogenise the cultural fingerprint of a codebase?" That's
the sneaky real question, and the pipeline we just walked through
can in principle answer it.
-->

---
layout: section
---

# Q & A

*5 minutes*

---
layout: center
class: text-center
---

# Thank you

<div class="text-lg opacity-70 mt-4">
Jakub Dubec · FIIT STU · <a href="https://github.com/Sibyx/oss-profanity">github.com/Sibyx/oss-profanity</a>
</div>

<div class="mt-6">
  <img src="/images/logo_fiit.svg" class="h-10 inline-block" alt="FIIT STU" />
</div>

<div class="mt-10 text-sm opacity-50">
Slides at <code>presentation/opencamp/</code> in the repo. PDF export
committed pre-talk. CC-BY-SA.
</div>

<!--
Pause here for applause then hand over to Q&A. Anticipated questions
and one-line answers (keep in your head):

- "Slovak swearing?" — future work; LDNOOBW is English; happy to
  collaborate on a Slovak list.
- "Why not ML profanity detection?" — reproducibility; dictionary
  is pinnable.
- "Did you find anything?" — descriptively yes, inferentially wait for
  the paper.
- "Which language swears most?" — reserved for IP-008.
- "Is this funded?" — PhD programme at FIIT STU, self-directed.
- "Code / data available?" — yes, MIT-licensed, on GitHub.
- "Can I reproduce your numbers?" — yes, image SHA is in the deploy
  runbook.
- "AI tooling?" — used for scaffolding and code; acknowledge and move
  on, no dedicated slide.
-->

---

# Further reading

<div class="grid grid-cols-2 gap-x-8 gap-y-3 text-sm mt-4">

<div>

**Prior art**

- **Strehmel, J. (2023).** *Is there a Correlation between the Use of
  Swearwords and Code Quality in Open Source Code?* B.Sc. thesis,
  KIT Karlsruhe.
- Zapletal, A. et al. (2021). *The SoftWipe tool and benchmark for
  assessing coding standards adherence of scientific software.*
  Sci. Rep. 11.
- Guzman, E. & Azócar, D. (2014). *Sentiment analysis of commit
  comments in GitHub.* MSR.
- Miller, C. et al. (2022). *"Did you miss my comment or what?"* ICSE.
- Baruch, Y. et al. (2017). *Swearing at work: the mixed outcomes
  of profanity.* JMP.

</div>

<div>

**Tools I leaned on**

- [Tree-sitter](https://tree-sitter.github.io/) — 40-grammar AST parser
- [LDNOOBW](https://github.com/LDNOOBW) — Shopify's bad-words list
- [lingua-rs](https://github.com/pemistahl/lingua-rs) — language detection
- [`emoji`](https://pypi.org/project/emoji/) — Unicode CLDR binding
- [`lizard`](https://github.com/terryyin/lizard) — cyclomatic complexity, 18 langs

</div>

<div>

**Method**

- Mann, H. & Whitney, D. (1947). *On a test of whether one of two
  random variables is stochastically larger than the other*. Ann.
  Math. Stat.
- Kerby, D. (2014). *The simple difference formula: an approach to
  teaching nonparametric correlation*.
- Bonferroni, C. (1936). *Teoria statistica delle classi e calcolo
  delle probabilità.*

</div>

<div>

**Infra**

- [GH Archive](https://www.gharchive.org/) — 2011-present
- [MongoDB docs](https://www.mongodb.com/docs/) — aggregation ref
- [Slidev](https://sli.dev/) — this deck's engine
- [github.com/Sibyx/oss-profanity](https://github.com/Sibyx/oss-profanity) — code, data, this deck

</div>

</div>

<!--
Photograph this slide if you want it offline. Left column is the
research context, right is the tooling I credit. Notes mention that
this slide is photographed frequently — leave it up an extra beat.
-->

---

# Credits

<v-clicks>

- **Jan Strehmel & Alexandros Stamatakis (KIT)** — for the original
  thesis and the question that started this
- **FIIT STU** — hardware, PhD program, institutional support
- **OpenCamp organisers** — for the slot, the venue, the stage
- **LDNOOBW maintainers** — Shopify + contributors
- **tree-sitter authors** — every grammar in the pack
- **pemistahl** — `lingua-rs` + the language-pack
- **Unicode Consortium** — CLDR emoji data
- **You** — for sitting through 60 minutes of this

</v-clicks>

<!--
Last slide before Q&A. Brief credits. Keep it under 45 seconds so we
preserve the full 5 minutes for audience questions.
-->

---
layout: center
class: text-center
---

# Questions? 🙋

<div class="mt-4 opacity-70">
<a href="https://github.com/Sibyx/oss-profanity">github.com/Sibyx/oss-profanity</a>
</div>

<div class="mt-8 text-sm opacity-50">
<em>"Public Git history is 80× more polite than you'd think — and 6× more emoji-ful than profane."</em>
</div>

<!--
Open the floor. If nobody volunteers in the first 5 seconds, I prompt:
"What's the most surprising number in the talk for you?" That
usually cracks the ice.
-->
