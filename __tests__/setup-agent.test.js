/* eslint-disable @typescript-eslint/no-require-imports */
const { test, describe } = require('node:test');
const assert = require('node:assert');
const { execSync } = require('node:child_process');
const path = require('node:path');
const fs = require('node:fs');

describe('Agent Setup Script', () => {
  test('executes npm ci and prisma commands deterministically', () => {
    const testDir = path.join(process.cwd(), '.tmp-setup-test');
    if (fs.existsSync(testDir)) fs.rmSync(testDir, { recursive: true });
    fs.mkdirSync(testDir);

    // Create mock dependencies in our fake PATH root
    const fakeNpm = path.join(testDir, 'npm');
    fs.writeFileSync(fakeNpm, '#!/bin/bash\necho "MOCK NPM: $@" >> ' + path.join(testDir, 'mock.log') + '\n');
    fs.chmodSync(fakeNpm, 0o755);

    const fakeNpx = path.join(testDir, 'npx');
    fs.writeFileSync(fakeNpx, '#!/bin/bash\necho "MOCK NPX: $@" >> ' + path.join(testDir, 'mock.log') + '\n');
    fs.chmodSync(fakeNpx, 0o755);

    const setupScript = path.join(process.cwd(), 'scripts', 'setup-agent.sh');
    let output = '';
    try {
      // Execute the script with the mocked path injected.
      output = execSync(`PATH="${testDir}:$PATH" "${setupScript}"`, {
        cwd: testDir,
        encoding: 'utf8',
        env: { ...process.env, PATH: `${testDir}:${process.env.PATH}` }
      });
    } catch (err) {
      assert.fail(`Setup script failed: ${err.message}\n${err.stdout}\n${err.stderr}`);
    }

    const logPath = path.join(testDir, 'mock.log');
    assert.ok(fs.existsSync(logPath), 'mock.log should exist');
    const log = fs.readFileSync(logPath, 'utf8');

    assert.match(log, /MOCK NPM: ci/, 'Should run npm ci');
    assert.match(log, /MOCK NPX: --no-install prisma generate/, 'Should run prisma generate');
    assert.match(log, /MOCK NPX: --no-install prisma migrate deploy/, 'Should run prisma migrate deploy');

    // Must contain DATABASE_URL setting in the output
    assert.match(output, /DATABASE_URL: file:/, 'Should output DATABASE_URL');
    assert.doesNotMatch(output, /dev\.db/, 'Should not use dev.db');

    // The path should be normalized to use forward slashes and not start with MSYS /c/ style paths on windows (though we test this in node env so it will be posix or standard win)
    const dbUrlMatch = output.match(/DATABASE_URL: file:(.+)/);
    assert.ok(dbUrlMatch, 'DATABASE_URL value must be parseable');
    assert.doesNotMatch(dbUrlMatch[1], /\\/, 'Should not contain backslashes');

    // Clean up
    fs.rmSync(testDir, { recursive: true });
  });
});
