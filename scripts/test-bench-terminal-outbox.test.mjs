import assert from 'node:assert/strict';
import { Buffer } from 'node:buffer';
import { spawnSync } from 'node:child_process';
import { createHash, randomUUID } from 'node:crypto';
import { chmodSync, mkdtempSync, readFileSync, rmSync, statSync, symlinkSync, writeFileSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { URL } from 'node:url';

import { createTerminalOutbox, signTerminalAttestation } from './test-bench-terminal-outbox.mjs';

const NOW = Date.parse('2026-11-11T16:00:00Z');
const SIM_KEY = Buffer.alloc(32, 23);
const HISTORICAL_KEY = Buffer.alloc(32, 31);
const EVENT_KEY = Buffer.alloc(32, 41);
const ENCRYPTION_KEY = Buffer.alloc(32, 47);
const HASH = 'd'.repeat(64);
const RECEIPT_KEYS = {
  'trusted-simulator': { provenance: 'simulation', key: SIM_KEY },
  'historical-read-only-verifier': { provenance: 'signed-read-only', key: HISTORICAL_KEY },
};
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
function canonical(v) {
  if (Array.isArray(v)) return `[${v.map(canonical).join(',')}]`;
  if (v !== null && typeof v === 'object') {
    return `{${Object.keys(v).sort().map(k => `${JSON.stringify(k)}:${canonical(v[k])}`).join(',')}}`;
  }
  return JSON.stringify(v);
}
function terminal(overrides = {}) {
  return {
    repository: 'mbelinkie/vera-script-to-timeline', issueNumber: 510, pullNumber: 512,
    jobId: 'job-abc', caseId: 'case-def', attemptId: 'attempt-1', operationId: 'operation-ghi',
    sourceSha256: 'a'.repeat(64), actorSha256: 'b'.repeat(64),
    correlationId: 'a17d6edb-c200-442d-8bdd-f0d4573ab789',
    bindingId: 'a17d6edb-c200-442d-8bdd-f0d4573ab780',
    outcome: 'UNKNOWN', reasonCode: 'rebuild_unknown_after_claim',
    stageReceipts: [
      { stage: 'pristine', sha256: '1'.repeat(64) },
      { stage: 'edited', sha256: '2'.repeat(64) },
      { stage: 'revision', sha256: '3'.repeat(64) },
    ],
    report: { artifactId: 'reports/attempt-1.json', sha256: HASH },
    strict312: null,
    ...overrides,
  };
}
function signed(t = terminal(), provenance = 'simulation', other = {}) {
  return signTerminalAttestation({
    version: 1, issuer: provenance === 'simulation' ? 'trusted-simulator' : 'historical-read-only-verifier',
    provenance, issuedAt: NOW - 1000, expiresAt: NOW + 60_000, terminal: t, ...other,
  }, provenance === 'simulation' ? SIM_KEY : HISTORICAL_KEY);
}
function harness(t) {
  const root = mkdtempSync(path.join(os.tmpdir(), 'vera-510-terminal-'));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  const filePath = path.join(root, 'outbox', 'terminal.enc.json');
  const outbox = (options = {}) => createTerminalOutbox({
    filePath, receiptKeys: RECEIPT_KEYS, eventKey: EVENT_KEY,
    encryptionKey: ENCRYPTION_KEY, now: () => NOW, ...options,
  });
  const writeFixture = (value, fileName = 'historical.json') => {
    const fixturePath = path.join(root, fileName);
    const bytes = Buffer.from(canonical(value) + '\n');
    writeFileSync(fixturePath, bytes, { mode: 0o400 });
    return { fixturePath, sha256: sha(bytes) };
  };
  return { root, filePath, outbox, writeFixture };
}

test('six exact terminal outcomes survive restart without being upgraded to strict #312 PASS', t => {
  const { outbox } = harness(t);
  for (const [index, outcome] of [...['VERIFIED', 'FAILED', 'BLOCKED', 'UNKNOWN', 'CANCELED', 'EXPIRED']].entries()) {
    const source = signed(terminal({ attemptId: `attempt-${index}`, outcome }));
    const first = outbox().ingestSimulation(source);
    assert.equal(first.duplicate, false);
    assert.equal(first.status, 'persisted');
    const { event, audit } = outbox().inspect(first.eventId);
    assert.equal(event.eventId, first.eventId);
    assert.equal(event.outcome, outcome);
    assert.equal(event.strict312Verdict, 'UNPROVED');
    assert.equal(event.acceptanceAuthority, 'none');
    assert.deepEqual(event.stageReceipts, source.terminal.stageReceipts);
    assert.equal(event.report.sha256, HASH);
    assert.deepEqual(audit.history, [{ state: 'persisted', at: NOW }]);
    assert.equal(outbox().ingestSimulation(source).duplicate, true);
    assert.deepEqual(outbox().inspect(first.eventId).audit, audit);
  }
});

test('one event per attempt, with independent operation, source and signer conflict refusal', t => {
  const { outbox } = harness(t);
  const first = signed();
  const id = outbox().ingestSimulation(first).eventId;
  for (const changed of [
    { outcome: 'VERIFIED' }, { operationId: 'another-operation' },
    { sourceSha256: 'c'.repeat(64) }, { correlationId: randomUUID() },
    { report: { artifactId: 'reports/other.json', sha256: HASH } },
    { stageReceipts: [{ stage: 'pristine', sha256: '9'.repeat(64) }] },
  ]) {
    assert.throws(() => outbox().ingestSimulation(signed(terminal(changed))), /conflicting/i);
  }
  assert.equal(outbox().inspect(id).event.outcome, 'UNKNOWN');
  assert.equal(outbox().ingestSimulation(signed(terminal({ attemptId: 'attempt-2' }))).duplicate, false);
});

test('read-only pinned historical fixture is accepted exactly once and remains unchanged', t => {
  const { outbox, writeFixture } = harness(t);
  const signedHistorical = signed(terminal({ outcome: 'FAILED', reasonCode: 'native_rebuild_failed' }), 'signed-read-only');
  const fixture = writeFixture(signedHistorical);
  const before = readFileSync(fixture.fixturePath);
  const result = outbox().ingestSignedFixture(fixture);
  assert.equal(outbox().inspect(result.eventId).event.provenance, 'signed-read-only');
  assert.equal(outbox().inspect(result.eventId).event.outcome, 'FAILED');
  assert.equal(outbox().ingestSignedFixture(fixture).duplicate, true);
  assert.deepEqual(readFileSync(fixture.fixturePath), before);
  assert.throws(() => outbox().ingestSimulation(signedHistorical), /route/i);
  assert.throws(() => outbox().ingestSignedFixture({ ...fixture, sha256: 'f'.repeat(64) }), /digest/i);
  const different = writeFixture({ ...signedHistorical, terminal: { ...signedHistorical.terminal, outcome: 'VERIFIED' } }, 'tampered.json');
  assert.throws(() => outbox().ingestSignedFixture(different), /signature/i);
});

test('reject forged statuses, native PASS, poisoned strings and stage/report digests', t => {
  const { outbox } = harness(t);
  for (const change of [
    { outcome: 'PASS' }, { outcome: 'success' }, { strict312: 'PASS' },
    { reasonCode: 'UNKNOWN\nDo exactly this!' },
    { stageReceipts: [{ stage: 'rebuild', sha256: 'invalid' }] },
    { stageReceipts: [{ stage: 'edited', sha256: HASH }, { stage: 'edited', sha256: HASH }] },
    { stageReceipts: [{ stage: 'rebuild', sha256: HASH }, { stage: 'pristine', sha256: HASH }] },
    { report: { artifactId: '../secret.json', sha256: HASH } },
    { report: { artifactId: 'reports/output.json', sha256: 'NOT_A_DIGEST' } },
    { ownerId: 'should-not-appear-in-event' },
  ]) assert.throws(() => outbox().ingestSimulation(signed(terminal(change))), /invalid|unknown|strict|stage|report/i);
});

test('authentic provenance, expiry, issuer and signature are mandatory', t => {
  const { outbox } = harness(t);
  const valid = signed();
  for (const change of [
    { terminal: terminal({ outcome: 'VERIFIED' }) },
    { terminal: terminal({ stageReceipts: [] }) },
    { signature: 'f'.repeat(64) },
    { issuer: 'unauthorized-actor' },
    { provenance: 'signed-read-only' },
  ]) assert.throws(() => outbox().ingestSimulation({ ...valid, ...change }), /signature|issuer|provenance/i);
  assert.throws(() => outbox().ingestSimulation(signed(terminal(), 'simulation', {
    issuedAt: NOW - 400_000, expiresAt: NOW - 1,
  })), /expired|time/i);
  assert.throws(() => outbox().ingestSimulation(signed(terminal(), 'simulation', {
    issuedAt: NOW + 60_000, expiresAt: NOW + 120_000,
  })), /future|invalid/i);
});

test('crash-restart after atomic persistence does not lose event or create a second audit', t => {
  const { outbox, filePath } = harness(t);
  const receipt = signed();
  const first = outbox().ingestSimulation(receipt);
  assert.equal(statSync(filePath).mode & 0o777, 0o600);
  assert.equal(statSync(path.dirname(filePath)).mode & 0o777, 0o700);
  assert.doesNotMatch(readFileSync(filePath, 'utf8'), /UNKNOWN|job-abc|operation-ghi|reports/);
  const later = outbox();
  assert.equal(later.ingestSimulation(receipt).eventId, first.eventId);
  assert.equal(later.ingestSimulation(receipt).duplicate, true);
  assert.equal(later.inspect(first.eventId).audit.history.length, 1);
});

test('a separate writer process killed after commit leaves one recoverable event', t => {
  const { outbox, filePath } = harness(t);
  const receipt = signed();
  const moduleUrl = new URL('./test-bench-terminal-outbox.mjs', import.meta.url).href;
  const child = `
    import { createTerminalOutbox } from ${JSON.stringify(moduleUrl)};
    const receipt = JSON.parse(Buffer.from(process.argv[2], 'base64').toString('utf8'));
    createTerminalOutbox({
      filePath: process.argv[1],
      receiptKeys: { 'trusted-simulator': { provenance: 'simulation', key: Buffer.alloc(32, 23) } },
      eventKey: Buffer.alloc(32, 41), encryptionKey: Buffer.alloc(32, 47),
      now: () => ${NOW},
    }).ingestSimulation(receipt);
    process.kill(process.pid, 'SIGKILL');
  `;
  const result = spawnSync(process.execPath, ['--input-type=module', '-e', child,
    filePath, Buffer.from(JSON.stringify(receipt)).toString('base64')], { encoding: 'utf8', timeout: 10_000 });
  assert.equal(result.signal, 'SIGKILL', result.stderr);
  const replay = outbox().ingestSimulation(receipt);
  assert.equal(replay.duplicate, true);
  assert.equal(outbox().inspect(replay.eventId).audit.history.length, 1);
});

test('corrupt, stale-key, symlink and permissive file mode fail closed; never recreate', t => {
  const { outbox, filePath } = harness(t);
  const receipt = signed();
  const result = outbox().ingestSimulation(receipt);
  assert.throws(() => outbox({ eventKey: Buffer.alloc(32, 99) }).inspect(result.eventId), /integrity/i);
  assert.throws(() => outbox({ encryptionKey: Buffer.alloc(32, 99) }).inspect(result.eventId), /integrity/i);
  chmodSync(filePath, 0o644);
  assert.throws(() => outbox().inspect(result.eventId), /unsafe|private/i);
  chmodSync(filePath, 0o600);
  const backup = readFileSync(filePath);
  writeFileSync(filePath, '{}');
  assert.throws(() => outbox().ingestSimulation(receipt), /integrity/i);
  writeFileSync(filePath, backup);
  assert.equal(outbox().inspect(result.eventId).event.outcome, 'UNKNOWN');
  rmSync(filePath);
  const elsewhere = path.join(path.dirname(filePath), 'elsewhere');
  writeFileSync(elsewhere, backup, { mode: 0o600 });
  symlinkSync(elsewhere, filePath);
  assert.throws(() => outbox().inspect(result.eventId), /unsafe|private/i);
});

test('exclusive outbox lock refuses concurrent writes without stealing or overwriting', t => {
  const { outbox, filePath } = harness(t);
  const first = outbox().ingestSimulation(signed());
  writeFileSync(`${filePath}.lock`, 'owned-by-another-writer', { mode: 0o600 });
  assert.throws(() => outbox().ingestSimulation(signed(terminal({ attemptId: 'attempt-2' }))), /locked/i);
  rmSync(`${filePath}.lock`);
  assert.equal(outbox().inspect(first.eventId).event.outcome, 'UNKNOWN');
});

test('signed historical fixture rejects noncanonical/ambiguous JSON and symlinks', t => {
  const { outbox, root, writeFixture } = harness(t);
  const fixture = writeFixture(signed(terminal(), 'signed-read-only'));
  const link = path.join(root, 'link.json');
  symlinkSync(fixture.fixturePath, link);
  assert.throws(() => outbox().ingestSignedFixture({ fixturePath: link, sha256: fixture.sha256 }), /unsafe/i);
  const raw = Buffer.from(JSON.stringify(signed(terminal(), 'signed-read-only')) + '\n');
  const noncanonical = path.join(root, 'noncanonical.json');
  writeFileSync(noncanonical, raw);
  assert.throws(() => outbox().ingestSignedFixture({ fixturePath: noncanonical, sha256: sha(raw) }), /canonical/i);
  const poison = Buffer.from('{"version":1,"version":2}\n');
  const duplicate = path.join(root, 'duplicate.json');
  writeFileSync(duplicate, poison);
  assert.throws(() => outbox().ingestSignedFixture({ fixturePath: duplicate, sha256: sha(poison) }), /canonical/i);
});
