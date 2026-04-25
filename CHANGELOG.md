# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-04-25

First public release — the artefact behind the Bratislava OpenCamp 2026 talk
*"Vulgarizmy, otvorený kód a jeho kvalita"*.

### Added

- Five-stage research pipeline: GH Archive ingest → profanity + emoji scoring
  → stratified cohort sampling → deep analysis (clone + ruff / lizard /
  bandit / jscpd / ESLint + tree-sitter source scan) → aggregation and plots.
- Docker harness with a one-command smoke run that exercises the full
  pipeline against a four-hour ingest window.
- Slidev presentation deck auto-published to GitHub Pages on push to `master`.
- Results notebook over a canonical 1 295-repo June-2020 cohort
  (688 clean / 607 profane).

### Known issues

- The ESLint analyser silently fails on every JS/TS repo in the cohort
  (100 % missingness on `eslint_issues`). The headline analysis drops the
  ESLint metric and reports five quality lenses instead of six. Fix
  scheduled for the next release.

[0.1.0]: https://github.com/Sibyx/oss-profanity/releases/tag/0.1.0
