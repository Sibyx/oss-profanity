# oss-profanity

**Does swearing in commit messages correlate with code quality?**

A research pipeline that mines one month of [GH Archive](https://www.gharchive.org/) data, scores profanity in commit messages and source comments, runs static analyzers (ruff, ESLint, lizard) over a sampled cohort of repositories, and tests for correlation between profanity rate and common code-quality metrics.

Built as an experiment for an OpenCamp conference talk. The null hypothesis says profanity is uncorrelated with quality; the result either confirms the null or reveals a direction worth a second look.

## Status

Early development. The approach is specified in [`docs/DRAFT.md`](docs/DRAFT.md) and decomposed into implementation proposals in [`docs/PLAN.md`](docs/PLAN.md). Code lives under `oss_profanity/` and is currently a stub.

## Research question

Is there a measurable correlation between profanity usage in developer communication (commit messages, code comments) and the quality of the source code they produce?

- **Null:** profanity frequency is uncorrelated with code quality metrics
- **Alternative:** profanity frequency correlates with code quality (direction unspecified; an inverse correlation would be as interesting as a positive one)

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
  Stage 1+2: ingest + score commit profanity ──► MongoDB (repos collection)
        │
        ▼
  Stage 3: stratified cohort sampling (profane vs. clean)
        │
        ▼
  Stage 4: git clone + checkout historical SHA + static analysis
           (36 concurrent repos across 3 workers)
        │
        ▼
  Stage 5: aggregation + plots + correlation tests
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
│   └── proposals/            # IP-XXX implementation proposals
│       ├── index.md
│       └── posts/
└── .venv/
```

## Known limitations

Stated upfront, not buried in slides:

- Profanity detection is noisy — Scunthorpe-class false positives, slang false negatives; ~5% error budget
- Static analysis only — no `npm install`, no `cargo build`, no type-checked analysis
- Correlation, not causation
- Language bias — LDNOOBW word lists vary in quality across languages
- Stratified sampling produces balanced cohorts, not a representative sample of GitHub

## Author

Jakub Dubec — <jakub.dubec@stuba.sk>