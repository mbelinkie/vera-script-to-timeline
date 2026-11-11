import assert from 'node:assert/strict';
import { Buffer } from 'node:buffer';
import { randomUUID } from 'node:crypto';
import { mkdtempSync, readFileSync, chmodSync, rmSync, statSync, symlinkSync, writeFileSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';

import { createOriginRegistry, signOriginAssertion } from './test-bench-origin-registry.mjs';

const NOW = Date.parse('2026-11-11T16:00:00Z');
const SIGNING_KEY = Buffer.alloc(32, 17);
const ENCRYPTION_KEY = Buffer.alloc(32, 29);
const ISSUER = 'verified-codex-bridge';

function origin(overrides = {}) {
  const ownerId = overrides.ownerId ?? 'private-owner-123';
  const threadId = overrides.threadId ?? 'private-thread-456';
  return {
    platform: 'codex', ownerId, threadId,
    repository: 'mbelinkie/vera-script-to-timeline', issueNumber: 510, pullNumber: 512,
    jobId: 'job-abc', caseId: 'case-def', operationId: 'operation-ghi',
    sourceSha256: 'a'.repeat(64), actorSha256: 'b'.repeat(64),
    authorizationScope: 'test-bench.terminal-result-delivery', authorizationExpiresAt: NOW + 86_400_000,
    callbackRoute: { kind: 'exact-thread', platform: 'codex', ownerId, threadId },
    correlationId: 'a17d6edb-c200-442d-8bdd-f0d4573ab789',
    ...overrides,
  };
}

function assertion(binding = origin(), purpose = 'register', overrides = {}, key = SIGNING_KEY) {
  return signOriginAssertion({
    version: 1, purpose, issuer: ISSUER, binding, nonce: randomUUID(),
    issuedAt: NOW - 1000, expiresAt: NOW + 60_000, ...overrides,
  }, key);
}

function fixture(t) {
  const dir = mkdtempSync(path.join(os.tmpdir(), 'vera-510-private-'));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  const filePath = path.join(dir, 'private', 'origins.enc.json');
  const registry = () => createOriginRegistry({ filePath, signingKey: SIGNING_KEY,
    encryptionKey: ENCRYPTION_KEY, trustedIssuers: { [ISSUER]: 'codex' }, now: () => NOW });
  return { filePath, registry };
}

test('binds a verified origin; only a new exact signed assertion resolves its private route', t => {
  const { filePath, registry } = fixture(t);
  const store = registry();
  const binding = origin();
  const receipt = store.registerOrigin(assertion(binding));
  assert.equal(receipt.correlationId, binding.correlationId);
  assert.equal(Object.hasOwn(receipt, 'threadId'), false);
  assert.deepEqual(store.resolveOrigin(assertion(binding, 'resolve')), binding);
  const disk = readFileSync(filePath, 'utf8');
  assert.doesNotMatch(disk, /private-owner|private-thread|job-abc|operation-ghi/);
  assert.equal((statSync(filePath).mode & 0o777), 0o600);
});

test('rejects unknown destination, incorrect owner or thread, foreign operation and stale source', t => {
  const { registry } = fixture(t);
  const store = registry();
  assert.throws(() => store.resolveOrigin(assertion(origin(), 'resolve')), /unknown/i);
  const binding = origin();
  store.registerOrigin(assertion(binding));
  for (const mismatch of [
    { ownerId: 'foreign-owner' }, { threadId: 'foreign-thread' }, { operationId: 'different-operation' },
    { sourceSha256: 'c'.repeat(64) }, { actorSha256: 'd'.repeat(64) }, { issueNumber: 999 },
    { correlationId: randomUUID() },
  ]) assert.throws(() => store.resolveOrigin(assertion(origin(mismatch), 'resolve')), /unknown|mismatch/i);
});

test('tampering, untrusted issuers, expired/future claims and wrong purpose fail closed', t => {
  const { registry } = fixture(t);
  const store = registry();
  const signed = assertion();
  assert.throws(() => store.registerOrigin({ ...signed, binding: origin({ sourceSha256: 'c'.repeat(64) }) }), /signature/i);
  assert.throws(() => store.registerOrigin(assertion(origin(), 'register', {}, Buffer.alloc(32, 99))), /signature/i);
  assert.throws(() => store.registerOrigin(assertion(origin(), 'register', { issuer: 'random-actor' })), /issuer/i);
  assert.throws(() => store.registerOrigin(assertion(origin({ platform: 'chatgpt', callbackRoute: {
    kind: 'exact-thread', platform: 'chatgpt', ownerId: 'private-owner-123', threadId: 'private-thread-456',
  } }))), /issuer|platform/i);
  assert.throws(() => store.registerOrigin(assertion(origin(), 'register', { expiresAt: NOW - 1 })), /expired|time/i);
  assert.throws(() => store.registerOrigin(assertion(origin(), 'register', { issuedAt: NOW + 60_000 })), /future|time/i);
  assert.throws(() => store.registerOrigin(assertion(origin(), 'resolve')), /purpose/i);
});

test('registration and resolution assertions are single-use, including after restart', t => {
  const { registry } = fixture(t);
  const signed = assertion();
  registry().registerOrigin(signed);
  assert.throws(() => registry().registerOrigin(signed), /replay/i);
  const resolve = assertion(origin(), 'resolve');
  registry().resolveOrigin(resolve);
  assert.throws(() => registry().resolveOrigin(resolve), /replay/i);
});

test('two bindings cannot claim the same correlation or job/case/operation identity', t => {
  const { registry } = fixture(t);
  registry().registerOrigin(assertion());
  assert.throws(() => registry().registerOrigin(assertion()), /conflict|duplicate/i);
  assert.throws(() => registry().registerOrigin(assertion(origin({ correlationId: randomUUID(), ownerId: 'another-owner',
    callbackRoute: { kind: 'exact-thread', platform: 'codex', ownerId: 'another-owner', threadId: 'private-thread-456' } }))), /conflict|duplicate/i);
});

test('invalid, redirecting or ambiguous scopes and callbacks are forbidden', t => {
  const { registry } = fixture(t);
  for (const invalid of [
    { authorizationScope: 'all' },
    { callbackRoute: { kind: 'https', url: 'https://evil.example/x' } },
    { callbackRoute: { kind: 'exact-thread', platform: 'zodex', ownerId: 'private-owner-123', threadId: 'private-thread-456' } },
    { callbackRoute: { kind: 'exact-thread', platform: 'codex', ownerId: 'private-owner-123', threadId: 'other-thread' } },
    { threadId: 'bad\nnewline' }, { threadId: 'path/../other-thread' }, { sourceSha256: 'not-a-hash' },
    { privateExtra: 'unexpected' },
  ]) assert.throws(() => registry().registerOrigin(assertion(origin(invalid))), /invalid|callback|scope|field/i);
});

test('private file permission failures and corrupted ciphertext do not reset to an empty store', t => {
  const { filePath, registry } = fixture(t);
  registry().registerOrigin(assertion());
  chmodSync(filePath, 0o644);
  assert.throws(() => registry().resolveOrigin(assertion(origin(), 'resolve')), /permission|private/i);
  chmodSync(filePath, 0o600);
  writeFileSync(filePath, '{}');
  assert.throws(() => registry().resolveOrigin(assertion(origin(), 'resolve')), /integrity|encrypted|corrupt|invalid/i);
});

test('symlink storage path is rejected rather than followed', t => {
  const { filePath, registry } = fixture(t);
  registry().registerOrigin(assertion());
  const target = path.join(path.dirname(filePath), 'other');
  writeFileSync(target, 'not the registry');
  rmSync(filePath);
  symlinkSync(target, filePath);
  assert.throws(() => registry().registerOrigin(assertion()), /symlink|symbolic/i);
});

test('concurrent writer lock is never silently stolen, and the registered origin survives', t => {
  const { filePath, registry } = fixture(t);
  registry().registerOrigin(assertion());
  writeFileSync(`${filePath}.lock`, 'other writer', { mode: 0o600 });
  assert.throws(() => registry().resolveOrigin(assertion(origin(), 'resolve')), /locked/i);
  rmSync(`${filePath}.lock`);
  assert.deepEqual(registry().resolveOrigin(assertion(origin(), 'resolve')), origin());
});

test('expired authorization never resolves, even when fresh assertions are signed', t => {
  const { filePath, registry } = fixture(t);
  const binding = origin({ authorizationExpiresAt: NOW + 5000 });
  registry().registerOrigin(assertion(binding));
  const later = createOriginRegistry({ filePath, signingKey: SIGNING_KEY, encryptionKey: ENCRYPTION_KEY,
    trustedIssuers: { [ISSUER]: 'codex' }, now: () => NOW + 6000 });
  assert.throws(() => later.resolveOrigin(assertion(binding, 'resolve', {
    issuedAt: NOW + 5990, expiresAt: NOW + 8000,
  })), /expired/i);
});
