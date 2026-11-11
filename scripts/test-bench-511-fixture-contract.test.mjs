// #510 -> #511: immutable, deliberately synthetic and publicly keyed fixture
// demonstrations. Never import these keys into an actual verifier or sender.
import assert from 'node:assert/strict';
import { Buffer } from 'node:buffer';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath, URL } from 'node:url';
import test from 'node:test';

import { createTerminalOutbox } from './test-bench-terminal-outbox.mjs';

const dir = fileURLToPath(new URL('./fixtures/test-bench-510/', import.meta.url));
const manifest = JSON.parse(readFileSync(path.join(dir, 'manifest.json'), 'utf8'));
const cases = { verified: 'VERIFIED', failed: 'FAILED', unknown: 'UNKNOWN' };

function store(t, time = manifest.frozenNow, receiptKey = Buffer.alloc(32, 73)) {
  const home = mkdtempSync(path.join(tmpdir(), 'vera-510-handoff-'));
  t.after(() => rmSync(home, { recursive: true, force: true }));
  return createTerminalOutbox({
    filePath: path.join(home, 'outbox', 'signed-fixtures.enc.json'),
    receiptKeys: {
      'fixture-only-verifier': { provenance: 'signed-read-only', key: receiptKey },
    },
    eventKey: Buffer.alloc(32, 74), encryptionKey: Buffer.alloc(32, 75),
    now: () => time,
  });
}

test('#511: pinned test-only signed VERIFIED, FAILED and UNKNOWN cases retain exact immutable semantics', t => {
  const outbox = store(t);
  const ids = new Set();
  assert.equal(manifest.scope, 'TEST_ONLY_SIGNED_READ_ONLY_FIXTURES_NOT_NATIVE_EVIDENCE');
  for (const [name, outcome] of Object.entries(cases)) {
    const fixturePath = path.join(dir, name + '.signed.json');
    const pin = manifest.fixtureSha256[name + '.signed.json'];
    const before = readFileSync(fixturePath);
    const result = outbox.ingestSignedFixture({ fixturePath, sha256: pin });
    const { event, audit } = outbox.inspect(result.eventId);
    assert.equal(event.outcome, outcome);
    assert.equal(event.provenance, 'signed-read-only');
    assert.equal(event.strict312Verdict, 'UNPROVED');
    assert.equal(event.acceptanceAuthority, 'none');
    assert.equal(audit.status, 'persisted');
    assert.deepEqual(audit.history.map(x => x.state), ['persisted']);
    assert.equal(outbox.ingestSignedFixture({ fixturePath, sha256: pin }).duplicate, true);
    assert.deepEqual(readFileSync(fixturePath), before);
    assert.equal(ids.has(result.eventId), false);
    ids.add(result.eventId);
    // A separately pinned read-only event is never a simulation input.
    assert.throws(() => outbox.ingestSimulation(JSON.parse(before)), /route/i);
  }
  assert.equal(ids.size, 3);
});

test('#511: pinned fixture mutation, expired attestation and changed trusted key fail closed', t => {
  const fixturePath = path.join(dir, 'verified.signed.json');
  const pin = manifest.fixtureSha256['verified.signed.json'];
  assert.throws(() => store(t).ingestSignedFixture({ fixturePath, sha256: '0'.repeat(64) }), /digest/i);
  assert.throws(() => store(t, manifest.frozenNow + 61_000).ingestSignedFixture({ fixturePath, sha256: pin }), /expired/i);
  assert.throws(() => store(t, manifest.frozenNow, Buffer.alloc(32, 99))
    .ingestSignedFixture({ fixturePath, sha256: pin }), /signature/i);
  const forged = store(t);
  assert.throws(() => forged.ingestSimulation(JSON.parse(readFileSync(fixturePath))), /route/i);
});
