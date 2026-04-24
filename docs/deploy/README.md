# docs/deploy

Reference files the operator copies to `/opt/oss-profanity/` on each of the
three faculty worker hosts:

- [`compose.yml`](compose.yml) — single-service Compose pointing at
  `ghcr.io/sibyx/oss-profanity:master` with `restart: on-failure` and a named
  `scratch` volume.
- [`.env.example`](.env.example) — per-host env template. Copy to `.env`,
  fill in `GITHUB_TOKEN`, `chmod 600`.

See [`docs/DEPLOYMENT.md`](../DEPLOYMENT.md) for the full operator runbook
(first-time setup, rollout, monitoring queries, shutdown, troubleshooting,
reproducibility).
