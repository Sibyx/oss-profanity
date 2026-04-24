# Deployment Runbook

IP-010. Linear operator procedure for running the 1,500-repo cohort on the
three faculty worker hosts against the faculty Mongo.

Scope: the OS + Docker Engine ≥ 24 are already installed on every host,
Docker volume storage is configured on the dedicated mount, and the 1,500
`status="pending"` cohort has already been migrated to the faculty Mongo.
Everything below assumes that starting state.

Reference files live in [`docs/deploy/`](deploy/):

- [`compose.yml`](deploy/compose.yml) — production per-host Compose
- [`.env.example`](deploy/.env.example) — per-host env template

## Topology

- **Mongo host** — native MongoDB 7, bound to the faculty private network on
  `10.150.104.106:27017`. Not managed by this runbook.
- **Worker hosts** — three × 16 vCPU / 16 GB. Each runs one Compose service
  that pulls `ghcr.io/sibyx/oss-profanity:master` and drains the `pending`
  queue via IP-007's claim-clone-analyze loop.
- **Concurrency** — 3 hosts × `WORKER_CONCURRENCY=12` = 36 concurrent repos.

The image is published by `.github/workflows/docker.yml` on every push to
`master` and every `vX.Y.Z` tag. The GHCR package is public — `docker pull`
on each worker host works unauthenticated.

## First-time setup per worker host

One-time per host; ~3 minutes each.

```bash
# On the operator's laptop — ship the two reference files to the worker host.
scp docs/deploy/compose.yml    worker-1:/opt/oss-profanity/compose.yml
scp docs/deploy/.env.example   worker-1:/opt/oss-profanity/.env

# SSH in, fill in the .env values. GITHUB_TOKEN is the one secret; MONGO_URI
# already points at the faculty Mongo IP. The rest are safe defaults.
ssh worker-1
sudo $EDITOR /opt/oss-profanity/.env

# Lock the .env down — it carries GITHUB_TOKEN. Owner-only read/write.
chmod 600 /opt/oss-profanity/.env

# Pull the image and start the worker.
cd /opt/oss-profanity
docker compose pull
docker compose up -d
docker compose logs -f --tail 50
```

Repeat for `worker-2` and `worker-3`.

Verification, within ~10 seconds of `up -d`:

```bash
# From any system with Mongo reachability.
mongosh 'mongodb://10.150.104.106:27017/profanity' --quiet --eval '
  print("claimed:", db.repos.countDocuments({status:"claimed"}));
  print("pending:", db.repos.countDocuments({status:"pending"}));
'
```

`claimed` should increment as soon as the worker starts; `pending`
decreases by the same amount.

## Monitoring the run

The operator can SSH into any host or run these from any system with
reachability to the faculty Mongo. No additional observability infra is
deployed (see IP-010 Q6 resolution) — these four one-liners are the whole
monitoring surface.

### 1. Status histogram

Expected: `pending` decreasing, `claimed` staying near 36, `done` increasing.

```bash
mongosh 'mongodb://10.150.104.106:27017/profanity' --quiet --eval '
db.repos.aggregate([{$group:{_id:"$status", n:{$sum:1}}}]).toArray()'
```

### 2. Per-worker claim distribution

Expect 36 concurrent claims spread across 3 host prefixes × ~12 procs each.
Each worker's ID is `{hostname}-{pid}-{4-hex-bytes}` per
`db.make_worker_id()` — so hostname-grouping falls out naturally.

```bash
mongosh 'mongodb://10.150.104.106:27017/profanity' --quiet --eval '
db.repos.aggregate([
  {$match:{status:"claimed"}},
  {$group:{_id:"$claimed_by", n:{$sum:1}}},
  {$sort:{_id:1}}
]).toArray()'
```

### 3. No-duplicate-processing verification

**Must return `[]`.** Any non-empty result means two workers agreed on the
same repo, which would be an IP-001 `claim_next_repo` CAS bug.

```bash
mongosh 'mongodb://10.150.104.106:27017/profanity' --quiet --eval '
db.repos.aggregate([
  {$match:{status:"claimed"}},
  {$group:{_id:"$_id", by:{$addToSet:"$claimed_by"}}},
  {$match:{"by.1":{$exists:true}}}
]).toArray()'
```

### 4. Oldest in-flight claim age

