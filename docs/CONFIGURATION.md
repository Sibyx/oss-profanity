# Configuration Guide

Every tunable in the oss-profanity pipeline, with defaults, source files, and when each one actually matters.

## Quick reference

| Where                                 | What                                                        | How to change                                                      |
|---------------------------------------|-------------------------------------------------------------|--------------------------------------------------------------------|
| **Environment**                       | Pipeline tunables (Mongo, concurrency, ingest window, caps) | Export env vars before launching `ingest` / worker / harness       |
| **Module constants**                  | Detection heuristics, tool flags, skip rules                | Edit the owning module; constants are intentionally not env-driven |
| **`/opt/baseline-eslint.config.mjs`** | ESLint rule set                                             | Shipped by IP-009's Dockerfile; change in the image, not per-repo  |
| **External binaries on PATH**         | `ruff`, `eslint`, `jscpd`                                   | Installed by IP-009's Dockerfile / IP-010's worker setup script    |

## Environment variables (IP-001)

Loaded once at import time into a frozen dataclass in [`oss_profanity/config.py`](../oss_profanity/config.py). Every process (ingest, worker, aggregation) must have at minimum `MONGO_URI` set. Missing required vars raise `ValueError` at import — that's the intended failure mode for batch jobs.

| Variable               | Default                                                    | Purpose                                                                                |
|------------------------|------------------------------------------------------------|----------------------------------------------------------------------------------------|
| `MONGO_URI`            | *(required)*                                               | PyMongo connection string, e.g. `mongodb://10.150.104.106:27017/profanity`             |
| `WORKER_CONCURRENCY`   | `12`                                                       | `multiprocessing.Pool` size per worker host                                            |
| `GHA_START`            | `2020-06-01-00`                                            | First hourly GH Archive file to ingest                                                 |
| `GHA_END`              | `2020-06-30-23`                                            | Last hourly GH Archive file to ingest                                                  |
| `SCRATCH_DIR`          | `/scratch`                                                 | Where repo clones land; must have headroom for the largest repo × `WORKER_CONCURRENCY` |
| `BOT_REGEX`            | `(bot\|dependabot\|renovate\|github-actions\|greenkeeper)` | Case-insensitive regex; matching authors' commits are dropped                          |
| `MAX_REPO_SIZE_MB`     | `2048`                                                     | GitHub API pre-check; larger repos are skipped before clone                            |
| `PER_REPO_TIMEOUT_SEC` | `600`                                                      | Hard cap per repo in Stage 4; exceeds → `status=failed`, `failure_reason=timeout`      |
| `STALE_CLAIM_TTL_MIN`  | `20`                                                       | Claims older than this are reclaimed as `pending` (handles dead workers)               |
| `EMOJI_TOP_N`          | `20`                                                       | Size of per-repo `emoji_top` counter after truncation                                  |
| `SAMPLE_PROFANE_N`     | `5`                                                        | Max profane commit messages retained per repo for talk material                        |
| `GITHUB_TOKEN`         | *(optional)*                                               | Personal access token for GitHub REST enrichment in Stage 4 (IP-007); unauth mode works but rate-limits at 60/hour per IP |
| `GITHUB_USER_AGENT`    | `oss-profanity/0.1 (jakub.dubec@stuba.sk)`                 | Sent on every GitHub API call so Cloudflare / GitHub abuse team can identify us        |
| `GIT_SUBPROCESS_TIMEOUT_SEC` | `300`                                                | Per-call timeout for each `git` subprocess in Stage 4 (clone / rev-list / checkout)    |

### `.env` file support

`oss_profanity/config.py` calls `dotenv.load_dotenv(override=False)` at import time, so a local `.env` next to the repo root (or anywhere up the cwd chain) is picked up automatically. A template lives at [`.env.example`](../.env.example) — copy it to `.env` and edit.

Rules of the game:

- **Real environment variables win.** `override=False` means `export MONGO_URI=...` in a shell (or a pytest `monkeypatch.setenv`, or a Docker `environment:` block) always beats the `.env` value.
- **Missing `.env` is a no-op.** Production deploys (IP-009 Docker, IP-010 OpenStack) don't need one.
- **`.env` is git-ignored.** Only `.env.example` is committed.
- **Tests are isolated.** `conftest.py` sets `MONGO_URI=mongodb://localhost:27017/profanity_test` as a default **before** `config.py` imports; tests that actually need Mongo skip unless `TEST_MONGO_URI` is also set.

### Local development

