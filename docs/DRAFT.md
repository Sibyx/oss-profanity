## Profanity libraries (no custom database)

These are the maintained Python options worth using:

- **`better-profanity`** — English, fast, simple API, handles obfuscation (f*ck, f.u.c.k). Good default.
- **`profanity-check`** — English, ML-based (scikit-learn), catches context better than wordlists. Heavier but smarter.
- **`alt-profanity-check`** — maintained fork of the above, actively updated.
- **`profanityfilter`** — supports English + some other languages via custom wordlists.

For **multilingual coverage without a DB**, the pragmatic path is:
- `better-profanity` for English
- **LDNOOBW list** (github.com/LDNOOBW/List-of-Dirty-Naughty-Obscene-and-Otherwise-Bad-Words) — covers ~28 languages as plain text files, just download and load into a set. This is the de facto standard list; most "multilingual profanity" libraries wrap it anyway.

So your profanity detection becomes a **~30-line module**:

```python
from better_profanity import profanity
from pathlib import Path

# Load LDNOOBW lists for non-English languages you care about
LANG_WORDS = {}
for lang in ["sk", "cs", "de", "ru", "es", "fr", "it"]:
    path = Path(f"ldnoobw/{lang}")
    if path.exists():
        LANG_WORDS[lang] = set(path.read_text().split())

def scan(text: str, detected_lang: str = "en") -> list[str]:
    hits = []
    words = set(text.lower().split())
    # English via better-profanity (smarter than wordlist)
    if profanity.contains_profanity(text):
        hits.extend(w for w in words if profanity.contains_profanity(w))
    # Other languages via LDNOOBW
    if detected_lang in LANG_WORDS:
        hits.extend(words & LANG_WORDS[detected_lang])
    return list(set(hits))
```

That's it. No bad_words Mongo collection needed.

## Simplified architecture

Since you want a **simple lab**, let me cut the fat:

**Drop:**
- `bad_words` Mongo collection → replaced by in-memory sets loaded from LDNOOBW at worker startup
- `commits` collection → aggregate stats directly into `repos` during ingest
- `pipeline_log` collection → just use Python's `logging` to stdout/file
- Separate orchestrator instance → run Stage 1+2 on the Mongo instance itself

**Keep:**
- `repos` collection (the one that matters)
- Two worker instances for Stage 4
- Mongo instance (small)

### Revised instance layout

```
┌──────────────────────────────────┐
│  mongo-instance                  │
│  8 VCPU / 16 GB / 500 GB         │
│  - MongoDB                       │
│  - Runs Stage 1+2 (ingest)       │
│  - Holds GH Archive downloads    │
└──────────────────────────────────┘
             ▲
             │ pymongo (internal network)
             │
┌────────────┴───────────────────────────────┐
│  worker-1: 32 VCPU / 48 GB / 1TB volume    │
│  worker-2: 32 VCPU / 48 GB / 1TB volume    │
│  - Stage 4: clone + scan + lint            │
└────────────────────────────────────────────┘
```

Total: 72 VCPU, 112 GB RAM, 2.5 TB. Fits your quota.

## Core modules (seven files, nothing more)

```
lab/
├── profanity.py          # ~40 lines — wrapper around better-profanity + LDNOOBW
├── archive_ingest.py     # ~150 lines — Stage 1+2: download, parse, upsert
├── repo_worker.py        # ~200 lines — Stage 4: claim, clone, analyze, save
├── analyzers.py          # ~100 lines — calls ruff/eslint/lizard, parses output
├── db.py                 # ~50 lines — Mongo connection + helpers
├── sampling.py           # ~30 lines — run once to pick cohort
└── analyze_results.py    # ~80 lines — final aggregation queries + CSV export
```

Under ~700 lines of Python total. That's the "simple lab" bar.

### What each module does

**`profanity.py`** — loads LDNOOBW wordlists at import time, exposes `scan(text, lang) -> list[str]`. Also exposes `detect_language(text) -> str` using `fasttext` or `langdetect` (langdetect is pure-Python and simpler; fasttext is faster but needs a model download — for simplicity, use **langdetect**).

