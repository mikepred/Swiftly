/* eslint-disable @typescript-eslint/no-require-imports */
const { test, describe } = require('node:test');
const assert = require('node:assert');
const { execFileSync } = require('node:child_process');
const path = require('node:path');
const fs = require('node:fs');
const os = require('node:os');

describe('Agent Setup Script', () => {
  test('executes npm ci and prisma commands deterministically', () => {
    // Create a temporary directory that will be cleaned up
    const testDir = fs.mkdtempSync(path.join(os.tmpdir(), 'agent-setup-test-'));

    try {
      // Create mock dependencies in our fake PATH root
      const fakeNpm = path.join(testDir, 'npm');
      fs.writeFileSync(fakeNpm, '#!/bin/bash\necho "MOCK NPM: $@" >> ' + path.join(process.cwd(), 'mock.log') + '\npwd >> ' + path.join(process.cwd(), 'mock.log') + '\n');
      fs.chmodSync(fakeNpm, 0o755);

      const fakeNpx = path.join(testDir, 'npx');
      fs.writeFileSync(fakeNpx, '#!/bin/bash\necho "MOCK NPX: $@" >> ' + path.join(process.cwd(), 'mock.log') + '\n');
      fs.chmodSync(fakeNpx, 0o755);

      const setupScript = path.join(process.cwd(), 'scripts', 'setup-agent.sh');
      let output = '';
      try {
        // Execute the script with the mocked path injected using explicit bash invocation.
        output = execFileSync('bash', [setupScript], {
          cwd: testDir,
          encoding: 'utf8',
          env: { ...process.env, PATH: `${testDir}:${process.env.PATH}` }
        });
      } catch (err) {
        assert.fail(`Setup script failed: ${err.message}\n${err.stdout}\n${err.stderr}`);
      }

      const logPath = path.join(process.cwd(), 'mock.log');
      assert.ok(fs.existsSync(logPath), 'mock.log should exist at repo root');
      const log = fs.readFileSync(logPath, 'utf8');

      assert.match(log, /MOCK NPM: ci/, 'Should run npm ci');
      assert.match(log, /MOCK NPX: --no-install prisma generate/, 'Should run prisma generate');
      assert.match(log, /MOCK NPX: --no-install prisma migrate deploy/, 'Should run prisma migrate deploy');
      assert.match(log, new RegExp(process.cwd()), 'Should run in repo root');

      // Must contain DATABASE_URL setting in the output
      assert.match(output, /DATABASE_URL: file:/, 'Should output DATABASE_URL');
      assert.doesNotMatch(output, /dev\.db/, 'Should not use dev.db');

      // The path should be normalized to use forward slashes and not start with MSYS /c/ style paths on windows
      const dbUrlMatch = output.match(/DATABASE_URL: file:(.+)/);
      assert.ok(dbUrlMatch, 'DATABASE_URL value must be parseable');
      assert.doesNotMatch(dbUrlMatch[1], /\\/, 'Should not contain backslashes');

      // Clean up log in repo root
      fs.unlinkSync(logPath);

    } finally {
      fs.rmSync(testDir, { recursive: true, force: true });
    }
  });
});
