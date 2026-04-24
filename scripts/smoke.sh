#!/usr/bin/env bash
# IP-009 smoke harness — one-command end-to-end gate.
#
# Boots the full pipeline (ingest → sampling → worker → assertions) via Compose
# profiles and propagates the assertions container's exit code as the script's
# verdict. `compose down` runs on every exit path (success, failure, SIGINT).
#
# Prereqs:
#   - Docker Engine ≥ 24 with Compose v2.20+ (profile + --exit-code-from)
#   - A local MongoDB on 127.0.0.1:27017 (the smoke writes to profanity_smoke
#     on that instance via host.docker.internal:27017)
#   - ~5 GB free disk for the image + 4 hours of GHA downloads
#
# See docs/proposals/posts/ip-009-docker-test-harness.md for the full design.

set -euo pipefail

export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-oss-profanity-smoke}"

cleanup() {
  echo ""
  echo "==> smoke: cleaning up compose stack"
  docker compose --profile assertions down --volumes --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "==> smoke: project=${COMPOSE_PROJECT_NAME}"
echo "==> smoke: starting ingest → sampling → worker → assertions chain"

docker compose --profile assertions up \
  --build \
  --abort-on-container-exit \
  --exit-code-from assertions
