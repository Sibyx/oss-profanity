# IP-009: single image shared by ingest, sampling, worker, and assertions roles.
# Role is selected at compose time via `command:` overrides; default = worker.
#
# Layer order is tuned for fast rebuild: system deps → Node toolchain
# (/opt/node-tools) → Python deps (tree-sitter-language-pack is the biggest single
# layer) → app code. Editing Python files only invalidates the final two layers.

FROM python:3.14-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    NODE_VERSION=22

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
        git curl ca-certificates gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# IP-013: unified Node toolchain at /opt/node-tools/. ESM resolves
# @eslint/js and typescript-eslint from a sibling node_modules; `npm
# install -g` does not work for flat-config because ESM bare specifiers
# do not consult the global prefix. jscpd ships from the same project
# for symmetry — every JS-side CLI lives in one place. Pins live in
# dockerfiles/node-tools/package.json (eslint@10.2.1, @eslint/js@10.0.1,
# typescript-eslint@8.59.0, jscpd@4.0.9 — IP-009 Q6 lineage).
COPY dockerfiles/node-tools/ /opt/node-tools/
RUN cd /opt/node-tools && npm install --omit=dev --no-audit --no-fund \
    && npm cache clean --force \
    && ln -s /opt/node-tools/node_modules/.bin/eslint /usr/local/bin/eslint \
    && ln -s /opt/node-tools/node_modules/.bin/jscpd /usr/local/bin/jscpd

# Build-time canary (IP-013): lint-clean fixture, so any non-zero exit fails the build.
RUN eslint --no-config-lookup --config /opt/node-tools/eslint.config.mjs \
        /opt/node-tools/canary.js

# Python deps. ruff / bandit / lizard are pinned in requirements.txt so a single
# `pip install` surface tracks all three plus the rest of the runtime deps.
WORKDIR /app
COPY requirements.txt ./
RUN pip install -r requirements.txt

# App code + smoke assertions script.
COPY oss_profanity/ ./oss_profanity/
COPY dockerfiles/assertions.py ./dockerfiles/assertions.py

# Default role = worker; sampling / ingest / assertions services override via compose `command:`.
CMD ["python", "-m", "oss_profanity.repo_worker"]
