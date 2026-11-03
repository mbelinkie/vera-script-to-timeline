import test from 'node:test';
import assert from 'node:assert/strict';
import { chmodSync, existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, statSync, symlinkSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { hostPreflight } from './deepseek-host-preflight.mjs';

const contract = (adapterSha256, updates = {}) => ({
  contract: 'VERA_DEEPSEEK_HOST_PREFLIGHT_V1',
  ready: true,
  adapterSha256,
  defaultMode: 'disabled',
  isolation: 'seatbelt',
  accounting: 'shared-lifetime-ledger',
  ...updates
});
const resultFor = (adapterSha256, updates) => ({
  status: 0,
  signal: null,
  stdout: JSON.stringify(contract(adapterSha256, updates)) + '\n',
  stderr: ''
});

function fixture() {
  const root = mkdtempSync(join(tmpdir(), 'vera-deepseek-host-preflight-'));
  chmodSync(root, 0o700);
  const receiptsParent = join(root, 'receipts-parent');
  const receiptRoot = join(receiptsParent, 'receipts');
  const cursorParent = join(root, 'receiver');
  const cursorPath = join(cursorParent, 'cursor.json');
  const runner = join(root, 'runner');
  mkdirSync(receiptsParent, { mode: 0o700 });
  mkdirSync(receiptRoot, { mode: 0o700 });
  mkdirSync(cursorParent, { mode: 0o700 });
  const runnerBytes = '#!/bin/sh\nexit 0\n';
  writeFileSync(runner, runnerBytes, { mode: 0o700 });
  chmodSync(runner, 0o700);
  const receiptPath = join(receiptRoot, 'existing-receipt.json');
  writeFileSync(receiptPath, '{"state":"reserved"}\n', { mode: 0o600 });
  chmodSync(receiptPath, 0o600);
  const adapterSha256 = createHash('sha256').update(runnerBytes).digest('hex');
  return { root, receiptsParent, receiptRoot, cursorParent, cursorPath, runner, receiptPath, adapterSha256 };
}

function optionsFor(value, options = {}) {
  return {
    runner: value.runner,
    adapterSha256: value.adapterSha256,
    receiptRoot: value.receiptRoot,
    cursorPath: value.cursorPath,
    env: { HOME: '/synthetic/home', PATH: '/private/path', ...options.env },
    spawn: options.spawn || (() => resultFor(value.adapterSha256)),
    allowEnabled: options.allowEnabled ?? false
  };
}

function stateOf(value) {
  return {
    runner: readFileSync(value.runner, 'utf8'),
    receiptNames: readdirSync(value.receiptRoot).sort(),
    receipt: readFileSync(value.receiptPath, 'utf8'),
    cursorExists: existsSync(value.cursorPath),
    modes: [value.receiptsParent, value.receiptRoot, value.cursorParent].map(path => statSync(path).mode & 0o777)
  };
}

function withFixture(run) {
  const value = fixture();
  try {
    run(value);
  } finally {
    rmSync(value.root, { recursive: true, force: true });
  }
}

test('host preflight uses a sanitized child environment and leaves receipt and cursor state untouched', () => {
  withFixture(value => {
    const before = stateOf(value);
    let invocation;
    const ready = hostPreflight(optionsFor(value, {
      env: {
        GITHUB_TOKEN: 'must-not-pass',
        DEEPSEEK_API_KEY: 'must-not-pass',
        VERA_DEEPSEEK_PROVIDER_KEY: 'must-not-pass'
      },
      spawn: (runner, args, options) => {
        invocation = { runner, args, options };
        return resultFor(value.adapterSha256);
      }
    }));
    assert.deepEqual(ready, contract(value.adapterSha256));
    assert.deepEqual(invocation.args, ['--host-preflight']);
    assert.equal(invocation.runner, value.runner);
    assert.deepEqual(invocation.options.env, {
      HOME: '/synthetic/home',
      PATH: '/usr/bin:/bin',
      VERA_DEEPSEEK_ADAPTER_SHA256: value.adapterSha256
    });
    assert.equal(invocation.options.maxBuffer, 16 * 1024);
    assert.equal(invocation.options.shell, false);
    assert.equal(invocation.options.timeout, 30_000);
    assert.deepEqual(stateOf(value), before);
  });
});

test('publication preflight refuses every enabled one-shot flag before invoking the runner', () => {
  for (const flag of [
    'VERA_DEEPSEEK_DISPATCH_ENABLED',
    'VERA_DEEPSEEK_LIVE_ENABLED',
    'VERA_DEEPSEEK_CONTINUATION_ENABLED',
    'VERA_DEEPSEEK_QUALITY_LIVE_ENABLED',
    'CONTINUATION_ENABLED',
    'QUALITY_LIVE_ENABLED'
  ]) {
    withFixture(value => {
      let calls = 0;
      assert.throws(
        () => hostPreflight(optionsFor(value, {
          env: { [flag]: 'true' },
          spawn: () => { calls += 1; return resultFor(value.adapterSha256); }
        })),
        /flags are enabled during publication preflight/
      );
      assert.equal(calls, 0);
    });
  }
});

test('explicit one-shot flags are accepted only with allowEnabled and are never forwarded to the child', () => {
  withFixture(value => {
    let childEnv;
    const ready = hostPreflight(optionsFor(value, {
      env: {
        VERA_DEEPSEEK_DISPATCH_ENABLED: 'true',
        VERA_DEEPSEEK_LIVE_ENABLED: 'true',
        CONTINUATION_ENABLED: 'true',
        QUALITY_LIVE_ENABLED: 'true',
        GITHUB_TOKEN: 'must-not-pass'
      },
      allowEnabled: true,
      spawn: (_runner, _args, options) => {
        childEnv = options.env;
        return resultFor(value.adapterSha256);
      }
    }));
    assert.equal(ready.ready, true);
    assert.deepEqual(Object.keys(childEnv).sort(), ['HOME', 'PATH', 'VERA_DEEPSEEK_ADAPTER_SHA256'].sort());
  });
});

test('runner must exist, be owner-only, executable, and match the approved hash', () => {
  withFixture(value => {
    const expected = value.adapterSha256;
    chmodSync(value.runner, 0o755);
    assert.throws(() => hostPreflight(optionsFor(value)), /owner-only executable regular file/);
    chmodSync(value.runner, 0o700);
    assert.throws(() => hostPreflight({ ...optionsFor(value), adapterSha256: 'a'.repeat(64) }), /SHA-256 does not match/);
    const missing = join(value.root, 'missing-runner');
    assert.throws(() => hostPreflight({ ...optionsFor(value), runner: missing }), error => {
      assert.match(error.message, /runner is unavailable/);
      assert.equal(error.message.includes(missing), false);
      return true;
    });
    assert.equal(value.adapterSha256, expected);
  });
});

test('runner symlinks and unavailable or unsafe storage are refused without invoking the child', () => {
  withFixture(value => {
    let calls = 0;
    const spawn = () => { calls += 1; return resultFor(value.adapterSha256); };
    const linked = join(value.root, 'runner-link');
    symlinkSync(value.runner, linked);
    assert.throws(() => hostPreflight({ ...optionsFor(value, { spawn }), runner: linked }), /owner-only executable regular file/);

    chmodSync(value.receiptsParent, 0o755);
    assert.throws(() => hostPreflight(optionsFor(value, { spawn })), /Receipt storage parent/);
    chmodSync(value.receiptsParent, 0o700);

    chmodSync(value.cursorParent, 0o755);
    assert.throws(() => hostPreflight(optionsFor(value, { spawn })), /Receiver cursor directory/);
    chmodSync(value.cursorParent, 0o700);

    assert.throws(() => hostPreflight({ ...optionsFor(value, { spawn }), receiptRoot: join(value.root, 'missing-receipts') }), /Receipt storage/);
    assert.equal(calls, 0);
  });
});

test('an existing cursor may be owner-readable 0400 when its parent is safely replaceable', () => {
  withFixture(value => {
    writeFileSync(value.cursorPath, '{"lastSeen":7}\n', { mode: 0o400 });
    chmodSync(value.cursorPath, 0o400);
    assert.equal(statSync(value.cursorPath).mode & 0o777, 0o400);
    assert.equal(hostPreflight(optionsFor(value)).ready, true);
    chmodSync(value.cursorPath, 0o600);
    assert.throws(() => hostPreflight(optionsFor(value)), /cursor file must be an owner-only regular file/);
    chmodSync(value.cursorPath, 0o644);
    assert.throws(() => hostPreflight(optionsFor(value)), /cursor file must be an owner-only regular file that is readable and safely replaceable/);
    rmSync(value.cursorPath);
    symlinkSync(value.receiptPath, value.cursorPath);
    assert.throws(() => hostPreflight(optionsFor(value)), /cursor file must be an owner-only regular file that is readable and safely replaceable/);
  });
});

test('child errors, oversized output, malformed JSON, and every contract drift fail safely', () => {
  withFixture(value => {
    const cases = [
      () => { throw new Error('private /Users/example/.codex path'); },
      () => ({ error: new Error('private /Users/example/.codex path'), status: null, stdout: '', stderr: '' }),
      () => ({ status: 1, signal: null, stdout: 'private path', stderr: '' }),
      () => ({ status: 0, signal: 'SIGTERM', stdout: '{}', stderr: '' }),
      () => ({ status: 0, stdout: 'x'.repeat(16 * 1024 + 1), stderr: '' }),
      () => ({ status: 0, stdout: '{}', stderr: 'x'.repeat(16 * 1024 + 1) }),
      () => ({ status: 0, stdout: 'private child output', stderr: '' }),
      () => ({ status: 0, stdout: JSON.stringify({ ...contract(value.adapterSha256), extra: true }), stderr: '' }),
      ...[
        { contract: 'wrong' }, { ready: false }, { adapterSha256: 'f'.repeat(64) },
        { defaultMode: 'enabled' }, { isolation: 'none' }, { accounting: 'per-task' }
      ].map(update => () => resultFor(value.adapterSha256, update))
    ];
    for (const makeResult of cases) {
      assert.throws(() => hostPreflight(optionsFor(value, { spawn: makeResult })), error => {
        assert.equal(error.message.includes(value.runner), false);
        assert.equal(error.message.includes('/Users/example/.codex'), false);
        assert.equal(error.message.includes('private child output'), false);
        return true;
      });
    }
  });
});


test('known private refusal codes map to actionable messages without exposing runner text or paths', () => {
  withFixture(value => {
    const reasons = {
      STATE_PERMISSIONS: /owner-only and owned by the current user/,
      STATE_ACCESS: /owner read\/write access/,
      ADAPTER_BUILD: /approved DeepSeek adapter build/,
      ACCOUNTING: /owner-only accounting ledger/,
      ISOLATION: /sandbox-exec availability/
    };
    for (const [reason, actionable] of Object.entries(reasons)) {
      const stdout = JSON.stringify({
        contract: 'VERA_DEEPSEEK_HOST_PREFLIGHT_V1', ready: false, reason
      });
      assert.throws(() => hostPreflight(optionsFor(value, {
        spawn: () => ({ status: 1, signal: null, stdout, stderr: '' })
      })), error => {
        assert.match(error.message, actionable);
        assert.equal(error.message.includes(value.runner), false);
        assert.equal(error.message.includes(reason), false);
        return true;
      });
    }
  });
});

test('unknown or malformed refusal codes fail closed without exposing the child payload', () => {
  withFixture(value => {
    const childPayload = 'PRIVATE=/Users/example/.codex/secret';
    for (const refusal of [
      { contract: 'VERA_DEEPSEEK_HOST_PREFLIGHT_V1', ready: false, reason: childPayload },
      { contract: 'VERA_DEEPSEEK_HOST_PREFLIGHT_V1', ready: false, reason: 'STATE_ACCESS', detail: childPayload }
    ]) {
      assert.throws(() => hostPreflight(optionsFor(value, {
        spawn: () => ({ status: 1, signal: null, stdout: JSON.stringify(refusal), stderr: childPayload })
      })), error => {
        assert.equal(error.message.includes(childPayload), false);
        assert.equal(error.message.includes('/Users/example/.codex'), false);
        return true;
      });
    }
  });
});

test('runner hash is checked again after the child returns', () => {
  withFixture(value => {
    assert.throws(() => hostPreflight(optionsFor(value, {
      spawn: () => {
        writeFileSync(value.runner, '#!/bin/sh\nexit 4\n', { mode: 0o700 });
        return resultFor(value.adapterSha256);
      }
    })), /changed during host preflight/);
  });
});
