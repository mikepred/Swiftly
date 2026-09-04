#!/bin/bash
set -euo pipefail

# Ensure a unique absolute DB path to avoid Prisma's relative path ambiguity
# We store it in a disposable location and expose it for validation
# Normalize REPO_ROOT for cross-platform compatibility (e.g. Windows Git Bash /c/ vs C:/)
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export REPO_ROOT
REPO_ROOT=$(node -e "console.log(require('path').resolve(process.env.REPO_ROOT).replace(/\\\\/g, '/'))")

export DATABASE_URL="file:${REPO_ROOT}/prisma/agent-ci-test.db"

echo "==> Configured disposable DATABASE_URL: $DATABASE_URL"

# We must CD so it works from any cwd
cd "$(dirname "${BASH_SOURCE[0]}")/.."

echo "==> Installing dependencies (npm ci)..."
npm ci

echo "==> Generating Prisma client..."
npx --no-install prisma generate

echo "==> Deploying Prisma migrations..."
npx --no-install prisma migrate deploy

echo "==> Agent setup complete."
