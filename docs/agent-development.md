# Agent Development Guide

Welcome to the Siftly repository. This guide covers how coding agents (like Jules) should initialize the project and verify their changes.

## Initial Setup

Before working on the codebase, Jules must run the unified initialization script:

```bash
export DATABASE_URL="file:$(pwd)/prisma/agent-ci-test.db"
CI=true ./scripts/setup-agent.sh
```

This script:
1. Resolves absolute paths defensively (especially important on Windows Git Bash setups to avoid Prisma path ambiguity).
2. Sets up a disposable SQLite database at `prisma/agent-ci-test.db`.
3. Overrides the database connection string via `DATABASE_URL` for the setup session (note: a child script export does not persist into your parent shell, so you must explicitly export the variable as shown above before doing any local dev tasks). Next.js may load `.env` in non-clean checkouts, so use the export to ensure the disposable DB is strictly used.
4. Performs an exact dependency installation (`npm ci`), generates the Prisma client, and applies migrations.

### Important Note on Windows Verification
If you are developing or executing verification on Windows, note that Git Bash translates `/c/...` paths differently from how Node and Prisma expect them (`C:/...`). The setup script contains a cross-platform normalizer so that Prisma continues to work seamlessly on all environments.

## Automated Checks (CI)

Our GitHub Action runs `scripts/setup-agent.sh` followed by:

1. Setup self-tests (`node --test scripts/tests/setup-agent.check.cjs`)
2. Application tests (`npm run test` using Vitest)
3. Linting (`npm run lint`)
4. Typechecking (`npx --no-install tsc --noEmit`)
5. Production build test (`npm run build`)

### Credentials and Tests
**No credentials are required for unit tests.** Fake credential placeholders in mocked unit tests are fine (existing tests use them). The AI services (Anthropic, OpenAI) should only be tested via narrow unit tests that mock the remote network boundaries.
