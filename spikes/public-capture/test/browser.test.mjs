import assert from 'node:assert/strict';
import test from 'node:test';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { writeFile, readFile } from 'node:fs/promises';
import path from 'node:path';
import { prepareSandbox } from '../browser.mjs';
import { capture } from '../capture.mjs';
import { LocalStore } from '../store.mjs';
import { loadFixture, FIXTURE_URL } from '../transport.mjs';
import { temporaryStore } from './helpers.mjs';

const exec = promisify(execFile);

test('OS sandbox denies unrelated file reads and outbound/inbound sockets', async () => {
  const sandbox = await prepareSandbox();
  const sentinel = path.join(await temporaryStore(), 'sentinel');
  await writeFile(sentinel, 'synthetic sentinel, never a user secret');
  const deniedRead = await exec('/usr/bin/sandbox-exec', ['-f', sandbox.policyPath, '/bin/cat', sentinel]).then(() => false, (error) => error.stderr.includes('Operation not permitted'));
  assert.equal(deniedRead, true);
  // This executable is only a denial probe; no Chromium context or inherited
  // user profile is involved. Both socket operations must fail in the kernel.
  const probe = `const net=require('node:net');
    let denials=0; const done=(error)=>{if(error.code!=='EPERM'&&error.code!=='EACCES')process.exit(2);if(++denials===2)console.log('two-kernel-denials');};
    net.createConnection({host:'127.0.0.1',port:9}).on('error',done);
    net.createServer().on('error',done).listen(0,'127.0.0.1');`;
  const { stdout } = await exec('/usr/bin/sandbox-exec', ['-f', sandbox.policyPath, '/usr/local/bin/node', '-e', probe], { timeout: 5000 });
  assert.equal(stdout.trim(), 'two-kernel-denials');
});

test('real Chromium: complete receipts, unchanged/changed recaptures, no cookie state', async () => {
  const root = await temporaryStore();
  for (const [command, fixtureName] of [['one', 'article-v1'], ['two', 'article-v1'], ['three', 'article-v2']]) {
    const result = await capture({ root, command, fixtureName });
    assert.equal(result.result, 'committed', JSON.stringify(result));
    assert.equal(result.status, 'ready');
  }
  const rows = await new LocalStore(root).history();
  assert.deepEqual(rows.map((row) => row.receipt.change.signal), ['initial_observation', 'same_exact_bytes', 'different_exact_bytes']);
  assert.ok(rows[0].raster.equals(rows[1].raster));
  assert.ok(!rows[0].raster.equals(rows[2].raster));
  assert.equal(new Set(rows.map((row) => row.receipt.runtime.cleanProfileId)).size, 3);
  for (const { receipt, commit } of rows) {
    for (const group of ['identity', 'authorization', 'request', 'network', 'runtime', 'timing', 'output', 'honesty', 'lease', 'change']) assert.ok(receipt[group], group);
    assert.equal(receipt.network.actualConnections, 0);
    assert.equal(receipt.runtime.initialCookies, 0);
    assert.equal(receipt.runtime.finalCookies, 0);
    assert.equal(receipt.runtime.importedState, false);
    assert.equal(receipt.runtime.outerSandbox, 'inherited-seatbelt');
    assert.equal(receipt.honesty.observation_not_reproduction, true);
    assert.equal(receipt.output.artifact.sha256, commit.artifact.sha256);
  }
  const initial = await readFile(path.join(root, rows[0].commit.artifact.path));
  assert.ok(initial.equals(rows[0].raster));
});

test('real Chromium: forbidden resources are review-required and cookie setters never survive', async () => {
  const root = await temporaryStore();
  const fixture = await loadFixture('hostile');
  fixture.routes.get(FIXTURE_URL).headers = { 'set-cookie': 'credential=SHOULD_NOT_BE_IMPORTED; Secure' };
  const result = await capture({ root, command: 'hostile', fixture });
  assert.equal(result.result, 'committed', JSON.stringify(result));
  assert.equal(result.status, 'review_required');
  const [{ receipt }] = await new LocalStore(root).history();
  assert.ok(receipt.honesty.warnings.includes('ip_literal_denied'));
  assert.ok(receipt.honesty.warnings.includes('offline_fixture_missing'));
  assert.equal(receipt.runtime.finalCookies, 0);
  assert.equal(receipt.runtime.javaScript, 'disabled');
  const next = await capture({ root, command: 'clean-again' });
  assert.equal(next.status, 'ready');
});
