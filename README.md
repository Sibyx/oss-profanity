# oss-profanity

**Does swearing — or 🚀-ing — in commit messages correlate with code quality?**

A research pipeline that mines one month of [GH Archive](https://www.gharchive.org/) data, scores two affect signals (profanity and emoji) in commit messages and source comments, runs static analyzers (ruff, ESLint, lizard) over a sampled cohort of repositories, and tests for correlation between each signal and common code-quality metrics.

Built as an experiment for an OpenCamp conference talk. The null hypothesis says neither signal is correlated with quality; the result either confirms the null or reveals a direction worth a second look. Profanity and emoji are measured independently — they may tell very different stories.

## Status

Stages 1+2 (IP-005 ingest), 3 (IP-006 sampling), and 4 (IP-007 deep analysis) are implemented. The Docker harness (IP-009) is accepted and ready to ship. The approach is specified in [`docs/DRAFT.md`](docs/DRAFT.md) and decomposed into implementation proposals in [`docs/PLAN.md`](docs/PLAN.md); see [`docs/proposals/index.md`](docs/proposals/index.md) for per-proposal status.

## Research question

Is there a measurable correlation between affect signals in developer communication (profanity and emoji in commit messages, code comments, and identifiers) and the quality of the source code they produce?

- **Null:** neither profanity rate nor emoji rate is correlated with code quality metrics
- **Alternative:** at least one of the two correlates with code quality (direction unspecified; an inverse correlation would be as interesting as a positive one). The two signals are analyzed independently — profanity carries a shared negative valence, while emoji usage is a noisier, more mixed signal (🚀 vs 🐛 vs 💩).

## Dataset

- **Source:** GH Archive public event stream
- **Window:** June 2020 (lockdown peak, pre-Copilot / pre-ChatGPT — human-generated commits)
- **Volume:** ~150 GB compressed JSON, 744 hourly files, ~50M events, ~20M `PushEvent`s, ~40M commits across ~500K unique repos
- **Deep-analysis cohort:** 1,500–3,000 repos, selected by stratified sampling (profane vs. clean), no manual curation

## Architecture at a glance

```
GH Archive .json.gz
        │
        ▼
  Stage 1+2: ingest + score commit profanity & emoji ──► MongoDB (repos collection)
        │
        ▼
  Stage 3: stratified cohort sampling (profane vs. clean)
        │
        ▼
  Stage 4: git clone + checkout historical SHA + static analysis
           (source profanity + emoji + ruff / eslint / lizard)
           (36 concurrent repos across 3 workers)
        │
        ▼
  Stage 5: aggregation + plots + correlation tests (profanity and emoji, separately)
```

One MongoDB collection (`repos`) holds everything; one document per repo. Stage 4 uses atomic `findAndModify` claims so workers coordinate without a queue.

See [`docs/DRAFT.md`](docs/DRAFT.md) for the full specification (infrastructure, schema, per-stage algorithms, deployment).

## Repository layout

```
oss-profanity/
├── README.md                 # this file
├── oss_profanity/            # Python package (implementation)
├── docs/
│   ├── DRAFT.md              # full experiment specification
│   ├── PLAN.md               # implementation decomposition into proposals
│   ├── CONFIGURATION.md      # all env vars + module tunables + external-binary pins
│   └── proposals/            # IP-XXX implementation proposals
│       ├── index.md
│       └── posts/
└── .venv/
```

## Prerequisites

- **Python 3.14** (`.python-version` pins this; `uv venv` picks it up)
- **Docker Engine ≥ 24** with **Compose v2.20+** (smoke harness uses profiles + `--exit-code-from`)
- **MongoDB 7** — either local (e.g. Homebrew `mongodb-community`) on `mongodb://localhost:27017` or the bundled `docker compose up mongo` service on `mongodb://localhost:27019`. Port **27018** is reserved for the SSH tunnel to the faculty / production Mongo during data migration — do not point local tools at it unless you mean production
- **GitHub Personal Access Token** (optional) — raises Stage 4's REST limit from 60/h to 5,000/h; see [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md) for setup

Every env var and module-level tunable is documented in [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md).

## Quick start

Minimum local dev setup:

```bash
uv venv && uv pip install -r requirements-dev.txt
export MONGO_URI=mongodb://localhost:27017/profanity_dev
pytest
```

Stage-by-stage run (each stage is an idempotent `python -m` entrypoint):

```bash
# Stage 1+2 — stream GH Archive hourly files, score profanity + emoji, upsert to repos
GHA_START=2020-06-01-00 GHA_END=2020-06-30-23 \
python -m oss_profanity.archive_ingest

# Stage 3 — stratified cohort sampling (see docs/COHORT.md for the method)
python -m oss_profanity.sampling

# Stage 4 — deep analysis (clone → ruff/eslint/lizard/bandit/jscpd → GitHub enrich)
WORKER_CONCURRENCY=12 SCRATCH_DIR=/scratch \
python -m oss_profanity.repo_worker
```

See [`docs/COHORT.md`](docs/COHORT.md) for a plain-language explainer of the sampling design.

## Smoke harness (IP-009)

A single command that exercises the full pipeline end-to-end on a 4-hour ingest window. Runs against a dedicated `profanity_smoke` database — the operator's production `profanity` data is never touched.

```bash
./scripts/smoke.sh      # or: make smoke
```

On M1 Max this takes ~9 minutes (ingest 4 h of GHA, sample a 5+5 cohort, analyze 10 repos in parallel, run six PyMongo assertions). Exit code 0 = green; any assertion failure surfaces as a named `FAIL` line in `docker compose logs assertions`. See [`docs/proposals/posts/ip-009-docker-test-harness.md`](docs/proposals/posts/ip-009-docker-test-harness.md) for the full design.

To run individual pipeline stages inside the image without the full smoke chain:

```bash
docker compose --profile ingest run --rm ingest
docker compose --profile worker up --scale worker=3 worker
```

## Documentation

| Doc | What's in it |
|-----|--------------|
| [`docs/DRAFT.md`](docs/DRAFT.md) | Full experiment specification — infrastructure, schema, per-stage algorithms |
| [`docs/PLAN.md`](docs/PLAN.md) | Implementation decomposition into IP-001 … IP-010 |
| [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md) | Every env var, module constant, external binary pin |
| [`docs/COHORT.md`](docs/COHORT.md) | Plain-language cohort-sampling explainer (talk source) |
| [`docs/SCHEMA.md`](docs/SCHEMA.md) | MongoDB document shapes |
| [`docs/IDEAS.md`](docs/IDEAS.md) | Parking lot for follow-up studies |
| [`docs/proposals/index.md`](docs/proposals/index.md) | IP-XXX proposal index with implementation status |

## Known limitations

Stated upfront, not buried in slides:

- Profanity detection is noisy — Scunthorpe-class false positives, slang false negatives; ~5% error budget
- Emoji semantics are ambiguous — we count occurrence, not sentiment (🚀 usually means "release", but we don't try to classify intent)
- Static analysis only — no `npm install`, no `cargo build`, no type-checked analysis
- Correlation, not causation
- Language bias — LDNOOBW word lists vary in quality across languages (emoji are Unicode-universal, so this bias is profanity-only)
- Stratified sampling produces balanced cohorts, not a representative sample of GitHub; emoji cohorts are sliced post-hoc from the same ingest data

## Author

Jakub Dubec — <jakub.dubec@stuba.sk>