```bash
cp .env.example .env
# Edit .env to set GHA_START / GHA_END to a narrow smoke window:
#   GHA_START=2020-06-01-00
#   GHA_END=2020-06-01-00
python -m oss_profanity.archive_ingest   # picks up .env
```

### Docker harness (IP-009)

Set these via `compose.yml` environment blocks per service. A 2-hour smoke test uses:

```yaml
environment:
  MONGO_URI: mongodb://mongo:27017/profanity
  GHA_START: "2020-06-01-00"
  GHA_END:   "2020-06-01-02"
  WORKER_CONCURRENCY: 2
```

### OpenStack deployment (IP-010)

Set in `/etc/environment` or a systemd drop-in; the setup scripts template these into place.

## GitHub token provisioning (IP-007)

Stage 4 workers make two authenticated REST calls per repo — `GET /repos/{full_name}` and `GET /repos/{full_name}/languages` — to enrich the `Repo.github_metadata` sub-document with stars, forks, topics, license, size, archived / disabled flags, byte-counts per language, and timestamps. The token raises the REST rate limit from 60/hour (unauth, per IP) to 5,000/hour (authenticated, per token). GitHub Pro does **not** raise REST limits; Pro raises Actions minutes and storage, not REST.

### Recommended: fine-grained personal access token

Fine-grained PATs (introduced 2022) have narrower blast radius than classic PATs.

