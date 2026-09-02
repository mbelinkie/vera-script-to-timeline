import assert from 'node:assert/strict';
import test from 'node:test';
import { readFile, readdir, writeFile, symlink } from 'node:fs/promises';
import path from 'node:path';
import { capture } from '../capture.mjs';
import { LocalStore, verifyPng } from '../store.mjs';
import { PROFILE, hash } from '../profile.mjs';
import { temporaryStore, stubRender } from './helpers.mjs';

test('new observations make distinct immutable revisions, exact bytes alone are reused', async () => {
  const root = await temporaryStore();
  const first = await capture({ root, command: 'one', render: stubRender() });
  assert.equal(first.result, 'committed');
  await writeFile(path.join(root, 'commits', '.DS_Store'), 'Finder metadata');
  const original = await new LocalStore(root).history();
  const originalReceiptHash = hash(await readFile(path.join(root, 'commits', original[0].directory, 'provenance.json')));
  const same = await capture({ root, command: 'two', render: stubRender() });
  const changed = await capture({ root, command: 'three', render: stubRender(99) });
  assert.equal(same.artifact.path, first.artifact.path);
  assert.notEqual(changed.artifact.path, first.artifact.path);
  const rows = await new LocalStore(root).history();
  assert.deepEqual(rows.map((row) => row.receipt.change.signal), ['initial_observation', 'same_exact_bytes', 'different_exact_bytes']);
  assert.equal(new Set(rows.map((row) => row.commit.attemptId)).size, 3);
  assert.equal(new Set(rows.map((row) => row.commit.revisionId)).size, 3);
  assert.equal(hash(rows[0].raster), hash(original[0].raster));
  assert.equal(hash(await readFile(path.join(root, 'commits', rows[0].directory, 'provenance.json'))), originalReceiptHash);
  assert.ok(rows.every((row) => row.receipt.selection === 'unselected'));
});

test('duplicate command never runs a second browser even if fixture bytes changed', async () => {
  const root = await temporaryStore();
  const first = await capture({ root, command: 'one', render: stubRender() });
  const duplicate = await capture({ root, command: 'one', fixtureName: 'article-v2', render: async () => { assert.fail('must not render'); } });
  assert.equal(duplicate.duplicate, true);
  assert.equal(first.revisionId, duplicate.revisionId);
  assert.equal((await new LocalStore(root).history()).length, 1);
});

test('unsafe initial URL never launches browser and rejection never stores its secret', async () => {
  const root = await temporaryStore();
  for (const [index, url] of ['http://127.0.0.1/', 'https://capture.example.org/?token=DO_NOT_RETAIN_THIS_SECRET', 'file:///private/secret'].entries()) {
    const result = await capture({ root, command: `unsafe-${index}`, url, render: async () => { assert.fail('must not navigate'); } });
    assert.equal(result.result, 'failed'); assert.equal(result.navigationStarted, false);
    const job = await readFile(path.join(root, 'jobs', result.jobId, 'outcome.json'), 'utf8');
    assert.ok(!job.includes('DO_NOT_RETAIN_THIS_SECRET'));
  }
  assert.equal((await new LocalStore(root).history()).length, 0);
});

test('malformed PNG, oversized dimensions, missing provenance, and browser crash never publish', async () => {
  for (const bad of ['format', 'dimensions', 'interlace', 'crc', 'provenance', 'crash']) {
    const root = await temporaryStore();
    const render = async (args) => {
      if (bad === 'crash') throw new Error('untrusted SECRET page/browser diagnostic');
      const output = await stubRender()(args);
      if (bad === 'format') output.raster = Buffer.from('not PNG');
      if (bad === 'dimensions') output.raster.writeUInt32BE(PROFILE.limits.pixels, 16);
      if (bad === 'interlace') output.raster[28] = 1;
      if (bad === 'crc') output.raster[29] ^= 1;
      if (bad === 'provenance') delete output.runtime;
      return output;
    };
    const result = await capture({ root, command: 'one', render });
    assert.equal(result.result, 'failed', bad);
    assert.equal((await new LocalStore(root).history()).length, 0);
    assert.ok(!JSON.stringify(result).includes('SECRET'));
  }
  assert.throws(() => verifyPng(Buffer.alloc(0)));
});

test('corrupted retained bytes or receipt are an integrity incident, never overwritten', async () => {
  for (const corrupt of ['artifact.png', 'provenance.json']) {
    const root = await temporaryStore();
    await capture({ root, command: 'one', render: stubRender() });
    const directory = (await readdir(path.join(root, 'commits')))[0];
    const file = path.join(root, 'commits', directory, corrupt);
    await writeFile(file, 'intentional corruption in test-owned output');
    await assert.rejects(capture({ root, command: 'two', render: stubRender() }));
    assert.equal(await readFile(file, 'utf8'), 'intentional corruption in test-owned output');
    assert.equal((await readdir(path.join(root, 'commits'))).length, 1);
  }
});

test('exclusive OS lock rejects overlapping writer and releases after completion', async () => {
  const root = await temporaryStore();
  const store = new LocalStore(root);
  await store.locked(async () => {
    await assert.rejects(capture({ root, command: 'one', render: stubRender() }), /store_busy/);
  });
  assert.equal((await capture({ root, command: 'one', render: stubRender() })).result, 'committed');
});

test('symlink store is not followed', async () => {
  const root = await temporaryStore();
  const link = path.join(await temporaryStore(), 'link');
  await symlink(root, link);
  await assert.rejects(capture({ root: link, command: 'one', render: stubRender() }), /store_must_be_private/);
});

test('publication exceptions retain no partial commit; lost reply returns existing commit', async () => {
  for (const point of ['after-artifact-stage', 'after-provenance-stage', 'before-publish', 'after-publish']) {
    const root = await temporaryStore();
    const result = await capture({ root, command: 'one', render: stubRender(), hit: async (where) => { if (where === point) throw new Error('injected failure'); } });
    assert.equal(result.result, point === 'after-publish' ? 'committed' : 'failed');
    assert.equal((await new LocalStore(root).history()).length, point === 'after-publish' ? 1 : 0);
    const replay = await capture({ root, command: 'one', render: async () => assert.fail('no implicit retry') });
    assert.equal(replay.result, result.result);
  }
});