**`archive_ingest.py`** — one script, runs on the Mongo instance:
```
for each hour in 2020-06:
    download gharchive file
    stream-parse JSON lines
    for each PushEvent:
        for each commit:
            detect language, scan profanity
            upsert into repos collection using $inc
```
Use `multiprocessing.Pool(16)` over the 744 hourly files. Each file is independent.

**`db.py`** — just two functions: `get_db()` and `claim_next_repo(worker_id)`.

**`repo_worker.py`** — the main loop on worker instances:
```python
while True:
    repo = claim_next_repo(worker_id)
    if not repo: break
    try:
        path = clone_at_sha(repo)
        primary_lang = detect_primary_language(path)
        results = analyze(path, primary_lang)
        mark_done(repo["_id"], results)
    except Exception as e:
        mark_failed(repo["_id"], str(e))
    finally:
        shutil.rmtree(path, ignore_errors=True)
```
Launch with `multiprocessing.Pool(32)` per instance.

**`analyzers.py`** — per-language subprocess calls:
- Python repo → `ruff check --output-format=json` + `lizard -X`
- JS/TS repo → `eslint --format=json` (with a simple default config) + `lizard -X`
- Other → `lizard -X` only
- Also: grep comments for profanity using the same `scan()` from `profanity.py`

**`sampling.py`** — you run this **once** between Stage 2 and Stage 4, interactively:
```python
# Mark everything as skipped first
db.repos.update_many({}, {"$set": {"status": "skipped"}})

# Flip the chosen cohort to pending
# e.g., 1000 profane + 1000 clean, min 20 commits
for repo in pick_cohort():
    db.repos.update_one({"_id": repo["_id"]}, {"$set": {"status": "pending"}})
```

**`analyze_results.py`** — run at the end, produces your plots/CSV.

## Simplified workflow

```
Day 1 morning (3h)
├── Provision 3 instances
├── Install: Python 3.11, mongo, git, ruff, eslint, lizard,
│   better-profanity, langdetect, pymongo, pygithub
├── Download LDNOOBW repo
└── Smoke test: ingest 1 hour of GHA, analyze 5 repos

Day 1 afternoon (4-6h)
└── Run archive_ingest.py for 2020-06

Day 1 evening (30 min)
└── Run sampling.py interactively, pick ~2000 repos

Day 1 night → Day 2 afternoon (~12-18h)
└── Start repo_worker.py on both worker instances, let it run

Day 2 evening (3h)
├── Run analyze_results.py
├── Make plots
└── Slides
```

## One scope decision worth making now

**Commit-level profanity counting: simple vs. rigorous.**

The simple version: count matching words in commit messages, increment `repos.profanity_hits`. Works, but will have false positives ("class" matching nothing, but "Scunthorpe problem" is real — "assume", "passage" won't match wordlists, but some Slavic roots look like English swears, etc).

The rigorous version: tokenize properly, check word boundaries, handle leetspeak, exclude code-like tokens (camelCase, snake_case).

**For 2 days, go simple.** Use the libraries as-is, accept ~5% false-positive rate, mention it as a limitation in your talk. Don't build a custom tokenizer.

## The "good enough data" checkpoint

The critical property of this design: **after Stage 2 finishes (end of Day 1), you already have a publishable result**: profanity statistics across all of GitHub for June 2020. Even if Stage 4 only finishes 300 repos, your talk can be:

1. *"Here's what profanity in commit messages looks like across GitHub for one month"* — based on the complete `repos` collection (~500k repos)
2. *"Here's the correlation with code quality for a sample we deep-analyzed"* — based on whatever Stage 4 finished

That's already a complete OpenCamp talk.

## Ready to build?

I'd suggest starting with `profanity.py` + `archive_ingest.py` — getting Stage 1+2 running today buys you a safety margin. Want me to write those two modules now so you can kick off ingest while we work on the rest?