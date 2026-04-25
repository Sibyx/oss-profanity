# oss-profanity

**Does swearing — or 🚀-ing — in commit messages correlate with code quality?**

A research pipeline that mines one month of [GH Archive](https://www.gharchive.org/),
scores profanity and emoji in commit messages and source comments, runs static
analysers over a stratified cohort of repositories, and tests for correlation
between each signal and common code-quality metrics.

Built as the artefact behind the Bratislava OpenCamp 2026 talk
*"Vulgarizmy, otvorený kód a jeho kvalita"*.

## Research question

Is there a measurable correlation between **affect signals** in developer
communication (profanity and emoji in commit messages, code comments,
identifiers) and the quality of the source code they produce? Profanity and
emoji are analysed as two independent signals — profanity carries a shared
negative valence, while emoji are a noisier, mixed signal (🚀 vs 🐛 vs 💩).

- **Null:** neither rate is correlated with code-quality metrics.
- **Alternative:** at least one of the two correlates, in either direction —
  an inverse correlation ("angry devs write better code") would be as
  interesting as a positive one.

## Headline results

A single-pool Mann–Whitney U test against a five-metric Bonferroni-corrected
family (α = 0.01) on the canonical June-2020 cohort of **1 295 repositories**
(688 clean / 607 profane, bin-matched on commit volume):

| Metric                             | Median Δ (profane − clean) | p           | r<sub>rb</sub> | Significant |
|------------------------------------|----------------------------|-------------|----------------|-------------|
| `lizard_ccn_p99` (top-1 % complexity) | +2.55 decisions / function | 6.6 × 10⁻⁵ | 0.141          | ✅           |
| `lizard_avg_ccn` (avg complexity)     | +0.20 decisions / function | 2.0 × 10⁻⁴ | 0.131          | ✅           |
| `comment_to_code_ratio`               | −0.003                     | 0.46        | −0.024         | ❌           |
| `ruff_issues_per_kloc` (Python only)  | +10.3 issues / kloc        | 0.48        | 0.057          | ❌           |
| `jscpd_duplicate_rate`                | −0.002                     | 0.89        | 0.004          | ❌           |

**Code in profane repositories is measurably more convoluted — about 10 % more
decisions per function on average — but the effect is small.** Lint warnings,
copy-paste rate, and comment density show no measurable cohort difference.

A separate descriptive pass shows commit-message-language affect bleeds into
the source: profane-cohort repos carry significantly more profanity in code
comments (p = 2.9 × 10⁻¹²) and identifiers (p = 3.4 × 10⁻¹⁰) than clean-cohort
repos.

Full results, methodology, and plots: [`notebooks/ip-008-results.ipynb`](notebooks/ip-008-results.ipynb)
and [`presentation/results.json`](presentation/results.json).

## Dataset

- **Source:** GH Archive public event stream
- **Window:** June 2020 (lockdown peak, pre-Copilot / pre-ChatGPT — human-generated commits)
- **Volume:** ~150 GB compressed JSON, 744 hourly files, ~50 M events,
  ~20 M `PushEvent`s, ~40 M commits across ~500 K unique repos
- **Cohort:** 1 295 deeply-analysed repos, stratified-sampled (profane vs clean,
  bin-matched on commit volume), no manual curation

## Architecture at a glance

```
GH Archive .json.gz
        │
        ▼
  Stage 1+2: ingest + score commit profanity & emoji ──► MongoDB (repos collection)
        │
        ▼
  Stage 3: stratified cohort sampling (profane vs clean)
        │
        ▼
  Stage 4: git clone + checkout historical SHA + static analysis
           (source profanity + emoji + ruff / eslint / lizard / bandit / jscpd)
        │
        ▼
  Stage 5: aggregation + plots + correlation tests
```

One MongoDB collection (`repos`) holds everything; one document per repo.
Stage 4 uses atomic `findAndModify` claims so workers coordinate without a queue.

## Prerequisites

- **Python 3.14** (`uv venv` picks it up)
- **Docker Engine ≥ 24** with **Compose v2.20+**
- **MongoDB 7** — local on `mongodb://localhost:27017`, or the bundled
  `docker compose up mongo` service on `mongodb://localhost:27019`
- **GitHub Personal Access Token** (optional) — raises Stage 4's REST limit
  from 60/h to 5 000/h

Every env var and module-level tunable is documented in
[`docs/CONFIGURATION.md`](docs/CONFIGURATION.md).

## Quick start

```bash
uv venv && uv pip install -e ".[dev]"
export MONGO_URI=mongodb://localhost:27017/profanity_dev
pytest
```

Stage-by-stage run (each stage is an idempotent `python -m` entrypoint):

```bash
# Stage 1+2 — stream GH Archive hourly files, score profanity + emoji
GHA_START=2020-06-01-00 GHA_END=2020-06-30-23 \
python -m oss_profanity.archive_ingest

# Stage 3 — stratified cohort sampling
python -m oss_profanity.sampling

# Stage 4 — deep analysis (clone → ruff / eslint / lizard / bandit / jscpd)
WORKER_CONCURRENCY=12 SCRATCH_DIR=/scratch \
python -m oss_profanity.repo_worker
```

## Smoke harness

A single command that exercises the full pipeline end-to-end on a 4-hour
ingest window. Runs against a dedicated `profanity_smoke` database — the
operator's production `profanity` data is never touched.

```bash
./scripts/smoke.sh      # or: make smoke
```

On an M1 Max this takes ~9 minutes. Exit code 0 = green; any assertion failure
surfaces as a named `FAIL` line in `docker compose logs assertions`.

To run individual pipeline stages inside the image without the full smoke chain:

```bash
docker compose --profile ingest run --rm ingest
docker compose --profile worker up --scale worker=3 worker
```

## Documentation

| Doc | What's in it |
|-----|--------------|
| [`docs/DRAFT.md`](docs/DRAFT.md)                 | Full experiment specification — infrastructure, schema, per-stage algorithms |
| [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md) | Every env var, module constant, external-binary pin                          |
| [`docs/COHORT.md`](docs/COHORT.md)               | Plain-language cohort-sampling explainer                                     |
| [`docs/SCHEMA.md`](docs/SCHEMA.md)               | MongoDB document shapes                                                      |
| [`docs/IDEAS.md`](docs/IDEAS.md)                 | Parking lot for follow-up studies                                            |

## Known limitations

Stated upfront, not buried in slides:

- Profanity detection is noisy — Scunthorpe-class false positives, slang false
  negatives; ~5 % error budget.
- Emoji semantics are ambiguous — we count occurrence, not sentiment.
- Static analysis only — no `npm install`, no `cargo build`, no type-checked
  analysis.
- Correlation, not causation.
- Language bias — LDNOOBW word lists vary in quality across languages
  (emoji are Unicode-universal, so this bias is profanity-only).
- The ESLint analyser silently failed on every JS/TS repo in the 0.1.0
  cohort; the headline analysis omits the ESLint metric. See [`CHANGELOG.md`](CHANGELOG.md).
- Stratified sampling produces balanced cohorts, not a representative sample
  of GitHub.

## Citation

If you use this software or its results, please cite via [`CITATION.cff`](CITATION.cff)
or use the *Cite this repository* button on GitHub.

## Author

Jakub Dubec — <jakub.dubec@stuba.sk>
