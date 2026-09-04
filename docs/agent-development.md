# Agent Development Guide

Welcome to the Siftly repository. This guide covers how coding agents (like Jules) should initialize the project and verify their changes.

## Initial Setup

Before working on the codebase, Jules must run the unified initialization script:

```bash
CI=true ./scripts/setup-agent.sh
```

This script:
1. Resolves absolute paths defensively (especially important on Windows Git Bash setups to avoid Prisma path ambiguity).
2. Sets up a disposable SQLite database at `prisma/agent-ci-test.db`.
3. Does **not** read your existing `dev.db`, `CLOUDFLARE_TUNNEL_TOKEN`, or API keys from `.env`.
4. Performs an exact dependency installation (`npm ci`), generates the Prisma client, and applies migrations.

### Important Note on Windows Verification
If you are developing or executing verification on Windows, note that Git Bash translates `/c/...` paths differently from how Node and Prisma expect them (`C:/...`). The setup script contains a cross-platform normalizer so that Prisma continues to work seamlessly on all environments.

## Automated Checks (CI)

Our GitHub Action runs `scripts/setup-agent.sh` followed by:

1. Setup self-tests (`node --test __tests__/setup-agent.test.js`)
2. Linting (`npm run lint`)
3. Typechecking (`npx --no-install tsc --noEmit`)
4. Production build test (`npm run build`)
5. Application tests (`npm run test` using Vitest)

### Credentials and Tests
**No credentials are required for unit tests.** Do not mock external auth provider credentials inside tests. The AI services (Anthropic, OpenAI) should only be tested via narrow unit tests that mock the remote network boundaries.
