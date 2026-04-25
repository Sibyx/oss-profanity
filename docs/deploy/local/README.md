# Local worker — MacBook Pro (M1 Max)

Single-container alternative to `docs/deploy/` for draining the cohort
locally when the faculty private network is unreachable. Runs one worker
against the host's native MongoDB on port 27017 (per project convention:
`27017` = native local, `27018` = SSH tunnel to production, `27019` =
docker compose Mongo).

## One-time setup

```bash
cd docs/deploy/local
cp .env.example .env
$EDITOR .env                # fill GITHUB_TOKEN; MONGO_URI already correct
chmod 600 .env              # GITHUB_TOKEN lives in this file
```

## Build + run

```bash
cd docs/deploy/local
docker compose build        # first time only; ~3 min on M1 Max
docker compose up           # foreground; Ctrl-C stops cleanly via SIGTERM
```

Logs stream to the terminal. The worker drains `status="pending"` until
the queue empties, then exits `(0)`. Re-run `up` to pick up any repos
that were re-added or reclaimed from stale claims.

## Tuning knobs

Everything lives in `.env`:

| Variable | Default (local) | Notes |
|---|---|---|
| `WORKER_CONCURRENCY` | `6` | 8 performance cores on M1 Max; 6 leaves headroom for OS + Mongo + browser. Bump to 8 if the laptop is otherwise idle. |
| `CLEANUP_AFTER_REPO` | `true` | Wipes the clone after each repo. Flip to `false` only to debug a single failing repo (SSD fills fast otherwise). |
| `MAX_REPO_SIZE_MB` | `1024` | Skip any repo over 1 GB. Production uses 2048; local is stricter so the fan stays quiet. |
| `SCRATCH_DIR` | `/scratch` | Named Docker volume. Do not bind-mount from the host on macOS — VirtioFS overhead on many small files is brutal for git. |
| `MONGO_URI` | `mongodb://host.docker.internal:27017/profanity` | Docker Desktop routes this to the host's native Mongo. |

## Monitoring

Same queries as `docs/DEPLOYMENT.md`, just pointed at `localhost:27017`:

```bash
# Status histogram
mongosh 'mongodb://localhost:27017/profanity' --quiet --eval '
db.repos.aggregate([{$group:{_id:"$status", n:{$sum:1}}}]).toArray()'

# Per-worker claim distribution (should show one hostname prefix)
mongosh 'mongodb://localhost:27017/profanity' --quiet --eval '
db.repos.aggregate([
  {$match:{status:"claimed"}},
  {$group:{_id:"$claimed_by", n:{$sum:1}}}
]).toArray()'

# Duplicate-claim assertion (must return [])
mongosh 'mongodb://localhost:27017/profanity' --quiet --eval '
db.repos.aggregate([
  {$match:{status:"claimed"}},
  {$group:{_id:"$_id", by:{$addToSet:"$claimed_by"}}},
  {$match:{"by.1":{$exists:true}}}
]).toArray()'
```

## Cleanup

```bash
docker compose down         # removes the container, keeps the scratch volume
docker volume rm local_scratch  # optional: reclaim the volume's disk
```

## When to prefer this over `docs/deploy/`

- Faculty private network is down / SSH tunnel is flaky.
- You need to reproduce a single-repo failure against a local Mongo copy
  with `CLEANUP_AFTER_REPO=false`.
- You're on the road and want to make forward progress.

For a 1,500-repo cohort this single laptop run takes roughly 15–20 h at
6-way concurrency (about 3× slower than the 3×12 faculty setup). Not
intended as a replacement for production runs.