Should stay below `PER_REPO_TIMEOUT_SEC` (600 s default). If it creeps past
`STALE_CLAIM_TTL_MIN` (20 min), the stale reaper will reclaim the row on
the next worker loop iteration.

```bash
mongosh 'mongodb://10.150.104.106:27017/profanity' --quiet --eval '
const oldest = db.repos.find({status:"claimed"})
  .sort({claimed_at:1}).limit(1).toArray()[0];
if (oldest) {
  const age_s = (Date.now() - oldest.claimed_at.getTime()) / 1000;
  print(oldest.full_name + "  " + oldest.claimed_by + "  " + age_s + "s");
} else {
  print("(no claimed repos)");
}'
```

## Rollout a new image (mid-run bug fix)

```bash
# On the operator's laptop — git push the fix; GHA rebuilds `master`.
# On each worker host:
cd /opt/oss-profanity
docker compose pull              # pulls the new master tag
docker compose up -d             # recreates the container; old one exits cleanly
docker compose logs -f --tail 20
```

Apply to all three hosts in the same sitting. To verify every host is on the
same image tag:

```bash
docker compose config | grep image:
```

## Graceful shutdown

`docker compose stop` sends SIGTERM; the IP-007 loop catches it and
finishes the current repo before exiting. Any in-flight claim left by a
hard kill flips back to `pending` via `reclaim_stale()` at the next start.

```bash
cd /opt/oss-profanity
docker compose stop
```

## Post-run cleanup

Run on each host after `pending == 0 && claimed == 0` and the container
shows `Exited (0)`.

```bash
cd /opt/oss-profanity
docker compose down              # removes the container; keeps the scratch volume
docker volume prune --force      # optional: reclaim scratch space
```

## Troubleshooting

**Worker logs show `401 Unauthorized` against GitHub** — `GITHUB_TOKEN` is
unset or still the placeholder. Fix: edit `/opt/oss-profanity/.env`, then
`docker compose up -d` to recreate the container with the new env.

**Worker container keeps restarting** — the image is crashing. Tail the
logs: `docker compose logs --tail 200`. Common causes: missing
`MONGO_URI`, unreachable Mongo (private network blip), bad PAT scopes.

**`status:"claimed"` count stuck at 36 but no progress on `done`** —
workers are alive but wedged on one repo each. Run monitoring query #4;
if ages exceed `STALE_CLAIM_TTL_MIN`, the stale reaper should recover
them on the next loop iteration. If not, `docker compose restart` on the
affected host.

**Queue drains and workers exit, but `pending` is > 0** — race between
the last claim and the queue-empty check. Rerun `docker compose up -d` on
any host; idle workers immediately claim the remnant and finish.

**Non-empty result from monitoring query #3 (duplicate claim)** — escalate.
This would be a broken IP-001 CAS primitive and invalidates the run's
no-duplicate guarantee. Stop all workers (`docker compose stop` on all
three hosts) before investigating.

## Reproducibility

The image SHA that produced the final `done` rows should be captured before
tearing down, so the paper can cite a byte-identical reference. On any one
host, after the run:

```bash
docker compose config | grep image:
docker inspect --format='{{index .RepoDigests 0}}' \
  ghcr.io/sibyx/oss-profanity:master
```

For a post-hoc re-run, swap `:master` for the pinned SHA in each host's
`/opt/oss-profanity/compose.yml`:

```yaml
services:
  worker:
    image: ghcr.io/sibyx/oss-profanity:sha-abc1234
```

Then `docker compose pull && docker compose up -d`. The `pull_policy:
always` clause is a no-op after the first pull for a SHA tag.

## References

- [IP-001 Foundations](proposals/posts/ip-001-foundations.md) —
  `claim_next_repo` CAS; `make_worker_id` uniqueness
- [IP-007 Repo worker](proposals/posts/ip-007-repo-worker.md) — clean-exit
  behavior, stale-claim reaper
- [IP-009 Docker test harness](proposals/posts/ip-009-docker-test-harness.md)
  — the shared Dockerfile the GHA workflow publishes
- [IP-010 Deployment](proposals/posts/ip-010-deployment.md) — this
  runbook's design rationale, alternatives, and trade-offs
- [`docs/CONFIGURATION.md`](CONFIGURATION.md) — every env var the
  workers read