1. Go to [github.com/settings/personal-access-tokens/new](https://github.com/settings/personal-access-tokens/new).
2. **Token name:** `oss-profanity-stage-4-worker`
3. **Expiration:** 30 days (matches the experiment timeframe; never leave tokens provisioned beyond project lifetime).
4. **Repository access:** "Public Repositories (read-only)". No need to enumerate repositories — this pseudo-scope grants read access to any public repo via REST.
5. **Account permissions:** leave at defaults (none required for public data).
6. **Repository permissions:** leave at defaults (none required for public data).
7. Click **Generate token** and copy the value once — GitHub shows it only at creation.
8. Set it as `GITHUB_TOKEN=github_pat_...` in the worker's environment.

### Alternative: classic personal access token

Use this only if the fine-grained UI is unavailable (e.g. some GitHub Enterprise accounts).

1. Go to [github.com/settings/tokens/new](https://github.com/settings/tokens/new).
2. **Note:** `oss-profanity-stage-4-worker`
3. **Expiration:** 30 days.
4. **Scopes:** **select none.** Classic tokens with zero scopes have the same visibility as unauthenticated requests for public repos, but count against the authenticated 5,000/hour rate limit rather than the 60/hour one.
5. Generate, copy, and set `GITHUB_TOKEN=ghp_...` in the worker environment.

### Verify the token is live

```bash
curl -sS \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  https://api.github.com/rate_limit \
  | python -c 'import json, sys; d = json.load(sys.stdin); print(d["resources"]["core"])'
```

Expected output fragment: `{'limit': 5000, 'remaining': 5000, ...}`. If `'limit': 60` appears, the token is not being read (env-var typo, missing `Authorization` header) — fix before running Stage 4.

### Security notes

- **Never commit the token.** It goes in `.env` (git-ignored) or a secret-manager env var on the deploy target. `.env.example` documents the variable name with an empty value.
- **Logs MUST NOT echo the `Authorization` header.** `httpx`'s default error messages redact credential headers; `_github.py` unit tests assert no token bytes appear in log output.
- **Rotate on suspected exposure** via the GitHub UI. Revoking the token immediately invalidates any in-flight workers using it.
- **Single shared token across all 36 workers is deliberate.** The 5,000/hour budget is per token; at 80 calls/minute shared across the pool we sit at ~1% of the secondary rate limit. Per-worker tokens would multiply the budget but add provisioning complexity that isn't justified at our scale.

### Rate-limit budget reference

At Stage 4 size (1,500 cohort repos, 2 calls per repo):

| Dimension | Value |
|---|---:|
| Total REST calls per run | 3,000 |
| Duration | 5-7 h |
| Calls per hour | ~430-600 (9-12% of 5,000/h ceiling) |
| Calls per minute (36 workers) | ~8-10 (~1% of 900/min secondary limit) |

Overnight capacity per token is 30,000 repos at two calls per repo — 20× the current cohort target. Full-population enrichment (~1 M repos) would take ~34 nights at this scope and is explicitly out of scope.

## Module-level constants

Everything below lives in Python module constants, not env vars — each one is a **design decision** with no operational tuning dimension, per the repo's "defer 'maybe later' parameters" principle. Change them by editing the owning file.

### Source walker — [`_walk.py`](../oss_profanity/analyzers/_walk.py)

| Constant | Default | When to change |
|---|---|---|
| `_SKIP_DIRS` | `node_modules, vendor, .git, dist, build, .venv, venv, __pycache__, .tox, .mypy_cache, .pytest_cache, .ruff_cache, target, .hg, .svn` | New tool conventions emerge (e.g., `.next` for Next.js builds). Add case-sensitive. |
| `_SKIP_NAME_SUBSTRINGS` | `(".min.", ".bundle.")` | New minified-bundle naming conventions show up in real data |
| `_MAX_FILE_BYTES` | `1_048_576` (1 MB) | Lowering reduces walk cost; raising pulls in generated/vendored megafiles that skew the study |

### Primary-language histogram — [`_language.py`](../oss_profanity/analyzers/_language.py)

| Constant | Purpose |
|---|---|
| `_LANGUAGE_TAGS` | The `identify` tags we vote on. **Intentionally excludes** markup/data (`markdown`, `json`, `yaml`, `toml`, `html`, `css`, `sql`) so a README-heavy Go repo classifies as `go`, not `markdown`. |

Tie-breaking is alphabetical so repeated runs produce the same answer.

### Tree-sitter extraction — [`_tokens.py`](../oss_profanity/analyzers/_tokens.py)

| Constant | Purpose |
|---|---|
| `_LANGUAGE_TAG_TO_TS` | `identify` tag → `tree-sitter-language-pack` parser name. Add an entry to support a new language. |
| `_COMMENT_NODE_TYPES` | Per-language override for comment AST node names (Rust uses `line_comment` / `block_comment`; most use `comment`) |
| `_IDENTIFIER_NODE_TYPES` | Per-language override for identifier AST node names (Haskell uses `variable`; most use `identifier`) |

Adding a grammar is: ship it in the Docker image (comes for free with `tree-sitter-language-pack`), add the `identify`→TS mapping, add override entries only if the grammar uses non-default node names.

### Tech-debt markers — [`_markers.py`](../oss_profanity/analyzers/_markers.py)

| Constant | Default | When to change |
|---|---|---|
| `_MARKER_RE` | `\b(TODO\|FIXME\|HACK\|XXX)\b` | Study wants to track additional markers (e.g., `NOTE`, `OPTIMIZE`, `DEPRECATED`) |

Case-sensitive by convention — lowercase `todo` in prose doesn't count.

### Profanity detection — [`profanity.py`](../oss_profanity/profanity.py)

| Constant | Default | Purpose |
|---|---|---|
| `_MIN_DETECT_LEN` | `20` | Lingua-py fallback threshold; text shorter than this falls back to English |
| `_LEETSPEAK_ENABLED` | `True` | Leetspeak normalization (`f4ck` → `fuck`, `@ss` → `ass`) before matching |
| `_LEETSPEAK_TABLE` | `"4103$5@!" → "aioessai"` | Leetspeak character map; extend if real data shows other obfuscation patterns |
| `_DETECTOR_CODES` | 24 ISO 639-1 codes | Lingua-py language-detection restriction; smaller set = smaller per-process memory |

### Emoji extraction — [`emoji_scan.py`](../oss_profanity/emoji_scan.py)

| Constant | Purpose |
|---|---|
| `_SKIN_TONE_CODEPOINTS` | `U+1F3FB..U+1F3FF` — stripped before counting so `👍🏽` collapses to `👍` |
| `_VS16` | `U+FE0F` — stripped for the same reason |

These are Unicode invariants, not tunables — a future `tone_sensitive=True` flag could expose them, but there is no request for it yet.

### Lizard wrapper — [`_lizard.py`](../oss_profanity/analyzers/_lizard.py)

| Constant | Default | When to change |
|---|---|---|
| `run(timeout=...)` | `120` s | Real run shows pathological repos hitting this consistently |

Per-function percentile aggregation is unconditional — lizard's XML carries the per-function records we need, and the `statistics.quantiles` cost is negligible.

### Ruff wrapper — [`_ruff.py`](../oss_profanity/analyzers/_ruff.py)

| Constant | Default | When to change |
|---|---|---|
| `_SELECT` | `E,W,F,I,N,UP,B,A,C4,SIM,RUF,S` | Study-wide rule set needs to vary (rarely) |
| `_BUG_PREFIXES` | `("F", "E9", "B", "S", "RUF")` | Ruff adds a new bug-class rule family that doesn't match any existing prefix |
| `run(timeout=...)` | `120` s | See lizard |

Any new ruff rule family not in `_BUG_PREFIXES` lands in `style` — conservative (under-reports bugs, doesn't invent them). The test suite pins `total == bug + style` so drift is caught fast.

### Bandit wrapper — [`_bandit.py`](../oss_profanity/analyzers/_bandit.py)

| Constant | Default | When to change |
|---|---|---|
| `run(timeout=...)` | `120` s | See lizard |

Bandit runs with its default rule set via `-r --exit-zero`. To restrict, add `-s`/`-t` flags by editing the argv.

### ESLint wrapper — [`_eslint.py`](../oss_profanity/analyzers/_eslint.py)

| Constant | Default | When to change |
|---|---|---|
| `_DEFAULT_CONFIG` | `/opt/baseline-eslint.config.mjs` | Never in this module — IP-009 ships the config |
| `run(timeout=...)` | `180` s | ESLint is the slowest tool; real-data calibration |

**The baseline config itself lives in the Docker image**, not the repo. IP-009's `Dockerfile` writes:

```js
// /opt/baseline-eslint.config.mjs
import js from "@eslint/js";
import tseslint from "typescript-eslint";
export default [
  { files: ["**/*.{js,mjs,cjs,jsx,ts,tsx}"],
    ...js.configs.recommended },
  ...tseslint.configs.recommended,
];
```

`@eslint/js`, `typescript-eslint`, and `eslint` itself are **version-pinned** in the Dockerfile so `recommended` means the same thing on every worker.

### jscpd wrapper — [`_jscpd.py`](../oss_profanity/analyzers/_jscpd.py)

| Constant | Default | When to change |
|---|---|---|
| `run(timeout=...)` | `180` s | Very large repos with many long runs |

jscpd's own `--min-lines`/`--min-tokens`/`--threshold` defaults are used. Pin jscpd version in the Docker image so duplication rates are comparable across cohorts.

### Parallel orchestrator — [`_runner.py`](../oss_profanity/analyzers/_runner.py)

| Constant | Default | When to change |
|---|---|---|
| `ThreadPoolExecutor(max_workers=4)` | `4` | IP-009 smoke test shows host CPU load > `vCPU × 2`; drop to `2` |
| `_PYTHON_TAGS` | `{"python"}` | You never change this |
| `_JS_TS_TAGS` | `{"javascript", "typescript", "jsx", "tsx"}` | Same |

The `max_workers=4` cap is sized for IP-007's 1.3 vCPU-per-repo budget. Raising it past 4 gains nothing (there are only 5 tasks at most) and risks thrashing the shared worker host.

## External binaries on PATH

These are **not Python deps**; IP-009's Dockerfile and IP-010's worker setup script are responsible for installing them at specific versions.

| Binary | Pin in | Used by |
|---|---|---|
| `lizard` | `requirements.txt` (Python package with CLI) | `_lizard.run` |
| `bandit` | `requirements.txt` | `_bandit.run` |
| `ruff` | Dockerfile (Rust binary) | `_ruff.run` |
| `eslint`, `@eslint/js`, `typescript-eslint` | Dockerfile (Node) | `_eslint.run` |
| `jscpd` | Dockerfile (Node) | `_jscpd.run` |
| `git` | Dockerfile (system) | IP-007 worker clone |
| `node`, `npm` | Dockerfile (system) | `eslint`, `jscpd` runtime |

If any of these binaries is missing on PATH, the corresponding wrapper returns `None` for its fields rather than crashing. This is intentional: a partial-metric repo is still useful for the other correlation axes.

## Minimum local dev setup

```bash
# One-time
uv venv
uv pip install -r requirements-dev.txt

# Every shell
export MONGO_URI=mongodb://localhost:27017/profanity_dev

# Lizard, bandit, tree-sitter-language-pack come from requirements.txt.
# Ruff/eslint/jscpd are Docker-only — the analyzer wrappers return None
# for their fields when they're absent, which is fine for unit tests.

pytest
mypy --strict oss_profanity/
```

## See also

- [`DRAFT.md`](DRAFT.md) — full experiment spec, stage-by-stage
- [`PLAN.md`](PLAN.md) — implementation proposal map (IP-001 through IP-010)
- [`proposals/posts/ip-001-foundations.md`](proposals/posts/ip-001-foundations.md) — source of env-var defaults
- [`proposals/posts/ip-004-static-analyzers.md`](proposals/posts/ip-004-static-analyzers.md) — source of the analyzer module constants
