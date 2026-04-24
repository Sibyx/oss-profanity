# IP-009: single image shared by ingest, sampling, worker, and assertions roles.
# Role is selected at compose time via `command:` overrides; default = worker.
#
# Layer order is tuned for fast rebuild: system deps → Node toolchain → ESLint
# config → Python deps (tree-sitter-language-pack is the biggest single layer) →
# app code. Editing Python files only invalidates the final two layers.

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

# Node toolchain — exact-pinned for cohort comparability (IP-009 Q6, verified 2026-04-24).
# Bump only on CVE or intentional rule-set refresh; see IP-009 for the version-verification
# source pages.
RUN npm install -g --omit=dev \
        eslint@10.2.1 \
        @eslint/js@10.0.1 \
        typescript-eslint@8.59.0 \
        jscpd@4.0.9 \
    && npm cache clean --force

# Baseline ESLint flat config (committed in the repo — IP-009 Q8).
COPY dockerfiles/eslint.config.mjs /opt/baseline-eslint.config.mjs

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
