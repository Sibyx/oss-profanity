# Experiment Proposal: Profanity vs. Code Quality in OSS Commits

**For:** OpenCamp conference talk
**Author:** Jakub Dubec
**Timeline:** 2 days to conference
**Status:** Implementation-ready specification

---

## 1. Research Question

Is there a measurable correlation between **affect signals** in developer communication (profanity and emoji in commit messages and code comments) and the quality of the source code they produce?

Profanity and emoji are treated as two independent signals, not lumped together. Profanity carries a widely-shared negative valence; emoji carry a mix (🚀 vs 💀 vs 🐛). Each gets its own count, rate, and correlation against the same quality metrics, so the talk can report both dimensions separately.

**Hypothesis (null):** Neither profanity nor emoji rate in commits is correlated with code quality metrics.
**Hypothesis (alternative):** At least one of profanity rate or emoji rate correlates with code quality — in either direction. An inverse correlation ("angry devs write better code") would be just as interesting as a positive one, and the emoji dimension may reveal a different pattern than profanity.

---

## 2. Dataset & Scope

- **Source:** [GH Archive](https://www.gharchive.org/) public event stream
- **Time window:** **June 2020** (one month, lockdown peak, pre-Copilot/ChatGPT — human-generated commit messages)
- **Volume:** ~150 GB compressed JSON, 744 hourly files, ~50M events, of which ~20M are `PushEvent`s containing ~40M commits
- **Expected repo count in window:** ~500K unique repos
- **Deep-analysis cohort target:** 1,500–3,000 repos (whatever completes within the time budget)

**Exclusions:**
- Known bot authors (dependabot, renovate-bot, github-actions, etc.)
- Repos with < 20 commits in window (insufficient signal)
- Repos > 2 GB in size (vendored/monolith skew)
- Forks (dedup via `repo_id`)

---

## 3. Infrastructure

**Already provisioned on OpenStack:**

| Host | IP | Flavor | vCPU | RAM | Role |
|------|----|----|------|-----|------|
| `jd-profanity-mogo` | 10.150.104.106 | fiit.8-16-10 | 8 | 16 GB | MongoDB + Stage 1+2 (ingest) |
| `jd-profanity-worker-1` | 10.150.104.107 | fei-16-16-30 | 16 | 16 GB | Stage 4 (clone + analyze) |
| `jd-profanity-worker-2` | 10.150.104.108 | fei-16-16-30 | 16 | 16 GB | Stage 4 (clone + analyze) |
| `jd-profanity-worker-3` | 10.150.104.109 | fei-16-16-30 | 16 | 16 GB | Stage 4 (clone + analyze) |

**Total compute:** 56 vCPU, 64 GB RAM across 4 nodes.

**RAM budget per worker (16 GB on fei-16-16-30):**
- OS + buffers: 2 GB
- Available for workers: 14 GB
- Per-worker budget at 12 concurrent processes: ~1.1 GB
- **Decision: 12 concurrent analyze processes per worker** (not 16 — leaves headroom for clone spikes). Total Stage 4 parallelism = **36 concurrent repos**.

**Storage:** Worker root disks are 30 GB. Git clones land in `/scratch` (use root disk; if insufficient, attach a Cinder volume per worker). Enforce aggressive cleanup after each repo.

**Network:** All 4 hosts on `10.150.104.0/24`. Mongo binds to internal IP only. No public ingress required.

---

## 4. Architecture

### 4.1 Pipeline stages

```
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 1+2: Ingest (runs on jd-profanity-mogo)                  │
│                                                                 │
│  GH Archive .json.gz ──► parse PushEvents ──► score profanity   │
│       (4 download workers)     (6 score workers)                │
│                                   │                             │
│                                   ▼                             │
│                        MongoDB: upsert repos collection         │
│                        (atomic $inc, $addToSet)                 │
└─────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 3: Cohort selection (one-shot script, 1 min)             │
│                                                                 │
│  Auto-select ~1500 repos by stratified sampling, no manual      │
│  curation. Flip them to status="pending".                       │
└─────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 4: Deep analysis (runs on worker-1, worker-2, worker-3)  │
│                                                                 │
│  [atomic claim] ──► git clone --filter=blob:none                │
│                 ──► checkout SHA before 2020-07-01              │
│                 ──► scan source comments for profanity          │
│                 ──► run ruff / eslint / lizard                  │
│                 ──► write result + mark done                    │
│                 ──► rm -rf clone                                │
│                                                                 │
│  12 workers × 3 hosts = 36 concurrent repos                     │
└─────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 5: Aggregation (one-shot script)                         │
│  MongoDB aggregation pipelines → CSV → matplotlib plots         │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 MongoDB schema

**Single collection: `repos`.** One document per repo, everything aggregated.

```python
{
  "_id": 12345678,                       # GitHub numeric repo ID (stable)
  "full_name": "owner/repo",
  "first_seen_at": ISODate,
  
  # Stage 1+2 output (commit message analysis)
  "commit_stats": {
    "total_commits_in_window": 42,
    "unique_authors": ["alice", "bob"],
    "languages_detected": {"en": 38, "ru": 4},
    "profanity_hits": 7,
    "profanity_rate": 0.167,             # hits / total_commits
    "severity_sum": 12,
    "sample_profane_messages": [...],    # capped at 5 for talk material
    "emoji_hits": 14,                    # total emoji occurrences in commit messages
    "emoji_rate": 0.33,                  # emoji_hits / total_commits
    "emoji_top": {"🚀": 6, "🔥": 3, "✨": 2, "🐛": 2, "👀": 1},  # top N, capped
    "emoji_commits": 9                   # commits with at least one emoji
  },
  
  # Lifecycle
  "status": "seen" | "pending" | "claimed" | "done" | "failed" | "skipped",
  "claimed_by": "worker-1-pid-12345",
  "claimed_at": ISODate,
  
  # Stage 4 output (set when status=done)
  "primary_language": "Python",
  "code_analysis": {
    "loc_total": 12400,
    "files_scanned": 87,
    "comment_profanity_hits": 3,
    "identifier_profanity_hits": 0,
    "comment_emoji_hits": 5,
    "identifier_emoji_hits": 0,
    "emoji_top": {"✅": 2, "⚠️": 2, "🚧": 1},
    "ruff_issues": 156,
    "ruff_issues_per_kloc": 12.6,
    "eslint_issues": null,
    "lizard_avg_ccn": 3.8,
    "lizard_max_ccn": 47,
    "lizard_functions": 342
  },
  "failure_reason": null,
  "processing_time_sec": 87.3
}
```

One index beyond the default `_id`:
```python
db.repos.create_index([("status", 1), ("commit_stats.profanity_rate", -1)])
```

### 4.3 Module layout

```
profanity-lab/
├── docker-compose.yml         # local test harness
├── Dockerfile                 # worker image (shared by all roles)
├── requirements.txt
├── ldnoobw/                   # cloned bad-word lists, 28 languages
├── lab/
│   ├── __init__.py
│   ├── config.py              # MongoDB URI, paths, tunables
│   ├── db.py                  # Mongo client + claim_next_repo
│   ├── profanity.py           # profanity scan(), detect_language()
│   ├── emoji_scan.py          # emoji extraction + counting
│   ├── archive_ingest.py      # Stage 1+2 entrypoint
│   ├── sampling.py            # Stage 3 one-shot
│   ├── repo_worker.py         # Stage 4 entrypoint
│   ├── analyzers.py           # ruff / eslint / lizard subprocess wrappers
│   ├── analyze_results.py     # Stage 5 aggregation + plots
│   └── tests/
│       └── test_smoke.py      # end-to-end on 1 hour of GHA + 5 repos
└── scripts/
    ├── setup_mongo.sh         # provisions jd-profanity-mogo
    ├── setup_worker.sh        # provisions worker-N
    └── run_local.sh           # starts docker-compose test run
```

Target: **~700 lines of Python total.** No orchestration framework; plain `multiprocessing.Pool` on each host.

---

## 5. Detailed Stage Specifications

### 5.1 Stage 1+2: `archive_ingest.py`

Runs on `jd-profanity-mogo`.

**Input:** date range (default: 2020-06-01 to 2020-06-30).
**Output:** populated `repos` collection with `commit_stats` set on all encountered repos.

**Algorithm:**
1. Generate list of 744 hourly file URLs: `https://data.gharchive.org/2020-06-{DD}-{HH}.json.gz`
2. `multiprocessing.Pool(4)` downloads files concurrently to `/data/archive_raw/`, writing through a queue.
3. `multiprocessing.Pool(6)` reads downloaded files, for each:
    - Stream-parse line by line with `orjson`
    - Filter to `type == "PushEvent"`
    - For each commit in `payload.commits`:
        - Skip if author login matches bot regex: `(bot|dependabot|renovate|github-actions|greenkeeper)`
        - `detect_language(message)` via `langdetect`
        - `profanity.scan(message, lang)` → list of hits
        - `emoji_scan.extract(message)` → list of emoji (stripped of skin-tone / ZWJ variants)
        - Upsert into `repos` using atomic operators. `$inc` accumulates scalars; per-emoji counts go into a nested `emoji_top` map via `$inc` on dotted keys (pruned to top-N later):
          ```python
          inc = {
              "commit_stats.total_commits_in_window": 1,
              "commit_stats.profanity_hits": len(hits),
              "commit_stats.emoji_hits": len(emoji),
              f"commit_stats.languages_detected.{lang}": 1,
          }
          if emoji:
              inc["commit_stats.emoji_commits"] = 1
          for e in set(emoji):
              inc[f"commit_stats.emoji_top.{e}"] = emoji.count(e)

          db.repos.update_one(
            {"_id": repo_id},
            {
              "$setOnInsert": {
                "full_name": repo_name,
                "first_seen_at": now,
                "status": "seen"
              },
              "$inc": inc,
              "$addToSet": {
                "commit_stats.unique_authors": author_login
              }
            },
            upsert=True
          )
          if hits:
            db.repos.update_one(
              {"_id": repo_id, "commit_stats.sample_profane_messages.4": {"$exists": False}},
              {"$push": {"commit_stats.sample_profane_messages": message[:200]}}
            )
          ```
4. After all files processed, run one-shot pass per doc to compute:
   - `profanity_rate = profanity_hits / total_commits_in_window`
   - `emoji_rate = emoji_hits / total_commits_in_window`
   - Prune `emoji_top` to the 20 most frequent (keeps per-doc size bounded when heavy emoji users get hundreds of distinct glyphs).

**Resilience:** each hourly file tracked in `ingest_progress` collection; reruns skip completed files. Downloads are idempotent (HTTP GET with resume).

**Expected runtime:** 5–7 hours.

### 5.2 Stage 3: `sampling.py`

Runs once on `jd-profanity-mogo`, interactively.

**Zero manual curation.** Pure automatic stratified sampling:

```python
# Mark all seen repos as skipped by default
db.repos.update_many({"status": "seen"}, {"$set": {"status": "skipped"}})

# Cohort A: "profane" — any profanity, at least 20 commits
profane = list(db.repos.find({
    "status": "skipped",
    "commit_stats.total_commits_in_window": {"$gte": 20},
    "commit_stats.profanity_hits": {"$gte": 1},
}).limit(750))

# Cohort B: "clean" — zero profanity, matched by commit-count distribution
clean = list(db.repos.find({
    "status": "skipped",
    "commit_stats.total_commits_in_window": {"$gte": 20},
    "commit_stats.profanity_hits": 0,
}).limit(750))

# Flip cohort to pending
ids = [r["_id"] for r in profane + clean]
db.repos.update_many({"_id": {"$in": ids}}, {"$set": {"status": "pending"}})

print(f"Ready: {len(profane)} profane + {len(clean)} clean = {len(ids)} pending")
```

### 5.3 Stage 4: `repo_worker.py`

Runs on each of worker-1, 2, 3. 12 processes per host → 36 concurrent repos total.

**Main loop per worker process:**

```python
WORKER_ID = f"{socket.gethostname()}-{os.getpid()}"
SCRATCH = Path("/scratch")

while True:
    repo = db.repos.find_one_and_update(
        {"status": "pending"},
        {"$set": {"status": "claimed",
                  "claimed_by": WORKER_ID,
                  "claimed_at": datetime.utcnow()}},
        sort=[("commit_stats.profanity_rate", -1)]  # interesting ones first
    )
    if not repo:
        # Check for stale claims (>20 min = worker died)
        reclaim_stale()
        if no_more_work(): break
        time.sleep(10); continue

    repo_dir = SCRATCH / str(repo["_id"])
    t0 = time.time()
    try:
        with timeout(600):  # 10 min hard cap per repo
            clone_partial(repo["full_name"], repo_dir)
            sha = resolve_sha_before(repo_dir, "2020-07-01")
            if not sha:
                raise SkipRepo("no commits in window")
            checkout(repo_dir, sha)
            primary_lang = detect_primary_language(repo_dir)
            results = analyzers.run_all(repo_dir, primary_lang)
            db.repos.update_one(
                {"_id": repo["_id"]},
                {"$set": {
                    "status": "done",
                    "primary_language": primary_lang,
                    "code_analysis": results,
                    "processing_time_sec": time.time() - t0
                }}
            )
    except TimeoutError:
        mark_failed(repo["_id"], "timeout")
    except SkipRepo as e:
        mark_failed(repo["_id"], f"skip: {e}")
    except Exception as e:
        mark_failed(repo["_id"], f"{type(e).__name__}: {e}")
    finally:
        shutil.rmtree(repo_dir, ignore_errors=True)
```

**Clone strategy:**
```bash
git clone --filter=blob:none --no-checkout https://github.com/{full_name} {repo_dir}
git -C {repo_dir} rev-list -1 --before="2020-07-01 00:00:00" HEAD
git -C {repo_dir} checkout {sha}
```

All git calls wrapped with `subprocess.run(..., timeout=300)`. Size check before clone via GitHub API; skip repos reported >2 GB.

### 5.4 `analyzers.py`

Language-dispatched static analysis. Builds nothing (no `npm install`, no `cargo build`).

```python
def run_all(repo_dir, primary_lang):
    result = {
        "loc_total": 0,
        "files_scanned": 0,
        "comment_profanity_hits": 0,
        "identifier_profanity_hits": 0,
        "comment_emoji_hits": 0,
        "identifier_emoji_hits": 0,
        "emoji_top": {},              # Counter-like: {emoji: count}
        "ruff_issues": None,
        "eslint_issues": None,
        "lizard_avg_ccn": None,
        "lizard_max_ccn": None,
        "lizard_functions": None,
    }

    # Source scan — polyglot, simple regex over comments + identifiers.
    # Returns profanity counts, emoji counts, and an emoji top-N map.
    scan_results = scan_source_tree(repo_dir)
    result.update(scan_results)

    # Lizard — always run, covers ~20 languages, no config needed
    lizard_out = subprocess.run(
        ["lizard", "-X", str(repo_dir)],
        capture_output=True, timeout=120
    )
    result.update(parse_lizard_xml(lizard_out.stdout))

    # Language-specific linter
    if primary_lang == "Python":
        ruff_out = subprocess.run(
            ["ruff", "check", "--output-format=json", str(repo_dir)],
            capture_output=True, timeout=120
        )
        result["ruff_issues"] = len(json.loads(ruff_out.stdout or "[]"))
    elif primary_lang in ("JavaScript", "TypeScript"):
        eslint_out = subprocess.run(
            ["eslint", "--format=json", "--no-eslintrc",
             "--config", "/opt/baseline-eslint.json", str(repo_dir)],
            capture_output=True, timeout=180
        )
        result["eslint_issues"] = count_eslint_issues(eslint_out.stdout)

    # Normalize per KLOC
    if result["loc_total"] > 0:
        kloc = result["loc_total"] / 1000
        if result["ruff_issues"] is not None:
            result["ruff_issues_per_kloc"] = result["ruff_issues"] / kloc
        if result["eslint_issues"] is not None:
            result["eslint_issues_per_kloc"] = result["eslint_issues"] / kloc

    return result
```

**Source scanning** — simple and fast:
- Walk files, skip `node_modules/`, `vendor/`, `.git/`, `dist/`, `build/`, minified JS (name contains `.min.`), files > 1 MB
- Extract comments with regex per file extension (`//`, `#`, `/* */`)
- Extract identifiers with regex (camelCase / snake_case word splitter)
- Feed each to `profanity.scan()` → `comment_profanity_hits`, `identifier_profanity_hits`
- Feed each to `emoji_scan.extract()` → `comment_emoji_hits`, `identifier_emoji_hits`, accumulate per-glyph counts into `emoji_top` (pruned to top 20 before return)

### 5.5 `profanity.py`

```python
from better_profanity import profanity as bp
from langdetect import detect, DetectorFactory
from pathlib import Path
import re

DetectorFactory.seed = 0  # deterministic

_LDNOOBW_DIR = Path(__file__).parent.parent / "ldnoobw"
_LANG_SETS = {}

def _load():
    bp.load_censor_words()  # English defaults
    for lang_file in _LDNOOBW_DIR.glob("*"):
        if lang_file.is_file() and len(lang_file.name) <= 3:
            words = {w.strip().lower() for w in lang_file.read_text().splitlines()
                     if w.strip() and not w.startswith("#")}
            _LANG_SETS[lang_file.name] = words

_load()

_TOKEN_RE = re.compile(r"\b[\w']+\b", re.UNICODE)

def detect_language(text: str) -> str:
    try:
        return detect(text) if len(text) >= 10 else "en"
    except Exception:
        return "en"

def scan(text: str, lang: str = "en") -> list[str]:
    if not text:
        return []
    text_lc = text.lower()
    tokens = set(_TOKEN_RE.findall(text_lc))
    hits = []
    # English via better-profanity (handles obfuscation)
    if bp.contains_profanity(text):
        hits.extend(t for t in tokens if bp.contains_profanity(t))
    # Non-English via LDNOOBW
    if lang in _LANG_SETS:
        hits.extend(tokens & _LANG_SETS[lang])
    return sorted(set(hits))
```

### 5.6 `emoji_scan.py`

Emoji are a second affect signal, tracked independently from profanity. Use the [`emoji`](https://pypi.org/project/emoji/) package for extraction (Unicode-correct, handles ZWJ sequences like 👨‍💻 and skin-tone modifiers) rather than a hand-rolled regex.

```python
import emoji

def extract(text: str) -> list[str]:
    """Return the emoji (in order of appearance) found in text.

    Skin-tone and variation-selector-16 are stripped so that 👍 and 👍🏽 collapse
    to the same base glyph for counting, but ZWJ-joined compounds (👨‍💻) are kept
    as a single unit.
    """
    if not text:
        return []
    return [d["emoji"] for d in emoji.emoji_list(text)]

def count(text: str) -> int:
    return emoji.emoji_count(text)
```

Notes:
- Shortcodes like `:rocket:` in commit messages are **not** expanded — we only count rendered Unicode emoji. Shortcode expansion is a platform-rendering artifact, not developer intent.
- Identifier scanning: emoji in Python / JS identifiers are rare but valid (PEP 3131, ECMAScript); counting them is cheap, and if the result is consistently zero we can drop it from the schema later.

---

## 6. Local Test Harness (before touching OpenStack)

**Goal:** validate the whole pipeline end-to-end on one local machine before deploying.

### `docker-compose.yml`

```yaml
services:
  mongo:
    image: mongo:7
    ports: ["27017:27017"]
    volumes: [mongo_data:/data/db]

  ingest:
    build: .
    depends_on: [mongo]
    environment:
      MONGO_URI: mongodb://mongo:27017/profanity
      GHA_START: "2020-06-01-00"
      GHA_END:   "2020-06-01-02"   # just 2 hours for smoke test
    command: python -m lab.archive_ingest

  worker:
    build: .
    depends_on: [mongo]
    deploy:
      replicas: 2
    environment:
      MONGO_URI: mongodb://mongo:27017/profanity
      WORKER_CONCURRENCY: 2
    volumes: [scratch:/scratch]
    command: python -m lab.repo_worker

volumes:
  mongo_data:
  scratch:
```

### Smoke test script (`tests/test_smoke.py`)

Runs the full pipeline against 2 hours of GH Archive and 5 repos, asserts:
- At least 100 repos ingested
- At least 1 repo with `profanity_hits > 0` found
- After sampling + running workers, at least 3 repos reach `status=done`
- `code_analysis.loc_total > 0` on the done repos

**Decision gate:** only deploy to OpenStack after `docker-compose up` runs this test green locally.

---

## 7. Deployment (keep it boring)

One bash script per role, no Ansible, no Terraform.

### `scripts/setup_mongo.sh`
```bash
#!/bin/bash
set -euo pipefail
# Run on jd-profanity-mogo (10.150.104.106)
sudo apt-get update
sudo apt-get install -y python3.11 python3-pip git docker.io
# Mongo in Docker, binds to internal IP only
docker run -d --name mongo \
  --restart=unless-stopped \
  -p 10.150.104.106:27017:27017 \
  -v /var/lib/mongo:/data/db \
  mongo:7
# Clone repo, install deps
git clone https://github.com/<you>/profanity-lab /opt/lab
cd /opt/lab && pip install -r requirements.txt
```

### `scripts/setup_worker.sh`
```bash
#!/bin/bash
set -euo pipefail
# Run on each worker
sudo apt-get update
sudo apt-get install -y python3.11 python3-pip git nodejs npm
pip install -r /opt/lab/requirements.txt
npm install -g eslint
sudo mkdir -p /scratch && sudo chmod 777 /scratch
# Configuration comes via env var MONGO_URI=mongodb://10.150.104.106:27017/profanity
```

Deploy = `scp` the repo + `ssh <host> bash scripts/setup_*.sh`. That's it.

---

## 8. Execution Plan

| When | Duration | Action | Host(s) |
|------|----------|--------|---------|
| Day 1, 08:00 | 1 h | Write modules, run docker-compose smoke test | laptop |
| Day 1, 09:00 | 1 h | Fix whatever broke in smoke test | laptop |
| Day 1, 10:00 | 30 min | Provision all 4 VMs via setup scripts | OpenStack |
| Day 1, 10:30 | 30 min | Run smoke test against real Mongo (2 hours of GHA) | mongo + 1 worker |
| Day 1, 11:00 | 6 h | Kick off full ingest for 2020-06 | mongo |
| Day 1, 17:00 | 10 min | Run `sampling.py`, verify cohort size | mongo |
| Day 1, 17:10 | overnight | Start `repo_worker.py` on all 3 workers | workers |
| Day 2, 09:00 | checkpoint | Review progress; expect ~600–1000 repos done | monitor |
| Day 2, 15:00 | hard stop | Stop workers regardless of completion | monitor |
| Day 2, 15:00 | 2 h | Run `analyze_results.py`, generate plots | mongo |
| Day 2, 17:00 | evening | Build slides | laptop |

**Partial-data guarantee:** even if Stage 4 finishes only 300 repos, the talk still works. Stage 1+2 alone (complete profanity statistics across all of GitHub for June 2020) is a publishable result.

---

## 9. Output — What the Talk Gets

Deliverables produced by `analyze_results.py`:

1. **`commit_profanity_distribution.csv/png`** — histogram of profanity rate across all ~500K repos. How swear-y is OSS on average?
2. **`commit_emoji_distribution.csv/png`** — histogram of emoji rate across all ~500K repos. How emoji-heavy is OSS on average?
3. **`language_breakdown.csv/png`** — which human languages show the most profanity and the most emoji per commit (two overlaid bars per language).
4. **`profanity_vs_quality.csv/png`** — scatter of `profanity_rate` vs `ruff_issues_per_kloc` + vs `lizard_avg_ccn`, with Spearman correlation + 95% CI.
5. **`emoji_vs_quality.csv/png`** — same shape as above but for `emoji_rate` vs the quality metrics.
6. **`cohort_comparison.csv`** — Mann-Whitney U between (a) profane vs clean cohorts and (b) high-emoji vs low-emoji cohorts on each quality metric.
7. **`top_emoji.csv/png`** — global top 50 emoji across commit messages and across source comments, side-by-side (expect very different distributions — `:rocket:` dominates commits, `⚠️` / `✅` likely dominate comments).
8. **`top_offenders.md`** — table of the 10 most profane commit messages found (redacted/asterisked), as talk material.
9. **`sample_repos.md`** — a handful of case studies across the full 2×2×2 (high/low profanity × high/low emoji × high/low quality).

---

## 10. Known Limitations (own them in the talk)

- **Profanity detection is noisy.** False positives from Scunthorpe-class matches, false negatives from non-dictionary slang. Accept ~5% error rate.
- **Emoji semantics are ambiguous.** 🚀 in a commit message often marks a release; 🐛 marks a bug fix; 💩 is sarcasm. We only count occurrence, not sentiment, so the "emoji rate" is a usage signal, not an affect signal.
- **No build-based analysis.** Static only — misses many real bugs that only appear in type-checked / compiled analysis.
- **Correlation, not causation.** Obvious but worth stating loudly.
- **Language bias.** LDNOOBW lists vary in quality across languages; English is richer than Slovak. (Emoji are Unicode-universal, so this bias is profanity-only.)
- **Sample bias.** Stratified sampling for balanced cohorts means results don't represent "average GitHub" — they represent the contrast between two ends of the profanity distribution. (Emoji cohorts are sliced post-hoc from the same ingest data, not separately sampled.)

---

## 11. Out of Scope

- Manual curation of repos (explicitly excluded)
- Analysis outside 2020-06
- Languages beyond whatever LDNOOBW + `better-profanity` cover
- Build-based static analysis (no `cargo`, `npm install`, etc.)
- Commit-level storage (aggregate only)
- Identifying individual developers (repo-level only; respect privacy)

---

## 12. Agent Implementation Order

Suggested order for implementing agents to pick up the work:

1. `lab/config.py` + `lab/db.py` + `lab/profanity.py` + `lab/emoji_scan.py` — foundations
2. `lab/analyzers.py` — can be unit-tested in isolation
3. `lab/archive_ingest.py`
4. `lab/repo_worker.py` + `lab/sampling.py`
5. `docker-compose.yml` + `Dockerfile` + `tests/test_smoke.py` — gate before deploy
6. `scripts/setup_mongo.sh` + `scripts/setup_worker.sh`
7. `lab/analyze_results.py` — write last, after we have real data shape

Each module is independent enough to be built and tested in parallel once `config.py`/`db.py`/`profanity.py`/`emoji_scan.py` exist.
